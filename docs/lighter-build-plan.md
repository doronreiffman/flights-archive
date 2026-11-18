# A lighter model build (q5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade**, quoted from the design (`docs/lighter-build.md:3`):

> Grade: production-lean, the data model's own grade ([data-model.md](data-model.md)): tested rules, a mutation check, a fresh review before anything ships, code only, no new infrastructure.

**Goal:** Make the model build fit the 8 GB development Mac until the record's gate and past it, through the design's three changes (the codeshare filter; each date folder's per-board work staged once, behind a marker and a source fingerprint; an explicit memory limit, thread count and temp directory) and a model folder written whole or not at all, with every output table identical to the tagged build's.

**Architecture:** The SQL stays in `src/model/rules.py`, each statement written once. R1 and R2's per-board work moves into one function, `per_board`, that runs on one date folder at a time; the whole-history statements read the staged results where they grouped `raw_rows`; `codeshares` gains its filter. A new `src/model/stage.py` stages each date folder of `raw/` and `receipts/` into Parquet with a marker, and opens the stage for the build. `src/model/build.py` sets the limits, runs the stage and then the rules, writes the five tables whole, and carries the options. The proof against the tagged code runs in two places. In CI, the tagged `rules.py` (a test fixture) builds every model test's archive and the day-boundary cases beside the new build. Locally, `scripts/tagged_check.py` runs the design's four checks on the real archive and its cuts (main session).

**Tech Stack:** Python 3.13 (`.venv`), DuckDB 1.5.6, pytest 9 with coverage. No new dependencies.

**Spec:** `docs/lighter-build.md` at 44bedea, with the owner's four calls of 2026-11-18 ("For the owner"), and `docs/flight-lookup.md`, "The record", condition 2 (line 699). Executors read the design sections their task names; the design's words win over any paraphrase here.

## Global Constraints

- Cost: $0 a month (code only), as the design says (`docs/lighter-build.md`, "Cost"). Local disk: about 14 MB of staged files today and about 0.7 MB a day more, plus temp files while a build runs, removed afterwards.
- Run everything with `.venv/bin/...` and `PYTHONPATH=src`. One test file: `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/<file>`. macOS has no `timeout`: `perl -e 'alarm N; exec @ARGV' <command>`. The shell is zsh: read `$?` on a command without a pipe.
- **The record.** Editing `src/model/` is housekeeping under "The record", condition 2, continuing `record-v1` (the owner's call, 2026-11-18). It may change how the build is computed and nothing else:
  - the five output tables (`snapshots`, `snapshot_runs`, `observations`, `flights`, `receipts`) keep their file names, columns, types and column order;
  - on every archive they hold the same rows as the tagged build's, and an archive the tagged build refuses is refused with the same kind of error (Task 2 holds every later commit to this);
  - `src/timeline/load.py`, `counting.py`, `rates.py` and `record.py` are touched by no task;
  - tag `record-v1` (b948ea2) stands. DuckDB 1.5.6 and Python 3.13 stay as its message names them.
- `src/model/` imports only the standard library, `model` and `duckdb` (no pyarrow, no pandas, nothing new), and no timeline module (`tests/test_frozen.py`).
- A task whose change makes the comparison with the tagged build fail stops and reports to the main session. Nobody edits an expected value or the comparison to make it pass.
- Tests never write under the checkout: every archive, stage, model and temp folder sits under `tmp_path`. No task reads or builds the real archive (`data/`); that is the main session's.
- Every task leaves the whole suite passing at its commit, with coverage at 95% or more: `PYTHONPATH=src .venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95`.
- Some tests cannot fail before their change, because the change is meant to change no result (Task 3's filter, Task 4's staging). The step says so, and the task's mutation entries are what prove those tests bite.
- **Mutation check.** `scripts/mutation_check.py` edits source files in place: run it alone, with nothing else running from the checkout, and never during a model build. New entry names start with their area: "R5 " for the codeshare filter (in `MODEL_MUTATIONS`), then "stage: ", "build: ", "tagged: " (the CI comparison) and "tagged check: " (the local script). Entries are picked by target file, not by name prefix, since older entries carry none. `MODEL_MUTATIONS` gives every entry the `MODEL` target; an entry with any other target or test set goes in `COLLECTOR_MUTATIONS` with its own, as "frozen: model imports timeline" does. Each task runs the entries of the files it touched (the guard stops an empty list, which would run all of them):

  ```sh
  PYTHONPATH=scripts .venv/bin/python -c 'import sys, mutation_check as m
  names = [n for n, ((f, _), _, _) in m.MUTATIONS.items() if f in sys.argv[1:]]
  sys.exit(m.main(names) if names else "no entries target " + " ".join(sys.argv[1:]))' <files the task changed>
  ```

  Expected: every entry CAUGHT, none STALE, none ERROR. Before that, after any edit to a file that entries target, check in seconds that every entry's text is still found exactly once:

  ```sh
  PYTHONPATH=scripts .venv/bin/python -c 'import mutation_check as m
  stale = [n for n, ((f, _), old, _) in m.MUTATIONS.items() if (m.ROOT / f).read_text().count(old) != 1]
  print(stale or "every entry found once")'
  ```
- **The 62 existing model entries** target `src/model/rules.py` and run `tests/test_model.py` with `tests/test_model_receipts.py`, which build through the new code, the only build. None should need rewording: the lines they quote stay where they are, or move with their text and indentation unchanged (Task 4 names the five that move). If a quoted line must change after all, the entry's old text becomes the new line and its new text the same break on it; the change goes in "Deviations".
- No push, no `gh`, no AWS from any task.
- Implementers by kind, one tier above the subagent-driven-development skill's cost guidance: transcription → Sonnet, integration → Opus, architecture → Fable; never Haiku. A fresh Opus reviewer reads each task's diff before the next task starts. A fresh Fable reviewer reads the whole branch once (Task 9). A reviewer's finding, and an implementer's note, is checked against its source before it is folded in.
- Documents in this repository are public: neutral voice; "I" and "my call" only in the owner's own words.
- Baseline at 44bedea (checked 2026-11-18): `PYTHONPATH=src .venv/bin/pytest -o addopts="" --collect-only -q` collects 1,453 tests. `scripts/mutation_check.py` holds 678 entries, 62 of them in `MODEL_MUTATIONS` and 64 targeting `src/model/` in all. `tests/test_model.py` with `tests/test_model_receipts.py` (100 tests) ran in 7.0 s. `git show record-v1:src/model/rules.py | shasum -a 256` gives `57a07619159113601e3ac9311a7ccd69ee27f93fc1a57ad7860d20a4c6bf4162`, the same as `src/model/rules.py` at 44bedea.

**Main-session steps.** These are run by the main session, never by an implementer, and are marked "(main session)" in the tasks:
- the comparison on the real archive and its cuts, and the new build's own time on it (Task 8), with nothing else running. The tagged build of the whole archive took 450 s and peaked at 8.33 GB on this 8 GB Mac (`docs/lighter-build.md`, one run);
- the full mutation check, alone (Task 11);
- syncing data (`sh scripts/sync.sh`, which checks the `flights-sam` identity itself);
- every commit that records a result, every push, and the merge, each on the owner's go.

## Review Focus

The input classes the design implies but its test table does not name, most likely first. Each has its test in the owning task.

1. **A build stopped midway**, by an error or by Ctrl-C, while staging a day or while writing the model folder. Expected: no day looks staged that is not whole, the last model folder stays whole, and temp folders are removed, or cleared by the next build. Tests: `test_a_day_whose_marker_was_not_written_is_staged_again` with a `KeyboardInterrupt` case (Task 5); `test_a_failed_build_leaves_the_last_model_as_it_was` with a `KeyboardInterrupt` case (Task 6).
2. **A stage left by other code, or a damaged one**: a branch switch, a zero-byte or hand-edited marker, a staged file deleted by hand. Expected: that day is staged again; it is never trusted and never stops the build. Tests: `test_a_changed_fingerprint_stages_every_day_again` and `test_a_damaged_stage_is_staged_again` (Task 5).
3. **A date folder with no snapshot files**: an interrupted sync's empty `date=…/`, or one holding only `.DS_Store`. Expected: skipped, not an error. Test: `test_an_empty_date_folder_is_skipped` (Task 4).
4. **A path with an apostrophe or a space** in the archive, stage, model or temp folder. Expected: the build works, since every path written into SQL has its quotes doubled. Tests: `test_paths_with_an_apostrophe_and_a_space_build` (Task 4) and the quoted temp folder in `test_the_connection_takes_the_limits_given` (Task 6).
5. **`--out` naming a folder that is not a model**, such as `--out data`. Writing whole or not at all means replacing the old folder, and so deleting it. Expected: refused, with nothing moved or deleted. Test: `test_a_folder_that_is_not_a_model_is_never_replaced` (Task 6).

## Order, and why

- Tasks 1 and 2 come first. The comparison with the tagged build exists, and passes on today's unchanged code, before any frozen file changes, so the suite itself checks every later commit against the tag.
- Task 3 is change 1, the smallest edit to a frozen statement and the one with the largest measured effect.
- Tasks 4 and 5 are change 2, in two steps. Task 4 stages every day on every build, which proves the SQL split on its own. Task 5 adds the marker and the fingerprint, the only state kept between builds.
- Task 6 is change 3 and the output folder. It wraps the build as it stands by then, and the default stage folder belongs with the options.
- Task 7 runs its child builds with Task 6's options (`--stage`, `--temp-dir`).
- Task 8 runs the real comparison before the whole-branch review, so a difference is found before the review is spent. Any later change to `src/model/` runs it again.
- Tasks 9 to 11 are the review, the documents (with Task 8's figures) and the final verification with the counts.

| Task | What | Implementer |
|---|---|---|
| 1 | The tagged fixture and the four checks (`scripts/tagged_check.py`) | integration (Opus) |
| 2 | Every model test against the tagged build; the day-boundary and cut cases | integration (Opus) |
| 3 | Change 1: the codeshare filter | transcription (Sonnet) |
| 4 | Change 2, part 1: the per-board work staged per date folder | integration (Opus) |
| 5 | Change 2, part 2: the marker, the fingerprint and reuse | integration (Opus) |
| 6 | Change 3 and the output folder: limits, temp folder, whole or nothing, options | integration (Opus) |
| 7 | The local check's runner | integration (Opus) |
| 8 | The comparison on the real archive; the new build's time | main session |
| 9 | Whole-branch review | Fable reviewer (main session) |
| 10 | Documents | transcription (Sonnet) |
| 11 | Final verification, then the push and the merge | main session and the owner |

**Coverage of the design.**
- "The design": change 1 in Task 3, change 2 in Tasks 4 and 5, change 3 in Task 6.
- "Re-run, crash, late files, rule change": Task 5. The from-scratch option is in Tasks 5 and 6.
- "The frozen record": "What 'identical' is checked as" in Task 1; "Against the tagged code" in Tasks 7 and 8; "In CI, on synthetic archives" in Task 2, with Task 4's entries.
- "Tests for the new parts", row by row:
  - the `codeshares` filter: Task 3;
  - staging equals the tagged build: Tasks 2 and 4;
  - reuse equals from scratch, crash safety and rule change: Task 5;
  - limits: Task 6;
  - the comparison itself: Task 1.
- "For the owner", call 4 (the output folder): Task 6.
- "Left to the plan": "What this plan decided", below. The document updates are Task 10.

## What this plan decided

The design leaves these to the plan.

- **Where the code lives.**
  - All SQL stays in `rules.py`: the new `per_board` and the whole-history statements. That keeps R1 and R2 written once, and keeps the 62 entries on the file they target.
  - `stage.py` holds the staging's file handling, and no rule.
  - `build.py` holds the connection's limits, the run, the output folder and the options.
- **How R1 and R2's SQL is shared.**
  - `per_board` holds two statements. One is today's `rows` statement without its filter on trusted snapshots. The other holds the per-snapshot counts that `snapshot_files` and `snapshots` grouped from `raw_rows`. Every line moves with its text unchanged.
  - The whole-history `snapshot_files` and `snapshots` read `staged_counts`.
  - `rows` becomes a view: the staged rows of the trusted snapshots, as in the prototype the design measured.
  - The scheduled-time range and each snapshot's kept-row counts stay in `snapshots`' `kept` part, which still reads `rows`. The design lists them among the staged columns. Left where they are, they keep the edit to the frozen statements smaller, and the filter on trusted snapshots stays written once, so its two entries still find their text once. The cost is one more read of the staged rows per build, which Task 8 measures.
  - The stage holds each snapshot's `incomplete` flag, worked out per day where the entry's line already is, in place of the declared total. The hash comes from the snapshot id, as today.
- **The stage folder.**
  - Layout: `<stage>/raw/date=YYYY-MM-DD/` holds `rows.parquet`, `counts.parquet` and `marker.json`, and `<stage>/receipts/date=YYYY-MM-DD/` holds `receipts.parquet` and `marker.json`. Parquet is ZSTD-compressed, as the prototype was (14 MB for the whole archive).
  - The command line's default is `stage/` beside `--raw`, so `data/stage/`, the folder the design names.
  - `model.build.build` called with no stage folder stages into a temporary one and removes it afterwards: one build, as the design asks.
- **The marker and the fingerprint.**
  - The marker is `{"fingerprint": …, "files": [[relative path, size], …]}`. It lists the day's `*.json.gz` (raw) or `*.json` (receipts) files under the day folder, recursively, as sorted relative POSIX paths.
  - A day is current only when its marker reads and equals that, and its staged files exist. Anything else, a read or parse error included, means "stage it again".
  - The fingerprint is the SHA-256 of every `src/model/*.py` (name and bytes, in name order) and `duckdb.__version__`. It is coarse on purpose, as the design says.
  - A day's old marker is deleted before its files are rewritten. Each file is written under a temporary name carrying the process id and then renamed, and the marker comes last.
- **Files outside the `date=` folders are refused**, for `raw/` and `receipts/` both. For `raw/`, the tagged build refuses a stray file too, through `load_raw`'s path check (`test_unexpected_file_layout_raises`). For `receipts/`, the tagged build would read a stray receipt, and the new build stops on it. The collector writes neither (its keys are `raw/date=…/…` and `receipts/date=…/…`, `src/collector/core.py:314` and :328), so the archive is unaffected, and Task 8 confirms it. Staging by date folder cannot place such a file, and skipping it silently could drop a sighting.
- **Options and defaults** for `python -m model.build`:
  - `--stage DIR` (default: `stage/` beside `--raw`);
  - `--restage`, which stages every date folder again (the from-scratch build);
  - `--memory-limit` (default `1GB`) and `--threads` (default `2`), the design's figures;
  - `--temp-dir DIR` (default: a new folder under the system's temp folder, from Python's `tempfile`, removed after the build). It is never `.tmp/` under the working directory, where DuckDB writes today and where the mutation check edits files; a Lambda's `/tmp` later is the same idea.
- **The model folder** is written beside itself as `<out>.building` and then swapped in, the way `timeline.build.write_site` does it. A folder (`<out>`, `<out>.building` or `<out>.old`) holding anything but the five table files is never replaced or deleted, so `--out data` cannot delete the archive copy. This check reads the folder's contents rather than a marker file, since the existing model folders carry none.
- **The tagged `rules.py` is a fixture**, `tests/fixtures/rules_record_v1.py`, byte for byte, its SHA-256 pinned in the script and in a test. It is not fetched from the tag:
  - CI's checkout (`actions/checkout@v4` in `.github/workflows/ci.yml`, with its defaults) fetches one commit and no tags (UNVERIFIED: the action's documented default, not checked for this plan), so fetching would change the workflow and need git in every mutation run;
  - a fixture works offline and shows the reference in the repository;
  - a test compares it with `git show record-v1:src/model/rules.py` whenever the tag is in the clone, and the local script refuses to run when the two differ.
- **"The same kind of error"** means the same exception class. The new build's message is pinned by that archive's own test.
- **The CI comparison's archives.**
  - Every model test's archive: `tests/test_model_tagged.py` collects `tests/test_model.py` and `tests/test_model_receipts.py` a second time, with the comparison switched on in `tests/model_helpers.py`.
  - The design's day-boundary cases, plus a board with an exact duplicate row and a key conflict, so that a count break has something to catch.
  - Every case of `tests/test_record_cut.py` built whole, and condition 3's three named cases (leave-and-return, retime-at-the-cut, flight-changes-after; `docs/flight-lookup.md:706`) at each of their moments. That is the plan's reading of the design's "the three cut cases" (the file holds eleven); building all eleven whole covers the other reading too.
- **The local script** is `scripts/tagged_check.py`.
  - Each build runs in its own process, so the tagged build's memory goes back to the system before the next build.
  - The tagged build runs exactly as tagged, except that DuckDB's temp folder is named. That changes where it spills, not what it computes.
  - A cut keeps the first ⌊N × fraction⌋ snapshot folders in path-time order, which gives the design's 459 and 918 of 1,837, and is copied by `cut_archive` (`tests/model_helpers.py`), one rule for both.
- **What the new tests add to the mutation check.** Estimated, UNVERIFIED:
  - each of the 64 entries on `src/model/` reruns the model tests, which take longer once every build stages: about 7 s today, perhaps 10 to 14 s;
  - about 40 new entries;
  - together, the full check from about 25 to about 35 minutes.

  Task 4 measures the model tests and Task 11 the full check. `TIME_LIMIT` stays at 120 s unless an unmutated target run passes about 20 s.

## Questions for the owner

1. **A line under "The record" in `docs/flight-lookup.md`.** The owner's call, 2026-11-18: yes, as recommended. Condition 2 says what housekeeping may be, but the record's own section will not say that it has happened. Recommendation: one neutral sentence after condition 2, written only once Task 8 has passed: "Housekeeping under this condition so far: the lighter model build of November 2026 ([lighter-build.md](lighter-build.md)), identical under both on the whole archive and its cuts; record-v1 continues." If yes, a reader of the record finds the change and its proof from the condition itself. If no, `docs/lighter-build.md` and `git diff record-v1 -- src/model` carry it alone, as the design's question 1 described. Task 10.

## Design and code

- `tests/test_frozen.py` checks only that `src/model/` imports no timeline module (`test_model_modules_import_no_timeline_module`). Its `ALLOWED` list ("the standard library, `model` and `duckdb`") applies to the four frozen timeline modules. This plan keeps `src/model/` to the standard library and `duckdb` as a rule its reviewers check; a guard test for it would be new scope.
- `docs/lighter-build.md:86` lists the scheduled-time range and the declared total among the staged per-snapshot columns. The plan keeps the range in `snapshots`, reading `rows`, and stages `incomplete` in place of the total ("What this plan decided").
- `docs/lighter-build.md:184`, "the three cut cases of `tests/test_record_cut.py`": the file holds eleven cases. See "What this plan decided".
- `scripts/mutation_check.py:37-43`: `TIME_LIMIT`'s comment cites the model tests at 7.7 to 11.3 s (2026-11-11); they ran in 7.0 s on 2026-11-18. Task 4 measures them after staging and updates the comment.
- `docs/data-model.md:3` gives the trigger for incremental work as "the nightly rebuild passing about five minutes". This change was driven by memory (`docs/lighter-build.md`, "The short answer"). Task 10 rewrites the line.
- `docs/data-model.md:50` (a 2 GB function "would run out after about two weeks of snapshots", "reading every raw file every night") no longer holds once the build stages, as measured on the Mac. Task 10 follows `docs/lighter-build.md`, "The nightly function (b)".
- `docs/lighter-build.md:26` describes `.tmp/` under the working directory as today's temp folder. After Task 6 that is no longer so. The design's measurement sections stay as written; Task 10 changes its status line.

---

### Task 1: The tagged fixture and the four checks

Implementer: integration (Opus). Design: `docs/lighter-build.md`, "The frozen record" (:165-198).

**Files:**
- Create: `tests/fixtures/rules_record_v1.py` (`git show record-v1:src/model/rules.py > tests/fixtures/rules_record_v1.py`, nothing else), `scripts/tagged_check.py`, `tests/test_tagged_check.py`
- Modify: `tests/fixtures/README.md` (one paragraph: what the file is, that it is the tag's `src/model/rules.py` byte for byte, and that its SHA-256 is pinned), `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `model.build.TABLES`; `timeline.load.load`; `timeline.record.main` and `timeline.record.TAG`; `model_helpers._path_time` in the script, with `tests/` put on `sys.path` at its top and a comment saying why (one cut rule for the tests and the script; Task 7 adds `cut_archive`); `model_helpers.write_snapshot`, `write_receipt`, `row`, `at` in the tests.
- Produces, in `scripts/tagged_check.py` (docstring: what it compares, and the command, as `scripts/figures_check.py` does):
  - `ROOT`; `TAGGED_RULES = ROOT / "tests" / "fixtures" / "rules_record_v1.py"`; `TAGGED_SHA256 = "57a07619159113601e3ac9311a7ccd69ee27f93fc1a57ad7860d20a4c6bf4162"`;
  - `tagged_rules() -> types.ModuleType`: the fixture loaded by `importlib` as module `rules_record_v1`, after checking its SHA-256. A mismatch raises `ValueError` naming both hashes;
  - `build_tagged(raw: Path, receipts: Path | None, out: Path, temp_dir: Path, known_orphans: frozenset[str] = frozenset()) -> dict[str, int]`: the tagged build as `src/model/build.py` ran it at the tag. It sets the module's `KNOWN_ORPHANS` to `known_orphans`, calls `connect()`, sets `temp_directory` to `temp_dir` and nothing else, calls `build_all(con, f"{raw}/**/*.json.gz", None if receipts is None else f"{receipts}/**/*.json")`, then writes `COPY {table} TO '<out>/{table}.parquet' (FORMAT PARQUET)` for each of `TABLES`, with `out` created first;
  - `compare_tables(a: Path, b: Path, names: tuple[str, str] = ("tagged", "new")) -> list[str]`: checks 1 and 2, one line per difference, `[]` when the same. For each table of `TABLES`, in order:
    - `f"{table}: columns differ: {names[0]} {cols_a}, {names[1]} {cols_b}"` when the (name, type) pairs of `DESCRIBE SELECT * FROM '<file>'` differ in any way, order included. The table's rows are then not compared;
    - otherwise `f"{table}: {n:,} row{'s' if n != 1 else ''} only in {name}"` for each side holding rows the other does not, counted with `EXCEPT ALL`, both ways, every column, exact values;
  - `compare_load(a: Path, b: Path) -> list[str]`: check 3. `f"load(): {part} differ"` for each of `flights`, `observations`, `snapshots` whose list from `timeline.load.load` differs;
  - `compare_progress(a: Path, b: Path, work: Path, names: tuple[str, str] = ("tagged", "new")) -> list[str]`: check 4. It runs `timeline.record.main(["--model", str(m), "--out", str(work / name)])` for each, then returns `f"timeline.record exit codes differ: {code_a} and {code_b}"` and/or `"progress.json differs"` when the bytes of `<work>/<name>/<TAG>/progress.json` differ;
  - `Cut(NamedTuple)`: `fraction: float`, `kept: int`, `total: int`, `moment: datetime`;
  - `cut_moments(raw: Path, fractions: Sequence[float]) -> list[Cut]`: the snapshot folders `raw/date=*/*Z-*` sorted by path time (`model_helpers._path_time`'s rule), with `kept = floor(total × fraction)` and `moment` the path time of the `kept`-th folder.
- Every DuckDB connection in the script sets `TimeZone = 'UTC'`.

- [ ] **Step 1: Write the failing tests** (`tests/test_tagged_check.py`, loading the script by `importlib`, as `tests/test_figures_check.py` does). The archive for the comparison tests holds two boards with receipts, and an unchanged receipt, so that every table has rows:
  - `test_the_fixture_is_the_tagged_rules_byte_for_byte`: `hashlib.sha256(TAGGED_RULES.read_bytes()).hexdigest() == "57a07619159113601e3ac9311a7ccd69ee27f93fc1a57ad7860d20a4c6bf4162" == TAGGED_SHA256`.
  - `test_a_changed_fixture_is_refused`: `TAGGED_RULES` monkeypatched to a copy with one byte changed; `tagged_rules()` raises `ValueError` matching "SHA-256".
  - `test_the_tagged_build_writes_the_five_tables`: five files, and counts with the keys `snapshots`, `observations`, `flights`, `receipts`.
  - `test_the_tagged_build_drops_the_known_orphans_given`: `test_a_known_orphan_is_dropped`'s archive builds with `known_orphans={b}`, and raises `ValueError` matching "no receipt" without it.
  - `test_one_archive_compares_equal`: `build_tagged` and `model.build.build` on one archive: `compare_tables` and `compare_load` both `[]`.
  - `test_one_changed_value_is_found_in_each_table`, parametrized over the five tables. A copy of the folder has one value changed in one row: `snapshots.rows`, `snapshot_runs.identical_repeats`, `observations.status`, `flights.final_status`, `receipts.rows`. Expected exactly `[f"{t}: 1 row only in tagged", f"{t}: 1 row only in new"]`.
  - `test_a_repeated_row_is_found`: one `observations` row written twice in the copy; expected `["observations: 1 row only in new"]`.
  - `test_a_missing_row_is_found_both_ways`: one `flights` row left out of the copy; expected `["flights: 1 row only in tagged"]`, and with the folders swapped `["flights: 1 row only in new"]`.
  - `test_a_changed_column_type_is_found`: `snapshot_runs.identical_repeats` cast to another integer type, values unchanged; expected one line, starting "snapshot_runs: columns differ".
  - `test_load_differences_are_found`: an `observations.status` changed; `compare_load` gives `["load(): observations differ"]`.
  - `test_equal_models_give_the_same_progress`: `compare_progress` on two copies of one model is `[]`.
  - `test_progress_differences_are_found`: `timeline.record.main` monkeypatched to write different bytes for the second model; expected `["progress.json differs"]`.
  - `test_cut_moments_take_the_floor`: 7 snapshot folders over two dates at fractions 0.25, 0.5, 0.75 and 1 keep 1, 3, 5 and 7, each moment the kept folder's path time; 8 folders keep 2, 4, 6 and 8.
- [ ] **Step 2: Run; fail.** `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/test_tagged_check.py` (the script does not exist yet).
- [ ] **Step 3: Implement** the fixture copy and the functions above. Check the copy with `shasum -a 256 tests/fixtures/rules_record_v1.py`.
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`TAGGED_CHECK = ("scripts/tagged_check.py", ["tests/test_tagged_check.py"])`). Each break, and the test that must fail:
  - "tagged check: the fixture's hash not checked" → `test_a_changed_fixture_is_refused`;
  - "tagged check: a table skipped" (the last of `TABLES` left out) → `test_one_changed_value_is_found_in_each_table[receipts]`;
  - "tagged check: repeats not counted" (`EXCEPT` for `EXCEPT ALL`) → `test_a_repeated_row_is_found`;
  - "tagged check: rows compared one way only" → `test_a_missing_row_is_found_both_ways`;
  - "tagged check: types not compared" (names only) → `test_a_changed_column_type_is_found`;
  - "tagged check: load() not compared" (`observations` left out) → `test_load_differences_are_found`;
  - "tagged check: progress.json not compared" → `test_progress_differences_are_found`;
  - "tagged check: cut by rounding" → `test_cut_moments_take_the_floor`.

  Run the entries of `scripts/tagged_check.py`.
- [ ] **Step 6: Commit** (`q5: the tagged rules as a pinned fixture, and the four checks that compare two model folders`).
- [ ] **Step 7: Review (Opus).**

### Task 2: Every model test against the tagged build; the day-boundary and cut cases

Implementer: integration (Opus). Design: `docs/lighter-build.md:184`.

**Files:**
- Modify: `tests/model_helpers.py`
- Create: `tests/test_model_tagged.py`

**Interfaces:**
- Consumes: Task 1's `tagged_check.build_tagged`, `compare_tables`, `compare_load`; `test_record_cut.CASES` and `Archive`; `model_helpers.cut_archive`.
- Produces, in `tests/model_helpers.py`:
  - `COMPARE_WITH_TAGGED: bool = False`;
  - `check_script() -> types.ModuleType`: `scripts/tagged_check.py`, loaded once by `importlib` and kept;
  - `build(raw, receipts=None)`, same signature and return (a connection holding every table the rules make). With `COMPARE_WITH_TAGGED` on:
    - when the new build raises, the tagged build runs on the same archive. An `AssertionError` is raised if it builds, or if it raises another exception class; otherwise the new build's own error is raised again, for the test's `pytest.raises`;
    - when the new build succeeds, its connection's five tables are written to a folder (`COPY … (FORMAT PARQUET)`) and the tagged build writes its own, with `known_orphans=model.rules.KNOWN_ORPHANS` (the tests monkeypatch that) and every folder under `raw.parent` (`tempfile.mkdtemp(dir=raw.parent)`). An `AssertionError` is raised if the tagged build refuses, or if `compare_tables + compare_load` is not `[]`, with the lines as its message.
- Produces, in `tests/test_model_tagged.py` (docstring: why it exists, the design's line 184, and that it re-runs the model tests):
  - `from test_model import *` and `from test_model_receipts import *` (`# noqa: F401,F403`, with one line saying why: pytest collects the imported tests again here, with the comparison on);
  - an autouse fixture that sets `model_helpers.COMPARE_WITH_TAGGED` to true through `monkeypatch`;
  - `BOUNDARY: dict[str, Callable[[Path, Path], None]]`, each case writing into `(raw, receipts)`, on 30 and 31 October 2026 (after `RECEIPTS_SINCE`) unless noted, each stored receipt carrying its board's rows and pages:
    - `repeated-store`: a board at 23:45, the same hash stored again at 00:01 with its own receipt, another board at 00:15;
    - `superseded`: a board at 23:30; a board at 23:58 with no receipt, stored again at 00:00 with the same hash and a receipt; a board at 00:15;
    - `retime`: LY 001 last listed at 23:45; the same number 2 hours later first listed at 00:00;
    - `codeshare`: EY 607, LY 9614 and W4 6406 in one group at 23:45; EY 607 and LY 9614 at 00:00; LY 9614 alone at 00:15;
    - `sighting`: a board at 23:50; unchanged receipts at 00:10 and 00:20 (receipts' 31 October folder); other content at 00:30;
    - `two-page`: a two-page board of 5 rows at 23:59; a board at 00:15;
    - `incomplete`: on 27 and 28 October, legacy with no receipts. A two-page board at 23:59 loses its second page; complete boards come at 23:45 and 00:15;
    - `pending-tail`: a board at 23:45 with its receipt; a board at 00:10 with none (pending, inside the 35 minutes);
    - `duplicates`: a board at 23:59 holding an exact duplicate row, and two rows on one key with different `_id`; a board at 00:15.

- [ ] **Step 1: Write the tests:**
  - `test_the_fixture_is_what_the_tag_holds`: `git show record-v1:src/model/rules.py` (run in `ROOT`) gives the fixture's bytes. Skipped, naming why, when git or the tag is missing (CI clones without tags).
  - `test_boundary_cases_match`, parametrized over `BOUNDARY`: the case's `raw/` holds two date folders (and the `sighting` case's `receipts/` two), then `model_helpers.build(raw, receipts)`.
  - `test_record_cut_cases_match` (importing only `CASES` and `Archive` from `test_record_cut`, so that its tests are not collected twice), parametrized over every `CASES` name built whole, and over `leave-and-return`, `retime-at-the-cut` and `flight-changes-after` cut at each of their moments (`cut_archive`); each through `model_helpers.build`.
  - `test_a_rule_changed_on_the_new_side_only_is_caught`: `model.rules.VANISH_HORIZON_HOURS` monkeypatched to 6 on `test_vanish_horizon_is_one_hour_past_the_last_appearance`'s archive. `model_helpers.build` raises `AssertionError` matching "flights".
  - `test_a_refusal_on_one_side_only_is_caught`: `model.rules.PENDING_GRACE_MINUTES` monkeypatched to 5 on an archive with a board 15 minutes after the newest receipt. `AssertionError` matching "refused".
- [ ] **Step 2: Run; fail.** `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/test_model_tagged.py`. Expected: every test errors, since `model_helpers` has no `COMPARE_WITH_TAGGED` for the autouse fixture to set.
- [ ] **Step 3: Implement** the comparison in `model_helpers.build`. The new side is today's build (`rules.connect()`, `rules.build_all`) until Task 4.
- [ ] **Step 4: Run; pass.** Then the full suite, and record the time of `tests/test_model_tagged.py` alone in the commit message.
- [ ] **Step 5: Mutation entries.** None here. This task changes test code only; the two "is caught" tests guard the comparison. The entries on `test_boundary_cases_match` come with the code they break, in Tasks 4 and 5.
- [ ] **Step 6: Commit** (`q5: every model test, the day-boundary cases and the cut cases also built by the tagged rules and compared`).
- [ ] **Step 7: Review (Opus).**

### Task 3: Change 1, the codeshare filter

Implementer: transcription (Sonnet). Design: `docs/lighter-build.md`, "The design", 1 (:72-81).

**Files:**
- Modify: `src/model/rules.py` (`build_flights`, the `codeshares` statement only), `tests/test_model.py` (R5 section), `scripts/mutation_check.py` (`MODEL_MUTATIONS`)

**Interfaces:**
- Produces: in the `codeshares` statement, `at_last` moves, unchanged, before `groups`, and `groups`' last line becomes `            FROM r WHERE group_key IN (SELECT group_key FROM at_last) GROUP BY group_key`. Nothing else in the statement changes.

- [ ] **Step 1: Write the test** `test_codeshare_group_holds_partners_last_seen_elsewhere`:
  - boards at `at(6)`, `at(6, 15)` and `at(6, 30)`, each with EY 607 and LY 9614 on counters 12-21; W4 6406 on counters 12-21 at `at(6, 15)` only;
  - EY 607 and LY 9614 have `codeshare_size` 2 and one `codeshare_group_id`, and their operator is EY 607, a guess;
  - W4 6406 has `codeshare_size` 3, operator EY 607, a guess, and a `codeshare_group_id` other than the pair's, equal to `hashlib.md5("|".join([ey, w4, ly]).encode()).hexdigest()` over their `flight_id`s in R6's order (607, 6406, 9614);
  - `SELECT count(*) FROM codeshares` is 3.
- [ ] **Step 2: Run it on the unchanged code.** Expected: PASS. The filter is meant to change no result. The entries in Step 5 prove the test bites.
- [ ] **Step 3: Implement** the filter.
- [ ] **Step 4: Run; pass.** `tests/test_model.py`, `tests/test_model_receipts.py`, `tests/test_model_tagged.py`; then the full suite.
- [ ] **Step 5: Mutation entries**, in `MODEL_MUTATIONS`:
  - "R5 codeshare filter on the flight's own row": `FROM r WHERE group_key IN (SELECT group_key FROM at_last) GROUP BY group_key` → `FROM r WHERE (flight_id || group_key) IN (SELECT flight_id || group_key FROM at_last) GROUP BY group_key`. W4 6406's group loses its partners;
  - "R5 codeshare filter on the first appearance": the same text → `FROM r WHERE group_key IN (SELECT arg_min(group_key, snap_rn) FROM r GROUP BY flight_id) GROUP BY group_key`. EY 607 and LY 9614 drop out of `codeshares`.

  Run the uniqueness check, then the entries of `src/model/rules.py`.
- [ ] **Step 6: Commit** (`q5: codeshares lists only the groups a flight ends in (change 1)`).
- [ ] **Step 7: Review (Opus).**

### Task 4: Change 2, part 1: the per-board work staged per date folder

Implementer: integration (Opus). Design: `docs/lighter-build.md`, "The design", 2 (:83-90). In this task every build stages every date folder; Task 5 adds reuse.

**Files:**
- Create: `src/model/stage.py`, `tests/test_model_stage.py`
- Modify: `src/model/rules.py`, `src/model/build.py`, `tests/model_helpers.py` (`build`'s new side), `tests/test_model.py` (`test_many_snapshot_files_build_within_a_small_memory_limit`), `scripts/mutation_check.py` (`STAGE`, `TAGGED`, `TAGGED_STAGE`, the entries, `TIME_LIMIT`'s comment)

**Interfaces:**
- Produces, in `src/model/rules.py`. The module docstring's table list follows: `raw_rows` is one date folder's files, and the new tables are named.
  - `per_board(con) -> None`, docstring: "R1 and R2 on every board in raw_rows, trusted or not". From `raw_rows` it makes `day_counts` and `day_rows`. `day_counts` is exactly:

    ```python
        con.execute(f"""
            CREATE OR REPLACE TABLE day_counts AS
            WITH s AS (SELECT snapshot_id, min(fetched_at) AS fetched_at,
                              count(*) < max(declared_total) AS incomplete,
                              count(DISTINCT page) AS pages, count(*) AS rows_raw,
                              count(*) - count(DISTINCT ({fields})) AS duplicate_rows
                       FROM raw_rows GROUP BY snapshot_id),
                 conflicts AS (SELECT snapshot_id, count(*) - count(DISTINCT ({key})) AS key_conflicts
                               FROM (SELECT DISTINCT snapshot_id, {fields} FROM raw_rows) GROUP BY snapshot_id)
            SELECT * FROM s JOIN conflicts USING (snapshot_id)
        """)
    ```

    (In `rules.py` the SQL sits 8 spaces in, as every statement there does, so the `incomplete` line starts with 26 spaces, as it does today.) `day_rows` is today's `rows` statement (`rules.py:241-270`) with two edits only: it creates `day_rows`, and `typed` loses its two-line `WHERE snapshot_id IN (SELECT snapshot_id FROM snapshot_runs …)` filter (:252-253). Every other line stays byte for byte.
  - `convert_times_and_dedupe(con) -> None` reads `staged_counts`, `staged_rows` and `receipts`, and no longer `raw_rows`:
    - `snapshot_files`' first part becomes

      ```sql
              WITH s AS (SELECT snapshot_id, fetched_at, right(snapshot_id, 12) AS sha, incomplete,
                                rows_raw AS file_rows, pages AS file_pages
                         FROM staged_counts),
      ```
    - `rows` becomes a view:

      ```sql
              CREATE OR REPLACE VIEW rows AS
              SELECT * FROM staged_rows
              WHERE snapshot_id IN (SELECT snapshot_id FROM snapshot_runs
                                    WHERE NOT repeat AND NOT incomplete AND receipt IN ('receipted', 'legacy'))
      ```
    - in `snapshots`, `per_file` becomes `SELECT snapshot_id, fetched_at, pages, rows_raw, duplicate_rows FROM staged_counts`, and `conflicts` becomes `SELECT snapshot_id, key_conflicts FROM staged_counts`. `kept`, `base`, `sightings`, `confirmed` and the final select stay as they are;
    - the locals `fields` and `key` go, unused;
    - the docstring says where the trusted snapshots are now picked: here, over the whole history, from the staged boards.
  - `build_tables(con) -> dict[str, int]` replaces `build_all`. It runs `convert_times_and_dedupe`, `link_retimes`, `build_observations` and `build_flights` on a connection that holds `staged_rows`, `staged_counts` and `receipts`, and returns the counts of `snapshots`, `observations`, `flights` and `receipts`.
- Produces, in `src/model/stage.py` (docstring: the layout under "What this plan decided", and that staging is per date folder because a snapshot's files never leave theirs):
  - `@dataclass(frozen=True) class Stage`: `raw_days: tuple[str, ...]` and `receipt_days: tuple[str, ...]` (the `date=…` folder names read, sorted), and `staged: tuple[str, ...]` (`"raw/date=…"` then `"receipts/date=…"` entries staged by this call, in date order);
  - `stage(con, raw_dir: Path, receipts_dir: Path | None, stage_dir: Path) -> Stage`:
    - the days of `raw_dir` are its `date=*` child folders holding at least one `*.json.gz`. Any `*.json.gz` under `raw_dir` outside them raises `ValueError(f"{n} files under {raw_dir} have a path that is not date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-NNN.json.gz: {names[:10]}")`. No day at all raises `ValueError(f"no snapshot files under {raw_dir}")`;
    - for each day: `rules.load_raw(con, str(day / "**" / "*.json.gz"))`, `rules.per_board(con)`, then `day_rows` to `<stage>/raw/<day>/rows.parquet` and `day_counts` to `counts.parquet`;
    - the days of `receipts_dir`, when it is a folder, are found the same way with `*.json`; a stray file raises `ValueError(f"{n} receipt files under {receipts_dir} are outside its date=YYYY-MM-DD folders: {names[:10]}")`. For each: `rules.load_receipts(con, str(day / "**" / "*.json"))`, then `receipts` to `<stage>/receipts/<day>/receipts.parquet`;
    - finally it drops `raw_rows`, `day_rows` and `day_counts`;
  - `open_stage(con, stage_dir: Path, st: Stage) -> None`: the view `staged_rows` over `read_parquet([...])` of the days' `rows.parquet`; the table `staged_counts` from their `counts.parquet`; the table `receipts` from the receipt days' files, or `rules.load_receipts(con, None)` when there are none. Every path's quotes are doubled;
  - `_copy(con, query: str, path: Path) -> None`: `COPY ({query}) TO '<temp>' (FORMAT PARQUET, COMPRESSION ZSTD)`, the temp name in `path`'s folder carrying the process id, then `os.replace`. The tests patch it.
- Produces, in `src/model/build.py`:
  - `run(con, raw_dir: Path, receipts_dir: Path | None, stage_dir: Path) -> dict[str, int]`: `stage.stage`, `stage.open_stage`, `rules.build_tables`;
  - `build(raw_dir, out_dir, receipts_dir=None) -> dict[str, int]`: `run` on `rules.connect()` and a `tempfile.TemporaryDirectory`, then the five `COPY`s as today, with the connection closed before the stage is removed.
- `tests/model_helpers.py`: `build`'s new side becomes `con = rules.connect(); model.build.run(con, raw, receipts, <a new tempfile.mkdtemp under raw.parent>)`.
- `tests/test_model.py`: the memory test runs `model.build.run(con, raw, None, raw.parent / "stage")` on its `rules.connect()` with the same two `SET`s. Its 20 snapshots stay in one date folder, so the 256 MB break still reads 20 files at once.

The five existing entries whose lines move, text and indentation unchanged:
- "R2 duplicates kept" (`        WHERE key_rank = 1\n`) and "R2 conflict keeps highest id" move into `day_rows`;
- "R2 incomplete snapshots kept" moves into `day_counts`;
- "R2 repeated snapshots kept" and "pending and orphan snapshots kept" move into the `rows` view.

Three more now run once per date folder, their text unchanged: "R2 missing total not refused", "unknown receipt version accepted" and "reader buffer 256 MB". If the last comes back MISSED, the memory test's snapshots go up, all in one date folder, until it is caught again; that goes in "Deviations".

- [ ] **Step 1: Write the failing tests** (`tests/test_model_stage.py`, each through `model.build.build` or `stage.stage` on a `rules.connect()`):
  - `test_each_date_folder_is_staged_to_its_own_files`: two days with receipts give `<stage>/raw/date=…/rows.parquet` and `counts.parquet` for each, and `<stage>/receipts/date=…/receipts.parquet`. `Stage.raw_days` names both days, and so does `Stage.staged`.
  - `test_a_staged_day_holds_every_board_trusted_or_not`: a day with a pending board and an incomplete one. Both are in `counts.parquet` (the incomplete one with `incomplete` true) and their rows are in `rows.parquet`; the model's `rows` holds neither.
  - `test_a_snapshot_file_outside_the_date_folders_stops_the_build`: `raw/stray.json.gz`, and `raw/copy/date=2026-10-27/060000Z-aaaaaaaaaaaa/page-000.json.gz`. Each raises `ValueError` matching "path".
  - `test_a_receipt_outside_the_date_folders_stops_the_build`: `receipts/stray.json` raises `ValueError` matching "outside".
  - `test_an_empty_date_folder_is_skipped` (Review Focus 3): an empty `date=2026-10-26/` and a `date=2026-10-25/` holding only `.DS_Store` beside a real day. The build succeeds, and `Stage.raw_days` names the real day only.
  - `test_paths_with_an_apostrophe_and_a_space_build` (Review Focus 4): the archive, stage and model under `tmp_path / "o'hare archive"`; the flights are built.
  - `test_without_receipts_the_receipts_table_is_empty`: receipts `None`, and a folder that does not exist. Each gives an empty `receipts` with today's columns and types.
  - `test_without_snapshot_files_the_build_stops`: `ValueError` matching "no snapshot files".
- [ ] **Step 2: Run; fail.** `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/test_model_stage.py`.
- [ ] **Step 3: Implement.** The existing model tests and `tests/test_model_tagged.py` pass before and after, by design.
- [ ] **Step 4: Run; pass.** `tests/test_model.py`, `tests/test_model_receipts.py`, `tests/test_model_stage.py`, `tests/test_model_tagged.py`, `tests/test_record_cut.py`; then the full suite. Time `tests/test_model.py` with `tests/test_model_receipts.py` (7.0 s at 44bedea), and put the new figure in `TIME_LIMIT`'s comment.
- [ ] **Step 5: Mutation entries**, with `BOUNDARY = "tests/test_model_tagged.py::test_boundary_cases_match"`, `TAGGED = ("src/model/rules.py", [BOUNDARY])`, `TAGGED_STAGE = ("src/model/stage.py", [BOUNDARY])`, `STAGE = ("src/model/stage.py", ["tests/test_model_stage.py"])`:
  - "tagged: a dropped snapshot's rows let into rows" (`TAGGED`): `        SELECT * FROM staged_rows\n        WHERE snapshot_id IN` → `        SELECT * FROM staged_rows\n        WHERE true OR snapshot_id IN`. Caught by the `repeated-store`, `superseded`, `incomplete` and `pending-tail` cases;
  - "tagged: a snapshot's raw count taken after duplicates are removed" (`TAGGED`): `count(DISTINCT page) AS pages, count(*) AS rows_raw,` → `count(DISTINCT page) AS pages, count(DISTINCT ({fields})) AS rows_raw,`. Caught by the `duplicates` case;
  - "tagged: a receipts day skipped" (`TAGGED_STAGE`): one receipts day left out of staging. Caught by the `sighting` case;
  - "stage: snapshot files outside the date folders ignored" → `test_a_snapshot_file_outside_the_date_folders_stops_the_build`;
  - "stage: receipts outside the date folders ignored" → `test_a_receipt_outside_the_date_folders_stops_the_build`;
  - "stage: an empty date folder read" → `test_an_empty_date_folder_is_skipped`;
  - "stage: a quote in a path not doubled" → `test_paths_with_an_apostrophe_and_a_space_build`.

  Run the uniqueness check: every entry found once, the five moved ones included. Then the entries of `src/model/rules.py`, `src/model/stage.py` and `src/model/build.py`.
- [ ] **Step 6: Commit** (`q5: each date folder's per-board work staged, the whole-history rules reading the stage (change 2, part 1)`).
- [ ] **Step 7: Review (Opus).** The reviewer reads `git diff record-v1 -- src/model/rules.py` against this task's Interfaces line by line.

### Task 5: Change 2, part 2: the marker, the fingerprint and reuse

Implementer: integration (Opus). Design: `docs/lighter-build.md:92` and "Re-run, crash, late files, rule change" (:126-133).

**Files:**
- Modify: `src/model/stage.py`, `src/model/build.py` (`run`, `build`), `tests/test_model_stage.py`, `scripts/mutation_check.py`

**Interfaces:**
- Produces, in `src/model/stage.py`:
  - `fingerprint(sources: Iterable[Path] | None = None, duckdb_version: str = duckdb.__version__) -> str`: SHA-256 hex over each source in name order (its name, a NUL, its bytes, a NUL), then the version. The default sources are `sorted(Path(__file__).resolve().parent.glob("*.py"))`;
  - `listing(day: Path, pattern: str) -> list[list]`: `[[relative POSIX path, size in bytes], …]` of every file under `day` matching `pattern`, recursively, sorted;
  - `stage(con, raw_dir, receipts_dir, stage_dir, restage: bool = False) -> Stage`. A day is skipped when `restage` is false and it is current. Current means: its `marker.json` reads as JSON equal to `{"fingerprint": fingerprint(), "files": listing(...)}`, and its staged files exist. Any `OSError` or `ValueError` while reading means not current. A day that is staged: its marker is deleted first, its files are written (`_copy`), and then its marker, under a temporary name and renamed, last. `Stage.raw_days` and `Stage.receipt_days` come from the source folders' listing, never from the stage's folders, so a day whose source folder is gone is not read.
- Produces, in `src/model/build.py`: `run(con, raw_dir, receipts_dir, stage_dir, restage: bool = False)` and `build(raw_dir, out_dir, receipts_dir=None, *, stage_dir: Path | None = None, restage: bool = False)`. With `stage_dir` given, it is kept; with none, a temporary one as before.

- [ ] **Step 1: Write the failing tests.** In each, "equals a fresh build" means `compare_tables` and `compare_load` (through `model_helpers.check_script()`) give `[]` against `model.build.build` of the same archive with no stage:
  - `test_a_second_build_on_the_same_files_stages_nothing`: `Stage.staged == ()` on the second call.
  - `test_reuse_equals_a_fresh_build`. Days 30 October to 2 November with receipts are staged. Then:
    - a day is added (3 November);
    - a board and its receipt are added to the last day staged (2 November);
    - a board and its receipt are added to an old day (30 October).

    `stage()` gives `staged == ("raw/date=2026-10-30", "raw/date=2026-11-02", "raw/date=2026-11-03", "receipts/date=2026-10-30", "receipts/date=2026-11-02", "receipts/date=2026-11-03")`, so 31 October and 1 November are reused. A build on the same stage equals a fresh build.
  - `test_a_late_receipt_restages_only_its_receipts_day`: an unchanged receipt added to an old day gives `staged == ("receipts/date=…",)` only, and the build equals a fresh one.
  - `test_a_late_second_page_is_staged_again`: legacy days 26 and 27 October, no receipts. A two-page board on the 27th with its second page missing is staged incomplete. When the page arrives, the day is staged again, the board is complete in `snapshot_runs`, and the build equals a fresh one.
  - `test_a_file_whose_size_changed_is_staged_again`: a page rewritten under the same name with one more row. Its day is staged again, and the build equals a fresh one.
  - `test_a_staged_day_whose_folder_is_gone_is_ignored`: legacy days 26 and 27 are staged, and `raw/date=2026-10-26` is removed. `Stage.raw_days == ("date=2026-10-27",)`, and the build equals a fresh build of what is left.
  - `test_a_day_whose_marker_was_not_written_is_staged_again`, parametrized over a fresh stage and a `restage=True` run on a current one, and over `ValueError` and `KeyboardInterrupt` (Review Focus 1). `stage._copy` is patched to raise on the first day's `counts.parquet`, and `stage()` raises that. The next `stage()` lists that day in `staged`, and the build equals a fresh one.
  - `test_a_changed_fingerprint_stages_every_day_again`: `stage.fingerprint` patched to return `"other"` stages every day.
  - `test_the_fingerprint_follows_the_model_source_and_duckdb`:
    - copies of two sources: one byte changed in one copy changes the fingerprint;
    - another `duckdb_version` changes it;
    - the default sources are every `src/model/*.py`, `rules.py`, `stage.py` and `build.py` among them.
  - `test_a_damaged_stage_is_staged_again` (Review Focus 2), parametrized: an empty `marker.json`, one that is not JSON, one without `"files"`, and a current marker whose `rows.parquet` was deleted. Each day is staged again with no error.
  - `test_restage_stages_every_day`: `restage=True` on a current stage stages every day.
- [ ] **Step 2: Run; fail.** `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/test_model_stage.py`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** The model test files and `tests/test_model_tagged.py`; then the full suite.
- [ ] **Step 5: Mutation entries** (`STAGE`):
  - "stage: a changed folder's stage reused" (the listing not compared) → `test_reuse_equals_a_fresh_build`;
  - "stage: file sizes left out of the listing" → `test_a_file_whose_size_changed_is_staged_again`;
  - "stage: a staged day read after its folder is gone" (the days read from the stage's own folders) → `test_a_staged_day_whose_folder_is_gone_is_ignored`;
  - "stage: marker written first" → `test_a_day_whose_marker_was_not_written_is_staged_again`;
  - "stage: old marker kept while staging again" → the same test, its `restage=True` cases;
  - "stage: fingerprint not compared" → `test_a_changed_fingerprint_stages_every_day_again`;
  - "stage: fingerprint without the DuckDB version" and "stage: fingerprint of rules.py only" → `test_the_fingerprint_follows_the_model_source_and_duckdb`;
  - "stage: a damaged marker stops the build" (the `except` narrowed) and "stage: staged files not checked" → `test_a_damaged_stage_is_staged_again`;
  - "stage: restage ignored" → `test_restage_stages_every_day`.

  Run the entries of `src/model/stage.py` and `src/model/build.py`.
- [ ] **Step 6: Commit** (`q5: a staged day is reused only while its marker matches its files, the model's source and DuckDB (change 2, part 2)`).
- [ ] **Step 7: Review (Opus).**

### Task 6: Change 3 and the output folder

Implementer: integration (Opus). Design: `docs/lighter-build.md`, "The design", 3 (:94), and "For the owner", question 4 (:222).

**Files:**
- Modify: `src/model/build.py` (its first line names the new command), `tests/model_helpers.py`, `tests/test_model.py` (the memory test), `scripts/mutation_check.py` (`BUILD`)
- Create: `tests/test_model_build.py`

**Interfaces:**
- Produces, in `src/model/build.py`:
  - `MEMORY_LIMIT = "1GB"`, `THREADS = 2`;
  - `connect(temp_dir: Path, memory_limit: str = MEMORY_LIMIT, threads: int = THREADS) -> duckdb.DuckDBPyConnection`: `rules.connect()`, then `SET memory_limit`, `SET threads` and `SET temp_directory`, the path's quotes doubled;
  - `write_model(con, out_dir: Path) -> None`:
    - the five tables are written by `_copy_out(con, table: str, path: Path)` (`COPY {table} TO '<path>' (FORMAT PARQUET)`, as at the tag) into `<out>.building`;
    - then `<out>` moves to `<out>.old`, `<out>.building` moves to `<out>`, and `<out>.old` is removed;
    - leftover `<out>.building` and `<out>.old` folders are removed first;
    - a failure of any kind while writing removes `<out>.building` and re-raises;
    - `ValueError(f"{folder} holds files that are not a model's: {names}; refusing to replace it")` stops it, before any work, when `<out>`, `<out>.building` or `<out>.old` holds anything but `<table>.parquet` files of `TABLES`;
  - `build(raw_dir, out_dir, receipts_dir=None, *, stage_dir=None, restage=False, memory_limit=MEMORY_LIMIT, threads=THREADS, temp_dir=None) -> dict[str, int]`. A `temp_dir` of `None` is a `tempfile.TemporaryDirectory(prefix="model-build-")`; a `stage_dir` of `None` is one with `prefix="model-stage-"`. Both are removed whatever happens. The connection is closed before they are;
  - `main(argv)`, with the options under "What this plan decided". `--stage` defaults to `args.raw.parent / "stage"`. It calls `build` with keyword arguments.
- `tests/model_helpers.py`: `build`'s new side uses `model.build.connect(<a new mkdtemp under raw.parent>)`. The memory test uses `model.build.connect(raw.parent / "duckdb-tmp", memory_limit="1GB", threads=2)`.

- [ ] **Step 1: Write the failing tests** (`tests/test_model_build.py`):
  - `test_the_connection_takes_the_limits_given`: `connect(tmp_path / "o'hare spill", "512MB", 3)` reads back `('488.2 MiB', 3, str(tmp_path / "o'hare spill"))` from `current_setting`.
  - `test_the_defaults_are_1_gb_and_2_threads`: `connect(tmp_path)` reads back `'953.6 MiB'` and `2`.
  - `test_main_passes_its_defaults`: `build.build` monkeypatched to record its arguments. `main(["--raw", raw, "--out", out])` passes `memory_limit="1GB"`, `threads=2`, `temp_dir=None`, `stage_dir=raw.parent / "stage"`, `restage=False` and the receipts beside `--raw`.
  - `test_main_passes_every_option`: each option reaches `build`.
  - `test_no_temp_file_under_the_working_directory`:
    - `monkeypatch.chdir(tmp_path / "cwd")`, and `tempfile.tempdir` monkeypatched to `tmp_path / "systmp"`;
    - `build.connect` wrapped to record `current_setting('temp_directory')`;
    - after `build.build(raw, out, receipts)`, the recorded folder was under `systmp`, `systmp` is empty, and `cwd` is empty.
  - `test_a_failed_build_leaves_the_last_model_as_it_was`, parametrized over `ValueError` and `KeyboardInterrupt` (Review Focus 1): a first build into `out`, then a second with `_copy_out` patched to raise on the third table. It raises that; `out`'s files keep their bytes; there is no `out.building` and no `out.old`.
  - `test_a_refused_archive_leaves_the_last_model_as_it_was`: a second build on the same `out`, from an archive whose receipt disagrees with its files, raises `ValueError`, and `out` is unchanged.
  - `test_a_new_model_replaces_the_old_one_whole`: the second build's five files, and nothing else, stand in `out`.
  - `test_leftovers_of_a_killed_build_are_cleared`: `out.building` and `out.old`, each holding a table file, are gone after a build.
  - `test_a_folder_that_is_not_a_model_is_never_replaced` (Review Focus 5), parametrized over `out` holding `notes.txt`, and over `out.old` holding one. `ValueError`, and the file is still there.
- [ ] **Step 2: Run; fail.** `PYTHONPATH=src .venv/bin/pytest -o addopts="" -q tests/test_model_build.py`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`BUILD = ("src/model/build.py", ["tests/test_model_build.py"])`):
  - "build: memory limit not set", "build: threads not set" and "build: temp directory not set" → `test_the_connection_takes_the_limits_given`;
  - "build: default memory limit 2GB" → `test_the_defaults_are_1_gb_and_2_threads`;
  - "build: --temp-dir ignored" and "build: --restage ignored" → `test_main_passes_every_option`;
  - "build: temporary stage kept" → `test_no_temp_file_under_the_working_directory`;
  - "build: model written in place" (`<out>.building` replaced by `<out>`) and "build: half-written model kept after a failure" → `test_a_failed_build_leaves_the_last_model_as_it_was`;
  - "build: a folder that is not a model replaced" → `test_a_folder_that_is_not_a_model_is_never_replaced`.

  Run the entries of `src/model/build.py`.
- [ ] **Step 6: Commit** (`q5: the build's memory limit, threads and temp folder, its options, and a model folder written whole or not at all (change 3)`).
- [ ] **Step 7: Review (Opus).**

### Task 7: The local check's runner

Implementer: integration (Opus). Design: `docs/lighter-build.md:182`.

**Files:**
- Modify: `scripts/tagged_check.py` (`main`, `tag_rules`, the child mode), `tests/test_tagged_check.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `model_helpers.cut_archive`, imported with `tests/` put on `sys.path` and a comment saying why (one cut rule for the tests and the script); Task 6's command line.
- Produces, in `scripts/tagged_check.py`:
  - `tag_rules() -> bytes | None`: `git -C ROOT show record-v1:src/model/rules.py`, or `None` when git or the tag is missing;
  - the child mode `tagged_check.py tagged-build --raw R --receipts X --out O --temp-dir T`, which runs `build_tagged` with `model.rules.KNOWN_ORPHANS`;
  - `main(argv) -> int` for `PYTHONPATH=src .venv/bin/python scripts/tagged_check.py --work DIR [--raw data/raw] [--receipts data/receipts] [--fractions 0.25 0.5 0.75 1]`:
    1. Exit 2 when `--work` exists and is not empty, or when `tagged_rules()` raises, or when `tag_rules()` is not `None` and differs from the fixture's bytes. Print the fixture's line: its path, its SHA-256, and "equal to record-v1's src/model/rules.py", or "tag record-v1 not in this clone: checked against the pinned SHA-256 only".
    2. Print the archive line: snapshots, receipts, the last board's path time.
    3. For each fraction, labelled `quarter`, `half`, `three quarters` and `whole` (any other fraction by its value):
       - the cut, copied into `<work>/<label>/archive` by `cut_archive`; the whole archive is read where it is;
       - the tagged build as a child process (`cwd=<work>/<label>`, `PYTHONPATH` with `ROOT/src`);
       - the new build as `python -m model.build --raw … --receipts … --out <work>/<label>/new --stage <work>/<label>/stage --temp-dir <work>/<label>/new-tmp`;
       - each build's wall time;
       - `compare_tables`, `compare_load` and `compare_progress` (into `<work>/<label>/record`).
    4. Print per archive: its label, kept and total snapshots, the moment, both times, each table's row count on both sides, then "identical: columns, rows, load(), progress.json" or each difference line. A child that exits non-zero is a difference, printed with the last line of its error output.
    5. Exit 0 when every archive is identical, 1 otherwise.

- [ ] **Step 1: Write the failing tests:**
  - `test_main_finds_no_difference_on_a_small_archive`: two days, 8 boards with receipts. Exit 0, and the output names `quarter`, `half`, `three quarters` and `whole`, each with "identical".
  - `test_main_exits_1_on_a_difference`: `compare_tables` patched to return one line. Exit 1, and the line is printed.
  - `test_main_refuses_a_work_folder_in_use`: exit 2, and nothing is added to the folder.
  - `test_main_stops_when_the_tag_and_the_fixture_differ`: `tag_rules` patched to return other bytes; exit 2.
- [ ] **Step 2: Run; fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries** (`TAGGED_CHECK`):
  - "tagged check: exit 0 on a difference" → `test_main_exits_1_on_a_difference`;
  - "tagged check: a work folder in use reused" → `test_main_refuses_a_work_folder_in_use`;
  - "tagged check: tag and fixture not compared" → `test_main_stops_when_the_tag_and_the_fixture_differ`.

  Run the entries of `scripts/tagged_check.py`.
- [ ] **Step 6: Commit** (`q5: scripts/tagged_check.py builds an archive and its cuts with the tagged and the new code and prints the four checks`).
- [ ] **Step 7: Review (Opus).**

### Task 8: The comparison on the real archive, and the new build's time (main session)

Nothing else runs meanwhile: no implementer, no mutation check, no other build. This is one build at a time on the 8 GB Mac.

- [ ] **Step 1:** Optionally `sh scripts/sync.sh` (it checks the identity). Name the archive in "Deviations": snapshots, receipts, the last board.
- [ ] **Step 2:** `perl -e 'alarm 3600; exec @ARGV' env PYTHONPATH=src .venv/bin/python scripts/tagged_check.py --work <scratchpad>/tagged-check-<date>`, then `echo $?`. Expected: 0, and "identical" for the quarter, the half, three quarters and the whole archive. The four tagged builds take about 15 minutes on today's archive (UNVERIFIED: the whole archive took 450 s, a quarter 20 s, a half 44 s; three quarters was not measured). If any line differs, or a build fails, stop and tell the owner with the printed lines. Nothing in `src/model/` is changed to agree with the tagged output without the owner.
- [ ] **Step 3:** The new build alone, twice, on the whole archive: `/usr/bin/time -l env PYTHONPATH=src .venv/bin/python -m model.build --raw data/raw --out <scratchpad>/model-q5 --stage <scratchpad>/stage-q5`. The first run stages every day; the second reuses them. Record each run's real time, peak memory footprint and maximum resident set size.
- [ ] **Step 4:** Write a section "## The comparison against the tagged code" into `docs/lighter-build.md`, before "## All runs (2026-11-18)": the date, the commit, both commands, the archive, each archive's line as printed, and Step 3's figures. Commit it (`q5: the comparison against the tagged code on the whole archive and its cuts, and the new build's time`).
- [ ] **Step 5:** If any later commit changes `src/model/`, Steps 2 to 4 run again and the section is replaced.

### Task 9: Whole-branch review (Fable)

- [ ] **Step 1:** A fresh Fable reviewer reads `git diff main...HEAD` against `docs/lighter-build.md`, `docs/flight-lookup.md` "The record" condition 2, and this plan: the code, the tests, the mutation entries and the plan's Deviations. It also reads `git diff record-v1 -- src/model` on its own, as the record's reader would.
- [ ] **Step 2:** Each finding is checked against its source. Fixes go to an Opus implementer, with a scoped Opus re-review. Then the full suite and the touched files' mutation entries. A fix in `src/model/` runs Task 8 again.

### Task 10: Documents

Implementer: transcription (Sonnet). Every claim is checked against the code as built and Task 8's section.

**Files:**
- Modify:
  - `docs/data-model.md`:
    - line 3, the grade line, becomes: "Grade: production-lean. A deterministic rebuild with tested rules: every rule runs over the whole history on every build, and only each date folder's per-board work is kept between builds, staged once ([lighter-build.md](lighter-build.md)). Runnable on a laptop now and in a small Lambda later.";
    - line 50 follows `docs/lighter-build.md`, "The nightly function (b)";
    - "Nightly run" step 1 (line 52) is replaced by the build as it stands, pointing at `lighter-build.md` for the staging, the limits and "Why not a trailing window"; step 2's temp-disk figure follows the same section;
    - "How to run" gives the command with `data/stage/`, its options and Task 8's first and later times;
    - "Tests" gets one sentence: the staging tests, and the comparison with the tagged rules in CI.
  - `docs/README.md`: after the `will-it-fly-plan.md` line, a line for `lighter-build.md` and one for this plan.
  - `docs/lighter-build.md`: the status line's "a design, nothing built" becomes built, to this plan, with the comparison under its new section.
  - `docs/flight-lookup.md`: Question 1's sentence, only if the owner says yes.
- The counts in `README.md:27`, `README.md:56` and `docs/operations.md:97` come from Task 11.
- [ ] **Step 1: Update the documents.**
- [ ] **Step 2: Commit** (`q5: documents follow the build`).
- [ ] **Step 3: Review (Opus).**

### Task 11: Final verification (main session), then the push and the merge

- [ ] **Step 1:** `PYTHONPATH=src .venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95`. Expected: every test passes and coverage is 95% or more; record the count.
- [ ] **Step 2:** `.venv/bin/python scripts/mutation_check.py`, alone. Expected: "Every mutation was caught."; record the count and the time.
- [ ] **Step 3:** `.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`, as CI runs it. Expected: no output.
- [ ] **Step 4:** Write Steps 1 and 2's counts into `README.md:27`, `README.md:56` and `docs/operations.md:97`, and Step 2's time into `docs/operations.md:97`. Commit (`q5: test and mutation counts`).
- [ ] **Step 5:** The push and the merge, each run by the main session on the owner's go, after `gh auth status` shows the project's own GitHub account.
- [ ] **Step 6:** After the merge, the first everyday build: `PYTHONPATH=src .venv/bin/python -m model.build --raw data/raw --out data/model`, which creates `data/stage/`.

## Deviations

- **2026-11-18, before Task 1 (a pre-flight read of this plan against the code at f039faf).**
  - "Task 7 adds `cut_archive`" (Task 1, Interfaces) is wrong: `cut_archive` is in `tests/model_helpers.py` since 2c5459d. Task 7 imports it; nothing adds it.
  - "For `raw/`, the tagged build refuses a stray file too" ("What this plan decided", files outside the `date=` folders) holds for a file such as `raw/stray.json.gz` only. The tagged `load_raw` matches `_SNAPSHOT_PATH` anywhere in the path (`regexp_extract`, not anchored at the start), so it reads a copy nested as `raw/copy/date=…/HHMMSSZ-<sha12>/page-NNN.json.gz`, which the new build refuses. The refusal stands, for the reason given there: staging by date folder cannot place such a file. On the archive as synced to 2026-11-17 20:32:45Z, no snapshot file and no receipt lies outside `raw/date=…/HHMMSSZ-<sha12>/` and `receipts/date=…/`, so no result there changes; Task 8 checks it again.
  - An archive with no snapshot files: the new build raises `ValueError("no snapshot files under …")` (Task 4), where the tagged `model.build.build` stops inside DuckDB on a pattern that matches no file, with DuckDB's own error class. "The same kind of error" does not hold for that one input through the function. The command line refuses it before either build, with exit 2, as at the tag (`src/model/build.py`, `main`), and Task 6's `main` keeps that check. No caller in the repository catches DuckDB's error there.
  - "Every line moves with its text unchanged" ("How R1 and R2's SQL is shared") holds for `day_rows` and the `rows` view. `day_counts` is the statement written out in Task 4, which reshapes the lines it takes from `snapshot_files` and `snapshots`; only its `incomplete` line keeps its text and indentation. No mutation entry's text is affected.
- **2026-11-18, Task 4.**
  - Staged Parquet is read with `hive_partitioning = false`. Without it, DuckDB read the `date=…` folder of each staged path as a column, and `receipts` gained a `date` column. The comparison with the tagged build caught it on the first run; the fix is in `stage.py` only, and the entry "stage: the date in a staged path read as a column" pins it.
  - The stage refuses every `*.json.gz` under `raw/` whose path relative to it is not exactly `date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-NNN.json.gz`, with the existing message, before any day is staged. A snapshot's id takes its date from the path, so with this layout no snapshot can span two date folders, which per-folder staging relies on. The task's review found the case: a day folder copied into another (`raw/date=2026-10-28/date=2026-10-27/…`) put one snapshot in two folders, and the new build gave other rows where the tagged build built one snapshot (legacy) or refused the archive (receipted). The tagged build accepts any path whose last three parts fit the layout; the new build refuses anything before `date=`. On the archive synced 2026-11-18 (boards to 18:02:45Z), no file is off that layout, and no folder is a symbolic link.
  - Receipts outside the date folders are refused before any raw day is staged, so both refusals come before any work.
  - Because off-layout paths no longer reach `load_raw`'s own path check, a well-formed path with an impossible time (hour 25) now tests it: `test_a_snapshot_path_with_an_impossible_time_stops_the_build`, with the entry renamed to "stage: a snapshot path with an impossible time read".
  - "The same kind of error" holds for an archive with one fault. Days are read one at a time, and stray receipts are checked first, so an archive with two faults in different places may be refused with another class than the tagged build's.
  - The counts and first-ten lists in `load_raw`'s and `load_receipts`' refusal messages now cover one date folder, not the archive.
  - `model.build.build` stages into a `tempfile.TemporaryDirectory(prefix="model-stage-")` (the prefix from Task 6), removed after the build; tests that call it stage in the system's temp folder, not under `tmp_path`.
- **2026-11-18, Task 2.** One test more than listed: `test_a_refusal_of_another_kind_is_caught`, for the comparison's branch where both builds refuse with different exception classes, which no listed test reached.
- **2026-11-18, Task 6.**
  - The refusal of a folder that is not a model's runs at the start of `build()`, before any staging, as well as in `write_model`, so `--out data` fails at once rather than after the stage.
  - `main` keeps its check that `--raw` holds a snapshot file (exit 2 before any build).
  - Four entries more than listed, among them "build: last model overwritten while the new one is written": the listed "model written in place" is caught only because the first build of its test has no model yet, so only the added entry reaches the check that the last model keeps its bytes.
- **2026-11-18, Task 7.**
  - `compare_progress` reports a `progress.json` missing on either side as its own line, so two runs that both write nothing never compare equal.
  - The tagged child build writes into `<work>/<label>/tagged`, with DuckDB's temp folder `<work>/<label>/tagged-tmp`; each build's output goes to a log beside it.
  - Each archive's line gives the snapshot folders the cut keeps and those copied.
  - The output names the commit compared and whether `src/model`, the script and the fixture hold uncommitted changes.
  - A fraction given twice, and a `--work` inside `--raw` or `--receipts`, are refused with exit 2 before anything is written.
  - The task's review found that no test proved the runner runs every check on two different folders and counts every archive in the exit code: four one-line breaks passed every test. `test_main_runs_every_check_on_every_archive` and four entries close it.
- **2026-11-18, after Task 7: points from the task reviews, fixed before Task 8** (any later change to `src/model/` would run Task 8 again).
  - "Leftover `<out>.building` and `<out>.old` folders are removed first" (Task 6) has one exception. A build stopped between its two renames leaves no `<out>`, the last model in `<out>.old` and the new one in `<out>.building`. `build()` now puts `<out>.old` back as `<out>` before any work, when there is no `<out>` and `<out>.old` holds exactly the five table files. Before that, the next build deleted it first, and if that build failed too, no model was left.
  - A day staged again first loses the `*.tmp` files a stopped build left in its stage folder.
  - A stage folder that equals, lies inside or holds `--raw` or `--receipts` is refused before any work: `--stage data` would have put `marker.json` among the receipts.
  - Pins: each day-boundary case checks that it still shows its feature, so the comparison cannot pass on a case hollowed out by a helper; a test for the comparison's branch where only the tagged build refuses; a marker that is valid JSON but not an object; a staged receipts day whose source folder is gone; a folder named like a table in `<out>`.
- **2026-11-18, Task 8.** The archive compared: synced the same evening, 1,922 snapshots, 2,040 receipts, the last board 18 November 18:02:45 UTC. The comparison passed on every cut and the whole archive (`docs/lighter-build.md`, "The comparison against the tagged code"). The stage measured 56.4 MB, not the 14 MB this plan's Global Constraints take from the prototype; Task 10's documents use the measured figure.
