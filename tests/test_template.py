"""Pin the infrastructure settings the collector's safety depends on.

cfn-lint checks the template is valid, but it doesn't catch a misspelled SAM
event property or a quietly changed retry count, so these settings are
asserted directly.
"""
import re
from pathlib import Path

import pytest
from cfnlint.decode import decode

TEMPLATE = Path(__file__).parent.parent / "template.yaml"


@pytest.fixture(scope="module")
def resources():
    template, matches = decode(str(TEMPLATE))
    assert not matches, matches
    return template["Resources"]


def test_no_retries_anywhere(resources):
    fn = resources["CollectorFunction"]["Properties"]
    assert fn["EventInvokeConfig"] == {"MaximumRetryAttempts": 0}
    event = fn["Events"]["EveryTwoMinutes"]
    assert event["Type"] == "ScheduleV2"
    assert event["Properties"]["ScheduleExpression"] == "rate(2 minutes)"
    assert event["Properties"]["RetryPolicy"] == {"MaximumRetryAttempts": 0}


def test_schedule_starts_switched_off(resources):
    template, _ = decode(str(TEMPLATE))
    param = template["Parameters"]["ScheduleState"]
    assert param["Default"] == "DISABLED" and sorted(param["AllowedValues"]) == ["DISABLED", "ENABLED"]
    event = resources["CollectorFunction"]["Properties"]["Events"]["EveryTwoMinutes"]["Properties"]
    assert event["State"] == {"Ref": "ScheduleState"}


def test_timeout_fits_inside_the_schedule(resources):
    assert 60 <= resources["CollectorFunction"]["Properties"]["Timeout"] < 120


def test_timeout_covers_the_slowest_honest_run(resources):
    """Status check + download + ping + 15 s for S3 and startup must fit, or a slow data.gov.il
    becomes a Lambda timeout instead of a clean CollectorError. The status check needs 20 s:
    10 s timed out twice right after the board's 13:01Z refresh on 2026-10-29."""
    from collector import core
    assert core.SHOW_TIMEOUT >= 20
    budget = core.SHOW_TIMEOUT + core.SEARCH_TIMEOUT + 10 + 15
    assert budget <= resources["CollectorFunction"]["Properties"]["Timeout"]


def test_user_agent_parameter_refuses_a_value_without_url_and_email(resources):
    template, _ = decode(str(TEMPLATE))
    pattern = template["Parameters"]["UserAgent"]["AllowedPattern"]
    assert re.fullmatch(pattern, "flights-archive/0.1 (+https://github.com/x/y; me@example.org)")
    assert not re.fullmatch(pattern, "flights-archive/0.1")  # what a space-split parameter override leaves


def test_bucket_is_locked_private_and_versioned(resources):
    bucket = resources["ArchiveBucket"]
    props = bucket["Properties"]
    assert bucket["DeletionPolicy"] == "Retain"
    assert props["ObjectLockEnabled"] is True
    assert props["VersioningConfiguration"] == {"Status": "Enabled"}
    assert all(props["PublicAccessBlockConfiguration"].values())
    assert "ObjectLockConfiguration" not in props  # no default retention, so state writes stay unlocked


def test_function_cannot_delete_or_bypass_locks(resources):
    statements = resources["CollectorFunction"]["Properties"]["Policies"][0]["Statement"]
    actions = {a for s in statements for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])}
    assert actions == {"s3:PutObject", "s3:PutObjectRetention", "s3:GetObject", "s3:ListBucket"}
    listing = next(s for s in statements if s["Action"] == "s3:ListBucket")
    assert "Condition" not in listing


def test_logs_go_to_a_group_created_first(resources):
    fn = resources["CollectorFunction"]["Properties"]
    assert fn["LoggingConfig"]["LogGroup"] == {"Ref": "CollectorLogs"}
    assert resources["CollectorLogs"]["Properties"]["RetentionInDays"] == 30


def test_only_snapshots_and_receipts_are_written_locked(resources):
    """The collector writes locked objects under raw/ and receipts/ only; state/ is the one key it reads and rewrites."""
    statements = resources["CollectorFunction"]["Properties"]["Policies"][0]["Statement"]
    by_sid = {s["Sid"]: s for s in statements}
    locked = by_sid["WriteOnceArchive"]
    assert sorted(locked["Action"]) == ["s3:PutObject", "s3:PutObjectRetention"]
    assert locked["Resource"] == [{"Fn::Sub": "${ArchiveBucket.Arn}/raw/*"}, {"Fn::Sub": "${ArchiveBucket.Arn}/receipts/*"}]
    assert by_sid["ReadWriteState"]["Resource"] == {"Fn::Sub": "${ArchiveBucket.Arn}/state/*"}
