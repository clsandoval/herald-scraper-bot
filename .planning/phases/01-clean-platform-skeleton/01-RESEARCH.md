# Phase 1: Clean Platform Skeleton - Research

**Researched:** 2026-07-01
**Domain:** Monorepo trimming (uv workspace), Fly.io deploy (Postgres + Alembic release migrations), Discord bot minimal boot, git history scrubbing
**Confidence:** HIGH (daimon source read directly; Fly/git-filter-repo mechanics cross-verified against official docs)

## Summary

This phase is a **trim-and-deploy** exercise, not a build-from-scratch exercise. The
fork source (`/home/clsandoval/cs/daimon-cma-open-source`) is a mature multi-tenant SaaS
codebase — its Discord adapter alone is 40+ files and its `bot.py` is 1,170 lines wired
to billing, provisioning, GitHub OAuth, MCP resolvers, and multi-tenant stores. **Trimming
that file in place is not practical for Phase 1.** The pragmatic path — consistent with
D-04's "keep only core (db/models/config/turn/skills) + Discord adapter + scheduler
adapter" and the ponytail constraint — is: keep the **package/deploy/db skeleton**
(`db.py`, `_models.py`, `config.py`, `alembic.ini`+`env.py`, `Dockerfile`, `fly.toml`
pattern, `uv` workspace shape) verbatim or near-verbatim, but **replace `bot.py`'s
`on_message` body with a ~30-line mention→pong handler** rather than trying to strip
1,170 lines down. The turn driver, MA wiring, and full `DaimonBot` class are *retained in
the dependency graph* (D-09) but not exercised by Phase 1's logic path.

Two concrete gotchas will bite if not planned for: (1) daimon's `defaults/apply.py`
(triggered by `docker/entrypoint.sh` on every non-alembic process boot) provisions a
tenant, resolves MA agents/environments, and reconciles skills against the Anthropic
API — this is Phase 2+ machinery and **must be skipped entirely** for Phase 1 (either by
not calling it, or replacing the entrypoint script). (2) Fly's `DATABASE_URL` secret
returns a `postgres://` scheme; daimon's SQLAlchemy async engine and Alembic `env.py`
require `postgresql+asyncpg://` — this needs an explicit rewrite step (daimon's own
`docker-compose.yml` hand-writes the `+asyncpg` scheme; nothing in the app does this
rewrite automatically).

**Primary recommendation:** Copy the `packages/core`, `packages/adapters/discord`,
`packages/adapters/scheduler` package *shapes* (pyproject.toml + directory layout) into
this repo, delete everything inside `discord/` except the minimal boot chain
(`__main__.py`, a trimmed `bot.py`, `runtime.py`, `health.py`), start with an **empty**
`_models.py` (`Base` only, no tables — Phase 1 has no domain schema) so the baseline
Alembic migration is trivially safe, and adapt `Dockerfile`/`fly.toml`/`entrypoint.sh` to
skip `daimon defaults apply`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Discord gateway connection + mention detection | Discord Adapter (process) | — | `discord.py` client owns the gateway websocket; must run as its own long-lived process |
| `pong` reply logic | Discord Adapter (process) | — | Trivial in-process reply; no DB/agent round-trip needed for Phase 1 |
| Fly process liveness (health checks) | Discord Adapter (process) | Core (`health.py`) | `health.py`'s raw-socket responder is core-owned but instantiated per-adapter-process |
| DB schema definition | Core (`_models.py`) | — | Single source of truth for Alembic; adapters never define tables |
| DB connection/session lifecycle | Core (`db.py`) | Discord Adapter (`runtime.py`) | Core provides builder functions; each adapter process constructs its own engine at boot (no shared singleton) |
| Env/secrets config | Core (`config.py`, pydantic-settings) | Fly secrets (platform) | Core defines the schema; Fly injects the values at the platform layer |
| Migration execution | Fly `release_command` (platform) | Core (`alembic.ini`/`env.py`) | Fly runs `alembic upgrade head` as a one-shot release-phase VM; core owns the migration scripts/target metadata |
| MA agent-loop / turn driver | Core (`turn/`, `ma.py`) | — | Wired but **not invoked** by Phase 1's pong path — kept for Phase 2+ |
| Scheduler (ingestion) | Scheduler Adapter (process) | — | Present in the fork (D-04) but does nothing in Phase 1 — no ingestion job registered yet |

## Package Legitimacy Audit

No new external packages are being introduced in Phase 1 beyond what daimon's own
`pyproject.toml` files already pin (all already resolved and running in the sibling
`daimon-cma-open-source` checkout, which has a working `uv.lock`). This phase copies
dependency declarations from a known-working local repo rather than sourcing new
packages from the registry, so the slopsquat risk vector (novel/hallucinated package
names) does not apply here.

The one *new* addition needed only on the **developer's local machine** (not shipped in
the Docker image) is `git-filter-repo`, used once for the history scrub.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `git-filter-repo` | PyPI | ~7 yrs (initial release 2019, maintained) | high (also ships via Homebrew, Debian/Ubuntu `git-filter-repo` package) | github.com/newren/git-filter-repo | not run (see below) | Approved — dev-only tool, not a runtime dependency |
| `daimon-core`, `daimon-adapter-discord`, `daimon-adapter-scheduler` (local workspace packages) | N/A — local path deps, not published to any registry | N/A | N/A | This repo, post-fork | N/A | Approved — not third-party, copied from a repo the user controls |

