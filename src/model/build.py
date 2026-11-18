"""Build the model: python -m model.build --raw data/raw --out data/model [--stage DIR] [--restage] [--temp-dir DIR]

Receipts are read from receipts/ beside --raw, and each date folder's work is kept in stage/ beside it, unless given;
--restage stages every date folder again (the from-scratch build). DuckDB runs within --memory-limit (1GB) on
--threads (2), and spills into --temp-dir, by default a new folder under the system's temp folder, removed after the
build (docs/lighter-build.md, "The design", 3). The model folder is written whole or not at all: beside itself, then
swapped in.
"""
from __future__ import annotations

import argparse
import contextlib
import shutil
import sys
import tempfile
from pathlib import Path

import duckdb

from . import rules, stage

TABLES = ("snapshots", "snapshot_runs", "observations", "flights", "receipts")
MEMORY_LIMIT = "1GB"
THREADS = 2


def _sql(text: str) -> str:
    """`text` inside an SQL string literal: its quotes doubled."""
    return text.replace("'", "''")


def connect(temp_dir: Path, memory_limit: str = MEMORY_LIMIT, threads: int = THREADS) -> duckdb.DuckDBPyConnection:
    """The rules' connection (rules.connect), held to `memory_limit` and `threads`, spilling into `temp_dir`."""
    con = rules.connect()
    con.execute(f"SET memory_limit = '{_sql(memory_limit)}'")
    con.execute(f"SET threads = {int(threads)}")
    con.execute(f"SET temp_directory = '{_sql(str(temp_dir))}'")
    return con


def run(con, raw_dir: Path, receipts_dir: Path | None, stage_dir: Path, restage: bool = False) -> dict[str, int]:
    """Stage raw_dir and receipts_dir into stage_dir (every day again when restage is true, otherwise only the days not
    current there), then build every table on con from the stage. Returns row counts per output table."""
    st = stage.stage(con, raw_dir, receipts_dir, stage_dir, restage=restage)
    stage.open_stage(con, stage_dir, st)
    return rules.build_tables(con)


def _siblings(out_dir: Path) -> tuple[Path, Path]:
    """<out>.building, where the new model is written, and <out>.old, where the last one waits while they swap."""
    return out_dir.with_name(out_dir.name + ".building"), out_dir.with_name(out_dir.name + ".old")


def refuse_foreign(out_dir: Path) -> None:
    """ValueError when out_dir, <out>.building or <out>.old holds anything but the model's table files: writing the
    model replaces those folders, so `--out data` would otherwise delete the archive copy. The folder's contents are
    the test, since model folders carry no marker."""
    model_files = {f"{table}.parquet" for table in TABLES}
    for folder in (out_dir, *_siblings(out_dir)):
        if folder.exists():
            names = sorted(p.name for p in folder.iterdir() if p.name not in model_files or not p.is_file())
            if names:
                raise ValueError(f"{folder} holds files that are not a model's: {names}; refusing to replace it")


def put_back(out_dir: Path) -> None:
    """A build killed between write_model's two renames leaves no out_dir and the last model, whole, in <out>.old:
    put it back as out_dir. A <out>.old holding fewer than the five tables (a build killed while removing it, with
    out_dir then deleted by hand) is not a whole model: it stays a leftover, which the next write clears. Run after
    refuse_foreign, so that <out>.old holds nothing but table files."""
    old = _siblings(out_dir)[1]
    if not out_dir.exists() and old.is_dir() and _every_table_in(old):
        old.rename(out_dir)


def _every_table_in(folder: Path) -> bool:
    """Whether `folder` holds the five table files and nothing else."""
    return sorted(p.name for p in folder.iterdir()) == sorted(f"{table}.parquet" for table in TABLES)


def refuse_overlap(stage_dir: Path, raw_dir: Path, receipts_dir: Path | None) -> None:
    """ValueError when the stage folder is raw_dir or receipts_dir, lies inside one, or holds one: staging there
    would write each day's files into the archive's own date=… folders (`--stage data`), where the next build would
    read a marker.json as a receipt. Paths are compared resolved."""
    stage = stage_dir.resolve()
    for source in (raw_dir, receipts_dir):
        if source is not None and (stage.is_relative_to(source.resolve()) or source.resolve().is_relative_to(stage)):
            raise ValueError(f"the stage folder {stage_dir} overlaps the archive ({raw_dir}, {receipts_dir}); "
                             "refusing to stage there")


