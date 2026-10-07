"""Sparse skill logs and interrupted corpus rescoring, entirely offline."""
import json

import pytest

from herald import ingest


@pytest.fixture
def db():
    conn = ingest.get_conn(":memory:")
    yield conn
    conn.close()


def add_build(db, mid, skills, *, mode="ALL_PICK_RANKED"):
    raw = {"gameMode": mode, "players": [{
        "heroId": 1, "abilities": [
            {"abilityId": ability, "isTalent": False, "time": index * 60}
            for index, ability in enumerate(skills)
        ],
    }]}
    db.execute("INSERT INTO matches(match_id, raw) VALUES (?, ?)", (mid, json.dumps(raw)))
    db.commit()


@pytest.mark.parametrize("skills", [[], [5003] * 4, [5003, 5004] * 2,
                                    [5003, 5004, 5003, 5004, 5003]])
def test_incomplete_builds_are_unscored_not_divided_by_zero(db, skills):
    # Three observations are enough to enter the ability pool, but <6 picks
    # intentionally never enter the positional corpus. Both passes must agree.
    for mid in range(3):
        add_build(db, mid, skills)
    assert ingest.score_skill_weirdness(db) == 3
    rows = db.execute("SELECT skill_weirdness, skill_notes FROM matches").fetchall()
    assert rows == [(0.0, "[]")] * 3


def test_complete_builds_still_score_and_short_logs_do_not_get_receipts(db):
    for mid in range(3):
        add_build(db, mid, [5003, 5004] * 3)
    add_build(db, 10, [5003, 5004] * 2)
    ingest.score_skill_weirdness(db)
    scores = dict(db.execute("SELECT match_id, skill_weirdness FROM matches"))
    assert all(scores[mid] > 0 for mid in range(3))
    assert scores[10] == 0
    notes = db.execute("SELECT skill_notes FROM matches WHERE match_id=10").fetchone()[0]
    assert json.loads(notes) == []


def test_new_ability_id_has_readable_receipt_without_crashing(db):
    for mid in range(3):
        add_build(db, mid, [999999] * 3 + [5004] * 3)
    ingest.score_skill_weirdness(db)
    notes = json.loads(db.execute("SELECT skill_notes FROM matches LIMIT 1").fetchone()[0])
    assert all(isinstance(pick[0], str) for note in notes for pick in note["picks"])
    assert "Ability 999999" in json.dumps(notes)
    assert notes[0]["tag"] == "opened Ability 999999 x3"


@pytest.mark.parametrize("mode", ["SINGLE_DRAFT", "RANDOM_DRAFT"])
def test_sparse_modes_remain_excluded(db, mode):
    for mid in range(3):
        add_build(db, mid, [5003, 5004] * 3, mode=mode)
    ingest.score_skill_weirdness(db)
    assert db.execute("SELECT skill_weirdness, skill_notes FROM matches").fetchall() == [
        (0.0, None)] * 3


@pytest.mark.parametrize("item, skill", [(None, 1.0), (1.0, None)])
def test_partial_score_pair_recovers_without_50_cycle_wait(db, item, skill):
    db.execute("INSERT INTO matches(match_id, weirdness, skill_weirdness) VALUES (1, ?, ?)",
               (item, skill))
    assert ingest.should_rescore(db, 1)


def test_new_rows_keep_existing_batch_threshold_and_periodic_cadence(db):
    db.executemany("INSERT INTO matches(match_id) VALUES (?)", [(i,) for i in range(500)])
    assert not ingest.should_rescore(db, 0)
    assert not ingest.should_rescore(db, 49)
    assert ingest.should_rescore(db, 50)
    assert ingest.should_rescore(db, 1, retry=True)
    db.execute("INSERT INTO matches(match_id) VALUES (500)")
    assert ingest.should_rescore(db, 1)


def test_complete_and_empty_archives_do_not_rescore_at_boot(db):
    assert not ingest.should_rescore(db, 0)
    db.execute("INSERT INTO matches(match_id, weirdness, skill_weirdness) VALUES (1, 0, 0)")
    assert not ingest.should_rescore(db, 0)
    assert not ingest.should_rescore(db, 1)


def test_loop_retries_failed_refresh_next_cycle_even_with_old_scores(db, monkeypatch):
    db.execute("INSERT INTO matches(match_id, weirdness, skill_weirdness) VALUES (1, 1, 1)")
    monkeypatch.setattr(ingest.sys, "argv", ["ingest", "--loop", "1"])
    monkeypatch.setattr(ingest, "get_conn", lambda: db)
    monkeypatch.setattr(ingest, "cycle", lambda conn: None)
    cycle_number = 0
    attempts = []

    def items(conn):
        attempts.append(("items", cycle_number))
        return 1

    def skills(conn):
        attempts.append(("skills", cycle_number))
        if cycle_number == 50:
            raise RuntimeError("Synthetic interrupted skill refresh")
        return 1

    def sleep(seconds):
        nonlocal cycle_number
        cycle_number += 1
        if cycle_number == 53:
            raise KeyboardInterrupt

    monkeypatch.setattr(ingest, "score_weirdness", items)
    monkeypatch.setattr(ingest, "score_skill_weirdness", skills)
    monkeypatch.setattr(ingest.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        ingest.main()
    assert attempts == [("items", 50), ("skills", 50), ("items", 51), ("skills", 51)]
