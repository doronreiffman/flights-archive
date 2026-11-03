"""Acquisition receipts in the model (docs/receipts.md): which snapshots it trusts, and when it refuses to build."""
from datetime import datetime, timedelta

import pytest

from collector import core
from collector.store import MemoryStore
from conftest import FakeAPI
from model import build, report, rules
from model_helpers import at, build as run, one, q, row, write_receipt, write_snapshot


@pytest.fixture
def raw(tmp_path):
    return tmp_path / "raw"


@pytest.fixture
def rec(tmp_path):
    return tmp_path / "receipts"


def statuses(con) -> dict[str, str]:
    return {r["snapshot_id"]: r["receipt"] for r in q(con, "SELECT snapshot_id, receipt FROM snapshot_runs")}


def kept(con) -> list[str]:
    return [r["snapshot_id"] for r in q(con, "SELECT snapshot_id FROM snapshots ORDER BY snap_rn")]


def test_what_the_collector_writes_builds_as_receipted(tmp_path, records, now):
    api, store = FakeAPI(records), MemoryStore()
    first = core.run_once(api, store, now)                                # stored
    core.run_once(api, store, now + timedelta(minutes=30))                # unchanged
    api.rows, api.last_modified = records[:-1], "2026-10-30T08:44:10.5"
    core.run_once(api, store, now + timedelta(minutes=45))                # stored
    for key, body in [(k, b) for k, (b, _) in store.objects.items()] + list(store.receipts.items()):
        (tmp_path / key).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / key).write_bytes(body)

    con = run(tmp_path / "raw", tmp_path / "receipts")
    assert sorted(statuses(con).values()) == ["receipted", "receipted"] and len(kept(con)) == 2
    r = q(con, "SELECT action, snapshot_id, run_started_at, resource_last_modified, pages, rows FROM receipts ORDER BY run_started_at")
    assert [x["action"] for x in r] == ["stored", "unchanged", "stored"]
    assert r[0]["snapshot_id"] == r[1]["snapshot_id"] == f"2026-10-30/080000Z-{first.sha256[:12]}"
    assert r[1]["run_started_at"] == datetime(2026, 10, 30, 8, 30)
    assert r[2]["resource_last_modified"] == datetime(2026, 10, 30, 8, 44, 10, 500000)
    assert [(x["pages"], x["rows"]) for x in r] == [(1, 38), (1, 38), (1, 37)]


def test_snapshots_before_the_first_receipt_are_legacy(raw, rec):
    old = write_snapshot(raw, at(6), [row()])
    new = write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    write_receipt(rec, new)
    con = run(raw, rec)
    assert statuses(con) == {old: "legacy", new: "receipted"} and kept(con) == [old, new]


def test_an_unchanged_receipt_can_be_the_first_and_name_a_legacy_snapshot(raw, rec):
    old = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, old, action="unchanged", when=at(6, 30))
    con = run(raw, rec)
    assert statuses(con) == {old: "legacy"}
    assert one(con, "SELECT confirmed_until FROM snapshots")["confirmed_until"] == at(6, 30)  # a sighting all the same (R9)


@pytest.mark.parametrize("make_dir", [False, True])
def test_without_receipts_every_snapshot_is_legacy(raw, rec, make_dir):
    a = write_snapshot(raw, at(6), [row()])
    b = write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    if make_dir:
        rec.mkdir()
    con = run(raw, rec)
    assert statuses(con) == {a: "legacy", b: "legacy"} and one(con, "SELECT count(*) n FROM receipts")["n"] == 0


@pytest.mark.parametrize("minutes", [15, 35])
def test_a_snapshot_newer_than_every_receipt_is_pending_and_dropped(raw, rec, minutes):
    """Receipts come at least every 30 minutes, so a sync can catch a store up to then without stopping."""
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    b = write_snapshot(raw, at(6, minutes), [row(status="DELAYED")])
    con = run(raw, rec)
    assert statuses(con) == {a: "receipted", b: "pending"} and kept(con) == [a]


