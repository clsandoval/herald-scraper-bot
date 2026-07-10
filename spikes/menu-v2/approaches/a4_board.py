"""a4 — The Match Board (Command Deck).

One pinned message IS the entire UI: stacked selects + nav buttons, every
click morphs the board in place (UPDATE_MESSAGE). Mockup shows the three
modes as successive messages: BROWSE, GROUPED (by hero), DETAIL.
"""

import datetime
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import charts
import render

GOLD = 0xC8A03C
GREEN = 0x66BB6A
RED = 0xE05252
PAGE = 5
DETAIL_ID = 8888295980  # Sniper 33/3, PA fed 19 — the ceiling case


# ---------- tiny component builders ----------

def td(text):
    return {"type": 10, "content": text}


def sep():
    return {"type": 14, "divider": True}


def row(*comps):
    return {"type": 1, "components": list(comps)}


def btn(label, cid, style=2, disabled=False):
    b = {"type": 2, "style": style, "label": label, "custom_id": cid}
    if disabled:
        b["disabled"] = True
    return b


def select(cid, placeholder, options, min_v=0, max_v=1):
    return {"type": 3, "custom_id": cid, "placeholder": placeholder,
            "min_values": min_v, "max_values": max_v, "options": options}


def opt(label, value, description=None, default=False, emoji_str=""):
    o = {"label": label[:100], "value": value[:100]}
    if description:
        o["description"] = description[:100]
    if default:
        o["default"] = True
    if emoji_str:  # "<:name:id>" -> partial emoji object
        _, name, eid = emoji_str.strip("<>").split(":")
        o["emoji"] = {"name": name, "id": eid}
    return o


# ---------- formatting helpers ----------

def when(m, with_date=False):
    t = datetime.datetime.fromtimestamp(m["start"])
    fmt = "%a %b %-d, %-I:%M %p" if with_date else "%a %-I:%M %p"
    return t.strftime(fmt)


def hero_strip(m):
    """10 hero emojis when seeded; degrade ladder -> plain names."""
    rad = [p["hero_id"] for p in m["players"] if p["is_radiant"]]
    dire = [p["hero_id"] for p in m["players"] if not p["is_radiant"]]
    r_e = [render.hero_emoji(h) for h in rad]
    d_e = [render.hero_emoji(h) for h in dire]
    if all(r_e) and all(d_e):
        return "".join(r_e) + " ⚔️ " + "".join(d_e)
    names = lambda hs: ", ".join(render.hero_name(h) for h in hs)
    return names(rad) + " ⚔️ " + names(dire)


def match_section(m):
    win = "Radiant win" if m["radiant_win"] else "Dire win"
    lines = [f"**{render.dur(m['duration'])} · {m['kills']} kills · {win}**",
             hero_strip(m)]
    f = render.factoid(m)
    lines.append(f"{when(m)} · {f}" if f else when(m))
    return {"type": 9, "components": [td("\n".join(lines))],
            "accessory": btn("View", f"board:view:{m['id']}")}


def player_line(p, bold):
    e = render.hero_emoji(p["hero_id"])
    name = render.hero_name(p["hero_id"])
    head = f"{e} " if e else ""
    head += f"**{name}**" if bold else name
    gpm = f" · {p['gpm']} GPM" if bold else ""
    items = "".join(render.item_emoji(i) for i in p["items"])
    if not all(render.item_emoji(i) for i in p["items"]):
        # degrade ladder: no item emojis -> first three item names
        items = ", ".join(render.item_name(i) for i in p["items"][:3])
    kda = f"`{p['k']}/{p['d']}/{p['a']}`"
    return f"{head} {kda}{gpm} · {p['networth'] / 1000:.1f}k — {items}"


def team_block(m, radiant):
    ps = sorted((p for p in m["players"] if p["is_radiant"] == radiant),
                key=lambda p: -p["networth"])
    won = m["radiant_win"] == radiant
    head = ("RADIANT" if radiant else "DIRE") + (" — WON" if won else "")
    return f"**{head}**\n" + "\n".join(
        player_line(p, bold=(i == 0)) for i, p in enumerate(ps))


# ---------- the five stacked selects ----------

def show_select():
    return select("board:show", "Show: Bloodbaths first", [
        opt("\U0001f195 Newest first", "newest"),
        opt("\U0001fa78 Bloodbaths — most total kills", "bloodiest", default=True),
        opt("\U0001f525 Absolute chaos — most kills per minute", "chaos"),
        opt("\U0001f550 Marathons — longest games", "longest"),
        opt("⏱ Speedruns — shortest games", "shortest"),
        opt("\U0001faa6 Feeding frenzies — biggest single-player death count", "feeders"),
        opt("⚖️ Nail-biters — closest final gold", "close"),
        opt("\U0001f682 Stomps — biggest final gold lead", "stomps"),
    ], min_v=1)


