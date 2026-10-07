"""Shared hero/item lookups and presentation helpers for both product modes.

Menu receipts and fixture adapters also serve the fenced presentation prototypes.
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CDN = "https://cdn.cloudflare.steamstatic.com"

MAX_COMPONENTS = 40
MAX_CHARS = 3600  # guard below Discord's 4000 total-text pool

BKB_ID = 116
MIDAS_ID = 65

_heroes = json.load(open(f"{HERE}/assets/heroes.json"))
_items = json.load(open(f"{HERE}/assets/items.json"))
_item_by_id = {v["id"]: {"key": k, **v} for k, v in _items.items() if v.get("id")}
try:
    _emoji = json.load(open(f"{HERE}/assets/emoji_map.json"))
except FileNotFoundError:
    _emoji = {}


# ---------- names / images / emojis ----------

def hero(hid):
    return _heroes.get(str(hid))


def hero_name(hid):
    h = hero(hid)
    return h["localized_name"] if h else f"Hero {hid}"


def hero_short(hid):
    h = hero(hid)
    return h["name"].removeprefix("npc_dota_hero_") if h else str(hid)


def hero_img(hid):
    return f"{CDN}/apps/dota2/images/dota_react/heroes/{hero_short(hid)}.png"


def hero_icon(hid):
    return f"{CDN}/apps/dota2/images/dota_react/heroes/icons/{hero_short(hid)}.png"


def item_name(iid):
    if not isinstance(iid, int) or isinstance(iid, bool) or iid <= 0:
        return "Unknown item"
    it = _item_by_id.get(iid)
    return (it.get("dname") or it["key"]) if it else f"Item {iid}"


def item_key(iid):
    if not isinstance(iid, int) or isinstance(iid, bool) or iid <= 0:
        return None
    it = _item_by_id.get(iid)
    return it["key"] if it else None


def item_img(iid):
    if not isinstance(iid, int) or isinstance(iid, bool) or iid <= 0:
        return None
    it = _item_by_id.get(iid)
    if not it or not it.get("img"):
        return None
    return CDN + it["img"].split("?")[0]


def hero_emoji(hid):
    """<:h_axe:123> or '' when not seeded."""
    e = _emoji.get(f"h_{hero_short(hid)}"[:32])
    return f"<:{e['name']}:{e['id']}>" if e else ""


def item_emoji(iid):
    k = item_key(iid)
    e = _emoji.get(f"i_{k}"[:32]) if k else None
    return f"<:{e['name']}:{e['id']}>" if e else ""


def dur(s):
    if (not isinstance(s, (int, float)) or isinstance(s, bool)
            or not math.isfinite(s) or s < 0):
        return "?:??"
    seconds = int(s)
    return f"{seconds // 60}:{seconds % 60:02d}"


# ---------- processed match view ----------

def load_matches():
    """Historical fixture loader; live transformations belong to ingest."""
    from .ingest import match_view
    with open(f"{HERE}/fixtures/herald_matches.json") as source:
        raw = json.load(source)
    return sorted((match_view(m) for m in raw["matches"]), key=lambda m: m["id"], reverse=True)


def item_icons(p, n=6):
    """Inline items; use readable names when application emojis are missing."""
    inventory = p.get("items") or []
    if not isinstance(inventory, (list, tuple)):
        return "items unavailable"
    items = [item_emoji(i) or item_name(i) for i in inventory[:n]]
    # Preserve the compact strip when every item has an emoji.
    separator = "" if all(item_emoji(i) for i in inventory[:n]) else ", "
    return separator.join(items)


def clip(text, limit):
    """Bound plain display text without leaving a dangling partial word."""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;·") + "…"


def limited_lines(lines, limit, omitted="… More details in the match links."):
    """Fit complete lines, preserving readable Markdown and an honest overflow note."""
    lines = [str(line) for line in lines if line]
    if len("\n".join(lines)) <= limit:
        return "\n".join(lines)
    kept = []
    for line in lines:
        if len("\n".join([*kept, line, omitted])) > limit:
            break
        kept.append(line)
    return "\n".join([*kept, omitted]) if kept else clip(lines[0], limit)


def application_emoji(name, emojis):
    """Use only an explicitly supplied current application emoji inventory."""
    name = name[:32]
    return f"<:{name}:{emojis[name]}>" if emojis.get(name) else ""


def named_items(items, emojis=None):
    """Final-slot names always remain readable even when emoji assets are absent."""
    return " · ".join(
        " ".join(filter(None, [application_emoji("i_" + (item_key(i) or ""), emojis or {}),
                                 item_name(i)])) for i in items[:6])


def skill_path(skills, limit=260):
    """Number observed non-talent picks, never confuse pick order with hero level."""
    if skills is None:
        return "Unavailable"
    if not skills:
        return "No non-talent picks recorded"
    tokens = [f"{i}. {clip(name, 48)}" for i, name in enumerate(skills[:8], 1)]
    path = []
    for token in tokens:
        if len(" → ".join([*path, token])) > limit - 16:
            break
        path.append(token)
    suffix = f" (+{len(tokens) - len(path)} picks)" if len(path) < len(tokens) else ""
    return " → ".join(path) + suffix


def _review_signals(raw, duration):
    # Local import keeps shared presentation importable independently of either
    # product's ingestion/eligibility policy. This function performs no I/O.
    from .report_signals import summarize
    return summarize(raw if isinstance(raw, dict) else {"players": []}, {}, duration)


def _notes(value):
    """Optional archive notes may predate the current schema or be malformed."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    return [note for note in value if isinstance(note, dict)] if isinstance(value, list) else []


