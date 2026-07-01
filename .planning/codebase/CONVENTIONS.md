# Coding Conventions

**Analysis Date:** 2026-07-01

## Naming Patterns

**Files:**
- Lowercase with underscores, one flat module per concern: `bot.py`, `database.py`, `discord_bot.py`, `functions.py`, `constants.py`, `lambda_function.py`
- No package/subdirectory structure — everything lives at repo root
- Entry-point scripts are named after their delivery mechanism (`discord_bot.py`, `lambda_function.py`, `bot.py`) rather than a shared `main.py`

**Functions:**
- `snake_case` throughout, e.g. `get_match_data_nostratz`, `ret_kill_density_nostratz`, `format_match_data` (`functions.py`)
- Verb-first names for actions: `send_message`, `query_stratz`, `create_match_embed` (`discord_bot.py:95`)
- Nested helper functions are common inside larger formatting functions, e.g. `get_hero_name`, `get_item_name`, `format_position` defined inside `format_match_data` (`functions.py:526-556`) and duplicated again inside `format_player_summary` (`functions.py:752-782`) and `create_player_embed` (`discord_bot.py:119-137`) — the same small helpers are re-implemented in three places instead of being shared utilities
- Inconsistent suffix usage: `_nostratz` suffix distinguishes OpenDota-only variants (`get_match_data_nostratz`, `ret_kill_density_nostratz`) from Stratz-based ones (`ret_kill_density`, `query_stratz`) — follow this suffix convention if adding another data-source-specific variant

**Variables:**
- `snake_case` for locals: `match_id`, `kill_density`, `stratz_players_data`
- Loop/aggregation variables are short and reused across functions: `radiant_players`, `dire_players`, `team_result`
- Module-level constants are `UPPER_SNAKE_CASE`: `STRATZ_API_TOKEN`, `OPENDOTA_URL`, `QUERY_HEADER`, `STRATZ_QUERY` (`functions.py:16-106`)
- Boolean-like state sometimes represented as `int` rather than `bool`, e.g. `leaver = 0` / `leaver = 1` in `discord_bot.py:237-240` and `lambda_function.py:48-51` instead of a `bool` flag

**Types:**
- Type hints are rare. Only `database.py:21` (`insert_row(table_name: str, data: Dict[str, Any]) -> bool`) uses full parameter and return annotations
- No annotations anywhere in `functions.py`, `discord_bot.py`, `lambda_function.py`, `bot.py` — when adding new functions in those files, match the surrounding untyped style unless doing a deliberate typing pass
- No dataclasses, TypedDicts, or Pydantic models — all structured data (match data, player data) is passed around as raw `dict`/`list` from JSON API responses and accessed via string keys (e.g. `match_data["data"]["match"]`)

## Code Style

**Formatting:**
- No formatter config detected (no `.black`, `pyproject.toml`, or `.prettierrc`). Code is manually formatted but broadly follows Black-like conventions: double quotes, trailing commas in multi-line calls, 4-space indentation
- Line lengths vary widely; some lines exceed 100 chars (e.g. long GraphQL query strings in `constants.py`)

**Linting:**
- No `.flake8`, `.pylintrc`, or `ruff` config present — no enforced lint rules
- Dead code is left in place rather than deleted, commented out with explanatory notes instead of removed, e.g. the entire Selenium/Chrome-options block in `functions.py:38-92` and the unused link-preview functions in `functions.py:429-441`. Follow this pattern when deprecating code: comment out with a `# Not used in X — reason` note rather than deleting outright, matching existing style

## Import Organization

**Order:**
Imports are not grouped by convention (no isort/stdlib-first ordering enforced). Typical pattern observed in `functions.py:1-13`:
1. Third-party/stdlib mixed together (`urllib`, `pypika`, `json`, `requests`, `time`, `logging`, `numpy`, `os`, `asyncio`, `aiohttp`)
2. Local wildcard imports (`from constants import *`)
3. Specific stdlib symbol imports (`from datetime import datetime, timedelta`)
4. Specific third-party symbol imports (`from pypika import Query, Table`)

**Path Aliases:**
- None (flat repo, no package structure, no `src/` layout)

**Wildcard imports:**
- `from functions import *` is used in `bot.py:2`, `discord_bot.py:11`, `lambda_function.py:5`
- `from constants import *` is used in `functions.py:11`
- This means constants like `HEROES`, `ITEMS`, `HERO_ID_TO_NAME` and every function in `functions.py` are implicitly available in consuming modules. When adding new shared helpers, add them to `functions.py` (or `constants.py` for static data) to preserve this pattern — do not introduce explicit imports inconsistently with siblings in the same file

## Error Handling

**Patterns:**
- Bare `except:` (no exception type) is common for network calls that should retry indefinitely, e.g. `functions.py:308`, `functions.py:361`, `functions.py:387`, `functions.py:409` — pattern is "infinite retry loop with `time.sleep(N)`":
  ```python
  while True:
      try:
          data = urllib.request.urlopen(req)
          break
      except:
          logging.warning("Timeout, retrying in 60 seconds")
          time.sleep(60)
  ```
