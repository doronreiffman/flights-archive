import gzip
import hashlib
import re
from datetime import timedelta, timezone

import pytest

from collector import core
from collector.store import MemoryStore
from conftest import FakeAPI, ckan, ok


def stored_state(api, now, minutes_ago, sha="old", **extra):
    return {"last_modified": api.last_modified, "last_full_fetch": (now - timedelta(minutes=minutes_ago)).isoformat(),
            "sha256": sha, "last_key": None, "pending_since": None, **extra}


# --- normal operation -------------------------------------------------------

def test_first_run_stores_the_reply_untouched(records, now):
    api, store = FakeAPI(records), MemoryStore()
    out = core.run_once(api, store, now)

    assert out.action == "stored" and out.rows == 38 and len(out.keys) == 1
    body, meta = store.objects[out.keys[0]]
    reply = api.reply(api.searches()[0])
    assert gzip.decompress(body) == reply
    assert out.sha256 == hashlib.sha256(reply).hexdigest() == meta["snapshot-sha256"] == meta["page-sha256"]
    assert meta["rows"] == "38" and meta["pages"] == "1" and meta["http-status"] == "200"
    assert meta["resource-last-modified"] == api.last_modified
    assert meta["fetched-at"] == now.isoformat()
    assert store.state == {"last_modified": api.last_modified, "last_full_fetch": now.isoformat(),
                           "sha256": out.sha256, "last_key": out.keys[0], "pending_since": None}


def test_key_layout_and_request_shape(records, now):
    api = FakeAPI(records)
    out = core.run_once(api, MemoryStore(), now)
    assert re.fullmatch(r"raw/date=2026-10-30/080000Z-[0-9a-f]{12}/page-000\.json\.gz", out.keys[0])
    assert "sort=_id" in api.searches()[0]
    assert api.timeouts == {"resource_show": core.SHOW_TIMEOUT, "datastore_search": core.SEARCH_TIMEOUT}


def test_skips_download_when_timestamp_unchanged_and_recent(records, now):
    api = FakeAPI(records)
    store = MemoryStore(stored_state(api, now, minutes_ago=10))
    out = core.run_once(api, store, now)
    assert out.action == "skipped"
    assert api.searches() == [] and store.objects == {} and store.state_writes == 0


def test_downloads_when_timestamp_changes(records, now):
    api = FakeAPI(records)
    store = MemoryStore(stored_state(api, now, minutes_ago=2))
    api.last_modified = "2026-10-27T16:00:25.000000"
    out = core.run_once(api, store, now)
    assert out.action == "stored" and store.state["last_modified"] == api.last_modified
    assert store.state["pending_since"] is None


def test_safety_download_every_30_min_keeps_the_hash(records, now):
    api = FakeAPI(records)
    first = core.run_once(api, MemoryStore(), now - timedelta(minutes=30))
    store = MemoryStore(stored_state(api, now, minutes_ago=30, sha=first.sha256))
    out = core.run_once(api, store, now)
    assert out.action == "unchanged" and len(api.searches()) == 2
    assert store.objects == {}
    assert store.state["last_full_fetch"] == now.isoformat() and store.state["sha256"] == first.sha256


def test_content_change_without_timestamp_change_is_caught(records, now):
    api = FakeAPI(records)
    store = MemoryStore(stored_state(api, now, minutes_ago=31, sha="something-else"))
    assert core.run_once(api, store, now).action == "stored"


def test_timestamp_moving_before_the_data_keeps_us_downloading(records, now):
    api, store = FakeAPI(records), MemoryStore()
    core.run_once(api, store, now)                                   # stored
    api.last_modified = "2026-10-27T16:00:25"                        # timestamp moves, data not yet
    out = core.run_once(api, store, now + timedelta(minutes=2))
    assert out.action == "unchanged" and store.state["pending_since"] == (now + timedelta(minutes=2)).isoformat()

    out = core.run_once(api, store, now + timedelta(minutes=4))      # still the same data: keep checking
    assert out.action == "unchanged" and len(api.searches()) == 3

    api.rows = records[:-1]                                          # data finally arrives
    out = core.run_once(api, store, now + timedelta(minutes=6))
    assert out.action == "stored" and store.state["pending_since"] is None


