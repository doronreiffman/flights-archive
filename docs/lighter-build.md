# A lighter model build (q5)

Grade: production-lean, the data model's own grade ([data-model.md](data-model.md)): tested rules, a mutation check, a fresh review before anything ships, code only, no new infrastructure.

Status: a design, nothing built. Written 2026-11-18. The measurements and the prototype are an agent's (Fable 5.2); I settled the four calls under "For the owner" on 2026-11-18, all as recommended. It tests step 1 of "Nightly run" in [data-model.md](data-model.md) rather than assuming it, and would replace that step.

Data: Israel Airports Authority, published on data.gov.il (dataset `flydata`). The counts here are of archived boards, not official figures.

Two purposes: (a) the frozen record ([flight-lookup.md](flight-lookup.md), "The record") stays buildable on the 8 GB development Mac until its gate, 60 days after counting began on 16 November 2026, and well past it; (b) a later nightly build can run in a small Lambda (q2, not this work).

## The short answer

- **The build is at the Mac's limit today.** On 1,837 snapshots it took 450 s with a peak memory footprint of 8.33 GB on an 8 GB machine. On one and a half times that (a synthetic archive) it still finished, in 903 s with 8.69 GB.
- **Reading the raw files is not the cost**: 20 s of the 450. One statement is. The codeshare step (R5) lists the members of every group on every board, 2,393,345 lists today, and reads at most 13,021 of them, one per flight. It took 663 of the 903 s above.
- **A memory limit alone does not work.** With a limit the build stops instead of slowing down: out of memory at a 2 GB limit on the whole archive and on half of it.
- **Three changes together do**: (1) list only the codeshare groups that are read; (2) do each day's per-board work once and keep the result as Parquet; (3) set an explicit memory limit, thread count and temp directory. A prototype of the three built the whole archive in 16 s within 1.21 GB and gave the same rows in all five tables as today's build. On four times the archive, about the size expected at the gate, it took 114 s within 1.30 GB.
- **No trailing-window rebuild is proposed.** Every rule that looks from one board to another still runs over the whole history on every build. The only thing kept between builds is each day's per-board work, which depends on that day's files and nothing else, so there is no kept state that can drift from a full rebuild.
- **The nightly function (b)** could run the same build inside 2 GB at the sizes measured: 1.30 GB at four times today's archive and 1.32 GB at eight times, in 114 s and 200 s. It would need more temp disk than the earlier sketch gives it. That is measured on this Mac, not in a Lambda.
- **Cost: $0 a month.** Code and local disk only.

## What was measured, and how

