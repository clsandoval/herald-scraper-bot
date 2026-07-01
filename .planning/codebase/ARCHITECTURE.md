<!-- refreshed: 2026-07-01 -->
# Architecture

**Analysis Date:** 2026-07-01

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Scheduler (fly.toml)                     │
│   shell loop: run discord_bot.py once, sleep 24h, repeat     │
└───────────────────────────┬───────────────────────────────────┘
                            │ process start
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Entry Point: `discord_bot.py`                 │
│  discord.py Bot -> on_ready() -> send_herald_report()         │
└───────────┬───────────────────────────┬────────────────────────┘
            │                           │
            ▼                           ▼
┌───────────────────────────┐  ┌───────────────────────────────┐
│   Data-fetch functions    │  │   Presentation functions      │
│   `functions.py`          │  │   `discord_bot.py`            │
│  query() / query_stratz() │  │  create_match_embed()         │
│  get_match_data_nostratz()│  │  create_player_embed()        │
└──────────┬─────────────────┘  └───────────┬────────────────────┘
           │ HTTP (OpenDota, Stratz, OpenAI)  │ discord.py API
           ▼                                  ▼
┌─────────────────────────────────────────────────────────────┐
│         External services: OpenDota, Stratz GraphQL,         │
│         OpenAI (gpt-4.1-mini), Discord Gateway/REST           │
└─────────────────────────────────────────────────────────────┘
```

There is no persistence layer in the active path. `database.py` (Supabase client wrapper) exists but is not imported by `discord_bot.py`, `functions.py`, `bot.py`, or `lambda_function.py` — it is dead code kept for a possible future feature.

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

**Overall:** Script-based batch job / cron-style scraper, not a long-running service or a layered application. There is a single conceptual "pipeline" (fetch matches → filter → enrich → format → publish) implemented as a sequence of function calls inside one `async` driver function, `send_herald_report()` in `discord_bot.py`.

**Key Characteristics:**
- No web server, no request/response cycle — the "entry point" is a scheduled batch run that starts, does work, and exits (`bot.close()` is called at the end of `on_ready`).
- No ORM/data layer in the live path; all state is transient in-memory (lists/dicts from JSON API responses).
- Business logic (filtering, kill-density math, text formatting) and I/O (HTTP calls, Discord API calls) are mixed together in the same functions rather than separated into layers.
- Three near-duplicate entry points exist (`discord_bot.py`, `bot.py`, `lambda_function.py`) implementing the same scrape-and-report flow against different output channels (Discord vs Telegram) and different eras of the `query()` function (async chunked vs sync single-call).
- Configuration is entirely environment-variable driven via `python-dotenv`, loaded at module import time with hard failures (`raise ValueError`) if required vars are missing (`discord_bot.py:32-36`, `functions.py:22-36`).

## Layers

**Entry / orchestration layer:**
- Purpose: Bootstraps the client, decides when to run, and drives the top-level control flow (loop over matches, decide what to send, when to stop).
- Location: `discord_bot.py` (primary), `bot.py` and `lambda_function.py` (legacy/alternate)
- Contains: `on_ready()`, `main()`, `send_herald_report()`, `cleanup_old_threads()`
- Depends on: `functions.py` for all data fetching/formatting, `discord.py` SDK for output
- Used by: nothing — this is the top of the call graph

**Data-fetch / domain logic layer:**
- Purpose: Query external match data APIs, compute derived metrics (kill density), decide which matches qualify ("Herald" rank + no leavers), and render human-readable summaries
- Location: `functions.py`
- Contains: `query()` (OpenDota, async/aiohttp, time-chunked), `get_match_data_nostratz()` (OpenDota sync), `query_stratz()` / `stratz_info()` (Stratz GraphQL, sync `requests`), `ret_kill_density()` / `ret_kill_density_nostratz()`, `check_for_guardian()`, `format_match_data()`, `format_player_summary()`, `create_heroes_string()`, `get_llm_summary()` (OpenAI)
- Depends on: `constants.py` for name lookups, `ability_ids.json` for ability names, external HTTP APIs
- Used by: `discord_bot.py`, `bot.py`, `lambda_function.py`

**Static data / lookup layer:**
- Purpose: Map numeric Dota 2 IDs (hero, item, rank) to display strings
- Location: `constants.py`, `ability_ids.json`
- Contains: Dictionaries only, no logic
- Depends on: Nothing
- Used by: `functions.py`, `discord_bot.py` (via `from functions import *`, which re-exports `constants.py` names)

**Unused persistence layer:**
- Purpose: Would insert scrape results into Supabase (`insert_row()`), but has no caller
- Location: `database.py`
- Depends on: `supabase` Python client, env vars `SUPABASE_URL`/`SUPABASE_KEY`
- Used by: nothing currently

## Data Flow

### Primary Request Path (Discord bot, active production path)

1. Process starts, `discord.py` Bot connects, fires `on_ready()` (`discord_bot.py:297`)
2. `send_herald_report()` resolves the target channel via `bot.get_channel`/`fetch_channel` (`discord_bot.py:201-206`)
3. `query(days_back=3)` builds hourly time-chunked SQL queries against OpenDota's `public_matches` explorer endpoint and gathers them concurrently with `aiohttp` (`functions.py:222-298`)
4. For each match: `get_match_data_nostratz(match)` fetches per-match detail from OpenDota (`functions.py:301-312`); `ret_kill_density_nostratz()` computes kills-per-minute (`functions.py:315-321`)
5. Leaver check: any player with nonzero `leaver_status` skips the match entirely (`discord_bot.py:237-241`)
6. `query_stratz(match)` fetches detailed GraphQL player stats from Stratz (`functions.py:366-391`); `stratz_info(match)` fetches a lighter player list used only for the rank/"Guardian" filter (`functions.py:394-413`)
7. `check_for_guardian()` skips the match if any player's rank exceeds Herold tier 5 (rank > 15) (`functions.py:518-523`)
8. Presentation: `create_match_embed()` and `create_player_embed()` build Discord embeds (`discord_bot.py:95-195`); `format_match_data()` renders a full text dump (`functions.py:526-749`); `get_llm_summary()` sends that text to OpenAI `gpt-4.1-mini` for a witty commentary summary (`functions.py:847-906`)
9. Publish: bot posts the match embed to the channel, creates a thread from that message, posts player embeds and the LLM summary into the thread — chunked into ≤1800-char code blocks to respect Discord's 2000-char message limit (`discord_bot.py:266-276`)
10. After all matches are processed, `cleanup_old_threads()` deletes bot-owned threads older than 10 days, scanning both archived and active threads (`discord_bot.py:39-92`, invoked at `discord_bot.py:290`)
11. `on_ready()` calls `bot.close()`, terminating the process (`discord_bot.py:305-312`); the outer shell loop in `fly.toml` sleeps 24h and restarts the process

### Legacy Telegram Path (`bot.py`, `lambda_function.py`)

1. Same OpenDota/Stratz fetch and filter steps, but synchronous (`query()` without `await`, `requests`-based HTTP)
2. `send_message()` posts plain-text, MarkdownV2 `curl`-style payloads directly to a hardcoded Telegram chat ID via the Bot API (`functions.py:340-363`)
3. No thread concept — three separate flat messages are sent per match (`bot.py:76-78`)

**State Management:**
- Entirely stateless across runs — there is no database read/write in the active path. Each run re-queries OpenDota for "matches in the last N days" and re-derives everything from scratch. Thread age (for cleanup) is the only "persisted" state, and it lives in Discord itself (`thread.created_at`), not in application storage.

## Key Abstractions

**Match record (dict):**
- Purpose: Raw OpenDota match summary (`match_id`, `duration`, `start_time`, `avg_rank_tier`) or full match detail (`radiant_score`, `dire_score`, `players[]`)
- Examples: Returned by `query()` and `get_match_data_nostratz()` in `functions.py`
- Pattern: Untyped `dict`/JSON passed by reference through the pipeline; no dataclass or schema validation

**Stratz GraphQL response (nested dict):**
- Purpose: Rich per-player stats (items, ability casts, kill/death events, ward placements) keyed as `response["data"]["match"]["players"]`
- Examples: `query_stratz()`, `stratz_info()` in `functions.py`; consumed by `create_player_embed()`, `format_match_data()`, `format_player_summary()`
- Pattern: Deeply nested dict access with defensive `.get()` calls and `None` checks scattered inline (no schema/model class)

**Kill density (float):**
- Purpose: Simple heuristic (`total_kills / (duration_minutes)`) used as the interestingness filter for which matches get reported
- Examples: `ret_kill_density()` (Stratz-based, buggy — sums `radiantKills` twice, see Anti-Patterns), `ret_kill_density_nostratz()` (OpenDota-based, correct)

**Herald rank filter:**
- Purpose: Restrict reports to Herald-tier matches (`avg_rank_tier <= 16` in the SQL query, plus a post-hoc `check_for_guardian()` that rejects if any player's `seasonRank > 15`)
- Examples: `functions.py:252` (SQL predicate), `functions.py:518-523` (post-filter)

## Entry Points

**`discord_bot.py` (active/production):**
- Location: `discord_bot.py`
- Triggers: Process start (invoked by the Fly.io scheduler loop in `fly.toml`, or by `Dockerfile`'s `CMD`)
- Responsibilities: Connect to Discord, run one full scrape-and-report cycle in `on_ready()`, clean up old threads, disconnect and exit

**`bot.py` (legacy, git-ignored, not deployed):**
- Location: `bot.py`
- Triggers: Manual script execution (`python bot.py`) — also written in Jupyter-cell style (`# %%` markers), suggesting interactive/notebook-style development use
- Responsibilities: Same scrape flow but posts to Telegram via `send_message()`; listed in `.gitignore` alongside `test.py`, meaning it is a local dev/experiment file not intended to be committed (though currently tracked in git history)

