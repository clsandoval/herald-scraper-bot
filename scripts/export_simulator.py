"""Export production payload snapshots; no Python callbacks run in this viewer."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from herald import board, scheduled, render
from herald.simulator import Simulator, ASSETS, synthetic_match

async def export(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    snapshots={};labels={}
    with tempfile.TemporaryDirectory() as temp:
        sim=Simulator(temp)
        for scenario in ('normal','missing-icons','long-text','empty','pruned','error'):
            p=await sim.request({'action':'reset','scenario':scenario})
            key=f'{scenario}-list';snapshots[key]=p;labels[key]=f'{scenario.replace("-", " ").title()} · menu'
            if scenario not in ('empty','pruned','error'):
                p=await sim.request({'action':'reset','scenario':scenario,'focus':True})
                key=f'{scenario}-items';snapshots[key]=p;labels[key]=f'{scenario.replace("-", " ").title()} · item builds'
                p=await sim.request({'action':'component','custom_id':'mb_detail','revision':p['revision']})
                key=f'{scenario}-skills';snapshots[key]=p;labels[key]=f'{scenario.replace("-", " ").title()} · skill builds'
        for page in range(1,3):
            p=await sim.request({'action':'reset','scenario':'normal'})
            for _ in range(page):
                p=await sim.request({'action':'component','custom_id':'mb_pn','revision':p['revision']})
            key=f'normal-page{page+1}';snapshots[key]=p;labels[key]=f'Normal · menu page {page+1}'
        p=await sim.request({'action':'reset','scenario':'normal'})
        p=await sim.request({'action':'component','custom_id':'mb_filt','values':['spoiler'],'revision':p['revision']})
        # Select a visible option through the real callback, preserving spoiler state.
        opening=next(c for c in sim.view.walk_children() if getattr(c,'custom_id',None)=='mb_open')
        p=await sim.request({'action':'component','custom_id':'mb_open','values':[opening.options[0].value],'revision':p['revision']})
        snapshots['spoiler-items']=p;labels['spoiler-items']='Spoiler-safe · item builds'
        p=await sim.request({'action':'reset','scenario':'normal'})
        p=await sim.request({'action':'component','custom_id':'mb_adv','revision':p['revision']})
        snapshots['advanced-modal']=p;labels['advanced-modal']='Advanced search · modal'
        raw=synthetic_match();candidate={'match_id':raw['id'],'start_time':raw['startDateTime'],
                                       'duration':raw['durationSeconds'],'avg_rank_tier':12}
        od={'duration':raw['durationSeconds'],'radiant_score':sum(raw['radiantKills']),
            'dire_score':sum(raw['direKills']),'radiant_win':raw['didRadiantWin'],
            'radiant_gold_adv':raw['radiantNetworthLeads'],
            'players':[{'hero_id':p['heroId'],'player_slot':i if i<5 else i+123,'leaver_status':0} for i,p in enumerate(raw['players'])]}
        spec=scheduled.payload(candidate,raw,od,{k:v['id'] for k,v in sim.emoji_inventory.items()})
        for key,message,label in [('scheduled-parent',spec['parent'],'Reporter · match overview'),
                                  ('scheduled-radiant',spec['teams'][0],'Reporter · Radiant item + skill builds'),
                                  ('scheduled-dire',spec['teams'][1],'Reporter · Dire item + skill builds')]:
            snapshots[key]={'components':[],**message,'files':{},'emojis':dict(sim.emoji_images),'budget':{'text':render.check_embeds(message)},'scenario':key,
                            'state':{},'provenance':'Synthetic fixture; real scheduled.payload classic embed; not a Components V2 message.'}
            labels[key]=label
    assets={}
    for payload in snapshots.values():
        for field in ('files','emojis'):
            for name,uri in payload[field].items():
                key=hashlib.sha256(uri.encode()).hexdigest()[:16];assets[key]=uri;payload[field][name]=key
    bridge='''
const SNAPSHOTS = __SNAPSHOTS__;
const SNAPSHOT_ASSETS = __ASSETS__;
let activeKey='normal-items';
function hydrateSnapshot(key){const p=structuredClone(SNAPSHOTS[key]);for(const field of ['files','emojis'])for(const name of Object.keys(p[field]||{}))p[field][name]=SNAPSHOT_ASSETS[p[field][name]];p.snapshotKey=key;return p;}
async function staticTransport(data){let key=activeKey;if(data.action==='reset'){key=document.querySelector('#snapshot-choice').value||'normal-items';}else if(data.custom_id==='mb_detail'){key=activeKey.replace(/-(items|skills)$/,(_,part)=>part==='items'?'-skills':'-items');}else if(data.custom_id==='mb_b'){key=activeKey.startsWith('normal')?'normal-list':activeKey.split('-').slice(0,-1).join('-')+'-list';}else if(data.custom_id==='mb_pn'){key=activeKey==='normal-list'?'normal-page2':'normal-page3';}else if(data.custom_id==='mb_pp'){key=activeKey==='normal-page3'?'normal-page2':'normal-list';}else{const p=hydrateSnapshot(activeKey);p.message='This export contains fixed production snapshots. Run python -m herald.simulator for live callback, filtering and modal tests.';return p;}if(!SNAPSHOTS[key])key=activeKey;activeKey=key;document.querySelector('#snapshot-choice').value=key;return hydrateSnapshot(key);}
'''.replace('__SNAPSHOTS__',json.dumps(snapshots,separators=(',',':'))).replace('__ASSETS__',json.dumps(assets,separators=(',',':')))
    app=(ASSETS/'app.js').read_text()
    start="const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,revision:prev?.revision})});const result=await response.json();if(id!==requestId)return;if(!response.ok)throw Error(result.message||'Simulator request failed');"
    app=app.replace(start,"const result=await staticTransport(data);if(id!==requestId)return;")
    app=app.replace("reset(new URLSearchParams(location.search).get('focus')==='1',new URLSearchParams(location.search).get('scenario')||'normal');", "$('#snapshot-choice').onchange=()=>reset();const requested=new URLSearchParams(location.search).get('snapshot');if(SNAPSHOTS[requested])$('#snapshot-choice').value=requested;reset();")
    html=(ASSETS/'index.html').read_text()
    html=html.replace('href="/style.css"','href="./style.css"').replace('src="/app.js"','src="./app.js"')
    html=html.replace('Real bot payloads. Synthetic matches. Discord-style preview.','Production payload snapshots · Synthetic data · Discord-style approximation')
    options=''.join(f'<option value="{k}"'+(' selected' if k=='normal-items' else '')+f'>{v}</option>' for k,v in labels.items())
    html=html.replace('<label for="scenario">Fixture scenario</label>',f'<label for="snapshot-choice">Snapshot</label><select id="snapshot-choice">{options}</select><p class="static-note">Static snapshot viewer. Menu callbacks are tested separately in the Python simulator.</p><div hidden><label for="scenario">Fixture scenario</label>')
    html=html.replace('<label class="check"><input id="narrow"', '</div><label class="check"><input id="narrow"')
    html=html.replace('<button id="race">Probe overlapping Next clicks</button>','<button id="race" hidden>Probe overlapping Next clicks</button>')
    html=html.replace('Exercise the production menu without a bot token or a live post.','Inspect item builds, skill paths and edge states from the production renderer.')
    html=html.replace('The preview uses the bot’s actual components and callbacks.','The preview uses captured production components and classic embeds. The downloadable local simulator runs actual callbacks.')
    (destination/'index.html').write_text(html)
    (destination/'style.css').write_text((ASSETS/'style.css').read_text()+'\n.static-note{font-size:11px;color:#b5bac1;line-height:1.6;margin:14px 0 20px}[hidden]{display:none!important}\n')
    (destination/'app.js').write_text(bridge+app)
    (destination/'snapshot-manifest.json').write_text(json.dumps({'snapshots':labels,'synthetic':True,'live_discord_verified':False,'python_callbacks_in_static_export':False},indent=2))
    print(f'Exported {len(snapshots)} production snapshots, {len(assets)} deduplicated assets to {destination}')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');asyncio.run(export(parser.parse_args().destination))
