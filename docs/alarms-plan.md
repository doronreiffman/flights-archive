# Alarms (q20) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the collector's error alarm with two alarms that email only when board versions are being lost (no receipt for 35 minutes) or data.gov.il has blocked the collector.

**Architecture:** Two CloudWatch Logs metric filters on the collector's existing log group turn the run-summary line of a receipt-writing run and the `BLOCKED:` line into two custom metrics; two metric alarms watch them and email the existing SNS topic on ALARM and on OK. The collector's logic does not change; two stale texts in it do. A test ties each filter pattern to the log lines the code actually writes.

**Tech Stack:** AWS SAM / CloudFormation (`template.yaml`), CloudWatch Logs metric filters, CloudWatch alarms, Python 3.13, pytest, cfn-lint (`cfnlint.decode` in the tests), `scripts/mutation_check.py`.

**Spec:** `docs/alarms.md` (approved 2026-11-02). Grade: production-lean.

## Global Constraints

- AWS: profile `flights-sam`, region `il-central-1`, nothing else; `aws sts get-caller-identity --profile flights-sam` must show account 137953273942 and user doron-admin before any AWS call.
- Every AWS write (`sam deploy`, `set-alarm-state`, change-set execution) and every `git push` runs only on the owner's go in chat. Subagents run no AWS, `gh` or push commands.
- Work on branch `q20-alarms`; merge to `main` (fast-forward) after the final review; deploy from a clean, committed `main` (`git status --porcelain src/` prints nothing).
- The deploy passes `ScheduleState=ENABLED` (the template default is `DISABLED`).
- Patterns, exactly as CloudFormation must receive them: `"\"receipt\": \"receipts/"` and `"BLOCKED:"`.
- Namespace `flights-archive`; metric names `Receipts`, `BlockedRuns`; resource names `ReceiptFilter`, `BlockedFilter`, `MissedRefreshAlarm`, `BlockedAlarm`.
- Tests: `.venv/bin/python -m pytest` (pythonpath `src`, `tests` from `pyproject.toml`). Mutation check: `.venv/bin/python scripts/mutation_check.py`; it edits files in place, so nothing else runs from the checkout meanwhile. A new mutation counts only if it fails on an assertion: the runner counts any non-zero exit as caught, so check a new one by hand once (`pytest <files> -x` on the broken file shows an `AssertionError`, not an import or collection error).
- Public docs: no pointer to `.claude/`; the owner's first person only for the owner's decisions; agent choices marked "(provisional)".
- No change to any request the collector makes to data.gov.il.

## Review Focus

1. **YAML eats the backslashes.** A double-quoted YAML scalar for the receipt pattern parses to a different pattern than the one tested. Pinned in Task 1: the parsed value equals the exact string, and is one quoted term.
2. **A log-format change silences the alarm.** Changing `json.dumps(summary)` (separators, indent) or the `BLOCKED:` text breaks a pattern without failing any collector test. Pinned in Task 1 by the tie test and two mutations.
3. **A filter and its alarm drift apart.** A renamed metric leaves the missed-refresh alarm stuck in ALARM or the block alarm silent. Pinned in Task 1: each alarm's namespace and metric name equal its filter's.
4. **The deploy switches collection off or loses a hidden setting.** Leaving out `ScheduleState=ENABLED`, or a parameter not carried over (the healthchecks.io URL is `NoEcho`, so it cannot be read back). Pinned in Task 4: the change set's parameters are read before it runs.
5. **A traceback counts as a receipt.** Source lines quoted in an error event. Pinned in Task 1 (a traceback line quoting `core.py:314` matches neither pattern) and in Task 4 (real lines through `test-metric-filter`).

---

### Task 1: The alarm resources and their contract

**Files:**
- Modify: `template.yaml:20-21` (the `AlertEmail` description), `template.yaml:129-147` (remove `ErrorAlarm`; add the four resources after `AlertTopic`)
- Modify: `tests/test_template.py:61-64` (remove `test_alarm_needs_two_consecutive_bad_windows`)
- Create: `tests/test_alarms.py`
- Modify: `scripts/mutation_check.py` (two file specs, new entries, remove "alarm on one window")

