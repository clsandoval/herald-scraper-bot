# Herald fixture dataset — fetched

## File
`/home/clsandoval/cs/herald-scraper-bot/spikes/menu-v2/fixtures/herald_matches.json` (~1.1 MB)
Shape: `{fetched_at_iso, source_note, matches: [38 raw Stratz match objects], od_rows: [38 matching OpenDota /publicMatches rows]}` — arrays are index-aligned by match.

## Counts
- OpenDota herald rows scanned (avg_rank_tier 10–15): ~150 in main pass + a 119-page deep scan for long games
- Stratz candidates queried: 43; **kept 38** (skipped 5: unparsed / no `networthPerMinute`)
- Duration: min **780s** (13 min) — max **2816s** (47 min)
- Total kills (sum radiantKills+direKills): min **30** — max **118**
- **All 38** matches have `radiantNetworthLeads` AND all 10 players have `stats.networthPerMinute` arrays and `itemPurchases`
- Unique hero ids across dataset: **107**

## Spice
No match hit the strict thresholds (no player with 20+ deaths; no game >3600s — max single-player deaths in the pool was 19, longest kept game 2816s; the two longer candidates 8888291892/8888292884 were unparsed on Stratz). Best "spice-adjacent" picks:
- **8888293313** — 118 total kills, 2816s (longest + bloodiest)
- **8888295980** — 108 kills, 2812s, one player with **19 deaths** (dataset max)
- **8888294804** — 111 kills, 2751s, 18-death player
- **8888295578** — 91 kills, 2807s, 18-death player
- **8888322003** — 91 kills in only 1576s (highest kill density)
- **8888322960** — 90 kills, 14-death player, 1602s

## ID shapes (real examples, from `players[0]` of first three matches)
- `{"heroId": 56, "item0Id": 160, "item1Id": 116, "item2Id": 63, "item3Id": 250, "item4Id": 168, "item5Id": 1858, "neutral0Id": 2097, "lane": "SAFE_LANE", "role": "HARD_SUPPORT", "position": "POSITION_5"}` (match 8888319188)
- `{"heroId": 25, "item0Id": 152, "item1Id": 1858, "item2Id": 911, "item3Id": 108, "item4Id": 48, "item5Id": 141, "neutral0Id": 2190, "lane": "MID_LANE", "role": "CORE", "position": "POSITION_2"}` (match 8888318886)
- `{"heroId": 1, "item0Id": 156, "item1Id": 147, "item2Id": 208, "item3Id": 139, "item4Id": 63, "item5Id": 160, "neutral0Id": 1168, "lane": "SAFE_LANE", "role": "CORE", "position": "POSITION_1"}` (match 8888319337)

Notes for design agents: item ids are ints, empty slots are `0` or `null`; item ids can exceed 1000 (e.g. 1858 = disperser-era ids, neutral ids ~1100–2400); `lane`/`role`/`position` are enum strings; `radiantKills`/`direKills` are per-minute int arrays; `towerDeaths` entries are `{time, isRadiant}`; per-player `stats.networthPerMinute` is an int array (one entry per minute) and `stats.itemPurchases` is `[{time, itemId}]`. Top-level enums seen: `gameMode: "ALL_PICK_RANKED"`, `bracket/rank` ints, lane outcomes like `TIE`/`RADIANT_VICTORY`.

Fetch scripts (reusable): `/tmp/claude-1000/-home-clsandoval-cs-herald-scraper-bot/1f39ddee-1bec-4fb0-afab-386684b668c4/scratchpad/fetch_fixtures.py` and `fetch_spice.py`. Gotcha hit: the Stratz token in spike.env needs `.strip()` before going into the Authorization header (aiohttp rejects it as header injection otherwise).