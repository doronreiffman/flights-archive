"""The figures check: A0's and A0b's SQL (docs/flight-lookup-figures.md) and the counting and sign code
(src/timeline/counting.py, src/timeline/record.py) run on the same model, every difference reported
(docs/flight-lookup.md, "Tests and checks", Counting). Local only: the model is not in the repository. Run from the
repository root:

    PYTHONPATH=src .venv/bin/python scripts/figures_check.py --model data/model-2026-11-12

It prints each figure the code gives with "ok" when it matches the figures file's printed value (EXPECTED), or with
both values, A25's sign counts the same way; then each number rule C1 groups differently from A0's `num`, each flight
whose place in a row of the table (its moment, and whether it ended cancelled) differs from A0's `cell`, each flight
whose signs in a row differ from A0b's, and anything the code holds twice, with the count of each. Exit 1 on any
difference. EXPECTED holds the figures file's results, which come from the model saved as data/model-2026-11-12:
`data/model` is rebuilt after every sync, so its figures move, while its flights, cells and signs must still match A0
and A0b.
"""
import argparse
import re
import sys
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb

from timeline import counting, rates, record
from timeline.load import load

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "flight-lookup-figures.md"

# The figures file's printed results: cancelled, flights, and "1 in" with its range's two ends, to one decimal.
EXPECTED: dict[str, object] = {
    "total": (81, 4658, 57.5, 36.3, 91.6),  # A2
    "70 hours": (48, 3028, 63.1, 33.2, 120.6),  # A6, one per row
    "48 hours": (47, 3316, 70.6, 38.1, 131.4),
    "24 hours": (35, 3449, 98.5, 49.3, 197.9),
    "12 hours": (25, 3625, 145.0, 71.4, 295.6),
    "6 hours": (19, 3704, 194.9, 96.6, 394.4),
    "3 hours": (16, 3754, 234.6, 120.0, 459.7),
    # A25: each sign at 48, 24, 12 and 6 hours: cancelled and flights with it, cancelled and flights without it, the
    # airlines and the days among the cancelled flights with it, and whether those clear the floor (C8)
    "A25": {
        ("S1", 48): (1, 1, 27, 1660, 1, 1, False),
        ("S1", 24): (2, 5, 20, 1715, 1, 2, False),
        ("S1", 12): (2, 7, 13, 1816, 2, 2, False),
        ("S1", 6): (1, 8, 9, 1842, 1, 1, False),
        ("S2", 48): (4, 15, 43, 3301, 3, 3, False),
        ("S2", 24): (4, 30, 31, 3419, 2, 3, False),
        ("S2", 12): (2, 36, 23, 3589, 2, 2, False),
        ("S2", 6): (1, 38, 18, 3666, 1, 1, False),
        ("S3", 48): (8, 170, 39, 3146, 3, 5, False),
        ("S3", 24): (11, 491, 24, 2958, 4, 7, False),
        ("S3", 12): (10, 987, 15, 2638, 5, 6, True),
        ("S3", 6): (7, 1151, 12, 2553, 4, 4, False),
        ("S4", 48): (0, 0, 47, 3316, 0, 0, False),
        ("S4", 24): (1, 11, 34, 3438, 1, 1, False),
        ("S4", 12): (2, 23, 23, 3602, 2, 2, False),
        ("S4", 6): (2, 30, 17, 3674, 2, 2, False),
    },
}
A25_HOURS = (48, 24, 12, 6)


def sql_blocks(doc: str, *names: str) -> dict[str, str]:
    """Each name ("A0") -> the ```sql block in its section ("## A0. ..."), before the next section begins. KeyError
    for a name with no such section, or a section with no such block."""
    out = {}
    for name in names:
        heading = re.search(rf"^## {re.escape(name)}\. .*$", doc, re.M)
        if heading is None:
            raise KeyError(name)
        end = re.compile(r"^## ", re.M).search(doc, heading.end())
        stop = end.start() if end else len(doc)
        block = re.compile(r"^```sql\n(.*?)^```", re.M | re.S).search(doc, heading.end(), stop)
        if block is None:
            raise KeyError(name)
        out[name] = block.group(1)
    return out


def run_sql(model_dir: Path, names: tuple[str, ...]) -> duckdb.DuckDBPyConnection:
    """The figures file's blocks `names`, run in order on one connection, reading the model in `model_dir` where
    they read data/model. ValueError when A0 reads no 'data/model/ path: it would then read some other model."""
    blocks = sql_blocks(DOC.read_text(encoding="utf-8"), *names)
    if "A0" in blocks and "'data/model/" not in blocks["A0"]:
        raise ValueError(f"A0 in {DOC} reads no 'data/model/ path, so the check would not read {model_dir}")
    folder = str(model_dir).replace("'", "''")
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for sql in blocks.values():
        con.execute(sql.replace("'data/model/", f"'{folder}/"))
    return con


