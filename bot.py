# %%
from functions import *
import logging

# %%
logging.info("Start Herald Match Scraping")
json_data = query(days=7)
logging.info("Opendota Data Pulled")
matches = [i["match_id"] for i in json_data["rows"]]
durations = [i["duration"] for i in json_data["rows"]]
dates = [
    datetime.utcfromtimestamp(int(i["start_time"])).strftime("%Y-%m-%d %H:%M:%S")
    for i in json_data["rows"]
]
# %%
for match_id, duration, date in zip(matches, durations, dates):
    match_data = query_stratz(match_id)
    total_kills, kill_density = ret_kill_density(match_data, duration)
    if kill_density != -1 and kill_density > 1.5:
        message = "{}\nMatch: opendota.com/matches/{}\nDuration: {}\nTotal Kills: {}\nKill Density: {}".format(
            date, match_id, duration, total_kills, kill_density
        )
        send_message(message)
    time.sleep(0.5)
logging.info("TG Messages Sent")

# %%
for match_id, duration in sorted(list(zip(matches, durations)), key=lambda x: x[1]):
    print(match_id, duration)
# %%
