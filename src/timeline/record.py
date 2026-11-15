"""The signs S1 to S4 (docs/flight-lookup.md, "Signs"; docs/flight-lookup-figures.md, A0b's `nrow`, `not_whole`,
`nsign` and `sign`): what the list showed about a number at its checkpoint moment that might go with a later
cancellation, read from what the list showed then and nothing later, and the signs its flight carries in that row.
They are tested on flights listed after the freeze and shown on no page.

The sign test ("Signs", "The gate", "The re-test"; A29): each sign's lift and scores on the 24-hour row's counted
flights, those first listed at or after the counting start, read up to the gate and no further. `main` keeps the
record's files:

    PYTHONPATH=src .venv/bin/python -m timeline.record --model data/model --out DIR
    PYTHONPATH=src .venv/bin/python -m timeline.record --model data/model --out DIR \
        --retest S3 --first-upload 2027-01-10T23:00:00Z

DIR/<TAG>/progress.json on every run, DIR/<TAG>/result.json once, when the gate is reached; the re-test the same two
files under DIR/<TAG>/retest-<SIGN>/.

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no timeline module but the
frozen ones (tests/test_frozen.py). Pure functions over the rows `timeline.load.load` returns and what
`timeline.counting` reads from them; model times are naive UTC. A number's flight is rule C1's grouping at the end
(the design's third known case of condition 3); its signs are as of its moment.
"""
from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass, replace
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import counting, rates
from .counting import Cell, Flight, Stretch
from .load import load

ISRAEL = ZoneInfo("Asia/Jerusalem")
TAG = "record-v1"  # the record's version: its folder, and the tag of the frozen code (the owner's, at Task 8)
COUNTING_START: datetime | None = datetime(2026, 11, 15, 22)  # owner's, Task 8: 16 Nov 2026 00:00 Israel, naive UTC
GATE_CANCELLED, GATE_DAYS, SIGN_ROW = 200, 60, 24  # "The gate": 200 cancelled in the 24-hour row, over 60 days or more

SIGNS = ("S1", "S2", "S3", "S4")
# A flight carries these only when every one of its numbers in the row shows them, the others when any does (A0b's
# `sign`)
EVERY = frozenset({"S4"})
CANCELED = "CANCELED"
INBOUND = (timedelta(minutes=30), timedelta(hours=12))  # S1: the inbound is scheduled this long before, both included
NEAR = timedelta(hours=24)  # S3: another flight of the airline scheduled this long either side, both included
LATE = timedelta(hours=48)  # S4: first listed under this long before the scheduled time it then showed


def _tied(a: Stretch, y: Stretch, airline_a: str, airline_y: str) -> bool:
    """Rule C1's direct tie read at a moment, for a number showing cancelled (A0b's `not_whole`): never across two
    terminals or two different desk ranges; then the same expected time and desks, the same airline, or the same
    desks. A missing value equals a missing one; a number with no desks shares none."""
    if y.terminal != a.terminal or (y.desks != "" and a.desks != "" and y.desks != a.desks):
        return False
    return (y.est_utc == a.est_utc and y.desks == a.desks) or airline_y == airline_a or (
        a.desks != "" and y.desks == a.desks)


def whole(a: Stretch, t: datetime, by_slot: dict, by_id: dict) -> bool:
    """Listed as cancelled as a whole at t (A0b's `not_whole`): `a`, the stretch of its number that holds t, shows
    CANCELED, and no other number tied to it at t shows anything else. Tied at t: in the same slot as the list showed
    it at t (`by_slot`: (direction, airport, sched_utc) -> every stretch shown in it), by direct ties only, since a
    chain needs the grouping at the end. A number that has left the list keeps the last status it showed (to_ever);
    one first seen after t is not read; a missing status counts for nothing, as in A0b. `by_id` is the flights
    table by flight_id."""
    r = by_id[a.flight_id]
    return a.status == CANCELED and not any(
        y.flight_id != a.flight_id and y.from_at <= t < y.to_ever and y.status not in (None, CANCELED)
        and _tied(a, y, r["airline"], by_id[y.flight_id]["airline"])
        for y in by_slot.get((r["direction"], r["airport"], a.sched_utc), ()))


def _by_sched(own: list[Stretch]) -> tuple[list[datetime], list[Stretch]]:
    ordered = sorted(own, key=lambda s: s.sched_utc)
    return [s.sched_utc for s in ordered], ordered


def _between(index: tuple[list[datetime], list[Stretch]], lo: datetime, hi: datetime) -> list[Stretch]:
    """The stretches of `index` (_by_sched's) scheduled from lo to hi, both included."""
    times, ordered = index
    return ordered[bisect_left(times, lo):bisect_right(times, hi)]


