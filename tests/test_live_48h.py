"""Offline-only tests for the separate one-shot runner proposal."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import re

import pytest

runner = Path(__file__).with_name("live_48h.py")
if not runner.is_file():
    runner = Path(__file__).resolve().parents[1] / "scripts/live_48h_20261007.py"
spec = importlib.util.spec_from_file_location("live_48h", runner)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def snowflake(timestamp):
    return str((timestamp * 1000 - 1420070400000) << 22)


class History:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def request(self, method, route, **kwargs):
        assert method == "GET"
        self.calls.append(route)
        return self.pages.pop(0)


def message(ts, **extra):
    return {"id": snowflake(ts), "channel_id": live.CHANNEL,
            "author": {"id": live.BOT}, **extra}


def test_plan_has_exact_requested_window_and_cap():
    plan = live.plan()
    assert plan["window_utc"] == ["2026-10-05T03:16:36+00:00", "2026-10-07T03:16:36+00:00"]
    assert plan["post_budget"] == 5
    assert plan["candidate_budget"] == 500


@pytest.mark.parametrize("changes", [
    {"GITHUB_ACTIONS": "false"}, {"GITHUB_REPOSITORY": "other/repo"},
    {"GITHUB_RUN_ATTEMPT": "2"}, {"RUNNER_DEBUG": "1"},
])
def test_runner_guard_rejects(changes, monkeypatch):
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": live.REPOSITORY,
                       "GITHUB_RUN_ATTEMPT": "1", "RUNNER_DEBUG": "0", **changes}.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(live.Stop):
        live.runner_guard()


def test_duplicate_identity_from_nonce_old_description_and_clean_link():
    row = message(live.START + 10, nonce="789:parent", embeds=[
        {"url": "https://stratz.com/matches/123"},
        {"description": "Match 456 · date\n[OpenDota](https://www.opendota.com/matches/111)"}])
    assert live.message_match_ids(row) == {789, 123, 456, 111}
    row["author"]["id"] = "other"
    assert live.message_match_ids(row) == set()


def test_history_exhaustion_and_oldest_cutoff_are_both_complete():
    api = History([[message(live.END, nonce="123:parent")]])
    found, proof = live.existing_matches(api)
    assert found == {123} and proof["complete"] is True
    rows = [message(live.START + 50 - i) for i in range(100)]
    found, proof = live.existing_matches(History([rows]))
    assert proof["pages"] == 1 and proof["messages_examined"] == 100


def test_history_budget_never_assumes_no_duplicates():
    pages = [[message(live.END - j * 100 - i) for i in range(100)] for j in range(10)]
    with pytest.raises(live.Stop, match="1,000-message"):
        live.existing_matches(History(pages))


@pytest.mark.parametrize("rows", [None, {}, [message(live.END, channel_id="other")],
    [message(live.END - 10), message(live.END)], [message(live.END), message(live.END)]])
def test_invalid_history_fails_closed(rows):
    with pytest.raises(live.Stop):
        live.existing_matches(History([rows]))


def test_identity_checks_exact_bot_and_guild():
    good = [{"id": live.BOT, "bot": True}, {"id": live.CHANNEL, "guild_id": live.GUILD, "type": 0}]
    live.identity(History(good))
    for index, key, value in [(0, "id", "wrong"), (0, "bot", False), (1, "guild_id", "wrong"), (1, "type", 1)]:
        changed = copy.deepcopy(good)
        changed[index][key] = value
        with pytest.raises(live.Stop):
            live.identity(History(changed))


@pytest.fixture
def pipeline(monkeypatch):
    import httpx
    from herald import api, scheduled, examples
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "offline-synthetic-token")
    monkeypatch.setenv("STRATZ_API_TOKEN", "offline-synthetic-token")
    monkeypatch.setenv("REVIEWED_SOURCE_SHA", "a" * 40)
    monkeypatch.setattr(live.time, "sleep", lambda _: None)
    fixture = examples.synthetic_match()
    fake_data = {}
    def candidate(mid):
        c, raw, od = copy.deepcopy(fixture)
        c.update(match_id=mid, start_time=live.START + mid)
        raw["id"] = mid
        od["match_id"] = mid
        fake_data[mid] = (c, raw, od)
        return c
    candidates = [candidate(i) for i in range(1, 8)]

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            mid = int(url.rsplit("/", 1)[1])
            class Response:
                status_code = 200
                headers = {}
                def raise_for_status(self): pass
                def json(self): return copy.deepcopy(fake_data[mid][2])
            return Response()
        def post(self, *args, **kwargs):
            raise AssertionError("Unexpected provider POST outside mocked pipeline")

    class Discord:
        def __init__(self, *args): pass
        def request(self, method, route, **kwargs):
            assert method == "GET", "Preparation attempted an external write"
            if route == "/users/@me": return {"id": live.BOT, "bot": True}
            if route == f"/channels/{live.CHANNEL}": return {"id": live.CHANNEL, "guild_id": live.GUILD, "type": 0}
            if route.startswith(f"/channels/{live.CHANNEL}/messages?"): return []
            if route == "/oauth2/applications/@me": return {"id": "app"}
            if route == "/applications/app/emojis": return {"items": []}
            raise AssertionError(route)
    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr(scheduled, "DiscordHTTP", Discord)
    monkeypatch.setattr(scheduled, "discover", lambda client, end, backfill: candidates)
    monkeypatch.setattr(api, "stratz_fetch_batch", lambda client, ids, fields, strict:
                        {mid: copy.deepcopy(fake_data[mid][1]) for mid in ids})
    monkeypatch.setattr(live, "prepare_icons", lambda selected, scheduled, fetch:
                        {"needed": 0, "downloaded": [], "fallbacks": [], "fetch_authorized": fetch})
    return scheduled, candidates, fake_data


def test_preparation_freezes_real_pipeline_specs_but_never_posts(tmp_path, pipeline):
    audit = tmp_path / "audit"
    live.prepare(audit)
    state = json.loads((audit / "result.json").read_text())
    assert state["phase"] == "prepared_no_discord_writes"
    assert state["selected_match_ids"] == [1, 2, 3, 4, 5]
    assert state["counts"] == {"found": 7, "existing": 0, "hydrated": 7,
        "stratz_missing": 0, "ineligible": 0, "eligible": 7, "selected": 5,
        "posted": 0, "deferred_post_cap": 2, "truncated": True}
    with sqlite3.connect(audit / "receipts.sqlite3") as db:
        rows = db.execute("SELECT data FROM deliveries").fetchall()
        assert len(rows) == 5
        assert db.execute("SELECT count(*) FROM pending_uploads").fetchone()[0] == 10
        assert db.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 0
    for (data,) in rows:
        receipt = json.loads(data)
        assert "inflight" not in receipt and "verified" not in receipt
        assert len(receipt["spec"]["teams"]) == 2
        assert receipt["spec"]["parent"]["embeds"][0]["url"].startswith("https://stratz.com/matches/")
        evidence = receipt["spec"]["build_evidence"]
        assert evidence["reference"]["matches"] == 0
        assert all(entry["status"] == "unscored" for kind in ("items", "skills") for entry in evidence[kind].values())
    assert hashlib.sha256((audit / "receipts.sqlite3").read_bytes()).hexdigest() == state["prepared_db_sha256"]


def test_candidate_cap_stops_before_hydration_and_posts(tmp_path, pipeline):
    _, candidates, _ = pipeline
    candidates.extend(copy.deepcopy(candidates[0]) for _ in range(501 - len(candidates)))
    with pytest.raises(live.Stop, match="provider budget"):
        live.prepare(tmp_path / "audit")
    state = json.loads((tmp_path / "audit/result.json").read_text())
    assert state["counts"]["hydrated"] == 0 and state["counts"]["posted"] == 0


def test_missing_secret_stops_before_any_http(tmp_path, pipeline, monkeypatch):
    monkeypatch.delenv("STRATZ_API_TOKEN")
    with pytest.raises(live.Stop, match="secret is absent"):
        live.prepare(tmp_path / "audit")


def test_send_requires_artifact_and_database_digest(tmp_path, pipeline, monkeypatch):
    audit = tmp_path / "audit"
    live.prepare(audit)
    monkeypatch.delenv("PREPARED_ARTIFACT_ID", raising=False)
    with pytest.raises(live.Stop, match="upload must succeed"):
        live.send(audit)
    monkeypatch.setenv("PREPARED_ARTIFACT_ID", "555")
    with (audit / "receipts.sqlite3").open("ab") as stream: stream.write(b"changed")
    with pytest.raises(live.Stop, match="database changed"):
        live.send(audit)


def test_send_preserves_cap_receipts_and_refuses_second_send(tmp_path, pipeline, monkeypatch):
    scheduled, _, _ = pipeline
    audit = tmp_path / "audit"
    live.prepare(audit)
    monkeypatch.setenv("PREPARED_ARTIFACT_ID", "555")
    calls = []
    def deliver(api, ledger, spec, channel, bot):
        calls.append(spec["match_id"])
        assert channel == live.CHANNEL and bot == live.BOT
        receipt = ledger.get(spec["match_id"])
        receipt.update(parent=str(100 + spec["match_id"]), thread=str(200 + spec["match_id"]),
                       radiant=str(300 + spec["match_id"]), dire=str(400 + spec["match_id"]),
                       verified=True, verified_at=live.END + 60)
        ledger.finish(receipt)
        original_request = api.request
        api.request = lambda method, route, **kwargs: ({"embeds": spec["parent"]["embeds"]}
            if route == f"/channels/{live.CHANNEL}/messages/{receipt['parent']}"
            else original_request(method, route, **kwargs))
        return receipt
    monkeypatch.setattr(scheduled, "deliver", deliver)
    live.send(audit)
    assert calls == [1, 2, 3, 4, 5]
    state = json.loads((audit / "result.json").read_text())
    assert state["counts"]["posted"] == 5 and len(state["receipts"]) == 5
    with pytest.raises(live.Stop, match="unchanged prepared manifest"):
        live.send(audit)


def test_new_duplicate_after_prepare_blocks_all_sends(tmp_path, pipeline, monkeypatch):
    scheduled, _, _ = pipeline
    audit = tmp_path / "audit"
    live.prepare(audit)
    monkeypatch.setenv("PREPARED_ARTIFACT_ID", "555")
    monkeypatch.setattr(live, "existing_matches", lambda discord: ({3}, {"complete": True}))
    monkeypatch.setattr(scheduled, "deliver", lambda *args: pytest.fail("Duplicate preflight must precede any POST"))
    with pytest.raises(live.Stop, match="posted after preparation"):
        live.send(audit)


def test_asset_keys_are_only_from_selected_cards_and_headline(pipeline):
    scheduled, _, fake = pipeline
    c, raw, od = fake[1]
    evidence = scheduled.reporter_novelty.unavailable(raw)
    keys = live.selected_icon_keys([(c, raw, od, evidence)], scheduled)
    assert "hero_8" in keys and "item_133" in keys
    assert "hero_145" not in keys and all(repr(key) for key in keys)


@pytest.mark.parametrize("bad_id", [None, 12345, True, "1"])
def test_stratz_wrong_or_missing_identity_stops_before_detail(tmp_path, pipeline, bad_id):
    _, _, fake = pipeline
    fake[1][1]["id"] = bad_id
    with pytest.raises(live.Stop, match="STRATZ detail"):
        live.prepare(tmp_path / "audit")


def test_prepare_failure_after_scoring_purges_reference_and_retains_no_raw_accounts(tmp_path, pipeline, monkeypatch):
    scheduled, _, _ = pipeline
    def fail(*args):
        raise live.Stop("Synthetic offline rendering failure")
    monkeypatch.setattr(live, "prepare_icons", fail)
    audit = tmp_path / "audit"
    with pytest.raises(live.Stop, match="rendering failure"):
        live.prepare(audit)
    with sqlite3.connect(audit / "receipts.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM deliveries").fetchone()[0] == 0
    assert b"steamAccount" not in (audit / "receipts.sqlite3").read_bytes()


def test_partial_send_stops_and_refuses_retry_with_all_frozen_intents_preserved(tmp_path, pipeline, monkeypatch):
    scheduled, _, _ = pipeline
    audit = tmp_path / "audit"
    live.prepare(audit)
    monkeypatch.setenv("PREPARED_ARTIFACT_ID", "555")
    calls = []
    def partial_delivery(api, ledger, spec, channel, bot):
        calls.append(spec["match_id"])
        receipt = ledger.get(spec["match_id"])
        if len(calls) == 2:
            receipt["inflight"] = "parent"
            ledger.save(receipt)
            raise RuntimeError("Synthetic uncertain second send")
        receipt.update(parent="101", thread="201", radiant="301", dire="401", verified=True, verified_at=live.END + 1)
        ledger.finish(receipt)
        original_request = api.request
        api.request = lambda method, route, **kwargs: ({"embeds": spec["parent"]["embeds"]}
            if route == f"/channels/{live.CHANNEL}/messages/101" else original_request(method, route, **kwargs))
        return receipt
    monkeypatch.setattr(scheduled, "deliver", partial_delivery)
    with pytest.raises(RuntimeError, match="uncertain second send"):
        live.send(audit)
    assert calls == [1, 2]
    state = json.loads((audit / "result.json").read_text())
    assert state["phase"] == "sending_do_not_retry" and state["counts"]["posted"] == 1
    with sqlite3.connect(audit / "receipts.sqlite3") as db:
        rows = [json.loads(data) for data, in db.execute("SELECT data FROM deliveries ORDER BY match_id")]
        assert len(rows) == 5 and all("spec" in row for row in rows)
        assert rows[0]["verified"] is True and rows[1]["inflight"] == "parent"
        assert db.execute("SELECT count(*) FROM pending_uploads").fetchone()[0] == 8
    with pytest.raises(live.Stop, match="unchanged prepared manifest"):
        live.send(audit)
    assert calls == [1, 2]


def test_preparation_missing_icons_stops_before_freezing_or_posting(tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(live, "prepare_icons", lambda *args: {
        "needed": 2, "missing_before": ["ability_999999"], "fallbacks": ["ability_999999"], "downloaded": []})
    audit = tmp_path / "audit"
    with pytest.raises(live.Stop, match="artwork is incomplete"):
        live.prepare(audit)
    state = json.loads((audit / "result.json").read_text())
    assert state["icons"]["fallbacks"] == ["ability_999999"] and state["counts"]["posted"] == 0
    with sqlite3.connect(audit / "receipts.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM deliveries").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 0


def test_selected_existing_icons_are_validated_and_get_source_provenance(tmp_path, monkeypatch):
    from PIL import Image
    from herald import card_images, scheduled
    monkeypatch.setattr(card_images, "ASSET_DIR", tmp_path)
    monkeypatch.setattr(live, "selected_icon_keys", lambda *args: {"hero_1", "item_133"})
    Image.new("RGB", (10, 10)).save(tmp_path / "hero_1.png")
    (tmp_path / "item_133.png").write_bytes(b"corrupt file")
    result = live.prepare_icons([], scheduled, False)
    assert result["already_bundled"] == 1 and result["fallbacks"] == ["item_133"]
    provenance = json.loads((tmp_path / "sources.json").read_text())
    assert provenance["hero_1"].endswith("/heroes/antimage.png")
    assert "item_133" not in provenance


def test_icon_budget_failure_returns_missing_counts_without_downloads(tmp_path, monkeypatch):
    from herald import card_images, scheduled
    monkeypatch.setattr(card_images, "ASSET_DIR", tmp_path)
    monkeypatch.setattr(live, "MAX_ICON_DOWNLOADS", 1)
    monkeypatch.setattr(live, "selected_icon_keys", lambda *args: {"hero_1", "item_133"})
    result = live.prepare_icons([], scheduled, True)
    assert result["blocked"] == "selected_icon_download_budget_exceeded"
    assert result["needed"] == 2 and result["downloaded"] == []
    assert result["fallbacks"] == ["hero_1", "item_133"]


def clean_parent(mid=42):
    return {"embeds": [{"title": "122 kills in 82 minutes", "description": "Radiant 55 · Dire 67",
                        "color": 0xC8A03C, "url": f"https://stratz.com/matches/{mid}"}]}


def parent_response(mid=42, **extra):
    return {**clean_parent(mid), "id": "222", "channel_id": live.CHANNEL,
            "author": {"id": live.BOT}, **extra}


def test_strict_recovery_ignores_identical_quiet_text_for_different_match():
    import httpx
    from herald import scheduled
    routes = []
    def handler(request):
        assert request.method == "GET"
        routes.append(str(request.url))
        return httpx.Response(200, json=[parent_response(41)])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = live.delivery_api(client, "offline-synthetic-token", scheduled)
        api.begin_report({"parent": clean_parent(42)})
        assert api.find_message(live.CHANNEL, live.BOT, clean_parent(42), "42:parent") is None
    assert len(routes) == 1


def test_same_nonce_wrong_match_identity_blocks_recovery():
    import httpx
    from herald import scheduled
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json=[parent_response(41, nonce="42:parent")])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = live.delivery_api(client, "offline-synthetic-token", scheduled)
        api.begin_report({"parent": clean_parent(42)})
        with pytest.raises(live.Stop, match="Same-nonce parent"):
            api.find_message(live.CHANNEL, live.BOT, clean_parent(42), "42:parent")


@pytest.mark.parametrize("method,path", [
    ("GET", f"/channels/{live.CHANNEL}/messages/222"),
    ("POST", f"/channels/{live.CHANNEL}/messages/222/threads"),
])
def test_wrong_parent_readback_stops_before_thread_writes(method, path):
    import httpx
    from herald import scheduled
    requests = []
    def handler(request):
        requests.append(request.method)
        return httpx.Response(200, json=parent_response(41))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = live.delivery_api(client, "offline-synthetic-token", scheduled)
        api.begin_report({"parent": clean_parent(42)})
        with pytest.raises(live.Stop, match="before thread/team writes"):
            api.request(method, path, **({"json": {"name": "new thread"}} if method == "POST" else {}))
    assert requests == ["GET"]


def test_new_parent_wrong_response_never_reaches_thread_or_team_writes(tmp_path):
    import httpx
    from herald import examples, scheduled
    candidate, raw, od = examples.synthetic_match()
    candidate["match_id"] = 42
    spec = scheduled.payload(candidate, raw, od, {})
    requests = []
    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET":
            assert request.url.params.get("limit") == "100"
            return httpx.Response(200, json=[])
        assert request.method == "POST" and request.url.path.endswith(f"/channels/{live.CHANNEL}/messages")
        obj = json.loads(request.content)
        obj.update(id="222", channel_id=live.CHANNEL, author={"id": live.BOT})
        obj["embeds"][0]["url"] = "https://stratz.com/matches/41"
        return httpx.Response(200, json=obj)
    ledger = scheduled.Receipts(tmp_path / "strict.sqlite3")
    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            api = live.delivery_api(client, "offline-synthetic-token", scheduled)
            api.begin_report(spec)
            with pytest.raises(live.Stop, match="before thread/team writes"):
                scheduled.deliver(api, ledger, spec, live.CHANNEL, live.BOT)
        assert sum(method == "POST" for method, _ in requests) == 1
        assert ledger.get(42)["inflight"] == "parent"
        assert "thread" not in ledger.get(42)
    finally:
        ledger.conn.close()


def test_exact_parent_proxy_metadata_is_safe_to_recover():
    import httpx
    from herald import scheduled
    expected = clean_parent(42)
    expected["embeds"][0]["author"] = {"name": "Juggernaut", "icon_url": "https://cdn.cloudflare.steamstatic.com/example.png"}
    actual = {**copy.deepcopy(expected), "id": "222", "author": {"id": live.BOT}, "channel_id": live.CHANNEL}
    actual["embeds"][0]["type"] = "rich"
    actual["embeds"][0]["author"]["proxy_icon_url"] = "https://images-ext-1.discordapp.net/proxy.png"
    assert live.authored_parent_matches(actual, expected)
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[actual]))) as client:
        api = live.delivery_api(client, "offline-synthetic-token", scheduled)
        api.begin_report({"parent": expected})
        assert api.find_message(live.CHANNEL, live.BOT, expected, "42:parent")["id"] == "222"


def test_diagnostics_strip_auth_query_and_arbitrary_paths(tmp_path):
    import httpx
    hidden = "never-print-this-secret"
    url = f"https://api.opendota.com/api/matches/42?key={hidden}"
    state = {}
    class Client:
        def get(self, target, **kwargs):
            return httpx.Response(403, json={"error": hidden}, headers={"X-Secret": hidden},
                                  request=httpx.Request("GET", target, headers={"Authorization": hidden}))
    audited = live.AuditedReadClient(Client(), state, tmp_path)
    response = audited.get(url, headers={"Authorization": hidden})
    assert response.status_code == 403
    text = (tmp_path / "result.json").read_text()
    assert hidden not in text and "?" not in text and "Authorization" not in text
    assert state["last_http"] == {"provider": "opendota", "method": "GET", "path": "/api/matches/42",
                                   "status_code": 403, "outcome": "response"}
    assert live.safe_request_identity("GET", f"https://api.opendota.com/{hidden}")["path"] == "[redacted]"
    assert live.safe_request_identity("GET", f"https://evil.example/api/matches/42?{hidden}")["provider"] == "unknown"


def detail_responses(tmp_path, monkeypatch, responses):
    import httpx
    state, calls, sleeps = {}, [], []
    monkeypatch.setattr(live.time, "sleep", sleeps.append)
    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            status, headers = item
            return httpx.Response(status, headers=headers, json={"match_id": 42}, request=httpx.Request("GET", url))
    return live.AuditedReadClient(Client(), state, tmp_path), state, calls, sleeps


@pytest.mark.parametrize("status", [400, 401, 403, 404, 418])
def test_permanent_detail_errors_never_retry_or_switch_routes(tmp_path, monkeypatch, status):
    import httpx
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [(status, {})])
    with pytest.raises(httpx.HTTPStatusError):
        live.opendota_detail(client, 42, state, tmp_path)
    assert len(calls) == 1 and sleeps == []
    assert state["last_http"]["status_code"] == status
    assert state["stage"] == "opendota_detail" and state["current_match_id"] == 42


def test_detail_429_honors_retry_after_then_recovers(tmp_path, monkeypatch):
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [(429, {"Retry-After": "3.5"}), (200, {})])
    assert live.opendota_detail(client, 42, state, tmp_path) == {"match_id": 42}
    assert sleeps == [3.5] and len(calls) == 2 and len(set(calls)) == 1
    assert state["recent_retries"][0]["status_code"] == 429


def test_detail_5xx_is_bounded_to_four_attempts(tmp_path, monkeypatch):
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [(503, {})] * 4)
    with pytest.raises(live.Stop, match="after four attempts"):
        live.opendota_detail(client, 42, state, tmp_path)
    assert len(calls) == 4 and sleeps == [2, 4, 8]
    assert state["last_http"]["status_code"] == 503


def test_transport_retry_is_read_only_and_sanitizes_exception(tmp_path, monkeypatch):
    import httpx
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [httpx.ReadTimeout("secret-in-exception"), (200, {})])
    assert live.opendota_detail(client, 42, state, tmp_path) == {"match_id": 42}
    assert len(calls) == 2 and sleeps == [2]
    assert "secret-in-exception" not in (tmp_path / "result.json").read_text()


def test_retry_after_http_date_and_invalid_values():
    import httpx
    from email.utils import format_datetime
    from datetime import datetime, timezone
    now = 1704067200
    value = format_datetime(datetime.fromtimestamp(now + 20, timezone.utc), usegmt=True)
    assert live.retry_delay(httpx.Response(429, headers={"Retry-After": value}), 1, now=now) == 20
    for malformed in ("nan", "inf", "-1", "not-a-date"):
        assert live.retry_delay(httpx.Response(429, headers={"Retry-After": malformed}), 1, now=now) == 10


def test_long_retry_after_stops_instead_of_retrying_early(tmp_path, monkeypatch):
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [(429, {"Retry-After": "999"})])
    with pytest.raises(live.Stop, match="exceeds"):
        live.opendota_detail(client, 42, state, tmp_path)
    assert len(calls) == 1 and sleeps == []
    assert state["retry_stop"] == "provider_wait_exceeds_bounded_budget"


def test_cumulative_retry_wait_has_a_bound(tmp_path, monkeypatch):
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [(429, {"Retry-After": "60"})] * 2)
    with pytest.raises(live.Stop, match="exceeds"):
        live.opendota_detail(client, 42, state, tmp_path)
    assert len(calls) == 2 and sleeps == [60]


def test_total_detail_request_budget_is_bounded(tmp_path, monkeypatch):
    client, state, calls, sleeps = detail_responses(tmp_path, monkeypatch, [])
    state["detail_http_attempts"] = live.MAX_DETAIL_HTTP_ATTEMPTS
    with pytest.raises(live.Stop, match="request budget exhausted"):
        live.opendota_detail(client, 42, state, tmp_path)
    assert calls == [] and sleeps == []


def test_failed_prepare_persists_exact_http_diagnostic_and_live_selection_counts(tmp_path, pipeline, monkeypatch):
    import httpx
    scheduled, _, _ = pipeline
    original = live.opendota_detail
    def fail_on_six(client, mid, state, audit):
        if mid == 6:
            state.update(stage="opendota_detail", current_match_id=mid, last_http={
                "provider": "opendota", "method": "GET", "path": "/api/matches/6", "status_code": 403, "outcome": "response"})
            raise httpx.HTTPStatusError("secret-message", request=httpx.Request("GET", "https://api.opendota.com/api/matches/6?secret=secret"), response=httpx.Response(403))
        return original(client, mid, state, audit)
    monkeypatch.setattr(live, "opendota_detail", fail_on_six)
    audit = tmp_path / "audit"
    with pytest.raises(httpx.HTTPStatusError):
        live.prepare(audit)
    state = json.loads((audit / "result.json").read_text())
    assert state["phase"] == "prepare_failed_no_discord_writes" and state["hydration_complete"] is False
    assert state["counts"]["selected"] == 5 and state["selected_match_ids"] == [1, 2, 3, 4, 5]
    assert state["error"]["match_id"] == 6 and state["error"]["last_http"]["status_code"] == 403
    assert "secret" not in json.dumps(state["error"])
    with sqlite3.connect(audit / "receipts.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM deliveries").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM report_builds").fetchone()[0] == 0
