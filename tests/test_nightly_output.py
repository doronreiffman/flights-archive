import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest
from botocore.exceptions import ClientError

from collector import core as collector_core
from model.build import TABLES
from model.stage import fingerprint
from nightly import output
from nightly.archive import Listing
from nightly.bucket import ConditionFailed, Item, MemoryBucket
from nightly.output import (CODE_SHA256, MANIFEST_VERSION, POINTER, PointerError, build_id, clean_up,
                            code_fingerprint, manifest, move_pointer, newest_receipt, read_pointer, table_entries,
                            upload_build)

STARTED = datetime(2026, 11, 20, 1, 40, 3, tzinfo=timezone.utc)
FINISHED = datetime(2026, 11, 20, 1, 52, 41, tzinfo=timezone.utc)
REQUEST = "1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809"
BUILD = "20261120T014003Z-1a2b3c4d"
LAST_NIGHT = "20261119T014002Z-0f1e2d3c"
OTHER = "20261120T015500Z-9f8e7d6c"  # a run by hand that overlaps tonight's
ROWS = {"snapshots": 1210, "observations": 2_400_000, "flights": 98_000, "receipts": 1205}  # build() reports four

# receipt keys as the collector writes them (docs/receipts.md): string order is time order
RECEIPT_OLD = "receipts/date=2026-11-18/224602Z-0123456789ab.json"
RECEIPT_MID = "receipts/date=2026-11-19/224602Z-a1b2c3d4e5f6.json"
RECEIPT_NEW = "receipts/date=2026-11-20/013102Z-f6e5d4c3b2a1.json"
BOARD_NEW = "raw/date=2026-11-20/013102Z-f6e5d4c3b2a1/page-000.json.gz"


def write_tables(folder: Path) -> Path:
    """Five table files of distinct sizes and bytes, as build() leaves them in its model folder."""
    folder.mkdir(parents=True)
    for n, table in enumerate(TABLES):
        (folder / f"{table}.parquet").write_bytes(f"PAR1 {table} ".encode() * (n + 1))
    return folder


def pointer_body(build: str, newest: str | None) -> bytes:
    """A manifest as the pointer holds one, with the fields move_pointer reads."""
    return json.dumps({"build_id": build, "archive": {"receipts": {"newest_key": newest}}},
                      sort_keys=True, indent=2).encode()


MINE = pointer_body(BUILD, RECEIPT_NEW)


def test_build_id_is_the_start_time_and_the_request_id():
    assert build_id(STARTED, REQUEST) == BUILD
    with pytest.raises(ValueError):
        build_id(STARTED.replace(tzinfo=None), REQUEST)
    with pytest.raises(ValueError):  # the same instant at +02:00 (Israel in winter): not UTC
        build_id(STARTED.astimezone(timezone(timedelta(hours=2))), REQUEST)


def test_the_function_fingerprint_is_made_as_the_collectors(tmp_path):
    (tmp_path / "a.py").write_bytes(b"A = 1\n")
    (tmp_path / "b.py").write_bytes(b"B = 2\n")
    (tmp_path / "notes.txt").write_bytes(b"not code")
    first = code_fingerprint(tmp_path)
    assert first == collector_core.code_fingerprint(tmp_path)
    (tmp_path / "b.py").write_bytes(b"B = 3\n")  # one byte changed
    assert code_fingerprint(tmp_path) != first
    assert code_fingerprint(tmp_path) == collector_core.code_fingerprint(tmp_path)
    assert CODE_SHA256 == code_fingerprint(Path(output.__file__).parent)


