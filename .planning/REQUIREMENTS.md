# Requirements: Herald Reviews Scout

**Defined:** 2026-07-01
**Core Value:** Surface Herald matches worth reviewing on stream in response to a question — without ever spamming the channel.

## v1 Requirements

Requirements for the initial working bot. Each maps to a roadmap phase.

### Platform (fork & cleanup)

- [x] **PLAT-01**: Fork daimon trimmed — keep core (db/models/config/turn/skills), Discord adapter, and scheduler adapter; strip multi-tenant, MCP, Slack, billing, provisioning, OAuth
- [x] **PLAT-02**: All secrets loaded from env / Fly secrets; no secrets committed to source
- [x] **PLAT-03**: Leaked Telegram bot token revoked; legacy Telegram/Lambda/dead code (`bot.py`, `lambda_function.py`, `database.py`) removed
- [ ] **PLAT-04**: Deploys on Fly.io with Postgres attached and Alembic migrations run on release

### Data model

- [ ] **DATA-01**: Postgres schema (SQLAlchemy + Alembic migration) for Herald matches, keyed by match_id, idempotent on re-ingest
- [ ] **DATA-02**: Per-match summary features stored: duration, total kills, radiant/dire win, patch, avg rank tier
- [ ] **DATA-03**: Per-player rows stored: hero_id, K/D/A, GPM/XPM, net worth, item list + counts, lane/role, time-dead where available
- [ ] **DATA-04**: Per-match net-worth-lead array (from Stratz) stored for throw/comeback detection
- [ ] **DATA-05**: Only the computable review-worthiness signals the `herald-replay-quality` skill needs are persisted (per spike B ledger)

### Ingestion

- [ ] **ING-01**: Poll OpenDota `/publicMatches` and select Herald matches (rank_tier 10–15)
- [ ] **ING-02**: Enrich each Herald match with parsed detail via Stratz GraphQL (per-minute curves, item timings, lanes, per-player stats)
- [ ] **ING-03**: Persist enriched matches, deduping by match_id (skip already-stored)
- [ ] **ING-04**: Prune matches older than the retention window (default 30 days, configurable)
- [ ] **ING-05**: Retry with backoff on OpenDota/Stratz errors and outages (OD 5xx observed mid-spike)
- [ ] **ING-06**: Run ingestion on a schedule via the scheduler adapter — storing only, never posting

### Domain skill

- [ ] **SKILL-01**: Productionize the `herald-replay-quality` skill (weighted 0–100 rubric from spike B) and bind it to the query agent

### Query agent

- [ ] **QRY-01**: The agent answers a natural-language question by querying the match DB
- [ ] **QRY-02**: The agent has a read-only SQL tool scoped to the match tables
- [ ] **QRY-03**: The agent applies the `herald-replay-quality` skill to score and rank candidate matches
- [ ] **QRY-04**: The agent returns a ranked shortlist of candidates, each with a match link/ID and a one-line reason it's review-worthy

### Discord interface

- [ ] **DISC-01**: Bot responds only when `@mentioned`; it never posts unprompted
- [ ] **DISC-02**: Bot replies in-channel with the ranked shortlist, handling concurrent requests safely

## v2 Requirements

Deferred. Tracked, not in current roadmap.

### Data depth

- **DATA-V2-01**: Store full per-minute-per-player time-slice tables (only if a query demands granularity beyond the net-worth array)

### Intake / UX

- **INTK-V2-01**: Viewer replay-submission pipeline (viewers submit specific matches for review)
- **UX-V2-01**: Slash-command interface as an alternative to mentions

## Out of Scope

| Feature | Reason |
|---------|--------|
| Scheduled auto-posting / broadcasting | This is the spam that triggered the overhaul — the whole point is to stop it |
| Non-Herald brackets | Bot's niche is Jenkins' Herald Reviews; keep the DB focused |
| Bot picking the final replay to review | Comedic/human-interest payload isn't computable (spike B) — bot ranks, human picks |
| Slack / CLI / multi-tenant / billing | Single-purpose personal bot; daimon's enterprise scaffolding is stripped |
| Manual Stratz parse requests | Stratz already returns Herald matches parsed (spike A) — no parse-request pipeline needed |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAT-01 | Phase 1 | Complete |
| PLAT-02 | Phase 1 | Complete |
| PLAT-03 | Phase 1 | Complete |
| PLAT-04 | Phase 1 | In Progress (buildable/migrating locally — live Fly deploy is 01-03) |
| DATA-01 | Phase 2 | Pending |
| ING-03 | Phase 2 | Pending |
| QRY-01 | Phase 2 | Pending |
| QRY-02 | Phase 2 | Pending |
| QRY-04 | Phase 2 | Pending |
| DISC-01 | Phase 2 | Pending |
| DATA-02 | Phase 3 | Pending |
| ING-01 | Phase 3 | Pending |
| ING-02 | Phase 3 | Pending |
| ING-04 | Phase 3 | Pending |
| ING-05 | Phase 3 | Pending |
| ING-06 | Phase 3 | Pending |
| SKILL-01 | Phase 4 | Pending |
| QRY-03 | Phase 4 | Pending |
| DATA-03 | Phase 5 | Pending |
| DATA-04 | Phase 5 | Pending |
| DATA-05 | Phase 5 | Pending |
| DISC-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-07-01*
*Last updated: 2026-07-01 after roadmap creation*
