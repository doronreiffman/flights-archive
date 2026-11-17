# Will It Fly? (q27) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade**, quoted from the design (`docs/flight-lookup.md:3`; `docs/site-redesign.md:3` says the same): "production-lean, the site's grade (`docs/site-redesign.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript." The 2026-11-17 update keeps it (`docs/flight-lookup.md:4`).

**Goal:** Build the "Will It Fly?" redesign: a chance per flight from the blend, delays of an hour or more, the flight page reorganised around the traveller's day, the approved words verbatim, look A with its self-hosted fonts and a dark scheme, the upload check's new rules, and a back-test of the blend on the last week.

**Architecture:** Three new modules beside the frozen ones, none of them frozen:
- `src/timeline/blend.py`: each flight number's, airline's and the airport's counts, and the two chances ("The blend").
- `src/timeline/backtest.py`: a local entry point that scores the blend on the last closed week.
- `src/timeline/names.py`: the hand-kept list of spoken airline names, and a local entry point that proposes it.

`words.py` gains every approved sentence; `display.py` the hour rule for DELAYED; `flights.py` the new titles and the story picker's skip; `views.py` the new pages; `check.py` its new rules; `static/fromhere.js` the page's age and the move of the next day ahead; `static/style.css` look A; `static/fonts/` the four font files; `scripts/publish.sh` a fourth upload. The frozen files (`src/model/`, `src/timeline/load.py`, `counting.py`, `rates.py`, `record.py`, tag `record-v1` on b948ea2) are read and never changed.

**Tech Stack:** Python 3.13 (`.venv`), DuckDB 1.5.6, pytest with coverage, Node 24 for the script tests (skipped where Node is missing). No new dependencies.

**Spec:** `docs/flight-lookup.md` and `docs/site-redesign.md` at 0f1b7e8 (decisions D10 to D13, owner-approved 2026-11-17), and `docs/terms.md`, clause 4 (lines 30 to 40). The round-4 mockups are local files kept outside the repository (`data/design-2026-11-17/v4/`: `contents.html`, `style.css`, `fonts/`, `fromhere.js`, `LIST.md`); they show look A's markup and CSS, and the design documents win wherever the two differ. Executors read the design sections their task names; the design's exact words win over any paraphrase here.

## Global Constraints

What holds from `docs/flight-lookup-plan.md` (lines 31 to 46), and what q27 changes:

- Cost: nothing new on AWS, $0 a month added. Four font files add four PUT requests to an upload, about $0.00002 (`docs/site-redesign.md:351`).
- Run everything with `.venv/bin/...` and `PYTHONPATH=src`; tests with `.venv/bin/pytest`. macOS has no `timeout`: wrap a command as `perl -e 'alarm N; exec @ARGV' <command>`.
- Model times (`*_at`, `*_utc`) are naive UTC: mark them UTC before converting (`.replace(tzinfo=timezone.utc)`). A test that touches Israel time runs under the `israeli_machine` fixture (`tests/test_timeline_words.py:14`).
- Same model, same bytes, across `PYTHONHASHSEED`. No random numbers, and no clock in the build: the build's time is the last sighting (`confirmed_until` of the last snapshot). The page's age is worked out in the browser.
- **Frozen files** (unchanged): `src/model/`, `src/timeline/load.py`, `counting.py`, `rates.py` and `record.py`. Other modules may import them; they import nothing new (`tests/test_frozen.py`). A task that finds it needs a change in one stops and asks the owner (`docs/flight-lookup.md`, "The record", condition 2). DuckDB's pinned version and Python's stay as the tag's message names them. The counting start and the tag stand as set on 2026-11-15.
- **Words.** The approved words of both design documents' "Words" and "Pages" are used verbatim. A line a traveller reads that the documents do not word is never written by an implementer: the task stops, and the line goes to "Questions for the owner" with a proposed wording. Every line passes the owner's test: a 60-year-old reads it aloud without pausing.
- Kept from 2026-10-30: no "we", "our", "us" on any page, nor in any `.js` or `.css` file, comments included (the check reads those files as written); "I" only on `how-it-works.html` and in the built-by line; no data-collection word ("board", "snapshot", "stored", "observed", "receipt", and plurals) outside `how-it-works.html`; no phrase in `check.BANNED` ("cancelled at", "canceled at", "delayed by", "operated by", "took off", "minutes late", "hours late", "pause in our collection").
- **Claims (changed by q27).** The flight-lookup plan's "a rate is always '1 in N' with its range, never a percentage" and "none of chance, odds, … on a reader page" no longer hold. Now:
  - figures are percentages, and no range stands on a traveller's page;
  - "chance" and "chances" are allowed, and every other odds word stays refused on a traveller's page ("odds" among them);
  - a chance reads "about" or "under" and is never "0%";
  - "cancelled", not "listed as cancelled", and "marked cancelled" where a sentence says when;
  - a cancellation never gets a clock time, and notice is a range or a bound;
  - a delay is "an hour or more", and nothing under an hour is shown;
  - a flight page with a chance carries a "Worked out from" line.
- Out of scope: a sign shown on any page, a browse view, delays under an hour, a tested model (q28), anything new on AWS, the upload itself.
- **The built site (changed by q27):** `.html`, `.css` and `.js` files, the four `.woff2` font files and their licence, `fonts/LICENSE.txt` (Question 7, answered 2026-11-17), where the flight-lookup plan had "only `.html`, `.css` and `.js`". The only scripts are `search.js` and `fromhere.js`. Every string from the airport's data goes through `views.d()`, and so does every flight number and spoken airline name inside a sentence.
- Every task leaves the whole suite passing at its commit, with coverage at 95% or more. A test that pins a retired word or rule is rewritten or retired in the same task, and the commit message names it.
- **Mutation check.** `scripts/mutation_check.py` edits source files in place: run it alone, with nothing else running from the checkout, and never during a model build. New entry names start with their area: "blend: ", "backtest: ", "names: ", "words: ", "display: ", "flights: ", "views: ", "site: ", "check: ", "style: ", "fromhere: ", "search: ", "publish: ". A change's entries are picked by target file, not by name prefix, since older entries carry none. Each task runs the entries of the files it touched (the guard stops an empty list, which would run all of them):

  ```sh
  PYTHONPATH=scripts .venv/bin/python -c 'import sys, mutation_check as m
  names = [n for n, ((f, _), _, _) in m.MUTATIONS.items() if f in sys.argv[1:]]
  sys.exit(m.main(names) if names else "no entries target " + " ".join(sys.argv[1:]))' <files the task changed>
  ```

  Expected: every entry CAUGHT, none STALE. A STALE entry is rewritten or retired; a MISSED one gets its test.
- No push, no `gh`, no AWS from any task.
- Implementers by kind, one tier above the subagent-driven-development skill's cost guidance: transcription → Sonnet, integration → Opus, architecture → Fable; never Haiku. A fresh Opus reviewer reads each task's diff before the next task starts. A fresh Fable reviewer reads the whole branch once, before the documents task (Task 16). A reviewer's finding, and an implementer's note, is checked against its source before it is folded in.
- Documents in this repository are public: neutral voice, "I" only for what the owner decided or did.
- Baseline at 0f1b7e8: `PYTHONPATH=src .venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95` collects 1,210 tests; `.venv/bin/python scripts/mutation_check.py` holds 510 entries, all caught on main. After any site build, `PYTHONPATH=src .venv/bin/python -m timeline.check site` exits 0 under the rules in force at that commit.

**Main-session steps.** These are run by the main session, never by an implementer, and are marked "(main session)" in the tasks:
- syncing data (`sh scripts/sync.sh`, which checks the `flights-sam` identity itself);
- the model build, `PYTHONPATH=src .venv/bin/python -m model.build --raw data/raw --out data/model-<date>`. It runs alone: a build reported for 2026-11-17 took 302 s and peaked at 8.23 GB on this 8 GB Mac (one measurement, not repeated for this plan);
- the timeline build and `timeline.check` on real data;
- the back-test and the names proposal on real data;
- the font licence and response-header reads (Task 7);
- the owner's hand check, in the owner's own browser (390 px and desktop, light and dark). The main session gives file paths and never drives the browser;
- every commit that records a result or an approval, every push, the merge, and the upload. The owner runs `! sh scripts/publish.sh` at the terminal.

## Review Focus

The input classes the design implies but its test lists do not exercise, most likely first. Each has its test in the owning task.

1. **A day ahead whose label is not UPCOMING at the last update.** On the 2026-11-17 model at 09:46, 2 days ahead had already landed or departed and 3 were labelled UNKNOWN. A day ahead can also be marked cancelled, or marked cancelled while its twin is still on. Expected: such a day still stands at the top, carries no chances, and the page passes the "Worked out from" rule (Questions 1 to 3). Tests in Tasks 10 and 11.
2. **A number grouped under another airline on some days and not on others.** On the 2026-11-17 model, 4,629 of 12,844 numbers belong to a flight grouped under another airline (C8), across 15 grouping airlines. Expected: one airline per page, that of the traveller's day; the partner line only when that airline is not the number's own; the build stops when that airline has no spoken name. Tests in Task 11.
3. **A page read long after its upload, or by a visitor whose clock is wrong.** Expected: a negative age reads "Updated less than an hour ago"; a page a week old reads "Updated more than 7 days ago", with every day passed; a time left above 72 hours shows the "more than 3 days" line and keeps the 70-hour pair. Tests in Task 12.
4. **A flight whose numbers disagree on how it ended.** A number can be UNKNOWN while its flight flew (3 on the 2026-11-17 model), or marked cancelled while a partner is still listed (A24: 13 closed flights spent 11.5 to 72 hours that way). Expected: counts follow the flight's C10 label, so a flight still listed is not yet counted (Question 4, and "What this plan decided"). Tests in Task 4, and the strip's key against the "so far" line in Task 11.
5. **One number flying twice on one day** (IZ 992 has two rows on 30 October). Expected: two marks in the strip with the same day under them and their own anchors; two flights in the counts; the traveller's day picked by time, not by date. Tests in Tasks 10 and 11.

## Order, and why

- Task 1 goes first. Every build test runs the upload check. Letting "chance" and the percent sign through before any page prints them, and changing the footer in the same commit, keeps the suite passing at every later commit.
- Tasks 2 and 3 are the row-level words every page uses. Landed first, they let the page tasks restructure pages without rewording them.
- Task 4 is the blend, and Task 5 its back-test right after. The main session then runs the back-test on the real model, so the owner's flag decision (ship, or change the weights) comes before any page shows a chance.
- Task 6 holds the words that carry figures, after the blend that gives them their values. The names proposal then runs on the real model, so the draft list exists before Task 11's build stop needs it.
- Task 7 adds the fonts and the upload. It is independent, and comes before the page tasks so that the stylesheet task has its faces. Its licence and header reads are the main session's, and they gate its end.
- Tasks 8 to 11 are the pages: every page's frame first, then the front page, then the flight page in two halves.
- Task 12 is the script, against the flight page's markup contract. Task 13 is the stylesheet, after all markup. Task 14 is "How this works"; the main session commissions its draft.
- Task 15 is the hand check, Task 16 the whole-branch review, Task 17 the documents, Task 18 the final verification.

| Task | What | Implementer |
|---|---|---|
| 0 | The baseline build on the latest model, and its page weights | main session |
| 1 | The upload check's new rules and the new footer | transcription (Sonnet) |
| 2 | Labels, notices and a day's lines; DELAYED by the hour rule | transcription (Sonnet) |
| 3 | What changed, titles, "Also sold as", the twin lines, the story picker | integration (Opus) |
| 4 | The blend (`blend.py`) | integration (Opus) |
| 5 | The back-test (`backtest.py`), then its run on real data | integration (Opus), then main session |
| 6 | Words that carry figures; the names list (`names.py`), then its proposal | transcription (Sonnet), then main session |
| 7 | Fonts, the fourth upload and the font rule; the licence and header reads | integration (Opus), with main-session reads |
| 8 | Every page's top line, "Updated" and footer; the day page; the cancelled-flights page | integration (Opus) |
| 9 | The front page and the search | integration (Opus) |
| 10 | The flight page: its frame, its days and the strip | integration (Opus) |
| 11 | The flight page: the slot, the figures and the build's wiring | integration (Opus) |
| 12 | `fromhere.js`: the page's age and the move of the next day ahead | integration (Opus) |
| 13 | Look A, light and dark (`style.css`) | integration (Opus) |
| 14 | How this works: the approved opening and section 1, the drafted sections 2 to 10 | draft: Fable (main session); code: transcription (Sonnet) |
| 15 | The hand check | main session and the owner |
| 16 | Whole-branch review | Fable reviewer (main session) |
| 17 | Documents | transcription (Sonnet) |
| 18 | Final verification, then the push, merge and upload | main session and the owner |

**Coverage of the design.**
- `docs/flight-lookup.md`:
  - "The blend": Task 4;
  - "Delays": Tasks 2 and 4;
  - "Before it ships: the back-test": Tasks 5 and 15;
  - "Words": Tasks 6, 9, 10 and 11, plus Task 3 for "In lists";
  - "Pages": Tasks 9 to 12 and 14;
  - "What q27 adds": Tasks 4 to 7;
  - "Tests and checks", the blend: Task 4; how numbers are written: Task 6; words and pages: Tasks 6 and 8 to 11; `fromhere.js`: Task 12; the upload check: Task 1;
  - "Five outsiders (q13)": Task 17;
  - "Left to the builder": "What this plan decided".
- `docs/site-redesign.md`:
  - "Words": Tasks 2 and 3; "Pages": Tasks 8 to 11 and 14;
  - "Look A": Tasks 7 and 13;
  - "How it is built", what q27 adds: Tasks 7, 9 and 12;
  - "Tests and checks", what q27 changes: Tasks 1, 2, 3, 7, 9, 10, 12 and 13.
- `docs/terms.md` and the documents named at `docs/flight-lookup.md:37`: Task 17.

## What this plan decided

The design leaves these to the builder. Where it gave a recommendation, the plan takes it unless this list says otherwise.

