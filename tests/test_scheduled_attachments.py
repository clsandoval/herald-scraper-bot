"""Production multipart and durable image recovery through an offline HTTP service."""
import copy
from email import policy
from email.parser import BytesParser
import hashlib
import json

import httpx
import pytest

from herald import card_images, scheduled as s

CHANNEL = '123456'
BOT = '777777'


def report_gallery(message):
    container = next(node for node in message["components"] if node["type"] == 17)
    return next(node for node in container["components"] if node["type"] == 12)


def tiny_spec(mid=987654, *, legacy_text=False):
    """A valid deterministic PNG exercises byte transport without renderer cost."""
    from io import BytesIO
    from PIL import Image
    data = BytesIO()
    Image.new('RGB', (20, 20), '#918ac2').save(data, format='PNG')
    teams, uploads = [], {}
    for stage in ('radiant', 'dire'):
        manifest = s.png_manifest(data.getvalue(), f'herald-{mid}-{stage}.png', f'{stage} team icon card')
        teams.append({'flags': 1 << 15, 'components': [{'type': 17, 'accent_color': 123,
            'components': [{'type': 12, 'items': [
                {'media': {'url': 'attachment://' + manifest['filename']},
                 'description': manifest['description'], 'spoiler': False}]}]}],
                      'attachments': [s.attachment_metadata(manifest)], '_files': [manifest],
                      'allowed_mentions': {'parse': []}})
        if legacy_text:
            teams[-1]['components'][0]['components'].insert(0, {'type': 10, 'content': stage.upper()})
        uploads[stage] = {manifest['filename']: data.getvalue()}
    return s.ReportSpec({'match_id': mid, 'parent': {'embeds': [{'title': f'Match {mid}'}]},
                         'teams': teams, 'thread_name': f'Match {mid}'}, uploads=uploads)


class DiscordService:
    def __init__(self):
        self.messages, self.files = {}, {}
        self.posts, self.requests = [], []
        self.fail_stage = self.reject_stage = None
        self.next_id = 100
        self.omit_component_attachments = False

    def __call__(self, request):
        self.requests.append(request)
        if request.url.host != 'discord.com':
            assert request.url.host == 'cdn.discordapp.com'
            assert not request.headers.get('authorization')
            assert not request.headers.get('cookie')
            return httpx.Response(200, content=self.files[request.url.path])
        assert request.headers['authorization'] == 'Bot synthetic-test-token'
        parts = request.url.path.removeprefix('/api/v10').split('/')
        channel = parts[2]
        if request.method == 'GET':
            if len(parts) == 4:
                return httpx.Response(200, json=[copy.deepcopy(v) for (ch, _), v in self.messages.items()
                                                if ch == channel])
            result = self.messages.get((channel, parts[4]))
            return httpx.Response(200, json=result) if result else httpx.Response(404)
        assert request.method == 'POST'
        files = []
        if request.headers['content-type'].startswith('multipart/form-data'):
            mime = BytesParser(policy=policy.default).parsebytes(
                f'Content-Type: {request.headers["content-type"]}\r\n\r\n'.encode() + request.read())
            for part in mime.iter_parts():
                name = part.get_param('name', header='content-disposition')
                if name == 'payload_json':
                    body = json.loads(part.get_payload(decode=True))
                else:
                    files.append((name, part.get_filename(), part.get_payload(decode=True),
                                  part.get_content_type()))
        else:
            body = json.loads(request.read())
        assert '_files' not in body
        stage = 'thread' if parts[-1] == 'threads' else body['nonce'].split(':')[-1]
        if self.reject_stage == stage:
            return httpx.Response(403, json={'message': 'synthetic denial'})
        self.next_id += 1
        mid = str(self.next_id)
        if stage == 'thread':
            obj = {'id': mid}
            self.messages[channel, parts[4]]['thread'] = obj
        else:
            obj = {**body, 'id': mid, 'author': {'id': BOT}, 'channel_id': channel}
            for attachment, (name, filename, data, content_type) in zip(obj.get('attachments', []), files):
                assert name == f'files[{attachment["id"]}]'
                assert filename == attachment['filename']
                attachment_id = str(self.next_id + 1000)
                url = f'https://cdn.discordapp.com/attachments/{channel}/{attachment_id}/{filename}?ex=refreshed&is=signature'
                attachment.update(id=str(self.next_id + 1000), size=len(data), content_type=content_type,
                                  url=url, proxy_url=url)
                self.files[httpx.URL(url).path] = data
                if obj.get('components'):
                    gallery = report_gallery(obj)
                    gallery['items'][0]['media'] = {'url': url, 'attachment_id': attachment_id,
                        'content_type': content_type, 'width': 20, 'height': 20,
                        'proxy_url': url, 'placeholder': 'response-only'}
                    for component_id, node in enumerate([obj['components'][0], *obj['components'][0]['components']], 1):
                        node['id'] = component_id
                else:
                    obj['embeds'][0]['image']['url'] = url
            if obj.get('components') and self.omit_component_attachments:
                obj['attachments'] = []
            self.messages[channel, mid] = obj
        self.posts.append((stage, copy.deepcopy(body), files))
        if self.fail_stage == stage:
            self.fail_stage = None
            raise KeyboardInterrupt('interruption after Discord accepted write')
        return httpx.Response(200, json=obj)