def number_signs(h: int, table: list[dict], st: dict[str, tuple[Stretch, ...]], holes_, first_fetch: datetime,
                 passings_: dict[tuple[str, int], tuple[datetime, str | None]]) -> dict[str, frozenset[str]]:
    """flight_id -> the signs the number shows at its h-hour passing, for every number in the row: one that passed h
    with a status other than CANCELED (C6; A0b's `nrow` and `nsign`). Each is read at the passing's moment t from
    what the list showed then, by the scheduled time it showed then. `holes_` (counting.holes) and `first_fetch`
    (the first snapshot's fetched_at) say when the records began or resumed, for S4."""
    by_id = {r["flight_id"]: r for r in table}
    by_slot: dict[tuple, list[Stretch]] = {}
    by_number: dict[tuple, list[Stretch]] = {}
    cancelled: dict[str, list[Stretch]] = {}
    for fid, own in st.items():
        r = by_id[fid]
        for s in own:
            by_slot.setdefault((r["direction"], r["airport"], s.sched_utc), []).append(s)
            by_number.setdefault((r["airline"], r["flight_no"], r["direction"]), []).append(s)
            if s.status == CANCELED:
                cancelled.setdefault(r["airline"], []).append(s)
    by_airline = {airline: _by_sched(own) for airline, own in cancelled.items()}
    resumed = {first_fetch, *(end for _, end in holes_)}  # S4: a number first seen then is never late
    out = {}
    for (fid, at_h), (t, status) in passings_.items():
        if at_h != h or status in (None, CANCELED):
            continue
        r = by_id[fid]
        sched = t + timedelta(hours=h)  # the scheduled time the list showed at t
        of_airline = by_airline.get(r["airline"], ([], []))
        signs = set()
        # S1: an arrival of the airline from the same airport, scheduled 30 minutes to 12 hours before this
        # departure, on the list at t and listed as cancelled as a whole. Departures only.
        if r["direction"] == "D" and any(
                by_id[a.flight_id]["direction"] == "A" and by_id[a.flight_id]["airport"] == r["airport"]
                and a.from_at <= t < a.to_at and whole(a, t, by_slot, by_id)
                for a in _between(of_airline, sched - INBOUND[1], sched - INBOUND[0])):
            signs.add("S1")
        # S2: of the same number's other flights known at t, the latest scheduled before this one (as shown at t, or
        # as last shown if it has left the list; on a tie, the smaller flight_id) is listed as cancelled as a whole
        before = sorted((a for a in by_number[r["airline"], r["flight_no"], r["direction"]]
                         if a.flight_id != fid and a.from_at <= t < a.to_ever and a.sched_utc < sched),
                        key=lambda a: a.flight_id)
        if before and whole(max(before, key=lambda a: a.sched_utc), t, by_slot, by_id):
            signs.add("S2")
        # S3: another number of the airline, in another slot scheduled within 24 hours either side, on the list at t
        # and listed as cancelled as a whole
        if any(b.flight_id != fid and b.from_at <= t < b.to_at
               and (by_id[b.flight_id]["direction"], by_id[b.flight_id]["airport"], b.sched_utc)
               != (r["direction"], r["airport"], sched)
               and whole(b, t, by_slot, by_id)
               for b in _between(of_airline, sched - NEAR, sched + NEAR)):
            signs.add("S3")
        # S4: first listed under 48 hours before the scheduled time it then showed, unless first seen when the
        # records began or resumed after a hole
        first = st[fid][0]
        if first.sched_utc - first.from_at < LATE and first.from_at not in resumed:
            signs.add("S4")
        out[fid] = frozenset(signs)
    return out


def flight_signs(cells_h: list[Cell], number_signs_: dict[str, frozenset[str]]) -> dict[tuple, frozenset[str]]:
    """Flight key -> the signs the flight carries in one checkpoint's row, for each of `cells_h` (that row's cells),
    from `number_signs_` (number_signs at the same checkpoint): S1 to S3 when any of its numbers in the row shows it,
    S4 when every one of them does (A0b's `sign`). ValueError for a cell with no number in `number_signs_`: a cell
    is in the row because one of its numbers is, so the two come from different checkpoints (and S4 would hold of no
    number at all)."""
    out = {}
    for c in cells_h:
        shown = [number_signs_[fid] for fid in c.flight.numbers if fid in number_signs_]
        if not shown:
            raise ValueError(f"row {c.h}: no number of the flight {c.flight.key} has signs in this row")
        out[c.flight.key] = frozenset(sign for sign in SIGNS
                                      if (all if sign in EVERY else any)(sign in signs for signs in shown))
    return out


# --- the sign test ("Signs", "The gate", "The re-test"; A29) ---------------------------------------------------------

