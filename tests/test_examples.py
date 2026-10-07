"""The example workflow is offline by default and uses isolated durable receipts."""
import copy
import hashlib
import json
import sqlite3
from unittest.mock import Mock

import httpx
import pytest

from herald import examples as e, render, scheduled


CHANNEL = "111111111111111111"  # Invented test destinations, never live channels.
OTHER_CHANNEL = "222222222222222222"
BOT = "333333333333333333"


@pytest.fixture
def specs():
    return e.build_examples()


class FakeDiscord:
    def __init__(self):
        self.messages = {}
        self.posts = []
        self.reads = []
        self.finds = []
        self.next_id = 100
        self.fail_stage = None
        self.bot_id = BOT
        self.channel_id = CHANNEL
        self.channel_type = 0
        self.is_bot = True
        self.application = {"id": "666666666666666666"}
        self.inventory = {"items": []}
        self.inventory_error = None
        self.files = {}
        self.uploads = []
        self.before_post = None

    def verify_attachments(self, actual, expected):
        for attachment, manifest in zip(actual.get("attachments", []), expected.get("_files", [])):
            data = self.files[attachment["url"]]
            assert len(data) == manifest["size"]
            assert hashlib.sha256(data).hexdigest() == manifest["sha256"]

    def find_message(self, channel, bot_id, expected, nonce):
        self.finds.append((channel, bot_id, nonce))
        return next((copy.deepcopy(message) for (destination, _), message in self.messages.items()
                     if destination == channel and message["author"]["id"] == bot_id
                     and scheduled.same_message(message, expected)), None)

    def request(self, method, path, **kwargs):
        if method == "GET":
            self.reads.append(path)
            if path == "/users/@me":
                return {"id": self.bot_id, "bot": self.is_bot}
            if path == f"/channels/{CHANNEL}":
                return {"id": self.channel_id, "type": self.channel_type, "guild_id": "4444"}
            if path == "/oauth2/applications/@me":
                return copy.deepcopy(self.application)
            if path == "/applications/666666666666666666/emojis":
                if self.inventory_error:
                    raise self.inventory_error
                return copy.deepcopy(self.inventory)
        parts = path.split("/")
        channel = parts[2]
        if method == "GET":
            return copy.deepcopy(self.messages.get((channel, parts[4])))
        assert method == "POST"
        body = copy.deepcopy(kwargs["json"])
        assert "_files" not in body
        if self.before_post:
            self.before_post()
        self.next_id += 1
        mid = str(self.next_id)
        if path.endswith("/threads"):
            obj = {"id": mid}
            self.messages[(channel, parts[4])]["thread"] = obj
            stage = "thread"
        else:
            obj = {**body, "id": mid, "author": {"id": self.bot_id}}
            files = kwargs.get("files", [])
            assert len(files) == len(obj.get("attachments", []))
            for attachment, (field, (filename, data, content_type)) in zip(
                    obj.get("attachments", []), files):
                assert field == f"files[{attachment['id']}]"
                assert attachment["filename"] == filename
                attachment_id = str(self.next_id + 1000)
                url = f"https://cdn.discordapp.com/attachments/{channel}/{attachment_id}/{filename}"
                attachment.update(id=str(self.next_id + 1000), size=len(data),
                                  content_type=content_type, url=url, proxy_url=url)
                self.files[url] = data
                self.uploads.append((filename, data))
                if obj.get("components"):
                    report_gallery(obj)["items"][0]["media"] = {
                        "url": url, "attachment_id": attachment_id, "content_type": content_type}
                else:
                    obj["embeds"][0]["image"]["url"] = url
            self.messages[(channel, mid)] = obj
            stage = body["nonce"].split(":")[-1]
        self.posts.append((path, body))
        if stage == self.fail_stage:
            self.fail_stage = None
            raise KeyboardInterrupt("synthetic interruption after Discord accepted the write")
        return copy.deepcopy(obj)


def report_gallery(message):
    container = next(node for node in message["components"] if node["type"] == 17)
    return next(node for node in container["components"] if node["type"] == 12)


