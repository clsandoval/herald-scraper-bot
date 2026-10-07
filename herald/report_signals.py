"""Small, factual review hooks from detail already fetched by the reporter.

These are observations, not a ranking or a claim that a build is off-meta.
The menu's corpus-relative experiments remain in ingest.py. Missing logs never
mean zero uses, no skill points, or an empty inventory. No network or DB access.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path

from . import ability_names, render


RAPIER_ID = 133
BKB_ID = 116
MIDAS_ID = 65
SMOKE_ID = 188
EARLY_SKILL_PICKS = 8
_ABILITY_NAMES = json.loads(
    (Path(__file__).parent / "assets" / "ability_ids.json").read_text()
)


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _events(value):
    return [event for event in value if isinstance(event, dict)] if isinstance(value, list) else []


def _time(event, duration):
    value = event.get("time")
    return value if duration > 0 and _number(value) and 0 <= value <= duration else None


def _inventory(player):
    keys = [f"item{i}Id" for i in range(6)]
    items = [player[key] for key in keys if _id(player.get(key))]
    if items:
        return items
    # NULL is an empty inventory slot in STRATZ; an absent key is unknown.
    if all(key in player and player[key] in (None, 0) and not isinstance(player[key], bool)
           for key in keys):
        return []
    return None


def _skill_ids(player):
    events = player.get("abilities")
    if not isinstance(events, list):
        return None
    # Never silently delete an unknown pick then relabel later picks as an opening.
    if any(not isinstance(e, dict) or not isinstance(e.get("isTalent"), bool)
           or isinstance(e.get("abilityId"), bool)
           or (e.get("isTalent") is False and e.get("abilityId") is None)
           or (e.get("abilityId") not in (None, 0) and not _id(e.get("abilityId")))
           for e in events):
        return None
    picks = [e for e in events if e.get("isTalent") is False and _id(e.get("abilityId"))
             and not _ABILITY_NAMES.get(str(e["abilityId"]), "").startswith("special_bonus_")]
    # STRATZ documents chronological order. Sort when timestamps are complete;
    # stable sorting keeps simultaneous banked-point picks in provider order.
    if picks and all(_number(e.get("time")) for e in picks):
        picks = sorted(picks, key=lambda e: e["time"])
    return [e["abilityId"] for e in picks]


def ability_name(ability_id, hero_id):
    """Pinned English label, with existing fallbacks for missing/new abilities."""
    name = _ABILITY_NAMES.get(str(ability_id))
    if not name:
        return f"Ability {ability_id}"
    label = ability_names.localized_name(name)
    if label:
        return label
    return name.removeprefix(render.hero_short(hero_id) + "_").replace("_", " ").title()


def _death_events(stats, duration):
    by_time = {}
    for event in _events(stats.get("deathEvents")):
        time = _time(event, duration)
        if time is not None:
            # One player's duplicate death entry must not create a dieback streak.
            by_time.setdefault(time, event)
    return sorted(by_time.items())


def _player_observations(player, duration, skills, items):
    stats = player.get("stats") if isinstance(player.get("stats"), dict) else {}
    deaths = _death_events(stats, duration)
    purchases = sorted({(time, event["itemId"])
                        for event in _events(stats.get("itemPurchases"))
                        if _id(event.get("itemId"))
                        and (time := _time(event, duration)) is not None})
    out = []
    rapiers = [time for time, item in purchases if item == RAPIER_ID]
    if rapiers:
        # Temporal coincidence is the claim, never that this rapier was dropped.
        quick_death = next(((buy, death) for buy in rapiers for death, _ in deaths
                            if 0 <= death - buy <= 90), None)
        if quick_death:
            buy, death = quick_death
            out.append(f"Divine Rapier bought {_clock(buy)}; died {int(death - buy)}s later")
        else:
            times = ", ".join(_clock(time) for time in rapiers[:3])
            suffix = f" (+{len(rapiers) - 3} more)" if len(rapiers) > 3 else ""
            out.append(f"Divine Rapier purchases: {times}{suffix}")

    for flag, label in (("isDieBack", "Buyback then died"),
                        ("isAttemptTpOut", "Died attempting TP")):
        times = [time for time, event in deaths if event.get(flag) is True]
        if len(times) >= 2:
            out.append(f"{label} ×{len(times)}: " + ", ".join(_clock(t) for t in times[:3]))

    # Merge known death intervals and clip at match end: duplicates or a final
    # respawn timer cannot turn 80 minutes of play into 90 minutes spent dead.
    intervals = [(time, min(duration, time + event["timeDead"]))
                 for time, event in deaths if _number(event.get("timeDead"))
                 and event["timeDead"] > 0]
    dead = 0
    end = 0
    for start, stop in intervals:
        dead += max(0, stop - max(start, end))
        end = max(end, stop)
    if duration > 0 and dead / duration >= .30:
        out.append(f"Recorded dead time: {_clock(dead)} ({dead / duration:.0%} of match)")

    # Require an explicit, unambiguous count. An absent itemUsed entry, a null
    # log, or a conflicting duplicate is not evidence that the item was unused.
    usage = {}
    for event in _events(stats.get("itemUsed")):
        item, count = event.get("itemId"), event.get("count")
        if _id(item):
            usage.setdefault(item, []).append(count)
    bought = {item for _, item in purchases}
    for item in (BKB_ID, MIDAS_ID):
        counts = usage.get(item, [])
        if (item not in bought or not counts or
                not all(_number(n) and n >= 0 and n == int(n) for n in counts)
                or len(set(counts)) != 1):
            continue
        uses = int(counts[0])
        if item == BKB_ID and uses == 0:
            out.append("BKB purchased; 0 recorded uses")
        elif item == MIDAS_ID and uses < 10:
            out.append(f"Hand of Midas purchased; {uses} recorded uses")

    smoke = usage.get(SMOKE_ID, [])
    if (smoke and all(_number(n) and n >= 10 and n == int(n) for n in smoke)
            and len(set(smoke)) == 1):
        # A display threshold, not a claim about rarity or intent.
        out.append(f"Smoke of Deceit: {int(smoke[0])} recorded uses")

    midas = [time for time, item in purchases if item == MIDAS_ID]
    if midas and midas[0] >= 30 * 60:
        out.append(f"First recorded Hand of Midas purchase: {_clock(midas[0])}")

    for item, count in Counter(items or []).items():
        if count >= 2 and (render._item_by_id.get(item, {}).get("cost") or 0) >= 1000:
            out.append(f"Final inventory: {count}× {render.item_name(item)}")
    if skills and len(skills) >= 3 and len(set(skills[:3])) == 1:
        out.append("First 3 non-talent picks: " + ability_name(skills[0], player.get("heroId")))
    if player.get("isRandom") is True:
        out.append("Randomed hero")
    return out


def _match_observations(raw, opendota, duration):
    out = []
    winner = opendota.get("radiant_win")
    if isinstance(winner, bool):
        side = "Radiant" if winner else "Dire"
        racks = opendota.get("barracks_status_radiant" if winner else "barracks_status_dire")
        if type(racks) is int and racks == 0:
            out.append(f"{side} won with all six of their barracks destroyed")
        leads = opendota.get("radiant_gold_adv")
        if isinstance(leads, list):
            values = [value for value in leads if _number(value)]
            deficit = max([0, *(-value if winner else value for value in values)])
            if deficit >= 8000:
                out.append(f"{side} won after trailing by {int(deficit):,} gold")

    for radiant, label in ((True, "Radiant"), (False, "Dire")):
        events = []
        for index, player in enumerate(raw.get("players") or []):
            if not isinstance(player, dict) or player.get("isRadiant") is not radiant:
                continue
            stats = player.get("stats") if isinstance(player.get("stats"), dict) else {}
            events.extend((time, index) for time, death in _death_events(stats, duration)
                          if death.get("isDieBack") is True)
        events.sort()
        best = []
        for start, _ in events:
            window = [(time, index) for time, index in events if start <= time <= start + 120]
            if len({index for _, index in window}) > len({index for _, index in best}):
                best = window
        count = len({index for _, index in best})
        if count >= 2:
            out.append(f"{label}: {count} different heroes died after buyback within "
                       f"{_clock(best[-1][0] - best[0][0])} "
                       f"({_clock(best[0][0])}–{_clock(best[-1][0])})")
    return out


def summarize(raw, opendota, duration):
    """Return display-ready observations, indexed by raw player position.

    ``match`` and ``players`` hold factual receipt strings. ``items`` holds
    observed final-slot IDs; ``skills`` holds the first eight recorded
    non-talent pick names (not hero levels). Missing keys mean unavailable;
    empty lists mean an explicitly recorded empty inventory/pick sequence.
    No OpenDota/STRATZ player-index join is used or assumed.
    """
    duration = duration if _number(duration) and duration > 0 else 0
    result = {"match": _match_observations(raw, opendota, duration),
              "players": {}, "items": {}, "skills": {}}
    for index, player in enumerate(raw.get("players") or []):
        if not isinstance(player, dict):
            continue
        items = _inventory(player)
        skills = _skill_ids(player)
        if items is not None:
            result["items"][index] = items
        if skills is not None:
            result["skills"][index] = [ability_name(a, player.get("heroId"))
                                       for a in skills[:EARLY_SKILL_PICKS]]
        result["players"][index] = _player_observations(player, duration, skills, items)
    return result
