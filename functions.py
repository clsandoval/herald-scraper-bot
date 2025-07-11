import urllib
import pypika
import json
import requests
import time
import logging
import numpy as np
import os
import asyncio
import aiohttp
from constants import *
from datetime import datetime, timedelta
from pypika import Query, Table

# Get environment variables
STRATZ_API_TOKEN = os.getenv("STRATZ_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validate required environment variables
if not STRATZ_API_TOKEN:
    logging.error("STRATZ_API_TOKEN environment variable is not set")
    raise ValueError("STRATZ_API_TOKEN environment variable is required")

if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY environment variable is not set")
    raise ValueError("OPENAI_API_KEY environment variable is required")

if not TELEGRAM_BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN environment variable is not set")
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

if not TELEGRAM_CHAT_ID:
    logging.error("TELEGRAM_CHAT_ID environment variable is not set")
    raise ValueError("TELEGRAM_CHAT_ID environment variable is required")

# Selenium and CV2 imports commented out since they're not used in lambda_function.py
# import cv2, uuid
# from linkpreview import link_preview, Link, LinkPreview, LinkGrabber
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By

# Load ability_ids from JSON file
try:
    with open("ability_ids.json", "r") as f:
        ability_ids = json.load(f)
except FileNotFoundError:
    logging.warning("ability_ids.json not found, ability names will show as Unknown")
    ability_ids = {}

# Chrome options function commented out since not used in lambda_function.py
# def get_chrome_options():
#     """Configure Chrome options for Docker/Lambda environment"""
#     chrome_options = Options()
#
#     # Essential headless options
#     chrome_options.add_argument("--headless")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--disable-gpu")
#     chrome_options.add_argument("--disable-web-security")
#     chrome_options.add_argument("--disable-features=VizDisplayCompositor")
#     chrome_options.add_argument("--disable-extensions")
#     chrome_options.add_argument("--disable-plugins")
#     chrome_options.add_argument("--disable-images")
#     chrome_options.add_argument("--disable-javascript")
#     chrome_options.add_argument("--disable-default-apps")
#     chrome_options.add_argument("--disable-background-timer-throttling")
#     chrome_options.add_argument("--disable-backgrounding-occluded-windows")
#     chrome_options.add_argument("--disable-renderer-backgrounding")
#     chrome_options.add_argument("--disable-background-networking")
#     chrome_options.add_argument("--disable-features=TranslateUI")
#     chrome_options.add_argument("--disable-ipc-flooding-protection")
#     chrome_options.add_argument("--single-process")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--remote-debugging-port=9222")
#     chrome_options.add_argument("--disable-software-rasterizer")
#
#     # Memory and performance optimizations
#     chrome_options.add_argument("--memory-pressure-off")
#     chrome_options.add_argument("--max_old_space_size=4096")
#     chrome_options.add_argument("--no-zygote")
#
#     # Set Chrome binary path if available
#     try:
#         chrome_options.binary_location = "/usr/bin/chromium-browser"
#     except:
#         pass
#
#     return chrome_options

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
STRATZ_QUERY = """{
  match(id: MATCH_ID) {
    players {
      heroId
      kills
      deaths
      assists
      position
      steamAccount {
        seasonRank
      }
      stats {
        actionsPerMinute
        abilityCastReport{
          abilityId
          count
          targets{
            target
            count
            damage
            duration
          }
        }
        itemUsed{
          itemId
          count
        }
        itemPurchases {
          time
          itemId
        }
        courierKills {
          time
          positionX
          positionY
        }
        wards {
          time
          positionX
          positionY
          type
        }
        killEvents {
          time
          target
          byAbility
          byItem
        }
        deathEvents {
          time
          attacker
          target
          byItem
          byAbility
          positionX
          positionY
        }
      }
      playbackData {
        purchaseEvents {
          time
          itemId
        }
        abilityLearnEvents {
          time
          abilityId
          level
        }
      }
      level
      item0Id
      item1Id
      item2Id
      item3Id
      item4Id
      item5Id
      heroDamage
      dotaPlus {
        level
      }
      isRadiant
    }
  }
}
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


async def query(url=OPENDOTA_URL, days_back=2, day_period=1):
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
    request_url = url + base_sql + urllib.parse.quote(str(q))

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(request_url, headers=QUERY_HEADER) as response:
                    if response.status == 200:
                        data = await response.text()
                        json_data = json.loads(data)
                        return json_data
                    else:
                        raise aiohttp.ClientError(f"HTTP {response.status}")
            except Exception as e:
                logging.warning(f"Request failed: {e}, retrying in 60 seconds")
                await asyncio.sleep(60)


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
    headers = {"Authorization": f"Bearer {api_token}", "User-Agent": "STRATZ_API"}
    stratz_query = stratz_query.replace("MATCH_ID", str(match))
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


# Functions below are not used in lambda_function.py - commented out to avoid dependency issues

# def get_link_preview_image(image_url, filename):
#     """Not used in lambda_function.py - placeholder function"""
#     return filename

# def overlay_medals_on_link_preview(match_data_url):
#     """Not used in lambda_function.py - placeholder function"""
#     job_id = match_data_url.split("/")[-1]
#     return f"{job_id}_link_medal_overlay.png"

# def overlay_medals_on_link_preview_exact(match_data_url):
#     """Not used in lambda_function.py - placeholder function"""
#     pass


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


def format_match_data(match_data):
    """
    Format match data with ALL available information from the enhanced GraphQL query
    """

    def get_hero_name(hero_id):
        return HEROES.get(hero_id, f"Unknown Hero {hero_id}")

    def get_item_name(item_id):
        if item_id is None:
            return "Empty"
        return ITEMS.get(item_id, f"Unknown Item {item_id}")

    def get_ability_name(ability_id):
        return ability_ids.get(str(ability_id), f"Unknown Ability {ability_id}")

    def format_position(position):
        position_map = {
            "POSITION_1": "Carry",
            "POSITION_2": "Mid",
            "POSITION_3": "Offlaner",
            "POSITION_4": "Soft Support",
            "POSITION_5": "Hard Support",
        }
        return position_map.get(position, position)

    def format_time(seconds):
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    match = match_data["data"]["match"]

    # Header
    result = "=== COMPLETE DOTA 2 MATCH ANALYSIS ===\n\n"

    # Teams
    radiant_players = [p for p in match["players"] if p["isRadiant"]]
    dire_players = [p for p in match["players"] if not p["isRadiant"]]

    # Format team with ALL available data
    def format_team(players, team_name):
        team_result = f"{team_name} TEAM:\n"
        team_result += "=" * 80 + "\n"

        for player in players:
            hero_name = get_hero_name(player["heroId"])
            position = format_position(player["position"])

            # Basic stats
            team_result += f"\n{hero_name} ({position})\n"
            team_result += (
                f"  KDA: {player['kills']}/{player['deaths']}/{player['assists']}\n"
            )
            team_result += f"  Level: {player['level']}\n"
            team_result += f"  Hero Damage: {player['heroDamage']:,}\n"

            # Calculate and display average APM
            if "stats" in player and "actionsPerMinute" in player["stats"]:
                apm_values = player["stats"]["actionsPerMinute"]
                if apm_values:
                    avg_apm = sum(apm_values) / len(apm_values)
                    team_result += f"  Average APM: {avg_apm:.1f}\n"

            # Rank and Dota Plus
            if player["steamAccount"] and player["steamAccount"]["seasonRank"]:
                rank = player["steamAccount"]["seasonRank"]
                team_result += f"  Rank: {rank}\n"

            if player["dotaPlus"] and player["dotaPlus"]["level"]:
                team_result += f"  Dota Plus Level: {player['dotaPlus']['level']}\n"

            # Final Items
            items = [
                get_item_name(player.get("item0Id")),
                get_item_name(player.get("item1Id")),
                get_item_name(player.get("item2Id")),
                get_item_name(player.get("item3Id")),
                get_item_name(player.get("item4Id")),
                get_item_name(player.get("item5Id")),
            ]
            team_result += f"  Final Items: {' | '.join(items)}\n"

            # NEW STATS DATA
            if "stats" in player:
                stats = player["stats"]

                # Actions per minute
                if "actionsPerMinute" in stats:
                    team_result += "  Actions Per Minute:\n"
                    for minute, apm in enumerate(stats["actionsPerMinute"]):
                        team_result += f"    Minute {minute} - {apm} APM\n"

                # Ability Cast Report (NOT WORKING CURRENTLY)
                # if "abilityCastReport" in stats and stats["abilityCastReport"]:
                #    team_result += f"  Ability Usage Summary:\n"
                #
                #    for ability_cast in stats["abilityCastReport"]:
                #        ability_name = get_ability_name(ability_cast["abilityId"])
                #        cast_count = ability_cast["count"]
                #        team_result += f"    {ability_name}: {cast_count} casts\n"
                #
                #        # Targets for this ability
                #        if "targets" in ability_cast and ability_cast["targets"]:
                #            for target in ability_cast["targets"]:
                #                target_name = get_hero_name(
                #                    target.get("target", "Unknown")
                #                )
                #                target_count = target.get("count", 0)
                #                damage = target.get("damage", 0)
                #                duration = target.get("duration", 0)
                #                team_result += f"      -> {target_name}: {target_count} times, {damage} dmg, {duration}s duration\n"

                # Item Usage
                if "itemUsed" in stats and stats["itemUsed"]:
                    team_result += f"  Item Usage Summary:\n"
                    for item_use in stats["itemUsed"]:
                        item_name = get_item_name(item_use["itemId"])
                        use_count = item_use["count"]
                        team_result += f"    {item_name}: Used {use_count} times\n"

                # Item Purchases (detailed timeline)
                if "itemPurchases" in stats and stats["itemPurchases"]:
                    team_result += f"  Complete Purchase History ({len(stats['itemPurchases'])} purchases):\n"
                    for purchase in stats["itemPurchases"]:
                        time_str = format_time(purchase["time"])
                        item_name = get_item_name(purchase["itemId"])
                        team_result += f"    {time_str} - {item_name}\n"

                # Courier Kills
                if "courierKills" in stats and stats["courierKills"]:
                    team_result += f"  Courier Kills ({len(stats['courierKills'])}):\n"
                    for courier_kill in stats["courierKills"]:
                        time_str = format_time(courier_kill["time"])
                        pos_x = courier_kill["positionX"]
                        pos_y = courier_kill["positionY"]
                        team_result += (
                            f"    {time_str} - Courier killed at ({pos_x}, {pos_y})\n"
                        )

                # Ward Placements
                if "wards" in stats and stats["wards"]:
                    team_result += f"  Ward Activity ({len(stats['wards'])} wards):\n"
                    for ward in stats["wards"]:
                        time_str = format_time(ward["time"])
                        pos_x = ward["positionX"]
                        pos_y = ward["positionY"]
                        ward_type = ward.get("type", "Unknown")
                        team_result += (
                            f"    {time_str} - {ward_type} ward at ({pos_x}, {pos_y})\n"
                        )

                # Kill Events
                if "killEvents" in stats and stats["killEvents"]:
                    team_result += (
                        f"  Kill Events ({len(stats['killEvents'])} kills):\n"
                    )
                    for kill in stats["killEvents"]:
                        time_str = format_time(kill["time"])
                        target_name = get_hero_name(kill.get("target", "Unknown"))
                        by_ability = (
                            get_ability_name(kill.get("byAbility"))
                            if kill.get("byAbility")
                            else "Auto-attack"
                        )
                        by_item = (
                            get_item_name(kill.get("byItem"))
                            if kill.get("byItem")
                            else "None"
                        )
                        team_result += (
                            f"    {time_str} - Killed {target_name} with {by_ability}"
                        )
                        if by_item != "None":
                            team_result += f" (using {by_item})"
                        team_result += "\n"

                # Death Events
                if "deathEvents" in stats and stats["deathEvents"]:
                    team_result += (
                        f"  Death Events ({len(stats['deathEvents'])} deaths):\n"
                    )
                    for death in stats["deathEvents"]:
                        time_str = format_time(death["time"])
                        attacker_name = get_hero_name(death.get("attacker", "Unknown"))
                        by_ability = (
                            get_ability_name(death.get("byAbility"))
                            if death.get("byAbility")
                            else "Auto-attack"
                        )
                        by_item = (
                            get_item_name(death.get("byItem"))
                            if death.get("byItem")
                            else "None"
                        )
                        pos_x = death.get("positionX", 0)
                        pos_y = death.get("positionY", 0)
                        team_result += f"    {time_str} - Killed by {attacker_name} with {by_ability}"
                        if by_item != "None":
                            team_result += f" (using {by_item})"
                        team_result += f" at ({pos_x}, {pos_y})\n"

            # Playback Data (skill order)
            if "playbackData" in player:
                if "abilityLearnEvents" in player["playbackData"]:
                    abilities = player["playbackData"]["abilityLearnEvents"]
                    team_result += (
                        f"  Complete Skill Order ({len(abilities)} levels):\n"
                    )
                    for i, ability in enumerate(abilities):
                        time_str = format_time(ability["time"])
                        ability_name = get_ability_name(ability["abilityId"])
                        team_result += f"    Lvl {i+1} ({time_str}): {ability_name}\n"

            team_result += "\n"

        return team_result

    # Add both teams
    result += format_team(radiant_players, "RADIANT")
    result += "\n"
    result += format_team(dire_players, "DIRE")

    return result


def format_player_summary(match_data):
    """
    Format a concise per-player summary with KDA, rank, items, Dota Plus level, and average APM
    """

    def get_hero_name(hero_id):
        return HEROES.get(hero_id, f"Unknown Hero {hero_id}")

    def get_item_name(item_id):
        if item_id is None:
            return "Empty"
        return ITEMS.get(item_id, f"Unknown Item {item_id}")

    def format_position(position):
        position_map = {
            "POSITION_1": "Carry",
            "POSITION_2": "Mid",
            "POSITION_3": "Offlaner",
            "POSITION_4": "Soft Support",
            "POSITION_5": "Hard Support",
        }
        return position_map.get(position, position)

    def format_herald_rank(rank):
        if rank is None:
            return "Unranked"
        if 11 <= rank <= 15:
            herald_level = rank - 10
            return f"Herald {herald_level}"
        else:
            return f"Rank {rank}"

    match = match_data["data"]["match"]

    # Header
    result = "=== PLAYER SUMMARY ===\n\n"

    # Teams
    radiant_players = [p for p in match["players"] if p["isRadiant"]]
    dire_players = [p for p in match["players"] if not p["isRadiant"]]

    def format_team_summary(players, team_name):
        team_result = f"{team_name} TEAM:\n"
        team_result += "-" * 50 + "\n"

        for player in players:
            hero_name = get_hero_name(player["heroId"])
            position = format_position(player["position"])

            # KDA
            kda = f"{player['kills']}/{player['deaths']}/{player['assists']}"

            # Rank
            rank = None
            if player["steamAccount"] and player["steamAccount"]["seasonRank"]:
                rank = player["steamAccount"]["seasonRank"]
            rank_str = format_herald_rank(rank)

            # Items
            items = [
                get_item_name(player.get("item0Id")),
                get_item_name(player.get("item1Id")),
                get_item_name(player.get("item2Id")),
                get_item_name(player.get("item3Id")),
                get_item_name(player.get("item4Id")),
                get_item_name(player.get("item5Id")),
            ]
            items_str = " | ".join(items)

            # Dota Plus Level
            dota_plus_level = "None"
            if player["dotaPlus"] and player["dotaPlus"]["level"]:
                dota_plus_level = str(player["dotaPlus"]["level"])

            # Average APM
            avg_apm = "N/A"
            if "stats" in player and "actionsPerMinute" in player["stats"]:
                apm_values = player["stats"]["actionsPerMinute"]
                if apm_values:
                    avg_apm = f"{sum(apm_values) / len(apm_values):.1f}"

            # Format player line
            team_result += f"{hero_name} ({position})\n"
            team_result += f"  KDA: {kda} | Rank: {rank_str} | APM: {avg_apm} | Dota+: {dota_plus_level}\n"
            team_result += f"  Items: {items_str}\n\n"

        return team_result

    # Add both teams
    result += format_team_summary(radiant_players, "RADIANT")
    result += format_team_summary(dire_players, "DIRE")

    return result


def get_llm_summary(match_data):
    """
    Send formatted match data to LLM for witty analysis
    """

    prompt = f"""

You are Jenkins the famous youtuber who commentates herald level Dota 2 Matches, and you've just reviewed a full Herald-tier match. Your job is to summarize the funniest, weirdest, or most questionable moments in a short, straight to the point no fluff.

Here is the match data (structured JSON):

{match_data}

Write a short match summary focused on:
- Any player doing something extremely dumb or weird (like no boots, multiple Rapiers, skipping ultimate, dying to neutrals, etc.)
- Strange item builds or skill orders
- Very high or low kills/deaths/assists
- Excessive pings, tips, or chat messages
- Abnormal gold/xp swings, throws, or comebacks
- Someone carrying the game solo or feeding nonstop
- Anything that looks like a throw, clown fiesta, or clearly Herald behavior


Example output:
- Juggernaut bought 3 Phase Boots, sold none.
- Crystal Maiden had 0 boots at 43:12, rushed Dagon 3.
- Viper skipped ult until level 16.
- Shadow Fiend went 1–21–3, died 5 times to neutrals.
- Dire led by 19k gold at 48 min, then fed 5-man wipe and lost.
- Pudge leveled Flesh Heap first, maxed it before hook.
- Radiant had no neutral items until 30 min.
- Zeus pinged enemy jungle 47 times in 60 seconds.
- No wards placed by either team after 25 min.
- Invoker disconnected at minute 4, reconnected at minute 38.
"""

    # Using OpenAI API - you'll need to set your API key
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)

        # Set your OpenAI API key here or via environment variable
        # openai.api_key = "your-api-key-here"

        response = client.chat.completions.create(
            model="o3",
            messages=[{"role": "user", "content": prompt}],
        )
        usage = response.usage
        print("input_tokens", usage.prompt_tokens)
        print("output_tokens", usage.completion_tokens)
        print("total_tokens", usage.total_tokens)

        return response.choices[0].message.content.strip()

    except ImportError:
        return "OpenAI library not installed. Run: pip install openai"
    except Exception as e:
        return f"Error calling LLM: {str(e)}"
