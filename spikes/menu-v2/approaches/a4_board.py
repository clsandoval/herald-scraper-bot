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
        {"label": "Curated", "value": "spice"},
        {"label": "Newest", "value": "new"},
        {"label": "Most kills", "value": "kills"},
        {"label": "Kills per minute", "value": "kpm"},
        {"label": "Longest", "value": "dur"},
        {"label": "Shortest", "value": "short"},
        {"label": "Biggest feeder", "value": "feed"},
        {"label": "Biggest throw", "value": "throw"},
        {"label": "Biggest comeback", "value": "cb"},
        {"label": "Closest game", "value": "close"},
        {"label": "Biggest stomp", "value": "stomp"},
        {"label": "Highest GPM", "value": "gpm"},
    ]}]}


def _filter_select(active=None):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|filter|{(active or 'none')[:20]}",
        "placeholder": f"Filters: {active}" if active else "Filters (pick any)",
        "min_values": 0, "max_values": 12, "options": [
        {"label": "100+ kills (4)", "value": "blood"},
        {"label": "80+ kills (12)", "value": "fight"},
        {"label": "40+ min (6)", "value": "war"},
        {"label": "Under 20 min (5)", "value": "speed"},
        {"label": "15+ death feeder (6)", "value": "feed"},
        {"label": "Throw (3)", "value": "throw"},
        {"label": "10k+ comeback (2)", "value": "cb"},
        {"label": "Close game (7)", "value": "close"},
        {"label": "Stomp (9)", "value": "stomp"},
        {"label": "Radiant win (21)", "value": "rwin"},
        {"label": "Dire win (17)", "value": "dwin"},
        {"label": "Divine Rapier (3)", "value": "rapier"},
    ]}]}


def _group_select(active="off"):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|group|{active[:20]}",
        "placeholder": f"Group by: {active}", "options": [
        {"label": "Off", "value": "none"},
        {"label": "Hero", "value": "hero"},
        {"label": "Main character", "value": "star"},
        {"label": "Role", "value": "role"},
        {"label": "Length", "value": "dur"},
        {"label": "Kill count", "value": "kills"},
        {"label": "Feeder severity", "value": "feed"},
        {"label": "Throw size", "value": "throw"},
        {"label": "Comeback size", "value": "cb"},
        {"label": "Final gold gap", "value": "gap"},
        {"label": "Winner side", "value": "side"},
        {"label": "Herald depth", "value": "rank"},
        {"label": "Day", "value": "day"},
        {"label": "Hour", "value": "hour"},
        {"label": "Item sightings", "value": "item"},
        {"label": "Towers lost by winner", "value": "towers"},
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
    ]}


def _board(header, rows_text, ms, sort="curated", filt=None, page="1/4"):
    return [{"type": 17, "accent_color": GOLD, "components": [
        {"type": 10, "content": header},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": rows_text},
        {"type": 14, "divider": True, "spacing": 1},
        _sort_select(sort), _filter_select(filt), _group_select(), _open_select(ms),
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

def browse_default(ms):
    top = sorted(ms, key=lambda m: -spice(m))[:10]
    rows = "\n".join(f"{badge(m)} {render.match_line(m)}" for m in top)
    return _board("## 🎛️ MATCH BOARD\n-# 38 matches · Jul 9", rows, top)


def browse_filtered(ms):
    feed = [m for m in ms if m["feeder"]["d"] >= 15]
    rows = "\n".join(f"{badge(m)} {render.match_line(m, star=m['feeder'])}" for m in feed[:8])
    return _board(f"## 🎛️ MATCH BOARD\n-# {len(feed)} matches · filters: 15+ death feeder",
                  rows, feed, filt="15+ death feeder", page="1/1")


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


def build():
    ms = sorted(render.load_matches(), key=lambda m: -m["kills"])
    pa = next(m for m in ms if m["id"] == 8888295980)
    comeback = max(ms, key=lambda m: m["comeback_gold"])
    f1, f1f = focus(ms[0])
    f2, f2f = full_graph(comeback)
    f3, f3f = focus(pa, dice=True)
    return [
        {"components": [_state("hub — first thing everyone sees"), *browse_default(ms)], "files": []},
        {"components": [_state("filtered: 15+ death feeder"), *browse_filtered(ms)], "files": []},
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
