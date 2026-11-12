# Flight lookup: the figures and their queries

The appendix of [flight-lookup.md](flight-lookup.md). Every figure in that document comes from a query here, run on 2026-11-12 on the model built that day from lists up to 2026-11-12 10:16:45Z (DuckDB 1.5.6). Each figure shows its query and its result. Model times are UTC. A later model gives later figures.

To reproduce: build the model (`docs/data-model.md`, "How to run"), then run A0 and A0b once in DuckDB from the repository's root, then any figure's query. This file is documentation. It is not the frozen rule: that will be tested code in a tagged commit (flight-lookup.md, "The record"), and this file is what that code is checked against.

Data: Israel Airports Authority, published on data.gov.il (dataset `flydata`).

## A0. Setup: rules C1 to C8 in SQL

```sql
SET TimeZone = 'UTC';
CREATE VIEW flights AS SELECT * FROM 'data/model/flights.parquet';
CREATE VIEW observations AS SELECT * FROM 'data/model/observations.parquet';
CREATE VIEW snapshots AS SELECT * FROM 'data/model/snapshots.parquet';

-- n0: one row per flight number and day (a `flights` row) with its slot (direction, airport, scheduled time)
CREATE TEMP TABLE n0 AS
SELECT f.*, direction || ' ' || airport || ' ' || strftime(sched_utc_final, '%Y-%m-%d %H:%M') AS slot,
       coalesce(counters_final, '') AS desks, outcome IN ('departed', 'landed') AS operated
FROM flights f;

-- tie: the pairs of numbers rule C1 ties directly, read at each number's last listing. Never across two
-- terminals or two different desk ranges. Then: the same expected time and desks (the model's R5 key); or, when
-- at least one of the two did not depart or land, the same airline or the same desks.
CREATE TEMP TABLE tie AS
SELECT a.flight_id AS a, b.flight_id AS b
FROM n0 a JOIN n0 b ON a.slot = b.slot
WHERE a.flight_id = b.flight_id OR (
      a.terminal_final IS NOT DISTINCT FROM b.terminal_final
  AND NOT (a.desks <> '' AND b.desks <> '' AND a.desks <> b.desks)
  AND ((a.est_utc_final IS NOT DISTINCT FROM b.est_utc_final AND a.desks = b.desks)
       OR (NOT (a.operated AND b.operated) AND (a.airline = b.airline OR (a.desks <> '' AND a.desks = b.desks)))));

-- num: each number with its flight (rule C1). Ties chain: every number takes the smallest id among those tied to
-- it, three rounds. Figure A12 checks that a fourth round changes nothing, and that no chain joins two numbers
-- that both departed or landed without the same expected time, terminal and desks (rule C1's last clause, whose
-- fallback is therefore not written out here; the code must implement it).
CREATE TEMP TABLE num AS
WITH l1 AS (SELECT a AS flight_id, min(b) AS lab FROM tie GROUP BY 1),
     l2 AS (SELECT t.a AS flight_id, min(l.lab) AS lab FROM tie t JOIN l1 l ON l.flight_id = t.b GROUP BY 1),
     l3 AS (SELECT t.a AS flight_id, min(l.lab) AS lab FROM tie t JOIN l2 l ON l.flight_id = t.b GROUP BY 1)
SELECT n.*, l3.lab AS tie_label, n.slot || ' /' || dense_rank() OVER (PARTITION BY n.slot ORDER BY l3.lab) AS flight_key
FROM n0 n JOIN l3 USING (flight_id);

-- fl: one row per flight (rules C1 to C4). Closed: scheduled at least 48 hours before the last sighting.
CREATE TEMP TABLE fl AS
SELECT flight_key, any_value(slot) AS slot, any_value(direction) AS direction, any_value(sched_utc_final) AS sched_utc,
       CAST(any_value(sched_local_final) AS DATE) AS il_day,
       CAST(date_trunc('week', any_value(sched_local_final) + INTERVAL 1 DAY) - INTERVAL 1 DAY AS DATE) AS il_week,
       count(*) AS numbers, min(first_seen_at) AS first_seen,
       any_value(sched_utc_final) <= (SELECT max(confirmed_until) FROM snapshots) - INTERVAL 48 HOUR AS closed,
       CASE WHEN bool_or(outcome IN ('departed', 'landed')) THEN 'operated'
            WHEN bool_or(outcome = 'canceled') THEN 'cancelled' ELSE 'unknown' END AS result,
       arg_min(airline, (TRY_CAST(regexp_extract(flight_no, '[0-9]+') AS INTEGER), airline)) AS lead_airline
FROM num GROUP BY flight_key;

-- st: what the list showed for a number from one change to the next. to_at ends the last stretch at the number's
-- last sighting (still on the list); to_ever keeps the last state after it left (used only by the signs).
CREATE TEMP TABLE st AS
SELECT o.flight_id, n.flight_key, n.airline, n.flight_no, n.direction, n.airport, n.first_seen_at, o.snap_rn,
       o.observed_at AS from_at,
       coalesce(lead(o.observed_at) OVER w, n.last_seen_at + INTERVAL 1 SECOND) AS to_at,
       coalesce(lead(o.observed_at) OVER w, TIMESTAMP '9999-12-31') AS to_ever,
       o.sched_utc, o.est_utc, o.status, o.terminal, coalesce(o.counters, '') AS desks
FROM observations o JOIN num n USING (flight_id)
WINDOW w AS (PARTITION BY o.flight_id ORDER BY o.snap_rn);

-- hole: stretches of more than an hour with no download (the model's GAP_HOURS)
CREATE TEMP TABLE hole AS
SELECT prev AS from_at, fetched_at AS to_at
FROM (SELECT fetched_at, gap_before_s, lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev FROM snapshots)
WHERE gap_before_s > 3600;

-- cp: for each number and each checkpoint h, the moment it was listed exactly h hours before the scheduled time
-- the list showed at that moment, and its status then (rule C6). The first such moment, never one inside a hole.
CREATE TEMP TABLE cp AS
SELECT flight_id, h, arg_min(t, snap_rn) AS t, arg_min(status, snap_rn) AS status
FROM (SELECT st.*, h, st.sched_utc - h * INTERVAL 1 HOUR AS t
      FROM st, (VALUES (70), (48), (24), (12), (6), (3)) AS checkpoints(h)) x
WHERE t >= from_at AND t < to_at AND NOT EXISTS (SELECT 1 FROM hole WHERE x.t > hole.from_at AND x.t < hole.to_at)
GROUP BY flight_id, h;

-- cell: the flights in each row of the table (rules C5 to C7): closed, known result, and at least one of its
-- numbers listed with a status other than cancelled at the checkpoint. k = 1 when the flight ended cancelled.
CREATE TEMP TABLE cell AS
SELECT r.h, r.flight_key, r.t, (f.result = 'cancelled')::INT AS k, f.lead_airline, f.il_day, f.il_week, f.direction, f.first_seen
FROM (SELECT n.flight_key, cp.h, min(cp.t) FILTER (WHERE cp.status <> 'CANCELED') AS t
      FROM cp JOIN num n USING (flight_id) GROUP BY 1, 2 HAVING bool_or(cp.status <> 'CANCELED')) r
JOIN fl f USING (flight_key) WHERE f.closed AND f.result <> 'unknown';

-- rng: the range (rule C8) for any set of (grp, k, lead_airline, il_day, il_week) rows: the rate, its standard error
-- with flights grouped by airline and week and by Israel day, the larger of the two, and two of them either side
-- on the log-odds scale. clears_floor is the floor of rule C8.
CREATE MACRO rng(src) AS TABLE
WITH x AS (SELECT * FROM query_table(src)),
     t AS (SELECT grp, sum(k) AS kk, count(*) AS nn, count(DISTINCT lead_airline) FILTER (WHERE k = 1) AS airlines,
                  count(DISTINCT il_day) FILTER (WHERE k = 1) AS days_ FROM x GROUP BY 1),
     g AS (SELECT 'airline-week' AS by_, grp, lead_airline || ' ' || il_week::VARCHAR AS c, sum(k) AS k, count(*) AS n FROM x GROUP BY 1, 2, 3
           UNION ALL SELECT 'day', grp, il_day::VARCHAR, sum(k), count(*) FROM x GROUP BY 1, 2, 3),
     se AS (SELECT g.by_, g.grp, sqrt(count(*) / (count(*) - 1.0) * sum(power(g.k - t.kk * 1.0 / t.nn * g.n, 2))) / any_value(t.nn) AS se
            FROM g JOIN t USING (grp) GROUP BY 1, 2),
     s AS (SELECT t.grp, t.kk, t.nn, t.airlines, t.days_, t.kk * 1.0 / t.nn AS r, max(se.se) AS se,
                  max(se.se) FILTER (WHERE se.by_ = 'airline-week') AS se_airline_week, max(se.se) FILTER (WHERE se.by_ = 'day') AS se_day
           FROM t JOIN se USING (grp) GROUP BY ALL)
SELECT grp, kk AS cancelled, nn AS flights, round(1 / r, 1) AS one_in,
       round(1 / (1 / (1 + exp(-(ln(r / (1 - r)) + 2 * se / (r * (1 - r)))))), 1) AS range_from_one_in,
       round(1 / (1 / (1 + exp(-(ln(r / (1 - r)) - 2 * se / (r * (1 - r)))))), 1) AS range_to_one_in,
       round(se_airline_week / sqrt(r * (1 - r) / nn), 2) AS airline_week_se_over_plain, round(se_day / sqrt(r * (1 - r) / nn), 2) AS day_se_over_plain,
       airlines AS airlines_with_a_cancellation, days_ AS days_with_a_cancellation,
       (kk >= 10 AND airlines >= 5 AND days_ >= 5) AS clears_floor
FROM s ORDER BY grp;
```

