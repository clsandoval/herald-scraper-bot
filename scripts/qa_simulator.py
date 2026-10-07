"""Optional local-browser QA: installed Playwright + Chromium, never live Discord.

uv run --with playwright python scripts/qa_simulator.py --output /tmp/herald-qa
Install Playwright's Chromium in your chosen test environment first. This script
is provided for a normal local executor; restricted cloud browsers may not allow
loopback previews. Failure does not count as a screenshot or a passed UI check.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main(output, chromium=None):
    from playwright.sync_api import sync_playwright
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    server=subprocess.Popen([sys.executable,'-m','herald.simulator','--port',str(port)],cwd=ROOT,
                            env={**os.environ,'MPLCONFIGDIR':str(output/'mpl-cache')},
                            stdout=subprocess.DEVNULL)
    results=[]
    try:
        for _ in range(100):
            try:
                with urlopen(base,timeout=1) as response:
                    if response.status==200:break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Offline simulator did not start')
        with sync_playwright() as playwright:
            launch={'headless':True}
            if chromium:launch['executable_path']=chromium
            browser=playwright.chromium.launch(**launch)
            for width in (1360,390):
                page=browser.new_page(viewport={'width':width,'height':1000},device_scale_factor=1)
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base+'/?focus=1')
                page.locator('.v2-container').wait_for()
                def screenshot(name):
                    page.screenshot(path=str(output/f'{name}-{width}.png'),full_page=True)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),name+' horizontally overflows'
                    results.append({'state':name,'width':width,'screenshot':f'{name}-{width}.png'})
                screenshot('items')
                page.locator('[data-custom-id="mb_detail"]').click()
                page.locator('[data-custom-id="mb_detail"]').filter(has_text='Item builds').wait_for()
                screenshot('skills')
                page.locator('[data-custom-id="mb_b"]').click()
                page.locator('[data-custom-id="mb_adv"]').click()
                page.locator('#advanced[open]').wait_for()
                page.locator('#cancel-modal').click()
                page.locator('[data-custom-id="mb_adv"]').click()
                page.locator('#advanced[open]').wait_for()
                screenshot('advanced')
                page.locator('#cancel-modal').click()
                for scenario in ('empty','missing-icons','long-text','pruned','error'):
                    page.locator('#scenario').select_option(scenario)
                    page.locator('.v2-container').wait_for()
                    if scenario in ('long-text','missing-icons'):
                        page.locator('#focus').click();page.locator('[data-custom-id="mb_detail"]').wait_for()
                    screenshot(scenario)
                assert not errors,errors
                page.close()
            browser.close()
        (output/'manifest.json').write_text(json.dumps({'live_discord_verified':False,'results':results},indent=2))
        print(f'Browser QA passed; {len(results)} screenshots in {output}')
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='/tmp/herald-simulator-qa')
    parser.add_argument('--chromium');args=parser.parse_args();main(args.output,args.chromium)
