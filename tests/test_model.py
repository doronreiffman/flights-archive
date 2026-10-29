"""Rules R1-R8 of docs/data-model.md, each on a tiny synthetic world of snapshots."""
import json
from pathlib import Path

import duckdb
import pytest

from model import build, report, rules
from model_helpers import at, build as run, one, q, row, write_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw(tmp_path):
    return tmp_path / "raw"


# R1 time conversion ---------------------------------------------------------

def test_winter_and_summer_offsets(raw):
    write_snapshot(raw, at(6), [row(flight_no="1", sched_local="2026-10-29T12:00:00"),
                                row(flight_no="2", sched_local="2026-07-01T12:00:00")])
    con = run(raw)
    got = {r["flight_no"]: r for r in q(con, "SELECT * FROM rows")}
    assert str(got["1"]["sched_utc"]) == "2026-10-29 10:00:00"
    assert str(got["2"]["sched_utc"]) == "2026-07-01 09:00:00"
    assert not any(r["sched_ambiguous"] or r["sched_nonexistent"] for r in got.values())


def test_fall_back_hour_takes_earlier_instant_and_is_flagged(raw):
    write_snapshot(raw, at(6), [row(flight_no="1", sched_local="2026-10-25T01:30:00"),
                                row(flight_no="2", sched_local="2026-10-25T00:30:00"),
                                row(flight_no="3", sched_local="2026-10-25T02:30:00")])
    got = {r["flight_no"]: r for r in q(run(raw), "SELECT * FROM rows")}
    assert str(got["1"]["sched_utc"]) == "2026-10-24 22:30:00" and got["1"]["sched_ambiguous"]
    assert str(got["2"]["sched_utc"]) == "2026-10-24 21:30:00" and not got["2"]["sched_ambiguous"]
    assert str(got["3"]["sched_utc"]) == "2026-10-25 00:30:00" and not got["3"]["sched_ambiguous"]
    assert got["1"]["est_ambiguous"]  # est defaulted to the same wall-clock


def test_spring_gap_shifts_forward_and_is_flagged(raw):
    write_snapshot(raw, at(6), [row(flight_no="1", sched_local="2026-03-27T02:30:00"),
                                row(flight_no="2", sched_local="2026-03-27T01:30:00"),
                                row(flight_no="3", sched_local="2026-03-27T03:30:00")])
    got = {r["flight_no"]: r for r in q(run(raw), "SELECT * FROM rows")}
    assert str(got["1"]["sched_utc"]) == "2026-03-27 00:30:00" and got["1"]["sched_nonexistent"]
    assert str(got["2"]["sched_utc"]) == "2026-03-26 23:30:00" and not got["2"]["sched_nonexistent"]
    assert str(got["3"]["sched_utc"]) == "2026-03-27 00:30:00" and not got["3"]["sched_nonexistent"]


def test_empty_or_bad_times_are_null_and_counted(raw):
    write_snapshot(raw, at(6), [row(flight_no="1", est_local=""), row(flight_no="2", sched_local="garbage", est_local="2026-10-28T10:00:00")])
    con = run(raw)
    got = {r["flight_no"]: r for r in q(con, "SELECT * FROM rows")}
    assert got["1"]["est_utc"] is None and got["1"]["est_ambiguous"] is None
    assert got["2"]["sched_utc"] is None
    snap = one(con, "SELECT * FROM snapshots")
    assert (snap["missing_est"], snap["unparsed_sched"]) == (1, 1)


# R2 duplicates --------------------------------------------------------------

def test_exact_duplicates_collapse_and_are_counted(raw):
    write_snapshot(raw, at(6), [row(), row()])
    con = run(raw)
    snap = one(con, "SELECT * FROM snapshots")
    assert (snap["rows_raw"], snap["rows"], snap["duplicate_rows"], snap["key_conflicts"]) == (2, 1, 1, 0)
    assert one(con, "SELECT count(*) n FROM observations")["n"] == 1
    assert one(con, "SELECT count(*) n FROM flights")["n"] == 1


