# Menu reliability and offline QA

The private `/heralds` menu can be exercised without a bot token, production
database, Discord server, or paid API. See [the simulator](SIMULATOR.md) for its
interactive controls and the difference between live Python callbacks and a
static preview.

## Regression coverage

The tests exercise the actual `Board`, `AdvModal`, SQLite reads and renderers.
Discord responses are fakes; nothing is sent to Discord.

- Rapid clicks share one session. Every callback reserves its order before an
  asynchronous acknowledgement; queued requests acknowledge without waiting for
  an earlier database read or render. A failed build or message edit does not
  commit proposed state. Cancellation releases the queue without skipping an
  earlier callback.
- Replacement views and stale advanced-search modals preserve the latest filters.
  Double Next advances two pages; page bounds, empty results, pruned matches and
  random selection are tested.
- Invalid numeric filters produce a private explanation and preserve the search.
  Duplicate hero/item terms are merged; no more than ten distinct hero and ten
  distinct item criteria are accepted in one form.
- Read-only database paths preserve `#`, `?`, `%`, spaces and Unicode. Missing
  archives are not accidentally created; schema failures keep session state.
- Unreadable raw rows do not hide healthy rows. Optional malformed notes are
  ignored; unknown player statistics remain unknown. Missing net-worth series
  render an unavailable placeholder instead of an invented flat line. Player
  team identities require literal booleans; numeric winner flags remain unknown.
- Item and skill builds have separate focus tabs. Spoiler focus never generates
  or attaches an outcome graph. Components and text budgets are checked on
  serialized Discord payloads, including missing emoji assets and long names.
- A menu expires after fourteen idle minutes, disables its controls and explains
  how to reopen it. A timeout from an old view cannot expire its replacement;
  deleted messages receive a private recovery response when possible.
- Chart caches distinguish archives and changed series, coalesce concurrent
  requests, recover from failed jobs and have size/count limits. Matplotlib
  rendering is serialized and figures are released on failure.

Run the offline suite with the locked dependencies:

```sh
uv sync --frozen
uv run pytest -q
uv run python -m herald.ingest --selfcheck
uv run python -m herald.ingest --skillcheck
uv run python -m herald.ingest --signalcheck
```

## Reproduce the latency probe

```sh
uv run python scripts/benchmark_menu.py --samples 7 --output /tmp/herald-menu-benchmark.json
```

The probe creates disposable 100-, 1,000- and 10,000-match archives from one
deterministic synthetic game, varying IDs, start times and stored rank/score
columns. It uses actual SQLite queries and chart rendering. “Cold” clears chart
caches, not the operating system's disk cache. No Discord transport is measured.

Initial cloud-workspace measurements on Python 3.12, 2026-10-06, seven samples:

| Archive | Warm list p50 / p95 | Hero + item search p50 / p95 | Cached focus p50 / p95 |
| --- | ---: | ---: | ---: |
| 100 matches | 10.1 / 11.7 ms | 13.4 / 15.8 ms | 2.1 / 2.5 ms |
| 1,000 matches | 33.8 / 47.0 ms | 58.1 / 82.5 ms | 2.0 / 2.3 ms |
| 10,000 matches | 332.1 / 416.0 ms | 613.6 / 739.5 ms | 2.4 / 3.6 ms |

The 10,000-match archive was approximately 167 MiB. Its cold focus render took
118.2 / 149.0 ms p50 / p95. List rendering made five SQLite reads, advanced search
six and focus one. With 150 ms of artificial delay per database/chart call, fake
acknowledgement happened in 0.02–0.03 ms and the largest observed
event-loop heartbeat gap was 25.1 ms. This demonstrates acknowledgement order and
off-loop work, not a promise about Discord network latency.

The old correlated hero-search condition repeatedly scanned a hero's player
slice for every match. On this 10,000-match archive it did not finish within the
4-second diagnostic limit. Materializing eligible match IDs once returned the
same count in 13.2 ms. The full search timings above also include guarded item
JSON reads, fresh corpus counters and rendering. Tests preserve the
requirement that all selected hero terms must match. Corpus counters still
refresh from the archive on each interaction rather than relying on a stale
whole-corpus cache.

## Boundaries

These checks do not prove Discord's server-side acceptance, guild installation
permissions, production API availability, Fly deployment behavior, real network
latency or all possible archives. The interactive simulator is a debugging aid,
not an exact Discord-client emulator. Live validation needs an explicitly
authorized test destination and should preserve the separate reporter and menu
policies. Synthetic timings vary with machine load and archive contents.
