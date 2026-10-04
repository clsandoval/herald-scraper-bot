"""LIVE Match Board — SQL-backed, exhaustive over herald.db.

Opened on demand via `/heralds` (ephemeral, private to the caller) and posts
nothing on its own. Every control
works: sort, multi-filter, open match, paging, dice,
advanced modal. Every interaction is a SQL query against herald.db — the
board covers everything ingest has enriched (14-day default retention); raw JSON is
parsed only for the rows actually displayed.

Run: python -m herald menu (after python -m herald.ingest --init-db)
"""

import asyncio
import io
import json
import logging
import sqlite3
from collections import OrderedDict

import discord

from . import charts, ingest, render

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("live_board")

import os

GOLD, GREEN, RED = 0xC8A03C, 0x3BA55D, 0xED4245
PAGE = 5

DB_PATH = os.environ.get("HERALD_DB", "herald.db")

# ponytail: NO shared conn, NO write connection. The old single `_conn`
# (check_same_thread=False) was touched directly on discord.py's one loop
# thread, so every sync query + matplotlib render blocked the gateway
# heartbeat; while ingest --loop holds the WAL/exclusive lock for minutes,
# busy_timeout=30s turned instant failure into a 30s loop stall and every
# interaction timed out. Every read below opens a FRESH read-only conn inside
# a worker thread (asyncio.to_thread), waits on busy_timeout OFF-loop, then
# closes it. Any write pragma/DDL here (journal_mode, CREATE, ALTER) needs a
# lock ingest holds for minutes at boot -> 'database is locked' -> container
# restart loop (2026-09-05). ingest owns the schema (its connect() migrates
# every column the board reads).