def test_same_board_stored_twice_counts_once(raw):
    write_snapshot(raw, at(6), [row()], sha="a" * 12)
    write_snapshot(raw, at(6, 2), [row()], sha="a" * 12)
    write_snapshot(raw, at(6, 4), [row()], sha="a" * 12)
    write_snapshot(raw, at(6, 15), [row(status="DELAYED")], sha="b" * 12)
    con = run(raw)
    snaps = q(con, "SELECT * FROM snapshots ORDER BY snap_rn")
    assert [(s["snap_rn"], s["identical_repeats"], s["gap_before_s"]) for s in snaps] == [(1, 2, None), (2, 0, 900)]
    f = one(con, "SELECT * FROM flights")
    assert (f["snapshots_seen"], f["observations"], f["last_seen_at"]) == (2, 2, at(6, 15))


def test_incomplete_multi_page_snapshot_is_dropped(raw):
    write_snapshot(raw, at(6), [row(flight_no=str(n)) for n in range(5)], pages=2)
    sid = write_snapshot(raw, at(6, 15), [row(flight_no=str(n)) for n in range(5)], pages=2)
    (raw / f"date=2026-10-27/{sid.split('/')[1]}" / "page-001.json.gz").unlink()  # the store was interrupted
    write_snapshot(raw, at(6, 30), [row(flight_no=str(n)) for n in range(5)], pages=2)
    con = run(raw)
    assert [s["snap_rn"] for s in q(con, "SELECT * FROM snapshots ORDER BY snap_rn")] == [1, 2]
    assert one(con, "SELECT count(*) n FROM snapshot_runs WHERE incomplete")["n"] == 1
    assert one(con, "SELECT max(snapshots_seen) n FROM flights")["n"] == 2
    out = raw.parent / "model"
    assert build.main(["--raw", str(raw), "--out", str(out)]) == 0
    assert "Snapshots dropped: 1 incomplete" in report.report(out)


def test_snapshot_without_a_declared_total_is_refused(raw):
    write_snapshot(raw, at(6), [row()])
    path = next(raw.rglob("page-000.json.gz"))
    import gzip, json
    doc = json.loads(gzip.decompress(path.read_bytes()))
    del doc["result"]["total"]
    path.write_bytes(gzip.compress(json.dumps(doc).encode()))
    with pytest.raises(ValueError, match="no result.total"):
        run(raw)


def test_key_conflict_keeps_lowest_id_and_is_counted(raw):
    write_snapshot(raw, at(6), [row(status="DELAYED", _id=7), row(status="ON TIME", _id=3)])
    con = run(raw)
    snap = one(con, "SELECT * FROM snapshots")
    assert (snap["rows"], snap["duplicate_rows"], snap["key_conflicts"]) == (1, 0, 1)
    assert one(con, "SELECT status FROM rows")["status"] == "ON TIME"


# R3 change detection --------------------------------------------------------

def test_unchanged_appearances_emit_no_observation(raw):
    for t in (at(6), at(6, 15), at(6, 30)):
        write_snapshot(raw, t, [row()])
    con = run(raw)
    assert [o["change_kind"] for o in q(con, "SELECT * FROM observations")] == ["first"]
    f = one(con, "SELECT * FROM flights")
    assert (f["snapshots_seen"], f["observations"]) == (3, 1)
    assert f["first_seen_at"] == at(6) and f["last_seen_at"] == at(6, 30)


def test_changes_emit_observation_naming_changed_fields(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(est_local="2026-10-28T10:30:00", status="DELAYED", status_he="מאחרת")])
    write_snapshot(raw, at(6, 30), [row(est_local="2026-10-28T10:30:00", status="DELAYED", status_he="מאחרת", counters="6-9")])
    obs = q(run(raw), "SELECT * FROM observations ORDER BY snap_rn")
    assert [o["change_kind"] for o in obs] == ["first", "change", "change"]
    assert obs[0]["changed_fields"] == []
    assert obs[1]["changed_fields"] == ["est_local", "status", "status_he"]
    assert obs[1]["prev_observed_at"] == at(6) and obs[2]["prev_observed_at"] == at(6, 15)
    assert obs[2]["changed_fields"] == ["counters"]
    assert str(obs[1]["est_utc"]) == "2026-10-28 08:30:00"


