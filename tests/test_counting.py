"""The counting rule: which numbers are one flight, its result and when it is closed (docs/flight-lookup.md, C1 to
C4; docs/flight-lookup-figures.md, A0's `tie`, `num` and `fl`, with values from A11 to A16), the number-level "as of"
reading: what the list showed for each number, and when it passed each checkpoint (C6; A0's `st`, `hole` and `cp`),
and the flights in each row of the table, with the total and the rows' rates (C4 to C7; A0's `cell`, A2 and A6).
Expected values by hand, but for the hand-built model's figures, which are A0's SQL's."""
from datetime import date, datetime, timedelta
from itertools import permutations

from pytest import approx

import counting_fixture
from counting_helpers import T, board, number, seen
from timeline import counting
from timeline.counting import Flight, Stretch
from timeline.rates import Counted

LAST = T(12, 10, 16, 45)  # the last sighting of the model the figures were run on (docs/flight-lookup-figures.md)

# One number, scheduled 4 Nov 12:00: first recorded at 10:00 on 3 Nov (snapshot 1), changed at 11:00 (snapshot 5),
# and last seen at 12:30.
SCHED = T(4, 12)
TABLE = [number("a", SCHED, last_seen_at=T(3, 12, 30))]
OBS = [seen("a", 1, T(3, 10), sched_utc=SCHED),
       seen("a", 5, T(3, 11), sched_utc=SCHED, est_utc=T(4, 12, 40), status="DELAYED", counters=None)]


def test_a_stretch_runs_to_the_next_change_and_the_last_to_a_second_after_the_last_sighting():
    st = counting.stretches(TABLE, OBS)
    assert st == {"a": (
        Stretch("a", 1, from_at=T(3, 10), to_at=T(3, 11), to_ever=T(3, 11), sched_utc=SCHED, est_utc=SCHED,
                status="ON TIME", terminal=3, desks="1-5"),
        Stretch("a", 5, from_at=T(3, 11), to_at=T(3, 12, 30, 1), to_ever=datetime.max, sched_utc=SCHED,
                est_utc=T(4, 12, 40), status="DELAYED", terminal=3, desks=""))}


def test_a_number_is_listed_from_its_first_record_to_the_end_of_its_last_stretch():
    st = counting.stretches(TABLE, OBS)
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
    st = counting.stretches(table, obs)
    assert counting.passings(st, ()) == {("a", 24): (T(1, 12), "ON TIME"), ("a", 12): (T(2, 2), "DELAYED"),
                                         ("a", 6): (T(2, 8), "DELAYED"), ("a", 3): (T(2, 11), "DELAYED")}


def test_a_number_first_listed_past_a_point_has_no_passing_there():
    table = [number("a", T(5, 12), last_seen_at=T(5, 12))]
    obs = [seen("a", 1, T(4, 16), sched_utc=T(5, 12))]  # 20 hours before its time
    st = counting.stretches(table, obs)
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
    passed = counting.passings(counting.stretches(table, obs), holes)
    assert {fid: passed.get((fid, 24)) for fid in hours} == {"at-the-last-sighting": (T(6, 10), "ON TIME"),
                                                             "inside": None,
                                                             "at-the-next-fetch": (T(6, 13), "ON TIME")}


def test_the_first_passing_counts():
    # Scheduled 5 Nov 10:00, its 24-hour moment passes at 4 Nov 10:00; a retime at 11:00 moves it to 5 Nov 14:00,
    # and the new time's own 24-hour moment, 4 Nov 14:00, passes as well.
    table = [number("a", T(5, 14), last_seen_at=T(5, 14))]
    obs = [seen("a", 1, T(4, 8), sched_utc=T(5, 10)),
           seen("a", 3, T(4, 11), sched_utc=T(5, 14), status="DELAYED")]
    st = counting.stretches(table, obs)
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


def test_the_checkpoints_are_rule_c5s():
    assert counting.CHECKPOINTS == (70, 48, 24, 12, 6, 3)


