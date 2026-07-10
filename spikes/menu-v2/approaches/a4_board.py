"""The Match Board v4 — control hub, no fluff.

One pinned message is the whole UI. Every row: hero icon + K/D/A + item icons.
Selects are direct: no descriptions, no flavor. Filters are multi-select.
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

GOLD, GREEN, RED, PURPLE = 0xC8A03C, 0x3BA55D, 0xED4245, 0x9B59B6


def _state(caption):
    return {"type": 10, "content": f"-# {caption}"}


def _sort_select(active="curated"):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|sort|{active[:20]}",
        "placeholder": f"Sort: {active}", "options": [
        {"label": "Most watchable (deaths + kills + throws)", "value": "spice"},
        {"label": "Newest", "value": "new"},
        {"label": "Most total kills", "value": "kills"},
        {"label": "Most kills per minute", "value": "kpm"},
        {"label": "Longest game", "value": "dur"},
        {"label": "Shortest game", "value": "short"},
        {"label": "Most deaths by one player", "value": "feed"},
        {"label": "Biggest gold lead lost by the loser", "value": "throw"},
        {"label": "Biggest gold deficit overcome by the winner", "value": "cb"},
        {"label": "Smallest gold lead all game", "value": "close"},
        {"label": "Biggest final gold gap", "value": "stomp"},
        {"label": "Highest single-player GPM", "value": "gpm"},
    ]}]}


def _filter_select(active=None):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|filter|{(active or 'none')[:20]}",
        "placeholder": f"Filters: {active}" if active else "Filters (pick any)",
        "min_values": 0, "max_values": 12, "options": [
        {"label": "100+ total kills (4)", "value": "blood"},
        {"label": "80+ total kills (12)", "value": "fight"},
        {"label": "Longer than 40 min (6)", "value": "war"},
        {"label": "Shorter than 20 min (5)", "value": "speed"},
        {"label": "A player died 15+ times (6)", "value": "feed"},
        {"label": "Loser had a 5k+ gold lead at some point (3)", "value": "throw"},
        {"label": "Winner was 10k+ gold behind at some point (2)", "value": "cb"},
        {"label": "Gold lead never passed 5k (7)", "value": "close"},
        {"label": "One side led start to finish (9)", "value": "stomp"},
        {"label": "Radiant won (21)", "value": "rwin"},
        {"label": "Dire won (17)", "value": "dwin"},
        {"label": "Divine Rapier was bought (3)", "value": "rapier"},
    ]}]}


def _group_select(active="off"):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|group|{active[:20]}",
        "placeholder": f"Group by: {active}", "options": [
        {"label": "Off", "value": "none"},
        {"label": "Hero", "value": "hero"},
        {"label": "Star player's hero (top fragger or feeder)", "value": "star"},
        {"label": "Role (carry / mid / offlane / supports)", "value": "role"},
        {"label": "Game length (<20 / 20-30 / 30-40 / 40+)", "value": "dur"},
        {"label": "Total kills (<60 / 60-80 / 80-100 / 100+)", "value": "kills"},
        {"label": "Worst feeder's deaths (<10 / 10-14 / 15+)", "value": "feed"},
        {"label": "Gold lead lost by the loser", "value": "throw"},
        {"label": "Gold deficit overcome by the winner", "value": "cb"},
        {"label": "Final gold gap", "value": "gap"},
        {"label": "Winning side (Radiant / Dire)", "value": "side"},
        {"label": "Rank (Herald 1 → 5)", "value": "rank"},
        {"label": "Day of week", "value": "day"},
        {"label": "Hour of day", "value": "hour"},
        {"label": "Notable items (Rapier / Midas / no boots)", "value": "item"},
        {"label": "Towers the winner lost", "value": "towers"},
    ]}]}


def _open_select(ms, n=10):
    return {"type": 1, "components": [{"type": 3, "custom_id": "mb|open", "placeholder": "Open a match", "options": [
        {"label": f"{render.dur(m['duration'])} · {m['kills']} kills · "
                  f"{render.hero_name(render.star_of(m)['hero_id'])} "
                  f"{render.star_of(m)['k']}/{render.star_of(m)['d']}/{render.star_of(m)['a']}",
         "value": str(m["id"])} for m in ms[:n]
    ]}]}


def _nav(page="1/4"):
    return {"type": 1, "components": [
        {"type": 2, "style": 2, "custom_id": "mb|pp", "label": "◀"},
        {"type": 2, "style": 2, "custom_id": "mb|pn", "label": f"{page} ▶"},
        {"type": 2, "style": 1, "custom_id": "mb|dice", "label": "🎲"},
        {"type": 2, "style": 2, "custom_id": "mb|adv", "label": "⚙️ Advanced"},
    ]}


def _graph_row(m, files):
    """Section: kills + length text, mini networth graph as thumbnail accessory."""
    fname = f"t{m['id']}.png"
    files.append((fname, charts.thumb_spark_png(m["leads"])))
    r = "".join(render.hero_emoji(p["hero_id"]) or "•" for p in m["players"] if p["is_radiant"])
    d = "".join(render.hero_emoji(p["hero_id"]) or "•" for p in m["players"] if not p["is_radiant"])
    return {"type": 9, "components": [
        {"type": 10, "content": f"**{m['kills']}** kills · `{render.dur(m['duration'])}`\n{r} ⚔ {d}"},
    ], "accessory": {"type": 11, "media": {"url": f"attachment://{fname}"}}}


def _board(header, ms, files, sort="curated", filt=None, page="1/6", n=7):
    return [{"type": 17, "accent_color": GOLD, "components": [
        {"type": 10, "content": header},
        {"type": 14, "divider": True, "spacing": 1},
        *[_graph_row(m, files) for m in ms[:n]],
        {"type": 14, "divider": True, "spacing": 1},
        _sort_select(sort), _filter_select(filt), _group_select(), _open_select(ms, n),
        _nav(page),
    ]}]


# ---------- curation ----------

def spice(m):
    s = 0
    s += max(0, m["feeder"]["d"] - 10) * 3
    s += max(0, m["kills"] - 70) // 5
    s += min(m["comeback_gold"], 20000) // 1500
    s += max(0, m["mins"] - 40)
    s += 3 if m["mins"] < 20 and m["kpm"] > 2.5 else 0
    return s


def badge(m):
    if m["feeder"]["d"] >= 15:
        return "💀"
    if m["comeback_gold"] >= 10000:
        return "📈"
    if m["kills"] >= 100:
        return "🩸"
    if m["mins"] >= 40:
        return "⏱️"
    if m["kpm"] >= 2.8:
        return "⚡"
    return "▪️"


# ---------- states ----------

def browse_default(ms, files):
    top = sorted(ms, key=lambda m: -spice(m))
    return _board("## 🎛️ MATCH BOARD\n-# 38 matches · Jul 9", top, files)


def browse_filtered(ms, files):
    feed = [m for m in ms if m["feeder"]["d"] >= 15]
    return _board(f"## 🎛️ MATCH BOARD\n-# {len(feed)} matches · filters: a player died 15+ times",
                  feed, files, filt="a player died 15+ times", page="1/1", n=6)


def grouped_hero(ms):
    agg = defaultdict(lambda: {"n": 0, "w": 0, "d": 0, "worst": None})
    for m in ms:
        for p in m["players"]:
            a = agg[p["hero_id"]]
            a["n"] += 1
            a["w"] += (p["is_radiant"] == m["radiant_win"])
            a["d"] += p["d"]
            if a["worst"] is None or p["d"] > a["worst"]["d"]:
                a["worst"] = p
    top = sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:10]
    rows = "\n".join(
        f"{render.hero_emoji(h) or '•'} **{render.hero_name(h)}** · {a['n']} games · "
        f"{a['w'] * 100 // a['n']}% win · {a['d'] / a['n']:.1f} avg deaths"
        for h, a in top)
    return [{"type": 17, "accent_color": PURPLE, "components": [
        {"type": 10, "content": "## 🎛️ MATCH BOARD\n-# grouped by hero · 107 heroes"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": rows},
        {"type": 14, "divider": True, "spacing": 1},
        _group_select("hero"),
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|drill", "placeholder": "Open a hero", "options": [
            {"label": f"{render.hero_name(h)} ({a['n']})", "value": str(h)} for h, a in top
        ]}]},
        _nav("1/11"),
    ]}]


def grouped_length(ms):
    buckets = [("Under 20 min", 0, 20), ("20–30 min", 20, 30), ("30–40 min", 30, 40), ("40+ min", 40, 999)]
    rows, opts = [], []
    for label, lo, hi in buckets:
        bs = [m for m in ms if lo <= m["mins"] < hi]
        if not bs:
            continue
        rows.append(f"⏱️ **{label}** · {len(bs)} matches · avg {sum(m['kills'] for m in bs) // len(bs)} kills "
                    f"· max {max(m['kills'] for m in bs)}")
        opts.append({"label": f"{label} ({len(bs)})", "value": label})
    return [{"type": 17, "accent_color": PURPLE, "components": [
        {"type": 10, "content": "## 🎛️ MATCH BOARD\n-# grouped by length"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "\n".join(rows)},
        {"type": 14, "divider": True, "spacing": 1},
        _group_select("length"),
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|drillb", "placeholder": "Open a bucket", "options": opts}]},
        _nav("1/1"),
    ]}]


def focus(m, dice=False):
    r = sorted([p for p in m["players"] if p["is_radiant"]], key=lambda p: -p["networth"])
    d = sorted([p for p in m["players"] if not p["is_radiant"]], key=lambda p: -p["networth"])
    png = charts.sparkline_png(m["leads"])
    win = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
    head = "🎲" if dice else f"Match {m['id']}"
    fname = f"spark_{m['id']}.png"
    return [{"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
        {"type": 10, "content": f"## {head} · {win} · `{render.dur(m['duration'])}` · "
                                f"🟢 {m['kills_r']} — {m['kills_d']} 🔴"},
        {"type": 12, "items": [{"media": {"url": f"attachment://{fname}"}}]},
        {"type": 10, "content": "**Radiant**\n" + "\n".join(render.player_line(p) for p in r)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**Dire**\n" + "\n".join(render.player_line(p) for p in d)},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "custom_id": "mb|nw", "label": "📈 Graph"},
            {"type": 2, "style": 2, "custom_id": "mb|list", "label": "◀ Board"},
            {"type": 2, "style": 1 if dice else 2, "custom_id": "mb|dice2", "label": "🎲"},
            {"type": 2, "style": 5, "url": f"https://www.opendota.com/matches/{m['id']}", "label": "OpenDota"},
        ]},
    ]}], [(fname, png)]


def full_graph(m):
    png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")
    return [{"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
        {"type": 10, "content": f"## Match {m['id']} · net worth"},
        {"type": 12, "items": [{"media": {"url": "attachment://nwfull.png"}}]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "mb|focus", "label": "◀ Scoreboard"},
            {"type": 2, "style": 2, "custom_id": "mb|list2", "label": "🎛️ Board"},
        ]},
    ]}], [("nwfull.png", png)]


def advanced_modal():
    """Mock of the native Discord popup the ⚙️ Advanced button opens."""
    field = lambda label, val: {"type": 10, "content": f"**{label}**\n```\n{val}\n```"}
    return [{"type": 17, "accent_color": 0x5865F2, "components": [
        {"type": 10, "content": "## ⚙️ Advanced search"},
        field("Min duration (minutes)", "90"),
        field("Min total kills", "90"),
        field("Heroes (all must be in the match)", "largo, treant"),
        field("Items (name xCount)", "rapier x2"),
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "adv|cancel", "label": "Cancel"},
            {"type": 2, "style": 1, "custom_id": "adv|go", "label": "Search"},
        ]},
    ]}]


def advanced_results(ms, files):
    close = sorted(ms, key=lambda m: (-m["kills"], -m["duration"]))[:3]
    return [{"type": 17, "accent_color": GOLD, "components": [
        {"type": 10, "content": "## 🎛️ MATCH BOARD\n-# 0 exact matches · showing 3 closest"
                                "\n-# 90+ min: max this week is 47 · 90+ kills: 12 · Largo+Treant: 0 together · rapier x2: 1"},
        {"type": 14, "divider": True, "spacing": 1},
        *[_graph_row(m, files) for m in close],
        {"type": 14, "divider": True, "spacing": 1},
        _open_select(close, 3),
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "adv|edit", "label": "⚙️ Edit search"},
            {"type": 2, "style": 2, "custom_id": "adv|clear", "label": "✕ Clear"},
        ]},
    ]}]


def build():
    ms = sorted(render.load_matches(), key=lambda m: -m["kills"])
    pa = next(m for m in ms if m["id"] == 8888295980)
    comeback = max(ms, key=lambda m: m["comeback_gold"])
    f1, f1f = focus(ms[0])
    f2, f2f = full_graph(comeback)
    f3, f3f = focus(pa, dice=True)
    hub_files, filt_files = [], []
    hub = browse_default(ms, hub_files)
    filt = browse_filtered(ms, filt_files)
    adv_files = []
    adv = advanced_results(ms, adv_files)
    return [
        {"components": [_state("hub — first thing everyone sees"), *hub], "files": hub_files},
        {"components": [_state("filtered: 15+ death feeder"), *filt], "files": filt_files},
        {"components": [_state("⚙️ Advanced → native popup (mocked): 90min · 90 kills · largo+treant · rapier x2"),
                        *advanced_modal()], "files": []},
        {"components": [_state("submit → board shows result"), *adv], "files": adv_files},
        {"components": [_state("grouped by hero"), *grouped_hero(ms)], "files": []},
        {"components": [_state("grouped by length"), *grouped_length(ms)], "files": []},
        {"components": [_state("match opened"), *f1], "files": f1f},
        {"components": [_state("graph"), *f2], "files": f2f},
        {"components": [_state("🎲 roll"), *f3], "files": f3f},
    ]


if __name__ == "__main__":
    msgs = build()
    ns, chs = [], []
    for i, m in enumerate(msgs):
        n, ch = render.check(m["components"], f"a4[{i}]")
        ns.append(n)
        chs.append(ch)
    print(f"OK a4v4: {len(msgs)} messages, components={ns}, chars={chs}, "
          f"files={sum(len(m['files']) for m in msgs)}")
