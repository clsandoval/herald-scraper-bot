"""Offline extraction parity and reusable held-out evidence math."""
from collections import Counter
import hashlib
import json
import math

import pytest

from herald import ingest, novelty


def player(hero=1, skills=(), purchases=()):
    return {"heroId": hero,
            "abilities": [{"abilityId": ability, "isTalent": False}
                          for ability in skills],
            "stats": {"itemPurchases": [{"itemId": item, "time": time}
                                        for item, time in purchases]}}


def match(*players, mode="ALL_PICK_RANKED"):
    return {"gameMode": mode, "players": list(players)}


def parity_matches():
    """Multiple heroes/modes, rare swaps, nulls, talents, duplicates, short logs.

    The expected digest was captured from the original scoring functions before
    extraction. It covers every stored score and JSON receipt byte, including
    tie order, menu pool compression, p99 aggregation, and one/two-digit rounding.
    """
    normal = [5003, 5004, 5003, 5005, 5004, 5003, 5004, 5005, 5006, 5005, 5006, 5006]
    second = [6001, 6002, 6001, 6002, 6003, 6001, 6002, 6003, 6004, 6004, 6003, 6004]
    for index in range(120):
        mode = "ALL_PICK_RANKED" if index < 90 else ("TURBO" if index < 110 else None)
        skills = list(normal)
        items = [(116, 1100), (116, 1500), (65, 650), (98, 2000)]
        if index in (11, 77, 109, 115):
            skills = [5006, 5006, 5006, 5005, 5005, 5004, 5003, 5003, 5004, 5003]
            items = [(133, 1800), (151, 2400), (48, 2700), (133, 2900)]
        if index == 78:
            skills = [999999, *normal]
        primary = player(1, skills, [*items, (1, 100), (133, 0), (133, -100)])
        primary["abilities"].insert(2, {"abilityId": 0, "isTalent": False})
        primary["abilities"].insert(5, {"abilityId": 123456, "isTalent": True})
        secondary = player(2, second, [(133, 1000), (151, 1600), (48, 2000)])
        if index % 7 == 0:
            secondary = player(2, list(reversed(second)), [(116, 1500), (65, 2000)])
        result = match(primary, secondary, player(99, [5003, 5004] * 2), mode=mode)
        if index == 119:
            result.pop("gameMode")
        yield result
    for mode in ("SINGLE_DRAFT", "RANDOM_DRAFT"):
        yield match(player(1, normal, [(65, 400)]), mode=mode)
    yield match(player(1), mode="UNKNOWN_FUTURE_MODE")


def score_rows(matches):
    db = ingest.get_conn(":memory:")
    try:
        for mid, raw in enumerate(matches):
            db.execute("INSERT INTO matches(match_id, raw) VALUES (?, ?)",
                       (mid, json.dumps(raw)))
        db.commit()
        assert ingest.score_weirdness(db) == 123
        assert ingest.score_skill_weirdness(db) == 123
        return db.execute("SELECT match_id, weirdness, weird_notes, skill_weirdness, skill_notes"
                          " FROM matches ORDER BY match_id").fetchall()
    finally:
        db.close()


def test_all_menu_scores_and_receipts_match_pre_extraction_golden():
    rows = score_rows(parity_matches())
    digest = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    assert digest == "df1ec878656856471c9ed9b904d023ec833dd2258779d653bdfebab76c02162a"


def test_item_own_exclusion_is_numerator_only_and_only_in_reference():
    target = player(1, purchases=[(10, 61)])
    corpus = novelty.ItemCorpus.fit(
        [match(target, player(1, purchases=[(11, 80)]),
               player(2, purchases=[(10, 60)]))], {10: "A", 11: "B"})
    held_out = corpus.score_player(target)
    own = corpus.score_player(target, target_in_reference=True)
    assert held_out.score == pytest.approx(-math.log((1.5 / 3) / (2 / 3)))
    assert own.score == pytest.approx(-math.log((0.5 / 3) / (2 / 3)))
    assert own.items == (novelty.ItemReceipt(10, "A", 1, own.score),)
    assert corpus.hero_builds == {1: 2, 2: 1}
    assert corpus.gtot == 3
    assert corpus.htot == {1: 2, 2: 1}


def test_item_distinct_families_ties_and_nonpositive_purchase_times():
    target = player(purchases=[(10, 60), (11, 120), (12, 180), (13, 240), (14, 300),
                               (14, 600), (10, 0), (10, -60)])
    families = {10: "Same", 11: "Same", 12: "C", 13: "D", 14: "E"}
    corpus = novelty.ItemCorpus.fit([match(target)], families)
    result = corpus.score_player(target, target_in_reference=True)
    assert corpus.gtot == 6
    assert len(result.items) == 3
    assert len({receipt.family for receipt in result.items}) == 3
    # Same-family equal scores retain the first encountered purchase, while
    # different-family equal scores favor the later minute.
    assert [receipt.item_id for receipt in result.items] == [13, 12, 10]


def test_item_unseen_global_and_empty_references_are_safe():
    target = player(purchases=[(10, 60)])
    empty = novelty.ItemCorpus.fit([], {10: "A"})
    assert empty.score_player(target) == novelty.PlayerItemScore(0.0, ())
    unseen = novelty.ItemCorpus.fit([match(player(purchases=[(11, 60)]))],
                                    {10: "A", 11: "B"})
    assert unseen.score_player(target) == novelty.PlayerItemScore(0.0, ())


