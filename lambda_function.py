# %%
from functions import *
import logging, time


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
    kill_density = ret_kill_density_nostratz(match_data)
    players = get_match_data_nostratz(match)["players"]
    leaver = 0
    for player in players:
        if player["leaver_status"] != 0:
            leaver = 1
    if leaver == 0:
        message = (
            "{}\nMatch: opendota.com/matches/{}\nDuration: {}\nKill Density: {}".format(
                date, match, duration, kill_density
            )
        )
        send_message(message)
    time.sleep(0.5)
    logging.info("Scrape complete")
