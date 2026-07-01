# Codebase Concerns

**Analysis Date:** 2026-07-01

## Tech Debt

**Dead/orphaned entry points (`bot.py`, `lambda_function.py`):**
- Issue: The repo has three separate "main" scripts (`bot.py`, `lambda_function.py`, `discord_bot.py`) that scrape and report matches via different channels (raw script, Telegram, Discord). Only `discord_bot.py` is wired into the Dockerfile/fly.toml deployment (`CMD ["python", "discord_bot.py"]` in `Dockerfile`). `bot.py` and `lambda_function.py` are stale and call APIs incorrectly (see Known Bugs).
- Files: `bot.py`, `lambda_function.py`
- Impact: Confusing for future maintainers — unclear which script is "the bot." Both are broken and would fail if run (see below), so they provide negative value if someone tries to use them as a reference.
- Fix approach: Delete `bot.py` and `lambda_function.py`, or clearly mark them as deprecated/archived, since `discord_bot.py` is the only actively deployed entry point per `Dockerfile` and `fly.toml`.

**Unused Supabase integration (`database.py`):**
- Issue: `database.py` initializes a Supabase client and defines `insert_row()`, but nothing in the codebase calls `insert_row` or imports `database` — verified via repo-wide grep. `supabase` is also not listed in `requirements.txt`, so importing this module would raise `ModuleNotFoundError` in the deployed container.
- Files: `database.py`, `requirements.txt`
- Impact: Dead code that would crash on import if anyone wired it in without first fixing dependencies. Adds confusion about whether match data is persisted anywhere (it currently is not — every run is stateless, relying only on Discord thread history).
- Fix approach: Either remove `database.py` entirely, or finish the integration (add `supabase` to `requirements.txt`, call `insert_row` from `discord_bot.py` after processing each match) and add persistence tests.

**Duplicate/near-duplicate formatting and query logic across scripts:**
- Issue: `format_match_data`, `format_player_summary`, `create_player_embed`, `get_hero_name`, `get_item_name`, `format_herald_rank`, and `format_position` closures are redefined inline in multiple places (`functions.py:531-556`, `functions.py:757-782`, `discord_bot.py:122-137`) instead of being shared helpers.
- Files: `functions.py`, `discord_bot.py`
- Impact: Any fix to hero/item/rank name-resolution logic must be applied in 3+ places; already a source of drift risk (e.g., `format_herald_rank` in `discord_bot.py` vs `functions.py` could diverge silently).
- Fix approach: Extract shared helpers (`get_hero_name`, `get_item_name`, `format_herald_rank`, `format_position`) into `constants.py` or a new `formatting.py` module and import them everywhere.

**Redundant OpenDota API calls per match:**
- Issue: `discord_bot.py:227` and `discord_bot.py:231` both call `get_match_data_nostratz(match)` — the exact same network request is made twice per match with no caching.
- Files: `discord_bot.py:227`, `discord_bot.py:231`
- Impact: Doubles OpenDota API load and latency per match unnecessarily; on a run with many matches this adds material wall-clock time and increases exposure to rate limiting / timeouts.
- Fix approach: Call `get_match_data_nostratz(match)` once, store in `match_data`, and read `match_data["players"]` for the leaver check.

**Large commented-out code blocks left in `functions.py`:**
- Issue: Selenium/Chrome/CV2 setup code (`functions.py:38-92`) and unused placeholder functions (`functions.py:427-441`) are commented out rather than removed, along with a disabled "ability cast report" block (`functions.py:619-637`).
- Files: `functions.py:38-92`, `functions.py:427-441`, `functions.py:619-637`
- Impact: Adds ~90 lines of noise to a single 906-line file, obscuring the active code path and making it harder to know what's actually load-bearing.
- Fix approach: Delete commented-out blocks; rely on git history if they're needed again. If ability cast reporting is a planned feature, track it as a TODO/issue instead of leaving disabled code inline.

**Unused imports:**
- Issue: `numpy` is imported in `functions.py:7` (`import numpy as np`) but never referenced anywhere in the file.
- Files: `functions.py:7`
- Impact: Unnecessary dependency increases install time/image size and signals unclear ownership of what's actually needed.
- Fix approach: Remove the import and drop `numpy` from `requirements.txt` if nothing else needs it.

