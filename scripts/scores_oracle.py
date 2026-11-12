"""The sign test's lift and score for the hand cases of tests/test_rates.py, outside the code under test: the source of
the literals in test_the_lift_hand_case, test_scores_hand_case, test_a_ratio_above_1_whose_range_reaches_below_it_fails
and test_the_larger_grouping_is_used. Not run in CI. Run from the repository root:

    .venv/bin/python scripts/scores_oracle.py

The lift is A0b's `ratio` (docs/flight-lookup-figures.md): the rate with the sign over the rate without it, and its
range, 2.5 grouped standard errors of the ratio's logarithm either side. The score has no SQL; it follows the plan's
Question 1 as answered (docs/flight-lookup-plan.md, "Questions for the owner"): the Brier score of the one rate and
of the split, the per-flight gain (the one rate's squared error minus the split's) averaged, and its range, 2 grouped
standard errors of that mean either side. Both standard errors are grouped as rule C8 groups flights
(docs/flight-lookup.md): by airline and week (weeks start on Sunday) and by day, the larger of the two. Every sum is
an exact fraction; only the square roots and the exponentials are floats. It imports nothing from src/: each case is
written out as rows of (airline, day, flights, cancelled), with the sign and without it.
"""
from datetime import date, timedelta
from fractions import Fraction
from math import exp, sqrt

LIFT_SE, GAIN_SE = 2.5, 2


def week(day: date) -> date:
    """The Sunday on or before `day`."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


GROUPINGS = {"airline and week": lambda airline, day: (airline, week(day)), "day": lambda airline, day: day}


def flights(rows: list[tuple[str, date, int, int]]) -> list[tuple[str, date, int]]:
    """(airline, day, k) for each flight of the rows, k 1 for a cancelled one."""
    return [(airline, day, int(i < k)) for airline, day, n, k in rows for i in range(n)]


def grouped(values: dict) -> float:
    """sqrt(G / (G - 1) * the sum of each group's value squared), over the G groups that are `values`' keys."""
    n_groups = len(values)
    return sqrt(Fraction(n_groups, n_groups - 1) * sum(v * v for v in values.values()))


def lift(with_: list, without: list) -> dict:
    """A0b's `ratio` for one sign: the counts, the floor, how many times the rate, the log ratio's standard error by
    each grouping and the larger, the range and the pass mark."""
    k1, n1 = sum(k for _, _, k in with_), len(with_)
    k0, n0 = sum(k for _, _, k in without), len(without)
    times = Fraction(k1, n1) / Fraction(k0, n0)
    se = {}
    for name, key in GROUPINGS.items():
        groups: dict = {}
        for flights_, at in ((with_, 0), (without, 2)):
            for airline, day, k in flights_:
                g = groups.setdefault(key(airline, day), [0, 0, 0, 0])
                g[at] += k
                g[at + 1] += 1
        se[name] = grouped({g: (a - Fraction(k1, n1) * b) / k1 - (c - Fraction(k0, n0) * d) / k0
                            for g, (a, b, c, d) in groups.items()})
    se_log = max(se.values())
    lo, hi = float(times) * exp(-LIFT_SE * se_log), float(times) * exp(LIFT_SE * se_log)
    airlines = len({airline for airline, _, k in with_ if k})
    days = len({day for _, day, k in with_ if k})
    clears = k1 >= 10 and airlines >= 5 and days >= 5
    return {"cancelled with": k1, "flights with": n1, "cancelled without": k0, "flights without": n0,
            "airlines": airlines, "days": days, "clears the floor": clears, "times": float(times),
            **{f"log ratio's standard error by {name}": v for name, v in se.items()}, "the larger": se_log,
            "from": lo, "to": hi, "passes": clears and lo > 1}


def scores(with_: list, without: list) -> dict:
    """The Brier scores of the one rate and of the split, the mean gain, its standard error by each grouping and the
    larger, and its range."""
    # each flight with the rate of its half of the split
    everyone = [(f, Fraction(sum(k for _, _, k in side), len(side))) for side in (with_, without) for f in side]
    n = len(everyone)
    one = Fraction(sum(k for (_, _, k), _ in everyone), n)
    gains = [((one - k) ** 2 - (half - k) ** 2, airline, day) for (airline, day, k), half in everyone]
    gain = sum(g for g, _, _ in gains) / n
    se = {}
    for name, key in GROUPINGS.items():
        groups: dict = {}
        for g, airline, day in gains:
            y, m = groups.get(key(airline, day), (Fraction(0), 0))
            groups[key(airline, day)] = (y + g, m + 1)
        se[name] = grouped({g: y - gain * m for g, (y, m) in groups.items()}) / n
    larger = max(se.values())
    return {"one rate": float(sum((one - k) ** 2 for (_, _, k), _ in everyone) / n),
            "split": float(sum((half - k) ** 2 for (_, _, k), half in everyone) / n),
            "gain": float(gain), **{f"gain's standard error by {name}": v for name, v in se.items()},
            "the larger": larger, "from": float(gain) - GAIN_SE * larger, "to": float(gain) + GAIN_SE * larger}


def show(title: str, with_rows: list, without_rows: list) -> None:
    with_, without = flights(with_rows), flights(without_rows)
    print(f"-- {title}")
    for part, values in (("lift", lift(with_, without)), ("score", scores(with_, without))):
        print(f"{part}: " + "; ".join(f"{name} {value:.10g}" if isinstance(value, float) else f"{name} {value}"
                                      for name, value in values.items()))


def day(i: int) -> date:
    return date(2026, 11, 2 + i)


if __name__ == "__main__":
    # test_the_lift_hand_case and test_scores_hand_case: airline i on 2026-11-0(2+i), one week
    show("the hand case",
         [(a, day(i), n, k) for i, (a, n, k) in enumerate((("A", 5, 3), ("B", 4, 2), ("C", 6, 2), ("D", 3, 2),
                                                           ("E", 5, 1)))],
         [(a, day(i), n, k) for i, (a, n, k) in enumerate((("A", 100, 1), ("B", 120, 2), ("C", 90, 0), ("D", 110, 1),
                                                           ("E", 80, 2)))])
    # test_a_ratio_above_1_whose_range_reaches_below_it_fails
    show("a ratio above 1 whose range reaches below it",
         [(a, day(i), 20, k) for i, (a, k) in enumerate(zip("ABCDE", (4, 1, 2, 2, 1)))],
         [(a, day(i), 15, k) for i, (a, k) in enumerate(zip("ABCDE", (0, 2, 1, 1, 1)))])
    # test_the_larger_grouping_is_used: two airlines on two days of one week
    show("the larger grouping",
         [("A", day(0), 4, 3), ("B", day(0), 4, 0), ("A", day(1), 4, 1), ("B", day(1), 4, 1)],
         [("A", day(0), 20, 1), ("B", day(0), 20, 0), ("A", day(1), 20, 2), ("B", day(1), 20, 1)])