def _score(value):
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value)) else 0


def _note_entries(note, key):
    entries = note.get(key)
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, (list, tuple)) and len(entry) >= 2
            and isinstance(entry[0], str) and entry[0]
            and isinstance(entry[1], (int, float)) and not isinstance(entry[1], bool)
            and math.isfinite(entry[1]) and entry[1] >= 0]


def menu_player_line(p, rawp=None, detail="items"):
    """Ten complete inventories and ten skill paths live on separate focus tabs."""
    if detail != "skills":
        line = player_line(p)
        if not p.get("items"):
            known = isinstance(rawp, dict) and all(
                f"item{i}Id" in rawp and rawp[f"item{i}Id"] in (None, 0)
                and not isinstance(rawp[f"item{i}Id"], bool) for i in range(6))
            line += " · no final-slot items" if known else " · items unavailable"
        return line
    skills = _review_signals({"players": [rawp]} if rawp else None, 0)["skills"].get(0)
    label = hero_emoji(p["hero_id"]) or f"**{hero_name(p['hero_id'])}**"
    return f"{label} · {skill_path(skills, 240)}"


def menu_match_preview(m, n=None, rank_label=""):
    """One real V2 TextDisplay, bounded for a five-card list without hidden overflow.

    Show the roster, then item/skill/micro evidence rather than ten KDA rows.
    Archive rarity notes retain their established score thresholds; ordinary
    inventory/skill fallbacks are observations, not claims of unusual play.
    """
    raw = m.get("_raw") or {"players": []}
    signals = _review_signals(raw, m.get("duration", 0))
    players = m.get("players") or []
    num = f"`{n}` · " if n else ""
    kills = f"{m['kills']} kills" if m.get("_scores_available", True) else "Kill totals unavailable"
    lines = [f"{num}{rank_label}`{m['id']}` · `{dur(m['duration'])}` · {kills}"]
    for radiant, side in ((True, "R"), (False, "D")):
        roster = " · ".join(hero_emoji(p["hero_id"]) or hero_name(p["hero_id"])
                            for p in players if bool(p["is_radiant"]) == radiant)
        lines.append(f"**{side}** {roster}")
    evidence = []
    item_notes = [note for note in _notes(m.get("_item_notes"))
                  if _score(note.get("score")) >= 6 and _note_entries(note, "items")
                  and (m.get("_weirdness") is None or _score(m["_weirdness"]) >= 6)]
    if item_notes:
        note = item_notes[0]
        buys = ", ".join(f"{x[0]} @{x[1]}m" for x in _note_entries(note, "items")[:2])
        evidence.append("Items · " + hero_name(note.get("hero_id")) + ": " + buys)
    else:
        index = next((i for i, p in enumerate(players) if p.get("items")), None)
        if index is not None:
            p = players[index]
            evidence.append(f"Items · {hero_name(p['hero_id'])}: {named_items(p['items'][:3])}")
    skill_notes = _notes(m.get("_skill_notes")) if _score(m.get("_skill_weirdness")) >= 8 else []
    if skill_notes:
        note = skill_notes[0]
        picks = ", ".join(f"{x[0]} @pick {x[1]}" for x in _note_entries(note, "picks")[:2])
        if picks:
            evidence.append(f"Skills · {hero_name(note.get('hero_id'))}: {picks}")
    if not any(line.startswith("Skills") for line in evidence):
        index = next((i for i, skills in signals["skills"].items() if skills), None)
        if index is not None and index < len(players):
            evidence.append(f"Skills · {hero_name(players[index]['hero_id'])}: "
                            + " → ".join(signals["skills"][index][:3]))
    moment = next(((i, receipts[0]) for i, receipts in signals["players"].items() if receipts), None)
    if moment and moment[0] < len(players):
        evidence.append(f"Review · {hero_name(players[moment[0]]['hero_id'])}: {moment[1]}")
    if not evidence:
        evidence.append("Item / skill / event detail unavailable for this match.")
    lines.extend(clip(line, 112) for line in evidence[:3])
    return limited_lines(lines, 640, "Open match for the remaining build details.")


