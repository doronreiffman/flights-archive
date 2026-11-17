"""The blend (src/timeline/blend.py; docs/flight-lookup.md, "The blend" and "Left to the builder"): a flight page's two
chances, cancelled and delayed an hour or more, from the flight number's own record, its airline's and the airport's.

The chances are hand-computed from the design's counts (docs/flight-lookup.md:305-330), recomputed for the plan to
the digits shown; every value is checked with `approx(rel=1e-4)`. The counts are checked on rows built with
tests/counting_helpers.py (LY 1 departing to ATH from terminal 3 at desks 1-5 by default), and the airport on the
hand-built model of tests/counting_fixture.py. The last sighting is LAST, so a flight is closed when scheduled by
4 November 00:00. All times are naive UTC.
"""
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import partial

import pytest

import counting_fixture
from counting_helpers import T, board, seen
from counting_helpers import number as counting_number
from timeline import blend, counting, rates, words
from timeline.blend import EMPTY, Airport, Tally, cancel_chance, delay_chance, pull, scaling

approx = partial(pytest.approx, rel=1e-4)
LAST = T(6, 0)  # the last sighting
CLOSED = T(3, 0)  # 72 hours before it: closed
H = timedelta(hours=1)


def made(k: int, n: int, airlines: int = 5, days: int = 5) -> rates.Rate:
    """C8's rate of k cancelled flights in n, the cancelled ones spread over `airlines` airlines and `days` days: it
    clears the floor at 10 or more cancelled with the defaults."""
    hit = [rates.Counted(1, f"A{i % airlines}", date(2026, 11, 1 + i % days)) for i in range(k)]
    return rates.rate(hit + [rates.Counted(0, "A0", date(2026, 11, 1))] * (n - k))


# The design's airport (docs/flight-lookup.md:307-315 and :327-330): the total 104 of 6,115, each row clearing the
# floor, and the delays an hour or more of departures and arrivals that flew.
AP = Airport(total=made(104, 6115),
             rows={70: made(71, 4472), 48: made(69, 4760), 24: made(52, 4892), 12: made(39, 5069), 6: made(31, 5149),
                   3: made(23, 5195)},
             delay={"D": made(231, 2982), "A": made(149, 3029)})


def tally(flights: int, cancelled: int, flew: int, delayed: int) -> Tally:
    """A record's counts; the chances read only the four counts."""
    return Tally(flights, cancelled, flew, delayed, (date(2026, 11, 9),) * cancelled,
                 T(9, 10) if cancelled else None)


LO155, LOT = tally(22, 0, 22, 0), tally(127, 0, 127, 2)
LH694, LH697, LH = tally(14, 4, 10, 0), tally(2, 1, 1, 0), tally(183, 11, 172, 7)


# --- the chances, hand-computed ------------------------------------------------------------------------

def test_lo_155():   # the number 0 of 22, LOT 0 of 127 with 2 delayed
    assert cancel_chance(LO155, LOT, AP, 48) == approx(0.0024834)
    assert cancel_chance(LO155, LOT, AP, 70) == approx(0.0027199)
    assert delay_chance(LO155, LOT, AP, "A") == approx(0.011854)


def test_lh_694():   # the number 4 of 14, 10 flew; Lufthansa 11 of 183, 172 flew, 7 delayed
    assert cancel_chance(LH694, LH, AP, 70) == approx(0.154306)
    assert delay_chance(LH694, LH, AP, "A") == approx(0.025562)


def test_lh_697():   # the number 1 of 2, 1 flew
    assert cancel_chance(LH697, LH, AP, 70) == approx(0.095003)
    assert delay_chance(LH697, LH, AP, "D") == approx(0.050601)


def test_a_number_with_no_flights_takes_its_airlines_rate():
    # Lufthansa (11 + 100 x 104 / 6,115) / (183 + 100) = 0.044879, by 71 / 4,472 over 104 / 6,115 = 0.93351
    assert cancel_chance(EMPTY, LH, AP, 70) == approx(0.044879 * 0.93351)
    # (7 + 100 x 231 / 2,982) / (172 + 100)
    assert delay_chance(EMPTY, LH, AP, "D") == approx(0.054215)