**`lambda_function.py` (legacy/alternate deployment target):**
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

**What happens:** `ret_kill_density()` (`functions.py:324-337`, Stratz-based) sums `match_data["radiantKills"]` for *both* `radiantKills` and `direKills` (`direKills = sum(match_data["radiantKills"])` — copy-paste bug at `functions.py:327`), silently double-counting Radiant kills and ignoring Dire kills entirely. Meanwhile `ret_kill_density_nostratz()` (`functions.py:315-321`, OpenDota-based) is correct and is the one actually used by `discord_bot.py`.
**Why it's wrong:** Any code path that calls the Stratz-based `ret_kill_density()` (currently only `bot.py`'s legacy Telegram driver via `ret_kill_density`, invoked from `bot.py`'s original commented flow, and directly in `bot.py`'s top-level script) will report incorrect kill totals/density.
**Do this instead:** Use `ret_kill_density_nostratz()` exclusively, or fix the copy-paste bug (`direKills = sum(match_data["direKills"])`) and delete the redundant function once the Telegram-based `bot.py` path is retired.

### Three parallel entry points implementing the same pipeline

**What happens:** `discord_bot.py`, `bot.py`, and `lambda_function.py` each re-implement "fetch matches → filter Herald rank/leavers → format → post" with slightly different HTTP libraries (sync `requests`/`urllib` vs async `aiohttp`), different output channels (Discord vs Telegram), and different levels of env-var validation.
**Why it's wrong:** Any bug fix or filter tweak (e.g., the kill-density formula, or the `days_back` window) must be manually ported across all three files, and they have already drifted (e.g., `bot.py` calls `query(days_back=1)` synchronously, which doesn't match the async signature now in `functions.py:222`, meaning `bot.py` is currently broken/unrunnable against the current `functions.py`).
**Do this instead:** Treat `discord_bot.py` as the single source of truth; either delete `bot.py`/`lambda_function.py` or explicitly mark them archived (e.g., move to a `legacy/` directory) so future changes only target one pipeline.