def numbers_of(table: list[dict]) -> list[tuple[str, ...]]:
    """Each flight's numbers, flights in key order."""
    return [f.numbers for f in counting.flights(table, LAST)]


# C1. Two numbers in one slot are one flight when they show the same expected time, terminal and desks, or when at
# least one did not depart or land and they share the airline or the desks. `tied` is the direct tie; `flights`
# chains ties and undoes a chain that would join two numbers that departed or landed apart.

def test_the_same_expected_time_terminal_and_desks_tie():
    ey = number("ey607", T(4, 9, 30), airline="EY", flight_no="607", airport="AUH", est_utc_final=T(4, 9, 52),
                counters_final="12-21", first_seen_at=T(1, 10))
    ly = number("ly9614", T(4, 9, 30), airline="LY", flight_no="9614", airport="AUH", est_utc_final=T(4, 9, 52),
                counters_final="12-21", first_seen_at=T(1, 9, 45))
    assert counting.tied(ey, ly)
    fl = counting.flights([ly, ey], LAST)
    assert fl == [Flight(key=("D", "AUH", T(4, 9, 30), "ey607"), numbers=("ey607", "ly9614"), result="operated",
                         closed=True, airline="EY", day=date(2026, 11, 4), first_seen=T(1, 9, 45))]
    assert counting.flight_of(fl) == {"ey607": fl[0], "ly9614": fl[0]}


def test_one_airline_at_one_desk_range_with_two_expected_times_is_two_flights():
    # A11b, D AUH 2026-10-29 05:00: two aircraft at one desk range, each with its LY partner.
    at = datetime(2026, 10, 29, 5)
    early, late = datetime(2026, 10, 29, 5, 18), datetime(2026, 10, 29, 6, 24)
    ey596, ly9606, ey610, ly9613 = (
        number(fid, at, airline=fid[:2].upper(), flight_no=fid[2:], airport="AUH", counters_final="12-21",
               est_utc_final=est)
        for fid, est in (("ey596", early), ("ly9606", early), ("ey610", late), ("ly9613", late)))
    assert not counting.tied(ey596, ey610)  # checked directly: C1's last clause would undo such a tie in the grouping
    assert numbers_of([ey596, ey610]) == [("ey596",), ("ey610",)]
    assert numbers_of([ey610, ly9613, ey596, ly9606]) == [("ey596", "ly9606"), ("ey610", "ly9613")]


def test_two_desk_ranges_never_tie():
    # A11b, D KTW 2026-11-10 03:00.
    at = T(10, 3)
    ent229 = number("ent229", at, airline="ENT", flight_no="229", airport="KTW", counters_final="220-223",
                    est_utc_final=T(10, 3, 46))
    ent359 = number("ent359", at, airline="ENT", flight_no="359", airport="KTW", counters_final="223-226",
                    est_utc_final=T(10, 3, 31))
    assert not counting.tied(ent229, ent359)
    assert numbers_of([ent229, ent359]) == [("ent229",), ("ent359",)]
    cancelled = ent229 | {"outcome": "canceled"}
    assert not counting.tied(cancelled, ent359)
    assert numbers_of([cancelled, ent359]) == [("ent229",), ("ent359",)]


def test_two_terminals_never_tie():
    at = T(4, 18)
    cancelled = number("ly5131", at, flight_no="5131", airport="LCA", terminal_final=1, counters_final="",
                       outcome="canceled")
    departed = number("ly5133", at, flight_no="5133", airport="LCA", terminal_final=3, counters_final="316-327",
                      est_utc_final=T(4, 18, 14))
    assert not counting.tied(cancelled, departed)
    assert numbers_of([cancelled, departed]) == [("ly5131",), ("ly5133",)]