- **Modules.** `blend.py`, `backtest.py` and `names.py` are new. `blend.py` reads the frozen modules' public functions (`counting.flights`, `flight_of`, `figures`, `cells`, `passings`, `stretches`, `holes`, `last_sighting`, `rates.rate`) and C8's order (`counting._number_order`); it changes nothing in them.
- **"Each flight whose ending is known"** (`docs/flight-lookup.md:375`, :867) is a flight whose C10 label (`display.label`) is DEPARTED, LANDED or CANCELLED. It is cancelled when that label is CANCELLED, and it flew when the label is DEPARTED or LANDED. This agrees with C2 everywhere except while one of the flight's numbers is still listed. C2 would then already call it cancelled; A24 found 12 of 13 such closed flights departed or landed later. The number's and the airline's counts follow this rule; the airport's rate and rows stay the frozen total and rows.
- **Taken as recommended** (`docs/flight-lookup.md:864-885`):
  - the row that scales a chance is the nearest checkpoint at or above the time left, and the 70-hour row above 48 hours and on a page with no flight ahead;
  - a flight page holds its prepared chances once per stretch still ahead of each day at the last update; the script shows the pair for the visitor's clock; without scripts, the pair for the time left at the last update shows;
  - the delay's airport rate is the direction's own, over closed flights with a known result that flew; every delay count is over flights that flew; an airline's delay count covers both directions;
  - the airline is C8's grouping airline of the traveller's day, or of the latest day when none is ahead, and there is one airline per page;
  - a number's record is per number and direction; an airline's counts include the number's own flights;
  - DELAYED is drawn from the number's last expected time on a day that flew and on a day ahead, never beside CANCELLED or UNKNOWN; in a list, it shows when any number of the flight has it;
  - a range on "How this works" has one decimal, its ends rounded outward;
  - "Worked out mostly from" stands below 14 counted flights;
  - a bad week is two or more cancelled flights all within 7 days;
  - rounding is to the nearest, halves up; "under 1%" covers every value below 1%;
  - "about 5,000" is the mean of the rows shown, to the nearest 500;
  - the delay sentence's stop and the back-test's mechanics, as below;
  - the check's three readings: the other odds words stay refused, both "1 in N" rules go, and the footer's second line is required on every page;
  - `fromhere.js` writes the page's age on every page;
  - a wrapper shows the search's label, box and hint together;
  - once the next day has moved up, a passed day goes to the head of the past days;
  - fonts sit in `site/fonts/`; the licence text is committed beside them (whether the site serves it is Question 7);
  - titles are marked whole as the airport's data; dates are written out on a page and short in lists;
  - "Already on the list" stands for a first record in the records' first list, or in the first list after a hole (`counting.holes`).
