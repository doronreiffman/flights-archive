"""The figures of tests/counting_fixture.py by A0's SQL, outside the code under test: the source of the literals in
tests/test_counting.py's FIXTURE. Not run in CI. Run from the repository root:

    .venv/bin/python scripts/counting_fixture_oracle.py           # the fixture
    .venv/bin/python scripts/counting_fixture_oracle.py --real    # data/model-2026-11-12: should print A2 and A6

It reads A0, A2 and A6 from docs/flight-lookup-figures.md as they stand and changes only the three model paths (to
Parquet files the fixture's rows are written to, in a temporary directory) and `rng`'s output, which keeps the rate
and its ends unrounded and gives the two standard errors themselves in place of their ratios to the plain one. It
imports nothing from src/: the fixture and its helpers are plain rows. `--real` checks that what it runs is A0.
"""
import re
import sys
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "flight-lookup-figures.md").read_text(encoding="utf-8")


def block(heading: str) -> str:
    """The first ```sql block after `heading`."""
    at = DOC.index(heading)
    m = re.compile(r"```sql\n(.*?)```", re.S).search(DOC, at)
    return m.group(1)


def once(s: str, old: str, new: str) -> str:
    assert s.count(old) == 1, old
    return s.replace(old, new)


def a0(model_dir: str) -> str:
    sql = block("## A0. Setup")
    sql = once(sql, "'data/model/flights.parquet'", f"'{model_dir}/flights.parquet'")
    sql = once(sql, "'data/model/observations.parquet'", f"'{model_dir}/observations.parquet'")
    sql = once(sql, "'data/model/snapshots.parquet'", f"'{model_dir}/snapshots.parquet'")
    sql = once(sql, "round(1 / r, 1) AS one_in", "1 / r AS one_in")
    sql = once(sql, "round(1 / (1 / (1 + exp(-(ln(r / (1 - r)) + 2 * se / (r * (1 - r)))))), 1) AS range_from_one_in",
               "1 / (1 / (1 + exp(-(ln(r / (1 - r)) + 2 * se / (r * (1 - r)))))) AS range_from_one_in")
    sql = once(sql, "round(1 / (1 / (1 + exp(-(ln(r / (1 - r)) - 2 * se / (r * (1 - r)))))), 1) AS range_to_one_in",
               "1 / (1 / (1 + exp(-(ln(r / (1 - r)) - 2 * se / (r * (1 - r)))))) AS range_to_one_in")
    sql = once(sql, "round(se_airline_week / sqrt(r * (1 - r) / nn), 2) AS airline_week_se_over_plain, "
                    "round(se_day / sqrt(r * (1 - r) / nn), 2) AS day_se_over_plain",
               "se_airline_week, se_day")
    return sql


def write_fixture(out: Path) -> None:
    sys.path.insert(0, str(ROOT / "tests"))
    import counting_fixture

    table, obs, snaps = counting_fixture.model()
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute("""CREATE TABLE flights (flight_id VARCHAR, airline VARCHAR, flight_no VARCHAR, direction VARCHAR,
        airport VARCHAR, sched_utc_final TIMESTAMP, sched_local_first TIMESTAMP, sched_local_final TIMESTAMP,
        est_utc_final TIMESTAMP, terminal_final INTEGER, counters_final VARCHAR, outcome VARCHAR,
        first_seen_at TIMESTAMP, last_seen_at TIMESTAMP)""")
    cols = ["flight_id", "airline", "flight_no", "direction", "airport", "sched_utc_final", "sched_local_first",
            "sched_local_final", "est_utc_final", "terminal_final", "counters_final", "outcome", "first_seen_at",
            "last_seen_at"]
    assert all(set(r) == set(cols) for r in table)
    con.executemany(f"INSERT INTO flights VALUES ({', '.join('?' * len(cols))})", [[r[c] for c in cols] for r in table])
    con.execute("""CREATE TABLE observations (flight_id VARCHAR, snap_rn BIGINT, observed_at TIMESTAMP,
        sched_utc TIMESTAMP, est_utc TIMESTAMP, status VARCHAR, terminal INTEGER, counters VARCHAR)""")
    ocols = ["flight_id", "snap_rn", "observed_at", "sched_utc", "est_utc", "status", "terminal", "counters"]
    assert all(set(o) == set(ocols) for o in obs)
    con.executemany("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [[o[c] for c in ocols] for o in obs])
    con.execute("""CREATE TABLE snapshots (snap_rn BIGINT, fetched_at TIMESTAMP, confirmed_until TIMESTAMP,
        gap_before_s BIGINT)""")
    con.executemany("INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                    [[rn, s["fetched_at"], s["confirmed_until"], s["gap_before_s"]] for rn, s in enumerate(snaps, 1)])
    for t in ("flights", "observations", "snapshots"):
        con.execute(f"COPY {t} TO '{out / t}.parquet' (FORMAT parquet)")
    con.close()


def show(con, sql: str) -> None:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    print(" | ".join(names))
    for row in cur.fetchall():
        print(" | ".join(repr(v) for v in row))


def run(model_dir: str) -> None:
    con = duckdb.connect()
    con.execute(a0(model_dir))
    print("-- the model: flights, Israel days, lead airlines; closed; closed and cancelled; closed unknown; open")
    show(con, """SELECT count(*) AS flights, count(DISTINCT il_day) AS il_days,
                 count(DISTINCT lead_airline) AS airlines,
                 sum(closed::INT) AS closed, sum((closed AND result = 'cancelled')::INT) AS closed_cancelled,
                 sum((closed AND result = 'unknown')::INT) AS closed_unknown, sum((NOT closed)::INT) AS open_,
                 sum((NOT closed AND result = 'cancelled')::INT) AS open_cancelled,
                 (SELECT count(*) FROM num) AS numbers FROM fl""")
    print("-- A2")
    con.execute(block("## A2.").split("SELECT * FROM rng")[0])
    show(con, "SELECT * FROM rng('a2')")
    print("-- A6")
    con.execute(block("## A6.").split("SELECT * FROM rng")[0])
    show(con, "SELECT * FROM rng('a6') ORDER BY grp DESC")
    print("-- the cancelled flights in each row (h: flight keys), to set beside the fixture's comments")
    show(con, """SELECT h, string_agg(flight_key, ', ' ORDER BY flight_key) AS cancelled_flights FROM cell WHERE k = 1
                 GROUP BY h ORDER BY h DESC""")
    show(con, """SELECT flight_key, string_agg(DISTINCT n.airline || ' ' || n.flight_no, ' + ') AS numbers
                 FROM fl JOIN num n USING (flight_key) WHERE fl.closed AND fl.result = 'cancelled'
                 GROUP BY 1 ORDER BY 1""")


if __name__ == "__main__":
    if "--real" in sys.argv[1:]:
        run(str(ROOT / "data" / "model-2026-11-12"))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(Path(tmp))
            run(tmp)
