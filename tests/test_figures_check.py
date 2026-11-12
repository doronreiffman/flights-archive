"""The figures check (scripts/figures_check.py): A0's SQL (docs/flight-lookup-figures.md) and the counting code run on
one model, every difference reported.

Here on a synthetic model built through the real model build (`model.build`, from tests/model_helpers.py): a week
of downloads every 30 minutes with a hole, everyday flights with cancellations at every lead time, and rule C1's and
rule C6's cases beside them, with the edges a break in the counting code would cross (the closed line, the last
second of a number's listing, an hour between downloads, a second passing of one point). It holds no slot where C1's
fallback fires (A0 leaves the fallback out, the comment above its `num`; tests/test_counting.py covers it), no chain
over three numbers (A0 chains in three label rounds) and no blank status (A0 reads a passing's moment and status with
two separate arg_min calls, which skip NULL). All times are naive UTC; Israel time is UTC+2 after the 25 October
clock change.
"""
from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from model import build as model_build
from model_helpers import row, write_receipt, write_snapshot
from timeline import counting
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


NUMBERS = (*C1_CASES, *C6_CASES, *everyday())


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


@pytest.fixture(scope="module")
def model(check, tmp_path_factory) -> Model:
    root = tmp_path_factory.mktemp("figures")
    raw, receipts = archive(root)
    model_build.build(raw, root / "model", receipts)
    table, obs, snaps = load(root / "model")
    assert counting.last_sighting(snaps) == LAST
    return Model(root / "model", table, obs, snaps, check.run_sql(root / "model", ("A0",)),
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


def test_a_planted_difference_is_named(check, model, monkeypatch):
    real = counting.flights

    def split(table, last):
        """Rule C1 as it stands, but EY 607 and LY 9614 apart."""
        out = []
        for f in real(table, last):
            if model.named(f.numbers) == {"EY 607", "LY 9614"}:
                out += [replace(f, key=(*f.key[:3], fid), numbers=(fid,)) for fid in f.numbers]
            else:
                out.append(f)
        return out

    monkeypatch.setattr(counting, "flights", split)
    found = check.compare_flights(model.con, counting.flights(model.table, counting.last_sighting(model.snaps)))
    assert len(found) == 2 and all("EY 607" in line and "LY 9614" in line for line in found), found


def test_main_fails_on_a_figure_that_differs(check, model, monkeypatch, capsys):
    expected = {name: sql_figure(r) for name, r in sql_figures(check, model).items()}
    monkeypatch.setattr(check, "EXPECTED", expected)
    assert check.main(["--model", str(model.dir)]) == 0
    assert capsys.readouterr().out.splitlines() == [*(f"{name}: {check.show(v)} ok" for name, v in expected.items()),
                                                    "flights: 0 differences", "cells: 0 differences"]

    cancelled, flights, *ends = expected["24 hours"]
    monkeypatch.setattr(check, "EXPECTED", expected | {"24 hours": (cancelled, flights + 1, *ends)})
    assert check.main(["--model", str(model.dir)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if not line.endswith(" ok")] == [
        f"24 hours: the code {check.show(expected['24 hours'])}, the figures file "
        f"{check.show((cancelled, flights + 1, *ends))}", "flights: 0 differences", "cells: 0 differences"]