def test_pending_counts_from_the_newest_receipt_of_either_kind(raw, rec):
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    write_receipt(rec, a, action="unchanged", when=at(6, 45))
    b = write_snapshot(raw, at(6, 50), [row(status="DELAYED")])
    assert statuses(run(raw, rec))[b] == "pending"


def test_receipts_older_than_raw_stop_the_build(raw, rec):
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    write_snapshot(raw, at(6, 36), [row(status="DELAYED")])
    with pytest.raises(ValueError, match=r"more than 35 min after the newest receipt.*scripts/sync.sh"):
        run(raw, rec)


def test_a_snapshot_without_its_receipt_between_receipts_stops_the_build(raw, rec):
    a = write_snapshot(raw, at(6), [row()])
    b = write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    c = write_snapshot(raw, at(6, 30), [row(status="BOARDING")])
    write_receipt(rec, a)
    write_receipt(rec, c)
    with pytest.raises(ValueError, match=rf"no receipt.*{b}.*KNOWN_ORPHANS"):
        run(raw, rec)


def test_a_known_orphan_is_dropped(raw, rec, monkeypatch):
    a = write_snapshot(raw, at(6), [row()])
    b = write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    c = write_snapshot(raw, at(6, 30), [row(status="BOARDING")])
    write_receipt(rec, a)
    write_receipt(rec, c)
    monkeypatch.setattr(rules, "KNOWN_ORPHANS", frozenset({b}))
    con = run(raw, rec)
    assert statuses(con) == {a: "receipted", b: "orphan", c: "receipted"} and kept(con) == [a, c]


@pytest.mark.parametrize("rows, pages", [(2, 1), (1, 2)])
def test_a_receipt_that_disagrees_with_its_files_stops_the_build(raw, rec, rows, pages):
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a, rows=rows, pages=pages)
    with pytest.raises(ValueError, match=rf"differ from their files.*{a}"):
        run(raw, rec)


@pytest.mark.parametrize("action", ["stored", "unchanged"])
def test_a_receipt_without_its_files_stops_the_build(raw, rec, action):
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    write_receipt(rec, "2026-10-27/061500Z-ffffffffffff", action=action, when=at(6, 15))
    with pytest.raises(ValueError, match=r"no files under raw/.*2026-10-27/061500Z-ffffffffffff"):
        run(raw, rec)


def test_an_unknown_receipt_version_stops_the_build(raw, rec):
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a, version=2)
    with pytest.raises(ValueError, match="receipt_version"):
        run(raw, rec)


def test_the_repeat_check_skips_dropped_snapshots(raw, rec, monkeypatch):
    """Two kept snapshots with the same content are one board stored twice, even with a dropped one between them."""
    a = write_snapshot(raw, at(6), [row()], sha="a" * 12)
    o = write_snapshot(raw, at(6, 15), [row(status="DELAYED")], sha="b" * 12)
    b = write_snapshot(raw, at(6, 30), [row()], sha="a" * 12)
    for sid in (a, o, b):
        write_receipt(rec, sid)
    (rec / "date=2026-10-27" / "061500Z-bbbbbbbbbbbb.json").unlink()
    monkeypatch.setattr(rules, "KNOWN_ORPHANS", frozenset({o}))
    con = run(raw, rec)
    assert kept(con) == [a] and one(con, "SELECT identical_repeats n FROM snapshots")["n"] == 1


def test_cli_reads_receipts_beside_raw_and_the_report_counts_them(tmp_path, capsys):
    raw, rec, out = tmp_path / "raw", tmp_path / "receipts", tmp_path / "model"
    old = write_snapshot(raw, at(6), [row()])
    new = write_snapshot(raw, at(6, 15), [row(status="DELAYED")])
    write_receipt(rec, new)
    write_receipt(rec, new, action="unchanged", when=at(6, 30))
    assert build.main(["--raw", str(raw), "--out", str(out)]) == 0
    assert "receipts: 2 rows" in capsys.readouterr().out and (out / "receipts.parquet").exists()
    text = report.report(out)
    assert "Receipts: 1 stored, 1 unchanged." in text
    assert "Snapshots by receipt: receipted 1, legacy 1, pending 0, orphan 0, superseded 0." in text
    assert old.startswith("2026-10-27")