# R4 retime linking ----------------------------------------------------------

def test_retime_links_new_time_in_next_snapshot(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(sched_local="2026-10-28T13:00:00")])
    con = run(raw)
    f = one(con, "SELECT * FROM flights")
    assert f["retimes"] == 1 and len(f["key_ids"]) == 2
    assert str(f["sched_local_first"]) == "2026-10-28 10:00:00" and str(f["sched_local_final"]) == "2026-10-28 13:00:00"
    obs = q(con, "SELECT * FROM observations ORDER BY snap_rn")
    assert [o["change_kind"] for o in obs] == ["first", "retime"]
    assert "sched_local" in obs[1]["changed_fields"]
    assert obs[1]["flight_id"] == obs[0]["flight_id"] and obs[1]["key_id"] != obs[0]["key_id"]


@pytest.mark.parametrize("new_time, flights", [("2026-10-28T22:00:00", 1), ("2026-10-28T22:01:00", 2),
                                               ("2026-10-27T22:00:00", 1), ("2026-10-29T10:00:00", 2),
                                               ("2026-10-27T10:00:00", 2)])
def test_retime_window_is_twelve_hours(raw, new_time, flights):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(sched_local=new_time)])
    assert one(run(raw), "SELECT count(*) n FROM flights")["n"] == flights


@pytest.mark.parametrize("old_status, new_status, flights", [
    ("DEPARTED", "ON TIME", 2), ("CANCELED", "ON TIME", 2), ("LANDED", "NOT FINAL", 2),
    ("ON TIME", "DEPARTED", 2), ("ON TIME", "ON TIME", 1), ("DELAYED", "NOT FINAL", 1)])
def test_retime_needs_non_terminal_status_on_both_sides(raw, old_status, new_status, flights):
    write_snapshot(raw, at(6), [row(status=old_status)])
    write_snapshot(raw, at(6, 15), [row(sched_local="2026-10-28T13:00:00", status=new_status)])
    assert one(run(raw), "SELECT count(*) n FROM flights")["n"] == flights


def test_retime_needs_the_very_next_snapshot(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(flight_no="999")])
    write_snapshot(raw, at(6, 30), [row(flight_no="999"), row(sched_local="2026-10-28T13:00:00")])
    assert one(run(raw), "SELECT count(*) n FROM flights WHERE flight_no = '001'")["n"] == 2


def test_retime_does_not_cross_a_collection_gap(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(8), [row(sched_local="2026-10-28T13:00:00")])
    con = run(raw)
    assert one(con, "SELECT count(*) n FROM flights")["n"] == 2
    assert one(con, "SELECT outcome FROM flights WHERE sched_local_final = '2026-10-28 10:00:00'")["outcome"] == "gap"


def test_retime_tie_stays_unlinked_and_nearest_wins(raw):
    write_snapshot(raw, at(6), [row(flight_no="1"), row(flight_no="2")])
    write_snapshot(raw, at(6, 15), [row(flight_no="1", sched_local="2026-10-28T08:00:00"),
                                    row(flight_no="1", sched_local="2026-10-28T12:00:00"),
                                    row(flight_no="2", sched_local="2026-10-28T09:00:00"),
                                    row(flight_no="2", sched_local="2026-10-28T13:00:00")])
    con = run(raw)
    assert one(con, "SELECT count(*) n FROM flights WHERE flight_no = '1'")["n"] == 3
    two = q(con, "SELECT retimes, sched_local_final::VARCHAR t FROM flights WHERE flight_no = '2' ORDER BY t")
    assert two == [{"retimes": 1, "t": "2026-10-28 09:00:00"}, {"retimes": 0, "t": "2026-10-28 13:00:00"}]