def test_an_airline_with_none_takes_the_airports():
    # the airport's rate, scaled by the row for the time left: the row's own rate
    assert cancel_chance(EMPTY, EMPTY, AP, 24) == approx(52 / 4892)
    assert delay_chance(EMPTY, EMPTY, AP, "A") == approx(149 / 3029)
    # a number with flights under an airline with none is pulled towards the airport's rate: LH 697's 1 of 2
    assert cancel_chance(LH697, EMPTY, AP, 70) == approx((1 + 14 * 104 / 6115) / 16 * 0.93351)


def test_each_pull_at_its_weight():
    assert (blend.NUMBER_WEIGHT, blend.AIRLINE_WEIGHT) == (14, 100)
    assert pull(1, 2, 0.1, 14) == approx((1 + 1.4) / 16)
    assert pull(1, 2, 0.1, 100) == approx((1 + 10) / 102)
    assert pull(0, 0, 0.3, 14) == approx(0.3)


def test_the_scaling_by_each_row():
    assert [round(scaling(AP, h), 3) for h in counting.CHECKPOINTS] == [0.934, 0.852, 0.625, 0.452, 0.354, 0.260]
    # LH 694 before the scaling is 16.5%; on the 6-hour row (6.0%) the factor 0.354 applies
    assert cancel_chance(LH694, LH, AP, 6) == approx(0.165297 * 31 / 5149 / (104 / 6115))


def test_a_delay_is_not_scaled():
    flat = replace(AP, rows={h: made(r.cancelled * 2, r.flights) for h, r in AP.rows.items()})
    assert delay_chance(LH694, LH, flat, "A") == delay_chance(LH694, LH, AP, "A") == approx(0.025562)


def test_a_clean_history_gives_a_chance_above_zero():
    clean = tally(127, 0, 127, 0)
    assert all(cancel_chance(LO155, clean, AP, h) > 0 for h in counting.CHECKPOINTS)
    assert delay_chance(LO155, clean, AP, "D") > 0 and delay_chance(LO155, clean, AP, "A") > 0


def test_no_chance_of_cancelling_on_an_airport_with_no_counted_flight():
    bare = Airport(total=rates.rate([]), rows=dict.fromkeys(counting.CHECKPOINTS, rates.rate([])), delay=AP.delay)
    assert cancel_chance(LH694, LH, bare, 70) is None and cancel_chance(EMPTY, EMPTY, bare, 3) is None
    # a small model: its one flight departed a day before the last sighting, so none is closed yet
    r = counted(number("a", T(5, 0)))
    assert r.airport.total.flights == 0 and r.numbers[("LY", "1", "D")] == Tally(1, 0, 1, 0, (), None)
    assert cancel_chance(r.numbers[("LY", "1", "D")], r.airlines["LY"], r.airport, 70) is None


def test_no_chance_of_a_delay_when_none_of_the_directions_flights_flew():
    no_departures = replace(AP, delay={"D": rates.rate([]), "A": AP.delay["A"]})
    assert delay_chance(LH697, LH, no_departures, "D") is None
    assert delay_chance(EMPTY, EMPTY, no_departures, "D") is None
    assert delay_chance(LH694, LH, no_departures, "A") == approx(0.025562)  # arrivals still have theirs
    # a small model: its one closed departure was cancelled, so no closed departure flew
    r = counted(number("a", CLOSED, "canceled"))
    assert (r.airport.total.cancelled, r.airport.total.flights, r.airport.delay["D"].flights) == (1, 1, 0)
    assert delay_chance(r.numbers[("LY", "1", "D")], r.airlines["LY"], r.airport, "D") is None


def test_row_for_each_stretch():
    found = [blend.row_for(h) for h in (72, 48.0001, 48, 24, 12, 6, 3, 0.5, None)]
    assert found == [70, 70, 48, 24, 12, 6, 3, 3, 70]
    assert blend.row_for(100) == 70  # above 72 hours, the 70-hour row still
    assert blend.row_for(0) == 3  # at the scheduled time, the nearest row at or above it


def test_a_row_below_the_floor_scales_by_the_nearest_clearing_row():
    def thin(h: int) -> rates.Rate:  # the row's flights, its cancelled ones from 4 airlines: below the floor
        return made(AP.rows[h].cancelled, AP.rows[h].flights, airlines=4)

    def without(*hs: int) -> Airport:
        return replace(AP, rows=AP.rows | {h: thin(h) for h in hs})

    assert not thin(3).clears_floor
    assert scaling(without(3), 3) == scaling(AP, 6)  # more time left first, the nearest
    assert scaling(without(70), 70) == scaling(AP, 48)  # none with more: the nearest with less
    assert scaling(without(24), 24) == scaling(AP, 48)  # not the 12-hour row
    assert scaling(without(24, 48), 24) == scaling(AP, 70)  # every row with more time left before one with less
    unscaled = without(*counting.CHECKPOINTS)
    assert scaling(unscaled, 70) is None and scaling(unscaled, 3) is None
    assert cancel_chance(LH694, LH, unscaled, 70) == approx(0.165297)


