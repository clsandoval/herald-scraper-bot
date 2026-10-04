# Architecture

Herald has a small stable reporter and an experimental menu. Both use Python 3.12+, OpenDota, Stratz and Discord. Neither needs an LLM key.

## Stable scheduled reports

`herald.scheduled` owns fixed selection, scheduling, payloads and durable delivery receipts. Its default reproduces the legacy `query(days_back=3, day_period=1)` window: the single day from **four days ago to three days ago**, ending exclusively at the upper bound. `--loop` waits 24 hours after each pass. `--backfill 7` is an explicit recent seven-day one-shot and cannot be combined with `--loop`.

1. Walk OpenDota Explorer in descending match-ID pages, restricting average rank to ≤16. Duration >4,500 seconds and the selected time window are checked locally. There is no lobby or KPM restriction.
2. Fetch Stratz detail in groups of 25 using a minimal report field selection and shared retry helper. Require ten players, five per team, present player accounts and no `seasonRank >15`; an account with unknown season rank remains acceptable, matching the legacy path.
3. Read OpenDota match detail and require exactly ten players with literal `leaver_status == 0`. Missing evidence is rejected.
4. Build the match card and two five-player team cards. Resolve application hero emojis from Discord's current application inventory, with readable hero names as fallback. No summary, LLM request, header post or emoji creation.
5. Persist the intended payload, parent message ID, thread ID and each team-card ID in the reporter's own SQLite ledger. Each completed message is fetched back and compared before the delivery is marked verified.

The fixed 400-page discovery bound fails visibly instead of claiming a complete scrape. A pass permits at most 500 Stratz batches. These are per-run safeguards, not guarantees about account-wide quota. Calls are paced; daily mode pins the pending window in SQLite and retries that same window after failure until it succeeds. The published match's selection is independent of the experimental menu database.

A local OS lock prevents two reporter processes from sharing one receipt ledger concurrently. A process interrupted after a write may reconcile the actual message/thread on restart. Recovery searches up to 1,000 recent messages; unresolved ambiguous writes stop rather than resend blindly. Definite API rejection clears the pending-write marker so a fixed permission/rate-limit problem can be retried. Deleted report messages are not recreated. There is no transactional exactly-once guarantee across SQLite and Discord; the conservative recovery boundary is deliberate.

## Experimental menu

`herald.ingest` writes `herald.db`; `herald.board` reads it through fresh read-only SQLite connections in worker threads. Discord views are always constructed on the event loop. `herald.menu_service` supervises both in one container, initializes the schema offline, and stops the service if either child exits.

The existing corpus differs from scheduled reports:

| Stage | Current menu rule |
| --- | --- |
| Explorer discovery | Average rank 10–15 in SQL; ranked lobby 7 and duration ≥3,600 seconds applied client-side; 100-row pages. |
| Stratz acceptance | Reject any known rank >15; leaver statuses `None`, `NONE`, `DISCONNECTED` accepted; parsed lead series required. |
| Duration and KPM | ≥3,600 seconds and ≥1.0 KPM by default. Existing ingest overrides remain supported. |
| Retention | 14 days by default. |

`matches` stores raw detail plus derived columns; `match_players` supports hero/item filters; `pending` tracks candidates; `stratz_calls` records the ingest's daily request budget. Ingest owns migrations, pruning, WAL checkpoints and scoring. `match_view` is the canonical display transformation, including for fixture-based prototypes.

The menu offers general sorts, filters, multi-sort, advanced hero/item search, and focused details. Item PMI and ability-order surprisal remain experimental corpus-relative signals. Unusual-build/skill filters use a positive score and the current 95th percentile. Corpus counts and watchability normalization refresh on interaction. Empty/singleton corpora, pruned matches and empty filtered dice rolls remain usable. Optional receipts shorten to stay within Discord's text budget. Spoiler mode suppresses the winner label, outcome tags and focus graph; it is not a guarantee that all statistics conceal the outcome.

## Code boundaries

| Location | Responsibility |
| --- | --- |
| `herald/scheduled.py` | Fixed-rule discovery and resumable Discord report delivery. |
| `herald/ingest.py` | Experimental corpus ingestion, SQLite schema, scoring and offline self-checks. |
| `herald/board.py` | `/heralds` private interactive menu. |
| `herald/render.py`, `charts.py` | Shared lookups/receipts and charts. |
| `herald/assets/`, `fixtures/` | Packaged public lookup data and retained offline fixture. |
| `spikes/` | Signal research, original menu alternatives, compatibility wrappers. |
| `experiments/daimon/` | Separate unfinished Postgres/agent experiment, with its own dependencies. |

The historical `scripts/ingest.py` and `spikes/menu-v2/live_board.py` commands forward to maintained code. Historical asset and fixture paths are relative symlinks to the packaged data. Unix/Linux is the supported operational environment (file locking and these compatibility links assume it).

## Deployment boundary

Root Dockerfile builds the actual product. Its default prints help; a mode must be selected explicitly. `fly.toml` is the scheduled-reporter template; `fly.board.toml` co-locates experimental ingest and menu on one SQLite volume. They use different data files/volumes and can use separate bot credentials. No Postgres or agent service is required. The archived scaffold's deploy configuration stays under `experiments/daimon/`.

Operational status supplied on 2026-10-04: Fly apps suspended, no machines. This handoff did not query live health, deploy, provision volumes or start either mode.
