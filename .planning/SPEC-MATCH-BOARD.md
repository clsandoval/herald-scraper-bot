# SPEC: The Match Board

Status: validated by live spike 2026-07-10 (user click-tested). Reference
implementation: `spikes/menu-v2/live_board.py` — treat it as the source of
truth for layout/behavior; this doc adds the production requirements the
spike deliberately skipped.

## Product statement

One pinned Discord message IS the entire UI for browsing a week of Herald
matches. Menu-only, zero AI framing. Every click morphs the message in place.
Data: ~2k Herald matches/week in Postgres (OpenDota discovery → Stratz
enrichment, per api-bakeoff spike).

## Views (all validated with the user)

### 1. Hub (default) — the control hub
- Header: `## 🎛️ MATCH BOARD` + `-# {n} matches · {date}[ · filters: {k}][ · {bucket}]`
- **7 match rows per page** (component cap forces exactly 7), each a Section:
  - line 1: `**{kills}** kills · `{mm:ss}``
  - line 2: ten hero emojis, `{radiant5} ⚔ {dire5}`
  - thumbnail accessory: mini net-worth-lead PNG (`charts.thumb_spark_png`)
  - NO per-row buttons (user-rejected), no badges, no side emoji
- Controls, all visible on page one (user requirement — no navigating to
  reach controls):
  - Sort select — 12 options
  - Filters **multi-select** (`min_values=0, max_values=all`) — 12 options
  - Group-by select — 16 options
  - Open-a-match select — the 7 visible rows
  - Nav row: `◀` `{page}/{pages} ▶` `🎲` `⚙️ Advanced`
- Budget: 38–39/40 components. THERE IS NO HEADROOM — adding any control
  means removing one or dropping a row.

### 2. Match view (user: "perfect — don't change")
- Header: `## Match {id} · {🟢/🔴 win} · {mm:ss} · 🟢 {k} — {k} 🔴`
- Radiant block then Dire block, players sorted by net worth desc, one glance
  line each: `{hero emoji} `{k:>2}/{d:>2}/{a:>2}` {six item emojis}`
  (missing emoji → `▫`)
- Full net-worth-lead chart embedded below the rows (`charts.networth_lead_png`).
  NO separate graph screen (user-removed).
- Buttons: `◀ Board` `🎲` `OpenDota` (link)

### 3. Grouped view
- Reached via Group-by. Aggregate rows (top ~10 buckets by size), a re-group
  select, an "Open a bucket" drill select (drilling = set bucket filter,
  return to hub), `◀ Board`.
- Hero grouping is per-player expansion: `{emoji} **{hero}** · {n} games ·
  {win}% win · {avg deaths} avg deaths`; other dims bucket whole matches.

### 4. Advanced search (modal)
- `⚙️ Advanced` opens a native modal, 4 text fields:
  `Min duration (minutes)` · `Min total kills` ·
  `Heroes (comma separated, all must play)` · `Items (name xCount)`
- Result: exact matches as hub rows; if 0 exact → `0 exact matches · showing
  3 closest` ranked by criteria satisfied. Buttons `⚙️ Edit search` `✕ Clear`.
- Modal submit MUST use `defer()` + `message.edit()` (response.edit_message
  from modal submit is the fragile path).

## Copy rules (user-enforced, hard)

- NO flavor text anywhere: no select option descriptions, no legends, no snark.
- Every option label states its exact criterion + live count:
  `Gold lead never passed 5k (7)`, never `Close game`.
- Buckets show their cuts in the label: `Game length (<20 / 20-30 / 30-40 / 40+)`.

## Sorts / filters / group-bys

Exact labels and predicates live in `live_board.py` `SORTS` / `FILTERS` /
`GROUPS` tables — implement from those. Counts in filter labels are computed
from the live dataset at render time. The option sets are deliberately
over-broad; prune from usage, don't add.

## Platform constraints (all verified live 2026-07-10)

- Components V2 (flag 32768): ≤40 components/message counting nesting +
  Section accessories; ≤4000 chars across TextDisplay content (select option
  text is EXEMPT — verified); no nested Containers; Section = 1–3 TextDisplays
  + accessory; MediaGallery ≤10 items; ≤10 attachments/message; select ≤25
  options; a select and a button cannot share an ActionRow.
- discord.py 2.7.1 `LayoutView`: lib enforces the 40 cap; check
  `content_length() ≤ 4000` yourself; explicit `custom_id` on EVERY component
  (auto-ids break persistence); `bot.add_view()` for restart survival.
- Charts: matplotlib PNGs attached via `attachment://name.png`; palette
  Radiant `#3BA55D` / Dire `#ED4245` on `#313338` (colorblind-validated);
  renderers in `spikes/menu-v2/charts.py` (full, sparkline, thumb).
- Icons: application emojis (264 seeded, map in
  `spikes/menu-v2/assets/emoji_map.json`, idempotent `emoji_sync.py`); 2000
  cap; 256KB source limit (4 known oversize items fall back to `▫`); hero CDN
  `heroes/{name}.png` + `heroes/icons/{name}.png` only — `_sb.png` is dead.

## Production requirements (spike → real deltas)

1. **Concurrency**: spike is one shared board — production gives each
   clicking user their own **ephemeral** board instance (interaction response
   flags 64); an optional public pinned board stays read-only/curated.
2. **Statelessness**: encode `{mode, sort, filters, group, bucket, page,
   match}` in `custom_id`s (≤100 chars) so restarts and the 15-min token
   window are non-events. No session table.
3. **Data**: Postgres tables per api-bakeoff schema (`matches`,
   `match_players`, `match_timeseries.radiant_networth_leads`). The board
   needs ONLY: match summary, per-player (hero, K/D/A, gpm, networth, items,
   position), leads array, tower_deaths count.
4. **Thumbnail cache**: mini-chart PNGs cached keyed by match_id (they never
   change once a match is final).
5. **Hero/item long tail**: top-25-by-frequency in selects; anything else via
   the Advanced modal's typed fields. No paginated hero selects in v1.
6. **Scope guard**: no auto-posting; the board posts once and edits in place.
   The NL/agent layer is a later, invisible addition behind @mention.

## Open items (decide during phase planning)

- Weekly rollover: new board message per ISO week vs. one eternal board.
- Whether the public pinned board exists in v1 or everything is ephemeral.
- `stomp` filter predicate ("one side led start to finish") is a weak proxy
  (`max_lead ≤ 2000 or min_lead ≥ -2000`) — tighten with sign-consistency of
  the leads array.
