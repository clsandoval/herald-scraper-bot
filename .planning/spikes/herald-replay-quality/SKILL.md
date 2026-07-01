---
name: herald-replay-quality
description: >-
  Score a stored Dota 2 match for how "review-worthy" it is for a Jenkins-style
  Herald Reviews stream segment. Use when ranking/triaging Herald-bracket
  replays (from OpenDota/Stratz match data) to surface the funniest, craziest,
  most absurd games a streamer would want to react to. Encodes Jenkins'
  stated filters ("the lower MMR the better, the crazier the game the better")
  as computable heuristics. First-draft / spike-quality; humor is not fully
  computable, so treat scores as candidate-surfacing, not final selection.
---

# Herald Replay Quality — review-worthiness scoring

Goal: given a stored match's data, estimate how good a candidate it is for a
Jenkins "Herald Reviews" segment. Output a 0-100 score + the top firing signals
as human-readable reasons, so a human makes the final pick.

## Guiding principle (from the source)

Jenkins' own criteria: **"the lower MMR the better, the crazier the game the
better."** The series casts the worst games as if they were pro matches — the
payload is *comedic contrast*. So we reward: extreme low bracket + chaos +
one legible absurd hook. We do NOT reward "good clean games." Humor itself is
uncomputable — heuristics surface candidates; they cannot certify a laugh.

## Hard gate (must pass, else disqualify or heavily penalize)

- **Bracket = Herald.** `rank_tier`/`avg_rank_tier` in the Herald band. Non-Herald
  games are off-format. Lower within Herald is strictly better (see G1).
- Skip / down-rank matches that are likely **smurf-contaminated** (see PURITY),
  since a smurf stomp is a different, less-funny thing. Soft, not hard.

## Scoring signals (grouped by theme; computable where possible)

Each signal contributes points. Suggested weights in [brackets] — tune later.
Cap total at 100. Track which signals fired for the "why" explanation.

### A. Bracket / purity (the gate, weighted) [0-20]
- **G1 low_mmr_bonus [0-12]:** the lower the bracket, the higher. Full points at
  Herald 1 / effective "10 MMR" floor, scaling down through Herald 5.
- **PURITY no_smurf [0-8]:** reward when all accounts look genuinely Herald
  (low account level / low game counts / no wild per-player skill outliers).
  Penalize a clear smurf (one player with vastly higher APM/GPM/last-hits than
  the lobby). Proxy-only; noisy.

### B. Chaos & length (signature axis) [0-30]
- **marathon [0-12]:** `duration` > 60 min starts scoring; steep bonus > 90 min;
  max > 120 min. E.g. "Warlock jungles for 70 minutes", "2 hour Herald game".
- **kill_chaos [0-10]:** high total kills (both teams) and/or high kills/min.
  200+ combined kills = max. ("220+ kills" games are prime.)
- **mega_standoff [0-8]:** long game where barracks fell early (mega creeps) but
  the game continued a long time, or net worth stayed close very late =
  mega-creep marathon / standoff.

### C. Absurd stat lines & item builds (comedic hook) [0-28]
- **int_build / troll_items [0-10]:** hero's purchases deviate hard from norms:
  wrong-stat items (e.g. Radiance/Dagon/Kaya on a hero that doesn't want them),
  **duplicate stacking** (>2 Divine Rapiers, multiple of a unique-ish item),
  no-boots-very-late, all-stats-no-ability builds ("0 skill points"). Each
  distinct absurdity adds. E.g. "Einstein... 0 skill points, Kaya/Yasha->Rapier",
  "Armlet + Dagon + Terrorblade", "real inventory... ~20 Rapiers".
- **feed_line [0-10]:** a single player with an extreme death count (>= ~25, and
  especially a 0-and-many line) = comedic feeder. Scale with deaths.
- **spectacle_stat [0-8]:** any jaw-dropping single number available in data —
  e.g. enormous single-hit damage / crit, absurd GPM, absurd last-hit or
  denies counts, huge net-worth gap. ("PA crits for 10,000.")

### D. Difficulty mismatch — hard/unusual hero in Herald [0-12]
- **hard_hero [0-8]:** `hero_id` in a "high-difficulty" set
  {Meepo, Invoker, Chen, Techies, Arc Warden, Visage, Morphling, Earth Spirit,
  Templar Assassin(off), ...}. Techies specifically is a recurring star
  ("takes the game hostage").
- **one_trick [0-4]:** player has an obsessive count of games on that one hero
  (needs a player-history API call, e.g. "2000 Pudge games"). Optional/partial.

### E. Throw / comeback / smurf-loss (narrative arc) [0-16]
- **lead_reversal [0-12]:** from the net-worth graph, the team that LOST held a
  large lead at some point (big throw — "more throws than basketball", "60k gold
  lead loss"), OR the WINNER climbed out of a large deficit (comeback). Score with
  the size of the reversed lead and how late it flipped. Fuses well with feed_line
  ("feed 43 deaths ... then win"). Note: deliberate-throw intent (a "failed 322")
  is NOT detectable — only the reversed-lead shape is.
- **smurf_loss [0-4]:** one clear stat-outlier player (very high kills/GPM/APM vs
  the lobby) who is on the LOSING team = comedic ("50-kill smurf still loses").
  Uses the same smurf proxy as PURITY, inverted. Do not stack with a no_smurf bonus.

### F. Wrong-role / accidental-genius (heuristic) [0-8]
- **off_role_dominance [0-8]:** a hero played wildly off its usual role/lane
  (support-hero-as-carry, "carry Warlock", jungling a laner) AND that player is
  top net worth/GPM on their team = "the best carry nobody expected" /
  "genius" framing. Heuristic; low precision.

### G. Behavior-score floor (proxy) [0-4]
- **low_behavior [0-4]:** signals of a toxic/low-priority lobby ("0 behavior score
  Herald", "low priority is extremely cursed"). Not exposed per-match by OpenDota;
  proxy via abandons/`leaver_status`, or pull from player profiles if available.
  Partial/low-confidence; optional.

## Signals that are NOT computable (flag, don't score from match data)

- **Comedic value / "is it actually funny"** — the whole point; uncomputable.
  Heuristic score = candidacy only.
- **Chat toxicity / all-chat drama / wholesomeness** — not reliably in match
  data; and note it's a *minor* axis for Jenkins anyway.
- **Human-interest story** (e.g. "63-year-old dad", a viewer's backstory) — comes
  from the submitter's note/DM, not the replay. Capture separately if a
  submission text is available; boost manually.

## Suggested output

```
score: 0-100
tier: must-review (>=70) / strong (50-69) / maybe (30-49) / skip (<30)
reasons: [ordered list of fired signals with their values, e.g.
  "137 min game (marathon)", "player 3-31 deaths (feed_line)",
  "Herald 1 bracket", "4 Divine Rapiers bought (troll_items)",
  "lost team led by 25k net worth at 40 min (lead_reversal)"]
uncomputable_flags: [needs human check: humor, chat, submitter story]
```

## Notes & caveats (spike-quality)

- Weights are first-draft guesses; calibrate against a labeled set of real
  featured vs non-featured Herald games if one can be assembled.
- Best candidates usually fire **multiple** signals at once (long + chaotic +
  one absurd hook). A single mild signal alone is rarely stream-worthy.
- Derived from titles/snippets only — NOT from transcripts or watching. Treat
  the hero-difficulty set, thresholds, and item-norm rules as tunable stubs.
- Do not reward clean, competent, short games — those are the opposite of the bit.
