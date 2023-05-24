# %%
from functions import *

json_data = query(days=2)
# %%
matches = [i["match_id"] for i in json_data["rows"]]
durations = [i["duration"] for i in json_data["rows"]]
len(matches)

# %%
