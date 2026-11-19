"""The night's measurements (docs/nightly-model.md, "Sizing", "What the function logs each night"): the process's peak
memory, the peak of a reading sampled while the build runs (the work folder's disk use), and how long staging took.

Staging's seconds are read off the files the stage writes, never by wrapping or patching the model's functions, even
at run time (the owner's call, 2026-11-19): src/model/stage.py writes each day's marker.json after that day's files,
and stages every day before model.build.run opens the stage and builds the tables. On a from-scratch build the
newest marker is therefore when staging ended; the rest of the build is the whole-history statements and writing the
tables."""
from __future__ import annotations

import resource
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from model.stage import MARKER


def peak_memory_mb() -> float:
    """The process's peak resident memory so far, in MB (2**20 bytes, as Lambda counts its memory): getrusage's
    ru_maxrss, which macOS gives in bytes and Linux in kilobytes."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (2**20 if sys.platform == "darwin" else 2**10)


class Sampler:
    """A context manager: while its block runs, a daemon thread calls `read` every `every` seconds, and `read` is also
    called once as the block starts and once as it ends, so a block shorter than the interval is read twice. `peak` is
    the largest value read. As the block ends, raised or not, the thread is stopped (without waiting the interval
    out) and joined."""

    peak: int

    def __init__(self, read: Callable[[], int], every: float = 1.0):
        self.read = read
        self.every = every
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, name="nightly-sampler", daemon=True)

    def _keep(self, value: int) -> None:
        self.peak = max(self.peak, value)

    def _sample(self) -> None:
        while not self._stop.wait(self.every):
            self._keep(self.read())

    def __enter__(self) -> Sampler:
        self.peak = self.read()
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        self._keep(self.read())


def staging_seconds(stage_dir: Path, started: float) -> float:
    """Seconds from `started` (a time.time() reading) to the newest modification time of any marker file under
    stage_dir, the same clock. 0.0 when there is none, or when the newest is older than `started`: a stage reused,
    not written, which a from-scratch night never has."""
    newest = max((marker.stat().st_mtime for marker in stage_dir.rglob(MARKER)), default=started)
    return max(newest - started, 0.0)