**Interfaces:**
- Consumes: `collector.handler.run(cfg, fetch, store, now, pinger, mode)`, `Config`, `collector.store.MemoryStore`, fixtures `records`, `now`, `blocked_html` and `conftest.FakeAPI` (as `tests/test_handler.py` uses them).
- Produces: template resources `ReceiptFilter`, `BlockedFilter`, `MissedRefreshAlarm`, `BlockedAlarm`; in `tests/test_alarms.py` the helper `filter_matches(pattern: str, event: str) -> bool` and the fixture `resources`; mutation file specs `ALARMS = ("template.yaml", ["tests/test_template.py", "tests/test_alarms.py"])` and `HANDLER_LOGS = ("src/collector/handler.py", ["tests/test_handler.py", "tests/test_alarms.py"])`.

- [ ] **Step 1: Write the failing tests in `tests/test_alarms.py`**

The module docstring says what it pins: the alarm resources, and that each filter pattern matches the lines the collector writes and nothing else, under the matching rule measured with `aws logs test-metric-filter` on 2026-11-02 (`docs/alarms.md`).

```python
RECEIPT_PATTERN = '"\\"receipt\\": \\"receipts/"'   # the characters CloudFormation must send
BLOCKED_PATTERN = '"BLOCKED:"'

def filter_matches(pattern, event):
    """CloudWatch's rule for one quoted term in an unstructured event, as measured:
    case-sensitive, anywhere in the event, \\" is a literal quote."""
    assert pattern.startswith('"') and pattern.endswith('"') and len(pattern) > 2
    term = pattern[1:-1]
    assert '"' not in term.replace('\\"', "")      # exactly one quoted term
    return term.replace('\\"', '"') in event

def lambda_event(record):
    """How Lambda's Python runtime writes a log record in Text format."""
    return f"[{record.levelname}]\t2026-10-30T08:00:00.000Z\t816ae84e-c86f-4fd4-98fc-fb50a1df375e\t{record.getMessage()}\n"
```

Tests (names and assertions):

- `test_error_alarm_is_gone(resources)`: `"ErrorAlarm" not in resources`.
- `test_filters_watch_the_collector_log_group(resources)`: for `ReceiptFilter` and `BlockedFilter`: `Type == "AWS::Logs::MetricFilter"`, `LogGroupName == {"Ref": "CollectorLogs"}`, `FilterPattern` equals `RECEIPT_PATTERN` / `BLOCKED_PATTERN`, and `MetricTransformations == [{"MetricNamespace": "flights-archive", "MetricName": "Receipts" / "BlockedRuns", "MetricValue": "1", "DefaultValue": 0}]`.
- `test_missed_refresh_alarm(resources)`: `Namespace "flights-archive"`, `MetricName "Receipts"`, `Statistic "Sum"`, `Period 60`, `EvaluationPeriods 35`, `DatapointsToAlarm 35`, `Threshold 1`, `ComparisonOperator "LessThanThreshold"`, `TreatMissingData "breaching"`, no `Dimensions`.
- `test_blocked_alarm(resources)`: `BlockedRuns`, `Sum`, `Period 300`, `EvaluationPeriods 1`, `DatapointsToAlarm 1`, `Threshold 1`, `"GreaterThanOrEqualToThreshold"`, `"notBreaching"`, no `Dimensions`.
- `test_each_alarm_watches_its_filters_metric(resources)`: for (`MissedRefreshAlarm`, `ReceiptFilter`) and (`BlockedAlarm`, `BlockedFilter`): `(alarm.Namespace, alarm.MetricName) == (transform.MetricNamespace, transform.MetricName)`.
- `test_alarms_email_on_alarm_and_on_ok(resources)`: both alarms: `AlarmActions == [{"Ref": "AlertTopic"}]`, `OKActions == [{"Ref": "AlertTopic"}]`, `"ActionsEnabled" not in` properties (default true).
- `test_alarm_descriptions_point_to_the_blocked_steps(resources)`: both `AlarmDescription`s contain `"docs/operations.md"`; the missed-refresh one contains `"35 minutes"`.
- `test_receipt_runs_match_only_the_receipt_filter(records, now, caplog)`: run `handler.run` once (stored), then again at `now + timedelta(minutes=31)` on the same store and board (unchanged, since the 30-minute full download is due and the content is the same), then once at `now + timedelta(minutes=33)` (skipped). For each run, the events are `lambda_event(r)` for the run's `caplog.records`. Stored and unchanged: some event matches `RECEIPT_PATTERN`, none matches `BLOCKED_PATTERN`. Skipped: no event matches either.
- `test_block_lines_match_only_the_blocked_filter(records, now, blocked_html, caplog)`: a 403 run (as `test_block_is_flagged_loudly`) and the latched run after it each log an event matching `BLOCKED_PATTERN` and none matching `RECEIPT_PATTERN`.
- `test_other_failures_match_neither(records, now, caplog)`: the drill (`mode="drill"`) and an ordinary failure (`FakeAPI([])`, zero rows): no event matches either pattern.
- `test_a_traceback_quoting_the_source_matches_neither()`: these two events match neither pattern: `'[ERROR] CollectorError: x\nTraceback (most recent call last):\n\xa0\xa0File "/var/task/collector/core.py", line 314, in _collect\n\xa0\xa0\xa0\xa0receipt_key = f"receipts/date={now:%Y-%m-%d}/{now:%H%M%S}Z-{digest[:12]}.json"\n'` and `'[ERROR] BlockedError: resource_show: HTTP 403\nTraceback (most recent call last):\n'`.

