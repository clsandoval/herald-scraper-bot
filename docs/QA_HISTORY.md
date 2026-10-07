# Historical regression checklist

Audit date: 2026-10-06. Base: `dcd6579`.

The checkout contains 104 commits reachable from HEAD and 180 across all refs.
The audit enumerated that history, commit messages and changed-path inventory,
then inspected the relevant selection, UI, signal, reliability and handoff diffs
and retained design evidence. This is a behavioral regression audit, not a claim
of line-by-line verification of every historical file or a credential audit.
Historical credentials, runtime logs and delivery receipts were not inspected.
Current `CLAUDE.md`, `README.md` and `docs/ARCHITECTURE.md` override old plans.
No live APIs, Discord operations, deployments or pushes were used.

## Highest-priority regression gates

### P0: Keep the two modes separate

- Reporter: duration strictly greater than 4,500 seconds, average rank at most
  16, no known player rank above 15, ten players/five per side, present accounts
  and explicit OpenDota leaver-status zero. Unknown account rank is allowed.
  No KPM/lobby gate and no corpus-relative ranking in report eligibility.
- Menu: ranked lobby, rank-average 10–15, default duration at least 3,600 seconds,
  at least 1 KPM; experimental corpus-relative signals are menu-only.
- The 2025 strict-missing-rank experiment (`1389973`, `src/models/stratz.py`) was
  reversed by `f3ad9e4`; that commit also disabled an account win/loss cutoff.
  Do not revive either as an inferred current requirement.
- The October handoff (`e9eab17`, `f3bf1be`, squashed in `dcd6579`) restored the
  delayed one-day reporter window and separated shared transport from policy.
  Rich factual observations may improve cards without changing match selection.
- Verify `tests/test_mode_boundaries.py` and reporter selection/recovery tests.

### P0: A responsive UI requires both sides of the async boundary

- Construct Discord views on the event loop. Moving view construction into
  `to_thread` silently broke dispatch (`44b5610`).
- Run SQLite reads, large raw-data decoding and matplotlib work off the event
  loop. Simply adding a 30-second busy timeout caused 30-second gateway stalls
  until `804c397` moved reads and rendering off-loop.
- The menu reader must have fresh read-only connections and no schema writes,
  WAL pragmas or telemetry commits. `5a99d7e` added usage writes; `44b5610`
  disabled them; `a228f78` removed the remaining write connection/DDL after
  startup locks caused restart loops. `e7b03f0` addressed another startup-lock
  failure. Imports must remain offline and must not query the archive.
- Assert acknowledgement before slow work, actual callback dispatch, repeated
  clicks, stale views/modals, error rollback, expiry and independent sessions.
  Source-text checks alone once matched a comment instead of a pragma
  (`4119c61`). Exercise behavior as well.

### P0: Respect Discord budgets and preserve readable evidence

- `6ee741c` fixed rejected overlong classic messages. Components V2 and classic
  embeds have different budgets; validate each real payload separately.
- The live menu evidence (`5f48ff3`, `.planning/spikes/menu-v2/README.md`) records
  the 40-component limit, aggregate TextDisplay budget and attachment behavior.
  Select-option text is separate from TextDisplay text.
- Preserve all ten players and six observed final-slot items per player before
  optional receipts. Fresh bots may have no application emojis. The handoff
  fix `971e560` explicitly restored readable item names in that case.
- Test long bundled names, new/unknown item and ability IDs, missing/null logs,
  both emoji modes, crowded receipts and actual serialized payload sizes.
  An absent usage record cannot prove an item was never used; an empty or
  absent skill log cannot prove that a player spent no skill points.

### P1: Preserve the validated scoring semantics

- Item signal (`241b5c2`, `b955251`, `44b5610`): corpus-relative PMI, distinct
  item-family top-three accumulation, purchase receipts, 1,000-gold item floor,
  multiple independently unusual players contributing to match score. The
  off-meta filter uses positive scores and the current 95th percentile.
- Skill signal (`5037ac0`, `d57abe5`, `8cd58f9`): hero-and-mode-conditioned
  positional surprisal, first 12 non-talent/nonzero picks, hero ability-pool
  filtering, own-pick exclusion, distinct-ability top three, early-ult discount,
  and separate item/skill sorts. Sparse SINGLE_DRAFT/RANDOM_DRAFT are excluded.
- Rule-only anomaly ranking was rejected for false positives. Markov ranking
  was rejected because it preferred many mildly odd choices over one clear
  review hook. Keep rule labels as supporting receipts, not a replacement
  score. Do not present either experiment as proven match quality.
- Badge mastery uses `dotaPlus.level`, never the XP sentinel. Include level 25
  Master badges (`d6b730d`), and sum Master+ badges so two strong specialists
  outrank one lone level 30 (`157ec74`); an average/max-only sort was superseded.

### P1: Rescoring must survive incomplete logs and partial failure

- `5037ac0` records a real re-enrichment incident: `INSERT OR REPLACE` nulled
  item scores. The same upsert still resets both experimental score columns.
  `e0b359f` added the >500 unscored-row trigger alongside the 50-cycle refresh.
- Audit reproduction: three builds with four picks across two abilities caused
  `score_skill_weirdness` to divide by zero. Training skipped <6 filtered picks,
  but scoring still subtracted their nonexistent own-observation counts.
- Fixed in this QA work: both passes require at least six filtered picks.
  Incomplete builds contribute no skill score or receipt. Complete-build
  probabilities, mode conditioning and established ranking thresholds remain.
  Unknown ability IDs also retain a readable `Ability ID` receipt instead of
  failing while generating the three-identical-opening-picks label.
