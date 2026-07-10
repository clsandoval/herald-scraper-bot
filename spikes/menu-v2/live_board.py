"""LIVE Match Board — fully clickable spike.

Posts one board message to test #replays and keeps running. Every control
works: sort, multi-filter, group-by + drill, open match, paging, dice,
advanced modal. State per message in memory (restart = post a new board).

Run:  DISCORD_BOT_TOKEN=... .venv/bin/python live_board.py
"""

import io
import logging
import random
from collections import defaultdict

import discord

import charts
import render

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("live_board")

CHANNEL = 1392724352155254876  # Herald Replays (TEST) #replays — never prod
GOLD, GREEN, RED, PURPLE = 0xC8A03C, 0x3BA55D, 0xED4245, 0x9B59B6
PAGE = 7

MS = render.load_matches()
STATE = {}  # message_id -> dict
_thumb_cache = {}


# ---------------- data: sorts / filters / groups ----------------

def _gap(m):
    return abs(m["leads"][-1])


def _max_abs_lead(m):
    return max(m["max_lead"], -m["min_lead"])


SORTS = {
    "spice": ("Most watchable (deaths + kills + throws)",
              lambda m: -(max(0, m["feeder"]["d"] - 10) * 3 + max(0, m["kills"] - 70) // 5
                          + min(m["comeback_gold"], 20000) // 1500 + max(0, m["mins"] - 40))),
    "new": ("Newest", lambda m: -(m["start"] or 0)),
    "kills": ("Most total kills", lambda m: -m["kills"]),
    "kpm": ("Most kills per minute", lambda m: -m["kpm"]),
    "dur": ("Longest game", lambda m: -m["duration"]),
    "short": ("Shortest game", lambda m: m["duration"]),
    "feed": ("Most deaths by one player", lambda m: -m["feeder"]["d"]),
    "throw": ("Biggest gold lead lost by the loser", lambda m: -_throw_size(m)),
    "cb": ("Biggest gold deficit overcome by the winner", lambda m: -m["comeback_gold"]),
    "close": ("Smallest gold lead all game", _max_abs_lead),
    "stomp": ("Biggest final gold gap", lambda m: -_gap(m)),
    "gpm": ("Highest single-player GPM", lambda m: -max(p["gpm"] for p in m["players"])),
}


def _throw_size(m):
    return m["max_lead"] if not m["radiant_win"] else -m["min_lead"]


def _has_rapier(m):
    return any(render.item_key(i) == "rapier" for p in m["players"] for i in p["items"])


FILTERS = {
    "blood": ("100+ total kills", lambda m: m["kills"] >= 100),
    "fight": ("80+ total kills", lambda m: m["kills"] >= 80),
    "war": ("Longer than 40 min", lambda m: m["mins"] >= 40),
    "speed": ("Shorter than 20 min", lambda m: m["mins"] < 20),
    "feed": ("A player died 15+ times", lambda m: m["feeder"]["d"] >= 15),
    "throw": ("Loser had a 5k+ gold lead at some point", lambda m: _throw_size(m) >= 5000),
    "cb": ("Winner was 10k+ gold behind at some point", lambda m: m["comeback_gold"] >= 10000),
    "close": ("Gold lead never passed 5k", lambda m: _max_abs_lead(m) < 5000),
    "stomp": ("One side led start to finish", lambda m: m["max_lead"] <= 2000 or m["min_lead"] >= -2000),
    "rwin": ("Radiant won", lambda m: m["radiant_win"]),
    "dwin": ("Dire won", lambda m: not m["radiant_win"]),
    "rapier": ("Divine Rapier was bought", _has_rapier),
}

_HOUR = lambda m: f"{((m['start'] or 0) // 3600) % 24:02d}:00 UTC"

GROUPS = {
    "hero": ("Hero", None),  # special: per-player expansion
    "star": ("Star player's hero", lambda m: render.hero_name(render.star_of(m)["hero_id"])),
    "role": ("Star player's role", lambda m: (render.star_of(m)["position"] or "?").replace("POSITION_", "pos ")),
    "dur": ("Game length", lambda m: "<20 min" if m["mins"] < 20 else "20-30 min" if m["mins"] < 30 else "30-40 min" if m["mins"] < 40 else "40+ min"),
    "kills": ("Total kills", lambda m: "<60" if m["kills"] < 60 else "60-79" if m["kills"] < 80 else "80-99" if m["kills"] < 100 else "100+"),
    "feed": ("Worst feeder's deaths", lambda m: "<10" if m["feeder"]["d"] < 10 else "10-14" if m["feeder"]["d"] < 15 else "15+"),
    "throw": ("Gold lead lost by the loser", lambda m: "none" if _throw_size(m) < 2000 else "2-5k" if _throw_size(m) < 5000 else "5k+"),
    "cb": ("Gold deficit overcome by winner", lambda m: "none" if m["comeback_gold"] < 2000 else "2-10k" if m["comeback_gold"] < 10000 else "10k+"),
    "gap": ("Final gold gap", lambda m: "<5k" if _gap(m) < 5000 else "5-15k" if _gap(m) < 15000 else "15k+"),
    "side": ("Winning side", lambda m: "Radiant" if m["radiant_win"] else "Dire"),
    "rank": ("Rank", lambda m: f"Herald {max(1, (m['rank'] or 13) % 10)}" if m["rank"] else "Herald ?"),
    "day": ("Day", lambda m: "Thu Jul 9"),
    "hour": ("Hour", _HOUR),
    "item": ("Notable items", lambda m: "Divine Rapier" if _has_rapier(m) else "none"),
    "towers": ("Towers the winner lost", lambda m: str(sum(1 for t in m["tower_deaths"] if t["isRadiant"] == m["radiant_win"]))),
}


def default_state():
    return {"mode": "list", "sort": "spice", "filters": [], "group": None,
            "bucket": None, "page": 0, "match": None, "adv": None}


def select_matches(st):
    ms = [m for m in MS if all(FILTERS[f][1](m) for f in st["filters"])]
    if st["group"] and st["bucket"] is not None:
        if st["group"] == "hero":
            ms = [m for m in ms if any(p["hero_id"] == int(st["bucket"]) for p in m["players"])]
        else:
            ms = [m for m in ms if GROUPS[st["group"]][1](m) == st["bucket"]]
    ms.sort(key=SORTS[st["sort"]][1])
    return ms


# ---------------- rendering ----------------

def thumb(m):
    if m["id"] not in _thumb_cache:
        _thumb_cache[m["id"]] = charts.thumb_spark_png(m["leads"])
    return _thumb_cache[m["id"]]


def _row_section(m):
    r = "".join(render.hero_emoji(p["hero_id"]) or "•" for p in m["players"] if p["is_radiant"])
    d = "".join(render.hero_emoji(p["hero_id"]) or "•" for p in m["players"] if not p["is_radiant"])
    return discord.ui.Section(
        discord.ui.TextDisplay(f"**{m['kills']}** kills · `{render.dur(m['duration'])}`\n{r} ⚔ {d}"),
        accessory=discord.ui.Thumbnail(f"attachment://t{m['id']}.png"),
    )


def _sel(custom_id, placeholder, options, cb, multi=False):
    s = discord.ui.Select(custom_id=custom_id, placeholder=placeholder, options=options,
                          min_values=0 if multi else 1,
                          max_values=len(options) if multi else 1)
    s.callback = cb
    return s


def _btn(custom_id, label, cb, style=discord.ButtonStyle.secondary, url=None):
    b = discord.ui.Button(custom_id=None if url else custom_id, label=label, style=discord.ButtonStyle.link if url else style, url=url)
    if not url:
        b.callback = cb
    return b


class Board(discord.ui.LayoutView):
    def __init__(self, st):
        super().__init__(timeout=None)
        self.st = st
        self.files = []
        build = {"list": self._list, "group": self._group, "focus": self._focus,
                 "graph": self._graph, "adv": self._adv_results}[st["mode"]]
        build()

    # ---- interactions plumbing ----
    async def _update(self, itx, **changes):
        self.st.update(changes)
        STATE[itx.message.id] = self.st
        nv = Board(self.st)
        files = [discord.File(io.BytesIO(b), filename=n) for n, b in nv.files]
        await itx.response.edit_message(view=nv, attachments=files)
        log.info(f"{itx.user} -> {changes}")

    # ---- list mode ----
    def _controls(self, ms):
        st = self.st
        sort_opts = [discord.SelectOption(label=v[0], value=k, default=(k == st["sort"]))
                     for k, v in SORTS.items()]
        filt_opts = [discord.SelectOption(
            label=f"{v[0]} ({sum(1 for m in MS if v[1](m))})", value=k,
            default=(k in st["filters"])) for k, v in FILTERS.items()]
        group_opts = ([discord.SelectOption(label="Off", value="off")] +
                      [discord.SelectOption(label=v[0], value=k) for k, v in GROUPS.items()])
        open_opts = [discord.SelectOption(
            label=f"{render.dur(m['duration'])} · {m['kills']} kills · "
                  f"{render.hero_name(render.star_of(m)['hero_id'])} "
                  f"{render.star_of(m)['k']}/{render.star_of(m)['d']}/{render.star_of(m)['a']}",
            value=str(m["id"])) for m in ms[st["page"] * PAGE:][:PAGE]] or [
            discord.SelectOption(label="no matches", value="none")]

        async def on_sort(itx):
            await self._update(itx, sort=(sel_sort.values or ["spice"])[0], page=0)

        async def on_filter(itx):
            await self._update(itx, filters=list(sel_filt.values), page=0)

        async def on_group(itx):
            v = (sel_group.values or ["off"])[0]
            if v == "off":
                await self._update(itx, group=None, bucket=None, mode="list", page=0)
            else:
                await self._update(itx, group=v, bucket=None, mode="group", page=0)

        async def on_open(itx):
            v = sel_open.values[0]
            if v != "none":
                await self._update(itx, match=int(v), mode="focus")

        sel_sort = _sel("mb_sort", "Sort", sort_opts, on_sort)
        sel_filt = _sel("mb_filt", "Filters (pick any)", filt_opts, on_filter, multi=True)
        sel_group = _sel("mb_group", "Group by", group_opts, on_group)
        sel_open = _sel("mb_open", "Open a match", open_opts, on_open)
        return sel_sort, sel_filt, sel_group, sel_open

    def _nav_row(self, pages):
        st = self.st

        async def prev(itx):
            await self._update(itx, page=max(0, st["page"] - 1))

        async def nxt(itx):
            await self._update(itx, page=min(pages - 1, st["page"] + 1))

        async def dice(itx):
            await self._update(itx, match=random.choice(MS)["id"], mode="focus")

        async def adv(itx):
            await itx.response.send_modal(AdvModal(self.st))

        row = discord.ui.ActionRow(
            _btn("mb_pp", "◀", prev),
            _btn("mb_pn", f"{st['page'] + 1}/{max(pages, 1)} ▶", nxt),
            _btn("mb_dice", "🎲", dice, style=discord.ButtonStyle.primary),
            _btn("mb_adv", "⚙️ Advanced", adv),
        )
        return row

    def _list(self):
        st = self.st
        ms = select_matches(st)
        pages = max(1, (len(ms) + PAGE - 1) // PAGE)
        page = ms[st["page"] * PAGE:][:PAGE]
        self.files = [(f"t{m['id']}.png", thumb(m)) for m in page]
        filt_txt = f" · filters: {len(st['filters'])}" if st["filters"] else ""
        bucket_txt = f" · {st['bucket']}" if st["bucket"] else ""
        c = discord.ui.Container(accent_colour=discord.Colour(GOLD))
        c.add_item(discord.ui.TextDisplay(f"## 🎛️ MATCH BOARD\n-# {len(ms)} matches{filt_txt}{bucket_txt}"))
        c.add_item(discord.ui.Separator())
        for m in page:
            c.add_item(_row_section(m))
        if not page:
            c.add_item(discord.ui.TextDisplay("no matches — clear a filter"))
        c.add_item(discord.ui.Separator())
        sel_sort, sel_filt, sel_group, sel_open = self._controls(ms)
        for s in (sel_sort, sel_filt, sel_group, sel_open):
            c.add_item(discord.ui.ActionRow(s))
        c.add_item(self._nav_row(pages))
        self.add_item(c)

    # ---- group mode ----
    def _group(self):
        st = self.st
        g = st["group"]
        ms = [m for m in MS if all(FILTERS[f][1](m) for f in st["filters"])]
        c = discord.ui.Container(accent_colour=discord.Colour(PURPLE))
        c.add_item(discord.ui.TextDisplay(f"## 🎛️ MATCH BOARD\n-# grouped by {GROUPS[g][0].lower()}"))
        c.add_item(discord.ui.Separator())
        if g == "hero":
            agg = defaultdict(lambda: {"n": 0, "w": 0, "d": 0})
            for m in ms:
                for p in m["players"]:
                    a = agg[p["hero_id"]]
                    a["n"] += 1
                    a["w"] += (p["is_radiant"] == m["radiant_win"])
                    a["d"] += p["d"]
            top = sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:10]
            rows = "\n".join(
                f"{render.hero_emoji(h) or '•'} **{render.hero_name(h)}** · {a['n']} games · "
                f"{a['w'] * 100 // a['n']}% win · {a['d'] / a['n']:.1f} avg deaths" for h, a in top)
            opts = [discord.SelectOption(label=f"{render.hero_name(h)} ({a['n']})", value=str(h))
                    for h, a in top]
        else:
            buckets = defaultdict(list)
            for m in ms:
                buckets[GROUPS[g][1](m)].append(m)
            items = sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:12]
            rows = "\n".join(
                f"**{b}** · {len(bs)} matches · avg {sum(m['kills'] for m in bs) // len(bs)} kills · "
                f"max {max(m['kills'] for m in bs)}" for b, bs in items)
            opts = [discord.SelectOption(label=f"{b} ({len(bs)})", value=str(b)) for b, bs in items]
        c.add_item(discord.ui.TextDisplay(rows or "no data"))
        c.add_item(discord.ui.Separator())

        async def on_drill(itx):
            await self._update(itx, bucket=drill.values[0], mode="list", page=0)

        async def on_group(itx):
            v = (regroup.values or ["off"])[0]
            if v == "off":
                await self._update(itx, group=None, bucket=None, mode="list")
            else:
                await self._update(itx, group=v, bucket=None, mode="group")

        drill = _sel("mb_drill", "Open a bucket", opts, on_drill)
        regroup = _sel("mb_regroup", f"Group by: {GROUPS[g][0].lower()}",
                       [discord.SelectOption(label="Off", value="off")] +
                       [discord.SelectOption(label=v[0], value=k) for k, v in GROUPS.items()], on_group)
        c.add_item(discord.ui.ActionRow(regroup))
        c.add_item(discord.ui.ActionRow(drill))

        async def back(itx):
            await self._update(itx, group=None, bucket=None, mode="list")

        c.add_item(discord.ui.ActionRow(_btn("mb_back", "◀ Board", back)))
        self.add_item(c)

    # ---- focus / graph ----
    def _focus(self):
        m = next(x for x in MS if x["id"] == self.st["match"])
        self.files = [(f"s{m['id']}.png", charts.sparkline_png(m["leads"]))]
        r = sorted([p for p in m["players"] if p["is_radiant"]], key=lambda p: -p["networth"])
        d = sorted([p for p in m["players"] if not p["is_radiant"]], key=lambda p: -p["networth"])
        win = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
        c = discord.ui.Container(accent_colour=discord.Colour(GREEN if m["radiant_win"] else RED))
        c.add_item(discord.ui.TextDisplay(
            f"## Match {m['id']} · {win} · `{render.dur(m['duration'])}` · 🟢 {m['kills_r']} — {m['kills_d']} 🔴"))
        g = discord.ui.MediaGallery()
        g.add_item(media=f"attachment://s{m['id']}.png")
        c.add_item(g)
        c.add_item(discord.ui.TextDisplay("**Radiant**\n" + "\n".join(render.player_line(p) for p in r)))
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay("**Dire**\n" + "\n".join(render.player_line(p) for p in d)))

        async def graph(itx):
            await self._update(itx, mode="graph")

        async def back(itx):
            await self._update(itx, mode="list", match=None)

        async def dice(itx):
            await self._update(itx, match=random.choice(MS)["id"])

        c.add_item(discord.ui.ActionRow(
            _btn("mb_g", "📈 Graph", graph, style=discord.ButtonStyle.primary),
            _btn("mb_b", "◀ Board", back),
            _btn("mb_d2", "🎲", dice),
            _btn(None, "OpenDota", None, url=f"https://www.opendota.com/matches/{m['id']}"),
        ))
        self.add_item(c)

    def _graph(self):
        m = next(x for x in MS if x["id"] == self.st["match"])
        self.files = [(f"g{m['id']}.png", charts.networth_lead_png(
            m["leads"], f"Match {m['id']} — Net Worth Lead"))]
        c = discord.ui.Container(accent_colour=discord.Colour(GREEN if m["radiant_win"] else RED))
        c.add_item(discord.ui.TextDisplay(f"## Match {m['id']} · net worth"))
        g = discord.ui.MediaGallery()
        g.add_item(media=f"attachment://g{m['id']}.png")
        c.add_item(g)

        async def back(itx):
            await self._update(itx, mode="focus")

        async def board(itx):
            await self._update(itx, mode="list", match=None)

        c.add_item(discord.ui.ActionRow(
            _btn("mb_sc", "◀ Scoreboard", back), _btn("mb_bd", "🎛️ Board", board)))
        self.add_item(c)

    # ---- advanced results ----
    def _adv_results(self):
        a = self.st["adv"]
        scored = []
        for m in MS:
            crits = [m["mins"] >= a["min_dur"], m["kills"] >= a["min_kills"],
                     all(any(h in render.hero_name(p["hero_id"]).lower() for p in m["players"])
                         for h in a["heroes"]) if a["heroes"] else True,
                     _item_count_ok(m, a["items"])]
            scored.append((sum(crits), m))
        scored.sort(key=lambda t: (-t[0], -t[1]["kills"]))
        exact = [m for s, m in scored if s == 4]
        show = exact[:PAGE] if exact else [m for _, m in scored[:3]]
        self.files = [(f"t{m['id']}.png", thumb(m)) for m in show]
        head = (f"{len(exact)} exact matches" if exact
                else "0 exact matches · showing 3 closest")
        c = discord.ui.Container(accent_colour=discord.Colour(GOLD))
        c.add_item(discord.ui.TextDisplay(f"## 🎛️ MATCH BOARD\n-# {head}"))
        c.add_item(discord.ui.Separator())
        for m in show:
            c.add_item(_row_section(m))
        c.add_item(discord.ui.Separator())

        async def on_open(itx):
            await self._update(itx, match=int(op.values[0]), mode="focus")

        op = _sel("mb_aopen", "Open a match", [discord.SelectOption(
            label=f"{render.dur(m['duration'])} · {m['kills']} kills", value=str(m["id"]))
            for m in show], on_open)
        c.add_item(discord.ui.ActionRow(op))

        async def edit(itx):
            await itx.response.send_modal(AdvModal(self.st))

        async def clear(itx):
            await self._update(itx, adv=None, mode="list", page=0)

        c.add_item(discord.ui.ActionRow(
            _btn("mb_ae", "⚙️ Edit search", edit), _btn("mb_ac", "✕ Clear", clear)))
        self.add_item(c)


