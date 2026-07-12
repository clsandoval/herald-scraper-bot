---
phase: quick-260712-nr8
plan: 01
subsystem: data
tags: [sqlite, stratz, discord, ingest, receipts, herald, tdd]

requires:
  - phase: spike-signal-mining
    provides: "VALIDATED thresholds for megas_comeback, chat_lines, feeding, BKB/Midas shame, randomed, mid-TP, buyback-then-died"
provides:
  - "matches.megas_comeback + matches.chat_lines derived columns (recompute-able, zero Stratz cost)"
  - "render.player_receipts() + render.megas_tag() pure, offline-importable helpers"
  - "'Most talkative' SORT and 'Comeback from mega creeps' FILTER on the live board"
  - "Spoiler-aware focus-view feeding/shame receipts + megas match tag"
affects: [match-board, discord-bot-v2]

tech-stack:
  added: []
  patterns:
    - "recompute()-backfillable derived columns: add to derived_cols() return dict only; recompute() UPDATEs every key automatically"
    - "TDD RED/GREEN split for pure render helpers: check_receipts.py written and run failing before render.py implementation existed"
    - "winner-neutral vs outcome-revealing helper separation: player_receipts() never mentions win/mega; megas_tag() is the only spoiler-gated string"

key-files:
  created:
    - spikes/menu-v2/check_receipts.py
  modified:
    - scripts/ingest.py
    - spikes/menu-v2/render.py
    - spikes/menu-v2/live_board.py

key-decisions:
  - "megas_comeback computed from winner's own barracksStatus bitmask (== 0), not fixed to Radiant/Dire — matches LOCKED spike definition exactly"
  - "player_receipts() and megas_tag() kept as two separate pure functions specifically so _focus() can gate only the outcome-revealing tag on spoiler mode"

requirements-completed: [SIGNAL-MEGAS, SIGNAL-CHAT, SIGNAL-RECEIPTS, SIGNAL-SPOILER]

duration: 35min
completed: 2026-07-12
---

# Phase quick-260712-nr8: Board Signals (Megas Comeback, Chat Lines, Focus Receipts) Summary

**Two new recompute-able derived columns (megas_comeback, chat_lines) plus spoiler-aware focus-view receipts (feeding/BKB/Midas/randomed/mid-TP/buyback shame + megas tag) surfaced on the live board, all backfillable from stored raw JSON with zero Stratz cost.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-12T16:40:00Z (approx)
- **Completed:** 2026-07-12T17:17:00Z
- **Tasks:** 2 completed (Task 2 is TDD: test + feat commits)
- **Files modified:** 3 (scripts/ingest.py, spikes/menu-v2/render.py, spikes/menu-v2/live_board.py); 1 created (spikes/menu-v2/check_receipts.py)

## Accomplishments
- Added `megas_comeback` (won while your own base was megged) and `chat_lines` (summed all-chat lines) as recompute-able derived columns, wired through `derived_cols()` → `CREATE TABLE` → `init_db` ALTER migration list → `upsert_match()`. `recompute()` needed no code change — it already UPDATEs every key `derived_cols()` returns.
- Added an offline `signalcheck()` self-test (mirroring the existing `skillcheck()` pattern) covering both winner sides and a `recompute()` idempotency check, exposed via `--signalcheck`.
- Built `render.player_receipts(rawp, duration_s)` (winner-neutral feeding/BKB/Midas/randomed/mid-TP/buyback-then-died tags) and `render.megas_tag(raw)` (outcome-revealing "won from mega creeps" string) as pure, offline-importable helpers, following the TDD RED→GREEN cycle: `check_receipts.py` was written and confirmed failing (`AttributeError`) before either function existed.
- Wired the board: `SORTS["talkative"]` (coalesce(chat_lines, 0)), `FILTERS["megas"]` (matches.megas_comeback = 1), and a new `_focus()` block that renders per-player receipts unconditionally and the megas tag only when `not sp` (spoiler mode off).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add megas_comeback + chat_lines derived columns to ingest** - `c958e74` (feat)
2. **Task 2 (RED): failing test for player_receipts/megas_tag** - `5e7deaa` (test)
2. **Task 2 (GREEN): board sort, filter, and spoiler-aware focus receipts** - `6c6c36a` (feat)