def test_a_cancelled_number_ties_by_airline_or_desks_only():
    # A14: OS 1083, listed as cancelled, beside OS 083, which landed (arrivals show no desks).
    at = T(7, 2, 20)
    os1083 = number("os1083", at, airline="OS", flight_no="1083", direction="A", airport="VIE", counters_final="",
                    outcome="canceled")
    os083 = number("os083", at, airline="OS", flight_no="083", direction="A", airport="VIE", counters_final="",
                   outcome="landed", est_utc_final=T(7, 2, 4))
    assert counting.tied(os1083, os083)
    assert numbers_of([os1083, os083]) == [("os083", "os1083")]
    # A14: U8 103, listed as cancelled, beside BZ 112, which departed from the same desks. A14 lists only the pair;
    # the desks are made up.
    at = T(4, 8, 30)
    u8 = number("u8103", at, airline="U8", flight_no="103", airport="LCA", counters_final="60-63",
                outcome="canceled")
    bz = number("bz112", at, airline="BZ", flight_no="112", airport="LCA", counters_final="60-63",
                est_utc_final=T(4, 8, 52))
    assert counting.tied(u8, bz)
    assert numbers_of([u8, bz]) == [("bz112", "u8103")]

    # A11, D JFK: IZ 991 listed as cancelled; LY 003, DL 7426 and AM 7895 departed from desks 78-99.
    def jfk(at: datetime, iz_desks: str, iz_est: datetime, est: datetime) -> list[dict]:
        iz = number("iz991", at, airline="IZ", flight_no="991", airport="JFK", counters_final=iz_desks,
                    est_utc_final=iz_est, outcome="canceled")
        return [iz] + [number(fid, at, airline=al, flight_no=no, airport="JFK", counters_final="78-99",
                              est_utc_final=est) for fid, al, no in (("ly003", "LY", "003"), ("dl7426", "DL", "7426"),
                                                                    ("am7895", "AM", "7895"))]

    at = datetime(2026, 10, 28, 22, 5)
    oct28 = jfk(at, "34-41", at, datetime(2026, 10, 28, 22, 48))
    assert not counting.tied(oct28[0], oct28[1])
    assert numbers_of(oct28) == [("am7895", "dl7426", "ly003"), ("iz991",)]
    nov7 = jfk(T(7, 22, 5), "", T(7, 19), T(7, 23))  # no desks: it shares neither airline nor desks with them
    assert not counting.tied(nov7[0], nov7[1])
    assert numbers_of(nov7) == [("am7895", "dl7426", "ly003"), ("iz991",)]
    # No desks is not the same desks: another airline's arrival listed as cancelled, at another expected time, stands
    # alone beside one that landed.
    at = T(1, 20)
    landed = number("aa1", at, airline="AA", direction="A", counters_final="", outcome="landed",
                    est_utc_final=T(1, 20, 26))
    cancelled = number("bb1", at, airline="BB", direction="A", counters_final="", outcome="canceled")
    assert not counting.tied(cancelled, landed)
    assert numbers_of([landed, cancelled]) == [("aa1",), ("bb1",)]


def test_ties_chain():
    # LY 1, listed as cancelled with no desks, ties to LY 2 by airline; LY 2 ties to DL 3 by desks; LY 1 and DL 3 do
    # not tie, and still are one flight, in whatever order the table holds them.
    at = T(4, 10)
    chain = [number("ly1", at, flight_no="1", counters_final="", outcome="canceled"),
             number("ly2", at, flight_no="2", est_utc_final=T(4, 10, 20)),
             number("dl3", at, airline="DL", flight_no="3", outcome="canceled")]
    assert not counting.tied(chain[0], chain[2])
    for order in permutations(chain):
        assert numbers_of(list(order)) == [("dl3", "ly1", "ly2")]


