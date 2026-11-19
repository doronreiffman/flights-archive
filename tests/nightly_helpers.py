"""For the nightly run's tests: an archive bucket made from folders, a small archive the real build accepts, and a
stand-in build that records what it was given."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from model.build import TABLES
from model_helpers import at, row, write_receipt, write_snapshot
from nightly.bucket import MemoryBucket
from nightly.handler import Runtime

NOW = datetime(2026, 11, 20, 1, 40, 3, tzinfo=timezone.utc)
RUNTIME = Runtime("1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809", 3008, lambda: 600.0)
COUNTS = {"snapshots": 2, "observations": 4, "flights": 3, "receipts": 3}  # build() reports four tables


def archive_bucket(raw: Path, receipts: Path) -> MemoryBucket:
    """Every file under raw/ and receipts/, keyed raw/<relative path> and receipts/<relative path>, as the collector
    stores them."""
    objects = {}
    for prefix, folder in (("raw/", raw), ("receipts/", receipts)):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                objects[prefix + path.relative_to(folder).as_posix()] = path.read_bytes()
    return MemoryBucket("flights-archive-archive", objects)


def small_archive(root: Path) -> tuple[Path, Path]:
    """Boards on 30 and 31 October 2026, after receipts began, each with its stored receipt, and an unchanged
    receipt for the second half an hour later. Returns (raw, receipts) under root."""
    raw, receipts = root / "raw", root / "receipts"
    first = write_snapshot(raw, at(6, day=30), [
        row(sched_local="2026-10-30T10:00:00"),
        row(flight_no="002", sched_local="2026-10-31T09:00:00"),
    ])
    write_receipt(receipts, first, rows=2)
    second = write_snapshot(raw, at(6, day=31), [
        row(flight_no="002", sched_local="2026-10-31T09:00:00", est_local="2026-10-31T10:15:00", status="DELAYED"),
        row(flight_no="003", sched_local="2026-11-01T07:30:00", direction="A", status="CANCELED"),
    ])
    write_receipt(receipts, second, rows=2)
    write_receipt(receipts, second, action="unchanged", when=at(6, 30, day=31), rows=2)
    return raw, receipts


def fake_build(calls: list) -> Callable[..., dict[str, int]]:
    """A stand-in for model.build.build: records its keyword arguments in `calls`, writes five small table files of
    distinct sizes to out_dir, and returns four counts, as build() does."""
    def build(**kwargs) -> dict[str, int]:
        calls.append(kwargs)
        out = kwargs["out_dir"]
        out.mkdir(parents=True)
        for n, table in enumerate(TABLES):
            (out / f"{table}.parquet").write_bytes(f"PAR1 {table} ".encode() * (n + 1))
        return dict(COUNTS)
    return build
