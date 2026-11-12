# Flight lookup (q21) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade**, quoted from the design (decision D1, approved): "production-lean, the site's grade (`docs/site-redesign.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript."

**Goal:** Build version 1 of `docs/flight-lookup.md`: one counting method for the whole site (rules C1 to C10), the front page's "From here to the scheduled time" table and total with ranges, the flight page's prepared figure, and the sign test, gate and re-test as tested code, frozen in a tagged commit before any flight they will be scored on is listed.

**Architecture:** Four frozen modules under `src/timeline/`, which with the model are the frozen rule (the design's "The record", condition 1):
- `load.py`: the model's rows, moved out of `build.py`.
- `counting.py`: the "as of" reading and rules C1 to C7.
- `rates.py`: C8 (the range, the floor and the rounding) and the sign test's lift and score.
- `record.py`: signs S1 to S4, counted flights, the gate, the test, the re-test, and the entry point `python -m timeline.record`, which writes a local report.

Task 8 ends in the commit the owner tags.

After the freeze, the page work:
- `display.py` (not frozen): C9, C10 and the front page's figures.
- `flights.py`: its lists through `counting` and `display`.
- `words.py`: the approved sentences.
- `views.py`: the table, the block and the tile's range.
- `check.py`: four new rules.
- `static/fromhere.js`: picks one prepared sentence by the visitor's clock.

`scripts/figures_check.py` checks the code against the figures file's SQL: in CI on synthetic models, and locally on the saved model.

**Tech Stack:** Python 3.13 (`.venv`), DuckDB 1.5.6 (it loads the model's Parquet files, and the figures check runs the figures file's SQL in it), pytest with coverage, Node for the two script tests (skipped where Node is missing). No new dependencies.

**Spec:** `docs/flight-lookup.md` (design v3, approved by me 2026-11-12 with D1 to D9 as recommended) and its appendix `docs/flight-lookup-figures.md`: A0 and A0b are the rules as SQL, and the code is checked against them. `docs/site-redesign.md` stands wherever the design does not change it. Executors read the design sections their task names; the design's exact words win over any paraphrase here.

## Global Constraints

- Cost: nothing new on AWS, $0 a month added; an upload stays about half a cent (design, "Cost").
- Run everything with `.venv/bin/...` and `PYTHONPATH=src`; tests with `.venv/bin/pytest` (configured in `pyproject.toml`).
- Model times (`*_at`, `*_utc`) are naive UTC: mark them UTC before converting (`.replace(tzinfo=timezone.utc)`). A test that touches Israel time runs under the `israeli_machine` fixture (`tests/test_timeline_words.py`).
- Same model, same bytes, across `PYTHONHASHSEED`. No random numbers. Neither the build nor the record reads the clock; the build time is the last sighting (`confirmed_until` of the last snapshot).
- Words: the design's "Words" are approved (D7) and used verbatim, with Appendix A (approved) and the answered parts of Question 4. Everything in `docs/site-redesign.md`, "Anti-goals" holds: no "we", "our", "us"; "I" only on `how-it-works.html` and in the built-by line; no data-collection words outside `how-it-works.html`; no phrase in `check.BANNED`.
- Claims: "listed as cancelled", never a cancellation's clock time; a rate is always "1 in N" with its range, "(between 1 in A and 1 in B)", never a percentage, and in the past tense; none of chance, odds, probability, likely, risk, forecast or predict on a reader page.
- Out of scope: any figure for one flight, a sign shown on any page, a browse view, delay figures, anything new on AWS, publishing.
- The built site holds only `.html`, `.css` and `.js` files, and its only scripts are `search.js` and `fromhere.js`. Every string from the airport's data goes through `views.d()`.
- **Frozen files**: `src/model/`, `src/timeline/load.py`, `counting.py`, `rates.py` and `record.py`. These hold the design's list ("rules C1 to C8, the four signs, the sign test with its score, the gate and the re-test", condition 1) and nothing shown only on pages. `tests/test_frozen.py` checks that they import no other `timeline` module, so that `git diff <tag> -- <frozen files>` shows every change to the rule. After Task 8, a change to a frozen file is a stop for the owner: under condition 2 it starts a new version, or it is housekeeping whose figures for closed flights are identical.
- The counting start is the owner's (Task 8). No implementer picks it.
- `scripts/mutation_check.py` edits source files in place, `src/model/rules.py` among them: run it alone, with nothing else running from the checkout, and never during a model build. New entry names start with their area: "counting: ", "rates: ", "record: ", "figures: ", "display: ", "frozen: ", "fromhere: ", and the existing ones.
- No push, no GitHub, no AWS from any task. The tag and every push are the owner's, run from the main session.
- Implementers by kind: transcription → Sonnet, integration → Opus, architecture → Fable; never Haiku. A fresh Opus reviewer reads each task's diff before the next task starts. A fresh Fable reviewer reads the whole branch before the tag (Task 8) and before the final push (Task 18). A finding is checked against its source before it is folded in.
- Documents in this repository are public: neutral voice, "I" only for what the owner decided.

## Review Focus

1. **A flight retimed after its 24-hour checkpoint, scheduled close to the gate.** A0 closes a flight by its final scheduled time (A0 `fl.closed`), while the gate orders flights by the time shown at the checkpoint (A29). So, without a guard, a run soon after the gate could see fewer flights before it than a later run. Expected, per Question 2 (answered: the guard): the gate is declared only once every flight with a 24-hour row at or before the candidate time is closed. Test in Task 7.
2. **A closed flight with one number cancelled and another still listed.** C10 labels it NO FINAL UPDATE, while C2 counts it as cancelled in the total. Expected, per Question 3 (answered): labels by C10, the total by C2, and the sum test over days without that case. Tests in Task 16, with the label in Task 9.
3. **A model too small to clear the floor anywhere**: a fresh archive, and every build test's own model. Expected: no range printed anywhere, "too few so far to say", and the upload check passes. Tests in Tasks 13, 14 and 16.
4. **NULL terminal, empty desks and NULL expected time in C1.** On the saved model, NULL values are absent: 0 of 10,023 numbers have a NULL terminal, expected time or desks value. Empty desks are common: 5,086 of 10,023 numbers end with none (both counted 2026-11-12). Expected: two NULL terminals tie, empty desks never conflict, and a NULL expected time equals a NULL expected time, as A0's `IS NOT DISTINCT FROM` reads them. Test in Task 3.
5. **A flight number with no digits, for C8's grouping airline.** Expected: it sorts after every numbered one. A0's `arg_min` does the same, since a struct key whose first field is NULL sorts last (checked in DuckDB 1.5.6), and R6 does it with `NULLS LAST`. Test in Task 3.

## Order, and why

- Task 1 comes first because the design asks for it ("The record", condition 3). Its comparison is expected to differ (Task 1, Step 8), so the plan stops there. Task 4 and every later task wait for the owner's ruling, since C5 to C7 are part of the frozen rule and read "as of" moments. Tasks 2 and 3 read no moment: they build on Task 1's committed number-level part while the owner rules.
- Tasks 2 to 7 are everything the frozen rule holds, and Task 8 is the freeze. No page work comes before it. The pages need only what the frozen modules already return, so no dependency forces page work earlier, and every day the freeze waits is a day the gate does not count.
- Tasks 9 to 16 change the pages (Task 9 holds C9, C10 and the front page's figures, which the design does not freeze), Task 17 the documents, and Task 18 runs the final checks.

| Task | What | Implementer |
|---|---|---|
| 1 | The "as of" reading, `load.py`, the cut-archive comparison; the stop | architecture (Fable) |
| 2 | C8: the range, the floor, the rounding (`rates.py`) | transcription (Sonnet) |
| 3 | C1 to C4: flights and results (`counting.py`) | integration (Opus) |
| 4 | C5 to C7: the table's rows and the total | integration (Opus) |
| 5 | The figures check: the code against A0's SQL, in CI and locally | integration (Opus) |
| 6 | Signs S1 to S4 (`record.py`) | integration (Opus) |
| 7 | The sign test, its score, the gate, the re-test, the entry point | integration (Opus) |
| 8 | **The freeze (stop)**: the counting start, the frozen-rule commit, the owner's tag | transcription (Sonnet), main session |
| 9 | `display.py`: C9, C10, the front page's figures | integration (Opus) |
| 10 | `flights.py` lists by C1, C9 and C10 | integration (Opus) |
| 11 | `words.py`: the approved sentences | transcription (Sonnet) |
| 12 | `check.py`: four new upload-check rules | transcription (Sonnet) |
| 13 | `views.py`: the front page and the lists | integration (Opus) |
| 14 | `views.py`: the flight page's block, How this works | integration (Opus) |
| 15 | `static/fromhere.js` | transcription (Sonnet) |
| 16 | `build.py` wiring and the site-wide tests | integration (Opus) |
| 17 | Documents | transcription (Sonnet) |
| 18 | Final verification | main session |

**Coverage of the design.**
- "What it changes in `docs/site-redesign.md`":
  - "Who is a flight": Tasks 3, 10, 17.
  - "Labels": 9, 10, 13, 17.
  - "Warning": 9, 10, 13, 17.
  - "Codeshares": 10, 14, 17.
  - The front page: 4, 9, 10, 13, 16, 17.
  - The rounding steps: 2, 17.
  - "Look", two scripts: 15, 16, 17.
  - The retired and rewritten tests: 10, 13, 16.
  - The non-goal replaced by "The gate": 17.
- "Tests and checks":
  - C1 to C4: Task 3.
  - C6: Task 1 (number level) and Task 4 (rows).
  - C7 and the synthetic fixture: 4.
  - C9, C10 and the late line: 9.
  - The local figures check: 5, 6, 7, 9.
  - The range: 2.
  - Signs: 6.
  - The test: 7.
  - The cut comparison: 1, 6.
  - Words: 11.
  - Pages: 13, 14, 16.
  - `fromhere.js`: 15.
  - The upload check: 12.

## What this plan decided

The design leaves these to the builder, or does not settle them:

- **Five modules, not one.** The design puts counting, the "as of" reading and the signs in "one new pure module" and leaves module names to the builder. This plan freezes `load.py`, `counting.py`, `rates.py` and `record.py`, which hold exactly the design's frozen list. C9, C10 and the lines shown only on pages go in `display.py`, which is not frozen.
- **C8's rounding lives in `rates.py`**, not `words.py` as "How it is built" suggests, because it is part of C8. `words.py` formats with it.
- **The loader moves to `load.py`.** The frozen code reads the model through it, and `build.py`, which later tasks edit, imports it.
- **"Read as of a moment" has two candidate readings, and the owner chooses** at Task 1's stop.
  - Under A0, a number's last stretch ends a second after its last sighting (`docs/flight-lookup-figures.md:63`). So whether a number is still listed at a moment t between two downloads is settled by the download after t, which a build cut at t cannot have.
  - The carry-forward reading takes the list at t to be what the last download at or before t showed: a number's last stretch runs to the next download after its last sighting, and on to the moment read while it is on the latest list.
  - Task 1 implements both and measures both against cut builds, at moments on and between downloads. The plan does not choose.
- **The flight key** is (direction, airport, `sched_utc_final`, the smallest `flight_id` in the flight). C9's tie-break is (`canceled_first_seen_at`, airline, flight number, `flight_id`).
- **Lead-in boundaries.** The pair for checkpoint h covers time left in (the next lower checkpoint, h], and the 70-hour pair covers (48, 72]. More than 72 hours shows the "More than 3 days" line. Zero or less hides the whole block and shows the "has passed" line, as the design says (`docs/flight-lookup.md:249`). The boundaries are written into the page as `data-after` and `data-upto` attributes, so `fromhere.js` holds none of its own.
- **The "Another flight number" line** names every number of the flight that departed or landed (or is still listed, for "is still listed"), whether or not the partner sentence names it too.
- **Upload-check rules 2 to 4** read the page text with tags stripped and nothing blanked. The design skips the airport's strings for rule 1 only. A false hit on the airport's data fails loudly.
- **Markup.** The table is a plain `<table class="fromhere">`, stacked under 600 px as the cancellations table is. The six pairs are `<li>` items, all shown without JavaScript. The "has passed" line sits right after the block, hidden.
- **`fromhere.js` loads only on flight pages with a block.**
- **The local report** goes under `data/record/<tag>/`, and a re-test under `data/record/<tag>/retest-<sign>/`; `data/` is gitignored. The files use a fixed serialization (Task 7). A proposed tag name, `record-v1`, is the owner's to confirm at Task 8.
- **The section order on "How this works"** is Appendix A's. `docs/README.md` gets one line each for the design, the figures file and this plan (Task 17).
- **The dropped signs X1 and X2** are not coded; A0b keeps them as documentation.

## Questions for the owner

1. **The score's range.** "Signs" says the score with and without the sign is "published beside the result with its range" (`docs/flight-lookup.md:291`), and A0b has no Brier query. **Answered by me, 2026-11-12:** the gain per flight (the one rate's squared error minus the split's) is averaged, and its range is 2 grouped standard errors either side, grouped as in C8, the larger of the two groupings. Task 7.
2. **Retimes near the gate.** C4 closes a flight by its final scheduled time (A0, `fl.closed`, `docs/flight-lookup-figures.md:52`). The gate orders flights by the time shown at the checkpoint (A29, `:850-856`). So a flight retimed after its checkpoint can close after flights that sort later, against "When the test is run does not change what it reads" (`docs/flight-lookup.md:285`). **Answered by me, 2026-11-12: the guard.** The gate is declared only once every flight with a 24-hour row at or before the candidate time is closed. Task 7.
3. **C2 against C10 for a closed flight that is still listed.** Suppose one number of a closed flight was listed as cancelled and another is still listed with another status. C10 rule 2 labels the flight NO FINAL UPDATE (`:180`), while C2 counts it as cancelled in the total (`:150`). The design's sum test (`:397`) would then fail for that day. It has not happened: on the saved model no number of a closed flight is still listed, and the number still listed longest after its time was 1.5 hours past it (counted 2026-11-12). **Answered by me, 2026-11-12:** labels by C10, the total by C2, and the sum test over days without that case. Task 16.
4. **Words the design does not give.** D7 approves the design's sentences, and the plan must not invent others. Needed before Task 11.
   - (a) "Another flight number … departed: LH 695." exists only in the singular (`:225`). **Answered by me, 2026-11-12:** name every number, joined as the partner sentence joins them.
   - (b) The bracket exists only as "(LH 0691A is listed as cancelled)" (`:226`). **Answered by me, 2026-11-12:** bracket only that case.
   - (c) No flight-page pair is given for a row below the floor (`:221`, floor at `:173`). **Answered by me, 2026-11-12:** leave that pair out.
   - (d) The total below the floor is given only as "the two counts and 'too few so far to say'" (`:173`). **Answered by me, 2026-11-12:** the first sentence of the total, then "Too few so far to say." This also covers a total with no cancelled flight ("So far, 0 of 900 …").
   - (e) On a flight page, the "More than 3 days" line's second sentence speaks of "this table" (`:217`). **Answered by me, 2026-11-12:** the line uses its first sentence only, "More than 3 days to go: the airport's list does not show the flight yet."
   - (f) The design names the third total tile ("that's about") only with a rate (`:239`). **Answered by me, 2026-11-12:** below the floor, that tile is left out.
   - (g) Counts in the tiles carry thousands separators (`docs/site-redesign.md`, "Look"). **Answered by me, 2026-11-12:** "1 in N" for N of 1,000 or more takes one too ("1 in 1,100").
   - (h) The design gives the late line only with a count (`:219`). **Answered by me, 2026-11-12:** the late line is left out when its count is zero.
5. **Appendix A**, the new "How this works" copy. **Answered by me, 2026-11-12:** approved as drafted.

## Design and code

The design and the code, or the design and its figures, disagree in two places.

1. **Which rules read one download ahead.** Condition 3 says "R2's repeated store and R9's last sighting read one download ahead" (`docs/flight-lookup.md:335`). In the code, R2's repeat check reads the previous snapshot (`src/model/rules.py:231-235`, `lag(sha)`). The reads one download ahead are the receipt status `superseded` (`rules.py:212`, `rules.py:222`, `lead(sha)` and `next_id`) and R9's sighting window, which runs to the next kept snapshot (`rules.py:286`, `rules.py:291-297`). Task 1's archive has a case for each.
2. **A35's 3-hour line is one step off.** C8 rounds each end of a range outward by its own step. The 3-hour row's lower end is 1 in 119.9922: C8's formula in plain Python over A0's `cell` on `data/model-2026-11-12`, computed 2026-11-12. A6 prints it to one decimal as 120.0. So it rounds down to "1 in 110", not "1 in 120", and the row prints "about 1 in 230 (between 1 in 110 and 1 in 460)". The total and the other five rows print as A35 does: their unrounded ends were computed the same way and are listed in Task 2. "1 in 120" is quoted at `docs/flight-lookup.md:201` and `docs/flight-lookup-figures.md:981`. Both were corrected on 2026-11-12, in the commit that adds this plan; this plan's tests follow C8.

---

### Task 1: The "as of" reading, `load.py` and the cut-archive comparison (the stop)

Implementer: architecture (Fable). Design: "The record", condition 3; C6; A0 (`st`, `hole`, `cp`); `docs/data-model.md`, R2, R4 and R9.

**Files:**
- Create: `src/timeline/load.py`. It takes `OBS_COLUMNS`, `_rows` and `load` from `src/timeline/build.py:23-47`, and `OBS_COLUMNS` gains `"sched_utc"` and `"est_utc"`. `build.py` imports `load` from it, so `build.load` keeps working (`tests/test_timeline_build.py:124`).
- Create: `src/timeline/counting.py` (first block only).
- Create: `tests/counting_helpers.py`, `tests/test_counting.py`, `tests/test_frozen.py`, `tests/test_record_cut.py`.
- Modify: `tests/model_helpers.py` (add `cut_archive`).
- Modify: `scripts/mutation_check.py`:
  - add `COUNTING = ("src/timeline/counting.py", ["tests/test_counting.py"])`, `LOAD = ("src/timeline/load.py", ["tests/test_timeline_build.py"])` and `FROZEN_GUARD = ("src/timeline/counting.py", ["tests/test_frozen.py"])`;
  - retarget "site: gap sentence from the store, not the last sighting" to `LOAD`, since its text moves to `load.py`.

**Interfaces:**
- Consumes: `model.build.build(raw, out, receipts)`; `model_helpers.write_snapshot`, `write_receipt`, `row`, `at`; `model.rules.GAP_HOURS`.
- Produces, in `timeline.load`: `load(model_dir: Path) -> tuple[list[dict], list[dict], list[dict]]`, as `build.load` was.
- Produces, in `timeline.counting`:

```python
CHECKPOINTS = (70, 48, 24, 12, 6, 3)
READINGS = ("a0", "carry")
READING = "a0"                 # the reading the frozen rule uses; set by the owner's ruling at this task's stop

@dataclass(frozen=True)
class Stretch:                 # what the list showed for one number from one change to the next (A0's st)
    flight_id: str; snap_rn: int
    from_at: datetime          # this observation's time
    to_at: datetime            # the next observation's time; else, by reading: "a0" the number's last_seen_at + 1 s,
                               # "carry" the next download after last_seen_at, or datetime.max on the latest list
    to_ever: datetime          # the next observation's time, else datetime.max (the last state kept after leaving)
    sched_utc: datetime; est_utc: datetime | None; status: str; terminal: int | None; desks: str   # desks: counters or ""

def stretches(table: list[dict], obs: list[dict], snaps: list[dict], reading: str = READING) -> dict[str, tuple[Stretch, ...]]
def holes(snaps: list[dict]) -> tuple[tuple[datetime, datetime], ...]   # (prev, fetched_at) where gap_before_s > GAP_HOURS*3600
def in_hole(t: datetime, holes_) -> bool                                # strictly inside
def passings(st: dict[str, tuple[Stretch, ...]], holes_) -> dict[tuple[str, int], tuple[datetime, str]]
    # (flight_id, h) -> (t, status) of the first passing: the lowest-snap_rn stretch whose own
    # sched_utc - h falls in [from_at, to_at), never inside a hole
def state_at(st: dict[str, tuple[Stretch, ...]], t: datetime) -> dict[str, Stretch]   # numbers listed at t, by to_at
def last_sighting(snaps: list[dict]) -> datetime                        # snaps[-1]["confirmed_until"]
```

- Produces, in `tests/model_helpers.py`: `cut_archive(raw: Path, receipts: Path, moment: datetime, dest: Path) -> tuple[Path, Path]`. It copies the snapshot folders and receipt files whose path time (`date=YYYY-MM-DD/HHMMSSZ-…`) is at or before `moment`.

**Part 1: the number-level reading (committed on its own).**

- [ ] **Step 1: Write the failing tests** in `tests/test_counting.py`. Rows come from `tests/counting_helpers.py`: `number(fid, sched_utc, **kw)` is a flights-table row holding the columns counting reads; `seen(fid, rn, at, **state)` an observation; `board(*fetches, gaps=…)` the snapshot rows as `load` returns them. All times are naive UTC in November 2026.
  - `test_a_stretch_runs_to_the_next_change_and_the_last_to_a_second_after_the_last_sighting`. A first record at 10:00 (rn 1), a change at 11:00 (rn 5), `last_seen_at` 12:30. Expected stretches (10:00, 11:00) and (11:00, 12:30:01), with `to_ever` 11:00 and `datetime.max`.
  - `test_carry_forward_runs_the_last_stretch_to_the_next_download`. The same number with the next download at 12:45: `to_at` is 12:45. On the latest list, `to_at` is `datetime.max`.
  - `test_the_clock_is_the_time_shown_at_the_moment`. Scheduled 2 Nov 12:00 until a retime seen 1 Nov 13:00 moves it to 2 Nov 14:00. At 1 Nov 12:00 the list still showed 2 Nov 12:00, so expected: `passings[(id, 24)] == (1 Nov 12:00, the first stretch's status)`. A reading by the final scheduled time would give 1 Nov 14:00, so this test separates the two.
  - `test_a_number_first_listed_past_a_point_has_no_passing_there`. First seen 20 h before its time: no `(id, 24)`; `(id, 12)` present.
  - `test_a_moment_inside_a_hole_is_not_a_checkpoint`. A hole from 10:00 to 13:00. At t = 11:00 there is no passing. At t = 10:00 and t = 13:00 there is, because the hole is strict.
  - `test_the_first_passing_counts`. Two stretches each hold their own 24-hour moment; expected the earlier stretch's (t, status).
  - `test_holes_from_the_last_sighting_to_the_next_fetch`. `gap_before_s` 3601 gives a hole (prev `confirmed_until`, `fetched_at`); 3600 gives none.
  - `tests/test_frozen.py::test_frozen_modules_import_only_frozen_modules`. Each module named in `FROZEN = {"load", "counting"}` (Tasks 2 and 6 add `"rates"` and `"record"`) is parsed with `ast`. Every relative import, and every import of `timeline.*`, must name a module in `FROZEN`; `model.*`, the standard library and `duckdb` are allowed.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_counting.py tests/test_frozen.py -q` fails on the missing `timeline.counting`.
- [ ] **Step 3: Implement** `load.py` (the move) and the `counting.py` block. `passings` iterates each number's stretches in `snap_rn` order and keeps the first hit per h.
- [ ] **Step 4: Run; pass.** `.venv/bin/pytest tests/test_counting.py tests/test_frozen.py tests/test_timeline_build.py -q`
- [ ] **Step 5: Mutation entries.** Then run, alone and before any sizing build (Step 9): `.venv/bin/python scripts/mutation_check.py "counting: " "frozen: " "site: gap sentence"`. Expected: every entry CAUGHT.
  - File `COUNTING`: "counting: a number's last stretch ends at its last sighting" (drop the extra second), "counting: every stretch runs to the last sighting" (drop the next change), "counting: carry-forward ends a second after the last sighting", "counting: the clock from the final scheduled time", "counting: the last passing counts", "counting: a hole's edges count as inside it", "counting: a hole at exactly an hour".
  - File `FROZEN_GUARD`: "frozen: counting imports words" (adds `from . import words` beside the first import).
- [ ] **Step 6: Review (Opus), then commit the number-level part on its own:**

```bash
git add src/timeline/load.py src/timeline/build.py src/timeline/counting.py tests/counting_helpers.py \
        tests/test_counting.py tests/test_frozen.py scripts/mutation_check.py
git commit -m "q21: the 'as of' reading, two candidate readings, and the model loader in its own module"
```

  Tasks 2 and 3 build on this commit.

**Part 2: the cut comparison (holds the stop).**

- [ ] **Step 7: Write the cut comparison** in `tests/test_record_cut.py`. Each case is its own small archive:
  - snapshots every 15 minutes from 2026-10-30 10:00Z to 14:00Z;
  - a stored receipt at each fetch;
  - flights scheduled so that one 24-, 12- or 6-hour moment of each falls inside the window.

  Every case is cut at moments on a download and between downloads. The cases and their cut moments (UTC, 30 October):
  - `leave-and-return`. LY 100 is listed 10:00 to 11:00, absent 11:15 to 11:45, and back from 12:00 (A20's case). Moments 11:07, 11:30, 12:30 and 12:37.
  - `return-after-a-same-number-key`. As above, plus LY 100 at a scheduled time 3 h later, first listed at 11:15 and not terminal. A cut at 11:30 can link it as a retime. The full build cannot, because the old key's last snapshot is 14:00 (`rules.py:337`, `rules.py:352`). Moments 11:15, 11:22, 11:30 and 12:30.
  - `retime-at-the-cut`. LY 200's key is last seen at 11:00, and a key 2 h later is first seen at 11:15. Moments 11:00, 11:07 and 11:15.
  - `flight-changes-after`. EY 607 and LY 9614 share expected time, terminal and desks until 12:00, and neither departs in the archive. At 12:15 LY 9614 moves to another desk range, so C1 no longer ties them (two desk ranges never tie), and the flight splits after the moment. Moments 12:00 and 12:07.
  - `leaves-between-downloads`. LY 300 is in the 11:00 download and gone from 11:15 on. A variant adds unchanged receipts at 11:04 and 11:08, so A0's last sighting is 11:08. Moments 11:06, 11:07, 11:10 and 11:20.
  - `repeated-store`. The 11:15 board is stored again at 11:17 with the same hash and its own receipt (R2 drops it, and R9 credits its sighting). Moments 11:15, 11:16 and 11:17.
  - `superseded`. An 11:15 snapshot with no receipt is stored again at 11:17 with one (`rules.py:222`). Moments 11:15, 11:16 and 11:17.
  - `unchanged-downloads`. Unchanged receipts at 11:17, 11:19 and 11:21 follow the 11:15 store, the next store is at 11:30, and one number leaves after 11:15. Moments 11:17, 11:18, 11:21 and 11:25.
  - `hole-in-progress`. Nothing is downloaded from 11:00 to 12:30. Moment 11:45.

  For each (case, moment T): build the full model and the model from `cut_archive`, and load both with `load`. L is the cut's `last_sighting`. The test ids are `<case>-<HHMM>`. The tests:
  - `test_cut_builds_build`: the cut model builds without error.
  - `test_record_readings_match`: both models by A0's reading, at moments up to L. For every number first seen at or before L, compare:
    - its first record (time, `sched_utc`, status);
    - its stretches with `from_at <= L` and `to_at` capped at L + 1 s (from, to, status, scheduled time, expected time, terminal, desks);
    - its passings with t at or before L.
  - `test_a0_against_carry_forward_at_the_moment`: at T itself, the full model by A0's reading against the cut by the carry-forward reading. Compare `state_at(…, T)` (listed or not, and if listed: status, scheduled time, expected time, terminal, desks) and the passings at or before T.
  - `test_carry_forward_matches_at_the_moment`: the same, with the full model also read by the carry-forward reading.
  - `test_retime_chains_match`: compare the key ids each number's chain holds (`flights.key_ids`), among keys first seen at or before L. Each key's first-seen time comes from a DuckDB read of the observations' `key_id` where `change_kind` is `first` or `retime`, in the test.
  - `test_flight_inputs_match`: compare each number's `est_utc_final`, `terminal_final` and `counters_final`, the full model's (read at the end, as C1 reads them) against the cut's. The design lists this as a known case (condition 3, third bullet). The outcome is left out, because C2 reads it at the end by design. Flight membership is compared in Task 6, once C1 exists.
- [ ] **Step 8: Run; the comparison is expected to fail.** `.venv/bin/pytest tests/test_record_cut.py -q`. Three failures follow from the cases' construction:
  - `leave-and-return` at 11:30: the cut ends LY 100's stretch at 11:00:01, while the full model runs it on.
  - `test_flight_inputs_match`: it differs by the design's reading at the end.
  - `leaves-between-downloads` under A0 against carry-forward.

  Nothing in Part 2 is committed while it fails.
- [ ] **Step 9: The stop: measure, then report to the owner.** The order matters. Run every measurement below only when no mutation check is running: a mutation check edits `src/model/rules.py` in place, so a build during one would run a planted bug. A full build peaked at 5.9 GiB on this 8 GiB Mac (`docs/data-model.md`, "Nightly run"). So run them before Tasks 2 and 3 start, or between those tasks' mutation runs.
  1. **What differs.** Each failing (case, moment, test), with its first differing values.
  2. **The effect on `data/model-2026-11-12`**, for each kind of difference, under A0's reading and under the carry-forward reading:
     - for each checkpoint: the flights that enter or leave the row, and the cancelled flights among them;
     - what A6 becomes. A2 reads no moment (its query reads only `fl`, `docs/flight-lookup-figures.md:248-249`), so the report confirms it stays 81 of 4,658.

     The carry-forward figures come from a scratch copy of A0's SQL, nothing committed, whose `st.to_at` ends a number's last stretch at the next download after its last sighting. Two kinds cannot be measured on the full model without cut builds: leave-and-return, and the retime chains. Bound them from A20's 7 numbers: the passings they hold, and the cancelled flights among their flights. For C1's inputs read at the end, count the 24-hour-row flights whose numbers changed expected time, terminal or desks after their 24-hour passing, and how many of those were cancelled.
  3. **The size of a cut build.** Work in a scratch folder outside the repository (`SCRATCH=$(mktemp -d)`).
     - One full build at DuckDB's default limit: `/usr/bin/time -l env PYTHONPATH=src .venv/bin/python -m model.build --raw data/raw --out "$SCRATCH/model"`. Read "real" and "maximum resident set size".
     - The default limit on this Mac is 6.3 GiB (`SELECT current_setting('memory_limit')`, 2026-11-12), and a peak near it shows the limit, not the need (`docs/data-model.md`, "Nightly run").
     - So build again under explicit limits of 4GB, 2GB, 1GB and 512MB, each under `/usr/bin/time -l`: `rules.connect()`, `SET memory_limit = '<limit>'`, `SET temp_directory = '$SCRATCH/spill'`, then `rules.build_all(con, 'data/raw/**/*.json.gz', 'data/receipts/**/*.json')`. The temp directory must be set: DuckDB's default is `.tmp` in the working directory (checked 2026-11-12), which would spill into the repository root.
     - Report the smallest limit that completes, the time at each limit, and whether `$SCRATCH/spill` holds files afterwards. Whether a lower limit spills or fails is UNVERIFIED.
  4. **How many cut builds a record would need**, on `data/model-2026-11-12`: the distinct last sightings at or before each 24-hour passing (snapshot fetches, and `receipts.run_started_at` truncated to the second, as R9 does), in total and per Israel day. Report also their product with one build's time over a 60-day record. The product is an estimate, since build time grows with the archive: 3.5 s at 150 snapshots and 13 s at 600 (`docs/data-model.md`).

  The owner then rules among three options:
  - keep A0's reading as a stated limit;
  - the carry-forward reading;
  - cut builds, which re-plans Tasks 4 to 8 with the sizing above.

  Tasks 2 and 3 may go ahead meanwhile. Tasks 4 to 8 wait.
- [ ] **Step 10: Apply the ruling.**
  - Set `READING` to the chosen reading, and remove the other one unless the ruling keeps it.
  - Make each cut-comparison test assert what the ruling accepts, with the ruling quoted in a comment.
  - Add a mutation entry for any behaviour the ruling adds.
  - Write a line in Deviations.

  Run `.venv/bin/pytest tests/test_counting.py tests/test_record_cut.py -q`, which passes, and the new entries alone (CAUGHT).
- [ ] **Step 11: Review (Opus), then commit** (`git commit -m "q21: the cut-archive comparison and the owner's ruling on the 'as of' reading"`).

### Task 2: C8, the range, the floor and the rounding (`rates.py`)

Implementer: transcription (Sonnet). Design: C8; A0 `rng`; A35. Builds on Task 1, Step 6.

**Files:**
- Create: `src/timeline/rates.py`, `tests/test_rates.py`
- Modify: `tests/test_frozen.py` (`"rates"` joins `FROZEN`), `scripts/mutation_check.py` (`RATES = ("src/timeline/rates.py", ["tests/test_rates.py"])`)

**Interfaces:**
- Produces, in `timeline.rates`:

```python
FLOOR_CANCELLED, FLOOR_AIRLINES, FLOOR_DAYS = 10, 5, 5

@dataclass(frozen=True)
class Counted: k: int; airline: str; day: date          # one flight in a set a rate is taken over

def week(day: date) -> date                              # the Sunday on or before `day`
def grouped_se(items: Sequence[Counted], key: Callable[[Counted], Hashable]) -> float
    # sqrt(G / (G - 1) * sum_g (k_g - r * n_g) ** 2) / N, summed with math.fsum over groups in sorted key order

@dataclass(frozen=True)
class Rate:
    cancelled: int; flights: int; airlines: int; days: int     # airlines and days among cancelled flights only
    clears_floor: bool
    one_in: float | None                                       # flights / cancelled; None at 0
    one_in_from: float | None; one_in_to: float | None         # the ends as "1 in": from = the higher rate's end
    se_airline_week: float | None; se_day: float | None

def rate(items: Sequence[Counted]) -> Rate      # ends only when 0 < K < N and each grouping has 2 or more groups
def step(x: float) -> int                       # 1 below 20, 5 below 100, 10 below 1000, else 100
def round_middle(x: float) -> int               # nearest step, halves up
def round_range(lo: float, hi: float) -> tuple[int, int]   # lo down, hi up, each by its own step
```

- [ ] **Step 1: Write the failing tests.** The two hand cases below were checked this session against A0's `rng` macro on the same rows: the macro gives 2.9 to 44.3, and 3.7 to 72.9.
  - `test_the_airline_week_grouping_is_the_larger`. Rows:
    - airline A, week of 2026-10-25: 10 flights, 3 cancelled;
    - airline B, the same week: 10 flights, 0 cancelled (both on 2026-10-27);
    - airline A, week of 2026-11-01: 10 flights, 1 cancelled;
    - airline B, that week: 10 flights, 0 cancelled (both on 2026-11-02).

    Expected `se_airline_week == approx(0.070711, abs=1e-6)`, `se_day == approx(0.05)`, `one_in == 10.0`, `one_in_from == approx(2.8699, abs=1e-4)`, `one_in_to == approx(44.3182, abs=1e-4)`.
  - `test_the_day_grouping_is_the_larger`. All rows in the week of 2026-10-25:
    - airline A: 10 flights with 2 cancelled on 10-26, and 10 with 0 on 10-27;
    - airline B: the same;
    - airline C: 10 with 0 on 10-28, and 10 with 0 on 10-26.

    Expected `se_airline_week == approx(0.033333, abs=1e-6)`, `se_day == approx(0.050918, abs=1e-6)`, `one_in == 15.0`, `one_in_from == approx(3.7249, abs=1e-4)`, `one_in_to == approx(72.9299, abs=1e-4)`.
  - `test_weeks_start_on_sunday`: `week(date(2026, 10, 31)) == date(2026, 10, 25)` (a Saturday) and `week(date(2026, 11, 1)) == date(2026, 11, 1)` (a Sunday).
  - `test_the_range_never_falls_below_zero`: in the first case, `0.1 - 2 * 0.070711 < 0`, yet `1 / one_in_to > 0`.
  - `test_the_floor`, parametrized:
    - 9, 10 and 11 cancelled, from 5 airlines on 5 days, give False, True, True;
    - 10 cancelled from 4 airlines gives False;
    - 10 cancelled from 4 days gives False;
    - the airlines and days of flights that were not cancelled do not count.
  - `test_no_range_at_zero_or_with_one_group`: 0 cancelled gives `one_in is None`, and one day group gives no ends.
  - `test_the_middle_to_the_nearest_step_halves_up`: 19.4 → 19, 19.5 → 20, 22.4 → 20, 22.5 → 25, 57.5 → 60, 97.5 → 100, 98.5 → 100, 104.9 → 100, 105 → 110, 145.0 → 150, 994.9 → 990, 995 → 1000, 1049 → 1000, 1050 → 1100.
  - `test_the_ends_round_outward_each_by_its_own_step`: (33.2, 120.6) → (30, 130), (36.3, 91.6) → (35, 95), (119.9922, 459.6909) → (110, 460), (120.0, 459.7) → (120, 460), (19.9, 20.1) → (19, 25), (999.5, 1000.5) → (990, 1100).
  - `test_the_real_rows_print_by_c8`. The unrounded values (`one_in`, from, to) on the saved model, computed this session with C8's formula in plain Python over A0's `cell`:

    | Row | one_in | from | to | Prints |
    |---|---|---|---|---|
    | total | 57.5062 | 36.2607 | 91.5526 | 60, 35, 95 |
    | 70 hours | 63.0833 | 33.2345 | 120.5719 | 65, 30, 130 |
    | 48 hours | 70.5532 | 38.1063 | 131.3727 | 70, 35, 140 |
    | 24 hours | 98.5429 | 49.3213 | 197.9028 | 100, 45, 200 |
    | 12 hours | 145.0 | 71.3918 | 295.5799 | 150, 70, 300 |
    | 6 hours | 194.9474 | 96.6079 | 394.4358 | 190, 95, 400 |
    | 3 hours | 234.625 | 119.9922 | 459.6909 | 230, 110, 460 |

    The 3-hour row is not A35's line ("Design and code", 2).
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_rates.py tests/test_frozen.py -q`
- [ ] **Step 3: Implement.** The ends are `logit(r) ± 2 * se / (r * (1 - r))` turned back into rates, with se the larger of the two groupings. The airline-and-week group key is `(airline, week(day))`.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** (file `RATES`): "rates: the smaller standard error", "rates: no small-sample factor", "rates: weeks start on Monday", "rates: range on the rate scale", "rates: floor at 9", "rates: floor without the airline count", "rates: floor without the day count", "rates: floor counts every flight's airline", "rates: halves down", "rates: no step of 10", "rates: ends rounded inward". Run `.venv/bin/python scripts/mutation_check.py "rates: "` alone. Expected: all CAUGHT. The summation order gets no entry: no test data separates `math.fsum` in sorted order from a plain sum, and Task 7's same-bytes test guards it.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: rule C8, the grouped range, the floor and the rounding"`).

### Task 3: C1 to C4, flights and results

Implementer: integration (Opus). Design: C1 to C4; A0 (`n0`, `tie`, `num`, `fl`); A10 to A16. Builds on Task 1, Step 6.

**Files:**
- Modify: `src/timeline/counting.py`, `tests/test_counting.py`, `tests/counting_helpers.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `rates.week`.
- Produces, in `timeline.counting`:

```python
CLOSED_AFTER = timedelta(hours=48)

@dataclass(frozen=True)
class Flight:
    key: tuple[str, str, datetime, str]   # direction, airport, sched_utc_final, the smallest flight_id
    numbers: tuple[str, ...]              # flight_ids, sorted
    result: str                           # "operated" | "cancelled" | "unknown" (C2)
    closed: bool                          # C4: sched_utc_final <= last sighting - 48 h
    airline: str                          # C8's grouping airline
    day: date                             # Israel date of sched_local_final
    first_seen: datetime                  # the earliest first_seen_at of its numbers

def tied(a: dict, b: dict) -> bool                                  # C1's direct tie: two flights-table rows of one slot
def flights(table: list[dict], last_sighting_: datetime) -> list[Flight]   # sorted by key
def flight_of(flights_: list[Flight]) -> dict[str, Flight]          # flight_id -> its flight
```

- [ ] **Step 1: Write the failing tests.** Rows come from `counting_helpers.number`, with values as in A11 and A14.
  - C1:
    - `test_the_same_expected_time_terminal_and_desks_tie`: EY 607 and LY 9614, both departed, in one flight.
    - `test_one_airline_at_one_desk_range_with_two_expected_times_is_two_flights`: EY 596 and EY 610, both departed, desks 12-21, expected 05:18 and 06:24.
    - `test_two_desk_ranges_never_tie`: ENT 229 at 220-223 and ENT 359 at 223-226, also with one of them cancelled.
    - `test_two_terminals_never_tie`: a cancelled LY at terminal 1 and a departed LY at terminal 3.
    - `test_a_cancelled_number_ties_by_airline_or_desks_only`:
      - OS 1083 with OS 083 gives one flight;
      - U8 103 with BZ 112 at the same desks gives one;
      - IZ 991 (34-41) with LY 003 (78-99) gives two;
      - IZ 991 cancelled with no desks, beside LY 003 departed at 78-99, gives two (A11's 7 November case).
    - `test_ties_chain`: LY cancelled (no desks), LY departed (1-5) and DL cancelled (1-5) are one flight.
    - `test_a_chain_never_joins_two_departed_numbers_apart`: LY 001 departed (1-5, expected 10:00), LY 002 departed (1-5, expected 10:40) and LY 9001 cancelled (1-5) give three flights, each number alone.
    - `test_nulls_tie_as_equal` (Review Focus 4): two `terminal=None` tie; `desks=""` never conflicts; `est_utc=None` equals `None`.
  - C2, `test_results`:
    - departed with canceled gives "operated";
    - canceled with vanished gives "cancelled";
    - gap with open gives "unknown".
  - C3, `test_last_status_counts`:
    - uncanceled, then landed, gives "operated";
    - uncanceled, then canceled again, gives one cancelled flight;
    - LH 0691A beside LH 695 departed gives "operated";
    - one number on two days gives two flights.
  - C4, `test_closed_48_hours_after`, with the last sighting at 2026-11-12 10:16:45:
    - a flight 47 h before it is not closed, and one exactly 48 h before is;
    - a flight first scheduled 50 h before it, then retimed to 47 h before, is not closed (closed by the final time).
  - `test_the_grouping_airline`:
    - LH 0691 against EY 607: the lowest numeric part picks EY, where string order would pick LH;
    - the airline on a tie: AA 100 before AB 100;
    - a number with no digits after every numbered one (Review Focus 5).
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_counting.py -q`
- [ ] **Step 3: Implement.**
  - Union-find within each slot over `tied` pairs.
  - Then the fallback, for a component holding two operated numbers that differ in expected time, terminal or desks: its numbers that did not operate each stand alone, and its operated numbers regroup by (expected time, terminal, desks).
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:** "counting: expected time left out of the tie", "counting: two desk ranges tie", "counting: two terminals tie", "counting: two operated numbers tie by airline", "counting: a cancelled number ties to any airline", "counting: no chains", "counting: no fallback", "counting: cancelled before operated", "counting: closed at 47 hours", "counting: closed by the first scheduled time", "counting: grouping airline by string order". Run `"counting: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: rules C1 to C4"`).

### Task 4: C5 to C7, the table's rows and the total

Implementer: integration (Opus). Design: C4 to C7, "The figures under the method"; A0 (`cp`, `cell`). Waits for Task 1's ruling.

**Files:**
- Modify: `src/timeline/counting.py`, `tests/test_counting.py`, `scripts/mutation_check.py`
- Create: `tests/counting_fixture.py` (the hand-computed model, in CI)

**Interfaces:**
- Consumes: Task 1's `stretches(table, obs)` (A0's rule, the owner's ruling; it has no reading option since Step 10), `holes` and `passings`; Task 3's `flights`; `rates.rate`, `rates.Counted`.
- Produces, in `timeline.counting`:

```python
@dataclass(frozen=True)
class Cell: h: int; flight: Flight; t: datetime; k: int     # a closed flight with a known result, in row h

def cells(flights_: list[Flight], passings_: dict) -> list[Cell]
    # in row h when any number passed h with a status other than CANCELED; t = the earliest such passing
def counted(f: Flight) -> rates.Counted                     # k = 1 when the result is cancelled; a cell's is counted(c.flight)

@dataclass(frozen=True)
class Figures:
    total: rates.Rate                                       # closed flights with a known result
    rows: tuple[tuple[int, rates.Rate], ...]                # (h, rate) in CHECKPOINTS order

def figures(table: list[dict], obs: list[dict], snaps: list[dict]) -> Figures
```

- [ ] **Step 1: Write the failing tests:**
  - C6 rows: `test_already_cancelled_at_the_point_is_not_in_the_row`, `test_a_delayed_number_is_in_the_row`, `test_a_flight_is_in_the_row_when_any_number_passed_listed_normally`, `test_the_rows_moment_is_the_earliest_passing`.
  - C7, `test_cancelled_after_its_time_counts_in_every_row_it_was_in`: k = 1 at 70, 48, 24, 12, 6 and 3.
  - C4 in rows, `test_open_and_unknown_flights_make_no_rate`.
  - `test_the_hand_computed_fixture`. `counting_fixture.model()` holds 650 flights over 6 Israel days and 6 airlines, 12 of them closed and cancelled, plus open, unknown, retimed and codeshare cases. The total and every row are asserted by count and by range. The expected values are computed outside the code (by hand, or with A0's SQL on the same rows) and written as literals.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_counting.py -q`
- [ ] **Step 3: Implement** `cells`, `counted` and `figures`.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:** "counting: a cancelled passing puts its flight in the row", "counting: open flights in the rate", "counting: unknown results in the rate", "counting: the row's moment from the latest passing". Run `"counting: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: rules C5 to C7, the table's rows and the total"`).

### Task 5: The figures check

Implementer: integration (Opus). Design: "Tests and checks", Counting, the last item; the figures file's "To reproduce".

**Files:**
- Create: `scripts/figures_check.py`, `tests/test_figures_check.py`
- Modify: `scripts/mutation_check.py` (`FIGURES = ("scripts/figures_check.py", ["tests/test_figures_check.py"])`; add `"tests/test_figures_check.py"` to `COUNTING`'s test list)

**Interfaces:**
- Consumes: `timeline.load.load`, `counting.figures`, `counting.flights`, `counting.cells`.
- Produces, in `scripts/figures_check.py`, which tests load with `importlib`, as `tests/test_mutation_check.py` loads its script:

```python
def sql_blocks(doc: str, *names: str) -> dict[str, str]            # "A0" -> the ```sql block under "## A0. "; KeyError if absent
def run_sql(model_dir: Path, names: tuple[str, ...]) -> duckdb.DuckDBPyConnection
    # the blocks, with 'data/model/ replaced by the model folder, run in order on one connection
def compare_flights(con, flights_) -> list[str]   # numbers grouped differently from A0's num.flight_key (as partitions)
def compare_cells(con, cells_) -> list[str]       # (h, flight, t, k) against A0's cell
EXPECTED: dict[str, object]                       # the figures file's printed values (A2 and A6 here; Tasks 6, 7, 9 add)
def main(argv: list[str]) -> int                  # --model DIR; prints each figure with "ok" or both values; 0 or 1
```

- [ ] **Step 1: Write the failing tests.** They run in CI on a synthetic model, built through `model.build` from `model_helpers`. The model holds C1 and C6 cases but no slot where C1's fallback fires: A0 leaves the fallback out (the figures file's comment above `num`), and Task 3's unit test covers it.
  - `test_sql_blocks_finds_a0_and_a0b_and_refuses_a_missing_section`.
  - `test_the_flights_match_a0`, `test_the_cells_match_a0`.
  - `test_the_rates_match_a0s_rng`: for the total and each row, A0's `rng` macro and `rates.rate` agree on counts, `one_in` and both ends to one decimal.
  - `test_a_planted_difference_is_named`: a monkeypatched `counting.flights` that splits one flight gives a non-empty `compare_flights`.
  - `test_main_fails_on_a_figure_that_differs`: with `EXPECTED` monkeypatched to the synthetic model's values, exit 0; with one count off by one, exit 1, and the figure is named.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_figures_check.py -q`
- [ ] **Step 3: Implement.** Copy `EXPECTED` from the figures file. A2: `81, 4658, 57.5, 36.3, 91.6`. A6's six rows:

  | Row | cancelled | flights | one_in | from | to |
  |---|---|---|---|---|---|
  | 70 | 48 | 3028 | 63.1 | 33.2 | 120.6 |
  | 48 | 47 | 3316 | 70.6 | 38.1 | 131.4 |
  | 24 | 35 | 3449 | 98.5 | 49.3 | 197.9 |
  | 12 | 25 | 3625 | 145.0 | 71.4 | 295.6 |
  | 6 | 19 | 3704 | 194.9 | 96.6 | 394.4 |
  | 3 | 16 | 3754 | 234.6 | 120.0 | 459.7 |

  A6's one-decimal values are correct roundings of the unrounded ends, so this check holds while A35's printed line does not.
- [ ] **Step 4: Run; pass.** Then run locally: `PYTHONPATH=src .venv/bin/python scripts/figures_check.py --model data/model-2026-11-12`. Expected: every line "ok" (for example "24 hours: 35 of 3,449, 1 in 98.5 (49.3 to 197.9) ok"), "flights: 0 differences", "cells: 0 differences", exit 0.
  - Checked this session: A0's SQL run on `data/model-2026-11-12` reproduces A2, A3, A6, A13, A17, A24 and A30, in about a second.
  - The check is local only, because the model is not in the repository. The saved copy stays put, while `data/model` is rebuilt after every sync.
- [ ] **Step 5: Mutation entries** (file `FIGURES`): "figures: SQL from the wrong section", "figures: a flight difference not reported", "figures: a figure off by one passes". Run `"figures: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: the figures check, the code against the figures file's SQL"`).

### Task 6: Signs S1 to S4

Implementer: integration (Opus). Design: "Signs" (the second paragraph and the table); A0b (`nrow`, `not_whole`, `nsign`, `sign`, `signcell`); A25. Waits for Task 1's ruling.

**Files:**
- Create: `src/timeline/record.py`, `tests/test_record.py`
- Modify:
  - `tests/test_record_cut.py` (flights and sign readings);
  - `scripts/figures_check.py` and `tests/test_figures_check.py` (A0b, A25);
  - `tests/test_frozen.py` (`"record"` joins `FROZEN`);
  - `scripts/mutation_check.py` (`RECORD = ("src/timeline/record.py", ["tests/test_record.py"])`).

**Interfaces:**
- Consumes: `counting.Stretch`, `stretches`, `holes`, `passings`, `Cell`, `cells`; the flights-table rows by `flight_id`.
- Produces, in `timeline.record`:

```python
SIGNS = ("S1", "S2", "S3", "S4")

def whole(a: Stretch, t: datetime, by_slot: dict, by_id: dict) -> bool
    # `a` shows CANCELED at t and no other number tied to it at t (same slot as shown at t, A0b's not_whole ties,
    # stretch read by to_ever) shows anything else
def number_signs(h: int, table: list[dict], st: dict, holes_, first_fetch: datetime,
                 passings_: dict) -> dict[str, frozenset[str]]
    # flight_id -> the signs it shows at its h-hour passing; only numbers in the row (status other than CANCELED)
def flight_signs(cells_h: list[Cell], number_signs_: dict[str, frozenset[str]]) -> dict[tuple, frozenset[str]]
    # S1 to S3 when any of the flight's numbers in the row shows it; S4 when every one of them does
```

- [ ] **Step 1: Write the failing tests** in `tests/test_record.py`, with rows from `counting_helpers`:
  - S1:
    - `test_s1_an_inbound_listed_as_cancelled_as_a_whole` (present);
    - `test_s1_departures_only`;
    - `test_s1_window`: the inbound scheduled 30 min and 12 h before the time shown at t is in, and 29 min and 12 h 1 min before is out;
    - `test_s1_window_from_the_time_shown_at_t`: a departure retimed 3 h later after its checkpoint, with an inbound scheduled 11 h before the time shown at t, carries S1. Measured from the final time, the inbound would fall outside the window;
    - `test_s1_needs_the_inbound_on_the_list_at_t` (`to_at`, not `to_ever`).
  - "As a whole":
    - `test_not_whole_while_a_tied_number_is_still_listed`;
    - `test_not_whole_when_a_tied_number_left_as_departed` (its last status is kept, through `to_ever`);
    - `test_a_number_first_seen_after_the_moment_is_ignored`.
  - S2:
    - `test_s2_the_latest_before_as_of_the_moment_after_a_retime`: the previous flight's time as shown at t decides, not its final time;
    - `test_s2_absent_when_the_latest_before_departed`.
  - S3, `test_s3_another_slot_within_24_hours`: 24 h either side is in; the flight's own slot is out.
  - S4:
    - `test_s4_first_listed_under_48_hours`: 47:59 is in, 48:00 out;
    - `test_s4_not_late_when_first_seen_at_the_first_list_or_after_a_hole`.
  - Carry, `test_a_flight_carries_s1_when_one_number_shows_it_and_s4_only_when_all_do`.
- [ ] **Step 2: Extend the cut comparison** for every case of Task 1, full model against cut, with the reading the ruling chose:
  - `test_flights_match`: C1's flights among numbers first seen at or before L. `flight-changes-after` splits by construction, which is the design's third known case.
  - `test_sign_readings_match`: the number-level signs at passings at or before L, and each flight's carry from `flight_signs`.

  Cases the ruling accepted as differing are asserted as the ruling says. A new difference beyond the ruling is a stop, as in Task 1, Step 9.
- [ ] **Step 3: Extend the figures check.**
  - `compare_signs(con, …)` compares the code with A0b's `sign` table one for one.
  - `EXPECTED["A25"]` holds S1 to S4 at 48, 24, 12 and 6 hours. At 24 hours: S1 `2, 5, 20, 1715`; S2 `4, 30, 31, 3419`; S3 `11, 491, 24, 2958`; S4 `1, 11, 34, 3438`, plus the airlines, days and floor columns. A0b reproduced these 24-hour rows on the saved model this session.
  - A test on the synthetic model compares signs with A0b.
- [ ] **Step 4: Run; fail, implement, pass.** `.venv/bin/pytest tests/test_record.py tests/test_record_cut.py tests/test_figures_check.py tests/test_frozen.py -q`
  - Approach: index stretches by (direction, airport, `sched_utc`) for `whole`, and by (airline, flight number, direction) for S2. For S1 and S3, keep only the CANCELED stretches, by airline. Without the indexes, S3's scan is every row against every stretch.
  - Then `PYTHONPATH=src .venv/bin/python scripts/figures_check.py --model data/model-2026-11-12` must print A25 "ok" and "signs: 0 differences". The target is about a minute (not measured); if it takes much longer, profile before going on.
- [ ] **Step 5: Mutation entries** (file `RECORD`): "record: S1 for arrivals too", "record: S1 window from the departure's final time", "record: whole ignores a tied number still listed", "record: a number that left read as cancelled afterwards", "record: S2 the earliest before", "record: S3 includes its own slot", "record: S4 late when first seen at the first list", "record: S4 carried when one number shows it", "record: S1 carried only when all show it", "record: a number first seen after the moment read". Run `"record: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: signs S1 to S4, read as of the moment"`).

