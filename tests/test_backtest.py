"""The back-test of the blend (src/timeline/backtest.py; docs/flight-lookup.md, "Before it ships: the back-test" and
:882; the plan's "What this plan decided", the back-test): the last closed week of flights predicted from the weeks
before it, against what happened.

The archive is in rows (tests/counting_helpers.py; LY 1 departing to ATH by default): two weeks of history, 1 to 10
November, and the week each test adds, 15 to 21 November in Israel (UTC+2). The last sighting is LAST, 23 November
22:00 UTC: 21 November is then the last Israel day whose flights are all closed, 48 hours after 22 November 00:00
in Israel, and the counts are cut at 15 November 00:00 in Israel (14 November 22:00 UTC). No row of an archive this
small clears C8's floor, so no chance is scaled. Every chance is hand-computed with the blend's formula: the
airport's rate; the airline's k of n pulled towards it as if it had 100 more flights at it; the number's pulled
towards that at 14. All times are naive UTC.
"""
import os
import subprocess
import sys
from dataclasses import replace
from datetime import date, timedelta
from functools import partial
from pathlib import Path

import pytest

from counting_helpers import T, board, number, seen
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import backtest
from timeline.backtest import Part

approx = partial(pytest.approx, rel=1e-9)
LAST = T(23, 22)
H = timedelta(hours=1)
DOUBLE, HALF, RANKED = backtest.FLAGS


def listed(fid: str, sched, outcome: str = "departed", ahead: float = 72, late: float | None = 0.0, **kw):
    """A flights row with the columns the blend reads beside counting's (the final expected time less the scheduled
    one in minutes, the published name), and its one observation, first stored `ahead` hours before its time. It is
    in the row of every checkpoint at or under `ahead` hours, once closed with a known result."""
    row = number(fid, sched, outcome=outcome, first_seen_at=sched - ahead * H, **kw)
    return (row | {"est_minus_sched_min": late, "airline_name": row["airline"]},
            seen(fid, 1, sched - ahead * H, sched_utc=sched))


def archive(*cases) -> tuple[list[dict], list[dict], list[dict]]:
    """The table, observations and snapshots of `cases`, each a (row, observation) pair; last sighting LAST."""
    return [row for row, _ in cases], [o for _, o in cases], board(LAST)


def history() -> list:
    """Flights all closed as of the cut (scheduled by 12 November 22:00): LY 1 to ATH daily 1 to 10 November at 06:00,
    cancelled on the 2nd and 5th, an hour late on the 3rd; LY 2 from ATH daily at 10:00, none cancelled, an hour late
    on the 4th and 6th; LO 155 to WAW daily 1 to 5 November at 12:00, cancelled on the 1st."""
    out = []
    for d in range(1, 11):
        out.append(listed(f"ly1-{d}", T(d, 6), "canceled" if d in (2, 5) else "departed",
                          late=60.0 if d == 3 else 0.0))
        out.append(listed(f"ly2-{d}", T(d, 10), "landed", late=60.0 if d in (4, 6) else 0.0, flight_no="2",
                          direction="A"))
    for d in range(1, 6):
        out.append(listed(f"lo-{d}", T(d, 12), "canceled" if d == 1 else "departed", airline="LO", flight_no="155",
                          airport="WAW"))
    return out


# The history's counts by hand: the airport's 3 cancelled of 25; LY's 2 of 20; of departures, 12 flew and 1 was an
# hour late; of arrivals, 10 flew and 2 were; LY's 3 delayed of 18 that flew, both directions.
AIRPORT = 3 / 25
LY = (2 + 100 * AIRPORT) / (20 + 100)
DELAY_D, DELAY_A = 1 / 12, 2 / 10
LY_DELAY_D, LY_DELAY_A = (3 + 100 * DELAY_D) / (18 + 100), (3 + 100 * DELAY_A) / (18 + 100)


