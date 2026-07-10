"""a5 — THE HERALD MACHINE: a slot machine for terrible Dota.

Three key screens, all real data:
  M0 lobby (idle machine), M2 reveal (lever pull -> 118-kill jackpot, chart),
  M2 themed reveal (Feeder roulette -> the 19-death PA game, chart).
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

GOLD = 0xF1C40F
JACKPOT = 0xE74C3C

REVEAL = 8888293313   # 118 kills / 46:56 lever pull
FEEDER = 8888295980   # PA 7/19/9 themed pull

RANK_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}


def _td(text):
    return {"type": 10, "content": text}


def _sep(spacing=1):
    return {"type": 14, "divider": True, "spacing": spacing}


def _btn(style, label, cid=None, url=None, emoji=None, disabled=False):
    b = {"type": 2, "style": style, "label": label}
    if url:
        b["url"] = url
    else:
        b["custom_id"] = cid
    if emoji:
        b["emoji"] = {"name": emoji}
    if disabled:
        b["disabled"] = True
    return b


def _he(hid):
    return render.hero_emoji(hid) or "•"


def _day(m):
    return datetime.datetime.fromtimestamp(m["start"], datetime.UTC).strftime("%A")


def _rank(m):
    return f"Herald {RANK_ROMAN.get(m['rank'] % 10, '?')}"


def _by_pos(m, side_radiant, pos):
    for p in m["players"]:
        if p["is_radiant"] == side_radiant and p["position"] == f"POSITION_{pos}":
            return p
    return None


# ---------- M0: the lobby ----------

def _lobby(ms):
    total_kills = sum(m["kills"] for m in ms)
    n = len(ms)

    def stock(k):
        return f"{k} in the rack" if k else "sold out this week"

    inv = {
        "feeder": sum(1 for m in ms if m["feeder"]["d"] >= 15),
        "bloodbath": sum(1 for m in ms if m["kills"] >= 100),
        "forever": sum(1 for m in ms if m["mins"] >= 45),
        "speedrun": sum(1 for m in ms if m["mins"] <= 20),
        "throw": sum(1 for m in ms if m["comeback_gold"] >= 10000),
        "kingpin": sum(1 for m in ms if any(p["gpm"] >= 900 for p in m["players"])),
        "pacifist": sum(1 for m in ms if any(p["k"] <= 2 and p["d"] >= 12 for p in m["players"])),
        "towers": sum(1 for m in ms if len(m["tower_deaths"]) >= 20),
    }

    def opt(emoji, label, desc, value):
        return {"label": label, "value": value, "description": desc[:100],
                "emoji": {"name": emoji}}

    menu = {
        "type": 3, "custom_id": "hm:pull_themed",
        "placeholder": "…or order off the menu",
        "options": [
            opt("💀", "Feed me a feeder", f"Somebody died 15+ times · {stock(inv['feeder'])}", "feeder"),
            opt("🩸", "Total bloodbath", f"100+ combined kills · {stock(inv['bloodbath'])}", "bloodbath"),
            opt("⏳", "The forever war", f"45 minutes and still going · {stock(inv['forever'])}", "forever"),
            opt("⚡", "20-minute speedrun", f"Somebody got flattened fast · {stock(inv['speedrun'])}", "speedrun"),
            opt("🃏", "Troll build roulette", "Wrong items, wrong hero, no regrets", "trollbuild"),
            opt("📉", "The throw", f"Up 10k+ net worth. Lost anyway. · {stock(inv['throw'])}", "throw"),
            opt("🪙", "Rags to riches", f"Down 10k+. Won anyway. · {stock(inv['throw'])}", "comeback"),
            opt("👑", "Herald kingpin", f"A 900+ GPM performance… in Herald · {stock(inv['kingpin'])}", "kingpin"),
            opt("🕊️", "The pacifist", f"0–2 kills, 12+ deaths · {stock(inv['pacifist'])}", "pacifist"),
            opt("🏰", "Tower massacre", f"20+ towers died · {stock(inv['towers'])}", "towers"),
            opt("🎪", "Rich support", "A pos 5 who out-farmed their cores", "richsupport"),
            opt("🎲", "Dealer's choice", "Same as the lever, for select enjoyers", "random"),
        ],
    }

    components = [
        _td("## A5 · THE HERALD MACHINE\n-# A slot machine for terrible Dota. "
            "Pull the lever, get a disaster, keep the good ones."),
        {
            "type": 17, "accent_color": GOLD,
            "components": [
                _td(f"# 🎰 THE HERALD MACHINE\n**{n} matches** collected this week. "
                    f"**{total_kills:,} kills.** All of them Herald. None of them good.\n"
                    "Pull the lever."),
                _sep(2),
                {"type": 1, "components": [_btn(1, "PULL THE LEVER", "hm:pull", emoji="🎰")]},
                {"type": 1, "components": [menu]},
                _sep(),
                {"type": 1, "components": [_btn(2, "Browse the rack", "hm:browse", emoji="📇")]},
                _td("-# rack restocks nightly · the icons are real and so, "
                    "unfortunately, are the players"),
            ],
        },
    ]
    return {"components": components, "files": []}


# ---------- M2: the reveal (lever pull, 118 kills) ----------

def _reveal_bloodbath(m):
    bb = _by_pos(m, True, 1)      # Bristleback 21/7/23
    am = _by_pos(m, True, 4)      # Anti-Mage 6/17/9, MoM + Battle Fury
    jak = _by_pos(m, False, 5)    # Jakiro 2/17/30
    chart_name = f"nw_{m['id']}.png"
    png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")

    hook = (
        f"{_he(bb['hero_id'])} **Bristleback — the pos 1 — went "
        f"{bb['k']}/{bb['d']}/{bb['a']}** and never once considered retreating.\n"
        f"Radiant ran a **pos 4 Anti-Mage** {_he(am['hero_id'])} with Mask of Madness "
        f"into Battle Fury. He went **{am['k']}/{am['d']}/{am['a']}**. On the winning team.\n"
        f"{_he(jak['hero_id'])} Dire's **Jakiro finished {jak['k']}/{jak['d']}/{jak['a']}** — "
        f"thirty assists in a {m['max_lead'] // 1000}k-gold loss."
    )
    verdict = (
        f"**The machine's verdict:** 🔥🔥🔥🔥🔥 — {m['kpm']} kills a minute for "
        f"{m['mins']} straight minutes. Nobody farmed, everybody fought. "
        "Certified Herald cinema.\n"
        f"-# match {m['id']} · {_rank(m)} · lever pull"
    )
    components = [{
        "type": 17, "accent_color": JACKPOT,
        "components": [
            _td(f"# 🎰 🩸 🩸 🩸 — JACKPOT\n### {_day(m)} · {render.dur(m['duration'])} · "
                f"**{m['kills']} kills** ({m['kills_r']}–{m['kills_d']}) · Radiant won"),
            _td(hook),
            _sep(),
            {"type": 12, "items": [{
                "media": {"url": f"attachment://{chart_name}"},
                "description": f"Radiant net worth lead, peaked at {m['max_lead'] // 100 / 10}k",
            }]},
            _td(verdict),
            _sep(),
            {"type": 1, "components": [
                _btn(1, "PULL AGAIN", "hm:reroll", emoji="🎰"),
                _btn(2, "Open it up", "hm:teardown", emoji="🔬"),
                _btn(3, "Keep", "hm:keep", emoji="📌"),
                _btn(2, "Menu", "hm:home", emoji="↩"),
                _btn(5, "OpenDota", url=f"https://www.opendota.com/matches/{m['id']}"),
            ]},
        ],
    }]
    return {"components": components, "files": [(chart_name, png)]}


# ---------- M2 themed: Feeder roulette (PA, 19 deaths) ----------

def _reveal_feeder(m):
    pa = _by_pos(m, True, 1)      # Phantom Assassin 7/19/9
    sn = _by_pos(m, True, 2)      # Sniper 33/3/8, 968 gpm
    jug = _by_pos(m, False, 5)    # pos 5 Juggernaut, Battle Fury + Blink
    chart_name = f"nw_{m['id']}.png"
    png = charts.networth_lead_png(m["leads"], f"Match {m['id']} — Net Worth Lead")

    hook = (
        f"{_he(pa['hero_id'])} **Phantom Assassin — the pos 1 — went "
        f"{pa['k']}/{pa['d']}/{pa['a']}.** Nineteen deaths. As the carry. "
        "On the winning team.\n"
        f"Meanwhile {_he(sn['hero_id'])} **Sniper mid went {sn['k']}/{sn['d']}** at "
        f"{sn['gpm']} GPM and dragged four passengers over the line.\n"
        f"The other team ran a **pos 5 Juggernaut** {_he(jug['hero_id'])} "
        "with a Battle Fury and a Blink Dagger. It did not help."
    )
    verdict = (
        f"**The machine's verdict:** 🔥🔥🔥🔥⚪ — Phantom Assassin died {pa['d']} times "
        "and probably typed ez. One man carries, one man buries.\n"
        f"-# match {m['id']} · {_rank(m)} · themed pull: 💀 Feed me a feeder"
    )
    components = [{
        "type": 17, "accent_color": JACKPOT,
        "components": [
            _td(f"# 🎰 💀 💀 💀 — JACKPOT\n### {_day(m)} · {render.dur(m['duration'])} · "
                f"**{m['kills']} kills** ({m['kills_r']}–{m['kills_d']}) · Radiant won"),
            _td(hook),
            _sep(),
            {"type": 12, "items": [{
                "media": {"url": f"attachment://{chart_name}"},
                "description": f"Radiant net worth lead — {len(m['tower_deaths'])} towers fell",
            }]},
            _td(verdict),
            _sep(),
            {"type": 1, "components": [
                _btn(1, "ANOTHER FEEDER", "hm:reroll", emoji="💀"),
                _btn(2, "Open it up", "hm:teardown", emoji="🔬"),
                _btn(3, "Keep", "hm:keep", emoji="📌"),
                _btn(2, "Menu", "hm:home", emoji="↩"),
                _btn(5, "OpenDota", url=f"https://www.opendota.com/matches/{m['id']}"),
            ]},
        ],
    }]
    return {"components": components, "files": [(chart_name, png)]}


def build() -> list[dict]:
    ms = render.load_matches()
    by_id = {m["id"]: m for m in ms}
    return [
        _lobby(ms),
        _reveal_bloodbath(by_id[REVEAL]),
        _reveal_feeder(by_id[FEEDER]),
    ]


if __name__ == "__main__":
    msgs = build()
    counts, chars, nfiles = [], [], 0
    for i, msg in enumerate(msgs):
        n, ch = render.check(msg["components"], f"a5 msg{i}")
        counts.append(n)
        chars.append(ch)
        nfiles += len(msg["files"])
        # every attachment:// reference must have a matching file tuple
        names = {f[0] for f in msg["files"]}
        import json as _json
        refs = {part.split(")")[0].split('"')[0]
                for part in _json.dumps(msg["components"]).split("attachment://")[1:]}
        refs = {r.split('\\"')[0] for r in refs}
        assert refs <= names, f"msg{i}: missing files for {refs - names}"
        for f in msg["files"]:
            assert f[1][:8] == b"\x89PNG\r\n\x1a\n", f"msg{i}: {f[0]} not a PNG"
    print(f"OK a5: {len(msgs)} messages, components={counts}, chars={chars}, files={nfiles}")