### Task 7: The sign test, its score, the gate, the re-test and the entry point

Implementer: integration (Opus). Design: "Signs" (the test and the score); "The gate"; "The re-test"; D3; A0b `ratio`; A29; A33. Follows Questions 1 and 2, as answered.

**Files:**
- Modify: `src/timeline/record.py`, `src/timeline/rates.py`, `tests/test_record.py`, `tests/test_rates.py`, `scripts/figures_check.py`, `tests/test_figures_check.py`, `scripts/mutation_check.py`

**Interfaces:**
- Produces, in `timeline.rates`:

```python
LIFT_SE = 2.5

@dataclass(frozen=True)
class Lift: cancelled_with: int; flights_with: int; cancelled_without: int; flights_without: int
            airlines: int; days: int; clears_floor: bool
            times: float | None; times_from: float | None; times_to: float | None; se_log: float | None; passes: bool

def lift(with_: Sequence[Counted], without: Sequence[Counted]) -> Lift   # A0b ratio; se of the log ratio grouped as C8
def passes(clears_floor: bool, lower: float | None) -> bool           # clears_floor and lower > 1
@dataclass(frozen=True)
class Scores: one_rate: float; split: float; gain: float; gain_from: float | None; gain_to: float | None
def scores(with_: Sequence[Counted], without: Sequence[Counted]) -> Scores
    # Brier, in sample; gain = the mean per-flight gain (one rate's squared error minus the split's),
    # gain_from/gain_to = gain -/+ 2 grouped standard errors of it, grouped as C8, the larger (Question 1)
```

