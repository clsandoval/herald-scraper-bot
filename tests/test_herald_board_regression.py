"""Regression tests for the Herald board + ingest — every bug found in the
2026-07-13 incident. Pure functions + in-memory SQLite + discord.py behavior;
no network, no live gateway.

Run:  .venv/bin/python -m pytest tests/test_herald_board_regression.py -q
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import sys

import pytest

# ingest reads a few settings from env with defaults; set harmless ones so import
# never depends on a real secret being present.
os.environ.setdefault("STRATZ_API_TOKEN", "test-token")
os.environ.setdefault("DUR_MIN", "3600")  # the 60-min floor we standardized on

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ingest  # noqa: E402


# ----------------------- synthetic match builders -----------------------

def _player(hero_id, is_radiant, *, k=6, d=4, a=10, items=(), leaver="NONE",
            season_rank=12, dplus=None):
    p = {
        "heroId": hero_id, "isRadiant": is_radiant, "kills": k, "deaths": d,
        "assists": a, "goldPerMinute": 300, "networth": 5000, "lane": 1, "role": 1,
        "position": "1", "heroDamage": 1000, "partyId": None,
        "intentionalFeeding": False, "isRandom": False, "leaverStatus": leaver,
        "dotaPlus": ({"level": dplus} if dplus is not None else None),
        "steamAccount": {"seasonRank": season_rank, "smurfFlag": 0},
        "stats": {"allTalks": [], "itemPurchases": [], "actionsPerMinute": [],
                  "networthPerMinute": []},
    }
    for i, iid in enumerate(items):
        p[f"item{i}Id"] = iid
    return p


def _match(mid=9001, *, duration=3600, leads=(0, 100, -100), players=None,
           radiant_kills=(1, 1, 1), dire_kills=(1, 1, 1)):
    return {
        "id": mid, "durationSeconds": duration, "startDateTime": 1700000000 + mid,
        "didRadiantWin": True, "gameMode": "ALL_PICK_RANKED", "rank": 12, "bracket": 1,
        "radiantKills": list(radiant_kills), "direKills": list(dire_kills),
        "radiantNetworthLeads": list(leads), "towerDeaths": [],
        "barracksStatusRadiant": 63, "barracksStatusDire": 63,
        "players": players if players is not None
        else [_player(i + 1, i < 5) for i in range(10)],
    }


# ----------------------- derived column computation -----------------------
# Bug: board rebuilt flips/avg_gap/rapier from raw JSON at every boot (1.5GB scan).
# Fix: precompute as ingest columns. These guard the exact math.

def test_derived_cols_avg_gap_and_flips():
    m = _match(leads=[0, 100, -100])
    c = ingest.derived_cols(m)
    assert c["avg_gap"] == pytest.approx((0 + 100 + 100) / 3)   # mean |lead|
    assert c["lead_flips"] == 2                                  # 0->+ , +->-


def test_derived_cols_rapier_count_from_final_items():
    players = [_player(1, True, items=[133, 1, 2]),      # 1 rapier
              _player(2, True, items=[133, 133]),        # 2 rapiers
              *[_player(i + 3, i + 3 <= 5) for i in range(8)]]
    c = ingest.derived_cols(_match(players=players))
    assert c["rapier_count"] == 3


def test_derived_cols_no_rapier_is_zero():
    assert ingest.derived_cols(_match())["rapier_count"] == 0


def test_gold_swings_counts_big_reversals_not_just_flips():
    # +5k, clawback to +1k (down 4k >= 3k), back to +6k (up 5k) => 2 swings,
    # even though the lead NEVER crossed zero (not a "flip")
    assert ingest.gold_swings([0, 5000, 1000, 6000]) == 2
    # tiny wobbles below the 3k threshold => no swing
    assert ingest.gold_swings([0, 100, -100, 200]) == 0
    assert ingest.gold_swings([]) == 0


def test_derived_cols_includes_gold_swings():
    m = _match(leads=[0, 5000, 1000, 6000])
    assert ingest.derived_cols(m)["gold_swings"] == 2


def test_offmeta_item_floor_is_1k():
    import inspect
    src = inspect.getsource(ingest.score_weirdness)
    assert ">= 1000" in src, "off-meta item cost floor should be 1k (was 2k)"


# ----------------------- bad-match predicates -----------------------
# The board must never surface abandons, guardians, <60min, or low-kill games.

def test_dur_boring_enforces_60_min_floor():
    assert ingest.DUR_MIN == 3600            # standardized 50->60 min on 2026-07-13
    assert ingest.dur_boring(3599) is True
    assert ingest.dur_boring(3600) is False


def test_has_abandon():
    ok = _match(players=[_player(i + 1, i < 5, leaver="NONE") for i in range(10)])
    bad = _match(players=[_player(1, True, leaver="ABANDONED"),
                          *[_player(i + 2, i + 2 <= 5) for i in range(9)]])
    assert ingest.has_abandon(ok) is False
    assert ingest.has_abandon(bad) is True
    # a brief disconnect that returns is NOT an abandon
    dc = _match(players=[_player(1, True, leaver="DISCONNECTED"),
                         *[_player(i + 2, i + 2 <= 5) for i in range(9)]])
    assert ingest.has_abandon(dc) is False


def test_has_guardian():
    ok = _match(players=[_player(i + 1, i < 5, season_rank=15) for i in range(10)])
    bad = _match(players=[_player(1, True, season_rank=16),      # Guardian > Herald
                          *[_player(i + 2, i + 2 <= 5) for i in range(9)]])
    assert ingest.has_guardian(ok) is False
    assert ingest.has_guardian(bad) is True


def test_low_kpm():
    # 60-min game: <60 total kills => kpm < 1.0 => boring
    assert ingest.low_kpm(_match(duration=3600, radiant_kills=[1], dire_kills=[1])) is True
    assert ingest.low_kpm(_match(duration=3600,
                                 radiant_kills=[40], dire_kills=[40])) is False


# ----------------------- recompute streams (OOM regression) -----------------------
# Bug: recompute did SELECT ... .fetchall() -> materialized the whole 1.5GB corpus
# in RAM -> OOM-killed. Fix: stream ids, fetch one raw at a time. This guards that
# recompute backfills the new columns correctly on a fresh-schema row.

def test_recompute_backfills_new_columns():
    import json
    conn = ingest.get_conn(":memory:")
    m = _match(mid=9500, leads=[0, 100, -100], players=[
        _player(1, True, items=[133]), *[_player(i + 2, i + 2 <= 5) for i in range(9)]])
    ingest.upsert_match(conn, m, avg_rank_tier=12)
    # simulate an OLD row whose new columns were never populated
    conn.execute("UPDATE matches SET avg_gap=NULL, rapier_count=NULL WHERE match_id=9500")
    conn.commit()
    n = ingest.recompute(conn)
    assert n == 1
    row = conn.execute(
        "SELECT avg_gap, rapier_count, lead_flips FROM matches WHERE match_id=9500"
    ).fetchone()
    assert row[0] == pytest.approx((0 + 100 + 100) / 3)
    assert row[1] == 1
    assert row[2] == 2


def test_recompute_does_not_fetchall_raw():
    """Guards the OOM fix: recompute must not load every raw blob into memory at
    once. We assert it selects ids first (a cheap projection), not `raw` in bulk."""
    import inspect
    src = inspect.getsource(ingest.recompute)
    assert "SELECT match_id FROM matches" in src, "recompute should stream ids first"
    assert "SELECT match_id, raw FROM matches" not in src, "recompute must not bulk-fetch raw"


# ----------------------- discord View must be built on the event loop --------------
# Bug: build_board ran Board() inside asyncio.to_thread (a worker thread with no
# running loop). discord.py wires a View's interaction-dispatch machinery from the
# running loop at construction; a thread-built view silently drops every click
# ("interaction failed" with no log). The board MUST construct the view on the loop.

_BOARD = REPO / "spikes" / "menu-v2" / "live_board.py"


def test_build_board_does_not_use_to_thread():
    import re
    src = _BOARD.read_text()
    m = re.search(r"async def build_board\(.*?\n(?:.*\n)*?(?=\n\S|\Z)", src)
    assert m, "build_board not found"
    body = m.group(0)
    assert "to_thread" not in body, (
        "regression: build_board must construct Board() on the event loop, never "
        "via asyncio.to_thread — thread-built discord views don't dispatch clicks"
    )
    assert "Board(" in body, "build_board should construct a Board"


def test_log_usage_is_noop_no_onloop_write():
    """Bug: log_usage did _wconn.commit() on the event loop; under the bloated WAL
    that blocked the loop ~30s, froze the heartbeat, and failed every interaction.
    It must not touch the DB anymore."""
    import re
    src = _BOARD.read_text()
    m = re.search(r"def log_usage\(.*?\n(?:.*\n)*?(?=\n\S|\Z)", src)
    assert m, "log_usage not found"
    body = m.group(0)
    # the actual write statements must be gone (docstring may still describe them)
    assert "INSERT INTO usage" not in body and ".execute(" not in body, (
        "regression: log_usage must not write to the DB on the event loop"
    )


def test_death_receipt_requires_30pct_of_game():
    """Owner 2026-07-13: feeding receipt fired too often (old absolute 20-min OR).
    Now it must require being dead >= 30% of the game and never below."""
    sys.path.insert(0, str(REPO / "spikes" / "menu-v2"))
    import render

    def player(time_dead):
        return {"isRandom": False, "stats": {"deathEvents": [{"timeDead": time_dead,
                "goldFed": 0}], "itemPurchases": [], "itemUsed": []}}

    dur = 3600
    # 27.7% dead -> no feeding receipt
    assert not any("dead" in r for r in render.player_receipts(player(1000), dur))
    # 30% dead -> feeding receipt fires
    assert any("dead" in r for r in render.player_receipts(player(1080), dur))
    # long game, 20 min dead but only 22% -> must NOT fire (the old bug)
    assert not any("dead" in r for r in render.player_receipts(player(1200), 5400))


def test_cycle_checkpoints_wal():
    """Hardening: a re-enabled ingest must bound the WAL each cycle, or the board's
    long-lived reader lets it grow unbounded -> slow reads + hung commits."""
    import inspect
    assert "wal_checkpoint" in inspect.getsource(ingest.cycle)


def test_load_matches_respects_limit():
    """Hardening: load_matches unbounded parses the entire corpus into RAM (OOM)."""
    conn = ingest.get_conn(":memory:")
    for mid in (9601, 9602, 9603):
        ingest.upsert_match(conn, _match(mid=mid), avg_rank_tier=12)
    assert len(ingest.load_matches(conn, limit=1)) == 1
    assert len(ingest.load_matches(conn, limit=2)) == 2


def test_board_sorts_read_columns_not_raw_json():
    """Bug: the board rebuilt sort tables from raw JSON (json_each over the whole
    corpus) at every boot — a multi-minute 1.5GB scan. Sorts must read columns."""
    src = _BOARD.read_text()
    assert "CREATE TEMP TABLE" not in src, (
        "regression: no boot-time temp tables — derived sorts are ingest columns "
        "(lead_flips, avg_gap, rapier_count)"
    )
