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
- [ ] Model matches richly — not one flat row; capture per-match detail (candidate: discrete time-window slices, pending spike)
- [ ] Answer natural-language questions by writing SQL over the match DB (the bot has the "smarts")
- [ ] Use a **domain-knowledge skill** for what makes a good Herald replay to review (mined from Jenkins' videos)
- [ ] Respond to `@bot`-mentions in-channel; never post unprompted
- [ ] Source match data from **OpenDota and/or Stratz** (chosen by spike bake-off)

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
- **Candidate base architecture**: `cs/daimon-cma-open-source` — a Discord agent bot
  (Anthropic Managed Agents loop + skills-as-repos + Postgres/SQLAlchemy + Fly deploy).
  Its agent-loop + skills system map directly onto "bot uses SQL + domain skills." Its
  multi-tenant / MCP / Slack / billing scaffolding would be stripped. Final fork-vs-trim
  decision deferred until after spikes.
- **Two spikes gate the design** (running in parallel):
  - **Spike A — data API bake-off**: OpenDota vs Stratz. Herald match discovery at volume,
    per-match granularity *without* a manual parse request (parsed vs unparsed data is the
    key risk for the time-slice ambition), and rate limits. Decides data source + schema.
  - **Spike B — domain knowledge**: mine Jenkins' Herald Reviews videos → distill "what makes
    a replay worth reviewing" into a skill the ranking agent uses.

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
| Base on daimon architecture (trim to essentials) | Reuse working agent-loop + skills + Discord + deploy instead of rebuilding | — Pending |
| Spike OpenDota vs Stratz before designing schema | Parsed/unparsed granularity is unknown and gates the data model | — Pending |
| Retention: prune matches older than ~30 days | Keep DB lean; recency is what matters for content | — Pending |
| DB: lean to inherited Postgres over new SQLite | If reusing daimon, adding a table beats swapping the DB | — Pending (post-spike) |

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
