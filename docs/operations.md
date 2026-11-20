# Operating flights-archive

How the collector works in detail, how to deploy and run it, and what it costs. The overview is in the [README](../README.md).

Source: Israel Airports Authority, data.gov.il dataset `flydata`, resource `e83f763b-b7d7-479e-b172-ae981ddc6de5`. Used under the [data.gov.il terms of use](https://data.gov.il/he/terms-of-use); the clauses that bear on this project, quoted, are in [terms.md](terms.md).

## What it does

Every 2 minutes a Lambda function in il-central-1 (Tel Aviv):

1. Asks `resource_show` when the board last changed. That's a small request.
2. Downloads the full board through `datastore_search` only if that timestamp moved, if the last full download is 30+ minutes old, or for up to 10 minutes after the timestamp moved without the data changing yet.
3. Stores the reply bytes untouched, gzipped, only if their SHA-256 differs from the last stored snapshot.
4. After every full download, stored or unchanged, writes a small receipt: when the run started and finished, the board's `last_modified`, rows, page hashes, which code wrote it, and the stored snapshot that holds this content.

The board refreshes about every 15 minutes, so that's roughly 4 downloads an hour.

Snapshots land at `raw/date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-000.json.gz` (UTC), with fetch time, HTTP status, latency, row count, hashes and the resource's `last_modified` in the object metadata. Receipts land at `receipts/date=YYYY-MM-DD/HHMMSSZ-<sha12>.json`, written after the pages, so a receipt means every page it names is in the archive; it also keeps `last_modified` and the hashes where a local sync can see them (sync drops object metadata). Snapshots stored before receipts existed (before the first receipt) have none. Object Lock (governance mode, 10 years by default) keeps every version of a snapshot or receipt, and the collector's writes carry a write-once condition, so it never replaces one (the code enforces that condition, not IAM). A small `state/collector.json` remembers the last timestamp, hash and snapshot key. Design: [receipts.md](receipts.md).

## Rules the code enforces

- **One identified client.** Every request sends the `USER_AGENT` you set, which must carry a `+https://` project URL and a contact email; the deploy and the code both refuse one without them.
- **Stop if blocked, and stay stopped.** A 401, 403 or 429, or an HTML page served where JSON belongs, raises `BlockedError`, pings healthchecks.io's `/fail`, stores nothing, and sets a latch in the state file. Every later run refuses to call data.gov.il until a person clears it. Don't switch to a browser User-Agent, another IP or anything else that works around a block: the data.gov.il license excludes data obtained by circumventing technical protection. Find out why, ask data.gov.il if needed, then unblock (below).
- **Outages aren't blocks.** 5xx errors, timeouts and HTML error pages fail that run without pinging `/fail`; the next run tries again. healthchecks.io's 15-minute grace period decides when a run of failures is an outage, and the missed-refresh alarm emails when no board has been downloaded for 35 to 40 minutes, so one slow reply stays quiet. The two alarms (missed refresh, block) are in [alarms.md](alarms.md).
- **Validate before writing.** Zero rows, a missing field, a total that doesn't match the rows, or the board changing mid-download all raise and store nothing.
- **No retries.** Neither the scheduler nor Lambda retries a failed run; the next scheduled run is the retry.
- **Never touch iaa.gov.il.** Its terms forbid copying without written consent.

## Deploy

You need a personal AWS account (nothing from an employer) with il-central-1 enabled, AWS CLI 2.32 or newer, the AWS SAM CLI, and Python 3.13 on your Mac for `sam build` (`brew install python@3.13`, or use `sam build --use-container` with Docker).

1. Sign in: `aws login --profile flights`. Then check that `aws sts get-caller-identity --profile flights-sam` shows your personal account. The `flights-sam` profile hands the `aws login` session to SAM.
2. Create a healthchecks.io check (period 2 minutes, grace 15 minutes) and copy its ping URL.
3. Email data.gov.il about the collector, with the User-Agent you'll use.
4. Build and deploy with the schedule switched off (`ScheduleState` defaults to `DISABLED`). The parameters stay on your command line, not in a file you might commit:

   Deploy from a clean, committed tree (`git status --porcelain src/` prints nothing): every receipt records a fingerprint of the collector's code, and only a committed tree lets you find the commit behind it. The run summary in the logs shows the same fingerprint.

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

   healthchecks.io should show a failure within a minute; run step 5 to clear it. The drill does not set off the alarms, which count downloads and block lines, not errors. To see an alarm's email, set it to ALARM by hand: it emails ALARM, then OK when it next evaluates. That works only on an alarm in OK; setting an alarm that is already in ALARM changes nothing and sends nothing.

   ```bash
   aws cloudwatch describe-alarms --alarm-name-prefix flights-archive- --query 'MetricAlarms[].AlarmName' --profile flights-sam --region il-central-1
   aws cloudwatch set-alarm-state --alarm-name <name> --state-value ALARM --state-reason drill --profile flights-sam --region il-central-1
   ```

   On a fresh deploy, prove the block alarm this way. The missed-refresh alarm stays in ALARM until the schedule is on, apart from about 35 minutes after step 5's one download; it proves itself at step 7, when the first scheduled download sends its OK email. The first deploy of the alarms on a live collector sends three emails by itself: the block alarm's OK, then the missed-refresh alarm's ALARM and OK ([alarms.md](alarms.md), "What might not be obvious").
7. Go live: deploy again with the same parameters plus `ScheduleState=ENABLED`. After 10 minutes, healthchecks.io should show a ping every 2 minutes and new snapshots should appear about every 15.

## If it's blocked

The block alarm's email and the `/fail` ping (`BLOCKED: <reason>`) mean the collector has stopped calling data.gov.il. While the latch holds, the block alarm stays in ALARM, and the missed-refresh alarm follows 35 to 40 minutes after the last download; both email OK after the unblock and the next download. Read the reason in the logs (log group `/flights-archive/collector`), sort it out with data.gov.il, then clear the latch:

```bash
aws lambda invoke --function-name <CollectorFunctionName> --payload '{"unblock": true}' \
  --cli-binary-format raw-in-base64-out out.json --profile flights-sam --region il-central-1
```

## Develop

From the repo root:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest --cov=collector --cov=model --cov=nightly --cov=timeline
cfn-lint --regions il-central-1 -- template.yaml site-template.yaml model-stack/template.yaml
python scripts/mutation_check.py
```

The mutation check breaks each rule in turn and expects a test to fail; it is 840 short pytest runs, about 25 minutes on my Mac. It edits source files in place while it runs, so run nothing else from the checkout meanwhile. The tests in `tests/test_timeline_search.py` and `tests/test_timeline_fromhere.py` run the search box's JavaScript and the page script every page loads (`fromhere.js`) under Node; each module is skipped as a whole where Node is missing. CI runs pytest, which includes both Node modules, and `scripts/mutation_check.py` on every push, which costs nothing on GitHub's free tier at this repo's push rate.

The tests use 38 real rows of the board (see `tests/fixtures/README.md`). Once the collector has stored its first reply, swap those rows for rows from it. `tests/test_template.py` pins the infrastructure settings safety depends on: no retries, the timeout, the lock and the permissions.

## Model

`src/model/` turns the raw snapshots into Parquet tables with DuckDB: `snapshots`, `observations` (one row per flight per change) and `flights` (one row per marketed flight with its retimes linked; the codeshare group is the physical movement; outcome, cancellation lead time), plus `receipts` and `snapshot_runs`. It trusts only snapshots with a receipt, or from before receipts existed, and stops when the local copy looks out of step; `sh scripts/sync.sh` copies receipts, then snapshots, into `data/`. The rules, what is still uncertain about them, and how to run the build are in [data-model.md](data-model.md); `data-quality-*.md` are reports from real snapshots. It runs locally, and nightly in AWS once deployed ([Nightly model build](#nightly-model-build), below).

## Nightly model build

Built, not deployed: no stack exists yet. Design, sizes and the reasons: [nightly-model.md](nightly-model.md); how it was built, and where the build departed from the plan: [nightly-model-plan.md](nightly-model-plan.md), "Deviations". Once a night (01:40 UTC) a second Lambda function, in a stack of its own, `flights-archive-model` (`model-stack/template.yaml`), does this:

1. Pings healthchecks.io's `/start`, empties its work folder under `/tmp` and checks that DuckDB has nothing installed beyond its built-in extensions.
2. Lists `receipts/` and `raw/` in the archive bucket and stops if either listing is smaller than the last build's. It then copies exactly what it listed and builds the five model tables on the copy (a 1 GB DuckDB limit, 2 threads).
3. Uploads the tables and a manifest (a small JSON file describing the build) under `models/<build id>/` in its own bucket, never replacing a file.
4. Moves the pointer, `latest.json` (one small file, written last, that names the newest complete build), to the new build, only forward, then deletes builds older than 30 days, never the one the pointer names.
5. Logs one summary line and sends it as the success ping. Any error is logged, sent to `/fail` and raised. An error before the pointer step leaves the pointer where it was and deletes nothing.

The function only reads the archive bucket (`raw/` and `receipts/`) and writes its own bucket; it never calls data.gov.il. The stack is separate so that a change to the model puts no change set on the collector or the locked archive.

**Deploying** (on the owner's go, from a clean committed tree: `git status --porcelain` prints nothing). The order, in full in [nightly-model.md](nightly-model.md), "Deploy and prove": the healthchecks.io check is created before the first deploy (period 1 day, grace 1 hour), its address kept out of the repository; the first deploy leaves the schedule `DISABLED`; then come the run by hand, the comparison and the drill (below); only once those have passed does `sh scripts/deploy_nightly.sh ENABLED` switch the schedule on.

Run `sh scripts/deploy_nightly.sh` in a terminal window: the script needs a real terminal to turn echo off and to ask for confirmation. It checks that the `flights-sam` profile is the project's user, then asks for the healthchecks.io ping address with echo off and never prints it; paste it at the prompt. It builds in `model-stack/`, names the template, the build folder and the stack explicitly, and runs `sam deploy` with `--confirm-changeset`: review the change set, which on the first deploy must hold only new resources in `flights-archive-model`, and confirm.

**A run by hand**, which is also the first measurement in a Lambda, and clears a failure shown by the drill:

```bash
aws lambda invoke --function-name <ModelFunctionName> --invocation-type Event --payload '{}' \
  --cli-binary-format raw-in-base64-out out.json --profile flights-sam --region il-central-1
```

The function name and `ModelBucketName` are the stack's outputs. The summary is the success ping's body in healthchecks.io, and in the log group `/flights-archive-model/nightly`. The drill fails on purpose before anything is read, to prove the alert: the same command with `--payload '{"drill": true}'`; healthchecks.io should show a failure and send its email.

**The comparison** checks the Lambda's model against a build on the Mac of the same boards. After `sh scripts/sync.sh`:

```bash
PYTHONPATH=src .venv/bin/python scripts/nightly_check.py --bucket <ModelBucketName> --work <a new folder>
```

It reads `latest.json` and the five tables from the model bucket, refuses tables that differ from the manifest's sizes or hashes, lays out from `data/` the same receipts and boards, builds the model on them and compares the two by the four checks of `scripts/tagged_check.py` (the tables' columns and types, their rows, `timeline.load.load()`, `progress.json`). Exit 0 when identical, 1 on any difference or on an unexpected error (with a traceback), 2 when it refuses to compare. `--work` must be a new or empty folder outside `data/raw` and `data/receipts`.

**The summary line** is one JSON line with: the seconds of each step (`list`, `copy`, `build`, `staging`, `upload`, `pointer`, `clean_up`, `total`) and `seconds_left`; the objects and bytes copied; `memory_mb` (the peak and the function's configured memory) and `tmp_mb` (the peak and the disk's total size, as read); `rows` and `table_bytes` for each table; `pointer` (`moved`, or `kept` when the pointer's build read a newer receipt) and `pointer_build_id`, the build the pointer names; `deleted`, the ids of the builds removed; the build id, the model fingerprint (a SHA-256 of the model's source files and the DuckDB version) and the DuckDB version. `staging` is the part of `build` spent on the stage: each day's per-board work, kept as Parquet. Two rules read the line ([nightly-model.md](nightly-model.md), "Sizing"), comparing the steps `list`, `copy`, `staging`, the rest of the build (`build` minus `staging`), `upload`, `pointer` and `clean_up`:

- A night past 300 s with `staging` the largest of those calls for keeping the stage in S3 between nights, so that a night stages only the days that changed ([nightly-model.md](nightly-model.md), "The stage between nights").
- A night past 300 s with `copy` the largest of those, or, with the stage kept, past 450 s, temp files past 5 GB or memory past 2,400 MB, calls for the step after. The design's options, in the order to try: more memory for the function and for DuckDB, if the account's quota allows more than 3,008 MB; the narrower step [lighter-build.md](lighter-build.md) names, which edits frozen files and so is a design of its own; the same code as a scheduled container task in place of a Lambda.

**The alert** is one healthchecks.io check, period 1 day, grace 1 hour. It gets a start ping and then a success or a failure; a killed night sends no success and is marked down after the grace. A night that never ran (schedule off, function broken, account trouble) leaves the check without a ping for a day and an hour, and an email goes out. The check sits outside AWS. If healthchecks.io itself is down, no alert goes out.

**Cost**: see [nightly-model.md](nightly-model.md), "Cost".

## Timeline

`src/timeline/` turns the model into a static site, "Will It Fly?": a front page that leads with "Find your flight", the chance table and the total; a page per flight number with its chances (cancelled, and delayed an hour or more), what they were worked out from, its days as a strip and what changed on each; a page per day; and a page of every cancellation. The wording never claims more than the airport's list showed (a cancellation's time is a range and its notice a range or a lower bound; delays only at an hour or more; no operators), and every page cites the source and says it is unofficial. Pages, words and checks: [site-redesign.md](site-redesign.md) and [flight-lookup.md](flight-lookup.md); v1 and the publishing decision: [timeline.md](timeline.md). Published at https://dt4564wsgvijr.cloudfront.net since 2026-10-30; my reading of the data.gov.il terms is that they allow publishing it ([terms.md](terms.md)).

```bash
PYTHONPATH=src .venv/bin/python -m timeline.build --model data/model --out site
.venv/bin/python -m http.server -d site 8000   # then open http://localhost:8000
```

Publishing (live since 2026-10-30): a separate stack, `site-template.yaml`, serves the site from a private S3 bucket through CloudFront, and `sh scripts/publish.sh` uploads a build after checking the AWS identity, the build marker, the banned phrases and words, the built-by placeholder (which stops any upload while it is still there), the source, unofficial and estimates lines on every page, and a "Worked out from" line on every flight page that gives a chance. Both write to AWS, so each runs only when I approve it; design, takedown and cost in [publishing.md](publishing.md).

## Cost

About $1 to $2 for the first year before the alarms (they add at most $0.70 a month at list price, likely $0 within the free tier: [alarms.md](alarms.md), "Cost"), a cautious figure: about 3,000 snapshots a month at about 47 KB each, so about 0.14 GB a month (measured 2026-10-29: 39 snapshots, 1.8 MB), plus a few cents of S3 requests. Receipts add about 3,300 small writes a month, about $0.02 at il-central-1 prices (AWS Price List, 2026-10-29). Lambda and EventBridge Scheduler stay inside their free allowances. Storage grows every year because nothing is deleted.
