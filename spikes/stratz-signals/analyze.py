"""Per-field verdict data: fill rate at Herald, payload bytes, content samples."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
data = json.load(open(HERE / "probe_result.json"))["data"]
matches = [m for m in data.values() if m]
players = [p for m in matches for p in m["players"]]
print(f"matches={len(matches)} players={len(players)}\n")

PSTAT = ["allTalks", "chatWheels", "deathEvents", "itemUsed", "wards",
         "campStack", "tripsFountainPerMinute", "courierKills",
         "matchPlayerBuffEvent", "runes", "level"]
PTOP = ["isRandom", "goldSpent", "invisibleSeconds", "behavior"]
MTOP = ["chatEvents", "pickBans", "barracksStatusRadiant", "barracksStatusDire"]

print(f"{'field':26} {'fill%':>6} {'bytes/match':>12}  sample/notes")
for f in PSTAT:
    vals = [(p.get("stats") or {}).get(f) for p in players]
    filled = [v for v in vals if v not in (None, [], 0)]
    size = sum(len(json.dumps(v)) for v in vals if v is not None) / len(matches)
    print(f"stats.{f:20} {len(filled)/len(vals):6.0%} {size:12.0f}")
for f in PTOP:
    vals = [p.get(f) for p in players]
    filled = [v for v in vals if v not in (None, False, 0)]
    uniq = Counter(v for v in vals if v is not None)
    print(f"player.{f:19} {len(filled)/len(vals):6.0%} {'':>12}  "
          f"values: {dict(list(uniq.items())[:6])}")
for f in MTOP:
    vals = [m.get(f) for m in matches]
    filled = [v for v in vals if v not in (None, [])]
    size = sum(len(json.dumps(v)) for v in vals if v is not None) / len(matches)
    print(f"match.{f:20} {len(filled)/len(vals):6.0%} {size:12.0f}")

print("\n--- ALL-CHAT SAMPLES (allTalks) ---")
shown = 0
for m in matches:
    for p in m["players"]:
        for t in (p.get("stats") or {}).get("allTalks") or []:
            print(f"  [{t['time']//60}m] {t['message']!r}")
            shown += 1
            if shown >= 25:
                break
        if shown >= 25:
            break
    if shown >= 25:
        break

print("\n--- DEATH EVENT GEMS ---")
for m in matches[:12]:
    for p in m["players"]:
        de = (p.get("stats") or {}).get("deathEvents") or []
        if not de:
            continue
        tot_dead = sum(d.get("timeDead") or 0 for d in de)
        diebacks = sum(1 for d in de if d.get("isDieBack"))
        tp_deaths = sum(1 for d in de if d.get("isAttemptTpOut"))
        heal_deaths = sum(1 for d in de if d.get("hasHealAvailable"))
        gold_fed = sum(d.get("goldFed") or 0 for d in de)
        if tot_dead > 600 or diebacks or tp_deaths >= 3:
            print(f"  m{m['id']} hero{p['heroId']}: {len(de)} deaths, "
                  f"{tot_dead//60}min dead, fed {gold_fed}g, "
                  f"diebacks={diebacks}, died-mid-TP={tp_deaths}, "
                  f"died-with-heal={heal_deaths}")

print("\n--- BARRACKS (megas check: 0 = all racks down) ---")
for m in matches:
    br, bd = m.get("barracksStatusRadiant"), m.get("barracksStatusDire")
    if br == 0 or bd == 0:
        print(f"  m{m['id']}: radiant={br} dire={bd}  <- mega creeps game")

print("\n--- CHAT WHEEL + behavior spot ---")
wheel = sum(len((p.get('stats') or {}).get('chatWheels') or []) for p in players)
print(f"chat wheel events total: {wheel}")