def test_a_chain_never_joins_two_departed_numbers_apart():
    # LY 9001, listed as cancelled at desks 1-5, ties to both; LY 001 and LY 002 left 40 minutes apart.
    at = T(4, 10)
    ly001 = number("ly001", at, flight_no="001")
    ly002 = number("ly002", at, flight_no="002", est_utc_final=T(4, 10, 40))
    ly9001 = number("ly9001", at, flight_no="9001", outcome="canceled")
    assert counting.tied(ly001, ly9001) and counting.tied(ly002, ly9001) and not counting.tied(ly001, ly002)
    fl = counting.flights([ly001, ly002, ly9001], LAST)
    assert [(f.numbers, f.result) for f in fl] == [(("ly001",), "operated"), (("ly002",), "operated"),
                                                   (("ly9001",), "cancelled")]
    # With DL 6002, LY 002's partner (the same expected time, terminal and desks), and a second LY number listed as
    # cancelled: the numbers that departed regroup by expected time, terminal and desks, and each number that did not
    # stands alone.
    dl6002 = number("dl6002", at, airline="DL", flight_no="6002", est_utc_final=T(4, 10, 40))
    ly9002 = number("ly9002", at, flight_no="9002", outcome="canceled")
    fl = counting.flights([ly001, ly002, ly9001, dl6002, ly9002], LAST)
    assert [(f.numbers, f.result) for f in fl] == [(("dl6002", "ly002"), "operated"), (("ly001",), "operated"),
                                                   (("ly9001",), "cancelled"), (("ly9002",), "cancelled")]


def test_nulls_tie_as_equal():
    # Review Focus 4: a missing terminal or expected time equals a missing one (SQL's IS NOT DISTINCT FROM), and a
    # number with no desks conflicts with no desk range.
    at = T(4, 10)
    a = number("a", at, airline="AA", terminal_final=None)
    b = number("b", at, airline="BB", terminal_final=None)
    assert counting.tied(a, b) and numbers_of([a, b]) == [("a", "b")]
    departed = number("d", at)  # desks 1-5
    for none in ("", None):
        cancelled = number("c", at, counters_final=none, outcome="canceled", est_utc_final=T(4, 9))
        assert counting.tied(cancelled, departed) and numbers_of([cancelled, departed]) == [("c", "d")]
    a = number("a", at, airline="AA", est_utc_final=None)
    b = number("b", at, airline="BB", est_utc_final=None)
    assert counting.tied(a, b) and numbers_of([a, b]) == [("a", "b")]


# C2. Operated when any number departed or landed; cancelled when none did and one ended listed as cancelled;
# unknown otherwise.

def test_results():
    at = T(4, 10)
    for outcomes, result in ((("departed", "canceled"), "operated"), (("canceled", "vanished"), "cancelled"),
                             (("gap", "open"), "unknown")):
        table = [number(f"n{i}", at, flight_no=str(i), outcome=o) for i, o in enumerate(outcomes)]
        assert [(f.numbers, f.result) for f in counting.flights(table, LAST)] == [(("n0", "n1"), result)], outcomes


# C3. The last status counts: a number counts as what it ended as, the flights table's outcome.

def test_last_status_counts():
    at = T(4, 10)
    # Listed as cancelled, changed back, then landed.
    assert [f.result for f in counting.flights([number("a", at, direction="A", outcome="landed")], LAST)] == [
        "operated"]
    # Listed as cancelled, changed back, then cancelled again: one cancelled flight.
    assert [(f.numbers, f.result) for f in counting.flights([number("a", at, outcome="canceled")], LAST)] == [
        (("a",), "cancelled")]
    # A14, D ATH 2026-11-08 23:00: LH 0691A, a number with a letter in it, beside LH 695, which departed.
    lh0691a = number("lh0691a", T(8, 23), airline="LH", flight_no="0691A", outcome="canceled")
    lh695 = number("lh695", T(8, 23), airline="LH", flight_no="695", est_utc_final=T(8, 23, 20))
    assert [(f.numbers, f.result) for f in counting.flights([lh0691a, lh695], LAST)] == [
        (("lh0691a", "lh695"), "operated")]
    # One number listed as cancelled on two days is a flight on each day, on its Israel date: 22:30 UTC is 00:30
    # the next day in Israel.
    days = [number("ly5-4", T(4, 22, 30), flight_no="5", outcome="canceled"),
            number("ly5-5", T(5, 22, 30), flight_no="5", outcome="canceled")]
    assert [(f.numbers, f.result, f.day) for f in counting.flights(days, LAST)] == [
        (("ly5-4",), "cancelled", date(2026, 11, 5)), (("ly5-5",), "cancelled", date(2026, 11, 6))]


