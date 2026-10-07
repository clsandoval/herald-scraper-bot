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
import copy
import hashlib
import io
import json
import logging
import sqlite3
from collections import OrderedDict
from pathlib import Path

import discord

from . import charts, ingest, render

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("live_board")

import os

GOLD, GREEN, RED = 0xC8A03C, 0x3BA55D, 0xED4245
PAGE = 5
MENU_TIMEOUT = 14 * 60  # Disable before the latest interaction token expires at 15 minutes.

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
    conn = sqlite3.connect(Path(DB_PATH).resolve().as_uri() + "?mode=ro", uri=True, timeout=30.0)
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
    rows = await q("SELECT match_id, raw, avg_rank_tier, weirdness, weird_notes,"
                   " skill_weirdness, skill_notes FROM matches"
                   f" WHERE match_id IN ({','.join('?' * len(ids))})", list(ids))
    by_id = await asyncio.to_thread(_hydrate_rows, rows)
    return [by_id[i] for i in ids if i in by_id]


def _optional_notes(value):
    try:
        notes = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return notes if isinstance(notes, list) else []


def _hydrate_rows(rows):
    """Parse potentially large stored timelines away from Discord's event loop."""
    by_id = {}
    for r in rows:
        try:
            raw = json.loads(r[1])
            if not all(isinstance(player.get("isRadiant"), bool) for player in raw["players"]):
                raise ValueError("Player team identity is unavailable")
            v = ingest.match_view(raw)
        except (TypeError, ValueError, KeyError, AttributeError, ZeroDivisionError):
            log.warning("Skipping unreadable menu match %s", r[0])
            continue
        v["art"] = r[2]  # OpenDota avg_rank_tier 11-15 -> rank medal emoji
        v.update(_raw=raw, _weirdness=r[3], _item_notes=_optional_notes(r[4]),
                 _skill_weirdness=r[5], _skill_notes=_optional_notes(r[6]))
        # match_view's [0] fallback supports historical scoring, but charts must
        # not present missing time-series evidence as a flat observed game.
        v["leads"] = raw.get("radiantNetworthLeads") or []
        v["_scores_available"] = all(
            isinstance(raw.get(side), list) and bool(raw[side])
            for side in ("radiantKills", "direKills"))
        by_id[r[0]] = v
    return by_id


MAX_THUMBS = 200  # bound matplotlib PNG cache; evict oldest id first
MAX_FOCUS_CHARTS = 20
MAX_CHART_BYTES = 16 * 1024 * 1024
_thumb_cache = OrderedDict()  # (database, match, lead digest) -> png bytes
_focus_cache = OrderedDict()
_chart_jobs = {}


async def _cached_chart(m, *, focus=False):
    """Bound memory, invalidate changed series, and share concurrent renders."""
    digest = hashlib.blake2b(json.dumps(m["leads"], separators=(",", ":")).encode(),
                             digest_size=16).digest()
    key = (str(Path(DB_PATH).resolve()), m["id"], digest)
    cache = _focus_cache if focus else _thumb_cache
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    job_key = (focus, key)
    task = _chart_jobs.get(job_key)
    if task is None:
        async def render_chart():
            if focus:
                return await asyncio.to_thread(charts.networth_lead_png, m["leads"],
                                               f"Match {m['id']} — Net Worth Lead")
            return await asyncio.to_thread(charts.thumb_spark_png, m["leads"])
        task = asyncio.create_task(render_chart())
        _chart_jobs[job_key] = task
        def finished(job):
            _chart_jobs.pop(job_key, None)
            if not job.cancelled():
                job.exception()  # Retrieve failures even if all requesters cancelled.
        task.add_done_callback(finished)
    data = await asyncio.shield(task)
    cache[key] = data
    cache.move_to_end(key)
    max_count = MAX_FOCUS_CHARTS if focus else MAX_THUMBS
    while len(cache) > max_count or sum(map(len, cache.values())) > MAX_CHART_BYTES:
        cache.popitem(last=False)
    return data