**Inconsistent function signatures across scripts (`query` days parameter):**
- Issue: `functions.py:222` defines `async def query(url=OPENDOTA_URL, days_back=2, day_period=1)`, but `bot.py:9` calls it as `query(days=3)` — a keyword argument that does not exist on the current signature.
- Files: `bot.py:9`, `functions.py:222`
- Impact: `bot.py` would raise `TypeError: query() got an unexpected keyword argument 'days'` immediately if run, confirming it is unmaintained/dead.
- Fix approach: Delete `bot.py` (see "Dead/orphaned entry points" above) or update the call site if it's ever revived.

## Known Bugs

**`lambda_function.py` calls async `query()` synchronously:**
- Symptoms: `functions.py:222` defines `query()` as `async def`. `lambda_function.py:23` calls `json_data = query(days_back=1)` without `await` and with no `asyncio.run()` wrapper anywhere in the file. This assigns a coroutine object to `json_data`, and the subsequent `json_data["rows"]` access (`lambda_function.py:26`) raises `TypeError: 'coroutine' object is not subscriptable`.
- Files: `lambda_function.py:23`, `functions.py:222`
- Trigger: Run `python lambda_function.py` (or invoke it as a Lambda handler) — it fails on the first real line of logic.
- Workaround: None currently; the script is unusable as-is. Not referenced by `Dockerfile` or `fly.toml`, so it is not part of the deployed path today.

**`send_message()` hardcodes a live Telegram bot token in the URL (leaked secret):**
- Symptoms: `functions.py:94` defines `TG_URL = "https://api.telegram.org/bot***REDACTED-REVOKED-TOKEN***/sendMessage"` — a full bot token embedded directly in source and committed to git history. `functions.py:340-363` (`send_message`) also hardcodes `"chat_id": "1405224455"` rather than using `TELEGRAM_CHAT_ID`/`TELEGRAM_BOT_TOKEN` env vars that are validated at module load (`functions.py:30-36`).
- Files: `functions.py:94`, `functions.py:340-363`
- Trigger: Any call to `send_message()` (used by `bot.py`, `lambda_function.py`) posts to this hardcoded token/chat, ignoring the `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` env vars that the module otherwise requires and validates.
- Workaround: None — this is a real secret exposed in a public-facing git repo. See Security Considerations below for remediation.

**`leaver_status` vs `leaverStatus` key naming mismatch risk:**
- Symptoms: `discord_bot.py:239` and `lambda_function.py:50` check `player["leaver_status"]` (snake_case, OpenDota REST API convention) against data returned by `get_match_data_nostratz` (OpenDota REST). Meanwhile `functions.py:332-334` (`ret_kill_density`, unused by `discord_bot.py`) checks `status["leaverStatus"]` (camelCase, Stratz GraphQL convention) on Stratz data. These two conventions are correct for their respective APIs individually, but the duplication is a trap: if a future edit assumes one field name works for both data sources, matches will silently fail the leaver check or raise `KeyError`.
- Files: `discord_bot.py:239`, `lambda_function.py:50`, `functions.py:332-334`
- Trigger: Passing Stratz-shaped data into the snake_case check (or vice versa) silently returns `False`/raises `KeyError` depending on `.get()` vs `[]` usage — currently both use direct `[]` indexing with no `.get()` fallback, so a missing key raises an uncaught `KeyError` inside the per-match `try/except` in `discord_bot.py:225-285`, which is caught generically and logged, masking the real cause.
- Workaround: None needed today since the two paths aren't mixed, but no test coverage protects against regression.

**Bare `except:` clauses swallow all exceptions including `KeyboardInterrupt`/network errors indiscriminately:**
- Symptoms: `functions.py:308`, `functions.py:387`, `functions.py:409` use bare `except:` (no exception type) inside `while True:` retry loops. These will silently retry forever on ANY error — including programming errors like `NameError` or `AttributeError` — not just transient network issues, since there's no distinction made.
- Files: `functions.py:301-312` (`get_match_data_nostratz`), `functions.py:366-391` (`query_stratz`), `functions.py:394-413` (`stratz_info`)
- Trigger: Any bug in response parsing, or a persistent 4xx from the API (e.g., invalid match ID, revoked API token, malformed query) causes an infinite retry loop that never terminates, hanging the entire scrape job.
- Workaround: None — this can cause the Discord bot process to hang indefinitely without ever calling `bot.close()`, defeating the "run once daily then exit" design in `fly.toml`'s scheduler loop.