def test_dry_run_has_no_environment_network_or_file_dependency(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    forbidden = Mock(side_effect=AssertionError("dry run crossed its offline boundary"))
    monkeypatch.setattr(e.os, "environ", {})
    monkeypatch.setattr(e.httpx, "Client", forbidden)
    monkeypatch.setattr(scheduled.api, "stratz_fetch_batch", forbidden)
    monkeypatch.setattr(scheduled.api, "explorer_fetch", forbidden)
    monkeypatch.setattr(e, "validate_receipt_path", forbidden)
    monkeypatch.setattr(e, "existing_application_emojis", forbidden)
    e.main([])
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "dry-run"
    assert result["channel"] is None
    assert result["thread_count"] == 2 and result["message_count"] == 6
    assert result["payloads"] == e.build_examples()
    assert list(tmp_path.iterdir()) == []
    forbidden.assert_not_called()


def test_payloads_are_deterministic_production_shapes_and_clearly_synthetic(specs):
    assert specs == e.build_examples()
    assert len(specs) == 2
    assert [spec["match_id"] for spec in specs] == list(e.EXAMPLE_IDS)
    # Verified artwork URLs are allowed; synthetic identities never link to a match.
    assert "stratz.com/matches/" not in json.dumps(specs)
    assert "opendota.com/matches/" not in json.dumps(specs)
    for spec in specs:
        assert spec["example"]["synthetic"] is True
        assert spec["thread_name"].startswith("Example ")
        assert len(spec["thread_name"]) <= 100
        assert len(spec["teams"]) == 2
        parent = spec["parent"]["embeds"][0]
        parent_chars = (len(parent.get("title", "")) + len(parent.get("description", ""))
                        + len(parent.get("footer", {}).get("text", ""))
                        + sum(len(field["name"]) + len(field["value"])
                              for field in parent.get("fields", [])))
        assert parent_chars <= 600
        for message in [spec["parent"], *spec["teams"]]:
            assert message["allowed_mentions"] == {"parse": []}
            scheduled.check_message(message)
            if message.get("components"):
                container, = message["components"]
                assert container["type"] == 17
                assert container["components"] == [report_gallery(message)]
                assert message["flags"] == 32768 and "embeds" not in message
            for embed in message.get("embeds", []):
                assert embed["footer"]["text"] == "Example"
                assert "example" not in embed["title"].lower()
                assert "url" not in embed
        assert isinstance(spec, scheduled.ReportSpec)
        assert all(len(model["players"]) == 5 for model in spec["cards"].values())
        assert all(model["synthetic"] for model in spec["cards"].values())
        for stage, team in zip(("radiant", "dire"), spec["teams"]):
            manifest, = team["_files"]
            assert manifest["content_type"] == "image/png"
            assert team["attachments"] == [scheduled.attachment_metadata(manifest)]
            data = spec.uploads[stage][manifest["filename"]]
            assert data.startswith(scheduled.PNG_SIGNATURE)
            assert hashlib.sha256(data).hexdigest() == manifest["sha256"]
            assert manifest["description"].startswith("Example. ")


def test_examples_call_actual_production_payload(monkeypatch):
    real = scheduled.payload
    spy = Mock(wraps=real)
    # Preserve the optional-evidence signature for the compatibility check.
    spy.__signature__ = e.inspect.signature(real)
    monkeypatch.setattr(scheduled, "payload", spy)
    assert len(e.build_examples()) == 2
    assert spy.call_count == 2
    assert spy.call_args_list[0].kwargs["evidence"]["reference"]["matches"] == 40
    assert spy.call_args_list[1].kwargs["evidence"]["reference"]["matches"] == 0


def test_warmed_reference_is_computed_and_cold_start_is_honest(specs):
    warm, cold = [spec["build_evidence"] for spec in specs]
    assert warm["reference"]["matches"] == 40
    assert warm["reference"]["target_in_reference"] is False
    assert warm["reference"]["synthetic"] is True
    assert "synthetic" in warm["reference"]["population"]
    assert warm["items"]["0"]["score"] > warm["items"]["1"]["score"]
    assert warm["skills"]["0"]["score"] > warm["skills"]["1"]["score"]
    assert warm["items"]["0"]["receipts"][0]["item_id"] == 151
    assert warm["skills"]["0"]["receipts"][0]["ability_id"] == 7314
    assert warm["skills"]["0"]["receipts"][0]["pick"] == 1
    assert cold["reference"]["matches"] == 0
    assert cold["items"]["0"]["reason"] == "purchase log unavailable"
    assert cold["skills"]["0"]["reason"] == "skill log unavailable"
    for kind in ("items", "skills"):
        assert all(entry["score"] is None for entry in cold[kind].values())
        assert "warming up" in cold[kind]["1"]["reason"]
    assert "unscored" not in json.dumps(specs[1]["parent"]).lower()


def test_unique_hero_skill_pools_and_receipts_match_displayed_inputs(specs):
    _, raw, _ = e.synthetic_match()
    assert len({player["heroId"] for player in raw["players"]}) == 10
    pools = dict(e._HERO_SKILLS)
    for player in raw["players"]:
        assert all(pick["abilityId"] in pools[player["heroId"]] for pick in player["abilities"])
    player = raw["players"][0]
    assert player["item0Id"] == player["stats"]["itemPurchases"][0]["itemId"] == 151
    assert player["abilities"][0]["abilityId"] == 7314
    assert "Armlet of Mordiggian" in json.dumps(specs[0])
    assert "Counterspell" in json.dumps(specs[0])
    assert "35s later" in json.dumps(specs[0])


def test_optional_novelty_falls_back_without_inventing_scores(monkeypatch):
    original = scheduled.payload
    def legacy_payload(candidate, raw, od, emojis):
        return original(candidate, raw, od, emojis)
    monkeypatch.setattr(scheduled, "payload", legacy_payload)
    result = e.build_examples(1)
    assert result[0]["thread_name"] == "Example 1 · Rapier → dead in 35s"
    assert "Scored build evidence" not in json.dumps(result)
    assert "40 generated matches" not in json.dumps(result)
    assert result[0]["parent"]["embeds"][0]["footer"]["text"] == "Example"
    assert result[0]["build_evidence"]["reference"]["matches"] == 0
    assert all(model["synthetic"] for model in result[0]["cards"].values())
    assert all(team["_files"][0]["description"].startswith("Example. ")
               for team in result[0]["teams"])


@pytest.mark.parametrize("args", [["--send"], ["--send", "--channel", "@everyone"],
                                  ["--send", "--channel", "0"], ["--count", "3"],
                                  ["--loop"], ["--send", "--dry-run"]])
def test_invalid_cli_never_constructs_http_client(args, monkeypatch):
    client = Mock(side_effect=AssertionError("must fail before network"))
    monkeypatch.setattr(e.httpx, "Client", client)
    with pytest.raises(SystemExit):
        e.main(args)
    client.assert_not_called()


def test_send_does_not_take_target_from_environment(monkeypatch):
    monkeypatch.setenv("DISCORD_CHANNEL_ID", CHANNEL)
    with pytest.raises(SystemExit):
        e.main(["--send"])


def test_send_requires_secure_runtime_token_without_creating_ledger(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    path = tmp_path / "examples.db"
    with pytest.raises(SystemExit):
        e.main(["--send", "--channel", CHANNEL, "--receipts", str(path)])
    assert not path.exists()
    assert not path.with_suffix(".db.lock").exists()


def test_production_ledger_is_rejected_without_modification(tmp_path, monkeypatch):
    path = tmp_path / "reports.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE deliveries (match_id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO deliveries VALUES (1, 'production receipt')")
    before = path.read_bytes()
    monkeypatch.setenv("HERALD_REPORT_DB", str(tmp_path / "different-reports.db"))
    with pytest.raises(ValueError, match="non-example"):
        e.ExampleReceipts(path, CHANNEL)
    assert path.read_bytes() == before
    alias = tmp_path / "example-alias.db"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="non-example"):
        e.ExampleReceipts(alias, CHANNEL)
    assert path.read_bytes() == before
    assert not path.with_suffix(".db.lock").exists()