# C4. A flight is closed 48 hours after its scheduled time, by the time it was finally scheduled for.

def test_closed_48_hours_after():
    assert counting.CLOSED_AFTER == timedelta(hours=48)
    israel = timedelta(hours=2)
    at47, at48, at50 = LAST - timedelta(hours=47), LAST - timedelta(hours=48), LAST - timedelta(hours=50)
    table = [number("47h", at47), number("48h", at48),
             number("retimed", at47, airport="LCA", sched_local_first=at50 + israel)]  # first scheduled 50 h before
    assert {f.numbers: f.closed for f in counting.flights(table, LAST)} == {
        ("47h",): False, ("48h",): True, ("retimed",): False}


# C8's grouping airline: the airline of the flight's number with the lowest number, by the integer value of its first
# run of digits, then by airline; a number with no digits comes after every numbered one.

def test_the_grouping_airline():
    at = T(4, 10)

    def airline(*numbers: tuple[str, str]) -> str:
        fl = counting.flights([number(f"{al}{no}", at, airline=al, flight_no=no) for al, no in numbers], LAST)
        assert len(fl) == 1
        return fl[0].airline

    assert airline(("LH", "0691"), ("EY", "607")) == "EY"  # "0691" < "607" as strings
    assert airline(("AB", "100"), ("AA", "100")) == "AA"
    assert airline(("AA", "ABC"), ("ZZ", "9999")) == "ZZ"


# C5 to C7. A closed flight with a known result is in a row when any of its numbers was listed, at that point, with a
# status other than cancelled; it counts there when its result is cancelled, however late the listing came.

def in_rows(table: list[dict], obs: list[dict]) -> list[tuple[int, tuple[str, ...], datetime, int]]:
    """Each cell's row, numbers, moment and k, on a board with no hole."""
    passed = counting.passings(counting.stretches(table, obs), ())
    return [(c.h, c.flight.numbers, c.t, c.k) for c in counting.cells(counting.flights(table, LAST), passed)]


def test_already_cancelled_at_the_point_is_not_in_the_row():
    # Scheduled 5 Nov 12:00, listed on time from 75 hours before, and as cancelled from 4 Nov 00:00, 36 hours before.
    s = T(5, 12)
    table = [number("a", s, outcome="canceled", last_seen_at=T(6, 12))]
    obs = [seen("a", 1, T(2, 9), sched_utc=s), seen("a", 50, T(4, 0), sched_utc=s, status="CANCELED")]
    assert in_rows(table, obs) == [(70, ("a",), T(2, 14), 1), (48, ("a",), T(3, 12), 1)]
    # Already listed as cancelled when first seen: in the total and in no row.
    obs = [seen("a", 1, T(2, 9), sched_utc=s, status="CANCELED")]
    assert in_rows(table, obs) == []
    fig = counting.figures(table, obs, board(LAST))
    assert (fig.total.cancelled, fig.total.flights) == (1, 1)
    assert [(h, r.flights) for h, r in fig.rows] == [(h, 0) for h in counting.CHECKPOINTS]


def test_a_delayed_number_is_in_the_row():
    # Listed on time from 72 hours before its time, then DELAYED from 30 hours before, to leave 50 minutes late.
    s = T(5, 12)
    table = [number("a", s, est_utc_final=T(5, 12, 50))]
    obs = [seen("a", 1, T(2, 12), sched_utc=s),
           seen("a", 40, T(4, 6), sched_utc=s, est_utc=T(5, 12, 50), status="DELAYED")]
    passed = counting.passings(counting.stretches(table, obs), ())
    assert [passed[("a", h)][1] for h in counting.CHECKPOINTS] == ["ON TIME"] * 2 + ["DELAYED"] * 4
    assert [(h, k) for h, _, _, k in in_rows(table, obs)] == [(h, 0) for h in counting.CHECKPOINTS]


