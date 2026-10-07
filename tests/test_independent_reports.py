"""Independent reporter/provider/scorer integration QA; fake transport only.

This module deliberately does not import the private menu or its simulator.
"""

import copy
import json
import sqlite3
from unittest.mock import Mock

import httpx
import pytest

from herald import api, ingest, render, report_signals, reporter_novelty, scheduled


def synthetic_match(mid=801):
    return {
        "id": mid, "startDateTime": 1780000000, "durationSeconds": 4800,
        "didRadiantWin": True, "radiantKills": [35], "direKills": [29],
        "radiantNetworthLeads": [0, 1000, -500, 4000],
        "players": [
            {"heroId": index + 1, "isRadiant": index < 5, "kills": 3,
             "deaths": 4, "assists": 5, "networth": 9000,
             "steamAccount": {"seasonRank": 12}, "stats": {},
             **{f"item{slot}Id": 0 for slot in range(6)}}
            for index in range(10)
        ],
    }


@pytest.mark.parametrize("winner,racks", [(None, 0), (0, 0), (False, False)])
def test_megas_tag_requires_known_winner_and_integer_barracks_mask(winner, racks):
    assert render.megas_tag({"didRadiantWin": winner, "barracksStatusDire": racks}) is None


@pytest.mark.parametrize("unknown", [{"isTalent": False},
                                     {"isTalent": False, "abilityId": None}])
def test_unknown_skill_pick_cannot_create_false_opening(unknown):
    raw = synthetic_match()
    raw["players"][0]["abilities"] = [
        {"abilityId": 5003, "isTalent": False}, unknown,
        {"abilityId": 5003, "isTalent": False},
        {"abilityId": 5003, "isTalent": False},
    ]

    result = report_signals.summarize(raw, {}, 4800)

    assert 0 not in result["skills"]
    assert not any("First 3" in receipt for receipt in result["players"][0])


class DeliveryFake:
    def __init__(self, fail_stage="radiant"):
        self.messages = {}
        self.posts = []
        self.fail_stage = fail_stage

    def find_message(self, channel, bot_id, expected, nonce):
        return next((copy.deepcopy(message) for (destination, _), message in self.messages.items()
                     if destination == channel and scheduled.same_message(message, expected)), None)

    def request(self, method, path, **kwargs):
        parts = path.split("/")
        channel = parts[2]
        if method == "GET":
            return copy.deepcopy(self.messages.get((channel, parts[4])))
        body = kwargs["json"]
        self.posts.append(copy.deepcopy(body))
        mid = str(100 + len(self.posts))
        if path.endswith("/threads"):
            self.messages[(channel, parts[4])]["thread"] = {"id": mid}
            result = {"id": mid}
            stage = "thread"
        else:
            result = {**copy.deepcopy(body), "id": mid, "author": {"id": "bot"}}
            self.messages[(channel, mid)] = result
            stage = body.get("nonce", "").rsplit(":", 1)[-1]
        if self.fail_stage == stage:
            self.fail_stage = None
            raise KeyboardInterrupt("synthetic interruption after remote acceptance")
        return copy.deepcopy(result)


def test_old_partial_receipt_resumes_original_payload_after_card_upgrade(tmp_path):
    raw = synthetic_match()
    candidate = {"match_id": raw["id"], "start_time": raw["startDateTime"],
                 "duration": 4800, "avg_rank_tier": 12}
    opendota = {"radiant_score": 35, "dire_score": 29, "duration": 4800}
    current = scheduled.payload(candidate, raw, opendota, {})
    # Frozen legacy-style three-message spec. New descriptions, fields, and
    # footer must never rewrite an already-started delivery after an upgrade.
    legacy = copy.deepcopy(current)
    for message in [legacy["parent"], *legacy["teams"]]:
        message["embeds"][0] = {
            "title": message["embeds"][0]["title"],
            "fields": [{"name": "Legacy field", "value": "Original receipt", "inline": False}],
        }
    transport = DeliveryFake()
    ledger = scheduled.Receipts(tmp_path / "delivery.db")
    try:
        with pytest.raises(KeyboardInterrupt):
            scheduled.deliver(transport, ledger, legacy, "channel", "bot")

        receipt = scheduled.deliver(transport, ledger, current, "channel", "bot")

        assert receipt["verified"] is True
        assert receipt["spec"] == legacy
        assert len(transport.posts) == 4  # One parent, thread, Radiant and Dire.
        assert all(message["embeds"][0]["fields"][0]["name"] == "Legacy field"
                   for message in transport.posts if "embeds" in message)
        scheduled.deliver(transport, ledger, current, "channel", "bot")
        assert len(transport.posts) == 4
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("body", [{}, {"rows": None}, {"rows": {}},
                                  {"error": "synthetic provider failure"}])
