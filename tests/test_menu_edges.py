"""Offline menu edge cases: temporary archives and synthetic interactions only."""

import asyncio
import copy
import json
import sqlite3
import threading
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest

from herald import board, ingest


DB_FILENAMES = [
    "archive.db",
    "archive#copy.db",
    "archive?copy.db",
    "archive%20copy.db",
    "Herald архив matches.db",
]


def configure_path(monkeypatch, tmp_path, filename, relative):
    """HERALD_DB is a filesystem path, never an already encoded SQLite URI."""
    path = tmp_path / filename
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(board, "DB_PATH", filename if relative else str(path))
    return path


def seed_archive(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE matches (match_id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO matches VALUES (42)")


@pytest.mark.parametrize("relative", [False, True], ids=["absolute", "relative"])
@pytest.mark.parametrize("filename", DB_FILENAMES)
def test_database_reader_opens_literal_path(tmp_path, monkeypatch, filename, relative):
    path = configure_path(monkeypatch, tmp_path, filename, relative)
    seed_archive(path)

    assert board._q_sync("SELECT match_id FROM matches") == [(42,)]
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize("relative", [False, True], ids=["absolute", "relative"])
@pytest.mark.parametrize("filename", DB_FILENAMES)
def test_database_reader_rejects_writes(tmp_path, monkeypatch, filename, relative):
    path = configure_path(monkeypatch, tmp_path, filename, relative)
    seed_archive(path)

    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        board._q_sync("CREATE TABLE write_probe (value INTEGER)")

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT match_id FROM matches").fetchall() == [(42,)]
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'write_probe'"
        ).fetchall() == []
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize("relative", [False, True], ids=["absolute", "relative"])
@pytest.mark.parametrize("filename", DB_FILENAMES)
def test_database_reader_never_creates_missing_archive(tmp_path, monkeypatch, filename, relative):
    configure_path(monkeypatch, tmp_path, filename, relative)

    with pytest.raises(sqlite3.OperationalError):
        board._q_sync("SELECT 1")

    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def menu_archive(tmp_path, monkeypatch):
    path = tmp_path / "menu.db"
    conn = ingest.get_conn(str(path))
    monkeypatch.setattr(board, "DB_PATH", str(path))
    monkeypatch.setattr(board, "thumb", AsyncMock(return_value=b"offline thumbnail"))
    monkeypatch.setattr(board.charts, "networth_lead_png", lambda *args: b"offline chart")
    yield conn
    conn.close()


def add_match(conn, mid, hero_replacements=None):
    hero_replacements = hero_replacements or {}
    ingest.upsert_match(conn, {
        "id": mid, "startDateTime": 1700000000 + mid, "durationSeconds": 4600,
        "didRadiantWin": True, "radiantKills": [50], "direKills": [40],
        "radiantNetworthLeads": [0, 1000], "players": [
            {"heroId": hero_replacements.get(i + 1, i + 1), "isRadiant": i < 5,
             "kills": 9, "deaths": 5,
             "assists": 6, "networth": 6000, "goldPerMinute": 300,
             "steamAccount": {"seasonRank": 12}, "stats": {}}
            for i in range(10)
        ],
    }, 12)


def interaction(*, acknowledged=False, ack_event=None, edits=None):
    itx = MagicMock()
    itx.response.is_done.return_value = acknowledged

    async def defer(**kwargs):
        itx.response.is_done.return_value = True
        if ack_event is not None:
            ack_event.set()

    async def edit(**kwargs):
        if edits is not None:
            edits.append(kwargs["view"])

    itx.response.defer = AsyncMock(side_effect=defer)
    itx.response.send_message = AsyncMock()
    itx.response.send_modal = AsyncMock()
    itx.followup.send = AsyncMock()
    itx.edit_original_response = AsyncMock(side_effect=edit)
    return itx


def controls(view):
    return {item.custom_id: item for item in view.walk_children()
            if getattr(item, "custom_id", None)}


async def test_overlapping_updates_keep_render_state_stable(menu_archive, monkeypatch):
    add_match(menu_archive, 1)
    view = await board.build_board(board.default_state())
    original_build = board.build_board
    entered, release, second_ack = asyncio.Event(), asyncio.Event(), asyncio.Event()
    renders, edits = [], []

    async def delayed_build(st):
        snapshot = copy.deepcopy(st)
        renders.append(snapshot)
        if len(renders) == 1:
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=5)
        assert st == snapshot, "another click mutated an in-flight render"
        return await original_build(st)

    monkeypatch.setattr(board, "build_board", delayed_build)
    first = asyncio.create_task(view._update(interaction(edits=edits), sort=["kills"]))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        second = asyncio.create_task(view._update(
            interaction(ack_event=second_ack, edits=edits), mode="focus", match=1))
        # A queued click must still be acknowledged before waiting for the render lock.
        await asyncio.wait_for(second_ack.wait(), timeout=5)
        release.set()
        await asyncio.gather(first, second)
    finally:
        release.set()
        await asyncio.gather(first, *([second] if second else []), return_exceptions=True)

    assert [st["mode"] for st in renders] == ["list", "focus"]
    assert [updated.st["mode"] for updated in edits] == ["list", "focus"]
    assert edits[-1].st["sort"] == ["kills"]
    assert edits[-1].st["match"] == 1


