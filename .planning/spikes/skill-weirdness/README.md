---
spike: skill-weirdness
name: skill-order-weirdness
type: comparison (PMI vs rules)
validates: "Given 15.8k Herald matches with ability sequences, when players are scored by positional surprisal of ability-at-skill-index given (hero, mode), then top-scored builds are genuinely weird on inspection and the top-20 match board is review-worthy"
verdict: VALIDATED
related: [herald-replay-quality]
tags: [scoring, abilities, weirdness]
---

# Spike: Skill-Order Weirdness Signal

## What This Validates

Given the full prod corpus (15,799 matches, abilities re-enriched 2026-07-12),
when players are scored corpus-relative on their skill order, then the signal
surfaces genuinely weird builds (not noise) and a tuned top-20 board looks
featureable. Code in `spikes/skill-weirdness/` (extract_prod.py, sanity.py,
pmi.py, pmi2.py, rules.py, tune.py + abil.tsv.gz corpus snapshot).

## Results

**Winner: positional surprisal (pmi2.py)** — `-log P(ability | hero, mode,
skill-index)`, smoothed, own-pick excluded, first 12 non-talent picks, player
score = sum of top-3 surprisals (mirrors item build-weirdness).

- **001 extract: VALIDATED.** 158k builds, 0.02% empty, 127 heroes (median
  1,023 builds/hero, min 128 — enough everywhere). Stratz `abilities` events:
  one per point spent, time-ordered, `level` = ability's prior level.
- **002a PMI: VALIDATED** after two required fixes found by eyeballing v1:
  - **Mode-conditioning is mandatory** — corpus is 79% TURBO, where banked
    skill points and hero re-picks are normal. Unconditioned stats put Turbo
    artifacts all over the top.
  - **Pool filter** (ability in ≥1% of hero's builds) kills Turbo hero-swap
    artifacts (pre-swap picks pollute the sequence, e.g. Telekinesis "on" PA).
  - **abilityId 0** = `dota_base_ability`, Stratz null placeholder — drop it.
  - Feared cascade inflation (one weird early pick shifting later indices)
    did NOT dominate; top-3 capping bounds it.
- **002b rules: INVALIDATED as scorer.** Explicit rules (ult-early, no-ult,
  wrong-max, mono-open) flag 7.8% of all builds — mass false positives unless
  tuned per hero per mode, which is what PMI already computes. Only 45% of
  PMI's top-1% is rule-flagged; rule-only hits eyeball as mild. **Rules
  survive as receipt labels only** ("ult as pick 4", "opened impale x3").
  Ults are corpus-derivable: common ability with highest median first-index.
- **003 tuning:** player-score percentiles p50=4.7 / p90=7.4 / p99=11.5.
  **NOTE_BAR = p99 ≈ 11.5**; match score = sum of players over bar (else max
  player), same accumulation as item weirdness. Top-20 board: banked-ult
  builds, triple-Nova CM, level-1 Marksmanship, never-skilled ults.
- **Zero overlap** between top-20 skill-weird and top-20 item-weird matches —
  the signals are complementary; keep skill-weirdness as its own component.

## Surprises / Trail

- `isTalent` also flags facet/innate special-bonuses (up to 12/player) —
  talents are unreliable as tier choices; excluded from v1 entirely.
- **Prod regression found & fixed during the spike:** the abilities re-enrich
  sweep re-upserted every match and nulled ALL item-weirdness scores (upsert
  doesn't carry the column; loop rescore only fires every 50 cycles and the
  counter resets on deploy). Ran `ingest.py --weirdness` one-off on prod to
  restore. **Any future re-enrich sweep must be followed by a rescore.**
- Old `ability_ids.json` was deleted in the repo overhaul; spike vendored a
  fresh copy from dotaconstants (100% id coverage on the corpus).

## How to Run

```
python3 spikes/skill-weirdness/sanity.py   # extract checks
python3 spikes/skill-weirdness/pmi2.py 15  # top/median/bottom builds
python3 spikes/skill-weirdness/rules.py    # rules baseline head-to-head
python3 spikes/skill-weirdness/tune.py     # top-20 match board + overlap
```

## Signal for the Build

Port pmi2.py's scorer into `score_weirdness()`-style pass in ingest.py:
same streaming shape, keyed (hero, mode, index), NOTE_BAR from p99, receipts
with rule labels + ability names, stored as its own column (e.g.
`skill_weirdness` + notes) so the board can sort/filter on it independently.
Talents/facets: out of scope for v1.