- Produces, in `timeline.record`. It imports `timeline.load`, `counting` and `rates` only, and takes the Israel zone from `zoneinfo` itself, so that `test_frozen.py` holds.

```python
TAG = "record-v1"                      # the owner confirms the name at Task 8
COUNTING_START: datetime | None = None # set at Task 8's stop: an Israel midnight, as naive UTC
GATE_CANCELLED, GATE_DAYS, SIGN_ROW = 200, 60, 24

def counted(cells_24: list[Cell], start: datetime) -> list[Cell]       # every number first seen at or after start
def unclosed(flights_: list[Flight], passings_: dict, start: datetime) -> list[datetime]
    # the 24-hour passing moments of counted flights not yet closed (the guard's input)
def gate_reached_at(counted_: list[Cell], unclosed_: list[datetime], start: datetime) -> datetime | None
    # in order of (t, key): the first t + 24 h that is 60 days or more after start, by which 200 were cancelled,
    # and only if no unclosed moment u has u + 24 h <= it (the guard, Question 2); else None
def read_until(counted_: list[Cell], gate_at: datetime | None) -> list[Cell]   # t + 24 h <= gate_at; all when None
@dataclass(frozen=True)
class Result: start: datetime; gate_at: datetime | None; row_cancelled: int; days: float
              signs: dict[str, tuple[Lift, Scores]]
def run(table: list[dict], obs: list[dict], snaps: list[dict], start: datetime) -> Result
def retest_start(first_upload: datetime) -> datetime                   # the next Israel midnight, as naive UTC
def write(result: Result, path: Path, once: bool) -> None
    # json.dumps(sort_keys=True, indent=2) after every float is cut to 12 significant digits (float(f"{x:.12g}"));
    # once=True opens with mode "x"
def main(argv: list[str] | None = None) -> int
    # python -m timeline.record --model DIR --out DIR [--retest SIGN --first-upload 2027-01-10T23:00:00Z]
    # the test: DIR/<TAG>/progress.json on every run, DIR/<TAG>/result.json once, when the gate is reached;
    # the re-test: the same two files under DIR/<TAG>/retest-<SIGN>/, never the main test's;
    # --first-upload must be a UTC time ending in "Z" (else exit 2); exit 2 while COUNTING_START is None;
    # exit 1 when a stored result differs from this run's (both printed)
```

