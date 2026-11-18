"""The stage (docs/lighter-build.md, "The design", 2): each date folder's per-board work done on that folder alone and
written to Parquet, and the whole-history rules run on what was staged. tests/test_model_tagged.py holds the results to
the tagged build's; these tests hold the stage's own files, the folders it reads and the ones it refuses, and when a
staged day is reused ("Re-run, crash, late files, rule change"): a build that reuses the stage gives the same rows as
a fresh build with no stage."""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from model import build, rules, stage
from model_helpers import at, check_script, q, row, write_receipt, write_snapshot

MODEL_SOURCE = Path(__file__).resolve().parent.parent / "src" / "model"

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
        assert sorted(p.name for p in (staged / "raw" / day).iterdir()) == ["counts.parquet", "marker.json", "rows.parquet"]
        assert [r["snapshot_id"] for r in read(staged / "raw" / day / "rows.parquet")] == [sid]
        assert [r["snapshot_id"] for r in read(staged / "raw" / day / "counts.parquet")] == [sid]
        assert sorted(p.name for p in (staged / "receipts" / day).iterdir()) == ["marker.json", "receipts.parquet"]
        assert [r["snapshot_id"] for r in read(staged / "receipts" / day / "receipts.parquet")] == [sid]
        # Each marker: the fingerprint, and the day's source files by path relative to its folder and size.
        page = raw / day / sid.split("/")[1] / "page-000.json.gz"
        assert json.loads((staged / "raw" / day / "marker.json").read_text()) == {
            "fingerprint": stage.fingerprint(), "files": [[page.relative_to(raw / day).as_posix(), page.stat().st_size]]}
        receipt = next((rec / day).iterdir())
        assert json.loads((staged / "receipts" / day / "marker.json").read_text()) == {
            "fingerprint": stage.fingerprint(), "files": [[receipt.name, receipt.stat().st_size]]}
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
    monkeypatch.setattr(stage, "stage", lambda con, r, x, s, **kw: stages.append(s) or real(con, r, x, s, **kw))

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


# --- reuse: a staged day is used again only while its marker matches its files, the model's source and DuckDB ----

def nov(day: int, hour: int = 6) -> datetime:
    """A fetch time (UTC) on 2026-11-<day>."""
    return datetime(2026, 11, day, hour)


def board(raw: Path, rec: Path | None, fetched_at: datetime, status: str = "ON TIME") -> str:
    """One one-row board, with its stored receipt when rec is given; returns its snapshot id."""
    sid = write_snapshot(raw, fetched_at, [row(status=status)])
    if rec is not None:
        write_receipt(rec, sid)
    return sid


def legacy_days(tmp_path) -> tuple[Path, Path]:
    """(raw, stage): a board on each of 26 and 27 October, before receipts began, so legacy and with no receipts."""
    raw = tmp_path / "raw"
    board(raw, None, at(6, day=26))
    board(raw, None, at(6), "DELAYED")
    return raw, tmp_path / "stage"


def receipted_days(tmp_path) -> tuple[Path, Path, Path]:
    """(raw, receipts, stage): a board on each of 30 and 31 October, after receipts began, with its receipt."""
    raw, rec = tmp_path / "raw", tmp_path / "receipts"
    board(raw, rec, at(6, day=30))
    board(raw, rec, at(6, day=31), "DELAYED")
    return raw, rec, tmp_path / "stage"


RECEIPTED_DAYS = ("raw/date=2026-10-30", "raw/date=2026-10-31", "receipts/date=2026-10-30", "receipts/date=2026-10-31")


def compare_with_fresh(raw: Path, rec: Path | None, staged: Path, work: Path) -> list[str]:
    """A build on the stage folder `staged` (work/staged) and a fresh build of the same archive with no stage
    (work/fresh), compared as the tagged check compares two models: one line per difference, [] when the same."""
    build.build(raw, work / "staged", rec, stage_dir=staged)
    build.build(raw, work / "fresh", rec)
    check = check_script()
    return (check.compare_tables(work / "fresh", work / "staged", ("fresh", "staged"))
            + check.compare_load(work / "fresh", work / "staged"))


def test_a_second_build_on_the_same_files_stages_nothing(tmp_path):
    """A build given a stage folder keeps it, and a second run on the same files reuses every day."""
    raw, rec, staged = receipted_days(tmp_path)
    build.build(raw, tmp_path / "model", rec, stage_dir=staged)
    st = stage.stage(rules.connect(), raw, rec, staged)
    assert st.staged == ()
    assert st.raw_days == st.receipt_days == ("date=2026-10-30", "date=2026-10-31")


