# Implemented reporter observations

Owned files: `herald/report_signals.py`, `tests/test_report_signals.py`, bounded-field regression in `tests/test_scheduled.py`, and this planning directory. Embed integration and query selection are owned separately in `herald/scheduled.py`/`render.py`.

## Findings used

- Current stable reporter is `herald.scheduled`; `slow_scraper` is historical.
- The existing item PMI and mode-conditioned ability-position surprisal are menu corpus experiments. Their statistics do not exist in the stable reporter. No rarity label or ranking is added here.
- `.planning/spikes/skill-weirdness/README.md` establishes that ability `level` means prior ability level, that ability ID 0 is a placeholder, and that fixed skill rules were rejected as a scorer. Opening-three-identical is displayed only as an exact observation.
- `.planning/spikes/signal-mining/README.md` and retained STRATZ probe substantiate event timestamps, death durations, diebacks and use counts. Missing item-use entries are not interpreted as zero.
- Jenkins' official channel examples support concrete inventory/event receipts: repeated expensive final slots and Rapier escalation; https://www.youtube.com/watch?v=dWr2cv3JbXo supports the high-Smoke-use receipt. No causal interpretation or judgment of a player is inferred.

## New pure contract

`summarize(raw, opendota, duration)` returns `match` strings and player-indexed `players`, `items`, `skills` mappings. Player indices refer only to the STRATZ player list; there is no unsafe provider-to-provider player-index join.

`items` contains observed final-slot IDs. `skills` contains bare names for the first eight recorded non-talent picks, preserving simultaneous event order and using numeric fallbacks for unknown ability IDs. Missing mapping entries mean unavailable; explicit empty arrays mean no recorded items/non-talent picks. Partial known inventories retain observed positive items without claiming empty absent slots.

Observations include:
- Rapier purchase times, or an exact purchase-to-death interval of at most 90 seconds. Never a dropped-Rapier claim.
- Repeated expensive final inventory copies, explicit zero-use BKB, explicit under-ten-use Midas, first recorded Midas purchase at/after 30 minutes, ten-plus recorded Smoke uses.
- Repeated diebacks and attempted-TP deaths, plus distinct same-team heroes dying after buyback within a two-minute window.
- Recorded dead-time intervals merged and clipped to the match duration; shown at 30% or more of the match. Unknown gold fed is never filled with zero.
- First three non-talent picks identical and randomed hero, stated factually.
- An actual winner's observed 8,000-plus gold deficit, and final all-barracks-destroyed state, using the already-fetched OpenDota response. Final barracks state is not presented as evidence of how long megas were defended.

Thresholds are bounded display heuristics, not calibrated rarity or quality scores. The extractor does no network or database I/O. The richer reporter selection adds fields to its existing batch; no extra API request or menu database dependency.

## Verification

- 50 focused deterministic signal tests pass, covering absence versus zero, malformed scalar values, contradictory usage logs, event ordering/deduplication, interval clipping, winner evidence, indexing and no input mutation.
- Current integrated checkout: 204 offline tests passed in 4.30 seconds; only upstream `audioop` deprecation warning.
- All 38 retained match fixtures run through the extractor without requiring new provider fields.
- No live STRATZ/OpenDota requests, Discord writes, credentials, deployment or push performed.

## Limits and next checks

- New rich fields cannot appear in older saved payloads. Existing immutable delivery receipts intentionally preserve previous message bodies.
- Unknown/new ability IDs keep an honest numeric label until bundled assets are refreshed.
- Missing/partial event feeds may omit interesting observations; missing telemetry never becomes a negative claim.
- The reporter deliberately has no corpus-calibrated off-meta score. Future statistical integration needs its own sample/patch/mode sufficiency design and cost review.
- Real Discord rendering still needs the explicitly authorized test-channel validation path. Offline payload checks do not establish live rendering.
- Independent review should stress delayed response ordering, headline cue prioritization, degraded optional data and the immutable-receipt recovery path after schema expansion.
