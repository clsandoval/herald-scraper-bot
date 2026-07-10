"""Approach 1 — The Herald Ledger.

Group-by-first stat explorer as a card catalog: SHELVES (pick a group-by)
-> DRAWER (aggregate table + distribution chart) -> STACK (paged match list)
-> CARD (single match). Static mockup: 5 messages, real fixture aggregates.
"""

import datetime
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
import matplotlib.pyplot as plt

import charts
import render

ACCENT = 0xA83A32  # dota red
RADIANT_GREEN = 0x3BA55D
DIRE_RED = 0xED4245

MS = render.load_matches()
CARD_ID = 8888293313  # 118 kills in 46:56, the fixture's bloodiest


# ---------- small helpers ----------

def _dt(m):
    return datetime.datetime.fromtimestamp(m["start"])


def _he(hid):
    return render.hero_emoji(hid) or "•"


def _hero_partial(hid):
    e = render._emoji.get(f"h_{render.hero_short(hid)}"[:32])
    return {"id": e["id"], "name": e["name"]} if e else None


def _items_str(p):
    parts = [render.item_emoji(i) or render.item_name(i) for i in p["items"][:6]]
    return "".join(x if x.startswith("<") else f" {x}" for x in parts).strip()


def _td(content):
    return {"type": 10, "content": content}


def _sep():
    return {"type": 14, "divider": True, "spacing": 1}


def _row(*components):
    return {"type": 1, "components": list(components)}


def _btn(label, cid, style=2, disabled=False, url=None):
    b = {"type": 2, "label": label, "style": style, "disabled": disabled}
    if url:
        b["url"] = url
    else:
        b["custom_id"] = cid
    return b


def _gallery(name, alt):
    return {"type": 12, "items": [{"media": {"url": f"attachment://{name}"},
                                   "description": alt}]}


def _bars_png(labels, values, title, color=charts.RADIANT, horizontal=False):
    """Dark-theme bar chart matching charts.py styling."""
    fig, ax = plt.subplots(figsize=(6.8, 3.6) if horizontal else (7.2, 3.2), dpi=144)
    charts._style(ax, fig)
    if horizontal:
        ys = range(len(labels))
        ax.barh(ys, values, color=color, alpha=0.8)
        ax.set_yticks(list(ys), labels)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        for y, v in zip(ys, values):
            ax.annotate(str(v), (v, y), textcoords="offset points", xytext=(5, 0),
                        va="center", color=charts.INK, fontsize=9, fontweight="bold")
    else:
        xs = range(len(labels))
        ax.bar(xs, values, color=color, alpha=0.8)
        ax.set_xticks(list(xs), labels)
        ax.grid(axis="x", visible=False)
        for x, v in zip(xs, values):
            ax.annotate(str(v), (x, v), textcoords="offset points", xytext=(0, 4),
                        ha="center", color=charts.INK, fontsize=9, fontweight="bold")
    ax.set_title(title, color=charts.INK, fontsize=11, loc="left", pad=10)
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=charts.SURFACE, edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


# ---------- real aggregates ----------

DUR_BUCKETS = [("under 20 min", 0, 20), ("20–25 min", 20, 25),
               ("25–30 min", 25, 30), ("30–35 min", 30, 35),
               ("35–40 min", 35, 40), ("40 min and up", 40, 10_000)]

KILL_BUCKETS = [("<45", 0, 45), ("45–60", 45, 60), ("60–80", 60, 80),
                ("80–100", 80, 100), ("100+", 100, 10_000)]


def _dur_rows():
    rows = []
    for label, lo, hi in DUR_BUCKETS:
        b = [m for m in MS if lo <= m["mins"] < hi]
        if b:
            wild = max(b, key=lambda m: m["kills"])
            rows.append((label, b, len(b), round(sum(m["kills"] for m in b) / len(b)),
                         f"{wild['kills']} kills in {render.dur(wild['duration'])}"))
        else:
            rows.append((label, [], 0, None, "—"))
    return rows


def _hero_rows():
    agg = defaultdict(lambda: [0, 0, 0])  # games, wins, deaths
    for m in MS:
        for p in m["players"]:
            a = agg[p["hero_id"]]
            a[0] += 1
            a[1] += p["is_radiant"] == m["radiant_win"]
            a[2] += p["d"]
    rows = [(hid, g, round(100 * w / g), d / g) for hid, (g, w, d) in agg.items()]
    rows.sort(key=lambda r: (-r[1], r[3]))
    return rows  # sorted by most played


# ---------- views ----------

