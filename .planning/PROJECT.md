# Herald Scraper Bot — Overhaul (Herald Reviews Scout)

## What This Is

A Discord bot that helps the streamer **Jenkins** find good Dota 2 Herald-bracket
matches to feature on his popular **"Herald Reviews"** series. It quietly ingests
recent valid Herald matches into a database (pruning old ones) and answers
natural-language questions on demand — e.g. "find me recent Herald matches where
X happened" — by writing SQL against that data and reasoning about it with Dota
domain knowledge. It only speaks when asked; it does **not** broadcast.

This is a hard pivot from the current bot, which auto-scrapes and posts match
reports on a schedule (the behavior server members are annoyed by).

## Core Value

Surface **Herald matches worth reviewing on stream** in response to a question —
without ever spamming the channel.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet for the new direction — the current auto-posting bot is being replaced.)

### Active

<!-- Current scope. Building toward these. Hypotheses until shipped + validated. -->

- [ ] Ingest recent **Herald-bracket** matches into a DB, pruning matches older than ~30 days (config knob)
- [ ] Model matches richly — summary features + Stratz networth-lead array (for throw/comeback detection); full per-minute-per-player slices deferred until a query needs them
- [ ] Answer natural-language questions by writing SQL over the match DB (the bot has the "smarts")
- [ ] Use the **`herald-replay-quality` skill** to rank review-worthy candidates; bot surfaces ranked candidates, a human picks
- [ ] Respond to `@bot`-mentions in-channel; never post unprompted
- [ ] **Discovery via OpenDota** `/publicMatches` (Herald filter) → **enrich via Stratz** (parsed detail); retry/backoff for OpenDota outages

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Scheduled auto-posting / broadcasting** — this is the spam that triggered the overhaul; killed entirely
- **Telegram / AWS Lambda paths** (`bot.py`, `lambda_function.py`) — legacy, being removed
- **Non-Herald brackets** — the bot's niche is Herald Reviews; keep the DB focused
- **Slack / CLI / multi-tenant / billing** — even if we base on daimon, this is one streamer's bot

## Context

- **Purpose**: exists to support Jenkins' "Herald Reviews" YouTube/stream series. The bot's
  judgment of "good replay" should be learned from what he actually reviews.
- **Current codebase** (see `.planning/codebase/`): flat, untyped Python bot. Live path is
  `discord_bot.py` on Fly.io (self-scheduled 24h loop) hitting OpenDota via `functions.py`.
  Dead code: `database.py` (unused Supabase), Telegram/Lambda paths, `numpy`.
  **Security: a live Telegram bot token is hardcoded in `functions.py` and committed — revoke it.**
- **Base architecture (decided)**: fork `cs/daimon-cma-open-source` — Anthropic Managed Agents
  loop + skills-as-repos + Postgres/SQLAlchemy + Fly deploy — trimmed to essentials. Keep
  core (db/models/config/turn/skills), Discord adapter, and the scheduler adapter (reused for
  the ingestion worker). Strip multi-tenant / MCP / Slack / billing / provisioning / OAuth.
- **Spikes complete** (findings in `.planning/spikes/`):
  - **Spike A — API bake-off** (`api-bakeoff/FINDINGS.md`): OpenDota is the only Herald ID feed
    (~2k Herald/day, 4.2% of publicMatches); 15/15 fresh OD Herald matches were *unparsed*, but
    the same matches come back *fully parsed* on Stratz (per-minute networth/xp, item timings,
    lanes). → OpenDota discovery + Stratz enrichment; time-slice modeling feasible via Stratz;
    ample rate-limit headroom; add retry/backoff (OD had a 15-min outage mid-spike).
  - **Spike B — domain knowledge** (`herald-replay-quality/`): "good replay" = chaos in the
    lowest bracket (10-MMR, marathon+kill-chaos, troll builds, hard heroes, big throws). Nearly
    all computable from match data; comedic/human-interest payload is not → rank candidates,
    human picks. Draft `SKILL.md` with a weighted 0–100 rubric written.

## Constraints

- **Tech stack**: Python; Discord via discord.py; Fly.io deployment (matches current + daimon)
- **Data source**: OpenDota and/or Stratz — external, rate-limited, free-tier APIs
- **Interaction**: pull-only (mention-triggered); no unprompted output — hard requirement from the spam complaint
- **Scope**: single-purpose personal bot for one streamer — resist enterprise scaffolding
- **Security**: revoke the leaked Telegram token; no secrets committed to source

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pivot from push (auto-post) to pull (answer on mention) | Server members annoyed by spam; the posting is the problem | — Pending |
| Herald-only ingestion | Bot's niche is Jenkins' Herald Reviews | — Pending |
| Agent writes SQL + uses domain skills (vs fixed query commands) | Flexibility; "smarts" is the product | — Pending |
| **Fork daimon, trimmed** (strip multi-tenant/MCP/Slack/billing; keep core+Discord+scheduler+deploy) | Reuse working MA agent-loop + skills + Discord + deploy; consistency with user's other bot | ✓ Decided |
| Spike OpenDota vs Stratz before designing schema | Parsed/unparsed granularity is unknown and gates the data model | ✓ Good — decisive result |
| **Data source: OpenDota discovery → Stratz enrichment** | OD is the only Herald ID feed (~2k/day); Stratz has parsed detail OD lacks (15/15 OD Herald unparsed) | ✓ Decided (spike evidence) |
| **DB: Postgres** (daimon's SQLAlchemy + Alembic) | Inherited with the daimon fork; 60k-row scale is trivial | ✓ Decided |
| Time-slices: store summary + networth-lead array; defer full per-minute slices | Covers throw/comeback scoring cheaply; full slices are YAGNI until a query needs them | — Pending |
| Retention: prune matches older than ~30 days | Keep DB lean; recency is what matters for content | — Pending |
| Bot ranks candidates, human picks | Comedic payload / human-interest angle isn't computable (spike B) | ✓ Decided (spike evidence) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-01 after initialization*
