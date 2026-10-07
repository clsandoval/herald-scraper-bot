"""Deterministic reporter observations, including absent and contradictory logs."""
import copy
import json
from pathlib import Path

import pytest

from herald import report_signals as signals


def player(**overrides):
    return {"heroId": 1, "isRadiant": True, **overrides}


def summarize(*players, od=None, duration=4800):
    return signals.summarize({"players": list(players)}, od or {}, duration)


def picks(*ids):
    return [{"abilityId": aid, "time": i * 60, "level": 0, "isTalent": False}
            for i, aid in enumerate(ids)]


def test_missing_is_not_an_empty_build_or_zero_uses():
    data = summarize(player(), player(stats=None, abilities=None))
    assert data == {"match": [], "players": {0: [], 1: []}, "items": {}, "skills": {}}
    p = player(abilities=[], **{f"item{i}Id": None for i in range(6)})
    data = summarize(p)
    assert data["items"] == {0: []} and data["skills"] == {0: []}


def test_partial_empty_inventory_is_unknown_but_known_items_survive():
    assert summarize(player(item0Id=None))["items"] == {}
    assert summarize(player(item0Id=133, item1Id=None))["items"] == {0: [133]}
    assert summarize(player(item0Id=False))["items"] == {}


def test_skills_are_time_ordered_named_picks_not_hero_levels():
    events = picks(5003, 5004, 5005, 5003, 5004, 5005, 5003, 5004, 5006)
    events[0]["level"] = 25  # STRATZ's ability prior level is NOT hero level.
    events.insert(2, {"abilityId": 999, "isTalent": True, "time": 70})
    events.insert(3, {"abilityId": 0, "isTalent": False, "time": 80})
    data = summarize(player(abilities=list(reversed(events))))
    assert len(data["skills"][0]) == 8
    assert data["skills"][0][0] == "Mana Break"
    assert data["skills"][0][1] == "Blink"
    assert not any("25" in name or "Level" in name for name in data["skills"][0])


def test_simultaneous_skills_preserve_provider_order_and_new_ids_are_honest():
    events = picks(987654321, 5004)
    for event in events:
        event["time"] = 60
    assert summarize(player(abilities=events))["skills"][0] == ["Ability 987654321", "Blink"]


@pytest.mark.parametrize("events", [None, "bad", [None], [{}],
                                   [{"abilityId": 5003}],
                                   [{"abilityId": "5003", "isTalent": False}],
                                   [{"abilityId": False, "isTalent": False}],
                                   [{"abilityId": 5003, "isTalent": 0}],
                                   [{"abilityId": 5003, "isTalent": None}]])
def test_unknown_skill_records_cannot_be_compressed_into_false_opening(events):
    assert summarize(player(abilities=events))["skills"] == {}


def test_mono_opening_is_factual_and_does_not_infer_ultimate_or_rarity():
    data = summarize(player(abilities=picks(5003, 5003, 5003, 5006)))
    assert data["players"][0] == ["First 3 non-talent picks: Mana Break"]
    assert all(word not in str(data).lower() for word in ("off-meta", "rare", "ult"))


@pytest.mark.parametrize("usage", [None, [], [{"itemId": 116}],
                                  [{"itemId": 116, "count": None}],
                                  [{"itemId": 116, "count": False}],
                                  [{"itemId": 116, "count": -1}],
                                  [{"itemId": 116, "count": 0.5}],
                                  [{"itemId": 116, "count": "0"}],
                                  [{"itemId": 116, "count": float("nan")}],
                                  [{"itemId": 116, "count": 0}, {"itemId": 116, "count": 4}]])
def test_missing_invalid_or_conflicting_bkb_usage_is_not_zero(usage):
    p = player(stats={"itemPurchases": [{"time": 1000, "itemId": 116}], "itemUsed": usage})
    assert summarize(p)["players"][0] == []


def test_explicit_zero_bkb_and_low_midas_use_are_reported_as_recorded():
    p = player(stats={"itemPurchases": [{"time": 1000, "itemId": 116},
                                        {"time": 1200, "itemId": 65}],
                      "itemUsed": [{"itemId": 116, "count": 0}, {"itemId": 65, "count": 3}]})
    assert summarize(p)["players"][0] == ["BKB purchased; 0 recorded uses",
                                          "Hand of Midas purchased; 3 recorded uses"]
    del p["stats"]["itemPurchases"]
    assert summarize(p)["players"][0] == []


def test_late_midas_uses_first_recorded_purchase_not_later_repurchase():
    p = player(stats={"itemPurchases": [{"time": 2400, "itemId": 65}]})
    assert summarize(p)["players"][0] == ["First recorded Hand of Midas purchase: 40:00"]
    p["stats"]["itemPurchases"].append({"time": 600, "itemId": 65})
    assert summarize(p)["players"][0] == []


def test_smoke_count_is_an_observation_without_purchase_or_abuse_inference():
    p = player(stats={"itemUsed": [{"itemId": 188, "count": 20}]})
    assert summarize(p)["players"][0] == ["Smoke of Deceit: 20 recorded uses"]
    p["stats"]["itemUsed"][0]["count"] = 9
    assert summarize(p)["players"][0] == []
    p["stats"]["itemUsed"] = [{"itemId": 188, "count": 20}, {"itemId": 188, "count": None}]
    assert summarize(p)["players"][0] == []


@pytest.mark.parametrize("duration", [0, -1, None, float("nan"), True])
def test_unknown_duration_suppresses_timed_observations(duration):
    p = player(stats={"itemPurchases": [{"itemId": 133, "time": 0}],
                      "deathEvents": [{"time": 0, "timeDead": 99}]})
    assert summarize(p, duration=duration)["players"][0] == []


