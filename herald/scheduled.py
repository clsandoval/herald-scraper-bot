"""Slow, opt-in match reports. Fixed legacy selection; no LLM calls.

Importing this module performs no network I/O. SQLite receipts survive interrupted threads.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import hashlib
import re
import logging
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import unquote, urlsplit

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
    """A match overview plus two deterministic icon-first PNG team cards.

    Old JSON-only receipts still resume their exact saved embeds; new reports
    save rendered images before sending. No menu ranking or provider call.
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
    def hero_label(index):
        hero = raw["players"][index]["heroId"]
        icon = render.application_emoji("h_" + render.hero_short(hero), emojis)
        return " ".join(filter(None, (icon, render.hero_name(hero))))

    cues = []
    # Only the strongest supported item and skill receipts belong in the
    # overview. Full inventories, twelve-pick sequences and support details are
    # already in the PNGs and immutable evidence; do not repeat them as text.
    for kind in ("items", "skills"):
        index = reporter_novelty.best_player(evidence, kind)
        if index is None:
            continue
        entry = evidence[kind][index]
        receipt = entry["receipts"][0]
        if kind == "items":
            item = render.named_items([receipt["item_id"]], emojis)
            detail = f"{item} @{receipt['minute']}m · PMI {entry['score']:.1f}"
        else:
            hero = raw["players"][index]["heroId"]
            ability = report_signals.ability_name(receipt["ability_id"], hero)
            detail = f"pick {receipt['pick']}: {ability} · surprisal {entry['score']:.1f}"
        cues.append(render.clip(f"{hero_label(index)} · {detail}", 180))
    for cue in signals["match"]:
        if len(cues) < 2 and cue not in cues:
            cues.append(render.clip(cue, 180))
    for index, receipts in signals["players"].items():
        if len(cues) < 2 and receipts:
            cues.append(render.clip(f"{hero_label(index)} · {receipts[0]}", 180))
    ref = evidence["reference"]
    scored = any(entry.get("status") == "scored"
                 for kind in ("items", "skills") for entry in evidence.get(kind, {}).values())
    if scored:
        status = "Scored where supported"
    elif ref.get("patch") is None:
        status = "Unscored: reference unavailable"
    elif ref.get("matches", 0) < reporter_novelty.MIN_HERO_BUILDS:
        status = "Unscored: warming up"
    else:
        status = "Unscored: insufficient compatible evidence"
    reference = (f"Experimental long-Herald · {ref.get('matches', 0):,} matches · "
                 f"patch {ref.get('patch') or '?'} · {status}")
    parent_fields = [
        {"name": "⏱️ Duration", "value": f"{duration // 60}m {duration % 60}s", "inline": True},
        {"name": "⚔️ Kills", "value": kill_label, "inline": True},
        {"name": "🔎 Review cues", "value": "\n".join("• " + cue for cue in cues[:2]) or
         "No standout cue recorded.", "inline": False},
        {"name": "Reference population", "value": reference, "inline": False},
    ]
    parent = {"embeds": [{"title": "🏆 Herald Match Review", "description":
        f"Match {mid} · {date} UTC\n[OpenDota](https://www.opendota.com/matches/{mid}) · Team cards in thread",
        "color": 0xC8A03C, "url": f"https://stratz.com/matches/{mid}", "fields": parent_fields,
        "footer": {"text": "Observed data · unscored does not mean normal"}}],
        "allowed_mentions": {"parse": []}}
    # Render once. JSON stays small and portable; the exact PNG bytes live only
    # in this transient object until the durable upload store accepts them.
    from . import card_images
    messages, uploads, models = [], {}, {}
    for radiant, label, color in [(True, "RADIANT", 0x3BA55D), (False, "DIRE", 0xED4245)]:
        stage = label.lower()
        model = card_images.build_team_card(candidate, raw, opendota, radiant=radiant,
                                           evidence=evidence, synthetic=bool(
                                               evidence.get("reference", {}).get("synthetic")))
        card = card_images.render_team_card(model)
        manifest = png_manifest(card.png_bytes, card.filename, card.description)
        filename = manifest["filename"]
        messages.append({
            "flags": 1 << 15,
            "components": [{"type": 17, "accent_color": color, "components": [
                {"type": 10, "content": f"## {label} Team"},
                {"type": 12, "items": [{"media": {"url": "attachment://" + filename},
                                         "description": manifest["description"], "spoiler": False}]},
                {"type": 10, "content": "-# Team image · final items and first 12 observed picks · unscored ≠ normal"},
            ]}],
            "attachments": [attachment_metadata(manifest)],
            "_files": [manifest], "allowed_mentions": {"parse": []},
        })
        uploads[stage] = {filename: card.png_bytes}
        models[stage] = model
    for message in [parent, *messages]:
        check_message(message)
    return ReportSpec({"match_id": mid, "parent": parent,
                       "thread_name": f"Match {mid} - {date}", "teams": messages,
                       "cards": models, "build_evidence": json.loads(json.dumps(evidence))},
                      uploads=uploads)


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PENDING_UPLOAD_BYTES = 32 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ReportSpec(dict):
    """Serializable immutable intent plus ephemeral, exact renderer output.

    JSON serialization deliberately excludes uploads. Once delivery begins,
    their only durable home is PendingUploads, never the delivery-history JSON.
    """
    def __init__(self, *args, uploads=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.uploads = uploads or {}


def attachment_metadata(manifest):
    return {key: manifest[key] for key in ("id", "filename", "description")}


def png_manifest(data, filename, description):
    if not isinstance(data, bytes) or not data.startswith(PNG_SIGNATURE):
        raise ValueError("Report renderer must return PNG bytes")
    if not 0 < len(data) <= MAX_UPLOAD_BYTES:
        raise ValueError("Report PNG exceeds the bounded upload size")
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,150}\.png", filename):
        raise ValueError("Report PNG filename is invalid")
    digest = hashlib.sha256(data).hexdigest()
    # A stable hash descriptor survives signed CDN URL refreshes. The full
    # digest is also retained in the manifest and checked against fetched bytes.
    if not filename[:-4].endswith((digest[:12], digest[:16], digest)):
        filename = filename[:-4] + "-" + digest[:16] + ".png"
    manifest = {"id": 0, "filename": filename, "description": render.clip(description, 1024),
                "size": len(data), "sha256": digest, "content_type": "image/png"}
    return manifest