def test_retime_after_the_old_key_was_seen_several_times(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row()])
    write_snapshot(raw, at(6, 30), [row(sched_local="2026-10-28T13:00:00")])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["retimes"] == 1 and f["snapshots_seen"] == 3


def test_old_key_is_judged_by_its_last_status(raw):
    write_snapshot(raw, at(6), [row(status="ON TIME")])
    write_snapshot(raw, at(6, 15), [row(status="DEPARTED")])
    write_snapshot(raw, at(6, 30), [row(sched_local="2026-10-28T13:00:00")])
    assert one(run(raw), "SELECT count(*) n FROM flights")["n"] == 2


def test_two_old_keys_one_new_key_links_only_the_nearest(raw):
    write_snapshot(raw, at(6), [row(sched_local="2026-10-28T08:00:00"), row(sched_local="2026-10-28T10:00:00")])
    write_snapshot(raw, at(6, 15), [row(sched_local="2026-10-28T11:00:00")])
    con = run(raw)
    got = {str(f["sched_local_first"]): f for f in q(con, "SELECT * FROM flights")}
    assert set(got) == {"2026-10-28 08:00:00", "2026-10-28 10:00:00"}
    assert got["2026-10-28 10:00:00"]["retimes"] == 1 and got["2026-10-28 08:00:00"]["retimes"] == 0
    assert one(con, "SELECT count(*) n FROM keymap")["n"] == 3


def test_retime_chain_of_three(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(sched_local="2026-10-28T11:00:00")])
    write_snapshot(raw, at(6, 30), [row(sched_local="2026-10-28T12:00:00")])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["retimes"] == 2 and str(f["sched_local_final"]) == "2026-10-28 12:00:00"


# R5/R6 codeshares -----------------------------------------------------------

def test_codeshare_group_and_operator_guess(raw):
    write_snapshot(raw, at(6), [row(airline="EY", flight_no="607", counters="12-21"),
                                row(airline="LY", flight_no="9614", counters="12-21"),
                                row(airline="W4", flight_no="6406", airport="MXP", counters="318-327")])
    got = {r["airline"]: r for r in q(run(raw), "SELECT * FROM flights")}
    assert got["EY"]["codeshare_group_id"] == got["LY"]["codeshare_group_id"] != got["W4"]["codeshare_group_id"]
    assert got["LY"]["codeshare_size"] == 2 and got["W4"]["codeshare_size"] == 1
    assert (got["LY"]["operating_airline"], got["LY"]["operating_flight_no"], got["LY"]["operating_is_guess"]) == ("EY", "607", True)
    assert (got["W4"]["operating_airline"], got["W4"]["operating_flight_no"], got["W4"]["operating_is_guess"]) == ("W4", "6406", False)
    assert got["LY"]["codeshare_basis"] == "counters"


def test_estimated_time_splits_same_slot_flights(raw):
    write_snapshot(raw, at(6), [row(airline="EY", flight_no="596", est_local="2026-10-28T10:18:00", counters="12-21"),
                                row(airline="LY", flight_no="9606", est_local="2026-10-28T10:18:00", counters="12-21"),
                                row(airline="EY", flight_no="610", est_local="2026-10-28T11:24:00", counters="12-21"),
                                row(airline="LY", flight_no="9613", est_local="2026-10-28T11:24:00", counters="12-21")])
    got = {r["flight_no"]: r for r in q(run(raw), "SELECT * FROM flights")}
    assert got["596"]["codeshare_group_id"] == got["9606"]["codeshare_group_id"]
    assert got["610"]["codeshare_group_id"] == got["9613"]["codeshare_group_id"]
    assert got["596"]["codeshare_group_id"] != got["610"]["codeshare_group_id"]
    assert all(r["codeshare_size"] == 2 for r in got.values())


def test_terminal_splits_a_codeshare_group(raw):
    write_snapshot(raw, at(6), [row(airline="EY", flight_no="607", terminal=3), row(airline="LY", flight_no="9614", terminal=1)])
    assert {r["codeshare_size"] for r in q(run(raw), "SELECT * FROM flights")} == {1}