def test_rapier_purchase_then_death_is_not_an_ownership_loss_claim():
    p = player(stats={"itemPurchases": [{"time": 3900, "itemId": 133}],
                      "deathEvents": [{"time": 3918}]})
    assert summarize(p)["players"][0] == ["Divine Rapier bought 65:00; died 18s later"]
    p["stats"]["deathEvents"] = [{"time": 3800}, {"time": 4000}]
    assert summarize(p)["players"][0] == ["Divine Rapier purchases: 65:00"]


def test_rapier_purchase_timeline_is_deduplicated_sorted_and_bounded():
    purchases = [{"time": t, "itemId": 133} for t in (4500, 3900, 4100, 4300, 3900)]
    assert summarize(player(stats={"itemPurchases": purchases}))["players"][0] == [
        "Divine Rapier purchases: 65:00, 68:20, 71:40 (+1 more)"]


def test_duplicate_final_items_are_exact_observations_not_purchase_history():
    p = player(item0Id=133, item1Id=133, item2Id=29, item3Id=29)
    assert summarize(p)["players"][0] == ["Final inventory: 2× Divine Rapier"]


def test_death_micro_events_need_repetition_and_exact_true_flags():
    p = player(stats={"deathEvents": [{"time": 3000, "isDieBack": True, "isAttemptTpOut": True},
                                      {"time": 4000, "isDieBack": True, "isAttemptTpOut": True},
                                      {"time": 4100, "isDieBack": "false"}]})
    assert summarize(p)["players"][0] == ["Buyback then died ×2: 50:00, 66:40",
                                          "Died attempting TP ×2: 50:00, 66:40"]
    p["stats"]["deathEvents"] = p["stats"]["deathEvents"][:1] * 3
    assert summarize(p)["players"][0] == []


def test_dead_time_merges_overlaps_and_clips_final_respawn_timer():
    p = player(stats={"deathEvents": [{"time": 0, "timeDead": 500},
                                      {"time": 400, "timeDead": 500},
                                      {"time": 900, "timeDead": 9999}]})
    assert summarize(p, duration=1000)["players"][0] == [
        "Recorded dead time: 16:40 (100% of match)"]
    p["stats"]["deathEvents"] = [{"time": 700, "timeDead": 300}]
    assert summarize(p, duration=1000)["players"][0] == [
        "Recorded dead time: 5:00 (30% of match)"]
    p["stats"]["deathEvents"][0]["timeDead"] = 299
    assert summarize(p, duration=1000)["players"][0] == []


def test_missing_or_invalid_dead_times_never_become_percentage_or_fed_gold():
    p = player(stats={"deathEvents": [{"time": 500, "timeDead": None},
                                      {"time": 700, "timeDead": -4},
                                      {"time": 99999, "timeDead": 50000},
                                      {"timeDead": 99999}]})
    assert summarize(p)["players"][0] == []


def test_team_dieback_cluster_requires_two_distinct_heroes_on_same_team():
    a = player(stats={"deathEvents": [{"time": 4300, "isDieBack": True}]})
    b = player(heroId=2, stats={"deathEvents": [{"time": 4345, "isDieBack": True}]})
    assert summarize(a, b)["match"] == [
        "Radiant: 2 different heroes died after buyback within 0:45 (71:40–72:25)"]
    b["isRadiant"] = False
    assert summarize(a, b)["match"] == []
    b["isRadiant"] = True
    b["stats"]["deathEvents"][0]["time"] = 4421
    assert summarize(a, b)["match"] == []
    assert summarize(a)["match"] == []


@pytest.mark.parametrize("winner,leads,expected", [
    (True, [0, -12000, 5000], "Radiant won after trailing by 12,000 gold"),
    (False, [0, 18000, -1000], "Dire won after trailing by 18,000 gold"),
])
def test_comeback_is_observed_deficit_for_actual_winner(winner, leads, expected):
    assert summarize(od={"radiant_win": winner, "radiant_gold_adv": leads})["match"] == [expected]


@pytest.mark.parametrize("od", [{}, {"radiant_win": None, "barracks_status_dire": 0},
                                {"radiant_win": 0, "barracks_status_dire": 0},
                                {"radiant_win": True, "barracks_status_radiant": False},
                                {"radiant_win": True, "radiant_gold_adv": [None, "bad", float("inf")]},
                                {"radiant_win": True, "radiant_gold_adv": [20000, -7999]}])
def test_missing_or_bad_match_evidence_never_invents_a_comeback(od):
    assert summarize(od=od)["match"] == []


def test_barracks_receipt_states_final_fact_not_unproven_timing():
    assert summarize(od={"radiant_win": False, "barracks_status_dire": 0})["match"] == [
        "Dire won with all six of their barracks destroyed"]


def test_no_input_mutation_player_indices_preserved_and_no_opendota_player_join():
    raw = {"players": [player(heroId=2), player(abilities=picks(5003))]}
    od = {"players": [{"hero_id": 1, "purchase_log": [{"key": "rapier", "time": 100}]}]}
    before = copy.deepcopy((raw, od))
    assert signals.summarize(raw, od, 4800)["skills"] == {1: ["Mana Break"]}
    assert (raw, od) == before


def test_retained_fixture_is_safe_and_requires_no_new_provider_data():
    path = Path(__file__).resolve().parents[1] / "herald/fixtures/herald_matches.json"
    for raw in json.loads(path.read_text())["matches"]:
        data = signals.summarize(raw, {}, raw.get("durationSeconds", 0))
        assert len(data["players"]) == len(raw.get("players") or [])
        assert "0 recorded uses" not in str(data)  # Old fixture never fetched item-use evidence.