## A0b. The signs (S1 to S4, and the two dropped), the sign test's ratio

```sql
-- A sign is read for one number at its own checkpoint moment t, from what the list showed at t and nothing later.
-- nrow: the numbers in each row (rule C6): listed with a status other than cancelled at their checkpoint.
CREATE TEMP TABLE nrow AS
SELECT cp.flight_id, cp.h, cp.t, cp.t + cp.h * INTERVAL 1 HOUR AS sched_then, n.flight_key, n.airline, n.flight_no,
       n.direction, n.airport
FROM cp JOIN num n USING (flight_id) WHERE cp.status <> 'CANCELED';

-- A number "listed as cancelled as a whole" at t: it shows CANCELED, and no number tied to it at t shows anything
-- else. Tied at t is rule C1 read at t for a number showing cancelled: the same direction, airport and scheduled
-- time as the list showed them at t, not across two terminals or two different desk ranges, and the same expected
-- time and desks, or the same airline, or the same desks. Direct ties only: a chain needs the grouping at the end.
-- A number that has left the list keeps the last status it showed (to_ever), so a flight that ended as departed
-- is not read as cancelled afterwards.
CREATE MACRO not_whole(fid, dir, ap, sched, al, term, dsk, est, t) AS EXISTS (
  SELECT 1 FROM st y WHERE y.flight_id <> fid AND y.direction = dir AND y.airport = ap AND y.sched_utc = sched
    AND y.terminal IS NOT DISTINCT FROM term AND NOT (y.desks <> '' AND dsk <> '' AND y.desks <> dsk)
    AND ((y.est_utc IS NOT DISTINCT FROM est AND y.desks = dsk) OR y.airline = al OR (dsk <> '' AND y.desks = dsk))
    AND y.from_at <= t AND t < y.to_ever AND y.status <> 'CANCELED');

-- nsign: the numbers of each row that show each sign
CREATE TEMP TABLE nsign AS
-- S1 inbound: a number of the same airline from the same airport, scheduled (as shown at t) to land 30 minutes to
-- 12 hours before this departure, is on the list at t and listed as cancelled as a whole
SELECT 'S1 inbound' AS sign, r.h, r.flight_id FROM nrow r WHERE r.direction = 'D' AND EXISTS (
  SELECT 1 FROM st a WHERE a.direction = 'A' AND a.airline = r.airline AND a.airport = r.airport
    AND a.from_at <= r.t AND r.t < a.to_at AND a.status = 'CANCELED'
    AND a.sched_utc BETWEEN r.sched_then - INTERVAL 12 HOUR AND r.sched_then - INTERVAL 30 MINUTE
    AND NOT not_whole(a.flight_id, a.direction, a.airport, a.sched_utc, a.airline, a.terminal, a.desks, a.est_utc, r.t))
UNION ALL
-- S2 the time before: of the same flight number's other flights known at t, the one whose scheduled time (as
-- shown at t, or as last shown if it has left the list) is the latest before this one's is, or ended, listed as
-- cancelled as a whole
SELECT 'S2 same number, the time before', r.h, r.flight_id FROM nrow r JOIN LATERAL (
    SELECT a.* FROM st a WHERE a.airline = r.airline AND a.flight_no = r.flight_no AND a.direction = r.direction
      AND a.flight_id <> r.flight_id AND a.from_at <= r.t AND r.t < a.to_ever AND a.sched_utc < r.sched_then
    ORDER BY a.sched_utc DESC, a.flight_id LIMIT 1) a ON TRUE
WHERE a.status = 'CANCELED'
  AND NOT not_whole(a.flight_id, a.direction, a.airport, a.sched_utc, a.airline, a.terminal, a.desks, a.est_utc, r.t)
UNION ALL
-- S3 same airline: another number of the same airline, in another slot, scheduled (as shown at t) within 24 hours
-- either side, is on the list at t and listed as cancelled as a whole
SELECT 'S3 same airline, another flight', r.h, r.flight_id FROM nrow r WHERE EXISTS (
  SELECT 1 FROM st b WHERE b.airline = r.airline AND b.flight_id <> r.flight_id
    AND b.from_at <= r.t AND r.t < b.to_at AND b.status = 'CANCELED'
    AND b.sched_utc BETWEEN r.sched_then - INTERVAL 24 HOUR AND r.sched_then + INTERVAL 24 HOUR
    AND NOT (b.direction = r.direction AND b.airport = r.airport AND b.sched_utc = r.sched_then)
    AND NOT not_whole(b.flight_id, b.direction, b.airport, b.sched_utc, b.airline, b.terminal, b.desks, b.est_utc, r.t))
UNION ALL
-- S4 added late: the number was first listed under 48 hours before the scheduled time it then showed (numbers
-- first seen when the records began, or when they resumed after a hole, are never "late")
SELECT 'S4 first listed under 48 h ahead', r.h, r.flight_id FROM nrow r
JOIN observations o ON o.flight_id = r.flight_id AND o.change_kind = 'first'
WHERE o.sched_utc - o.observed_at < INTERVAL 48 HOUR
  AND o.observed_at NOT IN (SELECT min(fetched_at) FROM snapshots UNION ALL SELECT to_at FROM hole)
UNION ALL
-- two signs the 5 November look had already found empty, re-measured and dropped
SELECT 'X1 status DELAYED (dropped)', cp.h, cp.flight_id FROM cp WHERE cp.status = 'DELAYED'
UNION ALL
SELECT 'X2 no check-in desks listed (dropped)', r.h, r.flight_id FROM nrow r
JOIN st s ON s.flight_id = r.flight_id AND s.from_at <= r.t AND r.t < s.to_at WHERE r.direction = 'D' AND s.desks = '';

-- sign: the flights of each row that carry each sign. The flight is the unit the result is counted on, so this
-- step alone uses the grouping at the end (rule C1). A flight carries S1, S2, S3 or X1 when any of its numbers in
-- the row shows it, and S4 or X2 when every one of them does.
CREATE TEMP TABLE sign AS
SELECT s.sign, r.h, r.flight_key
FROM (SELECT DISTINCT sign FROM nsign) s JOIN nrow r ON TRUE
LEFT JOIN nsign g ON g.sign = s.sign AND g.h = r.h AND g.flight_id = r.flight_id
GROUP BY 1, 2, 3
HAVING CASE WHEN s.sign LIKE 'S4%' OR s.sign LIKE 'X2%' THEN bool_and(g.flight_id IS NOT NULL) ELSE bool_or(g.flight_id IS NOT NULL) END;

-- signcell: every flight of every row, once per sign, with whether the sign was showing
CREATE TEMP TABLE signcell AS
SELECT s.sign, c.h, c.flight_key, c.k, c.lead_airline, c.il_day, c.il_week, c.first_seen, (sg.flight_key IS NOT NULL) AS present
FROM (SELECT DISTINCT sign FROM sign) s CROSS JOIN cell c
LEFT JOIN sign sg ON sg.sign = s.sign AND sg.h = c.h AND sg.flight_key = c.flight_key
WHERE c.direction = 'D' OR NOT (s.sign LIKE 'S1%' OR s.sign LIKE 'X2%');

-- ratio: for each sign and checkpoint in a set of signcell rows: flights with and without the sign, and, only
-- when the with-sign count clears rule C8's floor, how many times the rate and its range. The range uses 2.5
-- standard errors of the ratio's logarithm, grouped as in rule C8 (the larger of the two groupings). The last
-- column compares that grouped standard error with the plain one, sqrt(1/k1 - 1/n1 + 1/k0 - 1/n0), where the
-- with-sign count is 3 or more.
CREATE MACRO ratio(src) AS TABLE
WITH x AS (SELECT * FROM query_table(src)),
     t AS (SELECT sign, h, coalesce(sum(k) FILTER (WHERE present), 0) AS k1, count(*) FILTER (WHERE present) AS n1,
                  coalesce(sum(k) FILTER (WHERE NOT present), 0) AS k0, count(*) FILTER (WHERE NOT present) AS n0,
                  count(DISTINCT lead_airline) FILTER (WHERE present AND k = 1) AS airlines,
                  count(DISTINCT il_day) FILTER (WHERE present AND k = 1) AS days_ FROM x GROUP BY 1, 2),
     g AS (SELECT 'airline-week' AS by_, sign, h, lead_airline || ' ' || il_week::VARCHAR AS c, coalesce(sum(k) FILTER (WHERE present), 0) AS k1,
                  count(*) FILTER (WHERE present) AS n1, coalesce(sum(k) FILTER (WHERE NOT present), 0) AS k0,
                  count(*) FILTER (WHERE NOT present) AS n0 FROM x GROUP BY 1, 2, 3, 4
           UNION ALL
           SELECT 'day', sign, h, il_day::VARCHAR, coalesce(sum(k) FILTER (WHERE present), 0), count(*) FILTER (WHERE present),
                  coalesce(sum(k) FILTER (WHERE NOT present), 0), count(*) FILTER (WHERE NOT present) FROM x GROUP BY 1, 2, 3, 4),
     se AS (SELECT g.sign, g.h, g.by_, sqrt(count(*) / (count(*) - 1.0) * sum(power(
                   (g.k1 - t.k1 * 1.0 / t.n1 * g.n1) / t.k1 - (g.k0 - t.k0 * 1.0 / t.n0 * g.n0) / t.k0, 2))) AS se_log
            FROM g JOIN t USING (sign, h) WHERE t.k1 > 0 AND t.k0 > 0 GROUP BY 1, 2, 3),
     sm AS (SELECT sign, h, max(se_log) AS se_log FROM se GROUP BY 1, 2),
     r AS (SELECT t.*, sm.se_log, (t.k1 >= 10 AND t.airlines >= 5 AND t.days_ >= 5) AS clears_floor,
                  sm.se_log / sqrt(1.0 / nullif(t.k1, 0) - 1.0 / nullif(t.n1, 0) + 1.0 / nullif(t.k0, 0) - 1.0 / t.n0) AS se_ratio,
                  (t.k1 * 1.0 / nullif(t.n1, 0)) / nullif(t.k0 * 1.0 / t.n0, 0) AS times FROM t LEFT JOIN sm USING (sign, h))
SELECT sign, h, k1 AS cancelled_with, n1 AS flights_with, k0 AS cancelled_without, n0 AS flights_without,
       airlines AS airlines_with_a_cancellation, days_ AS days_with_a_cancellation, clears_floor,
       CASE WHEN clears_floor THEN round(times, 1) END AS times,
       CASE WHEN clears_floor THEN round(times * exp(-2.5 * se_log), 1) END AS times_from,
       CASE WHEN clears_floor THEN round(times * exp(2.5 * se_log), 1) END AS times_to,
       coalesce(clears_floor AND times * exp(-2.5 * se_log) > 1, false) AS passes,
       CASE WHEN k1 >= 3 THEN round(se_ratio, 2) END AS grouped_se_over_plain
FROM r;
```