def four_flights() -> tuple[list[dict], list[dict], list[dict]]:
    """The history, and four scored flights in the week beside one with no known result."""
    return archive(*history(),
                   listed("a", T(16, 6)),  # LY 1: its 2 of 10 cancelled; 1 of 8 that flew delayed
                   listed("b", T(17, 6), "canceled", flight_no="3"),  # LY 3: no flight before the cut
                   listed("c", T(18, 10), "landed", late=60.0, flight_no="2", direction="A"),  # LY 2: 0 of 10; 2 of 10
                   listed("d", T(19, 6), airline="W6", flight_no="900"),  # an airline with no flight before the cut
                   listed("e", T(20, 6), "vanished", flight_no="4"))  # no known result: not scored


CANCEL = {"a": (2 + 14 * LY) / (10 + 14), "b": LY, "c": (0 + 14 * LY) / (10 + 14), "d": AIRPORT}
DELAY = {"a": (1 + 14 * LY_DELAY_D) / (8 + 14), "c": (2 + 14 * LY_DELAY_A) / (10 + 14), "d": DELAY_D}


def test_the_week_is_the_last_seven_closed_israel_days(israeli_machine):
    # 21 November's flights are all closed 48 hours after 22 November 00:00 in Israel (21 November 22:00 UTC)
    assert backtest.week(board(T(23, 22))) == (date(2026, 11, 15), date(2026, 11, 21))
    assert backtest.week(board(T(23, 21, 59))) == (date(2026, 11, 14), date(2026, 11, 20))
    assert backtest.week(board(T(24, 21, 59))) == (date(2026, 11, 15), date(2026, 11, 21))
    # the last sighting, not the last download: the last snapshot seen again until 23 November 22:00
    assert backtest.week(board(T(23, 12), (T(23, 21), T(23, 22)))) == (date(2026, 11, 15), date(2026, 11, 21))
    r = backtest.run(*four_flights())
    assert (r.first_day, r.last_day) == (date(2026, 11, 15), date(2026, 11, 21))


def test_the_counts_are_cut_at_the_weeks_start(israeli_machine):
    r = backtest.run(*archive(
        *history(),
        listed("before", T(14, 21, 30), "canceled", flight_no="7"),  # 14 November 23:30 in Israel: before the start
        listed("inside", T(14, 22, 30), "canceled", flight_no="7", ahead=20),  # 15 November 00:30: in the week
        listed("scored", T(17, 6), flight_no="7")))
    # the flight before the start is in LY 7's counts (1 of 1) and LY's (3 of 21), but not yet closed as of it, so
    # not in the airport's (3 of 25); the flight inside the week is in none, and is not scored (first listed 20
    # hours ahead)
    assert (r.every.flights, r.every.cancelled) == (1, 0)
    assert r.every.expected_cancelled == approx((1 + 14 * (3 + 100 * AIRPORT) / (21 + 100)) / (1 + 14))


def test_only_the_24_hour_rows_flights_are_scored(israeli_machine):
    r = backtest.run(*archive(*history(),
                              listed("a", T(16, 6), ahead=24),  # first listed 24 hours ahead: in the row
                              listed("b", T(17, 6), flight_no="8", ahead=20)))  # 20 hours ahead: from 12 hours down
    assert (r.every.flights, r.every.expected_cancelled) == (1, approx(CANCEL["a"]))
    assert (r.no_chance, r.no_delay_chance) == (0, 0)


