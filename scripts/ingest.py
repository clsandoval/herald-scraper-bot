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
import math
import os
import sqlite3
import sys
import time
from collections import Counter

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("ingest")

# --- CONSTANTS ---

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
KPM_MIN = float(os.environ.get("KPM_MIN", "1.0"))


def dur_boring(seconds):
    return DUR_SKIP_LO <= seconds <= DUR_SKIP_HI


def low_kpm(m):
    kills = sum(m.get("radiantKills") or []) + sum(m.get("direKills") or [])
    return kills / max(m["durationSeconds"] / 60, 1) < KPM_MIN
MAX_PAGES = int(os.environ.get("MAX_PAGES", "400"))  # safety cap on an Explorer walk
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
    topLaneOutcome midLaneOutcome bottomLaneOutcome firstBloodTime numHumanPlayers
    towerDeaths { time isRadiant }
    players {
      heroId isRadiant leaverStatus kills deaths assists networth goldPerMinute
      experiencePerMinute numLastHits numDenies lane role position
      heroDamage towerDamage heroHealing level partyId intentionalFeeding
      dotaPlusHeroXp
      dotaPlus { level }
      abilities { abilityId time level isTalent }
      steamAccount { seasonRank smurfFlag dotaAccountLevel }
      item0Id item1Id item2Id item3Id item4Id item5Id
      backpack0Id backpack1Id backpack2Id neutral0Id
      stats { networthPerMinute itemPurchases { time itemId } actionsPerMinute }
    }
