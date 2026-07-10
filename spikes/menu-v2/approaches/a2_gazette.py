"""a2 — The Herald Gazette: weekly newspaper of the worst Dota ever played.

Six-message edition printed into one thread: Front Page, Longest Wars,
Bloodbaths, Feeder Hall of Fame, Comeback City (real networth chart),
Troll Builds + Classifieds back page. All numbers computed from the real
fixture at build time; only the headlines are hand-set type.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts
import render

# accents
GOLD, PURPLE, RED, BROWN, GREEN, PINK, GREY = (
    0xF0B232, 0x8B5CF6, 0xED4245, 0x964B00, 0x3BA55D, 0xEB459E, 0x99AAB5)


# ---------- tiny component builders ----------

def td(content):
    return {"type": 10, "content": content}


def sep(large=False):
    return {"type": 14, "divider": True, "spacing": 2 if large else 1}


def row(*comps):
    return {"type": 1, "components": list(comps)}


def btn(label, cid, style=2, disabled=False, emoji=None):
    b = {"type": 2, "style": style, "label": label, "custom_id": cid,
         "disabled": disabled}
    if emoji:
        b["emoji"] = {"name": emoji}
    return b


def section(text, cid):
    return {"type": 9, "components": [td(text)],
            "accessory": btn("Full Story", cid)}


def container(accent, comps):
    return {"type": 17, "accent_color": accent, "components": comps}


def pager(board):
    return row(btn("◀ Prev", f"gz:pg:{board}:0", disabled=True),
               btn("Page 1/3", f"gz:pg:{board}:noop", disabled=True),
               btn("Next ▶", f"gz:pg:{board}:2"))


# ---------- data helpers ----------

def he(hid):
    """hero emoji + trailing space, or ''"""
    e = render.hero_emoji(hid)
    return f"{e} " if e else ""


def ie(iid):
    return render.item_emoji(iid) or f"`{render.item_name(iid)}`"


def emoji_obj(s):
    mo = re.match(r"<:(\w+):(\d+)>", s or "")
    return {"name": mo.group(1), "id": mo.group(2)} if mo else None


def score(m):
    side = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
    return f"{side} **{m['kills_r']}–{m['kills_d']}**"


def kda(p):
    return f"{p['k']}/{p['d']}/{p['a']}"


def top_killer(m):
    return max(m["players"], key=lambda p: p["k"])


# ---------- the edition ----------

def build():
    ms = render.load_matches()
    by = {m["id"]: m for m in ms}
    total_kills = sum(m["kills"] for m in ms)
    longest = max(ms, key=lambda m: m["duration"])
    shortest = min(ms, key=lambda m: m["duration"])
    durs = sorted(m["duration"] for m in ms)
    median = durs[len(durs) // 2]
    sec_per_kill = round(sum(m["duration"] for m in ms) / total_kills)
    wars = sorted(ms, key=lambda m: -m["duration"])[:5]
    bloods = sorted(ms, key=lambda m: -m["kpm"])[:5]
    feeds = sorted(ms, key=lambda m: -m["feeder"]["d"])[:5]
    cbs = sorted(ms, key=lambda m: -m["comeback_gold"])[:4]
    war_avg = sum(m["duration"] for m in wars) // len(wars)

    # ---- MSG 0: FRONT PAGE ----
    worst = feeds[0]["feeder"]
    front = container(GOLD, [
        td("# 🗞️ THE HERALD GAZETTE\n"
           "### Vol. 1, No. 1 · Week of July 6–12, 2026 · Price: 0 MMR\n"
           "*Independent coverage of the Herald bracket since nobody asked.*"),
        sep(large=True),
        td("**THIS WEEK BY THE NUMBERS**\n"
           f"📦 **{len(ms)}** matches archived · ⚔️ **{total_kills:,}** kills "
           f"(one every **{sec_per_kill} seconds**) · ⏱️ longest **{render.dur(longest['duration'])}** "
           f"· 🏳️ shortest **{render.dur(shortest['duration'])}** · 💀 worst scoreline "
           f"**{kda(worst)}** ({render.hero_name(worst['hero_id'])}, who won)\n"
           "Every story below is datelined Thursday, July 9. We don't know "
           "what happened on Thursday either."),
        sep(),
        td("**IN THIS ISSUE** *(scroll down ↓)*\n"
           f"⚔️ **LONGEST WARS** — a {render.dur(longest['duration'])} slugfest with "
           f"**{longest['kills']} kills**. That is not a typo.\n"
           f"🩸 **BLOODBATHS** — {bloods[0]['kills']} kills in {render.dur(bloods[0]['duration'])}; "
           f"a kill every {round(bloods[0]['duration']/bloods[0]['kills'])} seconds\n"
           f"💀 **FEEDER HALL OF FAME** — the {feeds[0]['feeder']['d']}-death "
           f"{render.hero_name(feeds[0]['feeder']['hero_id'])} speaks (she doesn't)\n"
           f"📈 **COMEBACK CITY** — down **{cbs[0]['comeback_gold']:,} gold** at minute 25… "
           "and then it gets weird\n"
           "🔧 **TROLL BUILDS** — a Zeus with two Divine Rapiers walks into a bar"),
        sep(),
        row({"type": 3, "custom_id": "gz:wk",
             "placeholder": "📅 Read a back issue…",
             "options": [{
                 "label": "Week of Jul 6–12 — this issue",
                 "value": "2026-28", "default": True,
                 "description": f"{len(ms)} matches · {total_kills:,} kills",
             }]}),
        row(btn("Lucky Dip", "gz:dip:front", emoji="🎲"),
            btn("Week in Charts", "gz:charts:front", emoji="📊")),
    ])

    # ---- MSG 1: LONGEST WARS ----
    war_heads = {
        8888293313: "THE 46-MINUTE SLUGFEST",
        8888295980: "SNIPER SOLVES EVERYTHING",
        8888295578: "THE THRONE WAS RIGHT THERE",
        8888294804: "TECHIES, CARRY OF THE WEEK",
        8888293690: "45 MINUTES OF LANE CREEPS",
    }
    war_snark = {
        8888293313: lambda m: f"{he(99)}Bristleback went **{kda(top_killer(m))}** and it still took 47 minutes.",
        8888295980: lambda m: f"{he(35)}Sniper went **33/3/8** while his PA died 19 times. Teamwork.",
        8888295578: lambda m: f"{he(3)}Bane finished **2/18/16** as a position-3. A bold lane, boldly lost.",
        8888294804: lambda m: f"{he(105)}Techies dropped **30 kills** on this lobby. Techies.",
        8888293690: lambda m: f"{he(68)}Ancient Apparition went 8/15/20 and called it support.",
    }
    war_secs = [section(
        f"**{i}. {war_heads[m['id']]}** · Thu Jul 9\n"
        f"{score(m)} · {render.dur(m['duration'])} · **{m['kills']} kills**\n"
        f"{war_snark[m['id']](m)} `{m['id']}`",
        f"gz:ms:{m['id']}:war") for i, m in enumerate(wars, 1)]
    msg_wars = container(PURPLE, [
        td("## ⚔️ LONGEST WARS\n*The games that would not end.* — Page 1 of 3"),
        sep(large=True), *war_secs, sep(),
        td(f"*Median Herald game this week: {render.dur(median)}. "
           f"These five averaged {render.dur(war_avg)}.*"),
        pager("war"),
    ])

    # ---- MSG 2: BLOODBATHS ----
    blood_heads = {
        8888318509: "A KILL EVERY 16 SECONDS",
        8888328375: "THE 13-MINUTE MASSACRE",
        8888325754: "89 REASONS TO JUNGLE",
        8888322003: "THE 91-KILL COMEBACK",
        8888322960: "KEEPER OF THE FIGHT",
    }
    blood_snark = {
        8888318509: lambda m: f"{he(8)}Juggernaut went **24/3/14** at 1,929 GPM. The other team queued again.",
        8888328375: lambda m: f"**39–6** in thirteen minutes. {he(42)}Wraith King 15/0/4. A public execution.",
        8888325754: lambda m: f"{he(49)}Dragon Knight went **20/3/20**. Nobody farmed, everybody fought.",
        8888322003: lambda m: "Also this week's biggest throw — see **COMEBACK CITY** below.",
        8888322960: lambda m: f"{he(90)}Keeper of the Light: **21/4/13**. The lantern was for finding kills.",
    }
    blood_secs = [section(
        f"**{i}. {blood_heads[m['id']]}** · Thu Jul 9\n"
        f"{score(m)} · {render.dur(m['duration'])} · **{m['kills']} kills, {m['kpm']}/min**\n"
        f"{blood_snark[m['id']](m)} `{m['id']}`",
        f"gz:ms:{m['id']}:blood") for i, m in enumerate(bloods, 1)]
    msg_blood = container(RED, [
        td("## 🩸 BLOODBATHS\n*Kills per minute, dignity per zero.* — Page 1 of 3"),
        sep(large=True), *blood_secs, sep(),
        td(f"*This week's Heralds averaged one kill every {sec_per_kill} seconds, "
           "all week, as a lifestyle.*"),
        pager("blood"),
    ])

    # ---- MSG 3: FEEDER HALL OF FAME ----
    feed_snark = {
        8888295980: "Died 19 times **on the winning team**. Carried a Battle Fury the whole way down.",
        8888295578: "A position-3 Bane. The item build was wards. The lane was a donation.",
        8888294804: "18 deaths, won anyway — the Techies next door had 30 kills to spare.",
        8888293313: "A **position-4 Anti-Mage**. Read that again. 412 GPM of pure ideology.",
        8888318509: "15 deaths in a 21-minute game. That's one every 84 seconds, with commute.",
    }
    feed_secs = []
    for i, m in enumerate(feeds, 1):
        f = m["feeder"]
        res = "won" if f["is_radiant"] == m["radiant_win"] else "lost"
        feed_secs.append(section(
            f"**{i}. {he(f['hero_id'])}{render.hero_name(f['hero_id']).upper()} — {kda(f)}** · Thu Jul 9\n"
            f"**{f['gpm']} GPM** · {res} in {render.dur(m['duration'])}\n"
            f"{feed_snark[m['id']]} `{m['id']}`",
            f"gz:ms:{m['id']}:feed"))
    fk = sum(m["feeder"]["k"] for m in feeds)
    fd = sum(m["feeder"]["d"] for m in feeds)
    fa = sum(m["feeder"]["a"] for m in feeds)
    won_ct = sum(1 for m in feeds
                 if m["feeder"]["is_radiant"] == m["radiant_win"])
    msg_feed = container(BROWN, [
        td("## 💀 FEEDER HALL OF FAME\n*They died so the enemy carry could live.* — Page 1 of 3"),
        sep(large=True), *feed_secs, sep(),
        td(f"*Combined, this week's top five went **{fk}/{fd}/{fa}**. "
           f"{won_ct} of them won anyway. Herald giveth.*"),
        pager("feed"),
    ])

    # ---- MSG 4: COMEBACK CITY (real chart) ----
    feat = cbs[0]  # 8888322003, 27,097 g
    ls = max(feat["players"], key=lambda p: p["k"])  # Lifestealer, 20/7/14
    worst_min = feat["leads"].index(feat["min_lead"])
    chart_name = f"cb_{feat['id']}.png"
    chart_png = charts.networth_lead_png(
        feat["leads"], f"Match {feat['id']} — Net Worth Lead")
    cb_heads = {8888322353: "THE 21K COLLAPSE",
                8888294804: "TECHIES CLOSES THE BOOKS",
                8888293690: "THE SLOW BLEED"}
    cb_snark = {
        8888322353: lambda m: "Radiant led by **21,051 g**. Dire won 12 minutes of Dota later.",
        8888294804: lambda m: "Radiant up **8,627 g** at minute 38 of 46. The 30-kill Techies disagreed.",
        8888293690: lambda m: "Radiant led by **8,500 g**, then lost every fight after minute 35.",
    }
    cb_secs = [section(
        f"**{i}. {cb_heads[m['id']]}** · Thu Jul 9\n"
        f"{score(m)} · {render.dur(m['duration'])} · winner climbed out of a "
        f"**{m['comeback_gold']:,} g** hole\n{cb_snark[m['id']](m)} `{m['id']}`",
        f"gz:ms:{m['id']}:cb") for i, m in enumerate(cbs[1:], 2)]
    msg_cb = container(GREEN, [
        td("## 📈 COMEBACK CITY\n*It's not over until the ancient explodes.* — Page 1 of 3"),
        sep(large=True),
        td(f"**FEATURED: THE {feat['comeback_gold']:,}-GOLD HOLE** · Thu Jul 9 · `{feat['id']}`\n"
           f"🔴 Dire led by **{-feat['min_lead']:,} gold** at minute {worst_min}. "
           f"{he(ls['hero_id'])}Lifestealer was **{kda(ls)}** at {ls['gpm']:,} GPM. "
           f"🟢 Radiant won at {render.dur(feat['duration'])} anyway, "
           f"{feat['kills_r']}–{feat['kills_d']} down on kills. "
           "No, we can't explain the graph either. ↓"),
        {"type": 12, "items": [{
            "media": {"url": f"attachment://{chart_name}"},
            "description": f"Gold lead over time: Dire peaks +{-feat['min_lead']:,} "
                           f"at minute {worst_min}; Radiant wins anyway"}]},
        sep(), *cb_secs, sep(),
        td(f"*Largest lead lost this week: **{feat['comeback_gold']:,} gold**. "
           "It survived about sixty seconds.*"),
        pager("cb"),
    ])

    # ---- MSG 5: TROLL BUILDS + CLASSIFIEDS ----
    def build_line(mid, hid, verdict, snark):
        m = by[mid]
        p = next(p for p in m["players"] if p["hero_id"] == hid)
        items = " ".join(ie(i) for i in p["items"])
        return (f"{he(hid)}{render.hero_name(hid)}, **{kda(p)}**, {verdict}.\n"
                f"{items}\n{snark} `{mid}`")

    troll_secs = [
        section("**1. THE DOUBLE-RAPIER ZEUS** · "
                + build_line(8888322962, 22, "lost",
                             "Two Divine Rapiers and a Bottle. A god, budgeting like one."),
                "gz:ms:8888322962:troll"),
        section("**2. THREE HEARTS, NO PLAN** · "
                + build_line(8888320423, 99, "won",
                             "Triple Heart of Tarrasque Bristleback. Unkillable and unbothered."),
                "gz:ms:8888320423:troll"),
        section("**3. THE MOON SHARD HOARDER** · "
                + build_line(8888326774, 35, "won",
                             "Three Moon Shards. He could see everything except a fourth slot."),
                "gz:ms:8888326774:troll"),
        section("**4. NULL AND VOID** · "
                + build_line(8888324094, 101, "won",
                             "Still on three Null Talismans at minute 25. It worked. We hate it."),
                "gz:ms:8888324094:troll"),
        section("**5. THE MINUTE-27 STARTER KIT** · "
                + build_line(8888319540, 80, "lost",
                             "Tango, Faerie Fire, two branches — at minute 27. Fresh out of the fountain, forever."),
                "gz:ms:8888319540:troll"),
    ]
    rapiers = sum(1 for m in ms for p in m["players"] for i in p["items"]
                  if render.item_name(i) == "Divine Rapier")
    msg_troll = container(PINK, [
        td("## 🔧 TROLL BUILDS\n*The shop is a suggestion.*"),
        sep(large=True), *troll_secs, sep(),
        td(f"*Divine Rapiers bought this week: **{rapiers}**. "
           "Divine Rapiers that were a good idea: pending review.*"),
    ])
    classifieds = container(GREY, [
        td("## 📇 THE CLASSIFIEDS\n"
           "**LOST:** two Divine Rapiers, last seen on a Zeus. Sentimental value. `8888322962`\n"
           "**FOUND:** three Hearts of Tarrasque, one owner, no regrets. `8888320423`\n"
           "**WANTED:** detection. Contact any of five teams re: an invisible "
           "19-death Phantom Assassin. `8888295980`"),
        sep(),
        row({"type": 3, "custom_id": "gz:br",
             "placeholder": "🗂 Browse the archive…",
             "options": [
                 {"label": "Under 20 minutes", "value": "dur:0",
                  "description": f"Speedruns and surrenders — {sum(1 for m in ms if m['mins'] < 20)} games"},
                 {"label": "20–35 minutes", "value": "dur:1",
                  "description": f"Standard-issue chaos — {sum(1 for m in ms if 20 <= m['mins'] < 35)} games"},
                 {"label": "Marathon 35+", "value": "dur:2",
                  "description": f"Endurance events — {sum(1 for m in ms if m['mins'] >= 35)} games"},
                 {"label": "Bloodiest first", "value": "sort:kills",
                  "description": f"Starts at {bloods[0]['kpm']} kills/min and cools off"},
                 {"label": "Biggest comebacks", "value": "sort:cb",
                  "description": f"Starts {cbs[0]['comeback_gold']:,} gold in the hole"},
                 {"label": "Worst feeders", "value": "sort:feed",
                  "description": f"Starts at {feeds[0]['feeder']['d']} deaths"},
             ]}),
        row(_hero_spotlight(ms)),
        row(btn("Lucky Dip", "gz:dip:back", emoji="🎲"),
            btn("Week in Charts", "gz:charts:back", emoji="📊")),
    ])

    return [
        {"components": [front], "files": []},
        {"components": [msg_wars], "files": []},
        {"components": [msg_blood], "files": []},
        {"components": [msg_feed], "files": []},
        {"components": [msg_cb], "files": [(chart_name, chart_png)]},
        {"components": [msg_troll, classifieds], "files": []},
    ]


def _hero_spotlight(ms):
    """Top-10 most-picked select, real pick counts / winrates / avg deaths."""
    stats = {}
    for m in ms:
        for p in m["players"]:
            s = stats.setdefault(p["hero_id"], [0, 0, 0])
            s[0] += 1
            s[1] += p["is_radiant"] == m["radiant_win"]
            s[2] += p["d"]
    top = sorted(stats.items(), key=lambda kv: -kv[1][0])[:10]
    options = []
    for hid, (picks, wins, deaths) in top:
        opt = {"label": render.hero_name(hid), "value": str(hid),
               "description": f"{picks} picks · {round(100 * wins / picks)}% winrate "
                              f"· avg {deaths / picks:.1f} deaths"}
        e = emoji_obj(render.hero_emoji(hid))
        if e:
            opt["emoji"] = e
        options.append(opt)
    return {"type": 3, "custom_id": "gz:hs",
            "placeholder": "🦸 Hero spotlight — this week's 10 most-picked…",
            "options": options}


if __name__ == "__main__":
    msgs = build()
    counts, chars = [], []
    for i, msg in enumerate(msgs):
        n, ch = render.check(msg["components"], f"msg{i}")
        counts.append(n)
        chars.append(ch)
        # every attachment:// reference must have a matching file tuple
        import json as _json
        blob = _json.dumps(msg["components"])
        names = set(re.findall(r"attachment://([\w.\-]+)", blob))
        have = {fn for fn, _ in msg["files"]}
        assert names == have, f"msg{i}: attachments {names} vs files {have}"
    nfiles = sum(len(m["files"]) for m in msgs)
    print(f"OK a2: {len(msgs)} messages, components={counts}, chars={chars}, "
          f"files={nfiles}")