def _q_sync(sql, params=()):
    """Sync read on a worker thread only — never call from the loop thread."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")  # ingest writes/WAL-recovers — wait off-loop
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


async def q(sql, params=()):
    """Off-loop read: fresh RO conn per call, heartbeat never stalls on a locked DB."""
    return await asyncio.to_thread(_q_sync, sql, params)


async def hydrate(ids):
    """match_ids -> match_view dicts; raw JSON parsed only for these rows."""
    if not ids:
        return []
    rows = await q("SELECT match_id, raw, avg_rank_tier FROM matches"
                   f" WHERE match_id IN ({','.join('?' * len(ids))})", list(ids))
    by_id = {}
    for r in rows:
        v = ingest.match_view(json.loads(r[1]))
        v["art"] = r[2]  # OpenDota avg_rank_tier 11-15 -> rank medal emoji
        by_id[r[0]] = v
    return [by_id[i] for i in ids if i in by_id]


MAX_THUMBS = 200  # bound matplotlib PNG cache; evict oldest id first
_thumb_cache = OrderedDict()  # id -> png bytes

# Data fetch + PNG bytes happen in worker threads; the View itself MUST be
# built on the event loop. discord.py's View.__init__ only wires up the
# component-dispatch machinery when a running loop is present; building in a
# worker thread leaves the view non-dispatchable, so every button silently
# no-ops ("interaction failed"). So: await data off-loop, construct on-loop.
async def build_board(st):
    score, counts = await corpus_info()
    if st.get("mode") == "focus":
        ms = await hydrate([st["match"]])
        if not ms:
            st.update(mode="list", match=None)
            st["notice"] = "That match has left the archive. Choose another match."
            return await build_board(st)
        m = ms[0]
        chart = await asyncio.to_thread(
            charts.networth_lead_png, m["leads"], f"Match {m['id']} — Net Worth Lead")
        row = await q("SELECT weirdness, weird_notes FROM matches WHERE match_id=?", (m["id"],))
        srow = await q("SELECT skill_weirdness, skill_notes FROM matches WHERE match_id=?",
                       (m["id"],))
        raw_row = await q("SELECT raw FROM matches WHERE match_id=?", (m["id"],))
        focus_data = {"m": m, "row": row, "srow": srow, "raw_row": raw_row}
        return Board(st, focus_data=focus_data,
                     files=[(f"g{m['id']}.png", chart)])
    total, page, span = await select_page(st, score)
    files = []
    for m in page:
        files.append((f"t{m['id']}.png", await thumb(m)))
    return Board(st, list_data=(total, page, span), files=files, counts=counts)


# ---------------- data: sorts / filters / groups as SQL ----------------

# ponytail: flips/avg_gap/rapier_count used to be rebuilt from raw JSON at every
# board boot — a multi-minute 1.5GB scan that made the board unavailable after
# each restart. They're now ingest columns (lead_flips already existed); the
# board just reads them, so boot is a cheap indexed aggregate.
import math  # noqa: E402
_HDPM = "coalesce(hero_damage, 0) * 60.0 / duration_s"
_FLIPS = "coalesce(lead_flips, 0)"
# Watchability combines corpus-relative kills, hero damage, gold swings and duration.
# Recompute aggregates off-loop on each interaction so cold starts remain valid.
def score_expression(stats):
    """Finite sort expression for empty, constant and varied corpora."""
    terms = []
    for index, column, weight in ((0, "kpm", 1), (2, _FLIPS, .7),
                                  (4, _HDPM, .85), (6, "duration_s", .5)):
        mean, square = stats[index:index + 2]
        mean = mean or 0.0
        scale = max(math.sqrt(max((square or 0) - mean ** 2, 0)), 1.0)
        z = f"(({column} - {mean!r}) / {scale!r})"
        terms.append(f"{weight} * " + (f"min({z}, 2.0)" if index == 0 else z))
    return "(" + " + ".join(terms) + ")"


_SPICE = "coalesce(kpm, 0)"  # replaced from current corpus per menu refresh

# direction-neutral metrics; the ⬆/⬇ nav button supplies ASC/DESC
SORTS = {  # key -> (label, ORDER BY expr)
    "spice": ("Watchability (kills + hero damage + flips)", _SPICE),
    "hd": ("Combined hero damage", "coalesce(hero_damage, 0)"),
    "kills": ("Total kills", "kills"),
    "kpm": ("Kills per minute", "kpm"),
    "dur": ("Match time", "duration_s"),
    "tight": ("Average gold gap all game", "coalesce(avg_gap, 0)"),
    "flips": ("Number of big gold swings", "coalesce(gold_swings, 0)"),
    "rapiers": ("Divine Rapiers held at game end", "coalesce(rapier_count, 0)"),
    "rank": ("Average rank", "avg_rank_tier"),
    "weird": ("Item build weirdness", "coalesce(weirdness, 0)"),
    "skillweird": ("Skill-order weirdness", "coalesce(skill_weirdness, 0)"),
    "mastery": ("Dota Plus mastery (total Master+ badges)", "coalesce(mastery_sum, 0)"),
    "talkative": ("Most talkative (all-chat lines)", "coalesce(chat_lines, 0)"),
}
# picking a new primary sort resets direction to its natural default
PREF_DIR = {"rank": "ASC",   # lowest-rank games are the draw
            "tight": "ASC"}  # smallest average gap = the nailbiters

FILTERS = {  # key -> (label, WHERE expr; matches.-qualified so joins work too)
    "rare": ("Rare hero",
             "EXISTS (SELECT 1 FROM match_players p WHERE p.match_id = matches.match_id"
             " AND p.hero_id IN (SELECT hero_id FROM match_players GROUP BY hero_id"
             " ORDER BY count(*) LIMIT 10))"),
    "lowrank": ("Rank below Herald 3", "matches.avg_rank_tier < 13"),
    "highrank": ("Rank Herald 3+", "matches.avg_rank_tier >= 13"),
    "stack5": ("Full 5-stack", "matches.max_party >= 5"),
    "apm": ("500+ APM player", "matches.max_apm >= 500"),
    "mastery": ("Master+ badge", "matches.max_dplus >= 25"),
    "megas": ("Mega-creep comeback", "matches.megas_comeback = 1"),
}
# Threshold subqueries follow the corpus as ingest adds/prunes matches.
FILTERS["weirdf"] = ("Off-meta item build",
    "matches.weirdness > 0 AND matches.weirdness >= (SELECT weirdness FROM matches WHERE weirdness IS NOT NULL"
    " ORDER BY weirdness LIMIT 1 OFFSET (SELECT count(*) * 95 / 100 FROM matches"
    " WHERE weirdness IS NOT NULL))")
FILTERS["skillf"] = ("Unusual skill order",
    "matches.skill_weirdness > 0 AND matches.skill_weirdness >= (SELECT skill_weirdness FROM matches"
    " WHERE skill_weirdness IS NOT NULL ORDER BY skill_weirdness LIMIT 1"
    " OFFSET (SELECT count(*) * 95 / 100 FROM matches WHERE skill_weirdness IS NOT NULL))")
for _t in (70, 80):
    FILTERS[f"war{_t}"] = (f"Longer than {_t} min", f"matches.duration_s >= {_t * 60}")


async def corpus_info():
    stats = (await q(f"SELECT avg(kpm), avg(kpm*kpm), avg({_FLIPS}), avg({_FLIPS}*{_FLIPS}),"
        f" avg({_HDPM}), avg(({_HDPM}) * ({_HDPM})),"
        " avg(duration_s), avg(duration_s * 1.0 * duration_s) FROM matches"))[0]
    counts = (await q("SELECT " + ", ".join(
        f"coalesce(sum({expr}), 0)" for _, expr in FILTERS.values()) + " FROM matches"))[0]
    return score_expression(stats), dict(zip(FILTERS, counts))


def default_state():
    return {"mode": "list", "sort": ["spice"], "dir": "DESC", "filters": [],
            "page": 0, "match": None, "adv": None, "spoiler": False}


async def adv_conds(a):
    conds = []
    if a.get("dur"):
        op, n = a["dur"]
        conds.append(f"(matches.duration_s / 60.0 {op} {int(n)})")
    if a.get("min_kills"):
        conds.append(f"(matches.kills >= {int(a['min_kills'])})")
    if a.get("rank"):
        op, n = a["rank"]
        conds.append(f"(matches.avg_rank_tier {op} {int(n)})")
    hero_ids = {r[0] for r in await q("SELECT DISTINCT hero_id FROM match_players")}
    for h in a.get("heroes") or []:
        ids = [hid for hid in hero_ids if h in render.hero_name(hid).lower()]
        conds.append(
            "EXISTS (SELECT 1 FROM match_players p WHERE p.match_id = matches.match_id"
            f" AND p.hero_id IN ({','.join(map(str, ids))}))" if ids else "(0)")
    for key, n in a.get("items") or []:
        ids = [iid for iid, it in render._item_by_id.items() if key in it["key"]]
        conds.append(
            "((SELECT count(*) FROM match_players p, json_each(p.items) j"
            f" WHERE p.match_id = matches.match_id AND j.value IN ({','.join(map(str, ids))}))"
            f" >= {int(n)})" if ids else "(0)")
    return conds


async def build_where(st):
    conds = [FILTERS[f][1] for f in st["filters"]]
    if st.get("adv"):
        conds += await adv_conds(st["adv"])
    return (" WHERE " + " AND ".join(conds)) if conds else "", []


async def select_page(st, score=None):
    where, params = await build_where(st)
    total, lo, hi = (await q(
        f"SELECT count(*), min(start_time), max(start_time) FROM matches{where}",
        params))[0]
    span = ""
    if lo:
        import datetime
        f = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%b %-d")
        span = f(lo) if f(lo) == f(hi) else f"{f(lo)} – {f(hi)}"
    st["page"] = max(0, min(st["page"], max(0, (total - 1) // PAGE)))
    order = ", ".join(f"{score if k == 'spice' and score else SORTS[k][1]} {st['dir']}"
                      for k in st["sort"]) + ", match_id DESC"
    rows = await q(f"SELECT match_id FROM matches{where} ORDER BY {order}"
                   " LIMIT ? OFFSET ?", params + [PAGE, st["page"] * PAGE])
    return total, await hydrate([r[0] for r in rows]), span


async def random_match_id(st):
    where, params = await build_where(st)
    rows = await q(f"SELECT match_id FROM matches{where} ORDER BY RANDOM() LIMIT 1", params)
    return rows[0][0] if rows else None


# ---------------- rendering ----------------

async def thumb(m):
    hit = _thumb_cache.get(m["id"])
    if hit is None:
        hit = await asyncio.to_thread(charts.thumb_spark_png, m["leads"])
        _thumb_cache[m["id"]] = hit
        while len(_thumb_cache) > MAX_THUMBS:
            _thumb_cache.popitem(last=False)
    else:
        _thumb_cache.move_to_end(m["id"])
    return hit


def rank_emoji(tier):
    e = render._emoji.get(f"rank_{tier}")
    return f"<:{e['name']}:{e['id']}> " if e else ""


def _row_section(m, n=None):
    def side(rad):  # per-hero K/D/A inline: emoji`k/d/a`
        return " ".join(f"{render.hero_emoji(p['hero_id']) or render.hero_name(p['hero_id'])}`{p['k']}/{p['d']}/{p['a']}`"
                        for p in m["players"] if bool(p["is_radiant"]) == rad)
    num = f"`{n}` · " if n else ""
    return discord.ui.Section(
        discord.ui.TextDisplay(
            f"{num}{rank_emoji(m.get('art'))}`{m['id']}` · **{m['kills']}** kills"
            f" · `{render.dur(m['duration'])}`\n{side(True)}\n{side(False)}"),
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
    def __init__(self, st, list_data=None, focus_data=None, files=None, counts=None):
        super().__init__(timeout=None)
        self.st = st
        self.files = files or []
        self.counts = counts or {}
        if st["mode"] == "focus":
            self._focus(focus_data)
        else:
            self._list(list_data)
        self._fit_text_budget()

    def _fit_text_budget(self):
        """Keep team rows; shorten optional evidence before Discord rejects it."""
        texts = [item for item in self.walk_children() if isinstance(item, discord.ui.TextDisplay)]
        excess = sum(len(item.content) for item in texts) - render.MAX_CHARS
        # Optional focus receipts come after the title and both teams.
        optional = texts[3:] if self.st["mode"] == "focus" else texts
        for item in reversed(optional):
            if excess <= 0:
                break
            old = item.content
            target = max(70, len(old) - excess)
            if target < len(old):
                suffix = "\n… Additional receipts omitted."
                item.content = old[:max(0, target - len(suffix))].rsplit("\n", 1)[0] + suffix
                excess -= len(old) - len(item.content)
        # Defensive final cap for an unusually large core player row.
        for item in reversed(texts):
            if excess <= 0:
                break
            old = item.content
            target = max(30, len(old) - excess)
            item.content = old[:target - 1] + "…"
            excess -= len(old) - len(item.content)

    async def on_error(self, interaction, error, item):
        log.error("Menu interaction failed: %s", type(error).__name__)
        message = "The archive is temporarily unavailable. Try /heralds again shortly."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # ---- interactions plumbing ----
    async def _update(self, itx, **changes):
        self.st.update(changes)
        # ACK now (<3s), then build off-loop so a slow query can't freeze the heartbeat
        if not itx.response.is_done():
            await itx.response.defer()
        if self.st.pop("random", False):
            mid = await random_match_id(self.st)
            self.st.update(match=mid, mode="focus" if mid else "list")
        nv = await build_board(self.st)
        files = [discord.File(io.BytesIO(b), filename=n) for n, b in nv.files]
        await itx.edit_original_response(view=nv, attachments=files)
        log.info(f"{itx.user} -> {changes}")

    # ---- list mode ----
    def _controls(self, page_ms):
        st = self.st
        sort_opts = [discord.SelectOption(label=v[0], value=k, default=(k in st["sort"]))
                     for k, v in SORTS.items()]
        filt_opts = [discord.SelectOption(
            label=f"{v[0]} ({self.counts.get(k, 0)})", value=k,
            default=(k in st["filters"])) for k, v in FILTERS.items()]
        # ponytail: spoiler mode rides in the filter menu — no room for a 6th nav button
        filt_opts.append(discord.SelectOption(label="🙈 Hide winners (spoiler)",
                                              value="spoiler", default=st["spoiler"]))
        base = st["page"] * PAGE

        open_opts = [discord.SelectOption(
            label=f"{base + i} · {m['id']} · {render.dur(m['duration'])} · {m['kills']} kills",
            emoji=(discord.PartialEmoji.from_str(e.strip()) if (e := rank_emoji(m.get("art"))) else None),
            value=str(m["id"])) for i, m in enumerate(page_ms, 1)] or [
            discord.SelectOption(label="no matches", value="none")]

        async def on_sort(itx):
            vals = list(sel_sort.values) or ["spice"]
            await self._update(itx, sort=vals, dir=PREF_DIR.get(vals[0], "DESC"), page=0)

        async def on_filter(itx):
            vals = list(sel_filt.values)
            await self._update(itx, filters=[v for v in vals if v != "spoiler"],
                               spoiler=("spoiler" in vals), page=0)

        async def on_open(itx):
            v = sel_open.values[0]
            if v != "none":
                await self._update(itx, match=int(v), mode="focus")

        sel_sort = _sel("mb_sort", "Sort (pick 1+, ties break left to right)", sort_opts, on_sort, multi=True)
        sel_filt = _sel("mb_filt", "Filters (pick any)", filt_opts, on_filter, multi=True)
        sel_open = _sel("mb_open", "Open a match", open_opts, on_open)
        sel_open.disabled = not page_ms
        return sel_sort, sel_filt, sel_open

    def _nav_row(self, pages):
        st = self.st

        async def prev(itx):
            await self._update(itx, page=max(0, st["page"] - 1))

        async def nxt(itx):
            await self._update(itx, page=min(pages - 1, st["page"] + 1))

        async def dice(itx):
            await self._update(itx, random=True)

        async def adv(itx):
            await itx.response.send_modal(AdvModal(self.st))

        async def flip(itx):
            await self._update(itx, dir=("ASC" if st["dir"] == "DESC" else "DESC"), page=0)

        row = discord.ui.ActionRow(
            _btn("mb_pp", "◀", prev),
            _btn("mb_pn", f"{st['page'] + 1}/{max(pages, 1)} ▶", nxt),
            _btn("mb_dir", "⬇ high→low" if st["dir"] == "DESC" else "⬆ low→high", flip),
            _btn("mb_dice", "🎲", dice, style=discord.ButtonStyle.primary),
            _btn("mb_adv", "⚙️ Advanced", adv),
        )
        row.children[0].disabled = st["page"] == 0
        row.children[1].disabled = st["page"] >= pages - 1
        return row

    def _list(self, list_data):
        st = self.st
        total, page, span = list_data
        pages = max(1, (total + PAGE - 1) // PAGE)
        span_txt = f" · {span}" if span else ""
        filt_txt = f" · filters: {len(st['filters'])}" if st["filters"] else ""
        adv_txt = " · ⚙️ advanced on (submit empty form to clear)" if st["adv"] else ""
        sp_txt = " · 🙈 spoilers hidden" if st["spoiler"] else ""
        c = discord.ui.Container(accent_colour=discord.Colour(GOLD))
        c.add_item(discord.ui.TextDisplay(
            f"## HERALD MATCH BOARD\n-# {total} matches{span_txt}{filt_txt}{adv_txt}{sp_txt}"))
        c.add_item(discord.ui.Separator())
        for i, m in enumerate(page, 1 + st["page"] * PAGE):
            c.add_item(_row_section(m, i))
        if not page:
            hint = "No matches — clear a filter or advanced search." if st["filters"] or st["adv"] else "No matches yet. Try /heralds again after the next scrape."
            c.add_item(discord.ui.TextDisplay(hint))
        if notice := st.pop("notice", None):
            c.add_item(discord.ui.TextDisplay(notice))
        c.add_item(discord.ui.Separator())
        sel_sort, sel_filt, sel_open = self._controls(page)
        for s in (sel_sort, sel_filt, sel_open):
            c.add_item(discord.ui.ActionRow(s))
        c.add_item(self._nav_row(pages))
        self.add_item(c)

    # ---- focus / graph ----
    def _focus(self, focus_data):
        m = focus_data["m"]
        row = focus_data["row"]
        srow = focus_data["srow"]
        raw_row = focus_data["raw_row"]
        r = sorted([p for p in m["players"] if p["is_radiant"]], key=lambda p: -p["networth"])
        d = sorted([p for p in m["players"] if not p["is_radiant"]], key=lambda p: -p["networth"])
        sp = self.st.get("spoiler")
        if sp:
            head = f"## Match {m['id']} · `{render.dur(m['duration'])}` · ⚔ {m['kills']} kills"
            c = discord.ui.Container(accent_colour=discord.Colour(GOLD))
        else:
            win = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
            head = (f"## Match {m['id']} · {win} · `{render.dur(m['duration'])}`"
                    f" · 🟢 {m['kills_r']} — {m['kills_d']} 🔴")
            c = discord.ui.Container(accent_colour=discord.Colour(GREEN if m["radiant_win"] else RED))
        c.add_item(discord.ui.TextDisplay(head))
        c.add_item(discord.ui.TextDisplay("**Radiant**\n" + "\n".join(render.player_line(p) for p in r)))
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay("**Dire**\n" + "\n".join(render.player_line(p) for p in d)))
        # off-meta build receipts — why this match scores weird (purchases, not final items)
        if row and (row[0][0] or 0) >= 6 and row[0][1]:
            lines = []
            for note in json.loads(row[0][1]):
                if note["score"] < 6:
                    continue
                buys = ", ".join(f"{f} @{t}m" for f, t, _s in note["items"])
                lines.append(f"{render.hero_emoji(note['hero_id']) or render.hero_name(note['hero_id'])} {buys}")
            if lines:
                c.add_item(discord.ui.TextDisplay("🌀 **Off-meta item builds**\n" + "\n".join(lines)))
        # skill-order weirdness receipts — why this match scores weird on ability picks
        if srow and (srow[0][0] or 0) >= 8 and srow[0][1]:
            lines = []
            for note in json.loads(srow[0][1]):
                picks = ", ".join(f"{name} @pt{idx}" for name, idx, _s in note["picks"])
                tag = f" — {note['tag']}" if note.get("tag") else ""
                lines.append(
                    f"{render.hero_emoji(note['hero_id']) or render.hero_name(note['hero_id'])}"
                    f" {picks}{tag}"
                )
            if lines:
                c.add_item(discord.ui.TextDisplay("🌀 **Weird skill orders**\n" + "\n".join(lines)))
        # Dota Plus mastery badges — per-player receipt, Master+ (>=25, matches mastery_avg)
        gm_players = sorted((p for p in m["players"] if p.get("dplus", 0) >= 25),
                            key=lambda p: -p["dplus"])
        if gm_players:
            lines = [
                f"{render.hero_emoji(p['hero_id']) or render.hero_name(p['hero_id'])}"
                f" — {'GM' if p['dplus'] >= 26 else 'Master'} badge (lvl {p['dplus']})"
                for p in gm_players
            ]
            c.add_item(discord.ui.TextDisplay("🏆 **Dota Plus mastery**\n" + "\n".join(lines)))
        # Per-player feeding/shame receipts + megas match tag (spike signal-mining).
        # Receipts are winner-neutral and render regardless of spoiler; the
        # megas tag is outcome-revealing and is suppressed under spoiler mode.
        if raw_row:
            raw = json.loads(raw_row[0][0])
            lines = []
            for rawp, mp in zip(raw["players"], m["players"]):
                receipts = render.player_receipts(rawp, m["duration"])
                if receipts:
                    lines.append(
                        f"{render.hero_emoji(mp['hero_id']) or render.hero_name(mp['hero_id'])}"
                        f" {'; '.join(receipts)}"
                    )
            if lines:
                c.add_item(discord.ui.TextDisplay("💀 **Feeding & shame**\n" + "\n".join(lines)))
            if not sp:
                tag = render.megas_tag(raw)
                if tag:
                    c.add_item(discord.ui.TextDisplay(tag))
        g = discord.ui.MediaGallery()
        g.add_item(media=f"attachment://g{m['id']}.png")
        if not sp:
            c.add_item(g)

        async def back(itx):
            await self._update(itx, mode="list", match=None)

        async def dice(itx):
            await self._update(itx, random=True)

        c.add_item(discord.ui.ActionRow(
            _btn("mb_b", "◀ Board", back),
            _btn("mb_d2", "🎲", dice),
            _btn(None, "OpenDota", None, url=f"https://www.opendota.com/matches/{m['id']}"),
        ))
        self.add_item(c)


def parse_cmp(v, default_op=">="):
    """'>70' / '<=13' / '70' -> (op, int) with op whitelisted; None when empty/junk."""
    s = str(v or "").strip().replace(" ", "")
    if not s:
        return None
    for op in (">=", "<=", "=", ">", "<"):
        if s.startswith(op):
            s, use = s[len(op):], op
            break
    else:
        use = default_op
    try:
        return (use, int(s))
    except ValueError:
        return None


class AdvModal(discord.ui.Modal, title="Advanced search"):
    dur = discord.ui.TextInput(label="Duration in minutes (e.g. >70 or <20)", required=False,
                               placeholder=">70")
    min_kills = discord.ui.TextInput(label="Min total kills", required=False, placeholder="90")
    rank = discord.ui.TextInput(label="Avg rank tier 11-15 (13 = Herald 3)",
                                required=False, placeholder="<13")
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
        adv = {"dur": parse_cmp(self.dur.value), "min_kills": num(self.min_kills.value),
               "rank": parse_cmp(self.rank.value, default_op="<="),
               "heroes": [h.strip().lower() for h in str(self.heroes.value or "").split(",") if h.strip()],
               "items": items}
        if not (adv["dur"] or adv["min_kills"] or adv["rank"] or adv["heroes"] or adv["items"]):
            adv = None  # empty form = clear advanced criteria
        # advanced criteria are extra WHERE conds on the normal list — sorting
        # and paging keep working on top of them
        self.st.update(adv=adv, mode="list", page=0)
        await itx.response.defer()
        nv = await build_board(self.st)
        files = [discord.File(io.BytesIO(b), filename=n) for n, b in nv.files]
        # edit_original_response works for channel AND ephemeral boards after defer
        await itx.edit_original_response(view=nv, attachments=files)
        log.info(f"{itx.user} advanced: {adv}")


# ---------------- bot ----------------

client = discord.Client(intents=discord.Intents.default())
tree = discord.app_commands.CommandTree(client)


@tree.command(name="heralds", description="Open a private Herald match board only you can see")
async def board_cmd(itx: discord.Interaction):
    st = default_state()
    await itx.response.defer(ephemeral=True)
    try:
        v = await build_board(st)
    except sqlite3.Error:
        log.error("Menu archive is unavailable; initialize it with ingest --init-db")
        await itx.followup.send("The archive is not ready yet. Try /heralds again shortly.", ephemeral=True)
        return
    files = [discord.File(io.BytesIO(b), filename=n) for n, b in v.files]
    await itx.followup.send(view=v, files=files, ephemeral=True)
    log.info(f"{itx.user} opened a private board")


@client.event
async def on_ready():
    log.info(f"logged in as {client.user}")
    for g in client.guilds:
        tree.copy_global_to(guild=g)
        await tree.sync(guild=g)
    log.info(f"slash commands synced to {len(client.guilds)} guilds")


def main():
    client.run(os.environ["DISCORD_BOT_TOKEN"].strip(), log_handler=None)


if __name__ == "__main__":
    main()
