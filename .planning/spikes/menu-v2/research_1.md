# Dota 2 static data + image assets — verified 2026-07-10

## 1. dotaconstants (github.com/odota/dotaconstants)
Raw URL pattern (verified 200): `https://raw.githubusercontent.com/odota/dotaconstants/master/build/{file}.json`

Files in `build/` (from GitHub contents API): `abilities.json, ability_ids.json, aghs_desc.json, ancients.json, chat_wheel.json, cluster.json, countries.json, game_mode.json, hero_abilities.json, hero_lore.json, heroes.json, item_colors.json, item_ids.json, items.json, lobby_type.json, neutral_abilities.json, order_types.json, patch.json, patchnotes.json, permanent_buffs.json, player_colors.json, region.json, skillshots.json, xp_level.json`

- **`hero_names.json` does NOT exist** (404 on raw and on OpenDota mirror). Use `heroes.json` (keyed by numeric-string id) or `hero_abilities.json` (keyed by `npc_dota_hero_*`).
- **patch data is `build/patch.json`** (not `patchnotes/patch.json`); it's an array of `{name, date, id}`. Last entries: `7.39` (2025-05-22, id 58), `7.40` (2025-12-16, id 59), `7.41` (2026-03-24, id 60). `patchnotes.json` is per-patch changelists.

**heroes.json** entry shape (keyed `"14"`): `{id, name: "npc_dota_hero_pudge", primary_attr ("str"/"agi"/"int"/"all"), attack_type, roles[], img: "/apps/dota2/images/dota_react/heroes/pudge.png?", icon: "/apps/dota2/images/dota_react/heroes/icons/pudge.png?", base_health, base_mana, base_armor, base_mr, base_attack_min/max, base_str/agi/int, str_gain/agi_gain/int_gain, attack_range, projectile_speed, attack_rate, base_attack_time, attack_point, move_speed, turn_rate, cm_enabled, legs, day_vision, night_vision, localized_name}`. `img`/`icon` are CDN-relative paths ending in `?`.

**items.json** keyed by canonical name (`"blink"`), entry keys: `abilities, hint, id, img, dname, qual, cost, behavior, notes, attrib, mc, hc, cd, lore, components, created, charges` (+ `tier` 1-5 on neutral items). Example: blink → `img: "/apps/dota2/images/dota_react/items/blink.png?t=1593393829403", dname: "Blink Dagger", qual: "component", cost: 2250, cd: 15, components: null, created: false`. `qual` values + counts: null 272, artifact 22, common 20, component 56, consumable 30, `consumable;laning` 1, epic 35, rare 52, secret_shop 13.
Gotcha: **key ≠ display name** for newer items: Khanda is key `angels_demise` (cost 5600), Parasma is key `devastator` (cost 5975).

**item_ids.json**: flat `{"1": "blink", ...}`, 596 entries, highest ids 4204–4206 `famango/great_famango/greater_famango` (Healing Lotus) and 4300–4302 `ofrenda*`. **ability_ids.json**: flat `{"5003": "ability_name"}`, 3150 entries (same format the repo already uses locally).

## 2. OpenDota constants mirror
`https://api.opendota.com/api/constants/{resource}` — resource = any `build/` filename minus `.json`. Verified 200 today: `heroes, items, item_ids, ability_ids, hero_abilities, patch, patchnotes, game_mode`. The bare index `https://api.opendota.com/api/constants` returns `{"error":"Not Found"}` — there is no listing endpoint; enumerate from the GitHub repo. `constants/hero_names` → 404.

## 3. Image CDN (hotlinkable, all verified with real fetches today)
Base: `https://cdn.cloudflare.steamstatic.com` (prepend to `img`/`icon` paths from heroes.json/items.json).

| URL pattern | Status | Dimensions |
|---|---|---|
| `/apps/dota2/images/dota_react/heroes/{name}.png` (pudge, largo) | 200 | **256x144** PNG (~65-70 KB) |
| `/apps/dota2/images/dota_react/heroes/icons/{name}.png` (pudge, largo) | 200 | **32x32** PNG |
| `/apps/dota2/images/dota_react/heroes/crops/{name}.png` (pudge) | 200 | **400x250** PNG |
| `/apps/dota2/images/dota_react/heroes/{name}_sb.png` | **404** — `_sb` does not exist under dota_react | — |
| `/apps/dota2/images/dota_react/items/{name}.png` (blink, essence_distiller, dagger_of_ristul, madstone_bundle) | 200 | **88x64** PNG (some 87x64) |
| Legacy `/apps/dota2/images/heroes/{name}_sb.png` (pudge, kez, largo) | 200 | **59x33** — still maintained, includes 2024-2026 heroes |
| Legacy `/apps/dota2/images/heroes/{name}_lg.png` | 200 | **205x115** |
| Legacy `/apps/dota2/images/heroes/{name}_full.png` | 200 | **256x144** |

