"""Explicit maintenance-only refresh of pinned official Dota artwork.

Never imported by the reporter. Normal rendering is completely offline. Downloads
are restricted to asset keys from the packaged OpenDota lookup snapshots and the
known Valve CDN origin. Missing/replaced upstream icons remain explicit fallbacks.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from herald import render, report_signals

ROOT = Path(__file__).resolve().parents[1] / 'herald' / 'assets' / 'card_icons'


def sources():
    out = {f'hero_{int(hid)}': render.hero_img(int(hid)) for hid in render._heroes}
    out.update({f'item_{iid}': render.item_img(iid) for iid in render._item_by_id
                if render.item_img(iid) and not render.item_key(iid).startswith('recipe_')})
    heroes = {render.hero_short(int(hid)) for hid in render._heroes}
    out.update({f'ability_{aid}': f'{render.CDN}/apps/dota2/images/dota_react/abilities/{name}.png'
                for aid, name in report_signals._ABILITY_NAMES.items()
                if any(name.startswith(h + '_') for h in heroes)})
    return out


def fetch(key, url):
    path = ROOT / (key + '.png')
    if path.is_file():
        try:
            with Image.open(path) as existing:
                if existing.width <= 2048 and existing.height <= 2048:
                    existing.verify()
                    return key, url, True
        except (OSError, ValueError):
            pass  # Replace a corrupt cached file only after successful validation.
    process = subprocess.run(['curl', '--fail', '--silent', '--show-error',
                              '--proto', '=https', '--max-time', '20', url],
                             capture_output=True)
    if process.returncode or len(process.stdout) > 2_000_000:
        return key, url, False
    try:
        with Image.open(BytesIO(process.stdout)) as source:
            if source.width > 2048 or source.height > 2048:
                return key, url, False
            im = source.convert('RGB')
            im.thumbnail((256, 160) if key.startswith('hero_') else (128, 128), Image.Resampling.LANCZOS)
            im.save(path, format='PNG', optimize=True)
    except (OSError, ValueError):
        return key, url, False
    return key, url, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Explicitly allow public CDN downloads')
    args = parser.parse_args()
    if not args.fetch:
        parser.error('Use --fetch for explicit public-asset retrieval')
    ROOT.mkdir(parents=True, exist_ok=True)
    urls = sources()
    accepted, failed = {}, {}
    with ThreadPoolExecutor(max_workers=24) as executor:
        futures = [executor.submit(fetch, key, url) for key, url in urls.items()]
        for count, future in enumerate(as_completed(futures), 1):
            key, url, ok = future.result()
            (accepted if ok else failed)[key] = url
            if count % 100 == 0:
                print(f'{count}/{len(urls)} checked; {len(accepted)} usable, {len(failed)} unavailable', flush=True)
    (ROOT / 'sources.json').write_text(json.dumps(dict(sorted(accepted.items())), indent=2) + '\n')
    (ROOT / 'unavailable.json').write_text(json.dumps(dict(sorted(failed.items())), indent=2) + '\n')
    (ROOT / 'sha256.json').write_text(json.dumps({key: sha256((ROOT/(key+'.png')).read_bytes()).hexdigest()
                                              for key in sorted(accepted)}, indent=2) + '\n')
    print(f'Done: {len(accepted)} verified image files; {len(failed)} explicit fallbacks.')


if __name__ == '__main__':
    main()
