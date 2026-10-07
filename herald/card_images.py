"""Offline, icon-first scheduled-report cards.

Only pinned Valve artwork is rendered. The serializable model preserves exact
inventory slots and original non-talent pick positions; unknown data never turns
into an empty slot. No Discord, network, database, or clock access occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import textwrap
import importlib.util

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import render, report_signals, reporter_novelty

ASSET_DIR = Path(__file__).parent / "assets" / "card_icons"
VERSION = "icon-team-v1"
WIDTH = 1000
ROW_HEIGHT = 184
BG = "#10151d"
PANEL = "#19222e"
TEXT = "#e8eef5"
MUTED = "#97a5b7"
GOLD = "#efba63"


@dataclass(frozen=True)
class RenderedCard:
    png_bytes: bytes
    filename: str
    description: str


def _entry(evidence, kind, index):
    entries = evidence.get(kind, {})
    return entries.get(index, entries.get(str(index), {}))


def _number(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _short(text, limit=94):
    return render.clip(str(text), limit)


def build_team_card(candidate, raw, opendota, *, radiant, evidence=None, synthetic=False):
    """Create an immutable-ready, JSON-serializable presentation model.

    Full evidence remains in the delivery spec. Cards show at most two factual
    observations per hero, with no scoring or reference metadata on the image.
    """
    if type(radiant) is not bool:
        raise ValueError("radiant must be a boolean")
    proof = evidence or reporter_novelty.unavailable(raw)
    signals = report_signals.summarize(raw, opendota, candidate.get("duration", 0))
    # Select the strongest supported player for each cue. Positive scores alone
    # are not called anomalous, off-meta, or bad.
    best = {}
    for kind in ("items", "skills"):
        scored = [(float(_entry(proof, kind, i).get("score") or 0), i)
                  for i, _ in enumerate(raw.get("players", []))
                  if _entry(proof, kind, i).get("status") == "scored"
                  and _entry(proof, kind, i).get("receipts")]
        best[kind] = max(scored, default=(0, None), key=lambda x: (x[0], -x[1]))[1]
    players = []
    for index, p in enumerate(raw.get("players", [])):
        if p.get("isRadiant") is not radiant:
            continue
        hero = p.get("heroId")
        hero = hero if type(hero) is int and hero > 0 else None
        slots = []
        for slot in range(6):
            key = f"item{slot}Id"
            value = p.get(key)
            if key in p and (value is None or type(value) is int and value == 0):
                slots.append(0)
            else:
                slots.append(value if type(value) is int and value > 0 else None)
        skills = report_signals._skill_ids(p)
        skills = skills[:12] if skills is not None else None
        notes, item_marks, skill_marks = [], [], []
        observations = signals["players"].get(index, [])
        if observations:
            notes.append(_short(observations[0]))
        for kind in ("items", "skills"):
            entry = _entry(proof, kind, index)
            if best[kind] != index or not entry.get("receipts"):
                continue
            receipt = entry["receipts"][0]
            if kind == "items":
                item = receipt["item_id"]
                item_marks.append(item)
                note = f"{render.item_name(item)} @{receipt['minute']}m"
            else:
                pick = receipt["pick"]
                # Original observed pick is used verbatim. Never compress gaps.
                skill_marks.append(pick)
                note = f"Pick {pick}: {report_signals.ability_name(receipt['ability_id'], hero)}"
            # The text budget must not hide the selected item or skill tile.
            # An event plus an item note can consume both lines for one hero.
            if len(notes) < 2:
                notes.append(_short(note))
        states = {kind: _entry(proof, kind, index).get("status", "unscored")
                  for kind in ("items", "skills")}
        players.append({"hero_id": hero, "hero_name": render.hero_name(hero) if hero is not None else "Unknown hero",
                        "items": slots, "skills": skills,
                        "kda": "/".join(str(p[k]) if _number(p.get(k)) else "?"
                                         for k in ("kills", "deaths", "assists")),
                        "notes": notes, "item_marks": item_marks, "skill_marks": skill_marks,
                        "evidence_status": states})
    if len(players) != 5:
        raise ValueError("Each card requires exactly five team players")
    ref = proof.get("reference", {})
    synthetic = bool(synthetic or ref.get("synthetic"))
    score = opendota.get("radiant_score" if radiant else "dire_score")
    return {"version": VERSION, "match_id": candidate.get("match_id"),
            "team": "radiant" if radiant else "dire", "duration": candidate.get("duration", 0),
            "kills": score if _number(score) else None, "synthetic": synthetic,
            "reference": {"matches": ref.get("matches", 0), "patch": ref.get("patch"),
                          "population": ref.get("population", reporter_novelty.POPULATION)},
            "players": players}


def asset_path(kind, identifier):
    if kind not in {"hero", "item", "ability"} or type(identifier) is not int or identifier <= 0:
        return None
    path = ASSET_DIR / f"{kind}_{identifier}.png"
    return path if path.is_file() else None


@lru_cache(maxsize=1024)
def _asset(kind, identifier):
    path = asset_path(kind, identifier)
    if path is None:
        return None
    try:
        with Image.open(path) as im:
            if im.width > 2048 or im.height > 2048:
                return None
            return im.convert("RGB")
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=20)
def _font(size, bold=False):
    # Matplotlib is an existing declared dependency, so its bundled font gives
    # identical metrics on desktop, CI and the production Linux container.
    suffix = "-Bold" if bold else ""
    return ImageFont.truetype(str(Path(importlib.util.find_spec("matplotlib").origin).parent /
                                 "mpl-data" / "fonts" / "ttf" / f"DejaVuSans{suffix}.ttf"), size)


def _text(draw, xy, text, size=20, color=TEXT, bold=False):
    draw.text(xy, str(text), font=_font(size, bold), fill=color)


def _icon(canvas, draw, kind, identifier, box, *, highlight=False):
    x, y, w, h = box
    artwork = _asset(kind, identifier) if type(identifier) is int else None
    draw.rounded_rectangle((x-2, y-2, x+w+1, y+h+1), radius=4,
                           fill=GOLD if highlight else "#344152")
    if artwork is not None:
        canvas.paste(ImageOps.fit(artwork, (w, h), method=Image.Resampling.LANCZOS), (x, y))
        return
    draw.rectangle((x, y, x+w-1, y+h-1), fill="#111923")
    if identifier == 0:
        label = "–"
    elif identifier is None:
        label = "?"
    else:
        label = str(identifier)
    size = 18 if len(label) <= 4 else 14
    while size > 10 and draw.textlength(label, font=_font(size)) > w - 8:
        size -= 1
    if draw.textlength(label, font=_font(size)) > w - 8:
        # Keep a readable placeholder inside its tile. The complete identifier
        # stays unchanged in the saved model even when its label needs elision.
        while label and draw.textlength(label + "…", font=_font(size)) > w - 8:
            label = label[:-1]
        label += "…"
    bounds = draw.textbbox((0, 0), label, font=_font(size))
    tw = bounds[2]-bounds[0]
    _text(draw, (x+(w-tw)//2, y+(h-size)//2-2), label, size, MUTED)


def _display_notes(player):
    """Read old saved annotations without changing their model or frozen bytes."""
    return [re.split(r"\s+·\s+(?:PMI|surprisal)\b", note, maxsplit=1,
                     flags=re.IGNORECASE)[0] for note in player["notes"][:2]]


def card_description(card):
    """Concise attachment alt text; detailed evidence remains in the saved spec."""
    lines = [f"{'Example. ' if card['synthetic'] else ''}{card['team'].title()} team. "
             "Each row: hero portrait, six final item slots, twelve numbered non-talent picks."]
    for p in card["players"]:
        items = ", ".join(render.item_name(i) if i else "empty" if i == 0 else "unknown"
                          for i in p["items"])
        lines.append(f"{p['hero_name']} {p['kda']}: {items}. " + "; ".join(_display_notes(p)))
    return _short("\n".join(lines), 1024)


def render_team_card(card):
    """Render an existing model deterministically, with no I/O except local assets."""
    if card.get("version") != VERSION or len(card.get("players", [])) != 5:
        raise ValueError("Unsupported icon card model")
    height = 152 + ROW_HEIGHT * 5 + 84
    canvas = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(canvas)
    color = "#6bdd99" if card["team"] == "radiant" else "#ee8084"
    draw.rectangle((0, 0, WIDTH, 7), fill=color)
    _text(draw, (28, 23), card["team"].upper(), 36, color, True)
    badge = "Example" if card["synthetic"] else f"MATCH {card['match_id']}"
    bounds = draw.textbbox((0, 0), badge, font=_font(18, True))
    _text(draw, (WIDTH-28-(bounds[2]-bounds[0]), 37), badge, 18, MUTED, True)
    _text(draw, (29, 73), f"{render.dur(card['duration'])}   ·   " +
          (f"{card['kills']} team kills" if card['kills'] is not None else "Kills unavailable"), 22)
    _text(draw, (218, 117), "ITEMS  /  FIRST 12 SKILL PICKS", 16, MUTED, True)
    for index, player in enumerate(card["players"]):
        top = 152 + index * ROW_HEIGHT
        draw.rounded_rectangle((18, top, WIDTH-18, top+ROW_HEIGHT-10), radius=10, fill=PANEL)
        _icon(canvas, draw, "hero", player["hero_id"], (32, top+14, 156, 88))
        _text(draw, (32, top+110), player["hero_name"], 17, TEXT, True)
        _text(draw, (32, top+137), player["kda"], 18, MUTED)
        for slot, item in enumerate(player["items"]):
            _icon(canvas, draw, "item", item, (218+slot*83, top+12, 74, 54),
                  highlight=item in player["item_marks"])
        skills = player["skills"]
        for pick in range(12):
            ability = skills[pick] if skills is not None and pick < len(skills) else None
            # A short supplied sequence has no recorded pick after its end, which
            # is visually distinct from an unavailable entire ability log.
            if skills is not None and pick >= len(skills):
                ability = 0
            x = 218+pick*61
            _icon(canvas, draw, "ability", ability, (x, top+80, 52, 52),
                  highlight=pick+1 in player["skill_marks"])
            _text(draw, (x+19 if pick < 9 else x+15, top+134), pick+1, 13, MUTED)
        notes = _display_notes(player)
        positions = list(range(len(notes)))
        build_note = bool(notes and (notes[0].startswith("Pick ") or " @" in notes[0]))
        if notes and not build_note and (len(notes[0]) > 58 or len(notes) > 1):
            # Long events need the full-width line; item/skill facts can use
            # the small inventory-side space without moving any icon tiles.
            positions = [1, 0][:len(notes)]
        for line, note in zip(positions, notes):
            if line == 0:
                words = note.split(" · ")
                if len(words) == 1:
                    words = textwrap.wrap(note, width=29, break_long_words=False)
                    for line_index, part in enumerate(words[:2]):
                        _text(draw, (736, top+37+19*line_index), part, 14, GOLD)
                else:
                    _text(draw, (736, top+37), _short(words[0], 28), 14, GOLD)
                    _text(draw, (736, top+56), _short(" · ".join(words[1:]), 30), 12, MUTED)
            else:
                size = 14
                while size > 11 and draw.textlength(note, font=_font(size)) > 732:
                    size -= 1
                _text(draw, (218, top+154), note, size, GOLD)
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=False)
    data = out.getvalue()
    filename = f"herald-{card['match_id']}-{card['team']}-{sha256(data).hexdigest()[:12]}.png"
    return RenderedCard(data, filename, card_description(card))
