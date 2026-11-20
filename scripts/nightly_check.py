"""The nightly check: the model the Lambda built against a build on this machine of the same boards
(docs/nightly-model.md, "The frozen record"). Same code, same boards; what could still differ is the machine.

It reads latest.json from the model bucket, read-only, and downloads the five tables it names, refusing any whose
bytes or SHA-256 differ from the manifest's. From data/ (after `sh scripts/sync.sh`) it lays out every receipt and
board up to the manifest's newest keys, leaving out dot-files (Finder's .DS_Store) and anything synced after the
Lambda's listing, and refuses unless the two listing digests are the manifest's. It checks that this checkout's
model.stage.fingerprint() is the manifest's, builds the copy with model.build on a new stage, and compares the two
models by the four checks of scripts/tagged_check.py: the tables' columns and types, their rows both ways,
timeline.load.load(), and timeline.record's progress.json. Local only: the archive is not in the repository. Run from
the repository root:

    PYTHONPATH=src .venv/bin/python scripts/nightly_check.py --bucket <ModelBucketName> --work DIR \
        [--raw data/raw] [--receipts data/receipts]

--bucket is the model stack's ModelBucketName output, read as profile flights-sam, which must be
arn:aws:iam::137953273942:user/doron-admin. --work is a new or empty folder outside raw/ and receipts/, both checked
before any AWS call: the Lambda's tables go to lambda/, the copy of the boards to archive/, the build to mac/ (staged
in stage/, spilling into tmp/), timeline.record's runs to record/ and its output to record.log. Exit 0 when identical;
1 on any difference, or on an unexpected error, with its traceback; 2 when it refuses to compare, or on a usage error
(argparse's).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import boto3
import duckdb

import model.build
from model.build import TABLES
from model.stage import fingerprint
from nightly.archive import RAW, RECEIPTS, listing_sha256
from nightly.bucket import Bucket, Item, S3Bucket
from nightly.output import POINTER

# scripts/tagged_check.py holds the four checks. They are imported from there, the script's own folder put on the
# path, so that one set of checks judges both comparisons: the tag against the current build, the Lambda against Mac.
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.append(str(SCRIPTS))
from tagged_check import IDENTICAL, compare_load, compare_progress, compare_tables  # noqa: E402

PROFILE = "flights-sam"
REGION = "il-central-1"
IDENTITY = "arn:aws:iam::137953273942:user/doron-admin"
NAMES = ("lambda", "mac")


class Refused(Exception):
    """Anything that stops the comparison before a result."""


def open_bucket(name: str, session=None) -> S3Bucket:
    """The model bucket, read as the project's own AWS identity: Refused, before any S3 client is made, unless STS
    names IDENTITY. With no session given, profile flights-sam in il-central-1."""
    if session is None:
        session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    arn = session.client("sts").get_caller_identity()["Arn"]
    if arn != IDENTITY:
        raise Refused(f"AWS identity {arn}, not {IDENTITY} (profile {PROFILE}): nothing read")
    return S3Bucket(session.client("s3"), name)


def fetch_model(models: Bucket, dest: Path) -> dict:
    """The pointer's manifest, and the five tables it names downloaded into dest; Refused when there is no pointer,
    and for a table whose bytes or SHA-256 are not the manifest's."""
    found = models.read(POINTER)
    if found is None:
        raise Refused(f"{models.name} holds no {POINTER}: no build to compare with yet")
    manifest = json.loads(found[0])
    dest.mkdir(parents=True)
    for table in TABLES:
        entry = manifest["tables"][table]
        path = dest / f"{table}.parquet"
        models.download(entry["key"], path)
        data = path.read_bytes()
        size, sha = len(data), hashlib.sha256(data).hexdigest()
        if size != entry["bytes"] or sha != entry["sha256"]:
            raise Refused(f"{entry['key']}: {size:,} bytes, SHA-256 {sha}; the manifest names {entry['bytes']:,} "
                          f"bytes, SHA-256 {entry['sha256']}")
    return manifest


def select(folder: Path, prefix: str, newest: str | None) -> list[tuple[Item, Path]]:
    """Each file under folder as the archive's object it copies, keyed prefix + its relative path, with that path:
    those at or before `newest` (none when it is None), none with a part of its path starting with "." (a dot-file is
    no object of the archive), in key order."""
    if newest is None:
        return []
    picked = []
    for path in folder.rglob("*"):
        relative = path.relative_to(folder)
        if not path.is_file() or any(part.startswith(".") for part in relative.parts):
            continue
        key = prefix + relative.as_posix()
        if key <= newest:
            picked.append((Item(key, path.stat().st_size), path))
    return sorted(picked, key=lambda pair: pair[0].key)


