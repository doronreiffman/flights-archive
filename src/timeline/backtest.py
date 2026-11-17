"""The back-test of the blend (docs/flight-lookup.md, "Before it ships: the back-test", :882 and D13; the plan's "What
this plan decided", the back-test): before the blend ships, it predicts the last closed week of flights from the
weeks before it, and the prediction is compared with what happened.

    PYTHONPATH=src .venv/bin/python -m timeline.backtest --model data/model-<date>

The week is the 7 Israel days ending with the latest day whose flights are all closed at the last sighting. Its
scored flights are its closed flights with a known result in the 24-hour row (C5 to C7), each through C8's lead
number, its chances on the 24-hour row. The blend's counts are cut at the week's start (blend.records' `before`): a
number's and an airline's from flights scheduled before it, the airport's from the flights closed as of it; their
results are the full model's, a stated leak of at most the results that came in after the start. A flight whose
chance is None (blend: an empty base) is not scored, and the report counts it on a line of its own. The delay is
scored over the flights that flew, as its chance is that of a delay if the flight flies.

The report goes to the owner, flagged by FLAGS; no pass mark is frozen (D13), and its numbers are never published on
the site. Not part of the frozen rule: it reads the frozen modules and the blend and changes nothing in them. Model
times are naive UTC; no random numbers and no clock.
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from . import blend, counting, words
from .load import load

ROW = 24  # the checkpoint whose row the flights are scored on, and whose chance they are scored by
WEEK_DAYS = 7
FLAGS = ("expected cancelled more than double the actual", "expected cancelled under half the actual",
         "the top tenth cancelled no more often than the rest")


@dataclass(frozen=True)
class Part:
    """Actual against expected for a set of scored flights."""
    flights: int  # those with a chance of cancelling
    cancelled: int  # of them
    expected_cancelled: float  # the sum of their chances of cancelling
    flew: int  # those that flew and have a chance of a delay
    delayed: int  # of them, an hour or more
    expected_delayed: float  # the sum of their chances of a delay


@dataclass(frozen=True)
class Report:
    first_day: date  # the week, in Israel days
    last_day: date
    every: Part
    top: Part  # the top tenth by the chance of cancelling, and the rest
    rest: Part
    top_delay: Part  # the top tenth by the chance of a delay, among the flights that flew, and the rest
    rest_delay: Part
    flags: tuple[str, ...]  # from FLAGS, in order; cancellations only
    no_chance: int  # the week's flights in the row with no chance of cancelling (None): not scored
    no_delay_chance: int  # of them that flew, those with no chance of a delay (None): not scored for a delay


@dataclass(frozen=True)
class _Scored:
    key: tuple  # Flight.key
    cancelled: bool
    flew: bool
    delayed: bool  # flew, an hour or more late
    cancel: float | None  # blend.cancel_chance on the ROW row
    delay: float | None  # blend.delay_chance


def week(snaps: list[dict]) -> tuple[date, date]:
    """The first and last Israel days of the week: the last is the latest day whose flights are all closed at the
    last sighting, so the next day's midnight in Israel is at least 48 hours (C4) before it."""
    edge = words.il_time(counting.last_sighting(snaps) - counting.CLOSED_AFTER)
    last = edge.date() - timedelta(days=1)
    return last - timedelta(days=WEEK_DAYS - 1), last


def _start(day: date) -> datetime:
    """Midnight in Israel at the start of `day`, as a model time (naive UTC)."""
    return datetime.combine(day, time(), tzinfo=words.ISRAEL).astimezone(timezone.utc).replace(tzinfo=None)


def _top(items: list[_Scored], chance) -> tuple[list[_Scored], list[_Scored]]:
    """The top tenth of `items` by `chance`, the ceiling of a tenth, ties broken by the flight key; and the rest."""
    ranked = sorted(items, key=lambda i: (-chance(i), i.key))
    n = (len(ranked) + 9) // 10
    return ranked[:n], ranked[n:]


def _part(items: list[_Scored]) -> Part:
    cancel = [i for i in items if i.cancel is not None]
    delay = [i for i in items if i.flew and i.delay is not None]
    return Part(flights=len(cancel), cancelled=sum(i.cancelled for i in cancel),
                expected_cancelled=math.fsum(i.cancel for i in cancel),
                flew=len(delay), delayed=sum(i.delayed for i in delay),
                expected_delayed=math.fsum(i.delay for i in delay))


