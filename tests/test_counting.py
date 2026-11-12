"""The number-level "as of" reading: what the list showed for each number, and when it passed each checkpoint
(docs/flight-lookup.md, C6; docs/flight-lookup-figures.md, A0's `st`, `hole` and `cp`). Expected values by hand."""
from datetime import datetime, timedelta

import pytest

from counting_helpers import T, board, number, seen
from timeline import counting
from timeline.counting import Stretch

# One number, scheduled 4 Nov 12:00: first recorded at 10:00 on 3 Nov (snapshot 1), changed at 11:00 (snapshot 5),
# last seen at 12:30, and gone from the next download, at 12:45.
SCHED = T(4, 12)
TABLE = [number("a", SCHED, last_seen_at=T(3, 12, 30))]
OBS = [seen("a", 1, T(3, 10), sched_utc=SCHED),
       seen("a", 5, T(3, 11), sched_utc=SCHED, est_utc=T(4, 12, 40), status="DELAYED", counters=None)]
BOARD = board(*(T(3, 10) + timedelta(minutes=15 * i) for i in range(12)))  # every 15 minutes, 10:00 to 12:45


def test_a_stretch_runs_to_the_next_change_and_the_last_to_a_second_after_the_last_sighting():
    st = counting.stretches(TABLE, OBS, BOARD, reading="a0")
    assert st == {"a": (
        Stretch("a", 1, from_at=T(3, 10), to_at=T(3, 11), to_ever=T(3, 11), sched_utc=SCHED, est_utc=SCHED,
                status="ON TIME", terminal=3, desks="1-5"),
        Stretch("a", 5, from_at=T(3, 11), to_at=T(3, 12, 30, 1), to_ever=datetime.max, sched_utc=SCHED,
                est_utc=T(4, 12, 40), status="DELAYED", terminal=3, desks=""))}


def test_carry_forward_runs_the_last_stretch_to_the_next_download():
    st = counting.stretches(TABLE, OBS, BOARD, reading="carry")
    assert [(s.from_at, s.to_at, s.to_ever) for s in st["a"]] == [(T(3, 10), T(3, 11), T(3, 11)),
                                                                   (T(3, 11), T(3, 12, 45), datetime.max)]
    on_the_latest_list = counting.stretches(TABLE, OBS, BOARD[:-1], reading="carry")
    assert on_the_latest_list["a"][-1].to_at == datetime.max


def test_a_number_is_listed_from_its_first_record_to_the_end_of_its_last_stretch():
    st = counting.stretches(TABLE, OBS, BOARD, reading="a0")
    first, changed = st["a"]
    assert counting.state_at(st, T(3, 9, 59)) == {}
    assert counting.state_at(st, T(3, 10)) == {"a": first}
    assert counting.state_at(st, T(3, 11)) == {"a": changed}
    assert counting.state_at(st, T(3, 12, 30)) == {"a": changed}
    assert counting.state_at(st, T(3, 12, 30, 1)) == {}


def test_the_clock_is_the_time_shown_at_the_moment():
    # Scheduled 2 Nov 12:00 until a retime seen 1 Nov 13:00 moves it to 2 Nov 14:00. At 1 Nov 12:00 the list still
    # showed 2 Nov 12:00; a reading by the final scheduled time would put the 24-hour moment at 1 Nov 14:00.
    table = [number("a", T(2, 14), last_seen_at=T(2, 14, 30))]
    obs = [seen("a", 1, T(1, 0), sched_utc=T(2, 12)),
           seen("a", 40, T(1, 13), sched_utc=T(2, 14), status="DELAYED")]
    st = counting.stretches(table, obs, board(T(1, 0), T(1, 13), T(2, 14, 30)), reading="a0")
    assert counting.passings(st, ()) == {("a", 24): (T(1, 12), "ON TIME"), ("a", 12): (T(2, 2), "DELAYED"),
                                         ("a", 6): (T(2, 8), "DELAYED"), ("a", 3): (T(2, 11), "DELAYED")}


