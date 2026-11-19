# The nightly model build (q2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade**, quoted from the design (`docs/nightly-model.md:3`):

> Grade: production-lean, the data model's own grade ([data-model.md](data-model.md)): tested code, a mutation check (the code is broken on purpose and a test must fail), a fresh review before anything ships. Cheap, boring infrastructure: one function, one bucket, one schedule.

**Goal:** A Lambda function in a stack of its own, `flights-archive-model`, that once a night copies the archive's `receipts/` and `raw/` to its own disk, runs `model.build.build()` unchanged, uploads the five tables write-once under `models/<build id>/` with a manifest, moves `latest.json` forward and reports to healthchecks.io; with the script that deploys it and the local script that compares its model with a Mac build of the same boards.

**Architecture:** A new package, `src/nightly/`, beside `model/`, written as the collector is: a plain `run()` that is given its two buckets, its clock, its ping function and its build function, and a thin `handler()` that wires the real ones. `bucket.py` holds the S3 calls and the in-memory stand-in the tests use; `archive.py` the listings, the copy and the shrink check; `output.py` the manifest, the uploads, the pointer and the clean-up; `measure.py` the peaks and the build's phase times; `handler.py` the night. The infrastructure sits in `model-stack/`: the template, a `samconfig.toml` of its own, and the DuckDB layer's requirements file. `scripts/deploy_nightly.sh` builds and deploys it; `scripts/nightly_check.py` runs the comparison.

**Tech Stack:** Python 3.13 (`.venv`), boto3 1.43.119 (`src/requirements.txt`), DuckDB 1.5.6 (the layer, and `requirements-dev.txt`), AWS SAM (CLI 1.170.0 on this Mac), pytest 9 with botocore's `Stubber`, cfn-lint 1.58.0, POSIX `sh`. No new dependency.

**Spec:** `docs/nightly-model.md` at d636546, with the owner's six calls of 2026-11-19 ("For the owner"), all as recommended. Executors read the design sections their task names; the design's words win over any paraphrase here.

## Global Constraints

- Cost, as the design gives it ("Cost"): about $0.24 a month today at list price and about $0.96 at the gate; $0.06 and $0.22 if Lambda's free allowance covers the run time. healthchecks.io: $0. No paid service is added.
- Run everything with `.venv/bin/...` and `PYTHONPATH=src`. One test file: `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/<file>`. macOS has no `timeout`: `perl -e 'alarm N; exec @ARGV' <command>`. The shell is zsh: read `$?` on a command without a pipe.
- **The record.** No task edits `src/model/`, `src/timeline/load.py`, `counting.py`, `rates.py` or `record.py` (tag `record-v1`). A task that finds it needs to stops and reports to the main session, and the owner is asked. At every commit `git diff main -- src/model src/timeline/load.py src/timeline/counting.py src/timeline/rates.py src/timeline/record.py` prints nothing.
- **The collector does not change.** `template.yaml`, the root `samconfig.toml`, `src/requirements.txt` and `src/collector/` are touched by no task; at every commit `git diff main -- template.yaml samconfig.toml src/requirements.txt src/collector` prints nothing. `src/nightly/` imports no `collector` module (a test holds it, Task 5).
- `src/nightly/` imports the standard library, `model`, `duckdb`, `boto3` and `botocore`, nothing else.
- Every time in `src/nightly/` is timezone-aware UTC; `run()` refuses a naive clock. This Mac's zone is Asia/Jerusalem and CI's is UTC, so a naive conversion is wrong here and passes in CI.
- No AWS call, no `sam deploy`, no `git push` and no `gh` in any task; implementers never push. The one `sam build` is Task 6's, into `model-stack/.aws-sam/` (gitignored, `.gitignore:6`), never the repository root's `.aws-sam/`, and without Docker.
- Tests never write under the checkout: every archive, work folder, stage and model sits under `tmp_path`. No task reads the real archive (`data/`).
- The healthchecks.io address, credentials and the owner's email never go into the repository. Tests use `https://hc-ping.com/abc`, as the collector's do.
- Every task leaves the whole suite passing at its commit, with coverage at 95% or more. From Task 1 on: `PYTHONPATH=src .venv/bin/pytest --cov=collector --cov=model --cov=nightly --cov=timeline --cov-fail-under=95`.
- **Mutation check.** `scripts/mutation_check.py` edits files in place: run it alone, with nothing else running from the checkout. Every new entry goes in `COLLECTOR_MUTATIONS` with a target constant of its own (named in each task), and its name starts with its area: "nightly: " (`src/nightly/`), "model stack: " (`model-stack/`), "deploy: " (the deploy script), "nightly check: " (the comparison script). Entries are picked by target file, not by name, since older entries carry no prefix. Each task runs the entries of the files it touched (the guard stops an empty list, which would run all of them):

  ```sh
  PYTHONPATH=scripts .venv/bin/python -c 'import sys, mutation_check as m
  names = [n for n, ((f, _), _, _) in m.MUTATIONS.items() if f in sys.argv[1:]]
  sys.exit(m.main(names) if names else "no entries target " + " ".join(sys.argv[1:]))' <files the task changed>
  ```

  Expected: every entry CAUGHT, none STALE, none ERROR. Before that, after any edit to a file that entries target, check in seconds that every entry's text is found exactly once:

  ```sh
  PYTHONPATH=scripts .venv/bin/python -c 'import mutation_check as m
  stale = [n for n, ((f, _), old, _) in m.MUTATIONS.items() if (m.ROOT / f).read_text().count(old) != 1]
  print(stale or "every entry found once")'
  ```

  Each entry's break must leave its module importable (`scripts/mutation_check.py`'s docstring), and the test named with it must be one that fails.
- Implementers by kind, one tier above the subagent-driven-development skill's cost guidance: transcription → Sonnet, integration → Opus, architecture → Fable; never Haiku. A fresh Opus reviewer reads each task's diff before the next task starts; a fresh Fable reviewer reads the whole branch once (Task 9). A reviewer's finding, and an implementer's note, is checked against its source before it is folded in.
- Documents in this repository are public: neutral voice; "I" and "my call" only in the owner's own words; agents' work named neutrally, with model names; no pointer to files outside the repository's tracked tree.
- Baseline at d636546 (checked 2026-11-19): `PYTHONPATH=src .venv/bin/pytest -o addopts="" --collect-only -q` collects 1,686 tests; `scripts/mutation_check.py` holds 744 entries, 64 of them in `MODEL_MUTATIONS`; the full check took about 19 minutes on 2026-11-18.

**Main-session steps.** Run by the main session, never by an implementer, and marked "(main session)":
- before Task 6, the read-only account check under "What this plan decided", reserved concurrency;
- the whole-branch review (Task 9) and the full mutation check, alone (Task 11);
- every commit that records a result, every push and the merge, each on the owner's go.

The design's "Deploy and prove" is the owner's, at the end of this plan.

## Review Focus

The input classes the design implies but its test table does not name, most likely first. Each has its test in the owning task.

1. **The archive grows while the copy runs.** The collector writes every 2 minutes, and the copy takes seconds to minutes. Expected: only the keys listed are copied, and the manifest describes the listing, not the bucket at upload time. Test: `test_objects_written_during_the_copy_are_left_out` (Task 5).
2. **A key the copy cannot place**: one that climbs out of the work folder (`raw/../../x`), one ending in `/` (a folder object the S3 console makes), a zero-byte object. Expected: the first two fail the night before any download, naming the key; a zero-byte object is copied as an empty file. Tests: `test_a_key_the_copy_cannot_place_fails_before_any_download` and `test_a_zero_byte_object_is_copied` (Task 2).
3. **A pointer the function cannot read**: not JSON, not an object, or without `archive.receipts.newest_key` (edited by hand, or written by a later manifest version). Expected: the night fails before anything is written, and the pointer is never replaced on a guess. Tests: `test_an_unreadable_pointer_fails` (Task 3) and `test_an_unreadable_pointer_fails_the_night` (Task 5).
4. **Files in `data/` that S3 does not hold, for the comparison**: Finder's `.DS_Store`, and boards synced after the Lambda's listing. Expected: dot-files are not counted, keys past the manifest's newest are left out, and the digests compare like with like. Tests: `test_dot_files_are_not_counted` and `test_boards_after_the_newest_keys_are_left_out` (Task 8).
5. **Configuration slips**: one bucket named for both, a missing variable, an empty archive (a wrong bucket name, with no pointer yet to compare against). Expected: refused at start-up, or the night fails on the build's own "no snapshot files" with nothing under `models/`. Tests: `test_config_refuses_a_missing_or_shared_bucket` and `test_an_empty_archive_fails_the_night` (Task 5).

## Order, and why

- Tasks 1 to 3 are the parts `run()` is made of, each tested alone: the S3 calls first, since the in-memory stand-in every later test uses is checked there against what S3 answers.
- Task 4 is small and touches frozen modules at run time (it wraps three of their functions to time them, without editing them), so it gets a review of its own.
- Task 5 puts the night together and holds the design's "whole path" test.
- Tasks 6 to 8 are the infrastructure and the two scripts. Task 7's tests read Task 6's `model-stack/samconfig.toml`; Task 8 compares Task 5's output.
- Task 9 reviews the whole branch before the documents describe it; Task 11 measures the counts the documents carry.

| Task | What | Implementer |
|---|---|---|
| 1 | The bucket: S3 calls and the in-memory stand-in; coverage in CI | integration (Opus) |
| 2 | The archive: listings, the copy, the shrink check | integration (Opus) |
| 3 | The output: manifest, uploads, pointer, clean-up | integration (Opus) |
| 4 | Measurements: peaks and the build's phase times | integration (Opus) |
| 5 | The night: `run()`, pings, extensions, the handler | integration (Opus) |
| 6 | The model stack: template, `samconfig.toml`, layer; lint in CI | integration (Opus) |
| 7 | The deploy script | integration (Opus) |
| 8 | The comparison script | integration (Opus) |
| 9 | Whole-branch review | Fable reviewer (main session) |
| 10 | Documents | transcription (Sonnet) |
| 11 | Final verification | main session |
| – | Deploy and prove | the owner, at the terminal |

**Coverage of the design.**
- "What one night does", steps 1 to 10, and the drill: Task 5, from Tasks 1 to 4.
- 1, "Copy, not read": Task 2 (listing order, every page, sizes, a failed download); Task 1 (pages).
- 2, "The stage between nights": option (a) only, Task 5 (an emptied work folder, a new stage every night). Option (b) is designed for later and is not built.
- 3, "Sizing": Task 6 (the settings); Tasks 4 and 5 (what each night logs).
- 4, "Output and readers": Task 3, with the upload order and failures in Task 5.
- 5, "Stack and permissions": Task 6; the deploy script, Task 7. One build at a time: "What this plan decided".
- 6, "Alerts": Task 5 (pings); the check itself is the owner's.
- 7, "Packaging": Task 6 (layer, pins), Task 5 (the extension check).
- 8, "Schedule": Task 6.
- "The frozen record": Task 8, run by the owner (step 4 below).
- "Tests and mutation checks", row by row: listing, Tasks 1 and 2; copy, Task 2; work folder, build call, whole path, upload order, failure, Task 5; pointer, clean-up, manifest, Task 3 (and Task 5 for clean-up after a failure); a shrinking archive, Tasks 2 and 5; extensions, pings, Task 5; template, permissions, packaging, Task 6; deploy script, Task 7; the comparison script, Task 8.
- "Left to the plan": "What this plan decided", below; the documents, Task 10.

