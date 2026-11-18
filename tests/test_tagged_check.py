"""The tagged check (scripts/tagged_check.py): the model rules as tag record-v1 holds them, kept as
tests/fixtures/rules_record_v1.py with their SHA-256 pinned, build an archive as the tagged build did, and four checks
compare two model folders (docs/lighter-build.md, "The frozen record"): the tables' columns and types, their rows
with repeats counted, both ways, what `timeline.load.load` returns, and `timeline.record`'s progress.json.

Here on tiny archives in the collector's layout (tests/model_helpers.py), and on copies of one model folder with one
thing changed in one table.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
from datetime import timedelta
from pathlib import Path

import duckdb
import pytest

from model import build as model_build
from model import rules
from model.build import TABLES
from model_helpers import at, row, write_receipt, write_snapshot
from timeline import record

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "tagged_check.py"
RECORD_V1_SHA256 = "57a07619159113601e3ac9311a7ccd69ee27f93fc1a57ad7860d20a4c6bf4162"  # record-v1's src/model/rules.py
# One column of each table, changed in one row of a copy: a count, a count, a status, a status, a count.
CHANGED = {"snapshots": "rows", "snapshot_runs": "identical_repeats", "observations": "status",
           "flights": "final_status", "receipts": "rows"}


def load_script():
    spec = importlib.util.spec_from_file_location("tagged_check_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check():
    return load_script()


def write_archive(root: Path) -> tuple[Path, Path]:
    """Two boards with their receipts and an unchanged receipt between them, so that every table has rows."""
    raw, receipts = root / "raw", root / "receipts"
    first = write_snapshot(raw, at(6), [row(), row(airline="EY", flight_no="607")])
    write_receipt(receipts, first, rows=2)
    write_receipt(receipts, first, action="unchanged", when=at(6, 15))
    second = write_snapshot(raw, at(6, 30), [row(status="DELAYED"), row(airline="EY", flight_no="607")])
    write_receipt(receipts, second, rows=2)
    return raw, receipts


@pytest.fixture(scope="module")
def model(check, tmp_path_factory) -> Path:
    """The tagged build of write_archive's archive. Tests change copies of it, never the folder itself."""
    root = tmp_path_factory.mktemp("tagged")
    raw, receipts = write_archive(root)
    check.build_tagged(raw, receipts, root / "model", root / "duckdb-tmp")
    return root / "model"


def columns(file: Path) -> list[tuple[str, str]]:
    return [(name, kind) for name, kind, *_ in duckdb.connect().execute(f"DESCRIBE SELECT * FROM '{file}'").fetchall()]


def copy_model(model: Path, dest: Path, table: str | None = None, select: str = "SELECT * FROM t") -> Path:
    """A copy of the model folder at dest, with `table`'s file written again from `select`, which reads that table
    as t."""
    shutil.copytree(model, dest)
    if table is not None:
        con = duckdb.connect()
        con.execute("SET TimeZone = 'UTC'")
        con.execute(f"CREATE TABLE t AS SELECT * FROM '{model / f'{table}.parquet'}'")
        con.execute(f"COPY ({select}) TO '{dest / f'{table}.parquet'}' (FORMAT PARQUET)")
    return dest


def one_value_changed(model: Path, table: str) -> str:
    """A select over t that changes CHANGED[table] in t's first row and keeps its type."""
    column = CHANGED[table]
    kind = dict(columns(model / f"{table}.parquet"))[column]
    new = f"""coalesce("{column}", 0) + 1""" if kind == "BIGINT" else f"""coalesce("{column}", '') || ' (changed)'"""
    return f"""SELECT * EXCLUDE (n_) REPLACE (CASE WHEN n_ = 1 THEN {new} ELSE "{column}" END AS "{column}")
               FROM (SELECT *, row_number() OVER () AS n_ FROM t)"""


def test_the_fixture_is_the_tagged_rules_byte_for_byte(check):
    assert hashlib.sha256(check.TAGGED_RULES.read_bytes()).hexdigest() == RECORD_V1_SHA256 == check.TAGGED_SHA256
    assert check.TAGGED_RULES == ROOT / "tests" / "fixtures" / "rules_record_v1.py"