def shelves_msg():
    n = len(MS)
    avg_dur = sum(m["duration"] for m in MS) // n
    avg_kills = round(sum(m["kills"] for m in MS) / n)
    bloody = max(MS, key=lambda m: m["kills"])
    worst = max(MS, key=lambda m: m["feeder"]["d"])
    f = worst["feeder"]
    night = _dt(MS[0]).strftime("%A, %b %d").replace(" 0", " ")

    head = (
        "## \U0001F4D2 The Herald Ledger\n"
        "*A card catalog for the worst games ever played — pick a shelf, "
        "open a drawer, pull a match.*\n"
        f"**{night}** · **{n}** matches on file\n"
        f"Avg game **{render.dur(avg_dur)}** · avg **{avg_kills}** kills · "
        f"bloodiest **{bloody['kills']} kills** in {render.dur(bloody['duration'])} · "
        f"deadliest seat **{f['k']}/{f['d']}/{f['a']}** "
        f"({render.hero_name(f['hero_id'])})"
    )
    n_heroes = len(_hero_rows())
    lo_k, hi_k = min(m["kills"] for m in MS), max(m["kills"] for m in MS)
    lo_d, hi_d = min(m["mins"] for m in MS), max(m["mins"] for m in MS)
    shelf_select = {
        "type": 3, "custom_id": "L|shelf",
        "placeholder": "Group tonight's matches by…",
        "options": [
            {"label": "⏱️ Game length", "value": "dur",
             "description": f"{lo_d}-minute stomps to {hi_d}-minute sagas"},
            {"label": "⚔️ Total kills", "value": "kills",
             "description": f"a quiet {lo_k}-kill farm to a {hi_k}-kill warzone"},
            {"label": "\U0001F9D9 Hero", "value": "hero",
             "description": f"{n_heroes} heroes, sorted by how often they fed"},
            {"label": "\U0001F480 Feeder score", "value": "deaths",
             "description": "drawers by the match's worst K/D"},
            {"label": "\U0001F504 Comeback size", "value": "comeback",
             "description": "how big a gold hole did the winner climb out of"},
            {"label": "\U0001F319 Time of day", "value": "tod",
             "description": "3 AM games hit different"},
            {"label": "\U0001F3F3️ Winner & stomp size", "value": "side",
             "description": "Radiant vs Dire, nail-biter vs massacre"},
            {"label": "\U0001F4C5 Day of the week", "value": "day",
             "description": "one drawer — every one of these was a Thursday"},
        ],
    }
    components = [{
        "type": 17, "accent_color": ACCENT,
        "components": [
            _td(head),
            _sep(),
            _td("**Pick a shelf:** every shelf sorts the night's matches "
                "into drawers you can open."),
            _row(shelf_select),
            _row(_btn("\U0001F3B2 Pull a random match", "L|rand"),
                 _btn("\U0001F336️ Tonight's chaos", "L|chaos", style=4),
                 _btn("❔ How this works", "L|help")),
            _gallery("night_overview.png",
                     f"Kills per match, {night}: most games land between 60 and 100 kills"),
        ],
    }]
    counts = [sum(1 for m in MS if lo <= m["kills"] < hi) for _, lo, hi in KILL_BUCKETS]
    png = _bars_png([b[0] for b in KILL_BUCKETS], counts,
                    f"Kills per match — {night} · {n} matches",
                    color=charts.DIRE)
    return {"components": components, "files": [("night_overview.png", png)]}


def drawer_dur_msg():
    rows = _dur_rows()
    table = "Drawer          Matches  Avg kills  Wildest match\n"
    for label, _, cnt, avg, wild in rows:
        table += (f"{label:<16}{cnt:>7}  {avg if avg is not None else '—':>9}"
                  f"  {wild}\n")
    head = (f"# ⏱️ Shelf: Game length — {len(MS)} matches\n"
            f"```\n{table}```")

    options = [
        {"label": f"⏱️ {label} — {cnt} matches",
         "value": f"dur={lo}", "description": f"avg {avg} kills · wildest: {wild}"}
        for (label, _, cnt, avg, wild), (_, lo, _hi) in zip(rows, DUR_BUCKETS) if cnt
    ]
    components = [{
        "type": 17, "accent_color": ACCENT,
        "components": [
            _td(head),
            _gallery("dist_dur.png",
                     "Matches per game-length drawer; 25 to 30 minutes is the fat bucket"),
            _row({"type": 3, "custom_id": "L|drawer_open|dur",
                  "placeholder": "Open a drawer…", "options": options}),
            _row(_btn("⬅️ All shelves", "L|shelf_home"),
                 _btn("\U0001F3B2 Random from this shelf", "L|rand|dur")),
        ],
    }]
    png = _bars_png([r[0].replace(" min", "").replace("under ", "<") for r in rows],
                    [r[2] for r in rows],
                    f"Matches per drawer — game length (minutes)")
    return {"components": components, "files": [("dist_dur.png", png)]}


