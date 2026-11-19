"""The nightly run (docs/nightly-model.md, "What one night does", steps 1 to 10, and the drill): run() on in-memory
buckets, its healthchecks.io pings, the extension check, the configuration, and the guard that keeps src/nightly/ off
the collector's code."""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import shutil
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest
from botocore.exceptions import ClientError

import model.build
from model.build import TABLES
from model.stage import fingerprint
from model_helpers import check_script
from nightly import handler as nightly_handler
from nightly.archive import RAW, RECEIPTS, ArchiveShrunk, CopyError, Listing
from nightly.bucket import ConditionFailed, Item, MemoryBucket
from nightly.handler import (MEMORY_LIMIT, THREADS, WORK_DIR, Config, DrillError, ExtensionError,
                             installed_extensions, parse_event, ping, run)
from nightly.output import CODE_SHA256, POINTER, PointerError, build_id, manifest
from nightly_helpers import COUNTS, NOW, RUNTIME, archive_bucket, fake_build, small_archive

HC = "https://hc-ping.com/abc"
BUILD = "20261120T014003Z-1a2b3c4d"  # NOW and RUNTIME's request id
SECONDS = {"list", "copy", "build", "staging", "upload", "pointer", "clean_up", "total"}
NIGHTLY = Path(nightly_handler.__file__).parent


@pytest.fixture
def archive(tmp_path) -> MemoryBucket:
    return archive_bucket(*small_archive(tmp_path / "source"))


def config(tmp_path: Path, url: str = HC) -> Config:
    return Config(archive_bucket="flights-archive-archive", model_bucket="flights-archive-model", healthcheck_url=url,
                  work_dir=tmp_path / "work")


def night(cfg: Config, archive: MemoryBucket, models: MemoryBucket, pings: list, *, clock=lambda: NOW, **kw) -> dict:
    """run() with the pings collected; a stand-in build and no installed extension unless a test gives its own."""
    kw.setdefault("build", fake_build([]))
    kw.setdefault("extensions", lambda: [])
    return run(cfg, archive, models, RUNTIME, clock, lambda url, message: pings.append((url, message)), **kw)


def listing(bucket: MemoryBucket, prefix: str) -> Listing:
    """What the bucket holds under prefix, read without a call in its ops."""
    return Listing(prefix, tuple(Item(key, len(body)) for key, body in sorted(bucket.objects.items())
                                 if key.startswith(prefix)))


