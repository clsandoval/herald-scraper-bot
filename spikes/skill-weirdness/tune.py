"""Spike 003: match-level aggregation + threshold tuning + item-weirdness overlap.

Mirrors item weirdness: per match, weirdest player's score carries; players
over NOTE_BAR accumulate. Rule labels (from 002b) decorate receipts only.
Outputs: score distribution, suggested NOTE_BAR, top-20 board, overlap with
existing item weirdness.
"""
import gzip
import json
from collections import defaultdict
from pathlib import Path

import pmi2
from rules import derive_ults

HERE = Path(__file__).parent
ability_names = json.load(open(HERE / "ability_ids.json"))


def label(sk, ult):
    """Human tag for a weird build — receipt decoration, not scoring."""
    tags = []
    if ult is not None and ult in sk and sk.index(ult) <= 4:
        tags.append(f"ult as pick {sk.index(ult)+1}")
    if ult is not None and ult not in sk and len(sk) >= 10:
        tags.append("never skilled ult")
    if len(sk) >= 3 and sk[0] == sk[1] == sk[2]:
        tags.append(f"opened {ability_names.get(str(sk[0]), sk[0]).split('_')[-1]} x3")
    return ", ".join(tags)


def run():
    builds = pmi2.load()
    ults = derive_ults(builds)
    # rebalanced: distinct-ability top-3 + 0.5x early-ult (banking) discount
    ranked = pmi2.score(builds, distinct=True, ults=ults, ult_discount=0.5)

    scores = sorted(s for s, *_ in ranked)
    n = len(scores)
    pct = {p: scores[int(n * p / 100)] for p in (50, 90, 95, 99)}
    print("player-score percentiles:", {p: round(v, 1) for p, v in pct.items()})
    note_bar = round(pct[99], 1)
    print(f"NOTE_BAR (p99) = {note_bar}")

    per_match = defaultdict(list)
    for s, mid, slot, h, m, per, sk in ranked:
        per_match[mid].append((s, h, m, per, sk))
    match_scores = []
    for mid, players in per_match.items():
        players.sort(reverse=True)
        over = [p for p in players if p[0] >= note_bar]
        w = sum(p[0] for p in over) if over else players[0][0]
        match_scores.append((w, mid, over or players[:1]))
    match_scores.sort(reverse=True)

    iw = dict(line.split("\t") for line in
              gzip.open(HERE / "iw.tsv.gz", "rt").read().splitlines())
    top = match_scores[:20]
    top_item = sorted(((float(iw.get(str(m), 0)), m) for _, m, _ in match_scores),
                      reverse=True)[:20]
    both = {m for _, m, _ in top} & {m for _, m in top_item}
    print(f"overlap of top-20 skill-weird vs top-20 item-weird: {len(both)} matches")

    print("\n=== TOP 20 SKILL-WEIRD MATCHES ===")
    for w, mid, players in top:
        item_w = float(iw.get(str(mid), 0))
        print(f"\n{w:6.1f} m{mid}  (item-weirdness {item_w:.1f}, "
              f"{len(players)} player(s) over bar)")
        for s, h, m, per, sk in players[:3]:
            tag = label(sk, ults.get(h))
            picks = "; ".join(f"pt{i}:{ability_names.get(str(a), a).split('_')[-1]}({sc})"
                              for sc, i, a in per)
            print(f"    {s:5.1f} {pmi2.hero_names.get(h, h):16} {m:6.6} "
                  f"{('[' + tag + '] ') if tag else ''}{picks}")


if __name__ == "__main__":
    run()