- [ ] **Step 1: Write the failing tests:**
  - `test_the_lift_hand_case`. Airlines A to E in the week of 2026-11-01, airline i on 2026-11-0(2+i). With the sign: A 5 flights, 3 cancelled; B 4, 2; C 6, 2; D 3, 2; E 5, 1. Without it: A 100, 1; B 120, 2; C 90, 0; D 110, 1; E 80, 2. Expected:
    - 10 cancelled of 23 with the sign, against 6 of 500 without;
    - `times == approx(36.2319, abs=1e-4)`, `se_log == approx(0.405866, abs=1e-6)`;
    - `times_from == approx(13.1349, abs=1e-4)`, `times_to == approx(99.9434, abs=1e-4)`;
    - `passes`.

    Checked this session: A0b's `ratio` on these rows gives 36.2, 13.1, 99.9 and passes.
  - `test_scores_hand_case`: the same rows give `one_rate == approx(0.029657, abs=1e-6)` (r(1 - r), as A33 has it) and `split == approx(0.022142, abs=1e-6)`. Both were computed this session in plain Python, since A0b has no Brier query. `gain == one_rate - split`, and `gain_from` and `gain_to` sit 2 grouped standard errors either side, computed by hand on the same rows and written as literals.
  - `test_a_range_that_touches_1_fails`: `passes(True, 1.0)` is False, `passes(True, 1.000001)` is True, `passes(False, 5.0)` is False.
  - `test_the_floor_for_a_sign`: 9 cancelled with the sign gives no times and does not pass.
  - `test_counted_flights_only`: a flight whose numbers include one first seen before the start is not counted.
  - `test_the_gate`:
    - 199 cancelled by day 61 gives None;
    - 200 by day 59 gives None, until the first flight at day 60 or later;
    - the days and the count are taken over every counted flight.
  - `test_flights_after_the_gate_are_not_read_whenever_it_runs`: adding flights scheduled after `gate_at` (a later run) leaves `Result` equal.
  - `test_a_retime_near_the_gate` (Review Focus 1, Question 2). The counted cells reach the count and the 60 days at G. One more counted flight, retimed after its checkpoint, has its 24-hour moment u with u + 24 h ≤ G and is not yet closed: `gate_reached_at` is None. Once that flight is closed (a later run), the gate is declared, and every later run reads the same flights.
  - `test_a_second_run_does_not_replace_the_first`: after the gate, `result.json` stays byte-identical across runs; a run whose own result differs prints both and exits 1.
  - `test_two_runs_under_different_hash_seeds_write_the_same_bytes`: `main` in two subprocesses with `PYTHONHASHSEED` 0 and 1, as `tests/test_timeline_build.py` runs its same-bytes test.
  - `test_the_result_file_is_sorted_with_fixed_floats`: the keys are in sorted order at every level, and no float has more than 12 significant digits.
  - `test_the_retest_counts_only_from_its_own_start`, under `israeli_machine`: `retest_start(datetime(2027, 1, 10, 23, 0)) == datetime(2027, 1, 11, 22, 0)` (01:00 Israel time on 11 January, then the next Israel midnight at UTC+2). A naive conversion on an Israeli machine gives 2027-01-10 22:00, so this catches it. Flights first seen before the re-test's start are not read.
  - `test_a_retest_writes_its_own_folder`: `--retest S3 --first-upload 2027-01-10T23:00:00Z` writes under `DIR/<TAG>/retest-S3/` and leaves `DIR/<TAG>/result.json` byte-identical.
  - `test_first_upload_must_end_in_z`: "2027-01-10T23:00:00", "2027-01-10T23:00:00+02:00" and "yesterday" exit 2, naming the option.
  - `test_main_needs_the_counting_start`: exit 2 and a message naming Task 8 while `COUNTING_START` is None; with a monkeypatched start, `progress.json` is rewritten on every run.
