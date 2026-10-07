"""Fixed eligibility and delivery recovery against an in-memory Discord fake."""
import copy
from unittest.mock import Mock

import httpx
import pytest

from herald import scheduled as s


def report_gallery(message):
    container = next(node for node in message["components"] if node["type"] == 17)
    return next(node for node in container["components"] if node["type"] == 12)


def fixture():
    candidate = {'match_id': 987654, 'duration': 4501, 'avg_rank_tier': 16, 'start_time': 1000}
    raw = {'players': [{'heroId': i+1, 'isRadiant': i<5, 'kills': 1, 'deaths': 1,
                       'assists': 0, 'steamAccount': {'seasonRank': 15}} for i in range(10)]}
    od = {'players': [{'leaver_status': 0} for _ in range(10)],
          'radiant_score': 5, 'dire_score': 5, 'duration': 4501}
    return candidate, raw, od


def test_original_policy_boundaries_and_no_kpm_or_lobby_requirement():
    c, raw, od = fixture()
    assert s.eligible(c, raw, od)  # 0.13 KPM and no lobby field
    assert not s.eligible({**c, 'duration': 4500}, raw, od)
    assert not s.eligible({**c, 'avg_rank_tier': 17}, raw, od)
    raw['players'][0]['steamAccount']['seasonRank'] = 16
    assert not s.eligible(c, raw, od)
    raw['players'][0]['steamAccount'] = None
    assert not s.eligible(c, raw, od)
    c, raw, od = fixture(); od['players'][0]['leaver_status'] = 1
    assert not s.eligible(c, raw, od)
    del od['players'][0]['leaver_status']
    assert not s.eligible(c, raw, od)


def test_payload_has_two_icon_team_cards_and_no_summary():
    c, raw, od = fixture()
    spec = s.payload(c, raw, od, {'h_antimage': '123'})
    assert len(spec['teams']) == 2
    assert all('embeds' not in t and t['flags'] == 32768 for t in spec['teams'])
    assert all(report_gallery(t)['items'][0]['media']['url'].startswith('attachment://') for t in spec['teams'])
    assert spec['cards']['radiant']['players'][0]['hero_name'] == 'Anti-Mage'
    assert set(spec.uploads) == {'radiant', 'dire'}
    assert all('content' not in m for m in [spec['parent'], *spec['teams']])


class FakeDiscord:
    def __init__(self):
        self.messages = {}; self.posts = []; self.fail_stage = None
        self.next_id = 100
        self.files = {}

    def find_message(self, channel, bot_id, expected, nonce):
        return next((m for (ch, _), m in self.messages.items()
                     if ch == channel and s.same_message(m, expected)), None)

    def request(self, method, path, **kwargs):
        parts = path.split('/')
        channel = parts[2]
        if method == 'GET':
            return copy.deepcopy(self.messages.get((channel, parts[4])))
        body = kwargs['json']; self.next_id += 1; mid = str(self.next_id)
        if path.endswith('/threads'):
            obj = {'id': mid}
            self.messages[(channel, parts[4])]['thread'] = obj
        else:
            obj = {**copy.deepcopy(body), 'id': mid, 'author': {'id': 'bot'}}
            for attachment, (_, (filename, data, content_type)) in zip(obj.get('attachments', []), kwargs.get('files', [])):
                url = f'https://cdn.discordapp.com/attachments/123/{mid}/{filename}?ex=signed'
                attachment.update(id=mid, size=len(data), content_type=content_type, url=url)
                self.files[url] = data
                if obj.get('components'):
                    report_gallery(obj)['items'][0]['media'] = {
                        'url': url, 'attachment_id': mid, 'content_type': content_type}
                else:
                    obj['embeds'][0]['image']['url'] = url
            self.messages[(channel, mid)] = obj
        self.posts.append(path)
        stage = 'thread' if path.endswith('/threads') else body['nonce'].split(':')[-1]
        if self.fail_stage == stage:
            self.fail_stage = None
            raise KeyboardInterrupt('cancel after remote accepted write')
        return copy.deepcopy(obj)


    def verify_attachments(self, actual, expected):
        for attachment, manifest in zip(actual.get("attachments", []), expected.get("_files", [])):
            s._check_upload(self.files[attachment["url"]], manifest)