def menu_focus_receipts(m, item_rows=None, skill_rows=None, raw_rows=None):
    """Distinct winner-neutral evidence, with item/skill receipts first.

    Keep complete heading-plus-line blocks so the board can allocate its shared
    text budget without splitting Markdown or letting repeated notes crowd out
    a different kind of evidence.
    """
    def unique(values):
        return list(dict.fromkeys(values))

    raw = m.get("_raw")
    if raw is None and raw_rows:
        try:
            raw = json.loads(raw_rows[0][0])
        except (TypeError, ValueError, IndexError):
            raw = None
    signals = _review_signals(raw, m.get("duration", 0))
    blocks = []
    moments = []
    for i, receipts in signals["players"].items():
        if receipts and i < len(m["players"]):
            moments.append(f"{hero_name(m['players'][i]['hero_id'])}: "
                           + "; ".join(unique(receipts)[:2]))
    notes = m.get("_item_notes")
    item_score = m.get("_weirdness")
    if notes is None and item_rows:
        item_score, notes = item_rows[0]
    lines = []
    for note in _notes(notes):
        if _score(note.get("score")) < 6 or (item_score is not None and _score(item_score) < 6):
            continue
        buys = ", ".join(unique(f"{x[0]} @{x[1]}m" for x in _note_entries(note, "items"))[:3])
        if buys:
            lines.append(f"{hero_name(note.get('hero_id'))}: {buys}")
    if lines:
        blocks.append("🌀 **Item build receipts** · corpus-relative\n" + "\n".join(unique(lines)))
    notes = m.get("_skill_notes")
    score = m.get("_skill_weirdness", 0)
    if notes is None and skill_rows:
        score, notes = skill_rows[0]
    lines = []
    if _score(score) >= 8:
        for note in _notes(notes):
            picks = ", ".join(unique(f"{x[0]} @pick {x[1]}"
                                     for x in _note_entries(note, "picks"))[:3])
            if picks:
                lines.append(f"{hero_name(note.get('hero_id'))}: {picks}")
    if lines:
        blocks.append("🧩 **Skill-order receipts** · corpus-relative\n" + "\n".join(unique(lines)))
    if moments:
        blocks.append("🔎 **Review moments**\n"
                      + "\n".join(unique(clip(line, 240) for line in moments)))
    badges = [f"{hero_name(p['hero_id'])}: {'GM' if p['dplus'] >= 26 else 'Master'} "
              f"badge (lvl {p['dplus']})" for p in m["players"] if _score(p.get("dplus")) >= 25]
    if badges:
        blocks.append("🏆 **Dota Plus mastery**\n" + "\n".join(unique(badges)))
    return blocks


