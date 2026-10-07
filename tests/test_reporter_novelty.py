"""Standalone scheduled novelty, offline synthetic references only."""
import copy
import json
import sqlite3
from unittest.mock import Mock

import pytest

from herald import reporter_novelty as r, render, scheduled

NOW = 1_800_000_000
PATCH = 60
MODE = "ALL_PICK_RANKED"
SKILLS = [5003, 5004, 5003, 5004, 5003, 5006, 5003, 5004, 5005, 5005, 5005, 5006]


def report_gallery(message):
    container = next(node for node in message["components"] if node["type"] == 17)
    return next(node for node in container["components"] if node["type"] == 12)


def match(mid=1, *, patch=PATCH, mode=MODE):
    c = {"match_id": mid, "start_time": NOW - 1000 + mid, "duration": 4800, "avg_rank_tier": 15}
    players = [{"heroId": i + 1, "isRadiant": i < 5,
        "steamAccount": {"seasonRank": 15}, "kills": 2, "deaths": 3, "assists": 4,
        **{f"item{j}Id": item for j, item in enumerate([116, 65, 133, 108, 112, 1])},
        "abilities": [{"abilityId": a, "time": j * 60, "isTalent": False} for j, a in enumerate(SKILLS)],
        "stats": {"itemPurchases": [{"itemId": 116 if i == 0 else 151, "time": 1000}]}}
        for i in range(10)]
    raw = {"gameMode": mode, "players": players}
    od = {"patch": patch, "players": [{"leaver_status": 0} for _ in range(10)]}
    return c, raw, od


@pytest.fixture
def store():
    conn = sqlite3.connect(":memory:")
    value = r.ReferenceStore(conn)
    value.begin_pass(NOW)
    yield value
    conn.close()


def warm(store, count=40, **kwargs):
    for mid in range(1, count + 1):
        store.observe_and_score(*match(mid, **kwargs))
    store.begin_pass(NOW)


def test_fresh_reference_is_explicitly_unscored_and_compact(store):
    c, raw, od = match()
    raw["players"][0]["steamAccount"]["accountId"] = 12345
    result = store.observe_and_score(c, raw, od)
    assert result["reference"]["matches"] == 0
    assert result["items"][0]["score"] is None
    assert result["skills"][0]["score"] is None
    assert "warming up" in result["skills"][0]["reason"]
    text = store.conn.execute("SELECT data FROM report_builds").fetchone()[0]
    assert "accountId" not in text and "steamAccount" not in text and '"kills":' not in text
    assert len(json.loads(text)["players"][0]["abilities"]) == 12
    assert len(text.encode()) <= r.MAX_ROW_BYTES


def test_reference_is_frozen_until_next_pass_not_fitted_per_candidate(store):
    for mid in range(1, 41):
        result = store.observe_and_score(*match(mid))
        assert result["reference"]["matches"] == 0
        assert result["reference"]["target_in_reference"] is False
    store.begin_pass(NOW)
    result = store.observe_and_score(*match(99))
    assert result["reference"]["matches"] == 40
    assert result["items"][0]["status"] == result["skills"][0]["status"] == "scored"
    assert result["items"][0]["support"]["hero_builds"] == 40
    assert result["skills"][0]["support"]["hero_mode_builds"] == 40


def test_unusual_heldout_purchase_and_order_get_actual_evidence(store):
    warm(store)
    c, raw, od = match(99)
    raw["players"][0]["stats"]["itemPurchases"][0]["itemId"] = 151
    raw["players"][0]["abilities"][0]["abilityId"] = 5005
    result = store.observe_and_score(c, raw, od)
    item = result["items"][0]
    skill = result["skills"][0]
    assert item["status"] == skill["status"] == "scored"
    assert item["score"] > result["items"][1]["score"]
    assert skill["score"] > result["skills"][1]["score"]
    assert item["receipts"][0]["item_id"] == 151
    assert skill["receipts"][0]["ability_id"] == 5005
    assert skill["receipts"][0]["pick"] == 1
    assert len(skill["picks"]) == 12
    assert result["reference"]["target_in_reference"] is False


