"""The signs S1 to S4 (docs/flight-lookup.md, "Signs"; docs/flight-lookup-figures.md, A0b's `nrow`, `not_whole`,
`nsign` and `sign`): what the list showed about a number at its checkpoint moment that might go with a later
cancellation, read from what the list showed then and nothing later, and the signs its flight carries in that row.
They are tested on flights listed after the freeze and shown on no page.

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no timeline module but the
frozen ones (tests/test_frozen.py). Pure functions over the rows `timeline.load.load` returns and what
`timeline.counting` reads from them; model times are naive UTC. A number's flight is rule C1's grouping at the end
(the design's third known case of condition 3); its signs are as of its moment.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta

from .counting import Cell, Stretch

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
