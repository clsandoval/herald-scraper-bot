"""Spike 002a: positional surprisal scorer for skill orders.

Per (hero, skill-index i, ability a): surprise = -log P(a | hero, i), smoothed,
own pick excluded. Player score = sum of top-3 surprisals in first MAX_IDX
picks (mirrors item weirdness top-3). Prints top/bottom builds with receipts.

Known risk this spike probes: cascade inflation — one weird early pick shifts
all later indices. Eyeball the receipts for that failure mode.
"""
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
MAX_IDX = 12  # decision points that matter: maxing order + ult timing
TOP_K = 3

ability_names = json.load(open(HERE / "ability_ids.json"))
heroes = json.load(open(HERE / "../menu-v2/assets/heroes.json"))
hero_names = {v["id"]: v["localized_name"] for v in heroes.values()}


def load():
    builds = []  # (mid, slot, hero, [ability_id,...] non-talent, first MAX_IDX)
    for line in gzip.open(HERE / "abil.tsv.gz", "rt"):
        mid, slot, hero, seq = line.rstrip("\n").split("\t")
        if not seq:
            continue
        skills = [int(e) for e in seq.split(",") if not e.endswith("t")]
        if len(skills) < 6:  # too short to judge
            continue
        builds.append((int(mid), int(slot), int(hero), skills[:MAX_IDX]))
    return builds


def score(builds):
    count = Counter()  # (hero, idx, ability) -> n
    tot = Counter()    # (hero, idx) -> n
    pool = defaultdict(set)  # hero -> ability vocabulary
    for _, _, h, sk in builds:
        for i, a in enumerate(sk):
            count[(h, i, a)] += 1
            tot[(h, i)] += 1
            pool[h].add(a)

    def surprise(h, i, a):
        v = len(pool[h])
        p = (count[(h, i, a)] - 1 + 0.5) / (tot[(h, i)] - 1 + 0.5 * v)
        return -math.log(max(p, 1e-9))

    out = []
    for mid, slot, h, sk in builds:
        per = sorted(((surprise(h, i, a), i, a) for i, a in enumerate(sk)),
                     reverse=True)[:TOP_K]
        out.append((sum(s for s, _, _ in per), mid, slot, h,
                    [(round(s, 1), i + 1, a) for s, i, a in per], sk))
    out.sort(reverse=True)
    return out


def show(rows, label):
    print(f"\n=== {label} ===")
    for sc, mid, slot, h, per, sk in rows:
        picks = "; ".join(
            f"pt{i}:{ability_names.get(str(a), a)}({s})" for s, i, a in per)
        seq = ",".join(ability_names.get(str(a), str(a)).split("_")[-1][:9]
                       for a in sk)
        print(f"{sc:6.1f} {hero_names.get(h, h):20} m{mid} | {picks}\n"
              f"       seq: {seq}")


if __name__ == "__main__":
    builds = load()
    print(f"builds scored: {len(builds)}")
    ranked = score(builds)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    show(ranked[:n], f"TOP {n} WEIRDEST")
    show(ranked[len(ranked) // 2:len(ranked) // 2 + 3], "MEDIAN")
    show(ranked[-3:], "MOST NORMAL")
