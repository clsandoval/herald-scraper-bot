"""Slow, opt-in match reports. Fixed legacy selection; no LLM calls.

Importing this module performs no network I/O. SQLite receipts survive interrupted threads.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import sqlite3
import time

import httpx

from . import api, render, report_signals, reporter_novelty

log = logging.getLogger(__name__)
LOOKBACK_DAYS = 1
DELAY_DAYS = 3
INTERVAL_SECONDS = 86400
MIN_DURATION = 4500
MAX_AVERAGE_RANK = 16
MAX_PLAYER_RANK = 15
DISCORD_API = "https://discord.com/api/v10"
REPORT_FIELDS = """
    id gameMode players {
      heroId isRadiant kills deaths assists isRandom
      steamAccount { seasonRank }
      dotaPlus { level }
      item0Id item1Id item2Id item3Id item4Id item5Id
      abilities { abilityId time isTalent }
      stats {
        actionsPerMinute
        itemPurchases { time itemId }
        itemUsed { itemId count }
        deathEvents { time timeDead isDieBack isAttemptTpOut }
      }
    }
"""


def candidate_ok(candidate):
    return (candidate.get("duration", 0) > MIN_DURATION
            and candidate.get("avg_rank_tier") is not None
            and candidate["avg_rank_tier"] <= MAX_AVERAGE_RANK)


def eligible(candidate, raw, opendota):
    """Missing player/account/leaver evidence fails closed; no KPM/lobby filter."""
    players = raw.get("players") or []
    od_players = opendota.get("players") or []
    return (candidate_ok(candidate) and len(players) == 10
            and sum(p.get("isRadiant") is True for p in players) == 5
            and sum(p.get("isRadiant") is False for p in players) == 5
            and all(p.get("steamAccount") is not None
                    and (p["steamAccount"].get("seasonRank") or 0) <= MAX_PLAYER_RANK
                    for p in players)
            and len(od_players) == 10
            and all(p.get("leaver_status") == 0 for p in od_players))


def skill_path(player, limit=280):
    """Keep all twelve observed positions visible, with bounded ability labels."""
    ids = report_signals._skill_ids(player)
    if ids is None:
        return "Unavailable"
    if not ids:
        return "No non-talent picks recorded"
    names = [report_signals.ability_name(a, player.get("heroId")) for a in ids[:12]]
    full_path = " → ".join(f"{i}. {name}" for i, name in enumerate(names, 1))
    if len(full_path) <= limit:
        return full_path
    # Reserve every ordinal before allocating name space. Evidence receipts
    # separately spell out the scored ability and its original observed pick.
    width = max(4, (limit - sum(len(f"{i}. ") for i in range(1, len(names) + 1))
                    - 3 * (len(names) - 1)) // len(names))
    return " → ".join(f"{i}. {render.clip(name, width)}" for i, name in enumerate(names, 1))


def payload(candidate, raw, opendota, emojis, evidence=None):
    """Classic embed cards with factual build/event receipts, no menu ranking.

    This stays a parent plus two team messages so existing delivery receipts
    remain resumable. Components V2 is the interactive menu's separate format.
    """
    mid = candidate["match_id"]
    date = dt.datetime.fromtimestamp(candidate["start_time"], dt.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S")
    duration = candidate["duration"]
    scores = [opendota.get("radiant_score"), opendota.get("dire_score")]
    known_scores = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0
                       for value in scores)
    if known_scores:
        kills = sum(scores)
        density = kills / max((opendota.get("duration") or duration) / 60, 1)
        kill_label = f"{kills} · {density:.2f}/min"
    else:
        kill_label = "Unavailable"
    signals = report_signals.summarize(raw, opendota, duration)
    if evidence is None:
        evidence = reporter_novelty.unavailable(raw)
    cues = list(signals["match"][:2])
    for index, receipts in signals["players"].items():
        if receipts:
            cues.append(f"{render.hero_name(raw['players'][index]['heroId'])}: {receipts[0]}")
    cue_text = render.limited_lines([f"• {render.clip(cue, 180)}" for cue in cues[:4]], 800)
    parent_fields = [
            {"name": "📅 Date", "value": date, "inline": True},
            {"name": "⏱️ Duration", "value": f"{duration // 60}m {duration % 60}s", "inline": True},
            {"name": "⚔️ Kills", "value": kill_label, "inline": True},
            {"name": "🔎 Review cues", "value": cue_text or
             "No standout event cue in the supplied data. Check the item and skill paths below.",
             "inline": False}]
    item_index = reporter_novelty.best_player(evidence, "items")
    if item_index is None:
        item_index = next((i for i, items in signals["items"].items() if items), None)
    if item_index is not None:
        name = render.hero_name(raw["players"][item_index]["heroId"])
        parent_fields.append({"name": "🎒 Build preview", "inline": False,
                              "value": render.clip(f"**{name}** · " +
                                  render.named_items(signals["items"].get(item_index, [])), 400) + "\n" +
                                  reporter_novelty.evidence_text(evidence, "items", item_index,
                                      raw["players"][item_index]["heroId"], limit=350)})
    skill_index = reporter_novelty.best_player(evidence, "skills")
    if skill_index is None:
        skill_index = next((i for i, skills in signals["skills"].items() if skills), None)
    if skill_index is not None:
        name = render.hero_name(raw["players"][skill_index]["heroId"])
        parent_fields.append({"name": "🧩 Skill preview", "inline": False,
                              "value": f"**{name}** · " + skill_path(raw["players"][skill_index], 340) + "\n" +
                                  reporter_novelty.evidence_text(evidence, "skills", skill_index,
                                      raw["players"][skill_index]["heroId"], limit=350)})
    parent_fields.append({"name": "Reference population", "inline": False,
                          "value": reporter_novelty.reference_text(evidence)})
    parent = {"embeds": [{"title": "🏆 Herald Match Review", "description":
        f"Match ID: {mid} · [OpenDota](https://www.opendota.com/matches/{mid})"
        "\nTwo team cards in the thread show final items, early skill picks and observed moments.",
        "color": 0xC8A03C, "url": f"https://stratz.com/matches/{mid}", "fields": parent_fields,
        "footer": {"text": "Observed data · review cues are not a replay-quality score"}}],
        "allowed_mentions": {"parse": []}}
    messages = []
    for radiant, label, color in [(True, "RADIANT", 0x3BA55D), (False, "DIRE", 0xED4245)]:
        fields = []
        for index, p in enumerate(raw["players"]):
            if p["isRadiant"] != radiant:
                continue
            rank = p["steamAccount"].get("seasonRank")
            rank_label = (f"Herald {rank - 10}" if isinstance(rank, int) and 11 <= rank <= 15
                          else "Unranked" if not rank else "Rank unavailable")
            stats = p.get("stats") if isinstance(p.get("stats"), dict) else {}
            apm = stats.get("actionsPerMinute") or []
            apm = apm if isinstance(apm, list) else []
            apm = [value for value in apm if isinstance(value, (int, float))
                   and not isinstance(value, bool) and math.isfinite(value) and value >= 0]
            apm_label = f"{sum(apm) / len(apm):.1f}" if apm else "N/A"
            inventory = signals["items"].get(index)
            items_text = (render.named_items(inventory, emojis) if inventory else
                          "No final-slot items recorded" if inventory == [] else "Unavailable")
            if inventory and len(items_text) > 230:
                items_text = render.named_items(inventory)
            lines = ["**Items:** " + items_text,
                     "**Skill picks:** " + skill_path(p, 240),
                     "**Item evidence:** " + reporter_novelty.evidence_text(
                         evidence, "items", index, p["heroId"], limit=155),
                     "**Skill evidence:** " + reporter_novelty.evidence_text(
                         evidence, "skills", index, p["heroId"], limit=155)]
            receipts = signals["players"].get(index) or []
            if receipts:
                lines.append("**Review:** " + render.clip("; ".join(receipts[:2]), 90))
            kda = "/".join(str(p[key]) if p.get(key) is not None else "?"
                           for key in ("kills", "deaths", "assists"))
            lines.append(f"**KDA:** {kda} · {rank_label} · "
                         f"APM {apm_label} · Dota+ {(p.get('dotaPlus') or {}).get('level') or 'N/A'}")
            text = render.limited_lines(lines, 1024)
            name = render.hero_name(p["heroId"])
            emoji_name = ("h_" + render.hero_short(p["heroId"]))[:32]
            if emoji := render.application_emoji(emoji_name, emojis):
                name = f"{emoji} {name}"
            fields.append({"name": render.clip(name, 256), "value": text, "inline": False})
        messages.append({"embeds": [{"title": f"🛡️ {label} Team", "color": color, "fields": fields,
                         "footer": {"text": "Final inventory · first 12 non-talent picks · experimental long-Herald reference"}}],
                         "allowed_mentions": {"parse": []}})
    for message in [parent, *messages]:
        render.check_embeds(message)
    return {"match_id": mid, "parent": parent, "thread_name": f"Match {mid} - {date}",
            "teams": messages, "build_evidence": json.loads(json.dumps(evidence))}


class Receipts:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS deliveries (match_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS pending_window (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
        self.conn.commit()
        self.novelty = reporter_novelty.ReferenceStore(self.conn)

    def window(self, now, backfill):
        row = self.conn.execute("SELECT data FROM pending_window WHERE id=1").fetchone()
        if row:
            return json.loads(row[0])
        window = {"now": now, "backfill": backfill}
        self.conn.execute("INSERT INTO pending_window VALUES (1, ?)", (json.dumps(window),))
        self.conn.commit()
        return window

    def finish_window(self):
        self.conn.execute("DELETE FROM pending_window WHERE id=1")
        self.conn.commit()

    def get(self, mid):
        row = self.conn.execute("SELECT data FROM deliveries WHERE match_id=?", (mid,)).fetchone()
        return json.loads(row[0]) if row else {"match_id": mid}

    def save(self, receipt):
        self.conn.execute("INSERT OR REPLACE INTO deliveries VALUES (?, ?)",
                          (receipt["match_id"], json.dumps(receipt)))
        self.conn.commit()

    def pending(self):
        for data, in self.conn.execute("SELECT data FROM deliveries ORDER BY match_id"):
            receipt = json.loads(data)
            if not receipt.get("verified") and not receipt.get("deleted"):
                yield receipt


@contextlib.contextmanager
def exclusive_run(path):
    """One local writer per receipt DB. Kernel releases the lock on cancellation."""
    with open(str(Path(path).resolve()) + ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A scheduled reporter already owns this receipt DB") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class DefiniteRejection(RuntimeError):
    """Discord explicitly rejected the write; no acknowledgement ambiguity."""


class DiscordHTTP:
    def __init__(self, client, token):
        self.client = client
        self.headers = {"Authorization": "Bot " + token.strip()}

    def request(self, method, path, **kwargs):
        for _ in range(4):
            response = self.client.request(method, DISCORD_API + path, headers=self.headers, **kwargs)
            if response.status_code == 429:
                delay = float(response.json().get("retry_after", 1))
                if not 0 <= delay <= 60:
                    raise DefiniteRejection("Discord rate limit exceeds this run's wait budget")
                time.sleep(delay + .1)
                continue
            if response.status_code == 404:
                return None
            if response.status_code not in (200, 201):
                error = DefiniteRejection if 400 <= response.status_code < 500 else RuntimeError
                raise error(f"Discord HTTP {response.status_code} during {method}")
            return response.json()
        raise DefiniteRejection("Discord rate-limit retries exhausted")

    def find_message(self, channel, bot_id, expected, nonce):
        # Bounded recovery only; unresolved ambiguous sends are never retried blindly.
        before = ""
        for _ in range(10):
            rows = self.request("GET", f"/channels/{channel}/messages?limit=100{before}") or []
            for row in rows:
                if row.get("author", {}).get("id") != bot_id:
                    continue
                if str(row.get("nonce", "")) == nonce or same_message(row, expected):
                    return row
            if len(rows) < 100:
                break
            before = "&before=" + rows[-1]["id"]
        return None


def same_message(actual, expected):
    a, e = actual.get("embeds", []), expected.get("embeds", [])
    return bool(e) and len(a) == len(e) and all(
        x.get("title") == y.get("title") and x.get("description") == y.get("description")
        and x.get("fields", []) == y.get("fields", []) for x, y in zip(a, e))


def deliver(api, ledger, spec, channel, bot_id):
    receipt = ledger.get(spec["match_id"])
    if receipt.get("verified") or receipt.get("deleted"):
        return receipt
    if receipt.get("channel") not in (None, channel):
        raise RuntimeError("Receipt belongs to another channel; use a separate receipt DB")
    receipt.update(spec=receipt.get("spec", spec), channel=channel)
    spec = receipt["spec"]  # resume the exact original payload, even across code updates
    ledger.save(receipt)

    def write(stage, path, body):
        receipt["inflight"] = stage
        ledger.save(receipt)
        try:
            result = api.request("POST", path, json=body)
            if result is None:
                raise DefiniteRejection("Discord write destination was not found")
            return result
        except DefiniteRejection:
            receipt.pop("inflight", None)
            ledger.save(receipt)
            raise

    def message(stage, destination, expected):
        nonce = f"{spec['match_id']}:{stage}"
        if receipt.get(stage):
            found = api.request("GET", f"/channels/{destination}/messages/{receipt[stage]}")
            if found is None:
                receipt["deleted"] = True
                ledger.save(receipt)
                raise RuntimeError("A report message was deleted; refusing to recreate it")
        else:
            found = api.find_message(destination, bot_id, expected, nonce)
            if not found:
                if receipt.get("inflight") == stage:
                    raise RuntimeError(f"Unresolved {stage} send; reconcile Discord receipt before retry")
                found = write(stage, f"/channels/{destination}/messages",
                    {**expected, "nonce": nonce, "enforce_nonce": True})
                if not found:
                    raise RuntimeError("Discord message endpoint is unavailable")
            receipt[stage] = found["id"]
            ledger.save(receipt)
        verified = api.request("GET", f"/channels/{destination}/messages/{receipt[stage]}")
        if not verified or verified.get("author", {}).get("id") != bot_id or not same_message(verified, expected):
            raise RuntimeError("Discord receipt did not match the intended report")
        if receipt.get("inflight") == stage:
            receipt.pop("inflight", None)
        ledger.save(receipt)

    message("parent", channel, spec["parent"])
    if not receipt.get("thread"):
        parent = api.request("GET", f"/channels/{channel}/messages/{receipt['parent']}")
        thread = (parent or {}).get("thread")
        if not thread:
            if receipt.get("inflight") == "thread":
                raise RuntimeError("Unresolved thread creation; reconcile before retry")
            thread = write("thread", f"/channels/{channel}/messages/{receipt['parent']}/threads",
                           {"name": spec["thread_name"], "auto_archive_duration": 1440})
        if not thread:
            raise RuntimeError("Discord thread was not created")
        receipt["thread"] = thread["id"]
        receipt.pop("inflight", None)
        ledger.save(receipt)
    for stage, team in zip(("radiant", "dire"), spec["teams"]):
        message(stage, receipt["thread"], team)
    receipt["verified"] = True
    receipt["verified_at"] = int(time.time())
    ledger.save(receipt)
    return receipt


def report_window(now, backfill=None):
    end = now if backfill is not None else now - DELAY_DAYS * 86400
    return end - (backfill if backfill is not None else LOOKBACK_DAYS) * 86400, end


def discover(client, now, backfill=None):
    cutoff, end = report_window(now, backfill)
    last, found = None, {}
    for _ in range(400):
        frontier = f"AND match_id < {last} " if last else ""
        rows = api.explorer_fetch(client, "SELECT match_id,start_time,avg_rank_tier,duration "
            "FROM public_matches WHERE avg_rank_tier <= 16 " + frontier +
            "ORDER BY match_id DESC LIMIT 1000")
        if rows is None:
            raise RuntimeError("OpenDota discovery failed; no completeness claim")
        for row in rows:
            if cutoff <= row["start_time"] < end and candidate_ok(row):
                found[row["match_id"]] = row
        if not rows or max(r["start_time"] for r in rows) < cutoff:
            return sorted(found.values(), key=lambda r: r["start_time"])
        last = min(r["match_id"] for r in rows)
        time.sleep(1.1)
    raise RuntimeError("Discovery page limit reached; refusing to label this window complete")


def run_once(ledger, client, token, channel, backfill=None):
    window = ledger.window(int(time.time()), backfill)
    ledger.novelty.begin_pass(int(time.time()))
    log.info("Processing saved report window %s", report_window(window["now"], window["backfill"]))
    discord_api = DiscordHTTP(client, token)
    me = discord_api.request("GET", "/users/@me")
    target = discord_api.request("GET", f"/channels/{channel}")
    if not me or not target or target.get("type") != 0:
        raise RuntimeError("Scheduled reports require a Discord guild text channel")
    application = discord_api.request("GET", "/oauth2/applications/@me")
    emojis = discord_api.request("GET", f"/applications/{application['id']}/emojis")
    emoji_map = {e["name"]: e["id"] for e in emojis.get("items", [])}
    for receipt in list(ledger.pending()):
        deliver(discord_api, ledger, receipt["spec"], channel, me["id"])
    candidates = [r for r in discover(client, window["now"], window["backfill"])
                  if not ledger.get(r["match_id"]).get("verified")
                  and not ledger.get(r["match_id"]).get("deleted")]
    # 25 matches per Stratz request; fixed finite budget for this slow daily run.
    if len(candidates) > 25 * 500:
        raise RuntimeError("Candidate count exceeds the scheduled run's Stratz budget")
    for offset in range(0, len(candidates), 25):
        chunk = candidates[offset:offset + 25]
        matches = api.stratz_fetch_batch(client, [r["match_id"] for r in chunk], fields=REPORT_FIELDS, strict=True)
        if matches == "RATELIMIT":
            raise RuntimeError("Stratz unavailable or rate limited; receipts preserved")
        for candidate in chunk:
            raw = matches.get(candidate["match_id"])
            if not raw:
                continue
            od = client.get(f"{api.OPENDOTA_URL}/matches/{candidate['match_id']}")
            od.raise_for_status()
            od = od.json()
            if not isinstance(od, dict) or od.get("error") or od.get("err"):
                raise RuntimeError("OpenDota match detail unavailable; report window preserved")
            if eligible(candidate, raw, od):
                evidence = ledger.novelty.observe_and_score(candidate, raw, od)
                spec = payload(candidate, raw, od, emoji_map, evidence=evidence)
                deliver(discord_api, ledger, spec, channel, me["id"])
                log.info("Verified report for match %s", candidate["match_id"])
            time.sleep(1.1)
    ledger.finish_window()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="repeat after 24 hours; default runs once")
    parser.add_argument("--backfill", type=int, metavar="DAYS",
                        help="one explicit recent-window pass, e.g. --backfill 7")
    args = parser.parse_args(argv)
    if args.backfill is not None and (args.backfill < 1 or args.loop):
        parser.error("--backfill requires a positive day count and cannot be combined with --loop")
    token = os.environ["DISCORD_BOT_TOKEN"]
    channel = os.environ["DISCORD_CHANNEL_ID"]
    if not os.environ.get("STRATZ_API_TOKEN"):
        raise SystemExit("STRATZ_API_TOKEN is required")
    path = os.environ.get("HERALD_REPORT_DB", "herald-reports.db")
    logging.basicConfig(level=logging.INFO)
    with exclusive_run(path):
        ledger = Receipts(path)
        try:
            with httpx.Client(timeout=30) as client:
                while True:
                    try:
                        run_once(ledger, client, token, channel, args.backfill)
                    except Exception as error:
                        if not args.loop:
                            raise
                        log.error("Scheduled pass stopped (%s); receipts and window preserved; retry after 24 hours",
                                  type(error).__name__)
                    if not args.loop:
                        break
                    time.sleep(INTERVAL_SECONDS)
        finally:
            ledger.conn.close()


if __name__ == "__main__":
    main()
