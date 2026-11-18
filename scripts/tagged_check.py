"""The tagged check: the model build as tag record-v1 holds it and the current build, run on one copy of the archive,
and their two model folders compared four ways (docs/lighter-build.md, "The frozen record"):

1. each of the five tables (`model.build.TABLES`) has the same column names and types, in the same order;
2. each holds the same rows, repeats counted: the rows of either that the other lacks, checked both ways, every
   column, exact values;
3. `timeline.load.load` returns equal lists from both;
4. `timeline.record` writes the same progress.json, byte for byte, and exits with the same code.

Row order inside the files is not compared: it is not stable from one build to the next. The tagged rules are
tests/fixtures/rules_record_v1.py, record-v1's src/model/rules.py byte for byte, and a copy whose SHA-256 is not
TAGGED_SHA256 is refused. A cut of the archive keeps the first floor(N x fraction) snapshot folders in path-time
order. Local only: the archive is not in the repository. Run from the repository root:

    PYTHONPATH=src .venv/bin/python scripts/tagged_check.py --work DIR [--raw data/raw] [--receipts data/receipts] \
        [--fractions 0.25 0.5 0.75 1]
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
import sys
import types
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import duckdb

from model.build import TABLES
from timeline import record
from timeline.load import load

ROOT = Path(__file__).resolve().parent.parent
# tests/model_helpers.py holds the rule for a collector path's time that the tests' archive cuts use (cut_archive).
# The script reads it from there, so that the tests and the script cut an archive by one rule.
if str(ROOT / "tests") not in sys.path:
    sys.path.append(str(ROOT / "tests"))
from model_helpers import _path_time  # noqa: E402

TAGGED_RULES = ROOT / "tests" / "fixtures" / "rules_record_v1.py"
# The SHA-256 of `git show record-v1:src/model/rules.py`
TAGGED_SHA256 = "57a07619159113601e3ac9311a7ccd69ee27f93fc1a57ad7860d20a4c6bf4162"
LOAD_PARTS = ("flights", "observations", "snapshots")  # the three lists timeline.load.load returns, in its order


def _sql(path: Path) -> str:
    """A path inside an SQL string literal: its quotes doubled."""
    return str(path).replace("'", "''")


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    return con


def tagged_rules() -> types.ModuleType:
    """The tagged rules: the fixture as a new module `rules_record_v1` on every call, run from the bytes whose
    SHA-256 was checked. ValueError, naming both hashes, when that is not TAGGED_SHA256."""
    source = TAGGED_RULES.read_bytes()
    found = hashlib.sha256(source).hexdigest()
    if found != TAGGED_SHA256:
        raise ValueError(f"{TAGGED_RULES} has SHA-256 {found}; record-v1's src/model/rules.py has {TAGGED_SHA256}")
    spec = importlib.util.spec_from_file_location("rules_record_v1", TAGGED_RULES)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, str(TAGGED_RULES), "exec", dont_inherit=True), module.__dict__)
    return module


def build_tagged(raw: Path, receipts: Path | None, out: Path, temp_dir: Path,
                 known_orphans: frozenset[str] = frozenset()) -> dict[str, int]:
    """The tagged build of raw/ and receipts/ into out/, as src/model/build.py ran it at the tag, with
    `known_orphans` as the tagged rules' KNOWN_ORPHANS. DuckDB's temp folder is set to temp_dir: that changes where
    the build spills, not what it computes. Returns build_all's row counts."""
    rules = tagged_rules()
    rules.KNOWN_ORPHANS = known_orphans
    con = rules.connect()
    try:
        con.execute(f"SET temp_directory = '{_sql(temp_dir)}'")
        counts = rules.build_all(con, f"{raw}/**/*.json.gz", None if receipts is None else f"{receipts}/**/*.json")
        out.mkdir(parents=True, exist_ok=True)
        for table in TABLES:
            con.execute(f"COPY {table} TO '{_sql(out / f'{table}.parquet')}' (FORMAT PARQUET)")
    finally:
        con.close()
    return counts


def _columns(con: duckdb.DuckDBPyConnection, file: str) -> list[tuple[str, str]]:
    return [(name, kind) for name, kind, *_ in con.execute(f"DESCRIBE SELECT * FROM '{file}'").fetchall()]


def compare_tables(a: Path, b: Path, names: tuple[str, str] = ("tagged", "new")) -> list[str]:
    """Checks 1 and 2 on model folders a and b, called `names` in the lines: one line per difference, [] when the
    same. A table whose columns or types differ, order included, is reported so, and its rows are not compared."""
    con = _connect()
    lines = []
    try:
        for table in TABLES:
            files = [_sql(folder / f"{table}.parquet") for folder in (a, b)]
            cols = [_columns(con, file) for file in files]
            if cols[0] != cols[1]:
                lines.append(f"{table}: columns differ: {names[0]} {cols[0]}, {names[1]} {cols[1]}")
                continue
            for (this, other), name in zip((files, files[::-1]), names):
                only = f"SELECT * FROM '{this}' EXCEPT ALL SELECT * FROM '{other}'"
                n = con.execute(f"SELECT count(*) FROM ({only})").fetchone()[0]
                if n:
                    lines.append(f"{table}: {n:,} row{'s' if n != 1 else ''} only in {name}")
    finally:
        con.close()
    return lines


def compare_load(a: Path, b: Path) -> list[str]:
    """Check 3: one line for each of timeline.load.load's lists that differs between model folders a and b."""
    left, right = (dict(zip(LOAD_PARTS, load(folder))) for folder in (a, b))
    return [f"load(): {part} differ" for part in LOAD_PARTS if left[part] != right[part]]


def compare_progress(a: Path, b: Path, work: Path, names: tuple[str, str] = ("tagged", "new")) -> list[str]:
    """Check 4: timeline.record run in this process on model folders a and b, into work/<name>/ for each of
    `names`; a line when the exit codes differ, and one when the two progress.json files are not the same bytes."""
    codes = [record.main(["--model", str(model), "--out", str(work / name)]) for model, name in zip((a, b), names)]
    first, second = ((work / name / record.TAG / "progress.json") for name in names)
    first, second = (p.read_bytes() if p.exists() else None for p in (first, second))
    lines = []
    if codes[0] != codes[1]:
        lines.append(f"timeline.record exit codes differ: {codes[0]} and {codes[1]}")
    if first != second:
        lines.append("progress.json differs")
    return lines


class Cut(NamedTuple):
    fraction: float
    kept: int  # the first `kept` snapshot folders in path-time order
    total: int  # of this many
    moment: datetime  # the path time of the last one kept


def cut_moments(raw: Path, fractions: Sequence[float]) -> list[Cut]:
    """For each fraction, the cut of raw/ that keeps the first floor(total x fraction) snapshot folders
    (raw/date=*/*Z-*) in path-time order, and the moment it stops at. ValueError for a fraction that keeps none, or
    more than there are."""
    times = sorted(_path_time(folder.parent, folder.name) for folder in raw.glob("date=*/*Z-*") if folder.is_dir())
    cuts = []
    for fraction in fractions:
        kept = math.floor(len(times) * fraction)
        if not 0 < kept <= len(times):
            raise ValueError(f"a cut at {fraction} keeps {kept} of {len(times)} snapshot folders")
        cuts.append(Cut(fraction, kept, len(times), times[kept - 1]))
    return cuts