The `resources` fixture loads `template.yaml` with `cfnlint.decode.decode` as `tests/test_template.py` does.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python -m pytest tests/test_alarms.py -v`
Expected: FAIL on every resource test (`KeyError` / `ErrorAlarm` present); the log-line tests that need no template may pass already, which is right: they pin today's log format.

- [ ] **Step 3: Change `template.yaml`**

- Remove `ErrorAlarm` (lines 129-147).
- `AlertEmail` description: `Gets an email when board versions are being lost or data.gov.il has blocked the collector.`
- `ReceiptFilter` and `BlockedFilter`: `AWS::Logs::MetricFilter`, values as in Step 1. Write the receipt pattern as a YAML single-quoted scalar: `FilterPattern: '"\"receipt\": \"receipts/"'`. Comment above each, one line: what it counts and that the pattern is tied to the log line by `tests/test_alarms.py`.
- `MissedRefreshAlarm`: values as in Step 1. `AlarmDescription: "No board download for 35 minutes: at least one 15-minute board version was missed. Read /flights-archive/collector; a BLOCKED line means stop and ask (docs/operations.md, If it's blocked)."` Comment: missing data counts as no receipt, so a collector that stops running sets it off too.
- `BlockedAlarm`: values as in Step 1. `AlarmDescription: "data.gov.il blocked the collector and it has stopped calling. Stop and ask; never work around a block (docs/operations.md, If it's blocked)."`
- Both: `AlarmActions` and `OKActions` `[!Ref AlertTopic]`.

- [ ] **Step 4: Remove the old test**

Delete `test_alarm_needs_two_consecutive_bad_windows` from `tests/test_template.py` (lines 61-64).

- [ ] **Step 5: Run the tests and see them pass**

Run: `.venv/bin/python -m pytest tests/test_alarms.py tests/test_template.py -v`
Expected: all PASS. Then `cfn-lint --regions il-central-1 template.yaml` (as CI runs it, `.github/workflows/ci.yml:21`): no output.

- [ ] **Step 6: Mutation entries**

In `scripts/mutation_check.py`, add the specs `ALARMS` and `HANDLER_LOGS` (Interfaces), delete `"alarm on one window"`, and add the entries below. Each old text must occur exactly once in its file, or the runner reports it STALE: `receipts/`, `MetricName: Receipts`, `TreatMissingData` and `OKActions` each appear more than once in `template.yaml`, so take the whole line or the neighbouring lines that make it unique.

| Name | Spec | Break |
|---|---|---|
| `alarm: receipt pattern double-quoted in YAML` | ALARMS | the single-quoted `FilterPattern` line → the same pattern as a YAML double-quoted scalar |
| `alarm: receipt pattern misses the key` | ALARMS | `receipts/` → `receipt/` in the pattern |
| `alarm: block pattern in the wrong case` | ALARMS | `"BLOCKED:"` → `"Blocked:"` |
| `alarm: receipt metric renamed in the filter` | ALARMS | the filter's `MetricName: Receipts` → `MetricName: Receipt` |
| `alarm: missed refresh compares <=` | ALARMS | `LessThanThreshold` → `LessThanOrEqualToThreshold` |
| `alarm: missed refresh ignores silence` | ALARMS | its `TreatMissingData: breaching` → `notBreaching` |
| `alarm: missed refresh after 5 minutes` | ALARMS | its `EvaluationPeriods: 35` + `DatapointsToAlarm: 35` → `5` + `5` |
| `alarm: block alarm fires on silence` | ALARMS | its `TreatMissingData: notBreaching` → `breaching` |
| `alarm: no email on OK` | ALARMS | one alarm's `OKActions` block removed |
| `alarm: summary logged compact` | HANDLER_LOGS | `    log.info(json.dumps(summary))\n    pinger(cfg.healthcheck_url, json.dumps(summary))` → the same with `json.dumps(summary, separators=(",", ":"))` in the `log.info` call |
| `alarm: block logged in lower case` | HANDLER_LOGS | `log.error("BLOCKED: %s", err)` → `log.error("blocked: %s", err)` |
| `alarm: summary's receipt key renamed` | HANDLER_LOGS | `asdict(outcome) \| {"code_sha256": core.CODE_SHA256}` → `{("receipt_key" if k == "receipt" else k): v for k, v in asdict(outcome).items()} \| {"code_sha256": core.CODE_SHA256}` |