def test_a_flight_is_in_the_row_when_any_number_passed_listed_normally():
    # EY 607 and LY 9614, one flight (the same expected time, terminal and desks), scheduled 5 Nov 12:00 and listed
    # from 72 hours before: LY 9614 as cancelled from 50 hours before, EY 607 from 20 hours before.
    s = T(5, 12)
    table = [number("ey607", s, airline="EY", flight_no="607", outcome="canceled"),
             number("ly9614", s, flight_no="9614", outcome="canceled")]
    obs = [seen("ey607", 1, T(2, 12), sched_utc=s), seen("ey607", 70, T(4, 16), sched_utc=s, status="CANCELED"),
           seen("ly9614", 1, T(2, 12), sched_utc=s), seen("ly9614", 10, T(3, 10), sched_utc=s, status="CANCELED")]
    both = ("ey607", "ly9614")
    assert in_rows(table, obs) == [(70, both, T(2, 14), 1), (48, both, T(3, 12), 1), (24, both, T(4, 12), 1)]


def test_the_rows_moment_is_the_earliest_passing():
    # EY 607 and LY 9614, one flight, scheduled 5 Nov 12:00. EY 607 showed 13:00 until a retime seen 4 Nov 00:00, so
    # it passed 70 and 48 hours an hour after LY 9614, which showed 12:00 throughout.
    s = T(5, 12)
    table = [number("ey607", s, airline="EY", flight_no="607", sched_local_first=T(5, 15)),
             number("ly9614", s, flight_no="9614")]
    obs = [seen("ey607", 1, T(2, 12), sched_utc=T(5, 13)), seen("ey607", 50, T(4, 0), sched_utc=s),
           seen("ly9614", 1, T(2, 12), sched_utc=s)]
    passed = counting.passings(counting.stretches(table, obs), ())
    assert [passed[(fid, 70)][0] for fid in ("ey607", "ly9614")] == [T(2, 15), T(2, 14)]
    assert [passed[(fid, 48)][0] for fid in ("ey607", "ly9614")] == [T(3, 13), T(3, 12)]
    assert [(h, t) for h, _, t, _ in in_rows(table, obs)] == [
        (70, T(2, 14)), (48, T(3, 12)), (24, T(4, 12)), (12, T(5, 0)), (6, T(5, 6)), (3, T(5, 9))]


def test_cancelled_after_its_time_counts_in_every_row_it_was_in():
    # Listed on time from 72 hours before its time, 5 Nov 12:00, and as cancelled from an hour after it.
    s = T(5, 12)
    table = [number("a", s, outcome="canceled", last_seen_at=T(6, 12))]
    obs = [seen("a", 1, T(2, 12), sched_utc=s), seen("a", 90, T(5, 13), sched_utc=s, status="CANCELED")]
    assert [(h, k) for h, _, _, k in in_rows(table, obs)] == [(h, 1) for h in counting.CHECKPOINTS]
    fig = counting.figures(table, obs, board(LAST))
    assert [(h, r.cancelled, r.flights) for h, r in fig.rows] == [(h, 1, 1) for h in counting.CHECKPOINTS]
    # A cell counts as its flight: k, the grouping airline and the Israel day.
    (f,) = counting.flights(table, LAST)
    assert counting.counted(f) == Counted(1, "LY", date(2026, 11, 5))
    assert counting.counted(counting.flights([number("b", s)], LAST)[0]) == Counted(0, "LY", date(2026, 11, 5))