def test_completed_empty_item_pass_clears_stale_scores_and_does_not_retry():
    db = ingest.get_conn(":memory:")
    try:
        db.execute("INSERT INTO matches(match_id, raw, weirdness, weird_notes)"
                   " VALUES (1, ?, 99, ?)", (json.dumps(match(player())), '[{"stale": true}]'))
        assert ingest.score_weirdness(db) == 1
        assert ingest.score_skill_weirdness(db) == 1
        assert db.execute("SELECT weirdness, weird_notes, skill_weirdness, skill_notes"
                          " FROM matches").fetchone() == (0.0, "[]", 0.0, "[]")
        assert not ingest.should_rescore(db, 1)
    finally:
        db.close()


def test_skill_own_exclusion_applies_to_count_and_total_only_in_reference():
    normal = player(skills=[10, 11] * 3)
    alternative = player(skills=[11, 10] * 3)
    corpus = novelty.SkillCorpus.fit([match(normal, normal, normal, alternative)])
    assert corpus.mode_builds[(1, "ALL_PICK_RANKED")] == 4
    held_out = corpus.score_player(alternative, "ALL_PICK_RANKED")
    own = corpus.score_player(alternative, "ALL_PICK_RANKED", target_in_reference=True)
    assert held_out.score == pytest.approx(2 * -math.log(1.5 / 5))
    assert own.score == pytest.approx(2 * -math.log(0.5 / 4))
    # Equal candidates of the same ability retain the first pick; sorting
    # distinct abilities then favors the later index.
    assert [(receipt.ability_id, receipt.pick) for receipt in own.picks] == [(10, 2), (11, 1)]


def test_skill_mode_conditioning_and_complete_build_support():
    normal = player(skills=[10, 11] * 3)
    reverse = player(skills=[11, 10] * 3)
    short = player(skills=[10, 11] * 2)
    rows = [match(normal, normal, normal, short), match(reverse, reverse, reverse, mode="TURBO")]
    corpus = novelty.SkillCorpus.fit(rows)
    assert corpus.hero_builds[1] == 7
    assert corpus.mode_builds == {(1, "ALL_PICK_RANKED"): 3, (1, "TURBO"): 3}
    assert corpus.tot[(1, "ALL_PICK_RANKED", 0)] == 3
    assert corpus.score_player(normal, "TURBO").score > corpus.score_player(normal, "ALL_PICK_RANKED").score
    assert corpus.score_player(short, "ALL_PICK_RANKED") is None
    assert corpus.score_player(normal, "UNSEEN") is None


def test_skill_receipts_preserve_original_and_compressed_pick_numbers():
    normal = player(skills=[10, 11, 10, 11, 10, 11, 10])
    target = player(skills=[9999, 11, 10, 11, 10, 11, 10, 11])
    corpus = novelty.SkillCorpus.fit([match(normal, normal, normal, target)])
    assert 9999 not in corpus.pool[1]
    result = corpus.score_player(target, "ALL_PICK_RANKED", target_in_reference=True)
    assert result.picks
    assert all(receipt.original_pick == receipt.pick + 1 for receipt in result.picks)
    assert result.skills == (11, 10, 11, 10, 11, 10, 11)


def test_skill_pool_compression_does_not_fill_past_first_twelve_picks():
    normal = player(skills=[10, 11] * 6)
    target = player(skills=[9999, *([10, 11] * 6)])
    corpus = novelty.SkillCorpus.fit([match(normal, normal, normal, target)])
    result = corpus.score_player(target, "ALL_PICK_RANKED", target_in_reference=True)
    assert len(result.skills) == 11
    assert novelty.skill_ids(player(skills=[0, 10, None, 11])) == [10, 11]


def test_ult_inference_upper_median_and_early_ult_discount_match_legacy():
    regular = player(skills=[10, 11, 10, 11, 12, 10, 11, 12, 12, 10])
    target = player(skills=[12, 12, 12, 11, 10, 11, 10, 11, 10, 10])
    corpus = novelty.SkillCorpus.fit([match(regular, regular, regular, target)])
    assert corpus.ults == {1: 12}
    result = corpus.score_player(target, "ALL_PICK_RANKED", target_in_reference=True)
    ult_receipt = next(receipt for receipt in result.picks if receipt.ability_id == 12)
    assert ult_receipt.score == pytest.approx(-math.log(0.5 / 4.5) * 0.5)


@pytest.mark.parametrize("values", [[0], [0, 9], [0, 3, 3, 5], [4, 4, 4, 4, 11],
                                     [0] * 100 + [5] * 100 + [11] * 100])
def test_bounded_histogram_median_matches_old_full_first_index_lists(values):
    histogram = Counter(values)
    assert len(histogram) <= 12
    assert novelty._upper_median(histogram) == sorted(values)[len(values) // 2]


def test_fitting_is_replayable_streaming_and_rejects_one_shot_skill_iterator():
    calls = []

    def factory():
        calls.append("pass")
        for _ in range(3):
            yield match(player(skills=[10, 11] * 3, purchases=[(10, 61)]))

    corpus = novelty.SkillCorpus.fit(factory)
    assert calls == ["pass", "pass"]
    assert corpus.mode_builds[(1, "ALL_PICK_RANKED")] == 3
    novelty.ItemCorpus.fit(factory, {10: "A"})
    assert len(calls) == 3
    with pytest.raises(TypeError, match="replayable"):
        novelty.SkillCorpus.fit(factory())


def test_shared_math_has_no_menu_or_database_imports():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(novelty))
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imported += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                 for alias in node.names]
    assert not any(name and ("ingest" in name or "sqlite" in name or "scheduled" in name)
                   for name in imported)
