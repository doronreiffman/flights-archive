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

--work is a new or empty folder outside raw/ and receipts/. It refuses to run when the fixture is not the pinned one,
when tag record-v1 is in this clone and holds other bytes, or when two fractions name one archive. It prints the commit
compared and whether src/model, this script or the fixture hold changes not committed. Each fraction's archive (quarter, half, three quarters, whole) gets a folder of its
own under --work: the cut copied into archive/ (the whole archive is read where it is), then the tagged build into
tagged/ and the current build into new/, each in a process of its own so that one build's memory goes back to the
system before the next, its output in tagged.log or new.log. The four checks follow. Exit 0 when every archive is
identical, 1 when any differs or a build fails, 2 when it refuses to run.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import math
import os
import subprocess
import sys
import time
import types
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import duckdb

from model import rules
from model.build import TABLES
from timeline import record
from timeline.load import load

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).resolve()
# tests/model_helpers.py holds the tests' archive cut (cut_archive) and the rule for a collector path's time it uses.
# The script imports both from there, so that the tests and the script cut an archive by one rule.
if str(ROOT / "tests") not in sys.path:
    sys.path.append(str(ROOT / "tests"))
from model_helpers import _path_time, cut_archive  # noqa: E402

TAGGED_RULES = ROOT / "tests" / "fixtures" / "rules_record_v1.py"
# The SHA-256 of `git show record-v1:src/model/rules.py`
TAGGED_SHA256 = "57a07619159113601e3ac9311a7ccd69ee27f93fc1a57ad7860d20a4c6bf4162"
TAG = "record-v1"
# What either build runs: the current model, this script (the tagged build's code) and the tagged rules
BUILD_CODE = ("src/model", "scripts/tagged_check.py", "tests/fixtures/rules_record_v1.py")
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
    `names`; a line when the exit codes differ, one for each side that wrote no progress.json, and one when the two
    progress.json files are not the same bytes."""
    codes = [record.main(["--model", str(model), "--out", str(work / name)]) for model, name in zip((a, b), names)]
    first, second = ((work / name / record.TAG / "progress.json") for name in names)
    first, second = (p.read_bytes() if p.exists() else None for p in (first, second))
    lines = []
    if codes[0] != codes[1]:
        lines.append(f"timeline.record exit codes differ: {codes[0]} and {codes[1]}")
    for name, found in zip(names, (first, second)):
        if found is None:  # two runs that both write nothing are not the same progress
            lines.append(f"progress.json missing for {name}")
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


def tag_rules() -> bytes | None:
    """src/model/rules.py as tag record-v1 holds it (`git -C ROOT show`), or None when git or the tag is not in this
    clone (CI clones without tags)."""
    try:
        done = subprocess.run(["git", "-C", str(ROOT), "show", f"{TAG}:src/model/rules.py"], capture_output=True)
    except OSError:  # no git
        return None
    return done.stdout if done.returncode == 0 else None


def code_line() -> str:
    """The code being compared, printed beside the fixture line: this checkout's commit, and whether the files either
    build runs (BUILD_CODE) hold changes not committed. Not a refusal."""
    git = ["git", "-C", str(ROOT)]
    try:
        head = subprocess.run([*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        status = subprocess.run([*git, "status", "--porcelain", "--", *BUILD_CODE], capture_output=True, text=True)
    except OSError:  # no git
        return "code: git not available, so the commit compared is not known"
    for done in (head, status):
        if done.returncode != 0:
            why = (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
            return f"code: git could not tell the commit compared ({why})"
    changed = [line[3:] for line in status.stdout.splitlines()]  # "XY path": the path after the two status letters
    return f"code {head.stdout.strip()}: " + (f"UNCOMMITTED CHANGES in {', '.join(changed)}" if changed
                                               else f"clean ({', '.join(BUILD_CODE)})")


def run_tagged_build(argv: list[str]) -> int:
    """The child mode, `tagged_check.py tagged-build`: build_tagged on one archive, with the KNOWN_ORPHANS of today's
    rules (model.rules), the snapshots the archive is known to hold with no receipt."""
    parser = argparse.ArgumentParser(prog="tagged_check.py tagged-build",
                                     description="The tagged build of one archive, in a process of its own.")
    for option in ("--raw", "--receipts", "--out", "--temp-dir"):
        parser.add_argument(option, type=Path, required=True)
    args = parser.parse_args(argv)
    counts = build_tagged(args.raw, args.receipts, args.out, args.temp_dir, known_orphans=rules.KNOWN_ORPHANS)
    for table, n in counts.items():
        print(f"{table}: {n} rows -> {args.out / table}.parquet")
    return 0


LABELS = {0.25: "quarter", 0.5: "half", 0.75: "three quarters", 1: "whole"}  # any other fraction by its value
IDENTICAL = "identical: columns, rows, load(), progress.json"


def _shown(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _snapshot_folders(raw: Path) -> int:
    """How many snapshot folders raw/ holds, counted as cut_moments counts them."""
    return sum(1 for folder in raw.glob("date=*/*Z-*") if folder.is_dir())


def _row_counts(model: Path) -> list[int]:
    """Each table's row count in a model folder, in TABLES' order."""
    con = _connect()
    try:
        return [con.execute(f"SELECT count(*) FROM '{_sql(model / f'{t}.parquet')}'").fetchone()[0] for t in TABLES]
    finally:
        con.close()


def _build(name: str, args: list[str], folder: Path) -> tuple[float, str | None]:
    """One build: `python args` as a process of its own in `folder`, with ROOT/src first on its PYTHONPATH, so that it
    runs this checkout's code, and its output in folder/<name>.log. Returns its wall time in seconds, and None, or,
    when it exits non-zero, the difference line: its exit code and the last line of its output."""
    log = folder / f"{name}.log"
    path = os.pathsep.join(p for p in (str(ROOT / "src"), os.environ.get("PYTHONPATH")) if p)
    # Unbuffered, so that the log holds the output in the order it was written, and a traceback's line comes last.
    env = os.environ | {"PYTHONPATH": path, "PYTHONUNBUFFERED": "1"}
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        done = subprocess.run([sys.executable, *args], cwd=folder, env=env, stdin=subprocess.DEVNULL, stdout=out,
                              stderr=subprocess.STDOUT)
    took = time.monotonic() - start
    if done.returncode == 0:
        return took, None
    lines = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    return took, f"{name} build exited {done.returncode}: {(lines or ['(no output)'])[-1]} (log: {log})"


def compare_archive(label: str, cut: Cut, raw: Path, receipts: Path, folder: Path) -> list[str]:
    """One archive: the cut copied into folder/archive (the whole archive, fraction 1, read where it is), built by the
    tagged and the current code, the times and row counts printed, and the four checks. Returns the difference lines,
    [] when identical."""
    folder.mkdir()
    if cut.fraction != 1:
        raw, receipts = cut_archive(raw, receipts, cut.moment, folder / "archive")
    print(f"{label}: {cut.kept:,} of {cut.total:,} snapshots, to {cut.moment:%Y-%m-%d %H:%M:%S} UTC; "
          f"{_snapshot_folders(raw):,} snapshot folders in {raw}", flush=True)
    tagged, new = folder / "tagged", folder / "new"
    archive = ["--raw", str(raw), "--receipts", str(receipts)]
    times, lines = {}, []
    for name, args in (
            ("tagged", [str(SCRIPT), "tagged-build", *archive, "--out", str(tagged),
                        "--temp-dir", str(folder / "tagged-tmp")]),
            ("new", ["-m", "model.build", *archive, "--out", str(new), "--stage", str(folder / "stage"),
                     "--temp-dir", str(folder / "new-tmp")])):
        times[name], error = _build(name, args, folder)
        lines += [error] if error else []
    print(f"  tagged build {times['tagged']:.1f} s, new build {times['new']:.1f} s")
    if lines:
        return lines
    for table, a, b in zip(TABLES, _row_counts(tagged), _row_counts(new)):
        print(f"  {table}: tagged {a:,}, new {b:,} rows")
    with (folder / "record.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        progress = compare_progress(tagged, new, folder / "record")  # timeline.record's own lines go to its log
    return compare_tables(tagged, new) + compare_load(tagged, new) + progress


def main(argv: list[str]) -> int:
    if argv[:1] == ["tagged-build"]:
        return run_tagged_build(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work", type=Path, required=True,
                        help="a new or empty folder for the cuts, the builds and their logs")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--receipts", type=Path, default=Path("data/receipts"))
    parser.add_argument("--fractions", type=float, nargs="+", default=[0.25, 0.5, 0.75, 1],
                        help="the cuts, as fractions of the snapshot folders; 1 is the whole archive")
    args = parser.parse_args(argv)
    work, raw, receipts = (p.absolute() for p in (args.work, args.raw, args.receipts))  # the builds run elsewhere
    if work.exists() and (not work.is_dir() or any(work.iterdir())):
        print(f"{work} is not an empty folder: give a new folder, or an empty one", file=sys.stderr)
        return 2
    for archive in (raw.resolve(), receipts.resolve()):
        if work.resolve().is_relative_to(archive):
            print(f"{work.resolve()} is inside {archive}: the builds would read their own work", file=sys.stderr)
            return 2
    labels = [LABELS.get(fraction, f"{fraction:g}") for fraction in args.fractions]
    if len(set(labels)) != len(labels):
        twice = next(label for label in labels if labels.count(label) > 1)
        print(f'--fractions gives "{twice}" twice: each archive is built once, in a folder of its own', file=sys.stderr)
        return 2
    try:
        tagged_rules()
    except (OSError, ValueError) as refused:  # the fixture unreadable, or not the pinned one
        print(refused, file=sys.stderr)
        return 2
    tag = tag_rules()
    if tag is not None and tag != TAGGED_RULES.read_bytes():
        print(f"{_shown(TAGGED_RULES)} differs from {TAG}'s src/model/rules.py "
              f"(SHA-256 {hashlib.sha256(tag).hexdigest()} at the tag)", file=sys.stderr)
        return 2
    try:
        whole, cuts = cut_moments(raw, [1])[0], cut_moments(raw, args.fractions)
    except ValueError as refused:
        print(refused, file=sys.stderr)
        return 2
    print(f"fixture {_shown(TAGGED_RULES)}, SHA-256 {TAGGED_SHA256}: "
          + (f"tag {TAG} not in this clone: checked against the pinned SHA-256 only" if tag is None
             else f"equal to {TAG}'s src/model/rules.py"))
    print(code_line())
    print(f"archive {raw}: {whole.total:,} snapshots, {sum(1 for _ in receipts.rglob('*.json')):,} receipts, "
          f"last board {whole.moment:%Y-%m-%d %H:%M:%S} UTC", flush=True)
    work.mkdir(parents=True, exist_ok=True)
    failed = False
    for label, cut in zip(labels, cuts):
        lines = compare_archive(label, cut, raw, receipts, work / label)
        for line in lines or [IDENTICAL]:
            print(f"  {line}", flush=True)
        failed = failed or bool(lines)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
