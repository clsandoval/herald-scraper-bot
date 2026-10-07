"""The browser laboratory must exercise production code, not imitate its data."""
import json
import pytest
from herald import board, render
from herald.simulator import Simulator, synthetic_match

@pytest.fixture
def sim(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'DB_PATH', board.DB_PATH)
    monkeypatch.setattr(render, '_emoji', {})
    return Simulator(tmp_path)

async def reset(sim, **kwargs):
    return await sim.request({'action':'reset', **kwargs})

async def click(sim, payload, cid, values=None):
    return await sim.request({'action':'component','revision':payload['revision'],
                              'custom_id':cid, 'values':values or []})

def controls(payload):
    found={}
    def walk(cs):
        for c in cs:
            if c.get('custom_id'):found[c['custom_id']]=c
            walk(c.get('components', []))
    walk(payload['components']);return found

@pytest.mark.parametrize('scenario', ['normal','empty','missing-icons','long-text','pruned','error'])
async def test_scenarios_are_real_valid_payloads(sim, scenario):
    p=await reset(sim, scenario=scenario)
    assert p['budget']['components']<=40 and p['budget']['text']<=3600
    assert p['flags'] & 32768
    assert not p.get('embeds')
    if scenario=='empty': assert controls(p)['mb_open']['disabled']
    if scenario=='pruned': assert 'left the archive' in json.dumps(p['components'])
    if scenario=='error': assert p['error'] and 'unavailable' in p['message']

async def test_item_and_skill_tabs_use_actual_callback(sim):
    p=await reset(sim, focus=True)
    assert 'Black King Bar' in json.dumps(p['components']) or ':i_black_king_bar:' in json.dumps(p['components'])
    p=await click(sim,p,'mb_detail')
    assert p['state']['detail']=='skills'
    assert p['events']==['acknowledged','rendered']
    assert 'Berserker' in json.dumps(p['components'])
    p=await click(sim,p,'mb_detail')
    assert p['state']['detail']=='items'

async def test_select_modal_cancel_reopen_and_apply(sim):
    p=await reset(sim)
    p=await click(sim,p,'mb_adv')
    assert p['modal']['title']=='Advanced search'
    # Cancelling is client-side; reopening the real button must remain possible.
    p=await click(sim,p,'mb_adv')
    f=sim.modal.heroes.custom_id
    p=await sim.request({'action':'modal','revision':p['revision'],'values':{f:'axe'}})
    assert p['state']['adv']['heroes']==['axe']
    assert 'modal' not in p
    p=await click(sim,p,'mb_adv')
    p=await sim.request({'action':'modal','revision':p['revision'],'values':{}})
    assert p['state']['adv'] is None

async def test_invalid_modal_does_not_mutate_search(sim):
    p=await reset(sim)
    p=await click(sim,p,'mb_adv')
    p=await sim.request({'action':'modal','revision':p['revision'],
                        'values':{sim.modal.dur.custom_id:'nonsense'}})
    assert 'unchanged' in p['message']
    assert p['state']['adv'] is None

async def test_filters_spoilers_paging_stale_inputs_and_overlap(sim):
    p=await reset(sim)
    p=await click(sim,p,'mb_filt',['spoiler','highrank'])
    assert p['state']['spoiler'] and p['state']['filters']==['highrank']
    mid=controls(p)['mb_open']['options'][0]['value']
    p=await click(sim,p,'mb_open',[mid])
    assert not p['files']
    assert 'win' not in json.dumps(p['components']).lower()
    p=await reset(sim)
    old=p
    p=await sim.request({'action':'race','revision':p['revision']})
    assert p['state']['page']==2
    assert p['events'].count('acknowledged')==2
    stale=await click(sim,old,'mb_pn')
    assert 'stale' in stale['message'] and stale['state']==p['state']

async def test_unrecognized_component_and_values_rejected(sim):
    p=await reset(sim)
    with pytest.raises(ValueError,match='unavailable'):await click(sim,p,'fake')
    with pytest.raises(ValueError,match='Invalid select'):await click(sim,p,'mb_sort',['fake'])

async def test_distinct_missing_icon_scenario(sim):
    normal=await reset(sim)
    missing=await reset(sim,scenario='missing-icons')
    assert not missing['emojis']
    if sim.emoji_images:
        assert normal['emojis'] and '<:h_axe:' in json.dumps(normal['components'])
    assert 'Axe' in json.dumps(missing['components'])

def test_fixture_is_deterministic_and_has_no_account_ids():
    assert synthetic_match()==synthetic_match()
    for p in synthetic_match()['players']:
        assert set(p['steamAccount'])=={'seasonRank'}
        assert len(p['abilities'])==12 and len(p['stats']['itemPurchases'])==6

async def test_snapshots_do_not_mutate_shared_icon_inventory(sim):
    p=await reset(sim)
    if p['emojis']:
        name=next(iter(p['emojis']))
        p['emojis'][name]='changed in snapshot'
        assert sim.emoji_images[name].startswith('data:image/png;base64,')

async def test_fixture_exposes_observed_micro_cues(sim):
    p=await reset(sim,focus=True)
    text=json.dumps(p['components'])
    assert 'BKB' in text
    assert 'dieback' in text.lower() or 'buyback' in text.lower()
