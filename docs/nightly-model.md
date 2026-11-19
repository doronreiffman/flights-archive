# The nightly model build (q2)

Grade: production-lean, the data model's own grade ([data-model.md](data-model.md)): tested code, a mutation check (the code is broken on purpose and a test must fail), a fresh review before anything ships. Cheap, boring infrastructure: one function, one bucket, one schedule.

Status: an approved design. Nothing is built and nothing is deployed. Written 2026-11-19. The design and its measurements are an agent's (Fable 5.2); I settled the six calls under "For the owner" on 2026-11-19, all as recommended. Its figures and quotes were checked against their sources, and the Linux-against-Mac comparison was rerun, by the main session; a fresh reviewer (Opus 5.5) read it the same day, and its twelve findings are folded in (three important: two overlapping runs sharing a kept stage, the trigger for keeping the stage, and the pointer's build expiring during a long stop). It replaces step 2 of "Nightly run" in [data-model.md](data-model.md), the earlier sketch of this function. Every figure marked "this Mac" was measured on the 8 GB development Mac. Nothing was run in AWS.

Data: Israel Airports Authority, published on data.gov.il (dataset `flydata`). The counts here are of archived boards, not official figures.

Today the model is built by hand. `sh scripts/sync.sh` copies the archive to the Mac, and `python -m model.build` builds five Parquet tables there. The public site is built from those tables and uploaded by hand, so it goes stale between uploads. This design moves the build into AWS, once a night. The next piece of work (q23) rebuilds and publishes the site from its output.

## The short answer

- **One function, once a night.** A Lambda function (code that AWS runs on request and bills by the second) copies the archive to its own temporary disk, runs the same `model.build.build()` the Mac runs, and uploads the five tables to a bucket of its own.
- **Copy the archive, do not read it in place.** The build lists folders on a local disk, so with a local copy it runs unchanged. Reading S3 directly would mean editing `src/model/`, which is frozen under `record-v1`, and adding a DuckDB extension that is not in the package. With a copy, no frozen file changes.
- **Start from an empty disk every night, for now.** Nothing is kept between nights, so nothing can drift. Today that build takes 48 s on this Mac, and 65 to 133 s in a small Linux container on it. Staging alone grows by about 2 s for every day of history; the whole from-scratch build grew about 4 s a day on this Mac's figures (48 s now, about 261 s at the gate). The copy from S3 comes on top and was not measured. When a night passes 300 s and staging is its largest step, the staged work moves to S3 (designed below).
- **Size.** 3,008 MB of memory, a 10,240 MB temporary disk, the 900 s maximum timeout, arm64 processors. The build runs as on the Mac: DuckDB held to 1 GB, 2 threads.
- **It will outgrow Lambda, and the log will say when.** On this Mac's figures the 15-minute limit arrives between the record's gate (mid-January 2027) and the middle of 2027, depending on how fast a Lambda really is and how long the copy takes (not measured). The 10 GB disk fills at about eleven times today's archive, late May 2027. Each night logs its seconds, its peak memory and its peak disk use beside those limits.
- **A reader never sees half a model.** Each night's tables go under a folder of their own. One small pointer file, written last, names the newest complete night. S3 replaces a single object in one step, so a reader gets the old night or the new one.
- **A stack of its own**, `flights-archive-model`. It can read `raw/` and `receipts/` in the archive bucket and do nothing else there. Deploying it never puts a change on the collector's stack.
- **Alerts through healthchecks.io.** One check, pinged at the start and at the end of each run. A failed night, a night that was killed and a night that never ran all reach the owner. $0.
- **DuckDB arrives as a layer** (a separate zip of libraries that the function loads), built by SAM for Linux arm64. The collector's requirements and template do not change. The Linux package has every extension the build uses built in: a build with the network cut ran to the end.
- **Proof.** The model from AWS is compared with a Mac build of the same boards by the four checks the lighter build used. A Linux arm64 build in a container on this Mac already passes all four against the Mac's.
- **Cost.** About $0.24 a month today at list price and about $1 at the gate; $0.06 and $0.22 if Lambda's free allowance covers the run time.
- **Not measured: a Lambda.** Its speed decides how long this design lasts. The first step of the deploy is one run by hand, read before anything depends on it.

## What was measured, and how

All on 2026-11-19, on the development Mac (Apple M2, 8 GB, 8 cores, DuckDB 1.5.6, Python 3.13.18), one build at a time, one run each. Other work was running on the Mac (load average about 2.7), so the times are rough. The archive copy is the one synced on 18 November: 1,932 boards and 2,050 receipts, 94.7 MB, the last board from 20:32:45 UTC.

- **The command.** `/usr/bin/time -l env PYTHONPATH=src .venv/bin/python driver.py --raw data/raw --receipts data/receipts --out O --stage S --temp-dir T --threads N --memory-limit 1GB`. The driver is a scratch script outside the repository. It calls `model.build.build()` unchanged, times its three phases (staging, the whole-history statements, writing the tables) and reads the size of the temp folder five times a second. `O`, `S` and `T` were scratch folders; `data/` was only read.
- **A Linux stand-in.** The same driver in a Linux container on the same Mac: Debian 13, arm64, Python 3.13.18, DuckDB 1.5.6 installed from the Linux arm64 package, in a virtual machine with 2 processors, 2 GiB of memory and no swap. The archive was copied onto the container's own disk first. It is not a Lambda: the processors are the Mac's, and a Lambda's disk and memory accounting were not measured.

| where | threads | build | wall | staging | whole-history statements | peak temp files | peak memory |
|---|---|---|---|---|---|---|---|
| this Mac | 2 | from scratch (stages 22 days of boards, 21 of receipts) | 47.9 s | 33.9 s | 13.8 s | 0.53 GB | 1.23 GB |
| this Mac | 2 | again, reusing the stage | 13.2 s | 0.3 s | 12.7 s | 0.57 GB | 1.18 GB |
| this Mac | 1 | from scratch | 67.2 s | 43.3 s | 23.7 s | 0.64 GB | 1.27 GB |
| this Mac | 1 | again, reusing the stage | 21.7 s | 0.4 s | 21.1 s | 0.61 GB | 1.31 GB |
| Linux container | 2 | from scratch | 133.2 s | 44.0 s | 88.5 s | 0.40 GB | 1.21 GB |
| Linux container | 2 | again, reusing the stage | 32.2 s | 0.6 s | 31.3 s | 0.41 GB | 1.12 GB |
| Linux container | 2 | from scratch, a second time | 66.9 s | 43.1 s | 23.5 s | 0.42 GB | 1.18 GB |
| Linux container | 2 | from scratch, network cut | 64.5 s | 43.2 s | 20.9 s | 0.41 GB | 1.14 GB |
| Linux container | 1 | from scratch | 108.9 s | 65.3 s | 43.1 s | 0.42 GB | 1.10 GB |
| Linux container | 1 | again, reusing the stage | 30.9 s | 0.8 s | 29.8 s | 0.39 GB | 1.09 GB |

