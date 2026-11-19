"""What a night leaves in the model bucket (docs/nightly-model.md, section 4, "Output and readers").

models/<build id>/ holds the five tables and a manifest describing the build, every one uploaded write-once, the
tables first. latest.json, the pointer, holds the same bytes as the newest build's manifest. It is written last and
only forward: a build replaces it only when the newest receipt it read is the same as or newer than the pointer's,
and only while it is still the object just read; refused, the build reads it again and decides again, at most
POINTER_TRIES times. After the pointer has moved, builds that started more than KEEP_DAYS days ago are deleted,
except the one the pointer names.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

from model.build import TABLES
from model.stage import fingerprint
from nightly.archive import Listing
from nightly.bucket import Bucket, ConditionFailed

MANIFEST_VERSION = 1
POINTER = "latest.json"
MODELS = "models/"
MANIFEST = "manifest.json"
KEEP_DAYS = 30
POINTER_TRIES = 3
BUILD_TIME = "%Y%m%dT%H%M%SZ"
BUILD_START = re.compile(r"^(\d{8}T\d{6}Z)-")  # a build id begins with its start time


class PointerError(Exception):
    """The pointer changed under every try: each write was refused after a fresh read."""


def _utc(moment: datetime) -> datetime:
    """`moment` itself, or ValueError when it is not timezone-aware UTC."""
    if moment.utcoffset() != timedelta(0):
        raise ValueError(f"{moment!r} is not a timezone-aware UTC time")
    return moment


def build_id(started: datetime, request_id: str) -> str:
    """The run's start time and the first 8 characters of its request id, e.g. 20261120T014003Z-1a2b3c4d."""
    return f"{_utc(started):{BUILD_TIME}}-{request_id[:8]}"


def code_fingerprint(directory: Path) -> str:
    """SHA-256 over the .py files in a directory, sorted by name: each adds its name, a NUL byte and the SHA-256 of
    its bytes. A copy of collector.core.code_fingerprint (src/nightly imports no collector module); a test holds the
    two equal on the same folder."""
    h = hashlib.sha256()
    for path in sorted(directory.glob("*.py"), key=lambda p: p.name):
        h.update(path.name.encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


CODE_SHA256 = code_fingerprint(Path(__file__).parent)


def _table_key(build: str, table: str) -> str:
    return f"{MODELS}{build}/{table}.parquet"


def table_entries(out_dir: Path, build_id: str, rows: dict[str, int]) -> dict[str, dict]:
    """For each of the five tables in out_dir, in TABLES order: its key, bytes and SHA-256, and its rows where
    `rows` (build()'s report: four tables, not snapshot_runs) has them."""
    entries = {}
    for table in TABLES:
        path = out_dir / f"{table}.parquet"
        data = path.read_bytes()
        entry = {"key": _table_key(build_id, table), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if table in rows:
            entry["rows"] = rows[table]
        entries[table] = entry
    return entries


def manifest(build_id: str, started: datetime, finished: datetime, tables: dict, archive_bucket: str,
             receipts: Listing, raw: Listing, memory_limit: str, threads: int, measured: dict) -> bytes:
    """What this build is: when it ran (UTC), its tables, the archive listings it was built from, the code that built
    it, the build's settings, and what was measured up to now."""
    return json.dumps({
        "manifest_version": MANIFEST_VERSION,
        "build_id": build_id,
        "started_at": _utc(started).isoformat(),
        "finished_at": _utc(finished).isoformat(),
        "tables": tables,
        "archive": {"bucket": archive_bucket, "receipts": receipts.summary(), "raw": raw.summary()},
        "code": {"model_fingerprint": fingerprint(), "function_sha256": CODE_SHA256, "duckdb": duckdb.__version__,
                 "python": platform.python_version(), "machine": platform.machine()},
        # every night is a from-scratch build in an emptied work folder (the plan, "One run at a time on the disk")
        "build": {"memory_limit": memory_limit, "threads": threads, "stage_reused": False},
        "measured": measured,
    }, sort_keys=True, indent=2).encode()


def upload_build(models: Bucket, build_id: str, out_dir: Path, manifest: bytes) -> None:
    """The five tables, then the manifest beside them, each write-once: a key taken (two runs with one id) raises
    ConditionFailed and nothing after it is uploaded."""
    for table in TABLES:
        models.put_new(_table_key(build_id, table), (out_dir / f"{table}.parquet").read_bytes())
    models.put_new(f"{MODELS}{build_id}/{MANIFEST}", manifest)


def read_pointer(models: Bucket) -> tuple[dict, str] | None:
    """The pointer's manifest and ETag; None when there is no pointer yet. ValueError when it is not a JSON object."""
    found = models.read(POINTER)
    if found is None:
        return None
    body, etag = found
    try:
        doc = json.loads(body)
    except ValueError as err:  # not JSON, or bytes that are no text
        raise ValueError(f"{POINTER} is not JSON: {err}") from err
    if not isinstance(doc, dict):
        raise ValueError(f"{POINTER} is not a JSON object")
    return doc, etag


def newest_receipt(manifest: dict) -> str:
    """The newest receipt key the manifest's build read; ValueError when it names none."""
    try:
        newest = manifest["archive"]["receipts"]["newest_key"]
    except (KeyError, TypeError) as err:
        raise ValueError(f"the manifest names no archive.receipts.newest_key: {err!r}") from err
    if not isinstance(newest, str):
        raise ValueError(f"the manifest's archive.receipts.newest_key is not a key: {newest!r}")
    return newest


def move_pointer(models: Bucket, manifest: bytes, newest: str, tries: int = POINTER_TRIES) -> tuple[str, str]:
    """("moved", this build's id) once the pointer holds `manifest`, or ("kept", the pointer's build id) when the
    pointer's build read a newer receipt than `newest`. Each try reads the pointer; a refused write (ConditionFailed:
    412 or 409) leads to the next try. Any other error, an unreadable pointer among them, is raised at once.
    PointerError after `tries` refusals."""
    build = json.loads(manifest)["build_id"]
    for _ in range(tries):
        current = read_pointer(models)
        if current is None:
            try:
                models.put_new(POINTER, manifest)
            except ConditionFailed:  # another run wrote the first pointer meanwhile: read it and decide again
                continue
            return "moved", build
        pointer, etag = current
        if newest < newest_receipt(pointer):
            return "kept", pointer["build_id"]
        try:
            models.replace(POINTER, manifest, etag)
        except ConditionFailed:  # changed since it was read (412), or another write raced this one (409)
            continue
        return "moved", build
    raise PointerError(f"{POINTER}: {tries} writes refused, each after a fresh read; the pointer is left as it is")


def _started(build: str) -> datetime | None:
    """The start time a build id begins with; None for a name that does not begin with one."""
    match = BUILD_START.match(build)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), BUILD_TIME).replace(tzinfo=timezone.utc)
    except ValueError:  # digits in the shape of a time that are no time
        return None


def clean_up(models: Bucket, now: datetime, keep: str, days: int = KEEP_DAYS) -> list[str]:
    """Delete every key of each build under models/ that started more than `days` days before `now`, except the build
    `keep` (the one the pointer names), however old. A key whose part after models/ does not begin with a start time
    is left. Returns the ids deleted, sorted."""
    builds = defaultdict(list)
    for item in models.list(MODELS):
        builds[item.key.split("/")[1]].append(item.key)
    cutoff = now - timedelta(days=days)
    gone = []
    for build in sorted(builds):
        started = _started(build)
        if build != keep and started is not None and started < cutoff:
            for key in builds[build]:
                models.delete(key)
            gone.append(build)
    return gone