def drawer_hero_msg():
    rows = _hero_rows()
    table = "Hero              Games  Win%  Avg deaths\n"
    for hid, g, w, d in rows[:12]:
        table += f"{render.hero_name(hid):<18}{g:>5}  {w:>3}%  {d:>10.1f}\n"
    head = (f"# \U0001F9D9 Shelf: Hero — {len(rows)} heroes across "
            f"{len(MS)} matches\nSorted by **most played**\n```\n{table}```")

    sort_select = {
        "type": 3, "custom_id": "L|hero_sort", "placeholder": "Sort: most played",
        "options": [
            {"label": "Most played", "value": "played"},
            {"label": "Highest winrate", "value": "win"},
            {"label": "Lowest winrate", "value": "lose",
             "description": "the true Heralds"},
            {"label": "Most avg deaths", "value": "deaths"},
        ],
    }
    hero_options = []
    for hid, g, w, d in rows[:15]:
        o = {"label": render.hero_name(hid), "value": f"hero={hid}",
             "description": f"{g} games · {w}% win · {d:.1f} avg deaths"}
        pe = _hero_partial(hid)
        if pe:
            o["emoji"] = pe
        hero_options.append(o)

    components = [{
        "type": 17, "accent_color": ACCENT,
        "components": [
            _td(head),
            _gallery("dist_hero.png",
                     "Games played for the 15 most-picked heroes; Pudge on top with 11"),
            _row(sort_select),
            _row({"type": 3, "custom_id": "L|drawer_open|hero|hp=1",
                  "placeholder": "Open a hero's drawer…", "options": hero_options}),
            _row(_btn("◀", "L|hero_page|0", disabled=True),
                 _btn(f"Heroes 1–15 of {len(rows)}", "L|hero_noop", disabled=True),
                 _btn("▶", "L|hero_page|2"),
                 _btn("⬅️ All shelves", "L|shelf_home2")),
        ],
    }]
    png = _bars_png([render.hero_name(hid) for hid, *_ in rows[:15]],
                    [g for _, g, *_ in rows[:15]],
                    "Most-picked heroes tonight", horizontal=True)
    return {"components": components, "files": [("dist_hero.png", png)]}


def stack_msg():
    drawer = sorted((m for m in MS if m["mins"] >= 40), key=lambda m: -m["kills"])
    head = (f"# ⏱️ 40 min and up — {len(drawer)} matches · "
            f"page 1 of 2\nSorted by **bloodiest first**")

    sections = []
    for m in drawer[:5]:
        rad = "".join(_he(p["hero_id"]) for p in m["players"] if p["is_radiant"])
        dire = "".join(_he(p["hero_id"]) for p in m["players"] if not p["is_radiant"])
        f = m["feeder"]
        day = _dt(m).strftime("%a %b %d").replace(" 0", " ")
        txt = (f"**{render.dur(m['duration'])} · Radiant {m['kills_r']} – "
               f"{m['kills_d']} Dire** · {day}\n{rad} vs {dire}\n"
               f"{m['kills']} kills · worst seat: "
               f"{render.hero_name(f['hero_id'])} **{f['k']}/{f['d']}/{f['a']}**")
        sections.append({
            "type": 9, "components": [_td(txt)],
            "accessory": _btn("Open", f"L|card|{m['id']}|from=dur40.kills.1", style=1),
        })

    sort_select = {
        "type": 3, "custom_id": "L|stack_sort|dur=40",
        "placeholder": "Sort: bloodiest first",
        "options": [{"label": lbl, "value": v} for lbl, v in [
            ("Bloodiest first", "kills"), ("Longest", "long"), ("Shortest", "short"),
            ("Closest scoreline", "close"), ("Biggest stomp", "stomp"),
            ("Biggest feeder", "feeder"), ("Newest", "new")]],
    }
    components = [{
        "type": 17, "accent_color": ACCENT,
        "components": [
            _td(head),
            *sections,
            _row(sort_select),
            _row(_btn("◀ Prev", "L|stack_p|0", disabled=True),
                 _btn("Page 1/2", "L|stack_noop", disabled=True),
                 _btn("Next ▶", "L|stack_p|2"),
                 _btn("⬆️ Back to drawers", "L|drawer|dur"),
                 _btn("\U0001F3B2 Random from drawer", "L|rand|dur=40")),
        ],
    }]
    return {"components": components, "files": []}