def test_expected_and_actual(israeli_machine):
    r = backtest.run(*four_flights())
    assert r.every == Part(flights=4, cancelled=1, expected_cancelled=approx(sum(CANCEL.values())),
                           flew=3, delayed=1, expected_delayed=approx(sum(DELAY.values())))
    # a tenth of 4, rounded up: the one rated highest, LY 1
    assert r.top == Part(1, 0, approx(CANCEL["a"]), 1, 0, approx(DELAY["a"]))
    assert r.rest == Part(3, 1, approx(CANCEL["b"] + CANCEL["c"] + CANCEL["d"]), 2, 1, approx(DELAY["c"] + DELAY["d"]))
    # by the delay chance, among the three that flew: LY 2's arrival
    assert r.top_delay == Part(1, 0, approx(CANCEL["c"]), 1, 1, approx(DELAY["c"]))
    assert r.rest_delay == Part(2, 0, approx(CANCEL["a"] + CANCEL["d"]), 2, 0, approx(DELAY["a"] + DELAY["d"]))
    assert r.flags == (HALF, RANKED)  # 0.46 expected of 1; the top tenth none of 1, the rest 1 of 3
    assert (r.no_chance, r.no_delay_chance) == (0, 0)


def test_the_top_tenth_is_a_ceiling(israeli_machine):
    # LY 1 rated highest; ten numbers new to LY tied at LY's rate, the first by the flight key (the earliest) cancelled
    ties = [listed(f"t{i}", T(15, 8) + i * 12 * H, "canceled" if i == 0 else "departed", flight_no=str(100 + i))
            for i in range(10)]
    r = backtest.run(*archive(*history(), listed("a", T(15, 6)), *ties))
    assert (r.top.flights, r.top.cancelled, r.rest.flights, r.rest.cancelled) == (2, 1, 9, 0)
    assert r.top.expected_cancelled == approx(CANCEL["a"] + LY)
    assert (r.top_delay.flew, r.rest_delay.flew) == (1, 9)  # a tenth of the 10 that flew: LY 1
    assert r.top_delay.expected_delayed == approx(DELAY["a"])


def test_each_flag():
    assert backtest.FLAGS == ("expected cancelled more than double the actual",
                              "expected cancelled under half the actual",
                              "the top tenth cancelled no more often than the rest")

    def part(flights: int, cancelled: int, expected: float) -> Part:
        return Part(flights, cancelled, expected, flights - cancelled, 0, 0.0)

    top, rest = part(10, 2, 2.0), part(90, 8, 8.0)  # 20% against 8.9%: the top tenth cancelled more often
    assert backtest.flagged(part(100, 10, 10.0), top, rest) == ()
    assert backtest.flagged(part(100, 100, 201.0), top, rest) == (DOUBLE,)  # 2.01 times
    assert backtest.flagged(part(100, 100, 200.0), top, rest) == ()  # 2.00 times
    assert backtest.flagged(part(100, 100, 49.0), top, rest) == (HALF,)
    assert backtest.flagged(part(100, 100, 50.0), top, rest) == ()  # half
    even = part(10, 1, 1.0), part(90, 9, 9.0)  # 10% each
    assert backtest.flagged(part(100, 10, 10.0), *even) == (RANKED,)
    assert backtest.flagged(part(100, 9, 9.0), part(10, 0, 1.0), rest) == (RANKED,)  # less often
    assert backtest.flagged(part(100, 10, 30.0), *even) == (DOUBLE, RANKED)  # in FLAGS' order


def test_a_flight_with_no_chance_is_not_scored(israeli_machine):
    # before the cut, LY 1's departures flew (one an hour late) and LY 2's arrivals were all cancelled: no arrival flew
    before = [*(listed(f"d{d}", T(d, 6), late=60.0 if d == 3 else 0.0) for d in range(1, 6)),
              *(listed(f"a{d}", T(d, 10), "canceled", flight_no="2", direction="A") for d in (1, 2))]
    week = [listed("x", T(16, 6)), listed("y", T(17, 10), "landed", flight_no="2", direction="A"),
            listed("z", T(18, 10), "canceled", flight_no="2", direction="A")]
    r = backtest.run(*archive(*before, *week))
    # the airport 2 of 7, LY 2 of 7; LY 1 0 of 5, LY 2 2 of 2; delays: departures, LY and LY 1 each 1 of 5
    ly = (2 + 100 * 2 / 7) / (7 + 100)
    assert r.every == Part(3, 1, approx((0 + 14 * ly) / 19 + 2 * (2 + 14 * ly) / 16), 1, 0, approx(1 / 5))
    assert (r.no_chance, r.no_delay_chance) == (0, 1)  # the arrival that landed has no delay chance
    assert "Not scored, with no chance worked out: 0 for cancelling, 1 of those that flew for a delay" in (
        backtest.text(r))
    # no flight closed before the cut: no chance at all, and nothing scored
    bare = backtest.run(*archive(*week))
    assert bare.every == bare.top == bare.rest == bare.top_delay == bare.rest_delay == Part(0, 0, 0.0, 0, 0, 0.0)
    assert (bare.no_chance, bare.no_delay_chance) == (3, 2)  # of the two that flew, neither has a delay chance
    assert bare.flags == (RANKED,)  # none of 0 in the top tenth is no more often than none of 0


