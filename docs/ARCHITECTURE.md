# Architecture

Herald has a small stable reporter and an experimental menu. Both use Python 3.12+, OpenDota, Stratz and Discord. Neither needs an LLM key.

## Stable scheduled reports

`herald.scheduled` owns fixed selection, scheduling, payloads and durable delivery receipts. Its default reproduces the legacy `query(days_back=3, day_period=1)` window: the single day from **four days ago to three days ago**, ending exclusively at the upper bound. `--loop` waits 24 hours after each pass. `--backfill 7` is an explicit recent seven-day one-shot and cannot be combined with `--loop`.

1. Walk OpenDota Explorer in descending match-ID pages, restricting average rank to ≤16. Duration >4,500 seconds and the selected time window are checked locally. There is no lobby or KPM restriction.
2. Fetch Stratz detail in groups of 25 using a minimal report field selection and shared retry helper. Require ten players, five per team, present player accounts and no `seasonRank >15`; an account with unknown season rank remains acceptable, matching the legacy path.
3. Read OpenDota match detail and require exactly ten players with literal `leaver_status == 0`. Missing evidence is rejected.
4. Build the match card and two five-player team cards. Resolve application hero emojis from Discord's current application inventory, with readable hero names as fallback. No summary, LLM request, header post or emoji creation.
5. Persist the intended payload, parent message ID, thread ID and each team-card ID in the reporter's own SQLite ledger. Each completed message is fetched back and compared before the delivery is marked verified.

Shared `herald.api` handles API transport only; reporter selection and its minimal field set stay here. The fixed 400-page discovery bound fails visibly instead of claiming a complete scrape. A pass permits at most 500 Stratz batches of 25; up to three HTTP attempts per batch. Menu environment overrides do not affect these bounds. These are per-run safeguards, not guarantees about account-wide quota. Calls are paced; daily mode pins the pending window in SQLite and retries that same window after failure until it succeeds. The published match's selection is independent of the experimental menu database.

A local OS lock prevents two reporter processes from sharing one receipt ledger concurrently. A process interrupted after a write may reconcile the actual message/thread on restart. Recovery searches up to 1,000 recent messages; unresolved ambiguous writes stop rather than resend blindly. Definite API rejection clears the pending-write marker so a fixed permission/rate-limit problem can be retried. Deleted report messages are not recreated. There is no transactional exactly-once guarantee across SQLite and Discord; the conservative recovery boundary is deliberate.

## Experimental menu

`herald.ingest` writes `herald.db`; `herald.board` reads it through fresh read-only SQLite connections in worker threads. Discord views are always constructed on the event loop. On readiness the menu reads the current application emoji inventory, replacing historical prototype IDs; new bots or failed inventory reads use text fallbacks without provisioning emojis. `herald.menu_service` supervises both in one container, initializes the schema offline, and stops the service if either child exits.

The existing corpus differs from scheduled reports:

| Stage | Current menu rule |
| --- | --- |
| Explorer discovery | Average rank 10–15 in SQL; ranked lobby 7 and duration ≥3,600 seconds applied client-side; 100-row pages. |
| Stratz acceptance | Reject any known rank >15; leaver statuses `None`, `NONE`, `DISCONNECTED` accepted; parsed lead series required. |
| Duration and KPM | ≥3,600 seconds and ≥1.0 KPM by default. Existing ingest overrides remain supported. |
| Retention | 14 days by default. |

`matches` stores raw detail plus derived columns; `match_players` supports hero/item filters; `pending` tracks candidates; `stratz_calls` records the ingest's daily logical-batch budget (HTTP retries are not separately counted). Ingest owns migrations, pruning, WAL checkpoints and scoring. `match_view` is the canonical display transformation, including for fixture-based prototypes.

The menu offers general sorts, filters, multi-sort, advanced hero/item search, and focused details. Item PMI and ability-order surprisal remain experimental corpus-relative signals. Unusual-build/skill filters use a positive score and the current 95th percentile. Corpus counts and watchability normalization refresh on interaction. Empty/singleton corpora, pruned matches and empty filtered dice rolls remain usable. Optional receipts shorten to stay within Discord's text budget. Spoiler mode suppresses the winner label, outcome tags and focus graph; it is not a guarantee that all statistics conceal the outcome.

## Code boundaries

| Location | Responsibility |
| --- | --- |
| `herald/scheduled.py` | Fixed-rule discovery and resumable Discord report delivery. |
| `herald/ingest.py` | Experimental corpus ingestion, SQLite schema, scoring and offline self-checks. |
| `herald/board.py` | `/heralds` private interactive menu. |
| `herald/api.py`, `render.py`, `assets/` | Shared transport and hero/item presentation; no menu eligibility in reporter imports. |
| `herald/charts.py` | Menu focus graphs. |
| `herald/assets/`, `fixtures/` | Packaged public lookup data and retained offline fixture. |
| `spikes/` | Signal research, original menu alternatives, compatibility wrappers. |
| `spikes/daimon/` | Separate unfinished Postgres/agent experiment, with its own dependencies. |

The historical `scripts/ingest.py` and `spikes/menu-v2/live_board.py` commands forward to maintained code. Historical asset and fixture paths are relative symlinks to the packaged data. Unix/Linux is the supported operational environment (file locking and these compatibility links assume it).

## Deployment boundary

Root Dockerfile builds the actual product. Its default prints help; a mode must be selected explicitly. `fly.toml` is the scheduled-reporter template; `fly.board.toml` co-locates experimental ingest and menu on one SQLite volume. They use different data files/volumes and can use separate bot credentials. The root container entrypoint prepares fresh volumes, then runs commands as UID/GID 1000. No Postgres or agent service is required. The archived scaffold's deploy configuration stays under `spikes/daimon/`.