def test_reuse_equals_a_fresh_build(tmp_path):
    raw, rec, staged = tmp_path / "raw", tmp_path / "receipts", tmp_path / "stage"
    board(raw, rec, at(6, day=30))
    board(raw, rec, at(6, day=31), "DELAYED")
    board(raw, rec, nov(1))
    board(raw, rec, nov(2), "FINAL")
    assert len(stage.stage(rules.connect(), raw, rec, staged).staged) == 8

    board(raw, rec, nov(3), "DEPARTED")  # a day added
    board(raw, rec, nov(2, 7), "DEPARTED")  # a board added to the last day staged
    board(raw, rec, at(7, day=30), "DELAYED")  # a board added to an old day
    st = stage.stage(rules.connect(), raw, rec, staged)

    assert st.staged == ("raw/date=2026-10-30", "raw/date=2026-11-02", "raw/date=2026-11-03",
                         "receipts/date=2026-10-30", "receipts/date=2026-11-02", "receipts/date=2026-11-03")
    assert compare_with_fresh(raw, rec, staged, tmp_path / "after") == []


def test_a_late_receipt_restages_only_its_receipts_day(tmp_path):
    """An unchanged receipt for 30 October's board, synced after that day was staged: it changes no staged board."""
    raw, rec, staged = receipted_days(tmp_path)
    stage.stage(rules.connect(), raw, rec, staged)
    folder = next((raw / "date=2026-10-30").iterdir())
    write_receipt(rec, f"2026-10-30/{folder.name}", action="unchanged", when=at(7, day=30))

    assert stage.stage(rules.connect(), raw, rec, staged).staged == ("receipts/date=2026-10-30",)
    assert compare_with_fresh(raw, rec, staged, tmp_path / "after") == []


def test_a_late_second_page_is_staged_again(tmp_path):
    """A two-page board whose second page was not yet synced when its day was staged."""
    raw, staged = legacy_days(tmp_path)
    sid = write_snapshot(raw, at(7), [row(flight_no=str(n)) for n in range(1, 5)], pages=2)
    second = raw / "date=2026-10-27" / sid.split("/")[1] / "page-001.json.gz"
    page = second.read_bytes()
    second.unlink()
    stage.stage(rules.connect(), raw, None, staged)
    counts = {r["snapshot_id"]: r for r in read(staged / "raw" / "date=2026-10-27" / "counts.parquet")}
    assert counts[sid]["incomplete"] is True

    second.write_bytes(page)  # the page arrives
    assert stage.stage(rules.connect(), raw, None, staged).staged == ("raw/date=2026-10-27",)
    assert compare_with_fresh(raw, None, staged, tmp_path / "after") == []
    runs = {r["snapshot_id"]: r for r in read(tmp_path / "after" / "staged" / "snapshot_runs.parquet")}
    assert runs[sid]["incomplete"] is False


def test_a_file_whose_size_changed_is_staged_again(tmp_path):
    """A page rewritten under the same name with one more row: the day's listing holds the same paths."""
    raw, staged = legacy_days(tmp_path)
    stage.stage(rules.connect(), raw, None, staged)
    folder = next((raw / "date=2026-10-27").iterdir())
    size = (folder / "page-000.json.gz").stat().st_size
    shutil.rmtree(folder)
    write_snapshot(raw, at(6), [row(status="DELAYED"), row(flight_no="2")], sha=folder.name.split("-")[1])
    assert (folder / "page-000.json.gz").stat().st_size != size

    assert stage.stage(rules.connect(), raw, None, staged).staged == ("raw/date=2026-10-27",)
    assert compare_with_fresh(raw, None, staged, tmp_path / "after") == []


@pytest.mark.parametrize("when", ["before", "after"])
def test_a_file_synced_while_its_day_is_read_stages_that_day_again(tmp_path, monkeypatch, when):
    """A sync during a build: a board lands in 26 October's folder while that day is staged, just before or just after
    its files are read. The day's listing is taken before the read (stage._stage_day), so the marker never names a file
    the staged rows may lack: the next build stages that day again, and equals a fresh build."""
    raw, staged = legacy_days(tmp_path)
    real = stage._read_boards
    synced = []

    def read_during_a_sync(con, day):
        late = day.name == "date=2026-10-26" and not synced
        if late and when == "before":
            synced.append(board(raw, None, at(7, day=26), "DELAYED"))
        real(con, day)
        if late and when == "after":
            synced.append(board(raw, None, at(7, day=26), "DELAYED"))

    monkeypatch.setattr(stage, "_read_boards", read_during_a_sync)
    assert stage.stage(rules.connect(), raw, None, staged).staged == ("raw/date=2026-10-26", "raw/date=2026-10-27")
    assert len(synced) == 1

    assert stage.stage(rules.connect(), raw, None, staged).staged == ("raw/date=2026-10-26",)
    assert compare_with_fresh(raw, None, staged, tmp_path / "after") == []