def test_configured_and_default_report_paths_rejected_even_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    configured = tmp_path / "custom-production.db"
    monkeypatch.setenv("HERALD_REPORT_DB", str(configured))
    for path in (configured, tmp_path / "herald-reports.db"):
        with pytest.raises(ValueError, match="production report"):
            e.ExampleReceipts(path, CHANNEL)
        assert not path.exists()
    with pytest.raises(ValueError, match="durable"):
        e.ExampleReceipts(":memory:", CHANNEL)


def test_foreign_wal_database_is_not_opened_or_changed(tmp_path):
    path = tmp_path / "foreign.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE deliveries (id INTEGER PRIMARY KEY)")
        conn.commit()
        before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
        with pytest.raises(ValueError, match="WAL sidecar"):
            e.ExampleReceipts(path, CHANNEL)
        assert {file.name: file.read_bytes() for file in tmp_path.iterdir()} == before


def test_example_ledger_contains_only_isolated_tables(tmp_path):
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    try:
        tables = {row[0] for row in ledger.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {"example_meta", "example_deliveries", "example_pending_uploads"}
        assert "deliveries" not in tables and "report_builds" not in tables
        with pytest.raises(ValueError, match="identities"):
            ledger.get(123456)
    finally:
        ledger.conn.close()


def test_old_two_table_example_ledger_upgrades_without_changing_saved_text_spec(tmp_path, specs):
    path = tmp_path / "old-examples.db"
    old_spec = {
        "match_id": e.EXAMPLE_IDS[0], "example": specs[0]["example"],
        "parent": {"embeds": [{"title": "SYNTHETIC EXAMPLE legacy parent"}],
                   "allowed_mentions": {"parse": []}},
        "teams": [{"embeds": [{"title": f"SYNTHETIC EXAMPLE legacy {side}"}],
                   "allowed_mentions": {"parse": []}} for side in ("radiant", "dire")],
        "thread_name": "SYNTHETIC EXAMPLE legacy thread",
    }
    meta = {"format": e.LEDGER_FORMAT, "fixture_set": e.FIXTURE_SET,
            "channel": CHANNEL, "bot_id": BOT}
    old_receipt = {"match_id": e.EXAMPLE_IDS[0], "spec": old_spec,
                   "channel": CHANNEL, "bot_id": BOT}
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE example_meta (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        conn.execute("CREATE TABLE example_deliveries (match_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        conn.execute("INSERT INTO example_meta VALUES (1, ?)", (json.dumps(meta),))
        conn.execute("INSERT INTO example_deliveries VALUES (?, ?)",
                     (e.EXAMPLE_IDS[0], json.dumps(old_receipt)))
    ledger = e.ExampleReceipts(path, CHANNEL)
    api = FakeDiscord()
    try:
        assert e.send_examples(api, ledger, specs[:1], CHANNEL)[0]["verified"]
        assert ledger.get(e.EXAMPLE_IDS[0])["spec"] == old_spec
        assert api.uploads == []
        assert ledger.conn.execute("SELECT count(*) FROM example_pending_uploads").fetchone()[0] == 0
        assert {row[0] for row in ledger.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {
            "example_meta", "example_deliveries", "example_pending_uploads"}
    finally:
        ledger.conn.close()


def test_example_upload_cap_fails_before_any_post_without_spool_eviction(tmp_path, specs, monkeypatch):
    api = FakeDiscord()
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    total = sum(len(data) for files in specs[0].uploads.values() for data in files.values())
    monkeypatch.setattr(scheduled, "MAX_PENDING_UPLOAD_BYTES", total)
    api.fail_stage = "parent"
    try:
        with pytest.raises(KeyboardInterrupt):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        original = list(ledger.conn.execute("SELECT * FROM example_pending_uploads"))
        with pytest.raises(RuntimeError, match="storage cap"):
            e.send_examples(api, ledger, specs[1:], CHANNEL)
        assert list(ledger.conn.execute("SELECT * FROM example_pending_uploads")) == original
        assert len(api.posts) == 1
        assert "spec" not in ledger.get(e.EXAMPLE_IDS[1])
    finally:
        ledger.conn.close()


def test_exact_destinations_no_mentions_and_idempotent_repeat(tmp_path, specs, monkeypatch):
    api = FakeDiscord()
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    deliver = Mock(wraps=scheduled.deliver)
    monkeypatch.setattr(scheduled, "deliver", deliver)
    try:
        results = e.send_examples(api, ledger, specs, CHANNEL)
        assert len(results) == 2 and all(result["verified"] for result in results)
        assert deliver.call_count == 2
        assert len(api.posts) == 8  # Two parents + two threads + four team messages.
        for spec, result in zip(specs, results):
            assert api.messages[(CHANNEL, result["parent"])]["embeds"] == spec["parent"]["embeds"]
            for side, team in zip(("radiant", "dire"), spec["teams"]):
                message = api.messages[(result["thread"], result[side])]
                assert scheduled.same_message(message, team)
            assert f"/channels/{CHANNEL}/messages/{result['parent']}/threads" in [p for p, _ in api.posts]
        for path, body in api.posts:
            if not path.endswith("/threads"):
                assert body["allowed_mentions"] == {"parse": []}
                assert body["enforce_nonce"] is True
                assert len(body["nonce"]) <= 25
        e.send_examples(api, ledger, specs, CHANNEL)
        assert len(api.posts) == 8
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("stage", ["parent", "thread", "radiant", "dire"])
def test_accepted_write_then_crash_recovers_from_durable_receipts(tmp_path, specs, stage):
    path = tmp_path / "examples.db"
    ledger = e.ExampleReceipts(path, CHANNEL)
    api = FakeDiscord()
    api.fail_stage = stage
    expected_uploads = {(side, filename): data for side, files in specs[0].uploads.items()
                        for filename, data in files.items()}
    def assert_durable_before_post():
        rows = ledger.conn.execute(
            "SELECT stage, filename, data FROM example_pending_uploads WHERE match_id=?",
            (e.EXAMPLE_IDS[0],)).fetchall()
        assert {(side, filename): data for side, filename, data in rows} == expected_uploads
        saved = ledger.get(e.EXAMPLE_IDS[0])["spec"]
        assert saved == specs[0]
    api.before_post = assert_durable_before_post
    with pytest.raises(KeyboardInterrupt):
        e.send_examples(api, ledger, specs[:1], CHANNEL)
    assert ledger.get(e.EXAMPLE_IDS[0])["inflight"] == stage
    assert ledger.conn.execute("SELECT count(*) FROM example_pending_uploads").fetchone()[0] == 2
    ledger.conn.close()
    api.before_post = None
    resumed = e.ExampleReceipts(path, CHANNEL)
    try:
        result = e.send_examples(api, resumed, specs[:1], CHANNEL)
        assert result[0]["verified"]
        assert resumed.conn.execute("SELECT count(*) FROM example_pending_uploads").fetchone()[0] == 0
        assert dict(api.uploads) == {filename: data for (_, filename), data in expected_uploads.items()}
        assert len(api.posts) == 4
        e.send_examples(api, resumed, specs[:1], CHANNEL)
        assert len(api.posts) == 4
    finally:
        resumed.conn.close()


def test_ambiguous_write_never_blindly_resends(tmp_path, specs):
    api = FakeDiscord()
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    try:
        api.fail_stage = "radiant"
        with pytest.raises(KeyboardInterrupt):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        api.messages = {key: value for key, value in api.messages.items()
                        if not value.get("nonce", "").endswith(":radiant")}
        with pytest.raises(RuntimeError, match="Unresolved radiant"):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        assert len(api.posts) == 3
    finally:
        ledger.conn.close()


def test_definite_rejection_clears_inflight_and_can_retry(tmp_path, specs):
    api = FakeDiscord()
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    request = api.request
    def rejected(method, path, **kwargs):
        if method == "POST":
            raise scheduled.DefiniteRejection("synthetic permission rejection")
        return request(method, path, **kwargs)
    api.request = rejected
    try:
        with pytest.raises(scheduled.DefiniteRejection):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        assert "inflight" not in ledger.get(e.EXAMPLE_IDS[0])
        api.request = request
        assert e.send_examples(api, ledger, specs[:1], CHANNEL)[0]["verified"]
        assert len(api.posts) == 4
    finally:
        ledger.conn.close()


def test_resume_uses_original_payload_after_new_preview_changes(tmp_path, specs):
    api = FakeDiscord()
    path = tmp_path / "examples.db"
    ledger = e.ExampleReceipts(path, CHANNEL)
    api.fail_stage = "radiant"
    with pytest.raises(KeyboardInterrupt):
        e.send_examples(api, ledger, specs[:1], CHANNEL)
    original = ledger.get(e.EXAMPLE_IDS[0])["spec"]
    ledger.conn.close()
    changed = copy.deepcopy(specs[:1])
    report_gallery(changed[0]["teams"][1])["items"][0]["description"] = "EXAMPLE changed since interruption"
    resumed = e.ExampleReceipts(path, CHANNEL)
    try:
        result = e.send_examples(api, resumed, changed, CHANNEL)[0]
        assert result["verified"]
        assert resumed.get(e.EXAMPLE_IDS[0])["spec"] == original
        assert scheduled.same_message(api.messages[(result["thread"], result["dire"])], original["teams"][1])
        assert len(api.posts) == 4
    finally:
        resumed.conn.close()


def test_deleted_partial_message_is_not_recreated(tmp_path, specs):
    api = FakeDiscord()
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    try:
        api.fail_stage = "radiant"
        with pytest.raises(KeyboardInterrupt):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        receipt = ledger.get(e.EXAMPLE_IDS[0])
        del api.messages[(CHANNEL, receipt["parent"])]
        with pytest.raises(RuntimeError, match="deleted"):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        result = e.send_examples(api, ledger, specs[:1], CHANNEL)[0]
        assert result["deleted"] and not result["verified"]
        assert len(api.posts) == 3
        assert ledger.conn.execute("SELECT count(*) FROM example_pending_uploads").fetchone()[0] == 2
    finally:
        ledger.conn.close()


def test_wrong_channel_or_bot_is_rejected_even_for_verified_examples(tmp_path, specs):
    path = tmp_path / "examples.db"
    api = FakeDiscord()
    ledger = e.ExampleReceipts(path, CHANNEL)
    try:
        e.send_examples(api, ledger, specs[:1], CHANNEL)
        with pytest.raises(ValueError, match="different channel"):
            e.ExampleReceipts(path, OTHER_CHANNEL)
        with pytest.raises(ValueError, match="destination"):
            e.send_examples(api, ledger, specs[:1], OTHER_CHANNEL)
        api.bot_id = "555555555555555555"
        with pytest.raises(ValueError, match="different bot"):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        assert len(api.posts) == 4
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("attribute,value", [("channel_id", OTHER_CHANNEL), ("channel_type", 11),
                                            ("channel_type", 15), ("is_bot", False)])
def test_send_checks_exact_guild_text_channel_and_bot_before_writes(tmp_path, specs, attribute, value):
    api = FakeDiscord()
    setattr(api, attribute, value)
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    try:
        with pytest.raises(ValueError):
            e.send_examples(api, ledger, specs[:1], CHANNEL)
        assert api.posts == []
    finally:
        ledger.conn.close()


def test_example_single_writer_lock_is_released_after_interrupt(tmp_path):
    path = tmp_path / "examples.db"
    with pytest.raises(KeyboardInterrupt), scheduled.exclusive_run(path):
        with pytest.raises(RuntimeError, match="already owns"):
            with scheduled.exclusive_run(path):
                pass
        raise KeyboardInterrupt
    with scheduled.exclusive_run(path):
        pass


def test_mocked_live_cli_is_bounded_and_uses_no_provider_api(tmp_path, specs, monkeypatch, capsys):
    path = tmp_path / "examples.db"
    api = FakeDiscord()
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "synthetic-test-credential")
    monkeypatch.setattr(e.httpx, "Client", Mock(return_value=client))
    transport = Mock(return_value=api)
    monkeypatch.setattr(scheduled, "DiscordHTTP", transport)
    providers = Mock(side_effect=AssertionError("examples never query a provider"))
    monkeypatch.setattr(scheduled.api, "explorer_fetch", providers)
    monkeypatch.setattr(scheduled.api, "stratz_fetch_batch", providers)
    e.main(["--send", "--channel", CHANNEL, "--receipts", str(path), "--count", "1"])
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["mode"] == "send" and len(result["receipts"]) == 1
    assert result["receipts"][0]["verified"]
    assert "synthetic-test-credential" not in output
    assert len(api.posts) == 4
    assert "/oauth2/applications/@me" in api.reads
    assert "/applications/666666666666666666/emojis" in api.reads
    providers.assert_not_called()


def test_send_only_existing_inventory_is_passed_to_production_payload(tmp_path, specs, monkeypatch):
    api = FakeDiscord()
    api.inventory = {"items": [
        {"name": "h_antimage", "id": "777777777777777777"},
        {"name": "i_armlet", "id": "888888888888888888"},
        {"name": "@everyone", "id": "999999999999999999"},
        {"name": "h_axe", "id": "invalid/id"},
        {"name": "h_bane", "id": "999999999999999999", "available": False},
    ]}
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    real_payload = scheduled.payload
    payload = Mock(wraps=real_payload)
    payload.__signature__ = e.inspect.signature(real_payload)
    monkeypatch.setattr(scheduled, "payload", payload)
    try:
        result = e.send_examples(api, ledger, specs[:1], CHANNEL, use_existing_emojis=True)[0]
        saved = ledger.get(e.EXAMPLE_IDS[0])["spec"]
        text = json.dumps(saved)
        assert payload.call_args.args[3] == {"h_antimage": "777777777777777777",
                                            "i_armlet": "888888888888888888"}
        assert saved["cards"]["radiant"]["players"][0]["hero_id"] == 1
        assert saved["teams"][0]["_files"][0]["content_type"] == "image/png"
        assert "@everyone" not in text and "invalid/id" not in text
        assert "<:h_bane:" not in text
        assert api.reads[:4] == ["/users/@me", f"/channels/{CHANNEL}",
                                "/oauth2/applications/@me",
                                "/applications/666666666666666666/emojis"]
        assert len(api.posts) == 4 and all("/applications/" not in path for path, _ in api.posts)
        message = api.messages[(result["thread"], result["radiant"])]
        assert scheduled.same_message(message, saved["teams"][0])
        assert message["allowed_mentions"] == {"parse": []}
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("failure", [None, "permission", "network", "malformed"])
def test_empty_or_unavailable_existing_inventory_falls_back_to_text(tmp_path, specs, failure, caplog):
    api = FakeDiscord()
    if failure == "permission":
        api.inventory_error = scheduled.DefiniteRejection("synthetic forbidden")
    elif failure == "network":
        api.inventory_error = httpx.ConnectError("synthetic disconnected")
    elif failure == "malformed":
        api.inventory = None
    ledger = e.ExampleReceipts(tmp_path / "examples.db", CHANNEL)
    try:
        result = e.send_examples(api, ledger, specs[:1], CHANNEL, use_existing_emojis=True)
        assert result[0]["verified"] and len(api.posts) == 4
        saved = ledger.get(e.EXAMPLE_IDS[0])["spec"]
        assert saved == specs[0]
        assert "<:" not in json.dumps(saved)
        assert "Anti-Mage" in json.dumps(saved)
        if failure:
            assert "using text names" in caplog.text
    finally:
        ledger.conn.close()


@pytest.mark.parametrize("application", [None, {"id": "malformed/id"}, {"id": str(2**64)}])
def test_invalid_application_identity_never_enters_an_inventory_request_path(application):
    api = FakeDiscord()
    api.application = application
    assert e.existing_application_emojis(api) == {}
    assert api.reads == ["/oauth2/applications/@me"]
    assert api.posts == []


def test_changed_live_inventory_cannot_replace_saved_partial_payload(tmp_path, specs, monkeypatch):
    api = FakeDiscord()
    api.inventory = {"items": [
        {"name": "h_antimage", "id": "777777777777777777"},
        {"name": "h_juggernaut", "id": "888888888888888888"},
    ]}
    path = tmp_path / "examples.db"
    ledger = e.ExampleReceipts(path, CHANNEL)
    api.fail_stage = "radiant"
    with pytest.raises(KeyboardInterrupt):
        e.send_examples(api, ledger, specs[:1], CHANNEL, use_existing_emojis=True)
    saved = ledger.get(e.EXAMPLE_IDS[0])["spec"]
    assert "cards" in saved and saved["teams"][0]["_files"]
    ledger.conn.close()
    api.inventory = {"items": [{"name": "h_juggernaut", "id": "999999999999999999"}]}
    newer = e.build_examples(1)
    report_gallery(newer[0]["teams"][1])["items"][0]["description"] = "EXAMPLE changed renderer"
    newer[0].uploads = {"dire": {"wrong-after-upgrade.png": b"not the saved PNG"}}
    monkeypatch.setattr(e, "build_examples", Mock(return_value=newer))
    resumed = e.ExampleReceipts(path, CHANNEL)
    try:
        result = e.send_examples(api, resumed, specs[:1], CHANNEL, use_existing_emojis=True)[0]
        assert result["verified"] and len(api.posts) == 4
        assert resumed.get(e.EXAMPLE_IDS[0])["spec"] == saved
        actual = api.messages[(result["thread"], result["dire"])]
        assert scheduled.same_message(actual, saved["teams"][1])
        assert "999999999999999999" not in json.dumps(actual)
        assert "EXAMPLE changed renderer" not in json.dumps(actual)
        assert resumed.conn.execute("SELECT count(*) FROM example_pending_uploads").fetchone()[0] == 0
    finally:
        resumed.conn.close()