def test_identical_retry_is_not_counted_twice_and_own_exclusion_is_explicit(store):
    warm(store)
    result = store.observe_and_score(*match(1))
    assert result["reference"]["target_in_reference"] is True
    assert result["items"][0]["support"]["hero_builds"] == 39
    assert result["skills"][0]["support"]["hero_mode_builds"] == 39
    assert store.conn.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 40
    assert store.observe_and_score(*match(1)) == result


def test_changed_retry_is_unscored_instead_of_subtracting_nonexistent_pick(store):
    warm(store)
    c, raw, od = match(1)
    raw["players"][0]["abilities"][0]["abilityId"] = 5005
    result = store.observe_and_score(c, raw, od)
    assert result["reference"]["target_in_reference"] is None
    assert all(value["score"] is None for value in result["skills"].values())
    assert "incompatible" in result["skills"][0]["reason"]


@pytest.mark.parametrize("patch", [None, True, "60", 0, -1])
def test_missing_patch_never_borrows_previous_patch(store, patch):
    warm(store)
    result = store.observe_and_score(*match(99, patch=patch))
    assert result["items"][0]["score"] is None
    assert result["skills"][0]["reason"] == "OpenDota patch unavailable"
    assert store.conn.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 40


def test_patch_and_mode_partitions_prevent_false_comparisons(store):
    warm(store)
    result = store.observe_and_score(*match(99, patch=PATCH + 1))
    assert result["reference"]["matches"] == 0
    assert result["items"][0]["score"] is None
    result = store.observe_and_score(*match(100, mode="TURBO"))
    assert result["items"][0]["status"] == "scored"
    assert result["skills"][0]["score"] is None
    assert result["skills"][0]["support"]["hero_mode_builds"] == 0


@pytest.mark.parametrize("mode,reason", [(None, "game mode unavailable"),
    ("SINGLE_DRAFT", "unsupported sparse game mode"), ("RANDOM_DRAFT", "unsupported sparse game mode")])
def test_unsupported_modes_remain_unscored(store, mode, reason):
    warm(store)
    result = store.observe_and_score(*match(99, mode=mode))
    assert result["skills"][0]["score"] is None
    assert result["skills"][0]["reason"] == reason


def test_missing_partial_and_unsupported_logs_are_not_normal(store):
    warm(store)
    c, raw, od = match(99)
    raw["players"][0].pop("abilities")
    raw["players"][1]["abilities"] = raw["players"][1]["abilities"][:5]
    raw["players"][2]["abilities"][0]["abilityId"] = 999999
    raw["players"][3]["stats"]["itemPurchases"] = None
    raw["players"][4]["stats"]["itemPurchases"][0]["itemId"] = 133  # absent in reference
    result = store.observe_and_score(c, raw, od)
    assert result["skills"][0]["reason"] == "skill log unavailable"
    assert "fewer than 6" in result["skills"][1]["reason"]
    assert "outside reference" in result["skills"][2]["reason"]
    assert result["items"][3]["reason"] == "purchase log unavailable"
    assert result["items"][4]["reason"] == "item absent from reference"
    assert all(result["skills"][i]["score"] is None for i in range(3))


def test_age_version_and_count_pruning_never_touches_delivery_ledger(store, monkeypatch):
    store.conn.execute("CREATE TABLE deliveries (match_id INTEGER PRIMARY KEY, data TEXT)")
    store.conn.execute("INSERT INTO deliveries VALUES (1, 'immutable')")
    monkeypatch.setattr(r, "MAX_MATCHES", 3)
    for mid in range(1, 8):
        store.observe_and_score(*match(mid))
    assert [x[0] for x in store.conn.execute("SELECT match_id FROM report_builds ORDER BY match_id")] == [5, 6, 7]
    store.conn.execute("UPDATE report_builds SET version='old' WHERE match_id=5")
    store.conn.execute("UPDATE report_builds SET start_time=? WHERE match_id=6", (NOW - 31 * 86400,))
    store.begin_pass(NOW)
    assert store.conn.execute("SELECT match_id FROM report_builds").fetchall() == [(7,)]
    assert store.conn.execute("SELECT data FROM deliveries").fetchall() == [("immutable",)]


