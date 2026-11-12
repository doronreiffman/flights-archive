"""The counting rule, read number by number "as of" a moment: what the list showed for each number from one change
to the next, and the first moment it passed each checkpoint (docs/flight-lookup.md, C5 and C6;
docs/flight-lookup-figures.md, A0's `st`, `hole` and `cp`).

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no timeline module but the
frozen ones (tests/test_frozen.py). Pure functions over the rows `timeline.load.load` returns; model times are
naive UTC.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from model.rules import GAP_HOURS

CHECKPOINTS = (70, 48, 24, 12, 6, 3)  # C5: hours before the scheduled time the list showed at the moment
# Two candidate readings of where a number's last stretch ends ("The record", condition 3):
#   "a0"     a second after the number's last sighting, as A0's `st` reads it;
#   "carry"  at the next download after that sighting, or never (datetime.max) when it is on the latest list.
READINGS = ("a0", "carry")
READING = "a0"  # the reading the frozen rule uses; set by the owner's ruling at this task's stop


@dataclass(frozen=True)
class Stretch:
    """What the list showed for one number from one change to the next (A0's `st`)."""
    flight_id: str
    snap_rn: int
    from_at: datetime  # this observation's time
    to_at: datetime  # the next observation's time; after the last, where the reading ends it (READINGS)
    to_ever: datetime  # the next observation's time, else datetime.max: the last state, kept after the number left
    sched_utc: datetime
    est_utc: datetime | None
    status: str
    terminal: int | None
    desks: str  # the check-in counters, or ""


def _last_end(last_seen_at: datetime, fetches: list[datetime], reading: str) -> datetime:
    """Where a number's last stretch ends, by reading; `fetches` are the downloads in order."""
    if reading == "a0":
        return last_seen_at + timedelta(seconds=1)
    i = bisect_right(fetches, last_seen_at)
    return fetches[i] if i < len(fetches) else datetime.max


def stretches(table: list[dict], obs: list[dict], snaps: list[dict], reading: str = READING) -> dict[str, tuple[Stretch, ...]]:
    """Each number's stretches in snap_rn order, keyed by flight_id in the table's order."""
    if reading not in READINGS:
        raise ValueError(f"unknown reading {reading!r}; the readings are {READINGS}")
    fetches = [s["fetched_at"] for s in snaps]
    by_flight: dict[str, list[dict]] = {}
    for o in obs:
        by_flight.setdefault(o["flight_id"], []).append(o)
    out = {}
    for f in table:
        own = sorted(by_flight.get(f["flight_id"], []), key=lambda o: o["snap_rn"])
        end = _last_end(f["last_seen_at"], fetches, reading)
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
