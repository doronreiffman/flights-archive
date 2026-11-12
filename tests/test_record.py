"""The signs S1 to S4 (docs/flight-lookup.md, "Signs"; docs/flight-lookup-figures.md, A0b's `nrow`, `not_whole`,
`nsign` and `sign`): each read for a number at its own checkpoint moment, from what the list showed then and nothing
later, and carried by the number's flight. Expected values by hand. Then the sign test that reads them ("Signs", "The
gate", "The re-test"; A29): the counted flights, the gate and its guard, what a run reads, and the entry point's files.

Unless a test says otherwise, every number is first listed at the first download, FIRST, and last seen on 6 November;
the reader is LY 1 departing to ATH at 12:00 on 3 November, whose 24-hour moment is 12:00 on the 2nd.
"""
import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from counting_helpers import T, board, number, seen
from model import build as model_build
from model_helpers import write_receipt, write_snapshot
from test_figures_check import Number, nov
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import counting, record
from timeline.load import load

FIRST = T(1, 0)  # the first download
LATER = T(6, 0)  # the default last sighting: after every moment below
D = T(3, 12)  # the reader's scheduled time
AT = T(2, 12)  # its 24-hour moment


def _rn(at: datetime) -> int:
    """A snapshot number in time order: minutes since 1 November."""
    return int((at - T(1, 0)).total_seconds() // 60)


def listing(fid: str, sched: datetime, *statuses: tuple[datetime, str], shown: dict | None = None,
            **row) -> tuple[dict, list[dict]]:
    """A number scheduled at `sched` (UTC) and its observations: `statuses` are (time, status) pairs, each from that
    time on (by default ON TIME from FIRST); `shown` sets the rest of what the list showed (est_utc, terminal,
    counters); `row` sets the flights row (airline, flight_no, direction, airport, last_seen_at)."""
    statuses = statuses or ((FIRST, "ON TIME"),)
    obs = [seen(fid, _rn(at), at, sched_utc=sched, status=status, **(shown or {})) for at, status in statuses]
    return number(fid, sched, **({"last_seen_at": LATER} | row)), obs


def signs(h: int, *numbers, holes_=(), first_fetch: datetime = FIRST) -> dict[str, frozenset[str]]:
    """record.number_signs at checkpoint h over `numbers` (listing's pairs)."""
    table = [n for n, _ in numbers]
    obs = [o for _, own in numbers for o in own]
    st = counting.stretches(table, obs)
    return record.number_signs(h, table, st, holes_, first_fetch, counting.passings(st, holes_))


READER = listing("d", D)


def inbound(sched: datetime, *statuses, **row):
    """LY 2 landing from ATH at `sched`, listed as cancelled from 06:00 on 2 November (no desks, as arrivals)."""
    return listing("i", sched, *(statuses or ((FIRST, "NOT FINAL"), (T(2, 6), "CANCELED"))),
                   shown={"counters": None}, **({"flight_no": "2", "direction": "A"} | row))


# --- S1 -------------------------------------------------------------------------------------------------

def test_s1_an_inbound_listed_as_cancelled_as_a_whole():
    # LY 2 lands from ATH 4 hours before LY 1 leaves for it, listed as cancelled from 06:00 on the 2nd and alone in
    # its slot. LY 1 also shows S3 (another flight of its airline within 24 hours); LY 2, already cancelled at its own
    # 24-hour moment, is not in the row.
    assert signs(24, READER, inbound(T(3, 8))) == {"d": frozenset({"S1", "S3"})}


def test_s1_departures_only():
    # an arrival with the same inbound shows S3 only
    arrival = listing("a", D, flight_no="3", direction="A", shown={"counters": None})
    assert signs(24, arrival, inbound(T(3, 8))) == {"a": frozenset({"S3"})}
    # and the inbound is an arrival: a cancelled departure to the same airport is not one
    out = listing("x", T(3, 8), (FIRST, "ON TIME"), (T(2, 6), "CANCELED"), flight_no="4")
    assert signs(24, READER, out) == {"d": frozenset({"S3"})}


def test_s1_needs_an_inbound_from_the_same_airport():
    # LY 2 lands from CDG, not ATH: another flight of the airline (S3), not LY 1's inbound
    assert signs(24, READER, inbound(T(3, 8), airport="CDG"))["d"] == frozenset({"S3"})


def test_s1_and_s3_need_the_same_airline():
    # AF 2 lands from ATH 4 hours before LY 1 leaves for it, listed as cancelled as a whole: another airline's
    assert signs(24, READER, inbound(T(3, 8), airline="AF"))["d"] == frozenset()


@pytest.mark.parametrize("before, s1", [(timedelta(minutes=30), True), (timedelta(hours=12), True),
                                        (timedelta(minutes=29), False), (timedelta(hours=12, minutes=1), False)])
def test_s1_window(before, s1):
    found = signs(24, READER, inbound(D - before))
    assert ("S1" in found["d"]) == s1 and "S3" in found["d"]


def test_s1_window_from_the_time_shown_at_t():
    # LY 1 shows 12:00 on the 3rd at its 24-hour moment and is retimed to 15:00 at 14:00 on the 2nd. The inbound lands
    # 11 hours before the time shown at the moment, 14 hours before the final time.
    retimed = (number("d", T(3, 15), last_seen_at=LATER),
               [seen("d", _rn(FIRST), FIRST, sched_utc=D), seen("d", _rn(T(2, 14)), T(2, 14), sched_utc=T(3, 15))])
    assert signs(24, retimed, inbound(T(3, 1)))["d"] == frozenset({"S1", "S3"})


@pytest.mark.parametrize("last_seen, found", [(T(2, 11), frozenset()), (AT, frozenset({"S1", "S3"}))])
def test_s1_needs_the_inbound_on_the_list_at_t(last_seen, found):
    # last seen at 11:00, an hour before the moment, the inbound is off the list (S1 reads to_at, not to_ever); last
    # seen at the moment, it is listed until a second after
    assert signs(24, READER, inbound(T(3, 8), last_seen_at=last_seen)) == {"d": found}


# --- "As a whole" ------------------------------------------------------------------------------------------
# LY 5 leaves for CDG 6 hours before the reader, listed as cancelled from 06:00 on the 2nd: S3 for the reader when it
# is listed as cancelled as a whole. Another number y shares its slot (D CDG 06:00 on the 3rd), ON TIME throughout.

EST = T(3, 6)


def slot_pair(c_desks: str | None, airline: str, est: datetime, desks: str | None, terminal: int = 3,
              y_status: str = "ON TIME"):
    c = listing("c", EST, (FIRST, "ON TIME"), (T(2, 6), "CANCELED"), shown={"counters": c_desks}, flight_no="5",
                airport="CDG")
    y = listing("y", EST, (FIRST, y_status), shown={"est_utc": est, "counters": desks, "terminal": terminal},
                airline=airline, flight_no="6", airport="CDG")
    return c, y


TIED = {
    "the same expected time and no desks, another airline": (None, "AF", EST, None),
    "the same airline, another expected time": (None, "LY", EST + timedelta(minutes=30), None),
    "the same desks, another airline and expected time": ("20-25", "AF", EST + timedelta(minutes=30), "20-25"),
}


@pytest.mark.parametrize("pair", TIED.values(), ids=TIED.keys())
def test_not_whole_while_a_tied_number_is_still_listed(pair):
    assert signs(24, READER, *slot_pair(*pair))["d"] == frozenset()


NOT_TIED = {
    "another terminal": ("20-25", "AF", EST, "20-25", 1),
    "two desk ranges, one airline": ("20-25", "LY", EST, "30-35", 3),
    "nothing shared": (None, "AF", EST + timedelta(minutes=30), None, 3),
    "desks on the cancelled number only": ("20-25", "AF", EST + timedelta(minutes=30), None, 3),
    "desks on the other number only": (None, "AF", EST + timedelta(minutes=30), "20-25", 3),
}


@pytest.mark.parametrize("pair", NOT_TIED.values(), ids=NOT_TIED.keys())
def test_whole_when_no_number_of_the_slot_is_tied(pair):
    assert signs(24, READER, *slot_pair(*pair))["d"] == frozenset({"S3"})


def test_whole_when_every_tied_number_shows_cancelled():
    assert signs(24, READER, *slot_pair(None, "LY", EST, None, y_status="CANCELED")) == {"d": frozenset({"S3"})}


def test_not_whole_when_a_tied_number_left_as_departed():
    # read at the 12-hour moment, 00:00 on the 3rd: LY 5 at 14:00 on the 2nd is listed as cancelled; LY 6 in its slot
    # departed at 14:10 and left the list at 17:00, and keeps the last status it showed
    c = listing("c", T(2, 14), (FIRST, "ON TIME"), (T(2, 6), "CANCELED"), flight_no="5", airport="CDG")
    y = listing("y", T(2, 14), (FIRST, "ON TIME"), (T(2, 14, 10), "DEPARTED"), flight_no="6", airport="CDG",
                last_seen_at=T(2, 17))
    assert signs(12, READER, c, y)["d"] == frozenset()
    assert signs(12, READER, c)["d"] == frozenset({"S3"})


def test_a_number_first_seen_after_the_moment_is_ignored():
    c, _ = slot_pair(None, "LY", EST, None)
    y = listing("y", EST, (T(2, 13), "ON TIME"), flight_no="6", airport="CDG")  # tied by airline, from 13:00
    assert signs(24, READER, c, y) == {"d": frozenset({"S3"})}


# --- S2 -------------------------------------------------------------------------------------------------

def test_s2_the_latest_before_as_of_the_moment_after_a_retime():
    # LY 1's other flights at its moment: p1 shows 12:00 on the 2nd, listed as cancelled; p2 shows 06:00 on the 2nd
    # and is retimed to 16:00 at 13:00, after the moment. As of the moment p1 is the latest before; by final times p2
    # would be, and it is not cancelled. p1 is also another flight of LY within 24 hours (S3).
    p1 = listing("p1", AT, (FIRST, "CANCELED"))
    p2 = (number("p2", T(2, 16), last_seen_at=LATER),
          [seen("p2", _rn(FIRST), FIRST, sched_utc=T(2, 6)), seen("p2", _rn(T(2, 13)), T(2, 13), sched_utc=T(2, 16))])
    assert signs(24, READER, p1, p2)["d"] == frozenset({"S2", "S3"})


def test_s2_absent_when_the_latest_before_departed():
    # the latest before departed and left the list at 10:00, keeping its last status; an earlier one is listed as
    # cancelled, 40 hours before the reader (too far for S3)
    late = listing("late", T(2, 8), (FIRST, "ON TIME"), (T(2, 8, 10), "DEPARTED"), last_seen_at=T(2, 10))
    early = listing("early", T(1, 20), (FIRST, "CANCELED"))
    assert signs(24, READER, late, early)["d"] == frozenset()
    assert signs(24, READER, early)["d"] == frozenset({"S2"})


def test_s2_the_same_time_is_not_before():
    # LY 1 to CDG at the reader's own time, listed as cancelled: another flight of the airline (S3); the latest before
    # is LY 1 to ATH a day earlier, which departed
    same_time = listing("same", D, (FIRST, "CANCELED"), airport="CDG")
    earlier = listing("earlier", T(2, 8), (FIRST, "ON TIME"), (T(2, 8, 10), "DEPARTED"), last_seen_at=T(2, 10))
    assert signs(24, READER, same_time, earlier)["d"] == frozenset({"S3"})


@pytest.mark.parametrize("cancelled, found", [("pa", frozenset({"S2", "S3"})), ("pb", frozenset({"S3"}))])
def test_s2_a_tie_goes_to_the_smaller_flight_id(cancelled, found):
    # two flights of LY 1 at the same time a day before the reader, to two airports (so neither is tied to the other);
    # one is listed as cancelled. The latest before is pa, the smaller flight_id: S2 only when pa is the cancelled one
    pair = [listing(fid, AT, (FIRST, "CANCELED" if fid == cancelled else "ON TIME"), airport=airport)
            for fid, airport in (("pb", "CDG"), ("pa", "FCO"))]
    assert signs(24, READER, *pair)["d"] == found


# --- S3 -------------------------------------------------------------------------------------------------

S3_CASES = {
    "24 hours before": ("D", "CDG", D - timedelta(hours=24), 3, True),
    "24 hours after": ("D", "CDG", D + timedelta(hours=24), 3, True),
    "24 hours and a minute before": ("D", "CDG", D - timedelta(hours=24, minutes=1), 3, False),
    "24 hours and a minute after": ("D", "CDG", D + timedelta(hours=24, minutes=1), 3, False),
    "an arrival at the same time": ("A", "ATH", D, 3, True),
    "its own slot, another terminal": ("D", "ATH", D, 1, False),
}


@pytest.mark.parametrize("case", S3_CASES.values(), ids=S3_CASES.keys())
def test_s3_another_slot_within_24_hours(case):
    direction, airport, sched, terminal, s3 = case
    other = listing("o", sched, (FIRST, "CANCELED"), shown={"terminal": terminal}, flight_no="7",
                    direction=direction, airport=airport)
    assert signs(24, READER, other)["d"] == (frozenset({"S3"}) if s3 else frozenset())


# --- S4 -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("first, s4", [(T(2, 12, 1), True), (T(2, 12), False)])
def test_s4_first_listed_under_48_hours(first, s4):
    # scheduled 12:00 on the 4th, first listed 47:59 or 48:00 before; read at its 24-hour moment
    found = signs(24, listing("r", T(4, 12), (first, "ON TIME")))
    assert found == {"r": frozenset({"S4"}) if s4 else frozenset()}


def test_s4_not_late_when_first_seen_at_the_first_list_or_after_a_hole():
    snaps = board(T(2, 0), T(2, 0, 30), T(2, 4), T(2, 4, 30))  # nothing downloaded from 00:30 to 04:00
    holes_ = counting.holes(snaps)
    assert holes_ == ((T(2, 0, 30), T(2, 4)),)
    numbers = {"at the first list": T(2, 0), "after the hole": T(2, 4), "at the next download": T(2, 4, 30)}
    found = signs(24, *(listing(fid, D, (at, "ON TIME")) for fid, at in numbers.items()), holes_=holes_,
                  first_fetch=snaps[0]["fetched_at"])
    assert found == {"at the first list": frozenset(), "after the hole": frozenset(),
                     "at the next download": frozenset({"S4"})}


# --- what a flight carries ---------------------------------------------------------------------------------

def test_a_flight_carries_s1_when_one_number_shows_it_and_s4_only_when_all_do():
    def cell(*numbers: str) -> counting.Cell:
        f = counting.Flight(key=("D", "ATH", D, numbers[0]), numbers=numbers, result="operated", closed=True,
                            airline="LY", day=date(2026, 11, 3), first_seen=FIRST)
        return counting.Cell(24, f, AT, 0)

    every, one, out_of_row = cell("a", "b"), cell("c", "d"), cell("e", "f")
    shown = {"a": frozenset({"S1", "S2", "S3", "S4"}), "b": frozenset({"S4"}),
             "c": frozenset({"S1", "S3", "S4"}), "d": frozenset({"S2"}),
             "e": frozenset({"S4"})}  # f is not in the row
    assert record.flight_signs([every, one, out_of_row], shown) == {
        every.flight.key: frozenset({"S1", "S2", "S3", "S4"}),
        one.flight.key: frozenset({"S1", "S2", "S3"}),
        out_of_row.flight.key: frozenset({"S4"})}


def test_a_cell_with_no_number_in_the_row_is_refused():
    f = counting.Flight(key=("D", "ATH", D, "a"), numbers=("a",), result="operated", closed=True, airline="LY",
                        day=date(2026, 11, 3), first_seen=FIRST)
    with pytest.raises(ValueError, match="no number of the flight"):
        record.flight_signs([counting.Cell(24, f, AT, 0)], {"b": frozenset({"S4"})})


# --- the sign test: the counted flights, the gate and its guard, what a run reads ---------------------------------

def test_counted_flights_only():
    # LY 1 and AF 9 are one flight (the same expected time, terminal and desks); AF 9 was first seen a second before
    # the start, so the flight is not counted. LY 3, alone in its slot, was first seen at the start: counted.
    start = T(2, 0)
    table = [number("a", D, first_seen_at=start), number("b", D, airline="AF", flight_no="9",
                                                         first_seen_at=start - timedelta(seconds=1)),
             number("c", T(3, 14), flight_no="3", first_seen_at=start)]
    flights_ = counting.flights(table, LATER)
    assert [f.numbers for f in flights_] == [("a", "b"), ("c",)]
    row = [counting.Cell(24, f, f.key[2] - timedelta(hours=24), 0) for f in flights_]
    assert record.counted_cells(row, start) == row[1:]
    assert record.counted_cells(row, start - timedelta(seconds=1)) == row


GATE_START = datetime(2027, 1, 1, 22)  # an Israel midnight, as naive UTC


def at_day(i: int, days: float, k: int, direction: str = "D") -> counting.Cell:
    """A counted flight of the 24-hour row, its scheduled time (as shown at its moment) `days` after GATE_START."""
    sched = GATE_START + timedelta(days=days)
    f = counting.Flight(key=(direction, "ATH", sched, f"f{i:04d}"), numbers=(f"f{i:04d}",),
                        result="cancelled" if k else "operated", closed=True, airline="LY", day=sched.date(),
                        first_seen=GATE_START)
    return counting.Cell(24, f, sched - timedelta(hours=24), k)


def test_the_gate():
    assert (record.GATE_CANCELLED, record.GATE_DAYS, record.SIGN_ROW) == (200, 60, 24)
    # 199 cancelled by day 61, and flights listed normally after it: not reached
    few = [at_day(i, 1 + i * 0.3, 1) for i in range(199)] + [at_day(900 + i, 61 + i, 0) for i in range(3)]
    assert few[198].flight.key[2] < GATE_START + timedelta(days=61)
    assert record.gate_reached_at(few, [], GATE_START) is None
    # 200 by day 59: not reached, until the first flight at day 60 or later, whatever its result; in time order
    early = [at_day(i, 1 + i * 0.29, 1) for i in range(200)]
    assert early[-1].flight.key[2] < GATE_START + timedelta(days=59)
    assert record.gate_reached_at(early + [at_day(900, 59.99, 0)], [], GATE_START) is None
    later = [at_day(901, 61, 0), at_day(902, 60, 0), at_day(903, 60.5, 1)]
    assert record.gate_reached_at(list(reversed(early)) + later, [], GATE_START) == GATE_START + timedelta(days=60)
    # every counted flight of the row counts: arrivals as departures, whatever signs they carry
    mixed = [at_day(i, 1 + i * 0.29, 1, "A" if i % 2 else "D") for i in range(200)] + [at_day(900, 60, 0, "A")]
    assert record.gate_reached_at(mixed, [], GATE_START) == GATE_START + timedelta(days=60)


def flown(fid: str, sched: datetime, first: datetime, *, cancelled: datetime | None = None,
          retimed: tuple[datetime, datetime] | None = None, **row) -> tuple[dict, list[dict]]:
    """A number first listed at `first` and scheduled at `sched` (UTC), with its observations: listed as cancelled
    from `cancelled`, else departed (landed, for an arrival) 10 minutes after its final time; `retimed` (at, to)
    moves its time at `at`; last seen 3 hours after its final time. `row` sets the flights row."""
    final = retimed[1] if retimed else sched
    arrival = row.get("direction") == "A"
    shown = [(first, "NOT FINAL" if arrival else "ON TIME", sched)]
    if retimed:
        shown.append((retimed[0], shown[0][1], final))
    shown.append((cancelled, "CANCELED", final) if cancelled else
                 (final + timedelta(minutes=10), "LANDED" if arrival else "DEPARTED", final))
    obs = [seen(fid, _rn(at), at, sched_utc=s, status=status, counters=None if arrival else "1-5")
           for at, status, s in shown]
    outcome = "canceled" if cancelled else "landed" if arrival else "departed"
    return number(fid, final, first_seen_at=first, last_seen_at=final + timedelta(hours=3), outcome=outcome,
                  **row), obs


def run_on(numbers, last: datetime, start: datetime) -> record.Result:
    """record.run over `numbers` (flown's pairs), the board seen from 20:00 on 1 November to `last`."""
    return record.run([n for n, _ in numbers], [o for _, own in numbers for o in own], board((T(1, 20), last)), start)


START = T(1, 22)  # the counting start of the gate's runs below


@pytest.fixture
def small_gate(monkeypatch):
    """The gate at 2 cancelled flights and 1 day, so that a few flights reach it."""
    monkeypatch.setattr(record, "GATE_CANCELLED", 2)
    monkeypatch.setattr(record, "GATE_DAYS", 1)


# LY 11 and LY 13 at 06:00 and 08:00 on 3 November, both listed as cancelled from 18:00 on the 2nd, after their
# 24-hour moments: the row holds 2 cancelled flights at 08:00, more than a day after START, so the gate is there.
# LY 12 showed 07:00 at its 24-hour moment (07:00 on the 2nd) and was retimed at 20:00 to 07:00 on the 5th: it closes
# 48 hours after that. LY 14 at 05:00, also cancelled, was first seen at 21:00 on the 1st, before START: not counted.
NEAR_THE_GATE = [
    flown("a", T(3, 6), T(2, 0), cancelled=T(2, 18), flight_no="11"),
    flown("r", T(3, 7), T(2, 0), retimed=(T(2, 20), T(5, 7)), flight_no="12"),
    flown("b", T(3, 8), T(2, 0), cancelled=T(2, 18), flight_no="13"),
    flown("early", T(3, 5), T(1, 21), cancelled=T(2, 18), flight_no="14"),
]
GATE_AT = T(3, 8)


def test_a_retime_near_the_gate(small_gate):
    # seen to 12:00 on the 5th, LY 12 is not closed, and its moment plus 24 hours (07:00 on the 3rd) comes before the
    # gate: it could still enter the row before it, so the gate waits
    numbers_ = NEAR_THE_GATE
    table, obs = [n for n, _ in numbers_], [o for _, own in numbers_ for o in own]
    flights_ = counting.flights(table, T(5, 12))
    passings_ = counting.passings(counting.stretches(table, obs), ())
    counted_ = record.counted_cells([c for c in counting.cells(flights_, passings_) if c.h == 24], START)
    assert [c.flight.numbers for c in counted_] == [("a",), ("b",)]
    assert record.unclosed(flights_, passings_, START) == [T(2, 7)]
    assert record.gate_reached_at(counted_, [], START) == GATE_AT  # the count and the day are there
    assert record.gate_reached_at(counted_, [GATE_AT - timedelta(hours=24)], START) is None
    assert record.gate_reached_at(counted_, [GATE_AT - timedelta(hours=24) + timedelta(seconds=1)], START) == GATE_AT
    waiting = run_on(numbers_, T(5, 12), START)
    assert (waiting.gate_at, waiting.row_cancelled) == (None, 2)
    # seen to 12:00 on the 7th, LY 12 is closed and in the row at its moment: the gate is declared, and a later run
    # reads the same flights
    declared = run_on(numbers_, T(7, 12), START)
    assert declared.gate_at == GATE_AT
    s2 = declared.signs["S2"][0]
    assert (s2.flights_with + s2.flights_without, declared.row_cancelled) == (3, 2)
    assert declared.days == pytest.approx(1 + 10 / 24)  # to 08:00 on the 3rd, the latest flight read
    assert run_on(numbers_, T(9, 12), START) == declared


def test_flights_after_the_gate_are_not_read_whenever_it_runs(small_gate):
    # a later run holds flights scheduled after the gate, counted, closed and in the row: LY 15 an hour after it, LY 16
    # listed as cancelled at 12:00 on the 3rd, and an arrival on the 6th; it reads none of them
    after = [flown("e", T(3, 9), T(2, 0), flight_no="15"),
             flown("c", T(4, 0), T(2, 0), cancelled=T(3, 12), flight_no="16"),
             flown("d", T(6, 0), T(4, 0), direction="A", airport="CDG", flight_no="17")]
    declared = run_on(NEAR_THE_GATE, T(7, 12), START)
    later = run_on(NEAR_THE_GATE + after, T(9, 12), START)
    assert later == declared
    numbers_ = NEAR_THE_GATE + after
    table, obs = [n for n, _ in numbers_], [o for _, own in numbers_ for o in own]
    flights_ = counting.flights(table, T(9, 12))
    passings_ = counting.passings(counting.stretches(table, obs), ())
    counted_ = record.counted_cells([c for c in counting.cells(flights_, passings_) if c.h == 24], START)
    assert len(counted_) == 6 and len(record.read_until(counted_, GATE_AT)) == 3  # read without the bound, they count
    assert record.read_until(counted_, None) == counted_


def test_unclosed_holds_the_counted_flights_not_yet_closed():
    # seen to 12:00 on the 5th, flights scheduled after 12:00 on the 3rd are not closed. LY 21 and AF 21 are one flight
    # at 06:00 on the 4th; AF 21 showed 05:00 until 08:00 on the 3rd, so it passed 24 hours at 05:00, an hour before
    # LY 21. LY 22 was first seen before the start; LY 23 already showed cancelled at its moment; LY 24 is closed
    numbers_ = [flown("x", T(4, 6), T(1, 23), flight_no="21"),
                flown("y", T(4, 5), T(1, 23), airline="AF", flight_no="21", retimed=(T(3, 8), T(4, 6))),
                flown("z", T(4, 9), T(1, 21), flight_no="22"),
                flown("w", T(4, 10), T(1, 23), cancelled=T(3, 3), flight_no="23"),
                flown("v", T(3, 0), T(1, 23), flight_no="24")]
    table, obs = [n for n, _ in numbers_], [o for _, own in numbers_ for o in own]
    flights_ = counting.flights(table, T(5, 12))
    assert [f.numbers for f in flights_ if len(f.numbers) > 1] == [("x", "y")]
    passings_ = counting.passings(counting.stretches(table, obs), ())
    assert {fid: passings_[fid, 24] for fid in "xyvw"} == {
        "x": (T(3, 6), "ON TIME"), "y": (T(3, 5), "ON TIME"), "v": (T(2, 0), "ON TIME"), "w": (T(3, 10), "CANCELED")}
    assert record.unclosed(flights_, passings_, START) == [T(3, 5)]


def test_s1s_sets_hold_departures_only():
    # LY 31 leaves for ATH at 10:00 on 3 November; LY 32 lands from ATH at 06:00 and is listed as cancelled from 09:00
    # on the 2nd, after its own 24-hour moment and before LY 31's: LY 31 carries S1. The arrival is in the row and
    # counts for the gate, but it is in neither of S1's sets, as A0b's `signcell` keeps them; it is in S2's
    numbers_ = [flown("x", T(3, 10), T(2, 0), flight_no="31"),
                flown("y", T(3, 6), T(2, 0), cancelled=T(2, 9), direction="A", flight_no="32")]
    result = run_on(numbers_, T(7, 12), START)
    s1, s2 = result.signs["S1"][0], result.signs["S2"][0]
    assert (s1.cancelled_with, s1.flights_with, s1.cancelled_without, s1.flights_without) == (0, 1, 0, 0)
    assert (s2.cancelled_with, s2.flights_with, s2.cancelled_without, s2.flights_without) == (0, 0, 1, 2)
    assert (result.gate_at, result.row_cancelled) == (None, 1)


def test_the_retest_counts_only_from_its_own_start(israeli_machine, record_model, tmp_path, started):
    # 23:00 UTC on 10 January is 01:00 on the 11th in Israel; the next Israel midnight is 22:00 UTC on the 11th
    assert record.retest_start(datetime(2027, 1, 10, 23, 0)) == datetime(2027, 1, 11, 22, 0)
    assert record.retest_start(datetime(2027, 1, 10, 21, 59)) == datetime(2027, 1, 10, 22, 0)
    assert record.retest_start(datetime(2027, 1, 10, 22, 0)) == datetime(2027, 1, 11, 22, 0)  # the next, not this
    # the re-test of a split first uploaded at 23:00 UTC on 1 November starts at 22:00 UTC on the 2nd, and reads only
    # the flights first seen from then on
    args = ["--model", str(record_model), "--out", str(tmp_path)]
    assert record.main([*args, "--retest", "S2", "--first-upload", "2026-11-01T23:00:00Z"]) == 0
    retest = json.loads((tmp_path / record.TAG / "retest-S2" / "progress.json").read_text())
    assert retest["start"] == "2026-11-02T22:00:00Z"
    assert list(retest["signs"]) == ["S2"]  # the re-test is of the one sign whose split was uploaded
    table, obs, snaps = load(record_model)
    flights_ = counting.flights(table, counting.last_sighting(snaps))
    row = [c for c in counting.cells(flights_, counting.passings(counting.stretches(table, obs),
                                                                 counting.holes(snaps))) if c.h == 24]
    own = [c for c in row if c.flight.first_seen >= datetime(2026, 11, 2, 22)]
    assert 0 < len(own) < len(row)
    lift_ = retest["signs"]["S2"]["lift"]
    assert lift_["flights_with"] + lift_["flights_without"] == len(own)
    assert lift_["cancelled_with"] + lift_["cancelled_without"] == retest["row_cancelled"] == sum(c.k for c in own)


# --- the entry point: python -m timeline.record ------------------------------------------------------------------

RECORD_START = datetime(2026, 10, 31, 22)  # an Israel midnight (1 November), before every download below
H = timedelta(hours=1)


@pytest.fixture(scope="module")
def record_model(tmp_path_factory) -> Path:
    """A model built through the real build from downloads every 30 minutes, 1 November 00:00 to 7 November 12:00,
    each with its receipt: a flight every 2 hours 10 minutes from 2 November 00:00, four airlines and five airports,
    one in three an arrival, one in five listed as cancelled 10 hours ahead, every other one first listed 30 hours
    ahead and the rest 72 hours."""
    root = tmp_path_factory.mktemp("record")
    numbers_ = [Number(("LY", "IZ", "6H", "W6")[i % 4], str(500 + i), ("ATH", "CDG", "FCO", "LCA", "VIE")[i % 5],
                       nov(2, 0) + i * timedelta(hours=2, minutes=10), direction="A" if i % 3 == 0 else "D",
                       cancelled=10 * H if i % 5 == 2 else None, first=(30 if i % 2 else 72) * H)
                for i in range(62)]
    raw, receipts = root / "raw", root / "receipts"
    t = nov(1, 0)
    while t <= nov(7, 12):
        rows = [r for r in (n.at(t) for n in numbers_) if r is not None]
        write_receipt(receipts, write_snapshot(raw, t, rows), rows=len(rows))
        t += timedelta(minutes=30)
    model_build.build(raw, root / "model", receipts)
    return root / "model"


@pytest.fixture
def started(monkeypatch):
    """The counting start before every flight of record_model, and the gate at 3 cancelled flights and 2 days, so
    that the model reaches it (at 02:00 on 3 November)."""
    monkeypatch.setattr(record, "COUNTING_START", RECORD_START)
    monkeypatch.setattr(record, "GATE_CANCELLED", 3)
    monkeypatch.setattr(record, "GATE_DAYS", 2)


def files(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def test_main_needs_the_counting_start(record_model, tmp_path, monkeypatch, capsys):
    args = ["--model", str(record_model), "--out", str(tmp_path)]
    monkeypatch.setattr(record, "COUNTING_START", None)
    assert record.main(args) == 2
    assert "Task 8" in capsys.readouterr().err
    assert not (tmp_path / record.TAG).exists()
    monkeypatch.setattr(record, "COUNTING_START", RECORD_START)
    assert record.main(args) == 0
    progress = tmp_path / record.TAG / "progress.json"
    first = progress.read_bytes()
    progress.write_text("an earlier run's")
    assert record.main(args) == 0
    assert progress.read_bytes() == first
    assert f"{tmp_path / record.TAG}: " in capsys.readouterr().out


def test_a_second_run_does_not_replace_the_first(record_model, tmp_path, started, monkeypatch, capsys):
    args = ["--model", str(record_model), "--out", str(tmp_path)]
    assert record.main(args) == 0
    stored = (tmp_path / record.TAG / "result.json").read_bytes()
    assert record.main(args) == 0
    assert (tmp_path / record.TAG / "result.json").read_bytes() == stored
    # a run whose own result differs (here, one more cancelled flight) prints both and leaves the stored one
    real = record.run
    monkeypatch.setattr(record, "run", lambda *a: replace(real(*a), row_cancelled=real(*a).row_cancelled + 1))
    capsys.readouterr()
    assert record.main(args) == 1
    err = capsys.readouterr().err
    cancelled = json.loads(stored)["row_cancelled"]
    assert stored.decode() in err and f'"row_cancelled": {cancelled + 1},' in err
    assert (tmp_path / record.TAG / "result.json").read_bytes() == stored


def test_a_run_that_loses_a_recorded_gate_fails(record_model, tmp_path, started, monkeypatch, capsys):
    # a later run that does not reach the gate (here, with the gate moved to 100 cancelled flights) differs from the
    # stored result: it prints both and exits 1, and the stored result stays as it was
    args = ["--model", str(record_model), "--out", str(tmp_path)]
    assert record.main(args) == 0
    stored = (tmp_path / record.TAG / "result.json").read_bytes()
    monkeypatch.setattr(record, "GATE_CANCELLED", 100)
    capsys.readouterr()
    assert record.main(args) == 1
    out, err = capsys.readouterr()
    assert out.endswith("gate not reached\n")
    assert stored.decode() in err and '"gate_at": null,' in err
    assert (tmp_path / record.TAG / "result.json").read_bytes() == stored


def test_two_runs_under_different_hash_seeds_write_the_same_bytes(record_model, tmp_path):
    outs = []
    for seed in ("0", "1"):
        out = tmp_path / f"record-{seed}"
        code = ("import sys; from datetime import datetime; from timeline import record; "
                f"record.COUNTING_START = datetime({RECORD_START:%Y, %-m, %-d, %-H}); "
                "record.GATE_CANCELLED, record.GATE_DAYS = 3, 2; "
                f"sys.exit(record.main(['--model', {str(record_model)!r}, '--out', {str(out)!r}]))")
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=os.pathsep.join(["src", "tests"]))
        done = subprocess.run([sys.executable, "-c", code], env=env, cwd=Path(__file__).parent.parent,
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        outs.append(files(out))
    assert outs[0] == outs[1]
    assert list(outs[0]) == [f"{record.TAG}/progress.json", f"{record.TAG}/result.json"]


def float_digits(value) -> list[int]:
    """The significant digits of each float in a Result's fields, as Python writes it in full."""
    if isinstance(value, float):
        return [len(Decimal(repr(value)).normalize().as_tuple().digits)]
    if isinstance(value, (list, tuple)):
        return [d for v in value for d in float_digits(v)]
    if isinstance(value, dict):
        return float_digits(list(value.values()))
    if hasattr(value, "__dataclass_fields__"):
        return float_digits([getattr(value, name) for name in value.__dataclass_fields__])
    return []


def test_the_result_file_is_sorted_with_fixed_floats(record_model, tmp_path, started):
    assert record.main(["--model", str(record_model), "--out", str(tmp_path)]) == 0
    result = record.run(*load(record_model), RECORD_START)
    assert max(float_digits(result)) > 12  # the cut has something to cut
    for name in ("progress.json", "result.json"):
        orders: list[list[str]] = []
        data = json.loads((tmp_path / record.TAG / name).read_text(),
                          object_pairs_hook=lambda pairs: orders.append([k for k, _ in pairs]) or dict(pairs),
                          parse_float=Decimal)
        assert orders and all(keys == sorted(keys) for keys in orders), orders
        decimals = [v for d in [data] + [data["signs"][s][part] for s in record.SIGNS for part in ("lift", "scores")]
                    for v in d.values() if isinstance(v, Decimal)]
        assert decimals and max(len(d.normalize().as_tuple().digits) for d in decimals) <= 12
        assert (data["start"], data["gate_at"]) == ("2026-10-31T22:00:00Z", "2026-11-03T02:00:00Z")
        assert list(data["signs"]) == list(record.SIGNS) and list(data["signs"]["S1"]) == ["lift", "scores"]


def test_a_retest_writes_its_own_folder(record_model, tmp_path, started):
    args = ["--model", str(record_model), "--out", str(tmp_path)]
    assert record.main(args) == 0
    main_test = files(tmp_path / record.TAG)
    assert list(main_test) == ["progress.json", "result.json"]
    assert record.main([*args, "--retest", "S3", "--first-upload", "2027-01-10T23:00:00Z"]) == 0
    after = files(tmp_path / record.TAG)
    assert list(after) == ["progress.json", "result.json", "retest-S3/progress.json"]
    assert {name: after[name] for name in main_test} == main_test
    retest = json.loads((tmp_path / record.TAG / "retest-S3" / "progress.json").read_text())
    # no flight was first seen after 22:00 UTC on 11 January 2027: nothing read, no gate
    assert (retest["start"], retest["gate_at"], retest["row_cancelled"], retest["days"]) == (
        "2027-01-11T22:00:00Z", None, 0, None)
    assert list(retest["signs"]) == ["S3"]


@pytest.mark.parametrize("value", ["2027-01-10T23:00:00", "2027-01-10T23:00:00+02:00", "yesterday",
                                   "2027-01-32T23:00:00Z", "2027-01-10T23:00:00+02:00Z", "2027-01-10Z"])
def test_first_upload_must_end_in_z(record_model, tmp_path, started, capsys, value):
    with pytest.raises(SystemExit) as stop:
        record.main(["--model", str(record_model), "--out", str(tmp_path), "--retest", "S3", "--first-upload", value])
    assert stop.value.code == 2
    assert "--first-upload" in capsys.readouterr().err
    assert not (tmp_path / record.TAG).exists()


@pytest.mark.parametrize("given", [["--retest", "S3"], ["--first-upload", "2027-01-10T23:00:00Z"]])
def test_the_retest_needs_both_options(record_model, tmp_path, started, capsys, given):
    with pytest.raises(SystemExit) as stop:
        record.main(["--model", str(record_model), "--out", str(tmp_path), *given])
    assert stop.value.code == 2
    assert "--retest and --first-upload" in capsys.readouterr().err
