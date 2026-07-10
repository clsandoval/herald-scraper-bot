"""a0 "The Herald Reel" — poster-wall movie-catalog mockup.

One persistent gallery message the bot edits in place; media-first browsing.
Pillow poster composites from the design are approximated with MediaGalleries
of CDN hero portraits + matplotlib charts (per spike instructions).
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

GOLD = 0xC8A951
RADIANT_GREEN = 0x92A525
POSTERS_PER_PAGE = 4


def _dt(m):
    return datetime.datetime.fromtimestamp(m["start"]) if m["start"] else None


def _he(hid):
    return render.hero_emoji(hid) or "•"


def _ie(iid):
    return render.item_emoji(iid) or "•"


def _hero_emoji_obj(hid):
    """{'name','id'} dict for select-option emoji, or None if unseeded."""
    e = render._emoji.get(f"h_{render.hero_short(hid)}"[:32])
    return {"name": e["name"], "id": str(e["id"])} if e else None


def _pos(p):
    return (p.get("position") or "POSITION_?").replace("POSITION_", "Pos ")


def _star(m):
    return max(m["players"], key=lambda p: p["k"])


def _tragic(m):
    """Most tragic player: most deaths, fewest kills breaks ties."""
    return max(m["players"], key=lambda p: (p["d"], -p["k"]))


def _sep(large=False):
    return {"type": 14, "divider": True, "spacing": 2 if large else 1}


def _txt(content):
    return {"type": 10, "content": content}


# ---------- message 1: gallery wall (the hub) ----------

def _gallery_wall(ms):
    top4 = sorted(ms, key=lambda m: -m["kills"])[:POSTERS_PER_PAGE]
    pages = -(-len(ms) // POSTERS_PER_PAGE)
    day = _dt(ms[0]).strftime("%a %b %-d")

    posters = {
        "type": 12,
        "items": [
            {
                "media": {"url": render.hero_img(_star(m)["hero_id"])},
                "description": f"Poster: {render.hero_name(_star(m)['hero_id'])} — "
                               f"{m['kills']} kills in {render.dur(m['duration'])}",
            }
            for m in top4
        ],
    }

    rows = []
    for i, m in enumerate(top4, 1):
        s, f = _star(m), _tragic(m)
        head = (f"**{i} · {m['kills']} kills · {render.dur(m['duration'])} · "
                f"{'Radiant' if m['radiant_win'] else 'Dire'} wins**")
        line = (f"{_he(s['hero_id'])} {render.hero_name(s['hero_id'])} "
                f"{s['k']}/{s['d']}/{s['a']} ({s['gpm']} GPM) · "
                f"{_he(f['hero_id'])} {render.hero_name(f['hero_id'])} dies **{f['d']}×**")
        rows.append({
            "type": 9,
            "components": [_txt(f"{head}\n{line}")],
            "accessory": {"type": 2, "style": 1, "label": "Open",
                          "custom_id": f"a0:open:{m['id']}"},
        })

    lens = {
        "type": 1,
        "components": [{
            "type": 3, "custom_id": "a0:lens", "placeholder": "🎬 Sort the reel…",
            "options": [
                {"label": "Bloodiest first", "value": "blood", "emoji": {"name": "🩸"}, "default": True},
                {"label": "Longest epics", "value": "long", "emoji": {"name": "⏳"}},
                {"label": "Speedruns", "value": "short", "emoji": {"name": "⚡"}},
                {"label": "Chaos index", "value": "chaos", "emoji": {"name": "🌪️"},
                 "description": "kills/min + comebacks + throw factor"},
                {"label": "Biggest throws", "value": "throw", "emoji": {"name": "📉"},
                 "description": "largest networth lead lost"},
                {"label": "Tower massacres", "value": "towers", "emoji": {"name": "🏰"}},
                {"label": "Freshest", "value": "fresh", "emoji": {"name": "🕐"}},
                {"label": "By day — calendar view", "value": "calendar", "emoji": {"name": "📅"}},
                {"label": "Hero hunt…", "value": "herohunt", "emoji": {"name": "🔍"},
                 "description": "find matches with a specific hero"},
            ],
        }],
    }

    filt_opts = (
        [{"label": f"Day: {d}", "value": f"day{i}", "emoji": {"name": "📅"}}
         for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday",
                                "Friday", "Saturday", "Sunday"])]
        + [{"label": f"Length: {t}", "value": f"dur{i}", "emoji": {"name": "⏱️"}}
           for i, t in enumerate(["under 25 min", "25–35 min", "35–45 min", "45+ min"])]
        + [{"label": f"Kills: {t}", "value": f"k{i}", "emoji": {"name": "🩸"}}
           for i, t in enumerate(["under 40", "40–70", "70+"])]
        + [{"label": "Clear all filters", "value": "clear", "emoji": {"name": "✖️"}}]
    )
    filt = {
        "type": 1,
        "components": [{
            "type": 3, "custom_id": "a0:filter", "placeholder": "🧰 Filter… (pick up to 3)",
            "min_values": 0, "max_values": 3, "options": filt_opts,
        }],
    }

    nav = {
        "type": 1,
        "components": [
            {"type": 2, "style": 2, "emoji": {"name": "◀"}, "custom_id": "a0:page:prev"},
            {"type": 2, "style": 2, "emoji": {"name": "▶"}, "custom_id": "a0:page:next"},
            {"type": 2, "style": 3, "label": "🎲 Surprise me", "custom_id": "a0:random"},
            {"type": 2, "style": 4, "label": "🌶️ Chaos", "custom_id": "a0:lens:chaos"},
            {"type": 2, "style": 2, "emoji": {"name": "🔄"}, "custom_id": "a0:refresh"},
        ],
    }

    container = {
        "type": 17, "accent_color": GOLD,
        "components": [
            _txt(f"# 🎞️ The Herald Reel\n**This week:** {len(ms)} matches · {day} · "
                 f"showing **Bloodiest** · page 1 of {pages}"),
            posters,
            _sep(),
            *rows,
            _sep(large=True),
            lens,
            filt,
            nav,
        ],
    }
    return {
        "components": [
            _txt("## A0 — The Herald Reel\n-# A poster-wall movie-catalog for the worst "
                 "Dota ever played — browse Herald disasters like Netflix tiles. One "
                 "public message, edited in place forever."),
            container,
        ],
        "files": [],
    }


# ---------- message 2: match poster (detail) ----------

def _match_poster(m):
    star, worst = _star(m), _tragic(m)
    when = _dt(m).strftime("%a %b %-d, %-I:%M %p")
    death_rate = round(m["duration"] / 60 / worst["d"], 1)

    board = {
        "type": 12,
        "items": [
            {
                "media": {"url": render.hero_img(p["hero_id"])},
                "description": f"{render.hero_name(p['hero_id'])} {p['k']}/{p['d']}/{p['a']} — "
                               f"{'Radiant' if p['is_radiant'] else 'Dire'}",
            }
            for p in m["players"]
        ],
    }

    star_items = "".join(_ie(i) for i in star["items"])
    star_sec = {
        "type": 9,
        "components": [_txt(
            f"### ⭐ {render.hero_name(star['hero_id'])} — {star['k']}/{star['d']}/{star['a']}\n"
            f"{star['gpm']} GPM · {star['networth'] / 1000:.1f}k networth · {_pos(star)}\n"
            f"{star_items}")],
        "accessory": {"type": 11, "media": {"url": render.hero_img(star["hero_id"])},
                      "description": render.hero_name(star["hero_id"])},
    }
    worst_sec = {
        "type": 9,
        "components": [_txt(
            f"### 🗑️ {render.hero_name(worst['hero_id'])} — {worst['k']}/{worst['d']}/{worst['a']}\n"
            f"{worst['gpm']} GPM · {worst['networth'] / 1000:.1f}k networth · {_pos(worst)} — "
            f"died every {death_rate} minutes")],
        "accessory": {"type": 11, "media": {"url": render.hero_img(worst["hero_id"])},
                      "description": render.hero_name(worst["hero_id"])},
    }

    player_select = {
        "type": 1,
        "components": [{
            "type": 3, "custom_id": f"a0:player:{m['id']}", "placeholder": "🔍 Inspect a player…",
            "options": [
                {
                    "label": f"{render.hero_name(p['hero_id'])} — {p['k']}/{p['d']}/{p['a']} · {_pos(p)}",
                    "description": f"{p['gpm']} GPM · {'Radiant' if p['is_radiant'] else 'Dire'}",
                    "value": f"{m['id']}:{i}",
                    **({"emoji": _hero_emoji_obj(p["hero_id"])} if _hero_emoji_obj(p["hero_id"]) else {}),
                }
                for i, p in enumerate(m["players"])
            ],
        }],
    }

    buttons = {
        "type": 1,
        "components": [
            {"type": 2, "style": 2, "label": "◀ Back to reel", "custom_id": "a0:back"},
            {"type": 2, "style": 1, "label": "📈 More graphs", "custom_id": f"a0:graphs:{m['id']}"},
            {"type": 2, "style": 3, "label": "🎲 Another one", "custom_id": "a0:random2"},
            {"type": 2, "style": 5, "label": "Open on OpenDota",
             "url": f"https://www.opendota.com/matches/{m['id']}"},
        ],
    }

    gold_png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")
    container = {
        "type": 17,
        "accent_color": RADIANT_GREEN if m["radiant_win"] else 0xC23C2A,
        "components": [
            _txt(f"# ⚔️ {m['kills']}-kill slugfest\n"
                 f"**{render.dur(m['duration'])} · "
                 f"{'Radiant' if m['radiant_win'] else 'Dire'} victory · {when}** · "
                 f"{m['kills_r']}–{m['kills_d']} · Herald ☆"),
            board,
            _sep(),
            star_sec,
            worst_sec,
            _sep(large=True),
            {"type": 12, "items": [{"media": {"url": f"attachment://gold_{m['id']}.png"},
                                    "description": "Net worth lead over time"}]},
            player_select,
            buttons,
        ],
    }
    return {
        "components": [
            _txt("-# ⤷ pressing **Open** edits the same public message into this Poster view"),
            container,
        ],
        "files": [(f"gold_{m['id']}.png", gold_png)],
    }


# ---------- message 3: graphs view (specialty) ----------

def _graphs_view(m):
    lead = -m["min_lead"]  # Dire's biggest lead (they lost)
    worst_gpm = min(p["gpm"] for p in m["players"] if p["is_radiant"])
    gold_png = charts.networth_lead_png(
        m["leads"], f"The {lead / 1000:.0f}k comeback — Net Worth Lead")
    spark_png = charts.sparkline_png(m["leads"])
    container = {
        "type": 17,
        "accent_color": RADIANT_GREEN if m["radiant_win"] else 0xC23C2A,
        "components": [
            _txt(f"# 📈 {m['kills']} kills in {render.dur(m['duration'])} — the graphs\n"
                 f"Dire led by **{lead / 1000:.1f}k gold**. Dire lost. "
                 f"Every Radiant player finished over {worst_gpm} GPM."),
            {"type": 12, "items": [
                {"media": {"url": f"attachment://gold_{m['id']}.png"},
                 "description": "Net worth lead, full detail"},
                {"media": {"url": f"attachment://spark_{m['id']}.png"},
                 "description": "Same lead as a sparkline"},
            ]},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Back to match", "custom_id": f"a0:open2:{m['id']}"},
                {"type": 2, "style": 2, "label": "◀◀ Back to reel", "custom_id": "a0:back2"},
            ]},
        ],
    }
    return {
        "components": [
            _txt("-# ⤷ **📈 More graphs** swaps the poster for a pure chart wall — "
                 "the pictures ARE the page (shown for the speedrun throw)"),
            container,
        ],
        "files": [(f"gold_{m['id']}.png", gold_png), (f"spark_{m['id']}.png", spark_png)],
    }


# ---------- message 4: player card (ephemeral drilldown) ----------

def _player_card(m, p):
    name = render.hero_name(p["hero_id"])
    won = p["is_radiant"] == m["radiant_win"]
    side = "Radiant" if p["is_radiant"] else "Dire"

    # shopping spree: first purchase of each big-ticket item, chronological
    seen, spree = set(), []
    for buy in p["purchases"]:
        iid = buy["itemId"]
        it = render._item_by_id.get(iid)
        if not it or iid in seen or (it.get("cost") or 0) < 2000 or buy["time"] < 0:
            continue
        seen.add(iid)
        t = buy["time"]
        spree.append(f"`{t // 60:02d}:{t % 60:02d}` {_ie(iid)} {render.item_name(iid)}")
    spree_txt = ("**The shopping spree**\n" + "\n".join(spree[:6])
                 + f"\n\n**Final six:** {''.join(_ie(i) for i in p['items'])}")

    nw_png = charts.networth_lead_png(p["networth_per_min"], f"{name} — net worth by minute")
    container = {
        "type": 17,
        "accent_color": RADIANT_GREEN if p["is_radiant"] else 0xC23C2A,
        "components": [
            {"type": 9,
             "components": [_txt(
                 f"# {name} — {p['k']}/{p['d']}/{p['a']}\n"
                 f"**{p['gpm']} GPM · {p['networth'] / 1000:.1f}k networth · {_pos(p)} · "
                 f"{side} ({'won' if won else 'lost'})**")],
             "accessory": {"type": 11, "media": {"url": render.hero_img(p["hero_id"])},
                           "description": name}},
            _sep(),
            _txt(spree_txt),
            {"type": 12, "items": [{"media": {"url": f"attachment://nw_{m['id']}_p.png"},
                                    "description": f"{name} net worth per minute"}]},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "emoji": {"name": "◀"}, "custom_id": f"a0:pprev:{m['id']}"},
                {"type": 2, "style": 2, "emoji": {"name": "▶"}, "custom_id": f"a0:pnext:{m['id']}"},
                {"type": 2, "style": 2, "label": "All 10 builds", "custom_id": f"a0:allitems:{m['id']}"},
            ]},
        ],
    }
    return {
        "components": [
            _txt("-# ⤷ picking a player opens this **private** card (ephemeral) — "
                 "the public poster stays put; ◀ ▶ cycles all ten"),
            container,
        ],
        "files": [(f"nw_{m['id']}_p.png", nw_png)],
    }


# ---------- message 5: hero hunt picker (ephemeral) ----------

def _hero_hunt(ms):
    picks = {}
    for m in ms:
        for p in m["players"]:
            picks[p["hero_id"]] = picks.get(p["hero_id"], 0) + 1
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:25]

    sheet = {
        "type": 12,
        "items": [
            {"media": {"url": render.hero_img(hid)},
             "description": f"{render.hero_name(hid)} — {n} matches"}
            for hid, n in top[:8]
        ],
    }
    select = {
        "type": 1,
        "components": [{
            "type": 3, "custom_id": "a0:hh:pick", "placeholder": "Pick a hero…",
            "options": [
                {
                    "label": render.hero_name(hid),
                    "description": f"{n} matches this week",
                    "value": str(hid),
                    **({"emoji": _hero_emoji_obj(hid)} if _hero_emoji_obj(hid) else {}),
                }
                for hid, n in top
            ],
        }],
    }
    container = {
        "type": 17, "accent_color": GOLD,
        "components": [
            _txt(f"# 🔍 Hero hunt\nPage 1 · the 25 most-picked this week (of {len(picks)} seen)"),
            sheet,
            select,
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "More heroes ▶", "custom_id": "a0:hh:page2"},
                {"type": 2, "style": 2, "label": "A–Z instead", "custom_id": "a0:hh:az"},
            ]},
        ],
    }
    return {
        "components": [
            _txt("-# ⤷ **Hero hunt…** in the sort select opens this private picker; "
                 "picking a hero re-renders the public wall filtered to them"),
            container,
        ],
        "files": [],
    }


# ---------- build ----------

def build() -> list[dict]:
    ms = render.load_matches()
    by_id = {m["id"]: m for m in ms}
    slugfest = by_id[8888293313]     # 118 kills, 46:56
    speedrun = by_id[8888322003]     # 91 kills / 26:16, 27k comeback
    sniper_game = by_id[8888295980]  # Sniper 33/3/8, PA 19 deaths
    sniper = next(p for p in sniper_game["players"]
                  if render.hero_name(p["hero_id"]) == "Sniper")
    return [
        _gallery_wall(ms),
        _match_poster(slugfest),
        _graphs_view(speedrun),
        _player_card(sniper_game, sniper),
        _hero_hunt(ms),
    ]


if __name__ == "__main__":
    msgs = build()
    counts, chars, nfiles = [], [], 0
    for i, msg in enumerate(msgs):
        n, ch = render.check(msg["components"], f"a0 msg{i + 1}")
        counts.append(n)
        chars.append(ch)
        nfiles += len(msg["files"])
        # every attachment:// reference must have a matching file tuple
        names = {name for name, _ in msg["files"]}

        def _atts(cs):
            for c in cs:
                for it in c.get("items", []):
                    yield it.get("media", {}).get("url", "")
                acc = c.get("accessory")
                if acc:
                    yield (acc.get("media") or {}).get("url", "")
                yield from _atts(c.get("components", []))

        for url in _atts(msg["components"]):
            if url.startswith("attachment://"):
                assert url.removeprefix("attachment://") in names, \
                    f"msg{i + 1}: {url} has no file tuple"
        for name, data in msg["files"]:
            assert data[:8] == b"\x89PNG\r\n\x1a\n", f"msg{i + 1}: {name} not a PNG"
    print(f"OK a0: {len(msgs)} messages, components={counts}, chars={chars}, files={nfiles}")
