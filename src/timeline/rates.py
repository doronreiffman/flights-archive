"""A rate's range, the floor below which none is shown, and the rounding (docs/flight-lookup.md, C8;
docs/flight-lookup-figures.md, A0's `rng` and A35).

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no timeline module but the
frozen ones (tests/test_frozen.py). Pure functions over the flights of one set.

A rate is cancelled flights over flights. Flights are grouped twice, by (airline, week) and by day; each group is one
draw, and the larger of the two standard errors is used. The ends are two standard errors either side on the
log-odds scale, so a range never falls below zero. "1 in N" is shown to the step `step` gives; the middle goes to the
nearest step, halves up; the ends round outward.
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
