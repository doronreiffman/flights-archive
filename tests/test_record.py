"""The signs S1 to S4 (docs/flight-lookup.md, "Signs"; docs/flight-lookup-figures.md, A0b's `nrow`, `not_whole`,
`nsign` and `sign`): each read for a number at its own checkpoint moment, from what the list showed then and nothing
later, and carried by the number's flight. Expected values by hand.

Unless a test says otherwise, every number is first listed at the first download, FIRST, and last seen on 6 November;
the reader is LY 1 departing to ATH at 12:00 on 3 November, whose 24-hour moment is 12:00 on the 2nd.
"""
from datetime import date, datetime, timedelta

import pytest

from counting_helpers import T, board, number, seen
from timeline import counting, record

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
