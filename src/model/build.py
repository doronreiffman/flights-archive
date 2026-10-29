"""Build the model: python -m model.build --raw data/raw --out data/model"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import rules

TABLES = ("snapshots", "snapshot_runs", "observations", "flights")


def build(raw_dir: Path, out_dir: Path) -> dict[str, int]:
    con = rules.connect()
    counts = rules.build_all(con, str(raw_dir / "**" / "*.json.gz"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        target = str(out_dir / f"{table}.parquet").replace("'", "''")
        con.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET)")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/model"))
    args = parser.parse_args(argv)
    if not any(args.raw.rglob("*.json.gz")):
        print(f"no snapshots under {args.raw}", file=sys.stderr)
        return 2
    counts = build(args.raw, args.out)
    for table, n in counts.items():
        print(f"{table}: {n} rows -> {args.out / table}.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
