"""The data model's rules, each a named SQL step on one DuckDB connection.

Tables flow in this order (docs/data-model.md names the rules R1..R8):

  raw_rows   every row of every snapshot file, as the board published it
  receipts   one row per acquisition receipt (docs/receipts.md); decides which snapshots are trusted
  rows       R1 local times to UTC, R2 duplicates removed, board key added
  snapshots  one row per snapshot with its counts
  keys       one row per board key (airline, flight no., direction, airport, scheduled time)
  links      R4 retime links between keys; keymap gives each key its physical flight id
  observations  R3 one row per flight per change
  flights    R5-R8 one row per marketed flight (airline + number); the codeshare group is the physical movement

All *_utc columns are naive UTC timestamps; *_local columns are Israel wall-clock as published.
"""
from __future__ import annotations

import glob

import duckdb

TERMINAL_STATUSES = ("DEPARTED", "LANDED", "CANCELED")
RETIME_WINDOW_HOURS = 12
VANISH_HORIZON_HOURS = 1
# A hole in collection longer than this hides what happened to a flight that left the board in it.
GAP_HOURS = 1
# The largest reply the model reads. DuckDB reserves a read buffer per gzipped file from this, so 256 MB ran
# out of memory at 17 files; the collector refuses any reply past 32 MB (core.MAX_BODY_BYTES).
MAX_REPLY_BYTES = 32 * 1024 * 1024
# Receipts (docs/receipts.md). A snapshot newer than every receipt is waiting for its receipt; one this
# long after the newest receipt means receipts/ was synced earlier than raw/.
PENDING_GRACE_MINUTES = 5
RECEIPT_VERSIONS = (1,)
# Snapshots with pages but no receipt that a person has checked against the collector logs (a receipt
# write that failed); they are dropped. Any other unreceipted snapshot stops the build.
KNOWN_ORPHANS: frozenset[str] = frozenset()

# Board field -> model column. Names come from the datastore's field notes, except the
# city pair: the notes label CHLOC1TH "Location1City" and CHLOC1T "...CityHebrew" but the
# data is the other way round (CHLOC1TH holds Hebrew), so the mapping follows the data.
COLUMNS = {
    "CHOPER": "airline",
    "CHFLTN": "flight_no",
    "CHOPERD": "airline_name",
    "CHSTOL": "sched_local",
    "CHPTOL": "est_local",
    "CHAORD": "direction",
    "CHLOC1": "airport",
    "CHLOC1D": "airport_name",
    "CHLOC1TH": "city_he",
    "CHLOC1T": "city_en",
    "CHLOC1CH": "country_he",
    "CHLOCCT": "country_en",
    "CHTERM": "terminal",
    "CHCINT": "counters",
    "CHCKZN": "zone",
    "CHRMINE": "status",
    "CHRMINH": "status_he",
}
KEY = ("airline", "flight_no", "direction", "airport", "sched_local")
# Fields compared between a flight's consecutive appearances (R3). Identity fields are
# constant within a key; sched_local changes only across a retime link.
TRACKED = ("sched_local", "est_local", "status", "status_he", "terminal", "counters", "zone",
           "airline_name", "airport_name", "city_he", "city_en", "country_he", "country_en")