Run: `.venv/bin/python scripts/mutation_check.py "alarm: "`
Expected: every line `CAUGHT`, then "Every mutation was caught." Check two of them by hand for an `AssertionError` (Global Constraints).

- [ ] **Step 7: Commit**

```bash
git add template.yaml tests/test_alarms.py tests/test_template.py scripts/mutation_check.py
git commit -m "q20: missed-refresh and block alarms from log metric filters; ErrorAlarm removed"
```

### Task 2: Two stale texts in the collector

**Files:**
- Modify: `src/collector/core.py:277` (latch message)
- Modify: `src/collector/handler.py:93-94` (comment)
- Test: `tests/test_core.py:142-150` (`test_latched_collector_makes_no_requests_until_cleared`)
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: the latch message text `"Nothing was requested. A person must check, then clear the latch (see docs/operations.md, If it's blocked)."`

- [ ] **Step 1: Write the failing assertion**

In `test_latched_collector_makes_no_requests_until_cleared`, the latched `BlockedError`'s message contains `"docs/operations.md"` and not `"README"`.

- [ ] **Step 2: Run it and see it fail**

Run: `.venv/bin/python -m pytest tests/test_core.py::test_latched_collector_makes_no_requests_until_cleared -v`
Expected: FAIL (`README` in the message).

- [ ] **Step 3: Change the message and the comment**

- `core.py:277`: `"(see README)"` → `"(see docs/operations.md, If it's blocked)"`.
- `handler.py:93-94`: the comment keeps "No /fail ping" and names healthchecks.io's grace period as the reason; the clause about the alarm needing errors in two consecutive windows goes.

- [ ] **Step 4: Run the collector tests**

Run: `.venv/bin/python -m pytest tests/test_core.py tests/test_handler.py tests/test_alarms.py -v`
Expected: all PASS.

