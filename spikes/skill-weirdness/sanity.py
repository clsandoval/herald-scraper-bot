"""Spike 001 check: sequences parse, talents separable, per-hero N adequate."""
import gzip
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
rows = empty = 0
hero_n = Counter()
seq_lens = Counter()
talent_counts = Counter()
for line in gzip.open(HERE / "abil.tsv.gz", "rt"):
    mid, slot, hero, seq = line.rstrip("\n").split("\t")
    rows += 1
    if not seq:
        empty += 1
        continue
    ev = seq.split(",")
    skills = [e for e in ev if not e.endswith("t")]
    talents = [e for e in ev if e.endswith("t")]
    hero_n[int(hero)] += 1
    seq_lens[min(len(skills), 30)] += 1
    talent_counts[len(talents)] += 1

names = json.load(open(HERE / "ability_ids.json"))
print(f"rows={rows} empty_seq={empty} ({empty/rows:.1%})")
print(f"heroes={len(hero_n)} median_builds_per_hero={sorted(hero_n.values())[len(hero_n)//2]}")
print("min 5 heroes:", [(h, n) for h, n in hero_n.most_common()[-5:]])
print("skill-count dist (skills only, capped 30):",
      sorted(seq_lens.items())[:5], "...", sorted(seq_lens.items())[-5:])
print("talents per player:", sorted(talent_counts.items()))
# spot-check ability id -> name coverage on a random-ish sample
sample_ids = set()
for line in gzip.open(HERE / "abil.tsv.gz", "rt"):
    for e in line.rstrip("\n").split("\t")[3].split(","):
        if e and not e.endswith("t"):
            sample_ids.add(e)
    if len(sample_ids) > 400:
        break
missing = [i for i in sample_ids if i not in names]
print(f"name coverage: {len(sample_ids)-len(missing)}/{len(sample_ids)} known, missing e.g. {missing[:5]}")

assert rows > 150_000 and empty / rows < 0.05, "extract looks broken"
print("SANITY OK")
