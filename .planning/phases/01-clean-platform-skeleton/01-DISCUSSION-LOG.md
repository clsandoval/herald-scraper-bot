# Phase 1: Clean Platform Skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 1-Clean Platform Skeleton
**Areas discussed:** Fork strategy & git history, Deploy target (Fly app + Postgres), Phase 1 'done' bar, Anthropic MA access

---

## Fork strategy & git history

| Option | Description | Selected |
|--------|-------------|----------|
| Copy into this repo, revoke-only | Keep git history; revocation kills the token; skip history rewrite | |
| Fresh repo, clean history | New repo/remote, no leaked-secret trace; loses history, more setup | |
| Copy in + scrub history | Keep repo, rewrite history with git filter-repo to purge the token | ✓ |

**User's choice:** Copy in + scrub history
**Notes:** filter-repo requires a one-time force-push; safe since prod runs off its Fly machine, not the repo. Work on main; prod not redeployed until promotion.

---

## Deploy target — Fly app

| Option | Description | Selected |
|--------|-------------|----------|
| New app: herald-reviews-scout | Separate test app, region sea | |
| herald-scraper-bot-test | Explicit test-suffixed twin | ✓ |
| Reuse prod app | Deploy over herald-scraper-bot (violates guardrail) | |

**User's choice:** herald-scraper-bot-test
**Notes:** Prod herald-scraper-bot stays untouched.

---

## Deploy target — Postgres

| Option | Description | Selected |
|--------|-------------|----------|
| Fly managed Postgres | `fly postgres create` + attach; simplest, same platform | ✓ |
| External (Neon/Supabase) | Managed elsewhere; one more service + secret | |
| Fly volume + container | Self-run; cheapest, you own upgrades/backups | |

**User's choice:** Fly managed Postgres

---

## Phase 1 'done' bar

| Option | Description | Selected |
|--------|-------------|----------|
| Boot + connect + migrations | Deploy/boot/migrate/login only, no behavior | |
| Also add @bot → pong | Plus a trivial mention→pong health round-trip | ✓ |

**User's choice:** Also add @bot → pong
**Notes:** The pong reply proves the full deploy→boot→login→mention→reply loop before Phase 2 builds real behavior.

---

## Anthropic MA access

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, I have MA access | MA key ready; planner treats MA as ready | |
| Not sure — verify first | Flag as a research/verify item | |
| No MA — use plain API | Build on standard Claude API tool-use instead | |

**User's choice:** Free-text — "I'll make a new key, wait"
**Notes:** MA remains the approach. User is creating a new dedicated Anthropic API key with MA beta access. It's a deploy-time Fly secret (`ANTHROPIC_API_KEY`), not committed, not needed for the context doc.

## Claude's Discretion

- Exact daimon file-copy boundaries, Dockerfile/fly.toml adaptation, config shape, and the Alembic baseline migration.

## Deferred Ideas

- Match ingestion, richer schema, SQL query tool, scoring skill, hero_norms — Phase 2+.
- Promotion/cutover from test app to prod — later milestone.
