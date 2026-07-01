# API Bakeoff: OpenDota vs Stratz for a Herald-bracket Dota 2 match bot

**Spike type:** throwaway learning spike. No production code. Probe scripts live in scratchpad; only this doc is committed.
**Date:** 2026-07-01
**Method:** live calls. OpenDota keyless (`https://api.opendota.com/api`). Stratz GraphQL (`https://api.stratz.com/graphql`) with free-tier bearer token + `User-Agent: STRATZ_API`.

> Live-conditions caveat: OpenDota's API origin returned Cloudflare 521/522 for a ~15-min stretch during this spike (frontend `www.opendota.com` stayed up → origin/API outage, not our network). It recovered; all OpenDota numbers below are from live 200s. The public API does flap.

---

## VERDICT

**Use BOTH, split by role: OpenDota for discovery, Stratz for detail.**

- **OpenDota** is the only one that exposes a *stream of recent public match IDs with rank tier* (`/publicMatches`). Stratz has no public-match firehose.
- **Stratz** is the only one that reliably returns *granular per-minute / time-series data* for ordinary Herald pubs. On OpenDota those same matches are **unparsed** (no time-series at all).

Neither alone suffices. OpenDota alone can't answer time-window questions (pubs unparsed). Stratz alone can't discover which matches exist.

---

## Q1 - DISCOVERY (Herald match IDs at volume?)