# --- the counts ----------------------------------------------------------------------------------------

def number(fid: str, sched: datetime, outcome: str = "departed", late: float | None = 0.0, name: str = "EL AL",
           **kw) -> dict:
    """A flights row with the columns the blend reads beside counting's: the airport's final expected time less the
    scheduled time in minutes (the model's `est_minus_sched_min`) and the airline's name as published."""
    return counting_number(fid, sched, outcome=outcome, **kw) | {"est_minus_sched_min": late, "airline_name": name}


def counted(*rows: dict, before: datetime | None = None) -> blend.Records:
    """The records of `rows`, with no observations, as of LAST."""
    return blend.records(list(rows), [], board(LAST), before)


def test_the_endings_that_count():
    assert [blend.known(x) for x in (words.DEPARTED, words.LANDED, words.CANCELLED)] == [True] * 3
    assert [blend.known(x) for x in (words.UPCOMING, words.NO_NEWS_YET, words.UNKNOWN)] == [False] * 3


def test_which_flights_are_counted():
    past, ahead = T(5, 12), T(6, 12)  # before and after the last sighting; each case in a slot of its own
    r = counted(
        number("a", past, flight_no="1"),  # DEPARTED
        number("b", ahead, "canceled", flight_no="2"),  # CANCELLED ahead of its time
        number("c", ahead + H, "open", flight_no="3"),  # UPCOMING
        number("d", past - H, "vanished", flight_no="4"),  # UNKNOWN
        number("e", past - 2 * H, "open", flight_no="5"),  # NO NEWS YET
        # LY 6 marked cancelled while its partner LY 7 is still listed: the flight's ending is not known
        number("f", past - 3 * H, "canceled", flight_no="6"), number("g", past - 3 * H, "open", flight_no="7"),
        # LY 8 marked cancelled, LY 10 gone with no final word and LY 12 still listed, each beside a partner that
        # departed (Question 4)
        number("h", past - 4 * H, "canceled", flight_no="8"), number("i", past - 4 * H, flight_no="9"),
        number("j", past - 5 * H, "vanished", flight_no="10"), number("k", past - 5 * H, flight_no="11"),
        number("l", past - 6 * H, "open", flight_no="12"), number("m", past - 6 * H, flight_no="13"))
    flew, cancelled = Tally(1, 0, 1, 0, (), None), Tally(1, 1, 0, 0, (date(2026, 11, 6),), ahead)
    by_no = {no: r.numbers[("LY", no, "D")] for no in map(str, range(1, 14))}
    assert by_no == {"1": flew, "2": cancelled, "3": EMPTY, "4": EMPTY, "5": EMPTY, "6": EMPTY, "7": EMPTY,
                     "8": flew, "9": flew, "10": flew, "11": flew, "12": flew, "13": flew}
    assert r.airlines["LY"] == Tally(5, 1, 4, 0, (date(2026, 11, 6),), ahead)


def test_a_number_is_counted_per_direction():
    r = counted(number("a", T(5, 1)), number("b", T(4, 1)), number("c", T(5, 3), "landed", direction="A"),
                number("d", T(4, 3), "canceled", direction="A"))
    assert r.numbers[("LY", "1", "D")] == Tally(2, 0, 2, 0, (), None)
    assert r.numbers[("LY", "1", "A")] == Tally(2, 1, 1, 0, (date(2026, 11, 4),), T(4, 3))
    assert r.airlines["LY"] == Tally(4, 1, 3, 0, (date(2026, 11, 4),), T(4, 3))  # both directions


