"""Spike 002a v2: positional surprisal, mode-conditioned + pool-filtered.

Changes vs pmi.py after v1 findings:
- corpus stats keyed (hero, MODE, idx) — Turbo leveling differs wildly from
  ranked (banked points are normal there), 79% of corpus is Turbo
- events dropped unless ability is in the hero's corpus pool (>=1% of that
  hero's builds) — kills Turbo hero-swap artifacts and dota_base_ability
"""
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
MAX_IDX = 12
TOP_K = 3

ability_names = json.load(open(HERE / "ability_ids.json"))
heroes = json.load(open(HERE / "../menu-v2/assets/heroes.json"))
hero_names = {v["id"]: v["localized_name"] for v in heroes.values()}
modes = dict(line.rstrip("\n").split("\t")
             for line in gzip.open(HERE / "modes.tsv.gz", "rt"))


def load():
    builds = []
    for line in gzip.open(HERE / "abil.tsv.gz", "rt"):
        mid, slot, hero, seq = line.rstrip("\n").split("\t")
        if not seq:
            continue
        # id 0 = "dota_base_ability", Stratz null placeholder — not a pick
        skills = [int(e) for e in seq.split(",") if not e.endswith("t") and e != "0"]
        if len(skills) < 6:
            continue
        builds.append((int(mid), int(slot), int(hero), modes.get(mid, "?"),
                       skills[:MAX_IDX]))
    return builds


def score(builds, distinct=False, ults=None, ult_discount=1.0):
    """distinct: top-3 over distinct abilities (mirrors item distinct-family).
    ult_discount: multiplier on the hero's ult when first-picked early (<=5) —
    the banked-points signature; keeps it visible without board domination."""
    # hero ability pools from full corpus (mode-agnostic; kits don't vary by mode)
    seen = Counter()
    hero_builds = Counter()
    for _, _, h, _m, sk in builds:
        hero_builds[h] += 1
        for a in set(sk):
            seen[(h, a)] += 1
    pool = defaultdict(set)
    for (h, a), n in seen.items():
        if n >= max(3, 0.01 * hero_builds[h]):
            pool[h].add(a)

    count, tot = Counter(), Counter()
    filtered = []
    dropped_ev = 0
    for mid, slot, h, m, sk in builds:
        fsk = [a for a in sk if a in pool[h]]
        dropped_ev += len(sk) - len(fsk)
        if len(fsk) < 6:
            continue
        filtered.append((mid, slot, h, m, fsk))
        for i, a in enumerate(fsk):
            count[(h, m, i, a)] += 1
            tot[(h, m, i)] += 1
    print(f"dropped {dropped_ev} out-of-pool events; {len(filtered)} builds scored")

    def surprise(h, m, i, a):
        v = len(pool[h])
        p = (count[(h, m, i, a)] - 1 + 0.5) / (tot[(h, m, i)] - 1 + 0.5 * v)
        return -math.log(max(p, 1e-9))

    out = []
    for mid, slot, h, m, sk in filtered:
        ult = (ults or {}).get(h)
        cands = []
        for i, a in enumerate(sk):
            s = surprise(h, m, i, a)
            if a == ult and sk.index(a) <= 5:
                s *= ult_discount
            cands.append((s, i, a))
        if distinct:
            best = {}
            for s, i, a in cands:
                if s > best.get(a, (0, 0))[0]:
                    best[a] = (s, i)
            cands = [(s, i, a) for a, (s, i) in best.items()]
        per = sorted(cands, reverse=True)[:TOP_K]
        out.append((sum(s for s, _, _ in per), mid, slot, h, m,
                    [(round(s, 1), i + 1, a) for s, i, a in per], sk))
    out.sort(reverse=True)
    return out


def show(rows, label):
    print(f"\n=== {label} ===")
    for sc, mid, slot, h, m, per, sk in rows:
        picks = "; ".join(
            f"pt{i}:{ability_names.get(str(a), a)}({s})" for s, i, a in per)
        seq = ",".join(ability_names.get(str(a), str(a)).split("_")[-1][:9]
                       for a in sk)
        print(f"{sc:6.1f} {hero_names.get(h, h):16} {m:6.6} m{mid} | {picks}\n"
              f"       seq: {seq}")


if __name__ == "__main__":
    ranked = score(load())
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    show(ranked[:n], f"TOP {n} WEIRDEST")
    show(ranked[len(ranked) // 2:len(ranked) // 2 + 3], "MEDIAN")
    show(ranked[-3:], "MOST NORMAL")
