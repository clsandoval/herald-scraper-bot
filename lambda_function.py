# %%
from functions import *
import logging, time
import telebot

tb = telebot.TeleBot("1982794836:AAGupWyxWjOtOiObaM3atPty8hL7OArAv94")
logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    return event


logging.info("Start Herald Match Scraping")
json_data = query(days_back=1)
logging.info("Opendota Data Pulled")
matches = [i["match_id"] for i in json_data["rows"]]
durations = [i["duration"] for i in json_data["rows"]]
dates = [
    datetime.utcfromtimestamp(int(i["start_time"])).strftime("%Y-%m-%d %H:%M:%S")
    for i in json_data["rows"]
]
# %%
for match, duration, date in zip(matches, durations, dates):
    match_data = get_match_data_nostratz(match)
    max_hero_damage, hero_id = get_max_hero_damage(match_data)
    hero_name = HERO_ID_TO_NAME.get(hero_id, "Unknown")
    kill_density = ret_kill_density_nostratz(match_data)
    players = get_match_data_nostratz(match)["players"]
    leaver = 0
    for player in players:
        if player["leaver_status"] != 0:
            leaver = 1
    if leaver == 0:
        # get granular list of player data from stratz
        stratz_players_data = stratz_info(match)["data"]["match"]["players"]
        if check_for_guardian(stratz_players_data):
            continue

        match_summary = f"""
--------------------------------------
| Match ID   : {match}
| Date       : {date}
| Duration   : {duration}
| KD         : {kill_density}
| URL        : stratz.com/matches/{match}
--------------------------------------
"""
        radiant, dire = create_heroes_string(stratz_players_data)
        send_message(f"```{match_summary}```")
        send_message(f"```{radiant}```")
        send_message(f"```{dire}```")

    time.sleep(1)
    logging.info("Scrape complete")

# %%
