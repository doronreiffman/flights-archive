"""Rule C8: the grouped range, the floor and the rounding (docs/flight-lookup.md, C8; A0's `rng`, A35); and a sign's
lift and scores ("Signs"; A0b's `ratio`)."""
from datetime import date

import pytest
from pytest import approx

from timeline.rates import (LIFT_SE, Counted, Lift, Scores, lift, passes, rate, round_middle, round_range, scores, step,
                            week)


def rows(airline, day, n, k):
    return [Counted(1 if i < k else 0, airline, day) for i in range(n)]


def first_case():
    return (rows("A", date(2026, 10, 27), 10, 3) + rows("B", date(2026, 10, 27), 10, 0)
            + rows("A", date(2026, 11, 2), 10, 1) + rows("B", date(2026, 11, 2), 10, 0))


def test_the_airline_week_grouping_is_the_larger():
    r = rate(first_case())
    assert r.se_airline_week == approx(0.070711, abs=1e-6)
    assert r.se_day == approx(0.05)
    assert r.one_in == 10.0
    assert r.one_in_from == approx(2.8699, abs=1e-4)
    assert r.one_in_to == approx(44.3182, abs=1e-4)


def test_the_day_grouping_is_the_larger():
    items = (rows("A", date(2026, 10, 26), 10, 2) + rows("A", date(2026, 10, 27), 10, 0)
             + rows("B", date(2026, 10, 26), 10, 2) + rows("B", date(2026, 10, 27), 10, 0)
             + rows("C", date(2026, 10, 28), 10, 0) + rows("C", date(2026, 10, 26), 10, 0))
    r = rate(items)
    assert r.se_airline_week == approx(0.033333, abs=1e-6)
    assert r.se_day == approx(0.050918, abs=1e-6)
    assert r.one_in == 15.0
    assert r.one_in_from == approx(3.7249, abs=1e-4)
    assert r.one_in_to == approx(72.9299, abs=1e-4)


def test_weeks_start_on_sunday():
    assert week(date(2026, 10, 31)) == date(2026, 10, 25)
    assert week(date(2026, 11, 1)) == date(2026, 11, 1)


def test_the_range_never_falls_below_zero():
    assert 0.1 - 2 * 0.070711 < 0
    r = rate(first_case())
    assert 1 / r.one_in_to > 0


def spread(cancelled, airlines, days, extra_airlines=0, extra_days=0):
    items = []
    for i in range(cancelled):
        items.append(Counted(1, f"X{i % airlines}", date(2026, 10, 26 + i % days)))
    for i in range(30):  # flights not cancelled, from other airlines and days
        items.append(Counted(0, f"Z{i % 7}", date(2026, 11, 10 + i % 7)))
    return items


@pytest.mark.parametrize("cancelled, airlines, days, expected", [
    (9, 5, 5, False), (10, 5, 5, True), (11, 5, 5, True), (10, 4, 5, False), (10, 5, 4, False),
])
def test_the_floor(cancelled, airlines, days, expected):
    r = rate(spread(cancelled, airlines, days))
    assert r.clears_floor is expected
    assert r.cancelled == cancelled


def test_the_floor_counts_only_the_cancelled_flights_airlines_and_days():
    r = rate(spread(10, 4, 4))
    assert (r.airlines, r.days) == (4, 4)
    assert r.clears_floor is False


def test_no_range_at_zero_or_with_one_group():
    r = rate(rows("A", date(2026, 10, 26), 5, 0) + rows("B", date(2026, 10, 27), 5, 0))
    assert r.one_in is None and r.one_in_from is None and r.one_in_to is None
    one_day = rate(rows("A", date(2026, 10, 26), 5, 1) + rows("B", date(2026, 10, 26), 5, 0))
    assert one_day.one_in == 10.0
    assert one_day.one_in_from is None and one_day.one_in_to is None and one_day.se_day is None
    one_group = rate(rows("A", date(2026, 10, 26), 5, 1) + rows("A", date(2026, 10, 27), 5, 0))  # one airline, one week
    assert one_group.one_in == 10.0
    assert one_group.se_airline_week is None and one_group.one_in_from is None and one_group.one_in_to is None
    everything = rate(rows("A", date(2026, 10, 26), 3, 3) + rows("B", date(2026, 10, 27), 3, 3))
    assert everything.one_in == 1.0 and everything.one_in_from is None


