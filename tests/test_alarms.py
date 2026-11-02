"""Pin the two alarms and tie their log patterns to the lines the collector writes (docs/alarms.md).

CloudWatch matches a quoted term anywhere in an unstructured log event, case-sensitively, with \\" read as
a literal double quote: measured with `aws logs test-metric-filter` on real collector lines, 2026-11-02.
The tests below apply that rule to what `handler.run` logs, so a change to the log format or to a
pattern that would silence an alarm fails here.
"""
import logging
from datetime import timedelta
from pathlib import Path

import pytest
from cfnlint.decode import decode

from collector import core
from collector.handler import Config, DrillError, run
from collector.store import MemoryStore
from conftest import FakeAPI

TEMPLATE = Path(__file__).parent.parent / "template.yaml"
RECEIPT_PATTERN = '"\\"receipt\\": \\"receipts/"'  # the characters CloudFormation must send
BLOCKED_PATTERN = '"BLOCKED:"'


def filter_matches(pattern: str, event: str) -> bool:
    """CloudWatch's rule for one quoted term in an unstructured event, as measured."""
    assert pattern.startswith('"') and pattern.endswith('"') and len(pattern) > 2, pattern
    term = pattern[1:-1]
    assert '"' not in term.replace('\\"', ""), f"not exactly one quoted term: {pattern}"
    return term.replace('\\"', '"') in event


def lambda_event(record: logging.LogRecord) -> str:
    """How Lambda's Python runtime writes a log record in Text format."""
    return f"[{record.levelname}]\t2026-10-30T08:00:00.000Z\t816ae84e-c86f-4fd4-98fc-fb50a1df375e\t{record.getMessage()}\n"


def cfg() -> Config:
    return Config(bucket="b", user_agent="ua", healthcheck_url="https://hc-ping.com/abc")


def logged(caplog, action) -> list[str]:
    """The log events one run writes, as CloudWatch receives them."""
    caplog.clear()
    try:
        action()
    except core.CollectorError:
        pass
    return [lambda_event(r) for r in caplog.records]


def matching(pattern: str, events: list[str]) -> list[str]:
    return [e for e in events if filter_matches(pattern, e)]


@pytest.fixture(scope="module")
def resources():
    template, matches = decode(str(TEMPLATE))
    assert not matches, matches
    return template["Resources"]


@pytest.fixture(autouse=True)
def info_logs(caplog):
    caplog.set_level(logging.INFO)


# --- the resources --------------------------------------------------------------------------------

def test_error_alarm_is_gone(resources):
    assert "ErrorAlarm" not in resources


@pytest.mark.parametrize("name, pattern, metric", [
    ("ReceiptFilter", RECEIPT_PATTERN, "Receipts"),
    ("BlockedFilter", BLOCKED_PATTERN, "BlockedRuns"),
])
def test_filters_watch_the_collector_log_group(resources, name, pattern, metric):
    res = resources[name]
    assert res["Type"] == "AWS::Logs::MetricFilter"
    props = res["Properties"]
    assert props["LogGroupName"] == {"Ref": "CollectorLogs"}
    assert props["FilterPattern"] == pattern
    assert props["MetricTransformations"] == [
        {"MetricNamespace": "flights-archive", "MetricName": metric, "MetricValue": "1", "DefaultValue": 0}]


def test_missed_refresh_alarm(resources):
    alarm = resources["MissedRefreshAlarm"]["Properties"]
    assert (alarm["Namespace"], alarm["MetricName"], alarm["Statistic"]) == ("flights-archive", "Receipts", "Sum")
    assert (alarm["Period"], alarm["EvaluationPeriods"], alarm["DatapointsToAlarm"]) == (60, 35, 35)
    assert (alarm["Threshold"], alarm["ComparisonOperator"]) == (1, "LessThanThreshold")
    assert alarm["TreatMissingData"] == "breaching"  # no log lines at all counts as no receipt
    assert "Dimensions" not in alarm


def test_blocked_alarm(resources):
    alarm = resources["BlockedAlarm"]["Properties"]
    assert (alarm["Namespace"], alarm["MetricName"], alarm["Statistic"]) == ("flights-archive", "BlockedRuns", "Sum")
    assert (alarm["Period"], alarm["EvaluationPeriods"], alarm["DatapointsToAlarm"]) == (300, 1, 1)
    assert (alarm["Threshold"], alarm["ComparisonOperator"]) == (1, "GreaterThanOrEqualToThreshold")
    assert alarm["TreatMissingData"] == "notBreaching"
    assert "Dimensions" not in alarm