- [ ] **Step 2: Extend the figures check** with A29's dry run (start 2026-11-05 22:00Z): S1 `1, 2, 2, 269`; S2 `1, 9, 2, 515`; S3 `1, 73, 2, 451`; S4 `0, 7, 3, 517`; row cancelled 3; days 4.5; gate not reached. A29's SQL reproduced these on the saved model this session.
- [ ] **Step 3: Run; fail, implement, pass.** `.venv/bin/pytest tests/test_record.py tests/test_rates.py tests/test_figures_check.py tests/test_frozen.py -q`, then the local figures check: every line "ok", exit 0. Every float sum in `rates` and `record` runs with `math.fsum` over groups in sorted key order.
- [ ] **Step 4: Mutation entries:** "record: uncounted flights read", "record: flights after the gate read", "record: gate at 199", "record: gate without the 60 days", "record: gate declared before the row is closed" (the guard dropped), "rates: lift range at 2 standard errors", "rates: a range touching 1 passes", "rates: lift without the floor", "rates: split scored with the one rate", "rates: gain range from the plain standard error", "record: a second run replaces the first", "record: result keys unsorted", "record: floats written in full", "record: the re-test counts from the first start", "record: re-test start at the upload", "record: re-test start from a naive conversion", "record: re-test written over the main result", "record: first upload without Z accepted". Run `"record: " "rates: "` alone. Expected: all CAUGHT.
- [ ] **Step 5: Review (Opus), then commit** (`git commit -m "q21: the sign test, the gate and the re-test"`).

### Task 8: The freeze (stop)

Implementer: transcription (Sonnet) for the constant; the main session runs the stop. Design: D5; "The record" (conditions 1 and 2, "What counts", "What makes the freeze checkable"). The commit this task ends with is the frozen-rule commit: the first in which C1 to C8, the four signs, the sign test with its score, the gate and the re-test run from the model as tested code, with the counting start written in.

