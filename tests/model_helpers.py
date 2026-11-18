"""Build tiny raw snapshots in the collector's layout, and the model from them, for the model tests."""
from __future__ import annotations

import functools
import gzip
import hashlib
import importlib.util
import json
import shutil
import tempfile
import types
from datetime import datetime
from pathlib import Path

import model.build
from model import rules
from model.build import TABLES

ROOT = Path(__file__).resolve().parent.parent
UTC_DAY = datetime(2026, 10, 27)
# When true, build() also builds its archive by the rules as tag record-v1 holds them and compares the two
# (tests/test_model_tagged.py turns it on).
COMPARE_WITH_TAGGED: bool = False


def row(**kw) -> dict:
    """One board row with sensible defaults; override any field by its model name."""
    r = {
        "airline": "LY", "flight_no": "001", "airline_name": "EL AL ISRAEL AIRLINES",
        "sched_local": "2026-10-28T10:00:00", "est_local": None, "direction": "D",
        "airport": "JFK", "airport_name": "NEW YORK-JFK", "city_he": "ניו יורק", "city_en": "NEW YORK",
        "country_he": "ארהב", "country_en": "USA", "terminal": 3, "counters": "1-5", "zone": "A",
        "status": "ON TIME", "status_he": "בזמן",
    }
    row_id = kw.pop("_id", None)
    unknown = set(kw) - set(r)
    assert not unknown, unknown
    r.update(kw)
    if r["est_local"] is None:
        r["est_local"] = r["sched_local"]
    inverse = {v: k for k, v in rules.COLUMNS.items()}
    out = {inverse[k]: v for k, v in r.items()}
    return out if row_id is None else {"_id": row_id} | out


def at(hour: int, minute: int = 0, day: int = 27) -> datetime:
    """A fetch time (UTC) on 2026-10-<day>."""
    return UTC_DAY.replace(day=day, hour=hour, minute=minute)


