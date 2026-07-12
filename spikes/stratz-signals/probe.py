"""Run ON PROD: fetch 25 corpus matches with ALL candidate fields in one
aliased request (1 rate-limit unit), dump raw JSON for local analysis.
Mix: 10 weirdest-skill, 10 bloodiest, 5 newest — biased toward review-worthy
matches, which is where the receipts must deliver."""
import json
import os
import sqlite3

import httpx

FIELDS = """
  id barracksStatusRadiant barracksStatusDire
  chatEvents { time type fromHeroId value pausedTick isRadiant }
  pickBans { isPick heroId order isRadiant }
  players {
    heroId isRandom goldSpent networth invisibleSeconds behavior
    stats {
      allTalks { time message }
      chatWheels { time chatWheelId }
      deathEvents { time timeDead goldFed goldLost isDieBack isAttemptTpOut
                    hasHealAvailable isWardWalkThrough byAbility attacker }
      itemUsed { itemId count }
      wards { time type }
      campStack
      tripsFountainPerMinute
      courierKills { time }
      matchPlayerBuffEvent { time itemId abilityId stackCount }
      runes { time rune action }
      level
    }
  }
"""

c = sqlite3.connect("file:/data/herald.db?mode=ro", uri=True)
c.execute("PRAGMA busy_timeout=30000")
ids = [r[0] for r in c.execute(
    "SELECT match_id FROM matches ORDER BY skill_weirdness DESC LIMIT 10")]
ids += [r[0] for r in c.execute(
    "SELECT match_id FROM matches ORDER BY kills DESC LIMIT 10")]
ids += [r[0] for r in c.execute(
    "SELECT match_id FROM matches ORDER BY start_time DESC LIMIT 5")]
ids = list(dict.fromkeys(ids))[:25]

q = "{" + " ".join(f"m{i}: match(id: {mid}) {{ {FIELDS} }}"
                   for i, mid in enumerate(ids)) + "}"
r = httpx.post("https://api.stratz.com/graphql", json={"query": q},
               headers={"Authorization": "Bearer " + os.environ["STRATZ_API_TOKEN"],
                        "User-Agent": "STRATZ_API"}, timeout=120)
r.raise_for_status()
open("/tmp/probe_result.json", "w").write(r.text)
# count the spend against the shared ledger
c2 = sqlite3.connect("/data/herald.db")
c2.execute("PRAGMA busy_timeout=30000")
c2.execute("INSERT INTO stratz_calls(day, calls) VALUES(date('now'),1) "
           "ON CONFLICT(day) DO UPDATE SET calls = calls + 1")
c2.commit()
print("fetched", len(ids), "matches,", len(r.text), "bytes")
