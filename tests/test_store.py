import io
import json
from datetime import timedelta

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from collector.store import STATE_KEY, S3Store


@pytest.fixture
def s3():
    client = boto3.client("s3", region_name="il-central-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    with Stubber(client) as stub:
        yield client, stub
        stub.assert_no_pending_responses()


def test_snapshot_put_is_write_once_and_locked(s3, now):
    client, stub = s3
    stub.add_response("put_object", {}, {
        "Bucket": "b", "Key": "raw/k.json.gz", "Body": b"gz", "ContentType": "application/gzip",
        "Metadata": {"rows": "1"}, "IfNoneMatch": "*", "ObjectLockMode": "GOVERNANCE",
        "ObjectLockRetainUntilDate": now + timedelta(days=30), "ChecksumAlgorithm": "SHA256",
    })
    S3Store(client, "b", retention_days=30).put_snapshot("raw/k.json.gz", b"gz", {"rows": "1"}, now)


def test_existing_key_is_not_overwritten(s3, now):
    client, stub = s3
    stub.add_client_error("put_object", service_error_code="PreconditionFailed", http_status_code=412)
    with pytest.raises(client.exceptions.ClientError, match="PreconditionFailed"):
        S3Store(client, "b", retention_days=30).put_snapshot("raw/k", b"gz", {}, now)


def test_missing_state_reads_as_none(s3):
    client, stub = s3
    stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    assert S3Store(client, "b", retention_days=30).read_state() is None


def test_access_denied_on_state_is_not_hidden(s3):
    client, stub = s3
    stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)
    with pytest.raises(client.exceptions.ClientError):
        S3Store(client, "b", retention_days=30).read_state()


def test_state_round_trip(s3):
    client, stub = s3
    state = {"last_modified": "x", "sha256": "y"}
    body = json.dumps(state, sort_keys=True).encode()
    stub.add_response("put_object", {}, {"Bucket": "b", "Key": STATE_KEY, "Body": body,
                                         "ContentType": "application/json"})
    stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(body), len(body))},
                      {"Bucket": "b", "Key": STATE_KEY})
    store = S3Store(client, "b", retention_days=30)
    store.write_state(state)
    assert store.read_state() == state


def test_retention_must_be_positive(s3):
    client, _ = s3
    with pytest.raises(ValueError):
        S3Store(client, "b", retention_days=0)


def test_missing_state_as_plain_404_reads_as_none(s3):
    client, stub = s3
    stub.add_client_error("get_object", service_error_code="404", http_status_code=404)
    assert S3Store(client, "b", retention_days=30).read_state() is None
