# Acquisition receipts (q6)

Grade: production-lean. Small, tested, write-once; no new services, no change to the calls made to data.gov.il.

## Why

Three facts exist today only in logs or in the mutable state file:

- "The board was downloaded at T and was identical to snapshot S" (an `unchanged` run leaves a log line and an overwritten `state/collector.json`).
- "Snapshot S is complete" (the model infers it from the reply's own `total`).
- The board's `last_modified` for S (kept only in S3 object metadata, which `aws s3 sync` drops).

A receipt makes each of them a write-once archive object. Measured 2026-10-29 12:29Z to 15:20Z: 85 runs, 13 full downloads (all new boards, stored), 0 unchanged, 72 timestamp-only checks. So today receipts mostly carry completeness and `last_modified`; `unchanged` receipts start to matter when the board stalls (the 30-minute safety download then finds the same content), which the current model would misread as a collection hole.

## What a receipt is

One JSON object per full download, stored or unchanged, written after the pages and before the state file. Runs that only check the timestamp (`skipped`) get none.

Key: `receipts/date=YYYY-MM-DD/HHMMSSZ-<sha12>.json`: the run's start time (`now`, UTC) and the content hash. A stored receipt therefore has the same stem as its snapshot folder `raw/date=YYYY-MM-DD/HHMMSSZ-<sha12>/`, and a bucket listing shows which board every check saw.

Contents, version 1 (JSON, sorted keys, UTF-8, `application/json`):

```json
{
  "receipt_version": 1,
  "action": "stored",
  "run_started_at": "2026-10-29T15:16:45.008089+00:00",
  "downloaded_at": "2026-10-29T15:16:46.402117+00:00",
  "code_sha256": "<fingerprint of the collector's source files>",
  "source": "data.gov.il flydata resource e83f763b-b7d7-479e-b172-ae981ddc6de5 (Israel Airports Authority)",
  "resource_last_modified": "2026-10-29T15:16:02.929227",
  "snapshot": "raw/date=2026-10-29/151645Z-545e7febf10f",
  "snapshot_sha256": "545e7febf10f49b9...",
  "rows": 1912,
  "pages": [
    {"key": "raw/date=2026-10-29/151645Z-545e7febf10f/page-000.json.gz",
     "rows": 1912, "sha256": "<sha256 of the uncompressed reply>", "latency_ms": 812}
  ]
}
```

- `action` is `stored` or `unchanged`.
- `run_started_at` is the run's clock at invocation, the same instant as the snapshot path and the key. It comes before the status check and the download, so it can even precede `resource_last_modified`; `downloaded_at` is the clock right after the last page arrived.
- `code_sha256` fingerprints the code that wrote the receipt: SHA-256 over the collector package's `.py` files, sorted by name, each contributing its name, a NUL byte and the SHA-256 of its bytes. No deploy step is needed, and running the same function over any commit's `src/collector/` finds the commit. If a collector bug ever writes wrong receipts, this is the only way to tell which ones.
- No HTTP status: anything but 200 raises before a receipt exists.

For `unchanged`, `snapshot` and the page keys name the snapshot already stored with this content: the prefix of state's `last_key`, pages `page-000` to `page-<n-1>`. Rows, hashes, status and latency come from this download, which is identical page by page (same snapshot hash, and the snapshot hash is built from the page hashes). If state carries a matching hash but no `last_key`, or a `last_key` whose sha12 differs from the hash (never seen: the two have been written together since v0.1; it would mean a damaged state file), the run stores a fresh copy instead, so an `unchanged` receipt always names the snapshot with that content. The model drops that copy as an identical repeat (R2).

## Write order and what each failure leaves

Stored: pages, then receipt, then state. Unchanged: receipt, then state. Each step raises on failure and nothing after it runs.

| Fails at | Left in the archive | Next run | Model |
|---|---|---|---|
| a page | earlier pages, no receipt | downloads and stores again under a new key | stops on the orphan until a person checks the logs and lists it in `KNOWN_ORPHANS`; then drops it |
| the receipt (stored) | all pages, no receipt | same | same |
| the receipt (unchanged) | nothing new | downloads again (state untouched, so the 30-minute check is still due) | nothing to do |
| the receipt, but it landed (the AWS library retries a write after a read timeout; the retry gets 412 from the write-once check) | pages and receipt, state not written | stores again, or writes another `unchanged` receipt | keeps one copy, drops the identical repeat (R2) |
| the state | pages and receipt | stores again (the hash differs from the old state) | same |

## Write-once

Same protection as `raw/`: `IfNoneMatch="*"` (S3 refuses to replace an existing key) and Object Lock governance retention for `RetentionDays` (3,650 days), SHA-256 checksum on upload. The collector can never correct a receipt (only the account admin can bypass governance mode), which is why each one carries `receipt_version` and `code_sha256` from the first.

IAM: the existing write-once statement (`s3:PutObject`, `s3:PutObjectRetention`) grows from `raw/*` to `raw/*` and `receipts/*`, and its Sid becomes `WriteOnceArchive`. The action set is unchanged; `tests/test_template.py` pins the two resources. The collector never reads receipts, so no read permission is added.

## Code changes

- `core.py`: build the receipt after the pages; `store.put_receipt(key, body, now)`; `Outcome` gains `receipt` (the key), which the handler already logs and pings. `run_once` takes a `clock` (default: the real UTC clock) for `downloaded_at`, so tests stay deterministic.
- `store.py`: `put_receipt` on `S3Store` (JSON content type, same lock and checksum as snapshots) and on `MemoryStore` (refuses an overwrite; receipts kept apart from snapshot objects).
- `template.yaml`: the second resource on the write-once statement.

## Model changes

- Input: `data/receipts/` beside `data/raw/`, filled by `scripts/sync.sh` (identity check, then receipts, then raw). A receipt is written after its pages, so that order cannot bring a receipt without its pages. A single whole-bucket sync lists `raw/` before `receipts/`, the wrong order.
- New table `receipts` (one row per receipt), written as `receipts.parquet`.
- `snapshot_runs.receipt`, one of:
  - `receipted`: a stored receipt names this snapshot, and its row and page counts match the files. Kept.
  - `legacy`: no receipt, fetched before the first receipt in the archive. Kept under today's checks (declared `total`).
  - `pending`: no receipt, fetched after the newest local receipt. Dropped: its receipt is not written or not synced yet.
  - `orphan`: no receipt, fetched between the first and newest receipt, and listed in `KNOWN_ORPHANS` in `rules.py` after a person checked it. Dropped.
- The build stops, naming the snapshots, when the local copy cannot be trusted. A silent drop could move a flight's first CANCELED sighting by a refresh without flagging it, so each of these is an error rather than a filter:
  - a snapshot with no receipt between the first and newest receipt that is not in `KNOWN_ORPHANS` ("re-run scripts/sync.sh; if it persists, check the collector logs at that time");
  - a pending snapshot more than 5 minutes after the newest receipt ("receipts/ is older than raw/; run scripts/sync.sh");
  - a stored receipt whose row or page count differs from the files (the archive cannot produce this: it means a cut-off sync or a collector bug);
  - a stored receipt whose snapshot has no files locally ("re-sync raw/").
- R2's repeat check runs over kept snapshots only (today: over complete ones).
- No receipts at all: every snapshot is `legacy`, and the build prints that.
- Report: receipt counts by action, snapshot counts by receipt status.
- Not in this change (suggested follow-up, owner's call): treat `unchanged` receipts as sightings, so a stalled board is not a collection hole and cancellation brackets narrow. That changes R4, R7 and R8. One part of it is a precondition for q7: before the timeline publishes coverage gaps, gaps must come from all receipts, stored and unchanged, or a stall on data.gov.il's side shows up as our own collection hole.

## Tests and mutation checks

Collector: receipt after every page and before state, for stored and unchanged; contents; key; none on skip, block or a failed page; a failed receipt leaves state untouched, and so does one that landed before its write raised; multi-page receipt; matching hash without a usable `last_key` stores; the code fingerprint; the S3 call; the IAM resources. Model: each receipt status and each stop; repeat check over kept snapshots; no receipts means legacy. Sync script: identity check first, receipts before raw (run against a fake `aws`). Each rule gets an entry in `scripts/mutation_check.py`.

## Cost (monthly)

Prices from the AWS Price List API for il-central-1, read 2026-10-29: $0.0055 per 1,000 PUT/LIST, $0.0044 per 10,000 GET, $0.025 per GB-month (Standard).

- Receipt writes: 4.5 full downloads an hour measured, about 3,300 a month: $0.02. Ceiling, if every 2-minute run downloaded: 21,600, $0.12.
- Storage: under 1 KB each, about 40 MB a year: under $0.01.
- Local sync downloads: about 3,300 GETs: under $0.01.

Total about $0.02 a month (ceiling $0.13). Lambda time is unchanged in practice (one more small PUT per full download).

## Rejected

- Receipt inside the snapshot folder (`raw/.../receipt.json`): an unchanged download has no folder, and `raw/` stays "untouched replies only".
- A receipt for every run, `skipped` included: five times the writes for a weaker fact (the timestamp, not the content); the 30-minute safety download already bounds the spacing between receipts.
- A hard-coded cutover time for the legacy rule: unknown until the deploy, and it needs a second commit; the first receipt in the archive is the cutover.
- Verifying page hashes in the model now: row and page counts already catch a truncated copy; hash checks are a follow-up. (A check of the sha12 in the path against the receipt's hash would always pass: the receipt names the snapshot by that path.)
- S3 `VersionId` and checksum per page in the receipt (review suggestion): they would pin each page to an exact object version, but only the account admin can replace a page, `unchanged` receipts could not carry them without growing the state file, and the receipt's own page hashes already let anyone check the content.
- Dropping snapshots without a receipt silently (first draft): a sync slip would quietly skew lead times; see the stops above.
- IAM conditions that require the lock headers and `If-None-Match` on these prefixes: not checked against AWS's documentation this session; tests and the mutation check already pin the code.

## What to know

- Receipts are permanent (10-year lock). A wrong field stays wrong; `receipt_version` lets readers handle later versions, and `code_sha256` identifies receipts from a buggy build.
- A receipt is the collector's claim. It can be trusted because it is written last and cannot be overwritten; the hashes let anyone check it against the files.
- Snapshots stored before the deploy never get receipts and stay `legacy`.
- Every day without receipts is continuity evidence that cannot be recreated later.

## Design review (2026-10-29, Opus; Fable was over its limit and reviews the code before it ships)

Accepted: stops instead of silent drops, the sync script, `pending` vs `orphan`; `run_started_at` and `downloaded_at` instead of one misleading `fetched_at`; `code_sha256`; no HTTP status; the retried-write row in the failure table; the sha12 check on `last_key`; the sha12 in the receipt key; the Sid rename and "the collector cannot" wording; gaps from all receipts before q7 publishes them. Declined: S3 version ids in receipts and IAM condition keys (see Rejected).

## Deviations

- **Building started before the design review landed** (the owner's "go ahead" was read as a go to build). Storage, IAM and the first collector receipt were written test-first, then paused at the owner's word and reworked to the reviewed design. Nothing from the pre-review draft survived unreviewed.
- **The 30-minute safety-download test needed a real `last_key`.** It faked state with a matching hash and no key; under the stricter "unchanged" rule that state now stores a fresh copy, so the test gives the key the collector would have written.
- **An `unchanged` receipt naming missing files stops the build too**, not only a stored one: both mean the raw copy is behind the receipts.
- **The model refuses receipts it does not understand** (a `receipt_version` other than 1, an unknown action, or a snapshot path in another shape) instead of reading them by guesswork. Not in the design; it is what `receipt_version` is for.
- **`--receipts` defaults to `receipts/` beside `--raw`**, not a fixed `data/receipts`, so a build over any raw folder (tests included) never picks up the real local receipts.
- **An intermediate table `snapshot_files`** holds the per-snapshot file counts and receipt status; the stop checks run on it before `snapshot_runs` and the rest are built.
