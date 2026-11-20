"""The comparison script (scripts/nightly_check.py, docs/nightly-model.md, "The frozen record"): the model the Lambda
wrote, fetched with its hashes checked, against a build on this machine of the same boards laid out from data/, by the
four checks of scripts/tagged_check.py.

The Lambda's side here is what the function writes: Task 5's run(), with the real model.build, on small_archive, into
an in-memory model bucket. Each test gets a copy of that bucket and of the archive the run read, as its data/.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

import model.build
from model.build import TABLES
from model.stage import fingerprint
from model_helpers import at, row, write_receipt, write_snapshot
from nightly.bucket import MemoryBucket, S3Bucket
from nightly.handler import Config, run
from nightly.output import POINTER
from nightly_helpers import NOW, RUNTIME, archive_bucket, small_archive

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "nightly_check.py"
MODEL_BUCKET = "flights-archive-model-modelbucket-x1y2z3"
BUILD = "20261120T014003Z-1a2b3c4d"  # NOW and RUNTIME's request id
IDENTITY = "arn:aws:iam::137953273942:user/doron-admin"


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("nightly_check_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lambda_side(tmp_path_factory) -> tuple[Path, dict[str, bytes]]:
    """small_archive, and the model bucket's objects after one night on it: run() with the real build."""
    root = tmp_path_factory.mktemp("lambda")
    raw, receipts = small_archive(root / "data")
    models = MemoryBucket(MODEL_BUCKET)
    cfg = Config(archive_bucket="flights-archive-archive", model_bucket=MODEL_BUCKET, work_dir=root / "work")
    run(cfg, archive_bucket(raw, receipts), models, RUNTIME, lambda: NOW, lambda url, message: None,
        build=model.build.build, extensions=lambda: [])
    assert json.loads(models.objects[POINTER])["build_id"] == BUILD
    return root / "data", dict(models.objects)


@pytest.fixture
def models(lambda_side) -> MemoryBucket:
    return MemoryBucket(MODEL_BUCKET, lambda_side[1])


@pytest.fixture
def data(lambda_side, tmp_path) -> Path:
    """A copy of the archive the night read: this machine's data/, with raw/ and receipts/."""
    shutil.copytree(lambda_side[0], tmp_path / "data")
    return tmp_path / "data"


def run_main(check, capsys, models: MemoryBucket, data: Path, work: Path, opens: bool = True) -> tuple[int, str, str]:
    """main() on data/ with an opener that hands over `models`; the opener is called once, or never when not
    `opens` (a refusal made before any AWS call)."""
    opened = []

    def opener(name: str) -> MemoryBucket:
        opened.append(name)
        return models

    code = check.main(["--bucket", MODEL_BUCKET, "--work", str(work), "--raw", str(data / "raw"),
                       "--receipts", str(data / "receipts")], opener=opener)
    assert opened == ([MODEL_BUCKET] if opens else [])
    out, err = capsys.readouterr()
    return code, out, err


def pointer(models: MemoryBucket) -> dict:
    return json.loads(models.objects[POINTER])


def set_pointer(models: MemoryBucket, manifest: dict) -> None:
    models.force(POINTER, json.dumps(manifest, sort_keys=True, indent=2).encode())


def test_the_same_boards_compare_identical(check, models, data, tmp_path, capsys):
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, models, data, work)
    assert code == 0, out + err
    manifest = pointer(models)
    receipts, raw = manifest["archive"]["receipts"], manifest["archive"]["raw"]
    con, rows = duckdb.connect(), []
    for table in TABLES:
        file = str(work / "lambda" / f"{table}.parquet")
        n = con.execute("SELECT count(*) FROM read_parquet(?)", [file]).fetchone()[0]
        assert n > 0, table
        rows.append(f"{table}: lambda {n:,}, mac {n:,} rows")
    con.close()
    assert out.splitlines() == [
        f"build {BUILD}, read from {POINTER} in {MODEL_BUCKET}",
        f"newest receipt {receipts['newest_key']}",
        f"newest board {raw['newest_key']}",
        f"inputs: {receipts['objects']:,} receipts, {raw['objects']:,} board files: digests equal",
        f"model fingerprint {fingerprint()}: this checkout's equals the Lambda's",
        *rows,
        check.IDENTICAL,
    ]
    assert err == ""
    assert (receipts["objects"], raw["objects"]) == (3, 2)
    found = {p.name for p in work.iterdir()}
    assert found - {"tmp"} == {"archive", "lambda", "mac", "record", "record.log", "stage"}  # tmp: DuckDB's spill
    for side in ("lambda", "mac"):
        assert sorted(p.name for p in (work / side).iterdir()) == sorted(f"{t}.parquet" for t in TABLES)
    for table in TABLES:  # the tables fetched are the bytes the night uploaded
        assert (work / "lambda" / f"{table}.parquet").read_bytes() == models.objects[f"models/{BUILD}/{table}.parquet"]
    copied = sorted(p.relative_to(work / "archive").as_posix() for p in (work / "archive").rglob("*") if p.is_file())
    assert copied == sorted(key for key in archive_bucket(data / "raw", data / "receipts").objects)
    assert "cancelled in the row" in (work / "record.log").read_text()  # timeline.record's own line, kept out of out
    # read-only: the pointer, then the five tables it names
    assert models.ops == [("read", POINTER)] + [("download", manifest["tables"][t]["key"]) for t in TABLES]


