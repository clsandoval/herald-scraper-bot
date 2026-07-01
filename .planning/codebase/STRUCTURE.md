# Codebase Structure

**Analysis Date:** 2026-07-01

## Directory Layout

```
herald-scraper-bot/
├── discord_bot.py       # Active entry point: Discord bot, embeds, thread lifecycle, on_ready driver
├── functions.py         # Data-fetch + domain logic: OpenDota/Stratz/OpenAI calls, formatting, filters
├── constants.py         # Static lookup tables: HERO_ID_TO_NAME, ITEM_MAP, RANK_MAP (+ HEROES/ITEMS aliases)
├── database.py          # Supabase insert helper — standalone, currently unused by any entry point
├── bot.py               # Legacy manual/notebook-style script, Telegram output, git-ignored (still tracked)
├── lambda_function.py   # Legacy AWS-Lambda-oriented script, Telegram output, sync HTTP
├── ability_ids.json     # Ability ID -> name lookup, loaded at import time by functions.py
├── requirements.txt     # Python dependencies (no pinned versions)
├── Dockerfile           # Container build; copies only the active-path files; CMD runs discord_bot.py
├── fly.toml              # Fly.io deploy/scheduling config: shell loop restarts discord_bot.py every 24h
├── .dockerignore
├── .gitignore            # Ignores env.py, test.py, .env, *.md, LICENSE, fly.toml, bot.py (dev/secret files)
├── LICENSE
├── text.out              # Sample/scratch output dump from format_match_data() (not code, not consumed)
├── __pycache__/          # Compiled bytecode cache (generated, not committed logic)
└── .planning/
    └── codebase/          # GSD-generated codebase maps (this document and its siblings)
```

There are no subdirectories for source code — every Python module lives at the repository root. There is no `src/`, `tests/`, `app/`, or package (`__init__.py`) structure; this is a flat script collection, not an installable Python package.

## Directory Purposes

**Repository root (`/`):**
- Purpose: Holds all application code, all config, and all deployment manifests together — there is no nested organization
- Contains: Python modules, one JSON data file, one Dockerfile, one Fly.io TOML config, license/gitignore/dockerignore files
- Key files: `discord_bot.py` (entry point), `functions.py` (logic), `constants.py` (data), `Dockerfile` + `fly.toml` (deployment)