def _labels(con) -> dict[str, tuple[str, str]]:
    """flight_id -> its airline and number with the start of its id, and its slot, from the model's flights."""
    return {fid: (label, slot) for fid, label, slot in con.execute(
        """SELECT flight_id, airline || ' ' || flight_no || ' (' || left(flight_id, 8) || ')',
                  direction || ' ' || airport || ' ' || strftime(sched_utc_final, '%Y-%m-%d %H:%M')
           FROM flights""").fetchall()}


def _show_numbers(numbers, labels) -> str:
    return "nothing" if numbers is None else " + ".join(sorted(labels[fid][0] for fid in numbers))


def _a0_flights(con) -> dict[str, frozenset[str]]:
    """A0's flights: flight_key -> the flight_ids of its numbers."""
    rows = con.execute("SELECT flight_key, list(flight_id) FROM num GROUP BY 1").fetchall()
    return {key: frozenset(ids) for key, ids in rows}


def compare_flights(con, flights_: list[counting.Flight]) -> list[str]:
    """Each number whose flight (as the set of its numbers) differs between A0's `num` and `flights_`, once for each
    pair of differing flights: how A0 and the code group its slot's numbers. And each number the code puts in more
    than one flight."""
    a0 = {fid: ids for ids in _a0_flights(con).values() for fid in ids}
    code = {fid: frozenset(f.numbers) for f in flights_ for fid in f.numbers}
    labels = _labels(con)
    pairs = {(a0.get(fid), code.get(fid)) for fid in a0.keys() | code.keys() if a0.get(fid) != code.get(fid)}
    times = Counter(fid for f in flights_ for fid in f.numbers)
    return sorted([f"{labels[min(a or b)][1]}: A0 {_show_numbers(a, labels)}, the code {_show_numbers(b, labels)}"
                   for a, b in pairs]
                  + [f"{labels[fid][1]}: the code puts {labels[fid][0]} in {n} flights"
                     for fid, n in times.items() if n > 1])


def _show_cell(cell) -> str:
    if cell is None:
        return "not in the row"
    t, k = cell
    return f"in the row from {t:%Y-%m-%d %H:%M:%S}, " + ("cancelled" if k else "not cancelled")


def compare_cells(con, cells_: list[counting.Cell]) -> list[str]:
    """Each row and flight (as the set of its numbers) that is in the row in A0's `cell` or in `cells_` but not both,
    or with another moment t or result k. And each row and flight the code has in the row more than once."""
    flight = _a0_flights(con)
    a0 = {(h, flight[key]): (t, k) for h, key, t, k in con.execute("SELECT h, flight_key, t, k FROM cell").fetchall()}
    code = {(c.h, frozenset(c.flight.numbers)): (c.t, c.k) for c in cells_}
    labels = _labels(con)
    times = Counter((c.h, frozenset(c.flight.numbers)) for c in cells_)
    return sorted([f"{h} hours, {labels[min(ids)][1]} {_show_numbers(ids, labels)}: "
                   f"A0 {_show_cell(a0.get((h, ids)))}, the code {_show_cell(code.get((h, ids)))}"
                   for h, ids in a0.keys() | code.keys() if a0.get((h, ids)) != code.get((h, ids))]
                  + [f"{h} hours, {labels[min(ids)][1]} {_show_numbers(ids, labels)}: the code has it in the row "
                     f"{n} times" for (h, ids), n in times.items() if n > 1])


def signs_carried(table: list[dict], obs: list[dict], snaps: list[dict],
                  cells_: list[counting.Cell]) -> dict[int, dict[tuple, frozenset[str]]]:
    """h -> each flight of `cells_` in row h -> the signs it carries there (record.number_signs and
    record.flight_signs)."""
    st = counting.stretches(table, obs)
    holes_ = counting.holes(snaps)
    passings_ = counting.passings(st, holes_)
    return {h: record.flight_signs([c for c in cells_ if c.h == h],
                                   record.number_signs(h, table, st, holes_, snaps[0]["fetched_at"], passings_))
            for h in counting.CHECKPOINTS}


def _show_signs(signs) -> str:
    return " ".join(sorted(signs)) if signs else "none"


def compare_signs(con, cells_: list[counting.Cell], carried: dict[int, dict[tuple, frozenset[str]]]) -> list[str]:
    """Each row and flight (as the set of its numbers) whose signs differ between A0b's `signcell`, where the sign was
    showing (S1 to S4 by the start of their names; the dropped X signs left out), and `carried` (signs_carried's)."""
    flight = _a0_flights(con)
    a0: dict[tuple, set[str]] = {}
    for sign, h, key in con.execute("SELECT sign, h, flight_key FROM signcell WHERE present").fetchall():
        if sign.split()[0] in record.SIGNS:
            a0.setdefault((h, flight[key]), set()).add(sign.split()[0])
    numbers_of = {c.flight.key: frozenset(c.flight.numbers) for c in cells_}
    code = {(h, numbers_of[key]): set(signs) for h, of in carried.items() for key, signs in of.items() if signs}
    labels = _labels(con)
    return sorted(f"{h} hours, {labels[min(numbers)][1]} {_show_numbers(numbers, labels)}: "
                  f"A0 {_show_signs(a0.get((h, numbers)))}, the code {_show_signs(code.get((h, numbers)))}"
                  for h, numbers in a0.keys() | code.keys() if a0.get((h, numbers)) != code.get((h, numbers)))