async def test_failed_update_preserves_displayed_state(menu_archive, monkeypatch):
    view = await board.build_board(board.default_state())
    before = copy.deepcopy(view.st)
    original_build = board.build_board
    failure = AsyncMock(side_effect=sqlite3.OperationalError("synthetic unavailable archive"))
    monkeypatch.setattr(board, "build_board", failure)
    failed = interaction()

    with pytest.raises(sqlite3.OperationalError):
        await view._update(failed, filters=["highrank"], sort=["dur"])

    failed.response.defer.assert_awaited_once()
    failed.edit_original_response.assert_not_awaited()
    assert view.st == before
    monkeypatch.setattr(board, "build_board", original_build)
    retry = interaction()
    await view._update(retry)
    assert retry.edit_original_response.await_args.kwargs["view"].st == before


async def test_two_queued_next_clicks_advance_twice(menu_archive):
    for mid in range(1, board.PAGE * 3 + 1):
        add_match(menu_archive, mid)
    view = await board.build_board(board.default_state())
    next_button = controls(view)["mb_pn"]
    edits = []

    await asyncio.gather(next_button.callback(interaction(edits=edits)),
                         next_button.callback(interaction(edits=edits)))

    assert [updated.st["page"] for updated in edits] == [1, 2]
    assert controls(edits[-1])["mb_pn"].disabled


@pytest.mark.parametrize("field,value", [
    ("dur", ">oops"),
    ("dur", ">-1"),
    ("min_kills", "many"),
    ("min_kills", "-1"),
    ("rank", "abc"),
    ("rank", "<-1"),
    ("items", "rapier xmany"),
    ("items", "rapier x0"),
    ("items", "rapier x-1"),
])
async def test_invalid_advanced_search_preserves_criteria(monkeypatch, field, value):
    state = board.default_state()
    state["adv"] = {"dur": (">=", 80), "min_kills": 90, "rank": None,
                    "heroes": [], "items": []}
    before = copy.deepcopy(state)
    modal = board.AdvModal(state)
    getattr(modal, field)._value = value
    rebuild = AsyncMock()
    monkeypatch.setattr(board, "build_board", rebuild)
    itx = interaction()

    await modal.on_submit(itx)

    itx.response.send_message.assert_awaited_once()
    assert itx.response.send_message.await_args.kwargs["ephemeral"] is True
    itx.response.defer.assert_not_awaited()
    itx.edit_original_response.assert_not_awaited()
    rebuild.assert_not_awaited()
    assert state == before


