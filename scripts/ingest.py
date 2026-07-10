"""Standalone Herald match ingest script.

PONYTAIL MODE: one file, stdlib sqlite3, sync httpx, no new dependencies, no
dataclasses, dicts throughout. Discovers recent Herald matches on OpenDota,
enriches them via Stratz GraphQL, stores them in a local SQLite DB with
derived sort/filter columns + raw JSON per match, prunes old data, retries a
pending queue, and exposes a load_matches() reader that returns the exact
dict shape the menu-v2 board consumes.

Do NOT import from functions.py/constants.py — those enforce env vars at
import time, which would break --selfcheck (must run with no env vars set).
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("ingest")

# --- CONSTANTS ---

OD_URL = "https://api.opendota.com/api/publicMatches"
EXPLORER_URL = "https://api.opendota.com/api/explorer"
STRATZ_URL = "https://api.stratz.com/graphql"
RAPIER_ID = 133
# NONE = played through; DISCONNECTED = brief dc but returned (game still valid).
# Anything else (ABANDONED, AFK, NEVER_CONNECTED*, DISCONNECTED_TOO_LONG) = abandon.
LEAVER_OK = {None, "NONE", "DISCONNECTED"}
# 30-60 min = the ordinary-game band, not review material. Keep the short
# stomps (<30) and the marathon disasters (>60).
DUR_SKIP_LO = int(os.environ.get("DUR_SKIP_LO", "1800"))
DUR_SKIP_HI = int(os.environ.get("DUR_SKIP_HI", "3600"))


def dur_boring(seconds):
    return DUR_SKIP_LO <= seconds <= DUR_SKIP_HI
MAX_PAGES = int(os.environ.get("MAX_PAGES", "8"))
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "10"))
# ponytail: hard ceiling on Stratz calls per UTC day (free tier = 15k/day).
# Default leaves ~1/3 of the quota for anything else using the token.
STRATZ_DAILY_BUDGET = int(os.environ.get("STRATZ_DAILY_BUDGET", "10000"))
DB_PATH = os.environ.get("HERALD_DB", "herald.db")

# One aliased request fetches STRATZ_BATCH full matches and costs exactly ONE
# rate-limit unit (verified live 2026-07-10: 25 aliases, day counter -1).
STRATZ_BATCH = int(os.environ.get("STRATZ_BATCH", "25"))
STRATZ_FIELDS = """
    id durationSeconds startDateTime didRadiantWin gameMode rank bracket
    radiantKills direKills radiantNetworthLeads radiantExperienceLeads
    topLaneOutcome midLaneOutcome bottomLaneOutcome
    towerDeaths { time isRadiant }
    players {
      heroId isRadiant leaverStatus kills deaths assists networth goldPerMinute
      experiencePerMinute numLastHits numDenies lane role position
      item0Id item1Id item2Id item3Id item4Id item5Id
      backpack0Id backpack1Id backpack2Id neutral0Id
      stats { networthPerMinute itemPurchases { time itemId } }
    }
"""


# --- SCHEMA ---

def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")  # backfill + loop share the db
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
          match_id INTEGER PRIMARY KEY, start_time INTEGER, duration_s INTEGER,
          radiant_win INTEGER, game_mode TEXT, rank INTEGER, bracket INTEGER,
          avg_rank_tier INTEGER, kills_r INTEGER, kills_d INTEGER, kills INTEGER, kpm REAL,
          max_lead INTEGER, min_lead INTEGER, final_lead INTEGER, comeback_gold INTEGER,
          throw_gold INTEGER, feeder_deaths INTEGER, top_kills INTEGER, max_gpm INTEGER,
          winner_towers_lost INTEGER, has_rapier INTEGER, raw TEXT, enriched_at INTEGER)
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_start ON matches(start_time)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS match_players (
          match_id INTEGER, slot INTEGER, hero_id INTEGER, is_radiant INTEGER,
          kills INTEGER, deaths INTEGER, assists INTEGER, networth INTEGER, gpm INTEGER,
          position TEXT, items TEXT, PRIMARY KEY (match_id, slot))
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_players_hero ON match_players(hero_id)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending (
          match_id INTEGER PRIMARY KEY, avg_rank_tier INTEGER, start_time INTEGER,
          discovered_at INTEGER, attempts INTEGER DEFAULT 0, last_attempt INTEGER)
        """
    )
    conn.execute("CREATE TABLE IF NOT EXISTS stratz_calls (day TEXT PRIMARY KEY, calls INTEGER)")
    conn.commit()


