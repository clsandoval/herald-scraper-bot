# %%
from functions import *
import logging, time
import telebot

tb = telebot.TeleBot("1982794836:AAGupWyxWjOtOiObaM3atPty8hL7OArAv94")
logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    return event


logging.info("Start Herald Match Scraping")
json_data = query(days=1)
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
    hero_name = HERO_ID_TO_NAME[hero_id]
    kill_density = ret_kill_density_nostratz(match_data)
    players = get_match_data_nostratz(match)["players"]
    leaver = 0
    for player in players:
        if player["leaver_status"] != 0:
            leaver = 1
    if leaver == 0:
        message = """
        stratz.com/matches/{}\nDuration: {}\nKill Density: {}\nMax Hero Damage: {}\nHero: {}\n
        """.format(
            match,
            duration,
            kill_density,
            max_hero_damage,
            hero_name,
        )
        send_message(message)
        # medal_overlay_filepath = overlay_medals_on_link_preview(f'https://stratz.com/matches/{match}')
        # with open(medal_overlay_filepath, 'rb') as f:
        #    tb.send_photo('1405224455', f, caption=message, parse_mode='HTML')
    time.sleep(1)
    logging.info("Scrape complete")

# %%
