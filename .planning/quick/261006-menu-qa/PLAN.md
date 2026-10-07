# Menu and report QA, 2026-10-06

## Requested outcome

A production-backed offline Discord Components V2 simulator; repeated behavioral,
visual, and latency checks; readable item inventories, early skill paths and
factual match moments for Herald replay selection. Publish reviewable draft PRs.
The separate bot/repository integration is deferred.

## Safety and compatibility

- No live Discord messages, token use, API scraping, emoji provisioning or deployment.
- Keep reporter fixed eligibility and durable immutable delivery receipts separate
  from experimental menu scoring and corpus-relative novelty.
- Preserve unknown data as unknown. Purchase/death proximity is not proof of a
  dropped Rapier; public YouTube comments/views are not audience retention.
- Simulator snapshots are synthetic data, not screenshots of a live Discord server.
- No claim that a finite test suite exhausts every possible external failure.

## Checks

1. Original suite baseline: 47 passing tests before changes.
2. Real menu callback tests: immediate acknowledgement, concurrent/stale controls,
   rollback, modal validation/cancel/reopen, pruning, expiry and database failures.
3. Serialized wire contracts: all current sorts/directions, individual filters,
   spoiler/list/focus/page boundaries, attachment references and Discord limits.
4. Enumerate all 2,048 subsets of the current 11 filters on a deterministic archive
   and compare SQL results with set intersection. This is filter-combination
   coverage on one fixture, not exhaustive data or interaction coverage.
5. Report receipts: malformed/missing data, bounded output, explicit evidence,
   delivery recovery, and unchanged eligibility.
6. Size-dependent latency benchmarks and slow-operation acknowledgement tests.
7. Browser visual/interaction QA and screenshots when supported preview access is
   available; do not equate Python tests or static exports with browser QA.
8. Offline selfcheck, skillcheck, signalcheck; final aggregate tests and diff checks.

## History consulted

The full clone contains 104 HEAD ancestors and 180 commits across all refs.
Important prior decisions include the menu-v2 live prototype iterations, event-loop
and SQLite locking fixes, reporter/menu separation, corpus-conditioned skill/item
novelty, and rejected ward/fountain/Markov signals. Preserve those lessons rather
than replacing them with unvalidated rankings.
