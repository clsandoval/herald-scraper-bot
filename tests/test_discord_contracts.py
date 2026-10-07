"""Offline wire-shape contracts across menu combinations (not live Discord QA)."""
import copy
import json

import pytest

from herald import board, ingest, render


def nodes(components):
    for component in components:
        yield component
        yield from nodes(component.get('components', []))
        if component.get('accessory'):
            yield from nodes([component['accessory']])


def assert_component_contract(view):
    payload = view.to_components()
    all_nodes = list(nodes(payload))
    assert len(all_nodes) <= 40
    ids = [n['custom_id'] for n in all_nodes if 'custom_id' in n]
    assert len(ids) == len(set(ids))
    assert all(1 <= len(value) <= 100 for value in ids)
    assert sum(len(n.get('content', '')) for n in all_nodes) <= 4000
    for node in all_nodes:
        kind = node['type']
        if kind == 1:
            children = node['components']
            assert 1 <= len(children) <= 5
            assert all(c['type'] == 2 for c in children) or len(children) == 1
        elif kind == 2:
            assert len(node.get('label', '')) <= 80
            assert not ('url' in node and 'custom_id' in node)
        elif kind == 3:
            options = node['options']
            assert 1 <= len(options) <= 25
            assert len({o['value'] for o in options}) == len(options)
            assert 0 <= node.get('min_values', 1) <= node.get('max_values', 1) <= len(options)
            assert len(node.get('placeholder', '')) <= 150
            for option in options:
                assert 1 <= len(option['label']) <= 100
                assert 1 <= len(option['value']) <= 100
                assert len(option.get('description', '')) <= 100
        elif kind == 9:
            assert 1 <= len(node['components']) <= 3
            assert all(c['type'] == 10 for c in node['components'])
            assert node['accessory']['type'] in (2, 11)
    files = [name for name, data in view.files]
    assert len(files) <= 10 and len(files) == len(set(files))
    def attachment_urls(value):
        if isinstance(value, dict):
            for child in value.values():
                yield from attachment_urls(child)
        elif isinstance(value, list):
            for child in value:
                yield from attachment_urls(child)
        elif isinstance(value, str) and value.startswith('attachment://'):
            yield value.removeprefix('attachment://')
    assert set(attachment_urls(payload)) <= set(files)


@pytest.fixture
def archive(tmp_path, monkeypatch):
    path = tmp_path / 'contracts.db'
    conn = ingest.get_conn(str(path))
    monkeypatch.setattr(board, 'DB_PATH', str(path))
    monkeypatch.setattr(render, '_emoji', {})
    # Wire-shape tests do not benchmark or validate chart image rendering.
    monkeypatch.setattr(board.charts, 'thumb_spark_png', lambda *a, **k: b'chart-stub')
    monkeypatch.setattr(board.charts, 'networth_lead_png', lambda *a, **k: b'chart-stub')
    monkeypatch.setattr(board, '_thumb_cache', board.OrderedDict())
    for mid in range(1, 7):
        raw = {'id': mid, 'startDateTime': 1_780_000_000 + mid,
               'durationSeconds': 4600 + mid * 100, 'didRadiantWin': bool(mid % 2),
               'radiantKills': [30 + mid], 'direKills': [25 + mid],
               'radiantNetworthLeads': [0, 1000, -2000, 5000],
               'players': [{'heroId': i + 1, 'isRadiant': i < 5,
                            'kills': 3, 'deaths': 4, 'assists': 5,
                            'networth': 6000, 'goldPerMinute': 300,
                            'steamAccount': {'seasonRank': 12}, 'stats': {}}
                           for i in range(10)]}
        ingest.upsert_match(conn, raw, 11 + mid % 5)
    yield conn
    conn.close()


@pytest.mark.parametrize('sort_key', list(board.SORTS))
@pytest.mark.parametrize('direction', ['ASC', 'DESC'])
async def test_each_sort_direction_serializes_within_discord_limits(archive, sort_key, direction):
    state = board.default_state()
    state.update(sort=[sort_key], dir=direction)
    assert_component_contract(await board.build_board(state))


@pytest.mark.parametrize('filter_key', list(board.FILTERS))
@pytest.mark.parametrize('spoiler', [False, True])
async def test_each_filter_and_spoiler_wire_contract(archive, filter_key, spoiler):
    state = board.default_state()
    state.update(filters=[filter_key], spoiler=spoiler)
    assert_component_contract(await board.build_board(state))


@pytest.mark.parametrize('page', [-5, 0, 1, 999999])
async def test_page_boundaries_wire_contract(archive, page):
    state = board.default_state()
    state['page'] = page
    assert_component_contract(await board.build_board(state))
    assert 0 <= state['page'] <= 1


@pytest.mark.parametrize('spoiler', [False, True])
async def test_focus_and_pruned_focus_contract(archive, spoiler):
    state = board.default_state()
    state.update(mode='focus', match=1, spoiler=spoiler)
    view = await board.build_board(copy.deepcopy(state))
    assert_component_contract(view)
    text = json.dumps(view.to_components())
    if spoiler:
        assert 'Radiant win' not in text and 'Dire win' not in text
        assert 'attachment://g1.png' not in text
    archive.execute('DELETE FROM matches WHERE match_id=1')
    archive.commit()
    assert_component_contract(await board.build_board(state))
    assert state['mode'] == 'list'


async def test_all_filters_and_empty_archive_contract(archive):
    state = board.default_state()
    state['filters'] = list(board.FILTERS)
    assert_component_contract(await board.build_board(state))
    archive.execute('DELETE FROM matches')
    archive.execute('DELETE FROM match_players')
    archive.commit()
    assert_component_contract(await board.build_board(board.default_state()))

async def test_every_filter_subset_matches_set_intersection(archive):
    """Enumerate all current filter combinations on one small varied corpus."""
    keys = list(board.FILTERS)
    universe = {row[0] for row in await board.q('SELECT match_id FROM matches')}
    individual = {}
    for key in keys:
        state = board.default_state()
        state['filters'] = [key]
        where, params = await board.build_where(state)
        individual[key] = {r[0] for r in await board.q('SELECT match_id FROM matches' + where, params)}
    for mask in range(1 << len(keys)):
        selected = [key for bit, key in enumerate(keys) if mask & (1 << bit)]
        state = board.default_state()
        state['filters'] = selected
        where, params = await board.build_where(state)
        actual = {r[0] for r in await board.q('SELECT match_id FROM matches' + where, params)}
        expected = set(universe)
        for key in selected:
            expected &= individual[key]
        assert actual == expected, selected
