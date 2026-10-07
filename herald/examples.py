"""Preview two synthetic reporter threads; live delivery requires explicit --send.

No provider API, account data, credentials, network, or disk ledger is needed for
the default dry run. The optional sender shares production payload/delivery code
but owns a separate, destination-bound SQLite example receipt format.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import inspect
import json
import logging
import os
from pathlib import Path
import re
import sqlite3

import httpx

from . import render, scheduled

FIXTURE_SET = "synthetic-reporter-examples-v1"
EXAMPLE_IDS = (-101, -102)  # Local fixture identities, never actual match IDs.
FIXTURE_NOW = 1_704_067_200
LEDGER_FORMAT = "herald-example-receipts-v1"
DEFAULT_RECEIPTS = "herald-examples.db"
log = logging.getLogger(__name__)
_TABLES = {"example_meta", "example_deliveries"}
_UPLOAD_TABLE = "example_pending_uploads"
_HERO_SKILLS = (
    (1, (5003, 5004, 7314, 5006)),
    (2, (5007, 5008, 5009, 5010)),
    (3, (5011, 5012, 5014, 5013)),
    (5, (5126, 5127, 5128, 5129)),
    (6, (5019, 5632, 343, 5022)),
    (8, (5028, 5029, 5027, 5030)),
    (11, (5059, 5062, 5063, 5064)),
    (14, (5075, 5076, 5074, 5077)),
    (25, (5040, 5041, 5042, 5043)),
    (32, (5142, 5143, 5144, 5145)),
)


def synthetic_match(match_id=-101, *, reference_index=None, missing=False):
    """Deterministic invented gameplay, without player identities or source URLs."""
    candidate = {"match_id": match_id, "duration": 4920, "avg_rank_tier": 15,
                 "start_time": FIXTURE_NOW - (reference_index or 0) * 3600}
    players = []
    for index, (hero, skills) in enumerate(_HERO_SKILLS):
        item = 116 if index == 0 else 151
        sequence = [skills[i] for i in (0, 1, 0, 1, 0, 3, 0, 1, 2, 2, 2, 3)]
        if reference_index is None and index == 0:
            item = 151  # Held-out purchase, common only on other synthetic heroes.
            sequence[0] = skills[2]
        player = {
            "heroId": hero, "isRadiant": index < 5, "steamAccount": {"seasonRank": 15},
            "kills": 9 + index, "deaths": 8 + index, "assists": 12 + index,
            "dotaPlus": {"level": 4},
            **{f"item{slot}Id": value for slot, value in
               enumerate((item, 1, 112, 108, None, None))},
            "abilities": [{"abilityId": ability, "time": pick * 90, "isTalent": False}
                          for pick, ability in enumerate(sequence)],
            "stats": {"actionsPerMinute": [45, 50, 55],
                      "itemPurchases": [{"itemId": item, "time": 1200}],
                      "deathEvents": []},
        }
        if reference_index is None and index == 5 and not missing:
            player["item4Id"] = 133
            player["stats"]["itemPurchases"].append({"itemId": 133, "time": 4500})
            player["stats"]["deathEvents"] = [
                {"time": 4535, "timeDead": 90, "isDieBack": False},
            ]
        if missing and index == 0:
            player.pop("abilities")
            player["stats"].pop("itemPurchases")
        players.append(player)
    raw = {"gameMode": "ALL_PICK_RANKED", "players": players}
    od = {"patch": 1, "duration": candidate["duration"], "radiant_score": 55,
          "dire_score": 67, "players": [{"leaver_status": 0} for _ in players]}
    return candidate, raw, od


def _synthetic_evidence(matches):
    """Fit the production math on an isolated in-memory synthetic reference.

    Older reporter versions can still render baseline examples without the
    optional evidence API. Unexpected errors are not hidden by this fallback.
    """
    novelty = getattr(scheduled, "reporter_novelty", None)
    if novelty is None or "evidence" not in inspect.signature(scheduled.payload).parameters:
        return [None] * len(matches)
    with closing(sqlite3.connect(":memory:")) as conn:
        store = novelty.ReferenceStore(conn)
        store.begin_pass(FIXTURE_NOW)
        for index in range(1, 41):
            store.observe_and_score(*synthetic_match(-1000 - index, reference_index=index))
        store.begin_pass(FIXTURE_NOW)
        results = [store.observe_and_score(*matches[0])]
    if len(matches) > 1:
        with closing(sqlite3.connect(":memory:")) as conn:
            cold = novelty.ReferenceStore(conn)
            cold.begin_pass(FIXTURE_NOW)
            results.append(cold.observe_and_score(*matches[1]))
    for result in results:
        result["reference"]["population"] = "generated synthetic example matches"
        result["reference"]["synthetic"] = True
    return results


def build_examples(count=2, *, emojis=None):
    """Return complete production-shaped payload previews, with honest labels."""
    if type(count) is not int or count not in (1, 2):
        raise ValueError("Choose one or two example threads")
    matches = [synthetic_match(EXAMPLE_IDS[0]), synthetic_match(EXAMPLE_IDS[1], missing=True)]
    evidence = _synthetic_evidence(matches[:count])
    specs = []
    for index, (match, proof) in enumerate(zip(matches[:count], evidence), 1):
        kwargs = {"evidence": proof} if proof is not None else {}
        spec = scheduled.payload(*match, emojis or {}, **kwargs)
        # Compatibility wrappers may omit optional evidence, including its
        # synthetic flag. An image must carry the same honest label as its embed.
        for stage, team in zip(("radiant", "dire"), spec["teams"]):
            model = spec.get("cards", {}).get(stage)
            if model and not model.get("synthetic"):
                from . import card_images
                model["synthetic"] = True
                model["reference"]["population"] = "generated synthetic example matches"
                card = card_images.render_team_card(model)
                manifest = scheduled.png_manifest(card.png_bytes, card.filename, card.description)
                if team.get("flags", 0) & (1 << 15):
                    item = team["components"][0]["components"][1]["items"][0]
                    item["media"] = {"url": "attachment://" + manifest["filename"]}
                    item["description"] = manifest["description"]
                else:
                    team["embeds"][0]["image"] = {"url": "attachment://" + manifest["filename"]}
                team["attachments"] = [scheduled.attachment_metadata(manifest)]
                team["_files"] = [manifest]
                spec.uploads[stage] = {manifest["filename"]: card.png_bytes}
        label = "Cold start and missing evidence"
        if index == 1:
            label = "Scored build evidence" if proof is not None else "Build and event receipts"
        spec["example"] = {"fixture_set": FIXTURE_SET, "synthetic": True, "number": index}
        if "build_evidence" in spec:
            spec["build_evidence"]["reference"].update(
                population="generated synthetic example matches", synthetic=True)
        spec["thread_name"] = f"EXAMPLE {index} (synthetic) - {label}"
        parent = spec["parent"]["embeds"][0]
        parent["title"] = f"🧪 EXAMPLE {index} · Synthetic Herald report"
        parent["description"] = (
            f"{label}. Invented match and reference data; two team images in the thread."
        )
        for field in parent.get("fields", []):
            if field["name"] == "📅 Date":
                field["value"] = "Synthetic timeline (fixed fixture)"
            if field["name"] == "Reference population":
                if proof is None:
                    field["value"] = "Synthetic · did not calculate reference scores."
                else:
                    field["value"] = (
                        "Synthetic · 40 generated matches · invented patch 1 · target held out."
                        if index == 1 else
                        "Synthetic · 0 matches. Unscored does not mean normal; missing logs stay unavailable."
                    )
        for team in spec["teams"]:
            if team.get("flags", 0) & (1 << 15):
                nodes = team["components"][0]["components"]
                nodes[0]["content"] = "## 🧪 EXAMPLE · " + nodes[0]["content"].removeprefix("## ")
                nodes[2]["content"] = "-# SYNTHETIC EXAMPLE · generated team image · not a quality score"
            else:
                team["embeds"][0]["title"] = "🧪 EXAMPLE · " + team["embeds"][0]["title"]
        for message in (spec["parent"], *spec["teams"]):
            message["allowed_mentions"] = {"parse": []}
            for embed in message.get("embeds", []):
                embed.pop("url", None)  # No synthetic ID may point to a real match service.
                embed["footer"] = {"text": "SYNTHETIC EXAMPLE · invented data; not a quality score"}
            scheduled.check_message(message)
        specs.append(spec)
    return specs


def _channel_id(value):
    if not re.fullmatch(r"[1-9][0-9]{0,19}", value) or int(value) >= 2**64:
        raise ValueError("--channel must be the explicit numeric Discord text-channel ID")
    return value


def _read_meta(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables not in (_TABLES, _TABLES | {_UPLOAD_TABLE}):
        raise ValueError("Refusing a non-example database; choose a dedicated example receipt file")
    rows = conn.execute("SELECT data FROM example_meta WHERE id=1").fetchall()
    meta = json.loads(rows[0][0]) if len(rows) == 1 else {}
    if meta.get("format") != LEDGER_FORMAT or meta.get("fixture_set") != FIXTURE_SET:
        raise ValueError("Unrecognized example receipt format; preserve it for manual review")
    return meta


def validate_receipt_path(value, channel):
    """Reject production paths/formats before opening any database for writing."""
    if value == ":memory:":
        raise ValueError("Example delivery needs a durable receipt file")
    path = Path(value).expanduser().resolve()
    reserved = {Path("herald-reports.db").resolve(),
                Path(os.environ.get("HERALD_REPORT_DB", "herald-reports.db")).expanduser().resolve()}
    if path in reserved:
        raise ValueError("The production report ledger cannot be used for examples")
    if path.exists():
        # Immutable read avoids journal/shared-memory side effects on a foreign DB.
        # This workflow uses rollback journals; require operator review for WAL files.
        if Path(str(path) + "-wal").exists():
            raise ValueError("Receipt file has a WAL sidecar; stop its writer and review before use")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            meta = _read_meta(conn)
            if meta.get("channel") != channel:
                raise ValueError("Example receipt file belongs to a different channel")
    elif not path.parent.is_dir():
        raise ValueError("Create the private receipt directory before sending examples")
    return path


class ExampleReceipts(scheduled.PendingUploads):
    """Minimal production-deliver adapter; never creates production ledger tables."""
    upload_table = _UPLOAD_TABLE

    def __init__(self, path, channel):
        path = validate_receipt_path(str(path), channel)
        self.channel = _channel_id(channel)
        self.conn = sqlite3.connect(path)
        try:
            if not self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                with self.conn:
                    self.conn.execute("CREATE TABLE example_meta (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
                    self.conn.execute("CREATE TABLE example_deliveries (match_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
                    self.conn.execute("INSERT INTO example_meta VALUES (1, ?)", (json.dumps({
                        "format": LEDGER_FORMAT, "fixture_set": FIXTURE_SET, "channel": channel,
                        "bot_id": None}),))
            self.meta = _read_meta(self.conn)
            if self.meta["channel"] != channel:
                raise ValueError("Example receipt file belongs to a different channel")
            # Existing text-only example ledgers gain only their own upload spool.
            self.initialize_uploads()
        except BaseException:
            self.conn.close()
            raise

    def bind_bot(self, bot_id):
        if self.meta.get("bot_id") not in (None, bot_id):
            raise ValueError("Example receipt file belongs to a different bot")
        self.meta["bot_id"] = bot_id
        with self.conn:
            self.conn.execute("UPDATE example_meta SET data=? WHERE id=1", (json.dumps(self.meta),))

    def get(self, match_id):
        if match_id not in EXAMPLE_IDS:
            raise ValueError("Only the bounded synthetic example identities are permitted")
        row = self.conn.execute("SELECT data FROM example_deliveries WHERE match_id=?", (match_id,)).fetchone()
        return json.loads(row[0]) if row else {"match_id": match_id}

    def save(self, receipt):
        if receipt["match_id"] not in EXAMPLE_IDS or receipt.get("channel") != self.channel:
            raise ValueError("Example receipt identity or destination mismatch")
        if receipt.get("spec", {}).get("example", {}).get("fixture_set") != FIXTURE_SET:
            raise ValueError("Refusing a non-example payload in the example receipt file")
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO example_deliveries VALUES (?, ?)",
                              (receipt["match_id"], json.dumps(receipt)))

    def finish(self, receipt):
        """Keep unverified example bytes for reconciliation, including deletions."""
        if receipt.get("verified"):
            super().finish(receipt)
        else:
            self.save(receipt)

    def clear_uploads(self, match_id):
        if self.get(match_id).get("verified"):
            super().clear_uploads(match_id)


def existing_application_emojis(api):
    """Read only the authenticated app's current inventory; unavailable means text.

    This optional live embellishment never creates or changes an emoji. Invalid
    identifiers cannot influence a request path or introduce mention markup.
    """
    try:
        application = api.request("GET", "/oauth2/applications/@me")
        app_id = application.get("id") if isinstance(application, dict) else None
        if (not isinstance(app_id, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", app_id)
                or int(app_id) >= 2**64):
            raise ValueError("application identity unavailable")
        inventory = api.request("GET", f"/applications/{app_id}/emojis")
        rows = inventory.get("items") if isinstance(inventory, dict) else None
        if not isinstance(rows, list):
            raise ValueError("application emoji inventory unavailable")
        emojis = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("available") is False:
                continue
            name, emoji_id = row.get("name"), row.get("id")
            if (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_]{2,32}", name)
                    and isinstance(emoji_id, str)
                    and re.fullmatch(r"[1-9][0-9]{0,19}", emoji_id)
                    and int(emoji_id) < 2**64):
                emojis[name] = emoji_id
        return emojis
    except (httpx.HTTPError, scheduled.DefiniteRejection, RuntimeError, ValueError):
        log.warning("Existing application emojis unavailable; using text names")
        return {}


def send_examples(api, ledger, specs, channel, *, use_existing_emojis=False):
    """One bounded send through production delivery; injectable for offline tests.

    Explicit live callers may rebuild these fixture payloads with the current
    application inventory. Delivery still resumes immutable saved specs first.
    """
    if _channel_id(channel) != ledger.channel:
        raise ValueError("Example destination does not match its receipt file")
    me = api.request("GET", "/users/@me")
    target = api.request("GET", f"/channels/{channel}")
    if not me or not me.get("bot") or not me.get("id"):
        raise ValueError("Example delivery requires an authenticated Discord bot")
    if not target or target.get("id") != channel or target.get("type") != 0 or not target.get("guild_id"):
        raise ValueError("Examples require the exact requested Discord guild text channel")
    ledger.bind_bot(me["id"])
    if use_existing_emojis:
        specs = build_examples(len(specs), emojis=existing_application_emojis(api))
    results = []
    for spec in specs:
        receipt = scheduled.deliver(api, ledger, spec, channel, me["id"])
        results.append({"example": spec["example"]["number"], "verified": bool(receipt.get("verified")),
                        "deleted": bool(receipt.get("deleted")), "channel": channel,
                        **{key: receipt.get(key) for key in ("parent", "thread", "radiant", "dire")}})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--send", action="store_true", help="explicitly post once to Discord")
    mode.add_argument("--dry-run", action="store_true", help="print preview JSON; the default")
    parser.add_argument("--channel", help="explicit destination; required for --send; never read from .env")
    parser.add_argument("--count", type=int, choices=(1, 2), default=2, help="one or two threads (default: 2)")
    parser.add_argument("--receipts", default=DEFAULT_RECEIPTS,
                        help="dedicated durable example SQLite file (send mode only)")
    args = parser.parse_args(argv)
    if args.send and not args.channel:
        parser.error("--send requires an explicit --channel")
    if args.channel:
        try:
            _channel_id(args.channel)
        except ValueError as error:
            parser.error(str(error))
    specs = build_examples(args.count)
    if not args.send:
        print(json.dumps({"mode": "dry-run", "fixture_set": FIXTURE_SET, "synthetic": True,
                          "channel": args.channel, "thread_count": len(specs),
                          "message_count": 3 * len(specs), "payloads": specs}, indent=2))
        return
    try:
        path = validate_receipt_path(args.receipts, args.channel)
    except (ValueError, sqlite3.Error, OSError) as error:
        parser.error(str(error))
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token or not token.strip():
        parser.error("--send needs DISCORD_BOT_TOKEN from a secure runtime environment")
    with scheduled.exclusive_run(path):
        ledger = ExampleReceipts(path, args.channel)
        try:
            with httpx.Client(timeout=30) as client:
                results = send_examples(scheduled.DiscordHTTP(client, token), ledger, specs,
                                        args.channel, use_existing_emojis=True)
        finally:
            ledger.conn.close()
    print(json.dumps({"mode": "send", "synthetic": True, "receipts": results}, indent=2))


if __name__ == "__main__":
    main()
