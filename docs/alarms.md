# Alarms (q20)

Grade: production-lean. This is the alert path of a live collector: every rule is tested and mutation-checked, the filter patterns are proven against real log lines before the deploy, and nothing new runs (no new function, no new service).

Goal: an alarm email means one of two things, and nothing else sends one:

1. **Board versions are being lost.** No board download for 35 minutes.
2. **data.gov.il blocked the collector.** The collector has stopped calling it and waits for a person.

## Why

The collector's only CloudWatch alarm, `ErrorAlarm`, emails when the function errors in two consecutive 5-minute windows. Errors are not losses: a timeout or an empty reply fails one run, and the next run, two minutes later, usually gets the board. From 2026-10-29 14:22Z to 2026-10-31 19:32Z the function failed 22 times, yet receipts (written since 17:02Z on the 29th) were never more than 30 minutes apart. On the evening of 2026-10-31 data.gov.il's slow status endpoint made the alarm email three times (19:27Z, 19:32Z, 20:06Z, from the alarm's history). That night I had its emails paused (`aws cloudwatch disable-alarm-actions`), and asked for an alarm on what matters instead: a missed board refresh, or a block. Since then healthchecks.io has been the only alert path.

## What might not be obvious

- **A receipt is the signal.** Every full download writes a receipt, whether the board was new (`stored`) or the same as last time (`unchanged`) (`docs/receipts.md`). The collector downloads at least every 30 minutes even when the board's timestamp does not move (`FULL_FETCH_EVERY` in `src/collector/core.py`). So while data.gov.il answers, receipts are at most about 30 minutes apart. Measured on all 380 receipts from 2026-10-29 17:02Z to 2026-11-02 09:16Z: the longest gap is 30 min 1 s, and it happens every night around 00:00Z, when data.gov.il skips one refresh and the 30-minute download fills in. No gap reached 33 minutes.
- **35 minutes without a download means at least one board version was never fetched.** The board refreshes every 15 minutes, so any 30-minute stretch with no download contains the whole life of one version. Shorter gaps can lose a version too (a 20-minute gap at the wrong moment can); this alarm catches certain loss, not every possible loss. The model's collection gaps remain the full record.
- **The alarms read the collector's own log lines.** CloudWatch Logs metric filters turn matching lines into a metric; the collector's code does not change for this. A filter counts only lines logged after it exists, never earlier ones (AWS: "Filters do not retroactively filter data", https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/MonitoringLogData.html).
- **How a pattern matches was measured, not assumed.** AWS's syntax page does not say whether a term matches inside a longer word, or how to put a double quote inside a term (https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html). `aws logs test-metric-filter` (read-only) against real lines from `/flights-archive/collector`, 2026-11-02, settled both: a term matches anywhere in the line (`BLOCK` matches `BLOCKED`), case matters (`Blocked` matches only `BlockedError`), and `\"` inside a quoted term is a literal double quote.
- **Tracebacks quote source code.** When a run fails, Lambda logs the traceback with the source line of each frame. A line like `receipt_key = f"receipts/date=..."` from `core.py` can therefore appear in an error event. The pattern `"receipts/date="` matched such a line in the test above; the chosen pattern does not (Design).
- **No log lines counts as no receipt.** If the collector stops running altogether (schedule off, function broken, account trouble), no lines arrive and the metric has no data. The missed-refresh alarm treats missing data as breaching, so it fires then too: a second path beside healthchecks.io's 15-minute grace.
- **Switching the schedule off on purpose sets off the missed-refresh alarm** 35 minutes later. Disable its actions first if that is planned, and enable them again after.
- **The deploy will most likely send three emails.** A new alarm starts in INSUFFICIENT_DATA, and OK actions run on a move into OK "from any other state" (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudwatch-alarm.html, `OKActions`). So the block alarm emails OK within about 5 minutes. A new filter has no history, so the missed-refresh alarm's first evaluation sees 35 minutes of missing data and goes to ALARM ("If missing data points are considered breaching, the alarm goes into ALARM state", https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html); the first receipt after the deploy, within about 15 minutes, brings it back to OK. Observed at the deploy on 2026-11-02 (alarm history): the missed-refresh alarm went to ALARM at 10:44:26Z and back to OK at 10:47:26Z, after the first receipt at 10:46:45Z; the block alarm went to OK at 10:45:05Z; each change ran its email action. The emails double as proof that the email path works.
- **The email arrives some minutes after the 35-minute mark.** AWS documents no figure for how long a log line takes to become a metric datapoint. A second reason: `Receipts` has a datapoint only in minutes with log lines (about every other minute), and when an alarm has fewer real datapoints than its evaluation periods, CloudWatch looks further back ("CloudWatch attempts to retrieve a higher number of data points than the number specified as Evaluation Periods", alarms-and-missing-data.html, above), so a receipt a few minutes older than 35 can still hold the alarm at OK. Neither delay can cause a false alarm. UNVERIFIED until observed.
- **The deploy must pass `ScheduleState=ENABLED`.** The template's default is `DISABLED` (for a first test deploy); the live stack runs `ENABLED`. A deploy that leaves it out could stop collection. `samconfig.toml` holds no parameter values.
- **Errors stop emailing.** They stay in the log group (30 days) and in Lambda's own `Errors` metric (namespace `AWS/Lambda`, free), for anyone counting them by hand.
- **healthchecks.io does not change.** The collector pings it after every successful run, and pings `/fail` on a block and on the drill; its 15-minute grace decides when silence is an outage. Whether its alerts reach you is set on healthchecks.io's side; check that once.

## Design

All changes are in `template.yaml` (stack `flights-archive`), plus two text fixes in the collector (a message and a comment) and the docs.

### Removed

- `ErrorAlarm`. Its paused actions go with it, so nothing has to be re-enabled by hand.

### Two metric filters on `CollectorLogs`

| Resource | `FilterPattern` | Metric (namespace `flights-archive`) | Value | Default |
|---|---|---|---|---|
| `ReceiptFilter` | `"\"receipt\": \"receipts/"` | `Receipts` | 1 | 0 |
| `BlockedFilter` | `"BLOCKED:"` | `BlockedRuns` | 1 | 0 |

- The patterns are what CloudFormation must send, character for character: one quoted term each. In YAML the receipt pattern needs a single-quoted scalar (`'"\"receipt\": \"receipts/"'`); a double-quoted scalar would drop the backslashes and send a different pattern.
- `ReceiptFilter` matches the run summary that `handler.run` logs after a `stored` or `unchanged` run: `{"action": "stored", ..., "receipt": "receipts/date=...", ...}`. A `skipped` run logs `"receipt": null` and does not match. Measured 2026-11-02 against real stored, unchanged, skipped, failure and traceback lines, plus a traceback line quoting `core.py`'s `receipt_key` line: it matched the stored and unchanged lines only.
- `BlockedFilter` matches `BLOCKED: <reason>`, which `handler.run` logs on the run that is blocked and on every later run while the latch holds (`core.run_once` raises `BlockedError` before calling data.gov.il). It does not match the drill (`drill: ...`), an ordinary failure (`collector failed: ...`) or the traceback's `BlockedError` line. Measured the same way, on block lines written in the log's own format (the archive has never been blocked, so no real one exists).
- No dimensions, so a default value is allowed. The default of 0 is reported only for a minute in which some lines arrived and none matched; a minute with no lines at all reports nothing (MonitoringLogData, above).

### Two alarms, both emailing `AlertTopic` on ALARM and on OK

| | `MissedRefreshAlarm` | `BlockedAlarm` |
|---|---|---|
| Metric | `flights-archive` / `Receipts`, `Sum` | `flights-archive` / `BlockedRuns`, `Sum` |
| Period | 60 s | 300 s |
| Evaluation periods / datapoints to alarm | 35 / 35 | 1 / 1 |
| Threshold, comparison | `< 1` (`LessThanThreshold`) | `>= 1` (`GreaterThanOrEqualToThreshold`) |
| Missing data | `breaching` | `notBreaching` |
| Fires when | no receipt in the last 35 minutes (or a little longer, below) | a block line in the last 5 minutes |

- `MissedRefreshAlarm` is in ALARM when none of the last 35 one-minute periods holds a receipt (looking a few minutes further back while datapoints are sparse; What might not be obvious); a minute with no lines counts as one without a receipt. Description: "No board download for 35 minutes: at least one 15-minute board version was missed. Read /flights-archive/collector; a BLOCKED line means stop and ask (docs/operations.md, If it's blocked)."
- `BlockedAlarm` stays in ALARM while the latch holds (each latched run logs a block line every 2 minutes) and returns to OK about 5 minutes after the unblock. Description: "data.gov.il blocked the collector and it has stopped calling. Stop and ask; never work around a block (docs/operations.md, If it's blocked)."
- An alarm invokes its actions only when its state changes (https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html), so a long outage sends one ALARM email and one OK email, not one per run.
- `ActionsEnabled` is left at its default, true: the emails are on from the deploy.
- (provisional) Emails on OK as well as ALARM: one more email per incident, and it tells you when nothing more is needed.
- (provisional) Two alarms, not one: the email's subject names which of the two happened, and each stays a plain metric alarm.
- (provisional) One-minute periods for the missed-refresh alarm: it fires about 35 minutes after the last receipt. Five-minute periods line up with the clock and would add up to 5 minutes more.

### Two stale references in the collector

- The latch message in `core.run_once` (`src/collector/core.py:277`) says to clear the latch "(see README)"; the steps moved to `docs/operations.md`. I decided on 2026-10-29 to fix that at the next redeploy of the collector, with a test. It ships here: "(see docs/operations.md, If it's blocked)".
- The comment above `log.error("collector failed: ...")` in `handler.run` (`src/collector/handler.py:93-94`) explains the missing `/fail` ping partly by "the alarm needs errors in two consecutive windows". With `ErrorAlarm` gone, the reason left is healthchecks.io's grace period; the comment says so.
- Both change the code fingerprint that receipts record, as any change under `src/collector/` does.

### Docs

- `docs/operations.md`: "Outages aren't blocks" (the alarm no longer counts errors); deploy step 6 (the drill proves healthchecks.io; the alarm emails are proven by the deploy and with `set-alarm-state`, below); "If it's blocked" (the block email now comes from `BlockedAlarm`); the `AlertEmail` description in the template ("Gets an email when board versions are being lost or the collector is blocked").
- `docs/data-model.md`, "Nightly run" step 2 (a proposal, not deployed): it says "the existing SNS alarm" covers the nightly function's failures. No alarm counts errors after this change, so it says the nightly function needs its own alert, chosen when that function is designed (provisional).
- README: no change; it names CloudWatch and SNS in the stack and points to `docs/operations.md` for the alerts, both still true.

## Tests and mutation checks

- `tests/test_template.py`: `test_alarm_needs_two_consecutive_bad_windows` goes with `ErrorAlarm`; then: no `ErrorAlarm`; both filters on `CollectorLogs` with the patterns, namespace, metric names, value 1 and default 0 above; each alarm's metric, statistic, period, evaluation periods, datapoints, threshold, comparison and missing-data rule as in the table; each alarm's namespace and metric name equal to its filter's (a mismatch would leave the missed-refresh alarm stuck in ALARM and the block alarm silent forever); `AlarmActions` and `OKActions` both exactly `[AlertTopic]`.
- A test that ties each pattern to the lines the code writes: it reads both patterns from `template.yaml` as parsed (the values CloudFormation sends), checks each is exactly one quoted term (starts and ends with `"`, and the receipt pattern holds `\"`), applies the matching rule measured above (strip the outer quotes, read `\"` as `"`, then a case-sensitive substring test), and runs it over what `handler.run` logs for a stored, an unchanged and a skipped run, a block, a latched run, the drill and an ordinary failure, using the fakes `tests/test_handler.py` already has. Stored and unchanged match `ReceiptFilter` only; block and latched match `BlockedFilter` only; the rest match neither.
- The block-message test: the latched error names `docs/operations.md`.
- `scripts/mutation_check.py`: one entry each for the receipt pattern, the block pattern, the summary's `receipt` key, the `BLOCKED:` log text, the missed-refresh comparison, its missing-data rule, its 35 evaluation periods, the block alarm's missing-data rule, a filter's metric name, `OKActions`, and the README pointer. The existing "alarm on one window" entry goes with `ErrorAlarm`.
- cfn-lint, already in CI, checks the template for il-central-1.

## Deploy and prove (each step on my go)

1. Before the deploy: `aws logs test-metric-filter` (read-only) with the two patterns as `template.yaml` parses to them (what CloudFormation will send, not the YAML source text), over fresh real lines of each kind from the log group. A pattern that matches anything other than the table above stops the deploy.
2. Identity check, then `sam build` and `sam deploy` from a clean, committed tree, passing `ScheduleState=ENABLED` and the other parameters' current values. Review the change set: expected, two filters and two alarms added, `ErrorAlarm` removed, the function updated (the block message and the comment); nothing else.
3. Check the schedule is still on (`describe-stacks`, `ScheduleState`), and that the next receipt arrives on time.
4. Expect three emails: the block alarm's OK within about 5 minutes, the missed-refresh ALARM within minutes, then its OK after the first receipt. If the missed-refresh alarm never goes to ALARM, prove the email with `aws cloudwatch set-alarm-state --state-value ALARM` on it instead; the alarm returns to its real state at its next evaluation.
5. Prove the block email with `set-alarm-state` on `BlockedAlarm`: an ALARM email, then an OK email.
6. Over the next day: `Receipts` has a datapoint in every minute that had a download, both alarms sit in OK, and the nightly 30-minute gap around 00:00Z passes without an email.

## Cost (monthly)

From AWS's public price list for il-central-1 (`AmazonCloudWatch`, published 2026-10-07):

- 2 custom metrics at $0.30 each: $0.60.
- 2 standard-resolution alarms at $0.10 each, minus `ErrorAlarm`'s $0.10: $0.10.
- Metric filters carry no line of their own in that price list.
- Total at list price: $0.70 a month. The same list gives the first 10 custom metrics and the first 10 alarms free each month across the account; on 2026-11-02 il-central-1 held 1 alarm (`ErrorAlarm`) and no custom metrics, and other regions were not checked, so the likely cost is $0.

## Rejected

- **The collector publishes its own metric** (Embedded Metric Format, or a `PutMetricData` call each run): a code change, and for `PutMetricData` an extra API call every 2 minutes and a new IAM grant, for a signal the log already carries.
- **A watchdog function that lists `receipts/`:** a second function to build, test and keep alive.
- **healthchecks.io alone** (ping only after a receipt, with a 35-minute period): the main alert would sit outside AWS, and the 15-minute "not running" signal would be lost; I asked for the CloudWatch alarm's emails back.
- **Keeping `ErrorAlarm` without emails:** an alarm nobody reads; Lambda's `Errors` metric stays available.
- **One composite alarm for both:** $0.50 a month, and its email would not say which of the two happened.
- **The pattern `"receipts/date="`:** it also matched a traceback quoting `core.py`.