## What this plan decided

The design leaves these to the plan.

- **Names.** Package `src/nightly/`. Stack folder `model-stack/`: `template.yaml`, `samconfig.toml`, `layer/requirements.txt`. Scripts `scripts/deploy_nightly.sh` and `scripts/nightly_check.py`. Work folder `/tmp/nightly`. Environment variables `ARCHIVE_BUCKET`, `MODEL_BUCKET`, `HEALTHCHECK_URL`. Resources `ModelBucket`, `DuckDBLayer`, `ModelFunction`, `ModelLogs` (log group `/flights-archive-model/nightly`); parameters `ArchiveBucketName`, `HealthcheckUrl`, `ScheduleState`; outputs `ModelBucketName`, `ModelFunctionName`.
- **The split, and the in-memory S3.** The collector keeps `S3Store` and its in-memory `MemoryStore` side by side in `src/collector/store.py`; `src/nightly/bucket.py` does the same with `S3Bucket` and `MemoryBucket`, behind one six-method `Bucket` protocol. `S3Bucket`'s exact S3 parameters are pinned with botocore's `Stubber`, as `tests/test_store.py` pins the collector's. `MemoryBucket` answers as S3 does (write-once, `If-Match`, 404 as `None`) and lets a test fail a call, shorten a download or write as another run would.
- **Downloads.** 16 at once (a thread pool, with the client's connection pool set to 16), the starting value until the first run in AWS shows the copy's seconds. Every `get_object` carries `ChecksumMode="ENABLED"`: the collector stores every page and receipt with `ChecksumAlgorithm="SHA256"` (`src/collector/store.py:57`), and botocore 1.43.121's default `response_checksum_validation` is `when_supported` (`botocore/configprovider.py:201-206`), so a reply that does not match its stored checksum raises. Each file's size is then checked against the listing.
- **Uploads** are single `put_object` calls with `IfNoneMatch="*"` and `ChecksumAlgorithm="SHA256"` ("Design and code", 2).
- **The deploy script** takes one argument, `DISABLED` (the default) or `ENABLED`, and nothing else. It reads the healthchecks.io address from standard input, with echo off at a terminal, and refuses an address that does not start with `https://hc-ping.com/`. It changes into `model-stack/` before any `sam` call and names on the command line every setting it relies on, so no `samconfig.toml` can change its target ("Design and code", 1, 5 and 6).
- **Reserved concurrency (main session, before Task 6).** `aws sts get-caller-identity --profile flights-sam` (account 137953273942, user doron-admin), then the read-only `aws lambda get-account-settings --profile flights-sam --region il-central-1 --query AccountLimit`. The field is `UnreservedConcurrentExecutions` (botocore's Lambda model, `GetAccountSettings`). AWS lets a function reserve up to that value minus 100 (the design's quote), so at 101 or more Task 6 adds `ReservedConcurrentExecutions: 1` with a test pinning it; below that it adds nothing. The figure and the outcome go in "Deviations". If the main session does not run the check, the owner runs it before Task 6 starts.
- **`MaximumEventAgeInSeconds: 60`**, the shortest Lambda allows: cfn-lint 1.58.0's schema for `AWS::Lambda::EventInvokeConfig` gives 60 to 21,600.
- **The x86-64 run** is the owner's (step 3 below), and only if the first arm64 run's build, its staging, statements and writing together, takes more than 144 s, three times this Mac's 48 s. The design's 48 s is a build without the copy, so the copy is left out of the comparison.
- **The phase times.** The design's switch rule reads "staging is its largest step", which a single "staging and build" figure cannot show ("Design and code", 3). `measure.phase_timers()` wraps `model.stage.stage`, `model.rules.build_tables` and `model.build.write_model` in timers for the length of one build and puts the originals back after. No frozen file changes, and a test shows a timed build's tables equal an untimed one's.
- **The function's code fingerprint** is computed the way the collector's is (`src/collector/core.py:230`), by a copy of that five-line function in `nightly/output.py`, since the function must not import `collector`; a test holds the two equal on the same folder.
- **One run at a time on the disk.** `run()` empties `/tmp/nightly` first and builds with the stage, temp and model folders inside it: every night is a from-scratch build, option (a). The manifest's `build.stage_reused` is therefore always `false` until option (b).
- **CI.** `--cov=nightly` from Task 1; `model-stack/template.yaml` added to the cfn-lint line in Task 6.
- **What the new tests add to the mutation check.** About 80 entries. Their target test files run in about 1 to 5 s each on this Mac (estimated, UNVERIFIED), so the full check grows from about 19 minutes to perhaps 22 to 25. Task 11 measures it. `TIME_LIMIT` stays at 120 s unless an unmutated target run passes about 20 s.
- **Documents**: Task 10, as the design lists them, and the design's own status line.

## Design and code

Where the plan departs from or adds to the design, and what in the design proved ambiguous. Each is for the owner to see.

1. **`sam build` takes no stack name.** The design: the script "names the template, the build folder and the stack `flights-archive-model` on every `sam` call". SAM CLI 1.170.0's `sam build --help` lists `--template-file` and `--build-dir` but no `--stack-name`. The stack is named on every `sam deploy`; `sam build` names the template and the build folder.
2. **No multipart upload, so the lifecycle rule has nothing to end.** The design's lifecycle rule rests on "boto3 uploads a file over 8 MB in parts (`multipart_threshold`, `s3transfer`)". But s3transfer 0.19.3, the version installed with the pinned boto3, does not accept `IfNoneMatch` in `upload_file` (`TransferManager.ALLOWED_UPLOAD_ARGS`), so a write-once upload of a file cannot go through it. The tables go up as single `put_object` calls (4.5 MB today, about 80 MB at one year by the design's figures). The rule ending unfinished multipart uploads after 1 day stays as the design has it: it is free and covers a later change to multipart. The owner may drop it; the template test pins it until then.
3. **The phase times are an addition.** The design logs "seconds for each step (listing, copy, staging and build, upload)", one figure for the build, yet its switch rule needs "staging is its largest step". The plan logs the build's three phases beside the build's total, timed from outside `build()` (above). Without them, the 300 s rule could not be applied from the log.
4. **The manifest's `measured`** can only hold what is known when it is written: the seconds of the listing, the copy and the build (with its phases), and the peaks. The upload, pointer and clean-up seconds and the total come after it, so they are in the summary line only.
5. **"It refuses any other stack name"** has no input to refuse as the design describes the script: it names its stack itself. The plan reads it as two refusals. No argument may carry a stack name, since anything but `DISABLED` or `ENABLED` is refused. And `model-stack/samconfig.toml` must name `flights-archive-model`, so that the folder's settings, which a bare `sam` command typed there follows, cannot drift to the collector's stack.
6. **Identity first.** The script refuses a bad argument or a wrong `samconfig.toml` before its identity check, since neither needs AWS. The identity check is still its first AWS call and comes before every `sam` call.
7. **`profile = "flights-sam"` in `model-stack/samconfig.toml`** is an addition. A bare `sam deploy` typed in that folder would otherwise use the machine's default AWS profile, which is not this project's. The root `samconfig.toml` is left as it is.
8. **The deploy runs in a terminal window**, not through the coding agent's `!` prefix: it asks for the address, and `--confirm-changeset` asks for a keypress.
9. **The run by hand is asynchronous** (`--invocation-type Event`), as the schedule's is, read back from the log group and healthchecks.io. A synchronous `aws lambda invoke` waits on the CLI's read timeout, and on a timeout the CLI may send the call again (both from memory, UNVERIFIED), which would start a second build.
10. **`Config` refuses one bucket named for both**, an addition: the function deletes under `models/` in the bucket named `MODEL_BUCKET`.
11. **Not confirmed here:**
    - where SAM looks for `samconfig.toml` (the working folder or the template's), which is why the script names every setting itself;
    - that SAM builds `CodeUri: ../src/` from a template in a subfolder, which Task 6 checks with a local `sam build`;
    - the Lambda context's attribute names (`aws_request_id`, `memory_limit_in_mb`, `get_remaining_time_in_millis`), from memory, which the owner's first run checks;
    - that `ru_maxrss` is kilobytes on Linux and bytes on macOS, from memory, which Task 4's test checks on both platforms through CI.

---

### Task 1: The bucket: S3 calls and the in-memory stand-in

Implementer: integration (Opus). Design: section 4 (the conditions and S3's answers) and "Tests and mutation checks", the listing row.

**Files:**
- Create: `src/nightly/__init__.py` (a one-line docstring naming the design), `src/nightly/bucket.py`, `tests/test_nightly_bucket.py`
- Modify: `.github/workflows/ci.yml` (`--cov=nightly` after `--cov=model`), `scripts/mutation_check.py` (`NIGHTLY_BUCKET = ("src/nightly/bucket.py", ["tests/test_nightly_bucket.py"])`, the entries)

**Interfaces:**
- Produces, in `src/nightly/bucket.py`:
  - `class Item(NamedTuple)`: `key: str`, `size: int`;
  - `class ConditionFailed(Exception)`: S3 refused a conditional write, with 412 `PreconditionFailed` or 409 `ConditionalRequestConflict`;
  - `class Bucket(Protocol)`: `name: str`; `list(prefix: str) -> list[Item]` (every object under the prefix, in key order); `download(key: str, path: Path) -> None`; `read(key: str) -> tuple[bytes, str] | None` (the body and its ETag, `None` when the key is missing); `put_new(key: str, body: bytes) -> None` (write-once; `ConditionFailed` when the key exists or the write raced); `replace(key: str, body: bytes, etag: str) -> None` (only while the object's ETag is `etag`; `ConditionFailed` otherwise); `delete(key: str) -> None`;
  - `class S3Bucket(client, name: str)`, the protocol on a boto3 S3 client:
    - `list`: `list_objects_v2(Bucket=, Prefix=)`, then with `ContinuationToken=` each `NextContinuationToken` while `IsTruncated`, written as a loop (not a paginator);
    - `download` and `read`: `get_object(Bucket=, Key=, ChecksumMode="ENABLED")`; `read` maps `NoSuchKey` or `404` to `None`, as `S3Store.read_state` does, and raises any other error;
    - `put_new`: `put_object(Bucket=, Key=, Body=, ContentType=, IfNoneMatch="*", ChecksumAlgorithm="SHA256")`;
    - `replace`: the same with `IfMatch=etag` in place of `IfNoneMatch`;
    - `ContentType` is `application/json` for a key ending `.json`, else `application/octet-stream`;
    - a `ClientError` whose code is `PreconditionFailed` or `ConditionalRequestConflict` becomes `ConditionFailed`; any other is raised as it is;
    - `delete`: `delete_object(Bucket=, Key=)`;
  - `class MemoryBucket(name: str = "memory", objects: dict[str, bytes] | None = None)`, the protocol in memory:
    - `objects: dict[str, bytes]`, and an ETag per key that changes on every write;
    - `ops: list[tuple[str, str]]`: `(operation, key or prefix)` for each call, in order;
    - `fail: dict[tuple[str, str], list[BaseException]]`: a call of that operation on that key raises, and removes, the first exception in its list;
    - `short: set[str]`: keys whose download writes one byte fewer;
    - `hooks: dict[tuple[str, str], Callable[[], None]]`: called once, then removed, before that operation on that key;
    - `force(key: str, body: bytes) -> None`: a write as another run would make it, with a new ETag and no entry in `ops`;
    - `put_new` and `replace` refuse what S3 refuses, with `ConditionFailed`.

- [ ] **Step 1: Write the failing tests** (`tests/test_nightly_bucket.py`; a stubbed client as `tests/test_store.py` makes one, with `stub.assert_no_pending_responses()` at the end):
  - `test_list_reads_every_page`: a first page `{"Contents": [{"Key": "raw/b", "Size": 4}], "IsTruncated": True, "NextContinuationToken": "t"}`, a second expected with `ContinuationToken: "t"` and holding `raw/a`, size 3. `list("raw/") == [Item("raw/a", 3), Item("raw/b", 4)]`.
  - `test_an_empty_prefix_lists_nothing`: a reply without `Contents` gives `[]`.
  - `test_download_asks_for_the_checksum_and_writes_the_body`: expected params `{"Bucket": "b", "Key": "raw/k", "ChecksumMode": "ENABLED"}`; the file holds the body's bytes.
  - `test_read_returns_the_body_and_its_etag`; `test_a_missing_key_reads_as_none`, parametrized over `NoSuchKey` and `404`; `test_access_denied_is_not_hidden`.
  - `test_put_new_is_write_once`, parametrized over `models/x/flights.parquet` (`application/octet-stream`) and `latest.json` (`application/json`): the expected params include `IfNoneMatch: "*"` and `ChecksumAlgorithm: "SHA256"`.
  - `test_replace_carries_the_etag`: `IfMatch: '"e1"'`, no `IfNoneMatch`.
  - `test_a_refused_condition_is_condition_failed`, parametrized over `put_new` and `replace`, and over (`PreconditionFailed`, 412) and (`ConditionalRequestConflict`, 409).
  - `test_other_write_errors_are_not_hidden`: `AccessDenied` on `put_new` raises `ClientError`.
  - `test_delete_names_one_key`.
  - `test_the_memory_bucket_answers_as_s3_does`: `put_new` on an existing key and `replace` with a stale ETag or on a missing key raise `ConditionFailed` and change nothing; `read` of a missing key is `None`; `list` gives one prefix's keys in key order with their sizes; `ops` records each call; a `fail` list raises once per call and then lets the call through; `short` writes one byte fewer; a hook runs once; `force` changes the ETag, so a `replace` with the old one fails.
- [ ] **Step 2: Run; fail.** `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/test_nightly_bucket.py` (no module `nightly`).
- [ ] **Step 3: Implement** `src/nightly/bucket.py`, and add `--cov=nightly` to `.github/workflows/ci.yml`.
- [ ] **Step 4: Run; pass.** Then the full suite with the coverage command in "Global Constraints".
- [ ] **Step 5: Mutation entries** (`NIGHTLY_BUCKET`):
  - "nightly: write-once condition dropped" (`IfNoneMatch="*",` removed) → `test_put_new_is_write_once`;
  - "nightly: pointer condition dropped" (`IfMatch=etag,` removed) → `test_replace_carries_the_etag`;
  - "nightly: a 409 not a failed condition" (`ConditionalRequestConflict` left out of the codes) → `test_a_refused_condition_is_condition_failed`;
  - "nightly: listing stops after the first page" → `test_list_reads_every_page`;
  - "nightly: stored checksum not checked" (`ChecksumMode="ENABLED"` removed from `download`) → `test_download_asks_for_the_checksum_and_writes_the_body`;
  - "nightly: a missing pointer raises" (`NoSuchKey` and `404` no longer `None`) → `test_a_missing_key_reads_as_none`;
  - "nightly: memory bucket replaces an existing key" (its `put_new` check removed) → `test_the_memory_bucket_answers_as_s3_does`.

  Run the entries of `src/nightly/bucket.py`.
- [ ] **Step 6: Commit** (`q2: the nightly function's S3 calls, write-once and conditional, and an in-memory bucket for its tests`).
- [ ] **Step 7: Review (Opus).**

### Task 2: The archive: listings, the copy, the shrink check

Implementer: integration (Opus). Design: "What one night does", steps 3 and 4; section 1, "Copy, not read" (the order of the listings, a copy that is not complete must fail).

**Files:**
- Create: `src/nightly/archive.py`, `tests/test_nightly_archive.py`
- Modify: `scripts/mutation_check.py` (`NIGHTLY_ARCHIVE = ("src/nightly/archive.py", ["tests/test_nightly_archive.py"])`, the entries)

**Interfaces:**
- Consumes: Task 1's `Item`, `Bucket`, `MemoryBucket`.
- Produces, in `src/nightly/archive.py`:
  - `RECEIPTS = "receipts/"`, `RAW = "raw/"`, `DOWNLOAD_WORKERS = 16`;
  - `class CopyError(Exception)`, `class ArchiveShrunk(Exception)`;
  - `listing_sha256(items: Iterable[Item]) -> str`: the SHA-256 (hex) of one line per object, `f"{key}\t{size}\n"`, in key order, UTF-8;
  - `@dataclass(frozen=True) class Listing`: `prefix: str`, `items: tuple[Item, ...]` (key order); properties `objects: int`, `bytes: int`, `newest_key: str | None`, `sha256: str`; `summary() -> dict` giving `{"objects", "bytes", "newest_key", "listing_sha256"}`;
  - `list_archive(archive: Bucket) -> tuple[Listing, Listing]`: `receipts/`, then `raw/`, one call straight after the other;
  - `check_not_shrunk(previous: dict | None, receipts: Listing, raw: Listing) -> None`: `previous` is the pointer's manifest, or `None` for the first night. For each of `receipts` and `raw`, `ArchiveShrunk` naming both figures when the listing holds fewer objects than `previous["archive"][name]["objects"]`, or when that names a newest key and the listing's is older (string order, which is time order for the collector's keys; a listing with none counts as older);
  - `copy(archive: Bucket, listing: Listing, dest: Path, workers: int = DOWNLOAD_WORKERS) -> None`: every item to `dest / key`, folders made, `workers` downloads at once. Before any download, `CopyError` for a key ending in `/` or one whose path does not resolve inside `dest`. After each download, `CopyError(f"{key}: {n} bytes copied, the listing says {size}")` when the file's size differs. The first error raised by any download is raised by `copy`.

- [ ] **Step 1: Write the failing tests:**
  - `test_receipts_are_listed_before_boards`: `bucket.ops == [("list", "receipts/"), ("list", "raw/")]`, and each listing holds only its prefix's keys.
  - `test_the_listing_digest_covers_every_key_and_size`: `listing_sha256([Item("a", 1)]) == hashlib.sha256(b"a\t1\n").hexdigest()`; the same for any order of the input; another digest when one size changes, and when a key is added.
  - `test_a_listing_reports_its_objects_bytes_and_newest_key`: and an empty listing gives 0, 0 and `None`.
  - `test_every_listed_key_lands_at_its_path_with_its_size`: three objects over two date folders; each file under `dest` has its object's bytes.
  - `test_a_short_download_fails_the_copy`: a key in `short`; `CopyError` naming the key.
  - `test_a_failed_download_fails_the_copy`: `fail[("download", key)] = [OSError("reset")]`; `copy` raises `OSError`.
  - `test_a_key_the_copy_cannot_place_fails_before_any_download` (Review Focus 2), parametrized over `raw/../../escape.json.gz` and `raw/date=2026-10-30/`: `CopyError` naming the key, and no `download` in `bucket.ops`.
  - `test_a_zero_byte_object_is_copied` (Review Focus 2).
  - `test_downloads_run_at_once`: a `MemoryBucket` whose download waits on a `threading.Barrier(2, timeout=5)`; `copy(..., workers=2)` of two objects completes.
  - `test_a_listing_smaller_than_the_pointers_fails`, parametrized over `receipts` and `raw`, and over one object fewer and an older newest key: `ArchiveShrunk`.
  - `test_the_same_or_a_larger_archive_passes`: equal figures, more objects with a newer key, and `previous=None`.
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`NIGHTLY_ARCHIVE`):
  - "nightly: boards listed before receipts" → `test_receipts_are_listed_before_boards`;
  - "nightly: listing digest ignores sizes" → `test_the_listing_digest_covers_every_key_and_size`;
  - "nightly: copied size not checked" → `test_a_short_download_fails_the_copy`;
  - "nightly: a failed download ignored" (the futures' results not read) → `test_a_failed_download_fails_the_copy`;
  - "nightly: a key outside the work folder copied" → `test_a_key_the_copy_cannot_place_fails_before_any_download`;
  - "nightly: one download at a time" (the pool given 1 worker) → `test_downloads_run_at_once` (a broken barrier, not a hang: its timeout is 5 s);
  - "nightly: fewer objects accepted" and "nightly: an older newest key accepted" → `test_a_listing_smaller_than_the_pointers_fails`.

  Run the entries of `src/nightly/archive.py`.
- [ ] **Step 6: Commit** (`q2: list receipts then boards, copy exactly what was listed with each size checked, and stop on a shrunk archive`).
- [ ] **Step 7: Review (Opus).**

### Task 3: The output: manifest, uploads, pointer, clean-up

Implementer: integration (Opus). Design: section 4, "Output and readers" (the layout, the build id, the manifest's fields, the pointer only forward, retention).

**Files:**
- Create: `src/nightly/output.py`, `tests/test_nightly_output.py`
- Modify: `scripts/mutation_check.py` (`NIGHTLY_OUTPUT = ("src/nightly/output.py", ["tests/test_nightly_output.py"])`, the entries)

**Interfaces:**
- Consumes: Task 1's `Bucket`, `MemoryBucket`, `ConditionFailed`; Task 2's `Listing`; `model.build.TABLES`; `model.stage.fingerprint`.
- Produces, in `src/nightly/output.py`:
  - `MANIFEST_VERSION = 1`, `POINTER = "latest.json"`, `MODELS = "models/"`, `KEEP_DAYS = 30`, `POINTER_TRIES = 3`;
  - `class PointerError(Exception)`;
  - `build_id(started: datetime, request_id: str) -> str`: `f"{started:%Y%m%dT%H%M%SZ}-{request_id[:8]}"`; `ValueError` for a time that is not timezone-aware UTC;
  - `code_fingerprint(directory: Path) -> str`, computed as `collector.core.code_fingerprint` is; `CODE_SHA256 = code_fingerprint(Path(__file__).parent)`;
  - `table_entries(out_dir: Path, build_id: str, rows: dict[str, int]) -> dict[str, dict]`: for each of `TABLES`, `{"key": f"models/{build_id}/{table}.parquet", "bytes": n, "sha256": hex}`, plus `"rows"` where `rows` has the table (`build()` reports four, not `snapshot_runs`);
  - `manifest(build_id: str, started: datetime, finished: datetime, tables: dict, archive_bucket: str, receipts: Listing, raw: Listing, memory_limit: str, threads: int, measured: dict) -> bytes`: `json.dumps(..., sort_keys=True, indent=2)` of exactly `manifest_version`, `build_id`, `started_at`, `finished_at` (ISO, `+00:00`), `tables`, `archive` (`{"bucket": …, "receipts": receipts.summary(), "raw": raw.summary()}`), `code` (`model_fingerprint`: `model.stage.fingerprint()`; `function_sha256`: `CODE_SHA256`; `duckdb`: `duckdb.__version__`; `python`: `platform.python_version()`; `machine`: `platform.machine()`), `build` (`{"memory_limit": …, "threads": …, "stage_reused": False}`) and `measured`;
  - `upload_build(models: Bucket, build_id: str, out_dir: Path, manifest: bytes) -> None`: `put_new` of each table in `TABLES` order, then of `models/<build_id>/manifest.json`;
  - `read_pointer(models: Bucket) -> tuple[dict, str] | None`: the pointer's manifest and ETag; `ValueError` when it is not JSON or not an object;
  - `newest_receipt(manifest: dict) -> str`: `manifest["archive"]["receipts"]["newest_key"]`; `ValueError` when missing or not a string;
  - `move_pointer(models: Bucket, manifest: bytes, newest: str, tries: int = POINTER_TRIES) -> tuple[str, str]`: `("moved", this build's id)` or `("kept", the pointer's build id)`. Each try reads the pointer. With none, it is written with `put_new`. Otherwise, when `newest` is older than the pointer's newest receipt, it is kept; else it is replaced with `replace(..., etag)`. On `ConditionFailed` the next try reads again. After `tries` failures, `PointerError`;
  - `clean_up(models: Bucket, now: datetime, keep: str, days: int = KEEP_DAYS) -> list[str]`: lists `models/`, groups the keys by build id, and deletes every key of each build whose id starts with a time (`^\d{8}T\d{6}Z-`) more than `days` before `now`, except `keep`. Keys whose second part does not start with such a time are left. Returns the deleted ids, sorted.

- [ ] **Step 1: Write the failing tests:**
  - `test_build_id_is_the_start_time_and_the_request_id`: `build_id(datetime(2026, 11, 20, 1, 40, 3, tzinfo=timezone.utc), "1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809") == "20261120T014003Z-1a2b3c4d"`; a naive time raises `ValueError`.
  - `test_the_function_fingerprint_is_made_as_the_collectors`: on a folder of two `.py` files, `code_fingerprint(d) == collector.core.code_fingerprint(d)`; one byte changed changes it; `CODE_SHA256 == code_fingerprint(<src/nightly>)`.
  - `test_table_entries_hash_the_files_written`: each entry's `sha256` and `bytes` equal the file's; four carry `rows`, `snapshot_runs` none.
  - `test_the_manifest_records_the_build`: the nine top-level keys exactly; `code.model_fingerprint == model.stage.fingerprint()`; `code.function_sha256 == CODE_SHA256`; `build == {"memory_limit": "1GB", "threads": 2, "stage_reused": False}`; `archive.receipts == receipts.summary()`.
  - `test_upload_build_puts_the_tables_then_the_manifest`: `ops` is five `put_new` in `TABLES` order, then the manifest's; each object's bytes are the file's.
  - `test_the_first_pointer_is_written_once`: `("moved", id)`, and `ops` ends with `("put_new", "latest.json")`.
  - `test_a_newer_build_moves_the_pointer` and `test_the_same_newest_receipt_moves_the_pointer`: a `replace`.
  - `test_an_older_build_leaves_the_pointer`: `("kept", <the pointer's build id>)`, the pointer's bytes unchanged, no `replace` in `ops`.
  - `test_a_pointer_changed_meanwhile_is_read_again`: a hook on `("replace", "latest.json")` calls `force` once; the second try moves it; two `read`s.
  - `test_a_409_is_read_again`: `fail[("replace", "latest.json")] = [ConditionFailed("409")]`; moved on the second try.
  - `test_a_first_write_that_loses_the_race_reads_again`: a hook on `("put_new", "latest.json")` forces a pointer with an older newest receipt; the second try replaces it.
  - `test_three_refusals_fail_the_night`: every `replace` refused; `PointerError` after exactly three `read`s and three `replace`s.
  - `test_an_unreadable_pointer_fails` (Review Focus 3), parametrized over `b"not json"`, `b"[]"` and a manifest without `newest_key`: `ValueError`, nothing written.
  - `test_old_builds_are_deleted`: builds started 31, 29 and 1 days before `now`, the pointer on the newest: the 31-day build's keys are deleted, nothing else; returns its id.
  - `test_the_pointers_build_stays_however_old`: `keep` started 40 days back and another 35: only the 35-day build goes.
  - `test_a_build_exactly_30_days_old_stays`.
  - `test_keys_that_are_not_a_build_are_left`: `models/notes.txt` and `models/odd/x.parquet` stay.
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`NIGHTLY_OUTPUT`):
  - "nightly: pointer comparison turned round" → `test_an_older_build_leaves_the_pointer`;
  - "nightly: pointer tried four times" (`POINTER_TRIES = 4`) → `test_three_refusals_fail_the_night`;
  - "nightly: a refused pointer write not read again" (`ConditionFailed` raised on, not retried) → `test_a_pointer_changed_meanwhile_is_read_again`;
  - "nightly: a lost first write not read again" → `test_a_first_write_that_loses_the_race_reads_again`;
  - "nightly: the pointer's build deleted" → `test_the_pointers_build_stays_however_old`;
  - "nightly: a 30-day build deleted" (the comparison made inclusive) → `test_a_build_exactly_30_days_old_stays`;
  - "nightly: table hash of the wrong file" → `test_table_entries_hash_the_files_written`;
  - "nightly: manifest before the tables" → `test_upload_build_puts_the_tables_then_the_manifest`;
  - "nightly: function fingerprint ignores file content" → `test_the_function_fingerprint_is_made_as_the_collectors`.

  Run the entries of `src/nightly/output.py`.
- [ ] **Step 6: Commit** (`q2: the manifest, the write-once uploads, a pointer that only moves forward, and the 30-day clean-up`).
- [ ] **Step 7: Review (Opus).**

### Task 4: Measurements: peaks and the build's phase times

Implementer: integration (Opus). Design: section 3, "What the function logs each night"; "Design and code", 3.

**Files:**
- Create: `src/nightly/measure.py`, `tests/test_nightly_measure.py`
- Modify: `scripts/mutation_check.py` (`NIGHTLY_MEASURE = ("src/nightly/measure.py", ["tests/test_nightly_measure.py"])`, the entries)

**Interfaces:**
- Consumes: `model.stage.stage`, `model.rules.build_tables`, `model.build.write_model` (read, wrapped, put back; never edited). `model.build.run` looks up `stage.stage` and `rules.build_tables` on their modules at call time, and `build()` calls `write_model` by its module-level name (`src/model/build.py:44`, `:46`, `:146`), so a wrapper set on each module is the one called.
- Produces, in `src/nightly/measure.py`:
  - `peak_memory_mb() -> float`: `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` in MB, read as bytes on `darwin` and as kilobytes elsewhere;
  - `class Sampler(read: Callable[[], int], every: float = 1.0)`, a context manager: a daemon thread calls `read` every `every` seconds while the block runs, and once at entry and once at exit; `peak: int` is the largest value read. The thread is stopped and joined at exit;
  - `PHASES = (("staging", model.stage, "stage"), ("statements", model.rules, "build_tables"), ("writing", model.build, "write_model"))`;
  - `phase_timers(seconds: dict[str, float]) -> ContextManager[None]`: for the block, each function in `PHASES` is replaced by a wrapper that adds its wall time to `seconds[name]`, raised or not. The originals are put back at exit, raised or not.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_sampler_keeps_the_peak`: `read` gives 3, 9, 4 and then 4; `every=0.01`; after the block, `peak == 9`.
  - `test_the_sampler_stops_its_thread`: after the block, no thread the sampler started is alive.
  - `test_peak_memory_is_in_megabytes_on_this_platform`: `20 < peak_memory_mb() < 65536` (a Python process with DuckDB loaded). Read as the wrong unit, macOS gives about 1,000 times too much and Linux 1,000 times too little; CI runs it on Linux and the Mac locally.
  - `test_phase_timers_time_a_real_build`: a two-day archive written with `tests/model_helpers.py`; `model.build.build` inside `phase_timers(s)`; `s` has the three names, each above 0, their sum at most the build's wall time.
  - `test_a_timed_build_equals_an_untimed_one`: the same archive built with and without the timers; `compare_tables` and `compare_load` (`model_helpers.check_script()`) give `[]`.
  - `test_phase_timers_put_the_functions_back`, parametrized over a block that ends and one that raises `ValueError`: afterwards `model.stage.stage`, `model.rules.build_tables` and `model.build.write_model` are the originals (`is`).
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite, and `tests/test_model_tagged.py` alone: the frozen modules' own tests must not notice the timers.
- [ ] **Step 5: Mutation entries** (`NIGHTLY_MEASURE`):
  - "nightly: phase timers left in place" → `test_phase_timers_put_the_functions_back`;
  - "nightly: sampler keeps the last reading" → `test_the_sampler_keeps_the_peak`;
  - "nightly: peak memory in the wrong unit" (the platform test turned round) → `test_peak_memory_is_in_megabytes_on_this_platform`.

  Run the entries of `src/nightly/measure.py`.
- [ ] **Step 6: Commit** (`q2: peak memory and disk, and the build's staging, statements and writing timed from outside`).
- [ ] **Step 7: Review (Opus).** The reviewer confirms that `src/model/` is untouched and that nothing outside a `phase_timers` block sees a wrapper.

### Task 5: The night: `run()`, pings, extensions, the handler

Implementer: integration (Opus). Design: "What one night does", steps 1 to 10, and the drill; sections 3 (the log), 6 (alerts), 7 (no download at run time); "What you might not think to ask".

**Files:**
- Create: `src/nightly/handler.py`, `tests/nightly_helpers.py`, `tests/test_nightly_handler.py`
- Modify: `scripts/mutation_check.py` (`NIGHTLY_HANDLER = ("src/nightly/handler.py", ["tests/test_nightly_handler.py"])`, the entries)

**Interfaces:**
- Consumes: Tasks 1 to 4; `model.build.build`, `model.build.TABLES`, `model.stage.fingerprint`.
- Produces, in `src/nightly/handler.py`:
  - `MEMORY_LIMIT = "1GB"`, `THREADS = 2`, `WORK_DIR = Path("/tmp/nightly")`;
  - `@dataclass(frozen=True) class Config`: `archive_bucket: str`, `model_bucket: str`, `healthcheck_url: str = ""`, `work_dir: Path = WORK_DIR`; `from_env(env: dict[str, str]) -> Config`: `ValueError` naming each missing or blank `ARCHIVE_BUCKET` or `MODEL_BUCKET`, and when the two are the same; `HEALTHCHECK_URL` optional, its trailing `/` removed;
  - `@dataclass(frozen=True) class Runtime`: `request_id: str`, `memory_mb: int`, `seconds_left: Callable[[], float]`;
  - `class DrillError(Exception)`, `class ExtensionError(Exception)`;
  - `parse_event(event) -> str`: `"drill"` only for `{"drill": True}` (an exact `True`), else `"build"`;
  - `ping(url: str, message: str) -> None`: as the collector's (`src/collector/handler.py:61`), without a User-Agent: nothing when `url` is empty, the message's first 10,000 bytes posted with a 10 s timeout, any error logged as "healthcheck ping failed" and never raised;
  - `installed_extensions(con: duckdb.DuckDBPyConnection | None = None) -> list[str]`: sorted names from `duckdb_extensions()` that are `installed` with an `install_mode` other than `'STATICALLY_LINKED'`; with no connection given, on a new one, closed after;
  - `run(cfg: Config, archive: Bucket, models: Bucket, runtime: Runtime, clock: Callable[[], datetime], pinger: Callable[[str, str], None], mode: str = "build", build: Callable[..., dict[str, int]] = model.build.build, extensions: Callable[[], list[str]] = installed_extensions) -> dict`, in this order:
    1. `pinger(<url>/start, "")` (an empty URL when there is none);
    2. in `"drill"` mode, `DrillError("alert drill: nothing was read or written")`;
    3. `cfg.work_dir` removed if present and made again, empty;
    4. `extensions()` not empty: `ExtensionError` naming them, "before the build";
    5. `started = clock()`, which must be timezone-aware UTC; `build_id(started, runtime.request_id)`;
    6. `previous = read_pointer(models)`, then `list_archive(archive)`, then `check_not_shrunk` on the pointer's manifest or `None` (timed together as `list`);
    7. `copy` of the receipts, then of the boards, into `<work>/archive` (`copy`);
    8. inside `Sampler(lambda: shutil.disk_usage(cfg.work_dir).used)` and `phase_timers`: `build(raw_dir=<work>/archive/raw, out_dir=<work>/out, receipts_dir=<work>/archive/receipts, stage_dir=<work>/stage, temp_dir=<work>/temp, memory_limit=MEMORY_LIMIT, threads=THREADS)` (`build`);
    9. `extensions()` not empty: `ExtensionError`, "after the build";
    10. `table_entries`, `finished = clock()`, `manifest(...)` with `measured` (the seconds so far, `memory_mb`, `tmp_mb`);
    11. `upload_build` (`upload`), `move_pointer(models, manifest, receipts.newest_key or "")` (`pointer`), `clean_up(models, started, keep=<the pointer's build id>)` (`clean_up`);
    12. the summary logged as one JSON line, sent with `pinger(<url>, json.dumps(summary))`, the work folder removed (errors ignored), the summary returned.

    Any `Exception` after step 1 is logged (`"nightly build failed: %s: %s"`), sent with `pinger(<url>/fail, f"{type(err).__name__}: {err}")` and raised. The summary is exactly:

    ```python
    {"action": "built", "build_id": str, "pointer": "moved" | "kept", "pointer_build_id": str,
     "seconds": {"list", "copy", "build", "staging", "statements", "writing", "upload", "pointer", "clean_up", "total"},
     "seconds_left": float,
     "copied": {"receipts": {"objects": int, "bytes": int}, "raw": {"objects": int, "bytes": int}},
     "memory_mb": {"peak": float, "size": runtime.memory_mb},
     "tmp_mb": {"peak": float, "size": float},  # shutil.disk_usage(work_dir): used at its peak, and total
     "rows": <build()'s counts>, "table_bytes": {table: int for TABLES}, "deleted": [build ids],
     "model_fingerprint": str, "code_sha256": CODE_SHA256, "duckdb": duckdb.__version__}
    ```

    Seconds are rounded to 0.1 and megabytes to 0.1;
  - `handler(event, context)` (`# pragma: no cover`, thin AWS wiring, as the collector's): `Config.from_env(dict(os.environ))`; one `boto3.client("s3", config=botocore.config.Config(max_pool_connections=DOWNLOAD_WORKERS))`; an `S3Bucket` for each bucket; `Runtime(context.aws_request_id, int(context.memory_limit_in_mb), lambda: context.get_remaining_time_in_millis() / 1000)`; `run(..., clock=lambda: datetime.now(timezone.utc), pinger=ping, mode=parse_event(event))`. Logging set up as in `src/collector/handler.py:20-21`.
- Produces, in `tests/nightly_helpers.py`:
  - `archive_bucket(raw: Path, receipts: Path) -> MemoryBucket`: every file under each folder, keyed `raw/<relative path>` and `receipts/<relative path>`;
  - `small_archive(root: Path) -> tuple[Path, Path]`: with `model_helpers`, boards on 30 and 31 October 2026 (after receipts began), each with its stored receipt, and one unchanged receipt;
  - `fake_build(calls: list) -> Callable`: records its keyword arguments, writes five small files `<out_dir>/<table>.parquet`, returns four counts;
  - `NOW = datetime(2026, 11, 20, 1, 40, 3, tzinfo=timezone.utc)`, `RUNTIME = Runtime("1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809", 3008, lambda: 600.0)`.

Every run test passes `extensions=lambda: []` unless it tests the check, so that an extension installed on a developer's machine cannot fail it.

- [ ] **Step 1: Write the failing tests** (`tests/test_nightly_handler.py`; `work_dir` under `tmp_path`; pings collected into a list):
  - `test_config_refuses_a_missing_or_shared_bucket` (Review Focus 5): a blank `MODEL_BUCKET`, a missing `ARCHIVE_BUCKET`, and one name for both raise `ValueError`; `HEALTHCHECK_URL` loses a trailing `/`.
  - `test_parse_event`, parametrized as the collector's: `{"drill": True}` gives `"drill"`; `{"drill": "true"}`, `{}`, `None` and a scheduler event give `"build"`.
  - `test_a_night_builds_uploads_and_moves_the_pointer` (the design's "whole path"): `small_archive` in the archive bucket, the real `model.build.build`. Then:
    - the five tables named by `latest.json`, read back from the model bucket, against `model.build.build` of the same folders: `compare_tables(..., names=("lambda", "direct")) == []` and `compare_load(...) == []`;
    - `latest.json` holds the same bytes as `models/<id>/manifest.json`;
    - each table's SHA-256 in the manifest is the stored object's;
    - the manifest's listings equal those of the bucket;
    - the summary's `seconds` has the ten names, `staging`, `statements` and `writing` each above 0.
  - `test_the_build_gets_the_copys_folders_and_the_limits`: `fake_build`'s call has exactly `raw_dir`, `out_dir`, `receipts_dir`, `stage_dir`, `temp_dir` as in `run`'s step 8, `memory_limit == "1GB"`, `threads == 2`, and no `restage`.
  - `test_the_work_folder_is_emptied_first`: a file and an `out.building` folder left in `work_dir` are gone when the build is called, and its stage folder does not exist yet.
  - `test_the_work_folder_is_emptied_after_a_success`.
  - `test_tables_then_manifest_then_pointer`: the model bucket's `ops`, from the first `put_new`: five tables, the manifest, then the pointer; every key under `models/` is written with `put_new`.
  - `test_a_failed_build_leaves_the_pointer_as_it_was`: a pointer from an earlier build; `build` raises `ValueError("stop")`; `run` raises it, the pointer's bytes are unchanged, nothing new is under `models/`, and the last ping is `("https://hc-ping.com/abc/fail", "ValueError: stop")`.
  - `test_a_failed_upload_leaves_the_pointer_as_it_was`: `fail` on the third table's `put_new`; the pointer unchanged, no manifest written.
  - `test_a_second_run_with_the_same_build_id_changes_nothing`: two runs with one clock and request id; the second raises `ConditionFailed`, and the first run's tables and pointer are as it left them.
  - `test_a_failed_night_deletes_nothing`: a build from 40 days back and a pointer on it; the build raises; every key of the old build is still there.
  - `test_a_shrunk_archive_fails_the_night`: a pointer whose manifest names one receipt more than the bucket holds; `ArchiveShrunk`, no `download` in the archive's `ops`, no build call.
  - `test_an_unreadable_pointer_fails_the_night` (Review Focus 3): `latest.json` is `b"not json"`; the night fails, and `latest.json` is unchanged.
  - `test_an_installed_extension_fails_the_night`, parametrized over before and after: `extensions` gives `["httpfs"]` on its first call, or on its second. Before: no `list` in the archive's `ops` and no build call. After: nothing written to the model bucket. Both: `ExtensionError` naming `httpfs`, and a `/fail` ping.
  - `test_installed_extensions_lists_only_what_is_not_built_in`: on a new connection, `[]`; on a connection with `extension_directory` set to a folder holding an empty `v<duckdb version>/<PRAGMA platform>/httpfs.duckdb_extension`, `["httpfs"]` (measured on DuckDB 1.5.6: such a file is listed as installed, `install_mode` `UNKNOWN`).
  - `test_pings_start_then_success_with_the_summary`: pings are `[("https://hc-ping.com/abc/start", ""), ("https://hc-ping.com/abc", json.dumps(summary))]`, and the log holds the same line.
  - `test_each_failure_pings_fail_with_its_reason`, parametrized over a failed build, a short download, an installed extension and three refused pointer writes: the last ping goes to `/fail` and starts with the error's class name.
  - `test_the_drill_fails_before_reading_anything`: `DrillError`; both buckets' `ops` empty; pings `/start` then `/fail` with "drill".
  - `test_no_healthcheck_url_means_empty_ping_urls`.
  - `test_ping_posts_the_message`, with `urllib.request.urlopen` monkeypatched: URL, body and the 10 s timeout. `test_a_ping_that_fails_is_logged_not_raised`: `ping("http://127.0.0.1:9/", "x")` logs "healthcheck ping failed".
  - `test_objects_written_during_the_copy_are_left_out` (Review Focus 1): a hook on the first `download` puts a new receipt and a new board in the archive bucket; neither is downloaded, and the manifest's counts are the listing's.
  - `test_an_empty_archive_fails_the_night` (Review Focus 5): an empty archive bucket and no pointer; the real build's `ValueError` ("no snapshot files"), nothing under `models/`.
  - `test_a_naive_clock_is_refused`: `ValueError`, nothing written.
  - `test_the_summary_has_every_figure`: the keys exactly as in the Interfaces; `copied` equals the listings' counts and bytes; `memory_mb.size == 3008`; `seconds_left == 600.0`.
  - `test_nightly_imports_no_collector_module`: no module in `src/nightly/` imports `collector`, absolutely or relatively (an `ast` walk, as `tests/test_frozen.py` walks).
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement** `src/nightly/handler.py` and `tests/nightly_helpers.py`.
- [ ] **Step 4: Run; pass.** Then the full suite. Time `tests/test_nightly_handler.py` alone and note it in the commit message.
- [ ] **Step 5: Mutation entries** (`NIGHTLY_HANDLER`):
  - "nightly: work folder not emptied first" → `test_the_work_folder_is_emptied_first`;
  - "nightly: tables uploaded from the wrong folder" (`<work>/stage` for `<work>/out`) → `test_a_night_builds_uploads_and_moves_the_pointer`;
  - "nightly: memory limit not passed" and "nightly: temp folder not passed" → `test_the_build_gets_the_copys_folders_and_the_limits`;
  - "nightly: pointer moved before the tables" → `test_tables_then_manifest_then_pointer`;
  - "nightly: a failed upload ignored" (the upload wrapped in `try`/`except Exception: pass`) → `test_a_failed_upload_leaves_the_pointer_as_it_was`;
  - "nightly: clean-up before the build" → `test_a_failed_night_deletes_nothing`;
  - "nightly: shrink check skipped" → `test_a_shrunk_archive_fails_the_night`;
  - "nightly: extensions not checked before" and "nightly: extensions not checked after" → `test_an_installed_extension_fails_the_night`;
  - "nightly: no start ping", "nightly: no reason in the fail ping" and "nightly: summary not sent" → `test_pings_start_then_success_with_the_summary` and `test_each_failure_pings_fail_with_its_reason`;
  - "nightly: drill after the listing" → `test_the_drill_fails_before_reading_anything`;
  - "nightly: ping error raised" (`except Exception` narrowed to `ValueError`) → `test_a_ping_that_fails_is_logged_not_raised`;
  - "nightly: imports collector" (`import collector.core` added after `from __future__ import annotations`) → `test_nightly_imports_no_collector_module`.

  Run the entries of `src/nightly/handler.py`.
- [ ] **Step 6: Commit** (`q2: the nightly run: copy, build, upload, pointer, clean-up, one summary line, and healthchecks.io pings`).
- [ ] **Step 7: Review (Opus).** The reviewer walks the design's ten steps against `run()` line by line.

### Task 6: The model stack: template, `samconfig.toml`, layer; lint in CI

Implementer: integration (Opus). Design: sections 3 (the table), 4 (the bucket, retention), 5 (stack and permissions), 7 (packaging), 8 (schedule). Takes the main session's account check (above) as its input.

**Files:**
- Create: `model-stack/template.yaml`, `model-stack/samconfig.toml`, `model-stack/layer/requirements.txt` (the one line `duckdb==1.5.6`), `tests/test_model_stack.py`
- Modify: `.github/workflows/ci.yml` (the cfn-lint line gains `model-stack/template.yaml`), `scripts/mutation_check.py` (`MODEL_STACK = ("model-stack/template.yaml", ["tests/test_model_stack.py"])`, `MODEL_LAYER = ("model-stack/layer/requirements.txt", ["tests/test_model_stack.py"])`, `MODEL_SAMCONFIG = ("model-stack/samconfig.toml", ["tests/test_model_stack.py"])`, the entries)

**Interfaces:**
- Consumes: Task 5's `nightly.handler.handler` and its three environment variables.
- Produces:
  - `model-stack/template.yaml` (`Transform: AWS::Serverless-2016-10-31`; a description naming `docs/nightly-model.md` and why the stack is separate):
    - Parameters: `ArchiveBucketName` (String); `HealthcheckUrl` (String, `NoEcho: true`, `MinLength: 20`); `ScheduleState` (`DISABLED` by default, `[ENABLED, DISABLED]`).
    - `ModelBucket` (`AWS::S3::Bucket`): the four public-access blocks true; `BucketOwnerEnforced`; `AES256`; no versioning and no Object Lock; one lifecycle rule, `Id: end-unfinished-uploads`, `Status: Enabled`, `AbortIncompleteMultipartUpload: {DaysAfterInitiation: 1}`, over the whole bucket.
    - `DuckDBLayer` (`AWS::Serverless::LayerVersion`): `ContentUri: layer/`, `CompatibleRuntimes: [python3.13]`, `CompatibleArchitectures: [arm64]`, `Metadata: {BuildMethod: python3.13, BuildArchitecture: arm64}`.
    - `ModelFunction` (`AWS::Serverless::Function`):
      - `CodeUri: ../src/`, `Handler: nightly.handler.handler`, `Runtime: python3.13`, `Architectures: [arm64]`;
      - `MemorySize: 3008`, `EphemeralStorage: {Size: 10240}`, `Timeout: 900`;
      - `Layers: [!Ref DuckDBLayer]`;
      - `RuntimeManagementConfig: {UpdateRuntimeOn: FunctionUpdate}`;
      - `EventInvokeConfig: {MaximumRetryAttempts: 0, MaximumEventAgeInSeconds: 60}`;
      - `LoggingConfig: {LogGroup: !Ref ModelLogs}`;
      - `Environment`: `ARCHIVE_BUCKET: !Ref ArchiveBucketName`, `MODEL_BUCKET: !Ref ModelBucket`, `HEALTHCHECK_URL: !Ref HealthcheckUrl`;
      - `Events: {Nightly: {Type: ScheduleV2, Properties: {ScheduleExpression: "cron(40 1 * * ? *)", State: !Ref ScheduleState, RetryPolicy: {MaximumRetryAttempts: 0}}}}`;
      - `ReservedConcurrentExecutions: 1` only if the account check allows it;
      - `Policies`, one statement each, by `Sid`:

        | Sid | Action | Resource | Condition |
        |---|---|---|---|
        | `ReadTheArchive` | `s3:GetObject` | `!Sub "arn:aws:s3:::${ArchiveBucketName}/raw/*"`, `…/receipts/*` | |
        | `ListTheArchiveUnderRawAndReceipts` | `s3:ListBucket` | `!Sub "arn:aws:s3:::${ArchiveBucketName}"` | `StringLike: {"s3:prefix": ["raw/*", "receipts/*"]}` |
        | `WriteBuildsAndThePointer` | `s3:PutObject` | `!Sub "${ModelBucket.Arn}/models/*"`, `!Sub "${ModelBucket.Arn}/latest.json"` | |
        | `DeleteOldBuilds` | `s3:DeleteObject` | `!Sub "${ModelBucket.Arn}/models/*"` | |
        | `ReadThePointer` | `s3:GetObject` | `!Sub "${ModelBucket.Arn}/latest.json"` | |
        | `ListTheModelBucket` | `s3:ListBucket` | `!GetAtt ModelBucket.Arn` | |

        A comment on the last one: without it a missing `latest.json` answers 403, not 404, as the collector's template explains.
    - `ModelLogs` (`AWS::Logs::LogGroup`): `LogGroupName: !Sub "/${AWS::StackName}/nightly"`, `RetentionInDays: 30`.
    - Outputs: `ModelBucketName`, `ModelFunctionName`.
  - `model-stack/samconfig.toml`: the root file's shape. `[default.global.parameters]` with `stack_name = "flights-archive-model"`, `region = "il-central-1"` and `profile = "flights-sam"`; `[default.build.parameters]` with `use_container = false`; `[default.deploy.parameters]` with `capabilities = "CAPABILITY_IAM"`, `confirm_changeset = true` and `resolve_s3 = true`.

- [ ] **Step 1: Write the failing tests** (`tests/test_model_stack.py`, decoding with `cfnlint.decode.decode` and asserting no matches, as `tests/test_template.py` does):
  - `test_only_the_four_expected_resources`: `{"ModelBucket": "AWS::S3::Bucket", "DuckDBLayer": "AWS::Serverless::LayerVersion", "ModelFunction": "AWS::Serverless::Function", "ModelLogs": "AWS::Logs::LogGroup"}`.
  - `test_no_retries_and_a_short_event_age`: `EventInvokeConfig == {"MaximumRetryAttempts": 0, "MaximumEventAgeInSeconds": 60}`; the schedule's `RetryPolicy == {"MaximumRetryAttempts": 0}`.
  - `test_runs_daily_at_01_40_utc`: `Type == "ScheduleV2"`, `ScheduleExpression == "cron(40 1 * * ? *)"`, no `ScheduleExpressionTimezone`.
  - `test_the_schedule_starts_switched_off`: as `tests/test_template.py`'s.
  - `test_the_sizes`: 3008, `{"Size": 10240}`, 900, `["arm64"]`, `python3.13`, `nightly.handler.handler`, `../src/`.
  - `test_the_runtime_changes_only_on_a_deploy`: `{"UpdateRuntimeOn": "FunctionUpdate"}`.
  - `test_logs_go_to_a_group_created_first`: the `Ref`, 30 days, the group's name, and `LogFormat` absent or `Text`.
  - `test_the_ping_address_is_a_secret`: `NoEcho` true, `MinLength` 20, `HEALTHCHECK_URL == {"Ref": "HealthcheckUrl"}`.
  - `test_the_environment_names_both_buckets`.
  - `test_the_bucket_is_private_encrypted_and_unversioned`: and `LifecycleConfiguration == {"Rules": [<the one rule>]}`, with no `VersioningConfiguration` and no `ObjectLockEnabled`.
  - `test_the_layer_is_duckdb_for_python_3_13_on_arm64`: `ContentUri`, `Metadata`, both compatibility lists, and the function's `Layers`.
  - `test_the_permissions_are_the_designs`: the six statements by `Sid`, each `Action`, `Resource` and `Condition` exactly as in the table, and no seventh.
  - `test_archive_statements_only_read`: every statement whose resources name `${ArchiveBucketName}` holds only `s3:GetObject` or `s3:ListBucket`.
  - `test_listing_the_archive_is_held_to_raw_and_receipts`: the `Condition`, exactly.
  - `test_nothing_may_delete_the_pointer`: no statement with `s3:DeleteObject` names `latest.json`, the bucket's root or `*`.
  - `test_the_layer_pins_the_duckdb_that_ci_installs`: the `duckdb==` line of `model-stack/layer/requirements.txt` equals that of `requirements-dev.txt`.
  - `test_the_collectors_requirements_hold_no_duckdb`: no line of `src/requirements.txt` names `duckdb`.
  - `test_the_folders_samconfig_names_the_model_stack`: read with `tomllib`: `stack_name == "flights-archive-model"`, `region == "il-central-1"`, `profile == "flights-sam"`; the root `samconfig.toml` still names `flights-archive`.
  - `test_one_build_at_a_time` only if the account allows it: `ReservedConcurrentExecutions == 1`.
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Write** the three files and the CI line.
- [ ] **Step 4: Run; pass.** Then the full suite, and `.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml model-stack/template.yaml`: no output. If cfn-lint refuses the lifecycle rule without a filter, give it `Prefix: ""` and note it in "Deviations".
- [ ] **Step 5: The local build.** Requires `python3.13` on the `PATH`, as `docs/operations.md`'s deploy says; no Docker. Run `cd model-stack && sam build --template-file template.yaml --build-dir .aws-sam/build`. Expected:
  - "Build Succeeded";
  - `.aws-sam/build/ModelFunction/nightly/handler.py` exists;
  - `.aws-sam/build/DuckDBLayer/python/_duckdb.cpython-313-aarch64-linux-gnu.so` exists (the Linux library, as the design measured);
  - `du -sh` of both folders together is far below Lambda's 250 MB for a function and its layers (the design expects about 55 MB and 28 MB).

  Record the two sizes in "Deviations", then `rm -rf model-stack/.aws-sam`. Nothing is deployed. If SAM does not build `CodeUri: ../src/`, stop and report: the template's place would change, and that is a call for the main session.
- [ ] **Step 6: Mutation entries** (`MODEL_STACK`, unless named):
  - "model stack: function retries" (`MaximumRetryAttempts: 2` on the function) and "model stack: schedule retries" → `test_no_retries_and_a_short_event_age`;
  - "model stack: late events kept 6 hours" (`MaximumEventAgeInSeconds: 21600`) → the same test;
  - "model stack: runs at 01:30" → `test_runs_daily_at_01_40_utc`;
  - "model stack: schedule on by default" → `test_the_schedule_starts_switched_off`;
  - "model stack: memory 2048", "model stack: disk 512", "model stack: timeout 600" and "model stack: x86_64" → `test_the_sizes`;
  - "model stack: runtime updated automatically" (`Auto`) → `test_the_runtime_changes_only_on_a_deploy`;
  - "model stack: ping address shown" (`NoEcho: true` removed) → `test_the_ping_address_is_a_secret`;
  - "model stack: bucket versioned" and "model stack: lifecycle rule removed" → `test_the_bucket_is_private_encrypted_and_unversioned`;
  - "model stack: a write on the archive" (`s3:PutObject` added to `ReadTheArchive`) → `test_archive_statements_only_read`;
  - "model stack: archive listing not held to its prefixes" (the `Condition` removed) → `test_listing_the_archive_is_held_to_raw_and_receipts`;
  - "model stack: delete on the pointer" (`latest.json` added to `DeleteOldBuilds`) → `test_nothing_may_delete_the_pointer`;
  - "model stack: logs outside their group" → `test_logs_go_to_a_group_created_first`;
  - "model stack: layer on another DuckDB" (`MODEL_LAYER`: `duckdb==1.5.5`) → `test_the_layer_pins_the_duckdb_that_ci_installs`;
  - "model stack: samconfig aimed at the collector" (`MODEL_SAMCONFIG`: the collector's stack name) → `test_the_folders_samconfig_names_the_model_stack`.

  Run the entries of `model-stack/template.yaml`, `model-stack/layer/requirements.txt` and `model-stack/samconfig.toml`.
- [ ] **Step 7: Commit** (`q2: the model stack: a private bucket, the function sized as designed, its read-only hold on the archive, DuckDB as a layer`).
- [ ] **Step 8: Review (Opus).** The reviewer reads `git diff main -- template.yaml samconfig.toml src/requirements.txt` (empty) and the permissions table against the design's section 5.

### Task 7: The deploy script

Implementer: integration (Opus). Design: section 5 ("Two ways a deploy could reach the collector, both closed by the deploy script"); "Design and code", 1, 5, 6 and 8.

**Files:**
- Create: `scripts/deploy_nightly.sh`, `tests/test_deploy_nightly.py`
- Modify: `scripts/mutation_check.py` (`DEPLOY_NIGHTLY = ("scripts/deploy_nightly.sh", ["tests/test_deploy_nightly.py"])`, the entries; Task 6's `MODEL_SAMCONFIG` gains `tests/test_deploy_nightly.py`, whose runs in the checkout then refuse the changed file too)

**Interfaces:**
- Consumes: Task 6's `model-stack/` folder.
- Produces: `sh scripts/deploy_nightly.sh [DISABLED|ENABLED]`. Its header comment says that it writes to AWS, runs only on the owner's go and in a terminal window, and that the address is asked for. Constants: `PROFILE=flights-sam`, `REGION=il-central-1`, `EXPECTED=arn:aws:iam::137953273942:user/doron-admin`, `STACK=flights-archive-model`, `ARCHIVE_BUCKET=flights-archive-archivebucket-onpwo5ns74tw`, `FOLDER=$ROOT/model-stack` (`ROOT` from the script's own place, as `scripts/publish.sh` finds it). In order, each refusal printing a reason that ends "nothing deployed" and exiting 1:
  1. more than one argument, or one other than `DISABLED` or `ENABLED`: refused (no argument means `DISABLED`);
  2. `$FOLDER/samconfig.toml` without the line `stack_name = "flights-archive-model"`: refused;
  3. `aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text` not `$EXPECTED`: refused;
  4. "healthchecks.io ping address for the model check:" on standard error; one line read from standard input, with `stty -echo` only when it is a terminal (`[ -t 0 ]`), echo restored on exit; an address not starting `https://hc-ping.com/` (an empty one included): refused;
  5. `cd "$FOLDER"`;
  6. `sam build --template-file template.yaml --build-dir .aws-sam/build`;
  7. `sam deploy --template-file .aws-sam/build/template.yaml --stack-name "$STACK" --profile "$PROFILE" --region "$REGION" --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset --parameter-overrides "ArchiveBucketName=$ARCHIVE_BUCKET" "HealthcheckUrl=$url" "ScheduleState=$state"`.

  The address is never printed.

- [ ] **Step 1: Write the failing tests** (a fake `aws` and a fake `sam` first on the `PATH`, each appending its working folder and arguments, tab-separated, to a log, as `tests/test_publish.py` fakes `aws`; the address given on standard input):
  - `test_checks_then_builds_then_deploys`: exit 0; calls exactly `aws sts get-caller-identity …`, then `sam build` with the arguments of step 6, then `sam deploy` with those of step 7, `ScheduleState=DISABLED`; both `sam` calls run in `<repo>/model-stack`.
  - `test_enabled_reaches_the_schedule_state`.
  - `test_another_account_deploys_nothing`: one call, `sts`.
  - `test_an_unknown_argument_deploys_nothing`, parametrized over `enabled`, `--stack-name flights-archive`, and `ENABLED extra`: exit 1, no call at all.
  - `test_a_samconfig_naming_another_stack_deploys_nothing`: the script copied into `tmp_path/repo/scripts/`, beside a `model-stack/samconfig.toml` naming `flights-archive`: exit 1, no call.
  - `test_a_wrong_address_deploys_nothing`, parametrized over an empty line and `https://healthchecks.io/projects/x`: no `sam` call.
  - `test_the_address_is_never_printed`: the address is in neither standard output nor standard error.
  - `test_it_runs_from_anywhere`: started from another folder, both `sam` calls still run in `model-stack`.
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`DEPLOY_NIGHTLY`):
  - "deploy: identity not checked" → `test_another_account_deploys_nothing`;
  - "deploy: stack not named" (`--stack-name "$STACK"` removed) and "deploy: build folder not named" (`--build-dir .aws-sam/build` removed) → `test_checks_then_builds_then_deploys`;
  - "deploy: run where it was started" (`cd "$FOLDER"` removed) → `test_it_runs_from_anywhere`;
  - "deploy: any argument accepted" → `test_an_unknown_argument_deploys_nothing`;
  - "deploy: the stack name check removed" (the `samconfig.toml` check) → `test_a_samconfig_naming_another_stack_deploys_nothing`;
  - "deploy: any address accepted" → `test_a_wrong_address_deploys_nothing`;
  - "deploy: the address printed" (an `echo` of it) → `test_the_address_is_never_printed`.

  Run the entries of `scripts/deploy_nightly.sh` and `model-stack/samconfig.toml`.
- [ ] **Step 6: Commit** (`q2: the deploy script: identity first, the model stack named on every deploy, its own build folder, the address read and never shown`).
- [ ] **Step 7: Review (Opus).**

### Task 8: The comparison script

Implementer: integration (Opus). Design: "The frozen record" (the local script's five steps); Review Focus 4.

**Files:**
- Create: `scripts/nightly_check.py`, `tests/test_nightly_check.py`
- Modify: `scripts/mutation_check.py` (`NIGHTLY_CHECK = ("scripts/nightly_check.py", ["tests/test_nightly_check.py"])`, the entries)

**Interfaces:**
- Consumes: `nightly.bucket.S3Bucket`, `Bucket` and `Item`; `nightly.archive.listing_sha256`; `nightly.output.POINTER`; `model.build.build`, `TABLES`; `model.stage.fingerprint`; from `scripts/tagged_check.py`, `compare_tables`, `compare_load`, `compare_progress` and `IDENTICAL`, imported with the script's own folder put on `sys.path` and a comment saying why (one set of checks for both comparisons). Tests: Task 5's `run`, `MemoryBucket` and `tests/nightly_helpers.py`.
- Produces, in `scripts/nightly_check.py` (docstring: what it compares, the command, the exit codes):
  - the command: `PYTHONPATH=src .venv/bin/python scripts/nightly_check.py --bucket <ModelBucketName> --work DIR [--raw data/raw] [--receipts data/receipts]`;
  - `class Refused(Exception)`: anything that stops the comparison before a result;
  - `open_bucket(name: str, session=None) -> S3Bucket`: with no `session`, `boto3.Session(profile_name="flights-sam", region_name="il-central-1")`; `Refused` unless `session.client("sts").get_caller_identity()["Arn"]` is `arn:aws:iam::137953273942:user/doron-admin`, before any S3 client is made;
  - `fetch_model(models: Bucket, dest: Path) -> dict`: reads `latest.json` (`Refused` when missing), downloads the five tables it names into `dest`, and refuses any whose bytes or SHA-256 differ from the manifest's; returns the manifest;
  - `select(folder: Path, prefix: str, newest: str | None) -> list[tuple[Item, Path]]`: every file under `folder` whose key (`prefix` + its relative POSIX path) is at or before `newest`, no part of its path starting with `.`, in key order;
  - `lay_out(raw: Path, receipts: Path, manifest: dict, dest: Path) -> None`: for receipts and boards, `Refused("inputs differ: …")` naming both sides' objects and digests unless `listing_sha256` of the selection equals the manifest's; then copies the selection into `dest/receipts` and `dest/raw`;
  - `compare(models: Bucket, raw: Path, receipts: Path, work: Path) -> int`, in order:
    1. `work` new or empty;
    2. `fetch_model` into `work/lambda`;
    3. `model.stage.fingerprint()` equal to the manifest's `code.model_fingerprint`;
    4. `lay_out` into `work/archive`;
    5. `model.build.build` into `work/mac`, staged in `work/stage`, spilling into `work/tmp`;
    6. `compare_tables(work/lambda, work/mac, names=("lambda", "mac"))`, `compare_load(work/lambda, work/mac)` and `compare_progress(work/lambda, work/mac, work/record, names=("lambda", "mac"))`, with `timeline.record`'s own output in `work/record.log`;
    7. printed: the build id, the newest keys, the inputs' counts and "digests equal", the fingerprint, each table's rows on both sides, then `IDENTICAL` or each difference line.

    It returns 0 when identical and 1 on any difference; `main` turns `Refused` into its message on standard error and exit 2;
  - `main(argv: list[str], opener: Callable[[str], Bucket] = open_bucket) -> int`.

- [ ] **Step 1: Write the failing tests** (the "Lambda" side is made by Task 5's `run` with the real build, on `small_archive`, into a `MemoryBucket`, so the script reads what the function writes):
  - `test_the_same_boards_compare_identical`: `main([...], opener=lambda name: models)` exits 0 and prints `IDENTICAL`.
  - `test_one_changed_value_is_a_difference`: `flights.parquet` in the bucket rewritten with one `final_status` changed, and its manifest entry re-hashed to match; exit 1, and the line `flights: 1 row only in lambda` is printed.
  - `test_inputs_whose_digest_differs_are_refused`: one local receipt at or before the newest key grows by a byte; exit 2, "inputs differ", and no `work/mac`.
  - `test_boards_after_the_newest_keys_are_left_out` (Review Focus 4): a board and a receipt added locally after the Lambda's run; exit 0.
  - `test_dot_files_are_not_counted` (Review Focus 4): `.DS_Store` in `raw/` and in a date folder; exit 0.
  - `test_a_table_whose_hash_differs_is_refused`: one table's object changed, the manifest not; exit 2.
  - `test_another_model_fingerprint_is_refused`: the manifest's `model_fingerprint` changed; exit 2, no build.
  - `test_another_aws_identity_reads_nothing`: `open_bucket` with a fake session whose STS answers another ARN: `Refused`, and no `s3` client was asked for.
  - `test_a_work_folder_in_use_is_refused`: exit 2, nothing added to it.
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`NIGHTLY_CHECK`):
  - "nightly check: input digest not compared" → `test_inputs_whose_digest_differs_are_refused`;
  - "nightly check: boards after the newest key kept" → `test_boards_after_the_newest_keys_are_left_out`;
  - "nightly check: dot-files counted" → `test_dot_files_are_not_counted`;
  - "nightly check: table hash not checked" → `test_a_table_whose_hash_differs_is_refused`;
  - "nightly check: fingerprint not compared" → `test_another_model_fingerprint_is_refused`;
  - "nightly check: rows not compared" (`compare_tables` left out) → `test_one_changed_value_is_a_difference`;
  - "nightly check: exit 0 on a difference" → the same test;
  - "nightly check: identity not checked" → `test_another_aws_identity_reads_nothing`.

  Run the entries of `scripts/nightly_check.py`.
- [ ] **Step 6: Commit** (`q2: scripts/nightly_check.py: the Lambda's model against a Mac build of the same boards, by the four checks`).
- [ ] **Step 7: Review (Opus).**

### Task 9: Whole-branch review (Fable, main session)

- [ ] **Step 1:** A fresh Fable reviewer reads `git diff main...HEAD` against `docs/nightly-model.md` and this plan: the code, the template, the scripts, the tests, the mutation entries and "Deviations". It also confirms that `git diff main -- src/model src/timeline/load.py src/timeline/counting.py src/timeline/rates.py src/timeline/record.py template.yaml samconfig.toml src/requirements.txt src/collector` is empty.
- [ ] **Step 2:** Each finding is checked against its source. Fixes go to an Opus implementer, with a scoped Opus re-review. Then the full suite and the touched files' mutation entries.

### Task 10: Documents

Implementer: transcription (Sonnet). Every claim is checked against the code as built, the template and this plan's "Deviations".

**Files:**
- Modify:
  - `docs/operations.md`:
    - a section "## Nightly model build" after "## Model":
      - what a night does, in five lines, pointing at `nightly-model.md`;
      - deploying with `sh scripts/deploy_nightly.sh` in a terminal window, from a clean committed tree, the address pasted at its prompt, the change set reviewed;
      - a run by hand (`--invocation-type Event`), and the drill;
      - the comparison script;
      - the summary line's figures and the design's two rules: a night past 300 s with staging (`seconds.staging`) its largest step calls for the kept stage; one past 300 s with the copy largest, or with the stage kept past 450 s, temp files past 5 GB or memory past 2,400 MB, calls for the step after;
      - the healthchecks.io check (period 1 day, grace 1 hour);
      - the cost, pointing at `nightly-model.md`, "Cost";
    - "Model", its last sentence: it runs locally, and nightly in AWS once deployed (the new section);
    - "Develop": `pytest --cov=collector --cov=model --cov=nightly --cov=timeline`, and cfn-lint on the three templates.
  - `docs/data-model.md`, "Nightly run":
    - the heading becomes "Nightly run (built, not yet deployed)";
    - the paragraph before the steps and step 2 point at `nightly-model.md` (the design) and `nightly-model-plan.md` (the build), in place of the earlier sketch;
    - the cost paragraph points at `nightly-model.md`, "Cost", and keeps its last sentence on the GitHub Actions alternative.
  - `docs/README.md`: after the `lighter-build-plan.md` line, one line for `nightly-model.md` and one for this plan.
  - `docs/nightly-model.md`: only its status line, which becomes "built to [nightly-model-plan.md](nightly-model-plan.md); not deployed".
- The counts in `README.md:27`, `README.md:56` and `docs/operations.md:97` come from Task 11. `README.md`'s "What it does today" changes only once the function is live (the owner's step 6).
- [ ] **Step 1: Update the documents.**
- [ ] **Step 2: Commit** (`q2: documents follow the nightly build`).
- [ ] **Step 3: Review (Opus).**

### Task 11: Final verification (main session)

- [ ] **Step 1:** `PYTHONPATH=src .venv/bin/pytest --cov=collector --cov=model --cov=nightly --cov=timeline --cov-fail-under=95`. Expected: every test passes, coverage 95% or more; record the count.
- [ ] **Step 2:** `.venv/bin/python scripts/mutation_check.py`, alone. Expected: "Every mutation was caught."; record the count and the time.
- [ ] **Step 3:** `.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml model-stack/template.yaml`. Expected: no output.
- [ ] **Step 4:** `git diff main -- src/model src/timeline/load.py src/timeline/counting.py src/timeline/rates.py src/timeline/record.py template.yaml samconfig.toml src/requirements.txt src/collector`. Expected: no output.
- [ ] **Step 5:** Write Steps 1 and 2's counts into `README.md:27`, `README.md:56` and `docs/operations.md:97`, and Step 2's time into `docs/operations.md:97`. Commit (`q2: test and mutation counts`).
- [ ] **Step 6:** The push and the merge, each by the main session on the owner's go, after `gh auth status` shows the project's own GitHub account.

## Deploy and prove: the owner's checklist

Not agent tasks. Each step on the owner's go, at the terminal, from the merged and pushed `main`. Every AWS command uses `--profile flights-sam --region il-central-1`, after `aws sts get-caller-identity --profile flights-sam` shows account 137953273942 and user doron-admin. From the design's "Deploy and prove".

1. **The check.** Create a healthchecks.io check for the model: period 1 day, grace 1 hour. Keep its address out of the repository.
2. **The first deploy.**
   - `git status --porcelain` prints nothing.
   - In a terminal window (not the coding agent's `!` prefix): `sh scripts/deploy_nightly.sh`, which deploys with the schedule `DISABLED`. Paste the address at the prompt.
   - The change set must hold only new resources in the new stack `flights-archive-model`. Confirm.
   - If AWS refuses 3,008 MB, stop. The design's fallback, 2,048 MB and 1 thread, is a change to the template, the function's `THREADS` and their tests, made and reviewed on the owner's go before deploying again.
   - Afterwards the collector's stack shows no change (`aws cloudformation describe-stacks --stack-name flights-archive --query 'Stacks[0].LastUpdatedTime'` as before), and its next receipt arrives on time.
3. **One run by hand**, the first measurement in a Lambda:
   - `aws lambda invoke --function-name <ModelFunctionName> --invocation-type Event --payload '{}' --cli-binary-format raw-in-base64-out out.json`;
   - read the summary: the success ping's body in healthchecks.io, or the log group `/flights-archive-model/nightly`. Seconds for each step, peak memory, peak disk;
   - if the build (`staging + statements + writing`) took more than 144 s, try x86-64 once: the function's `Architectures` and the layer's `BuildArchitecture` and `CompatibleArchitectures`, with their test pins, deployed, run once, the faster kept. Both figures go in `nightly-model.md`.
4. **The comparison.** `sh scripts/sync.sh`, then `PYTHONPATH=src .venv/bin/python scripts/nightly_check.py --bucket <ModelBucketName> --work <a new folder>`. Expected: exit 0 and `identical: columns, rows, load(), progress.json`. Its output, date and command go into `docs/nightly-model.md`, under "The frozen record", before the schedule is switched on.
5. **The drill.** The same invoke with `--payload '{"drill": true}'`. healthchecks.io shows a failure and the email arrives. A run by hand (step 3's command) clears it.
6. **Live.** `sh scripts/deploy_nightly.sh ENABLED`. The next morning: a start and a success in healthchecks.io, and a new `latest.json` (`aws s3 cp s3://<ModelBucketName>/latest.json -`). Then a documents commit: the deploy date in `docs/operations.md`, `docs/data-model.md` ("Nightly run") and `docs/nightly-model.md`'s status line, and the function in `README.md`'s "What it does today".
7. **After a week.** The seven summaries beside the table under "Sizing", and the call on the stage by the 300 s rule.

## Deviations
