"""Rule C8: the grouped range, the floor and the rounding (docs/flight-lookup.md, C8; A0's `rng`, A35)."""
from datetime import date

import pytest
from pytest import approx

from timeline.rates import Counted, rate, round_middle, round_range, step, week


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
