"""Shared OpenDota/Stratz transport only; no eligibility, scoring or DB settings.

Importing this module performs no network calls and requires no credentials.
"""
import logging
import os
import time

log = logging.getLogger(__name__)
OPENDOTA_URL = "https://api.opendota.com/api"
EXPLORER_URL = OPENDOTA_URL + "/explorer"
STRATZ_URL = "https://api.stratz.com/graphql"


def explorer_fetch(client, sql):
    """OpenDota Explorer SQL. Needs an explicit User-Agent (default UA gets 403)."""
    params = {"sql": sql}
    headers = {"User-Agent": "herald-scraper-bot"}
    for _attempt in range(4):
        try:
            resp = client.get(EXPLORER_URL, params=params, headers=headers)
        except Exception as e:
            log.warning(f"explorer_fetch exception: {e}, retrying")
            time.sleep(5)
            continue
        if resp.status_code == 429:
            log.warning("explorer_fetch 429, sleeping 10s")
            time.sleep(10)
            continue
        if resp.status_code >= 500:
            log.warning(f"explorer_fetch {resp.status_code}, retrying")
            time.sleep(5)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("err"):
            log.warning(f"explorer_fetch sql error: {data['err']}, retrying")
            time.sleep(5)
            continue
        return data.get("rows") or []
    return None


def stratz_fetch_batch(client, ids, fields, strict=False):
    """One aliased request for the supplied match IDs. Returns
    {match_id: match_or_None}, or the string "RATELIMIT" when Stratz's cap is
    hit — callers must not count that as failed attempts."""
    tok = os.environ.get("STRATZ_API_TOKEN")
    if not tok:
        raise RuntimeError("STRATZ_API_TOKEN not set")
    headers = {"Authorization": f"Bearer {tok.strip()}", "User-Agent": "STRATZ_API"}
    parts = [f"m{i}: match(id: {int(mid)}) {{ {fields} }}" for i, mid in enumerate(ids)]
    body = {"query": "query { " + " ".join(parts) + " }"}
    for _attempt in range(3):
        try:
            resp = client.post(STRATZ_URL, json=body, headers=headers)
        except Exception as e:
            log.warning(f"stratz_fetch_batch exception: {e}, retrying")
            time.sleep(3)
            continue
        if resp.status_code == 429:
            log.warning("stratz_fetch_batch 429, sleeping 30s")
            time.sleep(30)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            if strict:
                raise RuntimeError("Stratz GraphQL errors; report batch incomplete")
            log.warning(f"stratz_fetch_batch errors: {str(data['errors'])[:200]}")
        d = data.get("data") or {}
        if strict and any(f"m{i}" not in d for i in range(len(ids))):
            raise RuntimeError("Stratz response omitted report matches")
        return {mid: d.get(f"m{i}") for i, mid in enumerate(ids)}
    return "RATELIMIT"  # retries exhausted: rate limit or transport failure
