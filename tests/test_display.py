"""Rules shown only on pages (src/timeline/display.py): a flight's label in lists and its DELAYED mark (C10), a
cancelled flight's warning number (C9), and the front page's figures: the closed flights with no known result counted
beside the rates (the count line, A3), the cancelled ones by where their first cancelled listing falls (the late line,
A17) and the Israel date of the first list. Expected values by hand.

Rows are the model's flights table as counting reads it (tests/counting_helpers.py: LY 1 departing to ATH from
terminal 3 at desks 1-5 by default), with the cancellation columns display reads. The last sighting is LAST, so a
flight is closed when scheduled by 4 November 00:00. All times are naive UTC.
"""
from datetime import date, datetime, timedelta

from counting_helpers import T, board
from counting_helpers import number as counting_number
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import counting, display, words

LAST = T(6, 0)  # the last sighting
CLOSED = T(3, 12)  # a time 60 hours before it: closed
H = timedelta(hours=1)
BRACKET = {"canceled_first_seen_at": None, "cancel_lead_min": None, "cancel_lead_max_min": None,
           "cancel_lead_censored": None}  # the model's R8 columns, none set for a number never listed as cancelled


def number(fid: str, sched: datetime, outcome: str, **kw) -> dict:
    """A flights row with the outcome given; `kw` sets any column of counting_helpers.number or of BRACKET."""
    own = {k: kw.pop(k) for k in list(kw) if k in BRACKET}
    return counting_number(fid, sched, outcome=outcome, **kw) | BRACKET | own


def cancelled(fid: str, sched: datetime, first_seen: datetime, lead_min: float | None, lead_max: float | None,
              censored: bool = False, **kw) -> dict:
    """A number that ended listed as cancelled: first seen as cancelled at `first_seen`, its bracket (R8) running
    `lead_max` to `lead_min` minutes before the scheduled time."""
    return number(fid, sched, "canceled", canceled_first_seen_at=first_seen, cancel_lead_min=lead_min,
                  cancel_lead_max_min=lead_max, cancel_lead_censored=censored, **kw)


def one_flight(*rows: dict) -> tuple[counting.Flight, dict[str, dict]]:
    """The one flight rule C1 makes of `rows`, and the rows by flight_id."""
    (f,) = counting.flights(list(rows), LAST)
    return f, {r["flight_id"]: r for r in rows}


# --- C10: a flight's label in lists ---------------------------------------------------------------------

def test_a_flight_with_a_number_still_listed_is_upcoming_until_it_departs():
    def flight(other: str, sched: datetime = T(5, 12), direction: str = "D"):
        """LH 0691A listed as cancelled, and LH 695 of the same flight (C1: one airline) ending as `other`."""
        return one_flight(
            cancelled("a", sched, sched - 20 * H, 20 * 60, 20 * 60 + 15, airline="LH", flight_no="0691A",
                      direction=direction),
            number("b", sched, other, airline="LH", flight_no="695", direction=direction))

    still_listed = flight("open")
    assert display.label(*still_listed, T(5, 0)) == words.UPCOMING
    assert display.label(*still_listed, T(5, 12)) == words.NO_NEWS_YET  # at its scheduled time it has passed
    assert display.label(*still_listed, T(5, 13)) == words.NO_NEWS_YET
    # Review Focus 2: 48 hours on, closed with a number still listed, NO NEWS YET; counted as cancelled (C2)
    closed = flight("open", sched=CLOSED)
    assert (closed[0].closed, closed[0].result) == (True, "cancelled")
    assert display.label(*closed, LAST) == words.NO_NEWS_YET
    # once LH 695 departs, or lands for an arrival
    assert display.label(*flight("departed"), T(5, 13)) == words.DEPARTED
    assert display.label(*flight("landed", direction="A"), T(5, 13)) == words.LANDED
    # rule 1 before rule 2: one number departed while another is still listed
    f, by_id = one_flight(cancelled("a", T(5, 12), T(5, 0), 12 * 60, 12 * 60 + 15, airline="LH", flight_no="0691A"),
                          number("b", T(5, 12), "departed", airline="LH", flight_no="695"),
                          number("c", T(5, 12), "open", airline="LH", flight_no="697"))
    assert len(f.numbers) == 3 and display.label(f, by_id, T(5, 13)) == words.DEPARTED