def test_invalid_explorer_response_cannot_finish_report_window(tmp_path, monkeypatch, body):
    """Pass 2: an HTTP success is not proof that discovery reached its end."""
    ledger = scheduled.Receipts(tmp_path / "report-window.db")
    old_window = ledger.window(10 * 86400, None)
    fake_discord = Mock()
    fake_discord.request.side_effect = [
        {"id": "bot"}, {"type": 0}, {"id": "application"}, {"items": []},
    ]
    monkeypatch.setattr(scheduled, "DiscordHTTP", lambda *_: fake_discord)
    monkeypatch.setattr(api.time, "sleep", Mock())
    client = Mock()
    client.get.return_value = httpx.Response(
        200, json=body, request=httpx.Request("GET", "https://example.invalid/explorer"))
    try:
        with pytest.raises(RuntimeError):
            scheduled.run_once(ledger, client, "synthetic", "channel")

        assert ledger.window(12 * 86400, 7) == old_window
        assert 1 <= client.get.call_count <= 4
        client.post.assert_not_called()
        assert not list(ledger.pending())
    finally:
        ledger.conn.close()


def test_explicit_empty_explorer_rows_can_finish_report_window(tmp_path, monkeypatch):
    ledger = scheduled.Receipts(tmp_path / "empty-report-window.db")
    ledger.window(10 * 86400, None)
    fake_discord = Mock()
    fake_discord.request.side_effect = [
        {"id": "bot"}, {"type": 0}, {"id": "application"}, {"items": []},
    ]
    monkeypatch.setattr(scheduled, "DiscordHTTP", lambda *_: fake_discord)
    client = Mock()
    client.get.return_value = httpx.Response(
        200, json={"rows": []}, request=httpx.Request("GET", "https://example.invalid/explorer"))
    try:
        scheduled.run_once(ledger, client, "synthetic", "channel")

        assert ledger.conn.execute("SELECT count(*) FROM pending_window").fetchone()[0] == 0
        assert client.get.call_count == 1
        client.post.assert_not_called()
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("body", [{"error": "synthetic provider failure"},
                                  {"err": "synthetic rate limit"}])
def test_opendota_error_envelope_is_not_an_ineligible_match(tmp_path, monkeypatch, body):
    ledger = scheduled.Receipts(tmp_path / "detail-failure-window.db")
    old_window = ledger.window(10 * 86400, None)
    raw = synthetic_match()
    candidate = {"match_id": raw["id"], "start_time": raw["startDateTime"],
                 "duration": 4800, "avg_rank_tier": 12}
    fake_discord = Mock()
    fake_discord.request.side_effect = [
        {"id": "bot"}, {"type": 0}, {"id": "application"}, {"items": []},
    ]
    monkeypatch.setattr(scheduled, "DiscordHTTP", lambda *_: fake_discord)
    monkeypatch.setattr(scheduled, "discover", lambda *_: [candidate])
    monkeypatch.setattr(api, "stratz_fetch_batch", lambda *_, **__: {raw["id"]: raw})
    monkeypatch.setattr(api.time, "sleep", Mock())
    client = Mock()
    client.get.return_value = httpx.Response(
        200, json=body, request=httpx.Request("GET", "https://example.invalid/match"))
    try:
        with pytest.raises(RuntimeError):
            scheduled.run_once(ledger, client, "synthetic", "channel")

        assert ledger.window(12 * 86400, 7) == old_window
        assert fake_discord.request.call_count == 4  # Startup reads, no report sends.
        assert not list(ledger.pending())
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("stage", ["parent", "thread", "radiant", "dire"])
def test_each_ambiguous_delivery_stage_recovers_after_database_reopen(tmp_path, stage):
    """Pass 2: every write boundary survives process-like receipt reopening."""
    raw = synthetic_match()
    candidate = {"match_id": raw["id"], "start_time": raw["startDateTime"],
                 "duration": 4800, "avg_rank_tier": 12}
    spec = scheduled.payload(candidate, raw,
                             {"radiant_score": 35, "dire_score": 29, "duration": 4800}, {})
    path = tmp_path / "reopened-receipts.db"
    transport = DeliveryFake(fail_stage=stage)
    interrupted = scheduled.Receipts(path)
    try:
        with pytest.raises(KeyboardInterrupt):
            scheduled.deliver(transport, interrupted, spec, "channel", "bot")
        assert interrupted.get(raw["id"])["inflight"] == stage
    finally:
        interrupted.conn.close()

    reopened = scheduled.Receipts(path)
    try:
        recovered = scheduled.deliver(transport, reopened, spec, "channel", "bot")

        assert recovered["verified"] is True
        assert "inflight" not in recovered
        assert len(transport.posts) == 4
        assert list(reopened.pending()) == []
        scheduled.deliver(transport, reopened, spec, "channel", "bot")
        assert len(transport.posts) == 4
    finally:
        reopened.conn.close()