def test_a_staged_day_whose_folder_is_gone_is_ignored(tmp_path):
    raw, staged = legacy_days(tmp_path)
    stage.stage(rules.connect(), raw, None, staged)
    shutil.rmtree(raw / "date=2026-10-26")

    st = stage.stage(rules.connect(), raw, None, staged)
    assert st.raw_days == ("date=2026-10-27",) and st.staged == ()
    assert (staged / "raw" / "date=2026-10-26" / "marker.json").exists()  # still there, and not read
    assert compare_with_fresh(raw, None, staged, tmp_path / "after") == []


def test_a_staged_receipts_day_whose_folder_is_gone_is_ignored(tmp_path):
    """An unchanged receipt for 30 October's board, filed under 31 October, staged, then gone from receipts/: the
    board is confirmed only until its own time again, as in a fresh build."""
    raw, rec, staged = tmp_path / "raw", tmp_path / "receipts", tmp_path / "stage"
    sid = board(raw, rec, at(23, 50, day=30))
    write_receipt(rec, sid, action="unchanged", when=at(0, 10, day=31))
    stage.stage(rules.connect(), raw, rec, staged)
    shutil.rmtree(rec / "date=2026-10-31")

    st = stage.stage(rules.connect(), raw, rec, staged)
    assert st.receipt_days == ("date=2026-10-30",) and st.staged == ()
    assert (staged / "receipts" / "date=2026-10-31" / "marker.json").exists()  # still there, and not read
    assert compare_with_fresh(raw, rec, staged, tmp_path / "after") == []
    assert read(tmp_path / "after" / "staged" / "snapshots.parquet")[0]["confirmed_until"] == at(23, 50, day=30)


@pytest.mark.parametrize("error", [ValueError, KeyboardInterrupt])
@pytest.mark.parametrize("restage", [False, True], ids=["new stage", "restage"])
def test_a_day_whose_marker_was_not_written_is_staged_again(tmp_path, monkeypatch, restage, error):
    """A build stopped by an error or by Ctrl-C while it stages 26 October, after that day's rows.parquet and before its
    counts.parquet (Review Focus 1), on a new stage, or staging again with restage on a current one: the day is not
    taken as staged by the next build."""
    raw, staged = legacy_days(tmp_path)
    if restage:
        stage.stage(rules.connect(), raw, None, staged)
    real = stage._copy

    def stopped(con, query, path):
        if (path.parent.name, path.name) == ("date=2026-10-26", "counts.parquet"):
            raise error("stopped")
        real(con, query, path)

    monkeypatch.setattr(stage, "_copy", stopped)
    with pytest.raises(error):
        stage.stage(rules.connect(), raw, None, staged, restage=restage)
    monkeypatch.setattr(stage, "_copy", real)

    st = stage.stage(rules.connect(), raw, None, staged)
    # Staging again stopped on 26 October; 27 October was staged by the first call and is current.
    assert st.staged == (("raw/date=2026-10-26",) if restage else ("raw/date=2026-10-26", "raw/date=2026-10-27"))
    assert compare_with_fresh(raw, None, staged, tmp_path / "after") == []


def test_a_stopped_write_leaves_no_temporary_file_once_its_day_is_staged_again(tmp_path):
    """A build stopped inside _copy or _mark leaves a file named <name>.<pid>.tmp beside the day's files (Review
    Focus 1): it is removed when that day is staged again. A day that is reused is not touched."""
    raw, staged = legacy_days(tmp_path)
    stage.stage(rules.connect(), raw, None, staged)
    leftovers = ["rows.parquet.12345.tmp", "marker.json.12345.tmp"]
    for day in ("date=2026-10-26", "date=2026-10-27"):
        for name in leftovers:
            (staged / "raw" / day / name).write_bytes(b"stopped")
    board(raw, None, at(7, day=26), "DELAYED")  # 26 October changes; 27 October is reused

    assert stage.stage(rules.connect(), raw, None, staged).staged == ("raw/date=2026-10-26",)
    assert sorted(p.name for p in (staged / "raw" / "date=2026-10-26").iterdir()) == \
        ["counts.parquet", "marker.json", "rows.parquet"]
    assert sorted(p.name for p in (staged / "raw" / "date=2026-10-27").iterdir()) == \
        sorted(["counts.parquet", "marker.json", "rows.parquet", *leftovers])


