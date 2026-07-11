---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Phase 1: Waves 1-2 complete; Wave 3 (live deploy) held pending Anthropic MA key + paid-infra go-ahead"
last_updated: "2026-07-01T12:40:49.140Z"
last_activity: 2026-07-01
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-01)

**Core value:** Surface Herald matches worth reviewing on stream in response to a question — without ever spamming the channel.
**Current focus:** Phase 1 — Clean Platform Skeleton

## Current Position

Phase: 1 (Clean Platform Skeleton) — EXECUTING
Plan: 3 of 3 (plan 01-01 complete)
Status: Ready to execute
Last activity: 2026-07-11 - Completed quick task 260711-wqo: Board usage telemetry + /heralds hint

Progress: [███████░░░] 67%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 1 | 1 | 25 min | 25 min |

**Recent Trend:**

- Last 5 plans: 01-01 (25 min, 4 tasks, 43 files)
- Trend: -

*Updated after each plan completion*
| Phase 01 P02 | 45min | 3 tasks | 20 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pre-Phase 1: Fork `daimon-cma-open-source` trimmed (core + Discord adapter + scheduler adapter only) rather than build fresh
- Pre-Phase 1: OpenDota for discovery, Stratz GraphQL for enrichment (spike-validated: OD Herald pubs are unparsed, Stratz has the same matches fully parsed)
- Pre-Phase 1: Bot ranks candidates via the `herald-replay-quality` skill; a human picks the final replay — comedic payload isn't computable
- [Phase 01-02]: HeraldBot written fresh (not trimmed from daimon's 1170-line bot.py) to avoid orphaned imports across excluded panel/setup modules
- [Phase 01-02]: Scheduler's main.py is a documented inert stub, not a verbatim copy -- daimon's real file depends on billing/defaults/ma_resolver/headless_runner machinery excluded from this fork
- [Phase 01-02]: docker-compose services invoke venv binaries directly (alembic, python -m) instead of uv run -- uv run in the read-only runtime image fails trying to write uv.lock

### Pending Todos

- Menu-first pivot: SPEC-MATCH-BOARD.md written from validated spike (2026-07-10) — fold into ROADMAP when re-planning Phase 2+ (menu board replaces/precedes the visible AI query layer)

### Blockers/Concerns

- RESOLVED (01-01): Leaked Telegram bot token revoked via @BotFather and scrubbed from all git history (git filter-repo + force-push). Zero token occurrences remain in history.
- Phase 5: Skill scoring signals used in Phase 4 will be based on summary-only data until Phase 5 lands richer per-player/net-worth-lead data — expect Phase 4 skill output to sharpen after Phase 5

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260710-by5 | Herald match ingest script: OpenDota discovery → Stratz enrichment → local SQLite, 10-day retention | 2026-07-10 | e5385af | [260710-by5-herald-match-ingest-script-opendota-disc](./quick/260710-by5-herald-match-ingest-script-opendota-disc/) |
| 260711-wqo | Board usage telemetry (ts + Discord user per interaction / /heralds use) into `usage` table + /heralds hint on public board | 2026-07-11 | fcacedf | [260711-wqo-add-usage-telemetry-timestamp-discord-us](./quick/260711-wqo-add-usage-telemetry-timestamp-discord-us/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Data depth | DATA-V2-01: full per-minute-per-player time-slice tables | Deferred to v2 | Requirements definition |
| Intake/UX | INTK-V2-01: viewer replay-submission pipeline | Deferred to v2 | Requirements definition |
| Intake/UX | UX-V2-01: slash-command interface | Deferred to v2 | Requirements definition |

## Session Continuity

Last session: 2026-07-01T12:40:49.133Z
Stopped at: Phase 1: Waves 1-2 complete; Wave 3 (live deploy) held pending Anthropic MA key + paid-infra go-ahead
Resume file: .planning/phases/01-clean-platform-skeleton/01-03-PLAN.md
