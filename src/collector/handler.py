"""AWS Lambda entry point. EventBridge Scheduler calls handler() every 2 minutes.

Manual events:
  {"drill": true}    fail on purpose without calling data.gov.il, to prove alerts work
  {"unblock": true}  clear the block latch after a person has checked what happened
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import partial
from typing import Callable

from . import core

log = logging.getLogger()
log.setLevel(logging.INFO)


@dataclass(frozen=True)
class Config:
    bucket: str
    user_agent: str
    healthcheck_url: str = ""
    retention_days: int = 3650
    page_size: int = 10000

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "Config":
        missing = [k for k in ("BUCKET", "USER_AGENT") if not env.get(k, "").strip()]
        if missing:
            raise ValueError(f"missing environment variables: {missing}")
        core.check_user_agent(env["USER_AGENT"])
        return cls(
            bucket=env["BUCKET"],
            user_agent=env["USER_AGENT"],
            healthcheck_url=env.get("HEALTHCHECK_URL", "").rstrip("/"),
            retention_days=int(env.get("RETENTION_DAYS", "3650")),
            page_size=int(env.get("PAGE_SIZE", "10000")),
        )


class DrillError(core.CollectorError):
    """Raised on purpose by a {"drill": true} event, to prove the alerts fire."""


def parse_event(event) -> str:
    """Return "drill", "unblock" or "collect". Only an exact `true` triggers a manual mode."""
    if isinstance(event, dict):
        if event.get("drill") is True:
            return "drill"
        if event.get("unblock") is True:
            return "unblock"
    return "collect"


def ping(url: str, message: str, user_agent: str) -> None:
    """Report to healthchecks.io. A failed ping is logged, never fatal."""
    if not url:
        return
    try:
        req = urllib.request.Request(url, data=message.encode()[:10000], headers={"User-Agent": user_agent})
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as err:  # noqa: BLE001 - monitoring must not break collection
        log.warning("healthcheck ping failed: %s", err)


def run(cfg: Config, fetch: core.Fetcher, store: core.Store, now: datetime,
        pinger: Callable[[str, str], None], mode: str = "collect") -> dict:
    fail_url = f"{cfg.healthcheck_url}/fail" if cfg.healthcheck_url else ""
    if mode == "unblock":
        cleared = core.clear_block(store)
        summary = {"action": "unblocked" if cleared else "was-not-blocked"}
        log.info(json.dumps(summary))
        return summary
    try:
        if mode == "drill":
            raise DrillError("alert drill: nothing was fetched or stored")
        outcome = core.run_once(fetch, store, now, page_size=cfg.page_size)
    except core.BlockedError as err:
        log.error("BLOCKED: %s", err)
        pinger(fail_url, f"BLOCKED: {err}")
        raise
    except DrillError as err:
        log.error("drill: %s", err)
        pinger(fail_url, f"DrillError: {err}")
        raise
    except Exception as err:
        # No /fail ping: healthchecks.io's grace period decides whether a run of errors is an
        # outage, so one slow reply stays quiet.
        log.error("collector failed: %s", err)
        raise
    summary = asdict(outcome) | {"code_sha256": core.CODE_SHA256}  # which code wrote this run's receipt
    log.info(json.dumps(summary))
    pinger(cfg.healthcheck_url, json.dumps(summary))
    return summary


def handler(event, context):  # pragma: no cover - thin AWS wiring, covered by run() and parse_event()
    import boto3

    from .store import S3Store

    cfg = Config.from_env(dict(os.environ))
    store = S3Store(boto3.client("s3"), cfg.bucket, cfg.retention_days)
    fetch = partial(core.http_get, user_agent=cfg.user_agent)
    pinger = partial(ping, user_agent=cfg.user_agent)
    return run(cfg, fetch, store, core.utcnow(), lambda url, msg: pinger(url, msg), mode=parse_event(event))