**Files:**
- Modify: `src/timeline/record.py` (`COUNTING_START`, and `TAG` if renamed), `tests/test_record.py`, `scripts/mutation_check.py`

- [ ] **Step 1: Whole-branch review (Fable)** of Tasks 1 to 7, by a fresh reviewer given this plan and the design, not the build's reasoning. Fold in each finding once it is checked against its source, then re-run the tests of the files touched.
- [ ] **Step 2: Checks**, in this order:
  - `.venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95` passes, `tests/test_frozen.py` with it;
  - `.venv/bin/python scripts/mutation_check.py` alone gives "Every mutation was caught.";
  - `PYTHONPATH=src .venv/bin/python scripts/figures_check.py --model data/model-2026-11-12` exits 0.
- [ ] **Step 3: Stop.** Report the three results to the owner. The owner decides:
  - the counting start, an Israel midnight later than the moment the tag will be pushed;
  - the tag's name (`record-v1` proposed);
  - the go for the tag and its push.
- [ ] **Step 4: Write the value** as naive UTC: an Israel midnight in winter time is 22:00 UTC the day before.
  - Add `test_the_counting_start_is_an_israel_midnight`: `words.il_time(COUNTING_START)` has hour, minute and second 0. A test may import `words`; the frozen modules may not.
  - Add the mutation "record: counting start an hour off".
  - Run `.venv/bin/pytest tests/test_record.py -q` (passes), and `.venv/bin/python scripts/mutation_check.py "record: counting start"` alone (CAUGHT).
- [ ] **Step 5: Commit** (`git commit -m "q21: record v1, the frozen rule, counting from <Israel date>"`).
  - The owner tags this commit (`git tag -a record-v1 -m "…" <sha>`) and pushes the branch and the tag before the counting start.
  - If the push comes at or after the counting start, the commit does not count: a later value, a new commit and a new tag.
  - Pushing the tag should start a public CI run that the hosting service dates (`.github/workflows/ci.yml`: `on: push` with no filter). That a tag push starts one is UNVERIFIED; the owner confirms when pushing.

### Task 9: `display.py`, C9, C10 and the front page's figures

Implementer: integration (Opus). Design: C9; C10; "Words" (the count line and the late line); A3; A17; A24. Not frozen.

**Files:**
- Create: `src/timeline/display.py`, `tests/test_display.py`
- Modify: `scripts/figures_check.py` and `tests/test_figures_check.py` (A3, A17), `scripts/mutation_check.py` (`DISPLAY = ("src/timeline/display.py", ["tests/test_display.py"])`)

**Interfaces:**
- Consumes: `counting.Flight`, `flights`, `figures`, `last_sighting`; `words` label names and `words.il_time`.
- Produces, in `timeline.display`:

```python
def label(f: Flight, by_id: dict[str, dict], last_fetch: datetime) -> str   # C10, rules 1 to 4
def delayed(f: Flight, delayed_ids: set[str]) -> bool                       # C10's DELAYED: any number showed it
def warning_number(f: Flight, by_id: dict[str, dict]) -> str | None         # C9: None unless the flight is cancelled

@dataclass(frozen=True)
class Summary:
    figures: counting.Figures
    unknown: int; unknown_gap: int; unknown_no_final: int   # closed flights with no known result (A3's split)
    late_after: int; late_holds: int; late_unplaced: int; late_before: int   # A17, by C9's number
    first_record: date                                      # Israel date of the first list

def summary(table: list[dict], obs: list[dict], snaps: list[dict]) -> Summary
```

- [ ] **Step 1: Write the failing tests:**
  - C10:
    - `test_a_flight_with_a_number_still_listed_is_upcoming_until_it_departs`: one number canceled and one open gives UPCOMING (scheduled after the last fetch) or NO FINAL UPDATE (before it). Once that number departs, DEPARTED; for an arrival, LANDED. Review Focus 2's label is this case after 48 hours.
    - `test_cancelled_only_when_no_number_is_listed_otherwise`: canceled with vanished gives CANCELLED; all unknown gives UNKNOWN.
    - `test_delayed_when_any_number_showed_it`.
  - C9, `test_the_warning_number_is_the_first_listed_as_cancelled`: the earliest `canceled_first_seen_at` wins, then airline and number on a tie; None for a flight that is not cancelled.
  - `test_unknown_counted_beside`: gap 2, vanished 1 and dropped 1 give `unknown == 4`, `unknown_gap == 2`, `unknown_no_final == 2`.
  - `test_the_late_line_from_the_bracket`, on C9's number:
    - `cancel_lead_max_min < 0` counts "after";
    - `lead_min < 0 <= lead_max` counts "holds";
    - `cancel_lead_censored` counts "unplaced";
    - anything else counts "before".
  - `test_the_first_record_is_the_israel_date`, under `israeli_machine`: a first fetch at 2026-10-27 22:30 UTC gives 28 October. A naive conversion gives 27 October.
  - Figures check: `EXPECTED["A3"]` `240, 27 + 2` and `EXPECTED["A17"]` `9, 1, 19, 52`, which A0's SQL reproduced this session.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_display.py tests/test_figures_check.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the local figures check: every line "ok", exit 0.
- [ ] **Step 5: Mutation entries** (file `DISPLAY`): "display: cancelled label before still listed" (rule 3 before rule 2, which `test_a_flight_with_a_number_still_listed_is_upcoming_until_it_departs` must catch), "display: DELAYED from the first number only", "display: warning from the last cancellation", "display: late line from the last cancelled number", "display: censored brackets counted as after", "display: gap and no-final-status counts swapped", "display: first record from the UTC date". Run `"display: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: rules C9 and C10, and the front page's figures"`).

### Task 10: `flights.py` lists by C1, C9 and C10

Implementer: integration (Opus). Design: "What it changes" (the "Who is a flight", "Labels", "Warning" and "Codeshares" bullets, the story box); "Day pages, the chart, the cancellation lists".

**Files:**
- Modify: `src/timeline/flights.py:134-203`, `tests/test_timeline_flights.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `counting.flights`, `flight_of`, `last_sighting`; `display.label`, `delayed`, `warning_number`.
- Produces, in `timeline.flights`. `headline_counts` is removed, because the total comes from `display.summary`.

```python
@dataclass(frozen=True)
class ListFlight:            # one flight under C1, as the lists show it
    rows: tuple[Row, ...]    # its numbers, in row order
    label: str; delayed: bool    # C10
    lead: Row                # C9's number when cancelled, else rows[0]
    day: date

def group_flights(rows: list[Row], table: list[dict], last_fetch: datetime) -> list[ListFlight]
def partners(lists: list[ListFlight], table: list[dict]) -> dict[str, tuple[Row, ...]]
    # the flight's other numbers with the same last expected time, terminal and desks
def others(lists: list[ListFlight]) -> dict[str, tuple[str, tuple[Row, ...]]]
    # for a row labelled CANCELLED in a flight that is not: ("departed" | "landed" | "is still listed", the rows named)
def day_infos(flights_: list[ListFlight], last_fetch: datetime, partial_days: set[date]) -> list[DayInfo]
def featured(flights_: list[ListFlight], censored: dict[str, bool]) -> Row | None      # among CANCELLED flights, through lead
def recent_cancellations(flights_: list[ListFlight], n: int = 10) -> list[ListFlight]
```

- [ ] **Step 1: Rewrite the tests.** The split tests are retired with the split they tested: `test_members_with_different_labels_are_separate_flights`, `test_a_member_shown_delayed_is_its_own_flight`, `test_members_with_different_warnings_are_separate_flights`, `test_partners_are_the_other_members_of_the_flight_after_the_split`, and the two `headline_counts` tests. New tests:
  - `test_lists_group_by_c1`;
  - `test_a_list_labels_a_flight_by_c10`: LH 0691A with LH 695 departed gives DEPARTED;
  - `test_a_cancelled_flights_warning_is_c9s`;
  - `test_the_story_picks_among_c10_cancellations_through_c9`: a number listed as cancelled inside a departed flight is never featured;
  - `test_partners_share_time_terminal_and_desks`: OS 1083 is not OS 083's partner;
  - `test_others_name_who_departed_landed_or_is_still_listed`;
  - `test_day_counts_and_the_chart_count_c10_flights`.

  Kept as they are: the anchor, address, search and `make_rows` tests.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_flights.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries.** Run `"flights: "` alone. Expected: all CAUGHT, and none STALE.
  - Retire: "flights: group split ignores the label", "flights: split ignores delayed", "flights: split ignores the warning", "flights: headline counts upcoming flights", "flights: headline leaves out a flight due at the last record".
  - Add: "flights: lists by codeshare group", "flights: a list labels a flight by its first number", "flights: story from a number's own label", "flights: partners tied by airline alone", "flights: day counts from numbers".
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: lists count and label flights by rules C1, C9 and C10"`).

### Task 11: `words.py`, the approved sentences

Implementer: transcription (Sonnet). Design: "Words" (every bullet, verbatim); C8's rounding (from `rates`); Question 4 as answered.

**Files:**
- Modify: `src/timeline/words.py:258-273` (replace `one_in` and `headline`), `tests/test_timeline_words.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `rates.Rate`, `round_middle`, `round_range`; `display.Summary`, imported for type hints only (under `TYPE_CHECKING`), because `display` imports `words`' label names.
- Produces, in `timeline.words`:
  - Constants, verbatim:
    - `PAST_ONLY`, `FROM_HERE_HEADING`, `FROM_HERE_FIRST`;
    - `FROM_HERE_COLUMNS` (the four heads);
    - `CHECKPOINT_NAMES` (`{70: "70 hours", …}`);
    - `UNDER_TABLE` (the three lines);
    - `TOO_FEW = "too few so far to say"`;
    - `MORE_THAN_3_DAYS` (that line's first sentence, Question 4e);
    - `LEAD_INS` (`{70: "between 2 and 3 days", 48: "between 1 and 2 days", 24: "between 12 and 24 hours", 12: "between 6 and 12 hours", 6: "between 3 and 6 hours", 3: "under 3 hours"}`);
    - `A_FLIGHT` (the "How this works" paragraph).
  - `one_in_range(rate: Rate) -> str | None`: "1 in 100 (between 1 in 45 and 1 in 200)"; None below the floor.
  - `total(rate: Rate) -> str`; `count_line(s: Summary) -> str`; `late_line(s: Summary) -> str | None` (None at a count of zero, Question 4h).
  - `pair(h: int, rate: Rate) -> str | None`; `condition(updated: datetime) -> str`; `has_passed(updated: datetime) -> str`. `updated` is the model's naive UTC.
  - `another_number(verb: str) -> str`: the sentence up to the colon; the view adds the linked names and the full stop.
  - `BRACKET = "is listed as cancelled"`.
- [ ] **Step 1: Write the failing tests**, one exact-text test per sentence, with the design's values:
  - `total(rate)` == "So far, 81 of 4,658 flights with a known outcome were listed as cancelled. That's about 1 in 60 (between 1 in 35 and 1 in 95)."
  - Below the floor (Question 4d): "So far, 3 of 120 flights with a known outcome were listed as cancelled. Too few so far to say."; with none cancelled, "So far, 0 of 900 flights with a known outcome were listed as cancelled. Too few so far to say."
  - `one_in_range` gives A35's lines for the total and the 70- to 6-hour rows. For the 3-hour row it gives "1 in 230 (between 1 in 110 and 1 in 460)" ("Design and code", 2). For N = 1,100 it gives "1 in 1,100" (Question 4g).
  - `pair(24, …)` == "This flight has between 12 and 24 hours to go. So far, of all flights at the airport still listed normally with 24 hours to go, about 1 in 100 (between 1 in 45 and 1 in 200) were later listed as cancelled."
  - `condition(datetime(2026, 11, 12, 10, 16, 45))` == "The figure is for flights the airport's list showed normally. This page was last updated 12 Nov 2026, 12:16 and cannot say what the list shows now. Check the airport's own list.", under `israeli_machine`.
  - `has_passed(…)`.
  - `count_line(…)`: the design's sentence with 4,658, 27 October 2026, 269, 240 and 29.
  - `late_line`: "At least 9 of the 81 cancelled flights were listed as cancelled only after their scheduled time."; None at zero.
  - `another_number("departed")` == "Listed as cancelled. Another flight number with the same scheduled time and airport departed:", and likewise for "landed" and "is still listed".
  - Every constant against the design's text.

  The old `one_in` and `headline` tests are retired.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_words.py -q`
- [ ] **Step 3: Implement.** Counts and every N carry thousands separators.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries.** Run `"words: "` alone. Expected: all CAUGHT, and none STALE.
  - Retire: "words: one_in without halves up", "words: headline without thousands separators".
  - Add: "words: a rate without its range", "words: a range shown below the floor", "words: lead-in of the wrong checkpoint", "words: condition in UTC", "words: count line without separators", "words: 1 in N without separators", "words: late line at zero".
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: the approved words for rates"`).

### Task 12: `check.py`, four new upload-check rules

Implementer: transcription (Sonnet). Design: "Tests and checks", the upload check.

