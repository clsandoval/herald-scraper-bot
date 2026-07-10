---
phase: quick-260710-by5
plan: 01
subsystem: data
tags: [sqlite, httpx, opendota, stratz, ingest, herald]

requires: []
provides:
  - "scripts/ingest.py: standalone Herald match ingest (discover -> enrich -> prune -> read)"
  - "load_matches(conn) reader with board-parity dict shape for the future Match Board"
affects: [match-board, discord-bot-v2]

tech-stack:
  added: []
  patterns:
    - "Single-file PONYTAIL script: stdlib sqlite3 + httpx, no ORM, dicts throughout"
    - "Lazy env var read inside stratz_fetch() only, so --selfcheck runs with zero env vars"
    - "match_view()/derived_cols() as single source of truth for derived semantics, kept in exact parity with spikes/menu-v2/render.py load_matches()"

key-files:
  created:
    - scripts/ingest.py
  modified:
    - .gitignore

key-decisions:
  - "Reused the exact derived-column formulas from spikes/menu-v2/render.py rather than re-deriving, to guarantee board parity"
  - "Pending queue gates enrichment behind a 180s discovered_at age check to respect Stratz's known ingest lag"
  - "attempts<8 cap with drop-on-exhaustion prevents pending table from growing unbounded on permanently-unenrichable matches"

requirements-completed: [HERALD-INGEST-01]

duration: 25min
completed: 2026-07-10
---

# Phase quick-260710-by5: Herald Match Ingest Script (OpenDota + Stratz) Summary

**Single-file `scripts/ingest.py` that discovers Herald-bracket matches on OpenDota, enriches them via Stratz GraphQL, stores derived sort/filter columns + raw JSON in SQLite, and exposes a `load_matches()` reader matching the menu-v2 board's exact dict shape.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-10T08:40:00Z (approx)
- **Completed:** 2026-07-10T08:49:37Z
- **Tasks:** 2 completed
- **Files modified:** 2 (scripts/ingest.py created, .gitignore modified)

## Accomplishments
- Built a standalone, dependency-free (stdlib sqlite3 + httpx only) ingest pipeline with discover/enrich/prune/cycle stages and a `--selfcheck` offline self-test.
- Verified offline parity: `--selfcheck` passes 38 matches / 380 players against the committed fixture, including recomputed `kills`/`comeback_gold` spot-checks and full `load_matches()` key-shape/order parity with `spikes/menu-v2/render.py`.
- Ran a live end-to-end smoke test against real OpenDota + Stratz APIs: first cycle discovered 40 candidate matches into `pending`; a second cycle (after the ~180s Stratz ingest-lag window passed) enriched 33 of them into `matches` with zero auth/UA/httpx errors.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write scripts/ingest.py and pass the offline --selfcheck** - `e5385af` (feat)
2. **Task 2: LIVE smoke test against real OpenDota + Stratz** - no repo changes (script worked correctly on first live run; no bug fix needed)

**Plan metadata:** to be committed by orchestrator

## Files Created/Modified
- `scripts/ingest.py` - Standalone Herald ingest script: schema (`matches`, `match_players`, `pending`), `match_view()`/`derived_cols()` derived-semantics transform, OpenDota discovery, Stratz enrichment, prune, `load_matches()` reader, `--selfcheck`, `--loop` CLI.
- `.gitignore` - Added `herald.db`, `herald.db-wal`, `herald.db-shm` (runtime SQLite artifacts).

## Live Smoke Test Results

Ran against real APIs using the spike env's `STRATZ_API_TOKEN`, DB pointed at a scratchpad path (`HERALD_DB=.../smoke.db`), via `.venv/bin/python scripts/ingest.py`:

| Metric | Cycle 1 (t=0) | Cycle 2 (t=~190s later) |
|---|---|---|
| discovered | 40 | 15 |
| enriched | 0 (ingest lag) | 33 |
| not-ready | 0 | 7 |
| dropped | 0 | 0 |
| matches (total) | 0 | 33 |
| pending (total) | 40 | 22 |

Final smoke.db state (verified via `sqlite3` CLI):
- `matches`: 33 rows
- `match_players`: 330 rows (== 10 x 33 matches, as expected)
- `pending`: 22 rows, `avg_rank_tier` range 12-15 (within the 10-15 discovery filter)
- `raw` column on a sampled row parsed successfully as valid JSON (`json.loads` round-trip confirmed)
- No Stratz 403/auth/User-Agent errors in any HTTP call log line
- Zero occurrences of `STRATZ_API_TOKEN` or `Bearer ` in command output or logs

Token hygiene: the spike env file was sourced into a subshell only (`set -a; source ...; set +a`), never echoed/printed/catted, and is not part of any commit. `smoke.db` lives entirely in the scratchpad directory outside the repo and was not added to git.

## Deviations from Plan

None — plan executed exactly as written. `scripts/ingest.py` matches the spec's DDL, formulas, and control flow verbatim; the live smoke test passed on the first attempt with no need for the anticipated Stratz-403/User-Agent bug fix.

## Known Stubs

None. Every code path (discover, enrich, prune, cycle, selfcheck, CLI) is fully implemented and exercised by either the offline selfcheck or the live smoke test.

## Threat Flags

None. All network surface (OpenDota GET, Stratz GraphQL POST) and the token-handling path were anticipated in the plan's `<threat_model>` and implemented per the locked mitigation plan (lazy env read, no token logging, parameterized SQL, rate-limit backoff).

## Self-Check: PASSED

- FOUND: `scripts/ingest.py` (created, 450 insertions, min_lines requirement of 250 satisfied)
- FOUND: commit `e5385af` in `git log --oneline --all`
- FOUND: `.venv/bin/python scripts/ingest.py --selfcheck` -> `selfcheck OK: 38 matches / 380 players`, exit 0
- FOUND: live smoke test landed 33 matches / 330 match_players / 22 pending rows in scratchpad `smoke.db`, zero auth/UA errors, zero token exposure
