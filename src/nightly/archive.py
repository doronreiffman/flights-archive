"""The archive's two listings, a copy of exactly what they hold, and the check that the archive has not shrunk.

docs/nightly-model.md, "What one night does", steps 3 and 4, and section 1, "Copy, not read": receipts are listed
before boards, one listing straight after the other; every listed object is copied to its key's path with its size
checked; a copy that is not complete fails the night rather than build.
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from nightly.bucket import Bucket, Item

RECEIPTS = "receipts/"
RAW = "raw/"
DOWNLOAD_WORKERS = 16  # downloads at once: the plan's starting value until a run in AWS times the copy


class CopyError(Exception):
    """The copy is not the listing: a key with no place under the work folder, or a file of another size."""


class ArchiveShrunk(Exception):
    """A listing holds fewer objects, or an older newest key, than the last build's: a wrong bucket or a listing
    fault, since the archive only grows."""


def listing_sha256(items: Iterable[Item]) -> str:
    """SHA-256 of one line per object, key, tab, size, in key order."""
    digest = hashlib.sha256()
    for key, size in sorted(items):
        digest.update(f"{key}\t{size}\n".encode("utf-8"))
    return digest.hexdigest()


@dataclass(frozen=True)
class Listing:
    prefix: str
    items: tuple[Item, ...]  # key order

    @property
    def objects(self) -> int:
        return len(self.items)

    @property
    def bytes(self) -> int:
        return sum(item.size for item in self.items)

    @property
    def newest_key(self) -> str | None:
        """The greatest key: the collector's keys start with the date and time, so string order is time order."""
        return max((item.key for item in self.items), default=None)

    @property
    def sha256(self) -> str:
        return listing_sha256(self.items)

    def summary(self) -> dict:
        return {"objects": self.objects, "bytes": self.bytes, "newest_key": self.newest_key,
                "listing_sha256": self.sha256}


def list_archive(archive: Bucket) -> tuple[Listing, Listing]:
    """Receipts, then boards, back to back. The collector writes a receipt after its pages, so a board stored between
    the two listings arrives without its receipt and the model drops it as pending; never the reverse."""
    receipts = Listing(RECEIPTS, tuple(archive.list(RECEIPTS)))
    raw = Listing(RAW, tuple(archive.list(RAW)))
    return receipts, raw


def check_not_shrunk(previous: dict | None, receipts: Listing, raw: Listing) -> None:
    """ArchiveShrunk when either listing holds fewer objects, or an older newest key, than the last build's manifest
    (`previous`, None on the first night) names. A listing with no newest key counts as older than one named."""
    if previous is None:
        return
    for name, listing in (("receipts", receipts), ("raw", raw)):
        before = previous["archive"][name]
        if listing.objects < before["objects"]:
            raise ArchiveShrunk(f"{listing.prefix} lists {listing.objects} objects, the last build's "
                                f"{before['objects']}: a wrong bucket or a listing fault, not a smaller archive")
        newest = before["newest_key"]
        if newest is not None and (listing.newest_key or "") < newest:
            raise ArchiveShrunk(f"{listing.prefix} lists its newest key as {listing.newest_key}, older than the last "
                                f"build's {newest}: a wrong bucket or a listing fault, not a smaller archive")


def _place(root: Path, key: str) -> Path:
    """The key's path under the work folder `root` (resolved), or CopyError for a key that has none."""
    if key.endswith("/"):
        raise CopyError(f"{key}: a folder object, not a file; the copy has no place for it")
    path = (root / key).resolve()
    if root not in path.parents:
        raise CopyError(f"{key}: resolves to {path}, outside the work folder {root}")
    return path


def _download(archive: Bucket, item: Item, path: Path) -> None:
    archive.download(item.key, path)
    copied = path.stat().st_size
    if copied != item.size:
        raise CopyError(f"{item.key}: {copied} bytes copied, the listing says {item.size}")


def copy(archive: Bucket, listing: Listing, dest: Path, workers: int = DOWNLOAD_WORKERS) -> None:
    """Every listed object to `dest / key`, `workers` at once, each file's size checked against the listing.
    Every key is placed before any download; the first download to fail fails the copy."""
    root = dest.resolve()
    places = [(item, _place(root, item.key)) for item in listing.items]
    for folder in sorted({path.parent for _, path in places}):
        folder.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done in as_completed([pool.submit(_download, archive, item, path) for item, path in places]):
            done.result()  # raises the download's own error