**Plan metadata:** committed separately by the orchestrator (docs commit, not included here per execution constraints)

_Note: Task 2 is a TDD task — RED (failing test) then GREEN (implementation) commits, no REFACTOR commit needed._

## Files Created/Modified
- `scripts/ingest.py` - `derived_cols()` computes `megas_comeback`/`chat_lines`; `CREATE TABLE`, ALTER migration list, and `upsert_match()` INSERT/VALUES/params extended; new `signalcheck()` + `--signalcheck` CLI flag
- `spikes/menu-v2/render.py` - New `BKB_ID`/`MIDAS_ID` constants; `player_receipts(rawp, duration_s)` and `megas_tag(raw)` pure helpers
- `spikes/menu-v2/live_board.py` - `SORTS["talkative"]`, `FILTERS["megas"]`; `_focus()` gains a per-player "Feeding & shame" receipt block (always rendered) and the megas tag (rendered only when `not sp`)
- `spikes/menu-v2/check_receipts.py` (new) - Offline harness asserting every LOCKED threshold plus the winner-neutral/outcome-revealing separation contract

## Decisions Made
- `megas_comeback` reads `barracksStatusRadiant` when Radiant won, else `barracksStatusDire`, and compares to `0` — this matches the LOCKED spike definition (6.7% of corpus) rather than any Radiant/Dire-fixed shortcut.
- `player_receipts()` and `megas_tag()` were kept as two separate functions (not one combined receipts list) so `_focus()` can cleanly gate only the outcome-revealing megas tag behind spoiler mode while always rendering the winner-neutral per-player receipts.

## Deviations from Plan

None - plan executed exactly as written. All five LOCKED thresholds (feeding, BKB, Midas, randomed, mid-TP, buyback-then-died) and the two LOCKED derived-column definitions (megas_comeback, chat_lines) were implemented verbatim from `<context>`/`<interfaces>` with no retuning.

## TDD Gate Compliance

Task 2 (`tdd="true"`) followed the RED/GREEN gate sequence:
- RED: `5e7deaa` — `check_receipts.py` written and confirmed failing (`AttributeError: module 'render' has no attribute 'player_receipts'`) before implementation existed.
- GREEN: `6c6c36a` — `render.player_receipts`/`render.megas_tag` implemented, `live_board.py` wired; `check_receipts.py` now passes.
- No REFACTOR commit was needed (implementation was clean on first pass).

## Issues Encountered
None. The worktree's HEAD initially pointed at a stale base commit (`b955251`) that predated the plan file's commit (`a3320b6`) — per the mandatory `<worktree_branch_check>` setup step, the worktree was hard-reset to `a3320b6` before any work began (working tree was clean, no unique commits lost).

Neither `httpx` nor `discord.py` are installed in the system Python; all verification commands (`--signalcheck`, `--selfcheck`, `--skillcheck`, `check_receipts.py`, `py_compile`) were run via the repo's existing `.venv` (`/home/clsandoval/cs/herald-scraper-bot/.venv/bin/python3`), which already has both dependencies installed from prior quick tasks.

## User Setup Required

None - no external service configuration required. Per the plan's `<output>` MANUAL DEPLOY STEP (not run here): after deploying, run `python scripts/ingest.py --recompute` on the Fly `herald-board` prod machine to backfill `megas_comeback`/`chat_lines` across the whole corpus (zero Stratz cost) before restarting the board process, since its startup `FILT_COUNTS`/`SORTS` queries reference these columns.

## Next Phase Readiness

Board-side code is complete and all offline checks are green. Deploy + recompute is a manual step for the human (explicitly out of scope for this execution per the plan's `<output>` note) — no blockers.

---
*Phase: quick-260712-nr8*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created/modified files found on disk; all three task commit hashes (c958e74, 5e7deaa, 6c6c36a) found in git log.