def day_select(ms):
    per_day = Counter(datetime.date.fromtimestamp(m["start"]) for m in ms)
    latest = max(per_day)
    opts = [opt("Any day", "any")]
    for i in range(7):
        d = latest - datetime.timedelta(days=i)
        n = per_day.get(d, 0)
        opts.append(opt(d.strftime("%A %b %-d"), d.isoformat(),
                        f"{n} matches" if n else "no matches"))
    return select("board:day", "Day: any day", opts)


def len_select(ms):
    buckets = [
        ("Under 25 min", "d_lt25", lambda m: m["mins"] < 25),
        ("25–40 min", "d_25_40", lambda m: 25 <= m["mins"] <= 40),
        ("Over 40 min", "d_gt40", lambda m: m["mins"] > 40),
        ("60+ total kills", "k60", lambda m: m["kills"] >= 60),
        ("80+ total kills", "k80", lambda m: m["kills"] >= 80),
        ("100+ total kills", "k100", lambda m: m["kills"] >= 100),
        ("Someone died 15+ times", "feeder15", lambda m: m["feeder"]["d"] >= 15),
        ("Winner was 5k+ gold behind", "comeback", lambda m: m["comeback_gold"] >= 5000),
    ]
    opts = [opt(label, val, f"{sum(1 for m in ms if pred(m))} matches")
            for label, val, pred in buckets]
    return select("board:len", "Length & bloodshed: anything goes", opts, max_v=8)


def hero_select(ms):
    c = Counter(p["hero_id"] for m in ms for p in m["players"])
    opts = [opt("Anyone", "any")]
    for hid, n in c.most_common(23):
        opts.append(opt(render.hero_name(hid), str(hid), f"{n} matches",
                        emoji_str=render.hero_emoji(hid)))
    opts.append(opt("✏️ Someone else… (type a name)", "other"))
    return select("board:hero", "Hero: anyone", opts)


def group_select(active="none"):
    return select("board:group", "Group: flat list", [
        opt("Flat list (no grouping)", "none", default=active == "none"),
        opt("Group by hero", "hero", default=active == "hero"),
        opt("Group by day", "day", default=active == "day"),
        opt("Group by game length", "len", default=active == "len"),
    ])


def nav_row(page, pages):
    return row(
        btn("◀", "board:page:prev", disabled=page == 1),
        btn(f"Page {page} / {pages}", "board:page:noop", disabled=True),
        btn("▶", "board:page:next", disabled=page == pages),
        btn("\U0001f3b2 Random", "board:random", style=1),
        btn("♻ Reset", "board:reset"),
    )


FOOTER = ("-# Herald bracket only · pulled from OpenDota/Stratz nightly · "
          "filters are shared — last click wins")


# ---------- the three modes ----------

def browse_board(ms):
    top5 = sorted(ms, key=lambda m: -m["kills"])[:PAGE]
    days = sorted({datetime.date.fromtimestamp(m["start"]) for m in ms})
    window = days[0].strftime("%a %b %-d") if len(days) == 1 else \
        f"{days[0].strftime('%a %b %-d')} – {days[-1].strftime('%a %b %-d')}"
    header = (f"# \U0001f4cb Herald Match Board\n**{len(ms)} matches** · {window} · "
              f"**{len(ms)} match your filters** · refreshed nightly")
    return {"type": 17, "accent_color": GOLD, "components": [
        td(header), sep(),
        row(show_select()), row(day_select(ms)), row(len_select(ms)),
        row(hero_select(ms)), row(group_select()),
        sep(), *[match_section(m) for m in top5], sep(),
        nav_row(1, math.ceil(len(ms) / PAGE)), td(FOOTER),
    ]}


def hero_group_section(ms, hid, n):
    played = [m for m in ms if any(p["hero_id"] == hid for p in m["players"])]
    wins = sum(1 for m in played
               if next(p for p in m["players"] if p["hero_id"] == hid)["is_radiant"]
               == m["radiant_win"])
    bloodiest = max(m["kills"] for m in played)
    longest = max(m["duration"] for m in played)
    e = render.hero_emoji(hid)
    head = f"{e} " if e else ""
    text = (f"**{head}{render.hero_name(hid)}** — {n} matches\n"
            f"bloodiest {bloodiest} kills · longest {render.dur(longest)} · "
            f"won {round(100 * wins / n)}%")
    return {"type": 9, "components": [td(text)],
            "accessory": btn("Browse →", f"board:drill:hero:{hid}")}


def grouped_board(ms):
    c = Counter(p["hero_id"] for m in ms for p in m["players"])
    header = (f"# \U0001f4cb Herald Match Board\n**{len(ms)} matches** · "
              f"grouped by hero · {len(c)} heroes played · refreshed nightly")
    return {"type": 17, "accent_color": GOLD, "components": [
        td(header), sep(),
        row(show_select()), row(day_select(ms)), row(len_select(ms)),
        row(hero_select(ms)), row(group_select("hero")),
        sep(), *[hero_group_section(ms, hid, n) for hid, n in c.most_common(PAGE)],
        sep(), nav_row(1, math.ceil(len(c) / PAGE)), td(FOOTER),
    ]}


