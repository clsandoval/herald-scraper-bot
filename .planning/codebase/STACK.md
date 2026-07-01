# Technology Stack

**Analysis Date:** 2026-07-01

## Languages

**Primary:**
- Python 3.11 - All application code (`bot.py`, `discord_bot.py`, `functions.py`, `constants.py`, `database.py`, `lambda_function.py`)
  - Dockerfile pins `python:3.11-slim` (`Dockerfile:1`)
  - Local dev interpreter observed as Python 3.10.12 (host `python3 --version`); no `.python-version` or `pyproject.toml` pins a version for local dev

**Secondary:**
- None. No JS/TS, shell scripting is limited to the Dockerfile and `fly.toml` process command.

## Runtime

**Environment:**
- Python 3.11 (containerized), CPython
- Runs as a long-lived process on Fly.io that loops once per day (see `fly.toml:18`), not a typical request/response server

**Package Manager:**
- pip (`requirements.txt`)
- Lockfile: missing — `requirements.txt` has no pinned versions (unpinned dependency list), no `requirements-lock.txt`, `Pipfile.lock`, or `poetry.lock`

## Frameworks

**Core:**
- `discord.py` - Discord bot framework; primary runtime entry point (`discord_bot.py`)
- `pyTelegramBotAPI` (imported as `telebot`) - Telegram bot framework; used only in the legacy/alternate entry point `lambda_function.py`, not in the active Discord flow
- `aiohttp` - Async HTTP client used for concurrent OpenDota API queries (`functions.py:10`, `query()` function)
- `requests` - Synchronous HTTP client used for Stratz GraphQL calls and legacy Telegram send in `functions.py`
- `pypika` - SQL query builder used to construct OpenDota Explorer SQL queries programmatically (`functions.py:13`, `Query`/`Table`)

**Testing:**
- None detected. No test framework (pytest, unittest) is declared in `requirements.txt`, and no test files exist in the repository (`test.py` is explicitly gitignored and not present in the working tree)

**Build/Dev:**
- Docker (`Dockerfile`) - Container build for deployment; installs `gcc` as a system dependency, creates non-root `app` user
- `python-dotenv` - Loads `.env` file into environment variables for local development (`discord_bot.py:8`, `database.py:3`, `lambda_function.py:2`)
- Fly.io CLI (`fly.toml`) - Deployment/process configuration

## Key Dependencies

**Critical:**
- `discord.py` (unpinned) - Powers the bot's connection to Discord, message/embed/thread creation, and the `on_ready` lifecycle hook that drives the entire scrape-and-post flow (`discord_bot.py:297-312`)
- `openai` (unpinned) - Generates the "Jenkins the commentator" LLM match summary using model `gpt-4.1-mini` via `AsyncOpenAI` client (`functions.py:847-906`)
- `aiohttp` (unpinned) - Enables concurrent, chunked queries against the OpenDota Explorer SQL endpoint, critical for scraping performance (`functions.py:222-298`)
- `requests` (unpinned) - Used for synchronous Stratz GraphQL POST requests (`functions.py:366-413`) and legacy Telegram sends

**Infrastructure:**
- `numpy` (unpinned) - Declared in `requirements.txt` but no usage found anywhere in the codebase (`grep` for `numpy\.` or `np\.` returns nothing beyond the import) — dead dependency
- `pypika` (unpinned) - Used solely to build the OpenDota Explorer SQL query string in `functions.py:222-254`

## Configuration

**Environment:**
- Loaded via `python-dotenv` (`load_dotenv()`) from a local `.env` file (gitignored, not present in repo — see `.gitignore:4`)
- Required variables (validated with hard failures in `functions.py:16-36` and `discord_bot.py:27-36`):
  - `STRATZ_API_TOKEN` - Stratz GraphQL API bearer token
  - `OPENAI_API_KEY` - OpenAI API key
  - `TELEGRAM_BOT_TOKEN` - Telegram bot token (required by `functions.py` validation even though the active Discord flow doesn't send Telegram messages)
  - `TELEGRAM_CHAT_ID` - Telegram chat ID (same caveat as above)
  - `DISCORD_BOT_TOKEN` - Discord bot token (`discord_bot.py:27`)
  - `DISCORD_CHANNEL_ID` - Discord channel ID to post reports into (`discord_bot.py:28-30`)
  - `SUPABASE_URL`, `SUPABASE_KEY` - Read in `database.py:11-12` but only warn (not hard-fail) if missing; this module is not imported/used by any active entry point
- No `.env.example` or `.env.sample` file exists to document the required variables for a new developer

**Build:**
- `Dockerfile` - Single-stage build, installs `gcc`, copies only the files needed for the Discord bot flow (`lambda_function.py`, `discord_bot.py`, `functions.py`, `constants.py`, `ability_ids.json`), and runs `python discord_bot.py` as its `CMD`
- `.dockerignore` - Excludes git metadata, Python caches, docs, `test.py`, `bot.py`, and notably `fly.toml` from the build context
- `fly.toml` - Defines the Fly.io app (`herald-scraper-bot`), a single shared-CPU VM with 1GB memory, and a `scheduler` process that runs `discord_bot.py` in an infinite shell loop with a 24-hour (`sleep 86400`) sleep between runs — this is the production scheduling mechanism (no cron/external scheduler)

## Platform Requirements

**Development:**
- Python 3.11 (matching Dockerfile) recommended; a local `.env` file with all required variables (see above) must be created manually — no example file is provided
- `pip install -r requirements.txt` (note: `supabase` package is imported by `database.py` but is absent from `requirements.txt` — installing from the lockfile as-is will not support that module)

**Production:**
- Fly.io (`app = 'herald-scraper-bot'`, primary region `sea`), single shared VM, 1GB RAM
- Long-running container that self-schedules via a shell `while true` loop rather than being invoked by an external cron/scheduler service
- Despite the file name `lambda_function.py`, there is no evidence of actual AWS Lambda deployment (no `serverless.yml`, SAM template, or Lambda handler wiring) — this file appears to be a legacy/alternate entry point for a Telegram-based flow, superseded by `discord_bot.py`

---

*Stack analysis: 2026-07-01*
