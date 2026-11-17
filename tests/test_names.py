"""The spoken names (src/timeline/names.py): the name a traveller says aloud for each airline, and the list of
airlines that still need one (docs/will-it-fly-plan.md, Question 5, answered 2026-11-17: every airline some flight
is grouped under, and every airline with 100 or more counted flights). The archive is in rows
(tests/counting_helpers.py). Most are closed at LAST; LY's and the hour-700 slot are not, and the count does not
mind."""
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from counting_helpers import T, board, number
from timeline import blend, counting, names

LAST = T(20, 22)
PUBLISHED = {"AA": "AIRLINE A", "BB": "AIRLINE B", "DD": "AIRLINE D", "EE": "AIRLINE E", "LY": "EL AL ISRAEL AIRLINES"}


def rows(airline: str, count: int, base: int = 100, at: int = 0) -> list[dict]:
    """`count` numbers of `airline` that departed on time, numbered base, base + 1, ... (their flight IDs too), one an
    hour from `at` hours after 1 November, 00:00 UTC; a row is closed at LAST only when scheduled 48 hours or more
    before it. Rows of two airlines at the same hour are one slot, and the lower number groups it."""
    return [number(f"{airline}-{base + i}", T(1, 0) + timedelta(hours=at + i), airline=airline,
                   flight_no=str(base + i)) | {"airline_name": PUBLISHED[airline], "est_minus_sched_min": 0} for i in range(count)]


def archive():
    """AA groups 100 flights; BB is sold on 99 of them and DD on 100 (never grouped, 99 and 100 flights), EE on 3;
    LY groups 3 flights on its own. One more slot, AA 900 and BB 9000, has no known result: it counts for neither."""
    table = (rows("AA", 100) + rows("BB", 99, base=1000) + rows("DD", 100, base=2000) + rows("EE", 3, base=3000)
             + rows("LY", 3, at=500)
             + [r | {"outcome": "left"} for r in rows("AA", 1, base=900, at=700) + rows("BB", 1, base=9000, at=700)])
    assert len({r["flight_id"] for r in table}) == len(table)  # a flight ID names one row
    snaps = board(LAST)
    return blend.records(table, [], snaps), table, counting.flights(table, counting.last_sighting(snaps))


def test_spoken_names():
    assert {c: names.SPOKEN_NAMES[c] for c in ("LH", "LO", "LY")} == {"LH": "Lufthansa", "LO": "LOT", "LY": "El Al"}
    assert all(v and v == v.strip() and "  " not in v for v in names.SPOKEN_NAMES.values())
    assert names.spoken("LY") == "El Al"
    assert names.spoken("ZZ") is None


def test_names_needed():
    records, table, flights_ = archive()
    assert sorted(records.airlines) == ["AA", "LY"]  # BB, DD and EE group no flight
    assert names.needed(records, table, flights_) == [
        ("AA", "AIRLINE A", 100, "100 or more flights and a grouping airline"),
        ("DD", "AIRLINE D", 100, "100 or more flights"),  # 99 (BB) is not enough, 100 is
        ("LY", "EL AL ISRAEL AIRLINES", 3, "a grouping airline"),  # 3 flights, but flights are grouped under it
    ]  # EE: 3 flights, none grouped under it: not needed


def test_main_exit_codes(monkeypatch, capsys, tmp_path):
    empty = tmp_path / "model-none"
    empty.mkdir()
    assert names.main(["--model", str(empty)]) == 2  # no model
    assert "no model under" in capsys.readouterr().err
    (empty / "flights.parquet").write_bytes(b"")
    monkeypatch.setattr(names, "load", lambda folder: (archive()[1], [], board(LAST)))
    assert names.main(["--model", str(empty)]) == 1  # AA and DD have no spoken name
    out = capsys.readouterr().out
    # the header says what the count counts, and that it is not the pages' figure
    assert out.splitlines()[0] == ("code  published name  flights with a known result, closed or not, counted for "
                                   "every airline with a number on the flight (not the figure on the pages)  why  "
                                   "spoken name")
    assert "AA  AIRLINE A  100 flights  100 or more flights and a grouping airline  missing" in out
    assert "LY  EL AL ISRAEL AIRLINES  3 flights  a grouping airline  El Al" in out
    monkeypatch.setattr(names, "SPOKEN_NAMES", {"AA": "A", "DD": "D", "LY": "El Al"})
    assert names.main(["--model", str(empty)]) == 0  # every one has a name
    assert "missing" not in capsys.readouterr().out


def test_main_runs_as_a_module(tmp_path):
    env = dict(os.environ, PYTHONPATH="src", PYTHONHASHSEED="0")
    done = subprocess.run([sys.executable, "-m", "timeline.names", "--model", str(tmp_path)], env=env,
                          cwd=Path(__file__).parent.parent, capture_output=True, text=True)
    assert done.returncode == 2 and "no model under" in done.stderr


def test_main_counts_read_aloud(monkeypatch, capsys, tmp_path):
    (tmp_path / "flights.parquet").write_bytes(b"")
    monkeypatch.setattr(names, "load", lambda folder: (archive()[1], [], board(LAST)))
    monkeypatch.setattr(names, "needed", lambda *a: [("AA", "A", 1, "a grouping airline"),
                                                     ("DD", "D", 1234, "100 or more flights")])
    names.main(["--model", str(tmp_path)])
    out = capsys.readouterr().out
    assert "AA  A  1 flight  a grouping airline" in out
    assert "DD  D  1,234 flights  100 or more flights" in out