- **A row below the floor.** The scaling takes the nearest row that clears C8's floor, trying first the checkpoints with more time left, nearest first, then those with less. It is unscaled when no row clears. The all-airlines form for that stretch is left out. The all-airlines form without a time is left out when the total is below the floor.
- **The delay sentence's stop** ("It's about the same however soon you fly.", `docs/flight-lookup.md:881`). The build stops, naming the direction and the row, when a row's delay rate differs from its direction's rate by more than one percentage point. It checks only rows whose delayed flights clear C8's floor (10 delayed flights, 5 airlines, 5 days). Every small model in the tests would otherwise stop the build by chance. Today's rows hold well over that.
- **A bad week**: the first and last cancelled flights' Israel days at most 6 days apart (7 calendar days), with two or more flights.
- **Number formatting** lives in four functions (Task 6). The table's one decimal is computed in integers, so 3 of 2,000 prints 0.2%, not the float's 0.1%. The total's tile takes the table's form; its sentence takes the form for averages.
- **Spoken names.** `names.SPOKEN_NAMES` is keyed by airline code. The proposal covers the airlines with 100 or more counted flights, plus every airline that some flight is grouped under (C8's grouping airline; Question 5). The build stops when a partner line's airline has none. Spoken names and flight numbers inside sentences go through `views.d()`, so a name such as "US-Bangla" cannot trip the word rules. An airline's published name is the `airline_name` of its latest row.
- **Words functions that hold names** take two callables, `text` and `data`, identity by default; the views pass `e` and `d`. So the exact-text tests read plain text, and the pages mark names as data.
- **The flight page's markup contract** (Task 10) moves elements rather than duplicating them. Each day is written once. The script moves the support lines into the new top day, moves that day to the top, and moves a passed day to the head of the past days. It finds elements by `getElementById`, by `children` with `classList.contains`, and by `querySelectorAll("[data-updated]")`, so the Node tests' stand-in DOM needs no selector engine.
- **The page's age** from a negative difference reads "Updated less than an hour ago".
- **Fonts.** They are cached for 300 s like every other file, since their names carry no hash. They are pinned by name, size and SHA-256. `render` returns `bytes` for them.
- **Titles.** When one city's name is the beginning of another's, the shorter is named once, at the place of the newer of the two (the mockups' "Bucharest").
- **Typography.** The quoted words take curly quotes (“still on”), as “final” does today.
- **A landed day with no expected time** reads "scheduled to land at 19:45", since "landed around" needs a time.
- **The back-test** (`docs/flight-lookup.md:882`):
  - the week is the 7 Israel days ending with the latest day whose flights are all closed at the last sighting;
  - it scores the week's closed flights with a known result that are in the 24-hour row, each through C8's lead number;
  - the counts are cut at the week's start: the number's and airline's from flights scheduled before it, the airport's from `counting.flights` closed as of it. Their results are as the full model has them, a stated leak of at most the results that came in after the start;
  - the top tenth is the ceiling of a tenth, by chance, with ties broken by the flight key;
  - the report is written to `data/backtest/<model folder>/report.txt`. The exit code is 0 unflagged, 1 flagged and 2 with no model.
- **The page weight** is measured by the main session: the largest flight page and the whole site, at the baseline (Task 0) and at the hand check (Task 15). It goes in "Deviations".

## Questions for the owner

Answered by me on 2026-11-17: all eight as recommended, so each task stands as written. A bare line number (":562") is `docs/flight-lookup.md`'s.

1. **The "Worked out from" line when the traveller's day carries no chances.** The check requires the line on any flight page that holds a chance (`docs/flight-lookup.md:817`). A traveller's day that is marked cancelled, removed early or already landed carries none (:562), but a later day ahead carries its own chances with "no 'Worked out from' line of its own" (:563). Such a page fails the check. Recommendation: the slot keeps the line, in its flight-ahead form, under that day's own lines, whenever any day ahead on the page carries chances. Tasks 11 and 12.
2. **A day ahead that already departed or landed** (2 on the 2026-11-17 model). A day is ahead "whatever its label" (:557), and the slot's cases (:560-563) cover UPCOMING, cancelled and removed early only. Recommendation: it stays the traveller's day, with the past day's time line ("scheduled 19:45 · landed around 19:30 · LANDED"), no chances, and Question 1's rule for the line. Tasks 10 and 11.
3. **A day ahead on which the number is marked cancelled while its flight is still on as its twin.** "This flight is marked cancelled. Contact your airline." (:493, :504) and "This number is marked cancelled, but the flight is probably still on, as OS 083." (:499) would both stand, and they say opposite things. Recommendation: the CANCELLED label, its notice sentence and the twin line, with no chances, and without the "marked cancelled" line. Task 10.
4. **A day whose number is UNKNOWN or still listed while its flight flew under another number** (3 on the 2026-11-17 model). The 2026-11-17 decision counts a number marked cancelled on such a day as flown (:375); the other cases are not named. Recommendation: they count as flown too, by C2, and the strip keeps the number's own mark. On such a page the strip's key and the "so far" count then differ by that day. Task 4.
5. **How far the names list reaches.** ":468" says "every grouping airline is on the names list", and :539 says the build proposes it "for the airlines with the most flights and every airline that a number's flight is grouped under (C8)". On the 2026-11-17 model that is 54 of 69 airlines, which leaves the forms for "an airline with no spoken name" (:440-441, :448) for an airline new to the archive since the list was approved. The airlines under which another airline's number is grouped, the partner line's own need, are 15. Recommendation: the design's reading, every grouping airline plus every airline with 100 or more counted flights; the build stops when a partner line's airline has no name, and any other airline without one takes the "its airline" forms. Alternative: the 15 plus the airlines with 100 or more flights, a shorter list to approve. Task 6.
6. **Lines the documents do not word.** Proposed wordings, each built on an approved line:
   - a. A bad week on one day, across a month's end, and of two flights (:432-436, :459, :877): "…all on 6 November."; "…all between 30 October and 2 November."; "all" kept for two.
   - b. "Worked out from" with no flight ahead and cancellations spread, or one (:430-434 give these with a flight ahead only): "Worked out from this flight's history (3 of its 21 flights were cancelled) and Lufthansa's history.", on the pattern of :433.
   - c. A short history (under 14) with a bad week of its own. The terms reading asks for its dates (`docs/terms.md:34`), and no form gives them. The number's "so far" line takes them as the airline's does (:459): "LH 697 so far: 5 flights · 2 cancelled, all between 6 and 9 November · none delayed an hour or more".
   - d. A number with no flights yet: its "so far" line is left out, since the "Worked out from" line says "has no flights so far" (:447). Under an airline with none either: "Worked out from all airlines at Ben Gurion, because XX 123 and its airline have no flights so far."
   - e. A delay figure under 1% (small archives only; today 7.7% and 4.9%, :391, :461): "**Chance of a delay of an hour or more:** under 1% for departures and about 5% for arrivals." and "under 1% of arrivals delayed an hour or more".
   - f. Singular counts (:402-404; `docs/site-redesign.md:239-241`): "1 flight is left out because there's no record of how it ended."; "For 1 of these flights, there's no record of how it ended."; "Monday 16 November · 1 flight · 1 cancelled"; "Since 27 October, 1 of 420 flights at Ben Gurion was cancelled." A count of 0 leaves its line out, and its part of the day's title, as built.
   - g. A flight removed less than an hour early (`docs/site-redesign.md:76`; none on the 2026-11-17 model): "The airport removed this flight less than an hour early without saying why. …".
   - h. A number marked cancelled whose twin has no news yet: `flights.others` maps NO NEWS YET to "is still listed", and the approved "still on" form is for a twin still ahead (:499). Proposed: "This number was cancelled, but the flight may have gone ahead as OS 083." Alternative: no twin line on such a day.

   Tasks 6, 8, 9, 10 and 11.
7. **The font licence's notice on the site.** Answered after the read (2026-11-17): the four files carry IBM's copyright line and a link to the licence, not its text, so the site serves `fonts/LICENSE.txt` beside them, uploaded as `text/plain; charset=utf-8` (my choice). The licence is read at its source in Task 7. Recommendation: if it lets the notice travel in the font files' own metadata, the site serves the four files only, and the repository carries the licence text beside them. If it does not, the site also serves the licence text, which needs a fifth upload line (`*.txt` as `text/plain; charset=utf-8`). That is a file type the design does not list (`docs/site-redesign.md:35`), so it is the owner's call. Task 7.
8. **A stale line.** `docs/site-redesign.md:143` still lists "one composed line" as open, with "All three". `docs/flight-lookup.md:537` lists two open items, and D13 settled the partner line in the owner's own words. Recommendation: the documents task drops "and one composed line", and "All three" becomes "Both". Task 17.

## Design and code

- `docs/flight-lookup.md:38` says that only `docs/terms.md`'s clause 8 line still follows the build. `docs/site-redesign.md:350` names two lines: that one and the sentence ending the clause 4 paragraph (`docs/terms.md:40`), which still says the check refuses a percent sign. Task 17 brings both up.
- `src/timeline/check.py:35` says `SCANNED` is "every file type scripts/publish.sh uploads". After Task 7 the upload sends a fourth type that the check does not read (`docs/site-redesign.md:348`). Task 7 rewords the comment.
- `scripts/mutation_check.py:73` already holds a constant named `NAMES` (the test that ties markup to `fromhere.js`). The names list's target is therefore `NAME_LIST`.

---

### Task 0: The baseline on the latest model (main session)

The baseline and the first back-test (Task 5, Step 8) use the latest model already built (`data/model-2026-11-17`, boards to 07:46:44Z), not a new one: a full build peaked at 8.23 GB on this 8 GB Mac (one measurement), so the plan runs one fresh build, at the hand check (Task 15), where the owner reads the pages and the back-test.

- [ ] **Step 1:** Name the model used and its last sighting in "Deviations".
- [ ] **Step 2:** At 0f1b7e8, `PYTHONPATH=src .venv/bin/python -m timeline.build --model data/model-<date> --out site`, then `PYTHONPATH=src .venv/bin/python -m timeline.check site`. Expected: exit 0. Record in "Deviations" the largest file under `site/flight/` (bytes and name), the site's total bytes and its file count.

### Task 1: The upload check's new rules and the new footer

Implementer: transcription (Sonnet). Design: `docs/flight-lookup.md`, "Tests and checks", the upload check (:803-828); `docs/site-redesign.md`, "Footer (every page)" (:266-279).

**Files:**
- Modify: `src/timeline/check.py`, `src/timeline/words.py` (`UNOFFICIAL`, `TIMES_NOTE`, new constants), `src/timeline/views.py` (`layout`'s footer), `scripts/mutation_check.py`
- Test: `tests/test_timeline_check.py`, `tests/test_publish.py` (`make_site`'s footer), `tests/test_timeline_build.py`, `tests/test_timeline_views.py`

**Interfaces:**
- Produces, in `timeline.words`:
  - `UNOFFICIAL = "This site is unofficial: it isn't run by, connected to or approved by the Israel Airports Authority, data.gov.il or the State of Israel."`
  - `TIMES_NOTE = "All times are Israel time."`
  - `ESTIMATES = "The chances on this site are estimates from past flights, not promises."`
  - `MEANS = "What the numbers mean"` and `MEANS_ANCHOR = "what-the-numbers-mean"`
- Produces, in `timeline.views`: `layout`'s footer is three `<p>`:
  - `SOURCE_SHORT`, `UNOFFICIAL` and `TIMES_NOTE`;
  - `ESTIMATES` and `<a href="{root}how-it-works.html#what-the-numbers-mean">What the numbers mean</a>`;
  - How this works · Code on GitHub · Built by `BUILT_BY`.
- Produces, in `timeline.check`:
  - `ODDS_WORDS` without `chances?`;
  - no percent rule, and neither "1 in N" rule (`rate_hits`, `RANGED_RATE`, `BARE_RANGE`, `ONE_IN` and the record-line rule go);
  - `NOTICES` gains `"estimates line": ESTIMATES`;
  - `CHANCE = re.compile(r"\bchance (?:it's|its next flight is) (?:cancelled|delayed)\b")`, read on `flatten(strip_tags(raw))`;
  - `WORKED_OUT = re.compile(r"\bWorked out (?:mostly )?from\b")`, read on the case-kept `plain(strip_tags(raw))`: every approved form starts with a capital "Worked out from" or "Worked out mostly from" (`docs/flight-lookup.md:429-441`), while the partner line's lowercase "…worked out from LOT's history." (:460) stands on the same pages and must not count;
  - `missing_notices` adds `(name, "worked-out line")` for a page under `flight/` whose text matches `CHANCE` and holds no `WORKED_OUT` match.

- [ ] **Step 1: Write the failing tests:**
  - `test_chance_and_chances_pass_on_a_travellers_page`;
  - `test_the_other_odds_words_are_still_refused`, parametrized over every remaining word, "odds" and "likely" among them;
  - `test_how_it_works_stays_exempt_from_the_odds_words`;
  - `test_a_percent_sign_passes`: "1.7%" in a page's text. The two tests that refuse a percent sign are retired.
  - `test_a_chance_on_a_flight_page_needs_the_worked_out_line`:
    - "Chance it's cancelled" with no line is refused, and so is "Chance its next flight is cancelled";
    - with "Worked out from …" it passes, and with "Worked out mostly from …";
    - a later day's chances beside one line pass;
    - `index.html` with the column head "Chance it's cancelled" and no line passes.
  - `test_the_2026_10_30_unofficial_line_fails`: a page whose footer has "Unofficial; not affiliated with or endorsed by …" lacks the unofficial line.
  - `test_the_footers_second_line_is_required_on_every_page`;
  - `test_lines_near_a_banned_phrase_pass`: "CANCELLED" then "Cancelled with at least 21 hours' notice."; "(LH 0691A: cancelled)" before "to Athens".
  - The views and build tests of the footer read the three new lines.
  - Retired with their rules: the ranged-rate, bare-range, separator and record-line tests.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_check.py tests/test_publish.py tests/test_timeline_views.py tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement.** Rewrite the module docstring's "Four rules for rates" paragraph to the new rules.
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries.** Retire the "check: " entries of the removed rules. Add:
  - "check: chance refused on a traveller's page";
  - "check: worked-out rule off";
  - "check: worked-out rule on every page";
  - "check: next-flight headline not a chance";
  - "check: only 'worked out from' counts";
  - "check: estimates line not required";
  - "views: footer without the estimates line".

  Run the entries of `src/timeline/check.py`, `src/timeline/views.py` and `src/timeline/words.py`.
- [ ] **Step 6: Commit** (`q27: the upload check allows chances and percentages, requires the "Worked out from" line, and the new footer`).
- [ ] **Step 7: Review (Opus).**

### Task 2: Labels, notices and a day's lines; DELAYED by the hour rule

Implementer: transcription (Sonnet). Design: `docs/site-redesign.md`, "Labels" (:62-85), "Notice" (:87-111); `docs/flight-lookup.md`, "Delays" (:332-344) and :874.

**Files:**
- Modify: `src/timeline/words.py`, `src/timeline/display.py`, `src/timeline/flights.py` (`Row`, `make_rows`, `group_flights`), `src/timeline/views.py` (callers only), `scripts/mutation_check.py`
- Test: `tests/test_timeline_words.py`, `tests/test_display.py`, `tests/test_timeline_flights.py`, `tests/test_timeline_views.py`, `tests/test_timeline_build.py`

**Interfaces:**
- Produces, in `timeline.display`:
  - `DELAY_MINUTES = 60`;
  - `delayed_an_hour(r: dict) -> bool`: `est_minus_sched_min` is not None and is at least `DELAY_MINUTES`. It is the one rule for the label, the counts and the chances.
- Produces, in `timeline.words`:
  - `NO_NEWS_YET = "NO NEWS YET"`, which replaces `NO_FINAL_UPDATE` in `LABEL_ORDER`;
  - `label_note(f: dict, label: str, ahead: bool) -> str | None`: the "Line under it" column of :68-77, with "Check with your airline." added for a vanished day ahead;
  - `changed_back(f: dict, label: str) -> str | None`: "Marked cancelled for a while, then back on." and "Cancelled, back on, then cancelled again.";
  - `Notice` (frozen dataclass: `sentence: str`, `short: str`) and `notice(f: dict) -> Notice | None`: rules 1 to 11 of :93-105 in both forms, with "1 hour" and "1+ hours" (:107). `warning`, `warning_note` and `warning_sentence` are retired;
  - `NOTICE_GIVEN = "Notice given"`;
  - `time_line(direction: str, sched: datetime, est: datetime | None, label: str, page_date: date) -> str`, from Israel wall-clock times (:83):
    - "scheduled 19:45 · landed around 19:55" or "scheduled 17:30 · left around 17:38" on a day labelled LANDED or DEPARTED with an expected time, even when the two times are the same;
    - "scheduled 19:45 · expected 19:55" on a day with no final word (UPCOMING, NO NEWS YET, UNKNOWN) whose expected time differs;
    - otherwise "scheduled to land at 19:45" or "scheduled to leave at 05:35";
  - `scheduled(direction, local, page_date) -> str`: now with "at" ("scheduled to leave at 05:35");
  - `EXPECTED_NOTE` (:83, verbatim), which replaces `DELAY_SENTENCE`;
  - `FINAL_NOTE = "“Final” and “not final” are the airport's own words. It doesn't explain them."`.
- Produces, in `timeline.flights`:
  - `Row` loses `warning`, `warning_note` and `last_expected`, and gains `notice: words.Notice | None`, `est_final: datetime | None` (the airport's `est_local_final`) and `last_seen_at: datetime`;
  - `Row.delayed` is `display.delayed_an_hour(f)` and the label is not CANCELLED or UNKNOWN;
  - `ListFlight.delayed` is any of its rows delayed, unless the flight's label is CANCELLED or UNKNOWN.

- [ ] **Step 1: Write the failing tests:**
  - One exact-text test per row of "Labels" (:68-77), the vanished line on a day ahead and on a past day included.
  - `test_no_news_yet_is_decided_in_utc`, under `israeli_machine`: a flight at 23:55 Israel time on 29 October, last record 22:02 UTC.
  - One exact-text test per notice rule 1 to 11 in both forms. Include the 0 and 60 boundaries, a 42-hour censored bracket (LY 5409's shape), "1 hour's notice" and "1+ hours".
  - `test_delayed_at_59_and_at_60_minutes`;
  - `test_no_expected_time_is_not_delayed`;
  - `test_delayed_never_beside_cancelled_or_unknown`;
  - `test_a_list_flight_is_delayed_when_any_number_is`;
  - `test_the_airports_word_delayed_no_longer_labels`: an observation with status DELAYED and an expected time 20 minutes late gives no DELAYED;
  - `test_the_time_lines_four_forms`, with the same time twice, a landed day with no expected time, and an expected time on another date;
  - `test_changed_back_lines`, with `uncanceled` NULL as false.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_words.py tests/test_display.py tests/test_timeline_flights.py -q`
- [ ] **Step 3: Implement.** The current pages take the new words where they print the old ones: the label line, the notice sentence and its list form, the changed-back line, the time line, and the expected-times note. No page is restructured.
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries:**
  - "words: notice boundary 60 in the lower rule";
  - "words: 1 hours";
  - "words: vanished line without its day-ahead sentence";
  - "words: landed around on a day with no final word";
  - "words: expected shown when the same";
  - "display: DELAYED from the airport's word";
  - "display: DELAYED at 59 minutes";
  - "flights: DELAYED beside CANCELLED";
  - "flights: list DELAYED from the first number only".

  Retire the entries of the retired functions. Run the entries of every file the task changed.
- [ ] **Step 6: Commit** (`q27: labels, notices and a day's lines in the approved words; DELAYED by the hour rule`).
- [ ] **Step 7: Review (Opus).**

### Task 3: What changed, titles, "Also sold as", the twin lines and the story picker

Implementer: integration (Opus). Design: `docs/site-redesign.md`, "What changed" (:113-125), "Codeshares" (:127-131), "Names" (:133-139), front page item 6 (:195), "Left to the builder" (:394-397); `docs/flight-lookup.md`, "Flight page: other situations" (:494-499, :505-507), "In lists" (:509-515).

**Files:**
- Modify: `src/timeline/words.py` (`change_lines`, `_earliest`, new constants), `src/timeline/flights.py` (`make_rows`, `page_title`, `ListFlight`, `featured`), `src/timeline/build.py` (`render` passes the resumes), `src/timeline/views.py` (callers, the bracket, the two lines), `scripts/mutation_check.py`
- Test: `tests/test_timeline_words.py`, `tests/test_timeline_flights.py`, `tests/test_timeline_views.py`, `tests/test_timeline_build.py`, `tests/test_timeline_search.py`

**Interfaces:**
- Produces, in `timeline.words`:
  - `change_lines(obs, direction, page_date, gap_hours, resumes: frozenset[datetime]) -> list[tuple[str, str]]`. The first line's left column is:
    - "First on the list at 09:32", or "First on the list on 14 Nov at 19:46" on another day;
    - "Already on the list at 20:04" (or "… on 27 Oct at 20:04") when the record's `observed_at` is in `resumes`;
    - its text is as built, with "already cancelled" in the status's place.
  - `ALSO_SOLD = "Also sold as"` and `SAME_PLANE = "(probably the same plane)."`;
  - `twin(verb: str) -> tuple[str, str]`, the words before and after the names:
    - "departed": "This number was cancelled, but the flight probably left as", ".";
    - "landed": "… probably landed as", ".";
    - "is still listed": "This number is marked cancelled, but the flight is probably still on, as", ".";
  - `another_number` and `BRACKET` are retired.
- Produces, in `timeline.flights`:
  - `make_rows(flights, obs, last_fetch, gap_hours, resumes)`. `build.render` passes `frozenset({snaps[0]["fetched_at"]} | {end for _, end in counting.holes(snaps)})`.
  - `page_title(rows) -> str`:
    - one city: "LO 155 · Warsaw to Tel Aviv", "WZ 016 · Tel Aviv to Moscow";
    - two: "LH 697 · Tel Aviv to Athens or Frankfurt", "LH 682 · Munich or Frankfurt to Tel Aviv";
    - three: "Tel Aviv to Athens, Larnaca or Munich";
    - more: "Tel Aviv to Vitoria, Pristina or 3 other cities";
    - the newest day's city first; a city whose name begins another's is named once, as the shorter.
  - `ListFlight` gains `first_seen: datetime` and `sched_utc: datetime`, the flight's `counting.Flight.first_seen` and `key[2]`.
  - `featured` skips a flight whose `first_seen` is after its `sched_utc`.
- Produces, in `timeline.views`:
  - a list row's bracket reads "(LH 0691A: cancelled)";
  - "Also sold as A.", "… A and B.", "… A, B and C." with each number linked;
  - the twin line names the numbers joined the same way.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_first_lines_four_forms`: a time; a date; "Already on the list" in the records' first list and after a hole; "already cancelled".
  - `test_the_records_first_list_reads_already_on_the_list`, in `tests/test_timeline_build.py`, on a model built through `model.build` (`tests/model_helpers.py`) with a hole longer than `GAP_HOURS`. It proves that `observed_at` meets the snapshot's `fetched_at`.
  - `test_titles`: one, two, three and five cities; "Bucharest (bane" folded into "Bucharest"; an arrival; the search entries carry the new titles.
  - `test_also_sold_as_with_one_two_and_three_numbers`;
  - `test_the_twin_lines`: a departure, an arrival and a twin still ahead, each linked;
  - `test_the_bracket_in_a_list_row`;
  - `test_the_story_skips_a_flight_first_listed_after_its_scheduled_time`: WZ 016's shape, scheduled 05:35 and first listed 09:32, is skipped for the next one; a flight first listed exactly at its time is kept.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_words.py tests/test_timeline_flights.py tests/test_timeline_views.py tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries:**
  - "words: first on the list for the records' first list";
  - "words: first line without its date";
  - "flights: title of the oldest city first";
  - "flights: a cut-short city named twice";
  - "flights: other cities counted wrong";
  - "flights: story keeps a flight first listed late";
  - "flights: story skips a flight listed at its time";
  - "views: also sold as without its brackets";
  - "views: twin line of the wrong verb".

  Run the entries of every file the task changed.
- [ ] **Step 6: Commit** (`q27: what changed, titles, "Also sold as", the twin lines and the story picker`).
- [ ] **Step 7: Review (Opus).**

### Task 4: The blend

Implementer: integration (Opus). Design: `docs/flight-lookup.md`, "The blend" (:286-356), "What q27 adds" (:731-740), "Tests and checks", the blend (:771-776), "Left to the builder" (:864-882); Questions 4 and 5.

**Files:**
- Create: `src/timeline/blend.py`, `tests/test_blend.py`
- Modify: `scripts/mutation_check.py` (`BLEND = ("src/timeline/blend.py", ["tests/test_blend.py"])`)

**Interfaces:**
- Consumes: `counting.flights`, `flight_of`, `figures`, `cells`, `passings`, `stretches`, `holes`, `last_sighting`, `Flight`, `_number_order`; `rates.rate`, `Rate`, `Counted`; `display.label`, `delayed_an_hour`.
- Produces, in `timeline.blend`:

```python
NUMBER_WEIGHT = 14     # docs/flight-lookup.md:301
AIRLINE_WEIGHT = 100
STRETCHES = ((48, 72, 70), (24, 48, 48), (12, 24, 24), (6, 12, 12), (3, 6, 6), (0, 3, 3))  # (after, upto, checkpoint)
BAD_WEEK_DAYS = 6      # the first and last cancelled day at most this far apart

Key = tuple[str, str, str]   # airline, flight_no, direction: one flight page

@dataclass(frozen=True)
class Tally:                 # one record's counts, over the flights whose ending is known (C10 label)
    flights: int
    cancelled: int
    flew: int                # DEPARTED or LANDED
    delayed: int             # of those that flew, any departed or landed number delayed_an_hour
    cancelled_days: tuple[date, ...]       # Israel days (Flight.day) of the cancelled flights, sorted
    last_cancelled: datetime | None        # the latest cancelled flight's sched_utc_final

@dataclass(frozen=True)
class Airport:
    total: rates.Rate                      # counting.Figures.total
    rows: dict[int, rates.Rate]            # counting.Figures.rows
    delay: dict[str, rates.Rate]           # "D", "A": closed flights with a known result that flew, k = delayed

@dataclass(frozen=True)
class Records:
    numbers: dict[Key, Tally]
    airlines: dict[str, Tally]             # by C8's grouping airline (Flight.airline)
    airport: Airport
    published: dict[str, str]             # airline code -> the airline_name of its latest row

def known(label: str) -> bool
def records(table, obs, snaps, before: datetime | None = None) -> Records
    # before=None: the airport is counting.figures itself. before=t: only flights scheduled before t count, and the
    # airport's total and rows are those of counting.flights(table, t) (the back-test's cut)
def pull(k: int, n: int, toward: float, weight: int) -> float          # (k + weight * toward) / (n + weight)
def row_for(hours_left: float | None) -> int                          # STRETCHES' checkpoint; 70 above 48 h and for None
def scaling(airport: Airport, h: int) -> float | None                 # the clearing row's rate over the total's; None
def cancel_chance(number: Tally, airline: Tally, airport: Airport, h: int) -> float | None   # None: no counted flight at the airport
def delay_chance(number: Tally, airline: Tally, airport: Airport, direction: str) -> float | None   # None: none of the direction's flights flew
def bad_week(t: Tally) -> tuple[date, date] | None                    # two or more, all within BAD_WEEK_DAYS
def lead(f: counting.Flight, by_id: dict[str, dict]) -> dict           # C8's grouping number: min by _number_order
def flat_delays(table, obs, snaps, airport: Airport) -> None
    # ValueError naming the direction, the checkpoint, the row's rate and the direction's rate, for a row whose
    # delayed flights clear C8's floor and whose rate differs from the direction's by more than 0.01
EMPTY = Tally(0, 0, 0, 0, (), None)
```

- [ ] **Step 1: Write the failing tests**, the chances hand-computed from the design's counts (:305-330, recomputed for this plan to the digits shown). The airport has the total 104 of 6,115; the rows 70: 71/4,472, 48: 69/4,760, 24: 52/4,892, 12: 39/5,069, 6: 31/5,149 and 3: 23/5,195, all clearing the floor; departures 231 of 2,982 delayed and arrivals 149 of 3,029. Every value is checked with `pytest.approx(rel=1e-4)`:

```python
def test_lo_155():   # the number 0 of 22, LOT 0 of 127 with 2 delayed
    assert cancel_chance(LO155, LOT, AP, 48) == approx(0.0024834)
    assert cancel_chance(LO155, LOT, AP, 70) == approx(0.0027199)
    assert delay_chance(LO155, LOT, AP, "A") == approx(0.011854)
def test_lh_694():   # the number 4 of 14, 10 flew; Lufthansa 11 of 183, 172 flew, 7 delayed
    assert cancel_chance(LH694, LH, AP, 70) == approx(0.154306)
    assert delay_chance(LH694, LH, AP, "A") == approx(0.025562)
def test_lh_697():   # the number 1 of 2, 1 flew
    assert cancel_chance(LH697, LH, AP, 70) == approx(0.095003)
    assert delay_chance(LH697, LH, AP, "D") == approx(0.050601)
```

  More tests:
  - `test_a_number_with_no_flights_takes_its_airlines_rate`;
  - `test_an_airline_with_none_takes_the_airports`;
  - `test_each_pull_at_its_weight`: `pull(1, 2, 0.1, 14) == (1 + 1.4) / 16`;
  - `test_the_scaling_by_each_row`: the six factors 0.934, 0.852, 0.625, 0.452, 0.354 and 0.260, to 3 places;
  - `test_a_delay_is_not_scaled`;
  - `test_a_clean_history_gives_a_chance_above_zero`;
  - `test_row_for_each_stretch`: 72 → 70, 48.0001 → 70, 48 → 48, 24 → 24, 12 → 12, 6 → 6, 3 → 3, 0.5 → 3, None → 70;
  - `test_a_row_below_the_floor_scales_by_the_nearest_clearing_row`: the 3-hour row below the floor scales by the 6-hour row; the 70-hour row below the floor scales by the 48-hour row; with no row clearing, the chance is unscaled.
  - `test_which_flights_are_counted`, on rows built with `tests/counting_helpers.py`. Counted: DEPARTED, and CANCELLED ahead of its time. Not counted: UPCOMING, UNKNOWN, NO NEWS YET, and a number marked cancelled whose partner is still listed. Counted as flown: a number marked cancelled whose partner departed, and a number UNKNOWN whose partner departed (Question 4).
  - `test_a_number_is_counted_per_direction`: LY 1 D and LY 1 A are two records.
  - `test_the_airline_is_c8s_grouping_airline`: LY 9255 with LO 155 counts under LO, and LO's counts hold the number's own flights.
  - `test_the_airport_is_the_frozen_figures`: `records(...).airport.total == counting.figures(...).total`, and the rows the same.
  - `test_the_cut_at_the_last_sighting_equals_the_frozen_figures`: `records(…, before=last_sighting)` gives the same airport.
  - `test_a_delay_counts_flights_that_flew_an_hour_or_more_late`: 59 minutes not counted, 60 counted, read from the departed number; a cancelled flight is not among those that flew.
  - `test_bad_week`: two cancelled flights 6 days apart give their dates; 7 apart, None; one, None; two on one day, that day twice.
  - `test_lead_is_c8s_number`: LO 155 beside LY 9255; a lettered number ("0691A") by its digits.
  - `test_flat_delays`: a row above the floor 1.01 points off stops, naming "departures" and "24 hours"; 1.00 off passes; below the floor passes.
  - `test_published_name_is_the_latest_rows`.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_blend.py -q`
- [ ] **Step 3: Implement.** A flight is labelled with `display.label(f, by_id, last_sighting(snaps))`. A row's flight comes from `counting.flight_of`. The cut replicates `counting.figures` with `counting.flights(table, before)`, closed and with a known result.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** (`BLEND`):
  - "blend: number weight 13";
  - "blend: airline weight 99";
  - "blend: weights swapped";
  - "blend: scaling dropped";
  - "blend: delay scaled";
  - "blend: a boundary in the upper stretch";
  - "blend: no floor fallback";
  - "blend: delays of both directions";
  - "blend: counts from the number's own outcome";
  - "blend: a flight still listed counted";
  - "blend: delays over every flight";
  - "blend: bad week at 7 days";
  - "blend: airline of the number's own";
  - "blend: flat check below the floor".

  Run them.
- [ ] **Step 6: Commit** (`q27: the blend: each number's, airline's and the airport's records, and the two chances`).
- [ ] **Step 7: Review (Opus).**

### Task 5: The back-test

Implementer: integration (Opus). Design: `docs/flight-lookup.md`, "Before it ships: the back-test" (:346-348), :882, D13 (:113); "What this plan decided", the back-test.

**Files:**
- Create: `src/timeline/backtest.py`, `tests/test_backtest.py`
- Modify: `scripts/mutation_check.py` (`BACKTEST = ("src/timeline/backtest.py", ["tests/test_backtest.py"])`)

**Interfaces:**
- Consumes: `blend.records`, `cancel_chance`, `delay_chance`, `lead`, `EMPTY`; `counting.flights`, `cells`, `passings`, `stretches`, `holes`, `last_sighting`; `timeline.load.load`.
- Produces, in `timeline.backtest`:

```python
FLAGS = ("expected cancelled more than double the actual", "expected cancelled under half the actual",
         "the top tenth cancelled no more often than the rest")

@dataclass(frozen=True)
class Part:
    flights: int; cancelled: int; expected_cancelled: float; flew: int; delayed: int; expected_delayed: float

@dataclass(frozen=True)
class Report:
    first_day: date; last_day: date
    every: Part; top: Part; rest: Part           # split by the cancellation chance
    top_delay: Part; rest_delay: Part            # split by the delay chance
    flags: tuple[str, ...]                       # from FLAGS, in order; cancellations only

def week(snaps: list[dict]) -> tuple[date, date]
def run(table, obs, snaps) -> Report
def text(r: Report) -> str                       # fixed lines, counts and sums to 2 decimals
def main(argv: list[str] | None = None) -> int   # --model DIR [--out data/backtest]: prints text(), writes
                                                 # <out>/<model folder name>/report.txt; 0 unflagged, 1 flagged, 2 no model
```

- [ ] **Step 1: Write the failing tests** on a synthetic archive in rows (`tests/counting_helpers.py`), three weeks of flights with the last week's results known:
  - `test_the_week_is_the_last_seven_closed_israel_days`: moving the last sighting by one minute across the 48-hour line moves the week by a day.
  - `test_the_counts_are_cut_at_the_weeks_start`: a flight scheduled before the start is in the number's counts, and one inside the week is not.
  - `test_only_the_24_hour_rows_flights_are_scored`: a flight first listed 20 hours before its time is not scored.
  - `test_expected_and_actual`: four scored flights whose chances are hand-computed with the blend's formula; the sum and the counts.
  - `test_the_top_tenth_is_a_ceiling`: 11 flights give a top of 2, with ties broken by the flight key.
  - `test_each_flag`: expected 2.01 times the actual is flagged, 2.00 times is not; under half is flagged; a top tenth cancelled as often as the rest is flagged.
  - `test_the_report_text_and_exit_codes`: the file is written at its path; exit 0, 1 and 2; two runs write the same bytes.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_backtest.py -q`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** (`BACKTEST`):
  - "backtest: the week holds a day not closed";
  - "backtest: counts not cut";
  - "backtest: scored on the 3-hour row";
  - "backtest: flights outside the 24-hour row";
  - "backtest: top tenth rounded down";
  - "backtest: double flag at twice";
  - "backtest: half flag off";
  - "backtest: top-tenth flag reversed".

  Run them.
- [ ] **Step 6: Commit** (`q27: the back-test of the blend on the last closed week`).
- [ ] **Step 7: Review (Opus).**
- [ ] **Step 8 (main session):** `PYTHONPATH=src .venv/bin/python -m timeline.backtest --model data/model-<date>`. Write its numbers into "Back-test record" and give the report to the owner. If it is flagged, the owner chooses between shipping and changing the weights. A change of weights is a one-line change to `blend.py` and its tests, reviewed by Opus.

### Task 6: Words that carry figures, and the names list

Implementer: transcription (Sonnet). Design: `docs/flight-lookup.md`, "Words" (:358-515: "How numbers are written", the front page's table and total, the headline, every "Worked out from" form and what picks it, the lines in smaller type, the strip, other situations); `docs/site-redesign.md`, "Every page" (:149-173); Questions 5 and 6.

**Files:**
- Modify: `src/timeline/words.py`, `scripts/mutation_check.py` (`NAME_LIST = ("src/timeline/names.py", ["tests/test_names.py"])`)
- Create: `src/timeline/names.py`, `tests/test_names.py`
- Test: `tests/test_timeline_words.py`

**Interfaces:**
- Produces, in `timeline.words`:
  - Numbers (:368-379):
    - `pct1(k: int, n: int) -> str`: one decimal, halves up, in integers (the table, the tiles, the table's first line);
    - `average(k: int, n: int) -> str`: "under 1%" below 1%, else `pct1` (the all-airlines figures, the total's sentence);
    - `about(x: float) -> str`, `x` a share: "under 1%" below 0.01, else "about N%", whole, halves up (the chances, the delay averages);
    - `pct_range(rate: Rate) -> str | None`: "1.7% (between 1.1% and 2.9%)", the ends outward from `rate.one_in_from` and `one_in_to`.
  - The front page (:381-406):
    - `TABLE_HEADING`, `TABLE_COLUMNS` and `NOT_ENOUGH`;
    - `ROW_NAMES = {70: "3 days away", 48: "2 days away", 24: "1 day away", 12: "12 hours away", 6: "6 hours away", 3: "3 hours away"}`;
    - `table_first(first: str, last: str) -> str`;
    - `under_table(mean_flights: int, since: date) -> str`;
    - `DELAY_LEAD = "Chance of a delay of an hour or more:"` and `delay_line(departures: float, arrivals: float) -> str`;
    - `total_tiles(rate: Rate) -> list[tuple[str, str]]` and `total_sentence(rate: Rate, since: date) -> str`, both forms;
    - `late_line(late: int, cancelled: int) -> str | None` and `left_out(n: int) -> str | None`, each None at 0.
  - The flight page:
    - `headline(cancel: float, delay: float, ahead: bool) -> tuple[tuple[str, str], tuple[str, str]]`: each (label, figure), e.g. `("Chance it's cancelled:", "under 1%")`; `ahead=False` gives the "its next flight" forms;
    - `History` (frozen dataclass: `name: str`, `flights: int`, `cancelled: int`, `delayed: int`, `week: tuple[date, date] | None`);
    - `Worked` (frozen dataclass: `text: str`, `names_number_week: bool`, `names_airline_week: bool`);
    - `worked_out(number: History, airline: History, spoken: str | None, ahead: bool, listed_since: bool, text=str, data=str) -> Worked`: every form of :427-441, picked by :443-448;
    - `so_far(h: History, with_week: bool, text=str, data=str) -> tuple[str, str]`: (bold part, rest);
    - `partner(number: str, lead: str, spoken: str, text=str, data=str) -> str`;
    - `STRETCH_NAMES = {70: "2 to 3 days", 48: "1 to 2 days", 24: "12 to 24 hours", 12: "6 to 12 hours", 6: "3 to 6 hours", 3: "less than 3 hours"}`;
    - `all_airlines(h: int | None, cancel: str, delay: str, direction: str) -> tuple[str, str]`.
  - Freshness and situations:
    - `updated_at(t: datetime) -> str`: "Updated 17 Nov at 09:46", in Israel time;
    - `FRESH_REST = "Things may have changed, so check with your airline."`;
    - `has_passed(updated: datetime) -> str` (:489);
    - `MORE_THAN_3_DAYS` (:490);
    - `not_listed(number: str, last: date, still_listed: bool, text=str, data=str) -> str` (:491-492);
    - `MARKED_CANCELLED = ("This flight is marked cancelled.", "Contact your airline.")`.
  - The strip:
    - `strip_heading(number, text=str, data=str) -> str`;
    - `strip_key(counts: dict[str, int]) -> list[str]`, in `LABEL_ORDER` ("landed 22", "upcoming 3");
    - `mark_name(day: date, label: str) -> str` ("Tuesday 17 November, upcoming").
  - Retired: `PAST_ONLY`, `FROM_HERE_*`, `CHECKPOINT_NAMES`, `UNDER_TABLE`, `TOO_FEW`, `LEAD_INS`, `one_in_range`, `total`, `count_line`, `pair`, `condition` and the old `has_passed`, once Tasks 9 and 11 stop calling them. Each goes in the task that removes its last caller.
- Produces, in `timeline.names`:
  - `SPOKEN_NAMES: dict[str, str] = {"LH": "Lufthansa", "LO": "LOT", "LY": "El Al"}`: the approved lines' three, until the owner approves the list;
  - `spoken(code: str) -> str | None`;
  - `needed(records: blend.Records, table: list[dict], flights_: list[counting.Flight]) -> list[tuple[str, str, int, str]]`: (code, published name, counted flights, why), where why is "100 or more flights", "a grouping airline", or both, sorted by code;
  - `main(argv=None) -> int`: `--model DIR`; prints `needed` with each airline's spoken name or "missing"; exit 1 when one is missing.

- [ ] **Step 1: Write the failing tests:**
  - One exact-text test per line of every table in "Words" (:381-499), in each of its forms. Counts are taken from the table, and Question 6's proposed lines are included.
  - `test_the_picker` (:787):
    - a flight ahead or none;
    - 13 and 14 flights;
    - an airline of 99 and of 100;
    - a bad week with a flight since and with none;
    - a spoken name or none;
    - `names_number_week` and `names_airline_week` set exactly where the line gives those dates.
  - `test_rounding`:
    - `about(0.0099999) == "under 1%"`, `about(0.01) == "about 1%"`, `about(0) == "under 1%"`;
    - `about(0.095003) == "about 10%"`, `about(0.154306) == "about 15%"`, `about(0.125) == "about 13%"`;
    - `pct1(3, 2000) == "0.2%"`, `pct1(1, 2000) == "0.1%"`, `pct1(39, 5069) == "0.8%"`;
    - `average(39, 5069) == "under 1%"`, `average(71, 4472) == "1.6%"`;
    - `about(231 / 2982) == "about 8%"`, `about(149 / 3029) == "about 5%"`.
  - `test_pct_range_rounds_outward`: `one_in_from` 34.9 and `one_in_to` 90.1 give "(between 1.1% and 2.9%)"; an end at exactly 1 in 100 reads 1.0%.
  - `test_the_six_stretches_of_the_all_airlines_line`, with "under 1%" where the table prints 0.8%.
  - `test_updated_at_is_israel_time`, under `israeli_machine`.
  - `test_the_strip_key_names_each_kind_with_its_count`: LH 694's "landed 10 · cancelled 4 · unknown 1".
  - `test_names_needed` (`tests/test_names.py`): an airline at 99 and at 100 flights; a grouping airline at 3 flights, needed; an airline at 3 flights that no flight is grouped under, not needed; `main`'s exit codes.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_words.py tests/test_names.py -q`
- [ ] **Step 3: Implement.** Counts carry thousands separators.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:**
  - "words: under 1% at 1%";
  - "words: halves down";
  - "words: table rounded in floats";
  - "words: mostly from at 14";
  - "words: all airlines at 100";
  - "words: how soon it leaves in a mostly form";
  - "words: not on the list since, without the check";
  - "words: bad week dates left out";
  - "words: range rounded inward";
  - "words: stretch names shifted";
  - "names: an airline no flight is grouped under needed";
  - "names: a missing name exits 0".

  Run the entries of `src/timeline/words.py` and `src/timeline/names.py`.
- [ ] **Step 6: Commit** (`q27: the words that carry figures, and the names list`).
- [ ] **Step 7: Review (Opus).**
- [ ] **Step 8 (main session):** `PYTHONPATH=src .venv/bin/python -m timeline.names --model data/model-<date>`. Draft a plain spoken name for each missing airline, the name a traveller says aloud ("Lufthansa", not "LUFTHANSA"). Commit the draft list (`q27: draft spoken names, for the owner's approval`), reviewed by Opus. Keep the table for the hand check.

### Task 7: Fonts, the fourth upload and the font rule

Implementer: integration (Opus), with two reads by the main session. Design: `docs/site-redesign.md`, "Look A", typefaces and loading (:287-288), "How it is built", what q27 adds (:346-351), "Tests and checks" (:373-374, :380), "Left to the builder" (:392), "Unverified" (:412-413); Question 7.

**Files:**
- Create: `src/timeline/static/fonts/sans-cond-300.woff2`, `sans-cond-400.woff2`, `sans-cond-600.woff2` and `hebrew-sans-400.woff2`, copied from the local mockup folder `data/design-2026-11-17/v4/fonts/`; `src/timeline/static/fonts/LICENSE.txt`, from Step 1.
- Modify:
  - `src/timeline/build.py`: `render` returns `dict[str, str | bytes]`, the fonts as bytes under `fonts/`; `write_site` writes bytes as bytes.
  - `src/timeline/static/style.css`: the four `@font-face` rules of the mockup's sheet (lines 9 to 12) and its font stack.
  - `src/timeline/views.py`: `layout` preloads the 400 and 600 files, `<link rel="preload" href="{root}fonts/…" as="font" type="font/woff2" crossorigin>`.
  - `src/timeline/check.py:35`: the comment.
  - `scripts/publish.sh`: `upload '*.woff2' 'font/woff2'`.
  - `scripts/mutation_check.py`.
- Test: `tests/test_timeline_style.py`, `tests/test_timeline_build.py`, `tests/test_publish.py`

- [ ] **Step 1 (main session): the licence, read at its source.** Find the two releases the design names (`@ibm/plex-sans-condensed@2.0.0`, `@ibm/plex-sans-hebrew@1.1.0`) in IBM's Plex repository (github.com/IBM/plex). Fetch each release's licence file into a new, empty folder in the scratch area. Record in "Deviations": the URLs, the SHA-256 of each file, the licence's name and version, the copyright lines, the Reserved Font Name clause, and what the licence asks of a redistributed or modified font. Compare these with the design's note (`docs/site-redesign.md:287`: family names of their own, since the licence keeps "Plex" for unchanged files). Copy the text verbatim into `LICENSE.txt`, with the copyright lines the font files carry. If the licence asks for the notice on the site, stop at Question 7.
- [ ] **Step 2 (main session): the response headers.** Read AWS's documentation of the managed response headers policies, and record in "Deviations" the URL and what `Managed-SecurityHeadersPolicy` (ID `67f7725c-6f97-4210-82d7-5512b31e9d03`, `site-template.yaml:58`) sends. If it sends a Content-Security-Policy that would block a font from the site's own address, stop for the owner: nothing new on AWS.
- [ ] **Step 3: Write the failing tests:**
  - `test_the_four_font_files_and_their_licence_are_pinned` (the licence joined after Step 1: Deviations, Task 7): names, sizes (11,484, 11,440, 11,468 and 2,108 bytes, and 4,456 for the licence) and SHA-256. The main session checks the hashes against the mockup's files.
  - `test_fonts_load_only_from_the_sites_own_folder`. It replaces `test_nothing_loaded_from_elsewhere`:
    - `@import` is refused;
    - each `url(` stands inside an `@font-face` rule and names `fonts/<one of the four>`;
    - no scheme, host or `data:` address, and no image.
  - `test_the_hebrew_face_is_limited_to_the_hebrew_block` (`unicode-range: U+0590-05FF`), and `font-display: swap` on all four.
  - `test_every_page_preloads_the_regular_and_semibold_files`;
  - `test_the_font_files_and_their_licence_are_written_byte_for_byte`, and `test_only_html_css_js_the_four_fonts_and_their_licence_besides_the_marker`, which replaces the html-css-js test;
  - `test_five_uploads_each_with_its_content_type`: `*.woff2` as `font/woff2` and `*.txt` as `text/plain; charset=utf-8`, with `--delete` and `max-age=300` like the others.
- [ ] **Step 4: Run; fail.** `.venv/bin/pytest tests/test_timeline_style.py tests/test_timeline_build.py tests/test_publish.py -q`
- [ ] **Step 5: Implement.**
- [ ] **Step 6: Run; pass.** Then the full suite.
- [ ] **Step 7: Mutation entries:**
  - "style: a font from another host";
  - "style: an image in the sheet";
  - "style: the Hebrew face for every character";
  - "site: fonts not written";
  - "site: fonts read as text";
  - "views: no preload";
  - "publish: fonts not uploaded";
  - "publish: fonts with a guessed type".

  Retire "style: a web font". Run the entries of every file the task changed. A binary font file cannot be broken by the script; the pin test guards it.
- [ ] **Step 8: Commit** (`q27: the four font files, their licence, the fourth upload and the font rule`).
- [ ] **Step 9: Review (Opus).** The task is done only once Steps 1 and 2 are recorded.

### Task 8: Every page's top line, "Updated" and footer; the day page; the cancelled-flights page

Implementer: integration (Opus). Design: `docs/site-redesign.md`, "Every page" (:149-173), "Day page" (:233-245), "Cancelled flights" (:247-256), "Footer" (:266-279); `docs/flight-lookup.md`, "Pages", `fromhere.js` item 3 (:573); Question 6f.

**Files:**
- Modify: `src/timeline/views.py` (`layout`, `day_page`, `cancellations_page`, every caller of `layout`), `src/timeline/words.py` (the two pages' words), `src/timeline/build.py`, `scripts/mutation_check.py`
- Test: `tests/test_timeline_views.py`, `tests/test_timeline_build.py`

**Interfaces:**
- Consumes: `words.updated_at`, `NOTICE_GIVEN`, `Notice`; Task 1's footer.
- Produces, in `timeline.views`: `layout(title: str, body: str, root: str, updated: datetime, head_extra: str = "", front: bool = False) -> str`. The top line reads:
  - "Will It Fly?" linked to `index.html`: `<h1 class="wordmark">` when `front`, else `<p class="wordmark">`;
  - "Tel Aviv airport";
  - `<p class="updated" data-updated="YYYY-MM-DDTHH:MM:SSZ">Updated 17 Nov at 09:46</p>`, the instant being the model's naive UTC written as itself.

  Every page loads `<script src="{root}fromhere.js" defer></script>`. `day_page(info, flights_, updated)` and `cancellations_page(flights_, updated)` take the last sighting.
- Produces, in `timeline.words`:
  - `day_title(day: date, total: int, cancelled: int) -> str`;
  - `PART_MISSING`, `unknown_line(n: int) -> str | None`, `NO_DEPARTURES` and `NO_ARRIVALS`;
  - `CANCELLED_TITLE`, `CANCELLED_INTRO`, `CANCELLED_UNDER` and `CANCELLED_COLUMNS`;
  - `NONE_CANCELLED = "No cancelled flights so far."`.

- [ ] **Step 1: Write the failing tests:**
  - `test_every_page_says_when_it_was_updated`, under `israeli_machine`: each page's `data-updated` equals the last sighting as a Z instant, and its text is the date and time in Israel time.
  - `test_every_page_loads_fromhere_js`;
  - `test_the_top_line`: `<h1>` on the front page only; the name linked on every page.
  - `test_each_pages_tab_title`: "Monday 16 November", "Cancelled flights", "How this works".
  - The day page: one exact-text test per line of :239-243, with zeros left out of the title, the singular forms of Question 6f, the partial-day line, the unknown line and the empty lists. Its rows carry the notice sentence for a cancelled flight, and a list row the bracket.
  - The cancelled-flights page: the title, the introduction and the line under it; the columns; the list forms of the notice; the route "Tel Aviv to Moscow (ZIA), scheduled to leave at 05:35"; the phone prefix "Notice given: " in its own span; newest first; "No cancelled flights so far." with none.
  - Kept: `test_the_chart_counts_equal_the_day_pages` (`tests/test_timeline_build.py:303`).
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement**, with the mockup's top-line markup (`.mast`, `.wordmark`, `.where`, `.updated`).
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries:**
  - "views: updated instant in Israel time";
  - "views: no-script updated in UTC";
  - "views: fromhere.js only on flight pages";
  - "views: day title keeps a zero";
  - "views: bracket left out";
  - "views: the sentence in the notice column".

  Run the entries of every file the task changed.
- [ ] **Step 6: Commit** (`q27: every page's top line, "Updated" and footer, the day page and the cancelled-flights page`).
- [ ] **Step 7: Review (Opus).**

### Task 9: The front page and the search

Implementer: integration (Opus). Design: `docs/site-redesign.md`, "Front page" (:175-200), "Look A" ("Flights each day", :296), "Left to the builder" (:393); `docs/flight-lookup.md`, "Front page: the table" (:381-393), "Front page: the total" (:395-406), "Pages", front page (:546-553), :880-881; Questions 6e and 6f.

**Files:**
- Modify: `src/timeline/views.py` (`front_page`; `from_here` becomes `chance_table`; `_total`; `_story`; `chart_svg` becomes `chart`; the day list), `src/timeline/words.py` (the front page's other words), `src/timeline/build.py` (`render` computes `blend.records`, calls `blend.flat_delays`, passes the airport), `src/timeline/static/search.js`, `scripts/mutation_check.py`
- Test: `tests/test_timeline_views.py`, `tests/test_timeline_build.py`, `tests/test_timeline_search.py`

**Interfaces:**
- Consumes: Task 6's front-page words; `blend.Records`, `Airport`, `flat_delays`; `display.Summary`.
- Produces, in `timeline.views`:
  - `front_page(summary, airport: blend.Airport, story, recent, chart_days, all_days, entries, last_record) -> str`;
  - `chance_table(summary: Summary, airport: blend.Airport) -> str`: the heading, the first line (left out when the first or last row is below the floor), the table, the line under it and the delay line;
  - `chart(days: list[DayInfo]) -> str`: an `<ol class="chart">`. Each `<li><a href="day/…">` holds the date, its marks ("today", "upcoming", "upcoming · not all listed yet", "some flights missing"), the counts in text, and an inline `<svg class="bar">` with the cancelled part as a red block standing on the line and the unknown part outlined. The accessible name states the counts.
  - `day_list(days) -> str`: "Pick a day:" and every day, in `<div class="pick" id="days">`, which holds the line and `<ol class="days">`, so that the link to `#days` keeps "Pick a day:" in view.
- Produces, in `timeline.words`: `FIND_LABEL`, `SEARCH_HINT`, `FIND_HINT`, `FIND_OFF` (the before, link and after parts), `intro(since)`, `STORY_HEADING`, `RECENT_HEADING`, `ALL_CANCELLED`, `CHART_HEADING`, `PICK_A_DAY`, `TITLE` and `description()`, all verbatim from :184-200.
- Produces, the front page's search markup:

```html
<div class="find" id="find" hidden>
  <label class="find-l" for="search">Find your flight</label>
  <input id="search" type="search" placeholder="Flight number or city, like LY 001 or Paris" aria-describedby="find-hint">
  <div aria-live="polite"><ul id="search-results" hidden></ul></div>
  <p class="find-hint" id="find-hint">Your flight number is on your ticket or booking email.</p>
</div>
<p class="find-off" id="find-off">To find your flight, <a href="#days">pick its day below</a>.</p>
```

- Produces, in `search.js`:
  - the more line, "N more. Keep typing to narrow it down.";
  - for a query that matches nothing, one item, "No flight found. Check the number, or try a city. Flights show up here about 3 days before they leave.";
  - once the data reads, `#find` is shown and `#find-off` hidden;
  - unreadable data leaves both as built.

- [ ] **Step 1: Write the failing tests:**
  - `test_front_page_order`: the top line, the search, the introduction, the table's section, the total, the story, the recent cancellations, "Flights each day", the day list, the footer. The built-by line that stood above the footer is gone (`docs/site-redesign.md:198`).
  - The table:
    - its heading, first line, column heads and six rows at one decimal;
    - "Not enough flights yet" for a row below the floor;
    - the first line left out when the first or last row is below it;
    - the line under it with the mean to the nearest 500 ("about 5,000" from the 2026-11-17 rows' 4,922.8);
    - the delay line from the delay rates (7.7% and 4.9% read "about 8%" and "5%").
  - The total: the tiles and the sentence in both forms; no third tile below the floor; the late line, left out at zero; the left-out line.
  - The story: its heading; its title linked to its row; "Tuesday 17 November · scheduled to leave at 05:35"; the picker's skip (Task 3) at work in a build.
  - The recent cancellations under "Notice given", and "All cancelled flights".
  - `test_the_chart_is_a_list_of_links` and its marks.
  - `test_without_scripts_the_search_is_replaced_by_the_day_list_link`.
  - `test_the_description_and_title`.
  - `test_a_delay_row_off_by_more_than_a_point_stops_the_build`, through `render`.
  - Search, under Node: "12 more. Keep typing to narrow it down."; the "No flight found" line; titles in the new form; the wrapper shown and the no-script line hidden; unreadable data leaves both as built. The tests of the old more line are rewritten.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py tests/test_timeline_build.py tests/test_timeline_search.py -q`
- [ ] **Step 3: Implement.** Retire `words.FROM_HERE_*`, `UNDER_TABLE`, `TOO_FEW`, `CHECKPOINT_NAMES`, `total`, `count_line` and the old `late_line` with their last callers.
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries:**
  - "views: table to whole numbers";
  - "views: first line kept below the floor";
  - "views: about 5,000 from every row";
  - "views: third tile below the floor";
  - "views: late line at zero";
  - "views: search label shown without scripts";
  - "search: the old more line";
  - "search: nothing written when nothing matches";
  - "search: wrapper shown before the data reads";
  - "site: flat-delay check off".

  Retire the entries of the retired functions. Run the entries of every file the task changed.
- [ ] **Step 6: Commit** (`q27: the front page leads with "Find your flight", the chance by how soon you fly, and the total`).
- [ ] **Step 7: Review (Opus).**

### Task 10: The flight page: its frame, its days and the strip

Implementer: integration (Opus). Design: `docs/site-redesign.md`, "Flight page" (:202-231), "Names" (:133-139), "Labels" (:83), "What changed" (:113-125); `docs/flight-lookup.md`, "Pages", flight page (:555-567), "the strip of days" (:474-483), "other situations" (:485-507); Questions 2, 3, 6g and 6h.

**Files:**
- Modify: `src/timeline/views.py` (`flight_page` and its helpers), `src/timeline/build.py`, `scripts/mutation_check.py`
- Test: `tests/test_timeline_views.py`, `tests/test_timeline_build.py`

**Interfaces:**
- Consumes: Tasks 2, 3 and 6's words.
- Produces, `flight_page(rows, partners, others, updated) -> str`, with this markup contract. Task 11 fills `.chances` and `.support`; Task 12's script reads every name in it:

```html
<div class="flight-h"><h1>{d(title)}</h1><p class="who">…</p></div>
<div id="now">                        <!-- the traveller's day: the nearest with sched_utc_final > updated, whatever its label -->
  <section class="day" id="{anchor}" data-sched="2026-11-17T17:45:00Z">
    <p class="head">…date written out · time line · city when many · labels…</p>
    …label line, notice sentence, changed-back line, twin line or "This flight is marked cancelled. Contact your airline."…
    <div class="chances">…Task 11…</div>             <!-- only on a day labelled UPCOMING -->
    <p class="passed" hidden>…words.has_passed(updated)…</p>
    <div class="support">…Task 11…</div>             <!-- in the top day only -->
    <div class="own">…"Also sold as …", <details> What changed …</details>…</div>
  </section>
</div>                                <!-- no day ahead: <p class="none-line">…words.not_listed…</p> and the support -->
<section class="record"><h2>…strip_heading…</h2><p class="key">…</p><ol class="strip">…</ol></section>
<div class="later">…each later day ahead, soonest first, as a section.day with data-sched…</div>
<div class="past">…each past day, newest first, as a section.day with no data-sched…</div>
```

- Rules for the markup:
  - A day's lines come in the order of :225.
  - The expected-times note stands once, on the first day in page order that shows "expected", "landed around" or "left around".
  - `FINAL_NOTE` stands once, by :55's rule.
  - A strip mark is `<li><a class="s-{label}" href="#{anchor}" aria-label="{mark_name}" title="{mark_name}"><i></i><b>{day of month}</b></a></li>`; the first mark of each month is on `<li class="mo" data-mo="Nov">`.
  - "Still listed", for `not_listed`, means the newest row's `last_seen_at` is at or after `updated`.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_flight_page_order`: the traveller's day once, at the top; the strip; later days soonest first; past days newest first.
  - `test_a_day_ahead_stays_at_the_top_whatever_its_label`: marked cancelled; removed early; landed early, with its past-day time line (Question 2).
  - `test_a_day_ahead_marked_cancelled_while_its_twin_is_still_on` (Question 3).
  - `test_the_two_not_listed_lines`, on a model built through `model.build`, so that `last_seen_at` is the model's own.
  - `test_the_title_and_the_line_under_it`: one city, a departure, several cities, the Hebrew city with `lang="he" dir="rtl"`; "(as the airport lists it)" is gone.
  - The strip:
    - `test_the_strip_marks_every_day_oldest_first_and_links_it`;
    - `test_the_strip_key_counts_its_own_marks`;
    - `test_two_flights_on_one_day_are_two_marks` (Review Focus 5);
    - `test_the_months_name_over_its_first_mark`.
  - `test_the_two_once_a_page_notes_in_their_places`;
  - `test_the_scheduled_instant_is_the_models_utc`, under `israeli_machine`;
  - `test_the_page_holds_every_name_of_the_contract`: the names above, read from this plan's list in the test.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement.** The from-here block and its words leave the page. Task 11 puts the slot in their place.
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries:**
  - "views: later days newest first";
  - "views: past days oldest first";
  - "views: traveller's day by its label";
  - "views: strip key counts the flights";
  - "views: a month's name on every mark";
  - "views: the expected note on every day";
  - "views: not-listed line while still listed";
  - "views: marked-cancelled line beside the twin line".

  Retire the entries of the from-here block. Run the entries of every file the task changed.
- [ ] **Step 6: Commit** (`q27: the flight page puts the traveller's day first, then the strip, then the later and the past days`).
- [ ] **Step 7: Review (Opus).**

### Task 11: The flight page: the slot, the figures and the build's wiring

Implementer: integration (Opus). Design: `docs/flight-lookup.md`, "Flight page: the headline" (:408-421), the "Worked out from" line (:423-448), the lines in smaller type (:450-472), "Pages", flight page (:559-565), "Left to the builder" (:864-876); `docs/site-redesign.md:229`; Questions 1, 4, 5 and 6.

**Files:**
- Modify: `src/timeline/views.py`, `src/timeline/build.py` (`render`: the page's figures and the names stop), `scripts/mutation_check.py`
- Test: `tests/test_timeline_views.py`, `tests/test_timeline_build.py`

**Interfaces:**
- Consumes: `blend.Records`, `Tally`, `cancel_chance`, `delay_chance`, `row_for`, `STRETCHES`, `bad_week`, `lead`; `names.spoken`; Task 6's words.
- Produces: `flight_page(rows, partners, others, updated, records: blend.Records, flights_: list[counting.Flight]) -> str`. The page's airline is C8's grouping airline of the traveller's day, or of the newest day when none is ahead. The partner line stands when that airline is not the number's own, naming `blend.lead`'s number of that day's flight. Markup:

```html
<div class="chances">                 <!-- one pair per stretch still ahead of this day at the last update -->
  <div class="pair" data-after="6" data-upto="12">
    <p class="fig"><span class="fl">Chance it's cancelled:</span> <span class="fv"><span class="q">under</span> <b class="n">1%</b></span></p>
    <p class="fig"><span class="fl">Chance it's delayed an hour or more:</span> <span class="fv">…</span></p>
  </div>
  <div class="pair" data-after="3" data-upto="6" hidden>…</div>
</div>
<div class="support">
  <div class="none-ahead" hidden>…the two "its next flight" figures, scaled by the 70-hour row…</div>
  <p class="worked">…flight-ahead form…</p>
  <p class="worked none-ahead" hidden>…no-flight-ahead form…</p>
  <p class="s-line">…the number's "so far"… </p>  [<p class="s-line">…partner…</p>]  <p class="s-line">…the airline's…</p>
  <div class="aa" data-more-after="72">
    <p data-after="48" data-upto="72" hidden>…</p> …          <!-- six forms, one left out per row below the floor -->
    <p class="more" hidden>…MORE_THAN_3_DAYS…</p>
    <p class="off">…the form without a time…</p>
  </div>
  <p class="fresh"><span data-updated="…Z">Updated 17 Nov at 09:46</span>. Things may have changed, so check with your airline.</p>
  <p class="means"><a href="../how-it-works.html#what-the-numbers-mean">What the numbers mean</a></p>
</div>
```

- Rules for the slot:
  - A later day ahead labelled UPCOMING carries its own `.chances`, with the "it's" forms on one line.
  - With no day ahead, the `.none-ahead` parts show, the flight-ahead line is left out, and `.aa` holds `.off` only.
  - A page whose days ahead all carry no chances has no flight-ahead line (Question 1).
  - Without scripts the pair for the time left at the last update shows; the others and every timed `.aa` form are hidden.
  - The lines' inputs: `words.History` is built from a `blend.Tally` (its flights, cancelled and delayed counts, and `week = blend.bad_week(tally)`). `listed_since` holds when any of the page's rows is scheduled after the number's `Tally.last_cancelled`. The number's "so far" line carries its week when `Worked.names_number_week` is false (Question 6c), and the airline's when `Worked.names_airline_week` is false.
  - `render` raises ValueError naming, sorted, every airline a partner line needs that has no spoken name.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_slot_with_a_day_ahead`: LO 155's shape. The lines are "Chance it's cancelled: under 1%" and "about 1%"; "Worked out from this flight's history (none of its 22 flights was cancelled), LOT's history, and how soon it leaves."; and the three lines in smaller type, verbatim.
  - `test_the_slot_with_none_ahead`: LH 694's shape, "about 15%" on the 70-hour row, the "its next flight" forms, and the not-listed line.
  - `test_the_slot_when_the_traveller_day_carries_no_chances`: cancelled, removed early or landed early, with and without a later day carrying chances (Question 1).
  - `test_a_later_day_carries_its_chances_and_no_line_of_its_own`.
  - `test_prepared_pairs_only_for_stretches_still_ahead`: a day 31 hours ahead holds 5 pairs, the (24, 48] one shown.
  - `test_the_counts_agree`: the "so far" line, the "Worked out from" line and the strip key's departed, landed and cancelled marks all give 22 (LO 155's shape).
  - `test_a_twin_day_counts_as_flown_and_keeps_its_mark`, and the UNKNOWN case of Question 4.
  - `test_a_bad_week_names_its_dates_and_a_spread_one_does_not`;
  - `test_the_airlines_line_carries_its_dates_where_the_worked_out_line_does_not`: LH 694's page carries them and LH 697's does not.
  - `test_the_partner_line`: LY 9255 sold with LO 155 reads "LY 9255 is also sold as LO 155, so the numbers here are worked out from LOT's history.", above "LOT POLISH AIRLINES so far: …".
  - `test_one_airline_per_page_when_the_grouping_differs_by_day` (Review Focus 2).
  - `test_a_partner_airline_with_no_spoken_name_stops_the_build`.
  - `test_the_all_airlines_forms_and_bounds`: a departure's page reads "of departures"; a row below the floor leaves its form out; the form without a time uses 1.7%.
  - `test_no_page_prints_0_percent`, over a whole build: no "0%" stands as a word.
  - `test_the_freshness_line_without_scripts`.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement.** Retire `words.pair`, `condition`, the old `has_passed`, `LEAD_INS` and `PAST_ONLY` with their last callers.
- [ ] **Step 4: Run; pass.** Then the full suite. Then a timeline build on the real model (main session): `timeline.check` exits 0, and the largest flight page's bytes go in "Deviations".
- [ ] **Step 5: Mutation entries:**
  - "views: chances on a cancelled day ahead";
  - "views: worked-out line left out";
  - "views: every pair shown without scripts";
  - "views: pairs for stretches already behind";
  - "views: flight-ahead headline with none ahead";
  - "views: partner line with the published name";
  - "views: airline dates where the worked-out line gives them";
  - "views: no-flight-ahead chance from the 3-hour row";
  - "site: names stop off";
  - "site: the airline of each day".

  Run the entries of every file the task changed.
- [ ] **Step 6: Commit** (`q27: the flight page's headline slot: the two chances, what they were worked out from, and the lines under them`).
- [ ] **Step 7: Review (Opus).**

### Task 12: `fromhere.js`: the page's age and the move of the next day ahead

Implementer: integration (Opus). Design: `docs/flight-lookup.md`, "Pages", `fromhere.js` (:569-576), "Tests and checks", `fromhere.js` (:796-801); `docs/site-redesign.md`, "Every page" (:161-171); Task 10's and Task 11's markup; Review Focus 3.

**Files:**
- Modify: `src/timeline/static/fromhere.js`, `scripts/mutation_check.py` (`NAMES` points at the new tie test)
- Test: `tests/test_timeline_fromhere.py` (rewritten), `tests/test_timeline_views.py` (`test_the_block_holds_every_name_fromhere_js_reads` becomes `test_the_page_holds_every_name_fromhere_js_reads`)

**Interfaces:**
- Produces, as `module.exports`:
  - `age(updatedIso: string, nowMs: number) -> string | null`. Whole hours rounded down: under 1 (or negative) reads "Updated less than an hour ago"; 1, "Updated 1 hour ago"; 2 to 23, "Updated N hours ago"; 24 to 47, "Updated more than a day ago"; 48 and over, "Updated more than N days ago", with N whole days rounded down. It gives null for a time that does not end in "Z" or does not parse.
  - `pick(schedIso, nowMs, bounds, moreAfter)`, as today: an index, "more", "passed", "none" or null.
  - `plan(scheds: Array<string>, nowMs: number) -> {passed: number[], top: number | null} | null`: the days passed by the visitor's clock, and the first day still ahead; null when any time is unreadable.
- The page hook, on `DOMContentLoaded`:
  1. Every `[data-updated]` element's text becomes `age(…)`; this is the only text the script writes.
  2. On a flight page (`#now` with days), it reads `plan` over the top day and `.later`'s days.
  3. Each day still ahead shows the pair for its own time left in its `.chances`. Above 72 hours its first pair stays.
  4. Each passed day hides its `.chances` and shows its `p.passed`.
  5. When days have passed and one is still ahead, the script moves `.support` into that day, before its `.own`, and moves that day into `#now`. It moves the passed days to the head of `.past`, the latest first.
  6. When none is ahead, the latest passed day stays in `#now`, and the earlier ones go to `.past`. The `.none-ahead` parts show and the flight-ahead `.worked` hides. In `.aa` only `.off` shows.
  7. Otherwise `.aa` shows the form for the top day's stretch, or `.more` above 72 hours, or nothing for a stretch left out; `.off` hides.
  8. Any unreadable attribute leaves that part as built.

- [ ] **Step 1: Write the failing tests**, under Node and skipped visibly without it. A stand-in DOM in the test supports `getElementById`, `children`, `classList`, `getAttribute`, `hidden`, `insertBefore`, `appendChild`, `firstElementChild` and `querySelectorAll("[data-updated]")`, and throws on any text set outside a `[data-updated]` element.
  - `test_each_boundary_between_the_six_stretches`; more than 72 hours; a passed time.
  - `test_a_passed_day_with_a_later_day_ahead`: that day is at the top with its own pair, the support block inside it, and the passed day at the head of the past days.
  - `test_two_passed_days`: they sit newest first at the head of the past days.
  - `test_the_last_day_ahead_passed`: its "time has passed" line, the no-flight-ahead headline and line, and the form without a time; nothing says "isn't on the airport's list".
  - `test_the_age_at_each_boundary`: 59 minutes and 1, 2, 23, 24, 47, 48 and 168 hours, under `TZ=Asia/Jerusalem`, `TZ=UTC` and `TZ=America/Los_Angeles`; a negative age; an unreadable instant leaves "Updated 17 Nov at 09:46".
  - `test_the_script_writes_no_text_but_the_updated_line`;
  - `test_a_missing_or_unreadable_attribute_leaves_the_page_as_built`;
  - `test_a_page_with_no_day_ahead_changes_nothing_but_its_age`;
  - `test_the_page_holds_every_name_fromhere_js_reads` (views): every id, class and attribute name the script reads, read out of the script, stands in a built page.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_fromhere.py tests/test_timeline_views.py -q`
- [ ] **Step 3: Implement.** Parse with `Date.parse`, and refuse a string that does not end in "Z".
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries:**
  - "fromhere: 60 minutes reads less than an hour";
  - "fromhere: days rounded up";
  - "fromhere: a time without Z read as local";
  - "fromhere: a passed day left at the top";
  - "fromhere: passed days oldest first";
  - "fromhere: the support left behind";
  - "fromhere: no-flight-ahead headline kept hidden";
  - "fromhere: text written outside the updated line";
  - "fromhere: the stretch from the passed day";
  - "fromhere: a bad attribute changes the page".

  Retire the entries the rewrite makes STALE. Run the entries of `fromhere.js` and the `NAMES` ties.
- [ ] **Step 6: Commit** (`q27: fromhere.js writes the page's age and moves the next day ahead to the top when one passes`).
- [ ] **Step 7: Review (Opus).**

### Task 13: Look A, light and dark

Implementer: integration (Opus). Design: `docs/site-redesign.md`, "Look A" (:283-301), "Left to the builder" (:390-391, :393), "Tests and checks" (:375); the mockup's `style.css`, a local file.

**Files:**
- Modify: `src/timeline/static/style.css` (rewritten), `scripts/mutation_check.py`
- Test: `tests/test_timeline_style.py` (rewritten)

- [ ] **Step 1: Write the failing tests:**
  - The tokens `--paper`, `--ink`, `--soft`, `--hair`, `--tint` and `--red` in both schemes. The light values are :289's; the dark ones come under `@media (prefers-color-scheme: dark)`, with paper and ink swapped and a lighter red.
  - `test_text_pairs_clear_4_5_to_1` in both schemes: ink on paper and on tint, soft on paper and on tint, red on paper and on tint.
  - `test_red_only_for_cancelled`: every rule that uses `var(--red)` has a selector naming a cancelled thing.
  - `test_every_label_has_its_mark`: the six labels and DELAYED (:293), NO NEWS YET's dotted ring included, and the strip's five marks (:295).
  - `test_nothing_on_a_phone_under_13_px`;
  - `test_the_sheet`: 1,160 px wide at most and the gutters of :291;
  - `test_no_has_selector`, `test_hidden_wins`, `test_published_double_spaces_show`, `test_hebrew_city_is_isolated`, `test_tabular_numbers` and `test_a_3_px_focus_outline`;
  - `test_the_cancellations_table_stacks_on_a_phone_and_the_chance_table_does_not`.
  - Retired: the band's, the pills' and the from-here table's tests.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_style.py -q`
- [ ] **Step 3: Implement.** Port the mockup's sheet to the built markup. Write the day page, the cancelled-flights page and "How this works" from the same parts (:391). Choose the dark values by the rule and the test.
- [ ] **Step 4: Run; pass.** Then the full suite.
- [ ] **Step 5: Mutation entries:**
  - "style: dim soft text";
  - "style: dark red too dark";
  - "style: red on a rule not cancelled";
  - "style: NO NEWS YET without its mark";
  - "style: phone text under 13 px";
  - "style: the chance table stacks";
  - "style: thin focus outline".

  Retire the entries of the old look. Run the entries of `style.css`.
- [ ] **Step 6: Commit** (`q27: look A, light and dark`).
- [ ] **Step 7: Review (Opus).**

### Task 14: How this works

Draft: a Fable drafter dispatched by the main session. Code: transcription (Sonnet). Design: `docs/flight-lookup.md`, "How this works" (:582-603), "What the numbers mean" (:517-533); `docs/site-redesign.md`, "How this works" (:258-264).

**Files:**
- Modify: `src/timeline/views.py` (`how_it_works_page`), `src/timeline/words.py` (`HOW_OPENING`, and `WHAT_THE_NUMBERS_MEAN` as seven (bold lead, rest) pairs), `scripts/mutation_check.py`
- Test: `tests/test_timeline_views.py`, `tests/test_timeline_build.py`

- [ ] **Step 1 (main session): the draft.** Dispatch a fresh Fable drafter with:
  - the outline and the drafter's rules (:584-603): no table of airlines; ranges as percentages; the gate quoted as the built page has it, bar "No figure is given for one flight yet."; the delay chance counts only flights that flew; airline names are spelled as the airport spells them; DELAYED by the hour rule;
  - the owner's reading test;
  - the built page's text (`views.how_it_works_page` at 0f1b7e8);
  - the sections of both design documents it may draw facts from;
  - the check's word rules, with "I" allowed on this page.

  It returns sections 2 to 10 as text, with each figure that comes from the model marked as a slot. Check every factual sentence against its source before the draft goes to the implementer. A claim with no source is cut or marked for the owner.
- [ ] **Step 2: Write the failing tests:**
  - the opening (`docs/site-redesign.md:262`) and section 1 (:521-533), verbatim, with section 1 at `id="what-the-numbers-mean"`;
  - `ATTRIBUTION` on the page;
  - the gate's text as the built page has it, its first sentence gone;
  - the ranges from `words.pct_range` on a hand-made `Rate`;
  - the tag's link, the counting start and the gaps, as built;
  - the page passes the check.
- [ ] **Step 3: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py tests/test_timeline_build.py -q`
- [ ] **Step 4: Implement** the draft verbatim, with the model's figures in its slots. Remove the skip of the footer's `how-it-works.html#what-the-numbers-mean` link in `tests/test_timeline_build.py`'s link and anchor test (added in Task 1), so the anchor is checked again.
- [ ] **Step 5: Run; pass.** Then the full suite.
- [ ] **Step 6: Mutation entries:** "views: section 1 without its anchor", "views: the gate's first sentence kept", "views: a range rounded inward". Run the entries of every file the task changed.
- [ ] **Step 7: Commit** (`q27: How this works: the approved opening and "What the numbers mean", sections 2 to 10 drafted for the owner`).
- [ ] **Step 8: Review (Opus).**

### Task 15: The hand check (main session and the owner)

- [ ] **Step 1:** `sh scripts/sync.sh` (expected: it names account 137953273942's user and syncs receipts, then raw), then `PYTHONPATH=src .venv/bin/python -m model.build --raw data/raw --out data/model-<date>`, alone; record its time and peak memory (`/usr/bin/time -l`). If the build fails for memory, stop and tell the owner: the incremental build (q5) then comes first.
- [ ] **Step 2:** Build the site on it and run `timeline.check site`. Expected: exit 0.
- [ ] **Step 3:** Run the back-test on the same model, and write its numbers into "Back-test record".
- [ ] **Step 4:** Run `python -m timeline.names` on the same model. Expected: exit 0, with every needed airline holding a drafted name.
- [ ] **Step 5:** Record the page weights in "Deviations": the largest flight page and the whole site, against Task 0's.
- [ ] **Step 6: The owner looks**, in their own browser at 390 px and on a desktop, light and dark. The main session gives the paths: the front page, a clean flight, a flight with one bad week, a page with no flight ahead, a page with a cancelled or removed day ahead if one exists, a partner page, a day page, the cancelled-flights page and "How this works". The main session does not drive the browser.
- [ ] **Step 7: The owner approves**, or rewords, the names list and sections 2 to 10. The owner reads the back-test report; if it is flagged, the owner chooses between shipping and changing the weights.
- [ ] **Step 8:** The owner's words are folded in, by the main session or a Sonnet implementer, and reviewed by Opus. Rebuild, then check: exit 0. The main session commits the approvals with their date.

### Task 16: Whole-branch review (Fable)

- [ ] **Step 1:** A fresh Fable reviewer reads `git diff main...HEAD` against both design documents and this plan: the code, the tests, the mutation entries and the plan's Deviations.
- [ ] **Step 2:** Each finding is checked against its source. Fixes go to an Opus implementer, with a scoped Opus re-review. Then the full suite, the touched files' mutation entries, and a rebuild with its check. A fix that changes what a page shows goes back to the owner, who looks at that page again before Task 18.

### Task 17: Documents

Implementer: transcription (Sonnet). Every claim is checked against the code as built.

**Files:**
- Modify:
  - `docs/publishing.md`: step 5's four syncs (`*.woff2` as `font/woff2`); line 33's file types (the check reads `.html`, `.css` and `.js`, and the fonts are pinned by a test); line 47's publish tests; line 32's unofficial line; the cost of four more PUTs.
  - `README.md`: the site's name and its line (41), the claims line (55), the stack, and the design-notes lines. The counts at 27 and 56 come from Task 18. The screenshots and their alt text come after the upload.
  - `docs/README.md`: the lines for `site-redesign.md` (9) and `flight-lookup.md` (13), and one for this plan.
  - `docs/timeline.md`: "Five outsiders (from the review)" (line 54) becomes a pointer to `docs/flight-lookup.md`, "Five outsiders (q13)".
  - `docs/terms.md`: the clause 8 line (29) quotes the new `UNOFFICIAL`; the sentence that ends the clause 4 paragraph (40) states the check's rules as they now stand.
  - `docs/operations.md:97`: the script sentence (`fromhere.js` on every page). Its counts come from Task 18.
  - `docs/flight-lookup.md` and `docs/site-redesign.md`: their status lines say the build is done, to this plan; `docs/site-redesign.md:143` follows Question 8.
  - `docs/flight-lookup-plan.md` and `docs/site-redesign-plan.md`: one line at the head of each Appendix A, saying the page's text since q27 is in `views.how_it_works_page` (`docs/flight-lookup.md:37`).
- [ ] **Step 1: Update the documents.**
- [ ] **Step 2: Commit** (`q27: documents follow the build`).
- [ ] **Step 3: Review (Opus).**

### Task 18: Final verification (main session), then the push, the merge and the upload

- [ ] **Step 1:** `PYTHONPATH=src .venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95`. Expected: every test passes and coverage is 95% or more; record the count.
- [ ] **Step 2:** `.venv/bin/python scripts/mutation_check.py`, alone. Expected: "Every mutation was caught."; record the count.
- [ ] **Step 3:** `.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`, as CI runs it. Expected: no output.
- [ ] **Step 4:** Build the site on the latest model and run `timeline.check site`. Expected: exit 0.
- [ ] **Step 5:** Write Steps 1 and 2's counts into `README.md:27`, `README.md:56` and `docs/operations.md:97`, and commit (`q27: test and mutation counts`).
- [ ] **Step 6:** The push and the merge, each run by the main session on the owner's go, after `gh auth status` shows the project's own GitHub account. Then the upload: the owner reads the terms page's update date (`docs/terms.md:44`) and runs `! sh scripts/publish.sh` at the terminal.
- [ ] **Step 7:** After the upload, on the owner's go, retake the README's two screenshots from the live site and rewrite their alt text, in a commit of their own. "Unverified" in `docs/site-redesign.md:413` (a font served through CloudFront) is then settled by that upload: record it.

## Back-test record

Filled in by the main session after each run on the real model: the model, the week, the flights scored, the expected and actual cancelled and delayed flights, the top tenth against the rest, the flags, and the owner's choice. Not published on the site (D13).

- Run 1 (2026-11-17, main session, Task 5 Step 8), branch q27-t4 at f48c343, model `data/model-2026-11-17` (last sighting 07:46:44Z): the week 8 to 14 November (Israel days), 2,226 flights scored in the 24-hour row, each by its lead number; none left unscored.
  - Cancelled: 24 actual against 20.96 expected (1.15 times). The top tenth by the chance of cancelling: 9 of 223 (4.0%), expected 10.36. The rest: 15 of 2,003 (0.7%), expected 10.61.
  - Delayed an hour or more, of those that flew: 143 of 2,202 against 127.17 expected. The top tenth: 32 of 221, expected 34.69. The rest: 111 of 1,981, expected 92.48.
  - Flags: none ("Not flagged"); exit 0. 3.96 s, peak memory footprint 186 MB.
  - Checked beside it: of the 24 flights counted as cancelled (C2), all 24 carry the CANCELLED label (C10); none is a number cancelled while another is still listed.
  - The owner's choice: not flagged, so it ships (D13); reported to the owner on 2026-11-17.
- Run 2 (2026-11-17, main session, Task 15 Step 3), at 29c43ee, model `data/model-2026-11-17-2032` (last sighting 20:32:45Z): the same week, 8 to 14 November, since no later day is yet closed; the same 2,226 flights and the same figures as run 1; not flagged.

## Deviations

The executor appends here whenever reality forces a change from this plan: what changed, why, and the commit.

- Task 0 (2026-11-17, main session): the baseline on `data/model-2026-11-17` (last sighting 2026-11-17 07:46:44Z), built at abe26ca, whose code is that of 0f1b7e8. `timeline.check site` exits 0. Largest flight page: `site/flight/KL461-A.html`, 34,953 bytes. Whole site: 1,109 files, 17,960,040 bytes. The timeline build took 4.3 s (peak footprint 206 MB).
- Task 1 (2026-11-17): the footer links to `how-it-works.html#what-the-numbers-mean` before Task 14 writes that section, so `tests/test_timeline_build.py`'s link and anchor test skips that one link until then; Task 14, Step 4 removes the skip. The task also rewrote `tests/test_timeline_words.py`, which the task's file list did not name: it pinned the old `UNOFFICIAL` and `TIMES_NOTE`. Commit d08cca6.
- Task 1 (2026-11-17), review: the brief's worked-out rule ("worked out " anywhere in the lowercased text) was met by the partner line (`docs/flight-lookup.md:460`), which stands on the same flight pages, so a page missing its "Worked out from" line passed. The rule now matches the line's own capitalised start, `WORKED_OUT`, on the case-kept text (Task 1's interfaces amended).
- Task 7, Steps 1 and 2 (2026-11-17, main session):
  - The licence, read from the npm registry's published tarballs `@ibm/plex-sans-condensed@2.0.0` and `@ibm/plex-sans-hebrew@1.1.0` (https://registry.npmjs.org/@ibm/plex-sans-condensed/-/plex-sans-condensed-2.0.0.tgz and https://registry.npmjs.org/@ibm/plex-sans-hebrew/-/plex-sans-hebrew-1.1.0.tgz; each tarball's SHA-512 equals the registry's integrity value). Both declare "OFL-1.1" and carry the same `package/LICENSE.txt` (93 lines, 4,456 bytes, SHA-256 7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da): the SIL Open Font License 1.1, under "Copyright © 2017 IBM Corp. with Reserved Font Name "Plex"". A cut-down file is a Modified Version (the licence's definitions), and condition 3 bars a Modified Version from using the Reserved Font Name as its primary font name, so the files' own family names are required, not only chosen. Condition 2: each copy contains the copyright notice and the licence, "either as stand-alone text files, human-readable headers or in the appropriate machine-readable metadata fields within text or binary files as long as those fields can be easily viewed by the user."
  - The four files, read with fontTools 4.55.0: name 0 "Copyright 2019 IBM Corp. All rights reserved."; family names "FA Sans Condensed" (Light, SemiBold) and "FA Hebrew Sans"; name 13 "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: http://scripts.sil.org/OFL"; no WOFF2 metadata block. They carry a link to the licence, not its text, so the site serves `fonts/LICENSE.txt` (Question 7). The file is the release's text byte for byte: its first line is the notice condition 2 names.
  - The response headers, read from the live policy (`aws cloudfront get-response-headers-policy --id 67f7725c-6f97-4210-82d7-5512b31e9d03`, read-only): `Managed-SecurityHeadersPolicy` sets no Content-Security-Policy, so it cannot block a font from the site's own address. It sends `X-Content-Type-Options: nosniff` (Override true), so every upload sets its content type, as `publish.sh` already does. Nothing new on AWS.
  - Change to Task 7: the build also writes `fonts/LICENSE.txt`; `publish.sh` gets a fifth upload, `upload '*.txt' 'text/plain; charset=utf-8'`; the file-type test admits it.
- Task 2 (2026-11-17, 7ea2fe8): `words.shows_expected` added, the one rule for the time line's "expected" form and for where the expected-times note stands; `style.css` changed for the renamed label (`.l-no-news-yet`) and the phone prefix "Notice given: " (design `docs/site-redesign.md:109`), needed by the renames; `ListFlight.delayed` has no separate CANCELLED or UNKNOWN guard, since under C10 such a flight's rows are never delayed (a comment says so; a guard would be an equivalent mutant); the entry "display: DELAYED from the airport's word" targets `flights.py`, where the status word was read. Still on the pages until later tasks: the flight page's summary "with no final update" (Task 10) and the "How this works" glossary's old labels and "How much warning" (Task 14).
- Task 4, review (2026-11-17): the chance functions divided by zero on an airport with no counted flight, or a direction with none that flew; the build's tests run such small models. Both now return `None` there. A day whose chances are `None` carries no chances (Task 11, the structure of Question 1, so no new words), and the back-test leaves such a flight unscored (Task 5).
- Task 6, Step 8 (2026-11-17, main session): `python -m timeline.names` on `data/model-2026-11-17` lists 60 airlines: the 54 grouping airlines (as Question 5 counted them) and 6 more with 100 or more flights under their numbers (Aeromexico, Aerolineas Argentinas, Iberia, SAS, TAP, Virgin Atlantic), whose flights are always grouped under another airline, so no sentence names them. 57 had no spoken name; the main session drafted all 57 (76729d3 on q27-t4), four marked "check" for the owner (One Click, Sky Up Nistru, the Royal Australian Air Force, Transaero).
- Task 9, review (2026-11-17): the search box's `aria-label` overrode its new visible label "Find your flight" (WCAG 2.5.3, Label in Name), so the markup drops it and points `aria-describedby` at the hint. The delay line had a floor the design does not give, which made Question 6e's "under 1%" form unreachable in the small archives it was approved for; it is now left out only when a direction has no flight that flew.
- Task 11 (2026-11-17, 61b6739): `flight_page` takes a seventh argument, `by_id`, because the partner line names C8's lead number, which `blend.lead` finds from the flights table. Choices the design does not word: an airline's "so far" line with no flights is left out, as the number's is; when no "Worked out from" line is visible, both "so far" lines give their bad-week dates; the all-airlines block is left out when it would be empty. Retired with their last callers: `words.pair`, `condition`, `_updated`, `LEAD_INS`, `one_in_range` (`PAST_ONLY` was already gone).
- Task 11, Step 4 (2026-11-17, main session): the real-model build at e3eee1b (`data/model-2026-11-17`): 1,076 flight pages, 6.13 s, peak footprint 233 MB; `timeline.check` exits 0. Largest flight page `flight/LY8854-A.html`, 43,653 bytes (Task 0: 34,953, KL461-A); whole site 25,988 KB (Task 0: 17,960,040 bytes). LO 155's slot reads as the design's approved lines, with LOT's count now 137 flights.
- Task 15, Steps 1 to 5 (2026-11-17, main session): `sh scripts/sync.sh` after the owner's `aws login` (the session had expired; identity checked: account 137953273942, doron-admin); the model build on boards to 20:32:45Z: 360 s, peak memory footprint 8.14 GB, resident 1.46 GB (8 GB Mac; DuckDB spilled to `.tmp/` and cleared it). The site at 29c43ee: 1,080 flight pages, 1,118 files, 25,964 KB, 5.56 s, 224 MB; `timeline.check` exits 0; largest flight page `flight/LY8391-D.html`, 42,955 bytes (Task 0: 34,953). `timeline.names`: 60 airlines needed, none without a drafted name.
- The clean-up batches (2026-11-17): deferred review items done in two batches before the hand check (pages, words, search and guards; fonts, the page script's tests, the calculation, back-test and names), each reviewed; the red "Cancelled" line in a list of changes gained its markup hook (`li.is-cancel`, `span.w`). A worked example in batch A's brief had its two outcomes reversed; the implementer followed the rule, not the example.
- Task 15, Steps 6 to 8 (2026-11-17): I looked at the site built from the 20:32 UTC boards, at phone width and on a desktop, light and dark: it looks okay. I approved "How this works" sections 2 to 10 as drafted (the two lead-ins of section 9, section 4's sentence on the lean and section 10's lock sentence kept; the 15-minute refresh sentence left out), and the spoken names with the Royal Australian Air Force as "RAAF" (12f3aec). On the open questions I took the main session's recommendations: "This flight is marked cancelled." stays in ink; a cancelled day reads its notice, then the marked line; "already cancelled" stays in ink; DL 7472's count by the flight and mark by the number stand (Question 4); the lines built from approved parts stand; the chart's bars, the narrow-phone wrap and "today · some flights missing" stand; the sentences on "How this works" that rest on today's data stay and are re-read before each upload; `docs/terms.md` line 33 and `docs/flight-lookup.md:303` become "A chance is never "0%". Below 1%, it reads "under 1%"." (Task 17).
- Task 12 (2026-11-17) ran in two parts. The first (12c3dff, merged in f6281f0 after Task 10's commit) was written ahead of Tasks 10 and 11, to this plan's markup contract: it rewrote `fromhere.js` and its Node tests on a stand-in page, and retired the old tie test, `test_the_block_holds_every_name_fromhere_js_reads`, with the mutation entries that ran it. The second (6d67766), once Task 11 had built the page, is the new tie test, `test_the_page_holds_every_name_fromhere_js_reads`, with its mutation entries. Beyond the ways listed under "What this plan decided" (the flight page's markup contract), the script reads `#now`'s parent to find `.later` and `.past`.
- The possessive (2026-11-17, b88cfa5): an airline's spoken name ending in a lowercase "s" takes a bare apostrophe ("British Airways' history"); every other name takes "'s" ("Lufthansa's", "SAS's"). It holds in the "Worked out from" line and the partner line (`words.possessive`). The design's lines show only "'s" ("LOT's", "Lufthansa's"). The main session set the rule during the build; it was put to the owner by name after the whole-branch review, and the owner approved it on 2026-11-17. It applies to 21 of the 60 entries of `names.SPOKEN_NAMES`, 20 names, since Electra Airways stands under both 3E and EAF (counted at 3a06f5b by running `words.possessive` over every entry).
- "It hasn't been on the airport's list since." (2026-11-17, 184297e, the owner's ruling): a later flight of the number counts as "since" only if it was still on the airport's list after the last cancelled flight's scheduled time. A later flight that the airport had already removed by then does not count, so the line stands. `docs/flight-lookup.md` ("What picks a form") follows in Task 17.
- Task 13, review (2026-11-17, 765f97b): on a phone the total's three tiles had fixed tracks and figures that could not wrap. At 360 px the total of that day already scrolled sideways (a scroll width of 367 px), and a five-digit one ("12,345", "234") scrolled at 390 px too (391). The phone row now wraps, and its figures are `clamp(2rem, 10vw, 2.875rem)`. Measured with headless Chrome, both totals keep one line at 360 px and wider; narrower, the third tile wraps, and no width scrolls. Where the mockup and the design differ, the build took the design (`docs/site-redesign.md`, "Look A"): "Updated" in the heavier weight, where the mockup has the regular one, and links in ink, where the mockup's links take the colour of the text around them.
- Task 16 (2026-11-17): the Fable whole-branch review of 5765719..18e40a3 found the branch ready to merge after fixes: no Critical finding, three Important and ten Minor. Important 1 (a day ahead labelled DELAYED still showed its delay chance) was fixed in e87d2ba on the owner's call. Important 2 (the page's age and its top day worked out only once, when the page loads) was fixed in 3a06f5b. A scoped Opus re-review found both addressed, with no new Critical or Important finding. Important 3 (rulings missing from these Deviations) is Task 17, with Minor 8 (stale code comments) and Minor 9 (the page weights' units).
- Task 16, the DELAYED day (2026-11-17, e87d2ba, the owner's call): a day ahead that already carries DELAYED (the airport's expected time an hour or more after the scheduled time) shows the cancellation chance alone, in every prepared pair, on the traveller's day and on a later day. No new words: its label and its "scheduled … · expected …" line already say it is late. The "Worked out from" line and the "its next flight" forms are unchanged. Above 760 px such a day built at the top leaves the right half of the slot's two columns empty; one that the page script moves to the top fills the width.
- Task 16, the page script (2026-11-17, 3a06f5b): `fromhere.js` works the page's age and the top day out again whenever the page is shown again, not only when it loads: on `DOMContentLoaded`, on `pageshow` (a page the browser brings back from memory) and on `visibilitychange` once the tab is visible. Each step reads the page as it stands, so a second run moves only the days that have passed since the first. `showNoneAhead` now also sets the all-airlines line back to its form without a time, which an earlier run could have left in a timed form. The script still writes no text but the age.
- Page weights in bytes (Minor 9 of the review): Task 0 counted bytes, while Tasks 11 and 15 gave `du`'s KB, which counts disk blocks. Measured in bytes with `find site -type f` (the build's 55-byte marker included), the site at 3a06f5b, built from `data/model-2026-11-17-2032`, holds 1,118 files and 24,166,896 bytes (`du -sk`: 25,960 KB), about 35% more than Task 0's 17,960,040. Its largest flight pages are `flight/LY8391-D.html` and `flight/VY5284-D.html`, 42,955 bytes each (Task 0: 34,953).
- The suite and the mutation entries, beside the baseline of "Global Constraints": 1,210 tests and 510 entries at 0f1b7e8; 1,407 tests and 673 entries at 29c43ee; 1,453 tests and 678 entries at 3a06f5b (`PYTHONPATH=src .venv/bin/pytest -o addopts="" -q`: 1,453 passed; `len(mutation_check.MUTATIONS)`: 678). The final counts are Task 18's.
- Task 17 (2026-11-18): this task's file list was behind the build. With the fonts' licence, step 5 of `docs/publishing.md` has five syncs and an upload five more PUT requests, not four. Task 9's markup (`day_list`'s wrapper and the search results' live region) and Task 7's test names were brought up to the build in their steps above.