def stratz_budget_left(conn):
    day = time.strftime("%Y-%m-%d", time.gmtime())
    row = conn.execute("SELECT calls FROM stratz_calls WHERE day=?", (day,)).fetchone()
    return STRATZ_DAILY_BUDGET - (row[0] if row else 0)


def stratz_spend(conn, n):
    day = time.strftime("%Y-%m-%d", time.gmtime())
    conn.execute(
        "INSERT INTO stratz_calls(day, calls) VALUES(?,?) "
        "ON CONFLICT(day) DO UPDATE SET calls = calls + ?",
        (day, n, n),
    )


def get_conn(path=DB_PATH):
    conn = sqlite3.connect(path)
    init_db(conn)
    return conn


# --- DERIVED VIEW ---

def match_view(raw):
    """Single source of truth for derived semantics — must match
    spikes/menu-v2/render.py load_matches() per-match transform EXACTLY."""
    rk = sum(raw.get("radiantKills") or [])
    dk = sum(raw.get("direKills") or [])
    leads = raw.get("radiantNetworthLeads") or [0]
    players = []
    for p in raw["players"]:
        items = [p.get(f"item{i}Id") for i in range(6)]
        players.append({
            "hero_id": p["heroId"], "is_radiant": p["isRadiant"],
            "k": p["kills"], "d": p["deaths"], "a": p["assists"],
            "gpm": p.get("goldPerMinute", 0), "networth": p.get("networth", 0),
            "items": [i for i in items if i], "lane": p.get("lane"),
            "role": p.get("role"), "position": p.get("position"),
            "networth_per_min": (p.get("stats") or {}).get("networthPerMinute") or [],
            "purchases": (p.get("stats") or {}).get("itemPurchases") or [],
        })
    feeder = max(players, key=lambda p: p["d"])
    win_r = raw["didRadiantWin"]
    max_lead, min_lead = max(leads), min(leads)
    deficit = -min_lead if win_r else max_lead  # winner's worst deficit
    return {
        "id": raw["id"], "duration": raw["durationSeconds"],
        "mins": raw["durationSeconds"] // 60, "start": raw.get("startDateTime"),
        "radiant_win": win_r, "kills_r": rk, "kills_d": dk, "kills": rk + dk,
        "kpm": round((rk + dk) / max(raw["durationSeconds"] / 60, 1), 1),
        "bracket": raw.get("bracket"), "rank": raw.get("rank"),
        "leads": leads, "max_lead": max_lead, "min_lead": min_lead,
        "comeback_gold": deficit if deficit > 0 else 0,
        "feeder": feeder, "players": players,
        "tower_deaths": raw.get("towerDeaths") or [],
        "lanes": {"top": raw.get("topLaneOutcome"), "mid": raw.get("midLaneOutcome"),
                  "bot": raw.get("bottomLaneOutcome")},
    }


# --- COLUMN COMPUTE ---

def derived_cols(raw):
    v = match_view(raw)
    throw_size = v["max_lead"] if not v["radiant_win"] else -v["min_lead"]  # loser's best lead
    throw_gold = max(0, throw_size)
    feeder_deaths = max((p["d"] for p in v["players"]), default=0)
    top_kills = max((p["k"] for p in v["players"]), default=0)
    max_gpm = max((p["gpm"] for p in v["players"]), default=0)
    winner_towers_lost = sum(
        1 for t in v["tower_deaths"] if t.get("isRadiant") == v["radiant_win"]
    )
    has_rapier = 1 if any(i == RAPIER_ID for p in v["players"] for i in p["items"]) else 0
    final_lead = v["leads"][-1]
    return {
        "kills_r": v["kills_r"], "kills_d": v["kills_d"], "kills": v["kills"], "kpm": v["kpm"],
        "max_lead": v["max_lead"], "min_lead": v["min_lead"], "final_lead": final_lead,
        "comeback_gold": v["comeback_gold"], "throw_gold": throw_gold,
        "feeder_deaths": feeder_deaths, "top_kills": top_kills, "max_gpm": max_gpm,
        "winner_towers_lost": winner_towers_lost, "has_rapier": has_rapier,
    }