### Blocking I/O inside `async def` functions

**What happens:** `query_stratz()`, `stratz_info()`, and `get_match_data_nostratz()` use synchronous `requests`/`urllib` calls with blocking `time.sleep()` retry loops, but are called from inside `async def send_herald_report()` in `discord_bot.py` (e.g., `functions.py:227-234` called at `discord_bot.py:227-234`).
**Why it's wrong:** Each blocking call freezes the entire `asyncio` event loop, meaning Discord heartbeats/gateway events can be delayed or missed while waiting on Stratz/OpenDota responses, especially under the `while True: ... time.sleep(60)` retry loops in `get_match_data_nostratz` (`functions.py:304-310`).
**Do this instead:** Use `aiohttp` (already a dependency, already used in `query()`) for all outbound HTTP calls made from async code, or wrap the sync calls with `asyncio.to_thread(...)`.

### Import-time environment variable enforcement in a shared module

**What happens:** `functions.py:22-36` raises `ValueError` at import time if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are missing, even though the active Discord pipeline (`discord_bot.py`) never sends Telegram messages.
**Why it's wrong:** Anyone using `functions.py` in isolation (unit tests, a new Discord-only deployment, a REPL) is forced to set unrelated Telegram credentials just to import the module.
**Do this instead:** Move env-var validation into the specific functions that need those variables (e.g., inside `send_message()`), or validate lazily/at call time rather than at import time.

