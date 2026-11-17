"""The blend (docs/flight-lookup.md, "The blend", D12; "Left to the builder"): a flight page's two chances, that the
flight is cancelled and that it is delayed an hour or more, from three records: its flight number's, its airline's
and the whole airport's. A first version, to be replaced in the same slot by a tested model (q28).

Not part of the frozen rule: it reads the frozen modules' flights, results and figures (counting, rates) and C10's
label (display), and changes nothing in them; no frozen module may import it (tests/test_frozen.py). Its counts are
new measurements. A number's and an airline's count each flight whose ending is known, C10's label DEPARTED, LANDED
or CANCELLED, so that a chance is worked out from the counts its page shows. The airport's rate and rows stay the
frozen total and rows, the figures the front page shows. Pure functions over the rows `timeline.load.load` returns;
model times are naive UTC; no random numbers and no clock.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from . import counting, display, rates
from .words import CANCELLED, DEPARTED, LANDED

NUMBER_WEIGHT = 14     # docs/flight-lookup.md:301
AIRLINE_WEIGHT = 100
# (after, upto, checkpoint): a time left in hours above `after`, up to `upto`, takes that checkpoint's row, the
# nearest at or above it; the 70-hour row above 48 hours
STRETCHES = ((48, 72, 70), (24, 48, 48), (12, 24, 24), (6, 12, 12), (3, 6, 6), (0, 3, 3))
BAD_WEEK_DAYS = 6      # the first and last cancelled day at most this far apart
_DIRECTIONS = {"D": "departures", "A": "arrivals"}  # the keys of Airport.delay

Key = tuple[str, str, str]   # airline, flight_no, direction: one flight page


@dataclass(frozen=True)
class Tally:
    """One record's counts, over the flights whose ending is known (C10 label)."""
    flights: int
    cancelled: int
    flew: int  # DEPARTED or LANDED
    delayed: int  # of those that flew, any departed or landed number delayed_an_hour
    cancelled_days: tuple[date, ...]  # Israel days (Flight.day) of the cancelled flights, sorted
    last_cancelled: datetime | None  # the latest cancelled flight's sched_utc_final


@dataclass(frozen=True)
class Airport:
    total: rates.Rate  # counting.Figures.total
    rows: dict[int, rates.Rate]  # counting.Figures.rows
    delay: dict[str, rates.Rate]  # "D", "A": closed flights with a known result that flew, k = delayed


@dataclass(frozen=True)
class Records:
    numbers: dict[Key, Tally]  # every number and direction of the table
    airlines: dict[str, Tally]  # by C8's grouping airline (Flight.airline), every one some flight has
    airport: Airport
    published: dict[str, str]  # airline code -> the airline_name of its latest row


EMPTY = Tally(0, 0, 0, 0, (), None)


def known(label: str) -> bool:
    """A flight whose ending is known: C10's label DEPARTED, LANDED or CANCELLED. A flight with a number still
    listed is not, even with another marked cancelled (C10's rule 2), nor one that left with no final word."""
    return label in (DEPARTED, LANDED, CANCELLED)


def _delayed(f: counting.Flight, by_id: dict[str, dict]) -> bool:
    """Delayed an hour or more, read from its numbers that departed or landed (the delay measurement's reading)."""
    return any(display.delayed_an_hour(by_id[fid]) for fid in f.numbers
               if by_id[fid]["outcome"] in counting.OPERATED)


def _tally(flights_: Iterable[counting.Flight], by_id: dict[str, dict], last: datetime) -> Tally:
    """The counts of `flights_`, each labelled by C10 as of `last`: a flight that flew under any of its numbers
    counts as flown for every one of them (C2)."""
    ended = [(f, lab) for f in flights_ if known(lab := display.label(f, by_id, last))]
    cancelled = [f for f, lab in ended if lab == CANCELLED]
    flew = [f for f, lab in ended if lab in (DEPARTED, LANDED)]
    return Tally(flights=len(ended), cancelled=len(cancelled), flew=len(flew),
                 delayed=sum(_delayed(f, by_id) for f in flew),
                 cancelled_days=tuple(sorted(f.day for f in cancelled)),
                 last_cancelled=max((f.key[2] for f in cancelled), default=None))


def _delay_rate(flights_: Iterable[counting.Flight], by_id: dict[str, dict], direction: str) -> rates.Rate:
    """The closed flights of `direction` with a known result that flew, as one rate whose k is a delay of an hour
    or more: C8's floor then reads the delayed flights."""
    return rates.rate([rates.Counted(int(_delayed(f, by_id)), f.airline, f.day) for f in flights_
                       if f.closed and f.result == "operated" and f.key[0] == direction])