def test_cli_says_when_there_are_no_receipts(tmp_path, capsys):
    raw = tmp_path / "raw"
    write_snapshot(raw, at(6), [row()])
    assert build.main(["--raw", str(raw), "--out", str(tmp_path / "model")]) == 0
    assert (f"no receipts under {tmp_path / 'receipts'}: snapshots from before receipts began are legacy, "
            "and any later one stops the build") in capsys.readouterr().out


def test_a_known_orphan_newer_than_every_receipt_is_dropped(raw, rec, monkeypatch):
    """A receipt write failed and no run has written a receipt since (blocked, or switched off)."""
    a = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, a)
    b = write_snapshot(raw, at(7), [row(status="DELAYED")])
    monkeypatch.setattr(rules, "KNOWN_ORPHANS", frozenset({b}))
    con = run(raw, rec)
    assert statuses(con) == {a: "receipted", b: "orphan"} and kept(con) == [a]


def test_an_orphan_stored_again_with_a_receipt_by_the_next_run_is_dropped(raw, rec):
    """A failed receipt write leaves state as it was, so the next run stores the same board again, with a receipt."""
    a = write_snapshot(raw, at(6), [row()])
    o = write_snapshot(raw, at(6, 15), [row(status="DELAYED")], sha="d" * 12)
    o2 = write_snapshot(raw, at(6, 17), [row(status="DELAYED")], sha="d" * 12)
    write_receipt(rec, a)
    write_receipt(rec, o2)
    con = run(raw, rec)
    assert statuses(con) == {a: "receipted", o: "superseded", o2: "receipted"} and kept(con) == [a, o2]


def test_an_interrupted_multi_page_orphan_stored_again_is_dropped(raw, rec):
    a = write_snapshot(raw, at(6), [row()])
    o = write_snapshot(raw, at(6, 15), [row(flight_no=str(n)) for n in range(4)], pages=2, sha="d" * 12)
    (raw / "date=2026-10-27" / f"{o.split('/')[1]}" / "page-001.json.gz").unlink()
    o2 = write_snapshot(raw, at(6, 17), [row(flight_no=str(n)) for n in range(4)], pages=2, sha="d" * 12)
    write_receipt(rec, a)
    write_receipt(rec, o2, rows=4, pages=2)
    assert statuses(run(raw, rec))[o] == "superseded"


def test_an_orphan_whose_next_snapshot_holds_other_content_stops_the_build(raw, rec):
    a = write_snapshot(raw, at(6), [row()])
    o = write_snapshot(raw, at(6, 15), [row(status="DELAYED")], sha="d" * 12)
    c = write_snapshot(raw, at(6, 17), [row(status="BOARDING")], sha="e" * 12)
    write_receipt(rec, a)
    write_receipt(rec, c)
    with pytest.raises(ValueError, match=rf"no receipt.*{o}"):
        run(raw, rec)


def test_an_orphan_is_superseded_only_by_a_receipted_copy(raw, rec, monkeypatch):
    a = write_snapshot(raw, at(6), [row()])
    o = write_snapshot(raw, at(6, 15), [row(status="DELAYED")], sha="d" * 12)
    o2 = write_snapshot(raw, at(6, 17), [row(status="DELAYED")], sha="d" * 12)
    c = write_snapshot(raw, at(6, 30), [row(status="BOARDING")])
    write_receipt(rec, a)
    write_receipt(rec, c)
    monkeypatch.setattr(rules, "KNOWN_ORPHANS", frozenset({o2}))
    with pytest.raises(ValueError, match=rf"no receipt.*{o}"):
        run(raw, rec)


