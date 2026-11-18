"""The build's own work (docs/lighter-build.md, "The design", 3, and "For the owner", question 4): DuckDB's memory limit,
threads and temp folder, the command line's options, and the model folder written whole or not at all. The rules and
the stage have their own tests (tests/test_model.py, tests/test_model_receipts.py, tests/test_model_stage.py)."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import duckdb
import pytest

from model import build
from model_helpers import at, row, write_receipt, write_snapshot

MODEL_FILES = sorted(f"{table}.parquet" for table in build.TABLES)


@pytest.fixture(autouse=True)
def system_temp(tmp_path, monkeypatch) -> Path:
    """The system's temp folder, where model.build.build makes its temporary stage and DuckDB temp folder: here a
    folder under tmp_path, so a test can see what is left in it."""
    folder = tmp_path / "systmp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


def archive(base: Path, status: str = "ON TIME") -> tuple[Path, Path, str]:
    """(raw, receipts, snapshot id) of an archive under `base`: one board of one row on 30 October, with its
    stored receipt."""
    raw, rec = base / "raw", base / "receipts"
    sid = write_snapshot(raw, at(6, day=30), [row(status=status)])
    write_receipt(rec, sid)
    return raw, rec, sid


def files(folder: Path) -> dict[str, bytes]:
    """Each file in `folder`, by name, with its bytes."""
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def snapshot_ids(model: Path) -> list[str]:
    return [r[0] for r in duckdb.connect().execute(
        f"SELECT snapshot_id FROM read_parquet('{model / 'snapshots.parquet'}') ORDER BY 1").fetchall()]


def no_leftovers(out: Path) -> bool:
    """Whether neither <out>.building nor <out>.old is there."""
    return not out.with_name(out.name + ".building").exists() and not out.with_name(out.name + ".old").exists()


# --- the connection: DuckDB's memory limit, threads and temp folder ---------------------------------------------------

def test_the_connection_takes_the_limits_given(tmp_path):
    spill = tmp_path / "o'hare spill"  # a quote and a space: the path's quotes are doubled in the SQL (Review Focus 4)
    con = build.connect(spill, "512MB", 3)
    got = con.execute("SELECT current_setting('memory_limit'), current_setting('threads'), "
                      "current_setting('temp_directory')").fetchone()
    assert got == ("488.2 MiB", 3, str(spill))
    assert con.execute("SELECT current_setting('TimeZone')").fetchone() == ("UTC",)  # the rules' own connection


def test_the_defaults_are_1_gb_and_2_threads(tmp_path):
    con = build.connect(tmp_path)
    assert con.execute("SELECT current_setting('memory_limit'), current_setting('threads')").fetchone() == ("953.6 MiB", 2)


# --- the command line -------------------------------------------------------------------------------------------------

def recording(monkeypatch) -> list[dict]:
    """model.build.build replaced by a fake that records the keyword arguments of each call and returns counts."""
    calls: list[dict] = []
    monkeypatch.setattr(build, "build", lambda **kwargs: calls.append(kwargs) or {"flights": 1})
    return calls


def test_main_passes_its_defaults(tmp_path, monkeypatch):
    raw, _, _ = archive(tmp_path)
    calls = recording(monkeypatch)
    assert build.main(["--raw", str(raw), "--out", str(tmp_path / "model")]) == 0
    assert calls == [{"raw_dir": raw, "out_dir": tmp_path / "model", "receipts_dir": tmp_path / "receipts",
                      "stage_dir": tmp_path / "stage", "restage": False, "memory_limit": "1GB", "threads": 2,
                      "temp_dir": None}]


def test_main_passes_every_option(tmp_path, monkeypatch):
    raw, _, _ = archive(tmp_path)
    calls = recording(monkeypatch)
    assert build.main(["--raw", str(raw), "--out", str(tmp_path / "model"), "--receipts", str(tmp_path / "rec"),
                       "--stage", str(tmp_path / "st"), "--restage", "--memory-limit", "512MB", "--threads", "3",
                       "--temp-dir", str(tmp_path / "spill")]) == 0
    assert calls == [{"raw_dir": raw, "out_dir": tmp_path / "model", "receipts_dir": tmp_path / "rec",
                      "stage_dir": tmp_path / "st", "restage": True, "memory_limit": "512MB", "threads": 3,
                      "temp_dir": tmp_path / "spill"}]


def test_main_still_stops_on_an_archive_with_no_snapshot_files(tmp_path, monkeypatch):
    calls = recording(monkeypatch)
    (tmp_path / "raw").mkdir()
    assert build.main(["--raw", str(tmp_path / "raw"), "--out", str(tmp_path / "model")]) == 2
    assert calls == []


# --- temp folders -----------------------------------------------------------------------------------------------------

def test_no_temp_file_under_the_working_directory(tmp_path, system_temp, monkeypatch):
    """DuckDB spills into the folder it is given, a new one under the system's temp folder by default, never .tmp/
    under the working directory; that folder and the temporary stage are removed after the build."""
    raw, rec, _ = archive(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    seen: list[Path] = []
    real = build.connect

    def connect(*args, **kwargs):
        con = real(*args, **kwargs)
        seen.append(Path(con.execute("SELECT current_setting('temp_directory')").fetchone()[0]))
        return con

    monkeypatch.setattr(build, "connect", connect)
    build.build(raw, tmp_path / "model", rec)
    assert len(seen) == 1 and seen[0].parent == system_temp and seen[0].name.startswith("model-build-")
    assert list(system_temp.iterdir()) == []
    assert list(cwd.iterdir()) == []


# --- the model folder: written whole or not at all --------------------------------------------------------------------

def stop_at_the_third_table(monkeypatch, error: type[BaseException]) -> None:
    """model.build._copy_out made to raise `error` when it comes to the third table."""
    real = build._copy_out

    def copy_out(con, table, path):
        if table == build.TABLES[2]:
            raise error("stopped while writing the third table")
        real(con, table, path)

    monkeypatch.setattr(build, "_copy_out", copy_out)


@pytest.mark.parametrize("error", [ValueError, KeyboardInterrupt])
def test_a_failed_build_leaves_the_last_model_as_it_was(tmp_path, system_temp, monkeypatch, error):
    """A build stopped while writing the model, by an error or by Ctrl-C (Review Focus 1): the last model stays
    whole, nothing is left beside it, and the temporary folders are removed."""
    out = tmp_path / "model"
    raw, rec, _ = archive(tmp_path / "first")
    build.build(raw, out, rec)
    before = files(out)
    raw, rec, _ = archive(tmp_path / "second", status="DELAYED")  # another board, so a model written in place shows
    stop_at_the_third_table(monkeypatch, error)
    with pytest.raises(error, match="the third table"):
        build.build(raw, out, rec)
    assert files(out) == before
    assert no_leftovers(out)
    assert list(system_temp.iterdir()) == []


def test_a_stop_between_the_renames_keeps_the_last_model(tmp_path, monkeypatch):
    """A build killed after <out> moved to <out>.old and before <out>.building moved in leaves no <out>, and
    <out>.old is then the last whole model (Review Focus 1). The next build puts it back first, so that one failing
    too still leaves the last model in place."""
    out = tmp_path / "model"
    raw, rec, _ = archive(tmp_path / "first")
    build.build(raw, out, rec)
    before = files(out)
    out.rename(tmp_path / "model.old")
    (tmp_path / "model.building").mkdir()
    (tmp_path / "model.building" / "snapshots.parquet").write_bytes(b"the new model, cut short")
    raw, rec, _ = archive(tmp_path / "second", status="DELAYED")
    stop_at_the_third_table(monkeypatch, ValueError)
    with pytest.raises(ValueError, match="the third table"):
        build.build(raw, out, rec)
    assert files(out) == before
    assert no_leftovers(out)


def test_a_refused_archive_leaves_the_last_model_as_it_was(tmp_path):
    out = tmp_path / "model"
    raw, rec, _ = archive(tmp_path / "first")
    build.build(raw, out, rec)
    before = files(out)
    raw, rec = tmp_path / "refused" / "raw", tmp_path / "refused" / "receipts"
    write_receipt(rec, write_snapshot(raw, at(6, day=30), [row()]), rows=2)  # the receipt counts two rows, the file one
    with pytest.raises(ValueError, match="differ from their files"):
        build.build(raw, out, rec)
    assert files(out) == before
    assert no_leftovers(out)


def test_a_new_model_replaces_the_old_one_whole(tmp_path):
    out = tmp_path / "model"
    raw, rec, first = archive(tmp_path / "first")
    build.build(raw, out, rec)
    assert snapshot_ids(out) == [first]
    raw, rec, second = archive(tmp_path / "second", status="DELAYED")
    build.build(raw, out, rec)
    assert sorted(p.name for p in out.iterdir()) == MODEL_FILES
    assert snapshot_ids(out) == [second]
    assert no_leftovers(out)


def test_leftovers_of_a_killed_build_are_cleared(tmp_path):
    out = tmp_path / "model"
    for leftover in ("model.building", "model.old"):
        (tmp_path / leftover).mkdir()
        (tmp_path / leftover / "flights.parquet").write_bytes(b"half written")
    raw, rec, sid = archive(tmp_path / "archive")
    build.build(raw, out, rec)
    assert no_leftovers(out)
    assert sorted(p.name for p in out.iterdir()) == MODEL_FILES
    assert snapshot_ids(out) == [sid]


@pytest.mark.parametrize("folder, foreign", [("model", "notes.txt"), ("model.building", "notes.txt"),
                                             ("model.old", "notes.txt"), ("model", "flights.parquet/")])
def test_a_folder_that_is_not_a_model_is_never_replaced(tmp_path, folder, foreign):
    """`--out data` must not delete the archive copy (Review Focus 5): a folder holding anything but the model's
    table files, a folder named like a table included, is refused, before any work, with nothing moved or deleted."""
    out = tmp_path / "model"
    raw, rec, _ = archive(tmp_path / "archive")
    (tmp_path / folder).mkdir()
    (tmp_path / folder / "snapshots.parquet").write_bytes(b"a table")
    name = foreign.rstrip("/")
    mine = tmp_path / folder / name / "notes.txt" if foreign.endswith("/") else tmp_path / folder / name
    mine.parent.mkdir(exist_ok=True)
    mine.write_text("mine")
    refusal = re.escape(f"{tmp_path / folder} holds files that are not a model's: ['{name}']; refusing to replace it")
    with pytest.raises(ValueError, match=refusal):
        build.build(raw, out, rec, stage_dir=tmp_path / "stage")
    assert not (tmp_path / "stage").exists()  # refused before any staging
    with pytest.raises(ValueError, match=refusal):
        build.write_model(None, out)  # refused on its own, before the connection is read
    assert mine.read_text() == "mine"
    assert sorted(p.name for p in (tmp_path / folder).iterdir()) == sorted([name, "snapshots.parquet"])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["archive", folder, "systmp"]