def test_one_changed_value_is_a_difference(check, models, data, tmp_path, capsys):
    manifest = pointer(models)
    entry = manifest["tables"]["flights"]
    original, changed = tmp_path / "flights.parquet", tmp_path / "changed.parquet"
    original.write_bytes(models.objects[entry["key"]])
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"CREATE TABLE t AS SELECT * FROM '{original}'")
    con.execute("UPDATE t SET final_status = 'CHANGED' WHERE rowid = (SELECT min(rowid) FROM t)")
    con.execute(f"COPY t TO '{changed}' (FORMAT PARQUET)")
    body = changed.read_bytes()
    models.force(entry["key"], body)
    entry.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    set_pointer(models, manifest)

    code, out, err = run_main(check, capsys, models, data, tmp_path / "work")
    assert code == 1, out + err
    lines = out.splitlines()
    assert lines[0] == f"build {BUILD}, read from {POINTER} in {MODEL_BUCKET}" and check.IDENTICAL not in lines
    assert [line.split(":")[0] for line in lines[5:10]] == list(TABLES)  # each table's rows, both sides
    # the rows both ways (compare_tables), then load() (compare_load); progress.json is the same on both sides
    assert lines[10:] == ["flights: 1 row only in lambda", "flights: 1 row only in mac", "load(): flights differ"]


def test_a_progress_difference_is_a_difference(check, models, data, tmp_path, capsys, monkeypatch):
    """The tables equal, timeline.record's progress.json not: the script's own name for the check is replaced, never
    tagged_check's or timeline.record's."""
    calls = []

    def progress(a: Path, b: Path, work: Path, names: tuple[str, str]) -> list[str]:
        calls.append((a, b, work, names))
        return ["progress.json differs"]

    monkeypatch.setattr(check, "compare_progress", progress)
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, models, data, work)
    assert code == 1, out + err
    assert calls == [(work / "lambda", work / "mac", work / "record", ("lambda", "mac"))]
    assert out.splitlines()[10:] == ["progress.json differs"] and check.IDENTICAL not in out


def test_inputs_whose_digest_differs_are_refused(check, models, data, tmp_path, capsys):
    newest = pointer(models)["archive"]["receipts"]["newest_key"]
    first = min(p for p in (data / "receipts").rglob("*.json"))
    assert "receipts/" + first.relative_to(data / "receipts").as_posix() <= newest
    first.write_bytes(first.read_bytes() + b"\n")  # still JSON, one byte longer
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, models, data, work)
    assert code == 2, out + err
    assert err.startswith("inputs differ: receipts/") and err.count("listing SHA-256") == 2
    assert out == ""
    assert not (work / "mac").exists() and not (work / "archive").exists()


def test_boards_after_the_newest_keys_are_left_out(check, models, data, tmp_path, capsys):
    """Review Focus 4: boards synced after the Lambda's listing are not part of its build."""
    later = write_snapshot(data / "raw", at(7, day=31), [row(flight_no="004", sched_local="2026-11-01T12:00:00")])
    write_receipt(data / "receipts", later, rows=1)
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, models, data, work)
    assert code == 0, out + err
    assert out.splitlines()[-1] == check.IDENTICAL
    assert not list((work / "archive").rglob("070000Z-*"))


