"""Factual, replay-first parent previews; scoring and delivery stay separate."""
import copy
import json
from unittest.mock import Mock

import pytest

from herald import examples, reporter_novelty, scheduled


NOISE = ("reference population", "pmi", "surprisal", "warming up", "unscored",
         "no standout", "does not mean normal", "invented", "patch", "sample",
         "quality score", "review cues", "generated matches", "hero builds")


def parent(match=None, evidence=None, emojis=None):
    c, raw, od = match or examples.synthetic_match(missing=True)
    return scheduled.parent_embed(c, raw, od, emojis or {},
                                  evidence or reporter_novelty.unavailable(raw))


def evidence(raw, *, items=True, skills=True):
    proof = reporter_novelty.unavailable(raw)
    if items:
        proof["items"][0] = {"status": "scored", "score": 999,
                              "receipts": [{"item_id": 151, "minute": 20}]}
    if skills:
        proof["skills"][1] = {"status": "scored", "score": 999,
                               "receipts": [{"ability_id": 5007, "pick": 12}]}
    return proof


def assert_clean(embed):
    text = json.dumps(embed, ensure_ascii=False).lower()
    assert all(term not in text for term in NOISE)
    assert "fields" not in embed
    assert scheduled.check_message({"embeds": [embed]}) <= 500


def test_rapier_parent_uses_supported_sequence_and_existing_artwork():
    match = examples.synthetic_match()
    embed = parent(match, evidence(match[1]))
    assert embed == {
        "title": "Rapier → dead in 35s", "description": "82m · 122 kills",
        "color": 0xC8A03C, "url": "https://stratz.com/matches/-101",
        "author": {"name": "Juggernaut", "icon_url":
            "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/juggernaut.png"},
        "thumbnail": {"url":
            "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/items/rapier.png"},
    }
    assert "dropped" not in str(embed).lower() and "lost" not in str(embed).lower()
    assert_clean(embed)


def test_empty_reference_has_match_facts_without_a_disclaimer_or_dummy_cue():
    embed = parent()
    assert embed["title"] == "122 kills in 82 minutes"
    assert embed["description"] == "Radiant 55 · Dire 67"
    assert "author" not in embed and "thumbnail" not in embed and "footer" not in embed
    assert_clean(embed)


@pytest.mark.parametrize("kind", ["unknown", "cold", "insufficient", "scored"])
def test_reference_state_never_leaks_into_parent(kind):
    match = examples.synthetic_match(missing=True)
    proof = evidence(match[1]) if kind == "scored" else reporter_novelty.unavailable(match[1])
    proof["reference"].update(patch=None if kind == "unknown" else 1,
                              matches={"unknown": 0, "cold": 0, "insufficient": 15,
                                       "scored": 40}[kind])
    assert_clean(parent(match, proof))


def test_item_and_skill_only_fallback_keeps_concrete_receipts_without_math():
    match = examples.synthetic_match(missing=True)
    embed = parent(match, evidence(match[1]))
    assert embed["title"] == "Armlet of Mordiggian at 20m"
    assert embed["author"]["name"] == "Anti-Mage"
    assert embed["description"] == "82m · 122 kills\nAxe · Berserker's Call at pick 12"
    assert embed["thumbnail"]["url"].endswith("/armlet.png")
    assert_clean(embed)


def test_skill_only_fallback_keeps_original_pick_number():
    match = examples.synthetic_match(missing=True)
    embed = parent(match, evidence(match[1], items=False))
    assert embed["title"] == "Berserker's Call at pick 12"
    assert embed["author"]["name"] == "Axe" and "thumbnail" not in embed
    assert_clean(embed)


def test_build_fallback_accepts_saved_json_keys_without_mutating_evidence():
    match = examples.synthetic_match(missing=True)
    proof = evidence(match[1])
    before = copy.deepcopy((match, proof))
    assert parent(match, proof) == parent(match, json.loads(json.dumps(proof)))
    assert (match, proof) == before


