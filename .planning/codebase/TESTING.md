# Testing Patterns

**Analysis Date:** 2026-07-01

## Test Framework

**Runner:**
- None. No `pytest`, `unittest`, or any test runner is declared in `requirements.txt` (`pypika`, `requests`, `numpy`, `pyTelegramBotAPI`, `openai`, `python-dotenv`, `discord.py`, `aiohttp` only)
- No `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, or `conftest.py` exists anywhere in the repo

**Assertion Library:**
- Not applicable — no test code exists

**Run Commands:**
```bash
# No test command exists. There is no `make test`, `npm test`-equivalent,
# CI workflow, or documented way to run tests in this repository.
```

## Test File Organization

**Location:**
- None. `find . -name "*.test.*" -o -name "*.spec.*"` and `find . -name "test_*.py"` return no results.
- `.gitignore` (`/home/clsandoval/cs/herald-scraper-bot/.gitignore`) explicitly ignores `test.py`, indicating a developer previously used an untracked local `test.py` scratch file for manual/ad-hoc testing, but this file is not present in the working tree and was never committed to git history (`git log --all --diff-filter=A --name-only | grep -i test` returns nothing).

**Naming:**
- Not applicable — no convention exists to document.

**Structure:**
- Not applicable.

## Test Structure

**Suite Organization:**
Not applicable — no automated test suite exists in this codebase.

**Patterns:**
- None found.

## Mocking

**Framework:** None (no `unittest.mock`, `pytest-mock`, or `responses`/`httpretty` used anywhere).

**What manual verification exists instead:**
- `bot.py` and `lambda_function.py` are written with `# %%` Jupyter/VSCode cell markers, suggesting the primary verification method during development is running cells interactively against live external APIs (OpenDota, Stratz) and inspecting `print()` output rather than automated tests, e.g. `bot.py:20` (`print(match_data)`) and `bot.py:31-32` (final cell just prints sorted match/duration pairs for manual inspection).
- Manual runs against production APIs are effectively the only validation mechanism currently in place. There is no fixture data, recorded HTTP cassette, or sample JSON payload checked into the repo to support offline testing (`ability_ids.json` at `/home/clsandoval/cs/herald-scraper-bot/ability_ids.json` is reference/lookup data, not test fixture data).

## Fixtures and Factories

**Test Data:**
- None exists. No sample match/player JSON payloads are checked in under any `fixtures/`, `test_data/`, or `__tests__/` directory.

**Location:**
- Not applicable.

## Coverage

**Requirements:** None enforced. No coverage tool (`coverage.py`, `pytest-cov`) is configured or installed.

**View Coverage:**
```bash
# Not applicable — no coverage tooling present.
```

## Test Types

**Unit Tests:** None. Pure functions that would be straightforward to unit test without network access exist and are good candidates if a test suite is introduced:
- `ret_kill_density_nostratz(match_data)` (`functions.py:315-321`) — pure arithmetic on a dict, no I/O
- `ret_kill_density(data, duration)` (`functions.py:324-337`) — pure logic, though note it contains a latent bug: `direKills = sum(match_data["radiantKills"])` reads `radiantKills` twice instead of `direKills` (line 327), so `totalKills` is always double the Radiant kill count. A unit test would catch this immediately.
- `check_for_guardian(stratz_players_data)` (`functions.py:518-523`) — pure logic over a list of dicts
- `format_herald_rank(rank)` — duplicated inline in `discord_bot.py:130-137` and `functions.py:775-782` — pure formatting logic, good candidate for extraction + unit testing
- `create_heroes_string`, `format_match_data`, `format_player_summary` (`functions.py`) — pure string-formatting functions given a match-data dict; testable with a hand-built fixture dict, no network needed

**Integration Tests:** None. Functions that call external APIs directly with no seam for substitution:
- `query()` (`functions.py:222-298`) — hits OpenDota's SQL explorer endpoint via `aiohttp`
- `query_stratz()` / `stratz_info()` (`functions.py:366-413`) — hit Stratz GraphQL API via `requests`
- `get_match_data_nostratz()` (`functions.py:301-312`) — hits OpenDota REST endpoint via `urllib.request`
- `get_llm_summary()` (`functions.py:847-906`) — calls OpenAI's `AsyncOpenAI` client directly inside the function body (constructed on every call), making it hard to substitute a fake client for testing
- `insert_row()` (`database.py:21-50`) — talks to Supabase; the module-level `supabase` client is a global initialized at import time from environment variables, which makes dependency injection for tests difficult without refactoring
- `send_message()` (`functions.py:340-363`) — POSTs to the Telegram Bot API directly with a hardcoded `chat_id` string literal (`"1405224455"`) rather than reading `TELEGRAM_CHAT_ID` from environment (inconsistent with the env-var validation for the same value earlier in the file at `functions.py:34-36`)

**E2E Tests:** None. `discord_bot.py`'s `send_herald_report()` orchestrates the full pipeline (OpenDota → Stratz → OpenAI → Discord) with no test double for any stage.

## Common Patterns

**Async Testing:**
```python
# Not applicable — no async test patterns exist.
# Note for future test authors: functions.py mixes async (`query`, `get_llm_summary`)
# and sync (`query_stratz`, `stratz_info`, `get_match_data_nostratz`, `send_message`)
# I/O functions. Any future test suite introducing pytest would need
# pytest-asyncio (or anyio) configured to exercise the async functions.
```

**Error Testing:**
```python
# Not applicable — no tests exist that assert on exception behavior,
# retry counts, or logging output.
```

## Recommendations for Introducing Tests

Since this repository currently has zero test infrastructure, if a future phase adds testing:

1. Add `pytest` (and `pytest-asyncio` for the async functions) to `requirements.txt` — currently absent (`/home/clsandoval/cs/herald-scraper-bot/requirements.txt`).
2. Start with pure-logic functions listed under "Unit Tests" above — they require no mocking and would immediately catch the `ret_kill_density` double-counting bug (`functions.py:327`).
3. For API-calling functions (`query_stratz`, `get_match_data_nostratz`, `query`), introduce `responses` or `aioresponses` to mock HTTP without hitting live OpenDota/Stratz endpoints — no such library exists in `requirements.txt` today.
4. For `database.py`, refactor the module-level `supabase` client into a function parameter or factory so tests can inject a fake client instead of relying on `SUPABASE_URL`/`SUPABASE_KEY` environment variables at import time.
5. For `get_llm_summary` (`functions.py:847`), extract the `AsyncOpenAI` client construction so a fake/mock client can be injected rather than instantiated inline on every call.
6. No CI configuration exists (no `.github/workflows/`) — introducing tests would also require adding a CI pipeline to run them automatically.

---

*Testing analysis: 2026-07-01*