def test_the_airline_is_c8s_grouping_airline():
    # LO 155 and LY 9255 are one flight (C1), grouped under LO (C8: 155 before 9255); LO 155 also flies alone
    r = counted(number("a", T(5, 1), airline="LO", flight_no="155"), number("b", T(5, 1), flight_no="9255"),
                number("c", T(4, 1), airline="LO", flight_no="155", outcome="canceled"))
    assert r.numbers[("LY", "9255", "D")] == Tally(1, 0, 1, 0, (), None)
    assert r.numbers[("LO", "155", "D")] == Tally(2, 1, 1, 0, (date(2026, 11, 4),), T(4, 1))
    assert r.airlines["LO"] == Tally(2, 1, 1, 0, (date(2026, 11, 4),), T(4, 1))  # the number's own flights in it
    assert r.airlines.get("LY", EMPTY) == EMPTY


def test_a_tally_holds_its_cancelled_days_in_order_and_the_latest():
    r = counted(number("a", T(5, 23), "canceled"), number("b", T(2, 1), "canceled"), number("c", T(4, 1)),
                number("d", T(3, 1), "canceled"))
    # 5 November 23:00 UTC is 6 November in Israel
    assert r.numbers[("LY", "1", "D")] == Tally(4, 3, 1, 0, (date(2026, 11, 2), date(2026, 11, 3),
                                                              date(2026, 11, 6)), T(5, 23))


def test_a_delay_counts_flights_that_flew_an_hour_or_more_late():
    r = counted(
        number("a", CLOSED, late=59.0, flight_no="1"),
        number("b", CLOSED + H, late=60.0, flight_no="2"),
        # LY 3 marked cancelled, its own row an hour and a half late; its flight departed as LY 4, half an hour late
        number("c", CLOSED + 2 * H, "canceled", late=90.0, flight_no="3"),
        number("d", CLOSED + 2 * H, late=30.0, flight_no="4"),
        # its partner departed an hour late, the number's own row with no expected time
        number("e", CLOSED + 3 * H, "canceled", late=None, flight_no="5"),
        number("f", CLOSED + 3 * H, late=60.0, flight_no="6"),
        # a cancelled flight, late on its row: not among those that flew
        number("g", CLOSED + 4 * H, "canceled", late=120.0, flight_no="7"),
        # an arrival an hour late: counted for arrivals only
        number("h", CLOSED + 5 * H, "landed", late=60.0, flight_no="8", direction="A"))
    delays = {no: r.numbers[("LY", no, d)].delayed for no, d in
              (("1", "D"), ("2", "D"), ("3", "D"), ("4", "D"), ("5", "D"), ("6", "D"), ("7", "D"), ("8", "A"))}
    assert delays == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 1, "6": 1, "7": 0, "8": 1}
    assert r.numbers[("LY", "7", "D")] == Tally(1, 1, 0, 0, (date(2026, 11, 3),), CLOSED + 4 * H)
    assert r.airlines["LY"] == Tally(6, 1, 5, 3, (date(2026, 11, 3),), CLOSED + 4 * H)  # both directions
    # the airport's: closed flights with a known result that flew, each direction its own
    assert (r.airport.delay["D"].cancelled, r.airport.delay["D"].flights) == (2, 4)
    assert (r.airport.delay["A"].cancelled, r.airport.delay["A"].flights) == (1, 1)


def test_bad_week():
    def week(*days: date) -> Tally:
        return Tally(len(days), len(days), 0, 0, tuple(sorted(days)), None)

    assert blend.BAD_WEEK_DAYS == 6
    one, six, seven = date(2026, 11, 1), date(2026, 11, 7), date(2026, 11, 8)
    assert blend.bad_week(week(one, six)) == (one, six)
    assert blend.bad_week(week(one, date(2026, 11, 3), six)) == (one, six)
    assert blend.bad_week(week(one, seven)) is None
    assert blend.bad_week(week(one, date(2026, 11, 3), seven)) is None
    assert blend.bad_week(week(one)) is None
    assert blend.bad_week(EMPTY) is None
    assert blend.bad_week(week(six, six)) == (six, six)


def test_lead_is_c8s_number():
    def lead(*rows: dict) -> str:
        (f,) = counting.flights(list(rows), LAST)
        return blend.lead(f, {r["flight_id"]: r for r in rows})["flight_no"]

    assert lead(number("a", T(5, 1), flight_no="9255"), number("b", T(5, 1), airline="LO", flight_no="155")) == "155"
    # a lettered number by its digits, not as text: 691 before 695, 70 before 691
    assert lead(number("a", T(5, 1), airline="LH", flight_no="695"),
                number("b", T(5, 1), airline="LH", flight_no="0691A")) == "0691A"
    assert lead(number("a", T(5, 1), airline="LH", flight_no="0691A"),
                number("b", T(5, 1), airline="LH", flight_no="70")) == "70"