def test_completed_no_purchase_corpus_does_not_rescore_forever():
    """A successful no-evidence pass must not resemble a half-finished pair."""
    db = ingest.get_conn(":memory:")
    raw = {"gameMode": "ALL_PICK_RANKED", "players": [
        {"heroId": 1, "stats": {}, "abilities": []},
    ]}
    try:
        for mid in (1, 2):
            db.execute("INSERT INTO matches(match_id,raw) VALUES(?,?)", (mid, json.dumps(raw)))
        db.commit()

        ingest.score_weirdness(db)
        ingest.score_skill_weirdness(db)

        assert not ingest.should_rescore(db, 51)
        assert not ingest.should_rescore(db, 52)
    finally:
        db.close()


def compact_source(hero=1, item=116):
    """Small build-cache fixture; production eligibility is tested separately."""
    return {"gameMode": "ALL_PICK_RANKED", "players": [{
        "heroId": hero, "stats": {"itemPurchases": [{"itemId": item, "time": 100}]},
        "abilities": [],
    }]}


def novelty_candidate(mid):
    return {"match_id": mid, "start_time": 2_000_000 + mid, "duration": 4800}


def test_frozen_reference_survives_rolling_eviction_and_model_lru(monkeypatch):
    """Pass 3: later patch queries see the same reference that began the pass."""
    monkeypatch.setattr(reporter_novelty, "MAX_MATCHES", 2)
    db = sqlite3.connect(":memory:")
    try:
        store = reporter_novelty.ReferenceStore(db)
        store.begin_pass(2_000_100)
        for mid in (1, 2):
            store.observe_and_score(novelty_candidate(mid), compact_source(), {"patch": 7})
        store.begin_pass(2_000_100)
        store.observe_and_score(novelty_candidate(3), compact_source(), {"patch": 8})
        first = store.observe_and_score(novelty_candidate(4), compact_source(), {"patch": 7})
        assert first["reference"]["matches"] == 2
        for mid, patch in ((5, 9), (6, 10)):
            store.observe_and_score(novelty_candidate(mid), compact_source(), {"patch": patch})
        refit = store.observe_and_score(novelty_candidate(7), compact_source(), {"patch": 7})

        assert refit["reference"] == first["reference"]
        assert refit["items"] == first["items"]
        assert db.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 2
    finally:
        db.close()


def test_changed_retained_target_cannot_create_false_own_exclusion(monkeypatch):
    # Lower support only isolates the arithmetic guard in a tiny fixture.
    # Production's real cold-start thresholds are unchanged and tested elsewhere.
    monkeypatch.setattr(reporter_novelty, "MIN_HERO_BUILDS", 0)
    db = sqlite3.connect(":memory:")
    try:
        store = reporter_novelty.ReferenceStore(db)
        store.begin_pass(2_000_100)
        store.observe_and_score(novelty_candidate(1), compact_source(1, 116), {"patch": 7})
        store.observe_and_score(novelty_candidate(2), compact_source(2, 133), {"patch": 7})
        store.begin_pass(2_000_100)
        unchanged = store.observe_and_score(novelty_candidate(1), compact_source(1, 116), {"patch": 7})
        changed = store.observe_and_score(novelty_candidate(1), compact_source(1, 133), {"patch": 7})

        assert unchanged["reference"]["target_in_reference"] is True
        assert changed["items"][0]["status"] == "unscored"
        assert changed["items"][0]["score"] is None
        assert "changed" in changed["items"][0]["reason"]
        assert changed["reference"]["target_in_reference"] is None
        assert db.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 2
    finally:
        db.close()


def test_complete_skill_names_are_not_shortened_when_the_full_path_fits():
    ids = [5007, 5008, 5007, 5009, 5007, 5010, 5007, 5008, 5008, 5008, 5010, 5009]
    player = {"heroId": 2, "abilities": [
        {"abilityId": aid, "isTalent": False, "time": index * 60}
        for index, aid in enumerate(ids)
    ]}
    full = " → ".join(f"{index}. {report_signals.ability_name(aid, 2)}"
                      for index, aid in enumerate(ids, 1))
    assert len(full) <= 240

    assert scheduled.skill_path(player, 240) == full