def _copy_out(con, table: str, path: Path) -> None:
    """One table to `path` as Parquet, as the build wrote it at the tag."""
    con.execute(f"COPY {table} TO '{_sql(str(path))}' (FORMAT PARQUET)")


def write_model(con, out_dir: Path) -> None:
    """The five tables on con written beside out_dir, as <out>.building, then swapped in: the last model moves to
    <out>.old, the new one moves in, and the old one is removed. Leftover <out>.building and <out>.old folders are
    removed first. A failure of any kind while writing, Ctrl-C included, removes <out>.building and leaves the last
    model as it was. A build killed outright leaves the last model or the new one in out_dir, with leftovers beside it
    that the next write removes; or, killed between the two renames, no out_dir and the last model whole in
    <out>.old, which the next build puts back before any work (put_back, in build)."""
    refuse_foreign(out_dir)  # before any work
    building, old = _siblings(out_dir)
    for leftover in (building, old):
        if leftover.exists():
            shutil.rmtree(leftover)
    building.mkdir(parents=True)
    try:
        for table in TABLES:
            _copy_out(con, table, building / f"{table}.parquet")
    except BaseException:
        shutil.rmtree(building, ignore_errors=True)
        raise
    if out_dir.exists():
        out_dir.rename(old)
    building.rename(out_dir)
    if old.exists():
        shutil.rmtree(old)


def build(raw_dir: Path, out_dir: Path, receipts_dir: Path | None = None, *, stage_dir: Path | None = None,
          restage: bool = False, memory_limit: str = MEMORY_LIMIT, threads: int = THREADS,
          temp_dir: Path | None = None) -> dict[str, int]:
    """The model of raw_dir (and receipts_dir) written to out_dir, whole or not at all. Staged in stage_dir, which is
    kept for the next build to reuse; DuckDB spills into temp_dir. Either one, when None, is a new folder under the
    system's temp folder, removed afterwards whatever happens.

    Before any work: ValueError when out_dir or a folder beside it holds anything but a model (refuse_foreign), or
    when a stage_dir given overlaps raw_dir or receipts_dir (refuse_overlap); then a whole last model that a build
    killed between write_model's two renames left in <out>.old is put back as out_dir (put_back), so it stays in
    place even if this build fails."""
    refuse_foreign(out_dir)  # before any staging: `--out data` stops at once, not after minutes of work
    if stage_dir is not None:
        refuse_overlap(stage_dir, raw_dir, receipts_dir)
    put_back(out_dir)
    with contextlib.ExitStack() as temporary:
        if temp_dir is None:
            temp_dir = Path(temporary.enter_context(tempfile.TemporaryDirectory(prefix="model-build-")))
        if stage_dir is None:
            stage_dir = Path(temporary.enter_context(tempfile.TemporaryDirectory(prefix="model-stage-")))
        con = connect(temp_dir, memory_limit, threads)
        try:
            counts = run(con, raw_dir, receipts_dir, stage_dir, restage)
            write_model(con, out_dir)
        finally:
            con.close()  # before the temporary folders it reads and spills into are removed
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/model"))
    parser.add_argument("--receipts", type=Path, default=None, help="default: receipts/ beside --raw")
    parser.add_argument("--stage", type=Path, default=None,
                        help="where each date folder's work is kept for the next build; default: stage/ beside --raw")
    parser.add_argument("--restage", action="store_true", help="stage every date folder again: the from-scratch build")
    parser.add_argument("--memory-limit", default=MEMORY_LIMIT, help="DuckDB's memory limit; default: %(default)s")
    parser.add_argument("--threads", type=int, default=THREADS, help="DuckDB's threads; default: %(default)s")
    parser.add_argument("--temp-dir", type=Path, default=None,
                        help="where DuckDB spills; default: a new folder under the system's temp folder, removed after")
    args = parser.parse_args(argv)
    if not any(args.raw.rglob("*.json.gz")):
        print(f"no snapshots under {args.raw}", file=sys.stderr)
        return 2
    receipts = args.receipts or args.raw.parent / "receipts"
    if not any(receipts.rglob("*.json")):
        print(f"no receipts under {receipts}: snapshots from before receipts began are legacy, "
              "and any later one stops the build")
    counts = build(raw_dir=args.raw, out_dir=args.out, receipts_dir=receipts,
                   stage_dir=args.stage or args.raw.parent / "stage", restage=args.restage,
                   memory_limit=args.memory_limit, threads=args.threads, temp_dir=args.temp_dir)
    for table, n in counts.items():
        print(f"{table}: {n} rows -> {args.out / table}.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