def test_published_name_is_the_latest_rows():
    r = counted(number("a", T(5, 1), name="EL AL"), number("b", T(2, 1), name="EL AL ISRAEL AIRLINES"),
                number("c", T(3, 1), airline="LO", flight_no="155", name="LOT  POLISH AIRLINES"))
    assert r.published == {"LO": "LOT  POLISH AIRLINES", "LY": "EL AL"}


# --- the airport: the frozen figures, and the cut -------------------------------------------------------

@pytest.fixture(scope="module")
def model():
    """The counting fixture's model, its rows with the delay and the published name the blend reads: one in ten
    of its everyday flights shows an expected time 45 minutes late (none an hour)."""
    table, obs, snaps = counting_fixture.model()
    def late(r):
        return None if r["est_utc_final"] is None else (r["est_utc_final"] - r["sched_utc_final"]).total_seconds() / 60
    return [r | {"est_minus_sched_min": late(r), "airline_name": r["airline"]} for r in table], obs, snaps


def test_the_airport_is_the_frozen_figures(model):
    figures = counting.figures(*model)
    airport = blend.records(*model).airport
    assert airport.total == figures.total and airport.rows == dict(figures.rows)
    assert airport.total.flights == 492 and airport.rows[24].flights == 407  # tests/test_counting.py's figures


def test_the_cut_at_the_last_sighting_equals_the_frozen_figures(model):
    full = blend.records(*model).airport
    assert blend.records(*model, before=counting.last_sighting(model[2])).airport == full


def test_a_cut_counts_only_flights_scheduled_before_it():
    def listed(fid: str, sched: datetime, outcome: str = "departed") -> tuple[dict, dict]:
        """A row and its one observation, 72 hours before its time: in every row of the table once closed."""
        return number(fid, sched, outcome), seen(fid, 1, sched - 72 * H, sched_utc=sched)

    cases = [listed("x", T(1, 0)), listed("y", T(2, 12), "canceled"), listed("z", T(4, 0))]
    table, obs = [row for row, _ in cases], [o for _, o in cases]
    full = blend.records(table, obs, board(LAST))
    cut = blend.records(table, obs, board(LAST), before=T(4, 0))  # closed by the cut: scheduled by 2 November 00:00
    assert full.numbers[("LY", "1", "D")] == Tally(3, 1, 2, 0, (date(2026, 11, 2),), T(2, 12))
    assert cut.numbers[("LY", "1", "D")] == Tally(2, 1, 1, 0, (date(2026, 11, 2),), T(2, 12))  # not z, at the cut
    assert cut.airlines["LY"] == cut.numbers[("LY", "1", "D")]
    assert (full.airport.total.cancelled, full.airport.total.flights) == (1, 3)
    assert (cut.airport.total.cancelled, cut.airport.total.flights) == (0, 1)
    assert {h: r.flights for h, r in full.airport.rows.items()} == dict.fromkeys(counting.CHECKPOINTS, 3)
    assert {h: r.flights for h, r in cut.airport.rows.items()} == dict.fromkeys(counting.CHECKPOINTS, 1)
    assert (full.airport.delay["D"].flights, cut.airport.delay["D"].flights) == (2, 1)


# --- the stop behind "It's about the same however soon you fly." ----------------------------------------

def departures(delayed: int) -> tuple[list[dict], list[dict], list[dict]]:
    """A model of 100 closed departures from 7 airlines, 28 October to 3 November, `delayed` of them an hour late,
    one in ten. Each is first listed 30 hours before its time, so it is in the rows from 24 hours down and in no 48-
    or 70-hour row."""
    table, obs = [], []
    for i in range(100):
        sched = datetime(2026, 10, 28) + i * 1.5 * H
        table.append(number(f"n{i}", sched, late=60.0 if i % 10 == 0 and i < 10 * delayed else 0.0,
                            airline=f"A{i % 7}", flight_no=str(100 + i), first_seen_at=sched - 30 * H))
        obs.append(seen(f"n{i}", 1, sched - 30 * H, sched_utc=sched))
    return table, obs, board(LAST)


