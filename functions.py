import urllib, cv2, uuid
import pypika
import json
import requests
import time
import logging
import numpy as np
from env import STRATZ_API_TOKEN
from datetime import datetime, timedelta
from pypika import Query, Table
from linkpreview import link_preview, Link, LinkPreview, LinkGrabber
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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

HERO_ID_TO_NAME = {
    1: "antimage",
    2: "axe",
    3: "bane",
    4: "bloodseeker",
    5: "crystal_maiden",
    6: "drow_ranger",
    7: "earthshaker",
    8: "juggernaut",
    9: "mirana",
    10: "morphling",
    11: "nevermore",
    12: "phantom_lancer",
    13: "puck",
    14: "pudge",
    15: "razor",
    16: "sand_king",
    17: "storm_spirit",
    18: "sven",
    19: "tiny",
    20: "vengefulspirit",
    21: "windrunner",
    22: "zuus",
    23: "kunkka",
    25: "lina",
    26: "lion",
    27: "shadow_shaman",
    28: "slardar",
    29: "tidehunter",
    30: "witch_doctor",
    31: "lich",
    32: "riki",
    33: "enigma",
    34: "tinker",
    35: "sniper",
    36: "necrolyte",
    37: "warlock",
    38: "beastmaster",
    39: "queenofpain",
    40: "venomancer",
    41: "faceless_void",
    42: "skeleton_king",
    43: "death_prophet",
    44: "phantom_assassin",
    45: "pugna",
    46: "templar_assassin",
    47: "viper",
    48: "luna",
    49: "dragon_knight",
    50: "dazzle",
    51: "rattletrap",
    52: "leshrac",
    53: "furion",
    54: "life_stealer",
    55: "dark_seer",
    56: "clinkz",
    57: "omniknight",
    58: "enchantress",
    59: "huskar",
    60: "night_stalker",
    61: "broodmother",
    62: "bounty_hunter",
    63: "weaver",
    64: "jakiro",
    65: "batrider",
    66: "chen",
    67: "spectre",
    69: "doom_bringer",
    68: "ancient_apparition",
    70: "ursa",
    71: "spirit_breaker",
    72: "gyrocopter",
    73: "alchemist",
    74: "invoker",
    75: "silencer",
    76: "obsidian_destroyer",
    77: "lycan",
    78: "brewmaster",
    79: "shadow_demon",
    80: "lone_druid",
    81: "chaos_knight",
    82: "meepo",
    83: "treant",
    84: "ogre_magi",
    85: "undying",
    86: "rubick",
    87: "disruptor",
    88: "nyx_assassin",
    89: "naga_siren",
    90: "keeper_of_the_light",
    91: "wisp",
    92: "visage",
    93: "slark",
    94: "medusa",
    95: "troll_warlord",
    96: "centaur",
    97: "magnataur",
    98: "shredder",
    99: "bristleback",
    100: "tusk",
    101: "skywrath_mage",
    102: "abaddon",
    103: "elder_titan",
    104: "legion_commander",
    105: "techies",
    106: "ember_spirit",
    107: "earth_spirit",
    108: "abyssal_underlord",
    109: "terrorblade",
    110: "phoenix",
    111: "oracle",
    112: "winter_wyvern",
    113: "arc_warden",
    114: "monkey_king",
    119: "dark_willow",
    120: "pangolier",
    121: "grimstroke",
    123: "hoodwink",
    126: "void_spirit",
    128: "snapfire",
    129: "mars",
    135: "dawnbreaker",
    136: "marci",
    137: "primal_beast",
    138: "muerta",
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
    grabber = LinkGrabber(
        initial_timeout=20,
        maxsize=1048576,
        receive_timeout=10,
        chunk_size=1024,
    )
    content, url = grabber.get_content(url)
    link = Link(url, content)
    preview = LinkPreview(link, parser="lxml")
    #preview = link_preview(image_url)
    preview_url = preview.image

    img_data = requests.get(preview_url).content
    image_filename = filename
    with open(filename, 'wb') as handler:
        handler.write(img_data)

    preview_image = cv2.imread(filename)
    preview_image = cv2.resize(preview_image,(1200,600))
    cv2.imwrite(filename, preview_image)
    
    return image_filename

def overlay_medals_on_link_preview(match_data_url):
    job_id = uuid.uuid4()

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(options = chrome_options)

    browser.set_window_size(3840,2160)
    browser.get(match_data_url)
    browser.save_screenshot(f'{job_id}_match_data.png')
    browser.close()

    # X crop from 1320 - 1884, 1930 - 2490
    # Y crop from 700 - 740, 700-740
    get_link_preview_image(match_data_url, f'{job_id}_link_preview.png')
    match_data_image = cv2.imread(f'{job_id}_match_data.png')
    link_preview_image = cv2.imread(f'{job_id}_link_preview.png')

    left_medals_image = match_data_image[700:730, 1354:1854]
    right_medals_image = match_data_image[700:730, 1960:2460]

    minimum_brightness = .66
    cols, rows, _= left_medals_image.shape
    brightness = np.sum(left_medals_image) / (255 * cols * rows)
    
    if brightness/minimum_brightness < 1:
        left_medals_image = cv2.convertScaleAbs(left_medals_image, alpha = 1, beta = 0)
        right_medals_image = cv2.convertScaleAbs(right_medals_image, alpha = 1, beta = 0)

    link_preview_image[405:435, 35:535] = left_medals_image
    link_preview_image[405:435, 665:1165] = right_medals_image

    cv2.imwrite( f'{job_id}_link_medal_overlay.png', link_preview_image)

    return f'{job_id}_link_medal_overlay.png'

