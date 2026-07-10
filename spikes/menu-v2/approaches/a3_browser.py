"""Herald Match Browser v2 — drill-down kiosk, glance-row edition.

Every list row and every scoreboard row: hero icon + K/D/A + item icons
in the same line. Screens: filter hub -> match list -> match card -> networth.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

GREEN, RED, BLUE = 0x3BA55D, 0xED4245, 0x5865F2


def _hub():
    return [{"type": 17, "accent_color": BLUE, "components": [
        {"type": 10, "content": "## 🔎 Herald Match Browser\n-# 38 matches · Thu Jul 9 · pick filters, hit Show"},
        {"type": 1, "components": [{"type": 3, "custom_id": "hb|f|dur", "placeholder": "⏱️ Length — any", "options": [
            {"label": "Any length", "value": "any"},
            {"label": "Under 25 min (stomps)", "value": "lt25", "description": "13 matches"},
            {"label": "25–40 min", "value": "25to40", "description": "19 matches"},
            {"label": "40+ min (wars)", "value": "gt40", "description": "6 matches"},
        ]}]},
        {"type": 1, "components": [{"type": 3, "custom_id": "hb|f|kills", "placeholder": "🩸 Blood — any", "options": [
            {"label": "Any kill count", "value": "any"},
            {"label": "80+ total kills", "value": "gt80", "description": "12 matches"},
            {"label": "100+ total kills (bloodbaths)", "value": "gt100", "description": "4 matches"},
            {"label": "Had a 15+ death feeder", "value": "feeder", "description": "6 matches"},
        ]}]},
        {"type": 1, "components": [{"type": 3, "custom_id": "hb|f|hero", "placeholder": "🎭 Hero — any", "options": [
            {"label": "Any hero", "value": "any"},
            {"label": "Pudge", "value": "14", "description": "11 matches"},
            {"label": "Crystal Maiden", "value": "5", "description": "10 matches"},
            {"label": "Invoker", "value": "74", "description": "10 matches"},
            {"label": "Sniper", "value": "35", "description": "9 matches"},
        ]}]},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "custom_id": "hb|show", "label": "Show matches"},
            {"type": 2, "style": 2, "custom_id": "hb|lucky", "label": "🎲 Surprise me"},
        ]},
    ]}]


def _list(ms):
    rows = []
    for m in ms[:6]:
        rows.append({"type": 9, "components": [
            {"type": 10, "content": render.match_line(m)},
        ], "accessory": {"type": 2, "style": 2, "custom_id": f"hb|open|{m['id']}", "label": "Open"}})
    return [{"type": 17, "accent_color": BLUE, "components": [
        {"type": 10, "content": "### Results — most kills first · 38 matches"},
        *rows,
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "hb|pg|p", "label": "◀"},
            {"type": 2, "style": 2, "custom_id": "hb|pg|n", "label": "Page 1/7 ▶"},
            {"type": 2, "style": 2, "custom_id": "hb|home", "label": "🏠 Filters"},
        ]},
    ]}]


def _card(m):
    r = sorted([p for p in m["players"] if p["is_radiant"]], key=lambda p: -p["networth"])
    d = sorted([p for p in m["players"] if not p["is_radiant"]], key=lambda p: -p["networth"])
    win = "Radiant" if m["radiant_win"] else "Dire"
    fact = render.factoid(m)
    return [
        {"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
            {"type": 10, "content": f"## Match {m['id']} — {win} win · `{render.dur(m['duration'])}`\n"
                                    f"-# 🟢 {m['kills_r']} — {m['kills_d']} 🔴 · Herald · {fact}"},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "**🟢 Radiant**\n" + "\n".join(render.player_line(p) for p in r)},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "**🔴 Dire**\n" + "\n".join(render.player_line(p) for p in d)},
            {"type": 1, "components": [
                {"type": 2, "style": 1, "custom_id": "hb|nw", "label": "📈 Net worth"},
                {"type": 2, "style": 2, "custom_id": "hb|back", "label": "◀ Results"},
                {"type": 2, "style": 5, "url": f"https://www.opendota.com/matches/{m['id']}", "label": "OpenDota"},
            ]},
        ]},
    ]


def _networth(m):
    png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")
    comps = [{"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
        {"type": 10, "content": f"### 📈 Match {m['id']} — who was winning, minute by minute"},
        {"type": 12, "items": [{"media": {"url": "attachment://nw.png"}}]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "hb|card", "label": "◀ Scoreboard"},
            {"type": 2, "style": 2, "custom_id": "hb|home2", "label": "🏠 Filters"},
        ]},
    ]}]
    return comps, [("nw.png", png)]


def build():
    ms = sorted(render.load_matches(), key=lambda m: -m["kills"])
    spice = next(m for m in ms if m["id"] == 8888295980)
    nw_comps, nw_files = _networth(spice)
    return [
        {"components": _hub(), "files": []},
        {"components": _list(ms), "files": []},
        {"components": _card(spice), "files": []},
        {"components": nw_comps, "files": nw_files},
    ]


if __name__ == "__main__":
    msgs = build()
    ns, chs = [], []
    for i, m in enumerate(msgs):
        n, ch = render.check(m["components"], f"a3[{i}]")
        ns.append(n)
        chs.append(ch)
    print(f"OK a3v2: {len(msgs)} messages, components={ns}, chars={chs}, "
          f"files={sum(len(m['files']) for m in msgs)}")
