import io

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from nightly.bucket import ConditionFailed, Item, MemoryBucket, S3Bucket


@pytest.fixture
def s3():
    client = boto3.client("s3", region_name="il-central-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    with Stubber(client) as stub:
        yield S3Bucket(client, "b"), stub
        stub.assert_no_pending_responses()


def body(data: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(data), len(data))


def test_list_reads_every_page(s3):
    bucket, stub = s3
    stub.add_response("list_objects_v2",
                      {"Contents": [{"Key": "raw/b", "Size": 4}], "IsTruncated": True, "NextContinuationToken": "t"},
                      {"Bucket": "b", "Prefix": "raw/"})
    stub.add_response("list_objects_v2", {"Contents": [{"Key": "raw/a", "Size": 3}], "IsTruncated": False},
                      {"Bucket": "b", "Prefix": "raw/", "ContinuationToken": "t"})
    assert bucket.list("raw/") == [Item("raw/a", 3), Item("raw/b", 4)]


def test_an_empty_prefix_lists_nothing(s3):
    bucket, stub = s3
    stub.add_response("list_objects_v2", {"IsTruncated": False, "KeyCount": 0}, {"Bucket": "b", "Prefix": "models/"})
    assert bucket.list("models/") == []


def test_download_asks_for_the_checksum_and_writes_the_body(s3, tmp_path):
    """The collector stores every object with a SHA-256 checksum; asking for it makes botocore check the reply."""
    bucket, stub = s3
    data = b"\x1f\x8b gzipped page"
    stub.add_response("get_object", {"Body": body(data)}, {"Bucket": "b", "Key": "raw/k", "ChecksumMode": "ENABLED"})
    bucket.download("raw/k", tmp_path / "k")
    assert (tmp_path / "k").read_bytes() == data


def test_read_returns_the_body_and_its_etag(s3):
    bucket, stub = s3
    stub.add_response("get_object", {"Body": body(b'{"a": 1}'), "ETag": '"e1"'},
                      {"Bucket": "b", "Key": "latest.json", "ChecksumMode": "ENABLED"})
    assert bucket.read("latest.json") == (b'{"a": 1}', '"e1"')


@pytest.mark.parametrize("code", ["NoSuchKey", "404"])
def test_a_missing_key_reads_as_none(s3, code):
    bucket, stub = s3
    stub.add_client_error("get_object", service_error_code=code, http_status_code=404,
                          expected_params={"Bucket": "b", "Key": "latest.json", "ChecksumMode": "ENABLED"})
    assert bucket.read("latest.json") is None


def test_access_denied_is_not_hidden(s3):
    bucket, stub = s3
    stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)
    with pytest.raises(ClientError, match="AccessDenied"):
        bucket.read("latest.json")


@pytest.mark.parametrize("key, content_type", [("models/x/flights.parquet", "application/octet-stream"),
                                               ("latest.json", "application/json")])
def test_put_new_is_write_once(s3, key, content_type):
    bucket, stub = s3
    stub.add_response("put_object", {}, {"Bucket": "b", "Key": key, "Body": b"data", "ContentType": content_type,
                                         "IfNoneMatch": "*", "ChecksumAlgorithm": "SHA256"})
    bucket.put_new(key, b"data")


def test_replace_carries_the_etag(s3):
    bucket, stub = s3
    stub.add_response("put_object", {}, {"Bucket": "b", "Key": "latest.json", "Body": b"{}",
                                         "ContentType": "application/json", "IfMatch": '"e1"',
                                         "ChecksumAlgorithm": "SHA256"})
    bucket.replace("latest.json", b"{}", '"e1"')


@pytest.mark.parametrize("code, status", [("PreconditionFailed", 412), ("ConditionalRequestConflict", 409)])
@pytest.mark.parametrize("write", [lambda b: b.put_new("latest.json", b"{}"),
                                   lambda b: b.replace("latest.json", b"{}", '"e1"')], ids=["put_new", "replace"])
def test_a_refused_condition_is_condition_failed(s3, write, code, status):
    bucket, stub = s3
    stub.add_client_error("put_object", service_error_code=code, http_status_code=status)
    with pytest.raises(ConditionFailed, match="latest.json") as refused:
        write(bucket)
    assert isinstance(refused.value.__cause__, ClientError)


def test_other_write_errors_are_not_hidden(s3):
    bucket, stub = s3
    stub.add_client_error("put_object", service_error_code="AccessDenied", http_status_code=403)
    with pytest.raises(ClientError, match="AccessDenied"):
        bucket.put_new("latest.json", b"{}")


def test_delete_names_one_key(s3):
    bucket, stub = s3
    stub.add_response("delete_object", {}, {"Bucket": "b", "Key": "models/old/flights.parquet"})
    bucket.delete("models/old/flights.parquet")


