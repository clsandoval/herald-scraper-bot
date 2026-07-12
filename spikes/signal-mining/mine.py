"""Signal mining over the enriched corpus: distributions, thresholds, top-N
eyeball lists for each candidate receipt/filter/sort."""
import gzip
import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
heroes = json.load(open(HERE / "../menu-v2/assets/heroes.json"))
hname = {v["id"]: v["localized_name"] for v in heroes.values()}

M = {}
for line in gzip.open(HERE / "mine_matches.tsv.gz", "rt"):
    mid, dur, rwin, br, bd, kills, w, sw = line.split("\t")
    M[int(mid)] = dict(dur=int(dur), rwin=int(rwin),
                       br=None if br == "None" else int(br),
                       bd=None if bd == "None" else int(bd),
                       kills=int(kills), w=float(w), sw=float(sw))

P = []
COLS = ("mid slot hero rad k d a networth gold_spent is_random chat_n "
        "time_dead gold_fed tp_deaths heal_deaths diebacks wards stacks "
        "trips courier_kills bkb_bought bkb_uses midas_bought midas_uses "
        "dplus").split()
for line in gzip.open(HERE / "mine_players.tsv.gz", "rt"):
    P.append(dict(zip(COLS, (int(x) for x in line.split("\t")))))

print(f"matches={len(M)} players={len(P)}\n")


def pct(vals, ps=(50, 90, 99)):
    vals = sorted(vals)
    return {p: vals[int(len(vals) * p / 100)] for p in ps}


# --- 1. feeding forensics ---
print("== TIME DEAD (min) ==", {k: round(v / 60, 1) for k, v in
      pct([p["time_dead"] for p in P]).items()})
dead_frac = [(p["time_dead"] / M[p["mid"]]["dur"], p) for p in P]
dead_frac.sort(key=lambda t: -t[0])
print("top 5 by fraction of game spent dead:")
for frac, p in dead_frac[:5]:
    print(f"  {frac:.0%} dead — {hname.get(p['hero'], p['hero'])} "
          f"{p['k']}/{p['d']}/{p['a']}, fed {p['gold_fed']}g, m{p['mid']}")
print("== GOLD FED ==", pct([p["gold_fed"] for p in P]))
print("tp_deaths>=3:", sum(1 for p in P if p["tp_deaths"] >= 3),
      "| heal_deaths>=5:", sum(1 for p in P if p["heal_deaths"] >= 5),
      "| any dieback:", sum(1 for p in P if p["diebacks"]))

# --- 2. megas ---
megas = []
for mid, m in M.items():
    if m["br"] is None:
        continue
    # 63 = all 6 racks alive; 0 = all dead (megas for the other side)
    r_megged, d_megged = m["br"] == 0, m["bd"] == 0
    if r_megged or d_megged:
        loser_megged_winner = (r_megged and m["rwin"]) or (d_megged and not m["rwin"])
        megas.append((mid, "comeback-vs-megas" if loser_megged_winner else "megas-win"))
kinds = Counter(k for _, k in megas)
print(f"\n== MEGAS == matches with megas: {len(megas)} ({len(megas)/len(M):.1%})",
      dict(kinds))
print("  comeback-vs-megas (won while OWN ancient was on megas):",
      [m for m, k in megas if k == "comeback-vs-megas"][:8])

# --- 3. item shame ---
bkb = [p for p in P if p["bkb_bought"]]
bkb0 = [p for p in bkb if p["bkb_uses"] == 0]
print(f"\n== BKB == bought by {len(bkb)} players, never used: {len(bkb0)} "
      f"({len(bkb0)/max(len(bkb),1):.0%})")
midas = [p for p in P if p["midas_bought"]]
if midas:
    mu = pct([p["midas_uses"] for p in midas])
    lazy = [p for p in midas if p["midas_uses"] < 10]
    print(f"== MIDAS == owners {len(midas)}, uses {mu}, <10 uses: {len(lazy)}")

# --- 4. wards/stacks/trips extremes ---
sup = [p for p in P if p["wards"] > 0]
print(f"\n== WARDS == players placing any: {len(sup)/len(P):.0%}, ",
      pct([p["wards"] for p in sup]))
zero_stack_matches = sum(1 for mid in M if all(
    p["stacks"] == 0 for p in P if p["mid"] == mid))
print(f"== TRIPS == fountain trips {pct([p['trips'] for p in P])}")
trips = sorted(P, key=lambda p: -p["trips"])[:3]
for p in trips:
    print(f"  {p['trips']} trips — {hname.get(p['hero'], p['hero'])} "
          f"{p['k']}/{p['d']}/{p['a']} m{p['mid']}")

# --- 5. died rich / gold hoarding ---
rich = sorted(P, key=lambda p: -(p["networth"] - p["gold_spent"]))
print("\n== UNSPENT GOLD (networth-goldSpent is buyback-reserve-ish; eyeball) ==")

# --- 6. chat ---
chat_n = [p["chat_n"] for p in P]
print(f"\n== CHAT == players talking: {sum(1 for c in chat_n if c)/len(P):.0%}, "
      f"lines {pct([c for c in chat_n if c])}")
talkers = sorted(P, key=lambda p: -p["chat_n"])[:3]
for p in talkers:
    print(f"  {p['chat_n']} lines — {hname.get(p['hero'], p['hero'])} "
          f"{p['k']}/{p['d']}/{p['a']} m{p['mid']}")
# correlation: do talkers die more?
died = statistics.median(p["d"] for p in P if p["chat_n"] >= 10)
quiet = statistics.median(p["d"] for p in P if p["chat_n"] == 0)
print(f"median deaths, chatty(>=10 lines) vs silent: {died} vs {quiet}")
print("randomed heroes:", sum(1 for p in P if p["is_random"]))