def counted_cells(cells_24: list[Cell], start: datetime) -> list[Cell]:
    """The counted flights of the 24-hour row (A29's `counted`): those whose every number was first seen at or after
    `start`, the counting start. Flight.first_seen is the earliest first sighting of its numbers."""
    return [c for c in cells_24 if c.flight.first_seen >= start]


def unclosed(flights_: list[Flight], passings_: dict[tuple[str, int], tuple[datetime, str | None]],
             start: datetime) -> list[datetime]:
    """The 24-hour moments of the counted flights not yet closed, in time order (the guard's input, Question 2): for
    each, the earliest moment one of its numbers passed the 24-hour point listed with a status other than CANCELED,
    as counting.cells reads a row's moment. Such a flight enters the row at that moment once it closes with a known
    result."""
    of = counting.flight_of(flights_)
    moment: dict[tuple, datetime] = {}
    for (fid, h), (t, status) in passings_.items():
        f = of[fid]
        if h == SIGN_ROW and status not in (None, CANCELED) and not f.closed and f.first_seen >= start:
            moment[f.key] = min(t, moment.get(f.key, t))
    return sorted(moment.values())


def gate_reached_at(counted_: list[Cell], unclosed_: list[datetime], start: datetime) -> datetime | None:
    """"The gate", its count: in the order of the scheduled time each counted flight showed at its 24-hour moment (t +
    24 h, then its key), the first such time at least GATE_DAYS after `start` by which GATE_CANCELLED of them were
    later listed as cancelled. Every counted flight of the row counts, whatever signs it carries. None until then,
    and while a counted flight not yet closed has a moment u with u + 24 h at or before that time, since it could
    still enter the row before it (the guard, Question 2)."""
    so_far = 0
    for c in sorted(counted_, key=lambda c: (c.t, c.flight.key)):
        so_far += c.k
        at = c.t + timedelta(hours=SIGN_ROW)
        if so_far >= GATE_CANCELLED and at >= start + timedelta(days=GATE_DAYS):
            return None if any(u + timedelta(hours=SIGN_ROW) <= at for u in unclosed_) else at
    return None


def read_until(counted_: list[Cell], gate_at: datetime | None) -> list[Cell]:
    """What the test reads: the counted flights scheduled (as shown at t) up to the gate and no later; all of them
    while it is not reached. When the test runs does not change what it reads."""
    return [c for c in counted_ if gate_at is None or c.t + timedelta(hours=SIGN_ROW) <= gate_at]


@dataclass(frozen=True)
class Result:
    """One run of the sign test from `start`: the gate if reached, the row's cancelled flights and the days from the
    start to the latest scheduled time over the flights read (None before any is read), and each sign's lift and
    scores."""
    start: datetime
    gate_at: datetime | None
    row_cancelled: int
    days: float | None
    # a sign's Lift.passes counts only once gate_at is set (A29's `sign_passes`); before the gate it decides nothing
    signs: dict[str, tuple[rates.Lift, rates.Scores]]


def run(table: list[dict], obs: list[dict], snaps: list[dict], start: datetime) -> Result:
    """The sign test on the model `load` returns, from the counting start `start` (naive UTC): the 24-hour row's
    counted flights read up to the gate, and each sign's lift (A0b's `ratio`) and scores on them. S1's sets, with and
    without, hold departures only, as A0b's `signcell` keeps them: S1 is read for departures only, so an arrival is
    in neither. The gate counts every counted flight of the row; `row_cancelled` and `days` are taken over the
    flights read, so that a later run's flights after the gate leave them as they were (A29 takes them over every
    counted flight; the two agree while the gate is not reached)."""
    flights_ = counting.flights(table, counting.last_sighting(snaps))
    st = counting.stretches(table, obs)
    holes_ = counting.holes(snaps)
    passings_ = counting.passings(st, holes_)
    counted_ = counted_cells([c for c in counting.cells(flights_, passings_) if c.h == SIGN_ROW], start)
    gate_at = gate_reached_at(counted_, unclosed(flights_, passings_, start), start)
    read = read_until(counted_, gate_at)
    carried = flight_signs(read, number_signs(SIGN_ROW, table, st, holes_, snaps[0]["fetched_at"], passings_))
    signs = {}
    for sign in SIGNS:
        row = [c for c in read if sign != "S1" or c.flight.key[0] == "D"]
        with_ = [counting.counted(c.flight) for c in row if sign in carried[c.flight.key]]
        without = [counting.counted(c.flight) for c in row if sign not in carried[c.flight.key]]
        signs[sign] = (rates.lift(with_, without), rates.scores(with_, without))
    last = max((c.t for c in read), default=None)
    days = None if last is None else (last + timedelta(hours=SIGN_ROW) - start) / timedelta(days=1)
    return Result(start, gate_at, sum(c.k for c in read), days, signs)


