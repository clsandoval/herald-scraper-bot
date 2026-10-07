# Offline presentation icons

Dota 2 hero and item images are Valve assets cached from the public Steam CDN.
The exact original URLs are listed in `sources.json`. They are retained solely
for the offline Discord-style presentation fixture; no application emojis were
created or modified. The fixture assigns made-up emoji IDs and resolves them to
these local images. These IDs are not usable on Discord.

The “missing application icons” scenario supplies an empty emoji inventory and
therefore exercises the production readable-name fallback. Production code does
not load this icon fixture or its synthetic inventory.