### OpenDota - YES, the discovery engine
- `GET /publicMatches` returns 100 records/page. **`avg_rank_tier` IS present** (average of the 10 players' tiers).
- Pagination: `?less_than_match_id=<lowest match_id from prev page>`. Confirmed working.
- **Measured yield (live, 8 pages = 800 matches spanning ~24 min of starts):**
  - Bucket dist (tens digit of `avg_rank_tier`; 1=Herald..7=Divine): `{Herald:34, Guardian:95, Crusader:167, Archon:216, Legend:164, Ancient:87, Divine:37}`
  - **Herald ~4.2%** (34/800). A separate single page gave 3/100.
  - 800 matches over ~24 min => feed surfaces **~2,000 matches/hr**, of which **~86 Herald/hr (~2,000/day)**.
  - `/publicMatches` is a *sampled* feed, not literally every match - so this is the ceiling on what OpenDota hands you, a floor on true game activity.
- Filter: keep rows where `avg_rank_tier` in 10-15 (strict Herald medal); 10-19 is the looser whole-tens bucket.

### Stratz - NO public-match stream
- Root query type `DotaQuery` exposes `match(id)` and `matches(ids)` but **no recent/public list**.
- `matches(ids:[...])` is **admin-only** on the free token (`"User is not an admin."`) AND capped at **10 IDs** (`"Max Request Size 10"`). So you fetch **one match per call** via `match(id)`.
- Rank enums exist (`RankBracket`: HERALD/GUARDIAN/...; `RankBracketBasicEnum` lumps `HERALD_GUARDIAN`) but only parameterize **aggregates** (`heroStats.*`) and **per-player history** (`player.matches(request)`), not a global feed.
- Conclusion: **Stratz cannot originate Herald match IDs**; it only enriches IDs you already have.

**Answer:** OpenDota `/publicMatches`, filter `avg_rank_tier` 10-15. Realistic yield ~**80-90 Herald/hr (~2k/day)** from the sampled feed.

---

## Q2 - GRANULARITY (full detail from both, no manual parse requested)

**Test match:** `8875698195` (Herald, from the feed).

### OpenDota `/matches/{id}` - UNPARSED (decisive limitation)
Checked **15 fresh Herald matches: every one unparsed** (`version: null`).

Unparsed OD match gives (final-state only): `radiant_win`, `duration`, `first_blood_time`, `tower_status_*`/`barracks_status_*` bitmasks, `picks_bans`, scores; per player final K/D/A, `net_worth`, `gpm/xpm`, `last_hits/denies`, final items, `hero_damage`, `tower_damage`, `rank_tier`, `ability_upgrades_arr`.

Unparsed match gives **NONE** of: `gold_t`/`xp_t`/`lh_t` curves, `objectives`, `teamfights`, `purchase_log`/`kills_log`/`runes_log`/`obs_log`, `lane`/`lane_role`, `radiant_gold_adv`/`radiant_xp_adv` - all null.

`POST /request/{match_id}` force-parses (returns `jobId`, confirmed 200) but is async (seconds-to-minutes, can fail if replay gone) and **spends your own quota per match**. Parsing ~2k/day = the whole daily budget.

### Stratz `match(id)` - FULLY PARSED for the same match
The exact match OD called unparsed came back from Stratz **already parsed**:
- `radiantNetworthLeads` (13 pts), `radiantExperienceLeads` (13 pts) - per-minute gold/xp lead curves.
- `towerDeaths` (20, with `time`,`isRadiant`), `chatEvents` (25), `firstBloodTime`.
- Lane outcomes: `top/mid/bottomLaneOutcome` (e.g. `DIRE_STOMP`).
- Per player: `lane` (OFF_LANE), `role` (LIGHT_SUPPORT), `position` (POSITION_4), plus `stats { networthPerMinute[], goldPerMinute[], lastHitsPerMinute[], itemPurchases[{time,itemId}], killEvents[], deathEvents[], runes[], wards, ... }`.
- e.g. player0 `networthPerMinute = [602,908,1088,1268,1333,1513,...]`; `itemPurchases` with negative `time` (pre-horn buys).

### Coverage / freshness (34 OD Herald IDs re-queried on Stratz, one-by-one)
- **23/34 (68%) present in Stratz, 100% of those parsed** (all had time-series).
- The 11 missing were the *freshest* IDs (seconds old / `duration:0`) - Stratz ingest lag, not a coverage gap. Re-query minutes later picks most up.

**Answer:** Stratz exposes the granular time-series for exactly the pubs OpenDota shows unparsed. **Per-match time-window slicing is FEASIBLE via Stratz**, effectively **infeasible via OpenDota alone**.

### Rank mapping note (store both - they disagree)
- OD `avg_rank_tier` = average of 10 players -> an OD-Herald-avg match often maps to Stratz `rank` in the 20s (Guardian). Example: OD avg 13 -> Stratz `rank` 20.
- Stratz `rank` = medal*10+stars (13/14 = Herald, 20-23 = Guardian). Stratz `bracket` (Byte) = medal index: **1=Herald, 2=Guardian, 3=Crusader**.
- Stratz `bracket` dist over the OD-Herald sample: `{1(Herald):7, 2(Guardian):15, 3(Crusader):1}`. OD's Herald-*average* filter is fuzzy; for strictly-Herald *matches*, re-filter on Stratz `bracket == 1` after enrichment.

---

## Q3 - RATE LIMITS / COST

### OpenDota (live headers + docs)
- Live: `x-rate-limit-remaining-minute: 59` (=> **60/min**), `x-rate-limit-remaining-day: ~2968`.
- Docs: keyless/free = 60 req/min; with a free API key, **50,000 calls/month** (daily header reflects the anonymous throttle). Premium = unlimited at higher rates, **per-call billing above 50k/mo** (card required).
- `POST /request/{id}` counts against the same budget, async.

### Stratz (response headers, direct)
- `x-ratelimit-limit-second: 8`, `-minute: 150`, `-hour: 1500`, `-day: 15000`.
- Free token: `matches(ids)` admin-only + 10-id cap => fetch **1 match/call** via `match(id)`.

### What limits mean for ingestion
- Discovery cheap: 1 `/publicMatches` call = 100 matches. Whole feed ~20 OD calls/hr - trivial vs 60/min.
- Enrichment is the bottleneck: **1 Stratz call per Herald match**. ~86/hr => ~2k/day => ~13% of Stratz 15k/day. Day-cap only bites above ~15k enrichments/day (~7x observed Herald volume).
- Steady state: capture all Herald the OD feed surfaces (~2k/day) end-to-end within free tiers, with backfill headroom.

---

## Feasibility of per-match time-slice modeling

**YES (via Stratz), small freshness caveat.**
- Time-window questions ("who led at 10 min", "net worth swing 15-25 min", "when did T1 mid fall") answerable from `radiantNetworthLeads`/`radiantExperienceLeads`, per-player `networthPerMinute`/`goldPerMinute`, `itemPurchases[].time`, `towerDeaths[].time`, `chatEvents[].time`.
- Enrich on a short delay (a few min after the match appears) so Stratz has parsed it. ~68% ready immediately; retry misses.
- Pure-OpenDota is **partial at best** and only by paying per-match parse cost - not viable at volume.

---

## Proposed minimal schema sketch (honest to the APIs)

```
matches
  match_id             BIGINT PK        -- OD match_id / Stratz id (same value)
  start_time           INT              -- OD start_time (epoch)
  duration_s           INT
  radiant_win          BOOL
  game_mode            INT
  region               INT
  od_avg_rank_tier     SMALLINT         -- averaged; discovery filter (10-15 = Herald avg)
  stratz_rank          SMALLINT         -- medal*10+stars (13/14 = Herald)
  stratz_bracket       SMALLINT         -- 1=Herald,2=Guardian,3=Crusader  <- strict Herald filter
  first_blood_time     INT
  tower_status_radiant INT              -- bitmask
  tower_status_dire    INT
  parsed               BOOL             -- Stratz parsedDateTime IS NOT NULL
  enriched_at          TIMESTAMP
  ingested_at          TIMESTAMP

match_players
  match_id             BIGINT FK
  player_slot          SMALLINT
  steam_account_id     BIGINT NULL      -- often anonymized (0) in Herald pubs
  hero_id              SMALLINT
  is_radiant           BOOL
  kills/deaths/assists SMALLINT
  net_worth            INT
  gpm/xpm              INT
  last_hits/denies     INT
  lane                 TEXT NULL        -- Stratz: OFF_LANE/MID/SAFE
  role                 TEXT NULL        -- Stratz: CORE/LIGHT_SUPPORT/...
  position             TEXT NULL        -- Stratz: POSITION_1..5
  items                INT[6]           -- final item ids
  PRIMARY KEY (match_id, player_slot)

match_timeseries         -- one row/match, Stratz-sourced
  match_id                BIGINT PK FK
  radiant_networth_leads  INT[]         -- per-minute gold lead
  radiant_xp_leads        INT[]         -- per-minute xp lead

player_timeseries        -- one row/(match,player)
  match_id             BIGINT
  player_slot          SMALLINT
  networth_per_min     INT[]
  gold_per_min         INT[]
  last_hits_per_min    INT[]
  PRIMARY KEY (match_id, player_slot)

match_events             -- flattened event log (Stratz)
  match_id             BIGINT
  event_type           TEXT             -- tower_death|item_purchase|kill|rune|chat
  time_s               INT              -- can be negative (pre-horn)
  actor_slot           SMALLINT NULL
  detail               JSONB            -- {itemId} / {npcId,isRadiant} / {rune} / {value}
```

Notes:
- `steam_account_id` frequently anonymized (0) in Herald pubs - don't key on it.
- Arrays-as-columns is the lean choice; normalize `*_timeseries` to per-minute rows only if you need SQL window queries on minutes.
- Discover on OD (`od_avg_rank_tier`), confirm strict Herald on `stratz_bracket == 1`.

---

## Rate-limit-driven ingestion notes

- **Discovery loop:** poll `/publicMatches` every ~2-3 min (paginate a few pages), dedupe by `match_id`, keep `avg_rank_tier` 10-15. ~20 OD calls/hr. Negligible.
- **Enrichment queue:** per new Herald ID, wait ~2-5 min then one Stratz `match(id)` call. ~86/hr => ~2k/day, ~13% of Stratz 15k/day cap.
- **Backpressure:** Stratz caps 8/s, 150/min. Token-bucket at ~2-3 req/s stays safe and drains fast.
- **Retries:** re-queue Stratz `null` (fresh) responses with backoff; ~30% need one retry.
- **OpenDota flakiness:** wrap `/publicMatches` in retry-with-backoff - origin 5xx (521/522) happens.
- **Ceiling:** capture the whole Herald slice (~2k/day) end-to-end within free tiers, with backfill room to Stratz 15k/day.

---

## Confidence & unknowns

| Claim | Confidence | Basis |
|---|---|---|
| OD /publicMatches has avg_rank_tier + paginates | High | live calls |
| Herald ~3-4% of feed; ~80-90/hr | Med-High | 800-match sample, one time window |
| OD pubs unparsed (no time-series) | High | 15/15 fresh Herald unparsed |
| Stratz returns parsed time-series for same matches | High | same id both sources |
| Stratz has no public-match discovery feed | High | full root introspection |
| Stratz free token 8/s,150/m,1500/h,15000/d | High | response headers |
| Stratz bracket=1 is Herald | High | enum + live data |
| OpenDota 60/min, 50k/month w/key | High | live headers + docs |

Still unknown:
- Herald yield across time-of-day / region (one 24-min window only).
- Stratz parse-latency tail (68% ready in minutes; tail untimed).
- Steam-account anonymization rate in Herald (affects per-player tracking).
- OpenDota API uptime (~15 min down this session; unquantified).
- Whether `player.matches(request)` + seeded Herald steam IDs is a viable *secondary* Stratz discovery fallback if OD is down.