def _check_upload(data, manifest):
    if (not isinstance(data, bytes) or not data.startswith(PNG_SIGNATURE)
            or not 0 < len(data) <= MAX_UPLOAD_BYTES or len(data) != manifest["size"]
            or hashlib.sha256(data).hexdigest() != manifest["sha256"]):
        raise RuntimeError("Pending report attachment failed its byte-integrity check")


def check_message(message):
    """Validate our static report layouts; keep classic receipt compatibility."""
    if not message.get("flags", 0) & (1 << 15):
        return render.check_embeds(message)
    if any(key in message for key in ("content", "embeds", "sticker_ids", "poll")):
        raise ValueError("Components V2 report cannot contain legacy message fields")
    count, chars, filenames = 0, 0, []

    def walk(nodes):
        nonlocal count, chars
        for node in nodes:
            count += 1
            if node["type"] == 17:
                walk(node["components"])
            elif node["type"] == 10:
                chars += len(node["content"])
            elif node["type"] == 12:
                if not 1 <= len(node["items"]) <= 10:
                    raise ValueError("MediaGallery requires 1–10 media items")
                for item in node["items"]:
                    url = item["media"]["url"]
                    if not url.startswith("attachment://") or len(item.get("description", "")) > 1024:
                        raise ValueError("Report galleries require bounded uploaded image references")
                    filenames.append(url.removeprefix("attachment://"))
            else:
                raise ValueError("Unsupported scheduled-report component")
    walk(message.get("components", []))
    if not 1 <= count <= 40 or chars > 4000:
        raise ValueError("Report Components V2 count/text budget exceeded")
    if sorted(filenames) != sorted(m["filename"] for m in message.get("_files", [])):
        raise ValueError("Report gallery references do not match its attachment manifest")
    return chars