def detail_board(m):
    win = "Radiant" if m["radiant_win"] else "Dire"
    leads = m["leads"]
    fname = f"nw_{m['id']}_lead.png"
    header = (f"# {win} win · {render.dur(m['duration'])} · {m['kills']} kills\n"
              f"{when(m, with_date=True)} · Herald · match {m['id']}")
    # rule-based footnote, all computed from real data
    lo_i = min(range(len(leads)), key=lambda i: leads[i])
    hi_i = max(range(len(leads)), key=lambda i: leads[i])
    final = leads[-1]
    notes = []
    if m["radiant_win"] and leads[lo_i] < -500:
        notes.append(f"Dire led by {-leads[lo_i] / 1000:.1f}k at {lo_i} min — "
                     f"Radiant flipped it and closed +{final / 1000:.1f}k.")
    elif not m["radiant_win"] and leads[hi_i] > 500:
        notes.append(f"Radiant led by {leads[hi_i] / 1000:.1f}k at {hi_i} min — "
                     f"Dire flipped it and closed {final / 1000:.1f}k.")
    if m["tower_deaths"]:
        notes.append(f"{len(m['tower_deaths'])} towers fell.")
    star = max(m["players"], key=lambda p: p["networth"])
    notes.append(f"{render.hero_name(star['hero_id'])} went "
                 f"{star['k']}/{star['d']} at {star['gpm']} GPM.")
    chart_row = row(select("board:chart", "Chart: who's winning", [
        opt("\U0001f4c8 Who's winning — net worth lead", "lead", default=True),
        opt("\U0001f5e1 Kills per minute — both teams", "kpm"),
        opt("\U0001f4b0 All ten players' gold", "all10"),
    ], min_v=1))
    container = {"type": 17,
                 "accent_color": GREEN if m["radiant_win"] else RED,
                 "components": [
        td(header),
        td(team_block(m, radiant=True)),
        td(team_block(m, radiant=False)),
        sep(),
        {"type": 12, "items": [{"media": {"url": f"attachment://{fname}"},
                                "description": f"Net worth lead over {len(leads) - 1} minutes"}]},
        td("-# " + " ".join(notes)),
        chart_row,
        row(btn("⬅ All matches", "board:back"),
            btn("◀", "board:adj:prev"),
            btn("▶", "board:adj:next"),
            btn("\U0001f3b2 Another", "board:random", style=1),
            {"type": 2, "style": 5, "label": "Dotabuff",
             "url": f"https://www.dotabuff.com/matches/{m['id']}"}),
    ]}
    png = charts.networth_lead_png(leads, f"Match {m['id']} — Net Worth Lead")
    return container, fname, png


# ---------- contract entry point ----------

def build():
    ms = render.load_matches()
    detail = next(m for m in ms if m["id"] == DETAIL_ID)
    d_container, d_fname, d_png = detail_board(detail)
    return [
        {"components": [td(
            "## The Match Board (Command Deck)\n"
            "-# One pinned message IS the entire UI — stacked selects + nav "
            "buttons, every click edits the board in place. Zero new messages, "
            "zero spam. Live it's ONE message morphing; mockup shows its three "
            "modes below.")], "files": []},
        {"components": [
            td("-# MODE 1 / 3 — BROWSE: flat list, five stacked filters"),
            browse_board(ms)], "files": []},
        {"components": [
            td("-# MODE 2 / 3 — GROUPED: same skeleton, rows become hero aggregates"),
            grouped_board(ms)], "files": []},
        {"components": [
            td("-# MODE 3 / 3 — DETAIL: one match expanded, chart swaps in place"),
            d_container], "files": [(d_fname, d_png)]},
    ]


if __name__ == "__main__":
    msgs = build()
    counts, chars, nfiles = [], [], 0

    def att_refs(c, acc):
        if isinstance(c, dict):
            u = c.get("media", {}).get("url", "") if isinstance(c.get("media"), dict) else ""
            if u.startswith("attachment://"):
                acc.add(u.removeprefix("attachment://"))
            for v in c.values():
                att_refs(v, acc)
        elif isinstance(c, list):
            for v in c:
                att_refs(v, acc)
        return acc

    for i, msg in enumerate(msgs, 1):
        n, ch = render.check(msg["components"], f"a4 msg{i}")
        counts.append(n)
        chars.append(ch)
        refs = att_refs(msg["components"], set())
        names = {f[0] for f in msg["files"]}
        assert refs == names, f"msg{i}: attachment refs {refs} != files {names}"
        nfiles += len(msg["files"])
    print(f"OK a4: {len(msgs)} messages, components={counts}, chars={chars}, files={nfiles}")
