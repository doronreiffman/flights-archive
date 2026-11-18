"""Build the model: python -m model.build --raw data/raw --out data/model (receipts from data/receipts, beside raw)"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import rules, stage

TABLES = ("snapshots", "snapshot_runs", "observations", "flights", "receipts")


def run(con, raw_dir: Path, receipts_dir: Path | None, stage_dir: Path, restage: bool = False) -> dict[str, int]:
    """Stage raw_dir and receipts_dir into stage_dir (every day again when restage is true, otherwise only the days not
    current there), then build every table on con from the stage. Returns row counts per output table."""
    st = stage.stage(con, raw_dir, receipts_dir, stage_dir, restage=restage)
    stage.open_stage(con, stage_dir, st)
    return rules.build_tables(con)


def build(raw_dir: Path, out_dir: Path, receipts_dir: Path | None = None, *, stage_dir: Path | None = None,
          restage: bool = False) -> dict[str, int]:
    """The model of raw_dir (and receipts_dir) written to out_dir. Staged in stage_dir, which is kept for the next
    build to reuse; with none, in a temporary folder removed afterwards."""
    if stage_dir is None:
        with tempfile.TemporaryDirectory(prefix="model-stage-") as temp:
            return build(raw_dir, out_dir, receipts_dir, stage_dir=Path(temp), restage=restage)
    con = rules.connect()
    try:
        counts = run(con, raw_dir, receipts_dir, stage_dir, restage)
        out_dir.mkdir(parents=True, exist_ok=True)
        for table in TABLES:
            target = str(out_dir / f"{table}.parquet").replace("'", "''")
            con.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET)")
    finally:
        con.close()  # before a temporary stage it reads is removed
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/model"))
    parser.add_argument("--receipts", type=Path, default=None, help="default: receipts/ beside --raw")
    args = parser.parse_args(argv)
    if not any(args.raw.rglob("*.json.gz")):
        print(f"no snapshots under {args.raw}", file=sys.stderr)
        return 2
    receipts = args.receipts or args.raw.parent / "receipts"
    if not any(receipts.rglob("*.json")):
        print(f"no receipts under {receipts}: snapshots from before receipts began are legacy, "
              "and any later one stops the build")
    counts = build(args.raw, args.out, receipts)
    for table, n in counts.items():
        print(f"{table}: {n} rows -> {args.out / table}.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