@pytest.mark.parametrize("x, expected", [
    (19.4, 19), (19.5, 20), (22.4, 20), (22.5, 25), (57.5, 60), (97.5, 100), (98.5, 100), (104.9, 100),
    (105, 110), (145.0, 150), (994.9, 990), (995, 1000), (1049, 1000), (1050, 1100),
])
def test_the_middle_to_the_nearest_step_halves_up(x, expected):
    assert round_middle(x) == expected


def test_the_steps():
    assert [step(x) for x in (1, 19.9, 20, 99.9, 100, 999.9, 1000, 5000)] == [1, 1, 5, 5, 10, 10, 100, 100]


@pytest.mark.parametrize("lo, hi, expected", [
    (33.2, 120.6, (30, 130)), (36.3, 91.6, (35, 95)), (119.9922, 459.6909, (110, 460)), (120.0, 459.7, (120, 460)),
    (19.9, 20.1, (19, 25)), (999.5, 1000.5, (990, 1100)),
])
def test_the_ends_round_outward_each_by_its_own_step(lo, hi, expected):
    assert round_range(lo, hi) == expected


@pytest.mark.parametrize("one_in, lo, hi, printed", [
    (57.5062, 36.2607, 91.5526, (60, 35, 95)), (63.0833, 33.2345, 120.5719, (65, 30, 130)),
    (70.5532, 38.1063, 131.3727, (70, 35, 140)), (98.5429, 49.3213, 197.9028, (100, 45, 200)),
    (145.0, 71.3918, 295.5799, (150, 70, 300)), (194.9474, 96.6079, 394.4358, (190, 95, 400)),
    (234.625, 119.9922, 459.6909, (230, 110, 460)),
])
def test_the_real_rows_print_by_c8(one_in, lo, hi, printed):
    low, high = round_range(lo, hi)
    assert (round_middle(one_in), low, high) == printed


# --- the sign test and its score (docs/flight-lookup.md, "Signs"; A0b's `ratio`) -----------------------------

def hand_case() -> tuple[list[Counted], list[Counted]]:
    """Airlines A to E in the week of 1 November 2026, airline i on 2026-11-0(2+i): (flights, cancelled) with the sign,
    and without it."""
    with_ = {"A": (5, 3), "B": (4, 2), "C": (6, 2), "D": (3, 2), "E": (5, 1)}
    without = {"A": (100, 1), "B": (120, 2), "C": (90, 0), "D": (110, 1), "E": (80, 2)}

    def flights(of):
        return [c for i, (airline, (n, k)) in enumerate(of.items()) for c in rows(airline, date(2026, 11, 2 + i), n, k)]
    return flights(with_), flights(without)


def test_the_lift_hand_case():
    # checked against A0b's `ratio` on the same rows: 36.2 times, 13.1 to 99.9, passes
    got = lift(*hand_case())
    assert (got.cancelled_with, got.flights_with, got.cancelled_without, got.flights_without) == (10, 23, 6, 500)
    assert (got.airlines, got.days, got.clears_floor) == (5, 5, True)
    assert got.times == approx(36.2319, abs=1e-4)
    assert got.se_log == approx(0.405866, abs=1e-6)
    assert got.times_from == approx(13.1349, abs=1e-4)
    assert got.times_to == approx(99.9434, abs=1e-4)
    assert got.passes is True
    assert LIFT_SE == 2.5


def test_scores_hand_case():
    got = scores(*hand_case())
    assert got.one_rate == approx(0.029657, abs=1e-6)  # r(1 - r), as A33 has it
    assert got.split == approx(0.022142, abs=1e-6)
    assert got.gain == approx(got.one_rate - got.split, abs=1e-15)
    # computed apart from this code (scripts/scores_oracle.py): the per-flight gain's grouped standard error is
    # 0.00238809 by airline and week and by day alike (here both make the same five groups); the gain is 0.00751499
    assert got.gain_from == approx(0.00273881, abs=1e-8)
    assert got.gain_to == approx(0.01229118, abs=1e-8)