_RECORD_TYPE = "STRUCT(" + ", ".join(['"_id" BIGINT'] + [f"{k} VARCHAR" for k in COLUMNS]) + ")"
_SNAPSHOT_PATH = r"date=(\d{4}-\d{2}-\d{2})/(\d{6})Z-([0-9a-f]{12})/page-(\d{3})\.json\.gz$"
_RECEIPT_COLUMNS = {
    "receipt_version": "INTEGER", "action": "VARCHAR", "run_started_at": "VARCHAR", "downloaded_at": "VARCHAR",
    "code_sha256": "VARCHAR", "resource_last_modified": "VARCHAR", "snapshot": "VARCHAR",
    "snapshot_sha256": "VARCHAR", "rows": "BIGINT",
    "pages": "STRUCT(key VARCHAR, rows BIGINT, sha256 VARCHAR, latency_ms BIGINT)[]",
}
_RECEIPT_SNAPSHOT = r"^raw/date=(\d{4}-\d{2}-\d{2})/(\d{6}Z-[0-9a-f]{12})$"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    # R1. A wall-clock time is valid at an offset if converting back from UTC gives it again.
    con.execute("CREATE MACRO il_ist_ok(t) AS timezone('Asia/Jerusalem', (t - INTERVAL 2 HOUR)::TIMESTAMPTZ) = t")
    con.execute("CREATE MACRO il_idt_ok(t) AS timezone('Asia/Jerusalem', (t - INTERVAL 3 HOUR)::TIMESTAMPTZ) = t")
    # Ambiguous (both valid): the earlier instant, which is the UTC+3 reading. UNSURE.
    # Nonexistent (neither): shift forward an hour into UTC+3, which equals t - 2h.
    con.execute("""CREATE MACRO il_to_utc(t) AS CASE
        WHEN t IS NULL THEN NULL
        WHEN il_idt_ok(t) THEN t - INTERVAL 3 HOUR
        ELSE t - INTERVAL 2 HOUR END""")
    con.execute("CREATE MACRO il_ambiguous(t) AS il_idt_ok(t) AND il_ist_ok(t)")
    con.execute("CREATE MACRO il_nonexistent(t) AS NOT il_idt_ok(t) AND NOT il_ist_ok(t)")
    return con


