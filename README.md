# Herald

Find Dota 2 Herald matches worth reviewing. Two modes share API and presentation helpers:

| Mode | Entry point | Purpose |
| --- | --- | --- |
| **Scheduled reports** | `python -m herald scheduled` | The simple baseline: scrape one delayed day (3–4 days ago), apply the original fixed rules, post one match card and two team cards in its thread. No summaries. |
| **Experimental menu** | `python -m herald menu` | Open `/heralds` for a private match browser with sorts, filters, item builds and skill orders. Ingestion runs separately. |

Scheduled reports have fixed selection and timing defaults. The menu explores signals; its scores are hypotheses about interesting matches, not validated predictions of a good review.

## Start here

The checked-in `.python-version` selects Python 3.12, matching the tested environment and Docker image. Use [uv](https://docs.astral.sh/uv/) for the locked setup; the first sync may download dependencies.

```sh
uv sync --frozen
cp .env.example .env
uv run pytest -q
uv run python -m herald.ingest --selfcheck
uv run python -m herald.ingest --skillcheck
uv run python -m herald.ingest --signalcheck
```

These checks are offline. Fill the credential fields in `.env` only when ready to connect to external services. Plain `python -m herald` prints help and performs no network calls. The commands below connect to the named APIs; the scheduled command **posts to the configured Discord text channel**.

### Scheduled reports

Set `DISCORD_BOT_TOKEN`, `STRATZ_API_TOKEN`, and `DISCORD_CHANNEL_ID`.

```sh
uv run --env-file .env python -m herald scheduled        # one pass
uv run --env-file .env python -m herald scheduled --loop # repeat after 24 hours
uv run --env-file .env python -m herald scheduled --backfill 7 # explicit recent seven-day pass
```

A qualifying match has duration **strictly greater than 4,500 seconds**, OpenDota average rank **≤16**, no Stratz player above season rank **15**, and exactly ten OpenDota players whose `leaver_status` is **0**. Missing Stratz accounts or missing OpenDota leaver evidence fail closed. There is **no kills-per-minute cutoff or ranked-lobby restriction**. Kill density is displayed, not used to select matches. Repeated runs and explicit backfills are deduplicated with persistent delivery receipts in `herald-reports.db`.

### Experimental `/heralds` menu

Set `DISCORD_BOT_TOKEN` and `STRATZ_API_TOKEN`; use the same `HERALD_DB` for both processes.

```sh
uv run --env-file .env python -m herald.ingest --init-db  # offline schema setup
uv run --env-file .env python -m herald ingest --loop 1800
# In another terminal:
uv run --env-file .env python -m herald menu
```

`python -m herald.menu_service` supervises both processes for a single-container deployment. The menu reads SQLite without writing and responds privately when `/heralds` is invoked. Its corpus currently uses stricter historical defaults: rank 10–15, ranked lobby, ≥60 minutes, ≥1 KPM, 14-day retention. **That corpus is not the scheduled reporter's candidate source.**

## Repository map

- `herald/`: maintained application code, shared lookup assets and offline fixtures.
- `tests/`: offline behavior and incident regressions.
- `scripts/ingest.py`, `spikes/menu-v2/{live_board,render,charts}.py`: compatibility shims for old commands/imports.
- `spikes/`: retained signal experiments and design comparisons; [index](spikes/README.md).
- `experiments/daimon/`: separate, unfinished Postgres/agent scaffold; [status](experiments/daimon/README.md).
- `.planning/`: historical decisions and quick-task records. Earlier pull-only plans are superseded by the two-mode direction above.
- `docs/`: [architecture](docs/ARCHITECTURE.md), [runbook](docs/RUNBOOK.md), [collaborator handoff](docs/HANDOFF.md), and historical snapshots.

The last supplied operational status on 2026-10-04 was that the Fly apps were suspended with no machines. This branch has only offline validation; configuration files are not evidence of running services. No deployment or live service health check was performed during this handoff.
