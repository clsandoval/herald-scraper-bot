# %%
from functions import *
import logging, time

logging.info("Start Herald Match Scraping")
json_data = query(days=7)
logging.info("Opendota Data Pulled")
matches = [i["match_id"] for i in json_data["rows"]]
durations = [i["duration"] for i in json_data["rows"]]
dates = [
    datetime.utcfromtimestamp(int(i["start_time"])).strftime("%Y-%m-%d %H:%M:%S")
    for i in json_data["rows"]
]
# %% kill density = kills/duration

for match, duration, date in zip(matches, durations, dates):
    message = "{}\nMatch: opendota.com/matches/{}\nDuration: {}".format(
        date, match, duration
    )
    send_message(message)
    time.sleep(0.5)
logging.info("Scrape complete")