# Data fetch + PNG bytes happen in worker threads; the View itself MUST be
# built on the event loop. discord.py's View.__init__ only wires up the
# component-dispatch machinery when a running loop is present; building in a
# worker thread leaves the view non-dispatchable, so every button silently
# no-ops ("interaction failed"). So: await data off-loop, construct on-loop.
async def build_board(st):
    if st.get("mode") == "focus":
        ms = await hydrate([st["match"]])
        if not ms:
            st.update(mode="list", match=None)
            st["notice"] = "That match has left the archive or has unreadable data. Choose another match."
            return await build_board(st)
        m = ms[0]
        files = []
        if not st.get("spoiler"):
            chart = await _cached_chart(m, focus=True)
            files.append((f"g{m['id']}.png", chart))
        row = [(m["_weirdness"], json.dumps(m["_item_notes"]))]
        srow = [(m["_skill_weirdness"], json.dumps(m["_skill_notes"]))]
        raw_row = [(json.dumps(m["_raw"]),)]
        focus_data = {"m": m, "row": row, "srow": srow, "raw_row": raw_row}
        return Board(st, focus_data=focus_data, files=files)
    score, counts = await corpus_info()
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
             "matches.match_id IN (SELECT match_id FROM match_players"
             " WHERE hero_id IN (SELECT hero_id FROM match_players GROUP BY hero_id"
             " ORDER BY count(*), hero_id LIMIT 10))"),
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
            "page": 0, "match": None, "adv": None, "spoiler": False, "detail": "items"}


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
    hero_ids = {r[0] for r in await q("SELECT DISTINCT hero_id FROM match_players")
                if isinstance(r[0], int) and r[0] > 0}
    for h in a.get("heroes") or []:
        ids = [hid for hid in hero_ids if h in render.hero_name(hid).lower()]
        conds.append(
            "matches.match_id IN (SELECT match_id FROM match_players"
            f" WHERE hero_id IN ({','.join(map(str, ids))}))" if ids else "(0)")
    for key, n in a.get("items") or []:
        ids = [iid for iid, it in render._item_by_id.items() if key in it["key"]]
        conds.append(
            "((SELECT count(*) FROM match_players p, json_each(CASE WHEN json_valid(p.items)"
            " THEN CASE WHEN json_type(p.items) = 'array' THEN p.items ELSE '[]' END"
            " ELSE '[]' END) j"
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
    page = await hydrate([r[0] for r in rows])
    if len(page) < len(rows):
        st.setdefault("notice", "Some matches on this page have incomplete archive data and couldn't be displayed.")
    return total, page, span


async def random_match_id(st):
    where, params = await build_where(st)
    rows = await q(f"SELECT match_id FROM matches{where} ORDER BY RANDOM() LIMIT 1", params)
    return rows[0][0] if rows else None


# ---------------- rendering ----------------

async def thumb(m):
    return await _cached_chart(m)


def rank_emoji(tier):
    e = render._emoji.get(f"rank_{tier}")
    return f"<:{e['name']}:{e['id']}> " if e else ""


def _row_section(m, n=None):
    return discord.ui.Section(
        discord.ui.TextDisplay(render.menu_match_preview(m, n, rank_emoji(m.get("art")))),
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


class MenuSession:
    """One private menu, shared across replacement views and open modals.

    State is committed only after the replacement message is accepted. The lock
    serializes rapid callbacks without delaying their Discord acknowledgement.
    """
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.lock = asyncio.Lock()
        self.current_view = None
        self.last_interaction = None
        self.expired = False
        self._tail = None

    async def update(self, itx, **changes):
        # Reserve callback-entry order before any network await. A slower ACK
        # must not let an older click overwrite a newer click's final state.
        previous = self._tail
        turn = asyncio.get_running_loop().create_future()
        self._tail = turn
        try:
            if not itx.response.is_done():
                await itx.response.defer()
            if previous is not None:
                await asyncio.shield(previous)
            return await self._apply_update(itx, **changes)
        finally:
            def release(_previous=None):
                if not turn.done():
                    turn.set_result(None)
            if previous is not None and not previous.done():
                # A cancelled middle callback must not let later clicks jump
                # past a still-running earlier callback.
                previous.add_done_callback(release)
            else:
                release()

    async def _apply_update(self, itx, **changes):
        async with self.lock:
            if self.expired:
                await itx.followup.send("This menu has expired. Run /heralds to open a fresh board.",
                                        ephemeral=True)
                return self.current_view
            state = copy.deepcopy(self.state)
            changes = dict(changes)
            page_delta = changes.pop("page_delta", 0)
            flip_direction = changes.pop("flip_direction", False)
            random = changes.pop("random", False)
            toggle_detail = changes.pop("toggle_detail", False)
            state.update(changes)
            if page_delta:
                state["page"] = max(0, state["page"] + page_delta)
            if flip_direction:
                state.update(dir="ASC" if state["dir"] == "DESC" else "DESC", page=0)
            if toggle_detail:
                state["detail"] = "skills" if state.get("detail", "items") == "items" else "items"
            if random:
                mid = await random_match_id(state)
                state.update(match=mid, mode="focus" if mid is not None else "list")
                if mid is None:
                    state["notice"] = "No matches fit these filters. Clear a filter and try again."
            view = await build_board(state)
            view.session = self
            files = [discord.File(io.BytesIO(data), filename=name) for name, data in view.files]
            try:
                await itx.edit_original_response(view=view, attachments=files)
            except discord.NotFound:
                self.expired = True
                view.stop()
                raise
            except BaseException:
                view.stop()
                raise
            finally:
                for file in files:
                    file.close()
            self.state = copy.deepcopy(view.st)
            previous = self.current_view
            self.current_view = view
            self.last_interaction = itx
            if previous is not None:
                previous.stop()
            log.info("Menu updated: %s", ", ".join(changes) or "navigation")
            return view


async def menu_error(interaction, error):
    log.error("Menu interaction failed: %s", type(error).__name__)
    message = "The archive is temporarily unavailable. Your filters are unchanged; try again shortly."
    if isinstance(error, discord.NotFound):
        message = "This menu has expired or was deleted. Run /heralds to open a fresh board."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        log.warning("Menu error response could not be delivered")


class Board(discord.ui.LayoutView):
    def __init__(self, st, list_data=None, focus_data=None, files=None, counts=None):
        super().__init__(timeout=MENU_TIMEOUT)
        self.st = copy.deepcopy(st)
        self.files = files or []
        self.counts = counts or {}
        if st["mode"] == "focus":
            self._focus(focus_data)
        else:
            self._list(list_data)
        self._fit_text_budget()
        self.session = MenuSession(self.st)
        self.session.current_view = self

    async def on_timeout(self):
        async with self.session.lock:
            if self.session.current_view is not self:
                return
            self.session.expired = True
            for item in self.walk_children():
                if isinstance(item, discord.ui.Select) or (isinstance(item, discord.ui.Button)
                                                          and item.url is None):
                    item.disabled = True
            texts = [item for item in self.walk_children() if isinstance(item, discord.ui.TextDisplay)]
            if texts:
                texts[0].content += "\n-# Menu expired. Run /heralds to open a fresh board."
                self._fit_text_budget()
            if self.session.last_interaction is not None:
                try:
                    await self.session.last_interaction.edit_original_response(view=self)
                except discord.HTTPException:
                    log.info("Expired menu could not be updated; token expired or message deleted")

    def _fit_text_budget(self):
        """Pack optional evidence fairly; never slice a receipt heading."""
        texts = [item for item in self.walk_children() if isinstance(item, discord.ui.TextDisplay)]
        if sum(len(item.content) for item in texts) <= render.MAX_CHARS:
            return
        if self.st["mode"] == "focus":
            self._fit_focus_receipts(texts)
            return
        excess = sum(len(item.content) for item in texts) - render.MAX_CHARS
        for item in reversed(texts):
            if excess <= 0:
                break
            old = item.content
            target = max(30, len(old) - excess)
            item.content = render.clip(old, target)
            excess -= len(old) - len(item.content)

    def _fit_focus_receipts(self, texts):
        """Keep all player rows, reserve item + skill evidence, then add detail.

        Complete headings and evidence lines are the allocation unit. The first
        useful line in each build category comes before repeated facts or badges.
        """
        marker = "… Additional receipts omitted."
        core, optional = texts[:3], texts[3:]
        core_size = sum(len(item.content) for item in core)
        if core_size > render.MAX_CHARS - len(marker):
            # Malformed/unbounded core values must not silently remove players.
            # Normal inventories and skill paths never need this defensive cap.
            rows = [item.content.splitlines() for item in core[1:]]
            count = sum(max(0, len(lines) - 1) for lines in rows)
            fixed = len(core[0].content) + sum(len(lines[0]) for lines in rows if lines)
            allowance = max(30, (render.MAX_CHARS - len(marker) - fixed - count) // max(count, 1))
            for item, lines in zip(core[1:], rows):
                item.content = "\n".join([lines[0], *(render.clip(line, allowance) for line in lines[1:])])
            core_size = sum(len(item.content) for item in core)
        remaining = render.MAX_CHARS - core_size - len(marker) - 1
        records = []
        for item in optional:
            lines = [line for line in item.content.splitlines() if line and line != marker]
            if not lines:
                records.append({"item": item, "header": "", "lines": [], "kept": [], "priority": 4})
                continue
            header, *body = lines
            priority = (0 if "**Item build receipts**" in header else
                        1 if "**Skill-order receipts**" in header else
                        2 if "**Review moments**" in header else 3)
            records.append({"item": item, "header": header, "lines": list(dict.fromkeys(body)),
                            "kept": [], "priority": priority})
        records.sort(key=lambda record: record["priority"])

        def take(record, *, cap=None):
            nonlocal remaining
            index = len(record["kept"])
            if index >= len(record["lines"]):
                return False
            line = record["lines"][index]
            overhead = len(record["header"]) + 1 if not record["kept"] else 1
            limit = remaining - overhead if cap is None else min(remaining, cap) - overhead
            if len(line) > limit:
                if cap is None or limit < 30:
                    return False
                # A pathological single line may exceed its category's share.
                # Prefer whole item/pick clauses; shorten only the body if needed.
                clauses = line.split(", ")
                fitted = []
                for clause in clauses:
                    if len(", ".join([*fitted, clause])) > limit - 1:
                        break
                    fitted.append(clause)
                line = ", ".join(fitted) + "…" if fitted else render.clip(line, limit)
            record["kept"].append(line)
            remaining -= overhead + len(line)
            return True

        primary = [record for record in records if record["priority"] < 2 and record["lines"]]
        first_lines_fit = sum(len(record["header"]) + 1 + len(record["lines"][0])
                              for record in primary) <= remaining
        for index, record in enumerate(primary):
            # Reserve a fair first-line allowance for every build category.
            take(record, cap=None if first_lines_fit else max(0, remaining // (len(primary) - index)))
        evidence = [record for record in records if record["priority"] <= 2]
        for record in evidence:
            if not record["kept"]:
                take(record)
        while True:
            progress = [take(record) for record in evidence]
            if not any(progress):
                break
        for record in records:
            if record["priority"] <= 2:
                continue
            while take(record):
                pass
            if not record["lines"] and record["header"] and len(record["header"]) <= remaining:
                record["kept"] = [record["header"]]
                record["header"] = ""
                remaining -= len(record["kept"][0])
        kept_items = []
        for record in records:
            item = record["item"]
            if record["kept"]:
                item.content = "\n".join(([record["header"]] if record["header"] else []) + record["kept"])
                kept_items.append(item)
            elif item.parent is not None:
                item.parent.remove_item(item)
        target = kept_items[-1] if kept_items else core[0]
        target.content += "\n" + marker

    async def on_error(self, interaction, error, item):
        await menu_error(interaction, error)

    # ---- interactions plumbing ----
    async def _update(self, itx, **changes):
        return await self.session.update(itx, **changes)

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
            label=f"{base + i} · {m['id']} · {render.dur(m['duration'])} · "
                  + (f"{m['kills']} kills" if m.get("_scores_available", True) else "Kill totals unavailable"),
            emoji=(discord.PartialEmoji.from_str(e.strip()) if (e := rank_emoji(m.get("art"))) else None),
            value=str(m["id"])) for i, m in enumerate(page_ms, 1)] or [
            discord.SelectOption(label="no matches", value="none")]

        async def on_sort(itx):
            vals = list(sel_sort.values) or ["spice"]
            await self._update(itx, sort=vals, dir=PREF_DIR.get(vals[0], "DESC"), page=0,
                               mode="list", match=None)

        async def on_filter(itx):
            vals = list(sel_filt.values)
            await self._update(itx, filters=[v for v in vals if v != "spoiler"],
                               spoiler=("spoiler" in vals), page=0, mode="list", match=None)

        async def on_open(itx):
            values = list(sel_open.values)
            if values and values[0] != "none":
                await self._update(itx, match=int(values[0]), mode="focus")
            elif not itx.response.is_done():
                await itx.response.defer()

        sel_sort = _sel("mb_sort", "Sort (pick 1+, ties break left to right)", sort_opts, on_sort, multi=True)
        sel_filt = _sel("mb_filt", "Filters (pick any)", filt_opts, on_filter, multi=True)
        sel_open = _sel("mb_open", "Open a match", open_opts, on_open)
        sel_open.disabled = not page_ms
        return sel_sort, sel_filt, sel_open

    def _nav_row(self, pages):
        st = self.st

        async def prev(itx):
            await self._update(itx, page_delta=-1)

        async def nxt(itx):
            await self._update(itx, page_delta=1)

        async def dice(itx):
            await self._update(itx, random=True)

        async def adv(itx):
            await itx.response.send_modal(AdvModal(self.session.state, session=self.session))

        async def flip(itx):
            await self._update(itx, flip_direction=True)

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
            if total:
                hint = "No readable matches on this page. Try another page or refresh after the next scrape."
            else:
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
        def wealth_order(player):
            value = player.get("networth")
            known = isinstance(value, (int, float)) and math.isfinite(value)
            return known, value if known else 0
        r = sorted([p for p in m["players"] if p["is_radiant"]], key=wealth_order, reverse=True)
        d = sorted([p for p in m["players"] if not p["is_radiant"]], key=wealth_order, reverse=True)
        sp = self.st.get("spoiler")
        winner_known = isinstance(m["radiant_win"], bool)
        if sp or not winner_known or not m.get("_scores_available", True):
            kills = f"⚔ {m['kills']} kills" if m.get("_scores_available", True) else "Kill totals unavailable"
            head = f"## Match {m['id']} · `{render.dur(m['duration'])}` · {kills}"
            if not sp and not winner_known:
                head += " · winner unavailable"
            c = discord.ui.Container(accent_colour=discord.Colour(GOLD))
        else:
            win = "🟢 Radiant win" if m["radiant_win"] else "🔴 Dire win"
            head = (f"## Match {m['id']} · {win} · `{render.dur(m['duration'])}`"
                    f" · 🟢 {m['kills_r']} — {m['kills_d']} 🔴")
            c = discord.ui.Container(accent_colour=discord.Colour(GREEN if m["radiant_win"] else RED))
        detail = self.st.get("detail", "items")
        if detail == "skills":
            head += "\n-# First 8 non-talent picks; pick number is not hero level"
        else:
            head += "\n-# Final-slot items · K/D/A"
        raw_players = (m.get("_raw") or {}).get("players") or []
        raw_by_player = {id(player): raw for player, raw in zip(m["players"], raw_players)}
        def player_line(player):
            return render.menu_player_line(player, raw_by_player.get(id(player)), detail)
        c.add_item(discord.ui.TextDisplay(head))
        c.add_item(discord.ui.TextDisplay("**Radiant**\n" + "\n".join(player_line(p) for p in r)))
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay("**Dire**\n" + "\n".join(player_line(p) for p in d)))
        for receipt in render.menu_focus_receipts(m, row, srow, raw_row):
            c.add_item(discord.ui.TextDisplay(receipt))
        if not sp and raw_row:
            tag = render.megas_tag(m.get("_raw") or json.loads(raw_row[0][0]))
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

        async def toggle_detail(itx):
            await self._update(itx, toggle_detail=True)

        c.add_item(discord.ui.ActionRow(
            _btn("mb_b", "◀ Board", back),
            _btn("mb_d2", "🎲", dice),
            _btn("mb_detail", "Item builds" if detail == "skills" else "Skill builds", toggle_detail),
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

    def __init__(self, st, session=None):
        super().__init__()
        self.st = copy.deepcopy(st)
        self.session = session or MenuSession(self.st)
        if advanced := st.get("adv"):
            for key in ("dur", "rank"):
                if advanced.get(key):
                    op, value = advanced[key]
                    getattr(self, key).default = f"{op}{value}"
            if advanced.get("min_kills"):
                self.min_kills.default = str(advanced["min_kills"])
            self.heroes.default = ", ".join(advanced.get("heroes") or []) or None
            self.items.default = ", ".join(
                f"{name.replace('_', ' ')} x{count}"
                for name, count in advanced.get("items") or []) or None

    async def on_error(self, interaction, error):
        await menu_error(interaction, error)

    async def on_submit(self, itx: discord.Interaction):
        def num(v, field, *, positive=False):
            try:
                value = int(str(v).strip())
            except ValueError:
                raise ValueError(f"{field} needs a whole number.") from None
            if value < (1 if positive else 0):
                raise ValueError(f"{field} must be {'positive' if positive else 'zero or greater'}.")
            return value

        def comparison(value, field, default_op=">="):
            if not str(value or "").strip():
                return None
            result = parse_cmp(value, default_op)
            if result is None or result[1] < 0:
                raise ValueError(f"{field} needs a nonnegative number, optionally with <, <=, =, > or >=.")
            return result

        items = []
        try:
            for part in str(self.items.value or "").split(","):
                part = part.strip().lower()
                if not part:
                    continue
                if " x" in part:
                    name, _, n = part.rpartition(" x")
                    if not name.strip():
                        raise ValueError("Each item needs a name before its count.")
                    items.append((name.strip().replace(" ", "_"), num(n, "Item count", positive=True)))
                else:
                    items.append((part.replace(" ", "_"), 1))
            adv = {"dur": comparison(self.dur.value, "Duration"),
                   "min_kills": num(self.min_kills.value, "Minimum kills") if str(self.min_kills.value or "").strip() else 0,
                   "rank": comparison(self.rank.value, "Average rank", default_op="<="),
                   "heroes": [h.strip().lower() for h in str(self.heroes.value or "").split(",") if h.strip()],
                   "items": items}
            adv["heroes"] = list(dict.fromkeys(adv["heroes"]))
            # Repeated item predicates imply the largest requested minimum,
            # not an additional independent inventory requirement.
            merged_items = {}
            for name, count in adv["items"]:
                merged_items[name] = max(merged_items.get(name, 0), count)
            adv["items"] = list(merged_items.items())
            if len(adv["heroes"]) > 10 or len(adv["items"]) > 10:
                raise ValueError("Use at most 10 different hero names and 10 different item names.")
        except ValueError as error:
            await itx.response.send_message(str(error) + " Your search is unchanged.", ephemeral=True)
            return
        if not (adv["dur"] or adv["min_kills"] or adv["rank"] or adv["heroes"] or adv["items"]):
            adv = None  # empty form = clear advanced criteria
        # advanced criteria are extra WHERE conds on the normal list — sorting
        # and paging keep working on top of them
        await self.session.update(itx, adv=adv, mode="list", match=None, page=0)


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
    except Exception as error:
        await menu_error(itx, error)
        return
    files = [discord.File(io.BytesIO(b), filename=n) for n, b in v.files]
    try:
        await itx.followup.send(view=v, files=files, ephemeral=True)
    finally:
        for file in files:
            file.close()
    v.session.last_interaction = itx
    log.info(f"{itx.user} opened a private board")


@client.event
async def on_ready():
    log.info(f"logged in as {client.user}")
    # Packaged emoji IDs belong to historical prototypes, not a collaborator's bot.
    render._emoji = {}
    try:
        emojis = await client.fetch_application_emojis()
        render._emoji = {e.name: {"name": e.name, "id": str(e.id)} for e in emojis}
    except (discord.HTTPException, discord.MissingApplicationID):
        log.warning("Application emoji inventory unavailable; using text fallbacks")
    synced = 0
    for g in client.guilds:
        try:
            tree.copy_global_to(guild=g)
            await tree.sync(guild=g)
        except discord.HTTPException:
            log.warning("Slash command sync failed for guild %s; check bot installation permissions", g.id)
            continue
        synced += 1
    log.info("slash commands synced to %s/%s guilds", synced, len(client.guilds))


def main():
    client.run(os.environ["DISCORD_BOT_TOKEN"].strip(), log_handler=None)


if __name__ == "__main__":
    main()
