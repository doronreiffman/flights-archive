"""The stage: each date folder's per-board work, done on that folder alone and kept as Parquet for the build to read as
the whole history (docs/lighter-build.md, "The design", 2).

The stage folder holds, ZSTD-compressed:

  raw/date=YYYY-MM-DD/rows.parquet            rules.per_board's day_rows: every board of that day, trusted or not
  raw/date=YYYY-MM-DD/counts.parquet          its day_counts: one row per snapshot of that day
  receipts/date=YYYY-MM-DD/receipts.parquet   that day's rows of the receipts table (rules.load_receipts and its check)

Staging goes by date folder because a snapshot's files never leave theirs: the collector writes every page of a
snapshot under raw/date=<the run's date>/HHMMSSZ-<sha12>/, so every count per snapshot can be made from one folder. A
snapshot file anywhere else, or a receipt outside the date folders, stops the build: staged by folder, it could be
counted under a day it does not belong to. The rules themselves are all in rules.py; this module only reads folders
and writes files.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import rules


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


def _copy(con, query: str, path: Path) -> None:
    """Write `query`'s result to `path` as Parquet: under a temporary name in the same folder, then renamed, so the
    file at `path` is always whole."""
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    con.execute(f"COPY ({query}) TO '{_sql(temp)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    os.replace(temp, path)


def stage(con, raw_dir: Path, receipts_dir: Path | None, stage_dir: Path) -> Stage:
    """Stage every date folder of raw_dir and receipts_dir (none when it is None or not a folder) into stage_dir.
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

    for day in raw_days:
        rules.load_raw(con, str(day / "**" / "*.json.gz"))
        rules.per_board(con)
        out = stage_dir / "raw" / day.name
        out.mkdir(parents=True, exist_ok=True)
        _copy(con, "SELECT * FROM day_rows", out / "rows.parquet")
        _copy(con, "SELECT * FROM day_counts", out / "counts.parquet")
    for day in receipt_days:
        rules.load_receipts(con, str(day / "**" / "*.json"))
        out = stage_dir / "receipts" / day.name
        out.mkdir(parents=True, exist_ok=True)
        _copy(con, "SELECT * FROM receipts", out / "receipts.parquet")
    for table in ("raw_rows", "day_rows", "day_counts"):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    return Stage(raw_days=tuple(d.name for d in raw_days), receipt_days=tuple(d.name for d in receipt_days),
                 staged=tuple(f"raw/{d.name}" for d in raw_days) + tuple(f"receipts/{d.name}" for d in receipt_days))


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
