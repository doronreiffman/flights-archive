import hashlib
import re
import threading

import pytest

from nightly.archive import (DOWNLOAD_WORKERS, RAW, RECEIPTS, ArchiveShrunk, CopyError, Listing, check_not_shrunk,
                             copy, list_archive, listing_sha256)
from nightly.bucket import Item, MemoryBucket

# keys as the collector writes them (docs/receipts.md): a receipt has the stem of its snapshot folder
RECEIPT_1 = "receipts/date=2026-10-30/101531Z-0123456789ab.json"
RECEIPT_2 = "receipts/date=2026-10-31/003102Z-a1b2c3d4e5f6.json"
RECEIPT_3 = "receipts/date=2026-10-31/004602Z-f6e5d4c3b2a1.json"
BOARD_1 = "raw/date=2026-10-30/101531Z-0123456789ab/page-000.json.gz"
BOARD_2 = "raw/date=2026-10-31/003102Z-a1b2c3d4e5f6/page-000.json.gz"
BOARD_3 = "raw/date=2026-10-31/004602Z-f6e5d4c3b2a1/page-000.json.gz"


def archive() -> MemoryBucket:
    return MemoryBucket("archive", {
        RECEIPT_1: b'{"r": 1}', RECEIPT_2: b'{"r": 22}', RECEIPT_3: b'{"r": 333}',
        BOARD_1: b"\x1f\x8b board one", BOARD_2: b"\x1f\x8b board two!", BOARD_3: b"\x1f\x8b board three",
        "state/collector.json": b"{}", "rawx/not-a-board": b"x",
    })


def listing_of(bucket: MemoryBucket, prefix: str) -> Listing:
    """The bucket's objects under the prefix, listed without an entry in `ops`."""
    return Listing(prefix, tuple(Item(key, len(body)) for key, body in sorted(bucket.objects.items())
                                 if key.startswith(prefix)))


def files_under(folder) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def test_receipts_are_listed_before_boards():
    """A receipt is written after its pages, so listing receipts first can only leave a board without its receipt
    (dropped as pending), never a receipt without its board (docs/nightly-model.md, section 1)."""
    bucket = archive()
    receipts, raw = list_archive(bucket)
    assert bucket.ops == [("list", "receipts/"), ("list", "raw/")]
    assert receipts == Listing(RECEIPTS, (Item(RECEIPT_1, 8), Item(RECEIPT_2, 9), Item(RECEIPT_3, 10)))
    assert raw == Listing(RAW, (Item(BOARD_1, 12), Item(BOARD_2, 13), Item(BOARD_3, 14)))


def test_the_listing_digest_covers_every_key_and_size():
    assert listing_sha256([Item("a", 1)]) == hashlib.sha256(b"a\t1\n").hexdigest()
    items = [Item(BOARD_1, 12), Item(BOARD_2, 13), Item(BOARD_3, 14)]
    expected = hashlib.sha256(f"{BOARD_1}\t12\n{BOARD_2}\t13\n{BOARD_3}\t14\n".encode()).hexdigest()
    assert listing_sha256(items) == expected
    assert listing_sha256(reversed(items)) == expected
    assert listing_sha256([items[1], items[2], items[0]]) == expected
    assert listing_sha256([items[0], items[1], Item(BOARD_3, 15)]) != expected
    assert listing_sha256(items + [Item("raw/date=2026-11-01/000000Z-000000000000/page-000.json.gz", 1)]) != expected
    assert listing_sha256([]) == hashlib.sha256(b"").hexdigest()


def test_a_listing_reports_its_objects_bytes_and_newest_key():
    listing = Listing(RAW, (Item(BOARD_1, 12), Item(BOARD_2, 13), Item(BOARD_3, 14)))
    assert (listing.objects, listing.bytes, listing.newest_key) == (3, 39, BOARD_3)
    assert listing.sha256 == listing_sha256(listing.items)
    assert listing.summary() == {"objects": 3, "bytes": 39, "newest_key": BOARD_3, "listing_sha256": listing.sha256}

    empty = Listing(RECEIPTS, ())
    assert (empty.objects, empty.bytes, empty.newest_key) == (0, 0, None)
    assert empty.summary() == {"objects": 0, "bytes": 0, "newest_key": None,
                               "listing_sha256": hashlib.sha256(b"").hexdigest()}


def test_every_listed_key_lands_at_its_path_with_its_size(tmp_path):
    bucket = archive()
    dest = tmp_path / "work" / "archive"
    copy(bucket, listing_of(bucket, RAW), dest)
    # exactly the listed objects, at their keys' paths, over two date folders; nothing else the bucket holds
    assert files_under(dest) == {BOARD_1: bucket.objects[BOARD_1], BOARD_2: bucket.objects[BOARD_2],
                                 BOARD_3: bucket.objects[BOARD_3]}
    assert sorted(key for op, key in bucket.ops if op == "download") == [BOARD_1, BOARD_2, BOARD_3]


def test_a_short_download_fails_the_copy(tmp_path):
    bucket = archive()
    bucket.short.add(BOARD_2)
    with pytest.raises(CopyError, match=re.escape(f"{BOARD_2}: 12 bytes copied, the listing says 13")):
        copy(bucket, listing_of(bucket, RAW), tmp_path / "work")


