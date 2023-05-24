import urllib
import pypika
import json
import requests
import time
from datetime import datetime, timedelta
from pypika import Query, Table

STRATZ_GRAPHQL_URL = "https://api.stratz.com/graphql"
OPENDOTA_URL = "https://api.opendota.com/api/"
QUERY_HEADER = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.11 (KHTML, like Gecko) "
    "Chrome/23.0.1271.64 Safari/537.11",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
    "Accept-Encoding": "none",
    "Accept-Language": "en-US,en;q=0.8",
    "Connection": "keep-alive",
}


def query(url=OPENDOTA_URL, days=1):
    public_matches = Table("public_matches")
    d_t = (datetime.now() - timedelta(days=days)).timestamp()
    base_sql = "explorer?sql="
    q = (
        Query.from_(public_matches)
        .select(
            public_matches.match_id,
            public_matches.start_time,
            public_matches.avg_rank_tier,
            public_matches.duration,
        )
        .where(public_matches.start_time >= d_t)
        .where(public_matches.avg_rank_tier <= 16)
        .where(public_matches.duration > 3000)
    )
    request = url + base_sql + urllib.parse.quote(str(q))
    print(request)
    req = urllib.request.Request(url=request, headers=QUERY_HEADER)
    while True:
        try:
            data = urllib.request.urlopen(req)
            break
        except:
            print("Timeout, retrying in 60 seconds")
            time.sleep(60)
    json_data = json.loads(data.read())
    return json_data


def remove_leavers(data):
    match_ids = set()
    match_data = data["data"]["matches"]
    if match_data == None:
        print(data)
    for match in match_data:
        match_id = match["id"]
        player_data = match["players"]
        for player in player_data:
            if (
                player["leaverStatus"] == "DISCONNECTED_TOO_LONG"
                or player["leaverStatus"] == "ABANDONED"
                or player["leaverStatus"] == "AFK"
            ):
                match_ids.add(match_id)
    return match_ids


def ret_kill_density(data):
    pass


def send_details():
    pass