@pytest.mark.parametrize("acknowledged", [False, True])
async def test_advanced_modal_reports_errors_privately(acknowledged):
    modal = board.AdvModal(board.default_state())
    itx = interaction(acknowledged=acknowledged)

    await modal.on_error(itx, sqlite3.OperationalError("synthetic unavailable archive"))

    sender = itx.followup.send if acknowledged else itx.response.send_message
    sender.assert_awaited_once()
    assert sender.await_args.kwargs["ephemeral"] is True
    assert "archive" in sender.await_args.args[0].lower()


async def test_stale_advanced_modal_preserves_newer_filters(menu_archive):
    view = await board.build_board(board.default_state())
    open_modal = interaction()
    await controls(view)["mb_adv"].callback(open_modal)
    modal = open_modal.response.send_modal.await_args.args[0]

    await view._update(interaction(), filters=["highrank"])
    modal.dur._value = ">70"
    submitted = interaction()
    await modal.on_submit(submitted)

    updated = submitted.edit_original_response.await_args.kwargs["view"]
    assert updated.st["filters"] == ["highrank"]
    assert updated.st["adv"]["dur"] == (">", 70)


async def test_failed_message_edit_rolls_back_state(menu_archive):
    view = await board.build_board(board.default_state())
    before = copy.deepcopy(view.st)
    failed = interaction()
    failed.edit_original_response.side_effect = ConnectionError("synthetic edit failure")

    with pytest.raises(ConnectionError):
        await view._update(failed, filters=["highrank"])

    assert view.st == before
    retry = interaction()
    await view._update(retry)
    assert retry.edit_original_response.await_args.kwargs["view"].st == before


async def test_cancelled_render_releases_session_lock(menu_archive, monkeypatch):
    view = await board.build_board(board.default_state())
    before = copy.deepcopy(view.st)
    original_build = board.build_board
    entered = asyncio.Event()

    async def blocked_build(st):
        entered.set()
        await asyncio.Future()

    monkeypatch.setattr(board, "build_board", blocked_build)
    task = asyncio.create_task(view._update(interaction(), filters=["highrank"]))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert view.st == before
    monkeypatch.setattr(board, "build_board", original_build)
    retry = interaction()
    await asyncio.wait_for(view._update(retry), timeout=5)
    assert retry.edit_original_response.await_args.kwargs["view"].st == before


async def test_spoiler_focus_does_not_render_or_attach_graph(menu_archive, monkeypatch):
    add_match(menu_archive, 1)
    renderer = Mock(side_effect=AssertionError("spoiler focus must not render a graph"))
    monkeypatch.setattr(board.charts, "networth_lead_png", renderer)
    state = board.default_state()
    state.update(mode="focus", match=1, spoiler=True)

    view = await board.build_board(state)

    renderer.assert_not_called()
    assert view.files == []
    assert not any(isinstance(item, board.discord.ui.MediaGallery)
                   for item in view.walk_children())


async def test_thumbnail_cache_regenerates_when_leads_change(monkeypatch):
    monkeypatch.setattr(board, "_thumb_cache", OrderedDict())
    renderer = Mock(side_effect=lambda leads: repr(leads).encode())
    monkeypatch.setattr(board.charts, "thumb_spark_png", renderer)

    first = await board.thumb({"id": 42, "leads": [0, 1000]})
    unchanged = await board.thumb({"id": 42, "leads": [0, 1000]})
    changed = await board.thumb({"id": 42, "leads": [0, -9000]})

    assert first == unchanged
    assert changed != first
    assert renderer.call_count == 2


