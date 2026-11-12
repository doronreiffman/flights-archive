"""A rate's range, the floor below which none is shown, and the rounding (docs/flight-lookup.md, C8;
docs/flight-lookup-figures.md, A0's `rng` and A35).

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no timeline module but the
frozen ones (tests/test_frozen.py). Pure functions over the flights of one set.

A rate is cancelled flights over flights. Flights are grouped twice, by (airline, week) and by day; each group is one
draw, and the larger of the two standard errors is used. The ends are two standard errors either side on the
log-odds scale, so a range never falls below zero. "1 in N" is shown to the step `step` gives; the middle goes to the
nearest step, halves up; the ends round outward.

A sign's lift and its scores ("Signs"; A0b's `ratio`) use the same two groupings, and the floor on the flights with
the sign.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

FLOOR_CANCELLED, FLOOR_AIRLINES, FLOOR_DAYS = 10, 5, 5  # C8: a rate shows only with at least this many of each


@dataclass(frozen=True)
class Counted:
    """One flight in a set a rate is taken over: k is 1 if it was listed as cancelled, else 0."""
    k: int
    airline: str  # the grouping airline (C8): never shown
    day: date  # the Israel day


def week(day: date) -> date:
    """The Sunday on or before `day` (weeks start on Sunday, as in Israel)."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def grouped_se(items: Sequence[Counted], key: Callable[[Counted], Hashable]) -> float:
    """sqrt(G / (G - 1) * sum_g (k_g - r * n_g) ** 2) / N over the groups `key` makes; G must be 2 or more."""
    total = sum(i.k for i in items)
    n_all = len(items)
    r = total / n_all
    ks: dict[Hashable, int] = {}
    ns: dict[Hashable, int] = {}
    for i in items:
        g = key(i)
        ks[g] = ks.get(g, 0) + i.k
        ns[g] = ns.get(g, 0) + 1
    groups = len(ks)
    squares = math.fsum((ks[g] - r * ns[g]) ** 2 for g in sorted(ks))
    return math.sqrt(groups / (groups - 1) * squares) / n_all


@dataclass(frozen=True)
class Rate:
    cancelled: int
    flights: int
    airlines: int  # among the cancelled flights only
    days: int  # among the cancelled flights only
    clears_floor: bool
    one_in: float | None  # flights / cancelled; None at 0
    one_in_from: float | None  # the ends as "1 in": from is the higher rate's end
    one_in_to: float | None
    se_airline_week: float | None
    se_day: float | None


def rate(items: Sequence[Counted]) -> Rate:
    """The rate of a set, its floor test and, when 0 < K < N and each grouping has 2 or more groups, its range."""
    n_all = len(items)
    cancelled = sum(i.k for i in items)
    airlines = len({i.airline for i in items if i.k})
    days = len({i.day for i in items if i.k})
    clears = cancelled >= FLOOR_CANCELLED and airlines >= FLOOR_AIRLINES and days >= FLOOR_DAYS
    one_in = n_all / cancelled if cancelled else None
    se_aw = se_d = lo = hi = None
    if 0 < cancelled < n_all:
        r = cancelled / n_all
        if len({(i.airline, week(i.day)) for i in items}) >= 2:
            se_aw = grouped_se(items, lambda i: (i.airline, week(i.day)))
        if len({i.day for i in items}) >= 2:
            se_d = grouped_se(items, lambda i: i.day)
        if se_aw is not None and se_d is not None:
            half = 2 * max(se_aw, se_d) / (r * (1 - r))
            logit = math.log(r / (1 - r))
            hi = 1 / (1 / (1 + math.exp(-(logit + half))))
            lo = 1 / (1 / (1 + math.exp(-(logit - half))))
    return Rate(cancelled, n_all, airlines, days, clears, one_in, hi, lo, se_aw, se_d)


LIFT_SE = 2.5  # "Signs": a lift's range is this many standard errors of its logarithm either side (four signs at once)


@dataclass(frozen=True)
class Lift:
    """A sign's test ("Signs"; A0b's `ratio`): the rate with the sign over the rate without it, its range and whether
    it passes."""
    cancelled_with: int
    flights_with: int
    cancelled_without: int
    flights_without: int
    airlines: int  # among the cancelled flights with the sign only
    days: int  # among the cancelled flights with the sign only
    clears_floor: bool  # C8's floor, for the flights with the sign
    times: float | None  # how many times the rate; None below the floor
    times_from: float | None
    times_to: float | None
    se_log: float | None  # the grouped standard error of the ratio's logarithm (the larger of C8's two groupings)
    passes: bool


