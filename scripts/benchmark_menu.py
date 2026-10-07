"""Repeatable offline menu latency probe; writes only disposable synthetic DBs.

Run from the checkout: uv run python scripts/benchmark_menu.py --samples 7
The JSON report distinguishes thumbnail-cache-cold renders from warm renders.
It does not drop the operating system's disk cache or simulate Discord transport.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herald import board, ingest, render  # noqa: E402
from herald.simulator import Interaction, synthetic_match  # noqa: E402


def percentiles(values):
    ordered = sorted(values)

    def at(fraction):
        position = (len(ordered) - 1) * fraction
        low, high = math.floor(position), math.ceil(position)
        return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)

    return {"p50": at(0.50), "p95": at(0.95), "min": at(0), "max": at(1)}


def populate(path, count):
    """Clone one rich fixture without repeatedly constructing ability lookups."""
    conn = ingest.get_conn(str(path))
    raw = synthetic_match(0)
    first_id = raw["id"]
    first_start = raw["startDateTime"]
    ingest.upsert_match(conn, raw, 11)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(matches)")]
    slots = {name: index for index, name in enumerate(columns)}
    template = conn.execute("SELECT * FROM matches").fetchone()

    def rows():
        for index in range(1, count):
            row = list(template)
            raw["id"] = first_id + index
            raw["startDateTime"] = first_start + index * 60
            row[slots["match_id"]] = raw["id"]
            row[slots["start_time"]] = raw["startDateTime"]
            row[slots["avg_rank_tier"]] = 11 + index % 5
            row[slots["raw"]] = json.dumps(raw, separators=(",", ":"))
            row[slots["weirdness"]] = (index % 20) / 2
            row[slots["skill_weirdness"]] = (index % 17) / 2
            yield row

    conn.executemany(
        "INSERT INTO matches VALUES (" + ",".join("?" for _ in columns) + ")", rows())
    player_columns = [row[1] for row in conn.execute("PRAGMA table_info(match_players)")]
    projection = ",".join("?" if name == "match_id" else name for name in player_columns)
    conn.executemany(
        f"INSERT INTO match_players SELECT {projection} FROM match_players WHERE match_id=?",
        ((first_id + index, first_id) for index in range(1, count)))
    conn.commit()
    actual = conn.execute("SELECT count(*) FROM matches").fetchone()[0]
    players = conn.execute("SELECT count(*) FROM match_players").fetchone()[0]
    assert actual == count and players == count * 10
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return first_id


async def measure(state, samples, *, cold=False):
    original_query = board._q_sync
    query_times = []

    def timed_query(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_query(*args, **kwargs)
        finally:
            query_times.append((time.perf_counter() - started) * 1000)

    board._q_sync = timed_query
    elapsed, db_time, queries = [], [], []
    try:
        if not cold:
            warmup = await board.build_board(copy.deepcopy(state))
            warmup.stop()
        for _ in range(samples):
            if cold:
                board._thumb_cache.clear()
                if hasattr(board, "_focus_cache"):
                    board._focus_cache.clear()
            query_times.clear()
            started = time.perf_counter()
            view = await board.build_board(copy.deepcopy(state))
            elapsed.append((time.perf_counter() - started) * 1000)
            db_time.append(sum(query_times))
            queries.append(len(query_times))
            view.stop()
    finally:
        board._q_sync = original_query
    return {"render_ms": percentiles(elapsed), "sqlite_ms": percentiles(db_time),
            "query_count": {"min": min(queries), "max": max(queries)}, "samples": samples}


async def slow_ack_probe(first_id, workload, delay_ms):
    """Measure ACK and heartbeat progress while a worker is artificially slow."""
    view = await board.build_board(board.default_state())
    itx = Interaction()
    old_defer = itx.response.defer
    acknowledged = None
    started = time.perf_counter()

    async def defer(**kwargs):
        nonlocal acknowledged
        acknowledged = (time.perf_counter() - started) * 1000
        await old_defer(**kwargs)

    itx.response.defer = defer
    owner = board if workload == "database" else board.charts
    attribute = "_q_sync" if workload == "database" else "networth_lead_png"
    original = getattr(owner, attribute)
    if workload == "chart" and hasattr(board, "_focus_cache"):
        board._focus_cache.clear()

    def slow(*args, **kwargs):
        time.sleep(delay_ms / 1000)
        return original(*args, **kwargs)

    ticks = []

    async def heartbeat():
        while True:
            ticks.append(time.perf_counter())
            await asyncio.sleep(0.005)

    ticker = asyncio.create_task(heartbeat())
    setattr(owner, attribute, slow)
    try:
        changes = {"sort": ["kills"]} if workload == "database" else {"mode": "focus", "match": first_id}
        await view._update(itx, **changes)
        elapsed = (time.perf_counter() - started) * 1000
    finally:
        setattr(owner, attribute, original)
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)
        view.stop()
        if itx.view is not None:
            itx.view.stop()
    gaps = [(right - left) * 1000 for left, right in zip(ticks, ticks[1:])]
    return {"injected_delay_ms_per_call": delay_ms, "ack_ms": round(acknowledged, 3),
            "complete_ms": round(elapsed, 3), "heartbeat_ticks": len(ticks),
            "max_heartbeat_gap_ms": round(max(gaps, default=0), 3)}


async def benchmark(sizes, samples, delay_ms):
    report = {"offline_only": True, "samples_per_scenario": samples,
              "fixture": "One repeated synthetic rich match; distinct IDs/start times and rank/score columns.",
              "cache_note": "Cold means thumbnail cache cleared; OS/SQLite disk caches are not dropped.",
              "timing_note": "SQLite time includes connection/setup/query/close, excluding worker scheduling. No Discord network transport.",
              "archives": []}
    original_path, original_emojis = board.DB_PATH, render._emoji
    render._emoji = {}
    try:
        with tempfile.TemporaryDirectory(prefix="herald-menu-benchmark-") as temporary:
            for size in sizes:
                path = Path(temporary) / f"archive-{size}.db"
                started = time.perf_counter()
                first_id = populate(path, size)
                population_ms = (time.perf_counter() - started) * 1000
                print(f"Populated {size:,} synthetic matches; measuring renders.", file=sys.stderr, flush=True)
                board.DB_PATH = str(path)
                board._thumb_cache.clear()
                default = board.default_state()
                focus = {**default, "mode": "focus", "match": first_id}
                scenarios = {
                    "list_cold": await measure(default, samples, cold=True),
                    "list_warm": await measure(default, samples),
                    "sort_kills": await measure({**default, "sort": ["kills"]}, samples),
                    "filter_highrank": await measure({**default, "filters": ["highrank"]}, samples),
                    "advanced_hero_item": await measure({**default, "adv": {
                        "heroes": ["axe"], "items": [("black_king_bar", 1)]}}, samples),
                    "focus_items": await measure(focus, samples),
                    "focus_cold": await measure(focus, samples, cold=True),
                    "focus_skills": await measure({**focus, "detail": "skills"}, samples),
                    "focus_spoiler": await measure({**focus, "spoiler": True}, samples),
                }
                report["archives"].append({"matches": size, "players": size * 10,
                    "database_bytes": path.stat().st_size, "population_ms": round(population_ms, 3),
                    "scenarios": scenarios, "slow_work": {
                        workload: await slow_ack_probe(first_id, workload, delay_ms)
                        for workload in ("database", "chart")}})
                print(f"Finished {size:,} matches: warm list p95 "
                      f"{scenarios['list_warm']['render_ms']['p95']} ms; advanced p95 "
                      f"{scenarios['advanced_hero_item']['render_ms']['p95']} ms.",
                      file=sys.stderr, flush=True)
    finally:
        board.DB_PATH, render._emoji = original_path, original_emojis
        board._thumb_cache.clear()
        if hasattr(board, "_focus_cache"):
            board._focus_cache.clear()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 1000, 10000])
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--slow-ms", type=float, default=150)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or any(size < 1 for size in args.sizes) or args.slow_ms < 0:
        parser.error("sizes and samples must be positive; slow-ms must be nonnegative")
    result = asyncio.run(benchmark(args.sizes, args.samples, args.slow_ms))
    output = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(output + "\n")
    print(output)


if __name__ == "__main__":
    main()