All on 2026-11-18, on the development Mac (8 GB, 8 cores, DuckDB 1.5.6, Python 3.13), one build at a time, one run each except where two are listed (the whole archive's later staged build at 1 GB and 2 threads ran twice: 16 s and 18 s). The archive copy held 1,837 snapshots (boards to 2026-11-17 20:32:45Z, 3,768,512 board rows) and 1,954 receipts.

- **The command.** `/usr/bin/time -l .venv/bin/python driver.py --raw R --receipts X --out O [--memory-limit 2GB] [--threads N] --temp T`. The driver is a scratch script outside the repository. It calls `rules.connect()`, sets `memory_limit`, `threads` and `temp_directory`, then runs `rules.build_all` and the five `COPY` statements of `model.build`. It times each statement and reads the process's memory footprint and DuckDB's own account (`duckdb_memory()`) five times a second. "Footprint" and "resident" below are `/usr/bin/time`'s "peak memory footprint" and "maximum resident set size", in GB of 10^9 bytes.
- **No limit is set today.** `rules.connect()` sets the time zone and the R1 macros and nothing else, so DuckDB takes its default, 6.3 GiB on this Mac (`current_setting('memory_limit')`), and writes its temp files to `.tmp/` under the working directory.
- **Cuts** are the archive as it stood at a moment, copied by the rule of `cut_archive` in `tests/model_helpers.py`: a quarter (459 snapshots, to 2026-11-03 07:47Z) and a half (918, to 2026-11-08 04:03Z).
- **Larger archives are synthetic.** The real archive, followed by copies of its receipted stretch (1,802 snapshots, 29 October 20:46Z to 17 November 20:32Z), each copy moved a further 19 days: folder dates, receipt times and the board's own scheduled and expected dates move together. 1.5× is 2,755 snapshots, 4× is 7,243 (to 13 January 2027), 8× is 14,451 (to 30 March 2027). Their flights are not real. They measure time and memory and nothing else.
- **The gate's size.** The archive grows by about 95 snapshots a day (1,817 in the 19.1 days since receipts began), so on 15 January 2027, the gate's earliest day, it holds about 7,350: four times today's.

### The build as it stands

| archive | snapshots | limit | wall time | footprint | resident | result |
|---|---|---|---|---|---|---|
| quarter | 459 | default 6.3 GiB | 20 s | 2.34 GB | 1.13 GB | completed |
| half | 918 | default | 44 s | 4.40 GB | 1.28 GB | completed |
| whole | 1,837 | default | 450 s | 8.33 GB | 1.16 GB | completed |
| 1.5× synthetic | 2,755 | default | 903 s | 8.69 GB | 1.43 GB | completed, 4.6 GB spilled to disk |
| quarter | 459 | 2 GB | 25 s | 2.32 GB | 1.00 GB | completed |
| quarter | 459 | 1 GB | 14 s | 1.53 GB | 0.92 GB | out of memory in `codeshares` |
| quarter | 459 | 1 GB, 1 thread | 29 s | 1.51 GB | 0.86 GB | completed |
| half | 918 | 2 GB | 41 s | 3.18 GB | 1.54 GB | out of memory in `codeshares` |
| half | 918 | 1 GB, 1 thread | 39 s | 1.42 GB | 1.15 GB | out of memory in `codeshares` |
| whole | 1,837 | 2 GB | 244 s | 3.32 GB | 1.18 GB | out of memory in `build_flights` |

What the build needs, and how that grows. With room to spare (the default limit) the footprint doubles with the archive: 2.34 GB at a quarter, 4.40 GB at a half. On the whole archive the 8.33 GB is the machine's ceiling, not the need: macOS was compressing and swapping, which is why resident memory stayed near 1.2 GB and why the time went from 44 s to 450 s for twice the boards. Earlier builds on this Mac, recorded when they ran and not repeated today, show the same pattern: 344 s on 2026-11-15, 302 s and 360 s on 2026-11-17, each with a footprint between 7.5 and 8.2 GB and about 1 GB resident.

Which step. On the whole archive: reading the raw JSON 20 s (footprint 1.5 GB while it ran), R1 and R2 with the per-snapshot counts 113 s, observations 30 s, `build_flights` 276 s with the peak. Statement by statement on the 1.5× archive: `codeshares` 663 s, the per-snapshot counts 89 s, observations 87 s, `rows` 31 s, raw JSON 8 s.

Why `codeshares`. It makes one member list for every group of every board (2,393,345 on the whole archive), then keeps the group each flight sat in at its last appearance (13,021 flights, 8,335 distinct groups). While it ran with room to spare, DuckDB's allocator held 1.04 GiB at a quarter and 2.08 GiB at a half, and under the small limits tried that memory did not go to disk: the out-of-memory stops in the table. The two in-memory tables, `raw_rows` and `rows`, together took about 0.7 GiB per million board rows (0.66 GiB at a quarter, 1.3 GiB at a half), so about 2.6 GiB today; those can go to disk.

The proposal's window, tested. [data-model.md](data-model.md) proposed rebuilding observations and flights over "roughly ten days of rows" in a 2 GB function. The half cut is 9.7 days of boards, and it stopped at a 2 GB limit and at 1 GB with one thread. So a window alone would not have fitted: the codeshare statement has to change first, whatever else is done.

### Is a memory limit enough?

No. Not as the code stands (the table above), and not with the codeshare statement fixed either:

| build | archive | limit | wall time | footprint | result |
|---|---|---|---|---|---|
| change 1 only | quarter | 1 GB | 17 s | 1.13 GB | completed, same rows |
| change 1 only | half | 1 GB | 47 s | 1.39 GB | completed, same rows |
| change 1 only | whole | 2 GB | 75 s | 2.63 GB | completed, same rows |
| change 1 only | whole | 1 GB | 20 s | 1.46 GB | out of memory in `rows` |
| change 1 only | 4× synthetic | 3 GB | 99 s | 4.07 GB | out of memory in `rows`, 7.8 GB spilled |

Change 1 with a 2 GB limit is the smallest thing that works today: 75 s instead of 450. It does not reach the gate: on four times the archive the `rows` statement (R2's ranking of every row of every board at once) ran out of memory at a 3 GB limit. That statement, the per-snapshot counts and the raw read are all work on one board at a time, so they can be done a day at a time and kept: change 2.

## The design

Three changes to `src/model/`. Each is justified by a row in the tables above.

**1. `codeshares` lists only the groups it reads.** In `build_flights`, `at_last` moves before `groups`, and `groups` gains one filter:

```sql
), groups AS (
    SELECT group_key, list(...) AS members   -- as today
    FROM r WHERE group_key IN (SELECT group_key FROM at_last) GROUP BY group_key
)
```

A group that is kept keeps all its rows, so its member list is the one built today; the groups dropped are the ones nothing read. On the whole archive under a 2 GB limit the statement went from the build's peak to 0.9 s.

**2. Each day's per-board work is done once and kept.** For each date folder of `raw/`, the build reads that day's files with the model's own `load_raw` and writes two Parquet files into a stage folder (`data/stage/`, already ignored by git):

- the day's rows after R1 and R2: local times converted, duplicates removed, board key added, for every snapshot of the day, trusted or not;
- one row per snapshot: its fetch time, hash, pages, row counts, declared total, duplicate rows, key conflicts and scheduled-time range.

For each date folder of `receipts/` it writes that day's rows of the `receipts` table, through the model's own `load_receipts` and its check. Receipts are staged because the JSON reader's memory grows with the number of files: 7,771 receipt files ran out of memory at a 1 GB limit.

Everything else runs as today, over the whole history, on every build: which snapshots are trusted, repeats, sightings, numbering, retime links, observations, codeshare groups, flights. `rows` becomes the staged rows of the kept snapshots; `snapshot_files` and `snapshots` read the staged per-snapshot rows where they grouped `raw_rows`. The five output tables keep their names, columns and types. There is one build: given no stage folder it stages into a temporary one, so the tests and a from-scratch build run the same code as an everyday build.

A staged day is used only when its marker says it is current. The marker is a small file written after the day's Parquet files, holding the names and sizes of the day's source files and a fingerprint of the model's source files and the DuckDB version. A day is staged again when the marker is missing, the folder's listing differs, or the fingerprint differs. A staged day whose folder is no longer there is ignored.

**3. Explicit limits.** `model.build` sets `memory_limit` (default 1 GB), `threads` (default 2) and `temp_directory` (a folder it names, outside the repository's tracked files), each with an option. Two threads were faster than eight on the larger archive under the same limit (114 s against 204 s at 4×) and about the same on today's (16 to 18 s against 15 s). A build option that ignores the stage and builds it again gives the from-scratch build.

### What the prototype measured

The prototype applied the three changes to the model's statements at run time, without editing the source, and ran them on the real archive, its cuts and the synthetic archives. It reused a staged day whenever its file was there: the marker, the fingerprint and the temporary-folder default are design, not prototype. 1 GB limit, 2 threads, except where noted:

| archive | snapshots | board rows | first build (stages every day) | later build | later build's footprint | later build's spill to disk |
|---|---|---|---|---|---|---|
| quarter | 459 | 0.96 M | 14 s | 2 s | 0.64 GB | none |
| half | 918 | 1.86 M | 24 s | 7 s | 1.09 GB | none |
| whole | 1,837 | 3.77 M | 53 s | 16 s | 1.21 GB | 0.5 GB |
| 4× synthetic | 7,243 | 14.87 M | not run in one go: staging its 78 days took 147 s (8 threads) | 114 s | 1.30 GB | 2.8 GB |
| 8× synthetic | 14,451 | 29.67 M | not run in one go: staging 77 more days took 122 s | 200 s | 1.32 GB | 6.0 GB |

- Staging takes 1.6 to 1.9 s a day of boards (39 s for 21 days, 122 s for 77, at 2 threads) at a footprint under 0.6 GB, once. The first builds peaked at 0.62, 1.13 and 1.26 GB. The staged files for the whole archive are 14 MB, about 0.7 MB a day, against 88 MB of gzipped raw.
- A later build's time is the whole-history statements: on the 4× archive, observations 55 s, `codeshares` 41 s, `flights` 10 s, everything else about 4 s together; on the 8× archive 90 s, 85 s and 17 s.
- The limit hardly changes the time at 4× with 8 threads: 204 s at 1 GB, 212 s at 2 GB, 172 s at 3 GB (footprints 1.55, 2.45 and 3.39 GB). The footprint sits 0.3 to 0.6 GB above the limit, which covers DuckDB's buffers but not everything the process holds.
- The same tables. On the quarter, the half and the whole archive the prototype's five tables hold the same rows as the unchanged build's, `timeline.load.load()` returns equal lists from both, and `timeline.record` writes the same `progress.json` byte for byte. The unchanged build of the whole archive in turn holds the same rows as the model built on 17 November from the same boards, kept in the local data folder.

So for purpose (a): the build at the gate's size takes about two minutes within 1.3 GB, and at twice that size, about the end of March 2027, a little over three minutes. Today's build takes seven and a half minutes at the machine's ceiling. From 4× to 8× the time grew a little less than the archive did. Growth past 8× was not measured.

### The options side by side

| | The build as it stands | Change 1 and a limit | All three (proposed) | Plus a trailing window (the earlier proposal) |
|---|---|---|---|---|
| (a) today | 450 s, 8.33 GB; stops under a 2 GB limit | 75 s, 2.63 GB at a 2 GB limit | 16 s, 1.21 GB | not built, not measured |
| (a) at the gate's size | not measured past 1.5×: 903 s, 8.69 GB | out of memory at a 3 GB limit | 114 s, 1.30 GB | not measured |
| (b) inside 2 GB | no: 4.8 days of boards fitted a 2 GB limit, 9.7 did not | no | yes at 4× and 8× on this Mac; time and temp disk grow with the history | the nightly work would stop growing |
| kept between builds | nothing | nothing | each day's per-board work | that, and every flight judged closed |
| can drift from a full rebuild | no | no | only if a staged day goes stale: the marker and a test guard it | yes: the table under "Why not a trailing window" |
| frozen files edited | none | one statement and the build's options | the same, and the staging | the same, and the window |

### Re-run, crash, late files, rule change

- **Re-run.** With the same files, no day is staged again and the rest is recomputed: the same rows in every table.
- **Crash midway.** Each staged file is written under a temporary name and renamed; the marker is written last. A day without a current marker is staged again. Nothing else is kept between builds, so there is nothing else to repair.
- **A file that arrives late** (the current day, an interrupted sync, a second page of a snapshot). The folder's listing no longer matches the marker, so the day is staged again, about 2 s.
- **A late receipt.** Its day of receipts is staged again; it changes no staged board. What it changes, whether a snapshot is `pending`, `superseded` or kept, the 35-minute grace, `confirmed_until`, a misplaced receipt stopping the build, is decided as today, from all receipts, on every build.
- **A rule change.** Any edit to the model's source changes the fingerprint, and every day is staged again: about 2.5 minutes at the gate's size. Coarse on purpose: there is no way to edit a rule and keep a stale stage.
- **From scratch.** Deleting the stage folder, or the option that ignores it, rebuilds everything from the raw files. That build is the reference: a build that reuses the stage must give the same rows, and a test holds it to that.

### Why not a trailing window

The proposal's second stage, rebuild only flights that can still change, is not in this design. It is not needed for (a), and it is the part that can go wrong quietly. These are the rules that look past one board, and what each would cost a windowed rebuild:

| Rule, table | What it reads beyond one board | Why a window could differ from a full build |
|---|---|---|
| R2 trust, `snapshot_files` | `superseded` reads the next snapshot; `legacy` and `pending` read the first and the newest receipt of the whole archive; the stops read every receipt and every snapshot | the newest snapshot's status changes with the next download or receipt |
| R2 repeats, `snapshot_runs` | the previous kept snapshot's hash; `identical_repeats` counts the repeats that follow | the last kept snapshot's count can still grow |
| R9, `snapshots` | `confirmed_until` reads every receipt up to the next kept snapshot; `gap_before_s` the previous snapshot's; `snap_rn` numbers every kept snapshot in order | one snapshot admitted or dropped renumbers all after it; the newest snapshot's last sighting keeps moving |
| R4, `keys`, `links`, `keymap` | a key's first and last snapshot over the whole archive; a link needs the new key in the very next snapshot after the old key's last, and no rival | a key that comes back moves its last snapshot, which can undo a link or, by removing a rival, make one: a flight's id changes after the fact |
| R3, `observations` | the flight's previous appearance, however far back, and that snapshot's `confirmed_until` | nothing beyond the flight's own rows, its chain (R4) and `snapshots` |
| R5 and R6, `codeshares` | the ids of the other flights in the group at the flight's last appearance | a partner's chain changing (R4) changes this flight's `codeshare_group_id` with no new row of its own |
| R7, `flights` | the archive's latest snapshot (`open`), the snapshot after the flight's last (`gap`), `last_seen_at` | a flight on the newest board changes on every build |
| R8 | the flight's last appearance that was not CANCELED | nothing beyond the flight's own rows and `snapshots` |

"A flight that can no longer change", precisely. Its row and its observations are the same in every later full build when all of these hold: (1) none of its keys is on any later board; (2) the snapshot after its last appearance is kept and every receipt before that snapshot is in the copy; (3) no key of the same airline, number, direction and airport, scheduled within 12 hours of one of its keys, appears or comes back later; (4) the same holds for every flight in its codeshare group at its last appearance; (5) no earlier snapshot is admitted or dropped later. (1), (3) and (4) are promises about what the airport will list, and nothing guarantees them. On the model of 17 November a flight stayed on the board at most 125.5 hours and was last seen at most 51.4 hours after its final scheduled time; 9 flights were missing from some boards between their first and last appearance, one of them from 106 boards. The record's "closed" (C4, 48 hours after the scheduled time) is therefore not "can no longer change": flights have still been listed after it.

So a windowed build could only use a horizon ("not listed for N days") plus a guard that falls back to a full rebuild when a sealed key is seen again, and every line of the table would need its own test. This design keeps nothing that those rules decide, so the question does not arise.

If (b) later needs less work per night than the whole-history statements, the measurements point at a narrower step than a time window: retime links are cheap over the whole history (`keys`, `links` and `keymap` took under 3 s together at 8×), and observations are computed flight by flight, so the two costly statements could be run only for flights with a new row or a changed chain. That is its own design, with its own proof, when q2 needs it.

## The nightly function (b)

Not this work. What the measurements say for it:

- The staged build at a 1 GB limit and 2 threads peaked at 1.30 GB at the gate's size and 1.32 GB at twice that. A 2 GB function has room for that. Measured on this Mac only: a Lambda's processors, its memory accounting and reading from S3 instead of a local disk were not measured. UNVERIFIED.
- [data-model.md](data-model.md)'s sketch gives the function 2 GB of temp disk and ten minutes. The build spilled 2.8 GB to disk at 4× and 6.0 GB at 8×, so the temp disk has to be larger than the sketch says; the time depends on the Lambda's speed.
- Each night it would stage one or two days and read every staged file: 14 MB today, about 0.7 MB more a day.
- The build time grows with the history (16 s, 114 s and 200 s for 1×, 4× and 8×). When that outgrows the function, the choice is a larger function or the narrower step above. Decide then, on a measurement taken in a Lambda.

## The frozen record

`src/model/` is frozen under tag `record-v1`. "The record", condition 2, lets a change that only changes how the build is computed continue the version "when every figure for flights closed before the change is identical under both". This design is such a change and nothing else: no rule's result changes. It still edits frozen files, so it needs the owner's go (below).

What the frozen readers read. `timeline.load.load()` is their only way into the model: every column of `flights.parquet`, 21 named columns of `observations.parquet`, and `fetched_at`, `confirmed_until` and `gap_before_s` of `snapshots.parquet`, each sorted by a key with no ties (`flight_id` last for flights; `flight_id, snap_rn`; `snap_rn`). `counting.py` also imports `GAP_HOURS`. Same file names, columns and types after the change, so `load.py`, `counting.py`, `rates.py` and `record.py` do not change.

What "identical" is checked as. For two model folders:

1. each of the five tables has the same column names, types and column order;
2. each holds the same rows, repeats counted: no row in one and not in the other, checked both ways, every column, exact values, no tolerance;
3. `load()` returns equal lists from both. Every frozen figure is computed from those lists, so this covers every flight, closed or not;
4. `timeline.record` writes the same `progress.json`, byte for byte.

Row order inside the files is not compared, because it is not stable today: two runs of the unchanged build on the same archive wrote `flights.parquet` with 10 of 13,021 rows in different places and `snapshot_runs.parquet` in a different order throughout. `flights` is ordered by a key with ties and `snapshot_runs` by none. No frozen figure depends on it (point 3).

Against what, and on what.

- **Against the tagged code.** The reference is `src/model/rules.py` as tagged, not the edited file's old path. A local check script, like `scripts/figures_check.py`, builds a given copy of the archive with both and prints the four checks. It runs on the whole archive and on cuts at a quarter, a half and three quarters, and its result is recorded here with its date and command before the change merges. It cannot run in CI: the archive is not in the repository.
- **While the tagged code can still build it.** The tagged build of the whole archive takes 450 s today and took 903 s at 1.5×. Later comparisons run on stretches it can still build: a stretch cut to begin at a stored snapshot after receipts began, with the receipts from that moment on (not tried on its own today).
- **In CI, on synthetic archives.** The tagged `rules.py` is kept beside the tests as a fixture, byte for byte, its SHA-256 pinned. A test builds each synthetic archive with it and with the new build and applies checks 1 to 3. The archives are the ones the model tests already write, plus the cases that sit on a day boundary, since staging splits by date folder: a repeated store, a superseded snapshot, a retime, a codeshare group and a receipt's sighting each straddling midnight; a two-page snapshot; an incomplete one; a pending tail; and the three cut cases of `tests/test_record_cut.py`. An archive the tagged build refuses must be refused by the new one with the same kind of error.

Tests for the new parts, each with mutation entries in `scripts/mutation_check.py` (the break, then the test that must fail):

| Part | Test | Breaks that must be caught |
|---|---|---|
| `codeshares` filter | a group with a partner whose own last appearance is elsewhere; groups no flight ends in | filter by the flight's own row instead of its group; filter on the first appearance |
| staging equals the tagged build | the CI comparison above | a dropped snapshot's rows let into `rows`; a per-snapshot count taken after duplicates are removed; a receipts day skipped |
| reuse equals from scratch | build, add a day, add a file to the last day, add a file to an old day, build again on the same stage, compare with a fresh build | a changed folder's stage reused; a staged day read after its folder is gone |
| crash safety | a failure between the Parquet files and the marker | marker written first |
| rule change | a changed fingerprint | fingerprint not compared |
| limits | the connection's `memory_limit`, `threads` and `temp_directory` are the options given; no temp file under the working directory | a limit not set |
| the comparison itself | two folders that differ in one value, one row, one column type | a table skipped; repeats not counted; types not compared |

The existing model tests and their 62 mutation entries then run through the new build, since it is the only build; the plan confirms each entry's text is still found exactly once.

## Cost

$0 a month. The change is code, run on the Mac; nothing is deployed and no AWS call is added. Local disk: 14 MB of staged files today, about 0.7 MB a day, and temp files while a build runs (0.5 GB today, 2.8 GB at 4×, 6.0 GB at 8×), removed afterwards. The nightly function's cost is q2's to estimate.

## What you might not think to ask

- **State that drifts.** Anything kept between builds can quietly stop matching a build from scratch, and nobody notices until a figure is wrong. Here only per-day work that depends on that day's files is kept, and a test compares a build that reuses it with a build from scratch.
- **The same input twice.** A step is safe to retry when running it again gives the same result (idempotent). Staging a day twice gives the same rows, so a retry after a failure cannot double-count a day.
- **Partial writes.** A build killed midway must not leave something that looks finished: staged files get a temporary name, a rename and a marker written last. The model's own output folder has this gap today (five files written in turn); question 4 below closes it.
- **Late and repaired data.** A pipeline that only looks at new days misses a file that lands in an old one, so the marker compares every folder's listing. It compares names and sizes, not contents; the archive is write-once, and a receipted snapshot's row and page counts are checked on every build.
- **A change of rules or tools.** Kept results are right only for the code that made them, so the fingerprint covers the model's source and the DuckDB version.
- **The reference can stop running.** The proof compares with the tagged code, and the tagged code is the build that is outgrowing the machine: the whole-archive comparison should be run while it still takes minutes.
- **"Identical" needs a definition.** Today's build does not write byte-identical files twice in a row, so the check is the same rows and equal `load()`, which is what the frozen figures depend on.
- **Tests that cannot see the real data.** CI has no archive: it proves the rules on small made-up boards, and a local script proves the real one, whose result has to be written down.

## For the owner

My calls, 2026-11-18: housekeeping under condition 2, continuing `record-v1`; all three changes as one; "identical" is the four checks; the output folder written whole or not at all. The questions as they were put:

1. **Is this housekeeping under condition 2, continuing `record-v1`?** Recommended: yes, on the comparison passing against the tagged code on the whole archive and its cuts. If yes: the record continues with its counting start of 16 November; `git diff record-v1 -- src/model` shows the change and this document the comparison's result. If it must be a new version instead: `record-v2` gets a new counting start and its 60 days begin again. If `src/model/` is left alone: the tagged build keeps working for now at seven and a half minutes and rising (15 minutes at 1.5×), with the Mac at its memory ceiling throughout; where it stops was not measured.
2. **All three changes, or only 1 and 3 for now?** Recommended: all three, as one change with one proof. Changes 1 and 3 alone work today (75 s at a 2 GB limit) and were measured to stop before the gate's size (out of memory at 4×), so the frozen files would be edited, and the proof repeated, a second time before the gate.
3. **Is "identical" the four checks above?** Recommended: yes. The alternative, byte-identical files, would at least need a full ordering added to two statements in the frozen rules (`flights` is ordered by a key with ties, `snapshot_runs` by none), for no figure's sake; it was not tried.
4. **Should the model's output folder be written whole or not at all?** Recommended: yes, a temporary folder swapped in at the end, a few lines in `model.build`. Without it nothing changes from today: a build killed midway can leave a mixed folder, which the next successful build overwrites.

## Left to the plan

- Where the staging code lives in `src/model/`, and how R1 and R2's SQL is shared so that it is written once.
- The option names, the temp folder's place, and the stage folder's layout.
- The tagged `rules.py` as a fixture (assumed above) or fetched from the tag in CI.
- What the new tests add to the mutation check's run time (each model entry runs the model tests).
- The updates to [data-model.md](data-model.md) ("Nightly run", "How to run", its grade line) and the line for this note in `docs/README.md`.

## Unverified

- Everything about a Lambda: speed, memory accounting, S3 reads, temp disk. Nothing was run there.
- Growth beyond the 8× synthetic archive, and where the unchanged build stops outright (it completed at 1.5×).
- The synthetic archives stand in for real growth: their boards repeat the same 19 days, with a jump where one copy meets the next.
- Every figure but one is a single run; the one repeated (16 s and 18 s) is the only measure of run-to-run spread.
- The record's own output is a weak check today: counting began on 16 November, so on these boards no counted flight has closed (`timeline.record` reports 0 cancelled, gate not reached). The table and `load()` checks carry the proof until counted flights close; the comparison before the merge is the one that matters.
- Why DuckDB could not move the codeshare lists to disk under small limits is not established; the stops are what was observed.
- The board limits (125.5 h on the board, 51.4 h after the scheduled time) are from one model, 17 November.
- The figures of the builds of 15 and 17 November are as recorded on those days, not repeated.
- A comparison on a stretch that does not begin at the archive's start was not tried.
- The marker, the fingerprint and the temporary-folder default were not in the prototype.

## All runs (2026-11-18)

"Unchanged" is `rules.build_all` as tagged. "Change 1" adds the codeshare filter at run time. "Staged" is the prototype of all three changes; "first" stages every day, "later" reuses the stage. Limits are as given to DuckDB (it reads 1 GB as 953.6 MiB). Spill is the most temp storage DuckDB reported.

| build | archive | limit | threads | wall | footprint | resident | spill | result |
|---|---|---|---|---|---|---|---|---|
| unchanged | quarter (459) | default | 8 | 20 s | 2.34 GB | 1.13 GB | 0.0 GB | completed |
| unchanged | half (918) | default | 8 | 44 s | 4.40 GB | 1.28 GB | 0.0 GB | completed |
| unchanged | whole (1,837) | default | 8 | 450 s | 8.33 GB | 1.16 GB | 0.6 GB | completed |
| unchanged | 1.5× synthetic (2,755) | default | 8 | 903 s | 8.69 GB | 1.43 GB | 4.6 GB | completed |
| unchanged | quarter (459) | 2 GB | 8 | 25 s | 2.32 GB | 1.00 GB | 0.1 GB | completed |
| unchanged | quarter (459) | 1 GB | 8 | 14 s | 1.53 GB | 0.92 GB | 0.9 GB | out of memory in `codeshares` |
| unchanged | quarter (459) | 1 GB | 2 | 46 s | 1.70 GB | 0.82 GB | 0.6 GB | out of memory in `codeshares` |
| unchanged | quarter (459) | 1 GB | 1 | 29 s | 1.51 GB | 0.86 GB | 0.5 GB | completed |
| unchanged | half (918) | 2 GB | 8 | 41 s | 3.18 GB | 1.54 GB | 2.6 GB | out of memory in `codeshares` |
| unchanged | half (918) | 1 GB | 1 | 39 s | 1.42 GB | 1.15 GB | 1.5 GB | out of memory in `codeshares` |
| unchanged | whole (1,837) | 2 GB | 8 | 244 s | 3.32 GB | 1.18 GB | 3.5 GB | out of memory in `build_flights` (statements not timed apart in this run) |
| change 1 | quarter (459) | 1 GB | 8 | 17 s | 1.13 GB | 0.89 GB | 0.5 GB | completed |
| change 1 | half (918) | 1 GB | 8 | 47 s | 1.39 GB | 1.15 GB | 1.3 GB | completed |
| change 1 | whole (1,837) | 2 GB | 8 | 75 s | 2.63 GB | 1.64 GB | 1.8 GB | completed |
| change 1 | whole (1,837) | 1 GB | 8 | 20 s | 1.46 GB | 1.05 GB | 2.2 GB | out of memory in `rows` |
| change 1 | whole (1,837) | 1 GB | 2 | 28 s | 1.47 GB | 1.12 GB | 1.6 GB | out of memory in `rows` |
| change 1 | 4× synthetic (7,243) | 3 GB | 8 | 99 s | 4.07 GB | 1.80 GB | 7.8 GB | out of memory in `rows` |
| staged, first | quarter (459) | 1 GB | 2 | 14 s | 0.62 GB | 0.66 GB | 0.0 GB | completed |
| staged, later | quarter (459) | 1 GB | 2 | 2 s | 0.64 GB | 0.72 GB | 0.0 GB | completed |
| staged, first | half (918) | 1 GB | 2 | 24 s | 1.13 GB | 1.06 GB | 0.0 GB | completed |
| staged, later | half (918) | 1 GB | 2 | 7 s | 1.09 GB | 0.70 GB | 0.0 GB | completed |
| staged, first | whole (1,837) | 1 GB | 2 | 53 s | 1.26 GB | 1.05 GB | 0.6 GB | completed |
| staged, later | whole (1,837) | 1 GB | 2 | 16 s | 1.21 GB | 1.17 GB | 0.5 GB | completed |
| staged, first | whole (1,837) | 2 GB | 8 | 45 s | 2.23 GB | 1.20 GB | 0.1 GB | completed |
| staged, later | whole (1,837) | 2 GB | 8 | 22 s | 2.20 GB | 0.90 GB | 0.1 GB | completed |
| staged, later | whole (1,837) | 1 GB | 8 | 15 s | 1.29 GB | 1.01 GB | 0.7 GB | completed |
| staged, later | whole (1,837) | 1 GB | 2 | 18 s | 1.24 GB | 0.93 GB | 0.5 GB | completed |
| staged, later | whole (1,837) | 500 MB | 2 | 1 s | 0.41 GB | 0.43 GB | 0.0 GB | out of memory reading 1,954 receipt files (before receipts were staged) |
| staged, first | 4× synthetic (7,243) | 1 GB | 8 | 148 s | 0.77 GB | 0.70 GB | 0.0 GB | 78 days staged in 147 s, then out of memory reading 7,771 receipt files (before receipts were staged) |
| staged, later | 4× synthetic (7,243) | 1 GB | 8 | 204 s | 1.55 GB | 1.27 GB | 3.3 GB | completed |
| staged, later | 4× synthetic (7,243) | 2 GB | 8 | 212 s | 2.45 GB | 1.30 GB | 2.5 GB | completed |
| staged, later | 4× synthetic (7,243) | 3 GB | 8 | 172 s | 3.39 GB | 1.74 GB | 1.8 GB | completed |
| staged, later | 4× synthetic (7,243) | 1 GB | 2 | 114 s | 1.30 GB | 1.20 GB | 2.8 GB | completed |
| staged, 77 new days | 8× synthetic (14,451) | 1 GB | 2 | 320 s | 1.36 GB | 1.29 GB | 5.8 GB | completed |
| staged, later | 8× synthetic (14,451) | 1 GB | 2 | 200 s | 1.32 GB | 1.32 GB | 6.0 GB | completed |
