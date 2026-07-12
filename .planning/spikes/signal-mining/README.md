---
spike: signal-mining
name: enriched-field-signal-mining
type: standard
validates: "Given the 4,876-match corpus with the 13 KEEP fields, when each signal area is mined with distributions and top-N eyeballs, then a concrete set of receipts/filters/sorts with tuned thresholds emerges"
verdict: VALIDATED
related: [stratz-signals, skill-weirdness]
tags: [scoring, chat, receipts]
---

# Spike: Signal Mining on the Enriched Corpus

Code: `spikes/signal-mining/` (extract_mine.py on prod → 3 TSVs → mine.py +
inline chat passes). Corpus: 4,876 ranked ≥50min matches, 48,760 players,
47,206 all-chat lines.

## Findings & thresholds

**Chat (the crown jewel):** 29% of players talk (p99 = 26 lines); 43%
Cyrillic. Corpus contains full Orthodox prayers typed into all-chat,
multi-line family-insult tirades, and **133 players who said "ez" and went
on to LOSE** (e.g. Sniper, minute 66). "gg" 3.4k, "ez" 863, "report" 498,
lone "?" 616. → chat excerpts on focus view + "trash talk" filter.

**Feeding:** time-dead p50/p90/p99 = 11/17/23.4 min; top fraction-dead is
70% of a 60-min game. gold-fed p99 ≈ 21k. died-mid-TP ≥3: 22 players.
`hasHealAvailable` ≈ never fires at 5+ — drop it. Diebacks are real in
marathons (11% of players ≥1). **Tinker artifact:** tops both time-dead and
fountain-trips (fountain-hydra gameplay) — fountain-trips receipt SKIPPED,
time-dead kept (fraction-of-game carries the story regardless of hero).

**Megas:** 59% of ≥50min games end with someone's racks gone — "megas
happened" is NOT a filter. The signal is **comeback-vs-megas: won while your
own base was megged — 327 matches (6.7%)**. Filter-worthy, computed from
barracksStatus + winner.

**Item shame:** 659 players (4% of BKB buyers) bought BKB and never pressed
it. Midas <10 uses: 49 players. Both receipt-worthy, marginal as filters.

**Randomed heroes:** 244 players. Receipt tag.

**Wards/stacks:** distributions too smooth to be funny (70% place wards) —
SKIPPED as receipts.

## Build proposal (next quick task)

- Derived cols (recompute-able): `megas_comeback` INT flag, `chat_lines` INT,
  `has_ez_loser` INT.
- Filters: "Comeback from mega creeps" (megas_comeback=1), "Trash talk in
  chat" (has_ez_loser or ez/report threshold).
- Sort: "Most talkative" (chat_lines).
- Focus-view receipts (parsed from raw at render, like existing ones):
  💬 up to 3 chat excerpts (priority: ez-from-loser > tirade > spam),
  💀 "spent X min (Y%) dead, fed Zk gold" for time-dead ≥ 20min or ≥ 33%,
  tags: died-mid-TP ≥2, buyback-then-died ≥2, BKB never used, Midas <10,
  randomed hero, "won from megas / lost despite megas".
