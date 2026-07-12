"""Spike 002c: state-conditional (Markov) scorer — temporally aware.

Each pick scored as -log P(ability | hero, mode, build-state-so-far), where
state = sorted (ability, points) multiset. Sparse states back off to the
positional model. Player score = MEAN surprisal over first 12 picks (whole-
build wrongness, not top-3 spikes) * 12 to keep the scale comparable.
"""
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import pmi2
from rules import derive_ults
from tune import label

HERE = Path(__file__).parent
ability_names = json.load(open(HERE / "ability_ids.json"))
MIN_STATE_N = 20  # below this, back off to positional stats


def score_markov(builds):
    # hero pools (reuse pmi2's filter logic by rebuilding counts here)
    seen, hero_builds = Counter(), Counter()
    for _, _, h, _m, sk in builds:
        hero_builds[h] += 1
        for a in set(sk):
            seen[(h, a)] += 1
    pool = defaultdict(set)
    for (h, a), n in seen.items():
        if n >= max(3, 0.01 * hero_builds[h]):
            pool[h].add(a)

    scount, stot = Counter(), Counter()   # state-conditional
    pcount, ptot = Counter(), Counter()   # positional backoff
    filtered = []
    for mid, slot, h, m, sk in builds:
        fsk = [a for a in sk if a in pool[h]]
        if len(fsk) < 6:
            continue
        filtered.append((mid, slot, h, m, fsk))
        st = Counter()
        for i, a in enumerate(fsk):
            key = (h, m, tuple(sorted(st.items())))
            scount[key + (a,)] += 1
            stot[key] += 1
            pcount[(h, m, i, a)] += 1
            ptot[(h, m, i)] += 1
            st[a] += 1

    def surprise(h, m, i, st_key, a):
        v = len(pool[h])
        key = (h, m, st_key)
        if stot[key] >= MIN_STATE_N:
            p = (scount[key + (a,)] - 1 + 0.5) / (stot[key] - 1 + 0.5 * v)
        else:
            p = (pcount[(h, m, i, a)] - 1 + 0.5) / (ptot[(h, m, i)] - 1 + 0.5 * v)
        return -math.log(max(p, 1e-9))

    out = []
    for mid, slot, h, m, fsk in filtered:
        st = Counter()
        tot = 0.0
        worst = []
        for i, a in enumerate(fsk):
            s = surprise(h, m, i, tuple(sorted(st.items())), a)
            tot += s
            worst.append((s, i, a))
            st[a] += 1
        mean = tot / len(fsk)
        worst = sorted(worst, reverse=True)[:3]
        out.append((mean * 12, mid, slot, h, m,
                    [(round(s, 1), i + 1, a) for s, i, a in worst], fsk))
    out.sort(reverse=True)
    return out


def show_board(ranked, ults, note_bar, n=20):
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
    for w, mid, players in match_scores[:n]:
        print(f"\n{w:6.1f} m{mid}  ({len(players)} over bar)")
        for s, h, m, per, sk in players[:3]:
            tag = label(sk, ults.get(h))
            picks = "; ".join(
                f"pt{i}:{ability_names.get(str(a), a).split('_')[-1]}({sc})"
                for sc, i, a in per)
            print(f"    {s:5.1f} {pmi2.hero_names.get(h, h):16} {m:6.6} "
                  f"{('[' + tag + '] ') if tag else ''}{picks}")


if __name__ == "__main__":
    builds = pmi2.load()
    ults = derive_ults(builds)
    ranked = score_markov(builds)
    scores = sorted(s for s, *_ in ranked)
    n = len(scores)
    pct = {p: round(scores[int(n * p / 100)], 1) for p in (50, 90, 99)}
    print("markov player-score percentiles:", pct)
    note_bar = scores[int(n * 0.99)]
    print(f"NOTE_BAR (p99) = {note_bar:.1f}")
    print("\n=== TOP 20 (MARKOV, whole-build) ===")
    show_board(ranked, ults, note_bar)