def load_raw(con, raw_glob: str) -> int:
    """Read every snapshot file matching raw_glob into raw_rows. Returns the row count."""
    path = raw_glob.replace("'", "''")
    renames = ", ".join(f"r.{k} AS {v}" for k, v in COLUMNS.items())
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_rows AS
        WITH f AS (
            SELECT filename,
                   regexp_extract(filename, '{_SNAPSHOT_PATH}', ['d', 't', 'sha', 'page']) AS m,
                   result
            FROM read_json('{path}', filename = true, maximum_object_size = {MAX_REPLY_BYTES},
                           columns = {{'success': 'BOOLEAN', 'result': 'STRUCT(total BIGINT, records {_RECORD_TYPE}[])'}})
        ), u AS (
            SELECT filename, m, result.total AS declared_total, unnest(result.records) AS r FROM f
        )
        SELECT m['d'] || '/' || m['t'] || 'Z-' || m['sha'] AS snapshot_id,
               try_cast(m['d'] || ' ' || substr(m['t'], 1, 2) || ':' || substr(m['t'], 3, 2) || ':' || substr(m['t'], 5, 2) AS TIMESTAMP) AS fetched_at,
               try_cast(m['page'] AS INTEGER) AS page,
               declared_total,
               r."_id" AS row_id,
               {renames}
        FROM u
    """)
    bad = con.execute("SELECT count(*) FROM raw_rows WHERE snapshot_id IS NULL OR fetched_at IS NULL OR snapshot_id = '/Z-'").fetchone()[0]
    if bad:
        raise ValueError(f"{bad} rows come from files whose path is not date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-NNN.json.gz")
    no_total = con.execute("SELECT count(DISTINCT snapshot_id) FROM raw_rows WHERE declared_total IS NULL").fetchone()[0]
    if no_total:
        raise ValueError(f"{no_total} snapshots have no result.total in their reply; completeness cannot be judged")
    return con.execute("SELECT count(*) FROM raw_rows").fetchone()[0]


def load_receipts(con, receipts_glob: str | None) -> int:
    """Read every receipt into `receipts`. No glob or no files gives an empty table: every snapshot is then legacy."""
    if receipts_glob and glob.glob(receipts_glob, recursive=True):
        path = receipts_glob.replace("'", "''")
        cols = ", ".join(f"'{k}': '{v}'" for k, v in _RECEIPT_COLUMNS.items())
        source = f"read_json('{path}', filename = true, columns = {{{cols}}})"
    else:
        source = "(SELECT NULL::VARCHAR AS filename, " + ", ".join(f"NULL::{t} AS {k}" for k, t in _RECEIPT_COLUMNS.items()) + " WHERE false)"
    con.execute(f"""
        CREATE OR REPLACE TABLE receipts AS
        WITH r AS (SELECT *, regexp_extract(snapshot, '{_RECEIPT_SNAPSHOT}', ['d', 'stem']) AS m FROM {source})
        SELECT 'receipts/' || regexp_extract(filename, 'date=[^/]+/[^/]+$') AS receipt_file,
               receipt_version, action,
               run_started_at::TIMESTAMPTZ::TIMESTAMP AS run_started_at,
               downloaded_at::TIMESTAMPTZ::TIMESTAMP AS downloaded_at,
               try_cast(resource_last_modified AS TIMESTAMP) AS resource_last_modified,
               nullif(m['d'] || '/' || m['stem'], '/') AS snapshot_id,
               snapshot_sha256, rows, len(pages) AS pages, code_sha256
        FROM r
    """)
    versions = ", ".join(str(v) for v in RECEIPT_VERSIONS)
    odd = [r[0] for r in con.execute(f"""
        SELECT receipt_file FROM receipts
        WHERE receipt_version NOT IN ({versions}) OR receipt_version IS NULL OR action NOT IN ('stored', 'unchanged')
           OR action IS NULL OR snapshot_id IS NULL ORDER BY 1""").fetchall()]
    if odd:
        raise ValueError(f"{len(odd)} receipts carry a receipt_version, action or snapshot this model does not "
                         f"understand: {odd[:10]}; update src/model/rules.py before building")
    return con.execute("SELECT count(*) FROM receipts").fetchone()[0]


def _check_receipts(con) -> None:
    """Stop the build when the local copy cannot be trusted. A silent drop could move a flight's first
    CANCELED sighting by a refresh without flagging it (docs/receipts.md, "Model changes")."""
    def ids(sql: str) -> list[str]:
        return [r[0] for r in con.execute(sql).fetchall()]

    missing = ids("SELECT DISTINCT snapshot_id FROM receipts WHERE snapshot_id NOT IN (SELECT snapshot_id FROM snapshot_files) ORDER BY 1")
    if missing:
        raise ValueError(f"{len(missing)} receipts name snapshots with no files under raw/: {missing[:10]}. Run scripts/sync.sh.")
    differ = ids("""SELECT snapshot_id FROM snapshot_files
                    WHERE receipt = 'receipted' AND (file_rows <> receipt_rows OR file_pages <> receipt_pages) ORDER BY 1""")
    if differ:
        raise ValueError(f"{len(differ)} receipted snapshots differ from their files: {differ[:10]}. The archive cannot "
                         "produce this: re-sync raw/, or suspect a collector bug.")
    stale = ids(f"""SELECT snapshot_id FROM snapshot_files
                    WHERE receipt = 'pending' AND fetched_at > newest_receipt + INTERVAL {PENDING_GRACE_MINUTES} MINUTE ORDER BY 1""")
    if stale:
        raise ValueError(f"receipts/ is older than raw/: {len(stale)} snapshots come more than {PENDING_GRACE_MINUTES} min "
                         f"after the newest receipt (first: {stale[0]}). Run scripts/sync.sh.")
    unreceipted = ids("SELECT snapshot_id FROM snapshot_files WHERE receipt = 'unreceipted' ORDER BY 1")
    if unreceipted:
        raise ValueError(f"{len(unreceipted)} snapshots have pages but no receipt: {unreceipted[:10]}. Re-run scripts/sync.sh; "
                         "if it persists, check the collector logs at those times and list confirmed orphans in "
                         "KNOWN_ORPHANS (src/model/rules.py).")


def convert_times_and_dedupe(con) -> None:
    """R1 and R2: rows = raw_rows with UTC times, one row per (snapshot, board key).

    A snapshot whose content hash (the sha12 in its path) equals the previous snapshot's is the
    same board stored twice (the collector's snapshot write succeeded but its state write failed);
    it is dropped and counted on the kept snapshot as identical_repeats. A snapshot whose files
    hold fewer rows than the reply's own `total` is an interrupted multi-page store; it is dropped
    and listed in snapshot_runs with incomplete = true.

    Receipts decide trust first: `receipted` and `legacy` snapshots are kept, `pending` and `orphan`
    ones dropped, and anything else stops the build (_check_receipts).
    """
    fields = ", ".join(COLUMNS.values())
    key = ", ".join(KEY)
    orphans = ", ".join(f"'{o}'" for o in sorted(KNOWN_ORPHANS)) or "NULL"
    con.execute(f"""
        CREATE OR REPLACE TABLE snapshot_files AS
        WITH s AS (SELECT snapshot_id, min(fetched_at) AS fetched_at, right(snapshot_id, 12) AS sha,
                          count(*) < max(declared_total) AS incomplete,
                          count(*) AS file_rows, count(DISTINCT page) AS file_pages
                   FROM raw_rows GROUP BY snapshot_id),
             b AS (SELECT min(date_trunc('second', run_started_at)) AS first_receipt,
                          max(date_trunc('second', run_started_at)) AS newest_receipt FROM receipts),
             st AS (SELECT snapshot_id, rows AS receipt_rows, pages AS receipt_pages FROM receipts WHERE action = 'stored')
        SELECT s.*, st.receipt_rows, st.receipt_pages, b.newest_receipt,
               CASE WHEN st.snapshot_id IS NOT NULL THEN 'receipted'
                    WHEN b.first_receipt IS NULL OR s.fetched_at < b.first_receipt THEN 'legacy'
                    WHEN s.fetched_at > b.newest_receipt THEN 'pending'
                    WHEN s.snapshot_id IN ({orphans}) THEN 'orphan'
                    ELSE 'unreceipted' END AS receipt
        FROM s CROSS JOIN b LEFT JOIN st USING (snapshot_id)
    """)
    _check_receipts(con)
    con.execute("""
        CREATE OR REPLACE TABLE snapshot_runs AS
        WITH c AS (SELECT * FROM snapshot_files WHERE NOT incomplete AND receipt IN ('receipted', 'legacy')),
             o AS (SELECT *, lag(sha) OVER (ORDER BY fetched_at, snapshot_id) AS prev_sha FROM c),
             g AS (SELECT *, sha IS NOT DISTINCT FROM prev_sha AS repeat,
                          count(*) FILTER (WHERE sha IS DISTINCT FROM prev_sha)
                              OVER (ORDER BY fetched_at, snapshot_id ROWS UNBOUNDED PRECEDING) AS grp
                   FROM o)
        SELECT snapshot_id, fetched_at, incomplete, receipt, repeat, count(*) OVER (PARTITION BY grp) - 1 AS identical_repeats FROM g
        UNION ALL
        SELECT snapshot_id, fetched_at, incomplete, receipt, false, 0 FROM snapshot_files
        WHERE incomplete OR receipt NOT IN ('receipted', 'legacy')
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE rows AS
        WITH typed AS (
            SELECT snapshot_id, fetched_at, page, row_id,
                   airline, flight_no, airline_name,
                   try_cast(sched_local AS TIMESTAMP) AS sched_local,
                   try_cast(nullif(est_local, '') AS TIMESTAMP) AS est_local,
                   direction, airport, airport_name, city_he, city_en, country_he, country_en,
                   try_cast(terminal AS INTEGER) AS terminal,
                   counters, zone, status, status_he
            FROM raw_rows
            WHERE snapshot_id IN (SELECT snapshot_id FROM snapshot_runs
                                  WHERE NOT repeat AND NOT incomplete AND receipt IN ('receipted', 'legacy'))
        ), ranked AS (
            SELECT *,
                   row_number() OVER (PARTITION BY snapshot_id, {key} ORDER BY row_id) AS key_rank
            FROM typed
        )
        SELECT * EXCLUDE (key_rank),
               md5(concat_ws('|', coalesce(airline, ''), coalesce(flight_no, ''), coalesce(direction, ''),
                             coalesce(airport, ''), coalesce(sched_local::VARCHAR, ''))) AS key_id,
               il_to_utc(sched_local) AS sched_utc,
               il_ambiguous(sched_local) AS sched_ambiguous,
               il_nonexistent(sched_local) AS sched_nonexistent,
               il_to_utc(est_local) AS est_utc,
               il_ambiguous(est_local) AS est_ambiguous,
               il_nonexistent(est_local) AS est_nonexistent
        FROM ranked
        WHERE key_rank = 1
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE snapshots AS
        WITH per_file AS (
            SELECT snapshot_id, min(fetched_at) AS fetched_at, count(DISTINCT page) AS pages, count(*) AS rows_raw,
                   count(*) - count(DISTINCT ({fields})) AS duplicate_rows
            FROM raw_rows GROUP BY snapshot_id
        ), conflicts AS (
            SELECT snapshot_id, count(*) - count(DISTINCT ({key})) AS key_conflicts
            FROM (SELECT DISTINCT snapshot_id, {fields} FROM raw_rows) GROUP BY snapshot_id
        ), kept AS (
            SELECT snapshot_id, count(*) AS rows, min(sched_local) AS min_sched_local, max(sched_local) AS max_sched_local,
                   count(*) FILTER (WHERE sched_local IS NULL) AS unparsed_sched,
                   count(*) FILTER (WHERE est_local IS NULL) AS missing_est
            FROM rows GROUP BY snapshot_id
        )
        SELECT snapshot_id, fetched_at, row_number() OVER (ORDER BY fetched_at, snapshot_id) AS snap_rn,
               epoch(fetched_at - lag(fetched_at) OVER (ORDER BY fetched_at, snapshot_id))::BIGINT AS gap_before_s,
               pages, rows_raw, rows, duplicate_rows, key_conflicts, unparsed_sched, missing_est, identical_repeats,
               min_sched_local, max_sched_local
        FROM per_file JOIN conflicts USING (snapshot_id) JOIN kept USING (snapshot_id)
        JOIN (SELECT snapshot_id, identical_repeats FROM snapshot_runs) USING (snapshot_id)  -- kept has no repeats or incompletes
    """)


def link_retimes(con) -> None:
    """R4: keys, links and keymap (key_id -> flight_id, the first key of its retime chain)."""
    terminal = ", ".join(f"'{s}'" for s in TERMINAL_STATUSES)
    con.execute("""
        CREATE OR REPLACE TABLE keys AS
        SELECT key_id, any_value(airline) AS airline, any_value(flight_no) AS flight_no,
               any_value(direction) AS direction, any_value(airport) AS airport,
               any_value(sched_local) AS sched_local, any_value(sched_utc) AS sched_utc,
               min(s.snap_rn) AS first_rn, max(s.snap_rn) AS last_rn,
               min(r.fetched_at) AS first_seen_at, max(r.fetched_at) AS last_seen_at,
               arg_min(status, s.snap_rn) AS first_status, arg_max(status, s.snap_rn) AS last_status
        FROM rows r JOIN snapshots s USING (snapshot_id)
        GROUP BY key_id
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE link_candidates AS
        SELECT o.key_id AS old_key, n.key_id AS new_key,
               abs(epoch(n.sched_utc - o.sched_utc)) AS gap_s
        FROM keys o JOIN keys n
          ON n.airline = o.airline AND n.flight_no = o.flight_no
         AND n.direction = o.direction AND n.airport = o.airport
         AND n.key_id <> o.key_id
         AND n.first_rn = o.last_rn + 1
        WHERE o.last_status NOT IN ({terminal}) AND n.first_status NOT IN ({terminal})
          AND abs(epoch(n.sched_utc - o.sched_utc)) <= {RETIME_WINDOW_HOURS} * 3600
          AND epoch(n.first_seen_at - o.last_seen_at) <= {GAP_HOURS} * 3600
    """)
    # One-to-one: each side's nearest candidate, with no tie on either side.
    con.execute("""
        CREATE OR REPLACE TABLE links AS
        WITH ranked AS (
            SELECT *,
                   rank() OVER (PARTITION BY old_key ORDER BY gap_s) AS r_old,
                   count(*) OVER (PARTITION BY old_key, gap_s) AS n_old,
                   rank() OVER (PARTITION BY new_key ORDER BY gap_s) AS r_new,
                   count(*) OVER (PARTITION BY new_key, gap_s) AS n_new
            FROM link_candidates
        )
        SELECT old_key, new_key, gap_s FROM ranked
        WHERE r_old = 1 AND n_old = 1 AND r_new = 1 AND n_new = 1
    """)
    con.execute("""
        CREATE OR REPLACE TABLE keymap AS
        WITH RECURSIVE chain(flight_id, key_id, hop) AS (
            SELECT key_id, key_id, 0 FROM keys WHERE key_id NOT IN (SELECT new_key FROM links)
            UNION ALL
            SELECT c.flight_id, l.new_key, c.hop + 1 FROM chain c JOIN links l ON l.old_key = c.key_id
        )
        SELECT flight_id, key_id, hop FROM chain
    """)


def build_observations(con) -> None:
    """R3: one row per flight per change, compared with the flight's previous appearance."""
    tracked = list(TRACKED)
    lags = ", ".join(f"lag({c}) OVER w AS prev_{c}" for c in tracked)
    diffs = ", ".join(f"CASE WHEN {c} IS DISTINCT FROM prev_{c} THEN '{c}' END" for c in tracked)
    con.execute(f"""
        CREATE OR REPLACE TABLE observations AS
        WITH seq AS (
            SELECT k.flight_id, r.*, s.snap_rn,
                   lag(r.key_id) OVER w AS prev_key_id,
                   lag(r.fetched_at) OVER w AS prev_observed_at,
                   {lags}
            FROM rows r JOIN keymap k USING (key_id) JOIN snapshots s USING (snapshot_id)
            WINDOW w AS (PARTITION BY k.flight_id ORDER BY s.snap_rn)
        ), marked AS (
            SELECT *, CASE WHEN prev_key_id IS NULL THEN []::VARCHAR[] ELSE list_filter([{diffs}], lambda x: x IS NOT NULL) END AS changed_fields,
                   CASE WHEN prev_key_id IS NULL THEN 'first'
                        WHEN key_id <> prev_key_id THEN 'retime'
                        ELSE 'change' END AS change_kind
            FROM seq
        )
        SELECT flight_id, key_id, snapshot_id, snap_rn, fetched_at AS observed_at, prev_observed_at,
               change_kind, changed_fields,
               airline, flight_no, airline_name, direction, airport, airport_name,
               city_en, city_he, country_en, country_he,
               sched_local, sched_utc, sched_ambiguous, sched_nonexistent,
               est_local, est_utc, est_ambiguous, est_nonexistent,
               terminal, counters, zone, status, status_he
        FROM marked
        WHERE change_kind <> 'change' OR len(changed_fields) > 0
        ORDER BY flight_id, snap_rn
    """)


def build_flights(con) -> None:
    """R5-R8: one row per marketed flight; its codeshare group is the physical movement."""
    latest = con.execute("SELECT max(snap_rn) FROM snapshots").fetchone()[0] or 0
    # R5/R6: the group a flight sat in at its last appearance, and the operator guess.
    con.execute("""
        CREATE OR REPLACE TABLE codeshares AS
        WITH r AS (
            SELECT k.flight_id, r.snapshot_id, s.snap_rn, r.airline, r.flight_no, r.counters,
                   md5(concat_ws('|', r.snapshot_id, r.direction, r.airport, r.sched_local::VARCHAR,
                                 coalesce(r.est_local::VARCHAR, ''), coalesce(r.terminal::VARCHAR, ''), coalesce(r.counters, ''))) AS group_key
            FROM rows r JOIN keymap k USING (key_id) JOIN snapshots s USING (snapshot_id)
        ), groups AS (
            SELECT group_key,
                   list(struct_pack(flight_id := flight_id, airline := airline, flight_no := flight_no,
                                    num := try_cast(regexp_extract(flight_no, '[0-9]+') AS INTEGER))
                        ORDER BY try_cast(regexp_extract(flight_no, '[0-9]+') AS INTEGER) NULLS LAST, airline, flight_id) AS members
            FROM r GROUP BY group_key
        ), at_last AS (
            SELECT flight_id, arg_max(group_key, snap_rn) AS group_key, arg_max(counters, snap_rn) AS counters
            FROM r GROUP BY flight_id
        )
        SELECT a.flight_id,
               md5(list_aggregate(list_transform(g.members, lambda m: m.flight_id), 'string_agg', '|')) AS codeshare_group_id,
               len(g.members) AS codeshare_size,
               g.members[1].airline AS operating_airline,
               g.members[1].flight_no AS operating_flight_no,
               len(g.members) > 1 AS operating_is_guess,
               CASE WHEN coalesce(a.counters, '') <> '' THEN 'counters' ELSE 'time-only' END AS codeshare_basis
        FROM at_last a JOIN groups g USING (group_key)
    """)
    terminal = ", ".join(f"'{s}'" for s in TERMINAL_STATUSES)
    fin_fields = ("sched_local", "sched_utc", "sched_ambiguous", "sched_nonexistent", "est_local", "est_utc",
                  "status", "status_he", "terminal", "counters", "zone", "airline_name", "airport_name",
                  "city_en", "city_he", "country_en", "country_he")
    fin = ", ".join(f"{c} := {c}" for c in fin_fields)
    con.execute(f"""
        CREATE OR REPLACE TABLE flights AS
        WITH seen AS (
            SELECT k.flight_id, count(DISTINCT r.snapshot_id) AS snapshots_seen,
                   max(s.snap_rn) AS last_rn, max(r.fetched_at) AS last_seen_at
            FROM rows r JOIN keymap k USING (key_id) JOIN snapshots s USING (snapshot_id)
            GROUP BY k.flight_id
        ), chain AS (
            SELECT flight_id, list(key_id ORDER BY hop) AS key_ids, count(*) - 1 AS retimes
            FROM keymap GROUP BY flight_id
        ), obs AS (
            -- arg_min / arg_max skip NULL values, so the first and final states travel as structs.
            SELECT flight_id,
                   count(*) AS observations,
                   min(observed_at) AS first_seen_at,
                   arg_min(struct_pack(status := status, sched_local := sched_local), snap_rn) AS fst,
                   arg_max(struct_pack({fin}), snap_rn) AS fin,
                   any_value(airline) AS airline, any_value(flight_no) AS flight_no,
                   any_value(direction) AS direction, any_value(airport) AS airport,
                   min(observed_at) FILTER (WHERE status = 'CANCELED') AS canceled_first_seen_at,
                   arg_min(struct_pack(sched_utc := sched_utc), snap_rn) FILTER (WHERE status = 'CANCELED') AS canceled_sched,
                   min(snap_rn) FILTER (WHERE status = 'CANCELED') AS canceled_rn,
                   max(snap_rn) FILTER (WHERE status <> 'CANCELED') AS last_not_canceled_rn
            FROM observations GROUP BY flight_id
        ), before_cancel AS (
            -- The last appearance before the cancellation showed: the announcement came after it.
            SELECT k.flight_id, max(r.fetched_at) AS cancel_announced_after
            FROM rows r JOIN keymap k USING (key_id) JOIN snapshots s USING (snapshot_id)
            JOIN obs o ON o.flight_id = k.flight_id
            WHERE r.status <> 'CANCELED' AND s.snap_rn < o.canceled_rn
            GROUP BY k.flight_id
        )
        SELECT o.flight_id, o.airline, o.flight_no, o.fin.airline_name AS airline_name, o.direction, o.airport,
               o.fin.airport_name AS airport_name, o.fin.city_en AS city_en, o.fin.city_he AS city_he,
               o.fin.country_en AS country_en, o.fin.country_he AS country_he,
               o.fst.sched_local AS sched_local_first, o.fin.sched_local AS sched_local_final,
               o.fin.sched_utc AS sched_utc_final, o.fin.sched_ambiguous AS sched_ambiguous,
               o.fin.sched_nonexistent AS sched_nonexistent,
               ch.retimes, ch.key_ids,
               o.first_seen_at, s.last_seen_at, s.snapshots_seen, o.observations,
               o.fst.status AS first_status, o.fin.status AS final_status, o.fin.status_he AS final_status_he,
               CASE WHEN o.fin.status = 'DEPARTED' THEN 'departed'
                    WHEN o.fin.status = 'LANDED' THEN 'landed'
                    WHEN o.fin.status = 'CANCELED' THEN 'canceled'
                    WHEN s.last_rn = {latest} THEN 'open'
                    WHEN nxt.fetched_at - s.last_seen_at > INTERVAL {GAP_HOURS} HOUR THEN 'gap'
                    WHEN o.fin.sched_utc > s.last_seen_at + INTERVAL {VANISH_HORIZON_HOURS} HOUR THEN 'vanished'
                    ELSE 'dropped' END AS outcome,
               o.fin.est_local AS est_local_final, o.fin.est_utc AS est_utc_final,
               epoch(o.fin.est_utc - o.fin.sched_utc) / 60 AS est_minus_sched_min,
               o.fin.terminal AS terminal_final, o.fin.counters AS counters_final, o.fin.zone AS zone_final,
               o.canceled_first_seen_at, b.cancel_announced_after,
               epoch(o.canceled_sched.sched_utc - o.canceled_first_seen_at) / 60 AS cancel_lead_min,
               epoch(o.canceled_sched.sched_utc - b.cancel_announced_after) / 60 AS cancel_lead_max_min,
               epoch(o.canceled_first_seen_at - b.cancel_announced_after) / 60 AS cancel_bracket_min,
               o.fst.status = 'CANCELED' AS canceled_at_first_sight,
               -- The lead time is only a bound when the flight was already cancelled when first seen or
               -- the bracket spans a collection hole (then the scheduled time may even sit inside it).
               CASE WHEN o.canceled_first_seen_at IS NULL THEN NULL
                    ELSE b.cancel_announced_after IS NULL
                         OR o.canceled_first_seen_at - b.cancel_announced_after > INTERVAL {GAP_HOURS} HOUR END AS cancel_lead_censored,
               o.canceled_rn IS NOT NULL AND o.last_not_canceled_rn > o.canceled_rn AS uncanceled,
               c.codeshare_group_id, c.codeshare_size, c.codeshare_basis,
               c.operating_airline, c.operating_flight_no, c.operating_is_guess
        FROM obs o JOIN seen s USING (flight_id) JOIN chain ch USING (flight_id) JOIN codeshares c USING (flight_id)
        LEFT JOIN before_cancel b USING (flight_id)
        LEFT JOIN snapshots nxt ON nxt.snap_rn = s.last_rn + 1
        ORDER BY o.fin.sched_utc, o.airline, o.flight_no
    """)


def build_all(con, raw_glob: str, receipts_glob: str | None = None) -> dict[str, int]:
    """Run every step. Returns row counts per output table."""
    load_raw(con, raw_glob)
    load_receipts(con, receipts_glob)
    convert_times_and_dedupe(con)
    link_retimes(con)
    build_observations(con)
    build_flights(con)
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("snapshots", "observations", "flights", "receipts")}
