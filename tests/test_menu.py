"""Behavioral menu checks: temporary SQLite, no Discord gateway or HTTP."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from herald import board, ingest


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'archive.db'
    conn = ingest.get_conn(str(path))
    monkeypatch.setattr(board, 'DB_PATH', str(path))
    yield conn
    conn.close()


def raw_match(mid=1):
    return {'id': mid, 'startDateTime': 1, 'durationSeconds': 4600,
            'didRadiantWin': True, 'radiantKills': [30], 'direKills': [25],
            'radiantNetworthLeads': [0, 1000], 'players': [
                {'heroId': i+1, 'isRadiant': i < 5, 'kills': 3, 'deaths': 4,
                 'assists': 5, 'networth': 6000, 'goldPerMinute': 300,
                 'steamAccount': {'seasonRank': 12}, 'stats': {}}
                for i in range(10)]}


async def test_empty_archive_has_usable_board(db):
    view = await board.build_board(board.default_state())
    text = json.dumps(view.to_components())
    assert 'No matches yet' in text
    controls = {c.custom_id: c for c in view.walk_children() if hasattr(c, 'custom_id')}
    assert controls['mb_open'].disabled
    assert controls['mb_pp'].disabled and controls['mb_pn'].disabled
    assert await board.random_match_id(board.default_state()) is None


async def test_singleton_scoring_and_pruned_focus(db):
    ingest.upsert_match(db, raw_match(), 12)
    state = board.default_state()
    state['page'] = 100
    score, counts = await board.corpus_info()
    assert 'nan' not in score and 'inf' not in score
    total, page, _ = await board.select_page(state, score)
    assert total == 1 and len(page) == 1 and state['page'] == 0
    db.execute('DELETE FROM matches'); db.commit()
    state.update(mode='focus', match=1)
    view = await board.build_board(state)
    assert state['mode'] == 'list'
    assert 'left the archive' in json.dumps(view.to_components())


async def test_counts_follow_ingest_and_dice_respects_filters(db):
    _, before = await board.corpus_info()
    ingest.upsert_match(db, raw_match(), 12)
    _, after = await board.corpus_info()
    assert before['lowrank'] == 0 and after['lowrank'] == 1
    state = board.default_state(); state['filters'] = ['highrank']
    assert await board.random_match_id(state) is None


async def test_random_acknowledges_before_query(db, monkeypatch):
    state = board.default_state()
    view = await board.build_board(state)
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done.return_value = False
    interaction.edit_original_response = AsyncMock()
    async def query_after_ack(_):
        interaction.response.defer.assert_awaited_once()
        return None
    monkeypatch.setattr(board, 'random_match_id', query_after_ack)
    await view._update(interaction, random=True)
    interaction.edit_original_response.assert_awaited_once()

async def test_full_receipts_fit_discord_text_budget(db):
    from herald import render
    raw = raw_match()
    for p in raw['players']:
        p.update({f'item{i}Id': item for i, item in enumerate([1,116,65,133,108,112])})
        p['dotaPlus'] = {'level': 30}
    ingest.upsert_match(db, raw, 12)
    notes = [{'hero_id': p['heroId'], 'score': 9,
              'items': [['Very expensive unusual item', 50, 9]] * 3} for p in raw['players']]
    skills = [{'hero_id': p['heroId'], 'picks': [['An unusually timed ability', 20, 9]] * 3,
               'tag': 'Unusual order'} for p in raw['players']]
    db.execute('UPDATE matches SET weirdness=9, weird_notes=?, skill_weirdness=9, skill_notes=?',
               (json.dumps(notes), json.dumps(skills))); db.commit()
    state = board.default_state(); state.update(mode='focus', match=1)
    view = await board.build_board(state)
    assert sum(len(item.content) for item in view.walk_children()
               if isinstance(item, board.discord.ui.TextDisplay)) <= render.MAX_CHARS
    content = json.dumps(view.to_components())
    assert 'Radiant' in content and 'Dire' in content
    assert 'Additional receipts omitted' in content

async def test_zero_scores_are_not_labeled_anomalous(db):
    ingest.upsert_match(db, raw_match(), 12)
    db.execute('UPDATE matches SET weirdness=0, skill_weirdness=0'); db.commit()
    _, counts = await board.corpus_info()
    assert counts['weirdf'] == 0 and counts['skillf'] == 0


@pytest.mark.parametrize('inventory_fails', [False, True])
async def test_new_bot_does_not_use_historical_emoji_ids(db, monkeypatch, inventory_fails):
    from herald import render
    ingest.upsert_match(db, raw_match(), 12)
    monkeypatch.setattr(render, '_emoji', {
        'rank_12': {'name': 'rank_12', 'id': '123456789012345678'},
    })
    client = MagicMock(guilds=[])
    client.fetch_application_emojis = AsyncMock(return_value=[])
    if inventory_fails:
        client.fetch_application_emojis.side_effect = board.discord.Forbidden(
            MagicMock(status=403, reason='Forbidden'), 'Synthetic offline denial')
    monkeypatch.setattr(board, 'client', client)
    await board.on_ready()
    assert board.rank_emoji(12) == ''
    view = await board.build_board(board.default_state())
    assert '123456789012345678' not in json.dumps(view.to_components())