def write_snapshot(raw: Path, fetched_at: datetime, rows: list[dict], ids: bool = True, pages: int = 1,
                   sha: str | None = None) -> str:
    """Write one snapshot (one file per page); returns its snapshot id. Rows get _id 1.. unless given.

    The collector names a snapshot by its content hash; pass sha to imitate the same board stored twice.
    """
    records = [({"_id": i} | r) if ids and "_id" not in r else r for i, r in enumerate(rows, start=1)]
    sha = sha or hashlib.sha256(json.dumps(records, ensure_ascii=False).encode() + fetched_at.isoformat().encode()).hexdigest()[:12]
    folder = raw / f"date={fetched_at:%Y-%m-%d}" / f"{fetched_at:%H%M%S}Z-{sha}"
    folder.mkdir(parents=True)
    size = -(-len(records) // pages)
    for page in range(pages):
        chunk = records[page * size:(page + 1) * size]
        body = json.dumps({"help": "x", "success": True,
                           "result": {"resource_id": rules.__name__, "total": len(records), "records": chunk}},
                          ensure_ascii=False).encode()
        (folder / f"page-{page:03d}.json.gz").write_bytes(gzip.compress(body))
    return f"{fetched_at:%Y-%m-%d}/{fetched_at:%H%M%S}Z-{sha}"


def write_receipt(receipts: Path, snapshot_id: str, *, action: str = "stored", when: datetime | None = None,
                  rows: int = 1, pages: int = 1, version: int = 1) -> str:
    """Write one receipt in the collector's layout (docs/receipts.md) for a snapshot id from write_snapshot.

    A stored receipt runs at its snapshot's own time; give `when` for an unchanged check later on."""
    day, stem = snapshot_id.split("/")
    sha12 = stem.split("-")[1]
    when = when or datetime.strptime(f"{day} {stem[:6]}", "%Y-%m-%d %H%M%S")
    prefix = f"raw/date={day}/{stem}"
    doc = {
        "receipt_version": version, "action": action,
        # Real receipts carry microseconds; the snapshot path keeps whole seconds.
        "run_started_at": f"{when:%Y-%m-%dT%H:%M:%S}.250117+00:00", "downloaded_at": f"{when:%Y-%m-%dT%H:%M:%S}.981004+00:00",
        "code_sha256": "c" * 64, "source": "test", "resource_last_modified": f"{when:%Y-%m-%dT%H:%M:%S}",
        "snapshot": prefix, "snapshot_sha256": sha12 + "0" * 52, "rows": rows,
        "pages": [{"key": f"{prefix}/page-{i:03d}.json.gz", "rows": rows, "sha256": "0" * 64, "latency_ms": 1}
                  for i in range(pages)],
    }
    path = receipts / f"date={when:%Y-%m-%d}" / f"{when:%H%M%S}Z-{sha12}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))
    return str(path)


def _path_time(day_folder: Path, name: str) -> datetime:
    """The time in a collector path: date=YYYY-MM-DD/HHMMSSZ-..."""
    return datetime.strptime(day_folder.name.removeprefix("date=") + name[:6], "%Y-%m-%d%H%M%S")


def cut_archive(raw: Path, receipts: Path, moment: datetime, dest: Path) -> tuple[Path, Path]:
    """The archive as it stood at `moment`: a copy under `dest` of the snapshot folders and receipt files whose path
    time is at or before it. Returns the copy's (raw, receipts)."""
    out_raw, out_receipts = dest / "raw", dest / "receipts"
    out_raw.mkdir(parents=True)
    out_receipts.mkdir(parents=True)
    for folder in sorted(raw.glob("date=*/*Z-*")):
        if folder.is_dir() and _path_time(folder.parent, folder.name) <= moment:
            shutil.copytree(folder, out_raw / folder.parent.name / folder.name)
    for file in sorted(receipts.glob("date=*/*Z-*.json")):
        if _path_time(file.parent, file.name) <= moment:
            (out_receipts / file.parent.name).mkdir(exist_ok=True)
            shutil.copy2(file, out_receipts / file.parent.name / file.name)
    return out_raw, out_receipts


@functools.cache
def check_script() -> types.ModuleType:
    """scripts/tagged_check.py, loaded once and kept: the tagged build and the checks that compare two model folders."""
    spec = importlib.util.spec_from_file_location("tagged_check", ROOT / "scripts" / "tagged_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_new(raw: Path, receipts: Path | None):
    """The build under test: today's rules, on a new connection with the build's limits, spilling into a new folder
    under raw.parent, staged into another that is kept, since the connection's views read it."""
    con = model.build.connect(Path(tempfile.mkdtemp(dir=raw.parent, prefix="duckdb-tmp-")))
    model.build.run(con, raw, receipts, Path(tempfile.mkdtemp(dir=raw.parent, prefix="stage-")))
    return con


def _build_tagged(raw: Path, receipts: Path | None, out: Path) -> None:
    """The tagged build of the same archive into out/, with the KNOWN_ORPHANS a test has set on today's rules."""
    check_script().build_tagged(raw, receipts, out, out.parent / "duckdb-tmp", known_orphans=rules.KNOWN_ORPHANS)


def build(raw: Path, receipts: Path | None = None):
    """A connection holding every table the rules make for raw/ (and receipts/).

    With COMPARE_WITH_TAGGED on, the archive is also built by the rules as tag record-v1 holds them, in folders under
    raw.parent, and an AssertionError is raised unless the two agree: when the new build refuses the archive, the
    tagged build refuses it with the same exception class (and the new build's error is raised again); otherwise the
    tagged build builds it, and compare_tables and compare_load find no difference in the five tables."""
    try:
        con = _build_new(raw, receipts)
    except Exception as refusal:
        if COMPARE_WITH_TAGGED:
            work = Path(tempfile.mkdtemp(dir=raw.parent, prefix="tagged-"))
            try:
                _build_tagged(raw, receipts, work / "tagged")
            except Exception as tagged:
                if type(tagged) is not type(refusal):
                    raise AssertionError(
                        f"the two builds refused this archive with different exception classes: new "
                        f"{type(refusal).__name__} ({refusal}), tagged {type(tagged).__name__} ({tagged})") from refusal
            else:
                raise AssertionError(f"the new build refused this archive ({type(refusal).__name__}: {refusal}), "
                                     "and the tagged build built it") from refusal
        raise
    if COMPARE_WITH_TAGGED:
        work = Path(tempfile.mkdtemp(dir=raw.parent, prefix="tagged-"))
        new, tagged = work / "new", work / "tagged"
        new.mkdir()
        for table in TABLES:
            target = str(new / f"{table}.parquet").replace("'", "''")
            con.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET)")
        try:
            _build_tagged(raw, receipts, tagged)
        except Exception as refusal:
            raise AssertionError(f"the tagged build refused this archive ({type(refusal).__name__}: {refusal}), "
                                 "and the new build built it") from refusal
        check = check_script()
        lines = check.compare_tables(tagged, new) + check.compare_load(tagged, new)
        if lines:
            raise AssertionError("\n".join(lines))
    return con


def q(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def one(con, sql: str) -> dict:
    rows = q(con, sql)
    assert len(rows) == 1, rows
    return rows[0]