def test_open_and_unknown_flights_make_no_rate():
    # Four flights, each listed on time from 72 hours before its time and through every point: one cancelled an hour
    # before and one that departed, both closed; one cancelled an hour before, scheduled 47 hours before the last
    # sighting (open); and one that left the list 2 hours before its time with no final status (unknown).
    cases = {"cancelled": (T(6, 12), "canceled"), "departed": (T(6, 14), "departed"),
             "open": (LAST - timedelta(hours=47), "canceled"), "unknown": (T(7, 12), "vanished")}
    table, obs = [], []
    for fid, (s, outcome) in cases.items():
        left = s - timedelta(hours=2) if outcome == "vanished" else s + timedelta(hours=12)
        table.append(number(fid, s, outcome=outcome, last_seen_at=left))
        obs.append(seen(fid, 1, s - timedelta(hours=72), sched_utc=s))
        if outcome == "canceled":
            obs.append(seen(fid, 2, s - timedelta(hours=1), sched_utc=s, status="CANCELED"))
    passed = counting.passings(counting.stretches(table, obs), ())
    assert all(passed[(fid, h)][1] == "ON TIME" for fid in cases for h in counting.CHECKPOINTS)
    assert {f.numbers: (f.closed, f.result) for f in counting.flights(table, LAST)} == {
        ("cancelled",): (True, "cancelled"), ("departed",): (True, "operated"), ("open",): (False, "cancelled"),
        ("unknown",): (True, "unknown")}
    assert sorted({c.flight.numbers for c in counting.cells(counting.flights(table, LAST), passed)}) == [
        ("cancelled",), ("departed",)]
    fig = counting.figures(table, obs, board(LAST))
    assert (fig.total.cancelled, fig.total.flights) == (1, 2)
    assert [(h, r.cancelled, r.flights) for h, r in fig.rows] == [(h, 1, 2) for h in counting.CHECKPOINTS]


# The figures on a model built by hand (tests/counting_fixture.py): 650 flights over 6 Israel days and 6 airlines, 12
# of them closed and cancelled. The expected values are A0's SQL's (docs/flight-lookup-figures.md, A0 with A2 and A6)
# run over the same rows, with the rate and its ends unrounded and the standard errors themselves.
FIXTURE = {  # cancelled, flights, airlines, days, clears_floor; one_in, from, to; se_airline_week, se_day
    "total": ((12, 492, 6, 5, True), (41.0, 26.7870, 63.0467), (0.00522317, 0.00279113)),
    70: ((7, 222, 5, 3, False), (31.7143, 16.6073, 61.4439), (0.0103367, 0.00474344)),
    48: ((8, 286, 5, 4, False), (35.75, 18.2871, 70.8534), (0.00949215, 0.00355744)),
    24: ((8, 407, 5, 5, False), (50.875, 25.2561, 103.5523), (0.00694530, 0.00488680)),
    12: ((7, 439, 6, 4, False), (62.7143, 31.0234, 127.8563), (0.00565302, 0.00473275)),
    6: ((8, 462, 5, 5, False), (57.75, 30.7713, 109.1767), (0.00548865, 0.00489028)),
    3: ((5, 459, 3, 4, False), (91.8, 35.2523, 241.7035), (0.00525211, 0.00365602)),
}


def test_the_hand_computed_fixture():
    table, obs, snaps = counting_fixture.model()
    fl = counting.flights(table, counting.last_sighting(snaps))
    assert (len(fl), len({f.day for f in fl}), len({f.airline for f in fl}),
            sum(f.closed and f.result == "cancelled" for f in fl)) == (650, 6, 6, 12)
    fig = counting.figures(table, obs, snaps)
    assert [h for h, _ in fig.rows] == list(counting.CHECKPOINTS)
    for name, r in [("total", fig.total), *fig.rows]:
        counts, ends, ses = FIXTURE[name]
        assert (r.cancelled, r.flights, r.airlines, r.days, r.clears_floor) == counts, name
        assert (r.one_in, r.one_in_from, r.one_in_to) == approx(ends, abs=1e-4), name
        assert (r.se_airline_week, r.se_day) == approx(ses, rel=1e-5), name
