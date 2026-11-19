"""The S3 calls the nightly build makes, and an in-memory bucket that answers as S3 does, for the tests.

Every upload is conditional (docs/nightly-model.md, section 4): a new key only if no object has it (If-None-Match),
the pointer replaced only while it is still the object just read (If-Match). S3 refuses either with 412
PreconditionFailed, or with 409 ConditionalRequestConflict when another write raced it; both become ConditionFailed.
"""
from __future__ import annotations

import itertools
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, NamedTuple, Protocol

from botocore.exceptions import ClientError

MISSING_CODES = ("NoSuchKey", "404")
CONDITION_CODES = ("PreconditionFailed", "ConditionalRequestConflict")
CHUNK = 1024 * 1024  # bytes read at a time from a download's body


class Item(NamedTuple):
    key: str
    size: int


class ConditionFailed(Exception):
    """S3 refused a conditional write: 412 PreconditionFailed or 409 ConditionalRequestConflict."""


class Bucket(Protocol):
    name: str

    def list(self, prefix: str) -> list[Item]: ...  # every object under the prefix, in key order
    def download(self, key: str, path: Path) -> None: ...
    def read(self, key: str) -> tuple[bytes, str] | None: ...  # the body and its ETag; None when the key is missing
    def put_new(self, key: str, body: bytes) -> None: ...  # write-once: ConditionFailed when the key exists or raced
    def replace(self, key: str, body: bytes, etag: str) -> None: ...  # only while the ETag is `etag`
    def delete(self, key: str) -> None: ...


def _code(err: ClientError) -> str | None:
    return err.response.get("Error", {}).get("Code")


def _content_type(key: str) -> str:
    return "application/json" if key.endswith(".json") else "application/octet-stream"


@contextmanager
def _conditional(key: str):
    """A refused condition raised as ConditionFailed; any other error as it is."""
    try:
        yield
    except ClientError as err:
        if _code(err) in CONDITION_CODES:
            raise ConditionFailed(f"{key}: {_code(err)}") from err
        raise


class S3Bucket:
    """The protocol on a boto3 S3 client."""

    def __init__(self, client, name: str):
        self.client = client
        self.name = name

    def list(self, prefix: str) -> list[Item]:
        args = {"Bucket": self.name, "Prefix": prefix}
        items = []
        while True:
            page = self.client.list_objects_v2(**args)
            items += [Item(obj["Key"], obj["Size"]) for obj in page.get("Contents", [])]
            if not page.get("IsTruncated"):
                break
            args["ContinuationToken"] = page["NextContinuationToken"]
        return sorted(items)

    def download(self, key: str, path: Path) -> None:
        # ChecksumMode asks for the checksum stored with the object; botocore raises once a body that does not match
        # it is read to its end. Named here so the check holds whatever response_checksum_validation is set to.
        reply = self.client.get_object(Bucket=self.name, Key=key, ChecksumMode="ENABLED")
        with open(path, "wb") as out:
            for chunk in reply["Body"].iter_chunks(CHUNK):
                out.write(chunk)

    def read(self, key: str) -> tuple[bytes, str] | None:
        try:
            obj = self.client.get_object(Bucket=self.name, Key=key, ChecksumMode="ENABLED")
        except ClientError as err:
            if _code(err) in MISSING_CODES:
                return None
            raise
        return obj["Body"].read(), obj["ETag"]

    def put_new(self, key: str, body: bytes) -> None:
        with _conditional(key):
            self.client.put_object(Bucket=self.name, Key=key, Body=body, ContentType=_content_type(key),
                                   IfNoneMatch="*", ChecksumAlgorithm="SHA256")

    def replace(self, key: str, body: bytes, etag: str) -> None:
        with _conditional(key):
            self.client.put_object(Bucket=self.name, Key=key, Body=body, ContentType=_content_type(key),
                                   IfMatch=etag, ChecksumAlgorithm="SHA256")

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.name, Key=key)


class MemoryBucket:
    """The protocol in memory, for tests. It refuses what S3 refuses, and lets a test fail a call, shorten a
    download, run something just before a call, or write as another run would."""

    def __init__(self, name: str = "memory", objects: dict[str, bytes] | None = None):
        self.name = name
        self.objects: dict[str, bytes] = dict(objects or {})
        self.ops: list[tuple[str, str]] = []  # (operation, key or prefix) for each call, in order
        self.fail: dict[tuple[str, str], list[BaseException]] = {}  # each call raises, and removes, the first
        self.short: set[str] = set()  # keys whose download writes one byte fewer
        self.hooks: dict[tuple[str, str], Callable[[], None]] = {}  # called once, then removed, before the call
        self._versions = itertools.count(1)
        self._etags: dict[str, str] = {}

    def _new_etag(self) -> str:
        return f'"m{next(self._versions)}"'

    def _etag(self, key: str) -> str:
        """The key's ETag, given on first use to an object the bucket was made with or a test put in `objects`."""
        if key not in self._etags:
            self._etags[key] = self._new_etag()
        return self._etags[key]

    def _call(self, op: str, key: str) -> None:
        self.ops.append((op, key))
        hook = self.hooks.pop((op, key), None)
        if hook is not None:
            hook()
        errors = self.fail.get((op, key))
        if errors:
            raise errors.pop(0)

    def _write(self, key: str, body: bytes) -> None:
        self.objects[key] = body
        self._etags[key] = self._new_etag()

    def list(self, prefix: str) -> list[Item]:
        self._call("list", prefix)
        return [Item(key, len(self.objects[key])) for key in sorted(self.objects) if key.startswith(prefix)]

    def download(self, key: str, path: Path) -> None:
        self._call("download", key)
        if key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": key}}, "GetObject")
        body = self.objects[key]
        path.write_bytes(body[:-1] if key in self.short else body)

    def read(self, key: str) -> tuple[bytes, str] | None:
        self._call("read", key)
        if key not in self.objects:
            return None
        return self.objects[key], self._etag(key)

    def put_new(self, key: str, body: bytes) -> None:
        self._call("put_new", key)
        if key in self.objects:
            raise ConditionFailed(f"{key}: PreconditionFailed")
        self._write(key, body)

    def replace(self, key: str, body: bytes, etag: str) -> None:
        self._call("replace", key)
        if key not in self.objects or self._etag(key) != etag:
            raise ConditionFailed(f"{key}: PreconditionFailed")
        self._write(key, body)

    def delete(self, key: str) -> None:
        self._call("delete", key)
        self.objects.pop(key, None)
        self._etags.pop(key, None)

    def force(self, key: str, body: bytes) -> None:
        """Write as another run would: a new ETag, and no entry in `ops`."""
        self._write(key, body)