def transport(service):
    # Deliberately set client-level credentials/cookies: CDN fetch must not copy them.
    client = httpx.Client(transport=httpx.MockTransport(service),
                         headers={'Authorization': 'client-default-secret'},
                         cookies={'test-secret': 'do-not-leak'},
                         auth=('client-user', 'client-password'))
    return s.DiscordHTTP(client, 'synthetic-test-token')


@pytest.mark.parametrize('stage', ['parent', 'thread', 'radiant', 'dire'])
def test_attachment_restart_resumes_exact_original_without_duplicates(tmp_path, stage):
    path = tmp_path / 'receipts.db'
    ledger, service, spec = s.Receipts(path), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = stage
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    frozen = ledger.get(spec['match_id'])['spec']
    assert ledger.conn.execute('SELECT count(*) FROM pending_uploads').fetchone()[0] == 2
    ledger.conn.close()
    ledger = s.Receipts(path)
    new = tiny_spec()
    report_gallery(new['teams'][0])['items'][0]['description'] = 'CHANGED AFTER UPGRADE'
    new.uploads = {'radiant': {'bad.png': b'never use these changed bytes'}}
    receipt = s.deliver(api, ledger, new, CHANNEL, BOT)
    assert receipt['verified'] and receipt['spec'] == frozen
    assert [stage for stage, _, _ in service.posts] == ['parent', 'thread', 'radiant', 'dire']
    for stage, _, files in service.posts[2:]:
        assert files[0][2] == next(iter(spec.uploads[stage].values()))
    assert ledger.conn.execute('SELECT count(*) FROM pending_uploads').fetchone()[0] == 0
    assert all(m['sha256'] in json.dumps(receipt) for team in frozen['teams'] for m in team['_files'])
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4
    ledger.conn.close()