def test_a_changed_fixture_is_refused(check, tmp_path, monkeypatch):
    changed = bytearray(check.TAGGED_RULES.read_bytes())
    changed[changed.index(b"rules")] = ord("R")  # in the docstring: still Python, one byte different
    copy = tmp_path / "rules_record_v1.py"
    copy.write_bytes(changed)
    monkeypatch.setattr(check, "TAGGED_RULES", copy)
    with pytest.raises(ValueError, match="SHA-256") as refused:
        check.tagged_rules()
    assert RECORD_V1_SHA256 in str(refused.value) and hashlib.sha256(changed).hexdigest() in str(refused.value)


def test_the_tagged_rules_are_the_fixture_loaded(check):
    tagged = check.tagged_rules()
    assert tagged.__name__ == "rules_record_v1" and tagged is not rules
    assert tagged.KNOWN_ORPHANS == frozenset() and callable(tagged.build_all)


def test_the_tagged_build_writes_the_five_tables(check, tmp_path):
    raw, receipts = write_archive(tmp_path)
    counts = check.build_tagged(raw, receipts, tmp_path / "model", tmp_path / "duckdb-tmp")
    assert sorted(p.name for p in (tmp_path / "model").iterdir()) == sorted(f"{t}.parquet" for t in TABLES)
    assert counts == {"snapshots": 2, "observations": 3, "flights": 2, "receipts": 3}


def test_the_tagged_build_drops_the_known_orphans_given(check, tmp_path, monkeypatch):
    """The archive of tests/test_model_receipts.py's test_a_known_orphan_is_dropped: b has pages and no receipt."""
    raw, receipts = tmp_path / "raw", tmp_path / "receipts"
    a = write_snapshot(raw, at(6), [row()])
    b = write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    c = write_snapshot(raw, at(6, 30), [row(status="BOARDING")])
    write_receipt(receipts, a)
    write_receipt(receipts, c)
    check.build_tagged(raw, receipts, tmp_path / "model", tmp_path / "duckdb-tmp", known_orphans=frozenset({b}))
    runs = duckdb.connect().execute(f"SELECT snapshot_id, receipt FROM '{tmp_path / 'model'}/snapshot_runs.parquet'")
    assert dict(runs.fetchall()) == {a: "receipted", b: "orphan", c: "receipted"}
    # Without it, refused: neither the last call's set nor the current rules' set reaches the tagged build.
    monkeypatch.setattr(rules, "KNOWN_ORPHANS", frozenset({b}))
    with pytest.raises(ValueError, match=rf"no receipt.*{b}"):
        check.build_tagged(raw, receipts, tmp_path / "refused", tmp_path / "duckdb-tmp")


def test_one_archive_compares_equal(check, tmp_path):
    raw, receipts = write_archive(tmp_path)
    check.build_tagged(raw, receipts, tmp_path / "tagged", tmp_path / "duckdb-tmp")
    model_build.build(raw, tmp_path / "new", receipts)
    assert check.compare_tables(tmp_path / "tagged", tmp_path / "new") == []
    assert check.compare_load(tmp_path / "tagged", tmp_path / "new") == []


@pytest.mark.parametrize("table", TABLES)
def test_one_changed_value_is_found_in_each_table(check, model, tmp_path, table):
    copy = copy_model(model, tmp_path / "copy", table, one_value_changed(model, table))
    assert columns(copy / f"{table}.parquet") == columns(model / f"{table}.parquet")
    assert check.compare_tables(model, copy) == [f"{table}: 1 row only in tagged", f"{table}: 1 row only in new"]


def test_a_repeated_row_is_found(check, model, tmp_path):
    copy = copy_model(model, tmp_path / "copy", "observations", "SELECT * FROM t UNION ALL (SELECT * FROM t LIMIT 1)")
    assert check.compare_tables(model, copy) == ["observations: 1 row only in new"]