def flagged(every: Part, top: Part, rest: Part) -> tuple[str, ...]:
    """FLAGS that hold, in order: the week's expected cancelled more than double the actual, or under half; the top
    tenth's share cancelled no higher than the rest's (in integers)."""
    holds = (every.expected_cancelled > 2 * every.cancelled,
             2 * every.expected_cancelled < every.cancelled,
             top.cancelled * rest.flights <= rest.cancelled * top.flights)
    return tuple(flag for flag, on in zip(FLAGS, holds) if on)


def run(table: list[dict], obs: list[dict], snaps: list[dict]) -> Report:
    """The back-test on the model `load` returns."""
    first, last = week(snaps)
    records = blend.records(table, obs, snaps, before=_start(first))
    flights_ = counting.flights(table, counting.last_sighting(snaps))
    by_id = {r["flight_id"]: r for r in table}
    row = {c.flight.key for c in counting.cells(flights_, counting.passings(counting.stretches(table, obs),
                                                                           counting.holes(snaps))) if c.h == ROW}
    items = []
    for f in [f for f in flights_ if first <= f.day <= last and f.key in row]:
        lead = blend.lead(f, by_id)
        number = records.numbers[(lead["airline"], lead["flight_no"], lead["direction"])]
        airline = records.airlines[f.airline]
        flew = f.result == "operated"
        items.append(_Scored(f.key, cancelled=f.result == "cancelled", flew=flew,
                             delayed=flew and blend.delayed(f, by_id),
                             cancel=blend.cancel_chance(number, airline, records.airport, ROW),
                             delay=blend.delay_chance(number, airline, records.airport, f.key[0])))
    top, rest = _top([i for i in items if i.cancel is not None], lambda i: i.cancel)
    top_delay, rest_delay = _top([i for i in items if i.flew and i.delay is not None], lambda i: i.delay)
    every, top_part, rest_part = _part(items), _part(top), _part(rest)
    return Report(first_day=first, last_day=last, every=every, top=top_part, rest=rest_part,
                  top_delay=_part(top_delay), rest_delay=_part(rest_delay),
                  flags=flagged(every, top_part, rest_part),
                  no_chance=sum(i.cancel is None for i in items),
                  no_delay_chance=sum(i.flew and i.delay is None for i in items))


def text(r: Report) -> str:
    """The report's fixed lines: counts, and sums to 2 decimals."""
    def cancelled(name: str, p: Part) -> str:
        return f"  {name}: {p.cancelled} of {p.flights}, expected {p.expected_cancelled:.2f}"

    def delayed(name: str, p: Part) -> str:
        return f"  {name}: {p.delayed} of {p.flew}, expected {p.expected_delayed:.2f}"

    return "\n".join([
        f"The back-test of the blend, on the week of {r.first_day.isoformat()} to {r.last_day.isoformat()} "
        "(Israel days)",
        f"Scored: the week's closed flights with a known result in the {ROW}-hour row, each by its lead number.",
        "The counts are cut at the week's start.",
        "A flight scheduled before it counts with its result as known at the last update, even one decided after the "
        "week began.",
        f"Not scored, with no chance worked out: {r.no_chance} for cancelling, {r.no_delay_chance} of those that "
        "flew for a delay of an hour or more.",
        "",
        "Cancelled: actual against expected",
        cancelled("every flight scored", r.every),
        cancelled("the top tenth by the chance of cancelling", r.top),
        cancelled("the rest", r.rest),
        "Delayed an hour or more: actual of those that flew, against expected",
        delayed("every flight that flew", r.every),
        delayed("the top tenth by the chance of a delay", r.top_delay),
        delayed("the rest", r.rest_delay),
        "",
        *([f"Flagged: {flag}" for flag in r.flags] or ["Not flagged."]),
    ]) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Print the report and write it to <out>/<model folder>/report.txt. Exit 0 when it is not flagged, 1 when it
    is, 2 with no model."""
    parser = argparse.ArgumentParser(prog="python -m timeline.backtest", description="The back-test of the blend "
                                     "(docs/flight-lookup.md, \"Before it ships: the back-test\").")
    parser.add_argument("--model", type=Path, required=True, help="the model folder (data/model-<date>)")
    parser.add_argument("--out", type=Path, default=Path("data/backtest"),
                        help="the folder that holds each model's report (default data/backtest)")
    args = parser.parse_args(argv)
    if not (args.model / "flights.parquet").exists():
        print(f"no model under {args.model}; run model.build first", file=sys.stderr)
        return 2
    report = run(*load(args.model))
    folder = args.out / args.model.absolute().name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.txt").write_text(text(report), encoding="utf-8")
    print(text(report), end="")
    return 1 if report.flags else 0


if __name__ == "__main__":
    sys.exit(main())