## A1. The total: closed flights by result (rules C1 to C4)

```sql
SELECT result, count(*) AS flights FROM fl WHERE closed GROUP BY 1 ORDER BY 2 DESC
```

Result:

```
result | flights
operated | 4577
unknown | 269
cancelled | 81
```

## A2. The total with its range (rule C8)

```sql
CREATE OR REPLACE TEMP TABLE a2 AS SELECT 'total' AS grp, (result = 'cancelled')::INT AS k, lead_airline, il_day, il_week
FROM fl WHERE closed AND result <> 'unknown';
SELECT * FROM rng('a2')
```

Result:

```
grp | cancelled | flights | one_in | range_from_one_in | range_to_one_in | airline_week_se_over_plain | day_se_over_plain | airlines_with_a_cancellation | days_with_a_cancellation | clears_floor
total | 81 | 4658 | 57.5 | 36.3 | 91.6 | 2.1 | 1.18 | 21 | 15 | True
```

## A3. The flights with no known result, by why

```sql
SELECT CASE WHEN gap THEN 'left the list during the hole in the record'
            WHEN left_before THEN 'left the list before the scheduled time, with no final status'
            ELSE 'left the list after the scheduled time, with no final status' END AS why, count(*) AS flights
FROM (SELECT f.flight_key, bool_or(n.outcome = 'gap') AS gap, bool_or(n.last_seen_at < n.sched_utc_final) AS left_before
      FROM fl f JOIN num n USING (flight_key) WHERE f.closed AND f.result = 'unknown' GROUP BY 1) GROUP BY 1 ORDER BY 2 DESC
```

Result:

```
why | flights
left the list during the hole in the record | 240
left the list before the scheduled time, with no final status | 27
left the list after the scheduled time, with no final status | 2
```

## A4. The same total if every flight that left the list with no final status had been a cancellation

```sql
WITH u AS (SELECT count(*) AS n FROM fl f WHERE f.closed AND f.result = 'unknown'
             AND NOT EXISTS (SELECT 1 FROM num n WHERE n.flight_key = f.flight_key AND n.outcome = 'gap'))
SELECT sum((result = 'cancelled')::INT) + any_value(u.n) AS cancelled, count(*) + any_value(u.n) AS flights,
       round((count(*) + any_value(u.n)) * 1.0 / (sum((result = 'cancelled')::INT) + any_value(u.n)), 1) AS one_in
FROM fl, u WHERE closed AND result <> 'unknown'
```

Result:

```
cancelled | flights | one_in
110 | 4687 | 42.6
```

## A5. The first and last scheduled times among counted flights, and the number of Israel days

```sql
SELECT min(sched_utc) AS first_utc, max(sched_utc) AS last_utc, count(DISTINCT il_day) AS israel_days
FROM fl WHERE closed AND result <> 'unknown'
```

Result:

```
first_utc | last_utc | israel_days
2026-10-26 16:40:00 | 2026-11-10 10:10:00 | 16
```

## A6. The 'from here' table (rules C5 to C8); grp is the checkpoint in hours

```sql
CREATE OR REPLACE TEMP TABLE a6 AS SELECT h AS grp, k, lead_airline, il_day, il_week FROM cell;
SELECT * FROM rng('a6') ORDER BY grp DESC
```

Result:

```
grp | cancelled | flights | one_in | range_from_one_in | range_to_one_in | airline_week_se_over_plain | day_se_over_plain | airlines_with_a_cancellation | days_with_a_cancellation | clears_floor
70 | 48 | 3028 | 63.1 | 33.2 | 120.6 | 2.25 | 0.8 | 14 | 11 | True
48 | 47 | 3316 | 70.6 | 38.1 | 131.4 | 2.14 | 0.91 | 14 | 10 | True
24 | 35 | 3449 | 98.5 | 49.3 | 197.9 | 2.07 | 0.82 | 12 | 10 | True
12 | 25 | 3625 | 145.0 | 71.4 | 295.6 | 1.78 | 0.65 | 11 | 10 | True
6 | 19 | 3704 | 194.9 | 96.6 | 394.4 | 1.54 | 0.76 | 11 | 10 | True
3 | 16 | 3754 | 234.6 | 120.0 | 459.7 | 1.35 | 0.81 | 11 | 10 | True
```

## A7. The same table by direction (not shown on the site in version 1)

```sql
SELECT h, direction, sum(k) AS cancelled, count(*) AS flights, round(count(*) * 1.0 / sum(k), 0) AS one_in
FROM cell GROUP BY 1, 2 ORDER BY 1 DESC, 2
```

Result:

```
h | direction | cancelled | flights | one_in
70 | A | 21 | 1526 | 73.0
70 | D | 27 | 1502 | 56.0
48 | A | 19 | 1655 | 87.0
48 | D | 28 | 1661 | 59.0
24 | A | 13 | 1729 | 133.0
24 | D | 22 | 1720 | 78.0
12 | A | 10 | 1802 | 180.0
12 | D | 15 | 1823 | 122.0
6 | A | 9 | 1854 | 206.0
6 | D | 10 | 1850 | 185.0
3 | A | 7 | 1883 | 269.0
3 | D | 9 | 1871 | 208.0
```

## A8. How much one airline moves the 24-hour row: the row with each airline left out in turn, lowest and highest (the airline is rule C8's, a guess, so it is not named)