def test_dot_files_are_not_counted(check, models, data, tmp_path, capsys):
    """Review Focus 4: Finder's .DS_Store, in raw/ and in a date folder, is no object of the archive."""
    (data / "raw" / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    day = min((data / "raw").glob("date=*"))
    (day / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    code, out, err = run_main(check, capsys, models, data, tmp_path / "work")
    assert code == 0, out + err
    assert out.splitlines()[-1] == check.IDENTICAL


def test_a_table_whose_hash_differs_is_refused(check, models, data, tmp_path, capsys):
    key = pointer(models)["tables"]["observations"]["key"]
    body = bytearray(models.objects[key])
    body[len(body) // 2] ^= 0xFF  # the same size: only the hash tells
    models.force(key, bytes(body))
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, models, data, work)
    assert code == 2, out + err
    assert err.startswith(f"{key}: ") and "the manifest" in err
    assert not (work / "archive").exists() and not (work / "mac").exists()


def test_another_model_fingerprint_is_refused(check, models, data, tmp_path, capsys):
    manifest = pointer(models)
    manifest["code"]["model_fingerprint"] = "0" * 64
    set_pointer(models, manifest)
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, models, data, work)
    assert code == 2, out + err
    assert fingerprint() in err and "0" * 64 in err
    assert not (work / "archive").exists() and not (work / "mac").exists() and not (work / "stage").exists()


def test_no_pointer_is_refused(check, data, tmp_path, capsys):
    work = tmp_path / "work"
    code, out, err = run_main(check, capsys, MemoryBucket(MODEL_BUCKET), data, work)
    assert code == 2, out + err
    assert err == f"{MODEL_BUCKET} holds no {POINTER}: no build to compare with yet\n"
    assert not work.exists() or not any(work.iterdir())


class FakeSession:
    """A boto3 session whose STS answers `arn`; records each client asked for."""

    def __init__(self, arn: str):
        self.arn = arn
        self.clients: list[str] = []

    def client(self, name: str):
        self.clients.append(name)
        if name == "sts":
            return SimpleNamespace(get_caller_identity=lambda: {"Arn": self.arn, "Account": self.arn.split(":")[4]})
        return SimpleNamespace(name=name)


def test_another_aws_identity_reads_nothing(check):
    session = FakeSession("arn:aws:iam::111122223333:user/someone")
    with pytest.raises(check.Refused, match="arn:aws:iam::111122223333:user/someone"):
        check.open_bucket(MODEL_BUCKET, session)
    assert session.clients == ["sts"]


def test_the_projects_identity_opens_the_bucket(check, monkeypatch):
    sessions = []

    def make(**kwargs):
        sessions.append(kwargs)
        return FakeSession(IDENTITY)

    monkeypatch.setattr(check.boto3, "Session", make)
    bucket = check.open_bucket(MODEL_BUCKET)
    assert sessions == [{"profile_name": "flights-sam", "region_name": "il-central-1"}]
    assert isinstance(bucket, S3Bucket) and bucket.name == MODEL_BUCKET and bucket.client.name == "s3"


def test_a_work_folder_in_use_is_refused(check, models, data, tmp_path, capsys):
    work = tmp_path / "work"
    work.mkdir()
    (work / "notes.txt").write_text("mine\n")
    code, out, err = run_main(check, capsys, models, data, work, opens=False)
    assert code == 2
    assert [p.relative_to(work).as_posix() for p in work.rglob("*")] == ["notes.txt"]
    assert err == f"{work} is not an empty folder: give a new folder, or an empty one\n" and out == ""
    assert models.ops == []


def test_select_keeps_the_keys_up_to_the_newest_in_key_order(check, tmp_path):
    folder = tmp_path / "raw"
    for name in ("date=2026-10-31/070000Z-b/page-000.json.gz", "date=2026-10-30/060000Z-a/page-001.json.gz",
                 "date=2026-10-30/060000Z-a/page-000.json.gz", "date=2026-10-30/.hidden/page-000.json.gz",
                 ".DS_Store"):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(name.encode())
    picked = check.select(folder, "raw/", "raw/date=2026-10-30/060000Z-a/page-001.json.gz")
    assert [(item.key, item.size, path) for item, path in picked] == [
        (f"raw/{name}", len(name), folder / name)
        for name in ("date=2026-10-30/060000Z-a/page-000.json.gz", "date=2026-10-30/060000Z-a/page-001.json.gz")]
    assert check.select(folder, "raw/", None) == []


@pytest.mark.parametrize("folder", ["raw", "receipts"])
def test_a_work_folder_inside_the_archive_is_refused(check, models, data, capsys, folder):
    """The copy and the builds would write into the synced archive: refused before any AWS call."""
    before = sorted(p.relative_to(data).as_posix() for p in data.rglob("*"))
    work = data / folder / "check"
    code, out, err = run_main(check, capsys, models, data, work, opens=False)
    assert code == 2
    assert err == f"{work.resolve()} is inside {(data / folder).resolve()}: the copy and the builds would write " \
                  "into the archive they read\n" and out == ""
    assert sorted(p.relative_to(data).as_posix() for p in data.rglob("*")) == before
    assert models.ops == []