@pytest.mark.parametrize("slow_work", ["database", "chart"])
async def test_slow_work_is_acknowledged_and_does_not_block_loop(
        menu_archive, monkeypatch, slow_work):
    add_match(menu_archive, 1)
    view = await board.build_board(board.default_state())
    started, release = threading.Event(), threading.Event()
    acknowledged = asyncio.Event()
    original_query = board._q_sync

    def slow(*args, **kwargs):
        started.set()
        if not release.wait(timeout=5):
            raise AssertionError("slow work blocked the event loop")
        return original_query(*args, **kwargs) if slow_work == "database" else b"offline chart"

    if slow_work == "database":
        monkeypatch.setattr(board, "_q_sync", slow)
        changes = {"sort": ["kills"]}
    else:
        monkeypatch.setattr(board.charts, "networth_lead_png", slow)
        changes = {"mode": "focus", "match": 1}
    itx = interaction(ack_event=acknowledged)
    task = asyncio.create_task(view._update(itx, **changes))
    try:
        await asyncio.wait_for(acknowledged.wait(), timeout=2)
        assert await asyncio.to_thread(started.wait, 2)
        # The event loop can make progress while a worker is still deliberately blocked.
        assert await asyncio.wait_for(asyncio.sleep(0, result="responsive"), timeout=1) == "responsive"
        assert not task.done()
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=5)
    itx.edit_original_response.assert_awaited_once()


@pytest.mark.parametrize("bad_raw", [None, "{", "null", "[]", "{}"])
async def test_corrupt_raw_does_not_hide_healthy_matches(menu_archive, bad_raw):
    add_match(menu_archive, 1)
    add_match(menu_archive, 2)
    menu_archive.execute("UPDATE matches SET raw=? WHERE match_id=2", (bad_raw,))
    menu_archive.commit()

    assert [match["id"] for match in await board.hydrate([2, 1])] == [1]
    view = await board.build_board(board.default_state())
    assert [option.value for option in controls(view)["mb_open"].options] == ["1"]


@pytest.mark.parametrize("bad_field,value", [("players", None), ("players", [None]),
                                            ("durationSeconds", None)])
async def test_malformed_required_fields_do_not_hide_healthy_matches(menu_archive, bad_field, value):
    add_match(menu_archive, 1)
    add_match(menu_archive, 2)
    raw = json.loads(menu_archive.execute("SELECT raw FROM matches WHERE match_id=2").fetchone()[0])
    raw[bad_field] = value
    menu_archive.execute("UPDATE matches SET raw=? WHERE match_id=2", (json.dumps(raw),))
    menu_archive.commit()

    assert [match["id"] for match in await board.hydrate([2, 1])] == [1]
    view = await board.build_board(board.default_state())
    assert [option.value for option in controls(view)["mb_open"].options] == ["1"]


@pytest.mark.parametrize("mode", ["list", "focus"])
@pytest.mark.parametrize("bad_notes", [None, "{", "null", "{}", '[null, 42, "bad"]',
                                     '[{"score": "oops", "items": [1], "picks": [1]}]',
                                     '[{"score": 9, "items": [1], "picks": [1]}]'])
async def test_malformed_optional_notes_preserve_match(menu_archive, mode, bad_notes):
    add_match(menu_archive, 1)
    menu_archive.execute("UPDATE matches SET weirdness=9, skill_weirdness=9,"
                         " weird_notes=?, skill_notes=?", (bad_notes, bad_notes))
    menu_archive.commit()
    state = board.default_state()
    state.update(mode=mode, match=1 if mode == "focus" else None)

    view = await board.build_board(state)

    if mode == "list":
        assert [option.value for option in controls(view)["mb_open"].options] == ["1"]
    else:
        assert view.st["match"] == 1
        assert "Match 1" in json.dumps(view.to_components())


