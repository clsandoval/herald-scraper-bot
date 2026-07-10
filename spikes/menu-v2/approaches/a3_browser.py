"""a3_browser — "Herald Match Browser": drill-down kiosk mockup.

Screens shown (successive messages, in drill order):
  M0 public kiosk -> L0 filter hub -> L1 results list -> L2 match card
  (spice match 8888295980) -> L3a players -> L3b networth (real chart).
All numbers come from the real fixture via render.load_matches().
"""

import datetime
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

MS = render.load_matches()
SPICE_ID = 8888295980
SPICE = next(m for m in MS if m["id"] == SPICE_ID)

BRONZE = 0xC27C0E
RUST = 0xB35900
GREEN = 0x2ECC71
RED = 0xE74C3C

LANE = {"SAFE_LANE": "Safe", "MID_LANE": "Mid", "OFF_LANE": "Off"}

# state segment shared by every component on a screen; only the action differs
_ST = "d0|u0|k0|h0|s1"


def cid(action, p=1, m=0, x=0):
    return f"hb|{action}|{_ST}|p{p}|m{m}|x{x}"


# ---------- tiny component builders ----------

def td(text):
    return {"type": 10, "content": text}


def sep():
    return {"type": 14, "divider": True, "spacing": 1}


def row(*comps):
    return {"type": 1, "components": list(comps)}


def btn(label, custom_id=None, style=2, emoji=None, disabled=False, url=None):
    b = {"type": 2, "label": label}
    if url:
        b["style"], b["url"] = 5, url
    else:
        b["style"], b["custom_id"] = style, custom_id
    if emoji:
        b["emoji"] = {"name": emoji}
    if disabled:
        b["disabled"] = True
    return b


def select(custom_id, placeholder, options):
    return {"type": 3, "custom_id": custom_id, "placeholder": placeholder,
            "options": options}


def opt(label, value, description=None, default=False):
    o = {"label": label[:100], "value": str(value)[:100]}
    if description:
        o["description"] = description[:100]
    if default:
        o["default"] = True
    return o


def container(comps, accent):
    return {"type": 17, "accent_color": accent, "components": comps}


def section(text, accessory):
    return {"type": 9, "components": [td(text)], "accessory": accessory}


# ---------- data helpers (emoji seeding pending -> name fallbacks) ----------

def hero_tag(hid):
    return render.hero_emoji(hid) or render.hero_name(hid)


def hero_strip(players):
    """Emoji strip when seeded, comma'd names otherwise — never double spaces."""
    tags = [hero_tag(p["hero_id"]) for p in players]
    joined_flush = all(t.startswith("<:") for t in tags)
    return ("".join if joined_flush else ", ".join)(tags)


def hero_label(hid):
    e = render.hero_emoji(hid)
    return f"{e} {render.hero_name(hid)}" if e else render.hero_name(hid)


def when(m, fmt="%a %b %-d, %-I:%M %p"):
    return datetime.datetime.fromtimestamp(m["start"]).strftime(fmt)


def score_line(m):
    dot = "\U0001f7e2" if m["radiant_win"] else "\U0001f534"
    return f"**{dot} {m['kills_r']} – {m['kills_d']}**"


def kfmt(gold):
    return f"{gold / 1000:.1f}k"


# ---------- M0: public kiosk (the only public message) ----------

def m0_kiosk():
    bloodiest = max(MS, key=lambda m: m["kills"])
    longest = max(MS, key=lambda m: m["duration"])
    feedy = max(MS, key=lambda m: m["feeder"]["d"])
    f = feedy["feeder"]
    text = (
        "## Herald Match Browser\n"
        "*Drill-down kiosk: filters → list → match card → players / networth / items.*\n"
        f"**{len(MS)}** Herald matches on file · {when(MS[-1], '%a %b %-d')}\n"
        f"Bloodiest: **{bloodiest['kills']} kills** · Longest: **{render.dur(longest['duration'])}** · "
        f"Most feeding: **{f['k']}/{f['d']} {render.hero_name(f['hero_id'])}**"
    )
    return container([
        td(text),
        row(
            btn("Browse Matches", cid("open"), style=1),
            btn("Surprise Me", cid("rand"), emoji="\U0001f3b2"),
        ),
    ], BRONZE)


# ---------- L0: filter hub ----------

def _dur_bucket(m):
    if m["mins"] < 20:
        return "speed"
    if m["mins"] < 35:
        return "std"
    if m["mins"] < 50:
        return "slog"
    return "eternal"