# --- UPSERT ---

def upsert_match(conn, raw, avg_rank_tier):
    mid = raw["id"]
    c = derived_cols(raw)
    conn.execute(
        """
        INSERT OR REPLACE INTO matches (
          match_id, start_time, duration_s, radiant_win, game_mode, rank, bracket,
          avg_rank_tier, kills_r, kills_d, kills, kpm, max_lead, min_lead, final_lead,
          comeback_gold, throw_gold, feeder_deaths, top_kills, max_gpm,
          winner_towers_lost, has_rapier, raw, enriched_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            mid, raw.get("startDateTime"), raw["durationSeconds"],
            1 if raw["didRadiantWin"] else 0, raw.get("gameMode"),
            raw.get("rank"), raw.get("bracket"), avg_rank_tier,
            c["kills_r"], c["kills_d"], c["kills"], c["kpm"], c["max_lead"], c["min_lead"],
            c["final_lead"], c["comeback_gold"], c["throw_gold"], c["feeder_deaths"],
            c["top_kills"], c["max_gpm"], c["winner_towers_lost"], c["has_rapier"],
            json.dumps(raw), int(time.time()),
        ),
    )
    conn.execute("DELETE FROM match_players WHERE match_id=?", (mid,))
    for slot, p in enumerate(raw["players"]):
        items = json.dumps([i for i in [p.get(f"item{i}Id") for i in range(6)] if i])
        conn.execute(
            """
            INSERT OR REPLACE INTO match_players (
              match_id, slot, hero_id, is_radiant, kills, deaths, assists,
              networth, gpm, position, items
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                mid, slot, p["heroId"], 1 if p["isRadiant"] else 0,
                p["kills"], p["deaths"], p["assists"], p.get("networth", 0),
                p.get("goldPerMinute", 0), p.get("position"), items,
            ),
        )
    conn.commit()


# --- READER ---

def load_matches(conn, where="", params=()):
    """The board imports THIS. Returns match_view dicts, newest first."""
    sql = "SELECT raw FROM matches" + (f" WHERE {where}" if where else "")
    sql += " ORDER BY start_time DESC"
    rows = conn.execute(sql, params).fetchall()
    return [match_view(json.loads(r[0])) for r in rows]


# --- OD HTTP ---

def od_fetch(client, less_than):
    params = {"less_than_match_id": less_than} if less_than else {}
    for _attempt in range(5):
        try:
            resp = client.get(OD_URL, params=params)
        except Exception as e:
            log.warning(f"od_fetch exception: {e}, retrying")
            time.sleep(3)
            continue
        if resp.status_code == 429:
            log.warning("od_fetch 429, sleeping 10s")
            time.sleep(10)
            continue
        if resp.status_code >= 500:
            log.warning(f"od_fetch {resp.status_code}, retrying")
            time.sleep(3)
            continue
        resp.raise_for_status()
        return resp.json()
    return []


# --- DISCOVERY ---

def discover(conn):
    pre = {r[0] for r in conn.execute("SELECT match_id FROM matches").fetchall()}
    pre |= {r[0] for r in conn.execute("SELECT match_id FROM pending").fetchall()}
    seen_new = set()
    less_than = None
    new = 0
    now = int(time.time())
    with httpx.Client(timeout=30) as client:
        for _page in range(MAX_PAGES):
            rows = od_fetch(client, less_than)
            if not rows:
                break
            page_ids = [m["match_id"] for m in rows]
            novel = [m for m in rows if m["match_id"] not in pre and m["match_id"] not in seen_new]
            for m in novel:
                seen_new.add(m["match_id"])
                rt = m.get("avg_rank_tier")
                if dur_boring(m.get("duration") or 0):
                    continue
                if rt is not None and 10 <= rt <= 15:
                    conn.execute(
                        "INSERT OR IGNORE INTO pending("
                        "match_id,avg_rank_tier,start_time,discovered_at,attempts,last_attempt"
                        ") VALUES(?,?,?,?,0,NULL)",
                        (m["match_id"], rt, m.get("start_time"), now),
                    )
                    new += 1
            conn.commit()
            if not novel:  # full page yielded only already-known ids -> reached frontier
                break
            less_than = min(page_ids)
            time.sleep(1.1)
    return new


