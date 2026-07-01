# Phase 1: Clean Platform Skeleton - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a trimmed, secret-safe fork of `daimon-cma-open-source` that **deploys and boots** on Fly.io with Postgres attached and Alembic migrations running on release — plus a trivial `@bot → pong` health reply proving the Discord round-trip. No match ingestion, no query/SQL agent, no scoring — those are Phase 2+. This phase is platform + deploy + connectivity only.

Covers requirements PLAT-01, PLAT-02, PLAT-03, PLAT-04.
</domain>

<decisions>
## Implementation Decisions

### Fork strategy & git history
- **D-01:** Copy the trimmed daimon subset **into this existing repo** (don't start a fresh repo). Keep the repo, replace its contents.
- **D-02:** **Scrub git history** with `git filter-repo` to purge the leaked Telegram-token blob — defense-in-depth *on top of* revoking the token (revocation is the real fix; scrub removes the dead trace). This rewrites history and requires a **one-time force-push** to the remote. Safe because prod runs off its Fly machine, not the repo.
- **D-03:** Work on `main`. Prod (`herald-scraper-bot` Fly app) keeps serving its current running release and is **not redeployed** until the overhaul is explicitly promoted.
- **D-04:** Trim scope — keep only daimon core (`db`/`models`/`config`/`turn`/`skills`), the Discord adapter, and the scheduler adapter. Remove multi-tenant, MCP, Slack, CLI, billing, provisioning, GitHub-OAuth. Remove legacy files `bot.py`, `lambda_function.py`, `database.py` and other dead code.

### Deploy target
- **D-05:** Deploy to a **new Fly app `herald-scraper-bot-test`** (test twin). Prod `herald-scraper-bot` untouched. Region `sea` (match current).
- **D-06:** **Fly managed Postgres** (`fly postgres create` + attach). Trivial cost at this scale; simplest wiring; same platform. Alembic migrations run automatically on release (daimon's release-command pattern).
- **D-07:** The bot connects to the **test Discord server** ("the herald replays server"), never a prod channel. Test-server guild/channel ID needed at execution.

### Phase 1 'done' bar
- **D-08:** Done = app deploys to `herald-scraper-bot-test`, boots against attached Postgres, Alembic migrations run on release, bot logs in to Discord, **and** an `@bot` mention returns a trivial `pong` (health round-trip). No other behavior.

### Agent loop / Anthropic access
- **D-09:** Keep **Anthropic Managed Agents (beta)** as the agent-loop approach (daimon's turn driver) — do NOT rip it out for the plain API.
- **D-10:** A **new dedicated Anthropic API key** with MA beta access is being created by the user. It is a **deploy-time Fly secret** (`ANTHROPIC_API_KEY`), never committed. Phase 1 execution prerequisite — the `pong` reply doesn't require a full MA turn, but MA config should be wired/validated.

### Secrets
- **D-11:** All secrets read from env / Fly secrets (`DISCORD_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, etc.). No secret values in source. Revoke the leaked Telegram token via @BotFather (user action).

### Claude's Discretion
- Exact daimon file-copy boundaries, Dockerfile/fly.toml adaptation, pydantic-settings config shape, and Alembic baseline migration — planner/executor decide, guided by daimon's existing structure.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project decisions
- `.planning/PROJECT.md` — the pivot, all locked architecture decisions (fork daimon trimmed, primitives-vs-knowledge split, Postgres, test-server-only)
- `.planning/ROADMAP.md` §"Phase 1" — goal + success criteria
- `.planning/REQUIREMENTS.md` — PLAT-01..04 definitions

### Fork source (the template being adapted)
- `/home/clsandoval/cs/daimon-cma-open-source/` — the repo being forked. Key files to adapt:
  - `Dockerfile`, `fly.toml` (multi-stage build, Fly processes, release-command `alembic upgrade head`)
  - `packages/core/daimon/core/db.py` (async engine + session factory)
  - `packages/core/daimon/core/_models.py` (SQLAlchemy ORM base — start minimal)
  - `packages/core/daimon/core/config.py` (pydantic-settings env config)
  - `packages/adapters/discord/daimon/adapters/discord/bot.py` + `__main__.py` (Discord adapter — strip to mention→reply)
  - `packages/core/daimon/core/turn/driver.py` (MA turn driver — kept for later phases)
  - `packages/adapters/scheduler/` (reused for ingestion in Phase 3)
  - `alembic.ini` + migrations setup

### Current codebase (being replaced)
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md` — what exists now (to remove)
- `.planning/codebase/CONCERNS.md` — leaked token location (`functions.py`), dead files list
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Current `fly.toml` (`app='herald-scraper-bot'`, region `sea`) — reference for the test app's config; do NOT deploy over the prod app name.
- Existing Fly secrets on prod (`STRATZ_API_TOKEN`, `OPENAI_API_KEY`, `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, Telegram pair) — the test app needs its own secret set; Telegram secrets are dropped.

### Established Patterns
- daimon's release-command runs `alembic upgrade head` — reuse this so migrations run on every deploy.
- daimon is a `uv` workspace (multi-package). Trimming means removing whole adapter packages, not editing within them.

### Integration Points
- Discord bot token → test server; Postgres `DATABASE_URL` from `fly postgres attach`; Anthropic MA key — all via Fly secrets.
</code_context>

<specifics>
## Specific Ideas

- Prod safety is paramount: the whole point of the overhaul is to stop annoying the server. Phase 1 must be provably isolated from prod — separate Fly app, test Discord server, its own DB.
- The `@bot → pong` reply exists purely to prove the round-trip (deploy → boot → Discord login → receive mention → reply) end-to-end before Phase 2 builds real behavior on it.
</specifics>

<deferred>
## Deferred Ideas

- Match ingestion (OpenDota/Stratz), schema beyond a migration baseline, SQL query tool, scoring skill, `hero_norms` — all Phase 2+.
- Promotion/cutover from `herald-scraper-bot-test` to prod `herald-scraper-bot` — a later milestone concern, not this phase.

None else — discussion stayed within phase scope.
</deferred>

---

*Phase: 1-Clean Platform Skeleton*
*Context gathered: 2026-07-01*
