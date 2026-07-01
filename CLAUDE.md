<!-- GSD:project-start source:PROJECT.md -->
## Project

**Herald Scraper Bot — Overhaul (Herald Reviews Scout)**

A Discord bot that helps the streamer **Jenkins** find good Dota 2 Herald-bracket
matches to feature on his popular **"Herald Reviews"** series. It quietly ingests
recent valid Herald matches into a database (pruning old ones) and answers
natural-language questions on demand — e.g. "find me recent Herald matches where
X happened" — by writing SQL against that data and reasoning about it with Dota
domain knowledge. It only speaks when asked; it does **not** broadcast.

This is a hard pivot from the current bot, which auto-scrapes and posts match
reports on a schedule (the behavior server members are annoyed by).

**Core Value:** Surface **Herald matches worth reviewing on stream** in response to a question —
without ever spamming the channel.

### Constraints

- **Tech stack**: Python; Discord via discord.py; Fly.io deployment (matches current + daimon)
- **Data source**: OpenDota and/or Stratz — external, rate-limited, free-tier APIs
- **Interaction**: pull-only (mention-triggered); no unprompted output — hard requirement from the spam complaint
- **Scope**: single-purpose personal bot for one streamer — resist enterprise scaffolding
- **Security**: revoke the leaked Telegram token; no secrets committed to source
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11 - All application code (`bot.py`, `discord_bot.py`, `functions.py`, `constants.py`, `database.py`, `lambda_function.py`)
- None. No JS/TS, shell scripting is limited to the Dockerfile and `fly.toml` process command.
## Runtime
- Python 3.11 (containerized), CPython
- Runs as a long-lived process on Fly.io that loops once per day (see `fly.toml:18`), not a typical request/response server
- pip (`requirements.txt`)
- Lockfile: missing — `requirements.txt` has no pinned versions (unpinned dependency list), no `requirements-lock.txt`, `Pipfile.lock`, or `poetry.lock`
## Frameworks
- `discord.py` - Discord bot framework; primary runtime entry point (`discord_bot.py`)
- `pyTelegramBotAPI` (imported as `telebot`) - Telegram bot framework; used only in the legacy/alternate entry point `lambda_function.py`, not in the active Discord flow
- `aiohttp` - Async HTTP client used for concurrent OpenDota API queries (`functions.py:10`, `query()` function)
- `requests` - Synchronous HTTP client used for Stratz GraphQL calls and legacy Telegram send in `functions.py`
- `pypika` - SQL query builder used to construct OpenDota Explorer SQL queries programmatically (`functions.py:13`, `Query`/`Table`)
- None detected. No test framework (pytest, unittest) is declared in `requirements.txt`, and no test files exist in the repository (`test.py` is explicitly gitignored and not present in the working tree)
- Docker (`Dockerfile`) - Container build for deployment; installs `gcc` as a system dependency, creates non-root `app` user
- `python-dotenv` - Loads `.env` file into environment variables for local development (`discord_bot.py:8`, `database.py:3`, `lambda_function.py:2`)
- Fly.io CLI (`fly.toml`) - Deployment/process configuration
## Key Dependencies
- `discord.py` (unpinned) - Powers the bot's connection to Discord, message/embed/thread creation, and the `on_ready` lifecycle hook that drives the entire scrape-and-post flow (`discord_bot.py:297-312`)
- `openai` (unpinned) - Generates the "Jenkins the commentator" LLM match summary using model `gpt-4.1-mini` via `AsyncOpenAI` client (`functions.py:847-906`)
- `aiohttp` (unpinned) - Enables concurrent, chunked queries against the OpenDota Explorer SQL endpoint, critical for scraping performance (`functions.py:222-298`)
- `requests` (unpinned) - Used for synchronous Stratz GraphQL POST requests (`functions.py:366-413`) and legacy Telegram sends
- `numpy` (unpinned) - Declared in `requirements.txt` but no usage found anywhere in the codebase (`grep` for `numpy\.` or `np\.` returns nothing beyond the import) — dead dependency
- `pypika` (unpinned) - Used solely to build the OpenDota Explorer SQL query string in `functions.py:222-254`
## Configuration
- Loaded via `python-dotenv` (`load_dotenv()`) from a local `.env` file (gitignored, not present in repo — see `.gitignore:4`)
- Required variables (validated with hard failures in `functions.py:16-36` and `discord_bot.py:27-36`):
- No `.env.example` or `.env.sample` file exists to document the required variables for a new developer
- `Dockerfile` - Single-stage build, installs `gcc`, copies only the files needed for the Discord bot flow (`lambda_function.py`, `discord_bot.py`, `functions.py`, `constants.py`, `ability_ids.json`), and runs `python discord_bot.py` as its `CMD`
- `.dockerignore` - Excludes git metadata, Python caches, docs, `test.py`, `bot.py`, and notably `fly.toml` from the build context
- `fly.toml` - Defines the Fly.io app (`herald-scraper-bot`), a single shared-CPU VM with 1GB memory, and a `scheduler` process that runs `discord_bot.py` in an infinite shell loop with a 24-hour (`sleep 86400`) sleep between runs — this is the production scheduling mechanism (no cron/external scheduler)
## Platform Requirements
- Python 3.11 (matching Dockerfile) recommended; a local `.env` file with all required variables (see above) must be created manually — no example file is provided
- `pip install -r requirements.txt` (note: `supabase` package is imported by `database.py` but is absent from `requirements.txt` — installing from the lockfile as-is will not support that module)
- Fly.io (`app = 'herald-scraper-bot'`, primary region `sea`), single shared VM, 1GB RAM
- Long-running container that self-schedules via a shell `while true` loop rather than being invoked by an external cron/scheduler service
- Despite the file name `lambda_function.py`, there is no evidence of actual AWS Lambda deployment (no `serverless.yml`, SAM template, or Lambda handler wiring) — this file appears to be a legacy/alternate entry point for a Telegram-based flow, superseded by `discord_bot.py`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Lowercase with underscores, one flat module per concern: `bot.py`, `database.py`, `discord_bot.py`, `functions.py`, `constants.py`, `lambda_function.py`
- No package/subdirectory structure — everything lives at repo root
- Entry-point scripts are named after their delivery mechanism (`discord_bot.py`, `lambda_function.py`, `bot.py`) rather than a shared `main.py`
- `snake_case` throughout, e.g. `get_match_data_nostratz`, `ret_kill_density_nostratz`, `format_match_data` (`functions.py`)
- Verb-first names for actions: `send_message`, `query_stratz`, `create_match_embed` (`discord_bot.py:95`)
- Nested helper functions are common inside larger formatting functions, e.g. `get_hero_name`, `get_item_name`, `format_position` defined inside `format_match_data` (`functions.py:526-556`) and duplicated again inside `format_player_summary` (`functions.py:752-782`) and `create_player_embed` (`discord_bot.py:119-137`) — the same small helpers are re-implemented in three places instead of being shared utilities
- Inconsistent suffix usage: `_nostratz` suffix distinguishes OpenDota-only variants (`get_match_data_nostratz`, `ret_kill_density_nostratz`) from Stratz-based ones (`ret_kill_density`, `query_stratz`) — follow this suffix convention if adding another data-source-specific variant
- `snake_case` for locals: `match_id`, `kill_density`, `stratz_players_data`
- Loop/aggregation variables are short and reused across functions: `radiant_players`, `dire_players`, `team_result`
- Module-level constants are `UPPER_SNAKE_CASE`: `STRATZ_API_TOKEN`, `OPENDOTA_URL`, `QUERY_HEADER`, `STRATZ_QUERY` (`functions.py:16-106`)
- Boolean-like state sometimes represented as `int` rather than `bool`, e.g. `leaver = 0` / `leaver = 1` in `discord_bot.py:237-240` and `lambda_function.py:48-51` instead of a `bool` flag
- Type hints are rare. Only `database.py:21` (`insert_row(table_name: str, data: Dict[str, Any]) -> bool`) uses full parameter and return annotations
- No annotations anywhere in `functions.py`, `discord_bot.py`, `lambda_function.py`, `bot.py` — when adding new functions in those files, match the surrounding untyped style unless doing a deliberate typing pass
- No dataclasses, TypedDicts, or Pydantic models — all structured data (match data, player data) is passed around as raw `dict`/`list` from JSON API responses and accessed via string keys (e.g. `match_data["data"]["match"]`)
## Code Style
- No formatter config detected (no `.black`, `pyproject.toml`, or `.prettierrc`). Code is manually formatted but broadly follows Black-like conventions: double quotes, trailing commas in multi-line calls, 4-space indentation
- Line lengths vary widely; some lines exceed 100 chars (e.g. long GraphQL query strings in `constants.py`)
- No `.flake8`, `.pylintrc`, or `ruff` config present — no enforced lint rules
- Dead code is left in place rather than deleted, commented out with explanatory notes instead of removed, e.g. the entire Selenium/Chrome-options block in `functions.py:38-92` and the unused link-preview functions in `functions.py:429-441`. Follow this pattern when deprecating code: comment out with a `# Not used in X — reason` note rather than deleting outright, matching existing style
## Import Organization
- None (flat repo, no package structure, no `src/` layout)
- `from functions import *` is used in `bot.py:2`, `discord_bot.py:11`, `lambda_function.py:5`
- `from constants import *` is used in `functions.py:11`
- This means constants like `HEROES`, `ITEMS`, `HERO_ID_TO_NAME` and every function in `functions.py` are implicitly available in consuming modules. When adding new shared helpers, add them to `functions.py` (or `constants.py` for static data) to preserve this pattern — do not introduce explicit imports inconsistently with siblings in the same file
## Error Handling
- Bare `except:` (no exception type) is common for network calls that should retry indefinitely, e.g. `functions.py:308`, `functions.py:361`, `functions.py:387`, `functions.py:409` — pattern is "infinite retry loop with `time.sleep(N)`":
- Broader business logic uses `except Exception as e:` with logging and either `continue` (skip this item, keep processing loop) or `raise` (propagate fatal error), e.g. `discord_bot.py:283-285` (`continue`) vs `discord_bot.py:292-294` (`raise` after logging "Fatal error")
- Specific Discord exceptions are caught before generic ones in `discord_bot.py:61-66`: `discord.Forbidden` → warning, `discord.NotFound` → warning, `Exception` → error. Follow this ordering (specific-to-generic) when adding new except blocks
- No custom exception classes defined anywhere in the codebase — all error handling uses built-in exceptions or third-party library exceptions (`aiohttp.ClientError`, `discord.Forbidden`, `discord.NotFound`)
- `database.py:44-50` follows a "return bool, log error" pattern rather than raising, for the Supabase insert helper — useful precedent for any new function that should not crash the caller on failure
## Logging
- `discord_bot.py:16-19` and `lambda_function.py:11-14` both configure logging identically via `logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")` then create a module logger with `logger = logging.getLogger(__name__)` — replicate this exact block when adding a new entry-point script
- `bot.py:5` instead calls `logging.getLogger().setLevel(logging.INFO)` directly on the root logger without `basicConfig` — inconsistent with the other two entry points; prefer the `discord_bot.py`/`lambda_function.py` pattern for new entry points
- `functions.py` uses the module-level `logging` calls directly (`logging.warning(...)`, `logging.error(...)`) rather than a named logger — it has no `logger = logging.getLogger(__name__)` of its own
- f-strings are used almost exclusively inside log calls: `logger.info(f"Found {len(matches)} matches to process")`
- Some low-level retry loops use `print()` instead of `logging` (`functions.py:360-362`, `functions.py:388`, `functions.py:410`) — inconsistent with the logging-based approach elsewhere; prefer `logging.warning`/`logging.error` for new code rather than `print`
## Comments
- Short inline comments explain "why", not "what", e.g. `functions.py:271` equivalent (`discord_bot.py:271`): `# ponytail: Discord caps a message at 2000 chars; chunk long summaries` — note the informal signed-comment style used for non-obvious workarounds
- Section-divider comments mark logical blocks within long functions, e.g. `# Teams`, `# Rank`, `# Items (shortened for embed)` inside `create_player_embed` (`discord_bot.py:141-186`)
- Large disabled code blocks are prefixed with an explanation of why they're inactive, e.g. `functions.py:38` (`# Selenium and CV2 imports commented out since they're not used in lambda_function.py`)
- Present on most top-level functions but not all; format is a plain triple-quoted one-liner or short paragraph, occasionally with `Args:`/`Returns:`/`Example:` sections
- `database.py:22-39` has the most complete docstring in the codebase (Google-style `Args:`/`Returns:`/`Example:`) — use this as the template for any new public function needing full documentation
- Most functions in `functions.py` and `discord_bot.py` use a single-line docstring only, e.g. `"""Create a Discord embed for match summary"""` (`discord_bot.py:96`)
- No module-level docstrings anywhere
## Function Design
## Module Design
- `constants.py`: static lookup data only (hero/item ID maps, GraphQL query templates, header dicts) — no logic
- `functions.py`: all business logic — API querying (OpenDota, Stratz), data transformation/formatting, Telegram sending, LLM summarization
- `database.py`: sole owner of the Supabase client and `insert_row` — only module using Supabase
- `discord_bot.py`, `lambda_function.py`, `bot.py`: three parallel entry points for different delivery channels (Discord bot, AWS Lambda/Telegram, notebook-style script), each importing from `functions.py` and duplicating similar orchestration logic (fetch matches → filter leavers/guardians → format → send). When modifying core match-processing logic, check all three entry points for divergence — they are not kept in sync automatically (e.g. `bot.py` uses the old `ret_kill_density` while `discord_bot.py`/`lambda_function.py` use `ret_kill_density_nostratz`)
- `bot.py` and `lambda_function.py` use `# %%` cell markers (Jupyter/VSCode interactive-cell syntax) indicating they were developed/run as notebooks rather than as standalone scripts
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
```
## Component Responsibilities
| Component | Responsibility | File |
|-----------|----------------|------|
| Discord bot process / entry point | Bootstraps `discord.py` client, wires `on_ready` to the report job, owns thread lifecycle (create + cleanup) | `discord_bot.py` |
| Data fetch & domain logic | Talks to OpenDota (match discovery), Stratz GraphQL (match detail), computes kill density, formats text/markdown reports, calls OpenAI for LLM commentary | `functions.py` |
| Static lookup tables | Hero ID → name, item ID → name, rank tier labels used purely for display formatting | `constants.py` |
| Ability ID lookup | Loaded at import time from JSON, used to label ability-cast/skill-order data | `ability_ids.json`, loaded in `functions.py` |
| Legacy/alternate entry point (Telegram) | Same scrape pipeline as `discord_bot.py` but posts synchronously to a Telegram chat instead of Discord; superseded by the Discord bot | `bot.py` |
| Legacy/alternate entry point (AWS Lambda / Telegram) | Same pipeline, hardened with env-var validation, intended for AWS Lambda deployment; also Telegram-based | `lambda_function.py` |
| Unused persistence module | Supabase insert helper; no caller anywhere in the codebase | `database.py` |
| Container build | Copies only `lambda_function.py`, `discord_bot.py`, `functions.py`, `constants.py`, `ability_ids.json`; runs `discord_bot.py` as the CMD | `Dockerfile` |
| Scheduling | Fly.io VM shell loop re-invokes `python discord_bot.py` every 24h (the process exits itself after one report) | `fly.toml` |
## Pattern Overview
- No web server, no request/response cycle — the "entry point" is a scheduled batch run that starts, does work, and exits (`bot.close()` is called at the end of `on_ready`).
- No ORM/data layer in the live path; all state is transient in-memory (lists/dicts from JSON API responses).
- Business logic (filtering, kill-density math, text formatting) and I/O (HTTP calls, Discord API calls) are mixed together in the same functions rather than separated into layers.
- Three near-duplicate entry points exist (`discord_bot.py`, `bot.py`, `lambda_function.py`) implementing the same scrape-and-report flow against different output channels (Discord vs Telegram) and different eras of the `query()` function (async chunked vs sync single-call).
- Configuration is entirely environment-variable driven via `python-dotenv`, loaded at module import time with hard failures (`raise ValueError`) if required vars are missing (`discord_bot.py:32-36`, `functions.py:22-36`).
## Layers
- Purpose: Bootstraps the client, decides when to run, and drives the top-level control flow (loop over matches, decide what to send, when to stop).
- Location: `discord_bot.py` (primary), `bot.py` and `lambda_function.py` (legacy/alternate)
- Contains: `on_ready()`, `main()`, `send_herald_report()`, `cleanup_old_threads()`
- Depends on: `functions.py` for all data fetching/formatting, `discord.py` SDK for output
- Used by: nothing — this is the top of the call graph
- Purpose: Query external match data APIs, compute derived metrics (kill density), decide which matches qualify ("Herald" rank + no leavers), and render human-readable summaries
- Location: `functions.py`
- Contains: `query()` (OpenDota, async/aiohttp, time-chunked), `get_match_data_nostratz()` (OpenDota sync), `query_stratz()` / `stratz_info()` (Stratz GraphQL, sync `requests`), `ret_kill_density()` / `ret_kill_density_nostratz()`, `check_for_guardian()`, `format_match_data()`, `format_player_summary()`, `create_heroes_string()`, `get_llm_summary()` (OpenAI)
- Depends on: `constants.py` for name lookups, `ability_ids.json` for ability names, external HTTP APIs
- Used by: `discord_bot.py`, `bot.py`, `lambda_function.py`
- Purpose: Map numeric Dota 2 IDs (hero, item, rank) to display strings
- Location: `constants.py`, `ability_ids.json`
- Contains: Dictionaries only, no logic
- Depends on: Nothing
- Used by: `functions.py`, `discord_bot.py` (via `from functions import *`, which re-exports `constants.py` names)
- Purpose: Would insert scrape results into Supabase (`insert_row()`), but has no caller
- Location: `database.py`
- Depends on: `supabase` Python client, env vars `SUPABASE_URL`/`SUPABASE_KEY`
- Used by: nothing currently
## Data Flow
### Primary Request Path (Discord bot, active production path)
### Legacy Telegram Path (`bot.py`, `lambda_function.py`)
- Entirely stateless across runs — there is no database read/write in the active path. Each run re-queries OpenDota for "matches in the last N days" and re-derives everything from scratch. Thread age (for cleanup) is the only "persisted" state, and it lives in Discord itself (`thread.created_at`), not in application storage.
## Key Abstractions
- Purpose: Raw OpenDota match summary (`match_id`, `duration`, `start_time`, `avg_rank_tier`) or full match detail (`radiant_score`, `dire_score`, `players[]`)
- Examples: Returned by `query()` and `get_match_data_nostratz()` in `functions.py`
- Pattern: Untyped `dict`/JSON passed by reference through the pipeline; no dataclass or schema validation
- Purpose: Rich per-player stats (items, ability casts, kill/death events, ward placements) keyed as `response["data"]["match"]["players"]`
- Examples: `query_stratz()`, `stratz_info()` in `functions.py`; consumed by `create_player_embed()`, `format_match_data()`, `format_player_summary()`
- Pattern: Deeply nested dict access with defensive `.get()` calls and `None` checks scattered inline (no schema/model class)
- Purpose: Simple heuristic (`total_kills / (duration_minutes)`) used as the interestingness filter for which matches get reported
- Examples: `ret_kill_density()` (Stratz-based, buggy — sums `radiantKills` twice, see Anti-Patterns), `ret_kill_density_nostratz()` (OpenDota-based, correct)
- Purpose: Restrict reports to Herald-tier matches (`avg_rank_tier <= 16` in the SQL query, plus a post-hoc `check_for_guardian()` that rejects if any player's `seasonRank > 15`)
- Examples: `functions.py:252` (SQL predicate), `functions.py:518-523` (post-filter)
## Entry Points
- Location: `discord_bot.py`
- Triggers: Process start (invoked by the Fly.io scheduler loop in `fly.toml`, or by `Dockerfile`'s `CMD`)
- Responsibilities: Connect to Discord, run one full scrape-and-report cycle in `on_ready()`, clean up old threads, disconnect and exit
- Location: `bot.py`
- Triggers: Manual script execution (`python bot.py`) — also written in Jupyter-cell style (`# %%` markers), suggesting interactive/notebook-style development use
- Responsibilities: Same scrape flow but posts to Telegram via `send_message()`; listed in `.gitignore` alongside `test.py`, meaning it is a local dev/experiment file not intended to be committed (though currently tracked in git history)
- Location: `lambda_function.py`
- Triggers: Intended for AWS Lambda invocation (per file name and comments referencing "lambda" environment), or manual `python lambda_function.py`
- Responsibilities: Same scrape flow, synchronous, posts to Telegram; contains commented-out Selenium/Chrome/OpenCV code for a screenshot-overlay feature that was removed from the active path
## Architectural Constraints
- **Threading:** Single-process, mixed sync/async. `discord_bot.py` runs on `asyncio` (via `discord.py`'s event loop) and calls `await query(...)`, but most `functions.py` HTTP calls (`query_stratz`, `stratz_info`, `get_match_data_nostratz`) are **blocking synchronous calls** (`requests`, `urllib`) executed directly inside async functions — this blocks the event loop for the duration of each HTTP request. No thread pool or `run_in_executor` offloading is used.
- **Global state:** Module-level singletons initialized at import time: the Discord `bot` client and intents (`discord_bot.py:22-24`), the Supabase `client` (`database.py:16-18`, unused), the `ability_ids` dict loaded from disk (`functions.py:46-51`), and all of `constants.py`'s dictionaries. Required env vars are read and validated at import time in both `discord_bot.py` and `functions.py`, meaning importing `functions.py` in any context (including test scripts) requires `STRATZ_API_TOKEN`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` to be set, even though the Telegram-related pipeline is not used by the active Discord entry point.
- **Circular imports:** None detected — `discord_bot.py` and `bot.py`/`lambda_function.py` import from `functions.py`, which imports from `constants.py`; no back-references.
- **Wildcard imports:** `discord_bot.py`, `bot.py`, and `lambda_function.py` all use `from functions import *`, which transitively re-exports `constants.py`'s names (`HEROES`, `ITEMS`, etc.) and stdlib imports (`datetime`, `time`, `asyncio`) into the importing module's namespace. This makes it hard to trace where a given name (e.g., `datetime`) actually originates.
- **Process lifecycle:** The bot is designed to run exactly once per process invocation and then call `bot.close()` — it is not a persistent daemon. Restart cadence is delegated entirely to the infrastructure layer (`fly.toml`'s shell loop), not to any in-app scheduler (no `cron`, `APScheduler`, etc.).
## Anti-Patterns
### Duplicate/divergent kill-density implementations
### Three parallel entry points implementing the same pipeline
### Blocking I/O inside `async def` functions
### Import-time environment variable enforcement in a shared module
## Error Handling
- Startup config validation raises `ValueError` immediately if required env vars are missing (`discord_bot.py:32-36`, `functions.py:22-36`)
- Per-match processing is wrapped in `try/except Exception as e: logger.error(...); continue` so one bad match doesn't abort the whole run (`discord_bot.py:225-285`, `bot.py:38-86`, `lambda_function.py`)
- HTTP calls use `while True: try/except: sleep(N); retry` infinite-retry loops with no backoff cap or max-attempts (`functions.py:257-270` for OpenDota chunk queries — 60s retry; `functions.py:304-310` for match detail — 60s retry; `functions.py:378-389` and `functions.py:405-411` for Stratz — 1s retry). None of these can be interrupted except by process kill.
- Top-level `send_herald_report()` catches any escaping exception, logs it as fatal, and re-raises (`discord_bot.py:292-294`) — the caller (`on_ready()`) then only logs it and proceeds to close the bot, so a fatal error still results in a graceful shutdown rather than a crash.
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