def _item_count_ok(m, items):
    for key, n in items:
        have = sum(1 for p in m["players"] for i in p["items"]
                   if key in (render.item_key(i) or ""))
        if have < n:
            return False
    return True


class AdvModal(discord.ui.Modal, title="Advanced search"):
    min_dur = discord.ui.TextInput(label="Min duration (minutes)", required=False, placeholder="90")
    min_kills = discord.ui.TextInput(label="Min total kills", required=False, placeholder="90")
    heroes = discord.ui.TextInput(label="Heroes (comma separated, all must play)", required=False,
                                  placeholder="largo, treant")
    items = discord.ui.TextInput(label="Items (name xCount, comma separated)", required=False,
                                 placeholder="rapier x2")

    def __init__(self, st):
        super().__init__()
        self.st = st

    async def on_submit(self, itx: discord.Interaction):
        def num(v):
            try:
                return int(str(v).strip())
            except ValueError:
                return 0

        items = []
        for part in str(self.items.value or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if " x" in part:
                name, _, n = part.rpartition(" x")
                items.append((name.strip().replace(" ", "_"), num(n) or 1))
            else:
                items.append((part.replace(" ", "_"), 1))
        adv = {"min_dur": num(self.min_dur.value), "min_kills": num(self.min_kills.value),
               "heroes": [h.strip().lower() for h in str(self.heroes.value or "").split(",") if h.strip()],
               "items": items}
        self.st.update(adv=adv, mode="adv")
        STATE[itx.message.id] = self.st
        nv = Board(self.st)
        files = [discord.File(io.BytesIO(b), filename=n) for n, b in nv.files]
        # defer + explicit message edit: the robust path for modal submits
        await itx.response.defer()
        await itx.message.edit(view=nv, attachments=files)
        log.info(f"{itx.user} advanced: {adv}")


# ---------------- bot ----------------

client = discord.Client(intents=discord.Intents.default())


@client.event
async def on_ready():
    log.info(f"logged in as {client.user}")
    ch = client.get_channel(CHANNEL) or await client.fetch_channel(CHANNEL)
    st = default_state()
    v = Board(st)
    files = [discord.File(io.BytesIO(b), filename=n) for n, b in v.files]
    msg = await ch.send(view=v, files=files)
    STATE[msg.id] = st
    log.info(f"LIVE board posted: https://discord.com/channels/{msg.guild.id}/{ch.id}/{msg.id}")


if __name__ == "__main__":
    import os
    client.run(os.environ["DISCORD_BOT_TOKEN"].strip(), log_handler=None)