def _side(name: str, objects: int, size: int, digest: str) -> str:
    return f"{name} {objects:,} objects, {size:,} bytes, listing SHA-256 {digest}"


def lay_out(raw: Path, receipts: Path, manifest: dict, dest: Path) -> None:
    """The receipts and boards the Lambda's build read, copied from receipts/ and raw/ to dest/<key>. Refused, before
    anything is copied, unless each selection's listing digest is the manifest's."""
    chosen = []
    for name, folder, prefix in (("receipts", receipts, RECEIPTS), ("raw", raw, RAW)):
        read = manifest["archive"][name]
        picked = select(folder, prefix, read["newest_key"])
        items = [item for item, _ in picked]
        digest = listing_sha256(items)
        if digest != read["listing_sha256"]:
            raise Refused(f"inputs differ: {prefix} "
                          + _side(f"in {folder}:", len(items), sum(item.size for item in items), digest)
                          + "; " + _side("the Lambda's build read", read["objects"], read["bytes"],
                                         read["listing_sha256"])
                          + " (sh scripts/sync.sh brings data/ up to the archive)")
        chosen += picked
    for folder in (RECEIPTS, RAW):
        (dest / folder).mkdir(parents=True)
    for item, path in chosen:
        target = dest / item.key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def _rows(folder: Path) -> list[int]:
    """Each table's row count in a model folder, in TABLES' order."""
    con = duckdb.connect()
    try:
        return [con.execute("SELECT count(*) FROM read_parquet(?)", [str(folder / f"{table}.parquet")]).fetchone()[0]
                for table in TABLES]
    finally:
        con.close()


def check_work(work: Path, raw: Path, receipts: Path) -> None:
    """Refused unless work is a new or empty folder outside raw/ and receipts/: the copy and the builds write there,
    and a folder inside the synced archive would leave files the next local build of data/ cannot read. Paths are
    compared resolved, as scripts/tagged_check.py compares them."""
    if work.exists() and (not work.is_dir() or any(work.iterdir())):
        raise Refused(f"{work} is not an empty folder: give a new folder, or an empty one")
    for archive in (raw.resolve(), receipts.resolve()):
        if work.resolve().is_relative_to(archive):
            raise Refused(f"{work.resolve()} is inside {archive}: the copy and the builds would write into the "
                          "archive they read")


def compare(models: Bucket, raw: Path, receipts: Path, work: Path) -> int:
    """The Lambda's model against this machine's build of the same boards, in work/. Prints what was compared and
    IDENTICAL or each difference; returns 0 when identical, 1 on any difference. Refused when it cannot compare."""
    check_work(work, raw, receipts)  # main has checked it before any AWS call; kept for a direct call
    lambda_model, mac_model, archive = work / "lambda", work / "mac", work / "archive"
    manifest = fetch_model(models, lambda_model)
    found, built = fingerprint(), manifest["code"]["model_fingerprint"]
    if found != built:
        raise Refused(f"this checkout's model fingerprint is {found}, the Lambda's build ran {built}: not the same "
                      "model code or DuckDB, so a difference would prove nothing about the machine")
    lay_out(raw, receipts, manifest, archive)
    model.build.build(archive / "raw", mac_model, archive / "receipts", stage_dir=work / "stage",
                      temp_dir=work / "tmp")
    with (work / "record.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        progress = compare_progress(lambda_model, mac_model, work / "record", names=NAMES)  # its lines to its log
    lines = (compare_tables(lambda_model, mac_model, names=NAMES) + compare_load(lambda_model, mac_model)
             + progress)

    read = manifest["archive"]
    print(f"build {manifest['build_id']}, read from {POINTER} in {models.name}")
    print(f"newest receipt {read['receipts']['newest_key']}")
    print(f"newest board {read['raw']['newest_key']}")
    print(f"inputs: {read['receipts']['objects']:,} receipts, {read['raw']['objects']:,} board files: digests equal")
    print(f"model fingerprint {found}: this checkout's equals the Lambda's")
    for table, a, b in zip(TABLES, _rows(lambda_model), _rows(mac_model)):
        print(f"{table}: lambda {a:,}, mac {b:,} rows")
    for line in lines or [IDENTICAL]:
        print(line)
    return 1 if lines else 0


def main(argv: list[str], opener: Callable[[str], Bucket] = open_bucket) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bucket", required=True, help="the model bucket: the model stack's ModelBucketName output")
    parser.add_argument("--work", type=Path, required=True,
                        help="a new or empty folder outside raw/ and receipts/, for the copy and the builds")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--receipts", type=Path, default=Path("data/receipts"))
    args = parser.parse_args(argv)
    try:
        check_work(args.work, args.raw, args.receipts)  # both local refusals come before the identity check
        return compare(opener(args.bucket), args.raw, args.receipts, args.work)
    except Refused as refused:
        print(refused, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