- Rescore detection now checks both score columns. A partially scored pair
  retries on the next cycle, and a failed periodic refresh is remembered even
  when old non-NULL values remain. New/re-enriched rows missing both scores keep
  the existing >500-row trigger and 50-cycle cadence, avoiding an unconditional
  expensive boot rescore. A small both-NULL wave can therefore still wait for
  the normal cadence; explicit `--weirdness` remains the maintenance option.
- Regression coverage: `tests/test_skill_scoring_edges.py` checks sparse logs,
  accepted six-pick builds, excluded modes, both partial-score directions,
  threshold boundaries, and a failed periodic pass that succeeds next cycle.

### P1: Avoid repeating the storage and discovery incidents

- `687b86b`: loading all purchase events during startup scoring exhausted a 1GB
  VM. `44ef6bd`/`44b5610`: stale pre-pivot rows and whole-corpus raw scans caused
  further OOMs; recomputation was made streaming and duration pruning enforced.
- `22924b3`: per-cycle WAL checkpoints and optional `load_matches` bounds were
  added after runaway WAL/commit delays. Live menu hydration must remain page
  scoped; chart caches and simultaneous renders need explicit bounds.
- `3f080ed`: keep the Explorer SQL walk rank-only, keyset-paginated in 100-row
  pages. Lobby, duration and time constraints are checked locally: putting the
  sparse conjunction back into SQL repeatedly exceeded Explorer's read budget.
- `c3943ed` replaced sampled `/publicMatches` discovery with the Explorer walk;
  `7766e69` established 25-alias Stratz batches. Old one-match-per-request and
  feed-completeness claims in the initial bakeoff are obsolete.
- Preserve delayed enrichment, retry handling, daily logical-batch budget,
  pruning after discovery failures, and the documented distinction between a
  live process and fresh data. No historical quota observation is a guarantee
  about a current provider account.

## Signal and presentation decisions that still matter

- **30% dead-time gate:** `44b5610` replaced the earlier absolute 20-minute OR
  test because it flagged ordinary players in long games. Recorded death
  intervals should be bounded by match duration and duplicates must not inflate
  totals. Preserve the percentage threshold.
- **Gold swings are reversals, not only zero crossings:** `44b5610` defined a
  3,000-gold reversal while still ahead as a swing. Do not substitute lead-flip
  count for the explicit swing sort.
- **Megas comeback means the winner's own barracks were destroyed:**
  `c958e74`/`6c6c36a`. Hide the outcome tag, winner and focus chart in spoiler
  mode. Ordinary stats and list thumbnails are not guaranteed outcome-free;
  the current architecture explicitly limits the spoiler promise.
- **Rejected/weak receipts:** `d2eb215`/`9a781c1` found broken invisible-seconds
  values and opaque behavior fields; fountain-trip extremes were a Tinker
  artifact; wards/stacks were too ordinary. Do not resurrect them as strong
  review signals just because those fields are available.
- **Chat is an unfinished opportunity, not lost implementation:** mining
  proposed raw chat excerpts and a trash-talk filter. The shipped quick task
  implemented `chat_lines`/Most talkative and other receipts, not chat excerpts.
  Preserve source language if later implemented, and avoid claiming unseen
  lines or inferred intent. Current detail cards can emphasize better-grounded
  item/skill/event evidence first.
- **Jenkins evidence is hypothesis-level:** the retained replay-quality spike
  used titles/snippets, not watched full episodes or transcripts. It supports
  candidate hooks such as unusual builds, marathons and extreme events, not
  an empirically validated automated funny/good-match classifier.

## UI evolution: preserve preferences, not abandoned infrastructure

- `f2ffbfd`/`06c3dbb`: direct, criterion-based labels; no flavor descriptions,
  legends or snark; multi-select filters; key controls visible on the hub.
- `a286cea`: compact team rosters with thumbnail graphs; no per-row buttons.
  `44b5610` later split the teams onto separate lines and reduced seven rows to
  five. The old seven-row design requirement is therefore superseded.
- `4cf5deb` established readable hero/KDA/item glance rows; `f4b7080` put the
  full graph inside match focus and removed a separate graph screen. Current
  rich item/skill cards extend this evidence-first layout.
- Grouping and closest-three fuzzy search were prototype behaviors; the SQL
  menu in `58f832b` replaced that design with exact advanced WHERE constraints,
  ordinary sorting and pagination. Their absence is not a new QA regression.
- `74cdb55`/`6a67be2` deliberately retired the eternal/public board, its refresh
  timer and stale-post cleanup. `/heralds` is private and on demand. Do not
  restore automatic posting from the old Gazette/weekly-board specification.
- The 2023–2025 Telegram/Lambda, LLM-summary, per-player account-history and
  later agent-platform experiments are historical branches, not dependencies
  to bring back. `c5b4ee3` removed the legacy application and the October
  handoff fenced the unfinished agent scaffold under `spikes/daimon`.
- Old thread cleanup once deleted threads without checking bot ownership;
  `3d727cb` added that guard. Current code need not regain any cleanup. Any
  future cleanup must be explicitly authorized and narrowly owner-scoped.

## Verification for this audit's code fix

- `pytest tests/test_skill_scoring_edges.py tests/test_herald_board_regression.py
  tests/test_mode_boundaries.py -q`: 36 passed.
- Ingest `--selfcheck`, `--skillcheck` and `--signalcheck`: passed.
- These results cover this scorer/retry patch only. Concurrent UI work and its
  final aggregate checks are separate; no live Discord/API correctness or
  deployment claim follows from offline success.
