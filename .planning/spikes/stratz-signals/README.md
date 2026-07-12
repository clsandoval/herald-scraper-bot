---
spike: stratz-signals
name: unexploited-stratz-fields
type: standard
validates: "Given 25 review-worthy Herald matches fetched with every candidate field, when fill rate / payload / content are inspected, then each field gets a KEEP / SKIP / HEAVY verdict"
verdict: VALIDATED
related: [skill-weirdness, api-bakeoff]
tags: [api, stratz, enrichment]
---

# Spike: Unexploited Stratz Fields

One aliased 25-match probe (1 rate-limit unit) with all candidate fields;
25 matches biased toward weird/bloody/new. Code: `spikes/stratz-signals/`
(probe.py runs on prod, analyze.py local, probe_result.json = evidence).

## Verdicts

| Field | Verdict | Evidence |
|---|---|---|
| `allTalks` | **KEEP** | 640 B/match; 28% of players talk; real text ("значит беру рапиру… ладно не беру"). The comedy signal. |
| `deathEvents` | **KEEP (slimmed)** | 33 KB/match full — fetch only `time timeDead goldFed goldLost isDieBack isAttemptTpOut hasHealAvailable`. 22-min-dead / 16k-gold-fed players confirmed real. |
| `barracksStatusRadiant/Dire` | **KEEP** | 1 byte; mega-creep games detected in probe (racks=0). |
| `goldSpent` | **KEEP** | scalar; networth−goldSpent = died-rich receipts. |
| `isRandom` | **KEEP** | 2/250 randomed — rare, perfect receipt. |
| `courierKills` | **KEEP** | 66 B; 25% fill. |
| `itemUsed` | **KEEP** | 3.7 KB; enables unused-BKB / Midas-efficiency receipts. |
| `wards` | **KEEP** | 3.6 KB; 73% fill; 1-ward-support receipts. |
| `chatWheels` | **KEEP** | 1.6 KB; 52% fill, 1,172 events in 25 matches; needs dotaconstants chat_wheel.json for phrases. |
| `pickBans` | **KEEP** | 1.7 KB; fetch `isPick heroId order isRadiant` only (skip win-rate opinion subfields per own-IP rule). |
| `level` (per-min) | **KEEP** | 1.6 KB; underleveled receipts. |
| `campStack`, `tripsFountainPerMinute` | **KEEP** | 2.2 KB each (per-minute arrays); zero-stacks + walks-home receipts. |
| `matchPlayerBuffEvent` | **KEEP** | 151 B; aegis held/wasted. |
| `runes` | SKIP | 4.5 KB for a weak receipt story. |
| `chatEvents` (match) | SKIP | 5.3 KB of numeric enums; text chat already in allTalks. |
| `invisibleSeconds` | SKIP | **broken** — values up to 211,600 s in a ≤2 h game. |
| `behavior` | SKIP | 96% zero, semantics opaque. |
| `heroAverage` | SKIP | Stratz aggregate baselines — adjacent to opinion fields; corpus-relative stats are our IP. |
| `locationReport`, `inventoryReport` | HEAVY | untested by design; revisit only with a concrete feature. |

## Payload math

All KEEPs with slimmed deathEvents ≈ **+25–35 KB per match raw** (~+70 MB on a
2.2k corpus, 5 GB volume — fine). Request cost unchanged: same 1 unit per
25-match aliased batch.

## Notes / gotchas

- Herald all-chat is heavily Russian; receipts should show the raw text, not
  translate.
- Diebacks were 0 across all 25 matches — Heralds don't buy back; keep the
  flag anyway (free) for the day one does.
- After adding fields to STRATZ_FIELDS, a re-enrich sweep only helps future
  matches unless run corpus-wide — and ANY sweep must be followed by
  `--weirdness` (both weirdness columns are nulled by re-upsert).

## Signal for the Build

Add the KEEP set to STRATZ_FIELDS, then: chat receipts (allTalks excerpts on
focus view), time-dead/gold-fed receipts, mega-comeback filter
(barracks == 0 + loser had megas), unused-BKB receipts, randomed-hero tag.
Vendor dotaconstants chat_wheel.json for chatWheel phrases.