def _kill_bucket(m):
    k = m["kills"]
    if k < 40:
        return "chill"
    if k < 70:
        return "spicy"
    if k < 100:
        return "blood"
    return "war"


def l0_hub():
    days = Counter(when(m, "%a %b %-d") for m in MS)
    dur_c = Counter(_dur_bucket(m) for m in MS)
    kill_c = Counter(_kill_bucket(m) for m in MS)
    picks = Counter(p["hero_id"] for m in MS for p in m["players"])

    day_opts = [opt(f"Any day ({len(MS)})", "any")] + [
        opt(f"{d} ({n})", f"day{i}") for i, (d, n) in enumerate(sorted(days.items()))
    ]
    dur_opts = [
        opt(f"Any length ({len(MS)})", "any"),
        opt(f"Speedruns · under 20 min ({dur_c['speed']})", "speed"),
        opt(f"Standard · 20–35 min ({dur_c['std']})", "std"),
        opt(f"Slogs · 35–50 min ({dur_c['slog']})", "slog"),
        opt(f"Eternal wars · 50 min + ({dur_c['eternal']})", "eternal"),
    ]
    kill_opts = [
        opt(f"Any ({len(MS)})", "any"),
        opt(f"Chill · under 40 kills ({kill_c['chill']})", "chill"),
        opt(f"Spicy · 40–70 kills ({kill_c['spicy']})", "spicy"),
        opt(f"Bloodbath · 70–100 kills ({kill_c['blood']})", "blood"),
        opt(f"Total war · 100+ kills ({kill_c['war']})", "war"),
    ]
    hero_opts = [opt("Any hero", "any")] + [
        opt(render.hero_name(h), f"h{h}", description=f"{n} matches")
        for h, n in picks.most_common(22)
    ] + [opt("Type a hero name…", "other", description="opens a search box")]

    text = (
        "## Herald Match Browser\n"
        f"**{len(MS)} matches** · {when(MS[-1], '%a %b %-d')}\n"
        "Set filters, then **Show Matches** — or roll the dice."
    )
    return container([
        td(text),
        sep(),
        row(select(cid("selday"), "\U0001f4c5 Day — any", day_opts)),
        row(select(cid("seldur"), "⏱️ Length — any", dur_opts)),
        row(select(cid("selkill"), "\U0001fa78 Bloodshed — any", kill_opts)),
        row(select(cid("selhero"), "\U0001f3ad Hero — any", hero_opts)),
        row(
            btn("Show Matches", cid("list"), style=1),
            btn("Surprise Me", cid("rand"), emoji="\U0001f3b2"),
            btn("Chaos Mode", cid("chaos"), style=4, emoji="\U0001f525"),
        ),
    ], RUST)


# ---------- L1: results list ----------

def _list_row(m):
    r = hero_strip([p for p in m["players"] if p["is_radiant"]])
    d = hero_strip([p for p in m["players"] if not p["is_radiant"]])
    fact = render.factoid(m) or f"{m['kpm']} kills/min"
    text = (
        f"{score_line(m)} · {render.dur(m['duration'])} · {when(m)}\n"
        f"{r} **vs** {d}\n"
        f"⚡ {fact}"
    )
    return section(text, btn("View", cid("m", m=m["id"]), style=1))


def l1_list():
    ranked = sorted(MS, key=lambda m: -m["kills"])
    pages = (len(ranked) + 4) // 5
    sort_opts = [
        opt("\U0001fa78 Most kills", "s1", default=True),
        opt("⚡ Highest kills per minute", "s2"),
        opt("⏱️ Longest first", "s3"),
        opt("⏱️ Shortest first", "s4"),
        opt("\U0001f550 Most recent", "s5"),
        opt("\U0001f504 Biggest comeback (networth swing)", "s6"),
        opt("\U0001f4c5 Grouped by day", "s7"),
        opt("\U0001f3ad Grouped by top hero", "s8"),
    ]
    header = (
        "### Results — \U0001fa78 Any · \U0001f4c5 Any day · ⏱️ Any length\n"
        f"**{len(ranked)} matches** · sorted by most kills · page 1 / {pages}"
    )
    comps = [td(header), row(select(cid("selsort"), "Sort: Most kills", sort_opts)), sep()]
    comps += [_list_row(m) for m in ranked[:5]]
    comps += [sep(), row(
        btn("◀ Prev", cid("prev"), disabled=True),
        btn("Next ▶", cid("next")),
        btn("Random from these", cid("rand", p=1), emoji="\U0001f3b2"),
        btn("Filters", cid("home"), emoji="\U0001f3e0"),
    )]
    return container(comps, RUST)