@pytest.mark.parametrize("missing_schema", [False, True], ids=["missing-file", "missing-schema"])
async def test_unavailable_archive_callback_preserves_state(
        menu_archive, tmp_path, monkeypatch, missing_schema):
    view = await board.build_board(board.default_state())
    before = copy.deepcopy(view.st)
    path = tmp_path / "unavailable.db"
    if missing_schema:
        sqlite3.connect(path).close()
    monkeypatch.setattr(board, "DB_PATH", str(path))
    itx = interaction()

    try:
        await view._update(itx, filters=["highrank"])
    except sqlite3.Error as error:
        await view.on_error(itx, error, None)

    itx.response.defer.assert_awaited_once()
    itx.edit_original_response.assert_not_awaited()
    itx.followup.send.assert_awaited_once()
    assert itx.followup.send.await_args.kwargs["ephemeral"] is True
    assert view.st == before
    assert view.session.state == before
    assert path.exists() is missing_schema


async def test_prior_view_timeout_does_not_expire_replacement(menu_archive):
    old = await board.build_board(board.default_state())
    itx = interaction()
    await old._update(itx, sort=["kills"])
    current = itx.edit_original_response.await_args.kwargs["view"]
    assert old.is_finished()

    await old.on_timeout()

    assert current.session.expired is False
    assert current.session.current_view is current
    await current._update(interaction(), sort=["dur"])


async def test_expiry_disables_actions_but_preserves_links(menu_archive, monkeypatch):
    add_match(menu_archive, 1)
    state = board.default_state()
    state.update(mode="focus", match=1)
    view = await board.build_board(state)
    before = copy.deepcopy(view.st)
    last = interaction()
    view.session.last_interaction = last

    await view.on_timeout()

    assert view.timeout == board.MENU_TIMEOUT
    assert view.session.expired
    for item in view.walk_children():
        if isinstance(item, board.discord.ui.Button) and item.url:
            assert not item.disabled
        elif isinstance(item, (board.discord.ui.Button, board.discord.ui.Select)):
            assert item.disabled
    assert "/heralds" in json.dumps(view.to_components())
    last.edit_original_response.assert_awaited_once()
    rebuild = AsyncMock(side_effect=AssertionError("expired menus must not query"))
    monkeypatch.setattr(board, "build_board", rebuild)
    clicked = interaction()
    await view._update(clicked, filters=["highrank"])
    clicked.response.defer.assert_awaited_once()
    clicked.followup.send.assert_awaited_once()
    assert clicked.followup.send.await_args.kwargs["ephemeral"] is True
    assert "/heralds" in clicked.followup.send.await_args.args[0]
    clicked.edit_original_response.assert_not_awaited()
    rebuild.assert_not_awaited()
    assert view.st == before and view.session.state == before


async def test_deleted_message_expires_session_and_gives_private_reopen(menu_archive):
    view = await board.build_board(board.default_state())
    before = copy.deepcopy(view.st)
    itx = interaction()
    error = board.discord.NotFound(MagicMock(status=404, reason="Not Found"), "Unknown message")
    itx.edit_original_response.side_effect = error

    with pytest.raises(board.discord.NotFound):
        await view._update(itx, filters=["highrank"])
    await view.on_error(itx, error, None)

    assert view.session.expired
    assert view.st == before and view.session.state == before
    itx.followup.send.assert_awaited_once()
    assert itx.followup.send.await_args.kwargs["ephemeral"] is True
    assert "/heralds" in itx.followup.send.await_args.args[0]


async def test_empty_dice_notice_is_not_retained(menu_archive):
    view = await board.build_board(board.default_state())
    first = interaction()
    await view._update(first, random=True)
    noticed = first.edit_original_response.await_args.kwargs["view"]
    assert "No matches fit" in json.dumps(noticed.to_components())
    assert "notice" not in noticed.session.state
    second = interaction()

    await noticed._update(second, sort=["kills"])

    updated = second.edit_original_response.await_args.kwargs["view"]
    assert "No matches fit" not in json.dumps(updated.to_components())