def test_a_number_first_listed_past_a_point_has_no_passing_there():
    table = [number("a", T(5, 12), last_seen_at=T(5, 12))]
    obs = [seen("a", 1, T(4, 16), sched_utc=T(5, 12))]  # 20 hours before its time
    st = counting.stretches(table, obs, board(T(4, 16), T(5, 12)), reading="a0")
    assert counting.passings(st, ()) == {("a", 12): (T(5, 0), "ON TIME"), ("a", 6): (T(5, 6), "ON TIME"),
                                         ("a", 3): (T(5, 9), "ON TIME")}


def test_a_moment_inside_a_hole_is_not_a_checkpoint():
    snaps = board(T(6, 9), T(6, 10), T(6, 13), T(6, 14))  # nothing downloaded from 10:00 to 13:00
    holes = counting.holes(snaps)
    assert holes == ((T(6, 10), T(6, 13)),)
    assert [counting.in_hole(t, holes) for t in (T(6, 10), T(6, 10, 0, 1), T(6, 12, 59, 59), T(6, 13))] == [
        False, True, True, False]
    hours = {"at-the-last-sighting": 10, "inside": 11, "at-the-next-fetch": 13}
    table = [number(fid, T(7, h), last_seen_at=T(6, 14)) for fid, h in hours.items()]
    obs = [seen(fid, 1, T(6, 9), sched_utc=T(7, h)) for fid, h in hours.items()]
    passed = counting.passings(counting.stretches(table, obs, snaps, reading="a0"), holes)
    assert {fid: passed.get((fid, 24)) for fid in hours} == {"at-the-last-sighting": (T(6, 10), "ON TIME"),
                                                             "inside": None,
                                                             "at-the-next-fetch": (T(6, 13), "ON TIME")}


def test_the_first_passing_counts():
    # Scheduled 5 Nov 10:00, its 24-hour moment passes at 4 Nov 10:00; a retime at 11:00 moves it to 5 Nov 14:00,
    # and the new time's own 24-hour moment, 4 Nov 14:00, passes as well.
    table = [number("a", T(5, 14), last_seen_at=T(5, 14))]
    obs = [seen("a", 1, T(4, 8), sched_utc=T(5, 10)),
           seen("a", 3, T(4, 11), sched_utc=T(5, 14), status="DELAYED")]
    st = counting.stretches(table, obs, board(T(4, 8), T(4, 11), T(5, 14)), reading="a0")
    assert [s.from_at <= s.sched_utc - timedelta(hours=24) < s.to_at for s in st["a"]] == [True, True]
    assert counting.passings(st, ())[("a", 24)] == (T(4, 10), "ON TIME")


def test_holes_from_the_last_sighting_to_the_next_fetch():
    # The snapshot fetched at 9:00 was seen again until 10:00 (R9); the next fetch comes an hour and a second later.
    over = board(T(8, 8), (T(8, 9), T(8, 10)), T(8, 11, 0, 1))
    assert [s["gap_before_s"] for s in over] == [None, 3600, 3601]
    assert counting.holes(over) == ((T(8, 10), T(8, 11, 0, 1)),)
    assert counting.holes(board(T(8, 8), (T(8, 9), T(8, 10)), T(8, 11))) == ()  # exactly an hour is no hole
    # The first snapshot has none before it: its gap is NULL, and it follows no hole.
    assert counting.holes(board(T(8, 9))) == ()


def test_the_last_sighting_is_the_latest_snapshot_seen_last():
    assert counting.last_sighting(board(T(9, 10), (T(9, 10, 15), T(9, 10, 29)))) == T(9, 10, 29)


def test_the_reading_is_one_of_the_two_candidates():
    assert counting.READINGS == ("a0", "carry")
    assert counting.READING in counting.READINGS
    assert counting.CHECKPOINTS == (70, 48, 24, 12, 6, 3)
    with pytest.raises(ValueError, match="reading"):
        counting.stretches(TABLE, OBS, BOARD, reading="cut")
