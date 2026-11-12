"""The cut-archive comparison (docs/flight-lookup.md, "The record", condition 3): the model read "as of" a moment
against the model built from the archive cut at that moment. Each case is its own small synthetic archive, built
whole and cut at each of its moments through the real model build; a moment is either on a download or between two.

L is the cut's last sighting (counting.last_sighting). Both models are read by A0's rule. Where they differ, the test
asserts the difference exactly, as measured at the plan's Task 1 and accepted by the owner's ruling (ACCEPTED below);
any other difference fails.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from model import build as model_build
from model_helpers import cut_archive, row, write_receipt, write_snapshot
from timeline import counting
from timeline.load import load

SECOND = timedelta(seconds=1)


def z(hour: int, minute: int = 0) -> datetime:
    """A download time on 30 October 2026 (naive UTC)."""
    return datetime(2026, 10, 30, hour, minute)


def utc(hour: int, minute: int = 0) -> datetime:
    """A scheduled time on 31 October 2026 (naive UTC)."""
    return datetime(2026, 10, 31, hour, minute)


GRID = tuple(z(10) + timedelta(minutes=15 * i) for i in range(17))  # every 15 minutes, 10:00 to 14:00


def listing(airline: str, flight_no: str, sched_utc: datetime, **kw) -> dict:
    """A board row; the board shows Israel time, UTC+2 after the 25 October clock change."""
    return row(airline=airline, flight_no=flight_no, sched_local=(sched_utc + timedelta(hours=2)).isoformat(), **kw)


STEADY = listing("LY", "001", utc(0, 45))  # on every board; its 12-hour moment is 30 October 12:45


class Archive:
    def __init__(self, root: Path):
        self.raw, self.receipts = root / "raw", root / "receipts"

    def store(self, when: datetime, rows: list[dict], *, sha: str | None = None, receipt: bool = True) -> str:
        sid = write_snapshot(self.raw, when, rows, sha=sha)
        if receipt:
            write_receipt(self.receipts, sid, rows=len(rows))
        return sid

    def unchanged(self, sid: str, when: datetime, rows: list[dict]) -> None:
        write_receipt(self.receipts, sid, action="unchanged", when=when, rows=len(rows))


def leave_and_return(a: Archive) -> None:
    """LY 100 is listed 10:00 to 11:00, absent 11:15 to 11:45, and back from 12:00 (A20's case). Its 24-hour
    moment, 11:30, falls while it is absent."""
    ly100 = listing("LY", "100", utc(11, 30))
    for t in GRID:
        a.store(t, [STEADY] + ([ly100] if t <= z(11) or t >= z(12) else []))


def return_after_a_same_number_key(a: Archive) -> None:
    """As leave-and-return, plus LY 100 three hours later, first listed at 11:15 and not terminal. A cut at 11:30
    can link it as a retime of the first; the full build cannot, since the first key's last snapshot is 14:00."""
    first, later = listing("LY", "100", utc(10, 30)), listing("LY", "100", utc(13, 30))
    for t in GRID:
        a.store(t, [STEADY] + ([first] if t <= z(11) or t >= z(12) else []) + ([later] if t >= z(11, 15) else []))


def retime_at_the_cut(a: Archive) -> None:
    """LY 200's key is last seen at 11:00; a key two hours later is first seen at 11:15."""
    first, later = listing("LY", "200", utc(11, 10)), listing("LY", "200", utc(13, 10))
    for t in GRID:
        a.store(t, [STEADY, first if t <= z(11) else later])


def flight_changes_after(a: Archive) -> None:
    """EY 607 and LY 9614 share expected time, terminal and desks until 12:00; at 12:15 LY 9614 moves to another desk
    range, so rule C1 no longer ties them. Neither departs in the archive; their 12-hour moment is 12:00."""
    for t in GRID:
        a.store(t, [STEADY, listing("EY", "607", utc(0), counters="12-21"),
                    listing("LY", "9614", utc(0), counters="12-21" if t <= z(12) else "30-35")])


def repeated_store(a: Archive) -> None:
    """The 11:15 board is stored again at 11:17 with the same hash and its own receipt: R2 drops the copy and R9
    credits its sighting. LY 500 is last listed on that board; its 24-hour moment is 11:16."""
    ly500 = listing("LY", "500", utc(11, 16))
    for t in GRID:
        rows = [STEADY] + ([ly500] if t <= z(11, 15) else [])
        sid = a.store(t, rows)
        if t == z(11, 15):
            a.store(z(11, 17), rows, sha=sid[-12:])


def superseded(a: Archive) -> None:
    """An 11:15 snapshot with no receipt is stored again at 11:17 with one (rules.py:222). On that board LY 400 shows
    DELAYED for the first time; its 24-hour moment is 11:16."""
    on_time = listing("LY", "400", utc(11, 16))
    delayed = listing("LY", "400", utc(11, 16), status="DELAYED", status_he="מתעכב")
    for t in GRID:
        rows = [STEADY, on_time if t < z(11, 15) else delayed]
        if t == z(11, 15):
            sid = a.store(t, rows, receipt=False)  # its receipt write failed
            a.store(z(11, 17), rows, sha=sid[-12:])  # so the next run stores the same board again
        else:
            a.store(t, rows)


def unchanged_downloads(a: Archive) -> None:
    """Unchanged receipts at 11:17, 11:19 and 11:21 follow the 11:15 store; the next store is at 11:30. LY 600 leaves
    after 11:15; its 24-hour moment is 11:20."""
    ly600 = listing("LY", "600", utc(11, 20))
    for t in GRID:
        rows = [STEADY] + ([ly600] if t <= z(11, 15) else [])
        sid = a.store(t, rows)
        if t == z(11, 15):
            for minute in (17, 19, 21):
                a.unchanged(sid, z(11, minute), rows)


def hole_in_progress(a: Archive) -> None:
    """Nothing is downloaded from 11:00 to 12:30. LY 700 is listed throughout; its 24-hour moment, 11:30, falls in
    the hole."""
    ly700 = listing("LY", "700", utc(11, 30))
    for t in GRID:
        if not z(11) < t < z(12, 30):
            a.store(t, [STEADY, ly700])


CASES = {
    "leave-and-return": (leave_and_return, (z(11, 7), z(11, 30), z(12, 30), z(12, 37))),
    "return-after-a-same-number-key": (return_after_a_same_number_key, (z(11, 15), z(11, 22), z(11, 30), z(12, 30))),
    "retime-at-the-cut": (retime_at_the_cut, (z(11), z(11, 7), z(11, 15))),
    "flight-changes-after": (flight_changes_after, (z(12), z(12, 7))),
    "repeated-store": (repeated_store, (z(11, 15), z(11, 16), z(11, 17))),
    "superseded": (superseded, (z(11, 15), z(11, 16), z(11, 17))),
    "unchanged-downloads": (unchanged_downloads, (z(11, 17), z(11, 18), z(11, 21), z(11, 25))),
    "hole-in-progress": (hole_in_progress, (z(11, 45),)),
}
MOMENTS = [pytest.param(name, moment, id=f"{name}-{moment:%H%M}") for name, (_, moments) in CASES.items()
           for moment in moments]


@dataclass(frozen=True)
class Model:
    dir: Path
    counts: dict
    table: list[dict]
    obs: list[dict]
    snaps: list[dict]


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    """(case, moment) -> (full model, cut model), each built once."""
    built: dict = {}

    def model(raw: Path, receipts: Path, out: Path) -> Model:
        counts = model_build.build(raw, out, receipts)
        return Model(out, counts, *load(out))

    def get(name: str, moment: datetime) -> tuple[Model, Model]:
        if name not in built:
            root = tmp_path_factory.mktemp(name)
            archive = Archive(root)
            CASES[name][0](archive)
            built[name] = (archive, model(archive.raw, archive.receipts, root / "model"))
        archive, full = built[name]
        if (name, moment) not in built:
            dest = tmp_path_factory.mktemp(f"{name}-{moment:%H%M}")
            raw, receipts = cut_archive(archive.raw, archive.receipts, moment, dest)
            built[name, moment] = model(raw, receipts, dest / "model")
        return full, built[name, moment]

    return get


# --- reading a model ---------------------------------------------------------------------------------

def _names(*models: Model) -> dict[str, str]:
    return {f["flight_id"]: f"{f['airline']} {f['flight_no']} at {f['sched_local_first']:%d %b %H:%M} Israel time"
            for m in models for f in m.table}


def _show(v):
    if isinstance(v, datetime):
        return "never" if v == datetime.max else f"{v:%d %H:%M:%S}"
    if isinstance(v, (tuple, list)):
        return tuple(_show(x) for x in v)
    return v


def differences(full: dict, cut: dict, names: dict[str, str]) -> dict[tuple, tuple]:
    """what -> (the full model's value, the cut's), for every key whose values differ; keys name a number by its
    flight_id, shown by its airline, number and first scheduled time (Israel time)."""
    def label(key):
        return tuple(names.get(k, k) if isinstance(k, str) else k for k in key)
    return {label(k): (_show(full.get(k, "absent")), _show(cut.get(k, "absent")))
            for k in sorted(set(full) | set(cut), key=str) if full.get(k, "absent") != cut.get(k, "absent")}


def record(m: Model, last: datetime) -> dict:
    """A0's reading of `m` up to `last`, for every number first seen by then: its first record, its stretches that
    began by then (ends capped a second after `last`) and its passings at or before `last`."""
    st = counting.stretches(m.table, m.obs)
    seen = {f["flight_id"] for f in m.table if f["first_seen_at"] <= last}
    out = {}
    for o in sorted(m.obs, key=lambda o: (o["flight_id"], o["snap_rn"])):
        if o["flight_id"] in seen:
            out.setdefault(("first record", o["flight_id"]), (o["observed_at"], o["sched_utc"], o["status"]))
    for fid in seen:
        out["stretches", fid] = tuple((s.from_at, min(s.to_at, last + SECOND), s.status, s.sched_utc, s.est_utc,
                                       s.terminal, s.desks) for s in st[fid] if s.from_at <= last)
    for (fid, h), passing in counting.passings(st, counting.holes(m.snaps)).items():
        if fid in seen and passing[0] <= last:
            out["passing", fid, h] = passing
    return out


def chains(m: Model, last: datetime) -> dict:
    """Each number's retime chain (flights.key_ids), among keys first seen at or before `last`."""
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    path = str(m.dir / "observations.parquet").replace("'", "''")
    first = {k: (t, f"{airline} {no} at {sched:%H:%M}Z") for k, t, airline, no, sched in con.execute(
        f"""SELECT key_id, min(observed_at), any_value(airline), any_value(flight_no), any_value(sched_utc)
            FROM '{path}' WHERE change_kind IN ('first', 'retime') GROUP BY key_id""").fetchall()}
    out = {}
    for f in m.table:
        keys = tuple(first[k][1] for k in f["key_ids"] if first[k][0] <= last)
        if keys:
            out["chain", f["flight_id"]] = keys
    return out


def inputs(m: Model, last: datetime) -> dict:
    """Rule C1's inputs for each number first seen at or before `last`, as the model reads them at its end."""
    return {("C1 inputs", f["flight_id"]): (f["est_utc_final"], f["terminal_final"], f["counters_final"])
            for f in m.table if f["first_seen_at"] <= last}


# --- the differences the ruling accepts ----------------------------------------------------------------
# The owner's ruling (docs/flight-lookup.md, "The record", "Measured and ruled, 2026-11-12"): "My call: the record reads
# the full model by A0's rule, with these differences as its stated limits, and is not computed from cut builds."
# Each entry below is one of those differences, exactly as this comparison measured it; values are shown as
# "DD HH:MM:SS" (UTC), "absent" where a model has no such key.

def piece(from_at: str, to_at: str, sched: str) -> tuple:
    """One stretch as `record` shows it: on time, scheduled and expected at `sched`, terminal 3, desks 1-5."""
    return (from_at, to_at, "ON TIME", sched, sched, 3, "1-5")


AWAY = "LY 100 at 31 Oct 13:30 Israel time"  # leave-and-return
FIRST, LATER = "LY 100 at 31 Oct 12:30 Israel time", "LY 100 at 31 Oct 15:30 Israel time"  # the same-number key


def same_number_key(end: str) -> dict[str, dict]:
    """Kind 2 at a cut whose last sighting is a second before `end`: the cut links LATER to FIRST as a retime (the two
    keys sit on adjacent lists), which the full model cannot, since FIRST's last list is 14:00. "A cut build would
    also link 3 of those numbers as retimes, at no checkpoint moment." (the ruling's paragraph)"""
    return {
        "record": {("first record", LATER): (("30 11:15:00", "31 13:30:00", "ON TIME"), "absent"),
                   ("stretches", LATER): ((piece("30 11:15:00", end, "31 13:30:00"),), "absent"),
                   ("stretches", FIRST): ((piece("30 10:00:00", end, "31 10:30:00"),),
                                          (piece("30 10:00:00", "30 11:15:00", "31 10:30:00"),
                                           piece("30 11:15:00", end, "31 13:30:00")))},
        "chains": {("chain", LATER): (("LY 100 at 13:30Z",), "absent"),
                   ("chain", FIRST): (("LY 100 at 10:30Z",), ("LY 100 at 10:30Z", "LY 100 at 13:30Z"))},
        "inputs": {("C1 inputs", LATER): (("31 13:30:00", 3, "1-5"), "absent"),
                   ("C1 inputs", FIRST): (("31 10:30:00", 3, "1-5"), ("31 13:30:00", 3, "1-5"))},
    }


ACCEPTED: dict[tuple[str, str], dict] = {
    # Kind 1, a number that left the list and came back: the full model reads it as listed throughout (it records
    # changes, not absences), the cut sees it gone after 11:00. "7 checkpoint moments of the 7 numbers that left the
    # list and came back fell while they were off it, so a cut build would leave those flights out of those rows."
    ("record", "leave-and-return-1130"): {
        ("passing", AWAY, 24): (("30 11:30:00", "ON TIME"), "absent"),
        ("stretches", AWAY): ((piece("30 10:00:00", "30 11:30:01", "31 11:30:00"),),
                              (piece("30 10:00:00", "30 11:00:01", "31 11:30:00"),))},
    # Kind 3, C1's inputs read at the end: "C1's inputs read at the end are compared in the plan's Task 6."
    ("inputs", "retime-at-the-cut-1100"): {
        ("C1 inputs", "LY 200 at 31 Oct 13:10 Israel time"): (("31 13:10:00", 3, "1-5"), ("31 11:10:00", 3, "1-5"))},
    ("inputs", "retime-at-the-cut-1107"): {
        ("C1 inputs", "LY 200 at 31 Oct 13:10 Israel time"): (("31 13:10:00", 3, "1-5"), ("31 11:10:00", 3, "1-5"))},
    ("inputs", "flight-changes-after-1200"): {
        ("C1 inputs", "LY 9614 at 31 Oct 02:00 Israel time"): (("31 00:00:00", 3, "30-35"), ("31 00:00:00", 3, "12-21"))},
    ("inputs", "flight-changes-after-1207"): {
        ("C1 inputs", "LY 9614 at 31 Oct 02:00 Israel time"): (("31 00:00:00", 3, "30-35"), ("31 00:00:00", 3, "12-21"))},
} | {(test, f"return-after-a-same-number-key-{moment}"): diffs  # kind 2 (and its C1 inputs, kind 3)
     for moment, end in (("1115", "30 11:15:01"), ("1122", "30 11:15:01"), ("1130", "30 11:30:01"))
     for test, diffs in same_number_key(end).items()}


def accepted(test: str, name: str, moment: datetime) -> dict:
    return ACCEPTED.get((test, f"{name}-{moment:%H%M}"), {})


def test_every_accepted_difference_names_a_case_and_moment():
    ids = {p.id for p in MOMENTS}
    assert {key for key in ACCEPTED if key[0] not in {"record", "chains", "inputs"} or key[1] not in ids} == set()


# --- the comparison ------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, moment", MOMENTS)
def test_cut_builds_build(models, name, moment):
    _, cut = models(name, moment)
    assert cut.counts["snapshots"] > 0 and cut.counts["flights"] > 0


@pytest.mark.parametrize("name, moment", MOMENTS)
def test_record_readings_match(models, name, moment):
    full, cut = models(name, moment)
    last = counting.last_sighting(cut.snaps)
    assert differences(record(full, last), record(cut, last), _names(full, cut)) == accepted("record", name, moment)


@pytest.mark.parametrize("name, moment", MOMENTS)
def test_retime_chains_match(models, name, moment):
    full, cut = models(name, moment)
    last = counting.last_sighting(cut.snaps)
    assert differences(chains(full, last), chains(cut, last), _names(full, cut)) == accepted("chains", name, moment)


@pytest.mark.parametrize("name, moment", MOMENTS)
def test_flight_inputs_match(models, name, moment):
    """The design lists this as a known case (condition 3, third bullet), and the ruling keeps it as a stated limit.
    The outcome is left out: rule C2 reads it at the end by design. Flight membership is compared in Task 6, once
    rule C1 exists."""
    full, cut = models(name, moment)
    last = counting.last_sighting(cut.snaps)
    assert differences(inputs(full, last), inputs(cut, last), _names(full, cut)) == accepted("inputs", name, moment)