def test_the_legacy_cutover_is_the_first_receipt_of_either_kind(raw, rec):
    """An orphan after an unchanged receipt is not legacy, even when no stored receipt comes before it."""
    old = write_snapshot(raw, at(6), [row()])
    write_receipt(rec, old, action="unchanged", when=at(6, 30))
    x = write_snapshot(raw, at(6, 35), [row(status="DELAYED")])
    y = write_snapshot(raw, at(6, 45), [row(status="BOARDING")])
    write_receipt(rec, y)
    with pytest.raises(ValueError, match=rf"no receipt.*{x}"):
        run(raw, rec)


def test_without_receipts_a_snapshot_from_after_receipts_began_stops_the_build(raw, rec):
    """A fresh clone, a deleted receipts/ or a raw-only sync must not quietly trust boards that should have receipts."""
    write_snapshot(raw, at(6), [row()])
    late = write_snapshot(raw, datetime(2026, 10, 30, 6, 0), [row(status="DELAYED")])
    with pytest.raises(ValueError, match=rf"no receipt.*{late}"):
        run(raw, rec)


def test_a_missing_first_receipt_does_not_make_later_snapshots_legacy(raw, rec):
    """Receipts began 2026-10-29 17:02:50Z: a snapshot after that with no receipt is never legacy, whatever the
    earliest local receipt says."""
    a = write_snapshot(raw, datetime(2026, 10, 29, 17, 16, 45), [row()])
    b = write_snapshot(raw, datetime(2026, 10, 29, 17, 32, 45), [row(status="DELAYED")])
    write_receipt(rec, b)
    with pytest.raises(ValueError, match=rf"no receipt.*{a}"):
        run(raw, rec)


# Receipts as observations (q14): every receipt, stored or unchanged, is a sighting of the board -----------
# A snapshot's confirmed_until is the last sighting of its content; a gap runs from there to the next snapshot.


def bridge(rec, snapshot_id, *whens):
    """Unchanged downloads that saw the snapshot's content again at `whens`."""
    for when in whens:
        write_receipt(rec, snapshot_id, action="unchanged", when=when)


def test_confirmed_until_is_the_last_sighting_of_the_board(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30), at(7))
    s2 = write_snapshot(raw, at(7, 30), [row(status="DELAYED")]); write_receipt(rec, s2)
    snaps = q(run(raw, rec), "SELECT confirmed_until, gap_before_s FROM snapshots ORDER BY snap_rn")
    assert [(s["confirmed_until"], s["gap_before_s"]) for s in snaps] == [(at(7), None), (at(7, 30), 1800)]


def test_without_a_sighting_in_between_the_gap_is_the_snapshot_spacing(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    s2 = write_snapshot(raw, at(7, 30), [row(status="DELAYED")]); write_receipt(rec, s2)
    snaps = q(run(raw, rec), "SELECT confirmed_until, gap_before_s FROM snapshots ORDER BY snap_rn")
    assert [(s["confirmed_until"], s["gap_before_s"]) for s in snaps] == [(at(6), None), (at(7, 30), 5400)]


def test_a_legacy_snapshots_window_closes_at_the_first_receipted_one(raw, rec):
    write_snapshot(raw, at(5), [row()])                                   # legacy: no receipt
    s1 = write_snapshot(raw, at(6), [row(status="DELAYED")]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30))
    snaps = q(run(raw, rec), "SELECT confirmed_until, gap_before_s FROM snapshots ORDER BY snap_rn")
    assert [(s["confirmed_until"], s["gap_before_s"]) for s in snaps] == [(at(5), None), (at(6, 30), 3600)]


def test_a_repeated_store_is_a_sighting_of_the_kept_snapshot(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()], sha="a" * 12); write_receipt(rec, s1)
    again = write_snapshot(raw, at(6, 40), [row()], sha="a" * 12); write_receipt(rec, again)  # R2 drops the repeat
    s2 = write_snapshot(raw, at(7, 30), [row(status="DELAYED")]); write_receipt(rec, s2)
    con = run(raw, rec)
    assert kept(con) == [s1, s2]
    snaps = q(con, "SELECT confirmed_until, gap_before_s FROM snapshots ORDER BY snap_rn")
    assert [(s["confirmed_until"], s["gap_before_s"]) for s in snaps] == [(at(6, 40), None), (at(7, 30), 3000)]