def test_operator_tie_breaks_on_airline_code(raw):
    write_snapshot(raw, at(6), [row(airline="BB", flight_no="607"), row(airline="AA", flight_no="607")])
    assert {r["operating_airline"] for r in q(run(raw), "SELECT * FROM flights")} == {"AA"}


def test_arrivals_group_on_time_only(raw):
    write_snapshot(raw, at(6), [row(airline="EY", flight_no="607", direction="A", counters="", zone="", status="NOT FINAL"),
                                row(airline="LY", flight_no="9614", direction="A", counters="", zone="", status="NOT FINAL")])
    got = q(run(raw), "SELECT * FROM flights")
    assert {r["codeshare_basis"] for r in got} == {"time-only"} and {r["codeshare_size"] for r in got} == {2}


@pytest.mark.parametrize("numbers, winner", [(("0115A", "9614"), "0115A"), (("008", "7431"), "008"), (("300", "299"), "299"), (("1000", "999"), "999")])
def test_operator_guess_uses_numeric_part(raw, numbers, winner):
    write_snapshot(raw, at(6), [row(airline="AA", flight_no=numbers[0]), row(airline="BB", flight_no=numbers[1])])
    assert {r["operating_flight_no"] for r in q(run(raw), "SELECT * FROM flights")} == {winner}


def test_codeshare_group_is_taken_at_last_appearance(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(), row(airline="W4", flight_no="6406")])
    got = q(run(raw), "SELECT * FROM flights")
    assert {r["codeshare_size"] for r in got} == {2} and len({r["codeshare_group_id"] for r in got}) == 1


# R7 outcomes ----------------------------------------------------------------

def test_outcomes(raw):
    past, future = "2026-10-27T07:00:00", "2026-10-28T10:00:00"   # 05:00Z and 08:00Z
    write_snapshot(raw, at(6), [
        row(flight_no="1", status="DEPARTED"),
        row(flight_no="2", direction="A", status="LANDED", counters=""),
        row(flight_no="3", status="CANCELED"),
        row(flight_no="4", status="ON TIME"),
        row(flight_no="5", status="ON TIME", sched_local=future),
        row(flight_no="6", direction="A", status="NOT FINAL", sched_local=past, counters=""),
    ])
    write_snapshot(raw, at(6, 15), [row(flight_no="4", status="ON TIME")])
    got = {r["flight_no"]: r["outcome"] for r in q(run(raw), "SELECT * FROM flights")}
    assert got == {"1": "departed", "2": "landed", "3": "canceled", "4": "open", "5": "vanished", "6": "dropped"}


def test_vanish_horizon_is_one_hour_past_the_last_appearance(raw):
    # last seen 06:00Z; 08:30 Israel = 06:30Z (dropped), 09:30 Israel = 07:30Z (vanished)
    write_snapshot(raw, at(6), [row(flight_no="1", sched_local="2026-10-27T08:30:00"),
                                row(flight_no="2", sched_local="2026-10-27T09:30:00")])
    write_snapshot(raw, at(6, 15), [row(flight_no="3")])
    got = {r["flight_no"]: r["outcome"] for r in q(run(raw), "SELECT * FROM flights")}
    assert got == {"1": "dropped", "2": "vanished", "3": "open"}


def test_gap_is_measured_from_the_last_appearance(raw):
    for t in (at(6), at(6, 30), at(7)):
        write_snapshot(raw, t, [row()])
    write_snapshot(raw, at(7, 30), [row(flight_no="other")])
    assert one(run(raw), "SELECT outcome FROM flights WHERE flight_no = '001'")["outcome"] == "vanished"


def test_gap_outcome_only_when_the_next_snapshot_is_late(raw):
    write_snapshot(raw, at(6), [row(flight_no="1"), row(flight_no="2", status="DEPARTED")])
    write_snapshot(raw, at(8), [row(flight_no="3")])
    got = {r["flight_no"]: r["outcome"] for r in q(run(raw), "SELECT * FROM flights")}
    assert got == {"1": "gap", "2": "departed", "3": "open"}


# R8 cancellations -----------------------------------------------------------

