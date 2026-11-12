"""The counting rule: which numbers are one flight, its result and when it is closed (docs/flight-lookup.md, C1 to
C4; docs/flight-lookup-figures.md, A0's `tie`, `num` and `fl`); and, read number by number "as of" a moment, what
the list showed for each number from one change to the next, and the first moment it passed each checkpoint (C5 and
C6; A0's `st`, `hole` and `cp`).

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no timeline module but the
frozen ones (tests/test_frozen.py). Pure functions over the rows `timeline.load.load` returns; model times are
naive UTC.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import combinations

from model.rules import GAP_HOURS

CLOSED_AFTER = timedelta(hours=48)  # C4: a flight is closed this long after its scheduled time
OPERATED = frozenset({"departed", "landed"})  # the outcomes of a number that departed or landed (A0's `n0`)
CHECKPOINTS = (70, 48, 24, 12, 6, 3)  # C5: hours before the scheduled time the list showed at the moment
# A number's last stretch ends a second after its last sighting, as A0's `st` reads it. The record reads the full
# model by this rule. The ways a model built from the archive cut at a moment was measured to read that moment
# otherwise are the rule's stated limits: a number that left the list and came back, a key of the same number
# linked as a retime during such an absence, and C1's inputs read at the end (docs/flight-lookup.md, "The record",
# "Measured and ruled, 2026-11-12"; tests/test_record_cut.py).


@dataclass(frozen=True)
class Stretch:
    """What the list showed for one number from one change to the next (A0's `st`)."""
    flight_id: str
    snap_rn: int
    from_at: datetime  # this observation's time
    to_at: datetime  # the next observation's time; after the last, a second after the number's last sighting
    to_ever: datetime  # the next observation's time, else datetime.max: the last state, kept after the number left
    sched_utc: datetime
    est_utc: datetime | None
    status: str
    terminal: int | None
    desks: str  # the check-in counters, or ""


def stretches(table: list[dict], obs: list[dict]) -> dict[str, tuple[Stretch, ...]]:
    """Each number's stretches in snap_rn order, keyed by flight_id in the table's order. The last ends a second
    after the number's last sighting (`last_seen_at`, R9)."""
    by_flight: dict[str, list[dict]] = {}
    for o in obs:
        by_flight.setdefault(o["flight_id"], []).append(o)
    out = {}
    for f in table:
        own = sorted(by_flight.get(f["flight_id"], []), key=lambda o: o["snap_rn"])
        end = f["last_seen_at"] + timedelta(seconds=1)
        out[f["flight_id"]] = tuple(
            Stretch(o["flight_id"], o["snap_rn"], from_at=o["observed_at"],
                    to_at=nxt["observed_at"] if nxt else end,
                    to_ever=nxt["observed_at"] if nxt else datetime.max,
                    sched_utc=o["sched_utc"], est_utc=o["est_utc"], status=o["status"], terminal=o["terminal"],
                    desks=o["counters"] or "")
            for o, nxt in zip(own, [*own[1:], None]))
    return out


def holes(snaps: list[dict]) -> tuple[tuple[datetime, datetime], ...]:
    """Stretches of more than GAP_HOURS with no download: from the last sighting to the next fetch. The first
    snapshot has no gap before it (NULL)."""
    return tuple((s["prev"], s["fetched_at"]) for s in snaps
                 if s["gap_before_s"] is not None and s["gap_before_s"] > GAP_HOURS * 3600)


def in_hole(t: datetime, holes_) -> bool:
    """Strictly inside a hole: at its edges the list was seen."""
    return any(a < t < b for a, b in holes_)


def passings(st: dict[str, tuple[Stretch, ...]], holes_) -> dict[tuple[str, int], tuple[datetime, str]]:
    """(flight_id, h) -> (t, status) of the number's first passing of checkpoint h: the lowest-snap_rn stretch whose
    own scheduled time less h hours falls in [from_at, to_at), never inside a hole (C6: the clock is the time
    shown at the moment; a number first listed with less time left has no passing there)."""
    out: dict[tuple[str, int], tuple[datetime, str]] = {}
    for fid, own in st.items():
        for s in sorted(own, key=lambda s: s.snap_rn):
            for h in CHECKPOINTS:
                t = s.sched_utc - timedelta(hours=h)
                if s.from_at <= t < s.to_at and not in_hole(t, holes_):
                    out.setdefault((fid, h), (t, s.status))
    return out


def state_at(st: dict[str, tuple[Stretch, ...]], t: datetime) -> dict[str, Stretch]:
    """The numbers listed at t, each with the stretch that holds t (from_at <= t < to_at)."""
    out = {}
    for fid, own in st.items():
        for s in own:
            if s.from_at <= t < s.to_at:
                out[fid] = s
                break
    return out


def last_sighting(snaps: list[dict]) -> datetime:
    """The last time the board was seen: the latest snapshot's last sighting (R9)."""
    return snaps[-1]["confirmed_until"]


@dataclass(frozen=True)
class Flight:
    """The numbers of one slot that rule C1 makes one flight, with its result (C2, C3) and whether it is closed (C4)
    (A0's `num` and `fl`)."""
    key: tuple[str, str, datetime, str]  # direction, airport, sched_utc_final, the smallest flight_id
    numbers: tuple[str, ...]  # flight_ids, sorted
    result: str  # "operated" | "cancelled" | "unknown" (C2)
    closed: bool  # C4: sched_utc_final <= the last sighting - 48 h
    airline: str  # C8's grouping airline (A0's `fl.lead_airline`)
    day: date  # the Israel date of sched_local_final
    first_seen: datetime  # the earliest first_seen_at of its numbers


def _desks(r: dict) -> str:
    """The check-in desks at the number's last listing, or "" (A0's `n0.desks`)."""
    return r["counters_final"] or ""


def _shown(r: dict) -> tuple:
    """The expected time, terminal and desks at the number's last listing: the model's codeshare key (R5)."""
    return r["est_utc_final"], r["terminal_final"], _desks(r)


def _operated(r: dict) -> bool:
    return r["outcome"] in OPERATED


def tied(a: dict, b: dict) -> bool:
    """C1's direct tie of two numbers of one slot (A0's `tie`), read at each number's last listing: never across two
    terminals or two different desk ranges; then the same expected time, terminal and desks, or, when at least one
    did not depart or land, the same airline or the same desks. A missing value equals a missing one (SQL's IS NOT
    DISTINCT FROM). A number with no desks conflicts with no desk range, and two with none do not share desks."""
    da, db = _desks(a), _desks(b)
    if a["terminal_final"] != b["terminal_final"]:
        return False
    if da != "" and db != "" and da != db:
        return False
    if _shown(a) == _shown(b):
        return True
    return not (_operated(a) and _operated(b)) and (a["airline"] == b["airline"] or (da != "" and da == db))


def _parts(rows: list[dict]) -> list[list[dict]]:
    """C1: ties chain. A slot's numbers in the parts its `tied` pairs connect, by union-find."""
    root = list(range(len(rows)))

    def find(i: int) -> int:
        while root[i] != i:
            i = root[i]
        return i

    for i, j in combinations(range(len(rows)), 2):
        if tied(rows[i], rows[j]):
            root[find(j)] = find(i)
    parts: dict[int, list[dict]] = {}
    for k, r in enumerate(rows):
        parts.setdefault(find(k), []).append(r)
    return list(parts.values())


def _apart(part: list[dict]) -> list[list[dict]]:
    """C1's last clause: a chain never joins two numbers that departed or landed without the same expected time,
    terminal and desks. If it would, the part's numbers that did not depart or land stand alone, and those that did
    regroup by expected time, terminal and desks (A12 found no such chain; A0 leaves this out)."""
    if len({_shown(r) for r in part if _operated(r)}) < 2:
        return [part]
    regrouped: dict[tuple, list[dict]] = {}
    for r in part:
        if _operated(r):
            regrouped.setdefault(_shown(r), []).append(r)
    return [[r] for r in part if not _operated(r)] + list(regrouped.values())


def _number_order(r: dict) -> tuple:
    """C8's order for the grouping airline (A0's `fl.lead_airline`): the integer value of the first run of digits
    in the flight number, a number with none after every numbered one; then the airline."""
    digits = re.search(r"[0-9]+", r["flight_no"])
    return (int(digits.group()) if digits else math.inf, r["airline"])


def _flight(rows: list[dict], last_sighting_: datetime) -> Flight:
    first = rows[0]  # the numbers of a flight share its slot
    outcomes = {r["outcome"] for r in rows}
    ids = tuple(sorted(r["flight_id"] for r in rows))
    return Flight(
        key=(first["direction"], first["airport"], first["sched_utc_final"], ids[0]),
        numbers=ids,
        # C2, read from each number's last status (C3)
        result="operated" if outcomes & OPERATED else "cancelled" if "canceled" in outcomes else "unknown",
        closed=first["sched_utc_final"] <= last_sighting_ - CLOSED_AFTER,
        airline=min(rows, key=_number_order)["airline"],
        day=first["sched_local_final"].date(),
        first_seen=min(r["first_seen_at"] for r in rows))


def flights(table: list[dict], last_sighting_: datetime) -> list[Flight]:
    """Every flight of the flights table (C1 to C4), sorted by key: the numbers of each slot (direction, airport,
    sched_utc_final) joined by rule C1, closed or not at `last_sighting_` (A0's `max(confirmed_until)`)."""
    # By exact values. A0's slot string cuts the time to the minute, and a NULL part makes it NULL, which joins
    # nothing; the two agree on today's data, whose times are whole minutes and whose slot parts are never NULL.
    slots: dict[tuple, list[dict]] = {}
    for r in table:
        slots.setdefault((r["direction"], r["airport"], r["sched_utc_final"]), []).append(r)
    return sorted((_flight(rows, last_sighting_) for slot in slots.values() for part in _parts(slot)
                   for rows in _apart(part)), key=lambda f: f.key)


def flight_of(flights_: list[Flight]) -> dict[str, Flight]:
    """Each number's flight, by flight_id."""
    return {fid: f for f in flights_ for fid in f.numbers}