def test_partial_thread_resumes_without_duplicate_posts(tmp_path):
    api = FakeDiscord(); ledger = s.Receipts(tmp_path/'receipts.db')
    spec = s.payload(*fixture(), {})
    api.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, 'channel', 'bot')
    assert not ledger.get(spec['match_id']).get('verified')
    assert ledger.get(spec['match_id'])['inflight'] == 'radiant'
    receipt = s.deliver(api, ledger, spec, 'channel', 'bot')
    assert receipt['verified']
    assert len(api.posts) == 4  # parent, thread, two teams
    s.deliver(api, ledger, spec, 'channel', 'bot')
    assert len(api.posts) == 4


def test_ambiguous_send_blocks_without_blind_resend(tmp_path):
    api = FakeDiscord(); ledger = s.Receipts(tmp_path/'receipts.db')
    spec = s.payload(*fixture(), {})
    api.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, 'channel', 'bot')
    api.messages = {k:v for k,v in api.messages.items() if not v.get('nonce', '').endswith(':radiant')}
    with pytest.raises(RuntimeError, match='Unresolved radiant'):
        s.deliver(api, ledger, spec, 'channel', 'bot')
    assert len(api.posts) == 3


def test_single_writer_lock_releases_on_cancel(tmp_path):
    path = tmp_path/'receipt.db'
    with pytest.raises(KeyboardInterrupt), s.exclusive_run(path):
        with pytest.raises(RuntimeError, match='already owns'):
            with s.exclusive_run(path):
                pass
        raise KeyboardInterrupt
    with s.exclusive_run(path):
        pass


def test_discord_rate_limit_bounded_and_retried(monkeypatch):
    monkeypatch.setattr(s.time, 'sleep', Mock())
    replies = [httpx.Response(429, json={'retry_after': 0}), httpx.Response(200, json={'id':'ok'})]
    client = Mock(); client.request.side_effect = replies
    assert s.DiscordHTTP(client, 'synthetic').request('GET', '/users/@me')['id'] == 'ok'
    client.request.side_effect = [httpx.Response(429, json={'retry_after': 61})]
    with pytest.raises(RuntimeError, match='wait budget'):
        s.DiscordHTTP(client, 'synthetic').request('GET', '/users/@me')


def test_original_delayed_daily_window_and_explicit_backfill():
    now = 10 * 86400
    assert s.report_window(now) == (6 * 86400, 7 * 86400)
    assert s.report_window(now, backfill=7) == (3 * 86400, now)


@pytest.mark.parametrize('status', [403, 429])
def test_definitive_rejection_can_retry_after_fix(tmp_path, status):
    api = FakeDiscord(); ledger = s.Receipts(tmp_path/'receipts.db')
    spec = s.payload(*fixture(), {})
    original = api.request
    def rejected(method, path, **kwargs):
        if method == 'POST':
            raise s.DefiniteRejection(f'Discord HTTP {status}')
        return original(method, path, **kwargs)
    api.request = rejected
    with pytest.raises(s.DefiniteRejection):
        s.deliver(api, ledger, spec, 'channel', 'bot')
    assert 'inflight' not in ledger.get(spec['match_id'])
    api.request = original
    assert s.deliver(api, ledger, spec, 'channel', 'bot')['verified']


def test_discovery_obeys_window_boundaries_and_original_filters(monkeypatch):
    now = 10 * 86400
    candidates = [
        {'match_id': 6, 'start_time': 7*86400, 'avg_rank_tier': 15, 'duration': 5000},
        {'match_id': 5, 'start_time': 6*86400, 'avg_rank_tier': 16, 'duration': 4501},
        {'match_id': 4, 'start_time': 6*86400+1, 'avg_rank_tier': 15, 'duration': 4500},
        {'match_id': 3, 'start_time': 6*86400+1, 'avg_rank_tier': 17, 'duration': 5000},
        {'match_id': 2, 'start_time': 6*86400-1, 'avg_rank_tier': 15, 'duration': 5000},
    ]
    fetch = Mock(side_effect=[candidates, []])
    monkeypatch.setattr(s.api, 'explorer_fetch', fetch)
    monkeypatch.setattr(s.time, 'sleep', Mock())
    assert [r['match_id'] for r in s.discover(Mock(), now)] == [5]
    query = fetch.call_args_list[0].args[1]
    assert 'avg_rank_tier <= 16' in query and 'lobby' not in query and 'kpm' not in query