## Error Handling

**Strategy:** Best-effort, log-and-continue at the per-match level; fail-fast (raise) at startup/config level.

**Patterns:**
- Startup config validation raises `ValueError` immediately if required env vars are missing (`discord_bot.py:32-36`, `functions.py:22-36`)
- Per-match processing is wrapped in `try/except Exception as e: logger.error(...); continue` so one bad match doesn't abort the whole run (`discord_bot.py:225-285`, `bot.py:38-86`, `lambda_function.py`)
- HTTP calls use `while True: try/except: sleep(N); retry` infinite-retry loops with no backoff cap or max-attempts (`functions.py:257-270` for OpenDota chunk queries — 60s retry; `functions.py:304-310` for match detail — 60s retry; `functions.py:378-389` and `functions.py:405-411` for Stratz — 1s retry). None of these can be interrupted except by process kill.
- Top-level `send_herald_report()` catches any escaping exception, logs it as fatal, and re-raises (`discord_bot.py:292-294`) — the caller (`on_ready()`) then only logs it and proceeds to close the bot, so a fatal error still results in a graceful shutdown rather than a crash.

## Cross-Cutting Concerns

**Logging:** Standard library `logging` module throughout, configured via `logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")` in each entry point (`discord_bot.py:16-19`, `lambda_function.py:11-14`); `bot.py` only sets the root logger level without a formatter. No structured logging, no external log aggregation.

**Validation:** No schema validation library. All "validation" is ad-hoc `if not X: raise ValueError(...)` checks on env vars at import/startup time, plus inline `None`/key-existence checks (`if "stats" in player and ...`) when reading nested API responses.

**Authentication:** All outbound auth is bearer-token/API-key based via env vars — `DISCORD_BOT_TOKEN`, `STRATZ_API_TOKEN` (Bearer header, `functions.py:373`), `OPENAI_API_KEY` (via `AsyncOpenAI` client, `functions.py:887`), `TELEGRAM_BOT_TOKEN` (embedded in the Telegram Bot API URL). No OAuth flows, no session/cookie auth.

---

*Architecture analysis: 2026-07-01*
