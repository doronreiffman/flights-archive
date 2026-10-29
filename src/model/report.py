"""Data-quality report from the built model: python -m model.report --model data/model"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb


def _rows(con, sql: str) -> list[tuple]:
    return con.execute(sql).fetchall()


def _table(headers: list[str], rows: list[tuple]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def report(model_dir: Path) -> str:
    con = duckdb.connect()
    for t in ("snapshots", "snapshot_runs", "observations", "flights"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{model_dir / t}.parquet'")
    s = ["Source: Israel Airports Authority flight board, published on data.gov.il (dataset flydata, "
         "resource e83f763b-b7d7-479e-b172-ae981ddc6de5). Built by flights-archive from archived snapshots.\n"]
    cov = _rows(con, """SELECT count(*), min(fetched_at), max(fetched_at), min(rows), max(rows), sum(identical_repeats),
                        sum(duplicate_rows), sum(key_conflicts), sum(unparsed_sched), sum(missing_est) FROM snapshots""")[0]
    s.append("## Coverage\n")
    s.append(_table(["snapshots", "first", "last", "rows min", "rows max", "stored twice", "duplicate rows", "key conflicts", "unparsed sched", "missing est"], [cov]))
    dropped = _rows(con, "SELECT count(*) FILTER (WHERE incomplete), count(*) FILTER (WHERE repeat) FROM snapshot_runs")[0]
    s.append(f"\nSnapshots dropped: {dropped[0]} incomplete (fewer rows than the reply's total), {dropped[1]} identical to the previous one.")
    gaps = _rows(con, "SELECT fetched_at, round(gap_before_s / 3600.0, 1) FROM snapshots WHERE gap_before_s > 3600 ORDER BY 1")
    s.append("\nCollection gaps over an hour (snapshot, hours since the previous one):\n")
    s.append(_table(["snapshot", "gap h"], gaps) if gaps else "none")

    s.append("\n## Flights\n")
    s.append(_table(["direction", "outcome", "flights"], _rows(con, "SELECT direction, outcome, count(*) FROM flights GROUP BY ALL ORDER BY 1, 3 DESC")))
    s.append("\nOutcomes: departed / landed / canceled are final statuses; open is still on the latest snapshot; gap left the board "
             "during a collection hole (unknown fate); vanished left early with a non-final status and no retime (possible unflagged "
             "cancellation); dropped rolled off after its time without a final status.")

    s.append("\n## Observations\n")
    s.append(_table(["kind", "rows"], _rows(con, "SELECT change_kind, count(*) FROM observations GROUP BY 1 ORDER BY 2 DESC")))
    s.append("\nFields that change (one count per changed field, `change` rows only):\n")
    s.append(_table(["field", "changes"], _rows(con, "SELECT f, count(*) FROM (SELECT unnest(changed_fields) f FROM observations WHERE change_kind = 'change') GROUP BY 1 ORDER BY 2 DESC")))
    regress = _rows(con, """SELECT count(*) FROM (SELECT status, lag(status) OVER (PARTITION BY flight_id ORDER BY snap_rn) prev FROM observations)
                            WHERE prev IN ('DEPARTED', 'LANDED') AND status NOT IN ('DEPARTED', 'LANDED')""")[0][0]
    flags = _rows(con, "SELECT sum(sched_ambiguous::INT), sum(sched_nonexistent::INT), sum(est_ambiguous::INT), sum(est_nonexistent::INT) FROM observations")[0]
    s.append(f"\nStatus going back from DEPARTED/LANDED to something else: {regress} observations.")
    s.append(f"DST flags (sched ambiguous, sched nonexistent, est ambiguous, est nonexistent): {tuple(int(x or 0) for x in flags)}.")

    s.append("\n## Retimes (R4)\n")
    ret = _rows(con, "SELECT count(*) FILTER (WHERE retimes > 0), max(retimes) FROM flights")[0]
    s.append(f"Flights with a retime link: {ret[0]} (most links in one flight: {ret[1]}).")
    overlap = _rows(con, """SELECT count(*) FROM flights v JOIN flights n
                              ON n.airline = v.airline AND n.flight_no = v.flight_no AND n.direction = v.direction
                             AND n.airport = v.airport AND n.flight_id <> v.flight_id
                             AND abs(epoch(n.sched_utc_final - v.sched_utc_final)) <= 12 * 3600
                             AND n.first_seen_at <= v.last_seen_at AND n.last_seen_at >= v.first_seen_at
                            WHERE v.outcome = 'vanished'""")[0][0]
    s.append(f"Vanished flights that shared the board with a same-number flight within 12 h (retimes R4 cannot link if "
             f"the board overlaps old and new rows): {overlap}.")
    ex = _rows(con, """SELECT airline || ' ' || flight_no, direction, airport, sched_local_first, sched_local_final, final_status
                       FROM flights WHERE retimes > 0 ORDER BY sched_local_final LIMIT 10""")
    if ex:
        s.append("")
        s.append(_table(["flight", "dir", "airport", "first sched", "final sched", "final status"], ex))

    s.append("\n## Codeshares (R5, R6)\n")
    s.append(_table(["basis", "group size", "flights"], _rows(con, "SELECT codeshare_basis, codeshare_size, count(*) FROM flights GROUP BY ALL ORDER BY 1, 2")))
    guess = _rows(con, "SELECT count(*) FILTER (WHERE operating_is_guess), count(*) FROM flights")[0]
    s.append(f"\nOperating carrier is a guess (group of two or more) for {guess[0]} of {guess[1]} flights.")

    s.append("\n## Cancellations (R8)\n")
    c = _rows(con, """SELECT count(*), count(*) FILTER (WHERE canceled_at_first_sight), count(*) FILTER (WHERE uncanceled),
                      count(*) FILTER (WHERE NOT cancel_lead_censored), round(max(cancel_bracket_min) FILTER (WHERE NOT cancel_lead_censored))
                      FROM flights WHERE canceled_first_seen_at IS NOT NULL""")[0]
    s.append(f"Flights seen CANCELED: {c[0]}. Already cancelled when first seen: {c[1]}. Later un-cancelled: {c[2]}. "
             f"Lead time usable (not censored by first sight or a collection hole): {c[3]}"
             + (f", widest bracket {c[4]:.0f} min." if c[3] else "."))
    lead = _rows(con, """SELECT round(median(cancel_lead_min) / 60, 1), round(min(cancel_lead_min) / 60, 1), round(max(cancel_lead_max_min) / 60, 1)
                         FROM flights WHERE NOT cancel_lead_censored""")[0]
    if lead[0] is None:
        s.append("No usable cancellation lead time yet.")
    else:
        s.append(f"Usable lead times, hours before scheduled time: median {lead[0]}, min {lead[1]}, max {lead[2]}.")

    s.append("\n## Estimated minus scheduled time (meaning unconfirmed)\n")
    s.append(_table(["direction", "final status", "flights", "median min"],
                    _rows(con, """SELECT direction, final_status, count(*), round(median(est_minus_sched_min))
                                  FROM flights WHERE est_minus_sched_min IS NOT NULL GROUP BY ALL ORDER BY 1, 3 DESC""")))
    s.append("\nThe datastore's field notes call CHPTOL \"AnticipatedTimeLocal\"; whether it is gate or runway time is still unknown, so no delay statistics are published from it.")
    return "\n".join(s) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("data/model"))
    args = parser.parse_args(argv)
    if not (args.model / "flights.parquet").exists():
        print(f"no model under {args.model}; run model.build first", file=sys.stderr)
        return 2
    print(report(args.model), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