```sql
WITH a AS (SELECT DISTINCT lead_airline FROM cell WHERE h = 24),
     r AS (SELECT a.lead_airline, sum(c.k) AS cancelled, count(*) AS flights, count(*) * 1.0 / sum(c.k) AS one_in
           FROM a JOIN cell c ON c.h = 24 AND c.lead_airline <> a.lead_airline GROUP BY 1)
SELECT round(min(one_in), 1) AS lowest_one_in, round(max(one_in), 1) AS highest_one_in,
       (SELECT max(kk) FROM (SELECT sum(k) AS kk FROM cell WHERE h = 24 GROUP BY lead_airline)) AS most_cancelled_in_one_airline_group,
       (SELECT sum(k) FROM cell WHERE h = 24) AS cancelled_in_the_row FROM r
```

Result:

```
lowest_one_in | highest_one_in | most_cancelled_in_one_airline_group | cancelled_in_the_row
77.5 | 123.8 | 8 | 35
```

## A9. Rule C1 measured the other ways, closed flights with a known result

```sql
SELECT 'per flight number (flights rows)' AS unit, sum((outcome = 'canceled')::INT) AS cancelled,
       sum((outcome IN ('departed', 'landed', 'canceled'))::INT) AS known FROM num WHERE sched_utc_final <= (SELECT max(confirmed_until) FROM snapshots) - INTERVAL 48 HOUR
UNION ALL
SELECT 'per codeshare group (R5; the site today, before its split)', count(DISTINCT codeshare_group_id) FILTER (WHERE outcome = 'canceled'),
       count(DISTINCT codeshare_group_id) FILTER (WHERE outcome IN ('departed', 'landed', 'canceled')) FROM num WHERE sched_utc_final <= (SELECT max(confirmed_until) FROM snapshots) - INTERVAL 48 HOUR
UNION ALL
SELECT 'same direction, airport and scheduled time only', sum((r = 'cancelled')::INT), sum((r <> 'unknown')::INT)
FROM (SELECT slot, CASE WHEN bool_or(outcome IN ('departed', 'landed')) THEN 'operated'
                        WHEN bool_or(outcome = 'canceled') THEN 'cancelled' ELSE 'unknown' END AS r
      FROM num WHERE sched_utc_final <= (SELECT max(confirmed_until) FROM snapshots) - INTERVAL 48 HOUR GROUP BY 1)
UNION ALL
SELECT 'this design (C1 to C4)', sum((result = 'cancelled')::INT), count(*) FROM fl WHERE closed AND result <> 'unknown'
```

Result:

```
unit | cancelled | known
per flight number (flights rows) | 109 | 7244
per codeshare group (R5; the site today, before its split) | 95 | 4671
same direction, airport and scheduled time only | 76 | 4614
this design (C1 to C4) | 81 | 4658
```

## A10. What rule C1 does: closed slots it splits into two or more flights; and, among numbers that departed or landed, where it differs from the model's codeshare rule (R5)

```sql
SELECT (SELECT count(*) FROM (SELECT slot FROM fl WHERE closed GROUP BY 1 HAVING count(*) > 1)) AS slots_split,
(SELECT count(*) FROM fl WHERE closed AND result = 'operated') AS operated_flights,
(SELECT count(*) FROM (SELECT f.flight_key FROM fl f JOIN num n USING (flight_key)
                       WHERE f.closed AND n.operated GROUP BY 1 HAVING count(DISTINCT n.codeshare_group_id) > 1)) AS flights_holding_two_r5_groups,
(SELECT count(*) FROM (SELECT n.codeshare_group_id FROM fl f JOIN num n USING (flight_key)
                       WHERE f.closed AND n.operated GROUP BY 1 HAVING count(DISTINCT n.flight_key) > 1)) AS r5_groups_split
```

Result:

```
slots_split | operated_flights | flights_holding_two_r5_groups | r5_groups_split
48 | 4577 | 0 | 0
```

## A10b. Why the expected time separates flights: pairs of numbers that both departed or landed in one slot with the same terminal and desks, by how far apart their last expected times are (numbers of closed flights)

```sql
SELECT CASE WHEN d = 0 THEN 'a. the same minute' WHEN d <= 10 THEN 'b. 1 to 10 minutes apart'
            WHEN d <= 60 THEN 'c. 11 to 60 minutes apart' ELSE 'd. over an hour apart' END AS expected_times, count(*) AS pairs
FROM (SELECT abs(epoch(a.est_utc_final - b.est_utc_final)) / 60 AS d
      FROM n0 a JOIN n0 b ON a.slot = b.slot AND a.flight_id < b.flight_id AND a.operated AND b.operated
           AND a.terminal_final IS NOT DISTINCT FROM b.terminal_final AND a.desks = b.desks
      WHERE a.sched_utc_final <= (SELECT max(confirmed_until) FROM snapshots) - INTERVAL 48 HOUR) GROUP BY 1 ORDER BY 1
```

Result:

```
expected_times | pairs
a. the same minute | 4292
b. 1 to 10 minutes apart | 7
c. 11 to 60 minutes apart | 7
d. over an hour apart | 9
```

## A11. Closed slots that hold a number listed as cancelled and more than one number: how rule C1 groups them (the flight is the part after the slash), with each number's end, desks and last expected time

```sql
SELECT n.flight_key, n.airline || ' ' || n.flight_no AS number, n.outcome, n.terminal_final AS terminal, n.desks,
       strftime(n.est_utc_final, '%H:%M') AS expected_utc
FROM num n JOIN fl f USING (flight_key)
WHERE f.closed AND n.slot IN (SELECT slot FROM num WHERE outcome = 'canceled')
  AND n.slot IN (SELECT slot FROM fl WHERE closed GROUP BY 1 HAVING count(*) > 1) ORDER BY 1, 2
```

Result:

```
flight_key | number | outcome | terminal | desks | expected_utc
D JFK 2026-10-28 22:05 /1 | IZ 991 | canceled | 3 | 34-41 | 22:05
D JFK 2026-10-28 22:05 /2 | AM 7895 | departed | 3 | 78-99 | 22:48
D JFK 2026-10-28 22:05 /2 | DL 7426 | departed | 3 | 78-99 | 22:48
D JFK 2026-10-28 22:05 /2 | LY 003 | departed | 3 | 78-99 | 22:48
D JFK 2026-10-29 11:30 /1 | ASY 991 | canceled | 3 |  | 11:30
D JFK 2026-10-29 11:30 /2 | IZ 991 | departed | 3 | 66-73 | 09:52
D JFK 2026-11-07 22:05 /1 | AM 7895 | departed | 3 | 78-99 | 23:00
D JFK 2026-11-07 22:05 /1 | DL 7426 | departed | 3 | 78-99 | 23:00
D JFK 2026-11-07 22:05 /1 | LY 003 | departed | 3 | 78-99 | 23:00
D JFK 2026-11-07 22:05 /2 | IZ 991 | canceled | 3 |  | 19:00
D LCA 2026-11-04 18:00 /1 | LY 5133 | departed | 1 | 316-327 | 18:14
D LCA 2026-11-04 18:00 /2 | 6H 993 | canceled | 3 |  | 18:00
D LCA 2026-11-06 23:15 /1 | LH 685 | vanished | 3 | 34-45 | 23:15
D LCA 2026-11-06 23:15 /2 | LH 0683A | canceled | 3 | 28-33 | 23:15
D ZIA 2026-11-04 06:30 /1 | UN WZ932 | canceled | 3 | 212-215 | 06:30
D ZIA 2026-11-04 06:30 /2 | WZ 932 | departed | 3 | 211-214 | 06:56
```

## A11b. Five of the slots rule C1 splits where every number departed or landed (examples: two desk ranges, two expected times)

```sql
SELECT n.flight_key, n.airline || ' ' || n.flight_no AS number, n.outcome, n.desks, strftime(n.est_utc_final, '%H:%M') AS expected_utc
FROM num n WHERE n.slot IN ('D KTW 2026-11-10 03:00', 'D KRK 2026-10-30 04:00', 'D AUH 2026-10-29 05:00', 'A ATH 2026-11-01 20:00', 'A FCO 2026-10-29 00:30')
ORDER BY 1, 2
```

Result:

```
flight_key | number | outcome | desks | expected_utc
A ATH 2026-11-01 20:00 /1 | 6H 570 | landed |  | 20:26
A ATH 2026-11-01 20:00 /2 | BZ 701 | landed |  | 18:47
A FCO 2026-10-29 00:30 /1 | AR 7856 | landed |  | 00:20
A FCO 2026-10-29 00:30 /1 | LY 384 | landed |  | 00:20
A FCO 2026-10-29 00:30 /1 | SK 3166 | landed |  | 00:20
A FCO 2026-10-29 00:30 /1 | TP 8897 | landed |  | 00:20
A FCO 2026-10-29 00:30 /2 | NO 9237 | landed |  | 02:05
D AUH 2026-10-29 05:00 /1 | EY 610 | departed | 12-21 | 06:24
D AUH 2026-10-29 05:00 /1 | LY 9613 | departed | 12-21 | 06:24
D AUH 2026-10-29 05:00 /2 | EY 596 | departed | 12-21 | 05:18
D AUH 2026-10-29 05:00 /2 | LY 9606 | departed | 12-21 | 05:18
D KRK 2026-10-30 04:00 /1 | LO 5251 | departed | 78-99 | 04:18
D KRK 2026-10-30 04:00 /1 | LY 5419 | departed | 78-99 | 04:18
D KRK 2026-10-30 04:00 /2 | LO 2112 | departed | 38-41 | 04:10
D KRK 2026-10-30 04:00 /2 | LY 9291 | departed | 38-41 | 04:10
D KTW 2026-11-10 03:00 /1 | ENT 229 | departed | 220-223 | 03:46
D KTW 2026-11-10 03:00 /2 | ENT 359 | departed | 223-226 | 03:31
```

## A12. Rule C1's chains: numbers a fourth round would move, and flights that hold two numbers that both departed or landed without the same expected time, terminal and desks (both must be 0)

```sql
SELECT (SELECT count(*) FROM (SELECT t.a, min(n.tie_label) AS m FROM tie t JOIN num n ON n.flight_id = t.b GROUP BY 1) x
 JOIN num n ON n.flight_id = x.a WHERE x.m <> n.tie_label) AS numbers_a_fourth_round_would_move,
(SELECT count(*) FROM (SELECT flight_key FROM num WHERE operated GROUP BY 1
                       HAVING count(DISTINCT est_utc_final) > 1 OR count(DISTINCT desks) > 1 OR count(DISTINCT terminal_final) > 1)) AS flights_joining_two_operated_numbers_apart
```

Result:

```
numbers_a_fourth_round_would_move | flights_joining_two_operated_numbers_apart
0 | 0
```

## A13. Rule C2: numbers listed as cancelled inside a flight that departed or landed

```sql
SELECT count(*) FILTER (WHERE f.closed) AS numbers, count(DISTINCT n.flight_key) FILTER (WHERE f.closed) AS flights,
       count(*) AS numbers_closed_or_not, count(DISTINCT n.flight_key) AS flights_closed_or_not
FROM num n JOIN fl f USING (flight_key) WHERE f.result = 'operated' AND n.outcome = 'canceled'
```

Result:

```
numbers | flights | numbers_closed_or_not | flights_closed_or_not
14 | 12 | 16 | 14
```

## A14. Rule C2: those flights, number by number

```sql
SELECT n.flight_key, string_agg(n.airline || ' ' || n.flight_no, ', ' ORDER BY n.airline, n.flight_no) FILTER (WHERE n.outcome = 'canceled') AS listed_as_cancelled,
       string_agg(n.airline || ' ' || n.flight_no, ', ' ORDER BY n.airline, n.flight_no) FILTER (WHERE n.outcome IN ('departed', 'landed')) AS departed_or_landed
FROM num n JOIN fl f USING (flight_key)
WHERE f.closed AND f.result = 'operated' AND f.flight_key IN (SELECT flight_key FROM num WHERE outcome = 'canceled') GROUP BY 1 ORDER BY 1
```

Result:

```
flight_key | listed_as_cancelled | departed_or_landed
A BUD 2026-11-05 21:40 /1 | IZ 292 | IZ 294
A VIE 2026-11-07 02:20 /1 | OS 1083 | OS 083
A VIE 2026-11-08 02:20 /1 | OS 1083 | OS 083
A VIE 2026-11-09 02:20 /1 | OS 1083 | OS 083
A VIE 2026-11-10 02:20 /1 | OS 1083 | OS 083
D ATH 2026-11-08 23:00 /1 | LH 0691A | LH 695
D ATH 2026-11-09 23:00 /1 | LH 0691A | LH 695
D EWR 2026-11-02 21:10 /1 | UA 091, UA 91D | UA 091D
D LCA 2026-11-04 08:30 /1 | U8 103 | BZ 112
D LCA 2026-11-07 23:15 /1 | LH 0683A | LH 685
D LCA 2026-11-08 23:15 /1 | LH 0683A, LH 683 | LH 685
D LCA 2026-11-09 23:15 /1 | LH 0683A | LH 685
```

## A15. Rule C2: cancelled flights that also hold a number with no known end (the count can be high as well as low)

```sql
SELECT count(*) AS cancelled_flights, sum(has_unknown::INT) AS with_a_number_of_no_known_end FROM (
SELECT f.flight_key, bool_or(n.outcome NOT IN ('canceled')) AS has_unknown
FROM fl f JOIN num n USING (flight_key) WHERE f.closed AND f.result = 'cancelled' GROUP BY 1)
```

Result:

```
cancelled_flights | with_a_number_of_no_known_end
81 | 1
```

## A16. Rule C3: numbers listed as cancelled at some point that ended otherwise; and numbers listed as cancelled on more than one day (numbers of closed flights)

```sql
SELECT (SELECT count(*) FROM num n JOIN fl f USING (flight_key) WHERE f.closed AND coalesce(n.uncanceled, false) AND n.outcome <> 'canceled') AS changed_back,
(SELECT count(*) FROM (SELECT n.airline, n.flight_no, n.direction FROM num n JOIN fl f USING (flight_key)
                       WHERE f.closed AND f.result = 'cancelled' AND n.outcome = 'canceled' GROUP BY 1, 2, 3 HAVING count(DISTINCT n.flight_key) > 1)) AS cancelled_on_more_than_one_day,
(SELECT max(c) FROM (SELECT count(DISTINCT n.flight_key) AS c FROM num n JOIN fl f USING (flight_key)
                     WHERE f.closed AND f.result = 'cancelled' AND n.outcome = 'canceled' GROUP BY n.airline, n.flight_no, n.direction)) AS most_days
```

Result:

```
changed_back | cancelled_on_more_than_one_day | most_days
7 | 10 | 4
```

## A17. The late line: cancelled flights by where the first cancelled listing falls against the scheduled time. The listing came between the last sighting still not cancelled and the first sighting as cancelled (the model's bracket, R8), for the number listed first (rule C9)

```sql
WITH c AS (SELECT f.flight_key, arg_min(n.cancel_lead_min, n.canceled_first_seen_at) AS lead_min,
                  arg_min(n.cancel_lead_max_min, n.canceled_first_seen_at) AS lead_max,
                  arg_min(n.cancel_lead_censored, n.canceled_first_seen_at) AS censored
           FROM fl f JOIN num n USING (flight_key) WHERE f.closed AND f.result = 'cancelled' AND n.outcome = 'canceled' GROUP BY 1)
SELECT CASE WHEN censored THEN 'c. cannot be placed: already cancelled when first seen, or the bracket spans the hole'
            WHEN lead_max < 0 THEN 'a. wholly after the scheduled time'
            WHEN lead_min < 0 THEN 'b. the bracket holds the scheduled time'
            ELSE 'd. before the scheduled time' END AS listing, count(*) AS cancelled_flights
FROM c GROUP BY 1 ORDER BY 1
```

Result:

```
listing | cancelled_flights
a. wholly after the scheduled time | 9
b. the bracket holds the scheduled time | 1
c. cannot be placed: already cancelled when first seen, or the bracket spans the hole | 19
d. before the scheduled time | 52
```

## A18. What the list can show, per flight number: when a number first appears (numbers first seen when records began or resumed left out), and how long it stays after its scheduled time, by how it ended

```sql
SELECT 'first listed, hours ahead' AS what, count(*) AS numbers, round(quantile_cont(epoch(o.sched_utc - o.observed_at) / 3600, 0.5), 1) AS median,
       round(min(epoch(o.sched_utc - o.observed_at) / 3600), 1) AS least, round(max(epoch(o.sched_utc - o.observed_at) / 3600), 1) AS most
FROM observations o WHERE o.change_kind = 'first' AND o.observed_at NOT IN (SELECT min(fetched_at) FROM snapshots UNION ALL SELECT to_at FROM hole)
UNION ALL
SELECT 'left the list, hours after: ' || outcome, count(*), round(quantile_cont(epoch(last_seen_at - sched_utc_final) / 3600, 0.5), 1),
       round(min(epoch(last_seen_at - sched_utc_final) / 3600), 1), round(max(epoch(last_seen_at - sched_utc_final) / 3600), 1)
FROM num WHERE outcome IN ('departed', 'landed', 'canceled') AND last_seen_at < (SELECT max(confirmed_until) FROM snapshots) GROUP BY outcome ORDER BY 1
```

Result:

