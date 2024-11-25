import urllib, cv2, uuid
import pypika
import json
import requests
import time
import logging
import numpy as np
from constants import *
from env import STRATZ_API_TOKEN
from datetime import datetime, timedelta
from pypika import Query, Table
from linkpreview import link_preview, Link, LinkPreview, LinkGrabber
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

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

STRATZ_INFO = """{{
  match(id:{}) {{
    players{{
    heroId,
    kills,
    deaths,
    assists,
    position,
    steamAccount{{
      seasonRank
    }}
      item0Id,
      item1Id,
      item2Id,
      item3Id,
      item4Id,
      item5Id,
      heroDamage,
      dotaPlus{{
        level
      }}
      isRadiant
    }}
  }}
}}
"""


def query(url=OPENDOTA_URL, days_back=2, day_period=1):
    public_matches = Table("public_matches")
    day_end = (datetime.now() - timedelta(days=days_back)).timestamp()
    day_start = (datetime.now() - timedelta(days=days_back + day_period)).timestamp()
    base_sql = "explorer?sql="
    q = (
        Query.from_(public_matches)
        .select(
            public_matches.match_id,
            public_matches.start_time,
            public_matches.avg_rank_tier,
            public_matches.duration,
        )
        .where(public_matches.start_time >= day_start)
        .where(public_matches.start_time <= day_end)
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
        "disable_web_page_preview": True,
        "disable_notification": False,
        "chat_id": "1405224455",
        "parse_mode": "MarkdownV2",
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


def stratz_info(
    match_id,
    url=STRATZ_GRAPHQL_URL,
    stratz_query=STRATZ_INFO,
    api_token=STRATZ_API_TOKEN,
):
    headers = {"Authorization": f"Bearer {api_token}", "User-Agent": "STRATZ_API"}
    url = url
    stratz_query = stratz_query.format(match_id)
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


def get_max_hero_damage(match_data):
    player_data = match_data["players"]
    max_hero_damage = 0
    hero_id = 0
    for player in player_data:
        if max_hero_damage < player["hero_damage"]:
            max_hero_damage = player["hero_damage"]
            hero_id = player["hero_id"]
    return max_hero_damage, hero_id


def get_link_preview_image(image_url, filename):
    url = image_url
    image_filename = filename
    while True:
        try:
            grabber = LinkGrabber(
                initial_timeout=20,
                maxsize=1048576,
                receive_timeout=10,
                chunk_size=1024,
            )
            content, url = grabber.get_content(url)
            link = Link(url, content)
            preview = LinkPreview(link, parser="lxml")
            preview_url = preview.image

            img_data = requests.get(preview_url).content
            with open(filename, "wb") as handler:
                handler.write(img_data)

            preview_image = cv2.imread(filename)
            preview_image = cv2.resize(preview_image, (1200, 600))
            break
        except:
            logging.warning("Link grabbing failed, retrying in 5 seconds")
            time.sleep(5)
            continue

    cv2.imwrite(filename, preview_image)
    return image_filename


def overlay_medals_on_link_preview(match_data_url):
    job_id = match_data_url.split("/")[-1]

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(options=chrome_options)

    browser.set_window_size(3840, 2160)
    browser.get(match_data_url)
    time.sleep(1)  # let page load
    browser.execute_script("document.body.style.zoom='150%'")
    browser.save_screenshot(f"{job_id}_match_data.png")
    browser.close()

    # X crop from 1320 - 1884, 1930 - 2490
    # Y crop from 700 - 740, 700-740
    get_link_preview_image(match_data_url, f"{job_id}_link_preview.png")
    match_data_image = cv2.imread(f"{job_id}_match_data.png")
    link_preview_image = cv2.imread(f"{job_id}_link_preview.png")

    left_medals_image = match_data_image[700:730, 1354:1854]
    right_medals_image = match_data_image[700:730, 1960:2460]

    minimum_brightness = 0.66
    cols, rows, _ = left_medals_image.shape
    brightness = np.sum(left_medals_image) / (255 * cols * rows)
    ratio = brightness / minimum_brightness

    if ratio < 1:
        left_medals_image = cv2.convertScaleAbs(
            left_medals_image, alpha=1 / ratio, beta=0
        )
        right_medals_image = cv2.convertScaleAbs(
            right_medals_image, alpha=1 / ratio, beta=0
        )

    link_preview_image[405:435, 35:535] = left_medals_image
    link_preview_image[405:435, 665:1165] = right_medals_image

    cv2.imwrite(f"{job_id}_link_medal_overlay.png", link_preview_image)

    return f"{job_id}_link_medal_overlay.png"


def overlay_medals_on_link_preview_exact(match_data_url):
    job_id = match_data_url.split("/")[-1]

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(options=chrome_options)

    browser.set_window_size(3840, 2160)
    browser.get(match_data_url)
    time.sleep(1)  # let page load
    s = browser.find_elements(By.XPATH, "//div[@data-heroid]")
    links = [elem.get_attribute("href") for elem in s]
    print(links)


def create_heroes_string(stratz_data):
    heroes = [
        {
            "name": HERO_ID_TO_NAME[x["heroId"]],
            "position": x["position"] if x["position"] else "Not Provided",
            "kills": x["kills"],
            "deaths": x["deaths"],
            "assists": x["assists"],
            "damage_done": x["heroDamage"],
            "dota_plus": x["dotaPlus"],
            "rank": (x["steamAccount"]["seasonRank"]),
            "items": [
                ITEM_MAP.get(str(x["item0Id"]), ""),
                ITEM_MAP.get(str(x["item1Id"]), ""),
                ITEM_MAP.get(str(x["item2Id"]), ""),
                ITEM_MAP.get(str(x["item3Id"]), ""),
                ITEM_MAP.get(str(x["item4Id"]), ""),
                ITEM_MAP.get(str(x["item5Id"]), ""),
            ],
            "isRadiant": x["isRadiant"],
        }
        for x in stratz_data
    ]

    radiant_heroes = [hero for hero in heroes if hero["isRadiant"]]
    dire_heroes = [hero for hero in heroes if not hero["isRadiant"]]

    # Function to generate a table for each hero
    def generate_hero_table(team_heroes, team_name):
        tables = []
        for hero in team_heroes:
            dota_plus_level = -1
            if hero["dota_plus"] is not None:
                dota_plus_level = hero["dota_plus"].get("level", -1)
            # Attribute rows for each hero
            kills, deaths, assists = hero["kills"], hero["deaths"], hero["assists"]
            rows = [
                ["Rank", RANK_MAP.get(hero["rank"], "No Medal")],
                ["Position", hero["position"]],
                ["K/D/A", f"{kills}/{deaths}/{assists}"],
                ["Damage Done", f"{hero['damage_done']:,}"],
                ["Dota Plus Level", f"{dota_plus_level:,}"],
            ]

            # Two item rows, three items each
            item1, item2, item3 = hero["items"][0], hero["items"][1], hero["items"][2]
            item4, item5, item6 = hero["items"][3], hero["items"][4], hero["items"][5]
            item_row_1 = f"{item1}, {item2}, {item3}"
            item_row_2 = f"{item4}, {item5}, {item6}"

            # Build formatted table for this hero
            col_width = 20
            format_row = "{:<20} | {:<" + f"{col_width}" + "}"

            # Table header
            table = f"""
{team_name} - {hero['name']}
{'-' * (col_width )}
"""
            # Add the rows to the table
            table += "\n".join([format_row.format(*row) for row in rows])
            table += f"\n{item_row_1}"
            table += f"\n{item_row_2}"

            # Add this table to the list of tables
            tables.append(table)

        return "\n".join(tables)

    # Generate and print tables for both teams
    radiant = generate_hero_table(radiant_heroes, "Radiant")
    dire = generate_hero_table(dire_heroes, "Dire")
    return radiant, dire


def check_for_guardian(stratz_data):
    for x in stratz_data:
        rank = x["steamAccount"]["seasonRank"] or 0
        if rank > 15:
            return True
    return False
