"""Production card behavior without Discord sends, credentials, or a live DB."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from herald import charts, ingest, render, scheduled


def report_gallery(message):
    container = next(node for node in message["components"] if node["type"] == 17)
    return next(node for node in container["components"] if node["type"] == 12)


def rich_match():
    candidate = {"match_id": 999001, "duration": 5100, "avg_rank_tier": 12,
                 "start_time": 1790000000}
    players = []
    for index in range(10):
        players.append({
            "heroId": index + 1, "isRadiant": index < 5,
            "kills": 7, "deaths": 12, "assists": 15,
            "steamAccount": {"seasonRank": 12},
            **{f"item{i}Id": value for i, value in enumerate([116, 65, 133, 108, 112, 1])},
            "abilities": [{"abilityId": value, "isTalent": False, "time": i * 80}
                          for i, value in enumerate([5003, 5004, 5003, 5004, 5003, 5006, 5003, 5004])],
            "stats": {"itemPurchases": [{"itemId": 116, "time": 2000}],
                      "itemUsed": [{"itemId": 116, "count": 0}],
                      "actionsPerMinute": [100, 150]},
        })
    raw = {"id": candidate["match_id"], "durationSeconds": candidate["duration"],
           "startDateTime": candidate["start_time"], "didRadiantWin": True,
           "radiantKills": [40], "direKills": [32], "radiantNetworthLeads": [0, 1000, -9000, 4000],
           "players": players}
    od = {"duration": 5100, "radiant_score": 40, "dire_score": 32,
          "radiant_win": True, "radiant_gold_adv": [0, -9000, 4000],
          "players": [{"leaver_status": 0} for _ in range(10)]}
    return candidate, raw, od


def test_scheduled_cards_surface_items_skills_and_micro_receipts():
    spec = scheduled.payload(*rich_match(), {"h_antimage": "123", "i_black_king_bar": "456"})
    for message in [spec["parent"], *spec["teams"]]:
        assert 0 <= scheduled.check_message(message) <= 6000
        assert message["allowed_mentions"] == {"parse": []}
    assert "components" not in spec["parent"] and not spec["parent"].get("flags")
    first = spec["cards"]["radiant"]["players"][0]
    assert first["hero_id"] == 1 and first["hero_name"] == "Anti-Mage"
    assert first["items"] == [116, 65, 133, 108, 112, 1]
    assert first["skills"] == [5003, 5004, 5003, 5004, 5003, 5006, 5003, 5004]
    assert first["notes"] == ["BKB purchased; 0 recorded uses"]
    assert first["kda"] == "7/12/15"
    for stage, message in zip(("radiant", "dire"), spec["teams"]):
        assert message["flags"] == 1 << 15
        assert "embeds" not in message and "content" not in message
        manifest = message["_files"][0]
        gallery = report_gallery(message)
        assert gallery["type"] == 12
        assert gallery["items"][0]["media"]["url"] == "attachment://" + manifest["filename"]
        assert spec.uploads[stage][manifest["filename"]].startswith(b"\x89PNG")
    assert "review-quality score" not in json.dumps(spec)  # no inferred numerical ranking
    parent = json.dumps(spec["parent"])
    assert "Review cues" not in parent and "Build preview" not in parent and "Skill preview" not in parent
    assert spec["parent"]["embeds"][0]["title"] == "Radiant won after trailing by 9,000 gold"
    assert spec["parent"]["embeds"][0]["description"] == "85m · 72 kills"
    assert render.check_embeds(spec["parent"]) <= 900


def test_missing_build_logs_are_not_reported_as_zero():
    candidate, raw, od = rich_match()
    for p in raw["players"]:
        for field in ["abilities", "stats", *(f"item{i}Id" for i in range(6))]:
            p.pop(field, None)
    spec = scheduled.payload(candidate, raw, od, {})
    first = spec["cards"]["radiant"]["players"][0]
    assert first["items"] == [None] * 6
    assert first["skills"] is None
    assert first["notes"] == []


def test_recorded_empty_inventory_and_skills_are_distinct_from_missing():
    candidate, raw, od = rich_match()
    for p in raw["players"]:
        p.update({f"item{i}Id": 0 for i in range(6)})
        p["abilities"] = []
    spec = scheduled.payload(candidate, raw, od, {})
    first = spec["cards"]["radiant"]["players"][0]
    assert first["items"] == [0] * 6
    assert first["skills"] == []


def test_missing_score_and_nullable_apm_remain_unavailable():
    candidate, raw, od = rich_match()
    od.pop("radiant_score")
    raw["players"][0]["stats"]["actionsPerMinute"] = [None, float("nan"), -1]
    spec = scheduled.payload(candidate, raw, od, {})
    parent = spec["parent"]["embeds"][0]
    assert "fields" not in parent and parent["description"] == "85m"
    assert "kills" not in json.dumps(parent)
    assert spec["cards"]["radiant"]["kills"] is None
    assert "APM" not in json.dumps(spec["cards"])  # Secondary statistics no longer crowd the icons.


def test_longest_real_inventory_names_and_skills_fit_without_cutting_items(monkeypatch):
    candidate, raw, od = rich_match()
    longest = sorted(render._item_by_id, key=lambda i: len(render.item_name(i)), reverse=True)[:6]
    for p in raw["players"]:
        p.update({f"item{i}Id": item for i, item in enumerate(longest)})
    spec = scheduled.payload(candidate, raw, od, {})
    for message in spec["teams"]:
        assert scheduled.check_message(message) <= 4000
        assert "embeds" not in message
        assert len(message["attachments"][0]["description"]) <= 1024
    for card in spec["cards"].values():
        for player in card["players"]:
            assert player["items"] == longest  # Icons retain all slots regardless of label length.
            assert len(player["skills"]) == 8


def test_preview_has_build_evidence_and_no_per_hero_kda_wall(monkeypatch):
    monkeypatch.setattr(render, "_emoji", {})
    _, raw, _ = rich_match()
    m = ingest.match_view(raw)
    m["_raw"] = raw
    preview = render.menu_match_preview(m, n=1, rank_label="Herald 2 · ")
    assert len(preview) <= 640
    assert "Items ·" in preview and "Skills ·" in preview and "Review ·" in preview
    assert "7/12/15" not in preview
    assert "Radiant win" not in preview


def test_preview_tolerates_missing_or_malformed_optional_notes(monkeypatch):
    monkeypatch.setattr(render, "_emoji", {})
    _, raw, _ = rich_match()
    m = ingest.match_view(raw)
    m.update(_item_notes="{broken", _skill_notes={"unexpected": "shape"}, _skill_weirdness=9)
    text = render.menu_match_preview(m)
    assert "Items ·" in text and len(text) <= 640
    assert "Skills ·" not in text
    for p in m["players"]:
        p["items"] = []
    assert "detail unavailable" in render.menu_match_preview(m)


def test_malformed_archive_receipt_entries_do_not_crash_or_fabricate():
    _, raw, _ = rich_match()
    m = ingest.match_view(raw)
    m.update(_item_notes=[{"score": "oops", "items": [1]},
                          {"score": 9, "items": [None, "not an item", {}, ["name", None]]}],
             _skill_notes=[{"picks": [1, {}, "invalid", ["skill", float("nan")]]}],
             _skill_weirdness=9)
    text = render.menu_match_preview(m) + "\n".join(render.menu_focus_receipts(m))
    assert "not an item" not in text and "invalid" not in text
    assert "@pick" not in text and "Item build receipts" not in text


def test_nullable_kda_renders_unknown_without_inventing_zero(monkeypatch):
    monkeypatch.setattr(render, "_emoji", {})
    text = render.player_line({"hero_id": 1, "k": None, "d": 0, "items": None})
    assert " ?/ 0/ ?" in text
    candidate, raw, od = rich_match()
    raw["players"][0].pop("kills")
    raw["players"][0]["assists"] = None
    player = scheduled.payload(candidate, raw, od, {})["cards"]["radiant"]["players"][0]
    assert player["kda"] == "?/12/?"


def test_invalid_optional_inventory_ids_and_badges_are_display_safe():
    _, raw, _ = rich_match()
    raw["players"][0]["item0Id"] = {"bad": 1}
    raw["players"][0]["dotaPlus"] = {"level": "unknown"}
    m = ingest.match_view(raw)
    m["_raw"] = raw
    assert "Unknown item" in render.menu_player_line(m["players"][0], raw["players"][0])
    assert render.item_img({"bad": 1}) is None
    assert "unknown" not in "\n".join(render.menu_focus_receipts(m))
    assert len(render.menu_match_preview(m)) <= 640


def test_focus_tabs_preserve_inventory_and_numbered_skill_paths(monkeypatch):
    monkeypatch.setattr(render, "_emoji", {})
    _, raw, _ = rich_match()
    m = ingest.match_view(raw)
    p = m["players"][0]
    items = render.menu_player_line(p, raw["players"][0])
    skills = render.menu_player_line(p, raw["players"][0], "skills")
    assert "Black King Bar" in items and "Divine Rapier" in items
    assert "1. Mana Break" in skills and "6. Mana Void" in skills
    assert "level 6" not in skills
    assert len(skills) <= 300


def test_skill_path_overflow_keeps_whole_pick_tokens():
    skills = ["A very long ability name with five words"] * 8
    text = render.skill_path(skills, 200)
    assert len(text) <= 200 and "(+" in text
    assert text.count("→") + 1 < 8
    assert text.endswith("picks)")


def test_optional_receipts_are_winner_neutral_and_do_not_infer_item_uses():
    _, raw, _ = rich_match()
    for p in raw["players"]:
        p["stats"].pop("itemUsed")
    raw["barracksStatusRadiant"] = 0
    m = ingest.match_view(raw)
    m["_raw"] = raw
    text = "\n".join(render.menu_focus_receipts(m))
    assert "BKB" not in text
    assert "won" not in text.lower() and "megas" not in text.lower()


def test_focus_receipts_deduplicate_before_caps_and_prioritize_items_and_skills():
    _, raw, _ = rich_match()
    m = ingest.match_view(raw)
    m["players"][0]["dplus"] = 30
    item_note = {"hero_id": 1, "score": 9,
                 "items": [["Battle Fury", 34, 9]] * 4 + [["Divine Rapier", 61, 8]]}
    skill_note = {"hero_id": 1,
                  "picks": [["Mana Break", 9, 9]] * 4 + [["Mana Void", 11, 8]]}
    m.update(_raw=raw, _weirdness=9, _skill_weirdness=9,
             _item_notes=[item_note] * 20, _skill_notes=[skill_note] * 20)

    blocks = render.menu_focus_receipts(m)

    assert "Item build receipts" in blocks[0]
    assert "Skill-order receipts" in blocks[1]
    assert "Review moments" in blocks[2]
    assert "Dota Plus mastery" in blocks[3]
    assert blocks[0].count("Battle Fury @34m") == 1
    assert blocks[0].count("Divine Rapier @61m") == 1
    assert blocks[1].count("Mana Break @pick 9") == 1
    assert blocks[1].count("Mana Void @pick 11") == 1
    assert len(blocks[0].splitlines()) == len(blocks[1].splitlines()) == 2
    assert all(block.splitlines()[0].count("**") == 2 for block in blocks)


def test_focus_receipts_deduplicate_micro_receipts_and_complete_lines(monkeypatch):
    _, raw, _ = rich_match()
    m = ingest.match_view(raw)
    # Duplicate rows must not consume the entire optional text budget.
    m["players"] = [dict(m["players"][0], dplus=30)] * 2
    monkeypatch.setattr(render, "_review_signals", lambda *_: {
        "players": {0: ["Recorded fact A"] * 3 + ["Recorded fact B"],
                    1: ["Recorded fact A", "Recorded fact B"]}})

    blocks = render.menu_focus_receipts(m)

    assert len(blocks) == 2
    assert blocks[0].splitlines() == ["🔎 **Review moments**",
                                    "Anti-Mage: Recorded fact A; Recorded fact B"]
    assert len(blocks[1].splitlines()) == 2


def test_classic_embed_guard_rejects_oversize_and_mixed_v2():
    embed = {"embeds": [{"title": "x", "fields": [{"name": "x", "value": "x" * 1025}]}]}
    with pytest.raises(ValueError, match="1024"):
        render.check_embeds(embed)
    with pytest.raises(ValueError, match="cannot contain"):
        render.check_embeds({"flags": 1 << 15, "embeds": [{"title": "x"}]})
    with pytest.raises(ValueError, match="6000"):
        render.check_embeds({"embeds": [{"description": "x" * 3500}] * 2})


def test_chart_renderers_are_safe_for_concurrent_empty_and_normal_calls():
    calls = [(charts.networth_lead_png, [0, 1000, -2000]),
             (charts.thumb_spark_png, [0, -1500, 3500]),
             (charts.sparkline_png, []), (charts.networth_lead_png, [])] * 2
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda args: args[0](args[1]), calls))
    assert all(result.startswith(b"\x89PNG\r\n\x1a\n") for result in results)
    assert not charts.plt.get_fignums()


def test_chart_render_failure_does_not_leak_figures(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic render failure")
    monkeypatch.setattr(charts.matplotlib.figure.Figure, "savefig", fail)
    with pytest.raises(RuntimeError, match="Synthetic"):
        charts.networth_lead_png([0, 1000, -1000])
    assert not charts.plt.get_fignums()