def earlier_build(models: MemoryBucket, archive: MemoryBucket, started: datetime,
                  request: str = "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b", pointer: bool = True) -> str:
    """A build that started at `started`, from the archive as it stands: five tables and a manifest under its own
    folder, and the pointer on it when `pointer`. Written as another run would, so no call is in either bucket's ops.
    Returns its build id."""
    build = build_id(started, request)
    tables = {}
    for table in TABLES:
        key, body = f"models/{build}/{table}.parquet", f"PAR1 earlier {table}".encode()
        models.force(key, body)
        tables[table] = {"key": key, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    body = manifest(build, started, started + timedelta(minutes=2), tables, archive.name, listing(archive, RECEIPTS),
                    listing(archive, RAW), MEMORY_LIMIT, THREADS, {})
    models.force(f"models/{build}/manifest.json", body)
    if pointer:
        models.force(POINTER, body)
    return build


def raising(err: Exception):
    def build(**kwargs):
        raise err
    return build


def writes(bucket: MemoryBucket) -> list[tuple[str, str]]:
    return [(op, key) for op, key in bucket.ops if op in ("put_new", "replace", "delete")]


# configuration and events

def test_config_refuses_a_missing_or_shared_bucket():
    for env, named in (({"ARCHIVE_BUCKET": "flights-archive-archive", "MODEL_BUCKET": " "}, "MODEL_BUCKET"),
                       ({"MODEL_BUCKET": "flights-archive-model"}, "ARCHIVE_BUCKET"),
                       ({"ARCHIVE_BUCKET": "one-bucket", "MODEL_BUCKET": "one-bucket"}, "one-bucket")):
        with pytest.raises(ValueError, match=named):
            Config.from_env(env)
    cfg = Config.from_env({"ARCHIVE_BUCKET": "a", "MODEL_BUCKET": "m", "HEALTHCHECK_URL": f"{HC}/"})
    assert cfg == Config(archive_bucket="a", model_bucket="m", healthcheck_url=HC, work_dir=WORK_DIR)
    assert Config.from_env({"ARCHIVE_BUCKET": "a", "MODEL_BUCKET": "m"}).healthcheck_url == ""
    assert WORK_DIR == Path("/tmp/nightly")


@pytest.mark.parametrize("event, mode", [
    ({"drill": True}, "drill"),
    ({"drill": "true"}, "build"),
    ({"drill": 1}, "build"),
    ({}, "build"),
    (None, "build"),
    ({"version": "0", "source": "aws.scheduler", "detail-type": "Scheduled Event"}, "build"),
])
def test_parse_event(event, mode):
    assert parse_event(event) == mode


# the whole path

def test_a_night_builds_uploads_and_moves_the_pointer(tmp_path):
    raw, receipts = small_archive(tmp_path / "source")
    archive, models, pings = archive_bucket(raw, receipts), MemoryBucket("flights-archive-model"), []
    summary = night(config(tmp_path), archive, models, pings, build=model.build.build)

    assert summary["build_id"] == BUILD and summary["pointer"] == "moved" and summary["pointer_build_id"] == BUILD
    assert models.objects[POINTER] == models.objects[f"models/{BUILD}/manifest.json"]
    pointer = json.loads(models.objects[POINTER])
    assert sorted(pointer["tables"]) == sorted(TABLES)  # the manifest is written with its keys sorted
    uploaded = tmp_path / "lambda"
    uploaded.mkdir()
    for table, entry in pointer["tables"].items():
        body = models.objects[entry["key"]]
        assert entry["bytes"] == len(body) and entry["sha256"] == hashlib.sha256(body).hexdigest()
        (uploaded / f"{table}.parquet").write_bytes(body)

    direct = tmp_path / "direct"
    model.build.build(raw, direct, receipts, stage_dir=tmp_path / "direct-stage", temp_dir=tmp_path / "direct-temp")
    check = check_script()
    assert check.compare_tables(uploaded, direct, names=("lambda", "direct")) == []
    assert check.compare_load(uploaded, direct) == []

    assert pointer["archive"] == {"bucket": archive.name, "receipts": listing(archive, RECEIPTS).summary(),
                                  "raw": listing(archive, RAW).summary()}
    seconds = summary["seconds"]
    assert set(seconds) == SECONDS
    # a two-day archive stages so fast that a figure rounded to 0.1 s can be 0.0
    assert 0 <= seconds["staging"] <= seconds["build"]


def test_the_build_gets_the_copys_folders_and_the_limits(tmp_path, archive):
    cfg, calls, found = config(tmp_path), [], {}
    work, stand_in = cfg.work_dir, fake_build(calls)

    def build(**kwargs):
        found["files"] = sorted(path.relative_to(work / "archive").as_posix()
                                for path in (work / "archive").rglob("*") if path.is_file())
        return stand_in(**kwargs)

    night(cfg, archive, MemoryBucket("models"), [], build=build)
    assert calls == [{"raw_dir": work / "archive" / "raw", "out_dir": work / "out",
                      "receipts_dir": work / "archive" / "receipts", "stage_dir": work / "stage",
                      "temp_dir": work / "temp", "memory_limit": "1GB", "threads": 2}]
    assert found["files"] == sorted(archive.objects)  # the copy is where the build reads
    assert (MEMORY_LIMIT, THREADS) == ("1GB", 2)


def test_the_work_folder_is_emptied_first(tmp_path, archive):
    cfg, found = config(tmp_path), {}
    work, stand_in = cfg.work_dir, fake_build([])
    (work / "out.building").mkdir(parents=True)  # left by a run killed while writing its model
    (work / "stage" / "raw" / "date=2026-10-30").mkdir(parents=True)  # and its stage
    (work / "leftover.json").write_text("{}")

    def build(**kwargs):
        found["names"] = sorted(path.name for path in work.iterdir())
        found["stage"] = kwargs["stage_dir"].exists()
        return stand_in(**kwargs)

    night(cfg, archive, MemoryBucket("models"), [], build=build)
    assert found == {"names": ["archive"], "stage": False}


def test_the_work_folder_is_emptied_after_a_success(tmp_path, archive):
    cfg = config(tmp_path)
    night(cfg, archive, MemoryBucket("models"), [])
    assert not cfg.work_dir.exists()


@pytest.mark.parametrize("earlier", [False, True], ids=["first night", "a later night"])
def test_tables_then_manifest_then_pointer(tmp_path, archive, earlier):
    models = MemoryBucket("models")
    if earlier:
        earlier_build(models, archive, NOW - timedelta(days=1))
    night(config(tmp_path), archive, models, [])
    tables = [("put_new", f"models/{BUILD}/{table}.parquet") for table in TABLES]
    assert models.ops == [("read", POINTER), *tables, ("put_new", f"models/{BUILD}/manifest.json"),
                          ("read", POINTER), ("replace" if earlier else "put_new", POINTER), ("list", "models/")]
    assert all(op == "put_new" for op, key in writes(models) if key.startswith("models/"))


# failures

def test_a_failed_build_leaves_the_pointer_as_it_was(tmp_path, archive):
    models, pings = MemoryBucket("models"), []
    earlier_build(models, archive, NOW - timedelta(days=1))
    before = dict(models.objects)
    with pytest.raises(ValueError, match="stop"):
        night(config(tmp_path), archive, models, pings, build=raising(ValueError("stop")))
    assert models.objects == before and writes(models) == []
    assert pings[-1] == (f"{HC}/fail", "ValueError: stop")


def test_a_failed_upload_leaves_the_pointer_as_it_was(tmp_path, archive):
    models = MemoryBucket("models")
    earlier_build(models, archive, NOW - timedelta(days=1))
    pointer = models.objects[POINTER]
    third = f"models/{BUILD}/{TABLES[2]}.parquet"
    models.fail[("put_new", third)] = [ClientError({"Error": {"Code": "InternalError", "Message": "try again"}},
                                                   "PutObject")]
    with pytest.raises(ClientError):
        night(config(tmp_path), archive, models, [])
    assert models.objects[POINTER] == pointer
    assert f"models/{BUILD}/manifest.json" not in models.objects
    assert writes(models) == [("put_new", f"models/{BUILD}/{table}.parquet") for table in TABLES[:3]]


def test_a_second_run_with_the_same_build_id_changes_nothing(tmp_path, archive):
    cfg, models = config(tmp_path), MemoryBucket("models")
    night(cfg, archive, models, [])
    first = dict(models.objects)
    with pytest.raises(ConditionFailed):
        night(cfg, archive, models, [])
    assert models.objects == first


def test_a_failed_night_deletes_nothing(tmp_path, archive):
    models = MemoryBucket("models")
    named = earlier_build(models, archive, NOW - timedelta(days=40))  # the pointer's build
    other = earlier_build(models, archive, NOW - timedelta(days=35), request="9f8e7d6c-5b4a-3928-1706-f5e4d3c2b1a0",
                          pointer=False)
    before = dict(models.objects)
    assert {key.split("/")[1] for key in before if key.startswith("models/")} == {named, other}
    with pytest.raises(ValueError, match="stop"):
        night(config(tmp_path), archive, models, [], build=raising(ValueError("stop")))
    assert models.objects == before and writes(models) == []


def test_old_builds_are_deleted_after_a_success(tmp_path, archive):
    models = MemoryBucket("models")
    named = earlier_build(models, archive, NOW - timedelta(days=40))
    other = earlier_build(models, archive, NOW - timedelta(days=35), request="9f8e7d6c-5b4a-3928-1706-f5e4d3c2b1a0",
                          pointer=False)
    recent = earlier_build(models, archive, NOW - timedelta(days=29), request="5a5b5c5d-0000-1111-2222-333344445555",
                           pointer=False)
    summary = night(config(tmp_path), archive, models, [])
    assert summary["deleted"] == sorted([named, other])
    assert {key.split("/")[1] for key in models.objects if key.startswith("models/")} == {recent, BUILD}


def test_a_shrunk_archive_fails_the_night(tmp_path, archive):
    models, calls = MemoryBucket("models"), []
    earlier_build(models, archive, NOW - timedelta(days=1))
    doc = json.loads(models.objects[POINTER])
    doc["archive"]["receipts"]["objects"] += 1  # the last build read one receipt more than the bucket now holds
    models.force(POINTER, json.dumps(doc).encode())
    with pytest.raises(ArchiveShrunk):
        night(config(tmp_path), archive, models, [], build=fake_build(calls))
    assert [op for op, _ in archive.ops] == ["list", "list"] and calls == []


def _no_newest_receipt(archive: MemoryBucket) -> bytes:
    models = MemoryBucket("scratch")
    earlier_build(models, archive, NOW - timedelta(days=1))
    doc = json.loads(models.objects[POINTER])
    del doc["archive"]["receipts"]["newest_key"]
    return json.dumps(doc).encode()


@pytest.mark.parametrize("body", [lambda archive: b"not json", lambda archive: b"[]", _no_newest_receipt],
                         ids=["not json", "not an object", "no newest receipt"])
def test_an_unreadable_pointer_fails_the_night(tmp_path, archive, body):
    body = body(archive)
    models, pings = MemoryBucket("models", {POINTER: body}), []
    with pytest.raises(ValueError):
        night(config(tmp_path), archive, models, pings)
    assert models.objects == {POINTER: body} and models.ops == [("read", POINTER)]
    assert archive.ops == []  # failed before the archive was listed, so nothing was downloaded
    assert pings[-1][0] == f"{HC}/fail"


@pytest.mark.parametrize("when, answers", [("before", [["httpfs"], []]), ("after", [[], ["httpfs"]])])
def test_an_installed_extension_fails_the_night(tmp_path, archive, when, answers):
    models, pings, calls, found = MemoryBucket("models"), [], [], iter(answers)
    with pytest.raises(ExtensionError, match=f"{when} the build.*httpfs") as err:
        night(config(tmp_path), archive, models, pings, build=fake_build(calls), extensions=lambda: next(found))
    if when == "before":
        assert ("list", RECEIPTS) not in archive.ops and calls == []
    else:
        assert len(calls) == 1 and writes(models) == []
    assert pings[-1] == (f"{HC}/fail", f"ExtensionError: {err.value}")


def test_installed_extensions_lists_only_what_is_not_built_in(tmp_path):
    folder = tmp_path / "extensions"  # not the machine's own, so an extension installed there cannot decide this
    folder.mkdir()
    con = duckdb.connect()
    try:
        con.execute(f"SET extension_directory = '{folder}'")
        assert installed_extensions(con) == []
        platform = con.execute("PRAGMA platform").fetchone()[0]
        extension = folder / f"v{duckdb.__version__}" / platform / "httpfs.duckdb_extension"
        extension.parent.mkdir(parents=True)
        extension.write_bytes(b"")  # listed as installed, install_mode UNKNOWN (measured on DuckDB 1.5.6)
        assert installed_extensions(con) == ["httpfs"]
    finally:
        con.close()


def test_installed_extensions_opens_and_closes_a_connection_of_its_own(tmp_path, monkeypatch):
    real, made = duckdb.connect, []

    def connect(*args, **kwargs):
        con = real(*args, **kwargs)
        con.execute(f"SET extension_directory = '{tmp_path}'")
        made.append(con)
        return con

    monkeypatch.setattr(duckdb, "connect", connect)
    assert installed_extensions() == []
    assert len(made) == 1
    with pytest.raises(duckdb.ConnectionException):
        made[0].execute("SELECT 1")  # closed after


# pings

def test_pings_start_then_success_with_the_summary(tmp_path, archive, caplog):
    caplog.set_level(logging.INFO)
    pings = []
    summary = night(config(tmp_path), archive, MemoryBucket("models"), pings)
    assert pings == [(f"{HC}/start", ""), (HC, json.dumps(summary))]
    assert json.dumps(summary) in [record.getMessage() for record in caplog.records]


def _failed_build(archive, models, kw):
    kw["build"] = raising(ValueError("stop"))


def _short_download(archive, models, kw):
    archive.short.add(min(key for key in archive.objects if key.startswith(RAW)))


def _installed_extension(archive, models, kw):
    kw["extensions"] = lambda: ["httpfs"]


def _refused_pointer_writes(archive, models, kw):
    models.fail[("put_new", POINTER)] = [ConditionFailed(f"{POINTER}: PreconditionFailed") for _ in range(3)]


@pytest.mark.parametrize("arrange, error", [
    (_failed_build, ValueError),
    (_short_download, CopyError),
    (_installed_extension, ExtensionError),
    (_refused_pointer_writes, PointerError),
], ids=["a failed build", "a short download", "an installed extension", "three refused pointer writes"])
def test_each_failure_pings_fail_with_its_reason(tmp_path, archive, caplog, arrange, error):
    models, pings, kw = MemoryBucket("models"), [], {}
    arrange(archive, models, kw)
    with pytest.raises(error) as err:
        night(config(tmp_path), archive, models, pings, **kw)
    reason = f"{error.__name__}: {err.value}"
    assert pings == [(f"{HC}/start", ""), (f"{HC}/fail", reason)]
    assert f"nightly build failed: {reason}" in caplog.text


def test_the_drill_fails_before_reading_anything(tmp_path, archive):
    models, pings = MemoryBucket("models"), []
    with pytest.raises(DrillError):
        night(config(tmp_path), archive, models, pings, mode="drill")
    assert archive.ops == [] and models.ops == []
    assert pings == [(f"{HC}/start", ""), (f"{HC}/fail", "DrillError: alert drill: nothing was read or written")]


def test_no_healthcheck_url_means_empty_ping_urls(tmp_path, archive):
    cfg, pings = config(tmp_path, url=""), []
    summary = night(cfg, archive, MemoryBucket("models"), pings)
    assert pings == [("", ""), ("", json.dumps(summary))]
    pings.clear()
    with pytest.raises(DrillError):
        night(cfg, archive, MemoryBucket("models"), pings, mode="drill")
    assert [url for url, _ in pings] == ["", ""]


def test_ping_posts_the_message(monkeypatch):
    calls = []

    class Reply:
        def close(self):
            calls.append("closed")

    def urlopen(req, timeout):
        calls.append((req.full_url, req.data, req.get_method(), req.header_items(), timeout))
        return Reply()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    ping(HC, "é" * 6000)  # 12,000 bytes in UTF-8
    assert calls == [(HC, ("é" * 6000).encode()[:10000], "POST", [], 10), "closed"]  # no User-Agent of our own
    calls.clear()
    ping("", "nothing is sent without an address")
    assert calls == []


def test_a_ping_that_fails_is_logged_not_raised(caplog):
    ping("http://127.0.0.1:9/", "x")  # nothing listens on port 9
    assert "healthcheck ping failed" in caplog.text


# the copy, the configuration slips, the clock

def test_objects_written_during_the_copy_are_left_out(tmp_path, archive):
    listed = {prefix: listing(archive, prefix) for prefix in (RECEIPTS, RAW)}
    new_receipt = "receipts/date=2026-10-31/071502Z-0a1b2c3d4e5f.json"
    new_board = "raw/date=2026-10-31/071502Z-0a1b2c3d4e5f/page-000.json.gz"

    def collector_writes():  # the collector stores a board and its receipt while the copy runs
        archive.force(new_board, b"a new board")
        archive.force(new_receipt, b"{}")

    archive.hooks[("download", min(key for key in archive.objects if key.startswith(RECEIPTS)))] = collector_writes
    models = MemoryBucket("models")
    summary = night(config(tmp_path), archive, models, [])
    downloaded = sorted(key for op, key in archive.ops if op == "download")
    assert new_receipt in archive.objects and new_board in archive.objects
    assert downloaded == sorted(item.key for prefix in (RECEIPTS, RAW) for item in listed[prefix].items)
    doc = json.loads(models.objects[POINTER])
    assert doc["archive"]["receipts"] == listed[RECEIPTS].summary() and doc["archive"]["raw"] == listed[RAW].summary()
    assert summary["copied"] == {"receipts": {"objects": listed[RECEIPTS].objects, "bytes": listed[RECEIPTS].bytes},
                                 "raw": {"objects": listed[RAW].objects, "bytes": listed[RAW].bytes}}


def test_an_empty_archive_fails_the_night(tmp_path):
    models, pings = MemoryBucket("models"), []
    with pytest.raises(ValueError, match="no snapshot files"):
        night(config(tmp_path), MemoryBucket("flights-archive-archive"), models, pings, build=model.build.build)
    assert models.objects == {} and writes(models) == []
    assert pings[-1][0] == f"{HC}/fail"


@pytest.mark.parametrize("started", [NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=2)))],
                         ids=["naive", "Israel in winter"])