def test_cancellation_lead_time_is_bracketed(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 30), [row()])
    write_snapshot(raw, at(7), [row(status="CANCELED", status_he="בוטלה")])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["canceled_first_seen_at"] == at(7) and f["cancel_announced_after"] == at(6, 30)
    assert f["cancel_lead_min"] == 25 * 60 and f["cancel_lead_max_min"] == 25 * 60 + 30
    assert (f["canceled_at_first_sight"], f["uncanceled"], f["outcome"], f["final_status"]) == (False, False, "canceled", "CANCELED")


def test_canceled_at_first_sight_is_censored(raw):
    write_snapshot(raw, at(6), [row(status="CANCELED")])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["canceled_at_first_sight"] and f["cancel_announced_after"] is None and f["cancel_lead_max_min"] is None
    assert f["cancel_lead_min"] == 26 * 60


def test_cancellation_across_a_collection_hole_is_censored(raw):
    write_snapshot(raw, at(6), [row(flight_no="1"), row(flight_no="2")])
    write_snapshot(raw, at(6, 30), [row(flight_no="1"), row(flight_no="2", status="CANCELED")])
    write_snapshot(raw, at(14), [row(flight_no="1", status="CANCELED"), row(flight_no="2", status="CANCELED")])
    got = {f["flight_no"]: f for f in q(run(raw), "SELECT * FROM flights")}
    assert got["1"]["cancel_lead_censored"] and got["1"]["cancel_bracket_min"] == 450
    assert not got["2"]["cancel_lead_censored"] and got["2"]["cancel_bracket_min"] == 30
    assert not got["2"]["canceled_at_first_sight"]


def test_never_cancelled_flight_has_null_cancel_columns(raw):
    write_snapshot(raw, at(6), [row()])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["cancel_lead_censored"] is None and f["cancel_lead_min"] is None and f["cancel_bracket_min"] is None


def test_uncanceled_flight_keeps_its_cancellation_record(raw):
    write_snapshot(raw, at(6), [row(status="CANCELED")])
    write_snapshot(raw, at(6, 15), [row(status="ON TIME")])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["uncanceled"] and f["canceled_first_seen_at"] == at(6)
    assert (f["final_status"], f["outcome"]) == ("ON TIME", "open")


# Whole pipeline -------------------------------------------------------------

def test_real_fixture_rows_build(raw):
    records = json.loads((FIXTURES / "records.json").read_text(encoding="utf-8"))
    write_snapshot(raw, at(9, 9), records)
    con = run(raw)
    keys = {(r["CHOPER"], r["CHFLTN"], r["CHAORD"], r["CHLOC1"], r["CHSTOL"]) for r in records}
    assert one(con, "SELECT count(*) n FROM flights")["n"] == len(keys)
    assert one(con, "SELECT rows FROM snapshots")["rows"] == len(records)
    ey = one(con, "SELECT * FROM flights WHERE airline = 'EY' AND flight_no = '607'")
    ly = one(con, "SELECT * FROM flights WHERE airline = 'LY' AND flight_no = '9614'")
    assert ey["codeshare_group_id"] == ly["codeshare_group_id"] and ly["operating_flight_no"] == "607"
    assert str(ey["sched_utc_final"]) == "2026-10-26 08:35:00" and ey["outcome"] == "landed"
    assert all(o["change_kind"] == "first" for o in q(con, "SELECT * FROM observations"))


def test_null_estimate_in_the_last_observation_is_kept(raw):
    write_snapshot(raw, at(6), [row(est_local="2026-10-28T10:30:00")])
    write_snapshot(raw, at(6, 15), [row(est_local="")])
    f = one(run(raw), "SELECT * FROM flights")
    assert f["est_local_final"] is None and f["est_utc_final"] is None and f["est_minus_sched_min"] is None


def test_two_page_snapshot_counts_as_one(raw):
    write_snapshot(raw, at(6), [row(flight_no=str(n)) for n in range(5)], pages=2)
    con = run(raw)
    snap = one(con, "SELECT * FROM snapshots")
    assert (snap["pages"], snap["rows"]) == (2, 5)
    assert one(con, "SELECT count(*) n FROM flights")["n"] == 5