def check_embeds(message):
    """Validate classic embed limits separately from the Components V2 budget.

    https://docs.discord.com/developers/resources/message#embed-object-embed-limits
    """
    if message.get("flags", 0) & (1 << 15) and message.get("embeds"):
        raise ValueError("Components V2 messages cannot contain classic embeds")
    embeds = message.get("embeds") or []
    if len(embeds) > 10:
        raise ValueError("More than 10 embeds in one message")
    total = 0
    for embed in embeds:
        if len(embed.get("fields") or []) > 25:
            raise ValueError("More than 25 embed fields")
        texts = [(embed.get("title", ""), 256), (embed.get("description", ""), 4096),
                 ((embed.get("footer") or {}).get("text", ""), 2048),
                 ((embed.get("author") or {}).get("name", ""), 256)]
        for field in embed.get("fields") or []:
            texts.extend([(field["name"], 256), (field["value"], 1024)])
        for value, limit in texts:
            if len(value) > limit:
                raise ValueError(f"Embed text exceeds {limit} characters")
            total += len(value)
    if total > 6000:
        raise ValueError("Embed message exceeds 6000 characters")
    return total


def player_line(p, stat=""):
    """`{hero} K/D/A {items}` — THE glance row. stat: optional trailing text."""
    h = hero_emoji(p["hero_id"]) or f"**{hero_name(p['hero_id'])[:14]}**"
    tail = f"  {stat}" if stat else ""
    kda = "/".join(f"{p[key] if p.get(key) is not None else '?':>2}" for key in ("k", "d", "a"))
    return f"{h} `{kda}` {item_icons(p)}{tail}"


def star_of(m):
    """Most glanceworthy player: feeder if extreme, else top fragger."""
    f = m["feeder"]
    if f["d"] >= 15:
        return f
    return max(m["players"], key=lambda p: p["k"])


def match_line(m, star=None):
    """One-line match row: result/length/kills + the star player's glance row."""
    s = star or star_of(m)
    side = "🟢" if m["radiant_win"] else "🔴"
    return f"{side} `{dur(m['duration'])}` · **{m['kills']}** kills — {player_line(s)}"


# ---------- the factoid ladder (judge: "cheapest charm per line") ----------

def factoid(m):
    f = m["feeder"]
    if f["d"] >= 15:
        return f"{hero_name(f['hero_id'])} died {f['d']} times and would do it again"
    top = max(m["players"], key=lambda p: p["k"])
    if top["k"] >= 20:
        return f"{hero_name(top['hero_id'])} dropped {top['k']} kills on this lobby"
    if m["kpm"] >= 2.5:
        return f"{m['kpm']} kills/min — nobody farmed, everybody fought"
    if m["comeback_gold"] >= 8000:
        return f"winner climbed out of a {m['comeback_gold'] // 1000}k gold hole"
    if m["mins"] >= 45:
        return f"{m['mins']} minutes of trench warfare"
    return ""


# ---------- receipts (spike signal-mining, LOCKED thresholds — do NOT retune) ----------

