# Collaborator handoff

Start with the root README and run the offline tests. Work on a normal branch; share credentials privately through the existing operator's secret store, never through a commit or chat transcript.

## Product intent

Keep the reliable daily report boring: a fixed delayed one-day window, the original long-match/Herald/no-leaver rules, match/thread/team cards, hero icons and no LLM summary. The seven-day scrape was an explicit one-shot backfill, not the new recurring default.

The private `/heralds` menu is the place to experiment. Item builds, ability choices, gold swings, chat and feeding receipts remain useful research directions. Maintain the evidence in `spikes/` and `.planning/spikes/`; a high anomaly score is an interesting candidate, not a proven good episode.

## What this branch changes

- Promotes application code, assets and fixtures into the installable `herald` package; preserves old commands/imports with shims and data symlinks.
- Restores an opt-in scheduled reporter with legacy eligibility, fixed timing and durable, verified partial-thread receipts. It is newly restored code and has only offline tests so far.
- Repairs menu cold starts, sparse-corpus scoring, disappearing matches, page bounds, filtered random selection and prompt interaction acknowledgement. Refreshes corpus counts/thresholds, offers an unusual-skill-order filter and caps optional detail text.
- Makes root dependencies, Docker/Fly templates and environment examples describe the real product. Moves the independent unfinished daimon workspace into `experiments/daimon/`.
- Replaces stale instructions with current architecture and a runbook. Historical documents and signal research remain indexed and available.

## Review and next validation

Offline tests cover original selection boundaries, no KPM/lobby cutoff, team/icon payloads, interrupted delivery recovery, ambiguous-write blocking, definitive rejection retry, local writer exclusion, rate-limit bounds, empty/singleton menu operation, live corpus counts and Discord detail limits. The existing ingest self-checks exercise its item/skill/signal fixtures.

Before a separately authorized deployment: test the reporter against a designated test channel, inspect real thread receipts and current application icons, confirm slash-command permissions, inspect volume ownership, and confirm the intended app/channel configuration. These checks were not run here. There is no claim that Fly services are currently healthy or running.

Remaining practical limits:

- Conservative recovery cannot promise exactly-once external writes. A rare ambiguous write beyond the bounded history search requires operator reconciliation.
- File locking protects a single ledger on one host. Multiple independent machines/ledgers are unsupported for the same report destination.
- Explorer coverage is bounded and API-dependent; reaching the page ceiling fails visibly. Discovery does not currently checkpoint pagination between failed passes.
- Raw research fixtures and ranking scores are historical evidence. They do not validate today's match-quality judgments or current game balance.
- The standalone daimon experiment was relocated, not completed or deployed.

## Local delivery

The handoff was prepared in `/home/clsandoval/cs/herald-handoff-20261004` on `chore/herald-collaborator-handoff-20261004`; a shell is available in tmux `main:herald-astra-handoff`. The original worker-owned `.omo/` and `scripts/prod_watch.sh` were not modified. No deploy, push, collaborator invitation, credential rotation or paid model call was performed.
