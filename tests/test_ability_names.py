"""Offline canonical labels change presentation only, never picks or evidence."""
import copy
import importlib
import json
from pathlib import Path
import socket

import pytest

from herald import ability_names, report_signals, reporter_novelty, scheduled


@pytest.mark.parametrize("ability_id,hero_id,label", [
    (5003, 1, "Mana Break"),
    (5044, 26, "Earth Spike"),
    (5045, 26, "Hex"),
    (5059, 11, "Shadowraze"),
    (5060, 11, "Shadowraze"),
    (5061, 11, "Shadowraze"),
    (5086, 42, "Wraithfire Blast"),
    (5110, 22, "Arc Lightning"),
])
def test_verified_labels_replace_internal_name_prettification(ability_id, hero_id, label):
    assert report_signals.ability_name(ability_id, hero_id) == label
    # Canonical ability labels do not depend on the hero lookup being available.
    assert report_signals.ability_name(ability_id, 999999) == label


def test_missing_labels_keep_existing_known_and_unknown_fallbacks():
    assert ability_names.localized_name(None) is None
    assert ability_names.localized_name("new_hero_unverified_ability") is None
    # A removed internal key has no current verified dname; do not guess its successor.
    assert ability_names.localized_name("antimage_spell_shield") is None
    assert report_signals.ability_name(5005, 1) == "Spell Shield"
    assert report_signals.ability_name(5005, 999999) == "Antimage Spell Shield"
    assert report_signals.ability_name(987654321, 26) == "Ability 987654321"


def test_bundled_labels_record_source_version_and_cover_only_verified_literal_names():
    assets = Path(ability_names.__file__).parent / "assets"
    data = json.loads((assets / "ability_names.json").read_text(encoding="utf-8"))
    source = data["source"]
    assert source["project"] == "OpenDota dotaconstants"
    assert source["locale"] == "en"
    assert source["version"] == "10.8.0"
    assert source["commit"] == "bf193a550f778dec35debf4d71d05a86bebcc418"
    assert source["git_blob_sha"] == "d2f0fe8bae8b941b508f72ebb4ab2cdf1381b7ac"
    assert source["url"].endswith(source["commit"] + "/" + source["path"])
    assert "The OpenDota Project" in (assets / "ability_names.LICENSE").read_text()
    ids = json.loads((assets / "ability_ids.json").read_text())
    assert set(data["names"]) <= set(ids.values())
    assert len(data["names"]) == 1055
    assert all(not key.startswith("special_bonus_") for key in data["names"])
    assert all(isinstance(name, str) and name.strip() and "{" not in name
               for name in data["names"].values())


def test_import_and_lookup_need_no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("ability label lookup must stay offline")

    monkeypatch.setattr(socket, "socket", forbidden)
    importlib.reload(ability_names)
    assert ability_names.localized_name("lion_voodoo") == "Hex"


def test_identical_shadowraze_labels_preserve_ids_repeats_and_unknown_pick_positions():
    ids = [5059, 987654321, 5060, 5061, 5059]
    player = {"heroId": 11, "abilities": [
        {"abilityId": value, "isTalent": False, "time": index * 60}
        for index, value in enumerate(ids)
    ]}
    original = copy.deepcopy(player)
    assert report_signals._skill_ids(player) == ids
    assert scheduled.skill_path(player) == (
        "1. Shadowraze → 2. Ability 987654321 → 3. Shadowraze → 4. Shadowraze → 5. Shadowraze"
    )
    assert player == original


def test_novelty_receipt_uses_labels_without_renumbering_or_mutating_evidence():
    evidence = {"skills": {0: {
        "status": "scored", "score": 3.5, "support": {"hero_mode_builds": 40},
        "receipts": [
            {"ability_id": 5045, "pick": 8, "score": 2.0},
            {"ability_id": 987654321, "pick": 11, "score": 1.5},
        ],
    }}}
    original = copy.deepcopy(evidence)
    text = reporter_novelty.evidence_text(evidence, "skills", 0, 26)
    assert "pick 8 Hex (2.0)" in text
    assert "pick 11 Ability 987654321 (1.5)" in text
    assert evidence == original
