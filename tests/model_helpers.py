"""Build tiny raw snapshots in the collector's layout, for the model tests."""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

from model import rules

UTC_DAY = datetime(2026, 10, 27)


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


def write_snapshot(raw: Path, fetched_at: datetime, rows: list[dict], ids: bool = True, pages: int = 1) -> str:
    """Write one snapshot (one file per page); returns its snapshot id. Rows get _id 1.. unless given."""
    records = [({"_id": i} | r) if ids and "_id" not in r else r for i, r in enumerate(rows, start=1)]
    sha = hashlib.sha256(json.dumps(records, ensure_ascii=False).encode() + fetched_at.isoformat().encode()).hexdigest()[:12]
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


def build(raw: Path):
    con = rules.connect()
    rules.build_all(con, str(raw / "**" / "*.json.gz"))
    return con


def q(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def one(con, sql: str) -> dict:
    rows = q(con, sql)
    assert len(rows) == 1, rows
    return rows[0]
