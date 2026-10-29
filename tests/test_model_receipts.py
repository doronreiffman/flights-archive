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
    assert statuses(run(raw, rec)) == {old: "legacy"}


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
    assert f"no receipts under {tmp_path / 'receipts'}: every snapshot is legacy" in capsys.readouterr().out


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
