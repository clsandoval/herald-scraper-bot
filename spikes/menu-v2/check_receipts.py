"""Offline assertion harness for render.player_receipts / render.megas_tag.

No discord/env/network — imports ONLY `render` (not live_board: live_board
opens the DB + builds TEMP tables at import time and is not offline-importable).

Run: python3 spikes/menu-v2/check_receipts.py
"""

import sys

import render


def _player(deathEvents=None, itemPurchases=None, itemUsed=None, isRandom=False):
    return {
        "isRandom": isRandom,
        "stats": {
            "deathEvents": deathEvents or [],
            "itemPurchases": itemPurchases or [],
            "itemUsed": itemUsed or [],
        },
    }


def _death(timeDead=0, goldFed=0, isDieBack=False, isAttemptTpOut=False):
    return {
        "time": 0, "timeDead": timeDead, "goldFed": goldFed, "goldLost": 0,
        "isDieBack": isDieBack, "isAttemptTpOut": isAttemptTpOut, "hasHealAvailable": False,
    }


def check_receipts():
    try:
        # timeDead sum 1300s (>=1200) -> feeding line present, "21 min" + goldFed
        p = _player(deathEvents=[_death(timeDead=700, goldFed=8000), _death(timeDead=600, goldFed=7000)])
        recs = render.player_receipts(p, duration_s=6200)
        assert any("21 min" in r and "dead" in r and "fed" in r for r in recs), (
            f"expected feeding line, got {recs}"
        )

        # timeDead 300s, frac<0.33 -> no feeding line
        p = _player(deathEvents=[_death(timeDead=300, goldFed=1000)])
        recs = render.player_receipts(p, duration_s=3000)
        assert not any("dead" in r for r in recs), f"expected no feeding line, got {recs}"

        # BKB bought (116, time>0), itemUsed lacks 116 -> "BKB bought, never used"
        p = _player(itemPurchases=[{"time": 600, "itemId": 116}], itemUsed=[])
        recs = render.player_receipts(p, duration_s=3000)
        assert any("BKB bought, never used" in r for r in recs), f"expected BKB tag, got {recs}"

        # Midas bought (65, time>0), itemUsed count 5 for 65 -> "Midas, 5 uses"
        p = _player(itemPurchases=[{"time": 300, "itemId": 65}],
                    itemUsed=[{"itemId": 65, "count": 5}])
        recs = render.player_receipts(p, duration_s=3000)
        assert any("Midas, 5 uses" in r for r in recs), f"expected Midas tag, got {recs}"

        # isRandom truthy -> "randomed"
        p = _player(isRandom=True)
        recs = render.player_receipts(p, duration_s=3000)
        assert any("randomed" in r for r in recs), f"expected randomed tag, got {recs}"

        # 2 deathEvents with isAttemptTpOut -> "died mid-TP x2"; 1 -> absent
        p = _player(deathEvents=[_death(isAttemptTpOut=True), _death(isAttemptTpOut=True)])
        recs = render.player_receipts(p, duration_s=3000)
        assert any("died mid-TP x2" in r for r in recs), f"expected mid-TP x2, got {recs}"

        p = _player(deathEvents=[_death(isAttemptTpOut=True)])
        recs = render.player_receipts(p, duration_s=3000)
        assert not any("died mid-TP" in r for r in recs), f"expected no mid-TP tag, got {recs}"

        # 2 deathEvents with isDieBack -> "buyback then died x2"; 1 -> absent
        p = _player(deathEvents=[_death(isDieBack=True), _death(isDieBack=True)])
        recs = render.player_receipts(p, duration_s=3000)
        assert any("buyback then died x2" in r for r in recs), f"expected buyback x2, got {recs}"

        p = _player(deathEvents=[_death(isDieBack=True)])
        recs = render.player_receipts(p, duration_s=3000)
        assert not any("buyback then died" in r for r in recs), f"expected no buyback tag, got {recs}"

        # nothing qualifies -> []
        p = _player()
        assert render.player_receipts(p, duration_s=3000) == [], "expected empty receipts"

        # megas_tag: didRadiantWin=True + barracksStatusRadiant=0 -> non-None
        raw = {"didRadiantWin": True, "barracksStatusRadiant": 0, "barracksStatusDire": 63}
        tag = render.megas_tag(raw)
        assert tag is not None, "expected non-None megas_tag"

        # barracksStatusRadiant=63 -> None
        raw = {"didRadiantWin": True, "barracksStatusRadiant": 63, "barracksStatusDire": 0}
        assert render.megas_tag(raw) is None, "expected None megas_tag"

        # spoiler contract: player_receipts strings are winner-neutral (no
        # win/mega wording), megas_tag IS outcome-revealing — the two helpers
        # must stay cleanly separated so _focus can gate only megas_tag on `sp`.
        FORBIDDEN = ("win", "Won", "mega")
        all_neutral_recs = []
        for p in (
            _player(deathEvents=[_death(timeDead=1300, goldFed=15000)]),
            _player(itemPurchases=[{"time": 600, "itemId": 116}]),
            _player(itemPurchases=[{"time": 300, "itemId": 65}], itemUsed=[{"itemId": 65, "count": 5}]),
            _player(isRandom=True),
            _player(deathEvents=[_death(isAttemptTpOut=True), _death(isAttemptTpOut=True)]),
            _player(deathEvents=[_death(isDieBack=True), _death(isDieBack=True)]),
        ):
            all_neutral_recs += render.player_receipts(p, duration_s=6200)
        for r in all_neutral_recs:
            assert not any(f in r for f in FORBIDDEN), f"receipt leaks outcome wording: {r!r}"

        winning_tag = render.megas_tag({"didRadiantWin": True, "barracksStatusRadiant": 0,
                                        "barracksStatusDire": 63})
        assert any(f.lower() in winning_tag.lower() for f in ("win", "mega")), (
            f"megas_tag should be outcome-revealing, got {winning_tag!r}"
        )

        print("check_receipts OK")
        return 0
    except AssertionError as e:
        print(f"check_receipts FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(check_receipts())
