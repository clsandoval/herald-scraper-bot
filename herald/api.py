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
        try:
            data = resp.json()
        except ValueError:
            log.warning("explorer_fetch invalid JSON; discovery is incomplete")
            return None
        if not isinstance(data, dict) or data.get("err") or data.get("error"):
            log.warning("explorer_fetch error response; discovery is incomplete")
            if _attempt < 3:
                time.sleep(5)
            continue
        rows = data.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            log.warning("explorer_fetch invalid rows; discovery is incomplete")
            return None
        return rows
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
        if resp.status_code >= 500:
            log.warning("stratz_fetch_batch server failure %s, retrying", resp.status_code)
            if _attempt < 2:
                time.sleep(3)
            continue
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            if strict:
                raise RuntimeError("Stratz returned invalid JSON; report batch incomplete") from None
            log.warning("stratz_fetch_batch invalid JSON; preserving pending candidates")
            return "RATELIMIT"
        if not isinstance(data, dict):
            if strict:
                raise RuntimeError("Stratz returned an invalid response; report batch incomplete")
            return "RATELIMIT"
        if data.get("errors"):
            if strict:
                raise RuntimeError("Stratz GraphQL errors; report batch incomplete")
            # Provider errors are not evidence of an unparsed match. Returning
            # None here used to burn menu attempts and eventually drop candidates.
            log.warning("stratz_fetch_batch GraphQL errors; preserving pending candidates")
            return "RATELIMIT"
        d = data.get("data")
        if not isinstance(d, dict) or any(f"m{i}" not in d for i in range(len(ids))):
            if strict:
                raise RuntimeError("Stratz response omitted report matches")
            log.warning("stratz_fetch_batch incomplete aliases; preserving pending candidates")
            return "RATELIMIT"
        if any(value is not None and (not isinstance(value, dict) or not value)
               for value in (d[f"m{i}"] for i in range(len(ids)))):
            if strict:
                raise RuntimeError("Stratz returned invalid match data; report batch incomplete")
            log.warning("stratz_fetch_batch invalid match shape; preserving pending candidates")
            return "RATELIMIT"
        if any(value is not None and "id" in value and
               (type(value["id"]) is not int or value["id"] != mid)
               for mid, value in ((mid, d[f"m{i}"]) for i, mid in enumerate(ids))):
            if strict:
                raise RuntimeError("Stratz returned mismatched match IDs; report batch incomplete")
            log.warning("stratz_fetch_batch mismatched IDs; preserving pending candidates")
            return "RATELIMIT"
        return {mid: d.get(f"m{i}") for i, mid in enumerate(ids)}
    return "RATELIMIT"  # retries exhausted: rate limit or transport failure