# --- OD EXPLORER (backfill discovery) ---

def explorer_fetch(client, sql):
    """OpenDota Explorer SQL. Needs an explicit User-Agent (default UA gets 403)."""
    params = {"sql": sql}
    headers = {"User-Agent": "herald-scraper-bot"}
    for _attempt in range(4):
        try:
            resp = client.get(EXPLORER_URL, params=params, headers=headers)
        except Exception as e:
            log.warning(f"explorer_fetch exception: {e}, retrying")
            time.sleep(5)
            continue
        if resp.status_code == 429:
            log.warning("explorer_fetch 429, sleeping 10s")
            time.sleep(10)
            continue
        if resp.status_code >= 500:
            log.warning(f"explorer_fetch {resp.status_code}, retrying")
            time.sleep(5)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("err"):
            log.warning(f"explorer_fetch sql error: {data['err']}, retrying")
            time.sleep(5)
            continue
        return data.get("rows") or []
    return None


def backfill(conn, days):
    """One-time depth fill: keyset-paginate Explorer's public_matches (PK index
    walk — start_time range scans time out server-side) back `days` days, then
    subsample evenly to BACKFILL_TARGET and queue for enrichment."""
    now = int(time.time())
    cutoff = now - days * 86400
    pre = {r[0] for r in conn.execute("SELECT match_id FROM matches").fetchall()}
    pre |= {r[0] for r in conn.execute("SELECT match_id FROM pending").fetchall()}
    found = []
    last = None
    with httpx.Client(timeout=120) as client:
        while True:
            frontier = f"AND match_id < {int(last)} " if last else ""
            rows = explorer_fetch(
                client,
                "SELECT match_id, start_time, avg_rank_tier FROM public_matches "
                f"WHERE avg_rank_tier BETWEEN 10 AND 15 {frontier}"
                f"AND (duration < {DUR_SKIP_LO} OR duration > {DUR_SKIP_HI}) "
                "ORDER BY match_id DESC LIMIT 1000",
            )
            if rows is None:
                log.warning(f"backfill: explorer gave up at {len(found)} rows, using what we have")
                break
            if not rows:
                break
            found.extend(r for r in rows if r["start_time"] >= cutoff)
            oldest = min(r["start_time"] for r in rows)
            last = min(r["match_id"] for r in rows)
            log.info(f"backfill: {len(found)} ids, at {(now - oldest) / 86400:.1f} days back")
            if oldest < cutoff:
                break
            time.sleep(1.1)
    queued = 0
    for r in found:
        if r["match_id"] in pre:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO pending("
            "match_id,avg_rank_tier,start_time,discovered_at,attempts,last_attempt"
            ") VALUES(?,?,?,?,0,NULL)",
            (r["match_id"], r["avg_rank_tier"], r["start_time"], now - 200),
        )
        queued += 1
    conn.commit()
    log.info(f"backfill: found {len(found)}, queued {queued} for enrichment")
    return queued


# --- STRATZ HTTP ---