**`__pycache__/`:**
- Purpose: Python bytecode cache, generated automatically by the interpreter
- Generated: Yes
- Committed: No (excluded via `.gitignore`'s `__pycache__` entry)

**`.planning/codebase/`:**
- Purpose: GSD tool output — architecture/structure/convention/testing/concerns docs produced by `/gsd:map-codebase`
- Generated: Yes (by this mapping process)
- Committed: Depends on project convention; not part of application runtime

## Key File Locations

**Entry Points:**
- `discord_bot.py`: Active production entry point — run directly (`python discord_bot.py`) or via `Dockerfile`'s `CMD`
- `bot.py`: Legacy manual-run script (Telegram output), written in Jupyter-cell style (`# %%` cell markers); listed in `.gitignore` as a dev-only file
- `lambda_function.py`: Legacy AWS-Lambda-style script (Telegram output); copied into the Docker image by `Dockerfile` but not actually invoked (`CMD` runs `discord_bot.py`)

**Configuration:**
- `fly.toml`: Deployment target, VM sizing, and the scheduling loop (`while true; do python discord_bot.py; sleep 86400; done`)
- `Dockerfile`: Build steps and the list of files shipped into the image
- `.env` (not committed, referenced by `python-dotenv`'s `load_dotenv()` in `discord_bot.py`, `functions.py`, `bot.py`): Expected to define `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `STRATZ_API_TOKEN`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `SUPABASE_URL`/`SUPABASE_KEY` for the unused `database.py`

**Core Logic:**
- `functions.py`: All external API calls (OpenDota SQL explorer, Stratz GraphQL, OpenAI chat completion), all match-filtering logic (kill density, leaver check, rank/"Guardian" check), and all text-formatting logic (`format_match_data`, `format_player_summary`, `create_heroes_string`)
- `constants.py`: Hero/item/rank ID-to-name dictionaries used purely for rendering
- `ability_ids.json`: Ability ID-to-name dictionary, loaded once at `functions.py` import time into the module-level `ability_ids` dict

**Testing:**
- None present. No `tests/` directory, no `test_*.py` files, no test runner config (no `pytest.ini`, `tox.ini`, or test dependencies in `requirements.txt`). `test.py` is referenced in `.gitignore` (implying a local, never-committed test/scratch file) but does not exist in the working tree.

## Naming Conventions

**Files:**
- Lowercase with underscores, matching their primary export/purpose (`discord_bot.py`, `lambda_function.py`, `ability_ids.json`)
- No suffix convention for tests, types, or interfaces (none of these categories exist in the repo)

**Directories:**
- None — the project intentionally has no subdirectory structure for source code

**Functions:**
- `snake_case` throughout (`get_llm_summary`, `check_for_guardian`, `ret_kill_density_nostratz`)
- Verb-first for actions (`query_stratz`, `create_match_embed`, `send_message`), `ret_`-prefixed for pure calculation helpers (`ret_kill_density`, `ret_kill_density_nostratz`)
- `_nostratz` suffix used as a naming convention to distinguish the OpenDota-only variant of a function from its Stratz-based counterpart (`get_match_data_nostratz` vs implicit Stratz equivalent, `ret_kill_density_nostratz` vs `ret_kill_density`)

**Constants/Dictionaries:**
- `UPPER_SNAKE_CASE` for module-level constant dicts and config values (`HERO_ID_TO_NAME`, `ITEM_MAP`, `RANK_MAP`, `STRATZ_QUERY`, `TG_URL`, `OPENDOTA_URL`)
- Alias pattern at the bottom of `constants.py` (`HEROES = HERO_ID_TO_NAME`, `ITEMS = ITEM_MAP`) to provide shorter import names without renaming the canonical dict

**Environment variables:**
- `UPPER_SNAKE_CASE`, read via `os.getenv(...)` at module import time (`DISCORD_BOT_TOKEN`, `STRATZ_API_TOKEN`, `SUPABASE_URL`)

## Where to Add New Code

**New data source / API integration:**
- Add a fetch function to `functions.py` following the existing pattern: define the base URL as a module-level constant near the top (alongside `OPENDOTA_URL`, `STRATZ_GRAPHQL_URL`), implement a function with an internal retry loop, and return parsed JSON
- Prefer `aiohttp` (async) over `requests`/`urllib` (sync) for anything called from `discord_bot.py`'s async flow, to avoid blocking the event loop (see ARCHITECTURE.md Anti-Patterns)

**New filter/qualification rule (e.g., a new "should we report this match" condition):**
- Add a small predicate function to `functions.py` near `check_for_guardian()` and `ret_kill_density_nostratz()`, then call it from the per-match loop in `send_herald_report()` in `discord_bot.py` (around `discord_bot.py:224-285`)

**New Discord output format (embed, thread structure, etc.):**
- Add a `create_*_embed()` function in `discord_bot.py` near `create_match_embed()`/`create_player_embed()`, following the existing `discord.Embed(...)` + `add_field(...)` pattern

**New lookup table (e.g., a new Dota 2 ID-to-name mapping):**
- Add the dict to `constants.py` using `UPPER_SNAKE_CASE`, and add a short alias at the bottom if it will be imported frequently (matching the `HEROES`/`ITEMS` pattern)

**Persistence (if reviving `database.py`):**
- `database.py` already defines `insert_row(table_name, data)` against Supabase; wire it into `send_herald_report()` in `discord_bot.py` if match history needs to be stored — currently no caller exists anywhere

**Tests (none exist yet):**
- No established pattern to follow. If introducing tests, a `tests/` directory with `pytest` (not currently a dependency — would need adding to `requirements.txt`) would be a reasonable default given the rest of the stack is plain Python with no test framework opinion already set.

## Special Directories

**`__pycache__/`:**
- Purpose: Python interpreter bytecode cache
- Generated: Yes
- Committed: No

**`.planning/`:**
- Purpose: GSD workflow state and generated documentation (this file and siblings)
- Generated: Yes (by GSD tooling)
- Committed: Project-dependent

---

*Structure analysis: 2026-07-01*