# ---------- L2: match card ----------

def l2_card(m):
    win_side = "Radiant" if m["radiant_win"] else "Dire"
    towers_r = sum(1 for t in m["tower_deaths"] if not t["isRadiant"])  # dire towers down
    towers_d = len(m["tower_deaths"]) - towers_r
    dot = "\U0001f7e2" if m["radiant_win"] else "\U0001f534"
    head = (
        f"## {dot} {win_side} Victory — {m['kills_r']} : {m['kills_d']}\n"
        f"Match `{m['id']}` · {render.dur(m['duration'])} · {when(m)} · Herald ☠️\n"
        f"**{m['kills']} kills** · {m['kpm']} kills/min · Towers {towers_r} – {towers_d}"
    )

    def team_line(radiant):
        ps = [p for p in m["players"] if p["is_radiant"] == radiant]
        return " · ".join(
            f"{hero_label(p['hero_id'])} {p['k']}/{p['d']}/{p['a']}" for p in ps
        )

    teams = (
        f"**Radiant — {m['kills_r']}**\n{team_line(True)}\n"
        f"**Dire — {m['kills_d']}**\n{team_line(False)}"
    )

    f = m["feeder"]
    rich = max(m["players"], key=lambda p: p["networth"])
    top = max(m["players"], key=lambda p: p["k"])
    hi = (
        f"\U0001f480 **Feeder of the game:** {render.hero_name(f['hero_id'])} "
        f"{f['k']}/{f['d']}/{f['a']} · \U0001f911 **Richest:** "
        f"{render.hero_name(rich['hero_id'])} {kfmt(rich['networth'])} ({rich['gpm']} GPM)\n"
        f"\U0001f52b {render.hero_name(top['hero_id'])} went {top['k']}/{top['d']} "
        f"in a {m['kills']}-kill game — in Herald"
    )

    return container([
        td(head),
        sep(),
        td(teams),
        td(hi),
        sep(),
        row(
            btn("Players", cid("pl", m=m["id"]), style=1, emoji="\U0001f465"),
            btn("Networth", cid("nw", m=m["id"]), emoji="\U0001f4c8"),
            btn("Items", cid("it", m=m["id"]), emoji="\U0001f6d2"),
        ),
        row(
            btn("◀ Results", cid("back", m=m["id"])),
            btn("Another random", cid("rand", m=m["id"]), emoji="\U0001f3b2"),
            btn("Filters", cid("home", m=m["id"]), emoji="\U0001f3e0"),
            btn("OpenDota ↗", url=f"https://www.opendota.com/matches/{m['id']}"),
        ),
    ], GREEN if m["radiant_win"] else RED)


# ---------- L3a: players view ----------

def _player_block(m, radiant):
    lines = [f"**{'Radiant' if radiant else 'Dire'}**"]
    for p in m["players"]:
        if p["is_radiant"] != radiant:
            continue
        e = render.hero_emoji(p["hero_id"])
        lead = f"{e} " if e else ""
        lines.append(
            f"{lead}**{render.hero_name(p['hero_id'])}** · {LANE.get(p['lane'], '?')} · "
            f"{p['k']}/{p['d']}/{p['a']} · {p['gpm']} GPM · {kfmt(p['networth'])}"
        )
        items = [render.item_emoji(i) or render.item_name(i) for i in p["items"]]
        lines.append("-# " + (", ".join(items) if items else "no items"))
    return "\n".join(lines)


def l3a_players(m):
    head = (
        f"### \U0001f465 Players — Match `{m['id']}` · "
        f"{score_line(m)} · {render.dur(m['duration'])}"
    )
    return container([
        td(head),
        td(_player_block(m, True)),
        sep(),
        td(_player_block(m, False)),
        sep(),
        row(
            btn("◀ Match", cid("m", m=m["id"])),
            btn("Networth", cid("nw", m=m["id"]), emoji="\U0001f4c8"),
            btn("Items", cid("it", m=m["id"]), emoji="\U0001f6d2"),
            btn("Filters", cid("home", m=m["id"]), emoji="\U0001f3e0"),
        ),
    ], GREEN if m["radiant_win"] else RED)