def stratz_fetch_batch(client, ids):
    """One aliased request for up to STRATZ_BATCH matches. Returns
    {match_id: match_or_None}, or the string "RATELIMIT" when Stratz's cap is
    hit — callers must not count that as failed attempts."""
    tok = os.environ.get("STRATZ_API_TOKEN")
    if not tok:
        raise RuntimeError("STRATZ_API_TOKEN not set")
    headers = {"Authorization": f"Bearer {tok.strip()}", "User-Agent": "STRATZ_API"}
    parts = [f"m{i}: match(id: {int(mid)}) {{ {STRATZ_FIELDS} }}" for i, mid in enumerate(ids)]
    body = {"query": "query { " + " ".join(parts) + " }"}
    for _attempt in range(3):
        try:
            resp = client.post(STRATZ_URL, json=body, headers=headers)
        except Exception as e:
            log.warning(f"stratz_fetch_batch exception: {e}, retrying")
            time.sleep(3)
            continue
        if resp.status_code == 429:
            log.warning("stratz_fetch_batch 429, sleeping 30s")
            time.sleep(30)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            log.warning(f"stratz_fetch_batch errors: {str(data['errors'])[:200]}")
        d = data.get("data") or {}
        return {mid: d.get(f"m{i}") for i, mid in enumerate(ids)}
    return "RATELIMIT"  # 3x 429 in a row = daily/minute cap, not bad matches


# --- ENRICHMENT ---

def has_abandon(m):
    return any(p.get("leaverStatus") not in LEAVER_OK for p in m.get("players") or [])


def enrich(conn):
    now = int(time.time())
    enriched = 0
    failed = 0
    dropped = 0
    cut = 0
    budget = stratz_budget_left(conn)  # in requests; each request = STRATZ_BATCH matches
    if budget <= 0:
        log.info("enrich: stratz daily budget spent, skipping until tomorrow UTC")
        return 0, 0, 0, 0
    # ponytail: 200 requests/cycle keeps a cycle under ~3 min; raise to drain faster
    n_req = min(200, budget)
    rows = conn.execute(
        "SELECT match_id, avg_rank_tier FROM pending WHERE discovered_at < ? AND attempts < 8 "
        "ORDER BY discovered_at ASC LIMIT ?",
        (now - 180, n_req * STRATZ_BATCH),
    ).fetchall()
    with httpx.Client(timeout=120) as client:
        for i in range(0, len(rows), STRATZ_BATCH):
            chunk = rows[i:i + STRATZ_BATCH]
            res = stratz_fetch_batch(client, [mid for mid, _ in chunk])
            stratz_spend(conn, 1)
            if res == "RATELIMIT":
                log.warning("enrich: stratz capped/unreachable — ending cycle, no attempts burned")
                conn.commit()
                break
            for mid, art in chunk:
                m = res.get(mid)
                ready = bool(m) and bool(m.get("radiantNetworthLeads"))
                # abandons + mid-length games are both cut here; discovery already
                # skips boring durations, this catches rows queued before the filter
                if ready and (has_abandon(m) or dur_boring(m["durationSeconds"])):
                    conn.execute("DELETE FROM pending WHERE match_id=?", (mid,))
                    cut += 1
                elif ready:
                    upsert_match(conn, m, art)
                    conn.execute("DELETE FROM pending WHERE match_id=?", (mid,))
                    enriched += 1
                else:
                    conn.execute(
                        "UPDATE pending SET attempts=attempts+1, last_attempt=? WHERE match_id=?",
                        (now, mid),
                    )
                    att = conn.execute(
                        "SELECT attempts FROM pending WHERE match_id=?", (mid,)
                    ).fetchone()[0]
                    if att >= 8:
                        conn.execute("DELETE FROM pending WHERE match_id=?", (mid,))
                        dropped += 1
                    failed += 1
            conn.commit()
            time.sleep(0.6)  # well under Stratz 150 req/min
    return enriched, failed, dropped, cut


# --- PRUNE ---

def prune(conn):
    now = int(time.time())
    cutoff = now - RETENTION_DAYS * 86400
    q = conn.execute("SELECT match_id FROM matches WHERE start_time < ?", (cutoff,))
    old = [r[0] for r in q.fetchall()]
    conn.executemany("DELETE FROM match_players WHERE match_id=?", [(x,) for x in old])
    conn.execute("DELETE FROM matches WHERE start_time < ?", (cutoff,))
    # ponytail: RETENTION_DAYS not 2 days — a backfilled queue can take days to
    # drain against Stratz's 15k/day cap and must not be pruned mid-drain
    conn.execute("DELETE FROM pending WHERE discovered_at < ?", (cutoff,))
    conn.commit()
    return len(old)