@pytest.mark.parametrize("heroes,expected", [
    (["axe"], {1, 2}),
    (["bane"], {1, 3}),
    (["axe", "bane"], {1}),
    (["axe", "axe"], {1, 2}),
    (["not-a-real-hero"], set()),
])
async def test_advanced_heroes_require_every_requested_hero(menu_archive, heroes, expected):
    add_match(menu_archive, 1)
    add_match(menu_archive, 2, {3: 14})  # Axe without Bane.
    add_match(menu_archive, 3, {2: 14})  # Bane without Axe.
    state = board.default_state()
    state["adv"] = {"heroes": heroes}

    total, matches, _ = await board.select_page(state)

    assert total == len(expected)
    assert {match["id"] for match in matches} == expected


async def test_thumbnail_cache_is_scoped_to_archive_path(tmp_path, monkeypatch):
    monkeypatch.setattr(board, "_thumb_cache", OrderedDict())
    renderer = Mock(side_effect=[b"first archive", b"second archive"])
    monkeypatch.setattr(board.charts, "thumb_spark_png", renderer)
    match = {"id": 42, "leads": [0, 1000]}
    monkeypatch.setattr(board, "DB_PATH", str(tmp_path / "first.db"))
    first = await board.thumb(match)
    monkeypatch.setattr(board, "DB_PATH", str(tmp_path / "second.db"))

    second = await board.thumb(match)

    assert first == b"first archive" and second == b"second archive"
    assert renderer.call_count == 2


async def test_concurrent_thumbnail_requests_share_work_after_cancellation(monkeypatch):
    monkeypatch.setattr(board, "_thumb_cache", OrderedDict())
    monkeypatch.setattr(board, "_chart_jobs", {})
    entered, release = threading.Event(), threading.Event()

    def render_once(leads):
        entered.set()
        if not release.wait(timeout=5):
            raise AssertionError("renderer was never released")
        return b"one shared thumbnail"

    renderer = Mock(side_effect=render_once)
    monkeypatch.setattr(board.charts, "thumb_spark_png", renderer)
    match = {"id": 42, "leads": [0, 1000]}
    first = asyncio.create_task(board.thumb(match))
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        second = asyncio.create_task(board.thumb(match))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert await asyncio.wait_for(second, timeout=5) == b"one shared thumbnail"
    finally:
        release.set()
        await asyncio.gather(first, *([second] if second else []), return_exceptions=True)
    assert renderer.call_count == 1
    assert await board.thumb(match) == b"one shared thumbnail"
    assert renderer.call_count == 1


async def test_failed_chart_job_can_be_retried(monkeypatch):
    monkeypatch.setattr(board, "_thumb_cache", OrderedDict())
    monkeypatch.setattr(board, "_chart_jobs", {})
    renderer = Mock(side_effect=[RuntimeError("synthetic chart error"), b"recovered"])
    monkeypatch.setattr(board.charts, "thumb_spark_png", renderer)
    match = {"id": 42, "leads": [0, 1000]}

    with pytest.raises(RuntimeError, match="synthetic chart error"):
        await board.thumb(match)

    assert await board.thumb(match) == b"recovered"
    assert renderer.call_count == 2


async def test_failed_guild_sync_does_not_block_other_guilds(monkeypatch, caplog):
    first, second = MagicMock(id=101), MagicMock(id=202)
    client = MagicMock(guilds=[first, second])
    client.fetch_application_emojis = AsyncMock(return_value=[])
    forbidden = board.discord.Forbidden(
        MagicMock(status=403, reason="Forbidden"), "Synthetic guild permission failure")
    tree = MagicMock()
    tree.sync = AsyncMock(side_effect=[forbidden, []])
    monkeypatch.setattr(board, "client", client)
    monkeypatch.setattr(board, "tree", tree)
    monkeypatch.setattr(board.render, "_emoji", {})

    await board.on_ready()

    assert tree.copy_global_to.call_args_list == [call(guild=first), call(guild=second)]
    assert tree.sync.await_args_list == [call(guild=first), call(guild=second)]
    assert "guild 101" in caplog.text