```
what | numbers | median | least | most
first listed, hours ahead | 7179 | 71.9 | -15.7 | 72.0
left the list, hours after: canceled | 118 | 23.9 | -54.6 | 51.4
left the list, hours after: departed | 3754 | 24.3 | 0.8 | 42.0
left the list, hours after: landed | 3890 | 23.8 | -0.1 | 43.3
```

## A19. Numbers first listed on time (70 hours or more ahead, records running): how many were already listed as cancelled

```sql
SELECT count(*) AS numbers_first_listed_on_time, sum((o.status = 'CANCELED')::INT) AS already_listed_as_cancelled
FROM observations o WHERE o.change_kind = 'first' AND o.sched_utc - o.observed_at >= INTERVAL 70 HOUR
  AND o.observed_at NOT IN (SELECT min(fetched_at) FROM snapshots UNION ALL SELECT to_at FROM hole)
```

Result:

```
numbers_first_listed_on_time | already_listed_as_cancelled
7092 | 2
```

## A20. Numbers that were missing from some lists between their first and last sighting (the model treats them as listed throughout)

```sql
WITH m AS (SELECT f.flight_id, (SELECT count(*) FROM snapshots s WHERE s.fetched_at >= f.first_seen_at AND s.fetched_at <= f.last_seen_at) - f.snapshots_seen AS missed
           FROM flights f)
SELECT count(*) AS numbers, sum((missed > 0)::INT) AS missing_from_some_list, min(missed) FILTER (WHERE missed > 0) AS fewest_lists_missed,
       max(missed) AS most_lists_missed FROM m
```

Result:

```
numbers | missing_from_some_list | fewest_lists_missed | most_lists_missed
10023 | 7 | 6 | 106
```

## A21. A flight number's own record: scheduled flights with a known result per flight number and direction (numbers of closed flights)

```sql
WITH r AS (SELECT n.airline, n.flight_no, n.direction, count(*) AS flights_
           FROM num n JOIN fl f USING (flight_key) WHERE f.closed AND n.outcome IN ('departed', 'landed', 'canceled') GROUP BY 1, 2, 3)
SELECT count(*) AS flight_numbers, median(flights_) AS median_flights, max(flights_) AS most FROM r
```

Result:

```
flight_numbers | median_flights | most
1033 | 6.0 | 17
```

## A22. Flight numbers whose scheduled time changed while they were listed (why rule C6 reads the time shown at the moment), numbers of closed flights

```sql
SELECT count(*) AS numbers, sum((scheds > 1)::INT) AS scheduled_time_changed FROM (
SELECT n.flight_id, count(DISTINCT o.sched_utc) AS scheds FROM num n JOIN fl f USING (flight_key) JOIN observations o USING (flight_id)
WHERE f.closed GROUP BY 1)
```

Result:

```
numbers | scheduled_time_changed
7657 | 43
```

## A23. Cancelled flights per Israel day, whole days after the hole (2026-10-30 to 2026-11-09)

```sql
SELECT min(c) AS fewest, max(c) AS most, count(*) AS days_ FROM (
SELECT il_day, sum((result = 'cancelled')::INT) AS c FROM fl WHERE closed AND result <> 'unknown'
  AND il_day BETWEEN DATE '2026-10-30' AND DATE '2026-11-09' GROUP BY 1)
```

Result:

```
fewest | most | days_
1 | 10 | 11
```

## A24. Rule C10: closed flights in which one number showed cancelled while another of its numbers was still listed and yet to depart or land: how many, for how long (first such moment to last), and how they ended

```sql
WITH o AS (SELECT a.flight_key, min(greatest(a.from_at, b.from_at)) AS from_at, max(least(a.to_at, b.to_at)) AS to_at
           FROM st a JOIN st b ON b.flight_key = a.flight_key AND b.flight_id <> a.flight_id
                AND b.status NOT IN ('CANCELED', 'DEPARTED', 'LANDED') AND a.status = 'CANCELED'
                AND b.from_at < a.to_at AND a.from_at < b.to_at
           GROUP BY 1)
SELECT f.result, count(*) AS flights, round(min(epoch(o.to_at - o.from_at) / 3600), 1) AS shortest_hours,
       round(max(epoch(o.to_at - o.from_at) / 3600), 1) AS longest_hours
FROM o JOIN fl f USING (flight_key) WHERE f.closed GROUP BY 1 ORDER BY 2 DESC
```

Result:

```
result | flights | shortest_hours | longest_hours
operated | 12 | 11.5 | 72.0
cancelled | 1 | 13.0 | 13.0
```

## A25. The signs, each read at the checkpoint moment; a ratio is printed only when the with-sign count clears the floor

```sql
CREATE OR REPLACE TEMP TABLE a25 AS SELECT * FROM signcell WHERE h IN (48, 24, 12, 6);
SELECT * FROM ratio('a25') ORDER BY sign, h DESC
```

Result:

```
sign | h | cancelled_with | flights_with | cancelled_without | flights_without | airlines_with_a_cancellation | days_with_a_cancellation | clears_floor | times | times_from | times_to | passes | grouped_se_over_plain
S1 inbound | 48 | 1 | 1 | 27 | 1660 | 1 | 1 | False |  |  |  | False | 
S1 inbound | 24 | 2 | 5 | 20 | 1715 | 1 | 2 | False |  |  |  | False | 
S1 inbound | 12 | 2 | 7 | 13 | 1816 | 2 | 2 | False |  |  |  | False | 
S1 inbound | 6 | 1 | 8 | 9 | 1842 | 1 | 1 | False |  |  |  | False | 
S2 same number, the time before | 48 | 4 | 15 | 43 | 3301 | 3 | 3 | False |  |  |  | False | 1.28
S2 same number, the time before | 24 | 4 | 30 | 31 | 3419 | 2 | 3 | False |  |  |  | False | 1.38
S2 same number, the time before | 12 | 2 | 36 | 23 | 3589 | 2 | 2 | False |  |  |  | False | 
S2 same number, the time before | 6 | 1 | 38 | 18 | 3666 | 1 | 1 | False |  |  |  | False | 
S3 same airline, another flight | 48 | 8 | 170 | 39 | 3146 | 3 | 5 | False |  |  |  | False | 1.62
S3 same airline, another flight | 24 | 11 | 491 | 24 | 2958 | 4 | 7 | False |  |  |  | False | 1.6
S3 same airline, another flight | 12 | 10 | 987 | 15 | 2638 | 5 | 6 | True | 1.8 | 0.5 | 6.3 | False | 1.25
S3 same airline, another flight | 6 | 7 | 1151 | 12 | 2553 | 4 | 4 | False |  |  |  | False | 1.31
S4 first listed under 48 h ahead | 48 | 0 | 0 | 47 | 3316 | 0 | 0 | False |  |  |  | False | 
S4 first listed under 48 h ahead | 24 | 1 | 11 | 34 | 3438 | 1 | 1 | False |  |  |  | False | 
S4 first listed under 48 h ahead | 12 | 2 | 23 | 23 | 3602 | 2 | 2 | False |  |  |  | False | 
S4 first listed under 48 h ahead | 6 | 2 | 30 | 17 | 3674 | 2 | 2 | False |  |  |  | False | 
X1 status DELAYED (dropped) | 48 | 0 | 0 | 47 | 3316 | 0 | 0 | False |  |  |  | False | 
X1 status DELAYED (dropped) | 24 | 0 | 3 | 35 | 3446 | 0 | 0 | False |  |  |  | False | 
X1 status DELAYED (dropped) | 12 | 0 | 6 | 25 | 3619 | 0 | 0 | False |  |  |  | False | 
X1 status DELAYED (dropped) | 6 | 2 | 19 | 17 | 3685 | 2 | 2 | False |  |  |  | False | 
X2 no check-in desks listed (dropped) | 48 | 15 | 889 | 13 | 772 | 7 | 7 | True | 1.0 | 0.4 | 2.7 | False | 1.07
X2 no check-in desks listed (dropped) | 24 | 2 | 303 | 20 | 1417 | 2 | 2 | False |  |  |  | False | 
X2 no check-in desks listed (dropped) | 12 | 1 | 5 | 14 | 1818 | 1 | 1 | False |  |  |  | False | 
X2 no check-in desks listed (dropped) | 6 | 0 | 2 | 10 | 1848 | 0 | 0 | False |  |  |  | False | 
```

## A26. The inbound sign: the departures that carried it 24 and 6 hours ahead, and how they ended

```sql
SELECT c.h, c.flight_key, f.result FROM sign s JOIN cell c USING (h, flight_key) JOIN fl f USING (flight_key)
WHERE s.sign LIKE 'S1%' AND c.h IN (24, 6) ORDER BY 1 DESC, 2
```

Result:

```
h | flight_key | result
24 | D FCO 2026-11-07 03:15 /1 | operated
24 | D FRA 2026-11-08 05:05 /1 | cancelled
24 | D FRA 2026-11-09 05:20 /1 | cancelled
24 | D JFK 2026-11-09 22:05 /1 | operated
24 | D VIE 2026-11-07 03:55 /1 | operated
6 | D EWR 2026-11-01 21:30 /1 | operated
6 | D FCO 2026-11-07 03:15 /1 | operated
6 | D FRA 2026-11-06 22:55 /1 | operated
6 | D JFK 2026-11-09 22:05 /1 | operated
6 | D OTP 2026-11-01 06:50 /1 | operated
6 | D TBS 2026-10-30 03:20 /1 | operated
6 | D VIE 2026-11-07 03:55 /1 | operated
6 | D ZIA 2026-11-04 03:50 /1 | cancelled
```

## A27. Cancelled departures whose listing can be timed: was a matching inbound flight (S1's definition) listed as cancelled before the departure's own listing, in the same download, or not at all

```sql
WITH d AS (SELECT f.flight_key, min(n.cancel_announced_after) AS still_normal_at, min(n.canceled_first_seen_at) AS listed_at
           FROM fl f JOIN num n USING (flight_key)
           WHERE f.closed AND f.result = 'cancelled' AND f.direction = 'D' AND n.outcome = 'canceled'
             AND NOT coalesce(n.canceled_at_first_sight, false) GROUP BY 1),
     i AS (SELECT d.flight_key, d.still_normal_at, d.listed_at, min(a.from_at) AS inbound_listed_at
           FROM d JOIN num dn USING (flight_key)
                JOIN st a ON a.direction = 'A' AND a.airline = dn.airline AND a.airport = dn.airport AND a.status = 'CANCELED'
                     AND a.from_at <= d.listed_at
                     AND a.sched_utc BETWEEN dn.sched_utc_final - INTERVAL 12 HOUR AND dn.sched_utc_final - INTERVAL 30 MINUTE
           WHERE NOT not_whole(a.flight_id, a.direction, a.airport, a.sched_utc, a.airline, a.terminal, a.desks, a.est_utc, d.listed_at)
           GROUP BY 1, 2, 3)
SELECT CASE WHEN i.flight_key IS NULL THEN 'c. no matching inbound listed as cancelled'
            WHEN i.inbound_listed_at <= i.still_normal_at THEN 'a. inbound listed first'
            ELSE 'b. same download' END AS which_first, count(*) AS cancelled_departures
FROM d LEFT JOIN i USING (flight_key) GROUP BY 1 ORDER BY 1
```

Result:

```
which_first | cancelled_departures
a. inbound listed first | 4
b. same download | 4
c. no matching inbound listed as cancelled | 33
```

## A28. The pace toward the gate, on flights seen from their first listing (scheduled from 2026-11-01 12:30Z): cancelled flights a day in all, and in the 24-hour row

```sql
WITH f AS (SELECT * FROM fl WHERE closed AND result <> 'unknown' AND sched_utc >= TIMESTAMP '2026-11-01 12:30:00'),
     d AS (SELECT epoch(max(sched_utc) - min(sched_utc)) / 86400 AS days_ FROM f),
     r AS (SELECT sum(c.k) AS k24, count(*) AS n24 FROM cell c JOIN f USING (flight_key) WHERE c.h = 24)
SELECT (SELECT sum((result = 'cancelled')::INT) FROM f) AS cancelled, (SELECT count(*) FROM f) AS flights, round(d.days_, 1) AS days_,
       round((SELECT sum((result = 'cancelled')::INT) FROM f) / d.days_, 1) AS cancelled_a_day,
       r.k24 AS cancelled_in_the_24_hour_row, r.n24 AS flights_in_the_24_hour_row, round(r.k24 / d.days_, 1) AS row_cancelled_a_day
FROM d, r
```

Result:

```
cancelled | flights | days_ | cancelled_a_day | cancelled_in_the_24_hour_row | flights_in_the_24_hour_row | row_cancelled_a_day
58 | 3029 | 8.9 | 6.5 | 32 | 2985 | 3.6
```

## A29. The sign test as it will run ("Signs", "The gate"), here as a dry run on flights already seen: the counting start is set to 2026-11-05 22:00Z for the run only, and the result decides nothing

```sql
SET VARIABLE counting_start = TIMESTAMP '2026-11-05 22:00:00';
-- the counted flights of the 24-hour row, in the order of the scheduled time they showed at the checkpoint
CREATE OR REPLACE TEMP TABLE counted AS
SELECT c.flight_key, c.k, c.t + INTERVAL 24 HOUR AS sched_then,
       sum(c.k) OVER (ORDER BY c.t, c.flight_key) AS cancelled_so_far
FROM cell c WHERE c.h = 24 AND c.first_seen >= getvariable('counting_start');
-- the gate is reached at the first scheduled time by which the row holds 200 cancelled flights and 60 days have passed
SET VARIABLE gate_at = (SELECT min(sched_then) FROM counted
                        WHERE cancelled_so_far >= 200 AND sched_then >= getvariable('counting_start') + INTERVAL 60 DAY);
-- the test reads the counted flights scheduled up to that time and no later ones (all of them so far, while it is not reached)
CREATE OR REPLACE TEMP TABLE a29 AS
SELECT s.* FROM signcell s JOIN counted c USING (flight_key)
WHERE s.h = 24 AND s.sign LIKE 'S%' AND (getvariable('gate_at') IS NULL OR c.sched_then <= getvariable('gate_at'));
SELECT r.sign, r.cancelled_with, r.flights_with, r.cancelled_without, r.flights_without, r.clears_floor, r.times, r.times_from, r.times_to,
       (SELECT sum(k) FROM counted) AS row_cancelled_so_far,
       (SELECT round(epoch(max(sched_then) - getvariable('counting_start')) / 86400, 1) FROM counted) AS days_so_far,
       getvariable('gate_at') AS gate_reached_at, (getvariable('gate_at') IS NOT NULL AND r.passes) AS sign_passes
FROM ratio('a29') r ORDER BY r.sign
```

Result:

```
sign | cancelled_with | flights_with | cancelled_without | flights_without | clears_floor | times | times_from | times_to | row_cancelled_so_far | days_so_far | gate_reached_at | sign_passes
S1 inbound | 1 | 2 | 2 | 269 | False |  |  |  | 3 | 4.5 |  | False
S2 same number, the time before | 1 | 9 | 2 | 515 | False |  |  |  | 3 | 4.5 |  | False
S3 same airline, another flight | 1 | 73 | 2 | 451 | False |  |  |  | 3 | 4.5 |  | False
S4 first listed under 48 h ahead | 0 | 7 | 3 | 517 | False |  |  |  | 3 | 4.5 |  | False
```

## A30. The model these figures come from

```sql
SELECT min(fetched_at) AS first_list, max(confirmed_until) AS last_sighting, count(*) AS lists,
       (SELECT count(*) FROM hole) AS holes_over_an_hour, (SELECT min(from_at) FROM hole) AS hole_from,
       (SELECT min(to_at) FROM hole) AS hole_to, (SELECT round(epoch(min(to_at) - min(from_at)) / 3600, 1) FROM hole) AS hole_hours
FROM snapshots
```

Result:

```
first_list | last_sighting | lists | holes_over_an_hour | hole_from | hole_to | hole_hours
2026-10-27 18:04:46 | 2026-11-12 10:16:45 | 1322 | 1 | 2026-10-27 18:24:31 | 2026-10-29 12:29:03 | 42.1
```

## A31. How often the tests would pass for a real sign (a simulation)

