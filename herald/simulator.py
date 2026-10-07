"""Offline Discord Components V2 laboratory backed by the production Board.

Run ``python -m herald.simulator``. It binds loopback only, creates disposable
synthetic SQLite archives, and never logs in to Discord or calls an API.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import json
import math
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

from . import board, ingest, render

ASSETS = Path(__file__).with_name("simulator_assets")
SCENARIOS = ("normal", "empty", "missing-icons", "long-text", "pruned", "error")


def synthetic_match(index=0, *, long_text=False):
    """Deterministic fabricated game: no account identifiers or network input."""
    heroes = [2, 5, 14, 8, 74, 11, 26, 44, 86, 93]
    item_sets = [[50, 1, 116, 145, 133, 112], [48, 102, 214, 218, 38, 36],
                 [116, 1, 119, 112, 29, 90], [50, 145, 147, 139, 135, 116]]
    if long_text:
        item_sets = [sorted(render._item_by_id, key=lambda i: len(render.item_name(i)),
                            reverse=True)[:6]]
    duration = 4567 + index * 173
    players = []
    ability_pools = {2: [5007, 5008, 5009, 5010], 5: [5126, 5127, 5128, 5129],
                     14: [5075, 5076, 5074, 5077], 8: [5028, 5029, 5027, 5030],
                     74: [5370, 5371, 5372], 11: [5059, 5062, 5063, 5064],
                     26: [5044, 5045, 5046, 5047], 44: [5190, 5191, 5192, 5193],
                     86: [5448, 5450, 7320, 5452], 93: [5494, 5495, 5496, 5497]}
    for slot, hid in enumerate(heroes):
        abilities = ability_pools[hid]
        items = item_sets[slot % len(item_sets)]
        skills = [abilities[i % len(abilities)] for i in [0, 1, 0, 2, 0, 3, 0, 1, 1, 1, 3, 2]] if abilities else []
        player = {"heroId": hid, "isRadiant": slot < 5,
                  "kills": 4 + ((slot * 7 + index) % 19),
                  "deaths": 4 + ((((slot + 5) % 10) * 7 + index) % 19),
                  "assists": 8 + slot * 2, "networth": 36000 - slot * 1700 + index * 50,
                  "goldPerMinute": 610 - slot * 21, "heroDamage": 38000 + slot * 2400,
                  "position": f"POSITION_{slot % 5 + 1}",
                  "dotaPlus": {"level": 30 if slot == 0 else 0},
                  "partyId": 1 if index % 3 == 0 and slot < 5 else None,
                  "steamAccount": {"seasonRank": 11 + index % 5},
                  "abilities": [{"abilityId": a, "isTalent": False, "time": 10 + pick * 70}
                                for pick, a in enumerate(skills)],
                  "stats": {"itemPurchases": [{"itemId": iid, "time": 140 + i * 515}
                                              for i, iid in enumerate(items)],
                            "actionsPerMinute": [120 + slot * 30],
                            "networthPerMinute": [600 + n * 420 for n in range(duration // 60)]}}
        if slot == 0:
            player["stats"]["itemUsed"] = [{"itemId": 116, "count": 0}]
        if slot == 6:
            player["stats"]["deathEvents"] = [
                {"time": 3600, "timeDead": 90, "goldFed": 1200, "isDieBack": True},
                {"time": 3900, "timeDead": 100, "goldFed": 1300, "isDieBack": True}]
        player.update({f"item{i}Id": iid for i, iid in enumerate(items)})
        players.append(player)
    return {"id": 9000000001 + index, "startDateTime": 1791158400 + index * 3600,
            "durationSeconds": duration, "didRadiantWin": index % 2 == 0,
            "gameMode": "ALL_PICK", "rank": 11 + index % 5, "bracket": 1,
            "radiantKills": [sum(p["kills"] for p in players[:5])],
            "direKills": [sum(p["kills"] for p in players[5:])],
            "radiantNetworthLeads": [int(math.sin(n / 7 + index) * 11000 + n * 90)
                                    for n in range(duration // 60 + 1)],
            "players": players}


def populate(path, scenario):
    conn = ingest.get_conn(str(path))
    if scenario != "empty":
        for index in range(12):
            raw = synthetic_match(index, long_text=scenario == "long-text")
            ingest.upsert_match(conn, raw, 11 + index % 5)
            notes = [{"hero_id": 2, "score": 9, "items": [
                [render.item_name(raw["players"][0]["item3Id"]), 28, 9],
                [render.item_name(raw["players"][0]["item4Id"]), 36, 8]]}]
            skills = [{"hero_id": 2, "score": 9, "picks": [["Berserker's Call", 7, 9]], "tag": "late opening pick"}]
            if scenario == "long-text":
                notes *= 20
                skills *= 20
            conn.execute("UPDATE matches SET weirdness=?, weird_notes=?, skill_weirdness=?, skill_notes=? WHERE match_id=?",
                         (9 if index == 0 else index / 3, json.dumps(notes), 9 if index == 0 else index / 4,
                          json.dumps(skills), raw["id"]))
        conn.commit()
    conn.close()


class Response:
    def __init__(self, interaction):
        self.interaction = interaction
        self.done = False

    def is_done(self):
        return self.done

    async def defer(self, **kwargs):
        self.done = True
        self.interaction.events.append("acknowledged")

    async def send_modal(self, modal):
        self.done = True
        self.interaction.modal = modal

    async def send_message(self, content, **kwargs):
        self.done = True
        self.interaction.message = content


class Interaction:
    def __init__(self):
        self.events = []
        self.response = Response(self)
        self.followup = SimpleNamespace(send=self.response.send_message)
        self.user = "offline-simulator"
        self.view = None
        self.modal = None
        self.message = None

    async def edit_original_response(self, *, view=None, **kwargs):
        self.view = view
        self.events.append("rendered")


class Simulator:
    """One browser session. Real callbacks, no Discord transport or token."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.paths = {}
        for scenario in SCENARIOS:
            path = self.directory / f"{scenario}.db"
            populate(path, scenario)
            self.paths[scenario] = path
        self.emoji_inventory = {p.stem: {"name": p.stem, "id": str(800000000000000001 + i)}
                                for i, p in enumerate(sorted((ASSETS / "icons").glob("*.png")))}
        self.emoji_images = {p.stem: "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
                             for p in (ASSETS / "icons").glob("*.png")}
        self.scenario = "normal"
        self.view = None
        self.modal = None
        self.revision = 0
        self.lock = asyncio.Lock()

    async def request(self, data):
        async with self.lock:
            action = data.get("action", "reset")
            if action == "reset":
                scenario = data.get("scenario", "normal")
                if scenario not in SCENARIOS:
                    raise ValueError("Unknown fixture scenario")
                self.scenario = scenario
                board.DB_PATH = str(self.paths[scenario])
                # Historical emoji IDs must not imply current application access.
                render._emoji = (self.emoji_inventory if scenario == "normal" else {})
                state = board.default_state()
                if data.get("focus"):
                    state.update(mode="focus", match=9000000001)
                if scenario == "pruned":
                    state.update(mode="focus", match=9999999999)
                self.view = await board.build_board(state)
                self.modal = None
                self.revision += 1
                if scenario == "error":
                    itx = Interaction()
                    await self.view.on_error(itx, RuntimeError("synthetic unavailable archive"), None)
                    return self.snapshot(message=itx.message, error=True)
                return self.snapshot()
            if self.view is None:
                raise ValueError("Reset the simulator before interacting")
            if data.get("revision") != self.revision:
                return self.snapshot(message="That simulator control is stale. The current menu is shown.")
            itx = Interaction()
            if action == "modal":
                if self.modal is None:
                    raise ValueError("No advanced search is open")
                values = data.get("values", {})
                for field in self.modal.children:
                    target = getattr(field, "component", field)
                    if hasattr(target, "_value"):
                        target._value = str(values.get(target.custom_id, ""))[:4000]
                await self.modal.on_submit(itx)
                self.modal = None
            elif action == "race":
                control = next((c for c in self.view.walk_children()
                                if getattr(c, "custom_id", None) == "mb_pn"), None)
                if control is None or control.disabled:
                    raise ValueError("Open the normal list before running the repeat-click probe")
                first, second = Interaction(), Interaction()
                await asyncio.gather(control.callback(first), control.callback(second))
                itx = second if second.view is not None else first
                itx.message = "Two overlapping Next callbacks completed against the same menu session."
                itx.events = first.events + second.events
            elif action == "component":
                cid = data.get("custom_id")
                control = next((c for c in self.view.walk_children()
                                if getattr(c, "custom_id", None) == cid), None)
                if control is None or getattr(control, "disabled", False):
                    raise ValueError("This control is unavailable")
                if isinstance(control, board.discord.ui.Select):
                    values = data.get("values", [])
                    allowed = {o.value for o in control.options}
                    if (not isinstance(values, list) or not all(v in allowed for v in values)
                            or not control.min_values <= len(values) <= control.max_values):
                        raise ValueError("Invalid select values")
                    control._values = values
                await control.callback(itx)
            else:
                raise ValueError("Unknown simulator action")
            if itx.view is not None:
                self.view = itx.view
                self.revision += 1
            if itx.modal is not None:
                self.modal = itx.modal
            return self.snapshot(message=itx.message, events=itx.events)

    def snapshot(self, **extra):
        components = self.view.to_components()
        count, chars = render.check(components, "offline simulator")
        payload = {"components": components, "files": {
            name: "data:image/png;base64," + base64.b64encode(content).decode()
            for name, content in self.view.files},
            "emojis": dict(self.emoji_images) if self.scenario == "normal" else {},
            "state": copy.deepcopy(self.view.st), "revision": self.revision,
            "scenario": self.scenario, "budget": {"components": count, "text": chars},
            "flags": 32768 | 64,
            "provenance": "Synthetic offline fixture; production Board.to_components(); Discord-style approximation, not live Discord.",
            **extra}
        if self.modal is not None:
            payload["modal"] = self.modal.to_dict()
        return payload


