# Walking Skeleton — Herald Reviews Scout

**Phase:** 1
**Generated:** 2026-07-01

## Capability Proven End-to-End

A person in the test Discord server can `@mention` the deployed bot and get a `pong` reply — a
round-trip that boots the trimmed daimon fork on Fly.io, connects to an attached Postgres with
Alembic migrations applied on release, logs into Discord, receives the mention, and replies —
while the bot stays silent when not mentioned.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Base architecture | Fork of `daimon-cma-open-source`, trimmed to core + Discord adapter + scheduler adapter | Reuse working MA agent-loop + skills-as-repos + Postgres/Fly plumbing (PROJECT.md, D-04); strip multi-tenant/MCP/Slack/CLI/billing/OAuth |
| Language / runtime | Python 3.12, `uv` workspace (multi-package) | Inherited from daimon; `uv.lock` gives pinned reproducible deps |
| Data layer | Postgres via SQLAlchemy 2.0 async (`asyncpg`) + Alembic | daimon's chosen ORM; async engine required for the Discord event loop (D-06) |
| Config / secrets | `pydantic-settings` nested `DAIMON_<SECTION>__<FIELD>`, all from env / Fly secrets; `SecretStr` on tokens | Type-safe fail-fast config; no secret literals in source (PLAT-02) |
| Agent loop | Anthropic Managed Agents (beta) turn driver wired but NOT invoked by the Phase 1 pong | D-09 keeps MA for Phase 2+; pong needs no turn |
| Discord adapter | New minimal `HeraldBot(discord.Client)` — `on_message` → mention-gate → `pong` | daimon's 1170-line bot.py is not trimmable in place (RESEARCH); write thin, keep the package/deploy skeleton |
| Migrations on deploy | Fly `release_command = "alembic upgrade head"` | Runs on the new image before traffic swaps (D-08, Pattern 3) |
| Entrypoint | `docker/entrypoint.sh` = `exec "$@"` — NO `daimon defaults apply` | daimon's defaults-apply provisions tenants/MA against live APIs; excluded machinery (Pitfall 1) |
| Deployment target | NEW Fly app `herald-scraper-bot-test`, region `sea`, own Postgres, test Discord server | Prod `herald-scraper-bot` stays on its running release, untouched (D-03/D-05/D-07) |
| Directory layout | `packages/core` (daimon-core) + `packages/adapters/{discord,scheduler}`, `alembic.ini` at root pointing at `packages/core/alembic` | Mirrors daimon's uv-workspace shape; trims by removing whole adapter packages, not editing within them |
| Schema baseline | Empty `Base` (`_models.py`) → empty `0001_baseline` migration | Phase 1 has zero DATA-* requirements; domain tables arrive in Phase 2 |

## Stack Touched in Phase 1

- [x] Project scaffold — uv workspace, `daimon-core` + discord/scheduler adapter packages, ruff config
- [x] Routing — Discord `on_message` handler (the one real "route": mention → pong)
- [x] Database — real connection + Alembic baseline migration applied on release (no domain read/write yet; empty schema by design)
- [x] "UI" — the `@mention` → `pong` interaction wired to the deployed process
- [x] Deployment — running on Fly `herald-scraper-bot-test` with attached Postgres; local `docker compose up` documented as the full-stack local run

## Out of Scope (Deferred to Later Slices)

- Match schema / domain tables (`matches`, per-player rows, net-worth arrays) — Phase 2/3/5
- Any ingestion (OpenDota discovery, Stratz enrichment, dedupe, prune, retry/backoff) — Phase 3
- The read-only SQL tool and any MA turn actually being invoked — Phase 2
- `herald-replay-quality` skill binding and scoring — Phase 4
- Scheduler adapter running a real job / being wired into `fly.toml` processes — Phase 3 (files copied inert now)
- Concurrency handling, message chunking, reply hardening — Phase 6
- Promotion/cutover from `herald-scraper-bot-test` to prod `herald-scraper-bot` — later milestone

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its
architectural decisions (Postgres/SQLAlchemy/Alembic, uv workspace, MA turn driver, Fly test app):

- Phase 2: `@mention` a question → MA agent uses a read-only SQL tool → replies with a candidate match from a minimal seeded `matches` table
- Phase 3: scheduler adapter runs unattended ingestion (OpenDota → Stratz → dedupe → prune) writing to the DB, never posting
- Phase 4: the query agent ranks candidates via the productionized `herald-replay-quality` skill
- Phase 5: per-player rows + net-worth-lead arrays deepen the data for throw/comeback/troll-build signals
- Phase 6: concurrent mentions + Discord message-size limits handled safely for daily live use