## Security Considerations

**Telegram bot token committed to source and git history:**
- Risk: A real, usable Telegram bot token is hardcoded in `functions.py:94` inside `TG_URL`. Anyone with repo access (or who finds it via GitHub search/history) can control this bot, send messages as it, or abuse the token.
- Files: `functions.py:94`, `functions.py:340-363`
- Current mitigation: None. The token is in the working tree today, not just history.
- Recommendations: Revoke/regenerate the token via the Telegram BotFather immediately, remove the hardcoded value, and use `os.getenv("TELEGRAM_BOT_TOKEN")` (already loaded at `functions.py:18` but unused by `send_message`). Consider scrubbing git history (e.g., `git filter-repo`) since the token is already exposed in past commits, and treat it as compromised regardless.

**`.env` correctly gitignored, but no `.env.example` for onboarding:**
- Risk: `.gitignore` correctly excludes `.env` (`.gitignore:12`) and `.dockerignore` also excludes it, so current secret hygiene for *new* secrets (Discord token, Stratz token, OpenAI key, Supabase keys) is reasonable. However, there is no `.env.example` documenting which vars are required, increasing the chance a future contributor pastes a real secret into a tracked file by mistake (as apparently happened with the Telegram token).
- Files: `.gitignore`, `.dockerignore` (no `.env.example` present)
- Current mitigation: `.gitignore`/`.dockerignore` exclude `.env`.
- Recommendations: Add a `.env.example` listing `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `STRATZ_API_TOKEN`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SUPABASE_URL`, `SUPABASE_KEY` with placeholder values, and add a pre-commit secret scanner (e.g., `gitleaks`, `detect-secrets`) to catch hardcoded tokens like the one in `functions.py:94` before merge.

