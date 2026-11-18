"""The stage: each date folder's per-board work, done on that folder alone and kept as Parquet for the build to read as
the whole history (docs/lighter-build.md, "The design", 2).

The stage folder holds, ZSTD-compressed:

  raw/date=YYYY-MM-DD/rows.parquet            rules.per_board's day_rows: every board of that day, trusted or not
  raw/date=YYYY-MM-DD/counts.parquet          its day_counts: one row per snapshot of that day
  receipts/date=YYYY-MM-DD/receipts.parquet   that day's rows of the receipts table (rules.load_receipts and its check)

and beside each day's files its marker.json: {"fingerprint": …, "files": [[relative path, size], …]}, the model's
fingerprint and the listing of the day's source folder when it was staged. A staged day is reused only while it is
current: its marker equals the fingerprint and the listing now, and its files are there. Anything else, a marker that
cannot be read or parsed included, stages the day again. The marker is deleted before a day is staged and written
after its files, so a build stopped midway leaves that day without one. The markers are the only state kept between
builds.

Staging goes by date folder because a snapshot's files never leave theirs: the collector writes every page of a
snapshot under raw/date=<the run's date>/HHMMSSZ-<sha12>/, so every count per snapshot can be made from one folder. A
snapshot file anywhere else, or a receipt outside the date folders, stops the build: staged by folder, it could be
counted under a day it does not belong to. The rules themselves are all in rules.py; this module only reads folders
and writes files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb

from . import rules

MARKER = "marker.json"


@dataclass(frozen=True)
class Stage:
    raw_days: tuple[str, ...]  # the date=… folders of raw/ read, sorted
    receipt_days: tuple[str, ...]  # the date=… folders of receipts/ read, sorted
    staged: tuple[str, ...]  # "raw/date=…" then "receipts/date=…" entries staged by this call, in date order


def _sql(path: Path) -> str:
    """A path inside an SQL string literal: its quotes doubled."""
    return str(path).replace("'", "''")


# Where the collector writes a snapshot's page under raw/ (src/collector/core.py), matched whole. A staged snapshot's
# id then always carries its own folder's date, so no snapshot spans two date folders: a day copied into another
# (`cp -r` onto an existing date=… folder nests it) is refused, never staged under the wrong day.
_SNAPSHOT_FILE = re.compile(r"date=\d{4}-\d{2}-\d{2}/\d{6}Z-[0-9a-f]{12}/page-\d{3}\.json\.gz", re.ASCII)


def _snapshot_file(path: str) -> bool:
    """Whether a path relative to raw/ is a snapshot page where the collector writes one."""
    return _SNAPSHOT_FILE.fullmatch(path) is not None


def _in_a_date_folder(path: str) -> bool:
    """Whether a path relative to receipts/ lies in one of its date=… folders, at any depth."""
    first, _, rest = path.partition("/")
    return first.startswith("date=") and rest != ""


def _days(folder: Path, pattern: str, placed: Callable[[str], bool]) -> tuple[list[Path], list[str]]:
    """The date=… child folders of `folder` holding at least one file matching `pattern` (at any depth), sorted, and
    the files matching it whose path relative to `folder` is not `placed`, as sorted POSIX paths."""
    days = [d for d in sorted(folder.glob("date=*")) if d.is_dir() and any(d.rglob(pattern))]
    misplaced = sorted(p for p in (f.relative_to(folder).as_posix() for f in folder.rglob(pattern)) if not placed(p))
    return days, misplaced


def fingerprint(sources: Iterable[Path] | None = None, duckdb_version: str = duckdb.__version__) -> str:
    """SHA-256 (hex) of each source file in name order (its name, a NUL, its bytes, a NUL), then the DuckDB version.
    By default the sources are every module of the model, so any edit to the model's source, a rule or not, and any
    other DuckDB, stages every day again: coarse on purpose (docs/lighter-build.md, "Re-run, crash, late files, rule
    change")."""
    if sources is None:
        sources = sorted(Path(__file__).resolve().parent.glob("*.py"))
    digest = hashlib.sha256()
    for source in sorted(sources, key=lambda p: p.name):
        digest.update(source.name.encode() + b"\0" + source.read_bytes() + b"\0")
    digest.update(duckdb_version.encode())
    return digest.hexdigest()


def listing(day: Path, pattern: str) -> list[list]:
    """[[relative POSIX path, size in bytes], …] of every file under `day` matching `pattern`, at any depth, sorted:
    lists, as the marker reads back from JSON."""
    return sorted([f.relative_to(day).as_posix(), f.stat().st_size] for f in day.rglob(pattern))


def _copy(con, query: str, path: Path) -> None:
    """Write `query`'s result to `path` as Parquet: under a temporary name in the same folder, then renamed, so the
    file at `path` is always whole."""
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    con.execute(f"COPY ({query}) TO '{_sql(temp)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    os.replace(temp, path)


def _current(out: Path, marker: dict, files: dict[str, str]) -> bool:
    """Whether the day staged in `out` can be reused: its marker reads as `marker`, and each of its `files` is there.
    A marker missing, unreadable or not JSON means no: a damaged stage is staged again, never trusted."""
    try:
        found = json.loads((out / MARKER).read_text())
    except (OSError, ValueError):
        return False
    return found == marker and all((out / name).is_file() for name in files)


def _mark(out: Path, marker: dict) -> None:
    """Write the day's marker: under a temporary name in the same folder, then renamed."""
    temp = out / f"{MARKER}.{os.getpid()}.tmp"
    temp.write_text(json.dumps(marker))
    os.replace(temp, out / MARKER)


def _stage_day(con, day: Path, out: Path, pattern: str, read: Callable[[], None], files: dict[str, str],
               print_: str, restage: bool) -> bool:
    """Stage the date folder `day` into `out`, unless restage is false and `out` is current. `read` loads the day's
    tables on con; `files` maps each staged file's name to the query it holds. Whether the day was staged."""
    marker = {"fingerprint": print_, "files": listing(day, pattern)}
    if not restage and _current(out, marker, files):
        return False
    (out / MARKER).unlink(missing_ok=True)
    read()
    out.mkdir(parents=True, exist_ok=True)
    for name, query in files.items():
        _copy(con, query, out / name)
    _mark(out, marker)
    return True


def _read_boards(con, day: Path) -> None:
    """The day's snapshot files into raw_rows, and R1 and R2 on each board into day_rows and day_counts."""
    rules.load_raw(con, str(day / "**" / "*.json.gz"))
    rules.per_board(con)


RAW_FILES = {"rows.parquet": "SELECT * FROM day_rows", "counts.parquet": "SELECT * FROM day_counts"}
RECEIPT_FILES = {"receipts.parquet": "SELECT * FROM receipts"}


def stage(con, raw_dir: Path, receipts_dir: Path | None, stage_dir: Path, restage: bool = False) -> Stage:
    """Stage every date folder of raw_dir and receipts_dir (none when it is None or not a folder) into stage_dir,
    except a day already staged there and current, unless restage is true. The days read are the source folders',
    so a staged day whose source folder is gone is not read.
    ValueError, before any day is staged, when a snapshot file lies anywhere but date=…/HHMMSSZ-<sha12>/page-NNN.json.gz,
    when a receipt lies outside the date folders, or when raw_dir holds no snapshot file at all."""
    raw_days, names = _days(raw_dir, "*.json.gz", _snapshot_file)
    if names:
        n = len(names)
        raise ValueError(f"{n} files under {raw_dir} have a path that is not date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-NNN.json.gz: {names[:10]}")
    if not raw_days:
        raise ValueError(f"no snapshot files under {raw_dir}")
    receipt_days: list[Path] = []
    if receipts_dir is not None and receipts_dir.is_dir():
        receipt_days, names = _days(receipts_dir, "*.json", _in_a_date_folder)
        if names:
            n = len(names)
            raise ValueError(f"{n} receipt files under {receipts_dir} are outside its date=YYYY-MM-DD folders: {names[:10]}")

    print_ = fingerprint()
    staged = []
    for day in raw_days:
        if _stage_day(con, day, stage_dir / "raw" / day.name, "*.json.gz", lambda: _read_boards(con, day),
                      RAW_FILES, print_, restage):
            staged.append(f"raw/{day.name}")
    for day in receipt_days:
        if _stage_day(con, day, stage_dir / "receipts" / day.name, "*.json",
                      lambda: rules.load_receipts(con, str(day / "**" / "*.json")), RECEIPT_FILES, print_, restage):
            staged.append(f"receipts/{day.name}")
    for table in ("raw_rows", "day_rows", "day_counts"):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    return Stage(raw_days=tuple(d.name for d in raw_days), receipt_days=tuple(d.name for d in receipt_days),
                 staged=tuple(staged))


def _read(folder: Path, days: tuple[str, ...], name: str) -> str:
    """SQL reading each day's staged file `name` under `folder`. DuckDB would otherwise take the date=… in each path
    as a Hive partition and add a `date` column to what it reads."""
    files = ", ".join(f"'{_sql(folder / day / name)}'" for day in days)
    return f"read_parquet([{files}], hive_partitioning = false)"


def open_stage(con, stage_dir: Path, st: Stage) -> None:
    """The staged days as the whole history, for rules.build_tables: the view staged_rows and the tables staged_counts
    and receipts."""
    con.execute(f"CREATE OR REPLACE VIEW staged_rows AS SELECT * FROM {_read(stage_dir / 'raw', st.raw_days, 'rows.parquet')}")
    con.execute(f"CREATE OR REPLACE TABLE staged_counts AS SELECT * FROM {_read(stage_dir / 'raw', st.raw_days, 'counts.parquet')}")
    if st.receipt_days:
        con.execute(f"CREATE OR REPLACE TABLE receipts AS SELECT * FROM {_read(stage_dir / 'receipts', st.receipt_days, 'receipts.parquet')}")
    else:
        rules.load_receipts(con, None)
