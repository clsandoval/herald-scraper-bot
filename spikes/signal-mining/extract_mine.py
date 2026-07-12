"""Run ON PROD: stream the corpus once, emit three compact TSVs for local
signal mining. One raw in memory at a time (1GB VM)."""
import gzip
import json
import sqlite3

BKB, MIDAS = 116, 65


def arr_total(a):
    """campStack / tripsFountainPerMinute are per-minute arrays; cumulative
    arrays are nondecreasing -> take last, else sum the increments."""
    if not a:
        return 0
    return a[-1] if all(x <= y for x, y in zip(a, a[1:])) else sum(a)


c = sqlite3.connect("file:/data/herald.db?mode=ro", uri=True)
c.execute("PRAGMA busy_timeout=30000")

fm = gzip.open("/tmp/mine_matches.tsv.gz", "wt")
fp = gzip.open("/tmp/mine_players.tsv.gz", "wt")
fc = gzip.open("/tmp/mine_chat.tsv.gz", "wt")
n = 0
for mid, w, sw, raw in c.execute(
        "SELECT match_id, weirdness, skill_weirdness, raw FROM matches"):
    m = json.loads(raw)
    fm.write("\t".join(str(x) for x in (
        mid, m["durationSeconds"], 1 if m["didRadiantWin"] else 0,
        m.get("barracksStatusRadiant"), m.get("barracksStatusDire"),
        sum(m.get("radiantKills") or []) + sum(m.get("direKills") or []),
        w or 0, sw or 0)) + "\n")
    for slot, p in enumerate(m["players"]):
        st = p.get("stats") or {}
        de = st.get("deathEvents") or []
        used = {u["itemId"]: u["count"] for u in st.get("itemUsed") or []}
        bought = {b["itemId"] for b in st.get("itemPurchases") or []
                  if (b.get("time") or 0) > 0}
        wards = st.get("wards") or []
        talks = st.get("allTalks") or []
        row = (mid, slot, p["heroId"], 1 if p["isRadiant"] else 0,
               p.get("kills"), p.get("deaths"), p.get("assists"),
               p.get("networth") or 0, p.get("goldSpent") or 0,
               1 if p.get("isRandom") else 0,
               len(talks),
               sum(d.get("timeDead") or 0 for d in de),
               sum(d.get("goldFed") or 0 for d in de),
               sum(1 for d in de if d.get("isAttemptTpOut")),
               sum(1 for d in de if d.get("hasHealAvailable")),
               sum(1 for d in de if d.get("isDieBack")),
               len(wards),
               arr_total(st.get("campStack")),
               arr_total(st.get("tripsFountainPerMinute")),
               len(st.get("courierKills") or []),
               1 if BKB in bought else 0, used.get(BKB, 0),
               1 if MIDAS in bought else 0, used.get(MIDAS, 0),
               (p.get("dotaPlus") or {}).get("level") or 0)
        fp.write("\t".join(str(x) for x in row) + "\n")
        for t in talks:
            msg = (t.get("message") or "").replace("\t", " ").replace("\n", " ")
            fc.write(f"{mid}\t{p['heroId']}\t{t.get('time')}\t{msg}\n")
    n += 1
for f in (fm, fp, fc):
    f.close()
print("matches:", n)