def test_cancelled_only_when_no_number_is_listed_otherwise():
    sched = T(5, 12)
    assert display.label(*one_flight(cancelled("a", sched, T(5, 0), 12 * 60, 12 * 60 + 15)), LAST) == words.CANCELLED
    for others in (("vanished",), ("gap", "dropped")):
        f, by_id = one_flight(cancelled("a", sched, T(5, 0), 12 * 60, 12 * 60 + 15),
                              *(number(f"b{i}", sched, o, flight_no=str(2 + i)) for i, o in enumerate(others)))
        assert len(f.numbers) == 1 + len(others)
        assert display.label(f, by_id, T(5, 0)) == words.CANCELLED, others
    f, by_id = one_flight(number("a", sched, "gap"), number("b", sched, "vanished", flight_no="2"),
                          number("c", sched, "dropped", flight_no="3"))
    assert display.label(f, by_id, LAST) == words.UNKNOWN


def test_delayed_at_59_and_at_60_minutes():
    assert display.DELAY_MINUTES == 60
    assert not display.delayed_an_hour({"est_minus_sched_min": 59.0})
    assert display.delayed_an_hour({"est_minus_sched_min": 60.0})
    assert display.delayed_an_hour({"est_minus_sched_min": 61.5})
    assert not display.delayed_an_hour({"est_minus_sched_min": -90.0})  # early is not late


def test_no_expected_time_is_not_delayed():
    assert not display.delayed_an_hour({"est_minus_sched_min": None})


# --- C9: a cancelled flight's warning -------------------------------------------------------------------

def test_the_warning_number_is_the_first_listed_as_cancelled():
    # LY 7 listed as cancelled first; LY 9 earlier still, but changed back and gone with no final status: not a
    # number that ended listed as cancelled
    f, by_id = one_flight(cancelled("a", CLOSED, T(3, 0), 12 * 60, 12 * 60 + 15, flight_no="5"),
                          cancelled("b", CLOSED, T(2, 12), 24 * 60, 24 * 60 + 15, flight_no="7"),
                          number("c", CLOSED, "vanished", flight_no="9", canceled_first_seen_at=T(2, 0)))
    assert display.warning_number(f, by_id) == "b"
    # listed as cancelled at the same moment: the airline decides, then the number
    at = T(3, 0)
    f, by_id = one_flight(cancelled("x", CLOSED, at, 12 * 60, 12 * 60 + 15, airline="UX", flight_no="1302"),
                          cancelled("y", CLOSED, at, 12 * 60, 12 * 60 + 15, flight_no="9999"),
                          cancelled("z", CLOSED, at, 12 * 60, 12 * 60 + 15, flight_no="730"))
    assert display.warning_number(f, by_id) == "z"
    # a flight still listed by another number is cancelled under C2: its warning is the cancelled number's
    f, by_id = one_flight(cancelled("a", T(5, 12), T(5, 0), 12 * 60, 12 * 60 + 15), number("b", T(5, 12), "open"))
    assert display.warning_number(f, by_id) == "a"
    # None when the flight is not cancelled: one of its numbers departed, or its result is unknown
    f, by_id = one_flight(cancelled("a", CLOSED, T(3, 0), 12 * 60, 12 * 60 + 15), number("b", CLOSED, "departed"))
    assert f.result == "operated" and display.warning_number(f, by_id) is None
    f, by_id = one_flight(number("a", CLOSED, "gap", canceled_first_seen_at=T(3, 0)))
    assert f.result == "unknown" and display.warning_number(f, by_id) is None