def test_pending_window_expires(records, now):
    api, store = FakeAPI(records), MemoryStore()
    core.run_once(api, store, now)
    api.last_modified = "2026-10-27T16:00:25"
    start = now + timedelta(minutes=2)
    core.run_once(api, store, start)
    out = core.run_once(api, store, start + core.PENDING_WINDOW - timedelta(minutes=1))
    assert out.action == "unchanged" and store.state["pending_since"] == start.isoformat()
    assert core.run_once(api, store, start + core.PENDING_WINDOW).action == "skipped"


def test_pages_are_fetched_and_stored_separately(records, now):
    api, store = FakeAPI(records), MemoryStore()
    out = core.run_once(api, store, now, page_size=10)
    assert len(api.searches()) == 4 and out.rows == 38 and len(out.keys) == 4
    bodies = [gzip.decompress(store.objects[k][0]) for k in out.keys]
    assert out.sha256 == hashlib.sha256(b"".join(hashlib.sha256(b).digest() for b in bodies)).hexdigest()
    assert [store.objects[k][1]["rows"] for k in out.keys] == ["10", "10", "10", "8"]
    assert sum(c.count("resource_show") for c in api.calls) == 2  # re-checked after paging


def test_board_changing_mid_paging_stores_nothing(records, now):
    class Moving(FakeAPI):
        def __call__(self, url, timeout):
            resp = super().__call__(url, timeout)
            if "datastore_search" in url:
                self.last_modified = "2026-10-27T16:00:00"
            return resp

    store = MemoryStore()
    with pytest.raises(core.CollectorError, match="changed while paging"):
        core.run_once(Moving(records), store, now, page_size=10)
    assert store.objects == {} and store.state is None


# --- blocks and the latch ---------------------------------------------------

@pytest.mark.parametrize("status", [401, 403, 429])
def test_block_statuses_raise_and_latch(records, now, status):
    api = FakeAPI(records)
    api.overrides["datastore_search"] = core.Response(status, b"{}", "application/json", 3)
    store = MemoryStore()
    with pytest.raises(core.BlockedError, match="Stop and ask"):
        core.run_once(api, store, now)
    assert store.objects == {}
    assert store.state["blocked"]["at"] == now.isoformat() and f"HTTP {status}" in store.state["blocked"]["reason"]


def test_latched_collector_makes_no_requests_until_cleared(records, now, blocked_html):
    api, store = FakeAPI(records), MemoryStore()
    api.overrides["resource_show"] = core.Response(403, blocked_html, "text/html", 3)
    with pytest.raises(core.BlockedError):
        core.run_once(api, store, now)
    del api.overrides["resource_show"]
    calls_before = len(api.calls)

    with pytest.raises(core.BlockedError, match="latched off"):
        core.run_once(api, store, now + timedelta(minutes=2))
    assert len(api.calls) == calls_before

    assert core.clear_block(store) is True
    assert core.run_once(api, store, now + timedelta(minutes=4)).action == "stored"
    assert core.clear_block(store) is False


def test_html_page_with_200_is_a_block(records, now, blocked_html):
    api = FakeAPI(records)
    api.overrides["resource_show"] = core.Response(200, blocked_html, "application/json", 3)
    with pytest.raises(core.BlockedError):
        core.run_once(api, MemoryStore(), now)


def test_html_content_type_with_200_is_a_block(records, now):
    api = FakeAPI(records)
    api.overrides["datastore_search"] = core.Response(200, ckan({"records": [], "total": 0}), "text/html", 3)
    with pytest.raises(core.BlockedError):
        core.run_once(api, MemoryStore(), now)