class PendingUploads:
    """Shared production/example upload spool, separate from immutable history.

    Rows are committed with the initial receipt before any Discord write. A
    global byte cap fails closed; pending retry material is never evicted.
    SQLite reuses freed pages, so repeated verified reports do not retain PNGs.
    """
    upload_table = "pending_uploads"

    def initialize_uploads(self):
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {self.upload_table} ("
                          "match_id INTEGER NOT NULL, stage TEXT NOT NULL, "
                          "filename TEXT NOT NULL, data BLOB NOT NULL, "
                          "PRIMARY KEY(match_id, stage, filename))")
        self.conn.commit()

    def prepare(self, receipt, spec):
        if "spec" in receipt:
            return  # Never rerender, replace or patch a previously frozen spec.
        frozen = json.loads(json.dumps(spec))
        if not isinstance(frozen.get("teams"), list) or len(frozen["teams"]) != 2:
            raise ValueError("A report requires exactly two team messages")
        if len(json.dumps(frozen).encode()) > 256 * 1024:
            raise ValueError("Report intent exceeds the bounded receipt size")
        uploads = getattr(spec, "uploads", {})
        rows = []
        for stage, expected in zip(("parent", "radiant", "dire"),
                                   (frozen["parent"], *frozen["teams"])):
            manifests = expected.get("_files", [])
            if len(manifests) > 1:
                raise ValueError("Each report stage supports at most one PNG")
            if expected.get("attachments", []) != [attachment_metadata(m) for m in manifests]:
                raise ValueError("Attachment metadata does not match its frozen manifest")
            for manifest in manifests:
                data = uploads.get(stage, {}).get(manifest["filename"])
                _check_upload(data, manifest)
                rows.append((receipt["match_id"], stage, manifest["filename"], data))
        used = self.conn.execute(
            f"SELECT coalesce(sum(length(data)), 0) FROM {self.upload_table}").fetchone()[0]
        if used + sum(len(row[3]) for row in rows) > MAX_PENDING_UPLOAD_BYTES:
            raise RuntimeError("Pending report attachments reached their storage cap; reconcile pending reports")
        with self.conn:
            self.conn.executemany(f"INSERT INTO {self.upload_table} VALUES (?, ?, ?, ?)", rows)
            receipt["spec"] = frozen
            self.save(receipt)

    def upload_files(self, match_id, stage, expected):
        files = []
        for manifest in expected.get("_files", []):
            row = self.conn.execute(f"SELECT data FROM {self.upload_table} "
                                    "WHERE match_id=? AND stage=? AND filename=?",
                                    (match_id, stage, manifest["filename"])).fetchone()
            data = bytes(row[0]) if row else None
            _check_upload(data, manifest)
            files.append((f"files[{manifest['id']}]",
                          (manifest["filename"], data, manifest["content_type"])))
        return files

    def finish(self, receipt):
        """Commit terminal state and PNG cleanup together, including on crashes."""
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.upload_table} WHERE match_id=?",
                              (receipt["match_id"],))
            self.save(receipt)

    def clear_uploads(self, match_id):
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.upload_table} WHERE match_id=?", (match_id,))