# --- CYCLE ---

def cycle(conn):
    n_disc = discover(conn)
    n_enr, n_fail, n_drop, n_cut = enrich(conn)
    n_prune = prune(conn)
    mtot = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    ptot = conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    log.info(
        f"cycle: discovered {n_disc}, enriched {n_enr}, cut {n_cut} (abandon/boring-dur), "
        f"not-ready {n_fail}, dropped {n_drop}, pruned {n_prune} | matches={mtot} pending={ptot}"
    )


# --- SELFCHECK ---

def selfcheck():
    """Offline, no network, no env vars."""
    try:
        fixture_path = os.path.join(
            os.path.dirname(__file__), "..", "spikes", "menu-v2", "fixtures", "herald_matches.json"
        )
        with open(fixture_path) as f:
            data = json.load(f)
        od_map = {r["match_id"]: r for r in data.get("od_rows", [])}
        conn = get_conn(":memory:")
        for raw in data["matches"]:
            upsert_match(conn, raw, od_map.get(raw["id"], {}).get("avg_rank_tier"))

        mcount = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        pcount = conn.execute("SELECT COUNT(*) FROM match_players").fetchone()[0]
        assert mcount == 38, f"expected 38 matches, got {mcount}"
        assert pcount == 380, f"expected 380 players, got {pcount}"

        raw0 = data["matches"][0]
        expect_kills = sum(raw0.get("radiantKills") or []) + sum(raw0.get("direKills") or [])
        q = conn.execute("SELECT kills, comeback_gold FROM matches WHERE match_id=?", (raw0["id"],))
        stored_kills, stored_comeback = q.fetchone()
        assert stored_kills == expect_kills, f"kills mismatch: {stored_kills} != {expect_kills}"

        leads0 = raw0.get("radiantNetworthLeads") or [0]
        max_lead0, min_lead0 = max(leads0), min(leads0)
        win_r0 = raw0["didRadiantWin"]
        deficit0 = -min_lead0 if win_r0 else max_lead0
        expect_comeback = deficit0 if deficit0 > 0 else 0
        assert stored_comeback == expect_comeback, (
            f"comeback_gold mismatch: {stored_comeback} != {expect_comeback}"
        )

        rows = load_matches(conn)
        assert len(rows) == 38, f"expected 38 rows from load_matches, got {len(rows)}"
        EXPECTED_KEYS = {
            "id", "duration", "mins", "start", "radiant_win", "kills_r", "kills_d",
            "kills", "kpm", "bracket", "rank", "leads", "max_lead", "min_lead",
            "comeback_gold", "feeder", "players", "tower_deaths", "lanes",
        }
        assert set(rows[0]) == EXPECTED_KEYS, f"key mismatch: {set(rows[0])}"
        player_keys = set(rows[0]["players"][0])
        expected_player_keys = {
            "hero_id", "k", "d", "a", "gpm", "networth", "items", "lane", "role",
            "position", "networth_per_min", "purchases", "is_radiant",
        }
        assert expected_player_keys.issubset(player_keys), f"player key mismatch: {player_keys}"
        assert rows[0]["start"] >= rows[-1]["start"], "rows not newest-first"

        print("selfcheck OK: 38 matches / 380 players")
        return 0
    except AssertionError as e:
        print(f"selfcheck FAILED: {e}")
        return 1


# --- CLI ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--loop", nargs="?", const=180, type=int, default=None)
    parser.add_argument("--backfill", nargs="?", const=RETENTION_DAYS, type=int, default=None,
                        metavar="DAYS", help="queue DAYS of history via OD Explorer SQL, then exit")
    args = parser.parse_args()

    if args.selfcheck:
        sys.exit(selfcheck())

    conn = get_conn()
    if args.backfill is not None:
        backfill(conn, args.backfill)
        return
    if args.loop is not None:
        while True:
            try:
                cycle(conn)
            except Exception as e:
                log.error(f"cycle failed: {e}")
            time.sleep(args.loop)
    else:
        cycle(conn)  # one-shot then exit


if __name__ == "__main__":
    main()
