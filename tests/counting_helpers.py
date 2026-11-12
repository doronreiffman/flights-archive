"""Rows for the counting tests, shaped as `timeline.load.load` returns them. All times are naive UTC, like the
model's own."""
from __future__ import annotations

from datetime import datetime, timedelta


def T(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """A model time (naive UTC) in November 2026."""
    return datetime(2026, 11, day, hour, minute, second)


def number(fid: str, sched_utc: datetime, **kw) -> dict:
    """A row of the model's flights table with the columns counting reads, and the first scheduled time a retime
    leaves behind; `kw` sets any of them. By default: LY 1 departing to ATH, never retimed, departed on time from
    terminal 3 at desks 1-5, first seen three days before its time and last seen at it. Israel time is UTC+2, as in
    November."""
    local = sched_utc + timedelta(hours=2)
    r = {"flight_id": fid, "airline": "LY", "flight_no": "1", "direction": "D", "airport": "ATH",
         "sched_utc_final": sched_utc, "sched_local_first": local, "sched_local_final": local,
         "est_utc_final": sched_utc, "terminal_final": 3, "counters_final": "1-5", "outcome": "departed",
         "first_seen_at": sched_utc - timedelta(days=3), "last_seen_at": sched_utc}
    unknown = set(kw) - set(r)
    assert not unknown, unknown
    return r | kw


def seen(fid: str, rn: int, at: datetime, **state) -> dict:
    """One observation: what the list showed for the number from snapshot `rn`, first stored at `at`. `state`
    sets sched_utc (required), est_utc (defaults to sched_utc), status, terminal and counters."""
    assert "sched_utc" in state, "an observation needs the scheduled time it showed"
    r = {"flight_id": fid, "snap_rn": rn, "observed_at": at, "sched_utc": None, "est_utc": None,
         "status": "ON TIME", "terminal": 3, "counters": "1-5"}
    unknown = set(state) - set(r)
    assert not unknown, unknown
    r |= state
    if "est_utc" not in state:
        r["est_utc"] = r["sched_utc"]
    return r


def board(*fetches) -> list[dict]:
    """The snapshots table as `load` returns it, one row per fetch. A fetch is its time, or a pair (fetched_at,
    confirmed_until) for a snapshot that later receipts saw again (R9). The gaps are the model's: whole seconds from
    the previous snapshot's last sighting to this fetch, NULL (None) for the first."""
    rows, prev = [], None
    for fetched_at, confirmed_until in (f if isinstance(f, tuple) else (f, f) for f in fetches):
        gap = None if prev is None else int((fetched_at - prev).total_seconds())
        rows.append({"fetched_at": fetched_at, "confirmed_until": confirmed_until, "prev": prev, "gap_before_s": gap})
        prev = confirmed_until
    return rows