def test_match_event_beats_scored_builds_and_uninteresting_player_order():
    c, raw, od = examples.synthetic_match(missing=True)
    raw["players"][0]["isRandom"] = True
    od.update(radiant_win=False, radiant_gold_adv=[0, 18000, -2000])
    embed = parent((c, raw, od), evidence(raw))
    assert embed["title"] == "Dire won after trailing by 18,000 gold"
    assert "author" not in embed
    assert_clean(embed)


def test_later_player_event_beats_earlier_random_hero_and_build_score():
    c, raw, od = examples.synthetic_match(missing=True)
    raw["players"][0]["isRandom"] = True
    raw["players"][7]["stats"]["deathEvents"] = [
        {"time": 3900, "isDieBack": True}, {"time": 4500, "isDieBack": True}]
    embed = parent((c, raw, od), evidence(raw))
    assert embed["title"] == "Buyback then died ×2: 65:00, 75:00"
    assert embed["author"]["name"] == "Pudge"
    assert_clean(embed)


@pytest.mark.parametrize("death", [None, {"time": 4499}, {"time": 4591}, {"time": True}])
def test_rapier_headline_requires_a_supported_purchase_then_quick_death(death):
    c, raw, od = examples.synthetic_match()
    raw["players"][5]["stats"]["deathEvents"] = [] if death is None else [death]
    embed = parent((c, raw, od))
    assert embed["title"] == "Divine Rapier purchases: 75:00"
    assert "dead in" not in embed["title"]
    assert_clean(embed)


@pytest.mark.parametrize("unknown", [None, -1, True, 55.0, "55"])
def test_unknown_score_never_becomes_zero_or_a_partial_total(unknown):
    c, raw, od = examples.synthetic_match(missing=True)
    od["radiant_score"] = unknown
    embed = parent((c, raw, od))
    assert embed["title"] == "82m match"
    assert "description" not in embed and "kills" not in json.dumps(embed)
    assert_clean(embed)


def test_duration_seconds_are_not_rounded_away():
    c, raw, od = examples.synthetic_match(missing=True)
    c["duration"] = 4945
    assert parent((c, raw, od))["title"] == "122 kills in 82m 25s"
    assert parent((c, raw, od), evidence(raw))["description"].startswith("82m 25s · 122 kills")


def test_unavailable_artwork_uses_only_supplied_application_emojis(monkeypatch):
    monkeypatch.setattr(scheduled, "_parent_artwork_sources", lambda: {})
    embed = parent(examples.synthetic_match(), emojis={"h_juggernaut": "123", "i_rapier": "456"})
    assert embed["title"] == "<:i_rapier:456> <:h_juggernaut:123> Rapier → dead in 35s"
    assert embed["author"] == {"name": "Juggernaut"}
    assert "thumbnail" not in embed
    without = parent(examples.synthetic_match())
    assert without["title"] == "Rapier → dead in 35s"
    assert without["author"] == {"name": "Juggernaut"}


def test_parent_generation_does_not_fetch_icons_or_provider_data(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("parent preview attempted network I/O"))
    monkeypatch.setattr(scheduled.httpx, "Client", forbidden)
    monkeypatch.setattr(scheduled.api, "explorer_fetch", forbidden)
    monkeypatch.setattr(scheduled.api, "stratz_fetch_batch", forbidden)
    assert parent(examples.synthetic_match())["title"] == "Rapier → dead in 35s"
    forbidden.assert_not_called()


def test_examples_preserve_production_parents_with_only_link_removal_and_one_label():
    for index, spec in enumerate(examples.build_examples()):
        match = examples.synthetic_match(examples.EXAMPLE_IDS[index], missing=bool(index))
        expected = parent(match, spec["build_evidence"])
        expected.pop("url")
        expected["footer"] = {"text": "Example"}
        actual = spec["parent"]["embeds"][0]
        assert actual == expected
        assert json.dumps(actual).lower().count("example") == 1
        assert_clean(actual)
