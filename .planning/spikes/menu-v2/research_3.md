# Discord Components V2 (IS_COMPONENTS_V2, flag `1<<15` = 32768) — spec as of 2026-07-10

Docs moved: `discord.com/developers/docs/*` now 301-redirects to `https://docs.discord.com/developers/*`. Source of truth verified against https://docs.discord.com/developers/components/reference (raw: github.com/discord/discord-api-docs `developers/components/reference.mdx`, repo pushed 2026-07-09).

## 1. Component types (current, complete)
| Type | Name | Style | Usage |
|---|---|---|---|
| 1 | Action Row | Layout | Message |
| 2 | Button | Interactive | Message (in Action Row or as Section accessory) |
| 3 | String Select | Interactive | Message, Modal |
| 4 | Text Input | Interactive | Modal only |
| 5 | User Select | Interactive | Message, Modal |
| 6 | Role Select | Interactive | Message, Modal |
| 7 | Mentionable Select | Interactive | Message, Modal |
| 8 | Channel Select | Interactive | Message, Modal |
| 9 | Section | Layout | Message |
| 10 | Text Display | Content | Message, Modal |
| 11 | Thumbnail | Content | Message (only as Section `accessory`) |
| 12 | Media Gallery | Content | Message |
| 13 | File | Content | Message |
| 14 | Separator | Layout | Message |
| 17 | Container | Layout | Message |
| 18 | Label | Layout | Modal only (added 2025-08-25; replaces ActionRow+TextInput in modals, now deprecated) |
| 19 | File Upload | Interactive | Modal only (added 2025-10-15; 0–10 files) |
| 21 | Radio Group | Interactive | Modal only (added 2026-02-12) |
| 22 | Checkbox Group | Interactive | Modal only (added 2026-02-12) |
| 23 | Checkbox | Interactive | Modal only (added 2026-02-12) |
Types 15/16/20 unassigned in public docs. Every component: `type` + optional `id` (32-bit int, unique per message, auto-generated sequentially if omitted; `id: 0` treated as empty).

## 2. Exact limits
- **40 total components/message** (raised from 10 top-level/30 total on 2025-04-29; no top-level limit, no per-Container limit anymore). Official docs don't state nesting rules, but the count is *total* — nested components count. Legacy (no flag): 5 action rows max.
- **4000 chars combined across all component text** (Text Display `content` etc.). NOT in official reference — documented in discord.js guide, dpp.dev, docs.discord.food; enforced by API. Individual Text Display has no stated per-component limit.
- Action Row: up to 5 Buttons OR exactly 1 select (types 3/5/6/7/8).
- Button: `label` max 80 chars; `custom_id` 1–100; `url` max 512. Styles: 1 Primary/2 Secondary/3 Success/4 Danger (require custom_id), 5 Link (requires url, no custom_id, no interaction), 6 Premium (requires sku_id; no custom_id/label/url/emoji; no interaction).
- Selects: max 25 options (String Select); `min_values` 0–25 (default 1), `max_values` ≤25 (default 1); `placeholder` max 150; option `label`/`value`/`description` max 100 chars each.
- Section: `components` = 1–3 Text Display children; `accessory` = Button **or** Thumbnail (docs warn both lists may expand).
- Thumbnail/Media Gallery item: `media` (unfurled media item), `description` (alt text) max 1024 chars, `spoiler` bool (default false). Thumbnail: images only incl. GIF/WEBP; no video.
- Media Gallery: `items` = 1–10 media gallery items.
- Separator: `divider` bool (default true), `spacing` 1=small (default) | 2=large.
- Container: `components` (children: Action Row, Text Display, Section, Media Gallery, Separator, File — **no nested Containers**), `accent_color` optional nullable integer RGB `0x000000`–`0xFFFFFF`, `spoiler` bool.
- File component: `file` unfurled-media-item that **only** accepts `attachment://<filename>`; `spoiler`; `name`/`size` are response-only. One attachment per File component.
- `custom_id`: 1–100 chars, must be unique per message.
- Unfurled media item: only `url` is settable (`https://...` or `attachment://<filename>`); Discord populates proxy_url, width/height, placeholder (thumbhash), content_type, flags (IS_ANIMATED `1<<0`), attachment_id.

## 3. Selects/buttons inside a Container — YES (wrapped in an Action Row)
```json
{"flags": 32768, "components": [
  {"type": 17, "accent_color": 703487, "components": [
    {"type": 10, "content": "# You have encountered a wild coyote!"},
    {"type": 12, "items": [{"media": {"url": "https://example.com/coyote.webp"}}]},
    {"type": 10, "content": "What would you like to do?"},
    {"type": 1, "components": [
      {"type": 2, "custom_id": "pet_coyote", "label": "Pet it!", "style": 1},
      {"type": 2, "custom_id": "run_away", "label": "Run away!", "style": 4}]}
  ]}
]}
```
(Official docs example, verbatim structure.) A select works the same: Action Row with a single `{"type": 3, ...}` inside the container.