**Files:**
- Modify: `src/timeline/check.py`, `tests/test_timeline_check.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `words.PAST_ONLY`.
- Produces, in `timeline.check`:
  - `ODDS_WORDS`: the whole words chance, chances, odds, probability, likely, unlikely, risk, forecast, forecasts, predict, predicts and prediction, case-insensitive. They are applied in `_word_hits` (`check.py:73-81`) to `.html` pages other than `EXPLAINER`, after the `DATA` mask, so the airport's strings are skipped as today.
  - `rate_hits(text: str) -> list[str]`. On the tag-stripped text, remove every "1 in N (between 1 in A and 1 in B)", then every bare "(between 1 in A and 1 in B)". Any "1 in N" left is a hit. N is `\d[\d,]*`, matched case-sensitively.
  - `"%"` in the tag-stripped text of an `.html` page is a hit.
  - `missing_notices` also names "record line" for an `.html` page whose text holds "1 in N" but not `PAST_ONLY`.
- [ ] **Step 1: Write the failing tests:**
  - each odds word is refused on `index.html` and passes on `how-it-works.html`;
  - `test_rates_pass_only_with_their_range`: "1 in 100 (between 1 in 45 and 1 in 200)" and "1 in 1,100 (between 1 in 900 and 1 in 1,400)" pass; "1 in 100" alone, and "1 in 100 (between 1 in 45)", are hits;
  - `test_a_percent_sign_in_page_text_is_refused`, with `&#37;` caught too;
  - `test_a_page_with_a_rate_needs_the_record_line`;
  - `test_the_designs_pass_cases`, each its own test:
    - "risky" inside an airline's data span;
    - "100%" inside `style.css`;
    - `width="72%"` inside the chart's SVG;
    - "(LH 0691A is listed as cancelled)" before "Athens": the existing "cancelled at" rule does not fire.

  Today's built pages hold none of the refused words and no percent sign in their text. That is the design's finding; the page code was grepped again this session and holds none of the words.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_check.py tests/test_publish.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:** "check: odds words allowed", "check: odds words as substrings", "check: odds words on how-it-works", "check: a rate without its range passes", "check: a bare range excuses every rate" (removal order swapped), "check: thousands separators break a rate", "check: percent signs allowed", "check: percent read in attributes", "check: record line not required". Run `"check: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: the upload check refuses rates without ranges"`).

### Task 13: `views.py`, the front page and the lists

Implementer: integration (Opus). Design: "Pages", Front page; "Day pages, the chart, the cancellation lists".

**Files:**
- Modify: `src/timeline/views.py`, `src/timeline/static/style.css` (the stacking rule in the `@media (max-width: 600px)` block), `tests/test_timeline_views.py`, `tests/test_timeline_style.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `flights.ListFlight`, `others`; `words` (Task 11); `display.Summary`.
- Produces:
  - `front_page(summary: Summary, story: Row | None, recent: list[ListFlight], chart_days: list[DayInfo], all_days: list[DayInfo], entries: list[dict], last_record: datetime) -> str`;
  - `from_here(summary: Summary) -> str`;
  - `day_page` and `cancellations_page`, taking `list[ListFlight]`.
- [ ] **Step 1: Rewrite the tests:**
  - `test_front_page_order`: the band, the search box, the "From here to the scheduled time" block, the tiles and the total, the story, recent cancellations, the chart, the day list and the built-by line.
  - `test_the_block`, in order:
    - the heading and the first line;
    - `<table class="fromhere">` with the four heads and six rows; the 24-hour row reads "24 hours", "3,449", "35", "1 in 100 (between 1 in 45 and 1 in 200)";
    - `PAST_ONLY`, the three lines, the count line and the late line.

    The table needs no `<script>`.
  - `test_a_row_below_the_floor_shows_its_counts_and_too_few_so_far_to_say`.
  - `test_the_tile_prints_its_range_right_after_it`: the page text holds "1 in 60 (between 1 in 35 and 1 in 95)", and the range may sit in a `<small>`.
  - `test_below_the_floor_no_third_tile` (Question 4f).
  - `test_a_model_below_the_floor_everywhere` (Review Focus 3): no "(between" anywhere on the page, "too few so far to say" shown, and `check.rate_hits` empty.
  - `test_day_rows_name_every_number_with_the_bracket`: "LH 695 (LH 0691A is listed as cancelled)", with the bracket before the route.
  - `test_cancellations_show_c9s_warning`.
  - In `tests/test_timeline_style.py`: the `.fromhere` table's parts are `display: block` under 600 px, as `.cancellations` is.
  - The headline tests (`test_front_page_headline`, `test_front_page_tiles_show_the_headline_counts`, `test_front_page_tiles_and_sentence_share_their_rounding_and_separators`, `test_no_headline_without_cancellations`, `test_front_page_without_cancellations`) are rewritten to the total.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py tests/test_timeline_style.py -q`
- [ ] **Step 3: Implement.** Every new number goes through `e()`, and every flight number through `d()`.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries.** Run `"views: " "style: "` alone. Expected: all CAUGHT, and none STALE.
  - Retire or rewrite: "views: headline at zero", "views: ratio tile rounded its own way", "views: cancelled tile shows the known count".
  - Add: "views: search after the block", "views: tile without its range", "views: third tile below the floor", "views: record line left out of the block", "views: bracket left out", "views: list row labelled by its first number", "style: from-here table never stacks".
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: the front page leads with the from-here table"`).

### Task 14: `views.py`, the flight page's block and How this works

Implementer: integration (Opus). Design: "Pages", Flight page and How this works; Appendix A of this plan.

**Files:**
- Modify: `src/timeline/views.py:164-207` and `views.py:266-295`, `tests/test_timeline_views.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `words.pair`, `condition`, `has_passed`, `MORE_THAN_3_DAYS`, `another_number`, `BRACKET`, `A_FLIGHT`; `flights.others`. `build.render` passes in `record.TAG` and `record.COUNTING_START`.
- Produces: `flight_page(rows, partners, others, since, summary, updated) -> str` and `how_it_works_page(attribution, gaps, tag, counting_start) -> str`. A row labelled UPCOMING carries the block above its `<details>`, with the "has passed" line right after it:

```html
<div class="fromhere" data-sched="2026-11-13T08:00:00Z">
  <ul><li data-after="48" data-upto="72">…pair…</li> … </ul>    <!-- six, or fewer below the floor (Question 4c) -->
  <p class="more" hidden>More than 3 days to go: the airport's list does not show the flight yet.</p>
  <p>…condition…</p> <p>…PAST_ONLY…</p>
</div>
<p class="passed" hidden>This flight's scheduled time has passed. …</p>
```

  `data-sched` is `sched_utc_final` written as `%Y-%m-%dT%H:%M:%SZ`. A page with a block loads `<script src="../fromhere.js" defer>`.
- [ ] **Step 1: Write the failing tests:**
  - `test_the_block_on_upcoming_rows_only`: rows labelled DEPARTED, CANCELLED or UNKNOWN get none.
  - `test_the_scheduled_instant_is_the_models_utc`, under `israeli_machine`: a row with `sched_utc_final` 2026-11-13 08:00 gives `data-sched="2026-11-13T08:00:00Z"`.
  - `test_without_javascript_all_pairs_show`: no `hidden` on the six `<li>`, and the "has passed" line hidden.
  - `test_a_pair_below_the_floor_is_left_out` (Review Focus 3, Question 4c): the block holds five pairs, and the page passes `check.rate_hits`.
  - `test_the_passed_line_sits_outside_the_block`.
  - `test_another_number_line`: "Listed as cancelled. Another flight number with the same scheduled time and airport departed: LH 695.", with LH 695 linked.
  - `test_the_partner_sentence_names_only_time_terminal_and_desks_partners`.
  - `test_fromhere_js_only_on_pages_with_a_block`.
  - `test_how_it_works_is_appendix_a_verbatim`, rewritten to this plan's Appendix A, with the counting start's Israel date and the tag filled in.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:** "views: block on a cancelled row", "views: scheduled instant in Israel time", "views: pairs hidden without JavaScript", "views: passed line inside the block", "views: another-number line left out", "views: condition line left out", "views: fromhere.js on every flight page". Run `"views: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: the flight page's from-here block"`).

### Task 15: `static/fromhere.js`

Implementer: transcription (Sonnet). Design: "Pages", Flight page (`docs/flight-lookup.md:248-250`); "Tests and checks", `fromhere.js`.

**Files:**
- Create: `src/timeline/static/fromhere.js`, `tests/test_timeline_fromhere.py`
- Modify: `scripts/mutation_check.py` (`FROMHERE = ("src/timeline/static/fromhere.js", ["tests/test_timeline_fromhere.py"])`)

**Interfaces:**
- Consumes: Task 14's markup.
- Produces, as a Node `module.exports`: `pick(schedIso: string, nowMs: number, bounds: Array<[after, upto]>) -> number | "more" | "passed" | "none" | null`. It returns:
  - the index of the pair with after < hours left ≤ upto;
  - "more" above the top `upto`;
  - "passed" at zero or less;
  - "none" when the fitting pair was left out below the floor (Question 4c);
  - null for a missing or unreadable `schedIso`.

  The page hook runs on `DOMContentLoaded`. For each `.fromhere`:
  - an index: hide every pair but that one;
  - "more": show `.more`;
  - "passed": hide the whole block and show the `p.passed` right after it (`docs/flight-lookup.md:249`);
  - "none": hide every pair;
  - null: change nothing.

  It writes no text.
- [ ] **Step 1: Write the failing tests**, under Node and skipped visibly without it, as `tests/test_timeline_search.py` is:
  - `test_each_boundary_between_lead_ins`:
    - 72 h left gives the (48, 72] pair, and 72 h and 1 ms gives "more";
    - 48, 24, 12, 6 and 3 h each fall in their lower pair;
    - 1 ms gives (0, 3], and 0 gives "passed".
  - `test_a_passed_time_hides_the_block_and_shows_the_passed_line`, against a stand-in page like the search test's `PAGE`.
  - `test_a_left_out_pair_shows_none`: with the 24-hour pair missing from `bounds`, 20 h left gives "none".
  - `test_a_missing_or_unreadable_attribute_leaves_the_list_showing`, against the stand-in page.
  - `test_the_same_result_under_three_time_zones`: run with `TZ=Asia/Jerusalem`, `TZ=UTC` and `TZ=America/Los_Angeles`. Checked this session: Node 24 parses an ISO time ending in Z as the same instant in all three, and one without Z as local time.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_fromhere.py -q`
- [ ] **Step 3: Implement.** Parse with `Date.parse`, and refuse a string that does not end in "Z".
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:** "fromhere: a boundary belongs to the upper lead-in", "fromhere: a time without Z read as local", "fromhere: passed a minute early", "fromhere: passed hides only the list", "fromhere: hides the list on a bad attribute", "fromhere: never shows more than 3 days". Run `"fromhere: "` alone. Expected: all CAUGHT.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: fromhere.js picks the prepared sentence by the visitor's clock"`).

### Task 16: `build.py` wiring and the site-wide tests

Implementer: integration (Opus). Design: "How it is built"; "Tests and checks", words and pages. Follows Question 3, as answered.

