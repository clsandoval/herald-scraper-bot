"""Pure icon-card contract and missing-evidence tests."""
import copy
from hashlib import sha256
from io import BytesIO
import json

from PIL import Image
import pytest

from herald import card_images, report_signals


def model(synthetic_match, *, radiant=True, missing=False):
    match = synthetic_match(missing=missing)
    return card_images.build_team_card(*match, radiant=radiant, synthetic=True)


def test_card_is_offline_deterministic_and_serializable(monkeypatch, synthetic_match):
    import httpx
    import socket
    def no_network(*a, **k):
        raise AssertionError('Card rendering must never access the network')
    monkeypatch.setattr(httpx.Client, 'request', no_network)
    monkeypatch.setattr(socket, 'create_connection', no_network)
    original = model(synthetic_match)
    decoded = json.loads(json.dumps(original))
    first = card_images.render_team_card(original)
    second = card_images.render_team_card(decoded)
    assert first == second
    with Image.open(BytesIO(first.png_bytes)) as png:
        assert png.format == 'PNG'
        assert png.size == (1000, 1156)
    assert sha256(first.png_bytes).hexdigest()[:12] in first.filename
    assert len(first.description) <= 1024
    assert 'Example.' in first.description


def test_exact_slots_missing_slots_and_unknown_ids_are_distinct(synthetic_match):
    match = synthetic_match()
    player = match[1]['players'][0]
    player.update(item0Id=151, item1Id=None, item2Id=999999, item3Id=False, item4Id=0)
    player.pop('item5Id')
    card = card_images.build_team_card(*match, radiant=True)
    assert card['players'][0]['items'] == [151, 0, 999999, None, 0, None]
    assert card_images.asset_path('item', 999999) is None
    assert card_images.render_team_card(card).png_bytes.startswith(b'\x89PNG')


def test_unknown_ability_keeps_its_observed_position(synthetic_match):
    match = synthetic_match()
    player = match[1]['players'][0]
    expected = report_signals._skill_ids(player)
    player['abilities'][1]['abilityId'] = 987654
    card = card_images.build_team_card(*match, radiant=True)
    assert card['players'][0]['skills'] == [expected[0], 987654, *expected[2:]]
    assert len(card['players'][0]['skills']) == 12
    assert card_images.render_team_card(card).png_bytes


def test_missing_and_empty_ability_logs_remain_distinct(synthetic_match):
    missing = model(synthetic_match, missing=True)
    assert missing['players'][0]['skills'] is None
    match = synthetic_match()
    match[1]['players'][0]['abilities'] = []
    empty = card_images.build_team_card(*match, radiant=True)
    assert empty['players'][0]['skills'] == []
    assert card_images.render_team_card(missing).png_bytes != card_images.render_team_card(empty).png_bytes


def test_skill_order_is_time_sorted_and_talents_do_not_shift_observed_positions(synthetic_match):
    match = synthetic_match()
    p = match[1]['players'][0]
    expected = report_signals._skill_ids(p)
    p['abilities'].insert(4, {'abilityId': 999, 'time': 15, 'isTalent': True})
    p['abilities'].reverse()
    card = card_images.build_team_card(*match, radiant=True)
    assert card['players'][0]['skills'] == expected


def test_warmed_receipts_are_bounded_and_match_original_pick_positions(synthetic_match, synthetic_evidence):
    match = synthetic_match()
    proof = synthetic_evidence(match)
    card = card_images.build_team_card(*match, radiant=True, evidence=proof)
    assert card['synthetic'] is True
    assert card['players'][0]['skill_marks'] == [1]
    assert card['players'][0]['item_marks'] == [151]
    assert len(card['players'][0]['notes']) == 2
    assert 'Counterspell' in card['players'][0]['notes'][1]
    assert card['players'][0]['notes'] == ['Armlet of Mordiggian @20m', 'Pick 1: Counterspell']
    assert all(not p['notes'] for p in card['players'][1:])
    assert card_images.build_team_card(*match, radiant=True, evidence=json.loads(json.dumps(proof))) == card


def test_factual_rapier_hook_is_preserved_without_claiming_item_drop(synthetic_match):
    card = model(synthetic_match, radiant=False)
    assert card['players'][0]['notes'] == ['Divine Rapier bought 75:00; died 35s later']
    assert 'dropped' not in json.dumps(card)


def test_each_card_requires_five_players_and_known_layout_version(synthetic_match):
    match = synthetic_match()
    match[1]['players'].pop(0)
    with pytest.raises(ValueError, match='exactly five'):
        card_images.build_team_card(*match, radiant=True)
    card = model(synthetic_match); card['version'] = 'future'
    with pytest.raises(ValueError, match='Unsupported'):
        card_images.render_team_card(card)


def test_icon_paths_never_accept_provider_paths_or_boolean_ids():
    for kind, identifier in [('hero', '../secrets'), ('hero', True), ('../../', 1), ('item', -1)]:
        assert card_images.asset_path(kind, identifier) is None


def test_every_packaged_icon_is_verified_against_its_public_source_key():
    sources = json.loads((card_images.ASSET_DIR / 'sources.json').read_text())
    assert sources
    for key, url in sources.items():
        kind, identifier = key.split('_', 1)
        assert card_images.asset_path(kind, int(identifier)).is_file()
        assert url.startswith('https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/')
        with Image.open(card_images.ASSET_DIR / f'{key}.png') as icon:
            icon.verify()


@pytest.mark.parametrize('radiant', [True, False])
@pytest.mark.parametrize('state', ['warm', 'cold', 'missing', 'real'])
def test_all_rendered_words_are_facts_or_minimal_labels(monkeypatch, synthetic_match,
                                                       synthetic_evidence, radiant, state):
    match = synthetic_match(missing=state == 'missing')
    proof = synthetic_evidence(match) if state == 'warm' else None
    before = copy.deepcopy((match, proof))
    card = card_images.build_team_card(*match, radiant=radiant, evidence=proof,
                                       synthetic=state != 'real')
    drawn = []
    text = card_images._text

    def capture(draw, xy, label, *args, **kwargs):
        drawn.append(str(label))
        return text(draw, xy, label, *args, **kwargs)

    monkeypatch.setattr(card_images, '_text', capture)
    rendered = card_images.render_team_card(card)
    visible = '\n'.join([*drawn, rendered.description]).lower()
    forbidden = ('pmi', 'surprisal', 'unscored', 'reference', 'population', 'sample',
                 'n=', 'quality score', 'receipt', 'patch', 'invented', 'synthetic')
    assert all(word not in visible for word in forbidden)
    assert drawn.count('Example') == (0 if state == 'real' else 1)
    assert len(card['players']) == 5
    assert all(len(player['items']) == 6 for player in card['players'])
    assert (match, proof) == before
    assert 'reference' in card
    assert all('evidence_status' in player for player in card['players'])


def test_saved_scoring_notes_render_cleanly_without_mutating_legacy_model(
        synthetic_match, synthetic_evidence):
    match = synthetic_match()
    proof = synthetic_evidence(match)
    fresh = card_images.build_team_card(*match, radiant=True, evidence=proof)
    legacy = copy.deepcopy(fresh)
    legacy['players'][0]['notes'] = [
        'Armlet of Mordiggian @20m · PMI 7.5 · n=40',
        'Pick 1: Counterspell · surprisal 2.2 · n=40',
    ]
    before = copy.deepcopy(legacy)

    assert card_images.render_team_card(legacy) == card_images.render_team_card(fresh)
    assert legacy == before
    assert legacy['version'] == 'icon-team-v1'