def serve(port=8766):
    with tempfile.TemporaryDirectory(prefix="herald-simulator-") as directory:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        async def create():
            return Simulator(directory)
        simulator = asyncio.run_coroutine_threadsafe(create(), loop).result()

        class Handler(BaseHTTPRequestHandler):
            def reply(self, content, content_type, status=200):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(content)

            def do_GET(self):
                name = self.path.split("?", 1)[0]
                if name == "/":
                    name = "/index.html"
                if name not in ("/index.html", "/app.js", "/style.css"):
                    return self.reply(b"Not found", "text/plain", 404)
                mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}
                file = ASSETS / name.lstrip("/")
                self.reply(file.read_bytes(), mime[file.suffix])

            def do_POST(self):
                if self.path != "/api":
                    return self.reply(b"Not found", "text/plain", 404)
                origin = self.headers.get("Origin")
                if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                    return self.reply(b"Origin denied", "text/plain", 403)
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 20000:
                    return self.reply(b"Invalid body", "text/plain", 400)
                try:
                    data = json.loads(self.rfile.read(length))
                    result = asyncio.run_coroutine_threadsafe(simulator.request(data), loop).result(timeout=60)
                    self.reply(json.dumps(result).encode(), "application/json")
                except Exception as exc:
                    self.reply(json.dumps({"error": True, "message": str(exc)}).encode(), "application/json", 400)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", port), Handler)
        print(f"Offline simulator: http://127.0.0.1:{port} (no Discord connection)", flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    serve(parser.parse_args().port)