def test_frozen_reference_survives_eviction_and_late_patch_fits(store, monkeypatch):
    monkeypatch.setattr(r, "MAX_MATCHES", 3)
    for mid, patch in [(1, 60), (2, 61), (3, 62)]:
        store.observe_and_score(*match(mid, patch=patch))
    store.begin_pass(NOW)
    for mid in range(10, 13):
        store.observe_and_score(*match(mid, patch=63))
    assert store.conn.execute("SELECT patch FROM report_builds").fetchall() == [(63,)] * 3
    for patch in [60, 61, 62, 60]:
        result = store.observe_and_score(*match(100 + patch, patch=patch))
        assert result["reference"]["matches"] == 1


def test_compact_parent_chooses_evidence_and_png_keeps_all_twelve_ordinals(store):
    warm(store)
    c, raw, od = match(99)
    raw["players"][5]["stats"]["itemPurchases"][0]["itemId"] = 116
    raw["players"][7]["abilities"][11]["abilityId"] = 5003
    result = store.observe_and_score(c, raw, od)
    spec = scheduled.payload(c, raw, od, {}, evidence=result)
    parent = spec["parent"]["embeds"][0]
    cues = json.dumps(parent)
    assert "fields" not in parent
    assert render.hero_name(raw["players"][5]["heroId"]) in cues
    assert render.hero_name(raw["players"][7]["heroId"]) in cues
    assert "pick 12" in cues and "12." not in cues
    assert "PMI" not in cues and "surprisal" not in cues
    assert "Black King Bar at 16m" in cues
    assert render.check_embeds(spec["parent"]) <= 900
    assert "long-Herald" not in json.dumps(spec["parent"])
    assert spec == json.loads(json.dumps(spec))
    for message in [spec["parent"], *spec["teams"]]:
        scheduled.check_message(message)
    for team in spec["teams"]:
        assert "embeds" not in team and team["flags"] == 32768
        assert report_gallery(team)["items"][0]["media"]["url"].startswith("attachment://")
    for card in spec["cards"].values():
        for player in card["players"]:
            assert len(player["items"]) == 6
            assert len(player["skills"]) == 12
            assert len(player["notes"]) <= 2
    selected = spec["cards"]["dire"]["players"][2]
    assert selected["skills"][11] == 5003
    assert selected["skill_marks"] == [12]
    assert any("Pick 12:" in note for note in selected["notes"])


def test_novelty_uses_existing_requests_and_never_changes_eligibility(tmp_path, monkeypatch):
    ledger = scheduled.Receipts(tmp_path / "reports.db")
    c, raw, od = match(99)
    monkeypatch.setattr(scheduled.time, "time", lambda: NOW)
    monkeypatch.setattr(scheduled.time, "sleep", lambda _: None)
    transport = Mock()
    transport.request.side_effect = [{"id": "bot"}, {"type": 0}, {"id": "app"}, {"items": []}]
    monkeypatch.setattr(scheduled, "DiscordHTTP", lambda *_: transport)
    monkeypatch.setattr(scheduled, "discover", lambda *_: [c])
    fetch = Mock(return_value={c["match_id"]: raw})
    monkeypatch.setattr(scheduled.api, "stratz_fetch_batch", fetch)
    deliver = Mock()
    monkeypatch.setattr(scheduled, "deliver", deliver)
    client = Mock()
    client.get.return_value.json.return_value = od
    scheduled.run_once(ledger, client, "synthetic", "channel")
    assert fetch.call_count == client.get.call_count == deliver.call_count == 1
    assert "gameMode" in fetch.call_args.kwargs["fields"]
    assert deliver.call_args.args[2]["build_evidence"]["skills"]["0"]["score"] is None
    assert scheduled.eligible(c, raw, od)
    assert ledger.conn.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 1
    ledger.conn.close()
