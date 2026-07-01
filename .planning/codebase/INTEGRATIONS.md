# External Integrations

**Analysis Date:** 2026-07-01

## APIs & External Services

**Dota 2 Match Data:**
- OpenDota API (`https://api.opendota.com/api/`, `functions.py:96` `OPENDOTA_URL`) - Queries the public Explorer SQL endpoint (`explorer?sql=`) for recent public matches filtered by rank tier and duration
  - Client: raw HTTP via `aiohttp` (async, chunked/concurrent — `functions.py:222-298` `query()`) and `urllib.request` (sync, single-match lookup — `functions.py:301-312` `get_match_data_nostratz()`)
  - Auth: none (public endpoint); a spoofed browser `User-Agent` header is sent (`functions.py:97-106` `QUERY_HEADER`)
  - Retry: infinite retry loop with 60-second backoff on any request failure (both async and sync paths)
- Stratz GraphQL API (`https://api.stratz.com/graphql`, `functions.py:95` `STRATZ_GRAPHQL_URL`) - Fetches detailed per-match player stats (KDA, items, ability casts, wards, kill/death events, purchase history, skill order)
  - Client: `requests.post` with a hardcoded GraphQL query string (`STRATZ_QUERY`, `functions.py:107-192`) and a secondary lighter query (`STRATZ_INFO`, `functions.py:194-219`)
  - Auth: `Authorization: Bearer {STRATZ_API_TOKEN}` header (env var `STRATZ_API_TOKEN`)
  - Retry: infinite retry loop with 1-second sleep on exception (`functions.py:366-413`, `query_stratz()` and `stratz_info()`)
  - Called twice per match (`query_stratz` and `stratz_info`) with overlapping but distinct GraphQL selections

**LLM / AI:**
- OpenAI API - Generates a stylized "commentator" summary of match highlights
  - Client: `openai.AsyncOpenAI` (`functions.py:885-895`, `get_llm_summary()`)
  - Model: `gpt-4.1-mini` (`functions.py:893`) — recently downgraded from `o3` per commit `8ce1ca5` ("Swap LLM summary model o3 -> gpt-4.1-mini (cheaper)")
  - Auth: `OPENAI_API_KEY` env var, passed directly to the client constructor
  - No streaming, no retries; a bare `except Exception` returns an error string in place of the summary (`functions.py:903-906`)

## Data Storage

**Databases:**
- Supabase (Postgres) - Client is defined in `database.py` (`create_client(SUPABASE_URL, SUPABASE_KEY)`) with a single helper `insert_row(table_name, data)` (`database.py:21-50`)
  - **Not currently wired into any active code path** — `database.py` is not imported by `discord_bot.py`, `functions.py`, `bot.py`, or `lambda_function.py` (verified via repo-wide grep). This appears to be planned/abandoned persistence that is not yet used.
  - Connection: `SUPABASE_URL`, `SUPABASE_KEY` env vars (only logged as a warning if missing, not a hard failure)
  - Client library: `supabase` Python package — **imported but absent from `requirements.txt`**, so a clean `pip install -r requirements.txt` will not make this module importable

**File Storage:**
- Local filesystem only. `ability_ids.json` (126KB, ~2,981 entries) is read at import time in `functions.py:46-51` to map ability IDs to names, with a graceful fallback (empty dict + warning) if the file is missing.
- `constants.py` contains large static in-memory maps (`HERO_ID_TO_NAME`, `HEROES`, `ITEMS`, `ITEM_MAP`, `RANK_MAP`, 653 lines) — no external data source, hardcoded Dota 2 reference data.

**Caching:**
- None. No Redis, in-memory TTL cache, or similar; every run re-fetches all match data from OpenDota/Stratz.

## Authentication & Identity