ROLE = {"CORE": "core", "LIGHT_SUPPORT": "support", "HARD_SUPPORT": "hard support"}
LANE = {"SAFE_LANE": "safe lane", "MID_LANE": "mid lane", "OFF_LANE": "offlane",
        "JUNGLE": "jungle", "ROAMING": "roaming"}


def card_msg():
    m = next(x for x in MS if x["id"] == CARD_ID)
    day = _dt(m).strftime("%A %b %d, %I:%M %p").replace(" 0", " ")
    head = (f"# Radiant {m['kills_r']} – {m['kills_d']} Dire · "
            f"{render.dur(m['duration'])}\n{day} · Herald bracket · "
            f"match {m['id']}")

    def roster(is_radiant):
        won = m["radiant_win"] == is_radiant
        lines = [f"**{'RADIANT' if is_radiant else 'DIRE'}"
                 f"{' — winners' if won else ''}**"]
        for p in m["players"]:
            if p["is_radiant"] != is_radiant:
                continue
            lines.append(
                f"{_he(p['hero_id'])} **{render.hero_name(p['hero_id'])}** "
                f"{p['k']}/{p['d']}/{p['a']} · {p['gpm']} GPM · "
                f"{p['networth'] / 1000:.1f}k — {_items_str(p)}")
        return "\n".join(lines)

    player_options = []
    for i, p in enumerate(m["players"]):
        side = "Radiant" if p["is_radiant"] else "Dire"
        role = " ".join(x for x in (LANE.get(p["lane"], ""), ROLE.get(p["role"], ""))
                        if x) or "position unknown"
        o = {"label": f"{render.hero_name(p['hero_id'])} — "
                      f"{p['k']}/{p['d']}/{p['a']}, {p['gpm']} GPM",
             "value": str(i), "description": f"{side} · {role}"}
        pe = _hero_partial(p["hero_id"])
        if pe:
            o["emoji"] = pe
        player_options.append(o)

    components = [{
        "type": 17,
        "accent_color": RADIANT_GREEN if m["radiant_win"] else DIRE_RED,
        "components": [
            _td(head),
            _td(roster(True)),
            _td(roster(False)),
            _gallery(f"nw_{m['id']}.png",
                     f"Gold lead over time; Radiant peaked at "
                     f"{m['max_lead'] / 1000:.1f}k ahead"),
            _row({"type": 3, "custom_id": f"L|player_pick|{m['id']}",
                  "placeholder": "Pull a player's report card…",
                  "options": player_options}),
            _row(_btn("⬅️ Back to stack", "L|stack|dur=40|s=kills|p=1"),
                 _btn("\U0001F3B2 Another one", "L|rand|dur=40|again"),
                 _btn("\U0001F4CC Keep this one", f"L|pin|{m['id']}", style=3),
                 _btn("OpenDota", None, style=5,
                      url=f"https://www.opendota.com/matches/{m['id']}")),
        ],
    }]
    png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")
    return {"components": components, "files": [(f"nw_{m['id']}.png", png)]}


def build():
    return [shelves_msg(), drawer_dur_msg(), drawer_hero_msg(),
            stack_msg(), card_msg()]


if __name__ == "__main__":
    msgs = build()
    counts, chars, nfiles = [], [], 0
    for i, msg in enumerate(msgs, 1):
        n, ch = render.check(msg["components"], f"a1 msg{i}")
        counts.append(n)
        chars.append(ch)
        nfiles += len(msg["files"])
        # every attachment:// reference must have a matching file tuple
        names = {name for name, _ in msg["files"]}

        def walk(c):
            url = ((c.get("media") or {}).get("url", ""))
            if url.startswith("attachment://"):
                assert url.removeprefix("attachment://") in names, f"msg{i}: {url}"
            for ch_ in c.get("components", []):
                walk(ch_)
            for it in c.get("items", []):
                walk(it)
            if "accessory" in c:
                walk(c["accessory"])

        for c in msg["components"]:
            walk(c)
        for name, data in msg["files"]:
            assert data[:8] == b"\x89PNG\r\n\x1a\n", f"msg{i}: {name} not a PNG"
    print(f"OK a1: {len(msgs)} messages, components={counts}, "
          f"chars={chars}, files={nfiles}")
