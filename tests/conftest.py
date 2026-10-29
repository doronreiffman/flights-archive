import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from collector import core

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def records():
    return json.loads((FIXTURES / "records.json").read_text(encoding="utf-8"))


@pytest.fixture
def blocked_html():
    return (FIXTURES / "blocked.html").read_bytes()


FIELDS = [{"id": "_id", "type": "int"}] + [{"id": f, "type": "numeric" if f == "CHTERM" else "text"}
                                            for f in sorted(core.REQUIRED_FIELDS)]


def ckan(result: dict, success: bool = True) -> bytes:
    """A datastore_search reply with the same envelope keys as the live one (archived 2026-10-29)."""
    limit, offset = result.get("limit", 10000), result.get("offset", 0)
    base = f"/api/3/action/datastore_search?resource_id={core.RESOURCE_ID}&limit={limit}&sort=_id"
    full = {"include_total": True, "limit": limit, "offset": offset, "records_format": "objects",
            "resource_id": core.RESOURCE_ID, "sort": "_id", "total_estimation_threshold": None,
            "fields": FIELDS, "_links": {"start": base, "next": f"{base}&offset={offset + limit}"},
            "total_was_estimated": False} | result  # records and total come from the caller
    return json.dumps({"help": "https://data.gov.il/api/3/action/help_show", "success": success,
                       "result": full}, ensure_ascii=False).encode()


def ok(body: bytes) -> core.Response:
    return core.Response(status=200, body=body, content_type="application/json; charset=utf-8", elapsed_ms=5)


class FakeAPI:
    """Serves resource_show and datastore_search from in-memory rows and records every call."""

    def __init__(self, rows, last_modified="2026-10-27T15:45:25.246426"):
        self.rows = rows
        self.total = None  # override to fake a wrong total
        self.last_modified = last_modified
        self.calls: list[str] = []
        self.timeouts: dict[str, float] = {}
        self.overrides: dict[str, core.Response] = {}

    def __call__(self, url: str, timeout: float) -> core.Response:
        self.calls.append(url)
        parsed = urlparse(url)
        action = parsed.path.rsplit("/", 1)[-1]
        self.timeouts[action] = timeout
        if action in self.overrides:
            return self.overrides[action]
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if action == "resource_show":
            return ok(ckan({"id": core.RESOURCE_ID, "last_modified": self.last_modified}))
        if action == "datastore_search":
            offset, limit = int(q.get("offset", 0)), int(q["limit"])
            page = self.rows[offset:offset + limit]
            total = len(self.rows) if self.total is None else self.total
            return ok(ckan({"resource_id": core.RESOURCE_ID, "records": page, "total": total,
                            "limit": limit, "offset": offset}))
        raise AssertionError(f"unexpected URL {url}")

    def reply(self, url: str) -> bytes:
        """The body this API returns for a URL, without recording a call."""
        calls, timeouts = list(self.calls), dict(self.timeouts)
        body = self(url, 0).body
        self.calls, self.timeouts = calls, timeouts
        return body

    def searches(self):
        return [c for c in self.calls if "datastore_search" in c]


@pytest.fixture
def now():
    return datetime(2026, 10, 30, 8, 0, 0, tzinfo=timezone.utc)
