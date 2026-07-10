# Discord Application Emojis for Dota Item/Hero Icons — Findings (verified 2026-07-10)

## 1. Limits & Upload Endpoint

- **Limit: 2,000 emojis per application** — "An application can own up to 2000 emojis that can only be used by that app." (official docs: https://docs.discord.com/developers/resources/emoji — note `discord.com/developers/docs/...` now 301s to `docs.discord.com/developers/...`). 250-450 icons fits with >4x headroom.
- **Create**: `POST /applications/{application.id}/emojis` with JSON body:
  ```json
  { "name": "blink_dagger", "image": "data:image/png;base64,<BASE64>" }
  ```
  - `image` is the standard Image Data URI (`data:image/jpeg;base64,...`); content type must match actual bytes; JPEG/PNG/GIF supported (discord.py also enforces JPG/PNG/GIF only).
  - Docs describe the image param as "128x128 emoji graphic"; **max file size 256 KiB** (larger → 400 Bad Request).
  - **Name rules**: 2–32 chars, alphanumeric + underscores (colon-name), and **names must be unique within the application** (userdoccers: https://docs.discord.food/resources/emoji).
- **Other endpoints**: `GET /applications/{id}/emojis` (list), `GET .../emojis/{emoji.id}`, `PATCH .../emojis/{emoji.id}` (rename only — body `{"name": ...}`), `DELETE .../emojis/{emoji.id}`.
- **Rate limits**: NOT specifically documented for app-emoji routes. The infamous "emoji routes don't follow normal conventions, limited per-guild" warning (50/hr on `POST /guilds/{id}/emojis`) is written about **guild** emoji routes; app-emoji routes have no guild bucket. Practical guidance: upload serially, honor `Retry-After`/`retry_after` on 429, and treat the 250-450 upload as a one-time seeding job (minutes, not seconds). Do not assume 50/hr, but budget for it worst-case (~9h for 450) in the spike.

## 2. Usage Without USE_EXTERNAL_EMOJIS

- **Yes — explicitly documented**: "The `USE_EXTERNAL_EMOJIS` permission is not required to use app emojis." App emojis work in any guild/channel the bot can send messages in (they're not tied to any guild; no role-locking, never "managed/unavailable"). Only the owning app can use them.
- **Format string in message content**: `<:name:id>` static, `<a:name:id>` animated (e.g. `<:mmLol:216154654256398347>`) — same as guild emojis (https://docs.discord.com/developers/reference, Message Formatting table).
- This kills the classic gotchas: no need to share a guild with an emoji-hosting server, and no webhook/@everyone-role external-emoji weirdness for the bot's own app emojis.

## 3. Rendering in Components V2 / Select Options

- **TextDisplay (Components V2, type 10)**: `content` field is "Text that will be displayed similar to a message" — "all the regular markdown rules apply", including custom-emoji `<:name:id>` syntax. App emojis render inline there. (https://docs.discord.com/developers/components/reference)
- **String Select options**: each option has `emoji?` — a **partial emoji object** `{ "id": "...", "name": "...", "animated": false }` (structured field, not the `<:...>` string). App emoji IDs work here. Option `label`/`description` are plain text — no custom emoji markdown inside labels; use the `emoji` field instead.
- **Buttons**: same `emoji?` partial-emoji field.
- Also render in embeds (title/description/fields) and can be used by the app for reactions.

## 4. Practical Bulk-Upload Pipeline (items are 88x64 on the CDN)

1. Fetch icon: `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/items/{name}.png` (88x64) or heroes `.../heroes/{name}.png` (via OpenDota `constants/items` / `constants/heroes` `img` paths).
2. **Resize**: Discord scales emojis to fit; non-square uploads get letterboxed/squished depending on client. Safest: pad to square 128x128 on transparent canvas with Pillow (`ImageOps.pad(img, (128,128), color=(0,0,0,0))` after RGBA convert). 88x64 PNGs are far under 256 KiB — no compression needed.
3. **Name**: slugify to `[a-z0-9_]{2,32}`, e.g. item key `blink` → `blink`, hero `npc_dota_hero_anti_mage` → `anti_mage`. Prefix to avoid collisions with hero names vs item names if desired (`i_blink`, `h_axe`) — names must be unique app-wide.
4. Upload via discord.py **>= 2.5**: `await bot.create_application_emoji(name=..., image=bytes)`; list via `await bot.fetch_application_emojis()` (added in 2.5, PR Rapptz/discord.py#9891). Store `{slug: emoji_id}` mapping in DB/JSON so the SQL-answering path can substitute `<:blink:123...>` into responses.
5. Alternative manual path: Dev Portal → your app → Emojis tab supports drag-and-drop bulk upload through the UI.

## 5. Listing / Sync / Dedupe

- **Yes**: `GET /applications/{application.id}/emojis` returns `{ "items": [ <emoji objects> ] }` (note the `items` wrapper — unlike the guild list endpoint which returns a bare array). Each object has `id`, `name`, `animated`, `user` (uploader: bot user if via API). Sync strategy: fetch list, diff by `name`, upload only missing — idempotent seeding script.

## 6. Fallbacks & Verdict

- **Unicode-only**: zero-infra fallback (⚔️🗡️🛡️) but can't represent ~200 distinct items — loses the whole point.
- **Guild emojis**: 50 static/guild (base tier) — would need ~9 boosted servers plus USE_EXTERNAL_EMOJIS in the target server; strictly worse.
- **MediaGallery / attachment images per message**: renders icons big, not inline with text; costs an upload per message; fine for a single "hero portrait" hero-image but not for item lists.
- **Verdict**: **Application emojis are the clear winner** — 2,000-cap covers all ~450 icons 4x over, no guild permission needed, renders inline in plain content, embeds, and Components V2 TextDisplay, with a documented list endpoint for idempotent sync; the only unknown is the (undocumented) upload rate limit, so make the seeding script serial + 429-aware and run it once.

## Key sources
- https://docs.discord.com/developers/resources/emoji (app emoji endpoints, 2000 cap, 256 KiB, permission exemption)
- https://docs.discord.com/developers/reference (emoji format strings, image data URI)
- https://docs.discord.com/developers/components/reference (TextDisplay markdown, select/button `emoji` field)
- https://docs.discord.food/resources/emoji (name 2-32 + uniqueness, `items` list shape)
- https://github.com/Rapptz/discord.py/pull/9891 (discord.py 2.5 `create_application_emoji` / `fetch_application_emojis`)
- https://github.com/discord/discord-api-docs/discussions/3281 (guild-emoji 50/hr context — guild routes only)