**Auth Provider:**
- None (custom, per-integration API tokens only). There is no user-facing authentication — this is a backend scraper/bot with no login system.
- Discord bot authenticates to the Discord Gateway via `DISCORD_BOT_TOKEN` (bot token, not OAuth user flow) — `discord_bot.py:27,318`.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, Rollbar, or similar error-tracking SDK. Errors are caught with broad `except Exception` blocks and logged via the standard `logging` module, then execution continues to the next match (`discord_bot.py:283-285`, `functions.py` various retry loops).

**Logs:**
- Python standard `logging` module, configured with `logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")` in both `discord_bot.py:16-19` and `lambda_function.py:11-14`
- No structured logging, no external log shipping (e.g., no Datadog/Papertrail integration) — logs go to stdout/stderr, presumably captured by Fly.io's platform logging

## CI/CD & Deployment

**Hosting:**
- Fly.io (`fly.toml`), app name `herald-scraper-bot`, primary region `sea`, single shared-CPU VM with 1GB RAM
- Deployment is container-based via the repo's `Dockerfile` (built by Fly's `[build]` stanza with no custom builder specified)
- Scheduling is self-managed inside the container: the `scheduler` process runs `discord_bot.py` once, then `sleep 86400` (24 hours), in an infinite shell loop (`fly.toml:18-19`) — there is no external cron, GitHub Actions schedule, or Fly Machines scheduled-run configuration

**CI Pipeline:**
- None detected. No `.github/workflows/`, `.gitlab-ci.yml`, or other CI config files exist in the repository. Deployment appears to be manual (`flyctl deploy` presumably run by hand).

## Environment Configuration

**Required env vars:**
- `DISCORD_BOT_TOKEN` - Discord bot token (hard-required, `discord_bot.py:32-33`)
- `DISCORD_CHANNEL_ID` - Target channel ID for posting reports (hard-required, `discord_bot.py:35-36`)
- `STRATZ_API_TOKEN` - Stratz GraphQL bearer token (hard-required, `functions.py:22-24`)
- `OPENAI_API_KEY` - OpenAI API key (hard-required, `functions.py:26-28`)
- `TELEGRAM_BOT_TOKEN` - Telegram bot token (hard-required by `functions.py:30-32` validation, even though the active Discord flow never sends Telegram messages — legacy coupling)
- `TELEGRAM_CHAT_ID` - Telegram chat ID (hard-required by `functions.py:34-36`, same legacy coupling)
- `SUPABASE_URL`, `SUPABASE_KEY` - Soft-required (warning only) for the unused `database.py` module

**Secrets location:**
- Local development: `.env` file (gitignored, not committed — `.gitignore:4`)
- Production: presumably Fly.io secrets (`flyctl secrets set ...`), referenced in `fly.toml:9` comment ("Add your environment variables here or set them via flyctl secrets") but not actually populated in the checked-in `fly.toml`
- **Security note:** `functions.py:94` contains a hardcoded Telegram Bot API URL with an embedded bot token literal (`TG_URL = "https://api.telegram.org/bot<TOKEN>/sendMessage"`), and `functions.py:345` hardcodes a Telegram `chat_id` literal inside `send_message()`. These are committed to source control in plaintext — a credential leak risk if the token is still live. `send_message()` is only called from the legacy `bot.py` and `lambda_function.py` paths, not from the active `discord_bot.py` flow.

## Webhooks & Callbacks

**Incoming:**
- None. The bot does not expose any HTTP server, webhook receiver, or slash-command listener — it is a one-shot batch job triggered by process start, not an event-driven service.

**Outgoing:**
- Discord: outbound REST calls via `discord.py` to post embeds/messages/threads into a configured channel (`discord_bot.py:267-276`) and to manage thread lifecycle/cleanup (`discord_bot.py:39-92`, deletes threads older than 10 days that were created by the bot itself, filtered by `thread.owner_id == bot.user.id`)
- Telegram: outbound `POST` to the Telegram Bot API `sendMessage` endpoint (`functions.py:340-363`, `send_message()`) — used only by the legacy `bot.py`/`lambda_function.py` entry points, not the active Discord flow

---

*Integration audit: 2026-07-01*