- Broader business logic uses `except Exception as e:` with logging and either `continue` (skip this item, keep processing loop) or `raise` (propagate fatal error), e.g. `discord_bot.py:283-285` (`continue`) vs `discord_bot.py:292-294` (`raise` after logging "Fatal error")
- Specific Discord exceptions are caught before generic ones in `discord_bot.py:61-66`: `discord.Forbidden` → warning, `discord.NotFound` → warning, `Exception` → error. Follow this ordering (specific-to-generic) when adding new except blocks
- No custom exception classes defined anywhere in the codebase — all error handling uses built-in exceptions or third-party library exceptions (`aiohttp.ClientError`, `discord.Forbidden`, `discord.NotFound`)
- `database.py:44-50` follows a "return bool, log error" pattern rather than raising, for the Supabase insert helper — useful precedent for any new function that should not crash the caller on failure

## Logging

**Framework:** Python stdlib `logging`

**Patterns:**
- `discord_bot.py:16-19` and `lambda_function.py:11-14` both configure logging identically via `logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")` then create a module logger with `logger = logging.getLogger(__name__)` — replicate this exact block when adding a new entry-point script
- `bot.py:5` instead calls `logging.getLogger().setLevel(logging.INFO)` directly on the root logger without `basicConfig` — inconsistent with the other two entry points; prefer the `discord_bot.py`/`lambda_function.py` pattern for new entry points
- `functions.py` uses the module-level `logging` calls directly (`logging.warning(...)`, `logging.error(...)`) rather than a named logger — it has no `logger = logging.getLogger(__name__)` of its own
- f-strings are used almost exclusively inside log calls: `logger.info(f"Found {len(matches)} matches to process")`
- Some low-level retry loops use `print()` instead of `logging` (`functions.py:360-362`, `functions.py:388`, `functions.py:410`) — inconsistent with the logging-based approach elsewhere; prefer `logging.warning`/`logging.error` for new code rather than `print`

## Comments

**When to Comment:**
- Short inline comments explain "why", not "what", e.g. `functions.py:271` equivalent (`discord_bot.py:271`): `# ponytail: Discord caps a message at 2000 chars; chunk long summaries` — note the informal signed-comment style used for non-obvious workarounds
- Section-divider comments mark logical blocks within long functions, e.g. `# Teams`, `# Rank`, `# Items (shortened for embed)` inside `create_player_embed` (`discord_bot.py:141-186`)
- Large disabled code blocks are prefixed with an explanation of why they're inactive, e.g. `functions.py:38` (`# Selenium and CV2 imports commented out since they're not used in lambda_function.py`)

**Docstrings:**
- Present on most top-level functions but not all; format is a plain triple-quoted one-liner or short paragraph, occasionally with `Args:`/`Returns:`/`Example:` sections
- `database.py:22-39` has the most complete docstring in the codebase (Google-style `Args:`/`Returns:`/`Example:`) — use this as the template for any new public function needing full documentation
- Most functions in `functions.py` and `discord_bot.py` use a single-line docstring only, e.g. `"""Create a Discord embed for match summary"""` (`discord_bot.py:96`)
- No module-level docstrings anywhere

## Function Design

**Size:** No enforced limit — several functions exceed 100 lines with deep nesting (`format_match_data` in `functions.py:526-749` is ~220 lines with 5 nested helper functions and heavy conditional branching). New formatting/report functions should expect to follow this "one big function with local helpers" shape rather than being split into a class or separate module.

**Parameters:** Positional-with-defaults is the norm for network/query helpers, e.g. `query_stratz(match, url=STRATZ_GRAPHQL_URL, stratz_query=STRATZ_QUERY, api_token=STRATZ_API_TOKEN)` (`functions.py:366-371`) — defaults reference module-level constants, letting callers override for testing.

**Return Values:** Mixed — some functions return raw dicts (API responses passed straight through, e.g. `query_stratz` returns the parsed JSON unchanged), others return formatted strings for display, others return tuples (`ret_kill_density` returns `(totalKills, kill_density)` or `(-1, -1)` as a sentinel pair on error, `functions.py:336`). No consistent error/result wrapper type is used — sentinel values (`-1`, `-1, -1`, `None`) signal failure inline.

## Module Design

**Exports:** No `__all__` defined in any module — everything at module scope is implicitly public and exported via `import *`.

**Structure:**
- `constants.py`: static lookup data only (hero/item ID maps, GraphQL query templates, header dicts) — no logic
- `functions.py`: all business logic — API querying (OpenDota, Stratz), data transformation/formatting, Telegram sending, LLM summarization
- `database.py`: sole owner of the Supabase client and `insert_row` — only module using Supabase
- `discord_bot.py`, `lambda_function.py`, `bot.py`: three parallel entry points for different delivery channels (Discord bot, AWS Lambda/Telegram, notebook-style script), each importing from `functions.py` and duplicating similar orchestration logic (fetch matches → filter leavers/guardians → format → send). When modifying core match-processing logic, check all three entry points for divergence — they are not kept in sync automatically (e.g. `bot.py` uses the old `ret_kill_density` while `discord_bot.py`/`lambda_function.py` use `ret_kill_density_nostratz`)
- `bot.py` and `lambda_function.py` use `# %%` cell markers (Jupyter/VSCode interactive-cell syntax) indicating they were developed/run as notebooks rather than as standalone scripts

---

*Convention analysis: 2026-07-01*
