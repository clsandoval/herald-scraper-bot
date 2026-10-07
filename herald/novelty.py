"""Policy-free, streaming item and ability-order evidence math.

Callers choose the reference population, eligible item families, and evidence
support required to publish a result. This module knows no database, menu,
patch, rank, reporting threshold, or network. A replayable match factory lets
the two skill fitting passes stream without retaining raw player histories.

Scores are exploratory corpus-relative signals, not judgments of play quality.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
import math
from typing import Any


MatchSource = Iterable[Mapping[str, Any]] | Callable[[], Iterable[Mapping[str, Any]]]


def _matches(source: MatchSource):
    return source() if callable(source) else iter(source)


def skill_ids(player, max_picks=12):
    """Observed non-talent picks in supplied order, before pool compression.

Ordering and validation belong to the caller; preserve the menu's provider
order and its exclusion of null/zero placeholders rather than silently sort.
"""
    return [event["abilityId"] for event in (player.get("abilities") or [])
            if not event.get("isTalent") and event.get("abilityId")][:max_picks]


def _purchases(player, families):
    for event in (player.get("stats") or {}).get("itemPurchases") or []:
        if event["itemId"] in families and event["time"] > 0:
            yield event


@dataclass(frozen=True)
class ItemReceipt:
    item_id: int
    family: str
    minute: int
    score: float


@dataclass(frozen=True)
class PlayerItemScore:
    score: float
    items: tuple[ItemReceipt, ...]


@dataclass
class ItemCorpus:
    item_families: Mapping[int, str]
    hcount: Counter = field(default_factory=Counter)
    htot: Counter = field(default_factory=Counter)
    gcount: Counter = field(default_factory=Counter)
    gtot: int = 0
    hero_builds: Counter = field(default_factory=Counter)

    @classmethod
    def fit(cls, matches: MatchSource, item_families: Mapping[int, str]):
        corpus = cls(dict(item_families))
        for match in _matches(matches):
            for player in match["players"]:
                hero = player["heroId"]
                has_purchase = False
                for event in _purchases(player, corpus.item_families):
                    item = event["itemId"]
                    corpus.hcount[(hero, item)] += 1
                    corpus.htot[hero] += 1
                    corpus.gcount[item] += 1
                    corpus.gtot += 1
                    has_purchase = True
                if has_purchase:
                    corpus.hero_builds[hero] += 1
        return corpus

    def score_player(self, player, *, target_in_reference=False):
        """Top three positive distinct-family PMI receipts, without rounding.

        In-reference scoring intentionally preserves the legacy *numerator
        only* own-purchase exclusion: neither hero total nor global counts
        shrink. Held-out scoring subtracts nothing. An item absent globally
        cannot support a hero-vs-global comparison and gets no receipt.
        """
        if not self.gtot:
            return PlayerItemScore(0.0, ())
        hero = player["heroId"]
        vocab = len(self.item_families)
        best = {}
        for event in _purchases(player, self.item_families):
            item = event["itemId"]
            if not self.gcount[item]:
                continue
            ph = ((self.hcount[(hero, item)] - int(target_in_reference) + 0.5)
                  / (self.htot[hero] + 0.5 * vocab))
            score = -math.log(max(ph / (self.gcount[item] / self.gtot), 1e-9))
            family = self.item_families[item]
            if score > (best[family].score if family in best else 0):
                best[family] = ItemReceipt(item, family, event["time"] // 60, score)
        # Legacy ties sort by minute and family name, not item ID or input order.
        top = tuple(sorted(best.values(),
                           key=lambda receipt: (receipt.score, receipt.minute, receipt.family),
                           reverse=True)[:3])
        return PlayerItemScore(sum(receipt.score for receipt in top), top)


@dataclass(frozen=True)
class SkillReceipt:
    ability_id: int
    pick: int
    original_pick: int
    score: float


@dataclass(frozen=True)
class PlayerSkillScore:
    score: float
    picks: tuple[SkillReceipt, ...]
    skills: tuple[int, ...]
    ult: int | None


def _upper_median(histogram):
    """Equivalent to sorted(indices)[len(indices)//2], with bounded storage."""
    middle = sum(histogram.values()) // 2
    cumulative = 0
    for index, count in sorted(histogram.items()):
        cumulative += count
        if cumulative > middle:
            return index
    raise ValueError("An empty histogram has no median")


@dataclass
class SkillCorpus:
    max_picks: int = 12
    min_build_picks: int = 6
    hero_builds: Counter = field(default_factory=Counter)
    mode_builds: Counter = field(default_factory=Counter)
    pool: dict = field(default_factory=dict)
    ults: dict = field(default_factory=dict)
    count: Counter = field(default_factory=Counter)
    tot: Counter = field(default_factory=Counter)

    @classmethod
    def fit(cls, matches: MatchSource, *, max_picks=12, min_build_picks=6,
            pool_min_builds=3, pool_fraction=0.01):
        """Fit pools/derived ults, then mode-conditioned positional counts.

        Pass a callable returning a fresh iterator (e.g. a SQLite SELECT) or a
        replayable collection. A one-shot iterator is rejected, never buffered.
        Mode exclusion is deliberately the caller's population policy.
        """
        if not callable(matches) and iter(matches) is matches:
            raise TypeError("SkillCorpus.fit needs a replayable iterable or iterator factory")
        corpus = cls(max_picks=max_picks, min_build_picks=min_build_picks)
        seen = Counter()
        first_indices = defaultdict(Counter)
        for match in _matches(matches):
            for player in match["players"]:
                skills = skill_ids(player, max_picks)
                if not skills:
                    continue
                hero = player["heroId"]
                corpus.hero_builds[hero] += 1
                for ability in set(skills):
                    seen[(hero, ability)] += 1
                first = {}
                for index, ability in enumerate(skills):
                    first.setdefault(ability, index)
                for ability, index in first.items():
                    first_indices[(hero, ability)][index] += 1

        pool = defaultdict(set)
        for (hero, ability), count in seen.items():
            if count >= max(pool_min_builds, pool_fraction * corpus.hero_builds[hero]):
                pool[hero].add(ability)
        corpus.pool = dict(pool)

        ults_raw = {}
        for (hero, ability), histogram in first_indices.items():
            if sum(histogram.values()) < 0.3 * corpus.hero_builds[hero]:
                continue
            median = _upper_median(histogram)
            if median > ults_raw.get(hero, (None, -1))[1]:
                ults_raw[hero] = (ability, median)
        corpus.ults = {hero: ability for hero, (ability, median) in ults_raw.items()
                       if median >= 4}

        for match in _matches(matches):
            mode = match.get("gameMode")
            for player in match["players"]:
                hero = player["heroId"]
                filtered = [ability for ability in skill_ids(player, max_picks)
                            if ability in corpus.pool.get(hero, ())]
                if len(filtered) < min_build_picks:
                    continue
                corpus.mode_builds[(hero, mode)] += 1
                for index, ability in enumerate(filtered):
                    corpus.count[(hero, mode, index, ability)] += 1
                    corpus.tot[(hero, mode, index)] += 1
        return corpus

    def score_player(self, player, mode, *, target_in_reference=False):
        """Distinct-ability top-three positional surprisals, without rounding.

        Both numerator and denominator exclude one own pick only for a target
        represented in the fitted reference. Pool compression is retained for
        the model and ``pick``; ``original_pick`` is the pre-pool non-talent
        pick number so reporters need not mislabel an observed choice.
        """
        hero = player["heroId"]
        pool = self.pool.get(hero, ())
        filtered = [(index + 1, ability)
                    for index, ability in enumerate(skill_ids(player, self.max_picks))
                    if ability in pool]
        if len(filtered) < self.min_build_picks or not self.mode_builds[(hero, mode)]:
            return None
        skills = tuple(ability for _, ability in filtered)
        ult = self.ults.get(hero)
        own = int(target_in_reference)
        best = {}
        for index, (original_pick, ability) in enumerate(filtered):
            probability = ((self.count[(hero, mode, index, ability)] - own + 0.5)
                           / (self.tot[(hero, mode, index)] - own + 0.5 * len(pool)))
            score = -math.log(max(probability, 1e-9))
            if ult is not None and ability == ult and skills.index(ability) <= 5:
                score *= 0.5
            if score > (best[ability].score if ability in best else -1):
                best[ability] = SkillReceipt(ability, index + 1, original_pick, score)
        # Legacy ties prefer later pick, then larger ability ID.
        top = tuple(sorted(best.values(),
                           key=lambda receipt: (receipt.score, receipt.pick, receipt.ability_id),
                           reverse=True)[:3])
        return PlayerSkillScore(sum(receipt.score for receipt in top), top, skills, ult)
