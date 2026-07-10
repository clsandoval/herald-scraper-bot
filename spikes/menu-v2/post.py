"""Raw Discord REST helpers for the menu spike: Components V2 + file attachments.

Token comes from DISCORD_BOT_TOKEN env (source scratchpad spike.env).
All posting targets the TEST server only (#replays).
"""

import json
import os

import aiohttp

API = "https://discord.com/api/v10"
FLAGS_V2 = 32768
REPLAYS_CHANNEL = 1392724352155254876  # Herald Replays (test) #replays


def _headers():
    return {"Authorization": f"Bot {os.environ['DISCORD_BOT_TOKEN']}"}


async def post_v2(session, channel_id, components, files=None):
    """POST a Components-V2 message. files: list of (filename, bytes) referenced
    as attachment://filename inside the components. Returns message JSON."""
    payload = {"flags": FLAGS_V2, "components": components}
    url = f"{API}/channels/{channel_id}/messages"
    if not files:
        async with session.post(url, headers={**_headers(), "Content-Type": "application/json"},
                                json=payload) as r:
            body = await r.text()
            if r.status not in (200, 201):
                raise RuntimeError(f"post failed {r.status}: {body[:800]}")
            return json.loads(body)

    payload["attachments"] = [{"id": i, "filename": name} for i, (name, _) in enumerate(files)]
    form = aiohttp.FormData()
    form.add_field("payload_json", json.dumps(payload), content_type="application/json")
    for i, (name, data) in enumerate(files):
        form.add_field(f"files[{i}]", data, filename=name, content_type="image/png")
    async with session.post(url, headers=_headers(), data=form) as r:
        body = await r.text()
        if r.status not in (200, 201):
            raise RuntimeError(f"post failed {r.status}: {body[:800]}")
        return json.loads(body)


async def create_thread(session, channel_id, name):
    url = f"{API}/channels/{channel_id}/threads"
    async with session.post(url, headers={**_headers(), "Content-Type": "application/json"},
                            json={"name": name, "auto_archive_duration": 1440, "type": 11}) as r:
        if r.status not in (200, 201):
            raise RuntimeError(f"thread failed {r.status}: {await r.text()}")
        return await r.json()


async def delete_message(session, channel_id, message_id):
    url = f"{API}/channels/{channel_id}/messages/{message_id}"
    async with session.delete(url, headers=_headers()) as r:
        return r.status == 204


def count_components(components):
    """Total components incl. nested + Section accessories (gallery items free)."""
    n = 0
    for c in components:
        n += 1
        n += count_components(c.get("components", []))
        if "accessory" in c:
            n += 1
    return n


if __name__ == "__main__":
    # Smoke test: chart-in-container round trip, then delete (channel stays clean).
    import asyncio

    from charts import networth_lead_png

    async def main():
        demo = [0, 800, 2500, 5200, 8000, 9500, 7100, 3000, -2800, -9600, -18000]
        png = networth_lead_png(demo, "SMOKE TEST — will self-delete")
        comps = [{"type": 17, "accent_color": 0x3BA55D, "components": [
            {"type": 10, "content": "## Smoke test\nattachment:// chart inside Container"},
            {"type": 12, "items": [{"media": {"url": "attachment://lead.png"}}]},
        ]}]
        async with aiohttp.ClientSession() as s:
            msg = await post_v2(s, REPLAYS_CHANNEL, comps, files=[("lead.png", png)])
            print("posted:", msg["id"])
            ok = await delete_message(s, REPLAYS_CHANNEL, msg["id"])
            print("deleted:", ok)
            assert ok

    asyncio.run(main())