@pytest.mark.parametrize("alarm, filter_", [("MissedRefreshAlarm", "ReceiptFilter"), ("BlockedAlarm", "BlockedFilter")])
def test_each_alarm_watches_its_filters_metric(resources, alarm, filter_):
    props = resources[alarm]["Properties"]
    transform = resources[filter_]["Properties"]["MetricTransformations"][0]
    assert (props["Namespace"], props["MetricName"]) == (transform["MetricNamespace"], transform["MetricName"])


@pytest.mark.parametrize("alarm", ["MissedRefreshAlarm", "BlockedAlarm"])
def test_alarms_email_on_alarm_and_on_ok(resources, alarm):
    props = resources[alarm]["Properties"]
    assert props["AlarmActions"] == [{"Ref": "AlertTopic"}]
    assert props["OKActions"] == [{"Ref": "AlertTopic"}]
    assert "ActionsEnabled" not in props  # default true: the emails are on from the deploy


def test_alarm_descriptions_point_to_the_blocked_steps(resources):
    missed = resources["MissedRefreshAlarm"]["Properties"]["AlarmDescription"]
    blocked = resources["BlockedAlarm"]["Properties"]["AlarmDescription"]
    assert "docs/operations.md" in missed and "docs/operations.md" in blocked
    assert "35 minutes" in missed


# --- the patterns against what the collector logs ---------------------------------------------------

def test_receipt_runs_match_only_the_receipt_filter(records, now, caplog):
    api, store = FakeAPI(records), MemoryStore()
    stored = logged(caplog, lambda: run(cfg(), api, store, now, lambda u, m: None))
    unchanged = logged(caplog, lambda: run(cfg(), api, store, now + timedelta(minutes=31), lambda u, m: None))
    skipped = logged(caplog, lambda: run(cfg(), api, store, now + timedelta(minutes=33), lambda u, m: None))
    assert '"action": "stored"' in "".join(stored) and '"action": "unchanged"' in "".join(unchanged)
    assert '"action": "skipped"' in "".join(skipped)
    for events in (stored, unchanged):
        assert matching(RECEIPT_PATTERN, events) and not matching(BLOCKED_PATTERN, events)
    assert not matching(RECEIPT_PATTERN, skipped) and not matching(BLOCKED_PATTERN, skipped)


def test_block_lines_match_only_the_blocked_filter(records, now, blocked_html, caplog):
    api, store = FakeAPI(records), MemoryStore()
    api.overrides["resource_show"] = core.Response(403, blocked_html, "text/html", 1)
    blocked = logged(caplog, lambda: run(cfg(), api, store, now, lambda u, m: None))
    latched = logged(caplog, lambda: run(cfg(), api, store, now + timedelta(minutes=2), lambda u, m: None))
    assert store.state["blocked"] and "latched off" in "".join(latched)
    for events in (blocked, latched):
        assert matching(BLOCKED_PATTERN, events) and not matching(RECEIPT_PATTERN, events)


def test_other_failures_match_neither(records, now, caplog):
    def drill():
        with pytest.raises(DrillError):
            run(cfg(), FakeAPI(records), MemoryStore(), now, lambda u, m: None, mode="drill")

    drilled = logged(caplog, drill)
    failed = logged(caplog, lambda: run(cfg(), FakeAPI([]), MemoryStore(), now, lambda u, m: None))
    assert "drill: " in "".join(drilled) and "collector failed: " in "".join(failed)
    for events in (drilled, failed):
        assert not matching(RECEIPT_PATTERN, events) and not matching(BLOCKED_PATTERN, events)


def test_a_traceback_quoting_the_source_matches_neither():
    events = [
        '[ERROR] CollectorError: x\nTraceback (most recent call last):\n\xa0\xa0File "/var/task/collector/core.py",'
        ' line 314, in _collect\n\xa0\xa0\xa0\xa0receipt_key = f"receipts/date={now:%Y-%m-%d}/{now:%H%M%S}Z-{digest[:12]}.json"\n',
        "[ERROR] BlockedError: resource_show: HTTP 403\nTraceback (most recent call last):\n",
    ]
    assert not matching(RECEIPT_PATTERN, events) and not matching(BLOCKED_PATTERN, events)
