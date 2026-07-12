# Spike Manifest

## Idea

Herald Reviews Scout: a quiet Discord bot holding a week of Herald-bracket
matches, surfaced through a **menu-first UI** (Components V2) so a non-technical
server browses filters/group-bys/graphs/icons with zero AI framing; the
NL-question agent layer comes later, hidden behind the same data.

## Requirements

Emerged from spiking — non-negotiable for the real build:

- OpenDota for discovery, Stratz for enrichment (api-bakeoff); enrich a few
  minutes delayed, retry the ~30% stragglers
- Menu-first, zero AI framing in the visible UI (user: server is "luddites")
- Architecture: **Gazette front-end on Browser back-end** — weekly boards
  edited in place + per-user ephemeral drill-downs, stateless custom_id grammar
- Inline item/hero icons via **application emojis** (seeded, map committed)
- Charts: matplotlib PNG attachments, validated palette (Radiant #3BA55D /
  Dire #ED4245 on #313338)
- One shared render layer owns the 40-component/3600-char budget guard
- Hero image URLs from dotaconstants `img` fields only — never hand-built
  (`_sb.png` is dead)
- All dev/testing in the test server (guild 1392724275538038826) only

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| api-bakeoff | OpenDota vs Stratz | comparison | Herald discovery + parsed detail within free tiers | VALIDATED (use both) | api, opendota, stratz |
| herald-replay-quality | replay-quality skill | standard | Jenkins' taste as computable 0-100 rubric | DRAFTED (design doc) | skill, scoring |
| menu-v2 | menu-first Components V2 | comparison (6-way) | menu UI feasible + one architecture wins | VALIDATED (Gazette×Browser hybrid) | discord, ui, components-v2 |
| skill-weirdness | skill-order weirdness signal | comparison (PMI vs rules) | corpus PMI over (hero, mode, skill-index) surfaces genuinely weird builds vs noise; rules baseline; tuned top-20 board eyeballs right | VALIDATED (PMI wins; rules = receipt labels only) | scoring, abilities, weirdness |
