# Runbook

## Local setup and offline checks

From the repository root:

```sh
uv sync --frozen
cp .env.example .env
uv run pytest -q
uv run python -m herald.ingest --selfcheck
uv run python -m herald.ingest --skillcheck
uv run python -m herald.ingest --signalcheck
```

The application does not implicitly load `.env`. Use `uv run --env-file .env` for live commands, or supply environment variables through your process manager. The template contains variable names only, without real keys. Do not copy another operator's `.omo/` files or runtime data into a collaborator checkout.

For air-gapped validation with a warm dependency cache, `uv sync --offline --frozen` and `uv run --offline --frozen pytest -q` perform no downloads.

## Scheduled reports

Required: `DISCORD_BOT_TOKEN`, `STRATZ_API_TOKEN`, `DISCORD_CHANNEL_ID`. Optional path: `HERALD_REPORT_DB` (default `herald-reports.db`). This command **writes to Discord**:

```sh
uv run --env-file .env python -m herald scheduled
```

Default window: one day 3–4 days ago, fixed legacy filters. `--loop` repeats after 24 hours; `--backfill 7` explicitly scans the latest seven days once. Backfills and daily runs share the same receipt DB to deduplicate overlapping matches. Preserve it across restarts and code changes. Each distinct destination needs a separate ledger. Do not schedule another reporter with a different ledger for the same channel/window: the local lock only protects one ledger path.

The bot needs to view the target guild text channel, send messages, embed links, create public threads, send messages in threads and read message history. The command validates that the destination is a guild text channel, uses current application hero emojis, and falls back to names where an icon is absent. Emoji provisioning is outside this command.

Delivery state is in the `deliveries` table's JSON `data`: immutable intended payload, `parent`, `thread`, `radiant`, `dire`, optional `inflight`, `verified`, and `deleted`. A verified report was fetched back successfully at delivery time; that is not a perpetual health claim.

If a pass stops:

1. Preserve the ledger and its `.lock` file. Stop any second writer before investigation.
2. Correct API availability, credentials or permissions without putting values in logs. Definite rejected requests may retry normally.
3. Re-run the same command. Incomplete threads resume before new discovery. Confirmed stages are reused; a remotely accepted write whose acknowledgement was interrupted is reconciled by its nonce/payload or parent thread reference.
4. An **unresolved** pending write requires checking the corresponding channel/thread history before retrying. The code searches at most 1,000 messages; it deliberately does not clear an ambiguous marker automatically. An operator can back up the ledger and repair the affected JSON row only after confirming the actual Discord IDs or confirming that no write occurred. Do not delete the whole ledger to make an error disappear.
5. A deleted report message is marked `deleted` and is not recreated. If someone deliberately removed a post, leave it removed.

Ctrl-C and process termination preserve already committed checkpoints. Daily mode logs failures and retries the same saved window after its fixed interval. `pending_window` pins its original clock and backfill scope until the pass succeeds, so midnight or restart cannot silently advance past an incomplete day. A pending window takes precedence over a newly requested backfill; after it completes, invoke the new backfill command again. A restart resumes the pinned window and incomplete reports, but the fixed delayed-day query does not automatically backfill every day missed during a long outage; use an explicit backfill after recovery.

## Experimental menu

Required: `DISCORD_BOT_TOKEN` for the menu and `STRATZ_API_TOKEN` for ingestion. `HERALD_DB` must point to the same file for both. The menu needs Discord application-command authorization, view-channel and attachment/embed permissions. It copies `/heralds` into connected guilds on readiness; command synchronization occurs only when started online.

```sh
uv run --env-file .env python -m herald.ingest --init-db
uv run --env-file .env python -m herald ingest --loop 1800
# Another terminal:
uv run --env-file .env python -m herald menu
```

For one container/process manager, use `python -m herald.menu_service`. It initializes the schema, starts both children and terminates the sibling if one exits. This replaces the old unmonitored background-ingest shell command.

An empty archive is valid and renders “No matches yet.” An absent/unavailable schema yields a private retry message. Ingest adds a three-minute delay before enrichment; a new install may therefore need a later cycle before any matches are available. Lack of matches is not automatically a bot failure.

Existing ingest tuning variables remain: `DUR_MIN=3600`, `KPM_MIN=1.0`, `RETENTION_DAYS=14`, `MAX_PAGES=400`, `STRATZ_DAILY_BUDGET=10000`, `STRATZ_BATCH=25`, `SWING_MIN=3000`. These affect the experimental corpus only. The scheduled reporter's eligibility and cadence are fixed in code.

`--recompute` and `--weirdness` are offline maintenance commands **that write the selected database**. `--backfill DAYS` on `herald.ingest` only queues discovery; later ingestion enriches it. This is different from the reporter's `--backfill DAYS`, which discovers, verifies and posts reports.

## Data and deployment

Use SQLite's backup API or `.backup` command for consistent snapshots. Copying only a live `.db` file can omit committed WAL data. Keep menu data and report receipts separate. Losing menu data costs a scrape; losing report receipts can duplicate deliveries.

The Docker image runs as UID/GID 1000. Its default data paths are under `/data`. A mounted volume must be writable by that user, including existing `.db`, `-wal` and `-shm` files. The former board image ran as root: **existing Fly volumes require an explicit ownership check/migration before rollout**. Set ownership on the dedicated Herald volume during a maintenance window while its writers are stopped; do not run a recursive ownership change on a shared volume. This repository task did not alter any volume.

For a fresh local named volume, provision it before starting the non-root container:

```sh
docker volume create herald_reports
docker run --rm --user 0 -v herald_reports:/data herald:local chown 1000:1000 /data
# Once secrets and the intended destination are configured:
docker run --rm --env-file .env -e HERALD_REPORT_DB=/data/herald-reports.db -v herald_reports:/data herald:local python -m herald scheduled
```

The explicit `-e` keeps receipt storage on the volume even if `.env` contains a relative local path. For menu containers, likewise set `-e HERALD_DB=/data/herald.db`.

Build `herald:local` with `docker build -t herald:local .` first. Docker/Fly builds and actual online behavior were not exercised during the offline handoff.

Fly templates are `fly.toml` (reports, `herald_reports` volume) and `fly.board.toml` (menu service, `herald_data` volume). The menu's writer and reader must share one mounted SQLite volume on one machine; copying a volume across machines does not produce a shared database. Starting machines, setting secrets and deploying are separate explicit operations. The last supplied state was suspended apps with no machines; no health claim is made here.
