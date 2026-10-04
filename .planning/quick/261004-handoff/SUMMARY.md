# Handoff result

Prepared an isolated, reviewable two-mode product: fixed-rule scheduled reports plus the experimental private menu. Restored the original delayed one-day report window and explicit one-shot backfill, checkpointed partial thread delivery and failed windows, preserved useful signal research, promoted runtime code/assets/fixtures into an installable package, and moved the unfinished daimon workspace into an independent experiment.

## Offline validation

- 40 pytest checks pass; one third-party discord.py/audioop deprecation warning on Python 3.12.
- Ingest selfcheck: 38 matches / 380 players; skillcheck and signalcheck pass.
- Old ingest CLI and all four historical import wrappers pass.
- Frozen uv sync and wheel/sdist build pass with network disabled. A separately installed wheel outside the checkout passes mode help plus all three selfchecks.
- Metadata-only scan of tracked text reports no potential credential-pattern matches; no actual .env file is tracked. This is a current-tree heuristic check, not a claim about all git history or revocation.
- git diff --check passes.

Independent adversarial review drove fixes for message-budget overflow, definitive rejection recovery, failed-window pinning, GraphQL failure propagation, minimal report API fields, deployment volume paths and help routing. Final review applies to the resulting commit identified by git history.

## Boundaries

No live API validation, Discord sends, deployments, pushes, secret rotations, collaborator invitations, paid calls, or changes to the ongoing worker's .omo/ and prod_watch.sh. Supplied Fly state remains suspended/no machines; no health claim. Docker/Fly execution and the archived daimon experiment were not exercised. See README.md and docs/ARCHITECTURE.md for current setup, recovery and operational limits.


## Rubric completion — 2026-10-04

- Extracted shared OpenDota/Stratz transport into `herald/api.py`; scheduled reports no longer import menu ingestion/settings/scoring. Legacy reporter eligibility and menu behavior preserved.
- Rewrote README with a compact two-mode overview, three Mermaid flows, exact 12-variable key/settings table, provider quota sources, permissions/intents, local setup and ordered setup for both Fly templates. Costs are sourced reference estimates, not measured bills.
- Folded runbook/handoff/root architecture wrapper into README + one architecture doc. Fenced daimon with all other experiments in `spikes/`; removed duplicate image/dependency wrappers and untracked the old prototype delivery receipt (local ignored copy retained).
- Fixed fresh-bot menu startup by replacing historical prototype emoji IDs with the current application inventory (read only), with text fallbacks for empty/unavailable inventories.
- Added a container entrypoint to prepare fresh volume-directory ownership before dropping to UID/GID 1000; existing DB-file ownership still requires explicit migration.
- Validation: `uv run pytest -q`: 45 passed (one third-party audioop deprecation warning); all three ingest selfchecks pass; offline wheel/sdist build passes; all four repository Mermaid blocks parse with Mermaid 11; all current local doc links and both Fly TOMLs validate. README environment inventory matches code exactly.
- No live operations or push; protected worker files were not inspected or changed. Docker/Fly execution and real Discord/API delivery remain untested within the authorized offline scope.