def _se_log(with_: Sequence[Counted], without: Sequence[Counted], key: Callable[[Counted], Hashable]) -> float | None:
    """A0b's `se` for one grouping: sqrt(G / (G - 1) * sum_g ((k1_g - k1 / n1 * n1_g) / k1 - (k0_g - k0 / n0 * n0_g)
    / k0) ** 2) over the G groups `key` makes of both sets; k1 and k0 must not be 0. None below 2 groups, where A0b's
    gives NaN."""
    k1, n1, k0, n0 = sum(i.k for i in with_), len(with_), sum(i.k for i in without), len(without)
    by: dict[Hashable, list[int]] = {}
    for at, items in ((0, with_), (2, without)):
        for i in items:
            g = by.setdefault(key(i), [0, 0, 0, 0])
            g[at] += i.k
            g[at + 1] += 1
    if len(by) < 2:
        return None
    spread = math.fsum(((a - k1 / n1 * b) / k1 - (c - k0 / n0 * d) / k0) ** 2
                       for a, b, c, d in (by[g] for g in sorted(by)))
    return math.sqrt(len(by) / (len(by) - 1) * spread)


def passes(clears_floor: bool, lower: float | None) -> bool:
    """A sign passes when it clears the floor and its whole range lies above 1 ("Signs"): a range that touches 1
    fails."""
    return clears_floor and lower is not None and lower > 1


def lift(with_: Sequence[Counted], without: Sequence[Counted]) -> Lift:
    """A sign's lift over the flights with it and without it (A0b's `ratio`). The floor is C8's, on the flights with
    the sign. How many times the rate, and its range, only when they clear it: LIFT_SE standard errors of the ratio's
    logarithm either side, grouped as in C8 (by airline and week, and by day; the larger)."""
    w = rate(with_)
    k0, n0 = sum(i.k for i in without), len(without)
    se_log = times = lo = hi = None
    if w.cancelled and k0:
        found = [_se_log(with_, without, lambda i: (i.airline, week(i.day))), _se_log(with_, without, lambda i: i.day)]
        if None not in found:
            se_log = max(found)
    clears = w.clears_floor
    if clears and k0:
        times = (w.cancelled / w.flights) / (k0 / n0)
        if se_log is not None:
            lo, hi = times * math.exp(-LIFT_SE * se_log), times * math.exp(LIFT_SE * se_log)
    return Lift(w.cancelled, w.flights, k0, n0, w.airlines, w.days, clears, times, lo, hi, se_log, passes(clears, lo))


@dataclass(frozen=True)
class Scores:
    """The score with and without a sign ("Signs"; not a pass mark, D3): the Brier score, in sample, of the row's one
    rate and of the two rates the sign splits it into, and the mean per-flight gain with its range. None for no
    flights."""
    one_rate: float | None
    split: float | None
    gain: float | None  # the one rate's squared error minus the split's, averaged over the flights
    gain_from: float | None  # the gain -/+ 2 grouped standard errors of it (Question 1)
    gain_to: float | None


def _se_of_mean(values: Sequence[tuple[Hashable, float]]) -> float | None:
    """C8's grouped standard error of the mean of a value per flight, over (group, value) pairs: sqrt(G / (G - 1) *
    sum_g (y_g - m * n_g) ** 2) / N, y_g the group's sum and m the mean. None below 2 groups."""
    of: dict[Hashable, list[float]] = {}
    for g, v in values:
        of.setdefault(g, []).append(v)
    if len(of) < 2:
        return None
    m = math.fsum(v for _, v in values) / len(values)
    spread = math.fsum((math.fsum(of[g]) - m * len(of[g])) ** 2 for g in sorted(of))
    return math.sqrt(len(of) / (len(of) - 1) * spread) / len(values)


def scores(with_: Sequence[Counted], without: Sequence[Counted]) -> Scores:
    """The Brier scores of the one rate and of the split over the flights with and without a sign, and the gain's
    range: 2 grouped standard errors of the mean gain either side, grouped as in C8 (the larger)."""
    n = len(with_) + len(without)
    if not n:
        return Scores(None, None, None, None, None)
    one = (sum(i.k for i in with_) + sum(i.k for i in without)) / n
    rated: list[tuple[Counted, float]] = []  # each flight with the rate of its half
    for side in (with_, without):
        if side:
            half = sum(i.k for i in side) / len(side)
            rated += [(i, half) for i in side]
    errors = [((one - i.k) ** 2, (own - i.k) ** 2) for i, own in rated]
    gains = [(i, a - b) for (i, _), (a, b) in zip(rated, errors)]
    gain = math.fsum(g for _, g in gains) / n
    found = [_se_of_mean([((i.airline, week(i.day)), g) for i, g in gains]),
             _se_of_mean([(i.day, g) for i, g in gains])]
    se = max(found) if None not in found else None
    return Scores(math.fsum(a for a, _ in errors) / n, math.fsum(b for _, b in errors) / n, gain,
                  None if se is None else gain - 2 * se, None if se is None else gain + 2 * se)


def step(x: float) -> int:
    """The step "1 in N" is shown to: 1 below 20, 5 below 100, 10 below 1000, else 100."""
    if x < 20:
        return 1
    if x < 100:
        return 5
    if x < 1000:
        return 10
    return 100


def round_middle(x: float) -> int:
    """The nearest step, halves up."""
    s = step(x)
    return math.floor(x / s + 0.5) * s


def round_range(lo: float, hi: float) -> tuple[int, int]:
    """The ends of a range, outward: lo down and hi up, each by its own step."""
    return math.floor(lo / step(lo)) * step(lo), math.ceil(hi / step(hi)) * step(hi)