TEXT = """\
The back-test of the blend, on the week of 2026-11-15 to 2026-11-21 (Israel days)
Scored: the week's closed flights with a known result in the 24-hour row, each by its lead number.
The counts are cut at the week's start.
Not scored, with no chance worked out: 0 for cancelling, 0 of those that flew for a delay of an hour or more.

Cancelled: actual against expected
  every flight scored: 1 of 4, expected 0.46
  the top tenth by the chance of cancelling: 0 of 1, expected 0.15
  the rest: 1 of 3, expected 0.30
Delayed an hour or more: actual of those that flew, against expected
  every flight that flew: 1 of 3, expected 0.39
  the top tenth by the chance of a delay: 1 of 1, expected 0.20
  the rest: 0 of 2, expected 0.19

Flagged: expected cancelled under half the actual
Flagged: the top tenth cancelled no more often than the rest
"""


def test_the_report_text_and_exit_codes(israeli_machine, tmp_path, monkeypatch, capsys):
    report = backtest.run(*four_flights())
    assert backtest.text(report) == TEXT
    assert backtest.text(replace(report, flags=())).endswith("the rest: 0 of 2, expected 0.19\n\nNot flagged.\n")
    folder, out = tmp_path / "model-2026-11-23", tmp_path / "backtest"
    folder.mkdir()
    (folder / "flights.parquet").write_bytes(b"")  # load is replaced: the folder only has to hold a model

    def load(model_dir: Path):
        assert model_dir == folder
        return four_flights()

    monkeypatch.setattr(backtest, "load", load)
    args = ["--model", str(folder), "--out", str(out)]
    assert backtest.main(args) == 1  # flagged
    written = out / "model-2026-11-23" / "report.txt"
    assert written.read_bytes() == TEXT.encode()
    assert capsys.readouterr().out == TEXT
    # two more runs, under two hash seeds, write the same bytes
    for seed in ("0", "1"):
        code = ("import sys, test_backtest as t; from timeline import backtest; "
                "backtest.load = lambda model_dir: t.four_flights(); "
                f"sys.exit(backtest.main(['--model', {str(folder)!r}, '--out', {str(tmp_path / seed)!r}]))")
        env = dict(os.environ, PYTHONHASHSEED=seed, TZ="Asia/Jerusalem",
                   PYTHONPATH=os.pathsep.join(["src", "tests"]))
        done = subprocess.run([sys.executable, "-c", code], env=env, cwd=Path(__file__).parent.parent,
                              capture_output=True, text=True)
        assert done.returncode == 1, done.stderr
        assert (tmp_path / seed / "model-2026-11-23" / "report.txt").read_bytes() == TEXT.encode()
    monkeypatch.setattr(backtest, "run", lambda *model: replace(report, flags=()))
    assert backtest.main(args) == 0  # not flagged
    assert written.read_text(encoding="utf-8").endswith("Not flagged.\n")
    capsys.readouterr()
    empty = tmp_path / "model-none"
    empty.mkdir()
    assert backtest.main(["--model", str(empty), "--out", str(out)]) == 2  # no model
    assert "no model" in capsys.readouterr().err
    assert not (out / "model-none").exists()