def test_a_failed_download_fails_the_copy(tmp_path):
    bucket = archive()
    bucket.fail[("download", BOARD_2)] = [OSError("reset")]
    # match: the size check of a file a failed download never wrote raises FileNotFoundError, an OSError too
    with pytest.raises(OSError, match="reset"):
        copy(bucket, listing_of(bucket, RAW), tmp_path / "work")


@pytest.mark.parametrize("key", ["raw/../../escape.json.gz", "raw/date=2026-10-30/"])
def test_a_key_the_copy_cannot_place_fails_before_any_download(tmp_path, key):
    """A key that climbs out of the work folder, and a folder object as the S3 console makes one (Review Focus 2)."""
    bucket = archive()
    bucket.force(key, b"")
    with pytest.raises(CopyError, match=re.escape(key)):
        copy(bucket, listing_of(bucket, RAW), tmp_path / "work")
    assert [op for op in bucket.ops if op[0] == "download"] == []
    assert files_under(tmp_path) == {}


def test_a_zero_byte_object_is_copied(tmp_path):
    bucket = archive()
    bucket.force(BOARD_2, b"")
    dest = tmp_path / "work"
    copy(bucket, listing_of(bucket, RAW), dest)
    assert (dest / BOARD_2).is_file() and (dest / BOARD_2).read_bytes() == b""
    assert sorted(files_under(dest)) == [BOARD_1, BOARD_2, BOARD_3]


def test_downloads_run_at_once(tmp_path):
    """Each download waits until the other has started: one at a time breaks the barrier after 5 s, never hangs."""
    bucket = MemoryBucket("archive", {BOARD_1: b"one", BOARD_2: b"two!"})
    barrier = threading.Barrier(2, timeout=5)
    for key in (BOARD_1, BOARD_2):
        bucket.hooks[("download", key)] = barrier.wait
    dest = tmp_path / "work"
    copy(bucket, listing_of(bucket, RAW), dest, workers=2)
    assert files_under(dest) == {BOARD_1: b"one", BOARD_2: b"two!"}
    assert DOWNLOAD_WORKERS == 16  # the plan's starting value ("Downloads"), until a run in AWS times the copy


def previous_build() -> dict:
    """The part of the pointer's manifest the check reads: the last build's two listings."""
    bucket = archive()
    return {"archive": {"bucket": "archive", "receipts": listing_of(bucket, RECEIPTS).summary(),
                        "raw": listing_of(bucket, RAW).summary()}}


@pytest.mark.parametrize("name", ["receipts", "raw"])
@pytest.mark.parametrize("change", ["one object fewer", "an older newest key"])
def test_a_listing_smaller_than_the_pointers_fails(name, change):
    previous = previous_build()
    before = previous["archive"][name]
    bucket = archive()
    listings = {"receipts": listing_of(bucket, RECEIPTS), "raw": listing_of(bucket, RAW)}
    items = listings[name].items
    if change == "one object fewer":  # the oldest gone: the newest key is the same, so only the count can stop it
        after = Listing(listings[name].prefix, items[1:])
        assert (after.objects, after.newest_key) == (before["objects"] - 1, before["newest_key"])
        figures = [f"{after.objects} objects", f"{before['objects']}"]
    else:  # as many objects, the newest older than the last build's: only the key can stop it
        after = Listing(listings[name].prefix, items[:-1] + (Item(items[-2].key + ".older", 1),))
        assert after.objects == before["objects"] and after.newest_key < before["newest_key"]
        figures = [after.newest_key, before["newest_key"]]
    listings[name] = after
    with pytest.raises(ArchiveShrunk, match=re.escape(after.prefix)) as shrunk:
        check_not_shrunk(previous, **listings)
    for figure in figures:
        assert figure in str(shrunk.value)  # both figures named


@pytest.mark.parametrize("name", ["receipts", "raw"])
def test_a_listing_with_no_newest_key_is_older(name):
    """An empty listing where the manifest names a newest key (a count of 0 beside a key: edited by hand)."""
    previous = previous_build()
    previous["archive"][name]["objects"] = 0
    bucket = archive()
    listings = {"receipts": listing_of(bucket, RECEIPTS), "raw": listing_of(bucket, RAW)}
    listings[name] = Listing(listings[name].prefix, ())
    with pytest.raises(ArchiveShrunk, match=re.escape(previous["archive"][name]["newest_key"])):
        check_not_shrunk(previous, listings["receipts"], listings["raw"])


def newer(listing: Listing) -> Listing:
    """One more object, under a key newer than any listed."""
    return Listing(listing.prefix, listing.items + (Item(listing.items[-1].key.replace("2026-10-31", "2026-11-01"), 5),))


@pytest.mark.parametrize("case", ["equal figures", "more objects with a newer key", "the first night",
                                  "an empty archive before"])
def test_the_same_or_a_larger_archive_passes(case):
    bucket = archive()
    receipts, raw = listing_of(bucket, RECEIPTS), listing_of(bucket, RAW)
    previous = previous_build()
    if case in ("more objects with a newer key", "the first night"):
        receipts, raw = newer(receipts), newer(raw)
    if case == "the first night":
        previous = None
    if case == "an empty archive before":  # no newest key to compare with
        previous = {"archive": {"receipts": Listing(RECEIPTS, ()).summary(), "raw": Listing(RAW, ()).summary()}}
    check_not_shrunk(previous, receipts, raw)
