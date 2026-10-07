"""Independent menu/callback/archive regressions using disposable fixtures only."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from herald import board, ingest, render


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


@pytest.fixture
def archive(tmp_path, monkeypatch):
    path = tmp_path / "independent.db"
    db = ingest.get_conn(str(path))
    monkeypatch.setattr(board, "DB_PATH", str(path))
    monkeypatch.setattr(render, "_emoji", {})
    monkeypatch.setattr(board.charts, "thumb_spark_png", lambda *_: b"offline chart")
    monkeypatch.setattr(board.charts, "networth_lead_png", lambda *_: b"offline chart")
    monkeypatch.setattr(board, "_thumb_cache", board.OrderedDict())
    monkeypatch.setattr(board, "_focus_cache", board.OrderedDict())
    for mid in (801, 802):
        ingest.upsert_match(db, synthetic_match(mid), 12)
    yield db
    db.close()


@pytest.mark.parametrize("mode", ["list", "focus"])
@pytest.mark.parametrize("path,value", [
    (("players", 0, "item0Id"), {"invalid": 1}),
    (("players", 0, "item0Id"), [133]),
    (("players", 0, "dotaPlus"), {"level": "unknown"}),
    (("durationSeconds",), 4800.0),
])
async def test_optional_archive_corruption_cannot_break_menu(archive, mode, path, value):
    raw = synthetic_match(802)
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    archive.execute("UPDATE matches SET raw=? WHERE match_id=802", (json.dumps(raw),))
    archive.commit()
    state = board.default_state()
    state.update(mode=mode, match=802 if mode == "focus" else None, spoiler=True)

    view = await board.build_board(state)

    render.check(view.to_components(), "independent malformed archive")
    if view.st["mode"] == "list":
        opener = next(item for item in view.walk_children()
                      if getattr(item, "custom_id", None) == "mb_open")
        assert "801" in [option.value for option in opener.options]
    view.stop()


async def test_boolean_item_id_is_not_a_blink_dagger(archive):
    raw = synthetic_match(802)
    raw["players"][0]["item0Id"] = True
    archive.execute("UPDATE matches SET raw=? WHERE match_id=802", (json.dumps(raw),))
    archive.commit()
    state = board.default_state()
    state.update(mode="focus", match=802, spoiler=True)

    view = await board.build_board(state)

    assert "Blink Dagger" not in json.dumps(view.to_components())
    view.stop()


async def test_ack_latency_cannot_reorder_user_filter_choices(archive):
    """ACK requests can finish out of order even when callbacks arrive in order."""
    view = await board.build_board(board.default_state())
    older_started, release_older, newer_acknowledged = (
        asyncio.Event(), asyncio.Event(), asyncio.Event())
    rendered = []

    def interaction(*, older=False):
        itx = MagicMock()
        itx.response.is_done.return_value = False

        async def defer():
            if older:
                older_started.set()
                await release_older.wait()
            else:
                newer_acknowledged.set()

        async def edit(**kwargs):
            rendered.append(kwargs["view"].st["filters"])

        itx.response.defer = AsyncMock(side_effect=defer)
        itx.edit_original_response = AsyncMock(side_effect=edit)
        return itx

    first = asyncio.create_task(view._update(interaction(older=True), filters=["highrank"]))
    second = None
    try:
        await asyncio.wait_for(older_started.wait(), timeout=5)
        second = asyncio.create_task(view._update(interaction(), filters=["lowrank"]))
        # The newer interaction must be ACKed promptly, even if its predecessor
        # is still waiting on the ACK network request.
        await asyncio.wait_for(newer_acknowledged.wait(), timeout=5)
        await asyncio.sleep(0)
        release_older.set()
        await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
    finally:
        release_older.set()
        await asyncio.gather(first, *([second] if second else []), return_exceptions=True)

    assert rendered == [["highrank"], ["lowrank"]]
    assert view.session.state["filters"] == ["lowrank"]
    view.session.current_view.stop()


async def test_legal_length_modal_cannot_exceed_sql_expression_depth(archive):
    modal = board.AdvModal(board.default_state())
    modal.heroes._value = ",".join(["axe"] * 1000)
    assert len(modal.heroes.value) <= 4000
    itx = MagicMock()
    itx.response.is_done.return_value = False
    itx.response.defer = AsyncMock()
    itx.response.send_message = AsyncMock()
    itx.edit_original_response = AsyncMock()

    await modal.on_submit(itx)

    # Dedupe or explain a validation bound; never misreport a healthy archive
    # as unavailable because the search generated a malformed SQL expression.
    assert itx.response.send_message.await_count + itx.edit_original_response.await_count == 1


async def test_cancelled_middle_callback_does_not_let_later_update_overtake(archive):
    view = await board.build_board(board.default_state())
    release_first, first_ack, middle_ack, last_ack = [asyncio.Event() for _ in range(4)]
    rendered = []

    def interaction(event, block=False):
        itx = MagicMock()
        itx.response.is_done.return_value = False

        async def defer():
            event.set()
            if block:
                await release_first.wait()

        async def edit(**kwargs):
            rendered.append(kwargs["view"].st["sort"])

        itx.response.defer = AsyncMock(side_effect=defer)
        itx.edit_original_response = AsyncMock(side_effect=edit)
        return itx

    tasks = [asyncio.create_task(view._update(interaction(first_ack, True), sort=["kills"]))]
    try:
        await asyncio.wait_for(first_ack.wait(), timeout=5)
        tasks.append(asyncio.create_task(view._update(interaction(middle_ack), sort=["dur"])))
        await asyncio.wait_for(middle_ack.wait(), timeout=5)
        tasks[1].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[1]
        tasks.append(asyncio.create_task(view._update(interaction(last_ack), sort=["rank"])))
        await asyncio.wait_for(last_ack.wait(), timeout=5)
        await asyncio.sleep(0)
        assert rendered == []
        release_first.set()
        await asyncio.wait_for(asyncio.gather(tasks[0], tasks[2]), timeout=5)
    finally:
        release_first.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert rendered == [["kills"], ["rank"]]
    assert view.session.state["sort"] == ["rank"]
    view.session.current_view.stop()


async def test_bad_derived_item_json_cannot_break_advanced_search(archive):
    archive.execute("UPDATE match_players SET items='broken' WHERE match_id=802")
    archive.commit()
    state = board.default_state()
    state["adv"] = {"items": [("rapier", 1)]}

    total, page, _ = await board.select_page(state)

    assert total == 0 and page == []


@pytest.mark.parametrize("radiant,dire", [(None, None), (None, [29]), ([], [])])
async def test_missing_kill_evidence_is_unavailable_in_preview_and_open_option(archive, radiant, dire):
    raw = synthetic_match(802)
    raw.update(radiantKills=radiant, direKills=dire)
    archive.execute("UPDATE matches SET raw=? WHERE match_id=802", (json.dumps(raw),))
    archive.commit()
    match = (await board.hydrate([802]))[0]

    preview = render.menu_match_preview(match)
    view = await board.build_board(board.default_state())
    opener = next(item for item in view.walk_children()
                  if getattr(item, "custom_id", None) == "mb_open")
    option = next(option for option in opener.options if option.value == "802")

    assert "unavailable" in preview.splitlines()[0].lower()
    assert "unavailable" in option.label.lower()
    assert f"{sum(radiant or []) + sum(dire or [])} kills" not in preview
    view.stop()


async def test_unknown_player_team_is_not_invented_as_dire(archive):
    raw = synthetic_match(802)
    raw["players"][0]["isRadiant"] = None
    archive.execute("UPDATE matches SET raw=? WHERE match_id=802", (json.dumps(raw),))
    archive.commit()

    hydrated = await board.hydrate([802, 801])
    state = board.default_state()
    state.update(mode="focus", match=802)
    view = await board.build_board(state)

    assert [match["id"] for match in hydrated] == [801]
    assert view.st["mode"] == "list"
    text = json.dumps(view.to_components())
    assert "unreadable" in text or "incomplete archive data" in text
    view.stop()


@pytest.mark.parametrize("unknown_winner", [0, 1])
async def test_numeric_winner_is_not_treated_as_literal_boolean(archive, unknown_winner):
    raw = synthetic_match(802)
    raw["didRadiantWin"] = unknown_winner
    archive.execute("UPDATE matches SET raw=? WHERE match_id=802", (json.dumps(raw),))
    archive.commit()
    state = board.default_state()
    state.update(mode="focus", match=802)

    view = await board.build_board(state)

    text = json.dumps(view.to_components())
    assert "Radiant win" not in text and "Dire win" not in text
    assert "winner unavailable" in text
    view.stop()


async def test_long_inventory_keeps_distinct_item_and_skill_receipts_before_duplicates(archive):
    """Pixel-review regression: optional overflow must not eat the skill heading."""
    raw = synthetic_match(802)
    longest = sorted(render._item_by_id, key=lambda item: len(render.item_name(item)), reverse=True)[:6]
    for player in raw["players"]:
        player.update({f"item{slot}Id": item for slot, item in enumerate(longest)})
    item_name = render.item_name(longest[0])
    item_notes = [{"hero_id": 1, "score": 9,
                   "items": [[item_name, 28, 9], [render.item_name(longest[1]), 36, 8]]}] * 20
    skill_notes = [{"hero_id": 1, "score": 9, "picks": [["Distinct skill evidence", 7, 9]]}]
    archive.execute("UPDATE matches SET raw=?, weirdness=9, weird_notes=?,"
                    " skill_weirdness=9, skill_notes=? WHERE match_id=802",
                    (json.dumps(raw), json.dumps(item_notes), json.dumps(skill_notes)))
    archive.commit()
    state = board.default_state()
    state.update(mode="focus", match=802, spoiler=True)

    view = await board.build_board(state)

    displays = [item.content for item in view.walk_children()
                if isinstance(item, board.discord.ui.TextDisplay)]
    item_block = next(text for text in displays if "**Item build receipts**" in text)
    skill_block = next(text for text in displays if "**Skill-order receipts**" in text)
    assert "corpus-relative" in item_block and "corpus-relative" in skill_block
    assert item_block.count(item_name + " @28m") == 1
    assert "Distinct skill evidence @pick 7" in skill_block
    core = "\n".join(text for text in displays
                     if text.startswith("**Radiant**") or text.startswith("**Dire**"))
    assert all(render.hero_name(player["heroId"]) in core for player in raw["players"])
    assert all(core.count(render.item_name(item)) == 10 for item in longest)
    render.check(view.to_components(), "long focus evidence priorities")
    view.stop()
