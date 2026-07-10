"""The Match Board v2 — one message IS the UI, glance-row edition.

Board states shown as successive messages: BROWSE (glance list) and
MATCH FOCUS (full 10-row glance scoreboard + chart). Every row:
hero icon + K/D/A + item icons, same line.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

GOLD, GREEN, RED = 0xC8A03C, 0x3BA55D, 0xED4245


def _browse(ms):
    rows = "\n".join(render.match_line(m) for m in ms[:8])
    return [{"type": 17, "accent_color": GOLD, "components": [
        {"type": 10, "content": "## 🎛️ THE MATCH BOARD\n-# 38 matches · Thu Jul 9 · sorted: most kills · row shows the match's main character"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": rows},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|sort", "placeholder": "Sort: most kills", "options": [
            {"label": "Most kills", "value": "kills"},
            {"label": "Longest", "value": "dur"},
            {"label": "Biggest feeder", "value": "feed"},
            {"label": "Biggest throw", "value": "throw"},
            {"label": "Newest", "value": "new"},
        ]}]},
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|filter", "placeholder": "Filter: everything", "options": [
            {"label": "Everything", "value": "any"},
            {"label": "Bloodbaths (100+ kills)", "value": "blood", "description": "4 matches"},
            {"label": "Wars (40+ min)", "value": "war", "description": "6 matches"},
            {"label": "Feeder games (15+ deaths)", "value": "feed", "description": "6 matches"},
            {"label": "Throws (winner was 5k+ behind)", "value": "throw", "description": "3 matches"},
        ]}]},
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|open", "placeholder": "🔍 Open a match…", "options": [
            {"label": f"{m['kills']} kills · {render.dur(m['duration'])} · {render.hero_name(render.star_of(m)['hero_id'])} {render.star_of(m)['k']}/{render.star_of(m)['d']}/{render.star_of(m)['a']}",
             "value": str(m["id"])} for m in ms[:8]
        ]}]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "mb|pp", "label": "◀"},
            {"type": 2, "style": 2, "custom_id": "mb|pn", "label": "Page 1/5 ▶"},
            {"type": 2, "style": 1, "custom_id": "mb|dice", "label": "🎲"},
        ]},
    ]}]


def _focus(m):
    r = sorted([p for p in m["players"] if p["is_radiant"]], key=lambda p: -p["networth"])
    d = sorted([p for p in m["players"] if not p["is_radiant"]], key=lambda p: -p["networth"])
    png = charts.sparkline_png(m["leads"])
    win = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
    return [{"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
        {"type": 10, "content": f"## 🎛️ Match {m['id']} · {win} · `{render.dur(m['duration'])}`\n"
                                f"-# 🟢 {m['kills_r']} — {m['kills_d']} 🔴 · {render.factoid(m)}"},
        {"type": 12, "items": [{"media": {"url": "attachment://spark.png"},
                                "description": "net worth lead sparkline"}]},
        {"type": 10, "content": "**🟢 Radiant**\n" + "\n".join(render.player_line(p) for p in r)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**🔴 Dire**\n" + "\n".join(render.player_line(p) for p in d)},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "custom_id": "mb|nw", "label": "📈 Full graph"},
            {"type": 2, "style": 2, "custom_id": "mb|list", "label": "◀ Board"},
            {"type": 2, "style": 5, "url": f"https://www.opendota.com/matches/{m['id']}", "label": "OpenDota"},
        ]},
    ]}], [("spark.png", png)]


def build():
    ms = sorted(render.load_matches(), key=lambda m: -m["kills"])
    focus_comps, focus_files = _focus(ms[0])  # 8888293313, 118 kills
    return [
        {"components": [{"type": 10, "content":
            "-# 🎛️ The Match Board: ONE pinned message is the whole UI — every click "
            "morphs it in place. Two states below: the board, then a match opened."}],
         "files": []},
        {"components": _browse(ms), "files": []},
        {"components": focus_comps, "files": focus_files},
    ]


if __name__ == "__main__":
    msgs = build()
    ns, chs = [], []
    for i, m in enumerate(msgs):
        n, ch = render.check(m["components"], f"a4[{i}]")
        ns.append(n)
        chs.append(ch)
    print(f"OK a4v2: {len(msgs)} messages, components={ns}, chars={chs}, "
          f"files={sum(len(m['files']) for m in msgs)}")
