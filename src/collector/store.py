"""Where snapshots and the collector's small state file live."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from botocore.exceptions import ClientError

STATE_KEY = "state/collector.json"


class S3Store:
    """Raw snapshots under raw/ and receipts under receipts/, write-once and Object Lock protected; state under state/."""

    def __init__(self, client, bucket: str, retention_days: int, lock_mode: str = "GOVERNANCE"):
        if retention_days < 1:
            raise ValueError("retention_days must be at least 1")
        self.client = client
        self.bucket = bucket
        self.retention = timedelta(days=retention_days)
        self.lock_mode = lock_mode

    def read_state(self) -> dict | None:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=STATE_KEY)
        except ClientError as err:
            if err.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(obj["Body"].read())

    def write_state(self, state: dict) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=STATE_KEY,
            Body=json.dumps(state, sort_keys=True).encode(),
            ContentType="application/json",
        )

    def put_snapshot(self, key: str, body: bytes, metadata: dict[str, str], now: datetime) -> None:
        self._put_locked(key, body, now, ContentType="application/gzip", Metadata=metadata)

    def put_receipt(self, key: str, body: bytes, now: datetime) -> None:
        self._put_locked(key, body, now, ContentType="application/json")

    def _put_locked(self, key: str, body: bytes, now: datetime, **extra) -> None:
        # IfNoneMatch="*" makes S3 refuse to replace an existing key; Object Lock keeps
        # every version from being deleted or overwritten until the retention date.
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            **extra,
            IfNoneMatch="*",
            ObjectLockMode=self.lock_mode,
            ObjectLockRetainUntilDate=now + self.retention,
            ChecksumAlgorithm="SHA256",
        )


class MemoryStore:
    """In-memory store for tests and local dry runs. Refuses overwrites like S3Store."""

    def __init__(self, state: dict | None = None):
        self.state = state
        self.objects: dict[str, tuple[bytes, dict[str, str]]] = {}
        self.receipts: dict[str, bytes] = {}
        self.state_writes = 0

    def read_state(self) -> dict | None:
        return None if self.state is None else dict(self.state)

    def write_state(self, state: dict) -> None:
        self.state = dict(state)
        self.state_writes += 1

    def put_snapshot(self, key: str, body: bytes, metadata: dict[str, str], now: datetime) -> None:
        if key in self.objects:
            raise FileExistsError(key)
        self.objects[key] = (body, dict(metadata))

    def put_receipt(self, key: str, body: bytes, now: datetime) -> None:
        if key in self.receipts:
            raise FileExistsError(key)
        self.receipts[key] = body
