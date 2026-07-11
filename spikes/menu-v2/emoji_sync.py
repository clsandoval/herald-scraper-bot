"""Seed application emojis for every hero + item that appears in the fixture.

Idempotent: lists existing app emojis first, uploads only missing ones,
serial with Retry-After handling (upload rate limit is undocumented).
Writes assets/emoji_map.json: {name: {name, id}}.
"""

import asyncio
import base64
import json
import os
import re

import aiohttp

import render

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://discord.com/api/v10"


def wanted():
    """(name, image_url) for all heroes + items that appear in herald.db."""
    import sqlite3
    c = sqlite3.connect(f"file:{HERE}/../../herald.db?mode=ro", uri=True)
    heroes = {r[0] for r in c.execute("SELECT DISTINCT hero_id FROM match_players")}
    items = {i for (blob,) in c.execute("SELECT DISTINCT items FROM match_players")
             for i in json.loads(blob)}
    out = []
    for h in sorted(heroes):
        out.append((f"h_{render.hero_short(h)}", render.hero_icon(h)))
    for i in sorted(items):
        key, img = render.item_key(i), render.item_img(i)
        if key and img and not key.startswith("recipe"):
            out.append((f"i_{key}", img))
    return [(re.sub(r"[^a-zA-Z0-9_]", "_", n)[:32], u) for n, u in out]


async def main():
    token = os.environ["DISCORD_BOT_TOKEN"].strip()
    h = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API}/applications/@me", headers=h) as r:
            app = (await r.json())["id"]
        async with s.get(f"{API}/applications/{app}/emojis", headers=h) as r:
            existing = {e["name"]: e for e in (await r.json())["items"]}
        print(f"existing: {len(existing)}")

        emap = {n: {"name": n, "id": e["id"]} for n, e in existing.items()}
        todo = [(n, u) for n, u in wanted() if n not in existing]
        print(f"to upload: {len(todo)}")
        ok = fail = 0
        for n, url in todo:
            async with s.get(url) as r:
                if r.status != 200:
                    print(f"skip {n}: image {r.status}")
                    fail += 1
                    continue
                img = await r.read()
            b64 = base64.b64encode(img).decode()
            while True:
                async with s.post(f"{API}/applications/{app}/emojis", headers=h,
                                  json={"name": n, "image": f"data:image/png;base64,{b64}"}) as r:
                    if r.status == 429:
                        wait = float((await r.json()).get("retry_after", 5))
                        print(f"429, sleeping {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    if r.status in (200, 201):
                        e = await r.json()
                        emap[n] = {"name": n, "id": e["id"]}
                        ok += 1
                    else:
                        print(f"fail {n}: {r.status} {(await r.text())[:120]}")
                        fail += 1
                    break
            await asyncio.sleep(0.35)  # ponytail: gentle serial pace, no docs on the real limit
        json.dump(emap, open(f"{HERE}/assets/emoji_map.json", "w"), indent=0)
        print(f"done: +{ok} uploaded, {fail} failed, map has {len(emap)}")


if __name__ == "__main__":
    asyncio.run(main())
