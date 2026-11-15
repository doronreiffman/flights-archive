"""The figures check (scripts/figures_check.py): A0's and A0b's SQL (docs/flight-lookup-figures.md) and the counting
and sign code run on one model, every difference reported.

Here on a synthetic model built through the real model build (`model.build`, from tests/model_helpers.py): a week
of downloads every 30 minutes with a hole, everyday flights with cancellations at every lead time, and rule C1's and
rule C6's cases and the signs' cases beside them, with the edges a break in the counting code would cross (the closed
line, the last second of a number's listing, an hour between downloads, a second passing of one point). It holds no
slot where C1's fallback fires (A0 leaves the fallback out, the comment above its `num`; tests/test_counting.py covers
it), no chain over three numbers (A0 chains in three label rounds) and no blank status (A0 reads a passing's moment
and status with two separate arg_min calls, which skip NULL). All times are naive UTC; Israel time is UTC+2 after the
25 October clock change.
"""
from __future__ import annotations

import importlib.util
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from model import build as model_build
from model_helpers import row, write_receipt, write_snapshot
from timeline import counting, display, rates, record
from timeline.load import load

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "figures_check.py"
DOC = (ROOT / "docs" / "flight-lookup-figures.md").read_text(encoding="utf-8")


def load_script():
    spec = importlib.util.spec_from_file_location("figures_check_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check():
    return load_script()


def test_sql_blocks_finds_a0_and_a0b_and_refuses_a_missing_section(check):
    blocks = check.sql_blocks(DOC, "A0", "A0b")
    assert list(blocks) == ["A0", "A0b"]
    assert blocks["A0"].startswith("SET TimeZone = 'UTC';\nCREATE VIEW flights AS SELECT * FROM 'data/model/")
    assert "CREATE TEMP TABLE cell AS" in blocks["A0"] and "nrow" not in blocks["A0"]
    assert blocks["A0b"].startswith("-- A sign is read for one number") and "CREATE TEMP TABLE nrow AS" in blocks["A0b"]
    with pytest.raises(KeyError):
        check.sql_blocks(DOC, "A0", "A99")
    # a name finds its own section, never one whose name it begins, and never the next section's block
    doc = ("## A10. Ten\n\n```sql\nten\n```\n\n## A1. One\n\n```sql\none\n```\n\n"
           "## A2. Two\n\nno query\n\n## A3. Three\n\n```sql\nthree\n```\n")
    assert check.sql_blocks(doc, "A1") == {"A1": "one\n"}
    with pytest.raises(KeyError):
        check.sql_blocks(doc, "A2")


# --- the synthetic model --------------------------------------------------------------------------------

def nov(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """A time (naive UTC) in November 2026."""
    return datetime(2026, 11, day, hour, minute, second)


START, END = datetime(2026, 10, 29), nov(5, 12)  # the first and the last download
MISSED = nov(1, 12, 30)  # not downloaded: an hour between two downloads, which is not a hole
LAST = nov(5, 12, 16, 45)  # the last sighting: the last download, seen again until then (R9)
BEFORE_HOLE, AFTER_HOLE = nov(2, 3), nov(2, 7)  # nothing downloaded in between; the 03:00 board seen again at 03:20
ISRAEL = timedelta(hours=2)
H = timedelta(hours=1)


@dataclass(frozen=True)
class Number:
    """One flight number on the board. Listed from `first` before its first scheduled time to `last` after its
    final one; it departs or lands 10 minutes after its expected time, unless it is listed as cancelled from
    `cancelled` before its final scheduled time (negative: after), or never shows a final status (`final` False)."""
    airline: str
    flight_no: str
    airport: str
    sched: datetime
    direction: str = "D"
    est: datetime | None = None  # the scheduled time when None
    counters: str | None = None  # "1-5" for a departure, none for an arrival
    terminal: int = 3
    cancelled: timedelta | None = None
    final: bool = True
    first: timedelta = 72 * H
    last: timedelta = 3 * H
    changes: tuple = ()  # (download time, {"sched" | "est" | "status": value}) from that download on

    def at(self, t: datetime) -> dict | None:
        """The board row at download `t`, or None when not listed."""
        status = "ON TIME" if self.direction == "D" else "NOT FINAL"
        shown = {"sched": self.sched, "est": self.est or self.sched, "status": status}
        for when, change in self.changes:
            if t >= when:
                shown |= change
        final_sched = self.sched
        for _, change in self.changes:
            final_sched = change.get("sched", final_sched)
        if not self.sched - self.first <= t <= final_sched + self.last:
            return None
        if self.cancelled is not None and t >= final_sched - self.cancelled:
            shown["status"] = "CANCELED"
        elif self.cancelled is None and self.final and t >= shown["est"] + timedelta(minutes=10):
            shown["status"] = "DEPARTED" if self.direction == "D" else "LANDED"
        counters = self.counters if self.counters is not None else "1-5" if self.direction == "D" else ""
        return row(airline=self.airline, flight_no=self.flight_no, direction=self.direction, airport=self.airport,
                   sched_local=(shown["sched"] + ISRAEL).isoformat(), est_local=(shown["est"] + ISRAEL).isoformat(),
                   status=shown["status"], terminal=self.terminal, counters=counters)


# Closed flights are those scheduled by LAST - 48 h, 3 November 12:16:45 (C4); every case below is closed but TP 1735.
C1_CASES = (
    # one flight: the same expected time, terminal and desks (the model's codeshare key), both departed
    Number("EY", "607", "AUH", nov(2, 9, 30), est=nov(2, 9, 52), counters="12-21"),
    Number("LY", "9614", "AUH", nov(2, 9, 30), est=nov(2, 9, 52), counters="12-21"),
    # two flights: one airline at one desk range, two expected times, both departed
    Number("EY", "596", "AUH", nov(1, 14), est=nov(1, 14, 18), counters="12-21"),
    Number("EY", "610", "AUH", nov(1, 14), est=nov(1, 15, 24), counters="12-21"),
    # two flights: two desk ranges, though one is cancelled and they share the airline
    Number("IZ", "201", "LCA", nov(1, 16), counters="1-5"),
    Number("IZ", "203", "LCA", nov(1, 16), counters="20-25", cancelled=30 * H),
    # two flights: two terminals, though one is cancelled and they share the desks
    Number("OS", "858", "VIE", nov(1, 18)),
    Number("W6", "2001", "VIE", nov(1, 18), terminal=1, cancelled=5 * H),
    # one flight, departed: a cancelled number ties by airline (no desks, another expected time). LY 541 showed
    # 11:00 until 06:00 on 1 November, so it passes the 70-hour point an hour before LY 543: the row's moment
    Number("LY", "541", "ATH", nov(2, 11), changes=((nov(1, 6), {"sched": nov(2, 12), "est": nov(2, 12, 40)}),)),
    Number("LY", "543", "ATH", nov(2, 12), counters="", cancelled=20 * H),
    # one flight, departed: a cancelled number of another airline ties by desks
    Number("VY", "7841", "BCN", nov(2, 20), counters="7-9"),
    Number("IB", "4321", "BCN", nov(2, 20), est=nov(2, 20, 30), counters="7-9", cancelled=8 * H),
    # one flight of three, departed: AZ 811 ties to AZ 813 by airline, AZ 813 to LY 8813 by the codeshare key, and
    # AZ 811 to LY 8813 not at all; the two that departed share expected time, terminal and desks
    Number("AZ", "811", "FCO", nov(3, 6), counters="", cancelled=40 * H),
    Number("AZ", "813", "FCO", nov(3, 6), est=nov(3, 6, 20), counters="30-33"),
    Number("LY", "8813", "FCO", nov(3, 6), est=nov(3, 6, 20), counters="30-33"),
    # one flight: arrivals with no desks and the same expected time, both landed
    Number("AF", "1620", "CDG", nov(2, 15), direction="A", est=nov(2, 15, 10)),
    Number("LY", "6620", "CDG", nov(2, 15), direction="A", est=nov(2, 15, 10)),
    # two flights: arrivals of two airlines with no desks and two expected times, one cancelled
    Number("BA", "165", "LHR", nov(2, 17), direction="A", est=nov(2, 17, 5)),
    Number("U2", "2083", "LHR", nov(2, 17), direction="A", cancelled=6 * H),
    # one flight, cancelled: both numbers cancelled together. The grouping airline (C8) is LY's: 730 is below 1302 as
    # a number, not as text
    Number("UX", "1302", "MAD", nov(2, 22), counters="40-41", cancelled=10 * H),
    Number("LY", "730", "MAD", nov(2, 22), counters="40-41", cancelled=10 * H),
    # one flight, departed: LY 1105 leaves the list at 10:00 on 2 November, exactly 12 hours ahead, with no final
    # status, and passes the 12-hour point in its last second; LY 2105 is first listed 10 hours ahead
    Number("LY", "1105", "NCE", nov(2, 22), final=False, last=-12 * H),
    Number("LY", "2105", "NCE", nov(2, 22), first=10 * H),
)
TOGETHER = {frozenset({"EY 607", "LY 9614"}), frozenset({"LY 541", "LY 543"}), frozenset({"VY 7841", "IB 4321"}),
            frozenset({"AZ 811", "AZ 813", "LY 8813"}), frozenset({"AF 1620", "LY 6620"}),
            frozenset({"UX 1302", "LY 730"}), frozenset({"LY 1105", "LY 2105"})}  # the flights of more than one number

C6_CASES = (
    # first listed 20 hours ahead: rows 12, 6 and 3 only; cancelled 2 hours ahead
    Number("FB", "472", "SOF", nov(2, 23), first=20 * H, cancelled=2 * H),
    # first listed 50 hours ahead, already cancelled: in no row
    Number("RO", "152", "OTP", nov(3, 2), first=50 * H, cancelled=60 * H),
    # retimed at 20:00 on 1 November from 08:00 to 11:00 on the 2nd: the 70-, 48- and 24-hour passings by the first
    # time, the 12-hour one by the second; the 6-hour moment (05:00) falls in the hole
    Number("CY", "2101", "LCA", nov(2, 8), changes=((nov(1, 20), {"sched": nov(2, 11), "est": nov(2, 11)}),)),
    # retimed at 22:00 on 2 November from 04:00 to 11:00 on the 3rd, then cancelled from 07:00: the 24-hour moment
    # by the first time falls in the hole, the 12-hour point is passed by each time (16:00 and 23:00; the first
    # counts), the 6-hour one by the second, and at the 3-hour one it shows cancelled
    Number("A3", "931", "PFO", nov(3, 4), cancelled=4 * H,
           changes=((nov(2, 22), {"sched": nov(3, 11), "est": nov(3, 11)}),)),
    # retimed at 20:00 on 2 November from 11:00 to 13:00 on the 3rd: open (C4), by its final time an hour inside the
    # 48 hours before the last sighting, though its first time is outside them
    Number("TP", "1735", "LIS", nov(3, 11), changes=((nov(2, 20), {"sched": nov(3, 13), "est": nov(3, 13)}),)),
    # DELAYED from 30 hours ahead: in every row
    Number("LX", "257", "ZRH", nov(2, 14), changes=((nov(1, 8), {"status": "DELAYED", "est": nov(2, 16)}),)),
    # listed as cancelled half an hour after its time: in every row, as cancelled; its 6-hour moment is the hole's end
    Number("LO", "152", "KRK", nov(2, 13), cancelled=-H / 2),
    # no known result: left 10 hours ahead (vanished), left after its time with no final status (dropped), and left
    # during the hole (gap)
    Number("BT", "773", "RIX", nov(2, 19), final=False, last=-10 * H),
    Number("A9", "692", "TBS", nov(2, 21), final=False, last=2 * H),
    Number("J2", "101", "GYD", nov(2, 6, 30), final=False, last=-H),
)
ROWS_OF = {"FB 472": (12, 6, 3), "RO 152": (), "CY 2101": (70, 48, 24, 12, 3), "A3 931": (70, 48, 12, 6),
           "LX 257": (70, 48, 24, 12, 6, 3), "LO 152": (70, 48, 24, 12, 6, 3), "TP 1735": (),
           "LY 1105": (70, 48, 24, 12, 6, 3)}  # each case's rows

SIGN_CASES = (
    # S1: LH 687 lands from FRA at 20:00 on 1 November, listed as cancelled 30 hours ahead and alone in its slot; LH 686
    # leaves for FRA 6 hours later and carries S1 from its 24-hour moment on
    Number("LH", "687", "FRA", nov(1, 20), direction="A", cancelled=30 * H),
    Number("LH", "686", "FRA", nov(2, 2)),
    # no S1: LH 1689 lands from MUC at 09:00 on 2 November, listed as cancelled 30 hours ahead, but LY 8689, tied to it
    # by the expected time and no desks, is listed normally and lands; LH 1688 leaves for MUC 5 hours later
    Number("LH", "1689", "MUC", nov(2, 9), direction="A", cancelled=30 * H),
    Number("LY", "8689", "MUC", nov(2, 9), direction="A"),
    Number("LH", "1688", "MUC", nov(2, 14)),
    # S2: OS 860 to VIE at 10:00 on 1 November is listed as cancelled 30 hours ahead; the same number a day later
    # carries S2 from its 48-hour moment on, also after the first has left the list (its last status kept)
    Number("OS", "860", "VIE", nov(1, 10), cancelled=30 * H),
    Number("OS", "860", "VIE", nov(2, 10)),
    # S4 not carried: KL 3433 and DL 9433 are one flight (the same expected time, terminal and desks); KL 3433 is first
    # listed 30 hours ahead, DL 9433 72 hours ahead, so from 24 hours on only one of its numbers in the row shows S4
    Number("KL", "3433", "AMS", nov(2, 18), counters="50-52", first=30 * H),
    Number("DL", "9433", "AMS", nov(2, 18), counters="50-52"),
    # never late: SN 3271 to BRU at 00:00 on 3 November would be first listed 19 hours ahead, in the hole; it is first
    # seen at the hole's end, 17 hours ahead
    Number("SN", "3271", "BRU", nov(3, 0), first=19 * H),
)
TOGETHER |= {frozenset({"LH 1689", "LY 8689"}), frozenset({"KL 3433", "DL 9433"})}

LEADS = (1, 36, -0.5, 9, 60, 4, 20)  # hours before the scheduled time an everyday cancellation is listed


def everyday() -> list[Number]:
    """A flight every 2 h 25 min from 29 October 01:10 to 6 November, five airlines and six airports, one in six
    cancelled, each at the next lead in LEADS; one in three an arrival."""
    out = []
    for i in range(88):
        out.append(Number(("LY", "IZ", "6H", "W6", "UA")[i % 5], str(300 + i),
                          ("BER", "AMS", "BRU", "CPH", "DUB", "HEL")[i % 6],
                          START + timedelta(hours=1, minutes=10) + i * timedelta(hours=2, minutes=25),
                          direction="A" if i % 3 == 0 else "D",
                          cancelled=LEADS[i // 6 % len(LEADS)] * H if i % 6 == 4 else None))
    return out


NUMBERS = (*C1_CASES, *C6_CASES, *SIGN_CASES, *everyday())


def downloads() -> list[datetime]:
    out, t = [], START
    while t <= END:
        if not BEFORE_HOLE < t < AFTER_HOLE and t != MISSED:
            out.append(t)
        t += timedelta(minutes=30)
    return out


def archive(root: Path) -> tuple[Path, Path]:
    raw, receipts = root / "raw", root / "receipts"
    for t in downloads():
        rows = [r for r in (n.at(t) for n in NUMBERS) if r is not None]
        sid = write_snapshot(raw, t, rows)
        write_receipt(receipts, sid, rows=len(rows))
        for again in {BEFORE_HOLE: (nov(2, 3, 20),), END: (nov(5, 12, 8), LAST)}.get(t, ()):
            write_receipt(receipts, sid, action="unchanged", when=again, rows=len(rows))
    return raw, receipts


@dataclass(frozen=True)
class Model:
    dir: Path
    table: list[dict]
    obs: list[dict]
    snaps: list[dict]
    con: object  # A0 run on the model
    labels: dict[str, str]  # flight_id -> "airline flight_no"

    def flights(self) -> list[counting.Flight]:
        return counting.flights(self.table, counting.last_sighting(self.snaps))

    def cells(self) -> list[counting.Cell]:
        return counting.cells(self.flights(), counting.passings(counting.stretches(self.table, self.obs),
                                                                counting.holes(self.snaps)))

    def named(self, numbers) -> frozenset[str]:
        return frozenset(self.labels[fid] for fid in numbers)

    def carried(self, check, cells_: list[counting.Cell]) -> dict[int, dict[tuple, frozenset[str]]]:
        return check.signs_carried(self.table, self.obs, self.snaps, cells_)


@pytest.fixture(scope="module")
def model(check, tmp_path_factory) -> Model:
    root = tmp_path_factory.mktemp("figures")
    raw, receipts = archive(root)
    model_build.build(raw, root / "model", receipts)
    table, obs, snaps = load(root / "model")
    assert counting.last_sighting(snaps) == LAST
    return Model(root / "model", table, obs, snaps, check.run_sql(root / "model", ("A0", "A0b")),
                 {f["flight_id"]: f"{f['airline']} {f['flight_no']}" for f in table})


# --- the comparisons ------------------------------------------------------------------------------------

def test_the_flights_match_a0(check, model):
    flights_ = model.flights()
    assert check.compare_flights(model.con, flights_) == []
    # the model holds rule C1's cases: these numbers are one flight each, and every other number is a flight alone
    assert {model.named(f.numbers) for f in flights_ if len(f.numbers) > 1} == TOGETHER
    assert len(model.table) == len(NUMBERS)  # each retime linked: one number, one flights row


def test_the_cells_match_a0(check, model):
    cells_ = model.cells()
    assert check.compare_cells(model.con, cells_) == []
    # the model holds rule C6's cases, and the hole takes some passings out
    rows_of = {}
    for c in cells_:
        for name in model.named(c.flight.numbers):
            rows_of.setdefault(name, []).append(c.h)
    assert {name: tuple(rows_of.get(name, ())) for name in ROWS_OF} == ROWS_OF
    seen_again = nov(2, 3, 20)  # the hole runs from the last sighting before it to the next download
    assert not [c for c in cells_ if seen_again < c.t < AFTER_HOLE]
    assert any(c.t == AFTER_HOLE for c in cells_) and any(BEFORE_HOLE < c.t <= seen_again for c in cells_)
    assert any(MISSED - H / 2 < c.t < MISSED + H / 2 for c in cells_)
    moment = {(c.h, model.named(c.flight.numbers)): c.t for c in cells_}
    assert moment[70, frozenset({"LY 541", "LY 543"})] == datetime(2026, 10, 30, 13)  # LY 541's passing, the earlier
    assert moment[12, frozenset({"A3 931"})] == nov(2, 16)  # the first of its two passings


def sql_figure(r: dict) -> tuple:
    """A row of A0's `rng` as figures_check.figure gives a rate: NULL, inf and NaN, which `rng` gives where a grouping
    has one group, read as no value, as rates.rate's None."""
    def value(x):
        return None if x is None or not math.isfinite(x) else x
    return (r["cancelled"], r["flights"], value(r["one_in"]), value(r["range_from_one_in"]),
            value(r["range_to_one_in"]))


def rng(check, model: Model, name: str) -> list[dict]:
    """The figures file's own query for A2 or A6, on the model."""
    cur = model.con.execute(check.sql_blocks(DOC, name)[name])
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def sql_figures(check, model: Model) -> dict[str, dict]:
    """The total (A2) and each row of the table (A6) as A0's `rng` gives them, named as figures_check names them."""
    return {"total": rng(check, model, "A2")[0]} | {f"{r['grp']} hours": r for r in rng(check, model, "A6")}


def test_the_rates_match_a0s_rng(check, model):
    fig = counting.figures(model.table, model.obs, model.snaps)
    code = {"total": fig.total} | {f"{h} hours": r for h, r in fig.rows}
    sql = sql_figures(check, model)
    assert list(sql) == list(code) == ["total", *(f"{h} hours" for h in counting.CHECKPOINTS)]
    for name, r in code.items():
        s = sql[name]
        assert (r.cancelled, r.flights, r.airlines, r.days, r.clears_floor) == (
            s["cancelled"], s["flights"], s["airlines_with_a_cancellation"], s["days_with_a_cancellation"],
            s["clears_floor"]), name
        assert check.figure(r) == sql_figure(s), name
        assert None not in check.figure(r) and 0 < r.cancelled < r.flights, name  # every end is compared


def carry(model: Model, carried: dict, cells_: list[counting.Cell], name: str, sched: datetime) -> dict:
    """h -> the signs the flight of number `name` scheduled at `sched` carries in row h, for each row it is in."""
    return {c.h: carried[c.h][c.flight.key] for c in cells_
            if name in model.named(c.flight.numbers) and c.flight.key[2] == sched}


def test_the_signs_match_a0b(check, model):
    cells_ = model.cells()
    carried = model.carried(check, cells_)
    assert check.compare_signs(model.con, cells_, carried) == []
    # the model holds the signs' cases
    none = frozenset()
    assert carry(model, carried, cells_, "LH 686", nov(2, 2)) == {
        70: none, 48: none, **{h: frozenset({"S1", "S3"}) for h in (24, 12, 6, 3)}}
    assert carry(model, carried, cells_, "LH 1688", nov(2, 14)) == {
        70: none, 48: frozenset({"S3"}), 24: frozenset({"S3"}), 12: none, 6: none, 3: none}
    assert carry(model, carried, cells_, "OS 860", nov(2, 10)) == {
        70: none, 48: frozenset({"S2", "S3"}), 24: frozenset({"S2", "S3"}), 12: frozenset({"S2"}), 3: frozenset({"S2"})}
    assert carry(model, carried, cells_, "KL 3433", nov(2, 18)) == {h: none for h in (70, 48, 24, 6, 3)}
    assert carry(model, carried, cells_, "FB 472", nov(2, 23)) == {h: frozenset({"S4"}) for h in (12, 6, 3)}
    assert carry(model, carried, cells_, "SN 3271", nov(3, 0)) == {h: none for h in (12, 6, 3)}


def sql_a25(check, model: Model) -> dict[tuple[str, int], tuple]:
    """A25's own query on the model, as figures_check.sign_counts gives it: S1 to S4 by the start of their names, the
    dropped X signs left out."""
    cur = model.con.execute(check.sql_blocks(DOC, "A25")["A25"])
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    return {(r["sign"].split()[0], r["h"]): (r["cancelled_with"], r["flights_with"], r["cancelled_without"],
                                              r["flights_without"], r["airlines_with_a_cancellation"],
                                              r["days_with_a_cancellation"], r["clears_floor"], r["times"],
                                              r["times_from"], r["times_to"], r["passes"])
            for r in rows if r["sign"].split()[0] in record.SIGNS}


def test_the_sign_counts_match_a25(check, model):
    cells_ = model.cells()
    code = check.sign_counts(cells_, model.carried(check, cells_))
    assert list(code) == [(sign, h) for sign in record.SIGNS for h in (48, 24, 12, 6)]
    assert code == sql_a25(check, model)
    assert {sign for (sign, _), counts in code.items() if counts[1]} == set(record.SIGNS)  # each sign is carried


def test_an_arrival_is_never_in_s1s_with_or_without_set(check, model):
    cells_ = model.cells()
    carried = model.carried(check, cells_)
    counts = check.sign_counts(cells_, carried)
    planted = {h: {key: signs | {"S1"} if key[0] == "A" else signs for key, signs in of.items()}
               for h, of in carried.items()}
    assert check.sign_counts(cells_, planted) == counts  # every arrival carrying S1 moves nothing
    for h in (48, 24, 12, 6):
        departures = sum(c.h == h and c.flight.key[0] == "D" for c in cells_)
        flights = sum(c.h == h for c in cells_)
        s1, s2 = counts["S1", h], counts["S2", h]
        assert s1[1] + s1[3] == departures < flights == s2[1] + s2[3]


def test_planted_sign_differences_are_named(check, model):
    cells_ = model.cells()
    carried = model.carried(check, cells_)
    key = {model.named(c.flight.numbers): c.flight.key for c in cells_ if c.h == 24}
    planted = {h: dict(of) for h, of in carried.items()}
    planted[24][key[frozenset({"LH 686"})]] = frozenset({"S3"})
    planted[24][key[frozenset({"KL 3433", "DL 9433"})]] = frozenset({"S2", "S4"})
    planted[12] = {k: signs for k, signs in planted[12].items() if k != key[frozenset({"LH 686"})]}
    assert one_each(check.compare_signs(model.con, cells_, planted), [
        ("24 hours, D FRA 2026-11-02 02:00 LH 686 (", "): A0 S1 S3, the code S3"),
        ("24 hours, D AMS 2026-11-02 18:00 DL 9433 (", "): A0 none, the code S2 S4"),
        ("12 hours, D FRA 2026-11-02 02:00 LH 686 (", "): A0 S1 S3, the code none")])


# A0b's floor in `ratio` (C8's, as in rates.rate) and the row from which it gives the grouped-over-plain column,
# each lowered to 1 cancelled flight
LOWERED = (("(t.k1 >= 10 AND t.airlines >= 5 AND t.days_ >= 5)", "(t.k1 >= 1 AND t.airlines >= 1 AND t.days_ >= 1)"),
           ("CASE WHEN k1 >= 3 THEN round(se_ratio, 2) END", "CASE WHEN k1 >= 1 THEN round(se_ratio, 2) END"))


def test_the_ratios_match_a0b(check, model, monkeypatch, tmp_path):
    cells_ = model.cells()
    carried = model.carried(check, cells_)
    assert check.compare_ratios(model.con, cells_, carried) == []
    # No sign here has 3 cancelled flights with it, so neither side gives a ratio, a range or the grouped-over-plain
    # column in any row. With the floor and that column's row lowered to 1 cancelled flight (from 1 airline on 1 day),
    # in A0b's text and in the code alike, four rows give them all, one passes, and they match.
    doc = DOC
    for old, new in LOWERED:
        assert doc.count(old) == 1
        doc = doc.replace(old, new)
    (tmp_path / "figures.md").write_text(doc, encoding="utf-8")
    monkeypatch.setattr(check, "DOC", tmp_path / "figures.md")
    for name in ("FLOOR_CANCELLED", "FLOOR_AIRLINES", "FLOOR_DAYS"):
        monkeypatch.setattr(rates, name, 1)
    monkeypatch.setattr(check, "SE_RATIO_FROM", 1)
    con = check.run_sql(model.dir, ("A0", "A0b"))
    assert check.compare_ratios(con, cells_, carried) == []
    given = {key: value for key, value in check.sql_ratios(con).items() if value != (None, None, None, False, None)}
    assert sorted(given) == [("S3", 24), ("S3", 48), ("S4", 6), ("S4", 12)]
    assert all(None not in value for value in given.values())
    assert [key for key, value in given.items() if value[3]] == [("S4", 12)]


def passing_s3_at_24(real):
    """rates.lift as it stands, but passing for S3's 24-hour row on this model, 2 cancelled of 17 with the sign."""
    def lift(with_, without):
        out = real(with_, without)
        return replace(out, passes=True) if (out.cancelled_with, out.flights_with) == (2, 17) else out
    return lift


def test_a_planted_ratio_difference_is_named(check, model, monkeypatch):
    cells_ = model.cells()
    carried = model.carried(check, cells_)
    monkeypatch.setattr(rates, "lift", passing_s3_at_24(rates.lift))
    assert check.compare_ratios(model.con, cells_, carried) == [
        "A25 S3 24 hours: A0b no ratio, does not pass, grouped over plain none, "
        "the code no ratio, passes, grouped over plain none"]


def splitting(model: Model, real):
    """counting.flights as it stands, but EY 607 and LY 9614 apart."""
    def flights(table, last):
        out = []
        for f in real(table, last):
            if model.named(f.numbers) == {"EY 607", "LY 9614"}:
                out += [replace(f, key=(*f.key[:3], fid), numbers=(fid,)) for fid in f.numbers]
            else:
                out.append(f)
        return out
    return flights


def dropping(model: Model, real):
    """counting.cells as it stands, but LX 257 left out of the 70-hour row."""
    def cells(flights_, passings_):
        return [c for c in real(flights_, passings_) if (c.h, model.named(c.flight.numbers)) != (70, {"LX 257"})]
    return cells


def test_a_planted_difference_is_named(check, model, monkeypatch):
    monkeypatch.setattr(counting, "flights", splitting(model, counting.flights))
    found = check.compare_flights(model.con, counting.flights(model.table, counting.last_sighting(model.snaps)))
    assert len(found) == 2 and all("EY 607" in line and "LY 9614" in line for line in found), found


def one_each(found: list[str], expected: list[tuple[str, str]]) -> bool:
    """As many lines in `found` as pairs, and each (start, end) pair matches exactly one line. A number is shown
    with the start of its flight_id, so a line is matched by what comes before and after it."""
    return len(found) == len(expected) and all(
        sum(line.startswith(a) and line.endswith(b) for line in found) == 1 for a, b in expected)


def test_planted_cell_differences_are_named(check, model):
    cells_ = model.cells()
    at = {(c.h, model.named(c.flight.numbers)): c for c in cells_}
    ro152 = next(f for f in model.flights() if model.named(f.numbers) == {"RO 152"})  # cancelled when first seen
    moved, flipped = at[24, frozenset({"LO 152"})], at[12, frozenset({"FB 472"})]
    planted = [c for c in cells_ if c not in (at[70, frozenset({"LX 257"})], moved, flipped)] + [
        replace(moved, t=moved.t + timedelta(minutes=1)), replace(flipped, k=0), counting.Cell(3, ro152, nov(2, 23), 1)]
    assert one_each(check.compare_cells(model.con, planted), [
        ("70 hours, D ZRH 2026-11-02 14:00 LX 257 (",
         ": A0 in the row from 2026-10-30 16:00:00, not cancelled, the code not in the row"),
        ("24 hours, D KRK 2026-11-02 13:00 LO 152 (", ": A0 in the row from 2026-11-01 13:00:00, cancelled, "
                                                     "the code in the row from 2026-11-01 13:01:00, cancelled"),
        ("12 hours, D SOF 2026-11-02 23:00 FB 472 (", ": A0 in the row from 2026-11-02 11:00:00, cancelled, "
                                                     "the code in the row from 2026-11-02 11:00:00, not cancelled"),
        ("3 hours, D OTP 2026-11-03 02:00 RO 152 (",
         ": A0 not in the row, the code in the row from 2026-11-02 23:00:00, cancelled")])


def test_a_duplicate_is_named(check, model):
    flights_, cells_ = model.flights(), model.cells()
    twice = next(f for f in flights_ if model.named(f.numbers) == {"EY 607", "LY 9614"})
    assert one_each(check.compare_flights(model.con, [*flights_, twice]), [
        ("D AUH 2026-11-02 09:30: the code puts EY 607 (", ") in 2 flights"),
        ("D AUH 2026-11-02 09:30: the code puts LY 9614 (", ") in 2 flights")])
    cell = next(c for c in cells_ if (c.h, model.named(c.flight.numbers)) == (70, {"LX 257"}))
    assert one_each(check.compare_cells(model.con, [*cells_, cell]), [
        ("70 hours, D ZRH 2026-11-02 14:00 LX 257 (", "): the code has it in the row 2 times")])


def test_run_sql_refuses_an_a0_that_reads_no_model_path(check, model, tmp_path, monkeypatch):
    doc = tmp_path / "figures.md"
    doc.write_text("## A0. Setup\n\n```sql\nCREATE VIEW flights AS SELECT * FROM 'data/model2/flights.parquet';\n"
                   "```\n")
    monkeypatch.setattr(check, "DOC", doc)
    with pytest.raises(ValueError, match="A0 .* reads no 'data/model/ path"):
        check.run_sql(model.dir, ("A0",))


A29_AT = datetime(2026, 10, 29, 22)  # A29's counting start on this model, 30 October's Israel midnight: half the row


def sql_a29(check, model: Model, start: datetime) -> dict[str, tuple]:
    """A29's own query on the model, its counting start moved to `start`, as figures_check.a29_counts gives it."""
    block = check.sql_blocks(DOC, "A29")["A29"]
    fixed = "TIMESTAMP '2026-11-05 22:00:00'"
    assert block.count(fixed) == 1
    cur = model.con.execute(block.replace(fixed, f"TIMESTAMP '{start:%Y-%m-%d %H:%M:%S}'"))
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    row = {(r["row_cancelled_so_far"], r["days_so_far"], r["gate_reached_at"]) for r in rows}
    assert len(row) == 1, row
    return {r["sign"].split()[0]: (r["cancelled_with"], r["flights_with"], r["cancelled_without"], r["flights_without"])
            for r in rows} | {"row": row.pop()}


def test_the_dry_run_matches_a29(check, model):
    code = check.a29_counts(record.run(model.table, model.obs, model.snaps, A29_AT))
    assert list(code) == [*record.SIGNS, "row"]
    assert code == sql_a29(check, model, A29_AT)
    # the start leaves flights of the row out, a sign is carried, and the gate is not reached
    everything = check.a29_counts(record.run(model.table, model.obs, model.snaps, A29_AT - timedelta(days=1)))
    assert 0 < code["S2"][1] + code["S2"][3] < everything["S2"][1] + everything["S2"][3]
    assert code["S3"][1] > 0 and code["row"][2] is None


def a29_as_sql(check, model: Model, monkeypatch) -> dict[str, tuple]:
    """A29's figures as its query gives them on this model, as figures_check's EXPECTED_A29 from A29_AT."""
    expected = sql_a29(check, model, A29_AT)
    monkeypatch.setattr(check, "A29_START", A29_AT)
    monkeypatch.setattr(check, "EXPECTED_A29", expected)
    return expected


A3_A17 = ("A3", "A17")


def sql_counts(check, model: Model) -> dict[tuple[str, str], int]:
    """A3's and A17's own queries on the model, one entry per row, named as figures_check.summary_counts names them."""
    return {(name, row): n for name in A3_A17
            for row, n in model.con.execute(check.sql_blocks(DOC, name)[name]).fetchall()}


def code_counts(check, model: Model) -> dict[tuple[str, str], int]:
    """A3's and A17's rows as the code gives them on the model (figures_check.summary_counts)."""
    return check.summary_counts(display.summary(model.table, model.obs, model.snaps), model.flights(), model.table)


def test_the_counts_match_a3_and_a17(check, model):
    code = code_counts(check, model)
    assert list(code) == list(check.EXPECTED_COUNTS)  # every row of A3 and A17, in the figures file's order
    assert code == sql_counts(check, model)
    assert 0 not in code.values()  # the model holds each row's case, so every row is compared


def counts_as_sql(check, model: Model, monkeypatch) -> dict[tuple[str, str], int]:
    """A3's and A17's figures as their queries give them on this model, as figures_check's EXPECTED_COUNTS."""
    sql = sql_counts(check, model)
    expected = {key: sql[key] for key in check.EXPECTED_COUNTS}
    monkeypatch.setattr(check, "EXPECTED_COUNTS", expected)
    return expected


def test_main_fails_on_a_figure_that_differs(check, model, monkeypatch, capsys):
    expected = {name: sql_figure(r) for name, r in sql_figures(check, model).items()}
    expected_a25 = sql_a25(check, model)
    expected_a29 = a29_as_sql(check, model, monkeypatch)
    expected_counts = counts_as_sql(check, model, monkeypatch)
    monkeypatch.setattr(check, "EXPECTED", expected)
    monkeypatch.setattr(check, "EXPECTED_A25", expected_a25)
    assert check.main(["--model", str(model.dir)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        *(f"{name}: {check.show(v)} ok" for name, v in expected.items()),
        *(f"A25 {sign} {h} hours: {check.show_signs(v)} ok" for (sign, h), v in expected_a25.items()),
        *(f"A29 {name}: {check.show_a29(name, v)} ok" for name, v in expected_a29.items()),
        *(f"{name} {row}: {n:,} ok" for (name, row), n in expected_counts.items()),
        "flights: 0 differences", "cells: 0 differences", "signs: 0 differences",
        "ratios: 0 differences"]

    cancelled, flights, *ends = expected["24 hours"]
    monkeypatch.setattr(check, "EXPECTED", expected | {"24 hours": (cancelled, flights + 1, *ends)})
    assert check.main(["--model", str(model.dir)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if not line.endswith(" ok")] == [
        f"24 hours: the code {check.show(expected['24 hours'])}, the figures file "
        f"{check.show((cancelled, flights + 1, *ends))}",
        "flights: 0 differences", "cells: 0 differences", "signs: 0 differences",
        "ratios: 0 differences"]


def test_main_fails_on_an_a25_row_that_differs(check, model, monkeypatch, capsys):
    """An A25 row alone fails the run, every figure and comparison matching."""
    expected_a25 = sql_a25(check, model)
    with_, flights_with, *rest = expected_a25["S3", 24]
    a29_as_sql(check, model, monkeypatch)
    counts_as_sql(check, model, monkeypatch)
    monkeypatch.setattr(check, "EXPECTED", {name: sql_figure(r) for name, r in sql_figures(check, model).items()})
    monkeypatch.setattr(check, "EXPECTED_A25", expected_a25 | {("S3", 24): (with_, flights_with + 1, *rest)})
    assert check.main(["--model", str(model.dir)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if not line.endswith(" ok")] == [
        f"A25 S3 24 hours: the code {check.show_signs(expected_a25['S3', 24])}, the figures file "
        f"{check.show_signs((with_, flights_with + 1, *rest))}",
        "flights: 0 differences", "cells: 0 differences", "signs: 0 differences",
        "ratios: 0 differences"]


@pytest.mark.parametrize("name", ["S3", "row"])
def test_main_fails_on_an_a29_row_that_differs(check, model, monkeypatch, capsys, name):
    """An A29 row alone fails the run, every figure and comparison matching."""
    expected_a29 = a29_as_sql(check, model, monkeypatch)
    counts_as_sql(check, model, monkeypatch)
    first, *rest = expected_a29[name]
    monkeypatch.setattr(check, "EXPECTED_A29", expected_a29 | {name: (first + 1, *rest)})
    monkeypatch.setattr(check, "EXPECTED", {name: sql_figure(r) for name, r in sql_figures(check, model).items()})
    monkeypatch.setattr(check, "EXPECTED_A25", sql_a25(check, model))
    assert check.main(["--model", str(model.dir)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if not line.endswith(" ok")] == [
        f"A29 {name}: the code {check.show_a29(name, expected_a29[name])}, the figures file "
        f"{check.show_a29(name, (first + 1, *rest))}",
        "flights: 0 differences", "cells: 0 differences", "signs: 0 differences",
        "ratios: 0 differences"]


@pytest.mark.parametrize(("figure", "row"), [("A3", 1), ("A17", 2)])
def test_main_fails_on_an_a3_or_a17_row_that_differs(check, model, monkeypatch, capsys, figure, row):
    """An A3 or A17 row alone fails the run, every other figure and comparison matching."""
    a29_as_sql(check, model, monkeypatch)
    monkeypatch.setattr(check, "EXPECTED", {name: sql_figure(r) for name, r in sql_figures(check, model).items()})
    monkeypatch.setattr(check, "EXPECTED_A25", sql_a25(check, model))
    expected = counts_as_sql(check, model, monkeypatch)
    key = (figure, (check.A3_ROWS if figure == "A3" else check.A17_ROWS)[row])
    monkeypatch.setattr(check, "EXPECTED_COUNTS", expected | {key: expected[key] + 1})
    assert check.main(["--model", str(model.dir)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if not line.endswith(" ok")] == [
        f"{figure} {key[1]}: the code {expected[key]:,}, the figures file {expected[key] + 1:,}",
        "flights: 0 differences", "cells: 0 differences", "signs: 0 differences",
        "ratios: 0 differences"]


def dropping_s1(model: Model, real):
    """record.flight_signs as it stands, but LH 686 not carrying S1 at 24 hours."""
    def flight_signs(cells_h, number_signs_):
        out = real(cells_h, number_signs_)
        for c in cells_h:
            if (c.h, model.named(c.flight.numbers)) == (24, {"LH 686"}):
                out[c.flight.key] -= {"S1"}
        return out
    return flight_signs


@pytest.mark.parametrize("plant", ["flight", "cell", "sign", "ratio"])
def test_main_fails_on_a_flight_cell_sign_or_ratio_difference(check, model, monkeypatch, capsys, plant):
    if plant == "flight":
        monkeypatch.setattr(counting, "flights", splitting(model, counting.flights))
    elif plant == "cell":
        monkeypatch.setattr(counting, "cells", dropping(model, counting.cells))
    elif plant == "sign":
        monkeypatch.setattr(record, "flight_signs", dropping_s1(model, record.flight_signs))
    else:
        monkeypatch.setattr(rates, "lift", passing_s3_at_24(rates.lift))
    # every figure as the planted code gives it, so that only the planted difference can fail the run
    fig = counting.figures(model.table, model.obs, model.snaps)
    cells_ = model.cells()
    monkeypatch.setattr(check, "EXPECTED", {"total": check.figure(fig.total)}
                        | {f"{h} hours": check.figure(r) for h, r in fig.rows})
    monkeypatch.setattr(check, "EXPECTED_A25", check.sign_counts(cells_, model.carried(check, cells_)))
    monkeypatch.setattr(check, "A29_START", A29_AT)
    monkeypatch.setattr(check, "EXPECTED_A29",
                        check.a29_counts(record.run(model.table, model.obs, model.snaps, A29_AT)))
    monkeypatch.setattr(check, "EXPECTED_COUNTS", code_counts(check, model))
    assert check.main(["--model", str(model.dir)]) == 1
    out = [line for line in capsys.readouterr().out.splitlines() if not line.endswith(" ok")]
    summary = [line for line in out if not line.startswith("  ")]
    if plant == "flight":
        pair = (r"  D AUH 2026-11-02 09:30: A0 EY 607 \(\w{8}\) \+ LY 9614 \(\w{8}\), "
                r"the code (EY 607|LY 9614) \(\w{8}\)")
        found = [re.fullmatch(pair, line) for line in out[:2]]
        assert None not in found and sorted(m.group(1) for m in found) == ["EY 607", "LY 9614"], out[:2]
        # in each of the flight's four rows: A0's flight not in the code's row, and the code's two not in A0's; in the
        # two rows where LY 9614 shows S3, A0's flight carries it and the code's LY 9614 alone does
        assert summary == ["flights: 2 differences", "cells: 12 differences", "signs: 4 differences",
                           "ratios: 0 differences"]
    elif plant == "cell":
        assert summary == ["flights: 0 differences", "cells: 1 difference", "signs: 0 differences",
                           "ratios: 0 differences"] and len(out) == 5
        assert one_each(out[1:2], [
            ("  70 hours, D ZRH 2026-11-02 14:00 LX 257 (",
             ": A0 in the row from 2026-10-30 16:00:00, not cancelled, the code not in the row")])
    elif plant == "sign":
        assert summary == ["flights: 0 differences", "cells: 0 differences", "signs: 1 difference",
                           "ratios: 0 differences"] and len(out) == 5
        assert one_each(out[2:3], [("  24 hours, D FRA 2026-11-02 02:00 LH 686 (", "): A0 S1 S3, the code S3")])
    else:
        assert out == ["flights: 0 differences", "cells: 0 differences", "signs: 0 differences",
                       "  A25 S3 24 hours: A0b no ratio, does not pass, grouped over plain none, the code no ratio, "
                       "passes, grouped over plain none", "ratios: 1 difference"]