- [ ] **Step 5: Mutation entry**

`"latch message points at the README"`: CORE, `"(see docs/operations.md, If it's blocked)"` → `"(see README)"`.
Run: `.venv/bin/python scripts/mutation_check.py "README"` → `CAUGHT`.

- [ ] **Step 6: Commit**

```bash
git add src/collector/core.py src/collector/handler.py tests/test_core.py scripts/mutation_check.py
git commit -m "q20: the block message points at docs/operations.md; the failure comment no longer cites the old alarm"
```

### Task 3: The docs

**Files:**
- Modify: `docs/operations.md:24` ("Outages aren't blocks"), `docs/operations.md:59-66` (deploy step 6), `docs/operations.md:69-71` ("If it's blocked")
- Modify: `docs/data-model.md:48` ("Nightly run", step 2)

**Interfaces:**
- Consumes: resource names from Task 1.
- Produces: nothing code depends on.

- [ ] **Step 1: `docs/operations.md`**

- Line 24: failures fail the run without pinging `/fail`; healthchecks.io's 15-minute grace decides when silence is an outage, and the missed-refresh alarm emails when no board has been downloaded for 35 minutes, so one slow reply stays quiet. Link `alarms.md` for the two alarms.
- Step 6: the drill proves healthchecks.io's `/fail` (unchanged); the alarm emails are proven with `aws cloudwatch set-alarm-state --alarm-name <name> --state-value ALARM --state-reason "drill" --profile flights-sam --region il-central-1` on each alarm (an ALARM email, then an OK email at the next evaluation); a first deploy of the alarms sends three emails by itself (`alarms.md`, "What might not be obvious"). The alarm names are in `aws cloudwatch describe-alarms --alarm-name-prefix flights-archive-`.
- "If it's blocked": "The block alarm's email and the `/fail` ping say `BLOCKED`." The rest stands. Add one line: while the latch holds, the block alarm stays in ALARM and the missed-refresh alarm follows after 35 minutes; both return to OK after the unblock and the next download.

- [ ] **Step 2: `docs/data-model.md:48`**

Replace "and the existing SNS alarm cover failures" with: the collector's alarms watch only the collector (`alarms.md`), so the nightly function needs its own alert, chosen when it is designed (provisional).

- [ ] **Step 3: Check**

Run: `grep -n -i 'alarm' docs/operations.md docs/data-model.md README.md`
Expected: no line says the alarm counts errors or windows; every mention matches `docs/alarms.md`. Run `.venv/bin/python -m pytest -q`: all pass (no doc is tested, but nothing else may break).

- [ ] **Step 4: Commit**

```bash
git add docs/operations.md docs/data-model.md
git commit -m "q20: operations and data-model docs follow the new alarms"
```

### Task 4: Review, merge, prove the patterns, deploy (main session; AWS steps on the owner's go)

**Files:** none changed, unless the review finds something (then a fix commit on the branch, and its mutation check).

- [ ] **Step 1: Full checks on the branch**

Run: `.venv/bin/python -m pytest -q` → all pass (590 before this plan, minus 1 removed, plus the new ones). Then `.venv/bin/python scripts/mutation_check.py` → "Every mutation was caught." Record both counts.

- [ ] **Step 2: Whole-branch review**

A fresh reviewer on Fable (`model: "fable"`; the newest Opus if Fable is at its limit, the report naming the swap) reads `docs/alarms.md`, this plan and `git diff main...q20-alarms`. Fold in what holds up (each finding checked against its source first); log changes from this plan under Deviations.

