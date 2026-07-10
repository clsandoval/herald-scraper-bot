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
STRATZ_URL = "https://api.stratz.com/graphql"
RAPIER_ID = 133
MAX_PAGES = int(os.environ.get("MAX_PAGES", "8"))
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "10"))
DB_PATH = os.environ.get("HERALD_DB", "herald.db")

STRATZ_QUERY = """
query($id: Long!) {
  match(id: $id) {
    id durationSeconds startDateTime didRadiantWin gameMode rank bracket
    radiantKills direKills radiantNetworthLeads radiantExperienceLeads
    topLaneOutcome midLaneOutcome bottomLaneOutcome
    towerDeaths { time isRadiant }
    players {
      heroId isRadiant kills deaths assists networth goldPerMinute
      experiencePerMinute numLastHits numDenies lane role position
      item0Id item1Id item2Id item3Id item4Id item5Id
      backpack0Id backpack1Id backpack2Id neutral0Id
      stats { networthPerMinute itemPurchases { time itemId } }
    }
  }
}
"""


# --- SCHEMA ---

def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
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
    conn.commit()


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
    sql = "SELECT raw FROM matches" + (f" WHERE {where}" if where else "") + " ORDER BY start_time DESC"
    rows = conn.execute(sql, params).fetchall()
    return [match_view(json.loads(r[0])) for r in rows]


# --- OD HTTP ---

def od_fetch(client, less_than):
    params = {"less_than_match_id": less_than} if less_than else {}
    for attempt in range(5):
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
        for page_i in range(MAX_PAGES):
            rows = od_fetch(client, less_than)
            if not rows:
                break
            page_ids = [m["match_id"] for m in rows]
            novel = [m for m in rows if m["match_id"] not in pre and m["match_id"] not in seen_new]
            for m in novel:
                seen_new.add(m["match_id"])
                rt = m.get("avg_rank_tier")
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


# --- STRATZ HTTP ---

def stratz_fetch(client, match_id):
    tok = os.environ.get("STRATZ_API_TOKEN")
    if not tok:
        raise RuntimeError("STRATZ_API_TOKEN not set")
    headers = {"Authorization": f"Bearer {tok.strip()}", "User-Agent": "STRATZ_API"}
    body = {"query": STRATZ_QUERY, "variables": {"id": match_id}}
    for attempt in range(3):
        try:
            resp = client.post(STRATZ_URL, json=body, headers=headers)
        except Exception as e:
            log.warning(f"stratz_fetch exception: {e}, retrying")
            time.sleep(3)
            continue
        if resp.status_code == 429:
            log.warning("stratz_fetch 429, sleeping 30s")
            time.sleep(30)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            log.warning(f"stratz_fetch errors: {data['errors']}")
        return (data.get("data") or {}).get("match")
    return None


# --- ENRICHMENT ---

def enrich(conn):
    now = int(time.time())
    enriched = 0
    failed = 0
    dropped = 0
    rows = conn.execute(
        "SELECT match_id, avg_rank_tier FROM pending WHERE discovered_at < ? AND attempts < 8 "
        "ORDER BY discovered_at ASC LIMIT 120",
        (now - 180,),
    ).fetchall()
    with httpx.Client(timeout=30) as client:
        for mid, art in rows:
            m = stratz_fetch(client, mid)
            ready = bool(m) and bool(m.get("radiantNetworthLeads"))
            if ready:
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
                    log.info(f"dropped {mid} after {att} attempts")
                failed += 1
            conn.commit()
            time.sleep(0.6)  # under Stratz 150/min
    return enriched, failed, dropped


# --- PRUNE ---

def prune(conn):
    now = int(time.time())
    cutoff = now - RETENTION_DAYS * 86400
    old = [
        r[0]
        for r in conn.execute("SELECT match_id FROM matches WHERE start_time < ?", (cutoff,)).fetchall()
    ]
    conn.executemany("DELETE FROM match_players WHERE match_id=?", [(x,) for x in old])
    conn.execute("DELETE FROM matches WHERE start_time < ?", (cutoff,))
    conn.execute("DELETE FROM pending WHERE discovered_at < ?", (now - 2 * 86400,))
    conn.commit()
    return len(old)


# --- CYCLE ---

def cycle(conn):
    n_disc = discover(conn)
    n_enr, n_fail, n_drop = enrich(conn)
    n_prune = prune(conn)
    mtot = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    ptot = conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    log.info(
        f"cycle: discovered {n_disc}, enriched {n_enr}, not-ready {n_fail}, "
        f"dropped {n_drop}, pruned {n_prune} | matches={mtot} pending={ptot}"
    )


# --- SELFCHECK ---

def selfcheck():
    """Offline, no network, no env vars."""
    try:
        fixture_path = os.path.join(
            os.path.dirname(__file__), "..", "spikes", "menu-v2", "fixtures", "herald_matches.json"
        )
        data = json.load(open(fixture_path))
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
        row = conn.execute("SELECT kills, comeback_gold FROM matches WHERE match_id=?", (raw0["id"],)).fetchone()
        stored_kills, stored_comeback = row
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
    args = parser.parse_args()

    if args.selfcheck:
        sys.exit(selfcheck())

    conn = get_conn()
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