def retest_start(first_upload: datetime) -> datetime:
    """"The re-test": its counting start, the next Israel midnight after a sign's split is first uploaded at
    `first_upload` (naive UTC), as naive UTC."""
    day = first_upload.replace(tzinfo=timezone.utc).astimezone(ISRAEL).date() + timedelta(days=1)
    return datetime.combine(day, time(), tzinfo=ISRAEL).astimezone(timezone.utc).replace(tzinfo=None)


def _cut(value):
    """Every float in `value` cut to 12 significant digits, so that a file's bytes do not hang on a sum's last
    bits."""
    if isinstance(value, float):
        return float(f"{value:.12g}")
    if isinstance(value, dict):
        return {k: _cut(v) for k, v in value.items()}
    return value


def _utc(t: datetime | None) -> str | None:
    return None if t is None else f"{t.isoformat()}Z"


def _text(result: Result) -> str:
    """The result as the files hold it: JSON with its keys sorted, times in UTC ending in Z, floats cut."""
    plain = {"start": _utc(result.start), "gate_at": _utc(result.gate_at), "row_cancelled": result.row_cancelled,
             "days": result.days,
             "signs": {sign: {"lift": asdict(lift), "scores": asdict(scores)}
                       for sign, (lift, scores) in result.signs.items()}}
    return json.dumps(_cut(plain), sort_keys=True, indent=2) + "\n"


def write(result: Result, path: Path, once: bool) -> None:
    """The result to `path`. With `once`, only when no file is there (FileExistsError otherwise): a result, once
    written, is never replaced."""
    with open(path, "x" if once else "w", encoding="utf-8", newline="\n") as f:
        f.write(_text(result))


def _first_upload(value: str) -> datetime:
    """--first-upload: a UTC time ending in Z (2027-01-10T23:00:00Z), as naive UTC."""
    if not value.endswith("Z"):
        raise argparse.ArgumentTypeError(f"{value!r} does not end in Z: give the time in UTC, as 2027-01-10T23:00:00Z")
    try:
        t = datetime.fromisoformat(value.removesuffix("Z"))
    except ValueError:
        t = None
    if t is None or t.tzinfo is not None or "T" not in value:  # a date alone is not a time
        raise argparse.ArgumentTypeError(f"{value!r} is not a UTC time such as 2027-01-10T23:00:00Z")
    return t


def main(argv: list[str] | None = None) -> int:
    """The test, or with --retest the re-test of one sign: progress.json on every run, result.json once the gate is
    reached. Exit 2 while COUNTING_START is not set, and 1 when a stored result differs from this run's, whether this
    run reaches the gate or not."""
    parser = argparse.ArgumentParser(prog="python -m timeline.record", description="The sign test and its re-test "
                                     "(docs/flight-lookup.md, \"Signs\", \"The gate\", \"The re-test\").")
    parser.add_argument("--model", type=Path, required=True, help="the model folder (data/model)")
    parser.add_argument("--out", type=Path, required=True, help=f"the folder that holds the record's {TAG}/")
    parser.add_argument("--retest", choices=SIGNS, help="run the re-test of this sign")
    parser.add_argument("--first-upload", type=_first_upload, metavar="UTC",
                        help="the re-test's: when the sign's split was first uploaded, as 2027-01-10T23:00:00Z")
    args = parser.parse_args(argv)
    if (args.retest is None) != (args.first_upload is None):
        parser.error("--retest and --first-upload go together")
    if COUNTING_START is None:
        print("timeline.record: COUNTING_START is not set; it is written into the frozen code at Task 8 "
              "(docs/flight-lookup-plan.md)", file=sys.stderr)
        return 2
    folder, start = args.out / TAG, COUNTING_START
    if args.retest:
        folder, start = folder / f"retest-{args.retest}", retest_start(args.first_upload)
    result = run(*load(args.model), start)
    if args.retest:  # the re-test is of the one sign whose split was uploaded ("The re-test")
        result = replace(result, signs={args.retest: result.signs[args.retest]})
    folder.mkdir(parents=True, exist_ok=True)
    write(result, folder / "progress.json", once=False)
    print(f"{folder}: {result.row_cancelled} cancelled in the row, "
          + ("gate not reached" if result.gate_at is None else f"gate reached at {_utc(result.gate_at)}"))
    stored_at = folder / "result.json"
    if result.gate_at is None and not stored_at.exists():
        return 0
    try:  # the first result is written once; every later run is compared with it, its gate reached or not
        write(result, stored_at, once=True)
    except FileExistsError:
        stored, now = stored_at.read_text(encoding="utf-8"), _text(result)
        if stored != now:
            print(f"{stored_at} differs from this run's result and is kept as it is.\n"
                  f"Stored:\n{stored}This run:\n{now}", file=sys.stderr, end="")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
