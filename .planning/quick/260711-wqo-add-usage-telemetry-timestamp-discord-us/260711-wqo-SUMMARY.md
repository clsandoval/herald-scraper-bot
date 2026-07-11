---
phase: quick-260711-wqo
plan: 01
subsystem: telemetry
tags: [discord.py, sqlite, usage-tracking]

# Dependency graph
requires:
  - phase: quick-260710-by5
    provides: herald.db schema and ingest conventions (WAL, busy_timeout, INTEGER epoch timestamps)
provides:
  - usage(ts, user_id, user_name, action) table in herald.db
  - log_usage() helper for future board interaction instrumentation
  - /heralds discoverability hint on the public board
affects: [herald-board]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dedicated read-write SQLite connection alongside a pre-existing read-only one, for a single shared writer table"
    - "log and continue" telemetry writes (never propagate failures into a Discord interaction)

key-files:
  created: []
  modified: [spikes/menu-v2/live_board.py]

key-decisions:
  - "Used a second sqlite3 connection (_wconn) instead of reopening _conn as read-write, since _conn is opened with mode=ro and shared elsewhere"
  - "Gated the /heralds hint with a private flag on state rather than duplicating default_state(), since both boards share it"

patterns-established:
  - "Any future write path against herald.db from live_board.py should reuse _wconn, not open a third connection"

requirements-completed: [QUICK-TELEMETRY-01, QUICK-HINT-01]

# Metrics
duration: 15min
completed: 2026-07-11
---

# Quick Task 260711-wqo: Usage Telemetry + /heralds Hint Summary

**Added a `usage` table + `log_usage()` helper wired into all three board interaction entry points, plus a static `/heralds` hint on the public board footer.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-11T23:39:35Z
- **Tasks:** 2 completed
- **Files modified:** 1

## Accomplishments
- Every board button/select interaction, Advanced modal submit, and `/heralds` slash invocation now writes one row to a new `usage(ts, user_id, user_name, action)` table in herald.db
- Writes go through a dedicated read-write connection (`_wconn`) with WAL + `busy_timeout=30000`, matching ingest.py conventions, since the existing `_conn` is read-only
- `log_usage()` never raises — failures are caught and logged as a warning, matching the codebase's "log and continue" DB error-handling precedent
- Public live board's list view now shows a small static footer line pointing viewers to `/heralds` for their own private board; the ephemeral `/heralds` board suppresses it via a `private` state flag

## Task Commits

Each task was committed atomically:

1. **Task 1: usage table + read-write conn + log_usage helper wired into all three entry points** - `5a99d7e` (feat)
2. **Task 2: static /heralds hint line on the public board main view** - `3e762b0` (feat)

**Plan metadata:** committed separately by the orchestrator (docs commit not made by this executor per constraints)

## Files Created/Modified
- `spikes/menu-v2/live_board.py` - Added `import time`, `_wconn` (read-write SQLite conn with WAL + busy_timeout), `usage` table DDL, `log_usage(user, action)` helper, three call sites (`_update`, `AdvModal.on_submit`, `board_cmd`), and the `/heralds` hint TextDisplay gated on `st.get("private")`

## Decisions Made
- Second SQLite connection (`_wconn`) chosen over converting `_conn` to read-write, since `_conn` is explicitly opened `mode=ro` via URI and is shared/relied upon elsewhere as read-only.
- `private` flag set directly on the state dict in `board_cmd` (after `default_state()`) rather than parameterizing `default_state()` itself, since both the public and ephemeral boards share that function and only one caller needs the flag.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Telemetry uses the same local/prod `herald.db` file already in use (respects `HERALD_DB` env var).

## Next Phase Readiness

- `usage` table is queryable ad hoc from herald.db (e.g. `sqlite3 herald.db "SELECT * FROM usage ORDER BY ts DESC LIMIT 20"`) — no dashboards or aggregation views were built, per plan scope.
- No blockers. This is a quick task, independent of the Phase 1 roadmap track.

---
*Phase: quick-260711-wqo*
*Completed: 2026-07-11*

## Self-Check: PASSED

- FOUND: spikes/menu-v2/live_board.py
- FOUND: 5a99d7e
- FOUND: 3e762b0
