"""Offline bounded-reference benchmark; uses a temporary synthetic ledger only.

Run: uv run python scripts/benchmark_reporter_novelty.py --matches 5000 --targets 100
No credentials, API calls, Discord sends, or existing databases are used.
"""
import argparse
import json
from pathlib import Path
import resource
import sqlite3
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from herald import reporter_novelty as novelty


def fixture(mid, now):
    picks = [5003, 5004, 5003, 5004, 5003, 5006, 5003, 5004, 5005, 5005, 5005, 5006]
    players = [{"heroId": ((mid * 10 + slot) % 127) + 1,
                "abilities": [{"abilityId": a, "isTalent": False, "time": i * 60}
                              for i, a in enumerate(picks)],
                "stats": {"itemPurchases": [{"itemId": item, "time": 600 + i * 400}
                            for i, item in enumerate([116, 65, 133, 108, 112, 1, 151, 133])]}}
               for slot in range(10)]
    return ({"match_id": mid, "start_time": now - 86400 + mid,
             "duration": 4800, "avg_rank_tier": 15},
            {"gameMode": "ALL_PICK_RANKED", "players": players}, {"patch": 60})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=5000)
    parser.add_argument("--targets", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.matches <= novelty.MAX_MATCHES or not 1 <= args.targets <= 1000:
        parser.error("matches must be 1..5000 and targets 1..1000")
    now = 1_800_000_000
    with tempfile.TemporaryDirectory(prefix="herald-novelty-benchmark-") as directory:
        path = Path(directory) / "synthetic.db"
        conn = sqlite3.connect(path)
        store = novelty.ReferenceStore(conn)
        started = time.perf_counter()
        for mid in range(1, args.matches + 1):
            candidate, raw, od = fixture(mid, now)
            data = json.dumps(novelty.compact_match(raw, candidate["duration"]), separators=(",", ":"))
            conn.execute("INSERT INTO report_builds(match_id,start_time,patch,version,data) VALUES (?,?,?,?,?)",
                         (mid, candidate["start_time"], od["patch"], novelty.VERSION, data))
        conn.commit()
        prepared = time.perf_counter() - started
        started = time.perf_counter()
        store.begin_pass(now)
        snapshot = time.perf_counter() - started
        started = time.perf_counter()
        first = store.observe_and_score(*fixture(args.matches + 1, now))
        fit = time.perf_counter() - started
        elapsed = []
        for mid in range(args.matches + 2, args.matches + args.targets + 2):
            started = time.perf_counter()
            store.observe_and_score(*fixture(mid, now))
            elapsed.append(time.perf_counter() - started)
        result = {"reference_matches": args.matches, "synthetic_players": args.matches * 10,
                  "prepare_seconds": round(prepared, 3), "snapshot_seconds": round(snapshot, 3),
                  "fit_and_first_score_seconds": round(fit, 3), "warm_targets": args.targets,
                  "warm_median_ms": round(statistics.median(elapsed) * 1000, 3),
                  "warm_max_ms": round(max(elapsed) * 1000, 3),
                  "ledger_mib": round(path.stat().st_size / 2**20, 2),
                  "snapshot_mib": round(conn.execute("PRAGMA temp.page_count").fetchone()[0] *
                    conn.execute("PRAGMA temp.page_size").fetchone()[0] / 2**20, 2),
                  "peak_process_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
                  "sample_skill_status": first["skills"][0]["status"]}
        conn.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
