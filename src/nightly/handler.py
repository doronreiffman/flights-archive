"""AWS Lambda entry point of the nightly model build. EventBridge Scheduler calls handler() once a night.

One night (docs/nightly-model.md, "What one night does"): ping healthchecks.io's /start; empty the work folder; check
that DuckDB has nothing installed beyond its built-in extensions; list receipts/ then raw/ in the archive bucket and
stop if either listing is smaller than the last build's; copy exactly what was listed; build the model on the copy;
check the extensions again; upload the five tables and the manifest, write-once; move the pointer, only forward;
delete builds older than 30 days, never the pointer's; log one summary line and send it as the success ping. Anything
that raises after the start ping is logged, sent to /fail with its reason, and raised. An error before the pointer
step leaves the pointer where it was and deletes nothing. The function reads S3 and pings healthchecks.io, nothing
else.

Manual event:
  {"drill": true}  fail on purpose before reading anything, to prove the alert
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

import model.build
from model.build import TABLES
from model.stage import fingerprint
from nightly.archive import DOWNLOAD_WORKERS, check_not_shrunk, copy, list_archive
from nightly.bucket import Bucket
from nightly.measure import Sampler, peak_memory_mb, staging_seconds
from nightly.output import (CODE_SHA256, build_id, clean_up, manifest, move_pointer, newest_receipt,
                            pointer_build_id, read_pointer, table_entries, upload_build)

log = logging.getLogger()
log.setLevel(logging.INFO)

MEMORY_LIMIT = "1GB"  # DuckDB's, as every comparison so far ran (docs/nightly-model.md, "Sizing")
THREADS = 2
WORK_DIR = Path("/tmp/nightly")  # under /tmp, the disk the template sizes (EphemeralStorage)
MB = 2**20


@dataclass(frozen=True)
class Config:
    archive_bucket: str
    model_bucket: str
    healthcheck_url: str = ""
    work_dir: Path = WORK_DIR

    @classmethod
    def from_env(cls, env: dict[str, str]) -> Config:
        """ValueError naming each of ARCHIVE_BUCKET and MODEL_BUCKET that is missing or blank, and when both name
        one bucket: the function deletes under models/ in MODEL_BUCKET. HEALTHCHECK_URL is optional."""
        names = {key: env.get(key, "").strip() for key in ("ARCHIVE_BUCKET", "MODEL_BUCKET")}
        missing = [key for key, name in names.items() if not name]
        if missing:
            raise ValueError(f"missing environment variables: {missing}")
        if names["ARCHIVE_BUCKET"] == names["MODEL_BUCKET"]:
            raise ValueError(f"ARCHIVE_BUCKET and MODEL_BUCKET both name {names['MODEL_BUCKET']}: the function "
                             "deletes under models/ in MODEL_BUCKET, so the archive needs a bucket of its own")
        return cls(archive_bucket=names["ARCHIVE_BUCKET"], model_bucket=names["MODEL_BUCKET"],
                   healthcheck_url=env.get("HEALTHCHECK_URL", "").rstrip("/"))


@dataclass(frozen=True)
class Runtime:
    """What the Lambda context tells the run."""
    request_id: str
    memory_mb: int
    seconds_left: Callable[[], float]


class DrillError(Exception):
    """Raised on purpose by a {"drill": true} event, to prove the alert fires."""


class ExtensionError(Exception):
    """DuckDB lists an installed extension that is not built into the package; the build is to use only the built-in
    ones (docs/nightly-model.md, section 7, "No download at run time")."""


def parse_event(event) -> str:
    """"drill" for {"drill": true}, and only an exact true; "build" for anything else, the schedule's event among
    them."""
    if isinstance(event, dict) and event.get("drill") is True:
        return "drill"
    return "build"


def ping(url: str, message: str) -> None:
    """Report to healthchecks.io: the message's first 10,000 bytes, posted. A failed ping is logged, never fatal."""
    if not url:
        return
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=message.encode()[:10000]), timeout=10).close()
    except Exception as err:  # noqa: BLE001 - monitoring must not fail the build
        log.warning("healthcheck ping failed: %s", err)


def installed_extensions(con: duckdb.DuckDBPyConnection | None = None) -> list[str]:
    """The names, sorted, of the extensions DuckDB lists as installed that are not built into the package. With no
    connection given, on a new one, closed after."""
    own = con is None
    if own:
        con = duckdb.connect()
    try:
        rows = con.execute("SELECT extension_name FROM duckdb_extensions() WHERE installed "
                           "AND install_mode IS DISTINCT FROM 'STATICALLY_LINKED' ORDER BY extension_name").fetchall()
    finally:
        if own:
            con.close()
    return [name for (name,) in rows]


def _no_extensions(extensions: Callable[[], list[str]], when: str) -> None:
    found = extensions()
    if found:
        raise ExtensionError(f"DuckDB lists extensions installed that are not built in, {when}: {', '.join(found)}")


@contextmanager
def _timed(seconds: dict[str, float], name: str) -> Iterator[None]:
    """The block's duration in seconds[name], on the monotonic clock, never the injected one."""
    start = time.monotonic()
    yield
    seconds[name] = time.monotonic() - start