def test_a_flight_whose_hole_the_sightings_bridge_is_not_lost_in_a_gap(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30), at(7))
    s2 = write_snapshot(raw, at(7, 30), [row(flight_no="other")]); write_receipt(rec, s2)
    f = one(run(raw, rec), "SELECT outcome, last_seen_at FROM flights WHERE flight_no = '001'")
    assert (f["outcome"], f["last_seen_at"]) == ("vanished", at(7))  # due 08:00Z next day: left early, no hole


def test_the_same_hole_without_sightings_is_a_gap(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    s2 = write_snapshot(raw, at(7, 30), [row(flight_no="other")]); write_receipt(rec, s2)
    f = one(run(raw, rec), "SELECT outcome, last_seen_at FROM flights WHERE flight_no = '001'")
    assert (f["outcome"], f["last_seen_at"]) == ("gap", at(6))


def test_a_retime_links_across_a_hole_the_sightings_bridge(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30), at(7))
    s2 = write_snapshot(raw, at(7, 30), [row(sched_local="2026-10-28T11:00:00")]); write_receipt(rec, s2)
    f = one(run(raw, rec), "SELECT retimes, outcome FROM flights")
    assert (f["retimes"], f["outcome"]) == (1, "open")


def test_a_retime_does_not_link_across_a_hole_no_sighting_bridges(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    s2 = write_snapshot(raw, at(7, 30), [row(sched_local="2026-10-28T11:00:00")]); write_receipt(rec, s2)
    assert sorted(f["outcome"] for f in q(run(raw, rec), "SELECT outcome FROM flights")) == ["gap", "open"]


def test_a_cancellation_bracket_starts_at_the_last_sighting_before_it(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30), at(7))
    s2 = write_snapshot(raw, at(7, 30), [row(status="CANCELED")]); write_receipt(rec, s2)
    f = one(run(raw, rec), "SELECT cancel_announced_after, cancel_bracket_min, cancel_lead_censored FROM flights")
    assert (f["cancel_announced_after"], f["cancel_bracket_min"], f["cancel_lead_censored"]) == (at(7), 30, False)


def test_a_change_is_bracketed_from_the_last_sighting_of_the_state_before(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30))
    s2 = write_snapshot(raw, at(6, 45), [row(status="DELAYED")]); write_receipt(rec, s2)
    o = one(run(raw, rec), "SELECT observed_at, prev_observed_at FROM observations WHERE change_kind = 'change'")
    assert (o["observed_at"], o["prev_observed_at"]) == (at(6, 45), at(6, 30))


def test_sightings_after_the_latest_snapshot_extend_it(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30))
    con = run(raw, rec)
    assert one(con, "SELECT confirmed_until FROM snapshots")["confirmed_until"] == at(6, 30)
    assert one(con, "SELECT last_seen_at, outcome FROM flights") == {"last_seen_at": at(6, 30), "outcome": "open"}


def test_a_receipt_whose_board_differs_from_the_kept_snapshot_of_its_time_stops_the_build(raw, rec):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    s2 = write_snapshot(raw, at(6, 15), [row(status="DELAYED")]); write_receipt(rec, s2)
    write_receipt(rec, s1, action="unchanged", when=at(6, 20))  # s1's content seen again in s2's time: not a stall
    with pytest.raises(ValueError, match="differs from the kept snapshot"):
        run(raw, rec)


def test_report_names_a_gap_from_the_last_sighting(raw, rec, tmp_path):
    s1 = write_snapshot(raw, at(6), [row()]); write_receipt(rec, s1)
    bridge(rec, s1, at(6, 30))
    s2 = write_snapshot(raw, at(8), [row()]); write_receipt(rec, s2)
    out = tmp_path / "model"
    build.build(raw, out, rec)
    assert "| 2026-10-27 06:30:00 | 2026-10-27 08:00:00 | 1.5 |" in report.report(out)