def test_flat_delays():
    model_ = departures(10)
    airport = blend.records(*model_).airport
    assert (airport.delay["D"].cancelled, airport.delay["D"].flights) == (10, 100)
    assert airport.rows[24].flights == 100 and airport.rows[48].flights == 0
    blend.flat_delays(*model_, airport)  # every row at the direction's own rate
    # the 24-hour row at 10%, the direction's set 1.01 points below it, then above it: the build stops
    for k in (899, 1101):
        with pytest.raises(ValueError) as stop:
            blend.flat_delays(*model_, replace(airport, delay=airport.delay | {"D": made(k, 10000)}))
        assert "departures" in str(stop.value) and "24 hours" in str(stop.value)
    for k in (900, 1100):  # 1.00 points off: it holds
        blend.flat_delays(*model_, replace(airport, delay=airport.delay | {"D": made(k, 10000)}))
    # a row whose delayed flights are below the floor (9 of them) is not read, however far off
    thin = departures(9)
    blend.flat_delays(*thin, replace(blend.records(*thin).airport, delay={"D": made(0, 100), "A": made(0, 0)}))


# --- end to end: from rows to the two chances ----------------------------------------------------------

def test_from_rows_to_the_two_chances():
    """docs/flight-lookup.md:775, "A synthetic fixture with hand-computed chances": rows through `records` to the
    chances of LY 1, each worked out by hand below. 200 departures, one an hour from 1 November 00:00 UTC, so each is
    a flight of its own, all closed at the last sighting (12 November 00:00). Of a number's flights the first are
    cancelled, the next departed an hour late and the rest on time. Each is first listed 30 hours before its time,
    so it is in the 24-hour row; EE's are first listed 10 hours before, so they are in no 24-hour row."""
    table, obs = [], []

    def fly(airline: str, flight_no: str, n: int, cancelled: int, delayed: int, ahead: int = 30) -> None:
        for i in range(n):
            sched, fid = T(1, 0) + len(table) * H, f"{airline}{flight_no}-{i}"
            table.append(number(fid, sched, "canceled" if i < cancelled else "departed",
                                late=60.0 if cancelled <= i < cancelled + delayed else 0.0, airline=airline,
                                flight_no=flight_no, name=airline))
            obs.append(seen(fid, 1, sched - ahead * H, sched_utc=sched))

    fly("LY", "1", 6, cancelled=2, delayed=1)
    fly("LY", "2", 19, cancelled=3, delayed=4)
    for airline, cancelled in (("AA", 2), ("BB", 1), ("CC", 1), ("DD", 1)):
        fly(airline, "1", 25, cancelled, delayed=0)
    fly("EE", "1", 75, cancelled=10, delayed=13, ahead=10)
    r = blend.records(table, obs, board(T(12, 0)))

    lead, ly, airport = r.numbers[("LY", "1", "D")], r.airlines["LY"], r.airport
    assert (lead.flights, lead.cancelled, lead.flew, lead.delayed) == (6, 2, 4, 1)
    assert (ly.flights, ly.cancelled, ly.flew, ly.delayed) == (25, 5, 20, 5)
    assert (airport.total.cancelled, airport.total.flights) == (20, 200)
    # LY's 25 and AA's to DD's 100; the cancelled ones from 5 airlines on 5 days (1 to 5 November): it clears the floor
    assert (airport.rows[24].cancelled, airport.rows[24].flights, airport.rows[24].clears_floor) == (10, 125, True)
    assert (airport.delay["D"].cancelled, airport.delay["D"].flights) == (18, 180)  # LY's 5 and EE's 13 of 180 flown

    # Cancelled, 20 hours before its time (the 24-hour row):
    #   the airport: 20 / 200 = 0.1
    #   LY: (5 + 100 x 0.1) / (25 + 100) = 15 / 125 = 0.12
    #   LY 1: (2 + 14 x 0.12) / (6 + 14) = 3.68 / 20 = 0.184
    #   scaled by the 24-hour row, 10 / 125 = 0.08, over the airport's 0.1, so by 0.8: 0.184 x 0.8 = 0.1472
    assert cancel_chance(lead, ly, airport, blend.row_for(20)) == approx(0.1472)
    # Delayed an hour or more, if it flies, not scaled:
    #   the departures that flew: 18 / 180 = 0.1
    #   LY: (5 + 100 x 0.1) / (20 + 100) = 15 / 120 = 0.125
    #   LY 1: (1 + 14 x 0.125) / (4 + 14) = 2.75 / 18 = 0.152778
    assert delay_chance(lead, ly, airport, "D") == approx(0.152778)