`{name}` = hero `name` minus `npc_dota_hero_` prefix; item URL name = items.json key (so Khanda's icon is `items/angels_demise.png`). All fine as Discord embed thumbnail/author-icon URLs.

## 4. New content since early 2024 (a 2023-era list misses all of this)
**Heroes** (ids verified in heroes.json; ids are non-contiguous):
- **Ringmaster — id 131** (`npc_dota_hero_ringmaster`, localized "Ring Master" in dotaconstants) — released Aug 2024.
- **Kez — id 145** (`npc_dota_hero_kez`) — released Nov 2024.
- **Largo — id 155** (`npc_dota_hero_largo`) — the 127th hero, released with patch 7.40 on 2025-12-16 ([announcement](https://www.dota2.com/newsentry/533243594419470467)). No other new heroes through July 2026.

**Current patch: 7.41** (2026-03-24), latest letter patch **7.41d** ([dota2.com/patches](https://www.dota2.com/patches)). Major 7.40/7.41 mechanics: 7.40 reworked talents (separate point system, no longer traded vs ability levels); **7.41 REMOVED facets entirely** and made innates fixed/level-scaled ([7.41 notes](https://www.dota2.com/newsentry/512986184073347348)).

**Items a stale list misses**: Blood Grenade (50g), Diadem (1000g), Cornucopia (1200g), Pavise (1350g), Tiara of Selemene (1700g), Harpoon (4700g), Disperser (6100g), Khanda (`angels_demise`, 5600g), Parasma (`devastator`, 5975g), Roshan's Banner, Healing Lotuses (`famango` keys, replace mangoes on map).

**Neutral item system (7.38 "Wandering Waters", Feb 2025)**: fixed neutral-item *drops are gone*. Neutral creeps drop **Madstones** (currency, capped ~5/15/25/35/45 by minute 5/15/25/35/60); players **craft** a neutral by combining an **Artifact** (active/passive, e.g. `dagger_of_ristul`) + an **Enchantment** (stat rider). items.json has 49 tiered neutral entries plus `madstone_bundle`. Any 2023-era neutral-item logic (tier drop timings, old items like Trusty Shovel) is obsolete.

## 5. Counts (emoji budget)
- **Heroes: 127** (heroes.json length; max id 155).
- **Purchasable items: ~208** (entries with `cost>0`, non-`recipe_*`, `tier==null`, has `dname`); items.json total 501 entries incl. recipes/neutrals/event junk; 49 neutral (tiered) items.
- 127 + 208 ≈ 335 emojis — exceeds per-server emoji slots (50 base) but fits Discord **application-owned emojis (limit 2000 per app)**, usable by the bot in any server.

## 6. Facets
- **In dotaconstants: yes** — `build/hero_abilities.json` per hero: `{abilities[], facets[], talents[]}`; facet entry: `{id, name, icon, color, gradient_id, title, description, deprecated?}`. 339 facet entries total, **289 flagged `"deprecated": "true"`** (facets removed from game in 7.41; kept for historical data).
- **OpenDota**: per-player match field **`hero_variant`** (1-indexed facet slot). Verified: an older match returned `hero_variant: 2`; a fresh patch-60 (7.41) match (id 8888363713) returns `hero_variant: 0`. So it only carries signal for pre-7.41 matches.
- **Stratz**: historically exposed the chosen facet on `MatchPlayerType` (field `variant`), but I could not verify against the live schema (GraphQL introspection at api.stratz.com/graphql requires an API token) — verify with token if needed. Since 7.41 removed facets, this only matters for matches before 2026-03-24; for the Herald bot's "recent matches" window (today) facets are irrelevant.

Sources: [Largo + 7.40 announcement](https://www.dota2.com/newsentry/533243594419470467), [7.41 Gameplay Patch](https://www.dota2.com/newsentry/512986184073347348), [7.41d](https://www.dota2.com/newsentry/672870947178414450), [Dota Patch Notes page (7.41d current)](https://www.dota2.com/patches), [Madstone crafting explainer](https://esports.gg/news/dota-2/dota-2-patch-7-38-madstone/), [Neutral items 7.39](https://pickem-mongolia.com/news/dota2-neutral-items/), plus direct fetches of raw.githubusercontent.com/odota/dotaconstants, api.opendota.com, and cdn.cloudflare.steamstatic.com performed 2026-07-10.