Peak memory is `/usr/bin/time`'s "peak memory footprint" on the Mac and the process's largest resident size in the container. Every run wrote the same row counts: 1,932 snapshots, 47,121 observations, 13,222 flights, 2,050 receipts.

What the runs say:

- **Staging is most of a from-scratch build today**, 34 of 48 s, and it is steady: 1.5 s per day of boards on the Mac and 2.0 s in the container, at 2 threads, in every run.
- **The whole-history statements were not steady in the container**: 20.9, 23.5, 31.3 and 88.5 s for the same work at 2 threads. The slowest was the first build after the archive was copied in. The cause was not established. The Mac took 12.7 to 13.8 s.
- **Temp files peak at 0.4 to 0.64 GB.** With the archive copy (95 MB) and the stage, that is already more than a Lambda's default 512 MB disk.
- **One thread costs 40% more time** from scratch on the Mac (67 s against 48 s). The stage it writes is smaller, 15.1 MB against 56.6 MB at 2 threads, for the same rows: its size depends on the order the rows are written in.

Other things measured:

- **The Linux package.** `pip download duckdb==1.5.6` for Python 3.13 fetched `duckdb-1.5.6-cp313-cp313-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl` for arm64: 19.5 MB zipped, 55.2 MB unzipped. The x86-64 one is 21.6 MB zipped, 61.0 MB unzipped.
- **Extensions.** In the container `duckdb_extensions()` lists 30 extensions. Four are built in (`STATICALLY_LINKED`): `core_functions`, `icu`, `json`, `parquet`. No other is installed. The Mac shows the same four. `httpfs` (DuckDB's reader for S3 and web addresses) and `aws` are `NOT_INSTALLED` on both. A from-scratch build with the container's network disconnected ran to the end, and no `~/.duckdb` folder, where DuckDB keeps downloaded extensions, existed afterwards.
- **The same tables on Linux.** The container's model against the Mac's, from the same boards: `compare_tables`, `compare_load` and `compare_progress` of `scripts/tagged_check.py` found no difference. The files are not the same bytes (`flights.parquet` is 1,668,455 bytes from Linux and 1,656,659 from the Mac). The checks compare rows, for the reason [lighter-build.md](lighter-build.md) gives: row order inside the files is not stable.
- **The layer builds on this Mac.** `sam build` (SAM CLI 1.170.0, no Docker) on a scratch template holding one layer (`BuildMethod: python3.13`, `BuildArchitecture: arm64`, a requirements file with `duckdb==1.5.6`) produced `python/_duckdb.cpython-313-aarch64-linux-gnu.so`, 54,606,888 bytes: the Linux library. Not deployed.
- **The Lambda's C library.** A `public.ecr.aws/lambda/python:3.12-arm64` image that was already on this Mac reports Amazon Linux 2023 and glibc 2.34. The package asks for 2.26 or newer. AWS's runtime table gives Amazon Linux 2023 for Python 3.13 too; that image was not on the Mac.
- **A sketch of the template, a scratch file outside the repository, passes cfn-lint** 1.58.0 for il-central-1. cfn-lint did not object when the sketch's memory was set to 10,241 MB, its timeout to 901 s or its runtime to `python9.99`. It caught a misspelt property name. So the template tests pin the values, and the first deploy is the real check of them.
- **When boards are stored.** Of the 1,932 boards, 1,896 were stored in the first three minutes after a quarter hour (median 105 s after it). Between 01:00 and 02:00 UTC they were stored at :00 to :02, :16, :30 to :32 and :46 to :48.
- **Growth.** Over the 19 full days from 30 October to 17 November: 94.8 boards (4.59 MB) and 102.1 receipts (76 KB) a day.

Three sizes are used below. "Today" is the copy above: 3,982 objects, 95 MB. "The gate" is mid-January 2027, the earliest day the frozen record's gate can be reached ([flight-lookup.md](flight-lookup.md), "The gate"): about 15,200 objects and 360 MB, four times today's archive. "One year" is the end of October 2027, a year after collection began: about 72,000 objects and 1.7 GB, about eighteen times today's. The last two are today's daily growth carried forward.

## The design

### What one night does

1. Tell healthchecks.io the run has started. Empty the work folder under `/tmp`, the function's only writable disk.
2. Check that DuckDB has nothing installed beyond its built-in extensions.
3. List `receipts/` in the archive bucket, then list `raw/`, one straight after the other. Note the counts, the bytes, the newest key and a digest of each listing. The archive only grows, so if either listing holds fewer objects, or an older newest key, than the manifest `latest.json` names, stop: a wrong bucket or a listing fault, not a smaller archive.
4. Download every listed object to the same relative path under the work folder. Check each file's size against the listing.
5. Call `model.build.build()` on the copy, with a stage folder and a temp folder inside the work folder, a 1 GB memory limit and 2 threads.
6. Check DuckDB's extensions again. Hash the five tables.
7. Upload the five tables under `models/<build id>/`, then a manifest (a small JSON file describing the build) beside them. Every upload there is write-once (`If-None-Match`), so no run can replace another's files.
8. Move the pointer `latest.json` to this build, only forward (below).
9. Delete the builds under `models/` older than 30 days, never the one the pointer names (section 4).
10. Log one summary line, send it to healthchecks.io as the success ping, and empty the work folder.

Anything that goes wrong at any step is logged, sent to healthchecks.io as a failure with its reason, and raised. The pointer does not move. The function never calls data.gov.il: it reads S3 and pings healthchecks.io, nothing else.

A manual event `{"drill": true}` fails on purpose before reading anything, as the collector's drill does, to prove the alert.

### 1. Copy, not read

**Recommended: copy `receipts/` and `raw/` to the function's disk and call `model.build.build()` unchanged.**

Why the build needs a local disk. `src/model/stage.py` finds each day's files with Python's own folder listing (`folder.glob("date=*")`, `rglob`). A staged day's marker holds that listing, each file's relative path and size (`listing`, read with `stat`), and the model's fingerprint. A staged day is reused only when its source folder is on the disk with the same listing, under the same fingerprint. And "a staged day whose source folder is gone is not read": a build given only the recent days would quietly produce a model of only those days.

What reading S3 directly would take. DuckDB can read `s3://` addresses through its `httpfs` extension. That route needs:

- `stage.py` to list S3 where it lists folders, and its markers to take sizes from S3. `stage.py` is a frozen file.
- `httpfs` to be loaded on the connection that `rules.connect()` makes, another frozen file, with AWS credentials given to DuckDB there. `httpfs` is not in the package (above), so it would be downloaded at run time or shipped and loaded by hand.
- A proof against the tagged code on the real archive, and the owner's go, because frozen files changed ([flight-lookup.md](flight-lookup.md), "The record", condition 2).

What the copy means for the frozen record. No file under `src/model/` changes, nor `src/timeline/load.py`, `counting.py`, `rates.py` or `record.py`. The function is new code beside them that imports `model.build`. The tables are uploaded exactly as the build wrote them. Condition 2 has nothing to rule on.

The order of the two listings matters, not the order of the downloads. `scripts/sync.sh` syncs receipts first because the collector writes a receipt after its pages, "so in this order every receipt that arrives finds its pages". The function keeps that order for the listings and takes them back to back. A board stored between the two listings arrives without its receipt, and the model drops it as `pending`, as it does on the Mac. The model stops the build when a pending board is more than 35 minutes newer than the newest receipt ([data-model.md](data-model.md), "Inputs"). Listing both first, seconds apart, keeps the function far from that stop however long the downloads take.

A copy that is not complete must fail, not build. Every page of both listings is read. Every object's size is checked. One failed download fails the night.

| | Copy, then build (recommended) | Read S3 from DuckDB |
|---|---|---|
| `src/model/` | unchanged | `stage.py`, `rules.py` and `build.py` edited |
| The frozen record | nothing to rule on | housekeeping to prove against the tag, on the owner's go |
| DuckDB | the package as it is | `httpfs` added and loaded |
| Disk | the archive copy, 95 MB today and 1.7 GB at one year | no copy |
| Requests a month, today / gate / one year | $0.05 / $0.20 / $0.95 | not measured: fewer objects once a stage is kept, in a request pattern that is DuckDB's own |

What the copy costs. Every night reads every object again: 3,982 today, about 15,200 at the gate, about 72,000 at one year. At $0.0044 per 10,000 GETs that is $0.05, $0.20 and $0.95 a month. Moving the bytes costs nothing: AWS does not charge for data sent from a bucket to an AWS service in the same Region (S3's price page, read today). How long the copy takes in a Lambda was not measured. The downloads run several at a time; how many is the plan's, from a measurement there.

### 2. The stage between nights

The stage is each day's per-board work, kept as Parquet so that the next build skips it ([lighter-build.md](lighter-build.md), "The design", 2). A Lambda's disk does not last from one night to the next, so the stage is either rebuilt or kept somewhere.

**Recommended: rebuild it every night on an emptied disk. Keep it in S3 when a night's run passes 300 s and staging is the largest step.**

| | (a) From scratch each night | (b) Stage kept in S3 | (c) Stage and archive on EFS |
|---|---|---|---|
| What a night does | copies everything, stages every day, runs the whole-history statements | copies everything and the stage, stages the one or two days that changed, runs the whole-history statements | copies only the new objects, stages the changed days, runs the whole-history statements |
| Time today, this Mac | 48 s | 13 s | 13 s |
| Time at the gate, this Mac | about 4.5 minutes (147 s staging and 114 s, the prototype's figures) | about 2 minutes (114 s) | about 2 minutes |
| Time at one year | over the 15-minute limit if growth stays linear | not measured past 8 times (200 s there) | not measured |
| New code | none beyond the function | download the stage first, upload the changed days after | a private network (VPC), a file system, mount settings |
| Kept between nights | nothing | the stage, a cache | the archive copy and the stage |
| Can drift from a full rebuild | no: every night is one | only if a staged day goes stale; the build's own marker check runs every night | the same, and the copy itself can fall out of step with the bucket |
| Monthly cost today / gate / one year, list price | $0.24 / $0.96 / does not fit | $0.20 / $0.80 / $2.54 | not priced |
| The same, if Lambda's free allowance covers the run time | $0.06 / $0.22 / does not fit | $0.08 / $0.30 / $1.43 | not priced |

The times leave out the copy from S3, which was not measured. The costs assume run lengths, because a Lambda's speed is not known: 150 s today and 600 s at the gate for (a); 100 s and 400 s for (b); the full 900 s at one year. The sums are under "Cost".

Why (a) first. It keeps nothing, so there is nothing to go stale and nothing to prove beyond the build itself. It is the least code. On the Mac's figures it has room through the gate.

Why not (a) for long. Staging grows by 1.5 to 2 s a night for every day collected, and it does not get faster with more processors: the prototype staged 78 days in 147 s on 8 threads, the same rate as on 2. If a Lambda runs at half this Mac's speed, a from-scratch night takes about 9 minutes at the gate and passes 15 minutes before the end of March 2027.

When to switch. The trigger is the step (b) removes, not the total. When a night's logged run passes 300 s, a third of the limit, and staging is its largest step, build (b). From there the run has to triple before it reaches the limit. On the prototype's growth that means the archive more than doubling, which is at least a month. If the copy is the largest step instead, (b) does not help, since it still copies the whole archive: that night calls for the step after (under "Sizing"), where the archive copy lasts between runs.

(b), designed now so the switch needs only a plan:

- Each build keeps its own stage, beside its tables: `stages/<build id>/`, holding for each day `rows.parquet`, `counts.parquet` and `marker.json`, and for each day of receipts `receipts.parquet` and `marker.json`. That is 108 objects and 57 MB today, about 2.6 MB more a day. The manifest names it.
- Before the build the function downloads the stage of the build `latest.json` names into its stage folder. The whole archive is still copied, because a staged day is only reused when its source folder is there.
- `build()` decides what to reuse, by its own marker rule. The function decides nothing.
- After the build, the function uploads its whole stage to its own `stages/<build id>/`, before the pointer moves. No stage is ever written by two runs: `build()`'s reuse check (`_current` in `src/model/stage.py`) trusts any marker whose listing matches and whose files are there, so one run's `rows.parquet` beside another run's marker would be reused unseen. A stage shared between runs could get exactly that from two overlapping runs.
- A missing stage is harmless: the build stages every day, as tonight's does. So `stages/` expires after 3 days by a lifecycle rule (S3 deleting objects by age, by itself). A run of failed nights longer than that costs one from-scratch build, nothing else.
- A manual event `{"restage": true}` passes `restage=True`: the from-scratch build.
- Proof: the Mac comparison under "The frozen record" is against a fresh Mac build, so it also checks a model built on a reused stage.

Why not (c), EFS (a network file system a Lambda can mount, which lasts between runs). It is the only option that stops re-reading the whole archive every night. It needs a private network (a VPC) around the function, the first thing in this project with a network to look after. Whether a function inside one can still reach healthchecks.io without a paid gateway was not checked, and EFS's prices were not in today's price files. Not for a job this size.

### 3. Sizing

| Setting | Value | Why |
|---|---|---|
| Memory | 3,008 MB | The build's footprint is 1.2 to 1.3 GB at a 1 GB DuckDB limit. Lambda gives processor time in proportion to memory, "the equivalent of one vCPU" at 1,769 MB, so 3,008 MB is 1.7 processors for 2 threads. The 2 GiB container finished every build, but its whole-history time varied four-fold. |
| Temporary disk (`/tmp`) | 10,240 MB, the maximum | The default 512 MB is already too small. The largest size costs about a cent a month at most, and a full disk fails the night. |
| Timeout | 900 s, the maximum | A lower one would only cap the cost of a hung run, which is under 4 cents at the maximum. |
| Processors | arm64 | 20% cheaper a second than x86-64 ($0.0000140001 against $0.0000175 a GB-second). The build was run and compared on Linux arm64 here. |
| `memory_limit` | `1GB` | The build's default, and the limit every comparison so far ran at. |
| `threads` | `2` | The default. On the Mac, 2 threads were faster than 8 on the 4-times archive ([lighter-build.md](lighter-build.md)). |
| `temp_dir`, `stage_dir`, `out_dir` | folders inside the work folder under `/tmp` | Left out, `build()` makes its temp and stage folders under the system's temp folder. Named, all of the function's disk use sits in one folder that is emptied and measured. |
| Retries | none, on the schedule and on the function | A build that failed will fail again the same way. The next night is the retry. |
| Runtime updates | "Function update" | AWS then moves the function to a newer Python runtime only when the function is deployed ("Update to the most recent and secure runtime version when you update your function", AWS's page on runtime updates). A runtime change then always falls on a deploy, which is followed by the comparison under "The frozen record". |

If AWS refuses 3,008 MB. "New AWS accounts have reduced concurrency and memory quotas" (AWS's Lambda quotas page). This account is from October 2026 and its quota is not known. If the deploy is refused, use 2,048 MB and 1 thread: 1.16 processors' worth, and the container's one-thread build took 109 s.

If arm64 turns out slow. The x86-64 package exists (21.6 MB). Switching is one line in the template and one in the layer. The plan tries it once if the first arm64 run takes more than three times this Mac's 48 s.

How the build grows, on this Mac. The first row is today's run. The next two are the lighter build's prototype on synthetic archives, not the built code; their multiples are of the archive of 17 November (1,837 boards).

| archive | reached about | from scratch | of which staging | reusing the stage | temp files |
|---|---|---|---|---|---|
| today (1,932 boards, 22 days) | now | 48 s | 34 s | 13 s | 0.5 to 0.6 GB |
| 4 times (7,243 boards) | mid-January 2027, the gate | about 4.5 minutes | about 147 s | 114 s | 2.8 GB |
| 8 times (14,451 boards) | end of March 2027 | about 8 minutes | about 270 s | 200 s | 6.0 GB |
| one year (about 34,600 boards) | end of October 2027 | not measured | about 10 minutes if linear | not measured | not measured |

In the Linux container the same from-scratch build took 1.3 to 2.8 times the Mac's time today.

When it outgrows Lambda, roughly:

- **The 15 minutes, from scratch.** At the Mac's own speed, not before the middle of 2027 if growth stays linear (it was not measured past 8 times). At half that speed, before the end of March 2027. Moving the stage to S3 takes staging out of the night and pushes this back by months. The copy from S3 adds to every figure here and was not measured.
- **The 10 GB disk.** Temp files grow by about 0.75 GB for each multiple of today's archive at a 1 GB limit. With the archive copy and the stage beside them the disk is full at about eleven times today's archive, late May 2027, whether or not the stage is kept. A higher DuckDB limit writes less to disk (3.3 GB at a 1 GB limit, 1.8 GB at 3 GB, on the 4-times archive at 8 threads), but needs more function memory than 3,008 MB.
- **The copy.** 72,000 downloads a night at one year. Not measured.

What comes after, in the order to try:

1. More memory for the function and for DuckDB, if the account's quota allows more than 3,008 MB. A settings change.
2. The narrower step [lighter-build.md](lighter-build.md) names: run the two costly statements only for flights with a new row or a changed chain. It edits frozen files, so it is its own design with its own proof.
3. The same code as a scheduled container task in place of a Lambda, for a longer run and a disk that lasts between runs. Its limits and prices were not read here.

Decide on a measurement taken in the Lambda, not on these.

What the function logs each night, in one JSON line, as the collector does:

- seconds for each step (listing, copy, staging and build, upload) and in total, and the seconds left before the timeout;
- objects and bytes copied, for receipts and for boards;
- peak memory of the process, and the function's configured memory;
- peak use of `/tmp`, read once a second while the build runs, and its configured size;
- rows in each table that `build()` reports, and each table's size;
- the build id, the model's fingerprint and the DuckDB version.

Lambda's own `REPORT` line adds the billed duration and "Max Memory Used". The same summary is the body of the success ping, so recent nights can be read in healthchecks.io: about fifty of them, since it keeps 100 log entries and a night sends two. Act when a night passes 300 s with staging its largest step (build (b)). Plan the step after when a night passes 300 s with the copy its largest step, or when, with the stage kept, a night passes 450 s, temp files pass 5 GB, or memory passes 2,400 MB.

### 4. Output and readers

**Recommended: a bucket of its own, in the model's stack.**

```
models/<build id>/snapshots.parquet        the five tables, as build() wrote them
models/<build id>/snapshot_runs.parquet
models/<build id>/observations.parquet
models/<build id>/flights.parquet
models/<build id>/receipts.parquet
models/<build id>/manifest.json            what this build is
latest.json                                the same bytes as the newest build's manifest
```

The build id is the run's start time and a few characters of the run's request id, for example `20261120T014003Z-1a2b3c4d`. Every upload under `models/` carries `If-None-Match` (write only if no object has that key), so even if two runs ever got the same id, neither could replace the other's tables: the second fails.

How a reader stays whole. S3 has no folder rename and cannot change several objects in one step: "There is no way to make atomic updates across keys." It does replace one object in one step: "Updates to a single key are atomic", and a reader gets "either the old data or the new data, but never partial or corrupt data" (S3 User Guide, "Amazon S3 data consistency model"). So:

- the tables are uploaded first, to keys nobody reads yet;
- `latest.json` is written last, in one write;
- a reader reads `latest.json` once, then fetches exactly the keys it names, and checks each size and SHA-256. It never lists the bucket.

A reader that started on last night's pointer still finds last night's files when a new night lands, because old builds stay for 30 days.

The pointer only moves forward. Lambda can deliver one scheduled event twice ("it's possible for it to receive the same event from Lambda multiple times", Lambda's guide on asynchronous invocation), and a run by hand can overlap the nightly one. Two builds cannot hurt each other: each has its own disk and its own folder in the bucket. The pointer is the one thing they share. A build replaces it only when the newest receipt it read is the same as or newer than the one the pointer names, and the write carries S3's `If-Match` condition: replace only if the object is still the one just read. S3 answers 412 Precondition Failed when it is not, and 409 ConditionalRequestConflict when another write raced it, for which S3 says to "fetch the object's ETag and retry the upload" (the `IfMatch` documentation of `PutObject` in botocore's S3 model, pinned in this repository's environment; the 412 also in S3 User Guide, "Conditional writes"). On either answer the function reads the pointer again and decides again, at most three times, then fails the night. The first ever write uses `If-None-Match`, the condition the collector uses.

What the manifest records, so a model in S3 can be traced to its code and its boards:

| Field | What it holds |
|---|---|
| `manifest_version`, `build_id`, `started_at`, `finished_at` | which build, when (UTC) |
| `tables` | for each of the five: its key, bytes, SHA-256, and rows where `build()` reports them (it reports four; not `snapshot_runs`) |
| `archive` | the bucket; for `receipts/` and for `raw/`: objects, bytes, the newest key, and the SHA-256 of the listing (one line per object, key and size, in key order) |
| `code` | the model's fingerprint (`model.stage.fingerprint()`: the model's source files and the DuckDB version), a fingerprint of the function's own source made the way the collector's is, the DuckDB and Python versions, the processor architecture |
| `build` | the memory limit, the threads, whether the stage was reused |
| `measured` | the summary line's seconds and peaks |

The boards are named by their listing's digest and newest key. The bucket is write-once and its keys sort by time, so the boards of any build can be laid out again from a later copy: every key up to the newest one, checked against the digest.

Retention. After the pointer has moved, the function deletes the builds under `models/` that started more than 30 days ago, except the one the pointer names. Deleting only after a success means a run of failed nights deletes nothing, so the build the pointer names is always there. That matters here: some of the model's stops can last weeks. A board with no receipt between receipts stops every build until it is listed in `KNOWN_ORPHANS` in `src/model/rules.py`, a frozen file, which takes a proof against the tag and the owner's go ([flight-lookup.md](flight-lookup.md), "The record", condition 2). A lifecycle rule (S3 deleting objects by age, by itself) was rejected for `models/` for that reason: it would delete the pointer's build after 30 failed nights. The bucket's one lifecycle rule (two once the stage is kept: `stages/` after 3 days, section 2) removes unfinished multipart uploads after 1 day: boto3 uploads a file over 8 MB in parts (`multipart_threshold`, `s3transfer`), the model reaches about 80 MB at one year, and a run killed mid-upload can leave its parts behind. No versioning and no Object Lock: the model can always be rebuilt from the archive, which is the thing that is kept. Thirty nights are 0.14 GB today and about 2.3 GB at one year, 6 cents a month.

Why not a `model/` prefix in the archive bucket. It would give a second function a write permission on the bucket that holds the archive, where today the collector is the only function that writes and a test pins what it may do. The storage costs the same in either bucket. That bucket keeps every version of every object, so each night's leftovers would need a lifecycle rule on it, and a lifecycle rule there is a change to the collector's stack.

### 5. Stack and permissions

**Recommended: a stack of its own, `flights-archive-model`, from a template of its own, as the site has** ([publishing.md](publishing.md), "A stack of its own"). The collector's stack holds the live function and the locked archive; a change to the model must never put a change set on it.

It holds: the model bucket; the function; the DuckDB layer; the schedule; a log group created before the function, kept 30 days, as the collector's is. Parameters: the archive bucket's name (the stack is told it; it does not import it from the collector's stack, which would tie the two together), the healthchecks.io address (`NoEcho`, given on the command line, never in a file), and `ScheduleState`, default `DISABLED`, as the collector has.

Two ways a deploy could reach the collector, both closed by the deploy script:

- `samconfig.toml` names `flights-archive` as the default stack. A bare `sam deploy` of the model's template from the repository root would aim the model's resources at the collector's stack.
- `sam build` writes to `.aws-sam/build` by default, and the collector's documented deploy is a bare `sam build` and `sam deploy` that use that folder. A model built there, followed by a bare `sam deploy`, would send the model's template to the collector's stack.

So the model's template lives in a folder of its own, beside a `samconfig.toml` of its own that names `flights-archive-model`: a `sam` command typed in that folder aims at the model's stack, and its build folder is that folder's own `.aws-sam/`, never the collector's. And the model is built and deployed only by a script, as the site is uploaded only by `scripts/publish.sh`. It checks the AWS identity first, as `scripts/sync.sh` does. It names the template, the build folder and the stack `flights-archive-model` on every `sam` call. It refuses any other stack name. A test with a fake `sam` holds it to that. A `sam build` typed at the repository root with the model's template named is the one path left open: it would still use the root `.aws-sam/`. The deploy steps say to use the script.

Permissions (IAM, the rules for what a function may call). The function's role gets exactly:

| On | Actions | Scope |
|---|---|---|
| the archive bucket | `s3:GetObject` | `raw/*` and `receipts/*` |
| the archive bucket | `s3:ListBucket` | only with a prefix under `raw/` or `receipts/` |
| the model bucket | `s3:PutObject` | `models/*` and `latest.json` |
| the model bucket | `s3:DeleteObject` | `models/*` (the 30-day clean-up) |
| the model bucket | `s3:GetObject` | `latest.json` |
| the model bucket | `s3:ListBucket` | so a missing pointer answers 404, not 403, as the collector's comment explains, and to find old builds |

Nothing lets it write, delete, change retention or read `state/` in the archive bucket. A template test asserts that every statement naming the archive bucket holds only those two read actions, and that no statement lets it delete `latest.json`. The archive's objects are encrypted with S3's own keys (`AES256` in `template.yaml`), so no key permission is needed. The S3-kept stage, when it comes, adds `GetObject` and `PutObject` on `stages/*` in the model bucket.

One build at a time. The design does not depend on it: two builds at once are harmless (section 4). Reserved concurrency (a cap on how many copies of a function run at once, free) set to 1 would also stop the second one. AWS allows it only when 100 units stay unreserved in the account: "You can reserve up to the Unreserved account concurrency value minus 100." A new account's quota may be too small for that. The plan checks with the read-only `aws lambda get-account-settings` and adds the cap if the account allows it. Rejected: a lock file in S3. It needs a rule for a lock left by a killed run, which is more code and more tests than the harm it prevents.

### 6. Alerts

**Recommended: one healthchecks.io check, as the collector has.** Period 1 day, grace 1 hour, set on healthchecks.io's side. Its address is a secret parameter, as the collector's is.

- The function pings `/start` when it begins, the plain address with its summary when it ends, and `/fail` with the reason when anything raises.
- **A failed night**: the `/fail` ping. An email at once.
- **A night that was killed** (the timeout, or out of memory): no code runs to say so. A job that sends a start and then no success within its grace time is marked down, and the alerts go out (healthchecks.io's documentation, "Measuring script run time", read today). An email within the hour.
- **A night that never ran** (schedule off, function broken, account trouble): no ping for a day and an hour. An email.
- A ping that cannot be sent is logged and never fails the build, as in the collector.

| | healthchecks.io check | CloudWatch alarms emailing through SNS (the collector's pattern) |
|---|---|---|
| Failed night | `/fail`, at once, with the reason in the email | an alarm on Lambda's own `Errors` metric, which counts timeouts too |
| Never ran | no ping in a day plus the grace | a second alarm on "no successful run", from Lambda's `Invocations` metric or a metric made from the summary line |
| New things to build | one more ping call in the function | two alarms, perhaps a metric filter, a topic and its email subscription |
| Known trouble | sits outside AWS; if healthchecks.io is down, no alert | with one data point a day, almost every period is empty; [alarms.md](alarms.md) records that CloudWatch then looks further back by an undocumented amount, so "a day without a success" cannot be timed exactly |
| Monthly price | $0: the Hobbyist plan costs nothing for 20 jobs, with 100 log entries kept for each (healthchecks.io's pricing page, read today); the collector uses one | $0.20 for two alarms, $0.50 with a metric made from a log line, at list price; the first 10 alarms and 10 such metrics a month are free (AWS's price list of 7 October, as [alarms.md](alarms.md), "Cost", records; today's file lists the free allowance without its size), and the collector's stack uses 2 and 2. The price of the emails was not read. |

Why one path is enough here. A missed night loses nothing: the archive is untouched, and the next night builds everything again. The collector has two paths because a missed download is gone for good.

### 7. Packaging

**Recommended: DuckDB as a layer in the model's stack; the function's code is `src/`.**

- The layer is one folder with one requirements file, `duckdb==1.5.6`, built by SAM for `python3.13` and `arm64` (measured above: it builds on this Mac without Docker). The folder sits outside `src/`, beside the model's template: anything inside `src/` also lands in the collector's package (its `CodeUri` is `src/`). A test holds its version equal to the one in `requirements-dev.txt`, which is what the Mac and CI install.
- The function's `CodeUri` is `src/`, as the collector's is, so it imports `model` exactly as the Mac does. Its own code is a new package beside `model/`. It gets the pinned `boto3` from `src/requirements.txt`, as the collector does.
- Size: the layer is 55 MB unzipped and `src/` with `boto3` 28 MB (the collector's last local build), against a limit of 250 MB for a function with its layers.
- The same layer serves q23, whose site build reads the tables with DuckDB. The site's code also converts times with Python's `zoneinfo` (`ZoneInfo("Asia/Jerusalem")`, `src/timeline/words.py`), which needs time-zone data that the model's build does not (DuckDB's connection converts with its own built-in `icu`). Whether the Python 3.13 Lambda image carries that data is not known; q23 may need the `tzdata` package in its layer.

What the collector deploys. `src/requirements.txt` holds only `boto3` (DuckDB is in `requirements-dev.txt`), and that does not change: a test asserts it. The collector's template does not change. One side effect: the collector's `CodeUri` is also `src/`, so its package gains the new package's few files at its next deploy, unused, as it already carries `model/` and `timeline/` (its last local build, 2 November). The collector's code fingerprint covers `src/collector/` only and does not move. The function must not import from `collector/`, so that a need of the model's never becomes an edit to the collector.

No download at run time. Three things hold it:

- the four extensions the Linux package has built in are all the build used: it ran with the network cut;
- the function checks, before and after the build, that DuckDB reports no installed extension that is not built in, and fails the night otherwise;
- a later DuckDB could move an extension out of the package: DuckDB's documentation says the built-in set differs a little from one distribution to another. The check above would catch that on the first night, and the Mac comparison is repeated after any change of DuckDB version.

Rejected: adding `duckdb` to `src/requirements.txt` (it would enter the collector's package: 55 MB in a function with 256 MB of memory that never uses it). A container image (needs Docker and an image registry; a zip is enough). A build script of the project's own that assembles the package (SAM already does it).

### 8. Schedule

**Recommended: every day at 01:40 UTC**, `cron(40 1 * * ? *)`. That is 03:40 in Israel in winter and 04:40 in summer.

The earlier sketch said 01:30. A board is stored at 01:30 to 01:32 (measured above), so a run at 01:30 lists the bucket while the collector is writing. Nothing breaks, because the model drops a board with no receipt yet. But ten minutes later the 01:30 board is in with its receipt, and the next refresh is five minutes away.

Each extra run a day costs what one run costs: $0.008 today, $0.032 at the gate, $0.07 at one year, at list price and the run lengths assumed under "Cost"; $0.002, $0.007 and $0.03 if the free allowance covers the run time. Today's price files show no free allowance for the requests. A run every hour would cost about $6 a month today and about $23 at the gate at list price. A build that copies the whole archive is the wrong shape for that: frequent runs want a copy that lasts between them. That is q23's to weigh when it picks a frequency.

## The frozen record

No frozen file changes ("1. Copy, not read"). What could still differ is the machine: the same code and the same boards, on Linux in AWS and not on the Mac. That is checked, not assumed.

"Identical" is the four checks of [lighter-build.md](lighter-build.md), "The frozen record", as `scripts/tagged_check.py` holds them:

1. each of the five tables has the same column names, types and order (`compare_tables`);
2. each holds the same rows, repeats counted, checked both ways (`compare_tables`);
3. `timeline.load.load()` returns equal lists from both (`compare_load`);
4. `timeline.record` writes the same `progress.json`, byte for byte, with the same exit code (`compare_progress`).

Already done: the Linux arm64 container's model against the Mac's, on the boards of 18 November. No difference on any of the four. The record's `progress.json` is still a weak check, as lighter-build says: 0 cancelled, gate not reached, on both sides.

After the first run in AWS, a local script (it cannot run in CI: the archive is not in the repository):

1. reads `latest.json` and downloads the five tables it names (read-only), checking each SHA-256;
2. after `sh scripts/sync.sh`, lays out the same boards from `data/`: every receipt and board up to the manifest's newest keys. It computes the two listing digests. If they are not the manifest's, it stops: the inputs differ;
3. checks that this checkout's `model.stage.fingerprint()` is the manifest's;
4. builds that copy with `model.build` into a scratch folder, on a new stage;
5. runs the four checks, the Mac's model against the Lambda's, and prints them as `tagged_check.py` does. Exit 0 only when identical.

Its output is recorded in this document with its date and command before the schedule is switched on. It is run again after any change of DuckDB version, Python version or processor architecture, and once more after the stage moves to S3.

## Tests and mutation checks

The function is written as the collector is: a plain `run()` that takes its S3 client, clock, ping function and build function as arguments, and a thin `handler()` that wires the real ones. The tests give it an in-memory S3, as `MemoryStore` stands in for the collector's. Every entry below goes into `scripts/mutation_check.py` with the test that must fail.

| Part | Test | Breaks that must be caught |
|---|---|---|
| Listing | both prefixes, every page, receipts before boards | boards listed first; stop after the first page |
| Copy | every listed key lands at its relative path with its size | a size not checked; a failed download ignored |
| Work folder | a folder left by an earlier run is emptied first | the folder not emptied |
| Build call | `build()` gets the copy's folders, the stage and temp folders, `1GB` and `2` | a limit or a folder not passed |
| The whole path | a synthetic archive in the in-memory S3; the uploaded tables equal a direct `model.build.build()` of the same archive (`compare_tables`, `compare_load`) | a table not uploaded; tables from the wrong folder |
| Upload order | tables, then manifest, then pointer; every `models/` upload write-once | pointer first; `If-None-Match` dropped |
| Failure | a build that raises, a failed upload: the pointer is as it was | pointer written anyway |
| Pointer | moves forward, stays put when an older build tries, reads again on a 412 or a 409 at most three times, first write | the comparison turned round; the condition dropped; a 409 not retried; no cap |
| Clean-up | after a success, builds started over 30 days ago are deleted and the pointer's build stays even when older; after a failure nothing is deleted | the pointer's build deleted; clean-up run after a failure |
| A shrinking archive | a listing with fewer objects, or an older newest key, than the pointer's manifest fails the night | the check skipped |
| Manifest | bytes, hashes and listing digests equal what was copied and uploaded | a hash of the wrong file; a digest that ignores sizes |
| Extensions | an installed extension that is not built in fails the night, before and after | either check skipped |
| Pings | start, success with the summary, `/fail` with the reason for each kind of failure, the drill; a ping that fails never fails the run | a ping missing; a ping error raised |
| Template | no retries on the schedule or the function; the cron expression; `ScheduleState` default off; 3,008 MB, 10,240 MB, 900 s, arm64; the log group first; the secret parameter `NoEcho`; runtime updates on "Function update"; the bucket private, encrypted, its one lifecycle rule ending unfinished uploads after 1 day | each value changed |
| Permissions | the table in section 5, exactly; archive statements read-only | a write action on the archive; a wider prefix |
| Packaging | the layer's DuckDB version equals `requirements-dev.txt`'s; `src/requirements.txt` has no `duckdb` | either pin changed |
| Deploy script | identity first; the stack, template and build folder named on every `sam` call; any other stack refused | the stack name check removed |
| The comparison script | two folders that differ in one value; inputs whose digest differs | a check skipped; the digest not compared |

CI lints the new template with the other two. That checks its shape, not its sizes (measured above).

## Deploy and prove (each step on the owner's go)

The owner runs the deploy script at the terminal, as with `scripts/publish.sh`: the coding agent's tooling refuses to run a production deploy even after the owner's go.

1. The owner creates the healthchecks.io check (period 1 day, grace 1 hour) and keeps its address out of the repository.
2. The deploy script, from a clean committed tree, with `ScheduleState` left `DISABLED`. The change set must show only new resources in a new stack. A refusal of 3,008 MB shows here. Afterwards the collector's stack shows no change, and its next receipt arrives on time.
3. One run by hand. Read the summary: seconds for each step, peak memory, peak disk. This is the first measurement in a Lambda and it settles the open figures.
4. The comparison script. Its result goes into this document.
5. The drill event: healthchecks.io shows a failure and the email arrives.
6. Deploy again with `ScheduleState=ENABLED`. The next morning: a start and a success in healthchecks.io, and a new `latest.json`.
7. After a week: the seven summaries beside the table under "Sizing", and the call on the stage.

## Cost

Prices are AWS's public price list for il-central-1, files of 18 and 19 November 2026.

- Lambda on arm64: $0.0000140001 a GB-second (a GB of memory held for one second). At 3,008 MB that is $0.0000411 a second, $0.037 for a full 15 minutes.
- The temporary disk: $0.0000000408 a GB-second, so $0.0000004 a second for 10 GB.
- S3: $0.0044 per 10,000 GETs, $0.0055 per 1,000 PUT or LIST requests, $0.025 a GB-month.
- The schedule: free (the first 14 million scheduled invocations). Logs: a few KB a night at $0.50 a GB.
- healthchecks.io: $0.

Run lengths are assumed, because a Lambda was not measured: 150 s today and 600 s at the gate from scratch, 900 s at one year.

| | today | the gate | one year |
|---|---|---|---|
| Objects copied a night | 3,982 | about 15,200 | about 72,000 |
| Run length assumed | 150 s | 600 s | 900 s, the limit |
| Lambda, one run | $0.0062 | $0.0249 | $0.0374 |
| Requests, one run | $0.0018 | $0.0068 | $0.0321 |
| One run | $0.008 | $0.032 | $0.069 |
| A month of nightly runs | $0.24 | $0.95 | $2.08 |
| 30 nights of tables stored | under $0.01 (0.14 GB) | $0.01 (0.5 GB) | $0.06 (2.3 GB) |
| **A month, list price** | **$0.24** | **$0.96** | **$2.14** |
| **A month, if the free allowance covers Lambda's memory time** | **$0.06** | **$0.22** | **$1.03** |

The one-year column is a ceiling for a run that uses the whole limit; from scratch it is not expected to fit by then. The temporary disk is charged in full in every sum, inside the free allowance or not.

With the stage kept in S3, option (b), on the same prices and assumed run lengths of 100 s, 400 s and 900 s: a run costs $0.0065, $0.026 and $0.080. The stage adds 108, about 395 and about 1,825 downloads a night and as many uploads (each build writes its whole stage to its own folder), and three days of stages in storage: 0.17, 0.6 and 2.9 GB. A month comes to $0.20, $0.80 and $2.54 at list price, and $0.08, $0.30 and $1.43 if the free allowance covers Lambda's memory time.

Lambda's free allowance is 400,000 GB-seconds a month across the account. The nightly run would use about 13,000 of them a month today and 53,000 at the gate. The collector draws on the same allowance, and its use was not measured.

## What q23 needs, and what is left to it

What q2 gives q23:

- **A model to read.** `latest.json` in the model bucket, and the reading rule in section 4. q23 needs `s3:GetObject` on that bucket and nothing in the archive bucket.
- **A moment to start.** `latest.json` is written once, last, on success only. An S3 event on that one key, or a second schedule, can start the site build. Which is q23's.
- **How fresh it is.** The manifest's newest receipt key and finish time.
- **DuckDB in AWS.** The layer.
- **What a bad night looks like.** The pointer stays on the last good build. The site would be a day older, not wrong.

Open, and not q2's to decide:

- **The record.** `timeline.record` writes `progress.json` on every run and `result.json` once, to a local folder, and "The first stored result stands and is the one published" ([flight-lookup.md](flight-lookup.md), "The record"). A Lambda has no folder that lasts. Whether a nightly job runs the record at all, where "written once" would live (S3 can refuse a second write to a key, as the collector's writes do), and whether the Mac or AWS writes the first result, are calls for q23 and the owner. q2 does not run the record.
- **The site build and upload in AWS**, its own checks, and the upload script's place in it.
- **How often.** Section 8 gives the cost of each run.
- **Whether the Mac keeps building.** Until q23, the site is still built from the Mac's model. q2 changes nothing on the Mac.

## What you might not think to ask

- **A disk that is not empty.** A Lambda can reuse its environment, and "the Lambda reset does not clear the `/tmp` directory content" even after a failure (Lambda's guide). A leftover copy would be read as tonight's. So the function empties its work folder first, every time.
- **The same run twice.** Lambda may deliver one event twice. Each run writes to its own folder and the pointer only moves forward, so a second run costs what one run costs and changes nothing.
- **A run that cannot say it failed.** A timeout or an out-of-memory kill stops the code mid-line. Only something outside the function can notice. That is why the check gets a start ping and a grace time.
- **A success that is wrong.** A build of half a copy would look fine and be missing days. So an incomplete copy fails the night, and the manifest records what was copied.
- **The build stopping on purpose.** The model stops on a board with no receipt between receipts, a misplaced receipt and the like ([data-model.md](data-model.md), "Inputs"). That is the model working. It needs a person, and until then every night fails and the pointer stays where it was. It can last weeks: clearing a board with no receipt means editing `KNOWN_ORPHANS` in a frozen file, with a proof against the tag and the owner's go. So nothing deletes the build the pointer names.
- **Half a result.** S3 cannot swap a folder. A reader follows one pointer; nothing is ever updated in place.
- **Same code, another machine.** CI runs on Linux with small made-up boards. The real archive had only ever been built on the Mac. It has now been built once on Linux, here, and compared.
- **Two copies of one dependency.** DuckDB is pinned in the layer and in `requirements-dev.txt`. A test keeps them equal, and the manifest names the version that built each model.
- **Quotas on a new account.** Memory and concurrency are both reduced for new accounts, by amounts AWS's page does not give. The first deploy finds the memory quota.
- **A linter that passes is not a deploy that works.** cfn-lint accepted a 10,241 MB function.
- **The deploy's default target.** SAM's saved settings point at the collector's stack. The model has a script so that nobody types the command that would follow them.
- **Cost that grows with history.** Every night reads the whole archive again. The requests are 5 cents a month now and 95 cents at one year, and today's price files show no free allowance for them.
- **Sized for months, not years.** The whole-history statements grow with the archive, and no setting here stops that. The nightly log is how the limit is seen coming.
- **A secret in a setting.** `NoEcho` hides the ping address in the deploy's output. The function's settings still hold it in plain text, readable with the command [operations.md](operations.md) uses to check the collector's User-Agent.
- **UTC and Israel time.** The schedule is in UTC, so the run moves by an hour on the Israeli clock when the clocks change.

## For the owner

My calls, 2026-11-19: all six as recommended. The questions as they were put:

1. **Rebuild the stage every night, or keep it in S3 from the first day?** Recommended: rebuild every night, and add the S3-kept stage when a night passes 300 s. Under that answer: the least code now, and every night is a from-scratch build; expect to plan the second step around the turn of the year if a Lambda runs at half this Mac's speed. If kept from day one: one plan, not two; more code and tests now; a cache to reason about before any measurement says it is needed.
2. **healthchecks.io alone, or a CloudWatch alarm as well?** Recommended: healthchecks.io alone, with a new check that the owner creates. Under that answer: $0, one more ping call, and no alert if healthchecks.io itself is down. If an alarm is added: an alarm on the function's `Errors` emailing a new SNS topic, $0.10 a month at list price and likely free, one more address to confirm, and a second path that catches a timeout at once.
3. **A bucket and a stack of its own?** Recommended: yes. Under that answer: one new bucket and one new stack in the account, and the collector's stack is never touched. The other answer, a `model/` prefix in the archive bucket: no new bucket, but a second writer on the archive bucket and a lifecycle change on the collector's stack.
4. **How long are nightly models kept?** Recommended: 30 days, deleted by the function after each successful night, never the build the pointer names. That is 6 cents a month at one year. Seven days would be 1 cent. Keeping all of them would pass 13 GB in the first year and keep growing. Whatever the number, a run of failed nights deletes nothing (section 4, "Retention").
5. **When does it run?** Recommended: daily at 01:40 UTC, moved from the sketch's 01:30 because a board is stored then. Any other hour costs the same. More than once a day is q23's question, at the prices in section 8.
6. **May the collector's package gain the new package's files at its next deploy?** Recommended: yes. They are unused there, as `model/` and `timeline/` already are, and the collector's code fingerprint does not move. If no: the function's code lives outside `src/` and its package is assembled by a build step of the project's own, which is more to build and test.

## Left to the plan

- Names: the package, the template file, the deploy script, the comparison script, the work folder, the environment variables.
- How the function is split into modules, and how the in-memory S3 for the tests is written.
- How many downloads run at once, from a measurement in the Lambda, and whether S3's stored checksums are checked on download.
- How the deploy script takes the secret address, and how it keeps clear of `samconfig.toml`.
- The read-only `aws lambda get-account-settings` check, and the reserved-concurrency line if the account allows it.
- How long a throttled or late event may wait before Lambda drops it (`MaximumEventAgeInSeconds`), set short so that a late copy of a night's event does not start a second build.
- One x86-64 run, if the first arm64 run is slower than three times this Mac's.
- What the new tests add to the mutation check's run time, and `--cov` for the new package in CI.
- The S3-kept stage as a later task, built only when the 300 s rule says so.
- Document updates: [data-model.md](data-model.md), "Nightly run" (step 2 points here); [operations.md](operations.md), a section for the nightly function and its deploy; the line for this note in `docs/README.md`.

## Unverified

- Everything about a real Lambda: its speed against this Mac, how it counts memory, how fast it copies from S3, how fast its disk is. The container on this Mac is a stand-in for Linux, not for Lambda.
- This account's memory quota and its concurrency quota.
- Whether the account is inside any free allowance, and how much of Lambda's the collector uses.
- Whether DuckDB runs in a Lambda with no home folder to write to. The build used only built-in extensions here, which should not need one.
- The Python 3.13 Lambda image itself: its C library was read from the Python 3.12 image and AWS's runtime table.
- Growth past 8 times today's archive, and the built code at 4 and 8 times: those rows are the prototype's, on synthetic archives.
- Why the container's whole-history time varied from 20.9 to 88.5 s.
- Each figure here is one run, on a Mac that was doing other work.
- The model's size at the gate and at one year: today's 4.5 MB carried forward by the day.
- The deployed archive bucket's lock settings, and what the deployed collector's package holds. Both are read here from `template.yaml`, `src/requirements.txt` and the last local build.
- Prices not in today's files: EFS, a container task, a network gateway, SNS emails. Whether the first 512 MB of the temporary disk are free: all of it is charged here.
- Whether a function inside a private network can reach healthchecks.io, and what a container task's limits are.
- That `aws lambda get-account-settings` is the command that shows the account's concurrency quota: named from memory.
- Whether the owner's healthchecks.io account is on the Hobbyist plan with a free slot.
- The allowed range of `MaximumEventAgeInSeconds`.
- Whether the Python 3.13 Lambda image carries time-zone data for `zoneinfo` (q23's concern, not the model's).
- How often S3 answers `If-Match` with 409 rather than 412; the retry handles both.
- That SAM uploads and attaches the layer as built. The build was run here; the deploy was not.
- Lambda's `Errors` metric counting an out-of-memory kill. AWS's page names timeouts; it lists memory exhaustion among invoke failures elsewhere.
- The exact words of healthchecks.io's and DuckDB's documentation: they are given here in paraphrase, from pages read today. The DuckDB page read was the current one, for version 2.0, not 1.5.6.