"""
# raw observables only — Stratz's opinion fields (imp/award/analysisOutcome/
# predicted*) stay out: watchability scoring is our own IP


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
          winner_towers_lost INTEGER, has_rapier INTEGER, raw TEXT, enriched_at INTEGER,
          lead_flips INTEGER, hero_damage INTEGER, has_smurf INTEGER, has_feeder INTEGER,
          max_party INTEGER, max_apm INTEGER, max_dplus INTEGER, weirdness REAL)
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_start ON matches(start_time)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS match_players (
          match_id INTEGER, slot INTEGER, hero_id INTEGER, is_radiant INTEGER,
          kills INTEGER, deaths INTEGER, assists INTEGER, networth INTEGER, gpm INTEGER,
          position TEXT, items TEXT, hero_damage INTEGER, season_rank INTEGER,
          dota_plus_xp INTEGER, PRIMARY KEY (match_id, slot))
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_players_hero ON match_players(hero_id)")
    # migrate pre-existing DBs (ALTER is a no-op error when the column exists)
    for table, col in [("matches", "lead_flips INTEGER"), ("matches", "hero_damage INTEGER"),
                       ("matches", "has_smurf INTEGER"), ("matches", "has_feeder INTEGER"),
                       ("matches", "max_party INTEGER"), ("matches", "max_apm INTEGER"),
                       ("matches", "max_dplus INTEGER"), ("matches", "weirdness REAL"),
                       ("match_players", "hero_damage INTEGER"),
                       ("match_players", "season_rank INTEGER"),
                       ("match_players", "dota_plus_xp INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
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
    leads = v["leads"]
    lead_flips = sum(1 for a, b in zip(leads, leads[1:]) if (a > 0) != (b > 0))
    hero_damage = sum(p.get("heroDamage") or 0 for p in raw["players"])
    rp = raw["players"]
    has_smurf = 1 if any((p.get("steamAccount") or {}).get("smurfFlag") or 0 for p in rp) else 0
    has_feeder = 1 if any(p.get("intentionalFeeding") for p in rp) else 0
    parties = {}
    for p in rp:
        if p.get("partyId") is not None:
            parties[p["partyId"]] = parties.get(p["partyId"], 0) + 1
    max_party = max(parties.values(), default=1)

    def _apm(p):
        a = (p.get("stats") or {}).get("actionsPerMinute") or []
        return sum(a) / len(a) if a else 0

    max_apm = int(max((_apm(p) for p in rp), default=0))
    max_dplus = max(((p.get("dotaPlus") or {}).get("level") or 0 for p in rp), default=0)
    return {
        "kills_r": v["kills_r"], "kills_d": v["kills_d"], "kills": v["kills"], "kpm": v["kpm"],
        "max_lead": v["max_lead"], "min_lead": v["min_lead"], "final_lead": final_lead,
        "comeback_gold": v["comeback_gold"], "throw_gold": throw_gold,
        "feeder_deaths": feeder_deaths, "top_kills": top_kills, "max_gpm": max_gpm,
        "winner_towers_lost": winner_towers_lost, "has_rapier": has_rapier,
        "lead_flips": lead_flips, "hero_damage": hero_damage,
        "has_smurf": has_smurf, "has_feeder": has_feeder, "max_party": max_party,
        "max_apm": max_apm, "max_dplus": max_dplus,
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
          winner_towers_lost, has_rapier, raw, enriched_at, lead_flips, hero_damage,
          has_smurf, has_feeder, max_party, max_apm, max_dplus
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            mid, raw.get("startDateTime"), raw["durationSeconds"],
            1 if raw["didRadiantWin"] else 0, raw.get("gameMode"),
            raw.get("rank"), raw.get("bracket"), avg_rank_tier,
            c["kills_r"], c["kills_d"], c["kills"], c["kpm"], c["max_lead"], c["min_lead"],
            c["final_lead"], c["comeback_gold"], c["throw_gold"], c["feeder_deaths"],
            c["top_kills"], c["max_gpm"], c["winner_towers_lost"], c["has_rapier"],
            json.dumps(raw), int(time.time()), c["lead_flips"], c["hero_damage"],
            c["has_smurf"], c["has_feeder"], c["max_party"], c["max_apm"], c["max_dplus"],
        ),
    )
    conn.execute("DELETE FROM match_players WHERE match_id=?", (mid,))
    for slot, p in enumerate(raw["players"]):
        items = json.dumps([i for i in [p.get(f"item{i}Id") for i in range(6)] if i])
        conn.execute(
            """
            INSERT OR REPLACE INTO match_players (
              match_id, slot, hero_id, is_radiant, kills, deaths, assists,
              networth, gpm, position, items, hero_damage, season_rank, dota_plus_xp
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                mid, slot, p["heroId"], 1 if p["isRadiant"] else 0,
                p["kills"], p["deaths"], p["assists"], p.get("networth", 0),
                p.get("goldPerMinute", 0), p.get("position"), items,
                p.get("heroDamage"), (p.get("steamAccount") or {}).get("seasonRank"),
                p.get("dotaPlusHeroXp"),
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


# --- OD EXPLORER (discovery) ---

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


def discover(conn, days=RETENTION_DAYS):
    """Exhaustive discovery: keyset-paginate Explorer's public_matches (PK index
    walk — start_time range scans time out server-side) newest-first, rank +
    duration filtered in SQL. Stops at `days` back, at a fully-known page (the
    frontier — everything older is already discovered), or at MAX_PAGES."""
    now = int(time.time())
    cutoff = now - days * 86400
    pre = {r[0] for r in conn.execute("SELECT match_id FROM matches").fetchall()}
    pre |= {r[0] for r in conn.execute("SELECT match_id FROM pending").fetchall()}
    queued = 0
    last = None
    with httpx.Client(timeout=120) as client:
        for _page in range(MAX_PAGES):
            frontier = f"AND match_id < {int(last)} " if last else ""
            rows = explorer_fetch(
                client,
                "SELECT match_id, start_time, avg_rank_tier FROM public_matches "
                f"WHERE avg_rank_tier BETWEEN 10 AND 15 {frontier}"
                f"AND (duration < {DUR_SKIP_LO} OR duration > {DUR_SKIP_HI}) "
                "ORDER BY match_id DESC LIMIT 1000",
            )
            if rows is None:
                log.warning(f"discover: explorer gave up after {queued} queued, using what we have")
                break
            if not rows:
                break
            novel = [r for r in rows if r["match_id"] not in pre and r["start_time"] >= cutoff]
            for r in novel:
                pre.add(r["match_id"])
                conn.execute(
                    "INSERT OR IGNORE INTO pending("
                    "match_id,avg_rank_tier,start_time,discovered_at,attempts,last_attempt"
                    ") VALUES(?,?,?,?,0,NULL)",
                    (r["match_id"], r["avg_rank_tier"], r["start_time"], now),
                )
                queued += 1
            conn.commit()
            oldest = min(r["start_time"] for r in rows)
            # ponytail: a 100%-known page = frontier reached; the rare straggler
            # ingested out of order beyond it is lost, acceptable
            if oldest < cutoff or not novel:
                break
            last = min(r["match_id"] for r in rows)
            if queued and queued % 5000 < len(novel):
                log.info(f"discover: {queued} queued, at {(now - oldest) / 86400:.1f} days back")
            time.sleep(1.1)
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


def has_guardian(m):
    """Any player ranked above Herald (seasonRank > 15). Anonymous/unranked
    (None) can't be checked and is allowed through."""
    return any(((p.get("steamAccount") or {}).get("seasonRank") or 0) > 15
               for p in m.get("players") or [])


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
                # cut = abandons, non-Herald players, mid-length games, low kill
                # density. duration is also pre-filtered at discovery
                if ready and (has_abandon(m) or has_guardian(m)
                              or dur_boring(m["durationSeconds"]) or low_kpm(m)):
                    # also evict any stale copy (re-enrich sweeps route through here)
                    conn.execute("DELETE FROM matches WHERE match_id=?", (mid,))
                    conn.execute("DELETE FROM match_players WHERE match_id=?", (mid,))
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


# --- BUILD WEIRDNESS (corpus-relative, no network) ---
# Wrongness, not rarity: PMI of item-given-hero vs item-overall, so a globally
# common item on the wrong hero (Armlet Lina) scores, a new rare item doesn't.
# Per match = the weirdest player's top-3 distinct-item-family sum.

def score_weirdness(conn):
    items_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "spikes", "menu-v2", "assets", "items.json")
    items = json.load(open(items_path))
    fam = {v["id"]: (v.get("dname") or str(v["id"])) for v in items.values()
           if (v.get("cost") or 0) >= 2000}
    # two streaming passes over raw — never hold the corpus in memory (1GB VM)
    hcount, htot, gcount = Counter(), Counter(), Counter()
    gtot = 0
    for (raw,) in conn.execute("SELECT raw FROM matches"):
        for p in json.loads(raw)["players"]:
            for b in (p.get("stats") or {}).get("itemPurchases") or []:
                if b["itemId"] in fam and b["time"] > 0:
                    hcount[(p["heroId"], b["itemId"])] += 1
                    htot[p["heroId"]] += 1
                    gcount[b["itemId"]] += 1
                    gtot += 1
    if not gtot:
        return 0
    V = len(fam)

    def pmi(h, i):
        ph = (hcount[(h, i)] - 1 + 0.5) / (htot[h] + 0.5 * V)  # own purchase excluded
        return -math.log(max(ph / (gcount[i] / gtot), 1e-9))

    n = 0
    updates = []
    for mid, raw in conn.execute("SELECT match_id, raw FROM matches"):
        w = 0.0
        for p in json.loads(raw)["players"]:
            best = {}
            for b in (p.get("stats") or {}).get("itemPurchases") or []:
                if b["itemId"] in fam and b["time"] > 0:
                    s = pmi(p["heroId"], b["itemId"])
                    if s > best.get(fam[b["itemId"]], 0):
                        best[fam[b["itemId"]]] = s
            w = max(w, sum(sorted(best.values(), reverse=True)[:3]))
        updates.append((round(w, 2), mid))
        n += 1
    conn.executemany("UPDATE matches SET weirdness=? WHERE match_id=?", updates)
    conn.commit()
    return n


