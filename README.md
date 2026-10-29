# flights-archive

Archives the Ben Gurion airport flight board that the Israel Airports Authority publishes on data.gov.il (dataset `flydata`), so the history survives after the board drops each flight, about a day after it flies.

Source: Israel Airports Authority, data.gov.il dataset `flydata`, resource `e83f763b-b7d7-479e-b172-ae981ddc6de5`. Used under the [data.gov.il terms of use](https://data.gov.il/he/terms-of-use), which allow reuse, including commercial, with the source cited.

## What it does

Every 2 minutes a Lambda function in il-central-1 (Tel Aviv):

1. Asks `resource_show` when the board last changed. That's a small request.
2. Downloads the full board through `datastore_search` only if that timestamp moved, if the last full download is 30+ minutes old, or for up to 10 minutes after the timestamp moved without the data changing yet.
3. Stores the reply bytes untouched, gzipped, only if their SHA-256 differs from the last stored snapshot.
4. After every full download, stored or unchanged, writes a small receipt: when the run started and finished, the board's `last_modified`, rows, page hashes, which code wrote it, and the stored snapshot that holds this content.

The board refreshes about every 15 minutes, so that's roughly 4 downloads an hour.

Snapshots land at `raw/date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-000.json.gz` (UTC), with fetch time, HTTP status, latency, row count, hashes and the resource's `last_modified` in the object metadata. Receipts land at `receipts/date=YYYY-MM-DD/HHMMSSZ-<sha12>.json`, written after the pages, so a receipt means every page it names is in the archive; it also keeps `last_modified` and the hashes where a local sync can see them (sync drops object metadata). Snapshots stored before receipts existed (before the first receipt) have none. Object Lock (governance mode, 10 years by default) plus a write-once condition mean the collector can't overwrite or delete a snapshot or a receipt. A small `state/collector.json` remembers the last timestamp, hash and snapshot key. Design: `docs/receipts.md`.

## Rules the code enforces

- **One identified client.** Every request sends the `USER_AGENT` you set, which must carry a `+https://` project URL and a contact email; the deploy and the code both refuse one without them.
- **Stop if blocked, and stay stopped.** A 401, 403 or 429, or an HTML page served where JSON belongs, raises `BlockedError`, pings healthchecks.io's `/fail`, stores nothing, and sets a latch in the state file. Every later run refuses to call data.gov.il until a person clears it. Don't switch to a browser User-Agent, another IP or anything else that works around a block: the data.gov.il license excludes data obtained by circumventing technical protection. Find out why, ask data.gov.il if needed, then unblock (below).
- **Outages aren't blocks.** 5xx errors, timeouts and HTML error pages fail that run without pinging `/fail`; the next run tries again. healthchecks.io's 15-minute grace period and the CloudWatch alarm (errors in two consecutive 5-minute windows) decide when a run of failures is an outage, so one slow reply stays quiet.
- **Validate before writing.** Zero rows, a missing field, a total that doesn't match the rows, or the board changing mid-download all raise and store nothing.
- **No retries.** Neither the scheduler nor Lambda retries a failed run; the next scheduled run is the retry.
- **Never touch iaa.gov.il.** Its terms forbid copying without written consent.

## Deploy

You need a personal AWS account (nothing from an employer) with il-central-1 enabled, AWS CLI 2.32 or newer, the AWS SAM CLI, and Python 3.13 on your Mac for `sam build` (`brew install python@3.13`, or use `sam build --use-container` with Docker).

1. Sign in: `aws login --profile flights`. Then check that `aws sts get-caller-identity --profile flights-sam` shows your personal account. The `flights-sam` profile hands the `aws login` session to SAM.
2. Create a healthchecks.io check (period 2 minutes, grace 15 minutes) and copy its ping URL.
3. Email data.gov.il about the collector, with the User-Agent you'll use.
4. Build and deploy with the schedule switched off (`ScheduleState` defaults to `DISABLED`). The parameters stay on your command line, not in a file you might commit:

   ```bash
   sam build
   sam deploy --profile flights-sam --region il-central-1 --parameter-overrides \
     'UserAgent="flights-archive/0.1 (+https://github.com/<you>/flights-archive; <email>)"' \
     'HealthcheckUrl=https://hc-ping.com/<uuid>' \
     'AlertEmail=<email>'
   ```

   The inner double quotes around the User-Agent matter: `--parameter-overrides` splits on spaces, and without them the value is silently cut at the first space (the template now rejects a value with no URL and email, which catches that). Review the change set and confirm. Afterwards check the live value: `aws lambda get-function-configuration --function-name <CollectorFunctionName> --query Environment.Variables.USER_AGENT --profile flights-sam --region il-central-1`. Then confirm the SNS subscription email AWS sends you. The function and bucket names are in the stack outputs.
5. Run it once by hand. That's one request to data.gov.il, the same as a manual check:

   ```bash
   aws lambda invoke --function-name <CollectorFunctionName> --payload '{}' \
     --cli-binary-format raw-in-base64-out out.json --profile flights-sam --region il-central-1
   cat out.json
   aws s3 ls s3://<bucket>/raw/ --recursive --profile flights-sam
   ```

   `out.json` should say `"action": "stored"` with about 2,000 to 2,800 rows, and the listing should show one snapshot.
6. Prove the alerts work with a drill, which fails on purpose without calling data.gov.il:

   ```bash
   aws lambda invoke --function-name <CollectorFunctionName> --payload '{"drill": true}' \
     --cli-binary-format raw-in-base64-out out.json --profile flights-sam --region il-central-1
   ```

   healthchecks.io should show a failure within a minute. The alarm email needs errors in two consecutive 5-minute windows, so run the drill again about 5 minutes later if you want to see that email too. Run step 5 to clear healthchecks.io.
7. Go live: deploy again with the same parameters plus `ScheduleState=ENABLED`. After 10 minutes, healthchecks.io should show a ping every 2 minutes and new snapshots should appear about every 15.

## If it's blocked

The alarm email and the `/fail` ping say `BLOCKED`. The collector has stopped calling data.gov.il. Read the reason in the logs (log group `/flights-archive/collector`), sort it out with data.gov.il, then clear the latch:

```bash
aws lambda invoke --function-name <CollectorFunctionName> --payload '{"unblock": true}' \
  --cli-binary-format raw-in-base64-out out.json --profile flights-sam --region il-central-1
```

## Develop

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest --cov=collector --cov=model
cfn-lint template.yaml
python scripts/mutation_check.py
```

The mutation check breaks each rule in turn and expects a test to fail; it is about 75 short pytest runs, a few minutes. CI runs it on every push, which costs nothing on GitHub's free tier at this repo's push rate.

The tests use 38 real rows of the board (see `tests/fixtures/README.md`). Once the collector has stored its first reply, swap those rows for rows from it. `tests/test_template.py` pins the infrastructure settings safety depends on: no retries, the timeout, the lock and the permissions.

## Model

`src/model/` turns the raw snapshots into Parquet tables with DuckDB: `snapshots`, `observations` (one row per flight per change) and `flights` (one row per marketed flight with its retimes linked; the codeshare group is the physical movement; outcome, cancellation lead time), plus `receipts` and `snapshot_runs`. It trusts only snapshots with a receipt, or from before receipts existed, and stops when the local copy looks out of step; `sh scripts/sync.sh` copies receipts, then snapshots, into `data/`. The rules, what is still uncertain about them, and how to run the build are in `docs/data-model.md`; `docs/data-quality-*.md` are reports from real snapshots. It runs locally for now; a nightly Lambda is proposed in the same doc.

## Cost

About $1 to $2 for the first year: roughly 3,000 to 4,400 snapshots and 0.3 to 0.7 GB a month, plus a few cents of S3 requests. Receipts add about 3,300 small writes a month, about $0.02 at il-central-1 prices (AWS Price List, 2026-10-29). Lambda and EventBridge Scheduler stay inside their free allowances. Storage grows every year because nothing is deleted.