def test_bounded_report_stratz_request(monkeypatch):
    monkeypatch.setenv('STRATZ_API_TOKEN', 'synthetic-test-value')
    client = Mock()
    client.post.return_value = httpx.Response(200, json={'data': {'m0': None}},
                                             request=httpx.Request('POST', 'https://example.invalid'))
    s.api.stratz_fetch_batch(client, [1], fields=s.REPORT_FIELDS)
    query = client.post.call_args.kwargs['json']['query']
    # Review observations ride the existing batch, with only used event fields.
    # Do not import the menu's rich selection or request chat/location timelines.
    for field in ('seasonRank', 'actionsPerMinute', 'abilities', 'abilityId',
                  'isTalent', 'itemPurchases', 'itemUsed', 'deathEvents',
                  'timeDead', 'isDieBack', 'isAttemptTpOut'):
        assert field in query
    for field in ('allTalks', 'chatWheels', 'inventoryReport', 'locationReport',
                  'heroAverage', 'networthPerMinute', 'wards', 'tripsFountainPerMinute'):
        assert field not in query
    assert client.post.call_count == 1


def test_failed_window_survives_restart_until_completed(tmp_path):
    path = tmp_path/'receipts.db'
    ledger = s.Receipts(path)
    old = ledger.window(10*86400, None)
    ledger.conn.close()
    resumed = s.Receipts(path)
    assert resumed.window(12*86400, 7) == old
    resumed.finish_window()
    assert resumed.window(12*86400, 7) == {'now':12*86400, 'backfill':7}


def test_failed_live_pass_preserves_discovery_window(tmp_path, monkeypatch):
    ledger = s.Receipts(tmp_path/'receipts.db')
    monkeypatch.setattr(s.time, 'time', lambda: 10*86400)
    client = Mock(); client.request.side_effect = httpx.ConnectError('synthetic offline failure')
    with pytest.raises(httpx.ConnectError):
        s.run_once(ledger, client, 'synthetic', 'channel')
    monkeypatch.setattr(s.time, 'time', lambda: 11*86400)
    assert ledger.window(int(s.time.time()), None)['now'] == 10*86400


def test_graphql_error_preserves_pending_window(tmp_path, monkeypatch):
    ledger = s.Receipts(tmp_path/'receipts.db')
    monkeypatch.setenv('STRATZ_API_TOKEN', 'synthetic-test-value')
    api = Mock()
    api.request.side_effect = [{'id':'bot'}, {'type':0}, {'id':'app'}, {'items':[]}]
    monkeypatch.setattr(s, 'DiscordHTTP', lambda client, token: api)
    monkeypatch.setattr(s, 'discover', lambda client, now, backfill: [fixture()[0]])
    client = Mock()
    client.post.return_value = httpx.Response(200, json={'errors':[{'message':'synthetic error'}]},
        request=httpx.Request('POST', 'https://example.invalid'))
    with pytest.raises(RuntimeError, match='GraphQL errors'):
        s.run_once(ledger, client, 'synthetic', 'channel')
    assert ledger.conn.execute('SELECT count(*) FROM pending_window').fetchone()[0] == 1
    assert not list(ledger.pending())


def test_parent_is_compact_and_never_duplicates_full_build_sequences(tmp_path, synthetic_match):
    candidate, raw, od = synthetic_match()
    ledger = s.Receipts(tmp_path / 'reference.db')
    ledger.novelty.begin_pass(candidate['start_time'])
    for index in range(1, 41):
        ledger.novelty.observe_and_score(*synthetic_match(-1000-index, reference_index=index))
    ledger.novelty.begin_pass(candidate['start_time'])
    evidence = ledger.novelty.observe_and_score(candidate, raw, od)
    spec = s.payload(candidate, raw, od, {'h_antimage': '123', 'i_armlet': '456'}, evidence=evidence)
    ledger.conn.close()
    embed = spec['parent']['embeds'][0]
    assert 'fields' not in embed and 'footer' not in embed
    assert embed['title'] == 'Rapier → dead in 35s'
    assert embed['author']['name'] == 'Juggernaut'
    assert embed['description'] == '82m · 122 kills'
    assert s.render.check_embeds(spec['parent']) <= 100
    assert all('embeds' not in team and s.check_message(team) == 0 for team in spec['teams'])
    assert len(spec['cards']['radiant']['players'][0]['skills']) == 12
    assert spec['build_evidence']['reference']['matches'] == 40
    assert spec['build_evidence']['items']['0']['receipts'][0]['item_id'] == 151
    assert spec['build_evidence']['skills']['0']['receipts'][0]['pick'] == 1
