# Standalone slow-reporter build evidence

## Request and ownership

Close the audited gap between build display/factual events and actual item PMI / mode-conditioned skill evidence in slow scheduled reports. Preserve reporter selection, menu experiments, Discord delivery shape and immutable saved specs. No menu DB, new API calls, live sends, deployment, secrets or simulator changes in this task.

## Implementation

- Extracted policy-free `herald.novelty` math. Existing menu wrappers have byte-identical score/receipt parity against 123 synthetic pre-extraction matches. Streaming skill first-index histograms avoid a raw positional-history list.
- Corrected completed no-item-evidence refresh so it clears stale positives and does not trigger endless partial-score rescans.
- Added `reporter_novelty.ReferenceStore`, a bounded 30-day/5,000-match compact reference table inside the reporter ledger. Same known patch, explicit version/asset compatibility; no account/raw/event payload retention. Freeze a bounded SQLite TEMP snapshot per pass; at most two fitted patch models; new reports are held out until later runs.
- Explicit unscored support floors: 30 item-bearing hero builds; 30 complete hero/mode builds and 20 observations at every skill position. Sparse modes, missing logs/patch, unsupported target abilities/items and changed retained targets remain unscored. Floors are evidence guards, not validation of rarity or play quality.
- Current-mode provenance and membership are persisted in delivery specs. Identical stored targets subtract their own observations exactly as legacy math; held-out data never subtracts. Compact records deduplicate by match ID.
- Added gameMode to the same Stratz request and patch from already-fetched OpenDota. No eligibility changes. Parent previews follow calculated evidence, and team cards retain all twelve observed skill ordinals with original-position scored receipts.

## Verification

- Shared math: 17 unit/parity tests, 90 related regressions, all three ingest selfchecks passed.
- Reporter tests cover cold start, patch/mode boundaries, missing and unsupported logs, target membership, changed retries, immutable JSON, frozen snapshot/LRU eviction, bounded retention, original pick 12, evidence-driven preview choice, and unchanged request counts/eligibility.
- Independent reviewer separately tests fixed snapshot membership, changed-target safety, provider errors, and existing delivery retry specs.
- Reproducible offline 5,000-match/50,000-player benchmark: preparation 1.459s, snapshot 0.045s, first fit/score 1.758s, 100 warm targets median 0.826ms/max 1.545ms, ledger 39.5MiB, temp snapshot 39.31MiB, peak process RSS 24.38MiB. Delivery-history growth is separate and intentionally retained.

- Aggregate check after integration: 408 tests passed, all three ingest selfchecks passed, and git diff --check clean.

## Warm-up

A fresh reference or new patch starts unscored. The first pass only seeds future reference data; next pass can score supported heroes/modes. A niche hero may not reach the conservative floor inside 30 days. Existing posts are not replayed or edited to provide warm-up scores. Documentation labels the population as eligible long-Herald scheduled reports, not universal Dota meta.
