"""The Match Board v3 — FULL state tour, glance-row edition.

One pinned message is the whole UI; every message in the thread below is one
state that same message morphs into. Every row: hero icon + K/D/A + item icons.
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

GOLD, GREEN, RED, PURPLE = 0xC8A03C, 0x3BA55D, 0xED4245, 0x9B59B6


def _state(caption):
    return {"type": 10, "content": f"-# ⬇️ STATE: {caption}"}


def _sort_select(active="Curated — most watchable first"):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|sort|{active[:20]}", "placeholder": f"Sort: {active}", "options": [
        {"label": "Curated — most watchable first", "value": "spice", "description": "feeders, throws, bloodbaths bubble up"},
        {"label": "Newest first", "value": "new"},
        {"label": "Most kills", "value": "kills"},
        {"label": "Kills per minute", "value": "kpm", "description": "pure violence density"},
        {"label": "Longest", "value": "dur"},
        {"label": "Shortest", "value": "short"},
        {"label": "Biggest feeder", "value": "feed", "description": "most deaths by one player"},
        {"label": "Biggest throw", "value": "throw", "description": "largest lead the loser held"},
        {"label": "Biggest comeback", "value": "cb", "description": "deepest hole the winner climbed out of"},
        {"label": "Closest game", "value": "close", "description": "networth stayed near even"},
        {"label": "Biggest stomp", "value": "stomp", "description": "largest final gold gap"},
        {"label": "Highest GPM player", "value": "gpm"},
        {"label": "Most towers fallen", "value": "towers"},
    ]}]}


def _filter_select(active="everything"):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|filter|{active[:20]}", "placeholder": f"Filter: {active}", "options": [
        {"label": "Everything", "value": "any", "description": "38 matches"},
        {"label": "Bloodbaths — 100+ kills", "value": "blood", "description": "4 matches"},
        {"label": "Big fights — 80+ kills", "value": "fight", "description": "12 matches"},
        {"label": "Wars — 40+ min", "value": "war", "description": "6 matches"},
        {"label": "Speedruns — under 20 min", "value": "speed", "description": "5 matches"},
        {"label": "Feeder games — someone died 15+", "value": "feed", "description": "6 matches"},
        {"label": "Throws — winner was 5k+ behind", "value": "throw", "description": "3 matches"},
        {"label": "Big comebacks — 10k+ hole", "value": "cb", "description": "2 matches"},
        {"label": "Close games — never past 5k gap", "value": "close", "description": "7 matches"},
        {"label": "Stomps — one-sided the whole way", "value": "stomp", "description": "9 matches"},
        {"label": "Radiant wins", "value": "rwin", "description": "21 matches"},
        {"label": "Dire wins", "value": "dwin", "description": "17 matches"},
        {"label": "Has a Divine Rapier", "value": "rapier", "description": "3 matches, 8 rapiers"},
    ]}]}


def _group_select(active="none — flat list"):
    return {"type": 1, "components": [{"type": 3, "custom_id": f"mb|group|{active[:20]}", "placeholder": f"Group by: {active}", "options": [
        {"label": "No grouping — flat list", "value": "none"},
        {"label": "Hero", "value": "hero", "description": "who shows up in the most disasters"},
        {"label": "Main character", "value": "star", "description": "grouped by each match's protagonist"},
        {"label": "Role / position", "value": "role", "description": "carries vs mids vs hard supports"},
        {"label": "Length", "value": "dur", "description": "speedruns → wars"},
        {"label": "Kill count", "value": "kills", "description": "quiet games → bloodbaths"},
        {"label": "Feeder severity", "value": "feed", "description": "0-9 / 10-14 / 15-17 / 18+ deaths"},
        {"label": "Throw size", "value": "throw", "description": "how big a lead got burned"},
        {"label": "Comeback size", "value": "cb", "description": "how deep the winner's hole was"},
        {"label": "Final gold gap", "value": "gap", "description": "photo finish → massacre"},
        {"label": "Winner side", "value": "side", "description": "Radiant vs Dire"},
        {"label": "Herald depth", "value": "rank", "description": "Herald 1 → Herald 5"},
        {"label": "Day", "value": "day", "description": "which weeknight was cursed"},
        {"label": "Hour", "value": "hour", "description": "3am games hit different"},
        {"label": "Item sightings", "value": "item", "description": "rapiers, Midas count, no-boots club"},
        {"label": "Towers lost by winner", "value": "towers", "description": "clean win → nearly threw"},
    ]}]}


def _open_select(ms, n=10):
    return {"type": 1, "components": [{"type": 3, "custom_id": "mb|open", "placeholder": "🔍 Open a match…", "options": [
        {"label": f"{m['kills']} kills · {render.dur(m['duration'])} · "
                  f"{render.hero_name(render.star_of(m)['hero_id'])} "
                  f"{render.star_of(m)['k']}/{render.star_of(m)['d']}/{render.star_of(m)['a']}",
         "value": str(m["id"])} for m in ms[:n]
    ]}]}


def _nav(page="1/5"):
    return {"type": 1, "components": [
        {"type": 2, "style": 2, "custom_id": "mb|pp", "label": "◀"},
        {"type": 2, "style": 2, "custom_id": "mb|pn", "label": f"Page {page} ▶"},
        {"type": 2, "style": 1, "custom_id": "mb|dice", "label": "🎲"},
    ]}


def _board(title_note, rows_text, ms, sort="Most kills", filt="everything", page="1/5"):
    return [{"type": 17, "accent_color": GOLD, "components": [
        {"type": 10, "content": f"## 🎛️ THE MATCH BOARD\n-# {title_note}"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": rows_text},
        {"type": 14, "divider": True, "spacing": 1},
        _sort_select(sort), _filter_select(filt), _group_select(), _open_select(ms),
        _nav(page),
    ]}]


# ---------- curation: mini replay-quality ladder ----------

def spice(m):
    s = 0
    s += max(0, m["feeder"]["d"] - 10) * 3          # feeder
    s += max(0, m["kills"] - 70) // 5               # bloodbath
    s += min(m["comeback_gold"], 20000) // 1500     # throw/comeback
    s += max(0, m["mins"] - 40)                     # marathon
    s += 3 if m["mins"] < 20 and m["kpm"] > 2.5 else 0  # violent speedrun
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
    return _board("tonight's 10 most watchable · 💀 feeder 🩸 bloodbath 📈 throw ⏱️ war ⚡ violent speedrun",
                  rows, top, page="1/4")


def browse_filtered(ms):
    feed = [m for m in ms if m["feeder"]["d"] >= 15]
    rows = "\n".join(render.match_line(m, star=m["feeder"]) for m in feed[:8])
    return _board(f"filter: **feeder games** · {len(feed)} matches · row = the feeder",
                  rows, feed, filt="feeder games", page="1/1")


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
    top = sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:8]
    rows = "\n".join(
        f"{render.hero_emoji(h) or '•'} **{render.hero_name(h)}** · {a['n']} games · "
        f"{a['w'] * 100 // a['n']}% won · {a['d'] / a['n']:.1f} avg deaths — "
        f"worst seat `{a['worst']['k']}/{a['worst']['d']}/{a['worst']['a']}`"
        for h, a in top)
    return [{"type": 17, "accent_color": PURPLE, "components": [
        {"type": 10, "content": "## 🎛️ THE MATCH BOARD — grouped by hero\n-# 107 heroes · sorted by appearances · pick one to see its matches"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": rows},
        {"type": 14, "divider": True, "spacing": 1},
        _group_select("hero"),
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|drill", "placeholder": "🎭 See this hero's matches…", "options": [
            {"label": f"{render.hero_name(h)} — {a['n']} games", "value": str(h)} for h, a in top
        ]}]},
        _nav("1/14"),
    ]}]


def grouped_length(ms):
    buckets = [("Under 20 min", 0, 20), ("20–30 min", 20, 30), ("30–40 min", 30, 40), ("40+ min", 40, 999)]
    rows = []
    for label, lo, hi in buckets:
        bs = [m for m in ms if lo <= m["mins"] < hi]
        if not bs:
            continue
        blood = max(bs, key=lambda m: m["kills"])
        rows.append(f"⏱️ **{label}** · {len(bs)} matches · avg {sum(m['kills'] for m in bs) // len(bs)} kills"
                    f" — bloodiest: **{blood['kills']}** in `{render.dur(blood['duration'])}`")
    return [{"type": 17, "accent_color": PURPLE, "components": [
        {"type": 10, "content": "## 🎛️ THE MATCH BOARD — grouped by length\n-# stomps at the top, wars at the bottom"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "\n".join(rows)},
        {"type": 14, "divider": True, "spacing": 1},
        _group_select("length"),
        {"type": 1, "components": [{"type": 3, "custom_id": "mb|drillb", "placeholder": "⏱️ Open a bucket…", "options": [
            {"label": "Under 20 min — 5 matches", "value": "b0"},
            {"label": "20–30 min — 21 matches", "value": "b1"},
            {"label": "30–40 min — 6 matches", "value": "b2"},
            {"label": "40+ min — 6 matches", "value": "b3"},
        ]}]},
        _nav("1/1"),
    ]}]


def focus(m, caption, dice=False):
    r = sorted([p for p in m["players"] if p["is_radiant"]], key=lambda p: -p["networth"])
    d = sorted([p for p in m["players"] if not p["is_radiant"]], key=lambda p: -p["networth"])
    png = charts.sparkline_png(m["leads"])
    win = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
    head = "🎲 THE BOARD ROLLS…" if dice else f"Match {m['id']}"
    fname = f"spark_{m['id']}.png"
    return [{"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
        {"type": 10, "content": f"## 🎛️ {head} · {win} · `{render.dur(m['duration'])}`\n"
                                f"-# 🟢 {m['kills_r']} — {m['kills_d']} 🔴 · {render.factoid(m)}"},
        {"type": 12, "items": [{"media": {"url": f"attachment://{fname}"},
                                "description": "net worth lead sparkline"}]},
        {"type": 10, "content": "**🟢 Radiant**\n" + "\n".join(render.player_line(p) for p in r)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**🔴 Dire**\n" + "\n".join(render.player_line(p) for p in d)},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "custom_id": "mb|nw", "label": "📈 Full graph"},
            {"type": 2, "style": 2, "custom_id": "mb|list", "label": "◀ Board"},
            {"type": 2, "style": 1 if dice else 2, "custom_id": "mb|dice2", "label": "🎲 Again" if dice else "🎲"},
            {"type": 2, "style": 5, "url": f"https://www.opendota.com/matches/{m['id']}", "label": "OpenDota"},
        ]},
    ]}], [(fname, png)]


def full_graph(m):
    png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")
    lead_txt = (f"Dire led by **{-m['min_lead']:,}g** at worst" if m["radiant_win"] and m["min_lead"] < 0
                else f"biggest lead **{max(m['max_lead'], -m['min_lead']):,}g**")
    return [{"type": 17, "accent_color": GREEN if m["radiant_win"] else RED, "components": [
        {"type": 10, "content": f"## 🎛️ Match {m['id']} — full graph\n-# {lead_txt} · "
                                f"{len(m['tower_deaths'])} towers fell · {render.factoid(m)}"},
        {"type": 12, "items": [{"media": {"url": "attachment://nwfull.png"}}]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "custom_id": "mb|focus", "label": "◀ Scoreboard"},
            {"type": 2, "style": 2, "custom_id": "mb|list2", "label": "🎛️ Board"},
        ]},
    ]}], [("nwfull.png", png)]


def build():
    ms = sorted(render.load_matches(), key=lambda m: -m["kills"])
    bloodbath = ms[0]                                   # 8888293313, 118 kills
    pa = next(m for m in ms if m["id"] == 8888295980)   # PA 19 deaths
    comeback = max(ms, key=lambda m: m["comeback_gold"])
    f1, f1f = focus(bloodbath, "opened from the board")
    f2, f2f = full_graph(comeback)
    f3, f3f = focus(pa, "dice roll", dice=True)
    msgs = [
        {"components": [{"type": 10, "content":
            "-# 🎛️ **The Match Board — full tour.** One pinned message is the whole UI; "
            "each message below is a state it morphs into when you click. Nothing here "
            "is a separate screen in real life."}], "files": []},
        {"components": [_state("THE CONTROL HUB — what everyone sees first: curated 10 + every control"), *browse_default(ms)], "files": []},
        {"components": [_state("filter select → feeder games (rows switch to the feeder)"), *browse_filtered(ms)], "files": []},
        {"components": [_state("group select → by hero (aggregate rows, drill via select)"), *grouped_hero(ms)], "files": []},
        {"components": [_state("group select → by length (buckets, drill via select)"), *grouped_length(ms)], "files": []},
        {"components": [_state("open a match → glance scoreboard + sparkline"), *f1], "files": f1f},
        {"components": [_state("📈 full graph — the 27k-gold comeback"), *f2], "files": f2f},
        {"components": [_state("🎲 — the board picks for you"), *f3], "files": f3f},
    ]
    return msgs


if __name__ == "__main__":
    msgs = build()
    ns, chs = [], []
    for i, m in enumerate(msgs):
        n, ch = render.check(m["components"], f"a4[{i}]")
        ns.append(n)
        chs.append(ch)
    print(f"OK a4v3: {len(msgs)} messages, components={ns}, chars={chs}, "
          f"files={sum(len(m['files']) for m in msgs)}")
