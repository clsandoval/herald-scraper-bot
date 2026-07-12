"""Spike 002b: explicit-rule baseline vs PMI (002a).

Rules (ult derived from corpus: common ability with highest median first-index):
  R1 ult-early    — ult taken at skill-index <= 4 (banked points)
  R2 ult-missing  — >= 10 points spent, ult never taken
  R3 wrong-max    — first ability to 4 points is first-maxed in < 5% of builds
  R4 mono-open    — first 3 picks identical, < 3% of that hero's builds do it

Head-to-head: overlap of rule-flagged builds vs PMI top percentile.
"""
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import pmi2

HERE = Path(__file__).parent
ability_names = json.load(open(HERE / "ability_ids.json"))


def derive_ults(builds):
    """hero -> ult ability id: among abilities in >=30% of a hero's builds,
    the one with the highest median first-pick index."""
    first_idx = defaultdict(list)
    hero_n = Counter()
    for _, _, h, _m, sk in builds:
        hero_n[h] += 1
        seen = {}
        for i, a in enumerate(sk):
            seen.setdefault(a, i)
        for a, i in seen.items():
            first_idx[(h, a)].append(i)
    ults = {}
    for (h, a), idxs in first_idx.items():
        if len(idxs) < 0.3 * hero_n[h]:
            continue
        med = sorted(idxs)[len(idxs) // 2]
        if med > ults.get(h, (None, -1))[1]:
            ults[h] = (a, med)
    return {h: a for h, (a, med) in ults.items() if med >= 4}


def run():
    builds = pmi2.load()
    ults = derive_ults(builds)
    print(f"ults derived for {len(ults)} heroes, e.g.",
          {pmi2.hero_names.get(h): ability_names.get(str(a))
           for h, a in list(ults.items())[:3]})

    # corpus stats for R3/R4
    first_max = Counter()   # (hero, ability) -> n builds where it maxed first
    hero_n = Counter()
    mono = Counter()        # (hero, ability) -> n builds opening a,a,a
    for _, _, h, _m, sk in builds:
        hero_n[h] += 1
        cnt = Counter()
        for a in sk:
            cnt[a] += 1
            if cnt[a] == 4:
                first_max[(h, a)] += 1
                break
        if len(sk) >= 3 and sk[0] == sk[1] == sk[2]:
            mono[(h, sk[0])] += 1

    flagged = {}
    for mid, slot, h, _m, sk in builds:
        flags = []
        ult = ults.get(h)
        if ult is not None:
            fi = sk.index(ult) if ult in sk else None
            if fi is not None and fi <= 4:
                flags.append(f"R1 ult@pt{fi+1}")
            elif fi is None and len(sk) >= 10:
                flags.append("R2 no-ult")
        cnt = Counter()
        for a in sk:
            cnt[a] += 1
            if cnt[a] == 4:
                if first_max[(h, a)] < 0.05 * hero_n[h]:
                    flags.append(f"R3 maxed-{ability_names.get(str(a), a)}")
                break
        if (len(sk) >= 3 and sk[0] == sk[1] == sk[2]
                and mono[(h, sk[0])] < 0.03 * hero_n[h]):
            flags.append(f"R4 open-{ability_names.get(str(a), a)}x3")
        if flags:
            flagged[(mid, slot)] = flags

    print(f"rule-flagged: {len(flagged)}/{len(builds)} "
          f"({len(flagged)/len(builds):.1%})")
    rule_dist = Counter(f.split(" ")[0] for v in flagged.values() for f in v)
    print("per rule:", dict(rule_dist))

    ranked = pmi2.score(builds)
    top1pct = ranked[:len(ranked) // 100]
    hit = sum(1 for _s, mid, slot, *_ in top1pct if (mid, slot) in flagged)
    print(f"\nPMI top-1% ({len(top1pct)}): {hit} ({hit/len(top1pct):.0%}) "
          f"also rule-flagged")

    pmi_ids = {(mid, slot) for _s, mid, slot, *_ in top1pct}
    only_rules = [k for k in flagged if k not in pmi_ids]
    print(f"rule-flagged but NOT PMI top-1%: {len(only_rules)} — sample:")
    by_key = {(mid, slot): r for r in ranked for _s, mid, slot, *_ in [r]}
    shown = 0
    for k in only_rules:
        r = by_key.get(k)
        if r is None:
            continue
        sc, mid, slot, h, m, _per, sk = r
        seq = ",".join(ability_names.get(str(a), str(a)).split("_")[-1][:9]
                       for a in sk)
        print(f"  pmi={sc:5.1f} {pmi2.hero_names.get(h, h):16} {m:6.6} "
              f"{flagged[k]} | {seq}")
        shown += 1
        if shown >= 8:
            break


if __name__ == "__main__":
    run()