class Receipts(PendingUploads):
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS deliveries (match_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS pending_window (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
        self.conn.commit()
        self.initialize_uploads()
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


def _attachment_url(url, filename):
    """Accept only Discord attachment CDN endpoints; signed queries are opaque."""
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        parts = unquote(parsed.path).split("/")
        return (parsed.scheme == "https" and parsed.hostname in
                {"cdn.discordapp.com", "media.discordapp.net"}
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and not parsed.fragment and len(parts) == 5 and parts[1] == "attachments"
                and parts[2].isdigit() and parts[3].isdigit() and parts[4] == filename)
    except ValueError:
        return False


def _v2_attachments(actual, expected):
    """Match our static V2 tree and return refreshable attachment download URLs.

    Discord assigns component IDs and enriches media objects. Uploaded media
    may be absent from message.attachments; the gallery's attachment_id/URL then
    identifies it. Only present, intentional values are compared; generated IDs,
    proxy URLs, dimensions, thumbhashes and signed queries are not payload text.
    """
    if (not actual.get("flags", 0) & (1 << 15) or actual.get("content")
            or actual.get("embeds") or not expected.get("components")):
        return None
    manifests = {m["filename"]: m for m in expected.get("_files", [])}
    attachments = actual.get("attachments", [])
    by_name = {a.get("filename"): a for a in attachments}
    if len(by_name) != len(attachments) or not set(by_name) <= set(manifests):
        return None
    matched = {}

    def nodes_match(actual_nodes, expected_nodes):
        if not isinstance(actual_nodes, list) or len(actual_nodes) != len(expected_nodes):
            return False
        for a, e in zip(actual_nodes, expected_nodes):
            if a.get("type") != e.get("type"):
                return False
            if e["type"] == 17:
                if (a.get("accent_color") != e.get("accent_color")
                        or bool(a.get("spoiler", False)) != bool(e.get("spoiler", False))
                        or not nodes_match(a.get("components"), e["components"])):
                    return False
            elif e["type"] == 10:
                if a.get("content") != e.get("content"):
                    return False
            elif e["type"] == 12:
                items = a.get("items")
                if not isinstance(items, list) or len(items) != len(e["items"]):
                    return False
                for item, intent in zip(items, e["items"]):
                    if (item.get("description") != intent.get("description")
                            or bool(item.get("spoiler", False)) != bool(intent.get("spoiler", False))):
                        return False
                    filename = intent["media"]["url"].removeprefix("attachment://")
                    manifest = manifests.get(filename)
                    if not manifest or filename in matched:
                        return False
                    media = item.get("media") or {}
                    url, identity = media.get("url"), media.get("attachment_id")
                    attachment = by_name.get(filename)
                    if url == intent["media"]["url"]:
                        # Some responses retain the original attachment reference
                        # while enriching proxy/attachment metadata separately.
                        url = attachment.get("url") if attachment else media.get("proxy_url")
                    if identity is None and attachment:
                        identity = attachment.get("id")
                    if not _attachment_url(url, filename) or str(identity) != unquote(urlsplit(url).path).split("/")[3]:
                        return False
                    if media.get("content_type") not in (None, manifest["content_type"]):
                        return False
                    if attachment:
                        if (str(attachment.get("id")) != str(identity)
                                or any(attachment.get(key) != manifest[key]
                                       for key in ("filename", "description", "size", "content_type"))
                                or not _attachment_url(attachment.get("url"), filename)
                                or unquote(urlsplit(attachment["url"]).path) != unquote(urlsplit(url).path)):
                            return False
                        url = attachment["url"]  # Prefer freshly returned attachment metadata.
                    matched[filename] = {"url": url, "filename": filename}
            else:
                return False
        return True

    if not nodes_match(actual.get("components"), expected["components"]) or set(matched) != set(manifests):
        return None
    return [matched[m["filename"]] for m in expected.get("_files", [])]


class DiscordHTTP:
    def __init__(self, client, token):
        self.client = client
        self.headers = {"Authorization": "Bot " + token.strip()}

    def request(self, method, path, **kwargs):
        if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
                or any(c in path for c in ("\\", "\r", "\n", "#"))):
            raise ValueError("Discord API requires a relative API path")
        # Do not let a caller redirect credentials or override the fixed API host.
        if any(key in kwargs for key in ("headers", "auth", "follow_redirects")):
            raise ValueError("Discord authentication and redirect policy are fixed")
        if kwargs.get("files"):
            kwargs["data"] = {"payload_json": json.dumps(kwargs.pop("json"))}
        for _ in range(4):
            response = self.client.request(method, DISCORD_API + path, headers=self.headers,
                                           auth=None, follow_redirects=False, **kwargs)
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
                observed_nonce = row.get("nonce")
                if observed_nonce is not None:
                    if str(observed_nonce) == nonce:
                        return row  # Even a damaged same-nonce row must block a resend.
                elif same_message(row, expected):
                    return row  # Discord may omit an older nonce; compare exact intent.
            if len(rows) < 100:
                break
            before = "&before=" + rows[-1]["id"]
        return None

    def verify_attachments(self, actual, expected):
        """Verify exact CDN bytes without inheriting API auth, cookies or redirects."""
        manifests = expected.get("_files", [])
        attachments = (_v2_attachments(actual, expected) if expected.get("flags", 0) & (1 << 15)
                       else actual.get("attachments", []))
        if attachments is None:
            raise RuntimeError("Discord Components V2 did not match the intended report")
        if len(attachments) != len(manifests):
            raise RuntimeError("Discord attachment count did not match the intended report")
        for attachment, manifest in zip(attachments, manifests):
            if type(manifest.get("size")) is not int or not 0 < manifest["size"] <= MAX_UPLOAD_BYTES:
                raise RuntimeError("Report attachment manifest exceeds the bounded size")
            url = attachment.get("url")
            if not _attachment_url(url, manifest["filename"]):
                raise RuntimeError("Discord returned an unsafe attachment URL")
            # Construct a *fresh* Request instead of Client.get/build_request:
            # those merge client default auth/cookies. send(auth=None) also
            # disables client-level auth. Credentials never reach CDN/assets.
            request = httpx.Request("GET", url, headers={"Accept": "image/png"})
            response = self.client.send(request, auth=None, follow_redirects=False, stream=True)
            try:
                if response.status_code != 200:
                    raise RuntimeError("Discord attachment could not be verified")
                length = response.headers.get("content-length")
                if length is not None and int(length) != manifest["size"]:
                    raise RuntimeError("Discord attachment size did not match the intended PNG")
                size, digest = 0, hashlib.sha256()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > manifest["size"] or size > MAX_UPLOAD_BYTES:
                        raise RuntimeError("Discord attachment exceeded its expected size")
                    digest.update(chunk)
                if size != manifest["size"] or digest.hexdigest() != manifest["sha256"]:
                    raise RuntimeError("Discord attachment bytes did not match the intended PNG")
            finally:
                response.close()


def same_message(actual, expected):
    if expected.get("flags", 0) & (1 << 15):
        return _v2_attachments(actual, expected) is not None
    if actual.get("flags", 0) & (1 << 15):
        return False
    a, e = actual.get("embeds", []), expected.get("embeds", [])
    base = (actual.get("content", "") == expected.get("content", "") and bool(e)
            and len(a) == len(e) and all(
                x.get("title") == y.get("title") and x.get("description") == y.get("description")
                and x.get("fields", []) == y.get("fields", []) for x, y in zip(a, e)))
    if not base:
        return False
    manifests = expected.get("_files", [])
    if not manifests:
        # Old JSON-only receipts keep their historical comparison semantics.
        return not actual.get("attachments") and not expected.get("attachments")
    attachments = actual.get("attachments", [])
    if len(attachments) != len(manifests):
        return False
    for attachment, manifest in zip(attachments, manifests):
        if any(attachment.get(key) != manifest[key]
               for key in ("filename", "description", "size", "content_type")):
            return False
        if not _attachment_url(attachment.get("url"), manifest["filename"]):
            return False
    for actual_embed, expected_embed in zip(a, e):
        if any(actual_embed.get(key) != expected_embed.get(key) for key in ("color", "footer", "url")):
            return False
        expected_url = expected_embed.get("image", {}).get("url")
        actual_url = actual_embed.get("image", {}).get("url")
        matches = [item for item in attachments if expected_url == "attachment://" + item["filename"]]
        if not matches or not (actual_url == expected_url or any(
                _attachment_url(actual_url, item["filename"])
                and unquote(urlsplit(actual_url).path) == unquote(urlsplit(item["url"]).path)
                for item in matches)):
            return False
    return True


def deliver(api, ledger, spec, channel, bot_id):
    receipt = ledger.get(spec["match_id"])
    if receipt.get("channel") not in (None, channel):
        raise RuntimeError("Receipt belongs to another channel; use a separate receipt DB")
    if receipt.get("bot_id") not in (None, bot_id):
        raise RuntimeError("Receipt belongs to another bot; use the original bot")
    if receipt.get("verified") or receipt.get("deleted"):
        ledger.clear_uploads(spec["match_id"])
        return receipt
    receipt["channel"] = channel
    if "spec" not in receipt:
        receipt["bot_id"] = bot_id
    ledger.prepare(receipt, spec)
    spec = receipt["spec"]  # resume the exact original payload, even across code updates
    if not isinstance(spec.get("teams"), list) or len(spec["teams"]) != 2:
        raise RuntimeError("Saved report does not have exactly two team messages")
    ledger.save(receipt)

    def write(stage, path, body, files=None):
        receipt["inflight"] = stage
        ledger.save(receipt)
        try:
            kwargs = {"json": body}
            if files:
                kwargs["files"] = files
            result = api.request("POST", path, **kwargs)
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
                ledger.finish(receipt)
                raise RuntimeError("A report message was deleted; refusing to recreate it")
        else:
            found = api.find_message(destination, bot_id, expected, nonce)
            if not found:
                if receipt.get("inflight") == stage:
                    raise RuntimeError(f"Unresolved {stage} send; reconcile Discord receipt before retry")
                files = ledger.upload_files(spec["match_id"], stage, expected)
                body = {key: value for key, value in expected.items() if not key.startswith("_")}
                found = write(stage, f"/channels/{destination}/messages",
                              {**body, "nonce": nonce, "enforce_nonce": True}, files)
            receipt[stage] = found["id"]
            ledger.save(receipt)
        verified = api.request("GET", f"/channels/{destination}/messages/{receipt[stage]}")
        if (not verified or verified.get("author", {}).get("id") != bot_id
                or verified.get("channel_id") not in (None, destination)
                or verified.get("nonce") is not None and str(verified["nonce"]) != nonce
                or not same_message(verified, expected)):
            raise RuntimeError("Discord receipt did not match the intended report")
        if expected.get("_files"):
            api.verify_attachments(verified, expected)
        if receipt.get("inflight") == stage:
            receipt.pop("inflight", None)
        ledger.save(receipt)

    message("parent", channel, spec["parent"])
    if "bot_id" not in receipt:
        # Older receipts predate bot binding. Bind only after verifying the
        # saved parent author, so a wrong configured token cannot poison them.
        receipt["bot_id"] = bot_id
        ledger.save(receipt)
    if not receipt.get("thread"):
        parent = api.request("GET", f"/channels/{channel}/messages/{receipt['parent']}")
        thread = (parent or {}).get("thread")
        if not thread:
            if receipt.get("inflight") == "thread":
                raise RuntimeError("Unresolved thread creation; reconcile before retry")
            thread = write("thread", f"/channels/{channel}/messages/{receipt['parent']}/threads",
                           {"name": spec["thread_name"], "auto_archive_duration": 1440})
        receipt["thread"] = thread["id"]
        receipt.pop("inflight", None)
        ledger.save(receipt)
    for stage, team in zip(("radiant", "dire"), spec["teams"]):
        message(stage, receipt["thread"], team)
    receipt["verified"] = True
    receipt["verified_at"] = int(time.time())
    ledger.finish(receipt)
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