# ---------- L3b: networth view (real chart) ----------

def l3b_networth(m):
    leads = m["leads"]
    hi_i = max(range(len(leads)), key=lambda i: leads[i])
    lo_i = min(range(len(leads)), key=lambda i: leads[i])
    lead_side = "Radiant" if leads[hi_i] >= -leads[lo_i] else "Dire"
    peak_i = hi_i if lead_side == "Radiant" else lo_i
    dip_i = lo_i if lead_side == "Radiant" else hi_i

    def at(i):
        return "the final whistle" if i >= m["mins"] else f"{i}:00"

    caption = (
        f"### \U0001f4c8 Networth — Match `{m['id']}`\n"
        f"{lead_side} peaked **+{kfmt(abs(leads[peak_i]))}** at {at(peak_i)} · "
        f"worst {lead_side} deficit **{kfmt(abs(leads[dip_i]))}** at {at(dip_i)} · "
        f"ended at {render.dur(m['duration'])}"
    )
    fname = f"nw_{m['id']}_lead.png"
    png = charts.networth_lead_png(leads, f"Match {m['id']} — Net Worth Lead")

    mode_opts = [
        opt("Team networth lead", "x0", default=True),
        opt("All 10 players", "x1"),
        opt("Cores only", "x2"),
        opt("Supports only", "x3"),
    ]
    for i, p in enumerate(m["players"]):
        side = "Radiant" if p["is_radiant"] else "Dire"
        mode_opts.append(opt(
            f"{render.hero_name(p['hero_id'])} ({side} {LANE.get(p['lane'], '?')})",
            f"x{10 + i}",
            description=f"{p['k']}/{p['d']}/{p['a']} · {kfmt(p['networth'])} networth",
        ))

    comps = container([
        td(caption),
        {"type": 12, "items": [{"media": {"url": f"attachment://{fname}"},
                                "description": "Networth lead graph"}]},
        row(select(cid("nwmode", m=m["id"]), "View: Team lead", mode_opts)),
        row(
            btn("◀ Match", cid("m", m=m["id"])),
            btn("Players", cid("pl", m=m["id"]), emoji="\U0001f465"),
            btn("Items", cid("it", m=m["id"]), emoji="\U0001f6d2"),
            btn("Filters", cid("home", m=m["id"]), emoji="\U0001f3e0"),
        ),
    ], GREEN if m["radiant_win"] else RED)
    return comps, [(fname, png)]


# ---------- build ----------

def build():
    nw_comps, nw_files = l3b_networth(SPICE)
    return [
        {"components": [m0_kiosk()], "files": []},
        {"components": [l0_hub()], "files": []},
        {"components": [l1_list()], "files": []},
        {"components": [l2_card(SPICE)], "files": []},
        {"components": [l3a_players(SPICE)], "files": []},
        {"components": [nw_comps], "files": nw_files},
    ]


if __name__ == "__main__":
    msgs = build()
    counts, chars, nfiles = [], [], 0

    def attachment_refs(cs):
        out = []
        for c in cs:
            for item in c.get("items", []):
                url = (item.get("media") or {}).get("url", "")
                if url.startswith("attachment://"):
                    out.append(url[len("attachment://"):])
            acc = c.get("accessory")
            if acc and acc.get("type") == 11:
                url = (acc.get("media") or {}).get("url", "")
                if url.startswith("attachment://"):
                    out.append(url[len("attachment://"):])
            out += attachment_refs(c.get("components", []))
        return out

    def custom_ids(cs):
        out = []
        for c in cs:
            if "custom_id" in c:
                out.append(c["custom_id"])
            if "accessory" in c:
                out += custom_ids([c["accessory"]])
            out += custom_ids(c.get("components", []))
        return out

    for i, msg in enumerate(msgs):
        n, ch = render.check(msg["components"], f"msg{i}")
        counts.append(n)
        chars.append(ch)
        nfiles += len(msg["files"])
        names = {f[0] for f in msg["files"]}
        for ref in attachment_refs(msg["components"]):
            assert ref in names, f"msg{i}: attachment://{ref} has no file tuple"
        cids = custom_ids(msg["components"])
        assert len(cids) == len(set(cids)), f"msg{i}: duplicate custom_id"
        assert all(len(c) <= 100 for c in cids), f"msg{i}: custom_id > 100 chars"
    print(f"OK a3: {len(msgs)} messages, components={counts}, chars={chars}, files={nfiles}")