def test_a_changed_fingerprint_stages_every_day_again(tmp_path, monkeypatch):
    """A stage left by other code, after a branch switch or a DuckDB upgrade (Review Focus 2)."""
    raw, rec, staged = receipted_days(tmp_path)
    stage.stage(rules.connect(), raw, rec, staged)
    monkeypatch.setattr(stage, "fingerprint", lambda *args, **kwargs: "other")
    assert stage.stage(rules.connect(), raw, rec, staged).staged == RECEIPTED_DAYS
    assert stage.stage(rules.connect(), raw, rec, staged).staged == ()  # the markers now carry the other one


def test_the_fingerprint_follows_the_model_source_and_duckdb(tmp_path):
    sources = [MODEL_SOURCE / "rules.py", MODEL_SOURCE / "stage.py"]
    (tmp_path / "copy").mkdir()
    copies = [Path(shutil.copy(source, tmp_path / "copy" / source.name)) for source in sources]
    first = stage.fingerprint(copies)
    assert len(first) == 64 and set(first) <= set("0123456789abcdef")  # SHA-256 in hex
    assert stage.fingerprint(sources) == first  # each file's name and bytes, not its folder
    assert stage.fingerprint(copies[::-1]) == first  # in name order
    text = copies[1].read_bytes()
    copies[1].write_bytes(text[:-1] + bytes([text[-1] ^ 1]))  # one byte changed
    assert stage.fingerprint(copies) != first
    copies[1].write_bytes(text)
    assert stage.fingerprint(copies) == first
    renamed = copies[1].rename(copies[1].with_name("other.py"))
    assert stage.fingerprint([copies[0], renamed]) != first  # the name counts too
    assert stage.fingerprint(sources, duckdb_version="0.0.0") != first
    assert stage.fingerprint(sources, duckdb_version=duckdb.__version__) == first

    # By default, every source file of the model.
    assert Path(stage.__file__).resolve().parent == MODEL_SOURCE
    model_sources = sorted(MODEL_SOURCE.glob("*.py"))
    assert {"rules.py", "stage.py", "build.py"} <= {p.name for p in model_sources}
    assert stage.fingerprint() == stage.fingerprint(model_sources)


def _damage(day: Path, how: str) -> None:
    if how == "empty marker":
        (day / "marker.json").write_text("")
    elif how == "marker not JSON":
        (day / "marker.json").write_text('{"fingerprint": "')  # cut short
    elif how == "marker without files":
        (day / "marker.json").write_text(json.dumps({"fingerprint": stage.fingerprint()}))
    elif how == "marker a JSON list":
        (day / "marker.json").write_text(json.dumps([stage.fingerprint(), []]))
    else:  # a current marker; the day's staged file deleted by hand
        (day / ("rows.parquet" if day.parent.name == "raw" else "receipts.parquet")).unlink()


@pytest.mark.parametrize("how", ["empty marker", "marker not JSON", "marker without files", "marker a JSON list",
                                 "staged file deleted"])
def test_a_damaged_stage_is_staged_again(tmp_path, how):
    """A zero-byte or hand-edited marker, or a staged file deleted by hand (Review Focus 2): never trusted, and never
    stopping the build."""
    raw, rec, staged = receipted_days(tmp_path)
    stage.stage(rules.connect(), raw, rec, staged)
    for day in sorted(staged.glob("*/date=*")):
        _damage(day, how)
    assert stage.stage(rules.connect(), raw, rec, staged).staged == RECEIPTED_DAYS


def test_restage_stages_every_day(tmp_path, monkeypatch):
    raw, rec, staged = receipted_days(tmp_path)
    stage.stage(rules.connect(), raw, rec, staged)
    assert stage.stage(rules.connect(), raw, rec, staged, restage=True).staged == RECEIPTED_DAYS

    # The build passes the option on to the stage.
    written = []
    real = stage._copy
    monkeypatch.setattr(stage, "_copy",
                        lambda con, query, path: written.append(path.relative_to(staged).as_posix()) or real(con, query, path))
    build.build(raw, tmp_path / "model", rec, stage_dir=staged, restage=True)
    assert written == ["raw/date=2026-10-30/rows.parquet", "raw/date=2026-10-30/counts.parquet",
                       "raw/date=2026-10-31/rows.parquet", "raw/date=2026-10-31/counts.parquet",
                       "receipts/date=2026-10-30/receipts.parquet", "receipts/date=2026-10-31/receipts.parquet"]