- [ ] **Step 3: Merge and push (owner's go for the push)**

`git checkout main && git merge --ff-only q20-alarms`; `gh auth status` shows doronreiffman; `git push`; CI green (`gh run list --limit 1`).

- [ ] **Step 4: Prove the patterns on real lines (read-only)**

Read both patterns from the parsed template:
`.venv/bin/python -c 'from cfnlint.decode import decode; r=decode("template.yaml")[0]["Resources"]; print(r["ReceiptFilter"]["Properties"]["FilterPattern"]); print(r["BlockedFilter"]["Properties"]["FilterPattern"])'`
Fetch the last hour of `/flights-archive/collector` events (`aws logs filter-log-events`), pick at least one stored, one unchanged (if none in the hour, the 2026-10-30 03:16:45Z one), several skipped, one `collector failed` and its traceback, and the REPORT lines; add the synthetic block, latched and drill lines in the log's own format. Run `aws logs test-metric-filter --filter-pattern '<pattern>' --log-event-messages ...` for each pattern.
Expected: the receipt pattern matches exactly the stored and unchanged lines; the block pattern exactly the block and latched lines. Anything else stops the deploy.

- [ ] **Step 5: Deploy as a change set (owner's go)**

Identity check; `git status --porcelain src/` prints nothing; `sam build`; `sam deploy --profile flights-sam --region il-central-1 --parameter-overrides ScheduleState=ENABLED --no-execute-changeset`.
Read the change set: `aws cloudformation describe-change-set --stack-name flights-archive --change-set-name <name> --profile flights-sam --region il-central-1 --query '{params:Parameters,changes:Changes[].ResourceChange.[Action,LogicalResourceId]}'`.
Expected: `ScheduleState` `ENABLED`; `UserAgent`, `AlertEmail`, `RetentionDays` at their current values and `HealthcheckUrl` carried over (shown masked); changes: Add `ReceiptFilter`, `BlockedFilter`, `MissedRefreshAlarm`, `BlockedAlarm`; Remove `ErrorAlarm`; Modify `CollectorFunction`; nothing else. If SAM refused the change set for missing parameter values, the owner supplies them on the command line (never written to a file). Anything unexpected: delete the change set, stop, tell the owner.
On the owner's go: `aws cloudformation execute-change-set ...`, then `aws cloudformation wait stack-update-complete ...`.

- [ ] **Step 6: Prove it works**

- `describe-stacks`: `ScheduleState` is `ENABLED`; the next receipt lands within 15 minutes; the run summary shows a new `code_sha256`.
- Expected emails: `BlockedAlarm` OK within about 5 minutes; `MissedRefreshAlarm` ALARM within minutes, then OK after the first receipt. Ask the owner which arrived. If `MissedRefreshAlarm` never went to ALARM, `set-alarm-state` it to ALARM (owner's go) and confirm the email.
- `set-alarm-state` on `BlockedAlarm` to ALARM (owner's go): an ALARM email, then an OK email.
- `aws cloudwatch get-metric-statistics --namespace flights-archive --metric-name Receipts --statistics Sum --period 60 ...` over the last 30 minutes shows a 1 in each minute that had a receipt.
- Next day: both alarms OK; no email from the nightly 30-minute gap around 00:00Z.

## Deviations

(Filled in during execution: each change reality forced from this plan, with the reason.)

- **Task 1, Step 5: the cfn-lint command needs `--`.** `cfn-lint --regions il-central-1 template.yaml` makes `--regions` take the file name as a second region, and cfn-lint then waits on standard input. CI's form is the right one: `cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`.
- **Task 3: one more line in `docs/operations.md`, step 6.** On a fresh deploy the guide keeps the schedule off until step 7, so the missed-refresh alarm sits in ALARM until then (no runs, no downloads); the guide now says so.
- **Task 4, Step 5: the change set also listed the schedule and its role as Modify.** `CollectorFunctionEveryTwoMinutes` (Target) and `CollectorFunctionEveryTwoMinutesRole` (Policies), both with Evaluation `Dynamic`, caused by `CollectorFunction.Arn`: CloudFormation flags resources that read an attribute of a resource being modified, because it can confirm the value only at execution. The function's code change does not replace it (`RequiresRecreation: Never`), so the ARN and both resources' values stay the same. The plan's expected list missed this; the deploy stopped, the owner was asked, and ran it on the owner's go (2026-11-02 10:43Z). Any future change to the function shows the same two lines.
