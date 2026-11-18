"""The stage (docs/lighter-build.md, "The design", 2): each date folder's per-board work done on that folder alone and
written to Parquet, and the whole-history rules run on what was staged. tests/test_model_tagged.py holds the results to
the tagged build's; these tests hold the stage's own files, the folders it reads and the ones it refuses."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import duckdb
import pytest

from model import build, rules, stage
from model_helpers import at, q, row, write_receipt, write_snapshot

# The receipts table's columns and types as the tagged build makes them (rules.load_receipts).
RECEIPT_COLUMNS = [
    ("receipt_file", "VARCHAR"), ("receipt_version", "INTEGER"), ("action", "VARCHAR"),
    ("run_started_at", "TIMESTAMP"), ("downloaded_at", "TIMESTAMP"), ("resource_last_modified", "TIMESTAMP"),
    ("snapshot_id", "VARCHAR"), ("snapshot_sha256", "VARCHAR"), ("rows", "BIGINT"), ("pages", "BIGINT"),
    ("code_sha256", "VARCHAR"),
]


@pytest.fixture(autouse=True)
def system_temp(tmp_path, monkeypatch) -> Path:
    """model.build.build stages into a temporary folder; here it is made under tmp_path."""
    folder = tmp_path / "systmp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


def read(path: Path) -> list[dict]:
    """The rows of one Parquet file."""
    rel = duckdb.connect().read_parquet(str(path))
    return [dict(zip(rel.columns, r)) for r in rel.fetchall()]


def test_each_date_folder_is_staged_to_its_own_files(tmp_path):
    raw, rec, staged = tmp_path / "raw", tmp_path / "receipts", tmp_path / "stage"
    first = write_snapshot(raw, at(23, 45, day=30), [row()])
    write_receipt(rec, first)
    second = write_snapshot(raw, at(0, 15, day=31), [row(status="DELAYED")])
    write_receipt(rec, second)

    con = rules.connect()
    st = stage.stage(con, raw, rec, staged)

    days = ("date=2026-10-30", "date=2026-10-31")
    assert st.raw_days == days and st.receipt_days == days
    assert st.staged == ("raw/date=2026-10-30", "raw/date=2026-10-31", "receipts/date=2026-10-30", "receipts/date=2026-10-31")
    for day, sid in zip(days, (first, second)):
        assert sorted(p.name for p in (staged / "raw" / day).iterdir()) == ["counts.parquet", "rows.parquet"]
        assert [r["snapshot_id"] for r in read(staged / "raw" / day / "rows.parquet")] == [sid]
        assert [r["snapshot_id"] for r in read(staged / "raw" / day / "counts.parquet")] == [sid]
        assert sorted(p.name for p in (staged / "receipts" / day).iterdir()) == ["receipts.parquet"]
        assert [r["snapshot_id"] for r in read(staged / "receipts" / day / "receipts.parquet")] == [sid]
    # Read back, the staged files carry their own columns only: no `date` taken from the date=… in their paths.
    stage.open_stage(con, staged, st)
    assert [(name, kind) for name, kind, *_ in con.execute("DESCRIBE receipts").fetchall()] == RECEIPT_COLUMNS
    assert "date" not in [name for name, *_ in con.execute("DESCRIBE staged_rows").fetchall()]
    assert "date" not in [name for name, *_ in con.execute("DESCRIBE staged_counts").fetchall()]


def test_a_staged_day_holds_every_board_trusted_or_not(tmp_path):
    """On 27 October, before receipts began: a legacy board at 06:00, one at 06:15 that lost its second page (legacy and
    incomplete), a receipted board at 07:00, and one at 07:15 with no receipt (pending, inside the grace)."""
    raw, rec, staged = tmp_path / "raw", tmp_path / "receipts", tmp_path / "stage"
    legacy = write_snapshot(raw, at(6), [row()])
    incomplete = write_snapshot(raw, at(6, 15), [row(flight_no=str(n)) for n in range(1, 5)], pages=2)
    (raw / "date=2026-10-27" / incomplete.split("/")[1] / "page-001.json.gz").unlink()  # the store was interrupted
    receipted = write_snapshot(raw, at(7), [row(status="DELAYED")])
    write_receipt(rec, receipted)
    pending = write_snapshot(raw, at(7, 15), [row(status="FINAL")])

    con = rules.connect()
    build.run(con, raw, rec, staged)

    day = staged / "raw" / "date=2026-10-27"
    counts = {r["snapshot_id"]: r for r in read(day / "counts.parquet")}
    assert set(counts) == {legacy, incomplete, receipted, pending}
    assert counts[incomplete]["incomplete"] is True and counts[pending]["incomplete"] is False
    assert {r["snapshot_id"] for r in read(day / "rows.parquet")} == {legacy, incomplete, receipted, pending}
    runs = {r["snapshot_id"]: r for r in q(con, "SELECT * FROM snapshot_runs")}
    assert (runs[incomplete]["receipt"], runs[incomplete]["incomplete"]) == ("legacy", True)
    assert (runs[pending]["receipt"], runs[pending]["incomplete"]) == ("pending", False)
    assert {r["snapshot_id"] for r in q(con, "SELECT DISTINCT snapshot_id FROM rows")} == {legacy, receipted}


@pytest.mark.parametrize("stray", ["stray.json.gz", "copy/date=2026-10-27/060000Z-aaaaaaaaaaaa/page-000.json.gz"])
def test_a_snapshot_file_outside_the_date_folders_stops_the_build(tmp_path, stray):
    raw = tmp_path / "raw"
    write_snapshot(raw, at(6), [row()])
    page = next(raw.rglob("page-000.json.gz")).read_bytes()
    (raw / stray).parent.mkdir(parents=True, exist_ok=True)
    (raw / stray).write_bytes(page)
    with pytest.raises(ValueError, match="path") as refused:
        stage.stage(rules.connect(), raw, None, tmp_path / "stage")
    assert stray in str(refused.value)
    assert not (tmp_path / "stage").exists()  # refused before any day is staged


@pytest.mark.parametrize("stray", ["date=2026-10-27/stray.json.gz",
                                   "date=2026-10-27/060000Z-aaaaaaaaaaaa/extra/page-000.json.gz"])
def test_a_snapshot_file_off_the_layout_inside_a_date_folder_stops_the_build(tmp_path, stray):
    raw, staged = tmp_path / "raw", tmp_path / "stage"
    write_snapshot(raw, at(6), [row()])
    page = next(raw.rglob("page-000.json.gz")).read_bytes()
    (raw / stray).parent.mkdir(parents=True, exist_ok=True)
    (raw / stray).write_bytes(page)
    with pytest.raises(ValueError, match="have a path that is not") as refused:
        stage.stage(rules.connect(), raw, None, staged)
    assert stray in str(refused.value)
    assert not list(staged.glob("*/date=*"))  # no day staged


@pytest.mark.parametrize("receipted", [False, True], ids=["legacy", "receipted"])
def test_a_day_copied_into_another_date_folder_stops_the_build(tmp_path, receipted):
    """`cp -r raw/date=D raw/date=E`, when raw/date=E exists, nests day D inside day E: one snapshot's page in two date
    folders, both under D's snapshot id. The tagged build reads the two copies as one snapshot (legacy: built, its raw
    rows counted twice; receipted: refused, its files then differ from its receipt). Staged by folder, the copy would
    be counted under E. It is refused before any day is staged."""
    raw, rec, staged = tmp_path / "raw", tmp_path / "receipts", tmp_path / "stage"
    day, other = (30, 31) if receipted else (27, 28)  # after receipts began, or before
    copied = write_snapshot(raw, at(6, day=day), [row()])
    kept = write_snapshot(raw, at(6, day=other), [row(status="DELAYED")])
    if receipted:
        write_receipt(rec, copied)
        write_receipt(rec, kept)
    shutil.copytree(raw / f"date=2026-10-{day}", raw / f"date=2026-10-{other}" / f"date=2026-10-{day}")
    with pytest.raises(ValueError, match="path") as refused:
        stage.stage(rules.connect(), raw, rec, staged)
    assert f"date=2026-10-{other}/date=2026-10-{day}/{copied.split('/')[1]}/page-000.json.gz" in str(refused.value)
    assert not list(staged.glob("*/date=*"))  # no day staged


def test_a_snapshot_path_with_an_impossible_time_stops_the_build(tmp_path):
    """A path in the collector's layout whose time cannot be (hour 25): rules.load_raw's own check refuses it."""
    raw = tmp_path / "raw"
    write_snapshot(raw, at(6), [row()])
    impossible = raw / "date=2026-10-27" / "250000Z-aaaaaaaaaaaa" / "page-000.json.gz"
    impossible.parent.mkdir()
    impossible.write_bytes(next(raw.rglob("page-000.json.gz")).read_bytes())
    with pytest.raises(ValueError, match="rows come from files whose path is not"):
        stage.stage(rules.connect(), raw, None, tmp_path / "stage")


def test_a_receipt_outside_the_date_folders_stops_the_build(tmp_path):
    raw, rec = tmp_path / "raw", tmp_path / "receipts"
    sid = write_snapshot(raw, at(23, 45, day=30), [row()])
    receipt = Path(write_receipt(rec, sid))
    (rec / "stray.json").write_bytes(receipt.read_bytes())
    with pytest.raises(ValueError, match="outside") as refused:
        stage.stage(rules.connect(), raw, rec, tmp_path / "stage")
    assert "stray.json" in str(refused.value)
    assert not list((tmp_path / "stage").glob("*/date=*"))  # no day staged


def test_an_empty_date_folder_is_skipped(tmp_path):
    """An interrupted sync's empty date folder, and one holding only the Finder's .DS_Store (Review Focus 3)."""
    raw, rec, staged = tmp_path / "raw", tmp_path / "receipts", tmp_path / "stage"
    (raw / "date=2026-10-26").mkdir(parents=True)
    (raw / "date=2026-10-25").mkdir()
    (raw / "date=2026-10-25" / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    write_snapshot(raw, at(6), [row()])
    (rec / "date=2026-10-26").mkdir(parents=True)

    con = rules.connect()
    st = stage.stage(con, raw, rec, staged)
    assert st.raw_days == ("date=2026-10-27",) and st.receipt_days == ()
    assert st.staged == ("raw/date=2026-10-27",)
    stage.open_stage(con, staged, st)
    assert rules.build_tables(con)["flights"] == 1


def test_paths_with_an_apostrophe_and_a_space_build(tmp_path, monkeypatch):
    """Every path written into SQL has its quotes doubled (Review Focus 4): the archive, the build's temporary stage
    and the model all sit under a folder named with both."""
    base = tmp_path / "o'hare archive"
    raw, rec, temp = base / "raw", base / "receipts", base / "tmp"
    sid = write_snapshot(raw, at(23, 45, day=30), [row(), row(flight_no="2")])
    write_receipt(rec, sid, rows=2)
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    stages = []
    real = stage.stage
    monkeypatch.setattr(stage, "stage", lambda con, r, x, s: stages.append(s) or real(con, r, x, s))

    assert build.build(raw, base / "model", rec)["flights"] == 2

    assert [s.parent for s in stages] == [temp]
    assert len(read(base / "model" / "flights.parquet")) == 2
    assert list(temp.iterdir()) == []  # the temporary stage is removed


@pytest.mark.parametrize("receipts", [None, "missing"])
def test_without_receipts_the_receipts_table_is_empty(tmp_path, receipts):
    raw = tmp_path / "raw"
    write_snapshot(raw, at(6), [row()])
    con = rules.connect()
    counts = build.run(con, raw, None if receipts is None else tmp_path / receipts, tmp_path / "stage")
    assert counts["receipts"] == 0 and counts["flights"] == 1
    assert [(name, kind) for name, kind, *_ in con.execute("DESCRIBE receipts").fetchall()] == RECEIPT_COLUMNS


@pytest.mark.parametrize("archive", ["no folder", "empty folder", "empty date folder"])
def test_without_snapshot_files_the_build_stops(tmp_path, system_temp, archive):
    raw = tmp_path / "raw"
    if archive != "no folder":
        raw.mkdir()
    if archive == "empty date folder":
        (raw / "date=2026-10-27").mkdir()
    with pytest.raises(ValueError, match="no snapshot files"):
        build.build(raw, tmp_path / "model")
    assert not (tmp_path / "model").exists()
    assert list(system_temp.iterdir()) == []  # the temporary stage is removed
