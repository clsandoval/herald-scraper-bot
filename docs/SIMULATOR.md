# Offline Discord laboratory

Run from a checkout with the locked dependencies installed:

```sh
uv run python -m herald.simulator
```

Open `http://127.0.0.1:8766` in your own browser. The server binds only loopback,
uses a disposable synthetic SQLite archive, and needs no tokens. It never starts
the Discord gateway, posts messages, changes application emojis, queries the live
archive, or calls OpenDota/Stratz. Closing the server removes the temporary data.
Use `--port 8767` if the default is occupied.

## What is exercised

- The real `Board.to_components()` wire payload, actual chart attachments, and
  actual select/button/modal callbacks, including ACK-before-work behavior.
- Item versus skill tabs, multi-sort, combined filters, pagination, dice,
  spoiler suppression, advanced validation, cancel/reopen, and stale controls.
- Deterministic populated, empty, pruned, unavailable, missing-icon and long-text
  scenarios. No real account identifiers are in the generated matches.
- A deliberate overlapping-Next probe invokes two production callbacks together.
  Ordinary preview clicks are gated during a pending request, so use this probe
  and the concurrency unit tests for race behavior rather than ordinary clicks.
- Real Discord component/text budgets displayed beside the preview.

The icon-capable fixture uses a clearly synthetic emoji inventory backed by
cached public Valve assets. It does not provision emojis. The missing-icons
fixture passes an empty inventory to the production renderer. The skill-order
sequences and corpus-relative scores are fabricated to exercise presentation,
not evidence about actual players or recommendations about builds.

## What is approximate

This is a Discord-style renderer, not Discord itself. Typography, exact pixel
spacing, select-menu behavior and responsive wrapping are approximations. It
cannot validate Discord gateway delivery, ephemeral permissions, CDN behavior,
mobile-client quirks or the official client’s final layout. A successful offline
check is not a live Discord check. V2 components and legacy reporter embeds must
remain separate messages; the latter have different budgets.

## Portable snapshot export

```sh
uv run python scripts/export_simulator.py /tmp/herald-preview
```

The export is a small static directory with embedded images and 19 captured
production payloads, including both menu tabs and the reporter’s classic embeds.
It can be served with a normal static-file server. Its sidebar explicitly labels
it a snapshot viewer: changing a snapshot, narrow layout, loading state, payload
inspection and selected navigation work locally. Filtering, arbitrary menu
commands and advanced submissions require the Python simulator above. The
export does not pretend to execute Python callbacks.

```sh
uv run pytest tests/test_simulator.py tests/test_menu_edges.py tests/test_discord_contracts.py
```

An optional repeatable screenshot runner is provided for a normal environment
with Playwright and Chromium installed:

```sh
uv run --with playwright python scripts/qa_simulator.py --output /tmp/herald-qa
```

It fails explicitly if its browser cannot start and writes no success manifest in
that case. It was not executed in the restricted cloud screenshot environment.

Browser QA should cover desktop and 390px-wide item/skill views, readable fallback
names, long receipts, empty/error/loading states, select keyboard dismissal,
modal cancel/reopen and validation, and no horizontal clipping. Save actual
browser screenshots separately from exported payloads. Browser screenshots have
not been claimed merely because the static export was generated.
