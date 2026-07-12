"""Run ON PROD (herald-board): dump per-player skill sequences to TSV.
Columns: match_id, slot, hero_id, seq — seq is comma-joined abilityId in
time order, talent events suffixed 't' (e.g. "5520,5518,525t,...").
"""
import gzip
import json
import sqlite3

c = sqlite3.connect("file:/data/herald.db?mode=ro", uri=True)
c.execute("PRAGMA busy_timeout=30000")
n = 0
with gzip.open("/tmp/abil.tsv.gz", "wt") as out:
    for mid, raw in c.execute("SELECT match_id, raw FROM matches"):
        for slot, p in enumerate(json.loads(raw)["players"]):
            ab = p.get("abilities") or []
            ab = sorted(enumerate(ab), key=lambda x: (x[1]["time"], x[0]))
            seq = ",".join(str(a["abilityId"]) + ("t" if a["isTalent"] else "")
                           for _, a in ab)
            out.write(f"{mid}\t{slot}\t{p['heroId']}\t{seq}\n")
        n += 1
print("matches:", n)
