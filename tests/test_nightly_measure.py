"""The night's measurements (docs/nightly-model.md, "Sizing", "What the function logs each night"): the process's peak
memory, a reading's peak sampled while the build runs, and the staging time read off the markers the stage writes,
with the frozen model's functions left as they are."""
from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import duckdb  # loaded, as in the night: the peak-memory bounds are for a process with DuckDB in it
import pytest

from model import build
from model_helpers import at, row, write_receipt, write_snapshot
from nightly import measure


def readings(*values: int, then: int) -> tuple[list[int], Callable[[], int]]:
    """A reader giving `values` in turn and `then` ever after, and the list of what it has given so far."""
    given: list[int] = []
    rest = iter(values)

    def read() -> int:
        given.append(next(rest, then))
        return given[-1]

    return given, read


def test_the_sampler_keeps_the_peak():
    given, read = readings(3, 9, 4, then=4)
    with measure.Sampler(read, every=0.01) as sampler:
        deadline = time.monotonic() + 5
        while len(given) < 4 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(given) >= 4  # 3, 9 and 4 read, and a 4 after them: the peak is not the last reading
    assert sampler.peak == 9


def test_the_sampler_reads_as_the_block_starts_and_as_it_ends():
    """A block shorter than the interval is read twice, and its end does not wait the interval out."""
    given, read = readings(5, 8, then=0)
    begun = time.monotonic()
    with measure.Sampler(read, every=60) as sampler:
        assert sampler.peak == 5
    assert time.monotonic() - begun < 5
    assert given == [5, 8]
    assert sampler.peak == 8


class BuildFailed(Exception):
    """Raised inside a sampled block, as a failed build would; its own class, so no other error passes for it."""


@pytest.mark.parametrize("block", ["ends", "raises"])
def test_the_sampler_stops_its_thread(block):
    """A failed build stops the thread too: a warm Lambda container would otherwise keep it reading."""
    before = set(threading.enumerate())
    with pytest.raises(BuildFailed) if block == "raises" else contextlib.nullcontext():
        with measure.Sampler(lambda: 1, every=0.01):
            started = [t for t in threading.enumerate() if t not in before]
            assert len(started) == 1 and started[0].daemon
            if block == "raises":
                raise BuildFailed
    assert not any(t.is_alive() for t in started)


def test_peak_memory_is_in_megabytes_on_this_platform():
    """ru_maxrss is bytes on macOS and kilobytes on Linux. Read as the wrong unit, macOS gives about 1,000 times too
    much and Linux about 1,000 times too little. On the development Mac (2026-11-20) a process with DuckDB loaded
    peaked at about 38 MB on its own and 55 MB under pytest, which the wrong unit reads as about 39,000 and 56,000:
    hence 16,384, not 65,536. CI runs this on Linux, the Mac locally."""
    assert 20 < measure.peak_memory_mb() < 16384


def marker(path: Path, mtime: float) -> None:
    """A file at `path` whose modification time is `mtime`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    os.utime(path, (mtime, mtime))


def test_staging_seconds_is_the_newest_marker(tmp_path):
    stage, started = tmp_path / "stage", time.time()
    marker(stage / "raw" / "date=2026-10-30" / "marker.json", started + 3)
    marker(stage / "raw" / "date=2026-10-31" / "marker.json", started + 7)
    marker(stage / "receipts" / "date=2026-10-30" / "marker.json", started + 5)
    marker(stage / "raw" / "date=2026-10-31" / "rows.parquet", started + 20)  # newer, and not a marker
    assert measure.staging_seconds(stage, started) == pytest.approx(7.0, abs=0.01)


def test_no_marker_written_since_the_start_means_no_staging(tmp_path):
    stage, started = tmp_path / "stage", time.time()
    stage.mkdir()
    assert measure.staging_seconds(stage, started) == 0.0
    marker(stage / "raw" / "date=2026-10-30" / "marker.json", started - 60)  # a stage reused, not written
    assert measure.staging_seconds(stage, started) == 0.0


def test_staging_seconds_of_a_real_build(tmp_path):
    raw, receipts = tmp_path / "archive" / "raw", tmp_path / "archive" / "receipts"
    for day in (30, 31):
        write_receipt(receipts, write_snapshot(raw, at(6, day=day), [row()]))
    started = time.time()
    build.build(raw, tmp_path / "model", receipts, stage_dir=tmp_path / "stage", temp_dir=tmp_path / "temp")
    assert 0 < measure.staging_seconds(tmp_path / "stage", started) <= time.time() - started
