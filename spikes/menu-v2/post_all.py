"""Post the full mockup suite to test-server #replays.

One intro hub message + one thread per approach (its messages in order) +
the definitive-plan message. Usage:

    python post_all.py            # post everything
    python post_all.py a2 a5      # post only these approaches (repost/iterate)

Records posted message/thread ids to out/posted.json so a re-run can be cleaned.
"""

import asyncio
import importlib
import json
import os
import sys

import aiohttp

import render
from post import REPLAYS_CHANNEL, create_thread, post_v2

APPROACHES = [
    ("a4_board", "🎛️ The Match Board v2", "one message IS the UI, glance rows"),
]

INTRO = [{"type": 17, "accent_color": 0x3BA55D, "components": [
    {"type": 10, "content": "## 📋 Menu spike v2 — Browser vs Board, glance-row edition"},
    {"type": 10, "content": (
        "Two finalists, rebuilt around one rule: **every row shows hero icon + "
        "K/D/A + item icons on the same line.** Real matches from today. "
        "Controls still visual-only — we're iterating on feel."
    )},
]}]


async def post_approach(session, key, title, desc):
    mod = importlib.import_module(f"approaches.{key}")
    msgs = mod.build()
    thread = await create_thread(session, REPLAYS_CHANNEL, title)
    posted = []
    for i, m in enumerate(msgs):
        render.check(m["components"], f"{key}[{i}]")
        r = await post_v2(session, thread["id"], m["components"], files=m.get("files") or None)
        posted.append(r["id"])
        await asyncio.sleep(0.7)
    print(f"{key}: thread {thread['id']}, {len(posted)} messages")
    return {"thread": thread["id"], "messages": posted, "title": title}


async def main(only=None):
    record = {}
    async with aiohttp.ClientSession() as s:
        if not only:
            intro = await post_v2(s, REPLAYS_CHANNEL, INTRO)
            record["intro"] = intro["id"]
            print("intro:", intro["id"])
        for key, title, desc in APPROACHES:
            if only and key.split("_")[0] not in only and key not in only:
                continue
            try:
                record[key] = await post_approach(s, key, title, desc)
            except Exception as e:
                print(f"FAILED {key}: {e}")
                record[key] = {"error": str(e)[:500]}
            await asyncio.sleep(1.0)
    os.makedirs("out", exist_ok=True)
    prev = json.load(open("out/posted.json")) if os.path.exists("out/posted.json") else {}
    prev.update(record)
    json.dump(prev, open("out/posted.json", "w"), indent=1)
    fails = [k for k, v in record.items() if isinstance(v, dict) and "error" in v]
    print(f"done. failures: {fails or 'none'}")


if __name__ == "__main__":
    asyncio.run(main(set(sys.argv[1:]) or None))