def test_same_nonce_bad_png_bytes_block_without_resending_and_can_reconcile(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    url, data = next(iter(service.files.items()))
    service.files[url] = bytes([data[0] ^ 1]) + data[1:]
    with pytest.raises(RuntimeError, match='bytes did not match'):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert len(service.posts) == 3 and not ledger.get(spec['match_id']).get('verified')
    assert ledger.conn.execute('SELECT count(*) FROM pending_uploads').fetchone()[0] == 2
    service.files[url] = data
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4


@pytest.mark.parametrize('change', ['size', 'filename', 'description', 'url', 'nonce', 'author', 'channel'])
def test_bad_metadata_or_identity_never_causes_duplicate_attachment_send(tmp_path, change):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    obj = next(m for m in service.messages.values() if m.get('nonce', '').endswith(':radiant'))
    if change == 'nonce':
        obj['nonce'] = '987654:dire'
    elif change == 'channel':
        obj['channel_id'] = 'wrong-channel'
    elif change == 'author':
        obj['author']['id'] = 'wrong-bot'
    else:
        obj['attachments'][0][change] = 999 if change == 'size' else 'changed'
    with pytest.raises(RuntimeError):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert len(service.posts) == 3
    assert not ledger.get(spec['match_id']).get('verified')


def test_missing_ambiguous_message_stops_without_blind_resend(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    service.messages = {k: v for k, v in service.messages.items() if not v.get('attachments')}
    with pytest.raises(RuntimeError, match='Unresolved radiant'):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert len(service.posts) == 3
    assert ledger.conn.execute('SELECT count(*) FROM pending_uploads').fetchone()[0] == 2


def test_deleted_known_parent_remains_deleted_and_cleans_temporary_pngs(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    receipt = ledger.get(spec['match_id'])
    del service.messages[CHANNEL, receipt['parent']]
    with pytest.raises(RuntimeError, match='deleted'):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['deleted']
    assert len(service.posts) == 3
    assert ledger.conn.execute('SELECT count(*) FROM pending_uploads').fetchone()[0] == 0


def test_old_json_only_receipt_resumes_without_image_upgrade(tmp_path):
    ledger, service = s.Receipts(tmp_path / 'receipts.db'), DiscordService()
    old = {'match_id': 10, 'parent': {'embeds': [{'title': 'legacy parent'}]},
           'teams': [{'embeds': [{'title': 'legacy RADIANT', 'fields': [{'name': 'old', 'value': 'unchanged'}]}]},
                     {'embeds': [{'title': 'legacy DIRE'}]}], 'thread_name': 'old thread'}
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, old, CHANNEL, BOT)
    receipt = s.deliver(api, ledger, tiny_spec(mid=10), CHANNEL, BOT)
    assert receipt['spec'] == old and receipt['verified']
    assert all(not files for _, _, files in service.posts)
    assert ledger.conn.execute('SELECT count(*) FROM pending_uploads').fetchone()[0] == 0


@pytest.mark.parametrize('stage', ['parent', 'thread', 'radiant', 'dire'])
def test_saved_v2_text_wrappers_resume_unchanged_after_gallery_only_upgrade(tmp_path, stage):
    ledger, service = s.Receipts(tmp_path / 'receipts.db'), DiscordService()
    legacy = tiny_spec(legacy_text=True)
    legacy['parent']['embeds'][0].update(
        fields=[{'name': 'Reference population', 'value': 'original saved reference'}],
        footer={'text': 'original saved footer'})
    before = copy.deepcopy(legacy)
    api = transport(service)
    service.fail_stage = stage
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, legacy, CHANNEL, BOT)
    receipt = s.deliver(api, ledger, tiny_spec(), CHANNEL, BOT)
    assert receipt['verified'] and receipt['spec'] == before
    assert len(service.posts) == 4
    posted = next(body for part, body, _ in service.posts if part == 'radiant')
    container = next(node for node in posted['components'] if node['type'] == 17)
    assert any(node['type'] == 10 and node['content'] == 'RADIANT'
               for node in container['components'])
    ledger.conn.close()


def test_corrupt_pending_bytes_prevent_any_image_upload(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.reject_stage = 'radiant'
    with pytest.raises(s.DefiniteRejection):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    ledger.conn.execute("UPDATE pending_uploads SET data=? WHERE stage='radiant'", (b'corrupted',))
    ledger.conn.commit()
    service.reject_stage = None
    with pytest.raises(RuntimeError, match='byte-integrity'):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert len(service.posts) == 2
    assert 'inflight' not in ledger.get(spec['match_id'])


def test_pending_storage_cap_fails_closed_without_evicting_existing_data(tmp_path, monkeypatch):
    ledger, service = s.Receipts(tmp_path / 'receipts.db'), DiscordService()
    first = tiny_spec(mid=1)
    size = sum(len(data) for files in first.uploads.values() for data in files.values())
    monkeypatch.setattr(s, 'MAX_PENDING_UPLOAD_BYTES', size)
    api = transport(service)
    service.fail_stage = 'parent'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, first, CHANNEL, BOT)
    before = list(ledger.conn.execute('SELECT * FROM pending_uploads'))
    with pytest.raises(RuntimeError, match='storage cap'):
        s.deliver(api, ledger, tiny_spec(mid=2), CHANNEL, BOT)
    assert list(ledger.conn.execute('SELECT * FROM pending_uploads')) == before
    assert ledger.get(2) == {'match_id': 2}
    assert len(service.posts) == 1
    assert s.deliver(api, ledger, first, CHANNEL, BOT)['verified']


def test_missing_icons_still_deliver_exact_offline_renderer_fallback(tmp_path, monkeypatch, synthetic_match):
    monkeypatch.setattr(card_images, '_asset', lambda *args: None)
    candidate, raw, od = synthetic_match()
    spec = s.payload(candidate, raw, od, {})
    for stage, model in spec['cards'].items():
        assert next(iter(spec.uploads[stage].values())) == card_images.render_team_card(model).png_bytes
    ledger, service = s.Receipts(tmp_path / 'receipts.db'), DiscordService()
    assert s.deliver(transport(service), ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4


def test_completed_receipt_remains_destination_and_bot_bound(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    s.deliver(api, ledger, spec, CHANNEL, BOT)
    with pytest.raises(RuntimeError, match='another channel'):
        s.deliver(api, ledger, spec, 'other', BOT)
    with pytest.raises(RuntimeError, match='another bot'):
        s.deliver(api, ledger, spec, CHANNEL, 'other')
    assert len(service.posts) == 4


def test_returned_embed_cdn_url_allows_refreshed_signature_but_not_different_attachment(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    obj = next(m for m in service.messages.values() if m.get('nonce', '').endswith(':radiant'))
    url = obj['attachments'][0]['url']
    report_gallery(obj)['items'][0]['media']['url'] = url.replace('cdn.discordapp.com', 'media.discordapp.net').split('?')[0] + '?ex=older-signature&width=1000'
    assert s.same_message(obj, spec['teams'][0])
    wrong = copy.deepcopy(obj)
    media = report_gallery(wrong)['items'][0]['media']
    media['url'] = media['url'].replace('/1103/', '/999/')
    assert not s.same_message(wrong, spec['teams'][0])
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4


def test_wrong_bot_cannot_poison_unbound_legacy_receipt(tmp_path):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.fail_stage = 'thread'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    legacy = ledger.get(spec['match_id'])
    legacy.pop('bot_id')
    ledger.save(legacy)
    with pytest.raises(RuntimeError, match='did not match'):
        s.deliver(api, ledger, spec, CHANNEL, 'other-bot')
    assert 'bot_id' not in ledger.get(spec['match_id'])
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4


@pytest.mark.parametrize('stage', ['parent', 'thread', 'radiant', 'dire'])
def test_v2_media_only_responses_recover_without_top_level_attachments(tmp_path, stage):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.omit_component_attachments = True
    service.fail_stage = stage
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4
    assert all(not message.get('attachments') for message in service.messages.values())


@pytest.mark.parametrize('change', ['flags', 'color', 'description', 'spoiler', 'attachment_id', 'url', 'type', 'extra'])
def test_v2_component_tampering_fails_closed(tmp_path, change):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.omit_component_attachments = True
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    obj = next(m for m in service.messages.values() if m.get('nonce', '').endswith(':radiant'))
    container = next(node for node in obj['components'] if node['type'] == 17)
    nodes = container['components']
    gallery = report_gallery(obj)
    item = gallery['items'][0]
    if change == 'flags':
        obj['flags'] = 0
    elif change == 'color':
        container['accent_color'] = 999
    elif change in ('description', 'spoiler'):
        item[change] = 'changed' if change == 'description' else True
    elif change in ('attachment_id', 'url'):
        item['media'][change] = '999' if change == 'attachment_id' else 'https://evil.invalid/image.png'
    elif change == 'type':
        gallery['type'] = 13
    else:
        nodes.append({'type': 10, 'content': 'unsaved extra text'})
    with pytest.raises(RuntimeError, match='did not match'):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    assert len(service.posts) == 3
    assert not ledger.get(spec['match_id']).get('verified')


def test_v2_report_contract_rejects_mixed_and_unresolved_components():
    message = tiny_spec()['teams'][0]
    assert s.check_message(message) == 0
    with pytest.raises(ValueError, match='legacy'):
        s.check_message({**message, 'embeds': []})
    bad = copy.deepcopy(message)
    report_gallery(bad)['items'][0]['media']['url'] = 'attachment://missing.png'
    with pytest.raises(ValueError, match='manifest'):
        s.check_message(bad)


def test_legacy_classic_png_receipt_does_not_upgrade_to_v2_on_resume(tmp_path):
    legacy = tiny_spec()
    for stage, message in zip(('radiant', 'dire'), legacy['teams']):
        filename = message['_files'][0]['filename']
        message.pop('flags')
        message.pop('components')
        message['embeds'] = [{'title': stage, 'image': {'url': 'attachment://' + filename}}]
    ledger, service = s.Receipts(tmp_path / 'receipts.db'), DiscordService()
    api = transport(service)
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, legacy, CHANNEL, BOT)
    assert s.deliver(api, ledger, tiny_spec(), CHANNEL, BOT)['spec'] == legacy
    assert len(service.posts) == 4
    assert all('components' not in message for message in service.messages.values())


@pytest.mark.parametrize('top_level', [True, False])
def test_v2_original_media_reference_can_use_matching_returned_cdn_metadata(tmp_path, top_level):
    ledger, service, spec = s.Receipts(tmp_path / 'receipts.db'), DiscordService(), tiny_spec()
    api = transport(service)
    service.omit_component_attachments = not top_level
    service.fail_stage = 'radiant'
    with pytest.raises(KeyboardInterrupt):
        s.deliver(api, ledger, spec, CHANNEL, BOT)
    obj = next(m for m in service.messages.values() if m.get('nonce', '').endswith(':radiant'))
    media = report_gallery(obj)['items'][0]['media']
    media['url'] = 'attachment://' + spec['teams'][0]['_files'][0]['filename']
    assert s.same_message(obj, spec['teams'][0])
    assert s.deliver(api, ledger, spec, CHANNEL, BOT)['verified']
    assert len(service.posts) == 4