def test_a_naive_clock_is_refused(tmp_path, archive, started):
    models, calls = MemoryBucket("models"), []
    with pytest.raises(ValueError, match="UTC"):
        night(config(tmp_path), archive, models, [], clock=lambda: started, build=fake_build(calls))
    assert models.ops == [] and archive.ops == [] and calls == []


# the summary

def test_the_summary_has_every_figure(tmp_path, archive):
    models = MemoryBucket("models")
    summary = night(config(tmp_path), archive, models, [])
    assert set(summary) == {"action", "build_id", "pointer", "pointer_build_id", "seconds", "seconds_left", "copied",
                            "memory_mb", "tmp_mb", "rows", "table_bytes", "deleted", "model_fingerprint",
                            "code_sha256", "duckdb"}
    assert (summary["action"], summary["build_id"], summary["pointer"], summary["pointer_build_id"]) == (
        "built", BUILD, "moved", BUILD)
    seconds = summary["seconds"]
    assert set(seconds) == SECONDS
    assert all(isinstance(value, float) and value >= 0 and value == round(value, 1) for value in seconds.values())
    assert seconds["total"] >= max(seconds[name] for name in SECONDS - {"total"})
    assert summary["seconds_left"] == 600.0
    receipts, raw = listing(archive, RECEIPTS), listing(archive, RAW)
    assert summary["copied"] == {"receipts": {"objects": receipts.objects, "bytes": receipts.bytes},
                                 "raw": {"objects": raw.objects, "bytes": raw.bytes}}
    assert summary["memory_mb"]["size"] == 3008 and 20 < summary["memory_mb"]["peak"] < 16384
    assert set(summary["memory_mb"]) == {"peak", "size"} and set(summary["tmp_mb"]) == {"peak", "size"}
    disk = shutil.disk_usage(tmp_path)
    assert 0 < summary["tmp_mb"]["peak"] <= summary["tmp_mb"]["size"] == round(disk.total / 2**20, 1)
    assert summary["rows"] == COUNTS
    assert summary["table_bytes"] == {table: len(models.objects[f"models/{BUILD}/{table}.parquet"])
                                      for table in TABLES}
    assert summary["deleted"] == []
    assert summary["model_fingerprint"] == fingerprint() and summary["code_sha256"] == CODE_SHA256
    assert summary["duckdb"] == duckdb.__version__
    measured = json.loads(models.objects[POINTER])["measured"]  # what was known when the manifest was written
    assert measured["seconds"] == {name: seconds[name] for name in ("list", "copy", "build", "staging")}
    assert measured["tmp_mb"] == summary["tmp_mb"]
    assert measured["memory_mb"]["size"] == 3008 and measured["memory_mb"]["peak"] <= summary["memory_mb"]["peak"]


