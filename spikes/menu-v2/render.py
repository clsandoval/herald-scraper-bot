"""Shared render layer for the six menu mockups.

Loads the real fixture + current dotaconstants, precomputes a friendly
per-match view, resolves hero/item names + CDN URLs + app emojis, provides
the factoid ladder and the component/char budget guard.

All mockup builders import from here so limits are enforced in ONE place.
"""

import json
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
    it = _item_by_id.get(iid)
    return (it.get("dname") or it["key"]) if it else f"Item {iid}"


def item_key(iid):
    it = _item_by_id.get(iid)
    return it["key"] if it else None


def item_img(iid):
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
    return f"{s // 60}:{s % 60:02d}"


# ---------- processed match view ----------

def load_matches():
    """Real fixture -> list of friendly dicts, newest first."""
    raw = json.load(open(f"{HERE}/fixtures/herald_matches.json"))
    out = []
    for m in raw["matches"]:
        rk = sum(m.get("radiantKills") or [])
        dk = sum(m.get("direKills") or [])
        leads = m.get("radiantNetworthLeads") or [0]
        players = []
        for p in m["players"]:
            items = [p.get(f"item{i}Id") for i in range(6)]
            players.append({
                "hero_id": p["heroId"], "is_radiant": p["isRadiant"],
                "k": p["kills"], "d": p["deaths"], "a": p["assists"],
                "gpm": p.get("goldPerMinute", 0), "networth": p.get("networth", 0),
                "items": [i for i in items if i], "lane": p.get("lane"),
                "role": p.get("role"), "position": p.get("position"),
                "networth_per_min": (p.get("stats") or {}).get("networthPerMinute") or [],
                "purchases": (p.get("stats") or {}).get("itemPurchases") or [],
                "dplus": (p.get("dotaPlus") or {}).get("level") or 0,
            })
        feeder = max(players, key=lambda p: p["d"])
        win_r = m["didRadiantWin"]
        max_lead, min_lead = max(leads), min(leads)
        # winner's worst deficit: how far behind the eventual winner ever was
        deficit = -min_lead if win_r else max_lead
        out.append({
            "id": m["id"], "duration": m["durationSeconds"], "mins": m["durationSeconds"] // 60,
            "start": m.get("startDateTime"), "radiant_win": win_r,
            "kills_r": rk, "kills_d": dk, "kills": rk + dk,
            "kpm": round((rk + dk) / max(m["durationSeconds"] / 60, 1), 1),
            "bracket": m.get("bracket"), "rank": m.get("rank"),
            "leads": leads, "max_lead": max_lead, "min_lead": min_lead,
            "comeback_gold": deficit if deficit > 0 else 0,
            "feeder": feeder, "players": players,
            "tower_deaths": m.get("towerDeaths") or [],
            "lanes": {"top": m.get("topLaneOutcome"), "mid": m.get("midLaneOutcome"),
                      "bot": m.get("bottomLaneOutcome")},
        })
    out.sort(key=lambda m: -(m["start"] or 0))
    return out


# ---------- glance rows: hero icon + KDA + item icons in ONE line ----------

def item_icons(p, n=6):
    """Inline item emoji strip; missing emojis render as ▫."""
    return "".join(item_emoji(i) or "▫" for i in p["items"][:n])


def player_line(p, stat=""):
    """`{hero} K/D/A {items}` — THE glance row. stat: optional trailing text."""
    h = hero_emoji(p["hero_id"]) or f"**{hero_name(p['hero_id'])[:14]}**"
    tail = f"  {stat}" if stat else ""
    return f"{h} `{p['k']:>2}/{p['d']:>2}/{p['a']:>2}` {item_icons(p)}{tail}"


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
    """Outcome-revealing string when the winner's own barracks bitmask == 0
    (won while your own base was megged, ~6.7% of the corpus). None otherwise.
    Callers MUST hide this under spoiler mode — player_receipts() above is
    winner-neutral and safe regardless, this is not."""
    winner_racks = raw.get("barracksStatusRadiant") if raw.get("didRadiantWin") else raw.get("barracksStatusDire")
    if winner_racks == 0:
        return "🔥 Won from mega creeps — the winning team's barracks were all razed"
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
