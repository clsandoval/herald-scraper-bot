# Working on Herald

Read README.md and docs/ARCHITECTURE.md first.

- Preserve two intended modes: the fixed-rule slow scheduled reporter and the experimental private `/heralds` menu. The menu's corpus/scoring policy does not replace the reporter's legacy eligibility rules.
- Keep the baseline simple. No LLM summaries, ranking framework, or new configuration matrix in scheduled reports.
- Preserve useful item/skill signal experiments and their evidence. Menu signals are exploratory, not proven quality judgments.
- Application code is in `herald/`; `spikes/` fences all experiments and old-path compatibility shims. `spikes/daimon/` is an independent unfinished scaffold.
- Prefer offline tests and synthetic fixtures. Importing modules must not connect to Discord, query a live DB, or call paid APIs.
- Never commit tokens, real .env files, runtime databases, delivery receipts, or logs. Do not inspect or alter `.omo/` or `scripts/prod_watch.sh` when another worker owns them.
- Sending reports, deploying, or modifying application emojis is a live operation. Repository maintenance alone does not authorize it.
- Record substantial changes in `.planning/quick/`; the earlier generated GSD command requirement depended on a missing CLI. Routine local work may proceed directly with a task plan, tests, and summary.

The pre-handoff generated instructions are retained for historical reference in docs/archive/CLAUDE-pre-handoff.md. They describe removed modules and are not current guidance.
