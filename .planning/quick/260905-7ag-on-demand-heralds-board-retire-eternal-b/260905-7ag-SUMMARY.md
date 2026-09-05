---
phase: quick-260905-7ag
plan: 01
subsystem: infra
tags: [discord.py, sqlite, docker, fly.io, board]

requires: []
provides:
  - /heralds slash command as the sole entry point to the Herald match board
  - on_ready reduced to command-tree sync only (no standing channel post)
  - Dockerfile.board running ingest.py --loop 1800 alongside the board again
  - regression test guarding against the eternal board ever coming back
affects: [board deployment, ingest scheduling]

tech-stack:
  added: []
  patterns:
    - "on-demand-only Discord views: every board render is ephemeral, triggered by a slash command, with no bot-initiated posts"

key-files:
  created: []
  modified:
    - spikes/menu-v2/live_board.py
    - Dockerfile.board
    - tests/test_herald_board_regression.py

key-decisions:
  - "Deleted refresh_board and the on_ready standing post entirely rather than gating them behind a flag — the always-up board was the root cause of the DB-lock/CPU/OOM contention (issue #4), so there is no config path that should re-enable it"
  - "Removed the public '/heralds hint' TextDisplay and the private state flag that suppressed it, since every board is ephemeral now and the flag has no remaining reader"
  - "Dockerfile.board CMD switched to shell form (ingest backgrounded, board execs as PID 1) so Fly's signals still reach the board process"

requirements-completed: [BOARD-ONDEMAND, BOARD-READONLY, INGEST-UNPAUSE, CLEANUP-STALE]

duration: 10min
completed: 2026-09-05
---

# Quick Task 260905-7ag: On-demand /heralds board, eternal board retired Summary

**Deleted the always-up board (`on_ready` standing post + `refresh_board` timer) from `live_board.py`, made `/heralds` the sole entry point, and un-paused the ingest loop in `Dockerfile.board` now that the board no longer holds a long-lived render task against the same SQLite file.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-09-05
- **Tasks:** 3/3
- **Files modified:** 3

## Accomplishments
- `on_ready` now only syncs the command tree and logs — no channel fetch, no stale-post sweep, no standing board post, no `refresh_board` timer task
- `/heralds` is the only way to open a board; it is always ephemeral (the `private` flag and the public "type /heralds" hint it suppressed are both gone, since there is no longer a non-private board)
- `Dockerfile.board` CMD restored to run `scripts/ingest.py --loop 1800` in the background alongside the board in the foreground (`exec`'d as PID 1)
- New regression test (`test_board_is_on_demand_only`) asserts `refresh_board` is gone, `/heralds` stays registered, and `on_ready` never posts a standing message again
- Full regression suite passes: 19/19 (18 pre-existing + 1 new)

## Task Commits

1. **Task 1: Make /heralds the sole board entry point** - `74cdb55` (feat)
2. **Task 2: Restore the ingest loop in Dockerfile.board and delete stale spike leftovers** - `2486a2c` (fix)
3. **Task 3: Lock the retirement in with regression tests** - `6a67be2` (test)

_Plan metadata commit (STATE.md/SUMMARY.md) is applied separately by the orchestrator._

## Files Created/Modified
- `spikes/menu-v2/live_board.py` - deleted `refresh_board`, the `on_ready` standing-post block, the unread `CHANNEL` constant, and the public board hint/`private` flag; updated the module docstring to describe on-demand behavior
- `Dockerfile.board` - CMD now runs `ingest.py --loop 1800` in the background and `exec`s the board in the foreground; removed the "INGEST LOOP PAUSED" comment block
- `tests/test_herald_board_regression.py` - added `test_board_is_on_demand_only`, guarding against the eternal board pattern regressing

## Decisions Made
- No existing test asserted the eternal board's existence, so nothing needed inversion/removal per Task 3's instructions — only a new guarding test was added.
- The stale untracked spike leftovers (`packages/core/daimon/core/match_embed.py`, `spikes/embed-v2/`) were already absent from this worktree (they were untracked in the main tree and therefore never materialized in this git worktree checkout) — confirmed via `grep` that no live code imports either path (only `.planning/spikes/menu-v2/README.md` mentions `embed-v2` as prior-art documentation, left untouched per plan instructions) and via direct file-existence checks that both paths are already gone. No deletion action was needed.

## Deviations from Plan

None - plan executed exactly as written. The one plan-anticipated edge case (stale spike files already absent) was explicitly called out in the orchestrator's notes and confirmed harmless per the plan's own grep-before-delete safety instruction.

## Issues Encountered

None. The worktree's HEAD had drifted ahead of the expected base commit at agent start (pointing at a commit from a stale prior session); per the mandatory branch-check protocol this was corrected with `git reset --hard` to the orchestrator-specified base commit before any task work began, since the working tree was clean (no uncommitted work lost).

## User Setup Required

None - no external service configuration required. No deploy was attempted (Fly CLI intentionally left logged out per plan constraints); `fly.board.toml` and `scripts/ingest.py` show no diff.

## Next Phase Readiness

The board module and Dockerfile are ready for a future manual `fly deploy -c fly.board.toml` (out of scope for this task). Ingest will resume running continuously once deployed, closing part 1 of issue #4. No blockers.

---
*Phase: quick-260905-7ag*
*Completed: 2026-09-05*

## Self-Check: PASSED

All created/modified files exist on disk and all three task commit hashes (74cdb55, 2486a2c, 6a67be2) are present in git log.