def sign_counts(cells_: list[counting.Cell], carried: dict[int, dict[tuple, frozenset[str]]]) -> dict[tuple, tuple]:
    """A25's columns as the code gives them, for each sign at 48, 24, 12 and 6 hours: cancelled and flights with the
    sign, cancelled and flights without it, the airlines and the days among the cancelled flights with it, and whether
    those clear the floor (C8). A row's flights as A0b's `signcell` holds them: S1's are departures only, so an
    arrival is in neither its with nor its without set."""
    out = {}
    for sign in record.SIGNS:
        for h in A25_HOURS:
            row = [c for c in cells_ if c.h == h and (sign != "S1" or c.flight.key[0] == "D")]
            with_ = rates.rate([counting.counted(c.flight) for c in row if sign in carried[h][c.flight.key]])
            without = [c.k for c in row if sign not in carried[h][c.flight.key]]
            out[sign, h] = (with_.cancelled, with_.flights, sum(without), len(without), with_.airlines, with_.days,
                            with_.clears_floor)
    return out


def one_decimal(x: float | None) -> float | None:
    """As DuckDB's round(x, 1) on a double: x * 10 to the nearest whole number, halves away from zero, over 10."""
    return None if x is None else float(Decimal(x * 10).to_integral_value(ROUND_HALF_UP)) / 10


def figure(r: rates.Rate) -> tuple:
    """A rate as the figures file prints it: cancelled, flights, and "1 in" with its range's two ends."""
    return r.cancelled, r.flights, one_decimal(r.one_in), one_decimal(r.one_in_from), one_decimal(r.one_in_to)


def _one_in(x: float | None) -> str:
    return "none" if x is None else f"{x:.1f}"


def show(value) -> str:
    """A figure as `figure` gives it, in words; "nothing" for a figure the code does not give."""
    if value is None:
        return "nothing"
    cancelled, flights, one_in, lo, hi = value
    return f"{cancelled:,} of {flights:,}, 1 in {_one_in(one_in)} ({_one_in(lo)} to {_one_in(hi)})"


def show_signs(value) -> str:
    """A25's columns as sign_counts gives them, in words; "nothing" for a row the code does not give."""
    if value is None:
        return "nothing"
    cancelled_with, flights_with, cancelled_without, flights_without, airlines, days, clears = value
    return (f"{cancelled_with:,} of {flights_with:,} with the sign, {cancelled_without:,} of {flights_without:,} "
            f"without; {airlines} airline{'' if airlines == 1 else 's'} and {days} day{'' if days == 1 else 's'} "
            "with a cancellation, " + ("clears the floor" if clears else "below the floor"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True, help="the model folder (data/model-2026-11-12)")
    model_dir = parser.parse_args(argv).model
    con = run_sql(model_dir, ("A0", "A0b"))
    table, obs, snaps = load(model_dir)
    flights_ = counting.flights(table, counting.last_sighting(snaps))
    cells_ = counting.cells(flights_, counting.passings(counting.stretches(table, obs), counting.holes(snaps)))
    carried = signs_carried(table, obs, snaps, cells_)
    fig = counting.figures(table, obs, snaps)
    got = {"total": figure(fig.total)} | {f"{h} hours": figure(r) for h, r in fig.rows}
    failed = False
    for name, expected in EXPECTED.items():
        if name == "A25":
            continue
        value = got.get(name)
        if value == expected:
            print(f"{name}: {show(value)} ok")
        else:
            print(f"{name}: the code {show(value)}, the figures file {show(expected)}")
            failed = True
    counts = sign_counts(cells_, carried)
    for (sign, h), expected in EXPECTED.get("A25", {}).items():
        if counts.get((sign, h)) == expected:
            print(f"A25 {sign} {h} hours: {show_signs(expected)} ok")
        else:
            print(f"A25 {sign} {h} hours: the code {show_signs(counts.get((sign, h)))}, the figures file "
                  f"{show_signs(expected)}")
            failed = True
    for what, found in (("flights", compare_flights(con, flights_)), ("cells", compare_cells(con, cells_)),
                        ("signs", compare_signs(con, cells_, carried))):
        for line in found:
            print(f"  {line}")
        print(f"{what}: {len(found)} difference{'' if len(found) == 1 else 's'}")
        failed = failed or bool(found)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