def records(table: list[dict], obs: list[dict], snaps: list[dict], before: datetime | None = None) -> Records:
    """Each number's, each airline's and the airport's records on the model `load` returns, labelled as of its last
    sighting. With `before`, the back-test's cut: a number's and an airline's counts hold only flights scheduled
    before it, and the airport's total, rows and delays are those of the flights closed as of it
    (counting.flights(table, before)); every result is the full model's."""
    last = counting.last_sighting(snaps)
    flights_ = counting.flights(table, last)
    by_id = {r["flight_id"]: r for r in table}
    of = counting.flight_of([f for f in flights_ if before is None or f.key[2] < before])
    per_number: dict[Key, dict[tuple, counting.Flight]] = {}
    per_airline: dict[str, dict[tuple, counting.Flight]] = {f.airline: {} for f in flights_}
    for r in table:
        own = per_number.setdefault((r["airline"], r["flight_no"], r["direction"]), {})
        if r["flight_id"] in of:
            f = of[r["flight_id"]]
            own[f.key] = f
            per_airline[f.airline][f.key] = f
    if before is None:
        figures, as_of = counting.figures(table, obs, snaps), flights_
    else:  # counting.figures, as of `before`
        as_of = counting.flights(table, before)
        in_rows = counting.cells(as_of, counting.passings(counting.stretches(table, obs), counting.holes(snaps)))
        figures = counting.Figures(
            total=rates.rate([counting.counted(f) for f in as_of if f.closed and f.result != "unknown"]),
            rows=tuple((h, rates.rate([counting.counted(c.flight) for c in in_rows if c.h == h]))
                       for h in counting.CHECKPOINTS))
    airport = Airport(total=figures.total, rows=dict(figures.rows),
                      delay={d: _delay_rate(as_of, by_id, d) for d in _DIRECTIONS})
    published = {r["airline"]: r["airline_name"] for r in sorted(table, key=lambda r: (r["sched_utc_final"],
                                                                                         r["flight_id"]))}
    return Records(numbers={k: _tally(per_number[k].values(), by_id, last) for k in sorted(per_number)},
                   airlines={a: _tally(per_airline[a].values(), by_id, last) for a in sorted(per_airline)},
                   airport=airport, published=dict(sorted(published.items())))


def pull(k: int, n: int, toward: float, weight: int) -> float:
    """k of n, pulled towards the rate `toward` as if there were `weight` more flights at it."""
    return (k + weight * toward) / (n + weight)


def row_for(hours_left: float | None) -> int:
    """The checkpoint whose row scales a chance with `hours_left` hours left (STRETCHES); the 70-hour row above 48
    hours and for a page with no flight ahead (None), the 3-hour row at 3 hours or less."""
    if hours_left is None:
        return STRETCHES[0][2]
    for after, _, checkpoint in STRETCHES:
        if hours_left > after:
            return checkpoint
    return STRETCHES[-1][2]


def _share(r: rates.Rate) -> float:
    return r.cancelled / r.flights


def scaling(airport: Airport, h: int) -> float | None:
    """The time-left curve's factor for checkpoint h: the row's rate over the total's. A row below C8's floor gives
    way to the nearest that clears it, trying first the checkpoints with more time left, nearest first, then those
    with less; None when no row clears, and the chance is unscaled."""
    tried = [h, *sorted(c for c in airport.rows if c > h), *sorted((c for c in airport.rows if c < h), reverse=True)]
    for c in tried:
        if airport.rows[c].clears_floor:
            return _share(airport.rows[c]) / _share(airport.total)
    return None


def cancel_chance(number: Tally, airline: Tally, airport: Airport, h: int) -> float:
    """The rule's four steps: the airport's rate; the airline's, pulled towards it; the number's, pulled towards
    the airline's; scaled by checkpoint h's factor. Above zero while the airport has a cancelled flight."""
    airline_rate = pull(airline.cancelled, airline.flights, _share(airport.total), AIRLINE_WEIGHT)
    chance = pull(number.cancelled, number.flights, airline_rate, NUMBER_WEIGHT)
    factor = scaling(airport, h)
    return chance if factor is None else chance * factor


def delay_chance(number: Tally, airline: Tally, airport: Airport, direction: str) -> float:
    """Steps 1 to 3 for a delay of an hour or more, over flights that flew: the airport's rate is the direction's
    own, and the airline's counts cover both directions. Not scaled: delays are flat across the time left
    (`flat_delays`)."""
    airline_rate = pull(airline.delayed, airline.flew, _share(airport.delay[direction]), AIRLINE_WEIGHT)
    return pull(number.delayed, number.flew, airline_rate, NUMBER_WEIGHT)


def bad_week(t: Tally) -> tuple[date, date] | None:
    """The first and last Israel days of a record's cancelled flights, when there are two or more and they fall
    within 7 calendar days; else None."""
    days = t.cancelled_days
    if len(days) >= 2 and (days[-1] - days[0]).days <= BAD_WEEK_DAYS:
        return days[0], days[-1]
    return None


def lead(f: counting.Flight, by_id: dict[str, dict]) -> dict:
    """C8's grouping number of a flight: its number first in C8's order, whose airline is Flight.airline."""
    return min((by_id[fid] for fid in f.numbers), key=counting._number_order)


def flat_delays(table: list[dict], obs: list[dict], snaps: list[dict], airport: Airport) -> None:
    """The stop behind "It's about the same however soon you fly.": ValueError when a row's delay rate, for
    departures or arrivals, is more than one percentage point from the direction's own rate in `airport`. Only rows
    whose delayed flights clear C8's floor are read; on fewer, a row differs by chance."""
    flights_ = counting.flights(table, counting.last_sighting(snaps))
    by_id = {r["flight_id"]: r for r in table}
    in_rows = counting.cells(flights_, counting.passings(counting.stretches(table, obs), counting.holes(snaps)))
    for direction, name in _DIRECTIONS.items():
        whole = airport.delay[direction]
        for h in counting.CHECKPOINTS:
            row = _delay_rate([c.flight for c in in_rows if c.h == h], by_id, direction)
            # |row.k / row.n - whole.k / whole.n| > 1/100, in integers, so that exactly one point passes
            if row.clears_floor and 100 * abs(row.cancelled * whole.flights - whole.cancelled * row.flights) > (
                    row.flights * whole.flights):
                raise ValueError(
                    f"delays of an hour or more: {name} in the {h} hours row, {row.cancelled} of {row.flights} "
                    f"({_share(row):.2%}), are more than one point from all {name}, {whole.cancelled} of "
                    f"{whole.flights} ({_share(whole):.2%}): \"It's about the same however soon you fly.\" no "
                    "longer holds")