def test_flight_with_a_hole_in_its_appearances(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row(flight_no="other")])
    write_snapshot(raw, at(6, 30), [row(status="DELAYED")])
    con = run(raw)
    f = one(con, "SELECT * FROM flights WHERE flight_no = '001'")
    assert (f["snapshots_seen"], f["observations"], f["outcome"]) == (2, 2, "open")
    obs = q(con, "SELECT * FROM observations WHERE flight_no = '001' ORDER BY snap_rn")
    assert obs[1]["prev_observed_at"] == at(6) and obs[1]["changed_fields"] == ["status"]


def test_snapshot_gap_is_recorded(raw):
    write_snapshot(raw, at(6), [row()])
    write_snapshot(raw, at(6, 15), [row()])
    gaps = [s["gap_before_s"] for s in q(run(raw), "SELECT * FROM snapshots ORDER BY snap_rn")]
    assert gaps == [None, 900]


def test_unexpected_file_layout_raises(raw):
    write_snapshot(raw, at(6), [row()])
    stray = raw / "stray.json.gz"
    stray.write_bytes(next(raw.rglob("page-000.json.gz")).read_bytes())
    with pytest.raises(ValueError, match="path"):
        run(raw)


def test_cli_writes_parquet(raw, tmp_path, capsys):
    write_snapshot(raw, at(6), [row(), row(flight_no="2")])
    out = tmp_path / "model"
    assert build.main(["--raw", str(raw), "--out", str(out)]) == 0
    assert "flights: 2 rows" in capsys.readouterr().out
    n = duckdb.sql(f"SELECT count(*) FROM '{out / 'flights.parquet'}'").fetchone()[0]
    assert n == 2 and (out / "observations.parquet").exists() and (out / "snapshots.parquet").exists()


def test_cli_without_snapshots_fails(tmp_path):
    assert build.main(["--raw", str(tmp_path), "--out", str(tmp_path / "m")]) == 2


def test_report_summarises_the_model(raw, tmp_path, capsys):
    write_snapshot(raw, at(6), [row(), row(flight_no="2", status="CANCELED"), row(flight_no="3", airline="EY", counters="12-21")])
    write_snapshot(raw, at(6, 15), [row(sched_local="2026-10-28T13:00:00"), row(flight_no="2", status="CANCELED"),
                                    row(flight_no="3", airline="EY", counters="12-21"), row(flight_no="9614", counters="12-21")])
    out = tmp_path / "model"
    assert build.main(["--raw", str(raw), "--out", str(out)]) == 0
    assert report.main(["--model", str(out)]) == 0
    text = capsys.readouterr().out
    assert "## Coverage" in text and "| 2 |" in text and "Snapshots dropped: 0 incomplete" in text
    assert "Flights with a retime link: 1" in text
    assert "Flights seen CANCELED: 1. Already cancelled when first seen: 1." in text
    assert "Source: Israel Airports Authority" in text
    assert "| counters | 2 | 2 |" in text
    assert report.main(["--model", str(tmp_path / "nope")]) == 2


def test_many_snapshot_files_build_within_a_small_memory_limit(raw):
    """DuckDB reserves a read buffer per gzipped file sized from maximum_object_size. At 256 MB the 17 real
    snapshots of 2026-10-29 exhausted the default limit on an 8 GB Mac; the cap now matches the collector's."""
    for i in range(20):
        write_snapshot(raw, at(6 + i // 4, (i % 4) * 15), [row(status=f"S{i}")])
    con = rules.connect()
    con.execute("SET memory_limit = '1GB'")
    con.execute("SET threads = 2")
    assert rules.build_all(con, str(raw / "**" / "*.json.gz"))["snapshots"] == 20


def test_every_reply_the_collector_archives_fits_the_model_reader():
    from collector import core
    assert rules.MAX_REPLY_BYTES >= core.MAX_BODY_BYTES