def player_receipts(rawp, duration_s):
    """Winner-NEUTRAL receipt strings for one raw Stratz player dict: feeding,
    BKB/Midas item shame, randomed hero, died-mid-TP, buyback-then-died. These
    strings NEVER reveal the winner — safe to render regardless of spoiler mode."""
    stats = rawp.get("stats") or {}
    out = []

    time_dead = sum(e.get("timeDead") or 0 for e in stats.get("deathEvents") or [])
    gold_fed = sum(e.get("goldFed") or 0 for e in stats.get("deathEvents") or [])
    frac = time_dead / duration_s if duration_s else 0
    # only flag genuine feeders: dead at least 30% of the game (the old absolute
    # 20-min OR fired on any long game and triggered too often — owner 2026-07-13)
    if frac >= 0.30:
        out.append(f"{time_dead // 60} min ({round(frac * 100)}%) dead, fed {gold_fed // 1000}k gold")

    used = {u["itemId"]: u.get("count", 0) for u in stats.get("itemUsed") or []}

    def bought(item_id):
        return any(b.get("itemId") == item_id and (b.get("time") or 0) > 0
                   for b in stats.get("itemPurchases") or [])

    if bought(BKB_ID) and used.get(BKB_ID, 0) == 0:
        out.append("BKB bought, never used")
    if bought(MIDAS_ID) and used.get(MIDAS_ID, 0) < 10:
        out.append(f"Midas, {used.get(MIDAS_ID, 0)} uses")
    if rawp.get("isRandom"):
        out.append("randomed")

    tp_deaths = sum(1 for e in stats.get("deathEvents") or [] if e.get("isAttemptTpOut"))
    if tp_deaths >= 2:
        out.append(f"died mid-TP x{tp_deaths}")
    dieback_deaths = sum(1 for e in stats.get("deathEvents") or [] if e.get("isDieBack"))
    if dieback_deaths >= 2:
        out.append(f"buyback then died x{dieback_deaths}")

    return out


def megas_tag(raw):
    """Outcome-revealing final barracks fact, requiring literal typed evidence.

    The final mask alone cannot establish when megas began or cause/timing of
    a comeback. Callers MUST hide this tag under spoiler mode.
    """
    winner = raw.get("didRadiantWin")
    if not isinstance(winner, bool):
        return None
    winner_racks = raw.get("barracksStatusRadiant") if winner else raw.get("barracksStatusDire")
    if type(winner_racks) is int and winner_racks == 0:
        return "🔥 Winning team's barracks were all destroyed by game end"
    return None


# ---------- budget guard ----------

def _texts(c):
    # Empirically verified 2026-07-10: select option/label text does NOT count
    # toward the 4000-char pool — only TextDisplay content does.
    yield c.get("content", "")
    for ch in c.get("components", []):
        yield from _texts(ch)
    if "accessory" in c:
        yield from _texts(c["accessory"])


def check(components, where="?"):
    """Count components + chars; raise if over budget. Returns (count, chars)."""
    def count(cs):
        n = 0
        for c in cs:
            n += 1
            n += count(c.get("components", []))
            if "accessory" in c:
                n += 1
        return n

    n = count(components)
    chars = sum(len(t) for c in components for t in _texts(c))
    if n > MAX_COMPONENTS:
        raise ValueError(f"{where}: {n} components > {MAX_COMPONENTS}")
    if chars > MAX_CHARS:
        raise ValueError(f"{where}: {chars} chars > {MAX_CHARS}")
    return n, chars


if __name__ == "__main__":
    ms = load_matches()
    assert len(ms) == 38 and all(m["leads"] for m in ms)
    spiciest = max(ms, key=lambda m: m["feeder"]["d"])
    print(f"ok: {len(ms)} matches; spiciest feeder {spiciest['feeder']['d']} deaths "
          f"({hero_name(spiciest['feeder']['hero_id'])}, match {spiciest['id']})")
    print("factoids:", sum(1 for m in ms if factoid(m)), "/", len(ms))
    print("sample:", factoid(spiciest))
    n, ch = check([{"type": 10, "content": "x" * 100}], "selfcheck")
    assert (n, ch) == (1, 100)