def test_table_entries_hash_the_files_written(tmp_path):
    out = write_tables(tmp_path / "model")
    entries = table_entries(out, BUILD, ROWS)
    assert list(entries) == list(TABLES)
    for table in TABLES:
        data = (out / f"{table}.parquet").read_bytes()
        expected = {"key": f"models/{BUILD}/{table}.parquet", "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()}
        if table in ROWS:
            expected["rows"] = ROWS[table]
        assert entries[table] == expected
    assert [table for table in TABLES if "rows" in entries[table]] == ["snapshots", "observations", "flights",
                                                                      "receipts"]


def test_the_manifest_records_the_build(tmp_path):
    tables = table_entries(write_tables(tmp_path / "model"), BUILD, ROWS)
    receipts = Listing("receipts/", (Item(RECEIPT_OLD, 310), Item(RECEIPT_NEW, 312)))
    raw = Listing("raw/", (Item(BOARD_NEW, 41_000),))
    measured = {"listing_seconds": 1.5, "copy_seconds": 30.2, "build_seconds": 48.0, "peak_memory_mb": 900.5}
    body = manifest(BUILD, STARTED, FINISHED, tables, "archive-bucket", receipts, raw, "1GB", 2, measured)
    doc = json.loads(body)
    assert body == json.dumps(doc, sort_keys=True, indent=2).encode()
    assert sorted(doc) == ["archive", "build", "build_id", "code", "finished_at", "manifest_version", "measured",
                           "started_at", "tables"]
    assert doc["manifest_version"] == MANIFEST_VERSION == 1
    assert doc["build_id"] == BUILD
    assert (doc["started_at"], doc["finished_at"]) == ("2026-11-20T01:40:03+00:00", "2026-11-20T01:52:41+00:00")
    assert doc["tables"] == tables
    assert doc["archive"] == {"bucket": "archive-bucket", "receipts": receipts.summary(), "raw": raw.summary()}
    assert doc["code"] == {"model_fingerprint": fingerprint(), "function_sha256": CODE_SHA256,
                           "duckdb": duckdb.__version__, "python": platform.python_version(),
                           "machine": platform.machine()}
    assert doc["build"] == {"memory_limit": "1GB", "threads": 2, "stage_reused": False}
    assert doc["measured"] == measured
    assert newest_receipt(doc) == RECEIPT_NEW


def test_the_manifest_refuses_a_time_that_is_not_utc(tmp_path):
    tables = table_entries(write_tables(tmp_path / "model"), BUILD, ROWS)
    listing = Listing("receipts/", ())
    with pytest.raises(ValueError):
        manifest(BUILD, STARTED.replace(tzinfo=None), FINISHED, tables, "a", listing, listing, "1GB", 2, {})
    with pytest.raises(ValueError):
        manifest(BUILD, STARTED, FINISHED.replace(tzinfo=None), tables, "a", listing, listing, "1GB", 2, {})


def test_upload_build_puts_the_tables_then_the_manifest(tmp_path):
    out = write_tables(tmp_path / "model")
    models = MemoryBucket("models")
    upload_build(models, BUILD, out, MINE)
    keys = [f"models/{BUILD}/{table}.parquet" for table in TABLES]
    assert models.ops == [("put_new", key) for key in keys] + [("put_new", f"models/{BUILD}/manifest.json")]
    for table, key in zip(TABLES, keys):
        assert models.objects[key] == (out / f"{table}.parquet").read_bytes()
    assert models.objects[f"models/{BUILD}/manifest.json"] == MINE


def test_an_upload_to_a_build_id_taken_fails_without_its_manifest(tmp_path):
    """Two runs with one id: the second's write-once upload fails, and the first's files stay as they were."""
    out = write_tables(tmp_path / "model")
    taken = f"models/{BUILD}/observations.parquet"
    models = MemoryBucket("models", {taken: b"the first run's"})
    with pytest.raises(ConditionFailed):
        upload_build(models, BUILD, out, MINE)
    assert models.objects[taken] == b"the first run's"
    assert f"models/{BUILD}/manifest.json" not in models.objects


def test_read_pointer_returns_the_manifest_and_its_etag():
    models = MemoryBucket("models")
    assert read_pointer(models) is None
    models.force(POINTER, pointer_body(LAST_NIGHT, RECEIPT_MID))
    doc, etag = read_pointer(models)
    assert doc == json.loads(pointer_body(LAST_NIGHT, RECEIPT_MID))
    assert etag == models.read(POINTER)[1]
    assert newest_receipt(doc) == RECEIPT_MID


def test_the_first_pointer_is_written_once():
    models = MemoryBucket("models")
    assert move_pointer(models, MINE, RECEIPT_NEW) == ("moved", BUILD)
    assert models.ops == [("read", POINTER), ("put_new", POINTER)]
    assert models.objects[POINTER] == MINE


def test_a_newer_build_moves_the_pointer():
    models = MemoryBucket("models", {POINTER: pointer_body(LAST_NIGHT, RECEIPT_MID)})
    assert move_pointer(models, MINE, RECEIPT_NEW) == ("moved", BUILD)
    assert models.ops == [("read", POINTER), ("replace", POINTER)]
    assert models.objects[POINTER] == MINE


def test_the_same_newest_receipt_moves_the_pointer():
    models = MemoryBucket("models", {POINTER: pointer_body(LAST_NIGHT, RECEIPT_NEW)})
    assert move_pointer(models, MINE, RECEIPT_NEW) == ("moved", BUILD)
    assert models.ops == [("read", POINTER), ("replace", POINTER)]
    assert models.objects[POINTER] == MINE


def test_an_older_build_leaves_the_pointer():
    before = pointer_body(OTHER, RECEIPT_NEW)
    models = MemoryBucket("models", {POINTER: before})
    assert move_pointer(models, pointer_body(BUILD, RECEIPT_MID), RECEIPT_MID) == ("kept", OTHER)
    assert models.objects[POINTER] == before
    assert models.ops == [("read", POINTER)]


def test_a_pointer_changed_meanwhile_is_read_again():
    """412: another run replaced the pointer between this run's read and its write."""
    models = MemoryBucket("models", {POINTER: pointer_body(LAST_NIGHT, RECEIPT_OLD)})
    models.hooks[("replace", POINTER)] = lambda: models.force(POINTER, pointer_body(OTHER, RECEIPT_MID))
    assert move_pointer(models, MINE, RECEIPT_NEW) == ("moved", BUILD)
    assert models.ops == [("read", POINTER), ("replace", POINTER)] * 2
    assert models.objects[POINTER] == MINE


def test_a_pointer_moved_past_this_build_meanwhile_is_kept():
    """Read again, decided again: the run that won the race read a newer receipt, so its pointer stays."""
    models = MemoryBucket("models", {POINTER: pointer_body(LAST_NIGHT, RECEIPT_OLD)})
    newer = pointer_body(OTHER, RECEIPT_NEW)
    models.hooks[("replace", POINTER)] = lambda: models.force(POINTER, newer)
    assert move_pointer(models, pointer_body(BUILD, RECEIPT_MID), RECEIPT_MID) == ("kept", OTHER)
    assert models.ops == [("read", POINTER), ("replace", POINTER), ("read", POINTER)]
    assert models.objects[POINTER] == newer


def test_a_409_is_read_again():
    models = MemoryBucket("models", {POINTER: pointer_body(LAST_NIGHT, RECEIPT_OLD)})
    models.fail[("replace", POINTER)] = [ConditionFailed(f"{POINTER}: ConditionalRequestConflict")]
    assert move_pointer(models, MINE, RECEIPT_NEW) == ("moved", BUILD)
    assert models.ops == [("read", POINTER), ("replace", POINTER)] * 2
    assert models.objects[POINTER] == MINE


def test_a_first_write_that_loses_the_race_reads_again():
    models = MemoryBucket("models")
    models.hooks[("put_new", POINTER)] = lambda: models.force(POINTER, pointer_body(OTHER, RECEIPT_MID))
    assert move_pointer(models, MINE, RECEIPT_NEW) == ("moved", BUILD)
    assert models.ops == [("read", POINTER), ("put_new", POINTER), ("read", POINTER), ("replace", POINTER)]
    assert models.objects[POINTER] == MINE


def test_three_refusals_fail_the_night():
    before = pointer_body(LAST_NIGHT, RECEIPT_OLD)
    models = MemoryBucket("models", {POINTER: before})
    models.fail[("replace", POINTER)] = [ConditionFailed(f"{POINTER}: PreconditionFailed") for _ in range(10)]
    with pytest.raises(PointerError):
        move_pointer(models, MINE, RECEIPT_NEW)
    assert models.ops == [("read", POINTER), ("replace", POINTER)] * 3
    assert models.objects[POINTER] == before


def test_a_pointer_deleted_meanwhile_fails_without_a_retry():
    """S3 answers a conditional write to a missing key with 404, not a refused condition: the night fails, and the
    pointer is not written again on a guess."""
    models = MemoryBucket("models", {POINTER: pointer_body(LAST_NIGHT, RECEIPT_OLD)})
    models.hooks[("replace", POINTER)] = lambda: models.delete(POINTER)
    with pytest.raises(ClientError) as raised:
        move_pointer(models, MINE, RECEIPT_NEW)
    assert raised.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    assert models.ops == [("read", POINTER), ("replace", POINTER), ("delete", POINTER)]
    assert POINTER not in models.objects


@pytest.mark.parametrize("body", [
    b"not json",
    b"\xff\xfe not text",
    b"[]",
    json.dumps({"build_id": LAST_NIGHT, "archive": {"receipts": {}}}).encode(),  # no newest_key
    pointer_body(LAST_NIGHT, None),  # newest_key not a string
    json.dumps({"build_id": LAST_NIGHT, "archive": []}).encode(),
], ids=["not-json", "not-text", "not-an-object", "no-newest-key", "newest-key-null", "archive-not-an-object"])
def test_an_unreadable_pointer_fails(body):
    """Review Focus 3: never replaced on a guess; the night fails before anything is written."""
    models = MemoryBucket("models", {POINTER: body})
    with pytest.raises(ValueError):
        move_pointer(models, MINE, RECEIPT_NEW)
    assert models.ops == [("read", POINTER)]
    assert models.objects == {POINTER: body}


NOW = datetime(2026, 11, 20, 1, 40, 3, tzinfo=timezone.utc)


def started(days: int, seconds: int = 0) -> str:
    """The id of a build started `days` (and `seconds`) before NOW."""
    return build_id(NOW - timedelta(days=days, seconds=seconds), REQUEST)


def build_keys(build: str) -> list[str]:
    return [f"models/{build}/{table}.parquet" for table in TABLES] + [f"models/{build}/manifest.json"]


def models_with(*builds: str) -> MemoryBucket:
    objects = {key: key.encode() for build in builds for key in build_keys(build)}
    objects[POINTER] = b"{}"
    return MemoryBucket("models", objects)


def deleted(models: MemoryBucket) -> list[str]:
    return sorted(key for op, key in models.ops if op == "delete")


def test_old_builds_are_deleted():
    old, recent, newest = started(31), started(29), started(1)
    models = models_with(old, recent, newest)
    assert clean_up(models, NOW, keep=newest) == [old]
    assert models.ops[0] == ("list", "models/")
    assert deleted(models) == sorted(build_keys(old))
    assert sorted(models.objects) == sorted(build_keys(recent) + build_keys(newest) + [POINTER])


def test_the_pointers_build_stays_however_old():
    keep, other = started(40), started(35)
    models = models_with(keep, other)
    assert clean_up(models, NOW, keep=keep) == [other]
    assert deleted(models) == sorted(build_keys(other))
    assert sorted(models.objects) == sorted(build_keys(keep) + [POINTER])


def test_a_build_exactly_30_days_old_stays():
    edge, past, newest = started(30), started(30, seconds=1), started(0)
    models = models_with(edge, past, newest)
    assert clean_up(models, NOW, keep=newest) == [past]
    assert sorted(models.objects) == sorted(build_keys(edge) + build_keys(newest) + [POINTER])


def test_keys_that_are_not_a_build_are_left():
    old, newest = started(31), started(1)
    models = models_with(old, newest)
    others = ["models/notes.txt", "models/odd/x.parquet",
              "models/20261001T000000Z/x.parquet",  # no request id after the time
              "models/2026101T000000Z-1a2b3c4d/x.parquet",  # seven digits of date
              "models/x-20261001T000000Z-1a2b3c4d/x.parquet",  # the time not first
              "models/20261399T996199Z-1a2b3c4d/x.parquet"]  # digits that are no time
    for key in others:
        models.force(key, b"kept")
    assert clean_up(models, NOW, keep=newest) == [old]
    assert deleted(models) == sorted(build_keys(old))
    assert sorted(models.objects) == sorted(build_keys(newest) + others + [POINTER])
