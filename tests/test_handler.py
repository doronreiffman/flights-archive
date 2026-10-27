import json

import pytest

from collector import core
from collector.handler import Config, DrillError, parse_event, ping, run
from collector.store import MemoryStore
from conftest import FakeAPI


def cfg(**kw):
    return Config(bucket="b", user_agent="ua", healthcheck_url="https://hc-ping.com/abc", **kw)


def test_config_requires_bucket_and_user_agent():
    with pytest.raises(ValueError, match="USER_AGENT"):
        Config.from_env({"BUCKET": "b", "USER_AGENT": " "})


def test_config_defaults_and_trailing_slash():
    c = Config.from_env({"BUCKET": "b", "USER_AGENT": "ua", "HEALTHCHECK_URL": "https://hc-ping.com/abc/"})
    assert c.healthcheck_url == "https://hc-ping.com/abc" and c.retention_days == 3650 and c.page_size == 10000


@pytest.mark.parametrize("event, mode", [
    ({}, "collect"),
    (None, "collect"),
    ({"source": "aws.scheduler"}, "collect"),
    ({"drill": True}, "drill"),
    ({"drill": "true"}, "collect"),
    ({"unblock": True}, "unblock"),
    ({"unblock": 1}, "collect"),
])
def test_parse_event(event, mode):
    assert parse_event(event) == mode


def test_success_pings_the_check(records, now):
    pings = []
    out = run(cfg(), FakeAPI(records), MemoryStore(), now, lambda u, m: pings.append((u, m)))
    assert out["action"] == "stored"
    assert pings == [("https://hc-ping.com/abc", json.dumps(out))]


def test_failure_pings_fail_and_reraises(now):
    pings = []
    with pytest.raises(core.CollectorError):
        run(cfg(), FakeAPI([]), MemoryStore(), now, lambda u, m: pings.append((u, m)))
    assert pings[0][0] == "https://hc-ping.com/abc/fail" and "zero rows" in pings[0][1]


def test_block_is_flagged_loudly(records, now, blocked_html):
    api, pings = FakeAPI(records), []
    api.overrides["resource_show"] = core.Response(403, blocked_html, "text/html", 1)
    with pytest.raises(core.BlockedError):
        run(cfg(), api, MemoryStore(), now, lambda u, m: pings.append((u, m)))
    assert pings[0][0].endswith("/fail") and pings[0][1].startswith("BLOCKED")


def test_unblock_clears_the_latch_without_fetching(records, now):
    api, store = FakeAPI(records), MemoryStore({"blocked": {"at": "x", "reason": "y"}, "sha256": "s"})
    out = run(cfg(), api, store, now, lambda u, m: None, mode="unblock")
    assert out == {"action": "unblocked"} and api.calls == []
    assert store.state == {"sha256": "s"}
    assert run(cfg(), api, store, now, lambda u, m: None, mode="unblock") == {"action": "was-not-blocked"}


def test_drill_fails_loudly_without_touching_the_source(records, now):
    api, store, pings = FakeAPI(records), MemoryStore(), []
    with pytest.raises(DrillError):
        run(cfg(), api, store, now, lambda u, m: pings.append((u, m)), mode="drill")
    assert api.calls == [] and store.objects == {} and store.state is None
    assert pings[0][0].endswith("/fail") and "drill" in pings[0][1]


def test_no_healthcheck_url_means_no_fail_url(now):
    pings = []
    with pytest.raises(core.CollectorError):
        run(Config(bucket="b", user_agent="ua"), FakeAPI([]), MemoryStore(), now,
            lambda u, m: pings.append((u, m)))
    assert pings[0][0] == ""


def test_ping_failure_is_not_fatal(caplog):
    ping("http://127.0.0.1:9/", "hello", "ua")  # nothing listens on port 9
    assert "healthcheck ping failed" in caplog.text


def test_empty_ping_url_does_nothing():
    ping("", "hello", "ua")