**Bot runs with unnecessary Docker root capability reduction only, no network egress restriction:**
- Risk: `Dockerfile:24-26` correctly creates and switches to a non-root `app` user, which is good practice. However, the container has unrestricted outbound network access to call four external APIs (OpenDota, Stratz, OpenAI, Discord) plus a hardcoded Telegram endpoint, with no egress allowlisting — a supply-chain-compromised dependency could exfiltrate the `DISCORD_BOT_TOKEN`/`OPENAI_API_KEY`/`STRATZ_API_TOKEN` env vars trivially.
- Files: `Dockerfile`
- Current mitigation: Non-root user execution (`Dockerfile:25-26`).
- Recommendations: Low priority for a small hobby bot, but consider Fly.io network policies or minimal-privilege API tokens (Stratz/OpenAI keys scoped to only what's needed) as defense in depth.

## Performance Bottlenecks

**Sequential per-match processing with fixed sleeps in `discord_bot.py`:**
- Problem: `send_herald_report()` processes matches one at a time in a `for` loop (`discord_bot.py:224-285`), making 3 blocking synchronous HTTP calls per match (`get_match_data_nostratz` x2, `query_stratz`, `stratz_info`) plus one async OpenAI call, with an explicit `await asyncio.sleep(2)` between matches (`discord_bot.py:281`).
- Files: `discord_bot.py:198-294`, `functions.py:301-413`
- Cause: `get_match_data_nostratz`, `query_stratz`, and `stratz_info` all use blocking `urllib.request`/`requests` calls (`functions.py:306`, `functions.py:380`, `functions.py:407`) inside an `async def` function (`send_herald_report`), which blocks the entire asyncio event loop (including Discord's heartbeat) for the duration of each HTTP request. With multiple matches per run (the `query()` window is `days_back=3`, `day_period=1`, i.e. a full day of Herald-tier 75+ minute matches), this can add up to minutes of wall-clock time and risks Discord gateway heartbeat timeouts/disconnects during long blocking calls.
- Improvement path: Convert `get_match_data_nostratz`, `query_stratz`, and `stratz_info` to use `aiohttp` (already a dependency, used in `query()`) instead of blocking `urllib`/`requests`, so the event loop isn't blocked and Discord's heartbeat keeps functioning during scrapes.

**Retry loops use long fixed sleeps with no exponential backoff or cap:**
- Problem: `functions.py:270` (`await asyncio.sleep(60)`), `functions.py:310` (`time.sleep(60)`) retry with a flat 60-second delay indefinitely on any failure, and `functions.py:389`/`functions.py:411` retry every 1 second indefinitely on Stratz failures.
- Files: `functions.py:257-270`, `functions.py:304-310`, `functions.py:378-389`, `functions.py:405-411`
- Cause: No backoff strategy, no maximum retry count, and (per bare `except:` above) no ability to distinguish a transient network blip from a permanent failure (bad match ID, revoked token, 4xx client error).
- Improvement path: Add exponential backoff with jitter and a max retry count (e.g., 5 attempts), and raise/log a clear error after exhausting retries instead of looping forever.

**All OpenDota `public_matches` queries fetch and filter Herald-tier matches with `avg_rank_tier <= 16` server-side, but Stratz/leaver/guardian filtering happens after 3-4 sequential API calls per match:**
- Problem: `discord_bot.py:224-247` fetches full match data, computes kill density, checks leavers, THEN calls `stratz_info` to check for "guardian" rank players (`check_for_guardian`) and skips (`continue`) only after already making 3 API calls (`get_match_data_nostratz` x2 + `query_stratz` + `stratz_info`) for matches that get discarded.
- Files: `discord_bot.py:224-247`
- Cause: Filtering order is not optimized — cheapest/most-selective filters (leaver status, from data already fetched via `get_match_data_nostratz`) run before the guardian check, but the guardian check requires yet another full API round-trip (`stratz_info`) that duplicates player data already available via `query_stratz` (`stratz_response`), which also contains `steamAccount.seasonRank` (`constants` / `STRATZ_QUERY` at `functions.py:116-118`) — the exact field `check_for_guardian` needs (`functions.py:518-523`).
- Improvement path: Reuse `stratz_response["data"]["match"]["players"]` (already fetched at `discord_bot.py:234`) for the guardian check instead of making a fourth API call via `stratz_info(match)` at `discord_bot.py:245`. This eliminates one full network round-trip per match.

## Fragile Areas

**`ret_kill_density()` sums the wrong team's kills (Radiant counted twice):**
- Files: `functions.py:324-337`
- Why fragile: `functions.py:326-327` computes `radiantKills = sum(match_data["radiantKills"])` and `direKills = sum(match_data["radiantKills"])` — both lines reference `radiantKills`, so Dire's actual kill data is never used. This function is currently only called from the dead `bot.py` script, so it has no live impact today, but if anyone revives or copies this logic, the bug will resurface silently (wrong total kill counts, no crash).
- Safe modification: Fix line `functions.py:327` to read `match_data["direKills"]` (or the correctly-cased field from the Stratz schema) before this function is used anywhere live. Currently `discord_bot.py`/`lambda_function.py` use `ret_kill_density_nostratz` instead (`functions.py:315-321`), which is correct, so this bug is currently dormant but latent.
- Test coverage: None — there are no automated tests anywhere in the repo (see Test Coverage Gaps).

**`get_llm_summary()` sends full raw match data (including position coordinates, timestamps, all events) to OpenAI with no data minimization or truncation:**
- Files: `functions.py:847-906`
- Why fragile: `format_match_data()` (`functions.py:526-750`) can produce very large text blobs — for a 75+ minute Herald match with full `killEvents`, `deathEvents`, `itemPurchases`, `wards`, and `abilityLearnEvents` per player (10 players), this could be tens of thousands of characters. This is passed directly into the prompt with no length check, token counting, or truncation before calling `gpt-4.1-mini` (`functions.py:892-895`), risking context-length errors or high per-run OpenAI cost for long matches with heavy activity.
- Safe modification: Add a token/length estimate and truncate or summarize `format_match_data()` output before sending to the LLM; consider dropping low-value fields (raw ward/courier-kill coordinates) from the prompt.
- Test coverage: None. No cost/length monitoring exists; the only signal is `print()` statements logging token usage (`functions.py:897-899`), which are not captured or alerted on anywhere.

**Discord embed field limits are not defensively handled:**
- Files: `discord_bot.py:147-189` (`create_team_embed`)
- Why fragile: Discord embeds have hard limits (25 fields max per embed, 1024 chars per field value, 6000 chars total). `create_team_embed` adds one field per player (5 per team, so under the 25-field cap currently), but `field_value` (`discord_bot.py:183-185`) concatenates KDA/rank/APM/Dota+/items with no length check. A player with many distinct items across a very long match, combined with long hero/item names, could exceed the 1024-character-per-field limit and cause `discord.HTTPException` when sending — which would be caught by the generic `except Exception` in `discord_bot.py:283-285` and silently skip that match's entire report (not just the embed).
- Safe modification: Truncate `field_value` defensively (e.g., cap at ~1000 chars) before adding to the embed, and add a specific `except discord.HTTPException` branch to distinguish Discord API failures from other errors in the per-match loop.
- Test coverage: None.

**`discord_bot.py` module-level `raise ValueError` on missing env vars crashes at import time, not gracefully:**
- Files: `discord_bot.py:32-36`
- Why fragile: If `DISCORD_BOT_TOKEN` or `DISCORD_CHANNEL_ID` are missing, the module raises at import time. This is reasonable for a fail-fast design, but combined with the `fly.toml` scheduler (`fly.toml:18-19`: `while true; do python discord_bot.py; sleep 86400; done`), a missing/misconfigured secret would cause the process to crash-loop every 24 hours indefinitely with no alerting — the failure would be silent to end users (no Discord message ever gets sent, and there's no external monitoring to notice the crash).
- Safe modification: Add external monitoring/alerting (e.g., Fly.io health checks or a dead-man's-switch ping to a monitoring service) so a startup crash is noticed rather than silently producing zero reports.
- Test coverage: None.

**`functions.py` performs environment-variable validation for Telegram/OpenAI/Stratz vars even though `discord_bot.py` doesn't use Telegram at all:**
- Files: `functions.py:30-36`, `discord_bot.py:11` (`from functions import *`)
- Why fragile: `discord_bot.py` imports everything from `functions.py`, which unconditionally requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to be set (`functions.py:30-36`) even though the Discord bot never sends Telegram messages. This creates an unnecessary coupling: the Discord bot won't even start if unrelated Telegram secrets are missing.
- Safe modification: Move Telegram-specific validation into `bot.py`/`lambda_function.py` (or delete those files and drop Telegram validation from `functions.py` entirely if Telegram support is no longer needed).
- Test coverage: None.

## Scaling Limits

**Single-process, single-run-per-day design with no concurrency across matches:**
- Current capacity: Processes matches sequentially with a 2-second sleep between each (`discord_bot.py:281`), plus 3-4 blocking HTTP calls per match. For a busy day with many qualifying Herald-tier 75+ minute matches, total run time scales linearly and could take many minutes to tens of minutes.
- Limit: `fly.toml:18-19` runs the bot once every 24 hours (`sleep 86400`) via a shell loop — if a run takes longer than expected (e.g., due to the infinite retry loops described above), the next scheduled run will simply be delayed, not skipped or run in parallel, so there's no hard "scaling wall" but growing match volume steadily degrades freshness of reports.
- Scaling path: Parallelize match processing with `asyncio.gather` (bounded by a semaphore to respect Discord/API rate limits) and convert blocking `requests`/`urllib` calls to `aiohttp` as noted in Performance Bottlenecks.

**OpenDota `public_matches` explorer endpoint has undocumented row/response limits:**
- Current capacity: `query()` (`functions.py:222-298`) already chunks requests into 1-hour windows to work around suspected OpenDota API response size limits, gathering them concurrently via `aiohttp`.
- Limit: If OpenDota's per-request row cap is lower than expected, or if match volume increases within a given hour (e.g., during a major patch or event), results could silently be truncated with no validation that the returned row count looks reasonable.
- Scaling path: Add a sanity check/log warning if any chunk returns a suspiciously round number of rows (e.g., exactly at a known API limit) to detect truncation early.

## Dependencies at Risk

**`supabase` used in code but absent from `requirements.txt`:**
- Risk: `database.py:5` does `from supabase import create_client, Client`, but `supabase` is not listed in `requirements.txt`. Any code path that imports `database.py` in the deployed Docker image (built from `requirements.txt`) will fail with `ModuleNotFoundError`.
- Impact: Currently no impact since nothing imports `database.py` (dead code, see Tech Debt), but this is a landmine for whoever tries to wire it up next.
- Migration plan: Add `supabase` to `requirements.txt` if `database.py` is kept/finished, or delete `database.py` if the Supabase integration is abandoned.

**`pyTelegramBotAPI` (`telebot`) and Telegram integration retained for dead code paths only:**
- Risk: `requirements.txt:4` includes `pyTelegramBotAPI`, used only by `lambda_function.py` (broken, see Known Bugs) and indirectly required by `functions.py`'s env-var validation (`functions.py:30-36`), even though the deployed bot (`discord_bot.py`) never sends Telegram messages.
- Impact: Unnecessary dependency and required env vars (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) for a feature that isn't part of the live product, increasing operational surface area (one more thing that can be misconfigured and block startup).
- Migration plan: Remove `pyTelegramBotAPI` from `requirements.txt` and the Telegram env var validation from `functions.py` once `bot.py`/`lambda_function.py` are deleted (see Tech Debt).

## Missing Critical Features

**No persistence layer for processed matches:**
- Problem: Every run of `discord_bot.py` re-queries OpenDota for the last `days_back=3` days (`discord_bot.py:210`) with no record of which matches were already reported. The only implicit de-duplication is that Discord threads exist for previously-reported matches, but the code does not check for or skip matches that already have a thread — if `days_back`/`day_period` windows ever overlap between runs (e.g., due to a delayed run), duplicate reports for the same match are possible.
- Blocks: Reliable exactly-once reporting; also blocks any future analytics/history features (e.g., "matches reported this month") since nothing is persisted (the `database.py` Supabase integration exists but is unused/unwired, see Tech Debt).

**No monitoring/alerting for scrape failures:**
- Problem: All top-level errors are caught and logged via Python `logging` only (`discord_bot.py:292-294`, `discord_bot.py:307-308`). Logs go to stdout (per `Dockerfile`/`fly.toml`, no log aggregation configured), so failures are only visible if someone manually checks Fly.io logs.
- Blocks: Any confidence that the daily report actually ran successfully; a silent failure (e.g., Discord token revoked, Stratz API down, OpenAI quota exceeded) could go unnoticed indefinitely since there's no fallback notification channel.

## Test Coverage Gaps

**No automated tests exist anywhere in the repository:**
- What's not tested: Every function in `functions.py`, `discord_bot.py`, `database.py`, `lambda_function.py`, and `bot.py` — there is no `tests/` directory, no `pytest`/`unittest` files, and no test runner configured in `requirements.txt` or any CI config (no `.github/workflows` directory found).
- Files: Entire repository — confirmed via `find`/`ls` showing no test files, and `requirements.txt` has no test framework listed.
- Risk: Every bug documented in this file (the `ret_kill_density` Radiant/Dire mix-up, the `query()`/`bot.py` signature mismatch, the async/sync `lambda_function.py` bug, the double API call in `discord_bot.py`) would have been caught by even minimal unit tests on the pure data-transformation functions (`ret_kill_density`, `ret_kill_density_nostratz`, `get_max_hero_damage`, `format_match_data`, `check_for_guardian`). None of these require network access to test given fixture JSON.
- Priority: High — these are pure functions with no external dependencies, making them cheap to test first. Recommend starting with `check_for_guardian`, `ret_kill_density_nostratz`, `get_max_hero_damage`, and `format_herald_rank`.

**No integration/smoke test for the deployed entry point (`discord_bot.py`):**
- What's not tested: `send_herald_report()` end-to-end flow, embed field-limit handling, thread creation/cleanup logic (`cleanup_old_threads`), and the message-chunking logic for the 2000-character Discord limit (`discord_bot.py:275-276`).
- Files: `discord_bot.py`
- Risk: Regressions in Discord-specific formatting (e.g., embed limits, chunking math) would only be caught in production when a report fails to send.
- Priority: Medium — would require mocking `discord.py`'s `Client`/`Channel`/`Thread` objects, more effort than the pure-function tests above, but high value given this is the only live code path.

---

*Concerns audit: 2026-07-01*