def run(cfg: Config, archive: Bucket, models: Bucket, runtime: Runtime, clock: Callable[[], datetime],
        pinger: Callable[[str, str], None], mode: str = "build",
        build: Callable[..., dict[str, int]] = model.build.build,
        extensions: Callable[[], list[str]] = installed_extensions) -> dict:
    """One night; returns its summary. `clock` gives the start and finish times (timezone-aware UTC, or ValueError);
    every duration is read off the monotonic clock."""
    began = time.monotonic()
    url = cfg.healthcheck_url
    pinger(f"{url}/start" if url else "", "")
    try:
        summary = _night(cfg, archive, models, runtime, clock, mode, build, extensions, began)
        line = json.dumps(summary)
        log.info(line)
        pinger(url, line)
        shutil.rmtree(cfg.work_dir, ignore_errors=True)
    except Exception as err:
        log.error("nightly build failed: %s: %s", type(err).__name__, err)
        pinger(f"{url}/fail" if url else "", f"{type(err).__name__}: {err}")
        raise
    return summary


def _night(cfg: Config, archive: Bucket, models: Bucket, runtime: Runtime, clock: Callable[[], datetime], mode: str,
           build: Callable[..., dict[str, int]], extensions: Callable[[], list[str]], began: float) -> dict:
    if mode == "drill":
        raise DrillError("alert drill: nothing was read or written")
    # A reused Lambda environment keeps /tmp, even after a failure: a leftover copy must never be read as tonight's.
    work = cfg.work_dir
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    _no_extensions(extensions, "before the build")
    started = clock()
    build_name = build_id(started, runtime.request_id)  # ValueError for a clock that is not timezone-aware UTC

    seconds: dict[str, float] = {}
    with _timed(seconds, "list"):
        pointer = read_pointer(models)
        previous = None if pointer is None else pointer[0]
        if previous is not None:  # a pointer naming no newest receipt or no build id fails here, before any listing
            newest_receipt(previous)
            pointer_build_id(previous)
        receipts, raw = list_archive(archive)
        check_not_shrunk(previous, receipts, raw)

    copied, out, stage = work / "archive", work / "out", work / "stage"
    with _timed(seconds, "copy"):
        copy(archive, receipts, copied)
        copy(archive, raw, copied)

    # The work folder stays in place for the whole sampled block: a reading that raises as the block ends would
    # replace the block's own error.
    with _timed(seconds, "build"):
        build_started = time.time()  # the stage's markers carry the real clock's times, not the injected clock's
        with Sampler(lambda: shutil.disk_usage(work).used) as disk:
            rows = build(raw_dir=copied / "raw", out_dir=out, receipts_dir=copied / "receipts", stage_dir=stage,
                         temp_dir=work / "temp", memory_limit=MEMORY_LIMIT, threads=THREADS)
    seconds["staging"] = staging_seconds(stage, build_started)
    _no_extensions(extensions, "after the build")

    tables = table_entries(out, build_name, rows)
    finished = clock()
    tmp_mb = {"peak": round(disk.peak / MB, 1), "size": round(shutil.disk_usage(work).total / MB, 1)}
    measured = {"seconds": {name: round(value, 1) for name, value in seconds.items()},
                "memory_mb": {"peak": round(peak_memory_mb(), 1), "size": runtime.memory_mb}, "tmp_mb": tmp_mb}
    body = manifest(build_name, started, finished, tables, cfg.archive_bucket, receipts, raw, MEMORY_LIMIT, THREADS,
                    measured)

    with _timed(seconds, "upload"):
        upload_build(models, build_name, out, body)
    with _timed(seconds, "pointer"):
        moved, pointer_build = move_pointer(models, body, receipts.newest_key or "")
    with _timed(seconds, "clean_up"):
        deleted = clean_up(models, started, keep=pointer_build)
    seconds["total"] = time.monotonic() - began

    return {
        "action": "built", "build_id": build_name, "pointer": moved, "pointer_build_id": pointer_build,
        "seconds": {name: round(value, 1) for name, value in seconds.items()},
        "seconds_left": round(runtime.seconds_left(), 1),
        "copied": {"receipts": {"objects": receipts.objects, "bytes": receipts.bytes},
                   "raw": {"objects": raw.objects, "bytes": raw.bytes}},
        "memory_mb": {"peak": round(peak_memory_mb(), 1), "size": runtime.memory_mb},  # the night's peak, uploads in
        "tmp_mb": tmp_mb,
        "rows": rows,
        "table_bytes": {table: tables[table]["bytes"] for table in TABLES},
        "deleted": deleted,
        "model_fingerprint": fingerprint(), "code_sha256": CODE_SHA256, "duckdb": duckdb.__version__,
    }


def handler(event, context):  # pragma: no cover - thin AWS wiring, covered by run() and parse_event()
    import boto3
    import botocore.config

    from nightly.bucket import S3Bucket

    cfg = Config.from_env(dict(os.environ))
    # One client, made here before any thread pool, shared by the copy's downloads: boto3's clients are generally
    # thread-safe, but boto3.client() is not to be called inside a concurrent context, and no custom botocore event
    # hook is added (boto3's guide, "Low-level clients", "Multithreading or multiprocessing with clients").
    client = boto3.client("s3", config=botocore.config.Config(max_pool_connections=DOWNLOAD_WORKERS))
    runtime = Runtime(context.aws_request_id, int(context.memory_limit_in_mb),
                      lambda: context.get_remaining_time_in_millis() / 1000)
    return run(cfg, S3Bucket(client, cfg.archive_bucket), S3Bucket(client, cfg.model_bucket), runtime,
               clock=lambda: datetime.now(timezone.utc), pinger=ping, mode=parse_event(event))
