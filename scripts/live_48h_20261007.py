#!/usr/bin/env python3
"""Local proposal: bounded real 48h reporter, separate prepare/send stages.

Nothing runs by import. Default is a secret-free offline plan. Live phases are
restricted to the authorized first-attempt GitHub runner and fixed destination.
The workflow must upload the prepared audit directory BEFORE invoking send.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

REPOSITORY = "clsandoval/herald-scraper-bot"
CHANNEL = "1392724276334825584"
GUILD = "1392724275538038826"
BOT = "1393107291741618359"
END = 1791342996  # 2026-10-07 03:16:36 UTC, pinned to the request.
START = END - 2 * 86400
MAX_CANDIDATES = 500
MAX_POSTS = 5
MAX_HISTORY_PAGES = 10
MAX_ICON_DOWNLOADS = 256
MAX_ICON_BYTES = 2_000_000
ICON_FETCH_SECONDS = 120
SCHEMA = "herald-real-48h-20261007-v1"


class Stop(RuntimeError):
    """Only deliberately secret-free messages may reach stdout/stderr."""


def plan():
    return {"schema": SCHEMA, "repository": REPOSITORY, "guild": GUILD,
            "channel": CHANNEL, "bot": BOT, "start_inclusive": START,
            "end_exclusive": END, "window_utc": [
                datetime.fromtimestamp(t, timezone.utc).isoformat() for t in (START, END)],
            "candidate_budget": MAX_CANDIDATES, "post_budget": MAX_POSTS,
            "selection": "First five eligible new matches in existing chronological discovery order; no ranking.",
            "history_page_budget": MAX_HISTORY_PAGES,
            "reference": "Fresh isolated reporter reference; this pass is unscored.",
            "secrets": ["DISCORD_BOT_TOKEN", "STRATZ_API_TOKEN"],
            "retry_policy": "Never rerun send. Reconcile persisted receipts and actual Discord messages first."}


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def runner_guard():
    if (os.environ.get("GITHUB_ACTIONS") != "true" or
            os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or
            os.environ.get("GITHUB_RUN_ATTEMPT") != "1" or
            os.environ.get("RUNNER_DEBUG") == "1"):
        raise Stop("Live phases require the fixed repository's first-attempt, non-debug GitHub runner.")


def identity(discord):
    me = discord.request("GET", "/users/@me")
    channel = discord.request("GET", f"/channels/{CHANNEL}")
    if not isinstance(me, dict) or me.get("id") != BOT or me.get("bot") is not True:
        raise Stop("Authenticated bot differs from the verified destination-bound bot.")
    if (not isinstance(channel, dict) or channel.get("id") != CHANNEL or
            channel.get("guild_id") != GUILD or channel.get("type") != 0):
        raise Stop("Discord target is not the exact authorized guild text channel.")


def message_match_ids(message):
    if message.get("author", {}).get("id") != BOT:
        return set()
    found = set()
    nonce = re.fullmatch(r"([1-9][0-9]*):parent", str(message.get("nonce", "")))
    if nonce:
        found.add(int(nonce[1]))
    for embed in message.get("embeds", []):
        if not isinstance(embed, dict):
            raise Stop("Discord history has an invalid embed shape.")
        for mid in re.findall(r"https://(?:www\.)?(?:stratz|opendota)\.com/matches/([1-9][0-9]*)",
                              str(embed.get("url", "")) + " " + str(embed.get("description", ""))):
            found.add(int(mid))
        for mid in re.findall(r"\bMatch\s+([1-9][0-9]*)\b", str(embed.get("description", ""))):
            found.add(int(mid))
    return found


def existing_matches(discord):
    """Require all parent history since window start, not a best-effort sample."""
    found, before, messages = set(), None, 0
    cutoff_id = ((START * 1000 - 1420070400000) << 22)
    for page in range(MAX_HISTORY_PAGES):
        route = f"/channels/{CHANNEL}/messages?limit=100" + (f"&before={before}" if before else "")
        rows = discord.request("GET", route)
        if not isinstance(rows, list) or len(rows) > 100:
            raise Stop("Could not establish complete Discord history coverage.")
        ids = []
        for row in rows:
            if (not isinstance(row, dict) or not str(row.get("id", "")).isdigit() or
                    row.get("channel_id") != CHANNEL):
                raise Stop("Discord history contains an unexpected message identity.")
            ids.append(int(row["id"]))
            found.update(message_match_ids(row))
        if ids != sorted(set(ids), reverse=True) or (before and ids and max(ids) >= before):
            raise Stop("Discord history pagination did not advance monotonically.")
        messages += len(rows)
        if len(rows) < 100 or min(ids, default=0) < cutoff_id:
            return found, {"complete": True, "pages": page + 1, "messages_examined": messages}
        before = min(ids)
    raise Stop("1,000-message bound reached before window start; stop rather than assume no duplicates.")


def authored_parent_matches(actual, expected):
    """Compare authored match identity and media, ignoring Discord proxy metadata."""
    if not isinstance(actual, dict) or actual.get("content", "") != expected.get("content", ""):
        return False
    observed, intended = actual.get("embeds"), expected.get("embeds")
    if not isinstance(observed, list) or not isinstance(intended, list) or len(observed) != len(intended):
        return False
    nested = {"author": ("name", "url", "icon_url"), "thumbnail": ("url",),
              "image": ("url",), "footer": ("text", "icon_url")}
    for seen, want in zip(observed, intended):
        if not isinstance(seen, dict):
            return False
        if any(seen.get(key) != want.get(key) for key in ("title", "description", "color", "url", "fields")):
            return False
        for key, fields in nested.items():
            a, e = seen.get(key), want.get(key)
            if a is None or e is None:
                if a != e:
                    return False
            elif not isinstance(a, dict) or not isinstance(e, dict) or any(a.get(k) != e.get(k) for k in fields):
                return False
    return True


def delivery_api(client, token, scheduled):
    """One-off strict parent recovery; historical core receipt behavior is untouched."""
    class StrictDiscord(scheduled.DiscordHTTP):
        parent_intent = None

        def begin_report(self, spec):
            self.parent_intent = spec["parent"]

        def request(self, method, path, **kwargs):
            # Every parent response used by deliver must identify the exact
            # intended match BEFORE thread creation or team-image writes.
            parent_route = re.fullmatch(rf"/channels/{CHANNEL}/messages/[0-9]+", path)
            create_parent = method == "POST" and path == f"/channels/{CHANNEL}/messages"
            create_thread = method == "POST" and re.fullmatch(rf"/channels/{CHANNEL}/messages/[0-9]+/threads", path)
            if create_thread:
                parent = self.request("GET", path.removesuffix("/threads"))
                if parent is None:
                    raise Stop("Parent disappeared before thread creation; stop without retry.")
            if create_parent and (self.parent_intent is None or not authored_parent_matches(kwargs.get("json"), self.parent_intent)):
                raise Stop("Parent POST differs from selected frozen intent.")
            result = super().request(method, path, **kwargs)
            if self.parent_intent is not None and result is not None and (create_parent or method == "GET" and parent_route):
                if (result.get("author", {}).get("id") != BOT or result.get("channel_id") != CHANNEL or
                        not authored_parent_matches(result, self.parent_intent)):
                    raise Stop("Parent identity/readback differs before thread/team writes; stop without retry.")
            return result

        def find_message(self, channel, bot_id, expected, nonce):
            if channel != CHANNEL or "embeds" not in expected:
                return super().find_message(channel, bot_id, expected, nonce)
            before = ""
            for _ in range(10):
                rows = self.request("GET", f"/channels/{channel}/messages?limit=100{before}")
                if not isinstance(rows, list):
                    raise Stop("Parent recovery history was unavailable.")
                for row in rows:
                    if row.get("author", {}).get("id") != bot_id:
                        continue
                    observed_nonce = row.get("nonce")
                    if observed_nonce is not None:
                        if str(observed_nonce) == nonce:
                            if not authored_parent_matches(row, expected):
                                raise Stop("Same-nonce parent has changed authored identity; reconcile without sending.")
                            return row
                    elif authored_parent_matches(row, expected):
                        return row
                if len(rows) < 100:
                    break
                before = "&before=" + rows[-1]["id"]
            return None
    return StrictDiscord(client, token)


def selected_icon_keys(selected, scheduled):
    """Only icons that appear in these real reports; no bulk asset refresh."""
    from herald import card_images
    keys = set()
    for candidate, raw, od, evidence in selected:
        for radiant in (True, False):
            card = card_images.build_team_card(candidate, raw, od, radiant=radiant, evidence=evidence)
            for player in card["players"]:
                if player["hero_id"]:
                    keys.add(f"hero_{player['hero_id']}")
                keys.update(f"item_{item}" for item in player["items"] if type(item) is int and item > 0)
                keys.update(f"ability_{ability}" for ability in player["skills"] or [] if type(ability) is int and ability > 0)
        # A headline may mention a sold/consumed item absent from final inventory.
        signals = scheduled.report_signals.summarize(raw, od, candidate["duration"])
        hook = scheduled._event_hook(signals)
        if hook and hook.get("item"):
            keys.add(f"item_{hook['item']}")
    return keys


def prepare_icons(selected, scheduled, fetch):
    """Optional, explicitly gated, unauthenticated selected-asset preparation."""
    import httpx
    from PIL import Image
    from herald import card_images
    root = Path(scheduled.__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("herald_selected_art_sources", root / "scripts/cache_card_icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = module.sources()  # Pure lookup-map construction, no fetch/main call.
    keys = selected_icon_keys(selected, scheduled)
    valid = set()
    for key in keys:
        path = card_images.ASSET_DIR / (key + ".png")
        if path.is_file():
            try:
                with Image.open(path) as existing:
                    if existing.format == "PNG" and 0 < existing.width <= 2048 and 0 < existing.height <= 2048:
                        existing.verify()
                        valid.add(key)
            except (OSError, ValueError):
                pass
    missing = sorted(keys - valid)
    eligible = [key for key in missing if key in sources]
    result = {"needed": len(keys), "already_bundled": len(keys) - len(missing),
              "missing_before": missing, "downloaded": [], "fallbacks": missing,
              "fetch_authorized": fetch}
    if fetch and len(eligible) > MAX_ICON_DOWNLOADS:
        result["blocked"] = "selected_icon_download_budget_exceeded"
        return result
    # Verified existing selected assets also establish parent-icon provenance.
    accepted = {key: sources[key] for key in valid if key in sources}
    if fetch:
        card_images.ASSET_DIR.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + ICON_FETCH_SECONDS
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            for key in eligible:
                if time.monotonic() >= deadline:
                    break
                url = sources[key]
                parsed = urlsplit(url)
                if (parsed.scheme != "https" or parsed.netloc != "cdn.cloudflare.steamstatic.com" or
                        not re.fullmatch(r"/apps/dota2/images/dota_react/(heroes|items|abilities)/[a-z0-9_]+\.png", parsed.path)
                        or parsed.query or parsed.fragment):
                    raise Stop("Artwork source is outside the pinned official public CDN path.")
                try:
                    with client.stream("GET", url) as response:
                        if response.status_code != 200:
                            continue
                        data = bytearray()
                        for part in response.iter_bytes():
                            data.extend(part)
                            if len(data) > MAX_ICON_BYTES:
                                raise ValueError("Oversized artwork")
                    with Image.open(BytesIO(data)) as source:
                        if source.width > 2048 or source.height > 2048:
                            continue
                        im = source.convert("RGB")
                        im.thumbnail((256, 160) if key.startswith("hero_") else (128, 128), Image.Resampling.LANCZOS)
                        im.save(card_images.ASSET_DIR / (key + ".png"), format="PNG", optimize=True)
                    accepted[key] = url
                    valid.add(key)
                    result["downloaded"].append(key)
                except (httpx.HTTPError, OSError, ValueError):
                    continue  # Actual ID placeholder remains visible; never invent art.
    if accepted:
        path = card_images.ASSET_DIR / "sources.json"
        recorded = json.loads(path.read_text()) if path.exists() else {}
        recorded.update(accepted)
        save_json(path, recorded)
    card_images._asset.cache_clear()
    result["fallbacks"] = sorted(keys - valid)
    return result


def prepare(audit, fetch_icons=False):
    import httpx
    from herald import api, scheduled
    if audit.exists() and any(audit.iterdir()):
        raise Stop("Preparation audit directory must be new and empty; never reset an earlier run.")
    audit.mkdir(parents=True, mode=0o700, exist_ok=True)
    state = {**plan(), "phase": "preparing", "run_id": os.environ["GITHUB_RUN_ID"],
             "source_sha": os.environ.get("REVIEWED_SOURCE_SHA"), "counts": {}, "matches": []}
    save_json(audit / "result.json", state)
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token.strip() or not os.environ.get("STRATZ_API_TOKEN", "").strip():
        raise Stop("Required repository secret is absent; no provider crawl or Discord send occurred.")
    ledger = scheduled.Receipts(audit / "receipts.sqlite3")
    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
            discord = scheduled.DiscordHTTP(client, token)
            identity(discord)
            seen, state["history"] = existing_matches(discord)
            app = discord.request("GET", "/oauth2/applications/@me")
            emojis = discord.request("GET", f"/applications/{app['id']}/emojis")
            emoji_map = {e["name"]: e["id"] for e in emojis.get("items", [])}
            candidates = scheduled.discover(client, END, backfill=2)
            state["discovery_complete"] = True
            counts = state["counts"] = {"found": len(candidates), "existing": 0, "hydrated": 0,
                "stratz_missing": 0, "ineligible": 0, "eligible": 0, "selected": 0, "posted": 0,
                "deferred_post_cap": 0, "truncated": False}
            candidates = [c for c in candidates if c["match_id"] not in seen]
            counts["existing"] = counts["found"] - len(candidates)
            save_json(audit / "result.json", state)
            if len(candidates) > MAX_CANDIDATES:
                raise Stop("Discovered candidate count exceeds the explicit provider budget; no posts were sent.")
            ledger.window(END, 2)
            ledger.novelty.begin_pass(END)
            selected = []
            for offset in range(0, len(candidates), 25):
                chunk = candidates[offset:offset + 25]
                matches = api.stratz_fetch_batch(client, [c["match_id"] for c in chunk], scheduled.REPORT_FIELDS, strict=True)
                if matches == "RATELIMIT":
                    raise Stop("STRATZ quota/availability blocked preparation; no posts were sent.")
                for candidate in chunk:
                    mid = candidate["match_id"]
                    raw = matches[mid]
                    if raw is None:
                        counts["stratz_missing"] += 1
                        state["matches"].append({"match_id": mid, "status": "stratz_missing"})
                        continue
                    if not isinstance(raw, dict) or type(raw.get("id")) is not int or raw["id"] != mid:
                        raise Stop("STRATZ detail does not identify the requested match; no posts were sent.")
                    response = client.get(f"{api.OPENDOTA_URL}/matches/{mid}", headers={"User-Agent": "herald-scraper-bot"})
                    response.raise_for_status()
                    od = response.json()
                    if not isinstance(od, dict) or od.get("error") or od.get("err"):
                        raise Stop("OpenDota match detail unavailable; no posts were sent.")
                    if type(od.get("match_id")) is not int or od["match_id"] != mid:
                        raise Stop("OpenDota detail does not identify the requested match; no posts were sent.")
                    counts["hydrated"] += 1
                    status = "ineligible"
                    if scheduled.eligible(candidate, raw, od):
                        counts["eligible"] += 1
                        status = "deferred_post_cap"
                        if len(selected) < MAX_POSTS:
                            evidence = ledger.novelty.observe_and_score(candidate, raw, od)
                            selected.append((candidate, raw, od, evidence))
                            status = "selected"
                    else:
                        counts["ineligible"] += 1
                    state["matches"].append({"match_id": mid, "status": status})
                    save_json(audit / "result.json", state)
                    time.sleep(1.1)
            counts["selected"] = len(selected)
            counts["deferred_post_cap"] = counts["eligible"] - len(selected)
            counts["truncated"] = counts["deferred_post_cap"] > 0
            state["icons"] = prepare_icons(selected, scheduled, fetch_icons)
            save_json(audit / "result.json", state)
            if state["icons"].get("blocked") or state["icons"].get("fallbacks"):
                raise Stop("Selected artwork is incomplete; exact missing IDs are in the sanitized audit. No posts were sent.")
            for candidate, raw, od, evidence in selected:
                spec = scheduled.payload(candidate, raw, od, emoji_map, evidence=evidence)
                receipt = {"match_id": candidate["match_id"], "channel": CHANNEL, "bot_id": BOT}
                ledger.prepare(receipt, spec)
            state["phase"] = "prepared_no_discord_writes"
            state["selected_match_ids"] = [c["match_id"] for c, *_ in selected]
            save_json(audit / "result.json", state)
    finally:
        try:
            # Also sanitize partial-preparation audits before the workflow's
            # always-upload step. Never retain an extra warm-up corpus.
            ledger.conn.execute("PRAGMA secure_delete=ON")
            ledger.conn.execute("DELETE FROM report_builds")
            ledger.conn.commit()
            ledger.conn.execute("VACUUM")
        finally:
            ledger.conn.close()
    state["prepared_db_sha256"] = hashlib.sha256((audit / "receipts.sqlite3").read_bytes()).hexdigest()
    save_json(audit / "result.json", state)
    print(json.dumps({key: state[key] for key in ("phase", "window_utc", "counts", "selected_match_ids", "icons")}))


def send(audit):
    import httpx
    from herald import scheduled
    state = json.loads((audit / "result.json").read_text())
    if (state.get("schema") != SCHEMA or state.get("phase") != "prepared_no_discord_writes" or
            state.get("run_id") != os.environ.get("GITHUB_RUN_ID") or
            state.get("channel") != CHANNEL or state.get("guild") != GUILD or state.get("bot") != BOT or
            state.get("start_inclusive") != START or state.get("end_exclusive") != END):
        raise Stop("Send requires this run's unchanged prepared manifest.")
    if not os.environ.get("PREPARED_ARTIFACT_ID", "").isdigit():
        raise Stop("Prepared artifact upload must succeed before any Discord send.")
    if hashlib.sha256((audit / "receipts.sqlite3").read_bytes()).hexdigest() != state["prepared_db_sha256"]:
        raise Stop("Prepared receipt database changed after its recorded digest.")
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token.strip():
        raise Stop("Required repository Discord secret is absent.")
    state["phase"] = "sending_do_not_retry"
    state["prepared_artifact_id"] = os.environ["PREPARED_ARTIFACT_ID"]
    save_json(audit / "result.json", state)
    with scheduled.exclusive_run(audit / "receipts.sqlite3"):
        ledger = scheduled.Receipts(audit / "receipts.sqlite3")
        try:
            pending = list(ledger.pending())
            if sorted(r["match_id"] for r in pending) != sorted(state["selected_match_ids"]) or len(pending) > MAX_POSTS:
                raise Stop("Prepared report identities/count differ from the frozen manifest.")
            by_match = {r["match_id"]: r for r in pending}
            pending = [by_match[mid] for mid in state["selected_match_ids"]]
            with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
                discord = delivery_api(client, token, scheduled)
                identity(discord)
                seen, state["send_history"] = existing_matches(discord)
                if seen.intersection(state["selected_match_ids"]):
                    raise Stop("A selected match was posted after preparation; reconcile before any sends.")
                state["receipts"] = []
                for receipt in pending:
                    discord.begin_report(receipt["spec"])
                    result = scheduled.deliver(discord, ledger, receipt["spec"], CHANNEL, BOT)
                    if not result.get("verified") or result.get("deleted"):
                        raise Stop("Delivery did not produce a verified receipt; stop without retry.")
                    parent = discord.request("GET", f"/channels/{CHANNEL}/messages/{result['parent']}")
                    if not authored_parent_matches(parent, receipt["spec"]["parent"]):
                        raise Stop("Parent embed readback differs from the frozen report.")
                    state["receipts"].append({key: result[key] for key in
                        ("match_id", "channel", "bot_id", "parent", "thread", "radiant", "dire", "verified", "verified_at")})
                    state["counts"]["posted"] += 1
                    save_json(audit / "result.json", state)
                ledger.finish_window()
                state["phase"] = "verified_complete_with_post_cap"
                save_json(audit / "result.json", state)
        finally:
            ledger.conn.close()
    print(json.dumps({key: state[key] for key in ("phase", "window_utc", "counts", "receipts")}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("plan", "prepare", "send"), nargs="?", default="plan")
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--fetch-selected-icons", action="store_true")
    args = parser.parse_args(argv)
    if args.phase == "plan":
        print(json.dumps(plan(), indent=2))
        return 0
    try:
        runner_guard()
        if args.audit_dir is None:
            raise Stop("An isolated audit directory is required.")
        logging.disable(logging.CRITICAL)  # Do not print raw provider exception bodies.
        if args.phase == "prepare":
            prepare(args.audit_dir, args.fetch_selected_icons)
        else:
            if args.fetch_selected_icons:
                raise Stop("Send never fetches or changes artwork.")
            send(args.audit_dir)
        return 0
    except Stop as exc:
        print(str(exc), file=sys.stderr)
    except Exception as exc:
        # Do not expose raw response bodies, URLs with query strings, or secrets.
        print(f"{type(exc).__name__}: phase stopped; inspect sanitized audit and do not retry send.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