# --- the front page's figures ---------------------------------------------------------------------------

SNAPS = board((T(1, 0), LAST))  # one list, seen until the last sighting


def test_unknown_counted_beside():
    table = [
        # left during the hole: three closed flights, the third with a number that left with no final status
        number("g1", CLOSED, "gap", airport="BER"),
        number("g2", CLOSED, "gap", airport="CDG"),
        number("g3", CLOSED, "gap", airport="DUB"), number("g3b", CLOSED, "vanished", airport="DUB", flight_no="2"),
        # left with no final status: before its time, and after it
        number("v", CLOSED, "vanished", airport="FCO"),
        number("d", CLOSED, "dropped", airport="GVA"),
        # not counted: a flight not yet closed, and closed flights with a known result
        number("open", T(5, 0), "gap", airport="HEL"),
        number("dep", CLOSED, "departed", airport="IST"),
        cancelled("can", CLOSED, T(3, 0), 12 * 60, 12 * 60 + 15, airport="JFK"),
    ]
    s = display.summary(table, [], SNAPS)
    assert (s.unknown, s.unknown_gap, s.unknown_no_final) == (5, 3, 2)
    assert s.figures == counting.figures(table, [], SNAPS)
    assert (s.figures.total.cancelled, s.figures.total.flights) == (1, 2)


def test_the_late_line_from_the_bracket():
    def flight(airport: str, lead_min: float, lead_max: float, censored: bool = False) -> dict:
        """A closed flight of one number listed as cancelled, its bracket from `lead_max` to `lead_min` minutes before
        the scheduled time."""
        return cancelled(airport, CLOSED, CLOSED - lead_min * timedelta(minutes=1), lead_min, lead_max, censored,
                         airport=airport)

    table = [
        flight("AAA", -50, -20),  # wholly after the scheduled time
        flight("BBB", -10, 5), flight("CCC", -15, 0),  # the bracket holds it
        # cannot be placed: the bracket spans the hole, wherever its ends fall
        flight("DDD", -300, -100, censored=True), flight("EEE", -30, 200, censored=True),
        flight("FFF", 300, 900, censored=True),
        flight("GGG", 60, 75), flight("HHH", 0, 15), flight("III", 9 * 60, 9 * 60 + 30),  # before it
        # two numbers listed as cancelled: the first decides (C9), before the scheduled time; the second came after
        cancelled("JJJ", CLOSED, CLOSED - 2 * H, 120, 135, airport="JJJ"),
        cancelled("JJJb", CLOSED, CLOSED + H, -60, -45, airport="JJJ", flight_no="2"),
        # not counted: a flight not yet closed, and a cancelled number in a flight that departed
        cancelled("KKK", T(5, 0), T(5, 1), -60, -45, airport="KKK"),
        cancelled("LLL", CLOSED, CLOSED + H, -60, -45, airport="LLL"), number("LLLb", CLOSED, "departed", airport="LLL",
                                                                              flight_no="2"),
    ]
    s = display.summary(table, [], SNAPS)
    assert (s.late_after, s.late_holds, s.late_unplaced, s.late_before) == (1, 2, 3, 4)
    assert s.figures.total.cancelled == 10
    # already cancelled when first seen: no bracket at all, and it cannot be placed
    s = display.summary([flight("AAA", -50, -20), cancelled("MMM", CLOSED, T(2, 0), 36 * 60, None, True)], [], SNAPS)
    assert (s.late_after, s.late_holds, s.late_unplaced, s.late_before) == (1, 0, 1, 0)


def test_the_first_record_is_the_israel_date(israeli_machine):
    assert display.summary([], [], board((datetime(2026, 10, 27, 22, 30), LAST))).first_record == date(2026, 10, 28)
    assert display.summary([], [], board((datetime(2026, 10, 27, 18, 4, 46), LAST))).first_record == date(2026, 10, 27)
