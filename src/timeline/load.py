"""The model's flights, observations and snapshots, read for the site and the counting rule.

Part of the frozen rule (docs/flight-lookup.md, "The record", condition 1): it imports no other timeline module
but the frozen ones (tests/test_frozen.py). Model times (`*_at`, `*_utc`) come back as naive UTC.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

OBS_COLUMNS = ("flight_id", "snap_rn", "observed_at", "prev_observed_at", "change_kind", "changed_fields",
               "sched_local", "est_local", "sched_utc", "est_utc", "status", "status_he", "terminal", "counters", "zone",
               "airline_name", "airport_name", "city_en", "city_he", "country_en", "country_he")


def _rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def load(model_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    src = {t: str(model_dir / f"{t}.parquet").replace("'", "''") for t in ("flights", "observations", "snapshots")}
    table = _rows(con, f"SELECT * FROM '{src['flights']}' ORDER BY sched_local_final, direction, airline, flight_no, flight_id")
    obs = _rows(con, f"SELECT {', '.join(OBS_COLUMNS)} FROM '{src['observations']}' ORDER BY flight_id, snap_rn")
    snaps = _rows(con, f"""SELECT fetched_at, confirmed_until, lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev, gap_before_s
                           FROM '{src['snapshots']}' ORDER BY snap_rn""")
    return table, obs, snaps
