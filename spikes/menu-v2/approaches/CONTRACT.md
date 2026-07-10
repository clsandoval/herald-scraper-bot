# Mockup builder contract

You are building ONE static Discord Components-V2 mockup module for a menu-design
spike. It renders your assigned design (from the scratchpad `designs.json`) with
REAL Herald match data. It will be posted into one thread in the test server by
the orchestrator — you never post, you only build payload dicts.

## Output

Write `spikes/menu-v2/approaches/a{N}_{key}.py` exposing:

```python
def build() -> list[dict]:
    # each dict = one message for the thread, in posting order:
    # {"components": [...v2 component dicts...],
    #  "files": [("chart1.png", png_bytes), ...]}   # [] if none
```

3–6 messages max. First message should title the approach (## heading) with its
tagline so a scroller knows what they're looking at. Buttons/selects are
non-functional in this mockup (any custom_id, must be unique per message) — they
exist so the user can FEEL the layout. Represent your design's KEY screens
(hub/list + detail + one specialty screen), not every state.

## Shared libs (import from `spikes/menu-v2/`, run with repo `.venv/bin/python` cwd=spikes/menu-v2)

- `render.load_matches()` → 38 REAL matches (see fields in render.py) — newest
  first. Use REAL numbers everywhere; never invent data. Spice picks:
  8888295980 (PA 19 deaths), 8888293313 (118 kills, 46m), 8888322003 (91 kills/26m).
- `render.hero_name/hero_img/hero_icon/item_name/item_img/hero_emoji/item_emoji/dur/factoid`
  Emoji helpers may return '' (seeding in progress) — ALWAYS fall back:
  `render.hero_emoji(h) or '•'` etc. Never let '' create double spaces.
- `render.check(components, where)` — call for EVERY message in a `__main__`
  self-check; it raises when over budget (40 components / 3600 chars TextDisplay text).
- `charts.networth_lead_png(leads, title)` / `charts.sparkline_png(leads)` —
  reference as `attachment://<name>.png` in MediaGallery/Thumbnail items and
  return the bytes in "files". Max ~2 charts per message.

## Hard V2 rules (verified live today)

- flag 32768 set by orchestrator; you produce only `components` lists.
- Container(17): children = ActionRow/TextDisplay/Section/MediaGallery/Separator/File.
  NO nested Containers. `accent_color` int.
- Section(9): 1–3 TextDisplay children + optional `accessory` (Thumbnail(11) or Button).
- MediaGallery(12): 1–10 items. Thumbnail only as Section accessory.
- ActionRow(1): ≤5 Buttons(2) OR exactly 1 select(3). String select ≤25 options.
- Button label ≤80 chars. Select option label/value/description ≤100 chars.
- Components count: every nested component AND Section accessories count toward 40.
- Select option text does NOT count toward the char pool (verified) — selects can be rich.
- Item images: `render.item_img(id)` full URLs; hero portraits `render.hero_img(id)`.
  The old `_sb.png` CDN variant is DEAD — never construct URLs by hand.

## Self-check (mandatory)

`__main__` block: call `build()`, run `render.check` per message, assert every
`attachment://` name has a matching file tuple, print
`OK a{N}: M messages, components=[...], chars=[...], files=N`.
Run it with `cd spikes/menu-v2 && ../../.venv/bin/python approaches/a{N}_{key}.py`
(add `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`).

## Tone

Plain-Discord-widget voice, zero AI vibes. Snark allowed where your design says so.
Real match IDs, real hero names, real death counts. Keep TextDisplay tight — the
40/3600 budget dies fast.