def test_a_missing_row_is_found_both_ways(check, model, tmp_path):
    copy = copy_model(model, tmp_path / "copy", "flights",
                      "SELECT * EXCLUDE (n_) FROM (SELECT *, row_number() OVER () AS n_ FROM t) WHERE n_ > 1")
    assert check.compare_tables(model, copy) == ["flights: 1 row only in tagged"]
    assert check.compare_tables(copy, model) == ["flights: 1 row only in new"]


def test_the_counts_and_names_in_a_line(check, model, tmp_path):
    copy = copy_model(model, tmp_path / "copy", "observations", "SELECT * FROM t UNION ALL SELECT * FROM t")
    assert check.compare_tables(model, copy, names=("old", "staged")) == ["observations: 3 rows only in staged"]


def test_a_changed_column_type_is_found(check, model, tmp_path):
    assert dict(columns(model / "snapshot_runs.parquet"))["identical_repeats"] == "BIGINT"
    copy = copy_model(model, tmp_path / "copy", "snapshot_runs",
                      "SELECT * REPLACE (CAST(identical_repeats AS INTEGER) AS identical_repeats) FROM t")
    found = check.compare_tables(model, copy)
    assert len(found) == 1 and found[0].startswith("snapshot_runs: columns differ: tagged [")
    assert "('identical_repeats', 'BIGINT')" in found[0] and "('identical_repeats', 'INTEGER')" in found[0]


def test_load_differences_are_found(check, model, tmp_path):
    copy = copy_model(model, tmp_path / "copy", "observations", one_value_changed(model, "observations"))
    assert check.compare_load(model, copy) == ["load(): observations differ"]


def test_equal_models_give_the_same_progress(check, model, tmp_path):
    work = tmp_path / "work"
    assert check.compare_progress(model, copy_model(model, tmp_path / "copy"), work) == []
    assert all((work / name / record.TAG / "progress.json").is_file() for name in ("tagged", "new"))


def fake_record_main(second: Path, progress: str, code: int):
    """A stand-in for timeline.record.main that writes `progress` and returns `code` for the model `second`, and
    writes "{}" and returns 0 for any other."""
    def main(argv: list[str]) -> int:
        model, out = Path(argv[argv.index("--model") + 1]), Path(argv[argv.index("--out") + 1]) / record.TAG
        out.mkdir(parents=True)
        (out / "progress.json").write_text(progress if model == second else "{}\n", encoding="utf-8")
        return code if model == second else 0
    return main


def test_progress_differences_are_found(check, model, tmp_path, monkeypatch):
    copy = copy_model(model, tmp_path / "copy")
    monkeypatch.setattr(record, "main", fake_record_main(copy, '{"row_cancelled": 1}\n', 0))
    assert check.compare_progress(model, copy, tmp_path / "work") == ["progress.json differs"]


def test_exit_code_differences_are_found(check, model, tmp_path, monkeypatch):
    copy = copy_model(model, tmp_path / "copy")
    monkeypatch.setattr(record, "main", fake_record_main(copy, "{}\n", 1))
    assert check.compare_progress(model, copy, tmp_path / "work") == ["timeline.record exit codes differ: 0 and 1"]


def test_cut_moments_take_the_floor(check, tmp_path):
    fractions = [0.25, 0.5, 0.75, 1]
    for total, kept in [(7, [1, 3, 5, 7]), (8, [2, 4, 6, 8])]:
        raw = tmp_path / str(total) / "raw"
        times = [at(22) + timedelta(minutes=37 * i) for i in range(total)]  # 27 and 28 October
        for t in reversed(times):
            write_snapshot(raw, t, [row()])
        assert {t.date() for t in times} == {at(0).date(), at(0, day=28).date()}
        expected = [check.Cut(f, k, total, times[k - 1]) for f, k in zip(fractions, kept)]
        assert check.cut_moments(raw, fractions) == expected


@pytest.mark.parametrize("fraction", [0.1, 1.2])
def test_a_cut_of_no_folder_or_past_the_last_is_refused(check, tmp_path, fraction):
    raw = tmp_path / "raw"
    for i in range(7):
        write_snapshot(raw, at(6) + timedelta(minutes=15 * i), [row()])
    with pytest.raises(ValueError, match=f"a cut at {fraction} keeps"):
        check.cut_moments(raw, [fraction])