Operational status supplied on 2026-10-04: Fly apps suspended, no machines. This handoff did not query live health, deploy, provision volumes or start either mode.

## Maintenance and recovery

Run `uv run pytest -q` before changes ship. Fixture checks also run offline:

```sh
uv run python -m herald.ingest --selfcheck
uv run python -m herald.ingest --skillcheck
uv run python -m herald.ingest --signalcheck
```

With a warm dependency cache, use `uv sync --offline --frozen` and `uv run --offline --frozen pytest -q` for air-gapped checks. Imports require no credentials and must never call external services. The old ingest CLI and menu import wrappers remain for compatibility, but new work imports `herald` directly. Python 3.12 is pinned; do not upgrade it independently of dependencies/tests.

### Reporter recovery

Keep `HERALD_REPORT_DB` across restarts and backfills; each distinct destination needs its own ledger. A second independent ledger for the same channel can duplicate posts. The OS lock protects one ledger on one host only.

The `deliveries.data` JSON stores the immutable `spec`, destination `channel`, message IDs `parent`, `radiant`, `dire`, `thread`, and optional `inflight`, `verified`, `verified_at`, `deleted`. `pending_window.data` pins `now` and `backfill` until success.

1. Preserve the ledger; stop any second writer. Fix credentials, channel permissions or provider availability without logging keys.
2. Re-run the same command: incomplete threads resume first, then discovery retries the saved window. Confirmed messages are reused and fetched back. Definite rejected writes can retry normally.
3. An unresolved `inflight` stage stops recovery after at most 1,000 recent messages. Inspect the actual channel/thread history. Back up the ledger, then repair only the affected JSON row with confirmed Discord IDs, or clear that stage only after confirming no write occurred. Never delete the whole ledger to bypass the error.
4. Deleted report messages stay deleted. `verified` means fetched back at delivery time, not continuous health.

`--loop` retries failed saved windows after 24 hours. A pending window takes precedence over a newly requested backfill: once it completes, invoke the backfill again. After a long outage, explicitly use `scheduled --backfill DAYS` to cover missed days; delayed daily mode does not automatically fill an outage. Discovery pagination is not checkpointed. There is no cross-system exactly-once transaction; ambiguous writes require human reconciliation.

### Menu maintenance

Ingest owns schema migrations, pruning, scoring and WAL checkpoints; the reader never writes SQLite. Empty archives show “No matches yet”; an unavailable schema returns a private retry message. New candidates wait three minutes before enrichment, and some provider matches lack parsed lead series; no matches does not by itself indicate bot failure.

`python -m herald.menu_service` initializes the schema, starts ingest with `--loop 1800` and the menu reader, and terminates the sibling if either child exits. Ingest itself logs cycle failures and continues, so a running supervisor alone is not evidence of fresh data. Inspect ingest logs and archive timestamps. `python -m herald ingest --loop 1800` plus `python -m herald menu` in separate terminals is the manual equivalent. Bare ingest `--loop` uses 180 seconds, not the supervisor's interval.

Offline commands below **write the selected menu DB**; stop ingest and back up first:

```sh
uv run --env-file .env python -m herald ingest --recompute
uv run --env-file .env python -m herald ingest --weirdness
```

Menu `ingest --backfill DAYS` only queues discovery; later cycles enrich it. Reporter `scheduled --backfill DAYS` discovers, verifies and posts. The menu's 400-page default can yield partial coverage, and its fully-known-page frontier can miss rare out-of-order matches. Scores depend on the changing corpus; unusual-build/skill filters use positive scores and its 95th percentile, not validated match-quality judgments. Spoiler mode suppresses winner labels/outcome tags/focus graph but cannot guarantee every statistic conceals the result.

### Backups and containers

Use SQLite's backup API for a consistent snapshot, including committed WAL data. Stop writers before restoring; copy the backup to the configured DB path and preserve ownership. Losing menu data costs a scrape; losing reporter receipts risks duplicate delivery. Example (backup path must be private and outside Git):

```sh
uv run --env-file .env python - <<'PY'
import os, sqlite3
from pathlib import Path
source = Path(os.environ.get('HERALD_REPORT_DB', 'herald-reports.db')).resolve()
# For the menu, use HERALD_DB/default herald.db instead.
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db:
    with sqlite3.connect('/absolute/private/path/herald-backup.db') as backup:
        db.backup(backup)
PY
```

The Docker entrypoint starts as root only to own `/data`, then drops groups/GID/UID to 1000 before executing the product. It does not change database ownership. Fresh volumes need no manual permission command. Existing volumes from the former root-run image require an ownership migration while writers are stopped: change only the dedicated mount and the configured Herald DB, `-wal`, `-shm` and reporter `.lock` files to `1000:1000`, using a root maintenance shell. Do not recursively chown a shared volume. Back up before maintenance; inspect permissions before restarting. Restore from a volume snapshot if no shell can be started on the old machine.

Local container setup (install Docker first; online commands send/connect):

```sh
docker build -t herald:local .
docker volume create herald_reports
docker run --rm --env-file .env -e HERALD_REPORT_DB=/data/herald-reports.db -v herald_reports:/data herald:local python -m herald scheduled
# Optional experimental menu, separate volume:
docker volume create herald_data
docker run --rm --env-file .env -e HERALD_DB=/data/herald.db -v herald_data:/data herald:local python -m herald.menu_service
```

Explicit path overrides keep DBs on volumes even if `.env` contains local relative paths. Docker/Fly execution and live delivery were not exercised during this refactor. Before an authorized rollout, use a designated test channel, verify real thread receipts and `/heralds`, and inspect existing volume ownership. No push, deployment, credential rotation or emoji provisioning was performed.
