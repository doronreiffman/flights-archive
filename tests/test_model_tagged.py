"""Every model test's archive built a second time, by the rules as tag record-v1 holds them, and compared
(docs/lighter-build.md:184, "In CI, on synthetic archives").

The lighter build may change how the model is computed and nothing else (docs/flight-lookup.md, "The record",
condition 2). This file holds every later commit to that in CI. With model_helpers.COMPARE_WITH_TAGGED on,
model_helpers.build also builds its archive with tests/fixtures/rules_record_v1.py (scripts/tagged_check.py) and fails
unless the two builds give the same five tables (checks 1 to 3 of "The frozen record"), or both refuse the archive with
the same exception class. It re-runs tests/test_model.py and tests/test_model_receipts.py that way, and adds the
archives the design names: cases that straddle midnight, since staging splits the archive by date folder, and the
cases of tests/test_record_cut.py, whole and cut.
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

# pytest collects the imported tests again here, with the comparison on (the autouse fixture below).
from test_model import *  # noqa: F401,F403
from test_model_receipts import *  # noqa: F401,F403

import model_helpers
from model import rules
from model_helpers import at, cut_archive, row, write_receipt, write_snapshot
from test_record_cut import CASES, Archive

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def compare_with_tagged(monkeypatch):
    monkeypatch.setattr(model_helpers, "COMPARE_WITH_TAGGED", True)


# --- the day-boundary cases ----------------------------------------------------------------------------------
# Each writes one archive into (raw, receipts): on 30 and 31 October 2026, after receipts began, unless noted. Every
# stored receipt carries its board's rows and pages.

def listed(flight_no: str = "001", **kw) -> dict:
    """A board row for a flight scheduled on 31 October, 10:00 Israel time unless given."""
    return row(**{"flight_no": flight_no, "sched_local": "2026-10-31T10:00:00"} | kw)


def store(raw: Path, receipts: Path, when, rows: list[dict], *, pages: int = 1, sha: str | None = None,
          receipt: bool = True) -> str:
    """One board, and its stored receipt unless `receipt` is false. Returns the snapshot id."""
    sid = write_snapshot(raw, when, rows, pages=pages, sha=sha)
    if receipt:
        write_receipt(receipts, sid, rows=len(rows), pages=pages)
    return sid


def repeated_store(raw: Path, receipts: Path) -> None:
    """The 23:45 board stored again at 00:01 with the same hash and its own receipt (R2 drops it, R9 credits its
    sighting to the 23:45 board); another board at 00:15."""
    board = [listed(), listed("002")]
    sid = store(raw, receipts, at(23, 45, day=30), board)
    store(raw, receipts, at(0, 1, day=31), board, sha=sid[-12:])
    store(raw, receipts, at(0, 15, day=31), [listed(status="DELAYED"), listed("002")])


def superseded(raw: Path, receipts: Path) -> None:
    """A board at 23:30; a board at 23:58 whose receipt write failed, stored again at 00:00 with the same hash and a
    receipt; a board at 00:15."""
    store(raw, receipts, at(23, 30, day=30), [listed()])
    sid = store(raw, receipts, at(23, 58, day=30), [listed(status="DELAYED")], receipt=False)
    store(raw, receipts, at(0, 0, day=31), [listed(status="DELAYED")], sha=sid[-12:])
    store(raw, receipts, at(0, 15, day=31), [listed(status="DELAYED"), listed("002")])


def retime(raw: Path, receipts: Path) -> None:
    """LY 001 last listed at 23:45; the same number, 2 hours later, first listed at 00:00 (R4 links the two)."""
    for when in (at(23, 30, day=30), at(23, 45, day=30)):
        store(raw, receipts, when, [listed()])
    for when in (at(0, 0, day=31), at(0, 15, day=31)):
        store(raw, receipts, when, [listed(sched_local="2026-10-31T12:00:00")])


def codeshare(raw: Path, receipts: Path) -> None:
    """EY 607, LY 9614 and W4 6406 in one group at 23:45; EY 607 and LY 9614 at 00:00; LY 9614 alone at 00:15. Each
    flight's last appearance is in a different group, and W4 6406's is on the other day."""
    ey, ly, w4 = (listed(flight_no, airline=airline, counters="12-21")
                  for airline, flight_no in (("EY", "607"), ("LY", "9614"), ("W4", "6406")))
    store(raw, receipts, at(23, 45, day=30), [ey, ly, w4])
    store(raw, receipts, at(0, 0, day=31), [ey, ly])
    store(raw, receipts, at(0, 15, day=31), [ly])


def sighting(raw: Path, receipts: Path) -> None:
    """A board at 23:50; unchanged receipts for it at 00:10 and 00:20, in receipts' 31 October folder (R9: its board
    is confirmed until 00:20); other content at 00:30."""
    board = [listed()]
    sid = store(raw, receipts, at(23, 50, day=30), board)
    for minute in (10, 20):
        write_receipt(receipts, sid, action="unchanged", when=at(0, minute, day=31), rows=len(board))
    store(raw, receipts, at(0, 30, day=31), [listed(status="DELAYED")])


def two_page(raw: Path, receipts: Path) -> None:
    """A two-page board of 5 rows at 23:59; a board at 00:15."""
    store(raw, receipts, at(23, 59, day=30), [listed(str(n)) for n in range(1, 6)], pages=2)
    store(raw, receipts, at(0, 15, day=31), [listed("1", status="DELAYED")] + [listed(str(n)) for n in range(2, 6)])


def incomplete(raw: Path, receipts: Path) -> None:
    """On 27 and 28 October, legacy, with no receipts: two-page boards of 5 rows at 23:45 and 00:15, complete, and one
    at 23:59 that lost its second page (R2 drops it as incomplete)."""
    board = [listed(str(n)) for n in range(1, 6)]
    changed = [listed("1", status="DELAYED")] + board[1:]
    write_snapshot(raw, at(23, 45, day=27), board, pages=2)
    sid = write_snapshot(raw, at(23, 59, day=27), changed, pages=2)
    (raw / "date=2026-10-27" / sid.split("/")[1] / "page-001.json.gz").unlink()  # the store was interrupted
    write_snapshot(raw, at(0, 15, day=28), changed, pages=2)


def pending_tail(raw: Path, receipts: Path) -> None:
    """A board at 23:45 with its receipt; a board at 00:10 with none: pending, inside the 35 minutes."""
    store(raw, receipts, at(23, 45, day=30), [listed()])
    store(raw, receipts, at(0, 10, day=31), [listed(status="DELAYED")], receipt=False)


def duplicates(raw: Path, receipts: Path) -> None:
    """A board at 23:59 holding an exact duplicate row, and two rows on one key with different `_id` and status (R2
    keeps the lower id); a board at 00:15."""
    store(raw, receipts, at(23, 59, day=30), [listed("100"), listed("100"),
                                               listed("200", status="DELAYED", _id=9), listed("200", _id=4)])
    store(raw, receipts, at(0, 15, day=31), [listed("100"), listed("200")])


BOUNDARY: dict[str, Callable[[Path, Path], None]] = {
    "repeated-store": repeated_store,
    "superseded": superseded,
    "retime": retime,
    "codeshare": codeshare,
    "sighting": sighting,
    "two-page": two_page,
    "incomplete": incomplete,
    "pending-tail": pending_tail,
    "duplicates": duplicates,
}

# Condition 3's three named cases (docs/flight-lookup.md:706), cut at each of their moments; every case is also built
# whole.
CUT = ("leave-and-return", "retime-at-the-cut", "flight-changes-after")
RECORD_CUT = ([pytest.param(name, None, id=f"{name}-whole") for name in CASES]
              + [pytest.param(name, moment, id=f"{name}-{moment:%H%M}") for name in CUT for moment in CASES[name][1]])


def test_the_fixture_is_what_the_tag_holds():
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed, so tag record-v1 cannot be read")
    done = subprocess.run([git, "show", "record-v1:src/model/rules.py"], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        pytest.skip(f"tag record-v1 cannot be read in this clone (CI clones without tags): {done.stderr.decode().strip()}")
    assert done.stdout == model_helpers.check_script().TAGGED_RULES.read_bytes()


@pytest.mark.parametrize("name", BOUNDARY)
def test_boundary_cases_match(tmp_path, name):
    raw, receipts = tmp_path / "raw", tmp_path / "receipts"
    BOUNDARY[name](raw, receipts)
    assert len(list(raw.glob("date=*"))) == 2
    if name == "sighting":
        assert len(list(receipts.glob("date=*"))) == 2
    model_helpers.build(raw, receipts)


@pytest.mark.parametrize("name, moment", RECORD_CUT)
def test_record_cut_cases_match(tmp_path, name, moment):
    archive = Archive(tmp_path / "whole")
    CASES[name][0](archive)
    raw, receipts = archive.raw, archive.receipts
    if moment is not None:
        raw, receipts = cut_archive(raw, receipts, moment, tmp_path / "cut")
    model_helpers.build(raw, receipts)


# --- the comparison catches a difference -----------------------------------------------------------------------

def test_a_rule_changed_on_the_new_side_only_is_caught(raw, monkeypatch):
    """test_vanish_horizon_is_one_hour_past_the_last_appearance's archive, with a 6-hour horizon on the new side
    only: flight 2 is dropped there and vanished in the tagged build."""
    write_snapshot(raw, at(6), [row(flight_no="1", sched_local="2026-10-27T08:30:00"),
                                row(flight_no="2", sched_local="2026-10-27T09:30:00")])
    write_snapshot(raw, at(6, 15), [row(flight_no="3")])
    monkeypatch.setattr(rules, "VANISH_HORIZON_HOURS", 6)
    with pytest.raises(AssertionError, match="flights"):
        model_helpers.build(raw)


def test_a_refusal_on_one_side_only_is_caught(raw, rec, monkeypatch):
    """A board 15 minutes after the newest receipt: pending for the tagged build (35 minutes' grace), refused by the
    new side with 5."""
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    monkeypatch.setattr(rules, "PENDING_GRACE_MINUTES", 5)
    with pytest.raises(AssertionError, match="refused"):
        model_helpers.build(raw, rec)


def test_a_refusal_of_another_kind_is_caught(raw, rec, monkeypatch):
    """A board 36 minutes after the newest receipt, which the tagged build refuses with a ValueError
    (test_receipts_older_than_raw_stop_the_build), while the new side's receipt check raises a RuntimeError."""
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    write_snapshot(raw, at(6, 36), [row(status="DELAYED")])

    def another_kind(con):
        raise RuntimeError("the receipts cannot be checked")

    monkeypatch.setattr(rules, "_check_receipts", another_kind)
    with pytest.raises(AssertionError, match="different exception classes"):
        model_helpers.build(raw, rec)