# --- RECOMPUTE (derived columns from stored raw, no network) ---

def recompute(conn):
    n = 0
    for mid, raw in conn.execute("SELECT match_id, raw FROM matches").fetchall():
        c = derived_cols(json.loads(raw))
        conn.execute(
            "UPDATE matches SET " + ", ".join(f"{k}=?" for k in c) + " WHERE match_id=?",
            list(c.values()) + [mid],
        )
        n += 1
        if n % 5000 == 0:
            conn.commit()
            log.info(f"recompute: {n}")
    conn.commit()
    return n


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
                        metavar="DAYS", help="one exhaustive discovery pass DAYS back, then exit")
    parser.add_argument("--recompute", action="store_true",
                        help="recompute derived columns from stored raw JSON, then exit")
    parser.add_argument("--weirdness", action="store_true",
                        help="rescore build weirdness for all matches, then exit")
    args = parser.parse_args()

    if args.selfcheck:
        sys.exit(selfcheck())

    conn = get_conn()
    if args.recompute:
        log.info(f"recompute: {recompute(conn)} matches updated")
        return
    if args.weirdness:
        log.info(f"weirdness: {score_weirdness(conn)} matches scored")
        return
    if args.backfill is not None:
        n = discover(conn, args.backfill)
        log.info(f"backfill: queued {n}")
        return
    if args.loop is not None:
        n = 0
        while True:
            try:
                cycle(conn)
                # ponytail: full corpus rescore every ~50 cycles (~daily at 30min
                # loops), NOT at boot — boot rescore raced board startup into OOM.
                # New matches sort as weirdness 0 until the next rescore.
                if n and n % 50 == 0:
                    log.info(f"weirdness: {score_weirdness(conn)} matches scored")
            except Exception as e:
                log.error(f"cycle failed: {e}")
            n += 1
            time.sleep(args.loop)
    else:
        cycle(conn)  # one-shot then exit


if __name__ == "__main__":
    main()
