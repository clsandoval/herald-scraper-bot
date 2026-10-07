"""Offline synthetic factories for independently publishable core reporter tests.

These fixtures intentionally do not import the optional example sender.
"""
from contextlib import closing
import sqlite3

import pytest

from herald import reporter_novelty

FIXTURE_NOW = 1_704_067_200
_HERO_SKILLS = (
    (1, (5003, 5004, 7314, 5006)),
    (2, (5007, 5008, 5009, 5010)),
    (3, (5011, 5012, 5014, 5013)),
    (5, (5126, 5127, 5128, 5129)),
    (6, (5019, 5632, 343, 5022)),
    (8, (5028, 5029, 5027, 5030)),
    (11, (5059, 5062, 5063, 5064)),
    (14, (5075, 5076, 5074, 5077)),
    (25, (5040, 5041, 5042, 5043)),
    (32, (5142, 5143, 5144, 5145)),
)


def _synthetic_match(match_id=-101, *, reference_index=None, missing=False):
    """Deterministic invented gameplay, without player identities or source URLs."""
    candidate = {"match_id": match_id, "duration": 4920, "avg_rank_tier": 15,
                 "start_time": FIXTURE_NOW - (reference_index or 0) * 3600}
    players = []
    for index, (hero, skills) in enumerate(_HERO_SKILLS):
        item = 116 if index == 0 else 151
        sequence = [skills[i] for i in (0, 1, 0, 1, 0, 3, 0, 1, 2, 2, 2, 3)]
        if reference_index is None and index == 0:
            item = 151  # Held-out purchase, common only on other synthetic heroes.
            sequence[0] = skills[2]
        player = {
            "heroId": hero, "isRadiant": index < 5, "steamAccount": {"seasonRank": 15},
            "kills": 9 + index, "deaths": 8 + index, "assists": 12 + index,
            "dotaPlus": {"level": 4},
            **{f"item{slot}Id": value for slot, value in
               enumerate((item, 1, 112, 108, None, None))},
            "abilities": [{"abilityId": ability, "time": pick * 90, "isTalent": False}
                          for pick, ability in enumerate(sequence)],
            "stats": {"actionsPerMinute": [45, 50, 55],
                      "itemPurchases": [{"itemId": item, "time": 1200}],
                      "deathEvents": []},
        }
        if reference_index is None and index == 5 and not missing:
            player["item4Id"] = 133
            player["stats"]["itemPurchases"].append({"itemId": 133, "time": 4500})
            player["stats"]["deathEvents"] = [
                {"time": 4535, "timeDead": 90, "isDieBack": False},
            ]
        if missing and index == 0:
            player.pop("abilities")
            player["stats"].pop("itemPurchases")
        players.append(player)
    raw = {"gameMode": "ALL_PICK_RANKED", "players": players}
    od = {"patch": 1, "duration": candidate["duration"], "radiant_score": 55,
          "dire_score": 67, "players": [{"leaver_status": 0} for _ in players]}
    return candidate, raw, od


@pytest.fixture
def synthetic_match():
    return _synthetic_match


@pytest.fixture
def synthetic_evidence():
    def score(match):
        with closing(sqlite3.connect(":memory:")) as conn:
            store = reporter_novelty.ReferenceStore(conn)
            store.begin_pass(FIXTURE_NOW)
            for index in range(1, 41):
                store.observe_and_score(*_synthetic_match(-1000 - index, reference_index=index))
            store.begin_pass(FIXTURE_NOW)
            result = store.observe_and_score(*match)
        result["reference"]["population"] = "generated synthetic example matches"
        result["reference"]["synthetic"] = True
        return result
    return score
