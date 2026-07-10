---
spike: menu-v2
name: menu-first-components-v2
type: comparison
validates: "Given a week of real Herald match data, when rendered as Components-V2 menu UIs (filter/group/graphs/icons, no AI framing), then a compelling, within-limits, luddite-friendly browser is feasible and one architecture clearly wins"
verdict: VALIDATED
related: [api-bakeoff, herald-replay-quality]
tags: [discord, components-v2, ui, emoji, charts, dotaconstants]
---

# Spike menu-v2: Menu-first Discord UX (Components V2)

Six competing menu designs for browsing Herald matches, built as live mockups
from **38 real matches fetched same-day** and posted to the test server
(#replays, guild 1392724275538038826). Code: `spikes/menu-v2/`.

## How to run

```bash
cd spikes/menu-v2
# secrets: DISCORD_BOT_TOKEN + STRATZ_API_TOKEN in env (never committed)
../../.venv/bin/python render.py        # self-check the shared layer
../../.venv/bin/python emoji_sync.py    # idempotent emoji seeding
../../.venv/bin/python post_all.py      # post all six threads + intro
../../.venv/bin/python post_all.py a2   # repost one approach
```

## Results — empirical findings (all verified live 2026-07-10)

1. **40-component cap** (nested + Section accessories count; MediaGallery items
   free) and **4000-char pool** are real; we guard at 3600 in one place
   (`render.check`). The Match Board runs at 38/40 — the judge's "zero
   headroom" warning is accurate.
2. **Select option/label text does NOT count toward the 4000-char pool**
   (3900 content + 4500 option chars accepted) — selects can be rich.
3. **Charts work**: matplotlib PNG → multipart `files[n]` + `attachments[{id,filename}]`
   → `attachment://name.png` in MediaGallery, including inside Containers.
   Quirk: the posted message's `attachments[]` array is EMPTY; the file
   surfaces only via the component's resolved `media.url`.
4. **Application emojis are the answer to inline item icons**: 264 seeded
   (107 fixture heroes + ~157 items) in ~2 min at 0.35s/upload, no 429s.
   2000-emoji cap fits everything 4×. Renders in TextDisplay + select options
   without any guild permission. 4 items failed Discord's 256KB source cap
   (`angels_demise`, `grisgris`, +2) — downscale with PIL if ever needed.
5. **Steam CDN `_sb.png` hero variant is DEAD** (404 for every hero).
   `packages/core/daimon/core/match_embed.py:_hero_url` is broken today.
   Use `heroes/{name}.png` (full) or `heroes/icons/{name}.png` (32px).
6. **dotaconstants is current**: 127 heroes (Kez=145, Largo=155), 501 items,
   per-entry CDN img paths. Snapshot committed to `spikes/menu-v2/assets/`.
7. **Stratz gotcha**: bearer token must be `.strip()`ed (aiohttp header
   injection guard trips on trailing whitespace/CR).
8. Chart palette validated (dataviz six checks, dark surface #313338):
   Radiant #3BA55D / Dire #ED4245.

## The six approaches (posted, judge-scored)

| Score | Approach | Thread |
|-------|----------|--------|
| 86 | 🗞️ Gazette — weekly newspaper boards | winner: lurkers get everything with 0 clicks |
| 81 | 🔎 Browser — ephemeral drill-down kiosk | zero constraint violations; stateless `hb|…` custom_id grammar |
| 78 | 🎛️ Match Board — one message IS the UI | elegant but 38/40 components, no headroom |
| 72 | 🎬 Reel — poster-wall catalog | wow but Pillow-composite-hungry |
| n/a | 🗃️ Ledger — group-by card catalog | GROUPED drill pattern worth stealing |
| n/a | 🎰 Machine — slot machine discovery | Lucky Dip button folds into Front Page |

## Definitive architecture (for the build spec)

**Gazette front-end on Browser back-end**: weekly-thread boards edited in
place (spine) + per-user ephemeral drill-downs (plumbing) + shared render
layer with factoid ladder, emoji slugs, single budget guard (from Board) +
Lucky Dip/Week-in-Charts garnish (from Reel/Machine). Interactions via
gateway INTERACTION_CREATE, respond type 7 (UPDATE_MESSAGE) / ephemeral 64;
defer(6) + PATCH @original when swapping chart attachments. discord.py 2.7.1
LayoutView supports all of it (research: scratchpad research_2.md).

## Investigation trail

- Prior art: `spikes/embed-v2/` (5 static layouts, July 2025) + `match_embed.py`.
- 12-agent workflow: 4 web researchers + 1 data fetcher + 6 designers + 1 judge.
- Judge only received 4/6 designs (prompt truncation) — Ledger/Machine folded
  in manually; doesn't change the winner.
- All smoke tests were self-deleting; the only persistent posts are the
  6 mockup threads + intro + plan message (ids in `spikes/menu-v2/out/posted.json`).
