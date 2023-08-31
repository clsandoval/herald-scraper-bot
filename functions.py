import urllib
import pypika
import json
import requests
import time
import logging
from env import STRATZ_API_TOKEN
from datetime import datetime, timedelta
from pypika import Query, Table


TG_URL = "https://api.telegram.org/bot1982794836%3AAAGupWyxWjOtOiObaM3atPty8hL7OArAv94/sendMessage"
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
STRATZ_QUERY = """{{
  match(id:{}) {{
  	radiantKills
    direKills
    durationSeconds
    players{{
      leaverStatus
    }}
  }}
}}
"""


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
        .where(public_matches.duration > 4500)
    )
    request = url + base_sql + urllib.parse.quote(str(q))
    req = urllib.request.Request(url=request, headers=QUERY_HEADER)
    while True:
        try:
            data = urllib.request.urlopen(req)
            break
        except:
            logging.warning("Timeout, retrying in 60 seconds")
            time.sleep(60)
    json_data = json.loads(data.read())
    return json_data


def get_match_data_nostratz(match_id):
    request = OPENDOTA_URL + "matches/{}".format(match_id)
    req = urllib.request.Request(url=request, headers=QUERY_HEADER)
    while True:
        try:
            data = urllib.request.urlopen(req)
            break
        except:
            logging.warning("Timeout, retrying in 60 seconds")
            time.sleep(60)
    json_data = json.loads(data.read())
    return json_data


def ret_kill_density_nostratz(match_data):
    duration, radiant_kills, dire_kills = (
        match_data["duration"],
        match_data["radiant_score"],
        match_data["dire_score"],
    )
    return (radiant_kills + dire_kills) / (duration / 60)


def ret_kill_density(data, duration):
    match_data = data["data"]["match"]
    radiantKills = sum(match_data["radiantKills"])
    direKills = sum(match_data["radiantKills"])
    totalKills = radiantKills + direKills
    kill_density = totalKills / (duration / 60)
    for status in match_data["players"]:
        if (
            status["leaverStatus"] == "DISCONNECTED_TOO_LONG"
            or status["leaverStatus"] == "ABANDONED"
            or status["leaverStatus"] == "AFK"
        ):
            return -1, -1
    return totalKills, kill_density


def send_message(message):
    payload = {
        "text": message,
        "disable_web_page_preview": False,
        "disable_notification": False,
        "chat_id": "1405224455",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Telegram Bot SDK - (https://github.com/irazasyed/telegram-bot-sdk)",
        "Content-Type": "application/json",
    }
    with requests.Session() as s:
        s.keep_alive = False
        response = s.request("POST", TG_URL, json=payload, headers=headers, timeout=5)
    payload = {
        "text": message,
        "disable_web_page_preview": False,
        "disable_notification": False,
        "chat_id": "1057769032",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Telegram Bot SDK - (https://github.com/irazasyed/telegram-bot-sdk)",
        "Content-Type": "application/json",
    }
    with requests.Session() as s:
        s.keep_alive = False
        try:
            response = s.request(
                "POST", TG_URL, json=payload, headers=headers, timeout=5
            )
            print("Telegram Message Status {}".format(response))
        except:
            print("Telegram API Timeout")
        time.sleep(0.5)


def query_stratz(
    match,
    url=STRATZ_GRAPHQL_URL,
    stratz_query=STRATZ_QUERY,
    api_token=STRATZ_API_TOKEN,
):
    headers = {"Authorization": f"Bearer {api_token}"}
    url = url
    stratz_query = stratz_query.format(match)
    stratz_query = stratz_query.replace("{{", "{")
    stratz_query = stratz_query.replace("}}", "}")
    while True:
        try:
            r = requests.post(url, json={"query": stratz_query}, headers=headers)
            break
        except:
            print("Stratz timeout, retrying in 1 second")
            time.sleep(1)
    data = json.loads(r.text)
    return data