def test_the_memory_bucket_answers_as_s3_does(tmp_path):
    given = {"models/b/y.parquet": b"de", "models/a/x.parquet": b"abc", "latest.json": b"{}",
             "modelsx": b"not under models/"}
    bucket = MemoryBucket(objects=given)
    assert bucket.name == "memory"
    assert MemoryBucket("archive").objects == {}

    # write-once: an existing key is refused and nothing changes, the ETag included
    first = bucket.read("latest.json")
    with pytest.raises(ConditionFailed, match="latest.json"):
        bucket.put_new("latest.json", b"new")
    assert bucket.read("latest.json") == first
    bucket.put_new("models/c/z.parquet", b"z")
    assert bucket.objects["models/c/z.parquet"] == b"z"
    assert "models/c/z.parquet" not in given  # the bucket keeps its own copy of what it was given

    # If-Match: only while the ETag is the one read; every write changes it
    body, etag = first
    bucket.replace("latest.json", b"v2", etag)
    second = bucket.read("latest.json")
    assert second[0] == b"v2" and second[1] != etag
    with pytest.raises(ConditionFailed, match="latest.json"):
        bucket.replace("latest.json", b"v3", etag)
    assert bucket.read("latest.json") == second
    # If-Match on a missing key: S3 answers 404, not a refused condition, and nothing changes
    before = dict(bucket.objects)
    with pytest.raises(ClientError, match="NoSuchKey") as missing:
        bucket.replace("missing.json", b"x", second[1])
    assert missing.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    assert not isinstance(missing.value, ConditionFailed)
    assert bucket.objects == before and bucket.read("latest.json") == second

    # a missing key reads as None; a download of one fails as S3's does
    assert bucket.read("missing.json") is None
    with pytest.raises(ClientError, match="NoSuchKey") as missing:
        bucket.download("missing.json", tmp_path / "missing.json")
    assert missing.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404

    # one prefix's keys, in key order, with their sizes
    assert bucket.list("models/") == [Item("models/a/x.parquet", 3), Item("models/b/y.parquet", 2),
                                      Item("models/c/z.parquet", 1)]
    bucket.delete("models/c/z.parquet")
    bucket.delete("models/c/z.parquet")  # S3 answers a delete of a missing key without an error
    assert bucket.list("models/") == [Item("models/a/x.parquet", 3), Item("models/b/y.parquet", 2)]
    assert bucket.list("raw/") == []

    # every call, in order
    assert bucket.ops == [("read", "latest.json"), ("put_new", "latest.json"), ("read", "latest.json"),
                          ("put_new", "models/c/z.parquet"), ("replace", "latest.json"), ("read", "latest.json"),
                          ("replace", "latest.json"), ("read", "latest.json"), ("replace", "missing.json"),
                          ("read", "latest.json"), ("read", "missing.json"), ("download", "missing.json"), ("list", "models/"),
                          ("delete", "models/c/z.parquet"), ("delete", "models/c/z.parquet"), ("list", "models/"),
                          ("list", "raw/")]

    # a fail list raises once per call, first to last, and then lets the call through
    bucket.ops.clear()
    target = tmp_path / "x.parquet"
    bucket.fail[("download", "models/a/x.parquet")] = [OSError("reset"), OSError("again")]
    with pytest.raises(OSError, match="reset"):
        bucket.download("models/a/x.parquet", target)
    with pytest.raises(OSError, match="again"):
        bucket.download("models/a/x.parquet", target)
    assert not target.exists()
    bucket.download("models/a/x.parquet", target)
    assert target.read_bytes() == b"abc"
    assert bucket.ops == [("download", "models/a/x.parquet")] * 3

    # a short download writes one byte fewer
    bucket.short.add("models/b/y.parquet")
    bucket.download("models/b/y.parquet", tmp_path / "y.parquet")
    assert (tmp_path / "y.parquet").read_bytes() == b"d"

    # a hook runs once, before its operation
    runs = []

    def another_run_writes():
        runs.append("hook")
        bucket.force("latest.json", b"forced")

    bucket.hooks[("read", "latest.json")] = another_run_writes
    assert bucket.read("latest.json")[0] == b"forced"
    assert bucket.read("latest.json")[0] == b"forced"
    assert len(runs) == 1 and bucket.hooks == {}

    # force writes as another run would: a new ETag, and no entry in ops
    bucket.ops.clear()
    body, etag = bucket.read("latest.json")
    bucket.force("latest.json", b"another run")
    bucket.force("models/d/new.parquet", b"n")
    with pytest.raises(ConditionFailed):
        bucket.replace("latest.json", b"mine", etag)
    assert bucket.objects["latest.json"] == b"another run"
    assert bucket.objects["models/d/new.parquet"] == b"n"
    assert bucket.ops == [("read", "latest.json"), ("replace", "latest.json")]