`slopcheck` was not run in this research session (no network install attempted for a
single well-known, git-history-verifiable tool with 7+ years of GitHub history and
official Homebrew/Debian packaging). This is a deliberate exception, not a gap: `git
-filter-repo` is endorsed directly in GitHub's own "Removing sensitive data" documentation
and ships as a maintained Debian/Homebrew package — multiple independent authoritative
distribution channels. **The planner should still gate its local install behind a
`checkpoint:human-verify` task** per the graceful-degradation rule, since this research
session did not run slopcheck mechanically.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none — `git-filter-repo` install step should still get a human-verify checkpoint per protocol default.

## Standard Stack

### Core (copied from daimon `packages/core/pyproject.toml`, verified present and pinned in that repo)
| Library | Version constraint (daimon's pyproject) | Purpose | Why Standard |
|---------|------|---------|--------------|
| `sqlalchemy[asyncio]` | `>=2.0` | Async ORM, `_models.py` declarative base | daimon's chosen ORM; async engine required for non-blocking DB I/O in the Discord event loop |
| `asyncpg` | `>=0.29` | Postgres async driver (`postgresql+asyncpg://`) | Required driver for SQLAlchemy async engine against Postgres |
| `alembic` | `>=1.13` | Schema migrations | daimon's migration tool; async-aware `env.py` already written |
| `pydantic` / `pydantic-settings` | `>=2.8` / `>=2.5` | Typed env config (`config.py`) | Nested `DAIMON_<SECTION>__<FIELD>` env var pattern via `env_nested_delimiter="__"` |
| `discord.py` | `>=2.7,<3` | Discord gateway client | daimon's Discord adapter dependency; matches current repo's existing `discord.py` usage |
| `anthropic` | `>=0.96` | Managed Agents beta SDK | D-09 keeps MA wiring even though Phase 1's pong doesn't invoke a turn |
| `structlog` | `>=24` | Structured logging | daimon's logging convention (`log = structlog.get_logger()`) — diverges from current repo's stdlib `logging` |
| `python-ulid` | `>=3,<4` | ULID generation (Discord adapter dep) | Used for request/session IDs in daimon's Discord code; likely still a transitive need even in a trimmed bot |
| `sentry-sdk` | `>=2.61` | Error tracking, optional | Only active if `DAIMON_SENTRY__DSN` is set — safe to include, inert without config |
| `croniter` | `>=6.0,<7` | Cron expression parsing (scheduler adapter dep) | Needed if scheduler adapter package is kept per D-04, even with no jobs registered |
| `cryptography` | `>=43` | At-rest secret encryption (`CryptoSettings`) | Transitive dependency of `daimon-core`; not actively used unless GitHub OAuth path is exercised (which is stripped) |

**Version verification:** These versions are read directly from the sibling repo's live
`pyproject.toml` files (`/home/clsandoval/cs/daimon-cma-open-source/packages/core/pyproject.toml`,
`packages/adapters/discord/pyproject.toml`), which has a working `uv.lock` — i.e., these
constraints are **already resolved and running**, not hypothetical. `[VERIFIED: local
filesystem — daimon-cma-open-source/packages/*/pyproject.toml]`.

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uv` (build tool, not a runtime dep) | `0.11.18` confirmed installed locally `[VERIFIED: uv --version]` | Workspace/dependency manager | Required to `uv sync`, run `alembic`, and build the Docker image (daimon's Dockerfile `COPY --from=ghcr.io/astral-sh/uv:latest`) |
| `git-filter-repo` | latest (PyPI/Homebrew/apt) | One-time history scrub of leaked Telegram token | Install locally (not in Docker image), run once, then can be removed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Trimming `bot.py` in place (delete billing/provisioning/etc. sections from the 1170-line file) | Write a new minimal `bot.py` from scratch, reusing only `health.py`, `db.py`, `config.py`, `runtime.py` shape | Trimming in place risks leaving dead imports/broken references across 40+ interdependent Discord-adapter files (agent_setup/, billing_panel/, privacy_panel/, routines_panel/ all reference `bot.py` internals). A from-scratch minimal file is faster and safer for a "thinnest fork that boots" goal. |
| Fly unmanaged Postgres (`fly postgres create`) as D-06 literally specifies | Fly Managed Postgres (`fly mpg create` + `fly mpg attach`) | Fly's own docs now steer users toward `fly mpg` — "We are not able to provide support or guidance for unmanaged Postgres." `fly postgres create` still exists in flyctl but is deprecated in spirit. **Flag this discrepancy for the planner/user**: D-06 names the older command; the current recommended path is `fly mpg`. Either works technically; `fly mpg` is safer for a new deploy in 2026. |
| Keeping `docker/entrypoint.sh`'s `daimon defaults apply` call | Replace entrypoint with a no-op or a script that skips defaults application entirely for Phase 1 | `defaults apply` needs the CLI adapter (excluded by D-04) and does full MA agent/environment provisioning against the live Anthropic API — unnecessary network calls and failure surface for a phase whose bar is just "boots + migrates + pongs" |

**Installation (uv workspace, run from repo root after copying package trees):**
```bash
uv sync --no-dev
```

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────┐
                         │   Fly.io platform    │
                         │  app: herald-scraper-│
                         │      bot-test         │
                         └──────────┬───────────┘
                                    │
                 release_command:  │  (runs once per deploy, then exits)
                 "alembic upgrade  │
                  head"            ▼
                         ┌─────────────────────┐        ┌──────────────────┐
                         │  Alembic migration   │──────▶│  Fly Postgres    │
                         │  VM (short-lived)    │        │  (managed/       │
                         └─────────────────────┘        │   unmanaged)     │
                                    │                    └────────┬─────────┘
                     on success,   │                             │
                     deploy proceeds                             │ DAIMON_DATABASE__URL
                                    ▼                             │ (postgresql+asyncpg://)
                         ┌─────────────────────┐                 │
                         │  discord process     │◀────────────────┘
                         │  (long-lived VM)      │
                         │  python -m            │
                         │  daimon.adapters.     │
                         │  discord              │
                         └──────────┬───────────┘
                                    │
                    1. connects to Discord gateway (DISCORD_BOT_TOKEN)
                    2. on_message: is bot mentioned? ──no──▶ ignore
                                    │ yes
                                    ▼
                    3. reply "pong" to the channel/thread
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Discord API         │
                         │  (test server only)  │
                         └─────────────────────┘

Liveness: discord process also binds a raw-socket 200-OK responder
(health.py::start_liveness_responder) on DAIMON_DISCORD__HEALTH_PORT so Fly's
[checks] block can detect a hung event loop and restart the VM.
```

### Recommended Project Structure
```
herald-scraper-bot/
├── pyproject.toml                  # uv workspace root (adapted from daimon's root pyproject.toml)
├── uv.lock                         # generated by `uv sync`
├── alembic.ini                     # points script_location at packages/core/alembic
├── Dockerfile                      # multi-stage, adapted from daimon's
├── fly.toml                        # app = "herald-scraper-bot-test", region "sea"
├── docker/
│   └── entrypoint.sh               # SIMPLIFIED — no `daimon defaults apply` call
├── docker-compose.yml              # local dev: postgres + discord process (adapt daimon's, drop mcp/slack/init-provisioning)
├── packages/
│   ├── core/
│   │   ├── pyproject.toml          # daimon-core, trimmed dependency list
│   │   ├── alembic/
│   │   │   ├── env.py              # copy verbatim (reads DAIMON_DATABASE_URL or DAIMON_DATABASE__URL)
│   │   │   └── versions/           # NEW baseline migration only — no domain tables yet
│   │   └── daimon/core/
│   │       ├── db.py               # copy verbatim (build_engine/build_session_factory)
│   │       ├── _models.py          # Base only — empty schema for Phase 1
│   │       ├── config.py           # trimmed Settings — drop Slack/GitHub/Billing/Notebook/MCP/Crypto sections
│   │       ├── health.py           # copy verbatim (liveness responder)
│   │       ├── logging_setup.py    # copy verbatim if small
│   │       └── errors.py           # copy minimal DaimonError base if referenced
│   └── adapters/
│       ├── discord/
│       │   ├── pyproject.toml      # daimon-adapter-discord, trimmed deps (drop billing/github/mcp-related)
│       │   └── daimon/adapters/discord/
│       │       ├── __main__.py     # adapt: drop Sentry/observability if not wired, keep health responder
│       │       ├── bot.py          # REWRITTEN minimal: on_message → mention check → pong reply
│       │       └── runtime.py      # trimmed DiscordRuntime — drop billing_config, notebook_rate_limiter, resolver_cache, deployment_default
│       └── scheduler/
│           ├── pyproject.toml      # daimon-adapter-scheduler (kept per D-04, inert — no jobs registered yet)
│           └── daimon/adapters/scheduler/  # copy as-is; Phase 3 wires real jobs
└── .planning/                      # GSD state (unchanged)
```

### Pattern 1: Pydantic-settings nested env config
**What:** `Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_prefix="DAIMON_", env_nested_delimiter="__")`. Each sub-config is a nested `BaseModel` (e.g., `DatabaseSettings.url`), populated from `DAIMON_DATABASE__URL`.
**When to use:** All config in this fork — matches daimon's convention exactly, and the `.env.example` in the source repo documents the naming (`DAIMON_ANTHROPIC__API_KEY`, `DAIMON_DATABASE__URL`, `DAIMON_DISCORD__BOT_TOKEN`).
**Example:**
```python
# Source: /home/clsandoval/cs/daimon-cma-open-source/packages/core/daimon/core/config.py
class DatabaseSettings(BaseModel):
    url: PostgresDsn
    test_url: PostgresDsn | None = None

class DiscordSettings(BaseModel):
    bot_token: SecretStr
    health_port: int = 8081

class Settings(BaseSettings):
    database: DatabaseSettings
    discord: DiscordSettings | None = None
    model_config = SettingsConfigDict(
        env_prefix="DAIMON_", env_nested_delimiter="__",
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )
```
**Trim guidance:** For Phase 1's `Settings`, keep only `database`, `anthropic`, `discord`, `log`. Drop `mcp`, `slack`, `github`, `crypto`, `credentials`, `gemini`, `notebook`, `billing`, `defaults_root` (or keep `defaults_root` only if a Phase-1-safe defaults-apply replacement is written — see Pitfall 1 below).

### Pattern 2: Async engine/session builders, no module-level singleton
**What:** `build_engine(url)` / `build_session_factory(engine)` are pure functions; the caller (adapter's `runtime.py`) owns engine lifecycle and disposes it in a `finally` block.
**When to use:** Every process that touches the DB constructs its own engine at boot via `build_runtime`'s `@asynccontextmanager`.
**Example:**
```python
# Source: /home/clsandoval/cs/daimon-cma-open-source/packages/core/daimon/core/db.py
def build_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(url, echo=echo)

def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

### Pattern 3: Fly release_command runs migrations before the new release goes live
**What:** `fly.toml`'s `[deploy] release_command = "alembic upgrade head"` spins up a short-lived Fly Machine using the *new* release's image, runs the command, and only proceeds to swap traffic to the new release if it exits 0.
**When to use:** Exactly D-08's requirement — "Alembic migrations run on release."
**Example:**
```toml
# Source: /home/clsandoval/cs/daimon-cma-open-source/fly.toml
[deploy]
  release_command = "alembic upgrade head"
  strategy        = "rolling"
```
**Gotcha:** The release_command VM runs the **entrypoint** too. daimon's `docker/entrypoint.sh` special-cases this: `if [ "$1" != "alembic" ]; then daimon defaults apply; fi` — i.e., it detects the alembic invocation and skips the defaults-seeding step for that specific run. Preserve this guard shape even after simplifying the entrypoint, or the release-phase VM will try to call a (possibly deleted) `daimon` CLI command and fail the release.

### Pattern 4: Raw-socket liveness responder shares the adapter's event loop (by design)
**What:** `start_liveness_responder(port)` binds `asyncio.start_server` on the *same* running loop as the Discord client. A hung event loop stops answering health checks, so Fly restarts the VM — this is intentional, not a bug.
**When to use:** Any non-HTTP long-lived process (discord, scheduler) that needs a Fly `[checks]` target.
**Example:**
```python
# Source: /home/clsandoval/cs/daimon-cma-open-source/packages/core/daimon/core/health.py
health_server = await start_liveness_responder(settings.discord.health_port)
try:
    await bot.start(settings.discord.bot_token.get_secret_value())
finally:
    health_server.close()
    await health_server.wait_closed()
```

### Anti-Patterns to Avoid
- **Trying to strip `bot.py` down via deletion:** 1,170 lines with imports into `agent_setup/`, `billing_panel/`, `privacy_panel/`, `routines_panel/`, `github_visibility.py`, `attachments.py`, `vision.py` — deleting sections risks orphaned imports across a dozen files. Write a new minimal file instead; delete the panel directories wholesale.
- **Leaving `daimon defaults apply` wired into the entrypoint:** it calls the live Anthropic API to provision agents/environments — unnecessary cost/failure surface and requires the excluded CLI package's provisioning logic. Skip it for Phase 1; wire it back when a real skill/agent needs seeding (Phase 4+).
- **Forgetting the `postgres://` → `postgresql+asyncpg://` scheme rewrite:** Fly's `DATABASE_URL` secret (from either `fly postgres attach` or `fly mpg attach`) is NOT automatically compatible with `create_async_engine`. See Pitfall 2.
- **Running `git filter-repo` without `--force` on a non-fresh clone, or forgetting the remote is stripped afterward:** filter-repo removes the `origin` remote as a safety measure after rewriting; re-add it before pushing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async Postgres engine/session management | Custom connection pool wrapper | `daimon.core.db.build_engine`/`build_session_factory` (copy verbatim) | Already correct (`expire_on_commit=False`, `NullPool` for Alembic), zero reason to rewrite |
| Env config validation | `os.getenv` + manual `raise ValueError` (current repo's pattern) | `pydantic-settings` `Settings` class (copy daimon's shape) | Type-safe, fails fast with clear errors, matches D-04's "keep core config" decision |
| Fly liveness/health check endpoint | Custom aiohttp/Flask health server | `daimon.core.health.start_liveness_responder` (copy verbatim, ~35 lines) | Deliberately minimal, already solves the "co-locate with the event loop" correctness property |
| Git history secret removal | Manual rebase/`filter-branch` (slow, error-prone, GitHub explicitly discourages) | `git-filter-repo --path <file> --invert-paths` | Purpose-built, faster, is what GitHub's own docs recommend over `filter-branch`/BFG for path-based removal |
| Alembic async env wiring | Custom asyncio-to-sync bridging for Alembic (which is sync-only by default) | Copy daimon's `alembic/env.py` verbatim (`async_engine_from_config` + `run_sync`) | Already solves the async/sync migration bridge correctly; this is a known-tricky integration point |

**Key insight:** Almost nothing in this phase should be written from scratch except the
trimmed `bot.py`/`runtime.py`/`config.py`/`Settings` **subset** (deletions, not new
logic) and the entrypoint simplification. The platform-plumbing code (db, alembic env,
health) is copy-paste correct as-is.

## Common Pitfalls

### Pitfall 1: `daimon defaults apply` runs on every non-alembic process boot and requires excluded machinery
**What goes wrong:** `docker/entrypoint.sh` calls `daimon defaults apply` before exec'ing the process command, for every process EXCEPT the alembic release-command invocation. `apply_defaults()` calls `provision_tenant`, resolves MA agents/environments against the live Anthropic API, and reconciles skills — none of which exist in a Phase-1-trimmed repo (the CLI package that owns `daimon defaults apply` as a command is explicitly excluded by D-04).
**Why it happens:** The entrypoint script is copied wholesale without noticing it has a hidden dependency on the CLI adapter package and a live network call.
**How to avoid:** Rewrite `docker/entrypoint.sh` for Phase 1 to just `exec "$@"` (drop the `daimon defaults apply` branch entirely). Re-introduce a Phase-1-safe seeding step only when a later phase actually needs seeded agents/skills.
**Warning signs:** Container crashes on boot with an error referencing `daimon.adapters.cli` module not found, or an Anthropic API call failing/timing out during what should be a trivial pong-bot boot.

### Pitfall 2: `DATABASE_URL` from Fly is not directly usable by SQLAlchemy's async engine
**What goes wrong:** Fly's Postgres attach (`fly postgres attach` or `fly mpg attach`) sets `DATABASE_URL=postgres://user:pass@host:port/db`. Passing this directly into `DAIMON_DATABASE__URL` and then into `create_async_engine()` either fails immediately (no `asyncpg` dialect registered for bare `postgres://`) or, if pydantic's `PostgresDsn` silently accepts it, SQLAlchemy still needs the `+asyncpg` driver suffix to select the async driver.
**Why it happens:** daimon's own `docker-compose.yml` hand-writes `DAIMON_DATABASE__URL=postgresql+asyncpg://...` — the app never rewrites schemes itself; this responsibility sits with whoever sets the env var.
**How to avoid:** After `fly postgres attach`/`fly mpg attach` sets `DATABASE_URL`, explicitly set a *second* Fly secret `DAIMON_DATABASE__URL` with the scheme rewritten to `postgresql+asyncpg://`, e.g.:
```bash
fly secrets set DAIMON_DATABASE__URL="$(fly secrets list ... | sed 's#^postgres://#postgresql+asyncpg://#')"
```
or, more robustly, do the rewrite at the shell/entrypoint level so the app always constructs its own `DAIMON_DATABASE__URL` from Fly's `DATABASE_URL` at container start. Either approach works; the plan must pick one explicitly — this is not automatic.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError: Could not parse SQLAlchemy URL` or a fallback to the sync `psycopg2` driver blocking the event loop.

### Pitfall 3: `fly postgres create` (D-06's literal wording) is the deprecated unmanaged path
**What goes wrong:** D-06 says "Fly managed Postgres (`fly postgres create` + attach)" — but Fly's current docs push users toward `fly mpg create`/`fly mpg attach` ("Managed Postgres") and explicitly say they "are not able to provide support or guidance for unmanaged Postgres" (the `fly postgres create` family). The command still exists in flyctl today but is not the currently-recommended path.
**Why it happens:** Naming drift — Fly renamed/relaunched their managed offering as "MPG" (`fly mpg`) after the older `fly postgres` (technically a self-managed Postgres *app* with some CLI conveniences, not a fully managed service) had been the long-standing default.
**How to avoid:** Confirm with the user at plan time whether "Fly managed Postgres" in D-06 means the newer `fly mpg` product (recommended) or the older `fly postgres create` command (still works, but Fly won't support it going forward). Either produces a `DATABASE_URL`-shaped secret; `fly mpg` is the safer long-term bet for a fresh 2026 deploy.
**Warning signs:** None at deploy time — both paths currently work. This is a forward-compatibility/support concern, not an immediate blocker.

### Pitfall 4: Alembic's `env.py` requires `DAIMON_DATABASE_URL` (flat, no double-underscore) OR `DAIMON_DATABASE__URL` — but reads them differently than the app
**What goes wrong:** `packages/core/alembic/env.py` checks `os.environ.get("DAIMON_DATABASE_URL") or os.environ.get("DAIMON_DATABASE__URL")` directly via `os.environ`, bypassing pydantic-settings entirely (comment: "alembic CLI runs outside pydantic-settings"). If only the app's `DAIMON_DATABASE__URL` (double underscore, nested) is set and alembic is invoked directly outside the app's process (e.g., manually debugging), this works. But if someone sets a differently-cased or malformed variant, alembic silently falls through to `sqlalchemy.url` in `alembic.ini` (empty by default) and raises `RuntimeError`.
**Why it happens:** Alembic's `env.py` is a standalone script; it can't rely on the app's `Settings` object being constructed, so it re-implements minimal env reading.
**How to avoid:** Ensure whatever Fly secret is set (`DAIMON_DATABASE__URL`, per app convention) is present in the release_command's environment too — Fly release_command VMs inherit the app's secrets/env automatically, so this should "just work" as long as the secret name matches exactly.
**Warning signs:** Release phase fails with `RuntimeError: No database URL configured` — check secret name spelling first.

### Pitfall 5: Force-pushing rewritten history breaks anything with a fork/clone still pointing at old commit SHAs
**What goes wrong:** `git filter-repo` rewrites every commit's SHA (even commits that don't touch the leaked-token file, because parent hashes change transitively). After `git push --force`, any existing local clone (including whatever Fly/CI cached, though Fly doesn't clone from git — it builds from local context) becomes divergent.
**Why it happens:** Inherent to any git history rewrite — this is expected, not a bug.
**How to avoid:** D-03 already confirms this is safe here ("prod runs off its Fly machine, not the repo"). Just confirm: (1) no CI/CD is configured to auto-deploy from a git webhook (checked: this repo has none), (2) re-add the `origin` remote after filter-repo removes it, (3) `git push --force --all --tags`.
**Warning signs:** None expected given D-03's confirmed isolation — this is a low-risk operation for this specific repo (single remote, single branch, no CI webhook).

## Code Examples

### Minimal mention→pong Discord handler (new code for Phase 1, following daimon's `DaimonBot` shape but stripped)
```python
# Pattern derived from daimon's on_message dispatch shape
# (packages/adapters/discord/daimon/adapters/discord/bot.py:459 on_message),
# rewritten minimal for Phase 1 — no turn driver, no stores, no billing.
import discord

class HeraldBot(discord.Client):
    async def on_ready(self) -> None:
        log.info("discord_ready", user=str(self.user))

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        if self.user not in message.mentions:
            return
        await message.channel.send("pong")
```
Note: daimon's real bot subclasses `commands.Bot` (for slash-command support) and uses
`discord.Intents.default()` + `intents.message_content = True` (from `__main__.py`) —
`message_content` intent must stay enabled or `message.content`/mention detection breaks
silently (empty content, no crash). `[CITED: daimon-cma-open-source/__main__.py]`

### Async Alembic env.py — copy verbatim
```python
# Source: /home/clsandoval/cs/daimon-cma-open-source/packages/core/alembic/env.py
db_url = os.environ.get("DAIMON_DATABASE_URL") or os.environ.get("DAIMON_DATABASE__URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
elif not config.get_main_option("sqlalchemy.url"):
    raise RuntimeError("No database URL configured...")

async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
```

### git filter-repo — purge the leaked Telegram token's file from all history
```bash
# 1. Install (dev machine only, not shipped in Docker image)
pip install git-filter-repo
# or: brew install git-filter-repo

# 2. Work from a fresh clone (filter-repo refuses otherwise, or pass --force)
git clone https://github.com/clsandoval/herald-scraper-bot.git herald-scraper-bot-filtered
cd herald-scraper-bot-filtered

# 3. Purge functions.py's historical blobs entirely (the file is being deleted
#    in this phase anyway per D-04, so removing it from history too is safe)
git filter-repo --path functions.py --invert-paths

# 4. filter-repo removes the `origin` remote as a safety measure — re-add it
git remote add origin https://github.com/clsandoval/herald-scraper-bot.git

# 5. One-time force-push (per D-02) — coordinate timing since this rewrites all SHAs
git push origin --force --all
git push origin --force --tags
```
`[CITED: github.com/newren/git-filter-repo README; GitHub Docs "Removing sensitive data from a repository"]`

### Fly Postgres attach + DATABASE_URL scheme fix
```bash
# Option A: Fly Managed Postgres (current recommended product)
fly mpg create --name herald-scraper-bot-test-db --region sea
fly mpg attach <clusterID> -a herald-scraper-bot-test
# ^ sets DATABASE_URL=postgres://... on the app automatically

# Option B: legacy unmanaged (matches D-06's literal wording, still functional)
fly postgres create --name herald-scraper-bot-test-db --region sea
fly postgres attach herald-scraper-bot-test-db -a herald-scraper-bot-test

# Either way, DATABASE_URL comes back as postgres:// — rewrite for the app's
# expected DAIMON_DATABASE__URL (nested pydantic-settings key, +asyncpg driver):
RAW_URL=$(fly secrets list -a herald-scraper-bot-test --json | jq -r '...')  # or read from `fly ssh console` env
fly secrets set -a herald-scraper-bot-test \
  DAIMON_DATABASE__URL="$(echo "$RAW_URL" | sed 's#^postgres://#postgresql+asyncpg://#')"
```
`[CITED: fly.io/docs/mpg/create-and-connect/, fly.io/docs/postgres/, community.fly.io thread on DATABASE_URL parsing]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `fly postgres create` (self-managed Postgres app with CLI conveniences) | `fly mpg create` (fully managed: HA, backups, connection pooling via PGBouncer) | Fly's docs now steer new users to MPG; exact deprecation date of `fly postgres` unclear from docs alone — `[ASSUMED: MPG is the "current" default per docs framing, exact sunset timeline not stated]` | Both work today; MPG is lower-maintenance and is what Fly explicitly supports going forward |
| `git filter-branch` for history rewriting | `git filter-repo` | filter-repo has been the recommended replacement for years; GitHub's own docs recommend it over filter-branch/BFG for this use case | Faster, safer, officially endorsed |

**Deprecated/outdated:**
- `git filter-branch`: officially discouraged by git itself (`git filter-branch --help` prints a warning); do not use it even though it's still technically available.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Fly Managed Postgres" in D-06 refers to either `fly mpg` (new) or `fly postgres create` (legacy) — both produce a usable `DATABASE_URL`-shaped secret, and the choice is not yet confirmed with the user | Common Pitfalls #3, Alternatives Considered | Low — either path works technically; only matters for long-term support/maintenance, not for Phase 1's boot bar. Planner should surface this as an explicit choice, not silently pick one. |
| A2 | `python-ulid`, `croniter`, `cryptography` remain necessary transitive dependencies even after trimming `bot.py`/config sections | Standard Stack (Core) | Low — worst case, an unused dependency ships in the image; does not block boot. Executor should verify via `uv sync` whether these can actually be dropped once the trimmed code is written. |
| A3 | Fly release_command VMs automatically inherit the app's Fly secrets (so `DAIMON_DATABASE__URL` set via `fly secrets set` is visible to `alembic upgrade head`) | Common Pitfalls #4 | Medium if wrong — release phase would fail immediately with a clear `RuntimeError`, so this is self-diagnosing, but worth an explicit verification task in the plan (deploy once, confirm release_command log shows a successful migration, not a missing-URL error). `[ASSUMED based on general Fly release_command behavior — not explicitly re-confirmed via docs this session]` |
| A4 | The exact `DATABASE_URL` scheme returned by `fly mpg attach` vs `fly postgres attach` is `postgres://` (not `postgresql://`) in both cases | Pitfall 2, Code Examples | Low — either scheme requires the same `+asyncpg` suffix fix; the exact base scheme string doesn't change the remediation |

**If this table is empty:** N/A — see above; four items logged.

## Open Questions

1. **Does "Fly managed Postgres" mean `fly mpg` or `fly postgres create`?**
   - What we know: D-06 says "Fly managed Postgres (`fly postgres create` + attach)" verbatim, but Fly's current docs recommend `fly mpg` as the managed product and call `fly postgres` "unmanaged."
   - What's unclear: Whether the user meant the specific command or the general concept ("Fly's Postgres offering, whatever it's called now").
   - Recommendation: Default to `fly mpg` (the currently-supported managed product) unless the user has a specific reason to prefer the legacy command (e.g., familiarity, existing tooling). Flag as a quick confirm at plan/execution time, not a blocker.

2. **Should `packages/adapters/scheduler` be copied in Phase 1 even though it does nothing yet?**
   - What we know: D-04 says keep the scheduler adapter ("reused for ingestion in Phase 3"). D-08's done-bar for Phase 1 only mentions discord+pong+migrations — no scheduler behavior.
   - What's unclear: Whether Phase 1 should deploy the scheduler as an inert Fly process (adds a `[processes]` entry + VM, costs a little, proves nothing new) or defer copying it until Phase 3 actually needs it.
   - Recommendation: Copy the scheduler package's *files* now (cheap, keeps D-04's "trim once" intent) but do NOT add it to `fly.toml`'s `[processes]` for Phase 1 — no reason to run an empty polling loop yet. Planner should decide the exact task boundary.

3. **What is the minimal `_models.py` for Phase 1?**
   - What we know: D-04 says "keep only daimon core (db/models/config/turn/skills)." Phase 1 has zero domain requirements (DATA-01..05 are Phase 2+). Alembic needs *some* `Base.metadata` to generate a baseline migration against.
   - What's unclear: Whether "keep models" means copy daimon's full multi-tenant schema (`Tenant`, `Account`, `CliPrincipal`, `PlatformPrincipal`, etc. — needed if any tenant-scoping is kept for later MA/Discord wiring) or start with a genuinely empty `Base` and add tables only when Phase 2 needs them.
   - Recommendation: Start with an empty (or near-empty) `Base` for the Phase 1 baseline migration — the phase boundary explicitly excludes "schema beyond a migration baseline" (Deferred Ideas). If the Discord adapter's trimmed `on_message` path ends up needing even minimal tenant/principal rows (e.g., for future gating), that's a Phase 2 concern per DATA-01.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Building/running the workspace, generating `uv.lock` | ✓ | 0.11.18 | — |
| `git-filter-repo` | D-02 history scrub | ✗ | — | `pip install git-filter-repo` or `brew install git-filter-repo` — no viable fallback for a clean history purge (filter-branch is discouraged) |
| `fly` CLI | Deploy, Postgres provisioning, secrets | not checked this session — `[ASSUMED not verified; executor should run `fly version` before relying on it]` | — | Install via `curl -L https://fly.io/install.sh \| sh` if missing |
| Docker | Local image build/test before deploy | not checked this session | — | Fly can also build remotely (`fly deploy --remote-only`) if local Docker is unavailable |

**Missing dependencies with no fallback:**
- None — `git-filter-repo` has a trivial one-line install fallback; nothing else in this phase has a hard external requirement without a documented install path.

**Missing dependencies with fallback:**
- `git-filter-repo`: install via pip/brew immediately before the history-scrub task.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None currently in this repo (`herald-scraper-bot` has zero test files per `.planning/codebase/STRUCTURE.md`). daimon's fork source uses `pytest` + `pytest-asyncio` (`[tool.pytest.ini_options]` in its root `pyproject.toml`) — that convention should carry over if tests are added in this phase. |
| Config file | none yet — see Wave 0 |
| Quick run command | `uv run pytest packages/adapters/discord/tests -x` (once test dir exists) |
| Full suite command | `uv run pytest` (workspace-wide, once `[tool.pytest.ini_options]` is copied from daimon's root `pyproject.toml`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAT-01 | Trimmed package set imports cleanly, no orphaned references to stripped adapters (billing/slack/mcp/cli) | smoke | `uv run python -c "import daimon.adapters.discord"` (import-only smoke check) | ❌ Wave 0 |
| PLAT-02 | No secret values appear in source; all config resolves from env | manual + static check | `grep -rn "sk-\|xoxb-\|discord.com/api/webhooks" packages/ --include="*.py"` (should return nothing) | ❌ Wave 0 (simple grep script, not a pytest test) |
| PLAT-03 | Leaked token file removed from working tree AND git history; `bot.py`/`lambda_function.py`/`database.py` deleted | manual verification | `git log --all -p -- functions.py \| grep -c "1982794836"` should be `0` after filter-repo; `ls bot.py lambda_function.py database.py` should fail (No such file) | ❌ Wave 0 (verification script, not pytest) |
| PLAT-04 | App deploys, Postgres attached, Alembic migration runs on release, bot logs in, `@bot` → `pong` | integration/manual (live Discord + Fly, cannot be a unit test) | `fly deploy -a herald-scraper-bot-test` then manually `@mention` the bot in the test server and observe the reply | ❌ Wave 0 — this is fundamentally a manual/e2e check; no unit test substitutes for "did Discord actually reply" |

### Sampling Rate
- **Per task commit:** import smoke check (`uv run python -c "import daimon.adapters.discord"`) + `uv run ruff check` if ruff config is kept
- **Per wave merge:** full `uv sync --no-dev` + local `docker compose up` boot test against a local Postgres before touching Fly
- **Phase gate:** live Fly deploy to `herald-scraper-bot-test` + manual `@bot` mention in the test Discord server — this is the actual Phase 1 acceptance bar (D-08) and cannot be automated away

### Wave 0 Gaps
- [ ] No test directory exists yet in this repo — if the plan wants automated coverage beyond import-smoke/grep checks, `packages/adapters/discord/tests/` needs to be created with at minimum a mention-detection unit test (mock `discord.Message`, assert `pong` is sent only when the bot is mentioned)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` not yet copied from daimon's root config
- [ ] Framework install: `uv add --dev pytest pytest-asyncio` if tests are added this phase

*(Given the phase's nature — deploy plumbing, not business logic — heavy automated test investment is likely low-value; a single mention-detection unit test plus the manual e2e deploy check is probably sufficient. Planner's call.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user-facing auth in Phase 1 — Discord's own bot-token auth model is used as-is |
| V3 Session Management | no | No session concept introduced in Phase 1 (MA sessions are Phase 2+, unused by pong) |
| V4 Access Control | partial | Mention-gating (`should_process_message`/mention check) is the only access control — ensures the bot only reacts to explicit mentions, satisfying DISC-01's "never posts unprompted" at the code level for this phase |
| V5 Input Validation | no | No user input parsed beyond "is the bot mentioned" — trivial, no injection surface |
| V6 Cryptography | no | No new crypto introduced; `CryptoSettings`/Fernet keys from daimon are dropped (GitHub OAuth path excluded) |
| V14 Configuration | yes | Secrets exclusively via Fly secrets / env (pydantic-settings), matching PLAT-02. No secret literals in source, Dockerfile, or fly.toml. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret committed to git history (the actual incident that triggered this phase) | Information Disclosure | `git filter-repo` history scrub (D-02) + token revocation (D-11, user action) — revocation is the real fix, scrub is defense-in-depth |
| Discord bot token leak via logs/error messages | Information Disclosure | pydantic `SecretStr` type on `bot_token` (daimon's convention) prevents accidental `repr()`/log exposure — preserve this type, don't downgrade to plain `str` |
| Force-push history rewrite silently breaking an unnoticed CI/CD git-triggered deploy hook | Tampering (accidental) | Confirmed: no CI/CD webhook exists in this repo (`fly.toml`'s deploy is manual `fly deploy`, not git-triggered) — low risk here, but worth a one-line check before pushing |
| Overly-broad Fly `DATABASE_URL` secret visible to a compromised dependency (supply-chain) | Information Disclosure | Out of scope for Phase 1 hardening — noted in the current repo's own `CONCERNS.md` as a pre-existing low-priority risk; not newly introduced by this phase |

## Sources

### Primary (HIGH confidence)
- `/home/clsandoval/cs/daimon-cma-open-source/Dockerfile`, `fly.toml`, `docker-compose.yml`, `docker/entrypoint.sh`, `alembic.ini`, `.env.example` — read directly this session
- `/home/clsandoval/cs/daimon-cma-open-source/packages/core/daimon/core/{db,config,health,_models}.py` — read directly this session
- `/home/clsandoval/cs/daimon-cma-open-source/packages/core/alembic/env.py` — read directly this session
- `/home/clsandoval/cs/daimon-cma-open-source/packages/adapters/discord/daimon/adapters/discord/{bot,runtime,__main__}.py` — read directly this session
- `/home/clsandoval/cs/daimon-cma-open-source/packages/adapters/discord/pyproject.toml`, `packages/core/pyproject.toml`, `packages/adapters/scheduler/pyproject.toml`, root `pyproject.toml` — read directly this session
- github.com/newren/git-filter-repo README (via WebFetch) — exact `--path`/`--invert-paths`/`--force` flags confirmed
- GitHub Docs "Removing sensitive data from a repository" — endorses filter-repo over filter-branch/BFG

### Secondary (MEDIUM confidence)
- fly.io/docs/mpg/create-and-connect/ (via WebFetch) — `fly mpg create`/`fly mpg attach` syntax, `DATABASE_URL` naming, pooled-connection PGBouncer note
- fly.io/docs/postgres/ (via WebFetch) — confirms unmanaged `fly postgres` is no longer the supported path, steers to MPG
- fly.io/docs/flyctl/postgres-create/ (via WebFetch) — `fly postgres create` flags
- WebSearch cross-verification on `postgresql+asyncpg://` scheme requirement for SQLAlchemy async engine (multiple independent sources agree)

### Tertiary (LOW confidence)
- None — all findings for this phase were verifiable against either the fork source directly or official Fly/GitHub documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions read directly from a working sibling repo's pyproject.toml files, not training-data guesses
- Architecture: HIGH — read the actual daimon source files listed in the phase's canonical refs
- Pitfalls: HIGH for daimon-internal gotchas (directly observed in source), MEDIUM for Fly-specific DATABASE_URL scheme behavior (cross-verified via WebSearch + WebFetch but not tested against a live Fly deploy this session)

**Research date:** 2026-07-01
**Valid until:** 30 days (Fly product naming/CLI commands can shift; daimon fork source is static/local so that portion doesn't expire)