def test_staging_is_read_from_the_builds_stage(tmp_path, archive):
    stand_in = fake_build([])

    def build(**kwargs):
        marker = kwargs["stage_dir"] / "d" / "marker.json"
        marker.parent.mkdir(parents=True)
        marker.write_text("{}")
        later = time.time() + 5
        os.utime(marker, (later, later))
        return stand_in(**kwargs)

    summary = night(config(tmp_path), archive, MemoryBucket("models"), [], build=build)
    assert 4.9 <= summary["seconds"]["staging"] < 10


# src/nightly/ never imports the collector (docs/nightly-model.md, section 7)

def collector_imports(source: str) -> list[str]:
    """Each import in `source` that reaches the collector package, absolutely or by a relative path."""
    bad = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "collector" for alias in node.names):
            bad.append(ast.unparse(node))
        elif isinstance(node, ast.ImportFrom):
            parts = node.module.split(".") if node.module else []
            if parts[:1] == ["collector"] or (
                    node.level > 0 and not parts and any(alias.name == "collector" for alias in node.names)):
                bad.append(ast.unparse(node))
    return bad


@pytest.mark.parametrize("source", [
    "import collector", "import collector.core", "import os, collector.store as store", "from collector import core",
    "from collector.handler import ping", "from .. import collector", "from ..collector import core",
    "from ..collector.core import CODE_SHA256", "def f():\n    import collector.core",
])
def test_the_collector_guard_refuses_a_collector_import(source):
    assert collector_imports(source) != []


@pytest.mark.parametrize("source", ["import model.build", "from model.stage import fingerprint",
                                    "from nightly.bucket import Bucket", "from . import output", "import collections"])
def test_the_collector_guard_allows_the_rest(source):
    assert collector_imports(source) == []


def test_nightly_imports_no_collector_module():
    found = {path.name: collector_imports(path.read_text(encoding="utf-8")) for path in sorted(NIGHTLY.glob("*.py"))}
    assert "handler.py" in found and found == {name: [] for name in found}