Not a measurement of the future. It takes the 24-hour row's rate, its airline-and-week groups and the ratio of its grouped standard error to the plain one from A6, and the row's pace from A28, and assumes they stay as measured. A simulated row is built by drawing whole groups, with the sizes measured, until it holds the flights of a row with the given number of cancelled flights. Every group gets one multiplier on its cancellation rates (gamma, mean 1), which is what makes its flights come in runs; the multiplier's spread is chosen so that the simulated rate's grouped error matches the measured ratio. Each sign is real by construction. In the last one the sign also shows more often in a group whose multiplier is high. Two tests are applied to each row, each with its own grouped standard error (groups as drawn). The sign's test ("Signs"): at least 10 cancelled flights with the sign, and the logarithm of the ratio more than 2.5 of its grouped standard errors above zero, by the formula of the `ratio` query (A0b). The Brier rule is the pass mark the first draft of the gate had, in its best case: the forecast is given the true rates in advance, a flight's gain is (table's rate - result) squared minus (its own rate - result) squared, and the rule asks for a mean gain more than 2 of its grouped standard errors above zero. Each line ends with the same two tests on rows drawn with no multipliers and judged with plain standard errors. Not simulated: the floor's 5 airlines and 5 days, and the grouping by day.

Result:

```
the 24-hour row's rate is 0.0101; its grouped standard error is 2.07 times the plain one (A6); the row gains 3.6 cancelled flights a day (A28); it has 131 airline-and-week groups of 1 to 613 flights
group multipliers with gamma shape 4.0: the simulated rate's grouped error is 1.20 times the plain one (median of 200 rows)
group multipliers with gamma shape 2.0: the simulated rate's grouped error is 1.35 times the plain one (median of 200 rows)
group multipliers with gamma shape 1.0: the simulated rate's grouped error is 1.62 times the plain one (median of 200 rows)
group multipliers with gamma shape 0.7: the simulated rate's grouped error is 1.82 times the plain one (median of 200 rows)
group multipliers with gamma shape 0.5: the simulated rate's grouped error is 2.03 times the plain one (median of 200 rows)
group multipliers with gamma shape 0.4: the simulated rate's grouped error is 2.11 times the plain one (median of 200 rows)
group multipliers with gamma shape 0.3: the simulated rate's grouped error is 2.37 times the plain one (median of 200 rows)
group multipliers with gamma shape 0.25: the simulated rate's grouped error is 2.47 times the plain one (median of 200 rows)
group multipliers with gamma shape 0.2: the simulated rate's grouped error is 2.70 times the plain one (median of 200 rows)
shape 0.4 is the closest to the measured 2.07; it is used below. 1,000 rows for each line, seed 20261112
sign rare and strong: on 1 flight in 100, at 10 times the rate of the rest
75 cancelled flights in the row (about 21 days, 7,614 flights in 197 groups): reaches 10 cancelled flights with the sign in 23% of rows; the sign's test passes in 23%; the Brier rule (true rates known) passes in 8%; the log ratio's grouped error is 0.90 times its plain one. With no runs in the draws and plain errors: 16% and 14%
200 cancelled flights in the row (about 56 days, 19,790 flights in 756 groups): reaches 10 cancelled flights with the sign in 97% of rows; the sign's test passes in 97%; the Brier rule (true rates known) passes in 30%; the log ratio's grouped error is 0.97 times its plain one. With no runs in the draws and plain errors: 99% and 48%
400 cancelled flights in the row (about 111 days, 39,430 flights in 1604 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 69%; the log ratio's grouped error is 0.99 times its plain one. With no runs in the draws and plain errors: 100% and 85%
sign rare and weaker: on 1 flight in 100, at 5 times the rate
75 cancelled flights in the row (about 21 days, 7,644 flights in 342 groups): reaches 10 cancelled flights with the sign in 1% of rows; the sign's test passes in 1%; the Brier rule (true rates known) passes in 3%; the log ratio's grouped error is 0.96 times its plain one. With no runs in the draws and plain errors: 0% and 3%
200 cancelled flights in the row (about 56 days, 19,724 flights in 729 groups): reaches 10 cancelled flights with the sign in 49% of rows; the sign's test passes in 49%; the Brier rule (true rates known) passes in 12%; the log ratio's grouped error is 0.97 times its plain one. With no runs in the draws and plain errors: 52% and 15%
400 cancelled flights in the row (about 111 days, 39,457 flights in 1446 groups): reaches 10 cancelled flights with the sign in 99% of rows; the sign's test passes in 99%; the Brier rule (true rates known) passes in 30%; the log ratio's grouped error is 0.98 times its plain one. With no runs in the draws and plain errors: 99% and 41%
sign common: on 14 flights in 100, at 3 times the rate (S3's shape at 24 hours, A25)
75 cancelled flights in the row (about 21 days, 7,402 flights in 231 groups): reaches 10 cancelled flights with the sign in 98% of rows; the sign's test passes in 94%; the Brier rule (true rates known) passes in 16%; the log ratio's grouped error is 0.92 times its plain one. With no runs in the draws and plain errors: 94% and 31%
200 cancelled flights in the row (about 56 days, 19,709 flights in 657 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 46%; the log ratio's grouped error is 0.97 times its plain one. With no runs in the draws and plain errors: 100% and 79%
400 cancelled flights in the row (about 111 days, 39,434 flights in 1563 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 89%; the log ratio's grouped error is 0.98 times its plain one. With no runs in the draws and plain errors: 100% and 98%
sign common and weaker: on 14 flights in 100, at 2 times the rate
75 cancelled flights in the row (about 21 days, 7,447 flights in 212 groups): reaches 10 cancelled flights with the sign in 94% of rows; the sign's test passes in 55%; the Brier rule (true rates known) passes in 7%; the log ratio's grouped error is 0.93 times its plain one. With no runs in the draws and plain errors: 53% and 12%
200 cancelled flights in the row (about 56 days, 19,763 flights in 823 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 92%; the Brier rule (true rates known) passes in 26%; the log ratio's grouped error is 0.97 times its plain one. With no runs in the draws and plain errors: 93% and 35%
400 cancelled flights in the row (about 111 days, 39,899 flights in 1377 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 56%; the log ratio's grouped error is 0.98 times its plain one. With no runs in the draws and plain errors: 100% and 71%
sign common, weaker and tied to its group: as the last, but showing more often in a group whose rate is high
75 cancelled flights in the row (about 21 days, 7,402 flights in 271 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 86%; the log ratio's grouped error is 1.40 times its plain one. With no runs in the draws and plain errors: 54% and 11%
200 cancelled flights in the row (about 56 days, 19,784 flights in 733 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 99%; the log ratio's grouped error is 1.51 times its plain one. With no runs in the draws and plain errors: 92% and 34%
400 cancelled flights in the row (about 111 days, 39,538 flights in 1419 groups): reaches 10 cancelled flights with the sign in 100% of rows; the sign's test passes in 100%; the Brier rule (true rates known) passes in 100%; the log ratio's grouped error is 1.64 times its plain one. With no runs in the draws and plain errors: 100% and 66%
```

## A32. What a later check of a published with-sign rate can catch (arithmetic)

A rate resting on k cancelled flights has a range of about exp(2 x factor / sqrt(k)) times either side, factor being the grouped-to-plain ratio of A6 (1 for the plain figure).

Result:

```
resting on 10 cancelled flights, a rate's range runs about 3.7 times either side (grouped), 1.9 times (plain)
resting on 18 cancelled flights, a rate's range runs about 2.7 times either side (grouped), 1.6 times (plain)
resting on 36 cancelled flights, a rate's range runs about 2.0 times either side (grouped), 1.4 times (plain)
```

## A33. A score needs the table beside it (arithmetic)

With r the 24-hour row's rate (A6): saying r for every flight has a Brier score of r(1 - r); saying "never" scores r.

Result:

```
saying the row's rate for every flight scores r(1-r) = 0.01004; saying 'never' scores r = 0.01015; 'never' is right for 99.0% of flights
```

## A34. A month of uploads if today's publish script ran more often (arithmetic)

Upload requests: files x price per request x uploads a day x 30. Invalidations: one path per upload. The price ($0.0055 per 1,000 PUT requests), "every build rewrites every file" and the 1,000 free invalidation paths a month are from `docs/publishing.md`, "Cost (monthly)"; 1,040 is the file count of the local build of 2026-11-04. None was re-read from AWS, and the price of an invalidation path beyond the free ones is not in the repository.

Result:

```
every 15 minutes: $16.47 in upload requests; 2,880 invalidations (1,880 beyond the 1,000 free)
hourly: $4.12 in upload requests; 720 invalidations (0 beyond the 1,000 free)
nightly: $0.17 in upload requests; 30 invalidations (0 beyond the 1,000 free)
```

## A35. The total and the table as a page would print them

Rule C8's rounding applied to A2 and A6: steps of 1 below 20, 5 from 20 to 99, 10 from 100 to 999, 100 above; the middle figure to the nearest step, halves up; the ends of the range outward.

Result:

```
total: 81 of 4,658: about 1 in 60 (between 1 in 35 and 1 in 95)
70 hours: 48 of 3,028: about 1 in 65 (between 1 in 30 and 1 in 130)
48 hours: 47 of 3,316: about 1 in 70 (between 1 in 35 and 1 in 140)
24 hours: 35 of 3,449: about 1 in 100 (between 1 in 45 and 1 in 200)
12 hours: 25 of 3,625: about 1 in 150 (between 1 in 70 and 1 in 300)
6 hours: 19 of 3,704: about 1 in 190 (between 1 in 95 and 1 in 400)
3 hours: 16 of 3,754: about 1 in 230 (between 1 in 120 and 1 in 460)
```

## A36. The front page's headline today, on this model

Computed in memory with the site's own functions, nothing written: `timeline.build.load`, `timeline.flights.make_rows`, `group_flights` and `headline_counts`, with the last sighting of the list as the build time.

Result:

```
106 of 5,367, 1 in 50.6
```
