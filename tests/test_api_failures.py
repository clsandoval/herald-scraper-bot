"""Transport/provider failure must not masquerade as an unparsed match."""
from unittest.mock import Mock
import httpx
import pytest
from herald import api, ingest


def response(status=200, data=None, *, text=None):
    request = httpx.Request('POST', api.STRATZ_URL)
    return httpx.Response(status, request=request, **({'text': text} if text is not None else {'json': data}))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('STRATZ_API_TOKEN', 'synthetic-offline-test-token')
    monkeypatch.setattr(api.time, 'sleep', Mock())
    return Mock()


@pytest.mark.parametrize('body', [
    {'errors': [{'message': 'Synthetic provider failure'}]},
    {'data': {'m0': None}, 'errors': [{'message': 'Partial failure'}]},
    {'data': {}}, {'data': None}, {'data': []}, [], None,
])
def test_provider_failure_preserves_menu_candidates(client, body):
    client.post.return_value = response(data=body)
    assert api.stratz_fetch_batch(client, [42], 'id') == 'RATELIMIT'


@pytest.mark.parametrize('body', [
    {'errors': [{'message': 'Synthetic provider failure'}]}, {'data': {}}, [], None,
])
def test_strict_reporter_rejects_incomplete_response(client, body):
    client.post.return_value = response(data=body)
    with pytest.raises(RuntimeError):
        api.stratz_fetch_batch(client, [42], 'id', strict=True)


def test_explicit_null_match_is_distinct_from_missing_alias(client):
    client.post.return_value = response(data={'data': {'m0': None}})
    assert api.stratz_fetch_batch(client, [42], 'id') == {42: None}


def test_server_failure_retries_with_bounded_attempts(client):
    client.post.side_effect = [response(503), response(502), response(data={'data': {'m0': {'id': 42}}})]
    assert api.stratz_fetch_batch(client, [42], 'id') == {42: {'id': 42}}
    assert client.post.call_count == 3


def test_exhausted_server_failures_preserve_pending(client):
    client.post.return_value = response(503)
    assert api.stratz_fetch_batch(client, [42], 'id') == 'RATELIMIT'
    assert client.post.call_count == 3


@pytest.mark.parametrize('strict', [True, False])
def test_invalid_json_is_not_a_missing_match(client, strict):
    client.post.return_value = response(text='not-json')
    if strict:
        with pytest.raises(RuntimeError, match='invalid JSON'):
            api.stratz_fetch_batch(client, [42], 'id', strict=True)
    else:
        assert api.stratz_fetch_batch(client, [42], 'id') == 'RATELIMIT'


def test_permanent_http_rejection_is_not_retried(client):
    client.post.return_value = response(401)
    with pytest.raises(httpx.HTTPStatusError):
        api.stratz_fetch_batch(client, [42], 'id')
    assert client.post.call_count == 1


def test_enrichment_provider_error_does_not_consume_match_attempt(tmp_path, client, monkeypatch):
    conn = ingest.get_conn(str(tmp_path / 'pending.db'))
    conn.execute('INSERT INTO pending(match_id,avg_rank_tier,start_time,discovered_at,attempts) VALUES(42,12,1,1,7)')
    conn.commit()
    client.post.return_value = response(data={'errors': [{'message': 'Synthetic provider failure'}]})
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(ingest.httpx, 'Client', Mock(return_value=client))
    try:
        assert ingest.enrich(conn) == (0, 0, 0, 0)
        assert conn.execute('SELECT match_id,attempts FROM pending').fetchall() == [(42, 7)]
    finally:
        conn.close()

@pytest.mark.parametrize('value', [False, [], '', 1, {}, {'id': 43}, {'id': True}])
@pytest.mark.parametrize('strict', [False, True])
def test_invalid_nested_match_is_not_unparsed_or_wrong_match(client, value, strict):
    client.post.return_value = response(data={'data': {'m0': value}})
    if strict:
        with pytest.raises(RuntimeError):
            api.stratz_fetch_batch(client, [42], 'id', strict=True)
    else:
        assert api.stratz_fetch_batch(client, [42], 'id') == 'RATELIMIT'