**Files:**
- Modify: `src/timeline/build.py` (`render`), `tests/test_timeline_build.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: everything above.
  - `render(table, obs, snaps) -> dict[str, str]` gains `fromhere.js` in the static files written.
  - The front page's figures come from `display.summary`, and the lists from `flights.group_flights`.
  - `build` imports `record` and passes `TAG` and `COUNTING_START` to `views.how_it_works_page`.
- [ ] **Step 1: Rewrite the tests.**
  - `test_the_headline_counts_only_flights_whose_scheduled_time_has_passed` becomes `test_the_total_counts_closed_flights`.
  - New:
    - `test_the_chart_counts_equal_the_day_pages`;
    - `test_over_days_whose_flights_are_all_closed_the_day_pages_sum_to_the_total` (Question 3's case left out);
    - `test_a_closed_flight_still_listed` (Review Focus 2): labelled NO FINAL UPDATE on its day page, and counted as cancelled in the total;
    - `test_a_fresh_small_model_passes_the_upload_check` (Review Focus 3): `check.scan` and `missing_notices` empty, and no "(between" on any page;
    - `test_fromhere_js_is_written`.
  - Kept: `test_only_html_css_and_js_besides_the_marker`, and the same-bytes tests across processes, unchanged in substance.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the timeline suite; pass.** `.venv/bin/pytest tests/test_timeline_*.py -q`
- [ ] **Step 5: Mutation entries.**
  - Retire: "site: headline counted up to the first record".
  - Add: "site: fromhere.js not written", "site: total from flights whose time has passed", "site: chart counted from numbers".
  - Run `"site: "` alone, then the full check once: `.venv/bin/python scripts/mutation_check.py`, with no STALE entries.
- [ ] **Step 6: Review (Opus), then commit** (`git commit -m "q21: build the site from the counting module"`).

### Task 17: Documents

Implementer: transcription (Sonnet). Every claim is checked against the code as built.

**Files:**
- Modify:
  - `docs/site-redesign.md`:
    - "Who is a flight", "Labels", "Warning" and "Codeshares" each get a line pointing to the rule in `docs/flight-lookup.md` that replaces or extends it;
    - front-page items 2 to 4 follow the new order;
    - "Look": "no script but `search.js`" becomes the two scripts;
    - "Tests and checks": the split test retired, and the headline tests rewritten;
    - the non-goal "Cancellation odds or forecasts" points to "The gate".
  - `docs/flight-lookup.md`: the status line names this plan, and that the build is done.
  - `docs/README.md`: one line each for `flight-lookup.md`, `flight-lookup-figures.md` and `flight-lookup-plan.md`.
  - `docs/operations.md:97`: the Node sentence also names `tests/test_timeline_fromhere.py`. The test and mutation counts, there and in `README.md:27` and `README.md:56`, are written in Task 18 from its own runs.
- Not in this task: the A35 correction ("Design and code", 2), which the main session makes outside this plan.
- [ ] **Step 1: Update the documents.**
- [ ] **Step 2: Review (Opus), then commit** (`git commit -m "q21: documents follow the flight lookup"`).

### Task 18: Final verification

Implementer: the main session.

- [ ] **Step 1:** `.venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95`. Expected: every test passes and coverage is 95% or more; record the count.
- [ ] **Step 2:** `.venv/bin/python scripts/mutation_check.py`, alone. Expected: "Every mutation was caught."; record the count.
- [ ] **Step 3:** `.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`, as CI runs it. Expected: no output.
- [ ] **Step 4:** `PYTHONPATH=src .venv/bin/python -m timeline.build --model data/model --out site`, then `PYTHONPATH=src .venv/bin/python -m timeline.check site`. Expected: exit 0.
- [ ] **Step 5:** `PYTHONPATH=src .venv/bin/python scripts/figures_check.py --model data/model-2026-11-12`. Expected: every line "ok", exit 0.
- [ ] **Step 6:** Open `site/index.html` and a flight page with an UPCOMING row by hand, at 375 px and at desktop width, light and dark. Expected: no sideways scroll; the table stacks; one pair shows with JavaScript and all six without it.
- [ ] **Step 7: Counts.** Write Steps 1 and 2's counts into `README.md:27`, `README.md:56` and `docs/operations.md:97`, replacing 665 tests and 274 mutations, all caught. Commit (`git commit -m "q21: README and operations notes: test and mutation counts"`).
- [ ] **Step 8: Whole-branch review (Fable)** of Tasks 9 to 17, by a fresh reviewer. Fold in each finding once it is checked against its source, then repeat Steps 1 to 5 for anything touched. The push is the owner's.

## Appendix A: "How this works", new sections (approved by me, 2026-11-12)

The sections are placed after "Probably the same flight".
- `{START}` is `record.COUNTING_START` as an Israel date, written as the lede writes "27 October 2026".
- `{TAG}` is `record.TAG`, linked to `{CODE_URL}/tree/{TAG}`. That this address shows a tag is UNVERIFIED until the tag is pushed.
- The gate's two conditions and the test's rule are the design's words, quoted.

> ## A flight
> Flight numbers with the same scheduled time and airport are counted as one flight when the list shows the same expected time, terminal and check-in desks for them. A number that did not depart or land is counted with a number of its own airline, or one with its own desks. A flight counts as departed or landed when any of its numbers did, and as cancelled only when none did and at least one was listed as cancelled.
>
> ## What is counted
> A flight is counted two days after its scheduled time, so that all the flights of one hour are counted together, whatever happened to them. A flight that left the list with no final status, or while nothing was recorded, has no known outcome. It is left out of every figure, and how many there are is given beside the figures.
>
> ## Why every figure is a range
> Cancellations come in runs: an airline cancels several flights in the same week, and a bad day hits many flights at once. So each figure comes with a range wide enough to allow for both. A figure is shown only when it rests on at least 10 cancelled flights, from at least 5 airlines and 5 days; below that, the page gives the counts and says there are too few so far to say.
>
> ## Why three days
> The airport's list shows a flight from about three days before its scheduled time, so the table starts at 70 hours to go. A flight that is already listed as cancelled when it first appears is almost never seen, so every figure is about flights that reached the list normally.
>
> ## Why the later rows hold more flights
> Flights whose first days on the list fell before the records began, or in the gap from 27 to 29 October, were seen only in their last hours. They are in the later rows of the table and not in the earlier ones.
>
> ## Signs under test
> No figure is given for one flight yet. I am testing four signs that might go with a later cancellation: a flight of the same airline from the same airport, scheduled to land 30 minutes to 12 hours before a departure, listed as cancelled; the same flight number's previous flight listed as cancelled; another flight of the same airline, scheduled within a day either side, listed as cancelled; and a flight number first listed less than two days before its scheduled time. The rules were fixed beforehand, in the code tagged [{TAG}]({CODE_URL}/tree/{TAG}). The counted flights are those first listed from {START}, the counting start; the 24-hour row is the table's row for 24 hours to go, and its checkpoint is that moment.
>
> A sign may change what this site shows only when both of these hold:
> 1. The count. Take the counted flights of the 24-hour row in the order of the scheduled time they showed at the checkpoint. The gate is reached at the first such time that is at least 60 days after the counting start and by which 200 of those flights were later listed as cancelled. The days and the count are taken over every counted flight in the row.
> 2. The sign has passed its test, read on the counted flights scheduled up to that time.
>
> The lift is the rate with the sign over the rate without it. Its range is 2.5 standard errors of its logarithm either side, grouped as the ranges above are. 2.5, not 2, because four signs are tested at once. A sign passes when it clears the floor (10 cancelled flights with the sign, from 5 airlines and 5 days) and the whole range lies above 1. A sign that fails stays failed for this version.

## Deviations

The executor appends here whenever reality forces a change from this plan: what changed, why, and the commit.

- 2026-11-12, before Task 1 (pre-flight scan): the clock test's retime moved from 1 Nov 11:00 to 1 Nov 13:00. Seen at 11:00, before the old 24-hour moment, a reading by the final scheduled time gave the same passing, so the mutation "the clock from the final scheduled time" could not be caught.
- 2026-11-12, the owner: every implementer on Opus, Task 1 included (marked architecture above); Fable stays for the two whole-branch reviews and for fix rounds 4 and 5.
- 2026-11-12, Task 1 Part 1 (b0ddbc1): `counting_helpers.board` takes no `gaps=` keyword; it works each gap out from the fetch and sighting times as the model does, which no later task contradicts. `_utc` stays in `build.py`: it sat inside the brief's line range but is not part of the loader. The carry-forward reading's "next download after the last sighting" is the next kept snapshot's `fetched_at`: kept snapshots are all the loaded model holds, R9 already folds unchanged and repeated downloads into `confirmed_until`, and a cut build drops the same downloads (reviewed against `src/model/rules.py`, `snapshot_files` and `sightings`).
- 2026-11-12, Task 1's stop: the owner ruled for A0's reading, with its differences from cut builds as stated limits (design, "The record", "Measured and ruled"). Step 10 therefore removes the carry-forward reading from `counting.py` (`READINGS`, `READING` and the carry option), with its tests and mutation entries, and makes `tests/test_record_cut.py` assert the measured differences under A0, the ruling quoted. Pre-flight item 3 (re-deriving A0 for carry-forward) does not arise.
- 2026-11-12, Task 1 Step 10 (the ruling applied): removed from `counting.py` `READINGS`, `READING`, the carry-forward branch and the `reading` and `snaps` parameters of `stretches`, which by A0's rule reads only the flights table and the observations (a number's last stretch ends a second after its `last_seen_at`); removed from the tests `test_carry_forward_runs_the_last_stretch_to_the_next_download`, the reading-constant test (the checkpoints keep a test of their own), the mutation entry "counting: carry-forward ends a second after the last sighting", `test_a0_against_carry_forward_at_the_moment`, `test_carry_forward_matches_at_the_moment` and the two `leaves-between-downloads` cases. `tests/test_record_cut.py` now reads both models by A0's rule and asserts, with the ruling quoted, exactly the 14 differences measured: leave-and-return at 11:30 (a stretch and a 24-hour passing), the same-number key at 11:15, 11:22 and 11:30 (first record, stretches, retime chain and C1 inputs), and C1's inputs read at the end in `retime-at-the-cut` (11:00, 11:07) and `flight-changes-after` (12:00, 12:07). Any other difference fails. `hole-in-progress` passes under A0 with no accepted difference.
- 2026-11-12, after Task 1's review: the two `leaves-between-downloads` cases are kept as Step 7 cases read by A0. In the first, LY 300's 24-hour moment, 11:07, falls between its last sighting (the 11:00 download) and the next download; in the variant, between the unchanged receipts at 11:04 and 11:08. Step 10 had removed them as carry-forward-only, which was wrong; both pass with no accepted difference. The comparison now keys numbers by `flight_id` and chains by `key_id`, compares full values, and names numbers only in failure messages; the accepted list is the same 14 differences.
- 2026-11-12, after Task 3's review (on 9e1daad): three mutation entries beyond the brief's eleven, "counting: no desks counts as the same desks", "counting: the fallback leaves every number alone" and "counting: the fallback keeps the numbers that did not operate together"; and `test_a_chain_never_joins_two_departed_numbers_apart` gains LY 002's departed partner (DL 6002) and a second LY number listed as cancelled, so the fallback's regroup is tested.
- 2026-11-12, after Task 4's review (on 2834b7f): `cells` reads a passing with no status as A0's `cell` reads NULL (NULL <> 'CANCELED' is NULL): it puts its flight in no row and sets no moment; an empty status stays listed normally. A fifth mutation entry beyond the brief's four, "counting: a passing with no status puts its flight in the row", with `test_a_passing_with_no_status_puts_its_flight_in_no_row`; the models of 2026-11-12 hold no NULL status, so the figures do not move. The fixture's oracle, which computed `test_the_hand_computed_fixture`'s literals with A0's SQL, is committed as `scripts/counting_fixture_oracle.py` (not run in CI).
- 2026-11-12, Task 4's fix round: a known difference between A0's SQL and the code, kept. A0's `cp` takes the moment and the status with two separate `arg_min` calls, and DuckDB's `arg_min` skips a NULL value, so when a number's first passing of a checkpoint has no status and a retime makes it pass again, A0 pairs the first moment with the later passing's status. The code reads that first passing as having no status and counts nothing for it, which is C6's wording ("listed with a status other than cancelled"). Neither saved model has an observation with no status, so the figures cannot differ today; the figures check (Task 5) would show it if they ever did.
- 2026-11-12, after Task 5's review (on 0415417): three mutation entries beyond the brief's three, "figures: a cell difference not reported", "figures: cells compared on one side only" and "figures: a found difference does not fail"; the cell, duplicate and path checks: `compare_cells` tested on four planted differences and `main` on a planted flight and cell difference, both comparisons naming a duplicate (a number in two flights, a flight twice in one row), and `run_sql` refusing an A0 that reads no `'data/model/` path; and five extra cases in the synthetic model (LY 541's earlier passing, A3 931's second passing, TP 1735 across the closed line, LY 730's grouping airline, LY 1105's last second) with one download missed (an hour between two, not a hole), so that `tests/test_figures_check.py` alone catches 23 of the 29 "counting: " mutants.
- 2026-11-12, Task 6: `compare_signs(con, cells_, carried)` compares the code with A0b's `signcell` rows where `present` is true, as (sign, row, the flight's numbers), S1 to S4 matched by the start of their names and the dropped X signs left out, not with the whole `sign` table, which also holds open and unknown flights the code never reads (the controller's ruling). `figures_check.py` gains `signs_carried`, `sign_counts` and `show_signs` to get there.
- 2026-11-12, Task 6: `EXPECTED["A25"]` holds, per sign and checkpoint, the columns from `cancelled_with` through `clears_floor` only; the ratio and pass columns are the sign test's, a later task (the controller's ruling). S1's rows count departures only, as `signcell` does (`test_an_arrival_is_never_in_s1s_with_or_without_set`), and each row prints as its own line, "A25 S1 24 hours: ... ok".
- 2026-11-12, Task 6: `tests/test_record_cut.py` gains a case beyond Task 1's, `signs-at-the-moment` (cut at 12:07 and 13:22), with `test_the_signs_case_shows_every_sign`: Task 1's cases hold no cancelled number and no number listed late with a passing by the cut's last sighting, so every sign reading there was empty. It matches with no accepted difference. The carry is read over every flight with a number in the row, closed or not, since these archives close none; and the file imports `number_signs` and `flight_signs` by name, because its own `record()` shadows the module.
- 2026-11-12, Task 6: `tests/test_record.py` holds tests beyond the brief's list: the tie kinds of "as a whole" (three tied, five not tied, and a tied number also cancelled), and `test_the_signs`. `tests/test_figures_check.py`'s synthetic model gains nine numbers (`SIGN_CASES`: an S1 inbound, an inbound not cancelled as a whole, S2 across a departure that left the list, S4 shown by one number of a two-number flight, a number first seen at the hole's end), and `test_main_fails_on_a_flight_or_cell_difference` becomes `test_main_fails_on_a_flight_cell_or_sign_difference` with a planted sign difference.
