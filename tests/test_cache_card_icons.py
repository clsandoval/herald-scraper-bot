"""Offline regressions for selected official-artwork maintenance."""

from io import BytesIO
from types import SimpleNamespace

from PIL import Image, PngImagePlugin
import pytest

from herald import render, report_signals
from scripts import cache_card_icons


@pytest.mark.parametrize("ability_id", [1229, 5102, 5103, 5105])
def test_sources_include_sand_king_catalog_spells(ability_id):
    name = report_signals._ABILITY_NAMES[str(ability_id)]
    assert name.startswith("sandking_")
    assert cache_card_icons.sources()[f"ability_{ability_id}"] == (
        f"{render.CDN}/apps/dota2/images/dota_react/abilities/{name}.png")


def test_sources_include_inventory_recipe_artwork():
    assert render.item_key(228) == "recipe_octarine_core"
    assert cache_card_icons.sources()["item_228"] == (
        f"{render.CDN}/apps/dota2/images/dota_react/items/recipe.png")


def test_ability_prefix_alias_does_not_admit_unknown_or_talent_keys(monkeypatch):
    monkeypatch.setattr(report_signals, "_ABILITY_NAMES", {
        "1": "sandking_burrowstrike", "2": "not_a_hero_spell",
        "3": "special_bonus_unique_sand_king", "4": "sandkingish_fake",
    })
    urls = cache_card_icons.sources()
    assert "ability_1" in urls
    assert all(f"ability_{identifier}" not in urls for identifier in (2, 3, 4))


def png_bytes(size=(88, 64), metadata_bytes=0):
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    if metadata_bytes:
        metadata.add_itxt("Synthetic metadata", "x" * metadata_bytes)
    Image.new("RGB", size, "blue").save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def stub_download(monkeypatch, tmp_path, data, *, returncode=0):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=returncode, stdout=data)

    monkeypatch.setattr(cache_card_icons, "ROOT", tmp_path)
    monkeypatch.setattr(cache_card_icons.subprocess, "run", run)
    return calls


def test_fetch_accepts_bounded_official_style_metadata_and_strips_it(monkeypatch, tmp_path):
    data = png_bytes(metadata_bytes=2_010_000)
    assert 2_000_000 < len(data) < cache_card_icons.MAX_DOWNLOAD_BYTES
    calls = stub_download(monkeypatch, tmp_path, data)
    url = cache_card_icons.sources()["item_1097"]

    assert cache_card_icons.fetch("item_1097", url) == ("item_1097", url, True)

    path = tmp_path / "item_1097.png"
    assert path.stat().st_size < 10_000
    with Image.open(path) as cached:
        assert cached.size == (88, 64)
        cached.verify()
    command = calls[0]
    assert command[command.index("--max-filesize") + 1] == str(cache_card_icons.MAX_DOWNLOAD_BYTES)
    assert "--location" not in command


@pytest.mark.parametrize("data,returncode", [
    (b"x" * (cache_card_icons.MAX_DOWNLOAD_BYTES + 1), 0),
    (b"not an image", 0),
    (png_bytes(size=(2049, 1)), 0),
    (png_bytes(), 22),
])
def test_fetch_rejects_oversized_invalid_and_failed_responses(monkeypatch, tmp_path, data, returncode):
    stub_download(monkeypatch, tmp_path, data, returncode=returncode)
    url = cache_card_icons.sources()["item_1097"]
    assert cache_card_icons.fetch("item_1097", url) == ("item_1097", url, False)
    assert not (tmp_path / "item_1097.png").exists()


def test_valid_cached_asset_does_not_download(monkeypatch, tmp_path):
    calls = stub_download(monkeypatch, tmp_path, b"must not download")
    (tmp_path / "item_180.png").write_bytes(png_bytes())
    url = cache_card_icons.sources()["item_180"]
    assert cache_card_icons.fetch("item_180", url) == ("item_180", url, True)
    assert calls == []
