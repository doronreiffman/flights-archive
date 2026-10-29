"""Fetch, validate and archive the flydata flight board.

Each run:
1. Asks data.gov.il when the board's resource last changed (a small call).
2. Downloads the whole board only if that changed, if the last full
   download is older than FULL_FETCH_EVERY, or while a timestamp change is
   still waiting for its data (PENDING_WINDOW).
3. Stores the reply bytes untouched (gzipped) only if their content hash
   differs from the last stored snapshot.

Anything unexpected raises instead of writing. A reply that looks like a
firewall block raises BlockedError and latches the collector off: every
later run refuses to call data.gov.il until a person clears the latch. Never
retry with a browser User-Agent, another IP, or anything else that works
around a block. The data.gov.il license excludes data obtained by
circumventing technical protection.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

API = "https://data.gov.il/api/3/action"
RESOURCE_ID = "e83f763b-b7d7-479e-b172-ae981ddc6de5"
SOURCE = f"data.gov.il flydata resource {RESOURCE_ID} (Israel Airports Authority)"
FULL_FETCH_EVERY = timedelta(minutes=30)
PENDING_WINDOW = timedelta(minutes=10)
# 20 s: data.gov.il answered resource_show slower than 10 s twice right after its 13:01Z refresh on 2026-10-29.
SHOW_TIMEOUT = 20.0
SEARCH_TIMEOUT = 45.0
# The board is about 1 MB uncompressed; a reply past this is not the board.
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_PAGES = 20

REQUIRED_FIELDS = frozenset({
    "CHOPER", "CHFLTN", "CHOPERD", "CHSTOL", "CHPTOL", "CHAORD", "CHLOC1",
    "CHLOC1D", "CHLOC1TH", "CHLOC1T", "CHLOC1CH", "CHLOCCT", "CHTERM",
    "CHCINT", "CHCKZN", "CHRMINE", "CHRMINH",
})


class CollectorError(Exception):
    """The reply was not what we expect. Nothing was stored."""


class BlockedError(CollectorError):
    """The reply looks like a firewall block. Stop and ask a person."""


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str
    elapsed_ms: int


Fetcher = Callable[[str, float], Response]


class Store(Protocol):
    def read_state(self) -> dict | None: ...
    def write_state(self, state: dict) -> None: ...
    def put_snapshot(self, key: str, body: bytes, metadata: dict[str, str], now: datetime) -> None: ...


@dataclass(frozen=True)
class Page:
    body: bytes
    rows: int
    status: int
    elapsed_ms: int


@dataclass
class Outcome:
    action: str  # "skipped" | "unchanged" | "stored"
    last_modified: str
    rows: int = 0
    sha256: str | None = None
    keys: list[str] = field(default_factory=list)


def check_user_agent(user_agent: str) -> str:
    """The User-Agent must name a project URL and a contact email, e.g.
    "flights-archive/0.1 (+https://github.com/you/repo; you@example.org)"."""
    if "+http" not in user_agent or "@" not in user_agent:
        raise ValueError("USER_AGENT must contain a +https:// project URL and a contact email address")
    return user_agent


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the same scheme and host. Anything else would mean fetching the
    board from somewhere other than data.gov.il, which the license and our rules do not cover."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (new.scheme, new.netloc) != (old.scheme, old.netloc):
            raise CollectorError(f"redirect to {new.scheme}://{new.netloc} refused; {old.netloc} is the only source")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameHostRedirects)


def http_get(url: str, timeout: float, *, user_agent: str) -> Response:
    """GET a URL. HTTP error statuses come back as a Response, not an exception."""
    check_user_agent(user_agent)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    start = time.monotonic()
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            body = resp.read(MAX_BODY_BYTES + 1)
            status, ctype = resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as err:
        body = err.read(MAX_BODY_BYTES + 1) or b""
        status, ctype = err.code, err.headers.get("Content-Type", "") if err.headers else ""
    elapsed = int((time.monotonic() - start) * 1000)
    if len(body) > MAX_BODY_BYTES:
        raise CollectorError(f"{url.split('?')[0]}: reply larger than {MAX_BODY_BYTES} bytes")
    return Response(status=status, body=body, content_type=ctype, elapsed_ms=elapsed)


def _looks_like_html(resp: Response) -> bool:
    head = resp.body.lstrip()[:64].lower()
    return "html" in resp.content_type.lower() or head.startswith((b"<!doctype", b"<html", b"<head", b"<body"))


def parse_result(resp: Response, what: str) -> dict:
    """Return the CKAN `result` object or raise.

    Blocks are 401/403/429, or an HTML page served with 200 where JSON belongs.
    Other errors, including HTML 5xx pages from an outage, are ordinary failures.
    """
    if resp.status in (401, 403, 429) or (resp.status == 200 and _looks_like_html(resp)):
        raise BlockedError(
            f"{what}: HTTP {resp.status}, content-type {resp.content_type!r}; looks like a firewall block. "
            "Stop and ask; do not work around it."
        )
    if resp.status != 200:
        raise CollectorError(f"{what}: HTTP {resp.status}")
    try:
        doc = json.loads(resp.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise CollectorError(f"{what}: reply is not JSON ({err})") from err
    if not isinstance(doc, dict) or doc.get("success") is not True or not isinstance(doc.get("result"), dict):
        raise CollectorError(f"{what}: CKAN reported failure or an unexpected shape")
    return doc["result"]


def resource_last_modified(fetch: Fetcher) -> str:
    result = parse_result(fetch(f"{API}/resource_show?id={RESOURCE_ID}", SHOW_TIMEOUT), "resource_show")
    stamp = result.get("last_modified")
    if not isinstance(stamp, str) or not stamp:
        raise CollectorError("resource_show: no last_modified")
    return stamp


def fetch_board(fetch: Fetcher, page_size: int) -> list[Page]:
    """Download every page of the board and validate it. Returns the raw pages."""
    pages: list[Page] = []
    offset = 0
    total = None
    last_id = None
    while True:
        url = (f"{API}/datastore_search?resource_id={RESOURCE_ID}"
               f"&limit={page_size}&offset={offset}&sort=_id")
        resp = fetch(url, SEARCH_TIMEOUT)
        result = parse_result(resp, f"datastore_search offset {offset}")
        records, page_total = result.get("records"), result.get("total")
        if not isinstance(records, list) or not isinstance(page_total, int):
            raise CollectorError("datastore_search: records or total missing")
        if total is None:
            total = page_total
        elif page_total != total:
            raise CollectorError(f"total changed during paging ({total} -> {page_total})")
        if total == 0:
            raise CollectorError("datastore_search: zero rows")
        for i, rec in enumerate(records):
            missing = REQUIRED_FIELDS.difference(rec) if isinstance(rec, dict) else REQUIRED_FIELDS
            if missing:
                raise CollectorError(f"record {offset + i} is missing fields: {sorted(missing)}")
            # Pages are cut by _id order, so a repeated or unsorted _id means rows could be skipped or doubled.
            row_id = rec.get("_id")
            if not isinstance(row_id, int) or (last_id is not None and row_id <= last_id):
                raise CollectorError(f"record {offset + i}: _id {row_id!r} is not strictly increasing after {last_id!r}")
            last_id = row_id
        pages.append(Page(body=resp.body, rows=len(records), status=resp.status, elapsed_ms=resp.elapsed_ms))
        offset += len(records)
        if offset >= total:
            break
        if not records:
            raise CollectorError(f"total is {total} but the page at offset {offset} is empty")
        if len(pages) >= MAX_PAGES:
            raise CollectorError(f"more than {MAX_PAGES} pages; raise page_size")
    if offset != total:
        raise CollectorError(f"got {offset} rows but total is {total}")
    return pages


def snapshot_sha256(pages: list[Page]) -> str:
    """SHA-256 of the raw reply for one page; for several pages, of their per-page digests."""
    if len(pages) == 1:
        return hashlib.sha256(pages[0].body).hexdigest()
    return hashlib.sha256(b"".join(hashlib.sha256(p.body).digest() for p in pages)).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def run_once(fetch: Fetcher, store: Store, now: datetime, page_size: int = 10000) -> Outcome:
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("now must be timezone-aware UTC")
    state = store.read_state() or {}
    latch = state.get("blocked")
    if latch:
        raise BlockedError(
            f"latched off since {latch.get('at')} after: {latch.get('reason')}. "
            "Nothing was requested. A person must check, then clear the latch (see README)."
        )
    try:
        return _collect(fetch, store, now, state, page_size)
    except BlockedError as err:
        try:
            store.write_state({**state, "blocked": {"at": now.isoformat(), "reason": str(err)[:500]}})
        except Exception as latch_err:  # noqa: BLE001 - the block must still be reported as a block
            raise BlockedError(f"{err} (and the block latch could not be saved: {latch_err}; "
                               "the next run will call data.gov.il again)") from err
        raise


def _collect(fetch: Fetcher, store: Store, now: datetime, state: dict, page_size: int) -> Outcome:
    last_modified = resource_last_modified(fetch)
    last_full = _parse_time(state.get("last_full_fetch"))
    pending_since = _parse_time(state.get("pending_since"))
    moved = last_modified != state.get("last_modified")
    full_due = last_full is None or now - last_full >= FULL_FETCH_EVERY
    pending = pending_since is not None and now - pending_since < PENDING_WINDOW
    if not (moved or full_due or pending):
        return Outcome(action="skipped", last_modified=last_modified)

    pages = fetch_board(fetch, page_size)
    if len(pages) > 1 and resource_last_modified(fetch) != last_modified:
        raise CollectorError("the board changed while paging; the next run will retry")
    digest = snapshot_sha256(pages)
    rows = sum(p.rows for p in pages)
    new_state = {
        "last_modified": last_modified,
        "last_full_fetch": now.isoformat(),
        "sha256": state.get("sha256"),
        "last_key": state.get("last_key"),
        "pending_since": None,
    }
    if digest == state.get("sha256"):
        # The timestamp can move before the data does; keep downloading for a while.
        if moved:
            new_state["pending_since"] = now.isoformat()
        elif pending:
            new_state["pending_since"] = state["pending_since"]
        store.write_state(new_state)
        return Outcome(action="unchanged", last_modified=last_modified, rows=rows, sha256=digest)

    prefix = f"raw/date={now:%Y-%m-%d}/{now:%H%M%S}Z-{digest[:12]}"
    keys = []
    for i, page in enumerate(pages):
        key = f"{prefix}/page-{i:03d}.json.gz"
        metadata = {
            "fetched-at": now.isoformat(),
            "source": SOURCE,
            "resource-last-modified": last_modified,
            "http-status": str(page.status),
            "latency-ms": str(page.elapsed_ms),
            "page": str(i),
            "pages": str(len(pages)),
            "rows": str(page.rows),
            "page-sha256": hashlib.sha256(page.body).hexdigest(),
            "snapshot-sha256": digest,
        }
        store.put_snapshot(key, gzip.compress(page.body, mtime=0), metadata, now)
        keys.append(key)
    new_state.update(sha256=digest, last_key=keys[0])
    store.write_state(new_state)
    return Outcome(action="stored", last_modified=last_modified, rows=rows, sha256=digest, keys=keys)


def clear_block(store: Store) -> bool:
    """Remove the block latch after a person has checked. Returns whether one was set."""
    state = store.read_state() or {}
    if "blocked" not in state:
        return False
    store.write_state({k: v for k, v in state.items() if k != "blocked"})
    return True


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