## 4. Attachments via attachment:// — multipart POST /channels/{id}/messages
`Content-Type: multipart/form-data`. Each file part `files[n]` needs `Content-Disposition: form-data; name="files[n]"; filename="..."`. The index `n` is the placeholder `id` in `attachments`. Per-file default limit 10 MiB (higher w/ Nitro/Boost; interactions expose `attachment_size_limit`). Max 10 attachments/message (general message limit, not restated in components docs).
```
--boundary
Content-Disposition: form-data; name="payload_json"
Content-Type: application/json

{"flags": 32768,
 "components": [
   {"type": 12, "items": [{"media": {"url": "attachment://myfilename.png"}, "description": "alt text"}]},
   {"type": 13, "file": {"url": "attachment://game.zip"}}],
 "attachments": [
   {"id": 0, "filename": "myfilename.png", "description": "Image of a cat"},
   {"id": 1, "filename": "game.zip"}]}
--boundary
Content-Disposition: form-data; name="files[0]"; filename="myfilename.png"
Content-Type: image/png

[image bytes]
--boundary
Content-Disposition: form-data; name="files[1]"; filename="game.zip"
Content-Type: application/zip

[file bytes]
--boundary--
```
On PATCH edits, only files listed in `attachments` are kept; omitted ones are removed. Webhook sends need `?with_components=true` or components are ignored.

## 5. Interaction handling
- Delivery is mutually exclusive: gateway `INTERACTION_CREATE` event (default for bots — herald bot will get this via discord.py) OR HTTP POST to a configured Interactions Endpoint URL.
- Must send initial response **within 3 seconds** or token invalidates; token then valid **15 minutes** for followups.
- Response types: 1 PONG, 4 CHANNEL_MESSAGE_WITH_SOURCE, 5 DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE, 6 DEFERRED_UPDATE_MESSAGE (component-only), 7 UPDATE_MESSAGE (component-only, edits the message the component is on), 8 AUTOCOMPLETE_RESULT, 9 MODAL (not for MODAL_SUBMIT), 12 LAUNCH_ACTIVITY.
- Callback `data.flags` may set: SUPPRESS_EMBEDS, EPHEMERAL (64), **IS_COMPONENTS_V2 (32768)**, IS_VOICE_MESSAGE, SUPPRESS_NOTIFICATIONS. Exception: with DEFERRED type 5, only EPHEMERAL is allowed — to make a deferred response componentized, set 32768 on `PATCH /webhooks/{app_id}/{token}/messages/@original`. Followups (`POST /webhooks/{app_id}/{token}`) also accept 32768 (5 followups max for user-installed apps).
- Received component interaction (type 3 MESSAGE_COMPONENT) `data` = `{custom_id, component_type, values?, resolved?}`. `custom_id` is 1–100 chars (set at creation). Component `id` fields also echo back.

## 6. What V2 cannot do (vs classic)
- `content`, `embeds`, `sticker_ids`, `poll`, `shared_client_theme` → 400 BAD REQUEST if provided with flag 32768 (Create Message docs, verbatim). No embeds at all — Container+accent_color is the substitute.
- Flag is one-way: once sent, cannot be removed by edit. When editing a message TO set the flag, previously-used `content`/`poll` must be reset to `null` and `embeds`/`sticker_ids` to `[]` or 400.
- Attachments don't render by default — must be surfaced via Media Gallery / Thumbnail / File components.
- Reactions still work normally (flag doesn't affect reactions).
- Mentions in Text Display DO ping, governed by top-level `allowed_mentions`; on edit, mention arrays are rebuilt from `components` text.
- No preview/hover embeds from links in Text Display text? Not documented — URLs in Text Display don't auto-unfurl into embeds (embeds are disabled).
- TTS/nonce unaffected. Voice-message flag mutually exclusive in practice.

## 7. Size limits recap with flag 32768
- 40 components total; 4000 chars total component text (vs 2000 content + 6000 embed chars classic); 10 attachments; 10 MiB/file default; overall request payload limit unchanged (JSON body ≤ Discord's standard limits).

## Sources
- https://docs.discord.com/developers/components/reference
- https://docs.discord.com/developers/components/using-message-components
- https://docs.discord.com/developers/reference#uploading-files
- https://docs.discord.com/developers/interactions/receiving-and-responding
- https://docs.discord.com/developers/change-log (2025-04-22 "Introducing New Components", 2025-04-29 "Raised Component Limits", 2025-08-25 Label, 2025-10-15 File Upload, 2026-02-12 Radio/Checkbox groups)
- 4000-char limit corroboration: https://discordjs.guide/legacy/popular-topics/display-components, https://dpp.dev/components_v2.html, https://docs.discord.food/resources/components