def test_a_range_that_touches_1_fails():
    assert passes(True, 1.0) is False
    assert passes(True, 1.000001) is True
    assert passes(False, 5.0) is False
    assert passes(True, None) is False


def test_the_floor_for_a_sign():
    with_, without = hand_case()
    nine = with_[1:]  # one of A's three cancelled flights left out: 9 cancelled, still from 5 airlines on 5 days
    got = lift(nine, without)
    assert (got.cancelled_with, got.airlines, got.days) == (9, 5, 5)
    assert got.clears_floor is False
    assert got.times is None and got.times_from is None and got.times_to is None
    assert got.passes is False
    assert got.se_log is not None  # the range could be computed: only the floor holds it back


def test_a_sign_with_no_cancelled_flight_without_it_has_no_ratio():
    # 10 cancelled with the sign, from 5 airlines on 5 days, clear the floor; none without it: no ratio, no pass
    days = [date(2026, 11, 2 + i) for i in range(5)]
    with_ = [c for a, d in zip("ABCDE", days) for c in rows(a, d, 4, 2)]
    without = [c for a, d in zip("ABCDE", days) for c in rows(a, d, 10, 0)]
    got = lift(with_, without)
    assert (got.clears_floor, got.times, got.times_from, got.times_to, got.passes) == (True, None, None, None, False)
    assert lift(with_, []).passes is False


def test_no_flights_no_figure():
    # before any counted flight is read, and for a sign no flight carries
    assert lift([], []) == Lift(0, 0, 0, 0, 0, 0, False, None, None, None, None, False)
    assert scores([], []) == Scores(None, None, None, None, None)
    _, without = hand_case()
    none_with = lift([], without)
    assert (none_with.flights_with, none_with.cancelled_without, none_with.se_log) == (0, 6, None)
    assert none_with.passes is False
    alone = scores([], without)  # no split: the one rate is the without set's own
    assert alone.split == approx(alone.one_rate) and alone.gain == 0 and alone.gain_from == alone.gain_to == 0
    # one airline on one day is one group in each grouping: no standard error, so no range
    one_group = (rows("A", date(2026, 11, 2), 4, 2), rows("A", date(2026, 11, 2), 8, 1))
    assert lift(*one_group).se_log is None
    assert scores(*one_group).gain_from is None and scores(*one_group).gain_to is None


def test_a_ratio_above_1_whose_range_reaches_below_it_fails():
    # clears the floor (10 cancelled with the sign, from 5 airlines on 5 days) at 1.5 times the rate, but its range
    # runs from 0.36 to 6.24 (computed apart from this code: scripts/scores_oracle.py): the range decides
    days = [date(2026, 11, 2 + i) for i in range(5)]
    with_ = [c for a, d, k in zip("ABCDE", days, (4, 1, 2, 2, 1)) for c in rows(a, d, 20, k)]
    without = [c for a, d, k in zip("ABCDE", days, (0, 2, 1, 1, 1)) for c in rows(a, d, 15, k)]
    got = lift(with_, without)
    assert got.clears_floor is True and got.times == approx(1.5)
    assert got.times_from == approx(0.360684, abs=1e-6) and got.times_to == approx(6.238155, abs=1e-6)
    assert got.passes is False


def test_the_larger_grouping_is_used():
    # two airlines on two days of one week: by airline and week the groups are A and B, by day 2 and 3 November. The
    # log ratio's standard error is 0.1 by airline and 0.7 by day; the mean gain's is 0.0118490 by airline and
    # 0.0063802 by day (computed apart from this code: scripts/scores_oracle.py). Each takes the larger.
    d1, d2 = date(2026, 11, 2), date(2026, 11, 3)
    with_ = rows("A", d1, 4, 3) + rows("B", d1, 4, 0) + rows("A", d2, 4, 1) + rows("B", d2, 4, 1)
    without = rows("A", d1, 20, 1) + rows("B", d1, 20, 0) + rows("A", d2, 20, 2) + rows("B", d2, 20, 1)
    assert lift(with_, without).se_log == approx(0.7)
    got = scores(with_, without)
    assert got.gain == approx(0.0095703125)
    assert got.gain_from == approx(-0.014127604, abs=1e-8) and got.gain_to == approx(0.033268229, abs=1e-8)