@pytest.mark.parametrize("status, body, ctype", [
    (502, b"<html><body><h1>502 Bad Gateway</h1></body></html>", "text/html"),
    (503, b"<!DOCTYPE html><title>Service Unavailable</title>", "text/html"),
    (404, ckan({"message": "Not found"}, success=False), "application/json"),
    (500, b"oops", "text/plain"),
])
def test_outages_are_errors_not_blocks(records, now, status, body, ctype):
    api, store = FakeAPI(records), MemoryStore()
    api.overrides["datastore_search"] = core.Response(status, body, ctype, 3)
    with pytest.raises(core.CollectorError) as err:
        core.run_once(api, store, now)
    assert not isinstance(err.value, core.BlockedError) and f"HTTP {status}" in str(err.value)
    assert store.state is None  # no latch


# --- malformed replies -------------------------------------------------------

@pytest.mark.parametrize("body, match", [
    (b"not json", "not JSON"),
    (ckan({}, success=False), "failure"),
    (b"[]", "unexpected shape"),
])
def test_bad_replies_raise(records, now, body, match):
    api = FakeAPI(records)
    api.overrides["datastore_search"] = ok(body)
    with pytest.raises(core.CollectorError, match=match):
        core.run_once(api, MemoryStore(), now)


def test_zero_rows_raise(now):
    with pytest.raises(core.CollectorError, match="zero rows"):
        core.run_once(FakeAPI([]), MemoryStore(), now)


def test_missing_field_raises(records, now):
    del records[5]["CHRMINE"]
    with pytest.raises(core.CollectorError, match="CHRMINE"):
        core.run_once(FakeAPI(records), MemoryStore(), now)


def test_non_object_record_raises(records, now):
    records[0] = ["not", "a", "record"]
    with pytest.raises(core.CollectorError, match="missing fields"):
        core.run_once(FakeAPI(records), MemoryStore(), now)


def test_total_larger_than_rows_raises(records, now):
    api = FakeAPI(records)
    api.total = 50
    with pytest.raises(core.CollectorError, match="empty"):
        core.run_once(api, MemoryStore(), now, page_size=20)


def test_total_smaller_than_rows_raises(records, now):
    api = FakeAPI(records)
    api.total = 30
    with pytest.raises(core.CollectorError, match="total is 30"):
        core.run_once(api, MemoryStore(), now)


def test_total_changing_between_pages_raises(records, now):
    class Shifting(FakeAPI):
        def __call__(self, url, timeout):
            resp = super().__call__(url, timeout)
            if "datastore_search" in url:
                self.total = 99
            return resp

    with pytest.raises(core.CollectorError, match="total changed"):
        core.run_once(Shifting(records), MemoryStore(), now, page_size=10)


def test_reply_without_records_or_total_raises(records, now):
    api = FakeAPI(records)
    api.overrides["datastore_search"] = ok(ckan({"total": 38}))
    with pytest.raises(core.CollectorError, match="records or total missing"):
        core.run_once(api, MemoryStore(), now)


def test_too_many_pages_raises(records, now):
    with pytest.raises(core.CollectorError, match="raise page_size"):
        core.run_once(FakeAPI(records), MemoryStore(), now, page_size=1)


def test_resource_show_without_timestamp_raises(records, now):
    api = FakeAPI(records)
    api.overrides["resource_show"] = ok(ckan({"id": core.RESOURCE_ID}))
    with pytest.raises(core.CollectorError, match="last_modified"):
        core.run_once(api, MemoryStore(), now)


@pytest.mark.parametrize("bad", ["naive", "israel"])
def test_requires_utc_now(records, now, bad):
    when = now.replace(tzinfo=None) if bad == "naive" else now.astimezone(timezone(timedelta(hours=2)))
    with pytest.raises(ValueError):
        core.run_once(FakeAPI(records), MemoryStore(), when)


def test_memory_store_refuses_overwrite(now):
    store = MemoryStore()
    store.put_snapshot("raw/x", b"1", {}, now)
    with pytest.raises(FileExistsError):
        store.put_snapshot("raw/x", b"2", {}, now)
