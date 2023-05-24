# %%
from functions import *

# %%
json_data = query(days=2)
matches = [i["match_id"] for i in json_data["rows"]]
durations = [i["duration"] for i in json_data["rows"]]
# %%
for match_id, duration in zip(matches, durations):
    match_data = query_stratz(match_id)
    total_kills, kill_density = ret_kill_density(match_data, duration)
    if kill_density != -1:
        message = "Match: opendota.com/matches/{}\nDuration: {}\nTotal Kills: {}\nKill Density: {}".format(
            match_id, duration, total_kills, kill_density
        )
        send_message(message)
    time.sleep(0.5)
