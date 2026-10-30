# Site redesign (q18) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v1 history site with the plain-language redesign in `docs/site-redesign.md`: a cancellations-first front page, one page per flight number, plain words, the same tested, deterministic static build.

**Architecture:** Three new pure modules under `src/timeline/`: `words.py` (every sentence and label, time helpers, constants), `flights.py` (model rows to display rows, grouping, counts, anchors, addresses, search entries) and `views.py` (HTML). `build.py` wires them and writes the site; `pages.py` and its tests are deleted once the wiring lands (Task 6). `check.py` gains the new word rules; `search.js` searches every flight from JSON on the front page; `style.css` gets the new look with a contrast test.

**Tech Stack:** Python 3.13 (`.venv`), DuckDB over the model's Parquet files, pytest with coverage, Node (only for the search test, skipped where missing), plain HTML, CSS and JavaScript. No new dependencies.

**Spec:** `docs/site-redesign.md` (design v2, approved by the owner 2026-10-30). Executors read the spec's "Words", "Pages" and "Look" sections before their task; the spec's exact copy wins over any paraphrase here.

## Global Constraints

- Grade: production-lean, as v1: deterministic (same model, same bytes, across `PYTHONHASHSEED`), tested, mutation-checked.
- Run everything with `.venv/bin/...` and `PYTHONPATH=src` (tests: `.venv/bin/pytest`, configured in the repo).
- Model times (`*_at`, `*_utc`) are naive UTC: mark them UTC before converting (`.replace(tzinfo=timezone.utc)`); never compare an Israel wall-clock value with a UTC one.
- No "we", "our", "us" anywhere on the site; "I" only on `how-it-works.html` and in the built-by line.
- No data-collection words ("board", "snapshot", "stored", "observed", "receipt") outside `how-it-works.html`.
- No "took off", "operated by", "delayed by", "cancelled at", "canceled at", "minutes late", "hours late", "pause in our collection" anywhere.
- A cancellation never gets a single clock time; it gets "Between HH:MM and HH:MM".
- Only `.html`, `.css`, `.js` files in the built site; no images, fonts or JSON files.
- Every page: `<html lang="en">`, `<meta name="robots" content="noindex">`, the footer (`SOURCE_SHORT`, `UNOFFICIAL`, `TIMES_NOTE`, links, built-by).
- Every string from the airport's data (flight numbers, airline names, cities, airport codes) is rendered through `views.d()`, which wraps it in `<span class="d">…</span>` after `html.escape`.
- The mutation check (`scripts/mutation_check.py`) edits source files in place: run it alone, with nothing else running from the checkout.
- Do not push, call GitHub or AWS, or touch the collector (`src/collector/`, `template.yaml`).

## Review Focus

1. A future airline or city name containing a banned word as a whole word ("US-BANGLA AIRLINES") must not stop an upload: the word rules skip `<span class="d">` contents. Test in Task 8.
2. A search query with regular-expression characters ("LY+1", "(", "\\") must return results or none, never throw. Test in Task 7.
3. A model with no cancellations, or whose only cancellation has an unknown warning, must still build a front page (headline and story omitted, everything else present). Test in Task 5.
4. "Today" near midnight: a last record at 22:30 UTC is 00:30 Israel time on the next date, so the next date is today. Test in Task 3.
5. A flight number with characters outside letters and digits, or two numbers that sanitize to the same file, must give a stable address or stop the build, never overwrite a page. Test in Task 3.

---

### Task 1: `words.py`: constants, times, labels, warning

**Files:**
- Create: `src/timeline/words.py`
- Test: `tests/test_timeline_words.py` (new)
- Modify: `scripts/mutation_check.py` (add `WORDS = ("src/timeline/words.py", ["tests/test_timeline_words.py"])` and the entries below; add an optional filter: `python scripts/mutation_check.py <substring> [...]` runs only entries whose name contains one of the substrings, and no argument runs all). New entry names start with their area: "words: ", "flights: ", "views: ", "site: ", "search: ", "check: ", "style: ".

**Interfaces:**
- Produces, all in `timeline.words`:
  - `UNOFFICIAL` (exactly v1's text), `SOURCE_SHORT = "Flight data: Israel Airports Authority, published on data.gov.il."`, `TIMES_NOTE = "Times are Israel time."`, `PLACEHOLDER = "[owner's wording]"`, `BUILT_BY = PLACEHOLDER`, `CODE_URL = "https://github.com/doronreiffman/flights-archive"`, `DELAY_SENTENCE` (the spec's sentence, verbatim), `ISRAEL = ZoneInfo("Asia/Jerusalem")`.
  - `il_time(utc_naive: datetime) -> datetime`; `clock(local: datetime, page_date: date | None) -> str` ("14:46" on the page date, else "28 Oct 23:30"; `page_date=None` always shows the date).
  - `hours(n: int) -> str` ("1 hour", "7 hours").
  - Label names: `DEPARTED, LANDED, CANCELLED, UPCOMING, NO_FINAL_UPDATE, UNKNOWN = "DEPARTED", "LANDED", "CANCELLED", "UPCOMING", "NO FINAL UPDATE", "UNKNOWN"`; `LABEL_ORDER` in that order.
  - `main_label(outcome: str, sched_utc_final: datetime, last_fetch: datetime) -> str`; raises `ValueError("unknown outcome …")`.
  - `label_note(f: dict) -> str | None` (keys: `outcome`, `sched_utc_final`, `last_seen_at`).
  - `warning(f: dict) -> str | None` (keys: `outcome`, `direction`, `cancel_lead_min`, `cancel_lead_max_min`, `cancel_lead_censored`); None unless `outcome == "canceled"`.
  - `warning_note(f: dict) -> str | None`; `warning_sentence(text: str) -> str`.
  - `changed_back(f: dict, label: str) -> str | None` (key `uncanceled`; NULL is false).
  - `scheduled(direction: str, local: datetime, page_date: date | None) -> str` ("scheduled to leave 17:10" / "scheduled to land 13:50").
  - `last_expected(f: dict, page_date: date | None) -> str | None` (keys `est_local_final`, `sched_local_final`): "last expected 17:09" when both exist and differ.
  - `one_in(cancelled: int, known: int) -> int | None`; `headline(cancelled: int, known: int) -> str | None`.

- [ ] **Step 1: Write the failing tests** in `tests/test_timeline_words.py`. Move v1's `israeli_machine` fixture and its two time tests here, renamed to `words.il_time`. Then:

```python
@pytest.mark.parametrize("lo, hi, censored, direction, text", [
    (1400.95, None, True, "A", "at least 23 hours"),            # rule 1, IZ 992
    (60.0, None, True, "D", "at least 1 hour"),                  # rule 1 boundary
    (59.9, None, True, "D", "unknown"),                          # rule 2
    (-59.05, None, True, "D", "unknown"),                        # rule 2, ASY 991
    (-50.0, -10.0, False, "D", "none: cancelled less than an hour after it was scheduled to leave"),
    (-70.0, -30.0, False, "D", "none: cancelled about an hour after it was scheduled to leave"),
    (-142.75, -126.75, False, "D", "none: cancelled about 2 hours after it was scheduled to leave"),  # TO 3459
    (-142.75, -126.75, False, "A", "none: cancelled about 2 hours after it was scheduled to land"),
    (-200.0, -100.0, True, "D", "none: cancelled after it was scheduled to leave"),                  # rule 4
    (75.95, 2600.48, True, "D", "between 1 and 44 hours"),       # rule 5, LY 5409
    (445.95, 2970.48, True, "A", "between 7 and 50 hours"),      # rule 5, LY 5410
    (0.0, 2000.0, True, "D", "up to 34 hours"),                  # rule 6, boundary 0
    (-64.05, 2460.48, True, "D", "unknown: no records for that time"),  # rule 7, BZ 254
    (400.0, 416.0, False, "D", "at least 6 hours"),              # rule 8
    (0.0, 59.0, False, "D", "less than an hour"),                # rule 9, boundary 0
    (45.0, 74.0, False, "D", "about an hour"),                   # rule 10
    (59.9, 60.0, False, "D", "about an hour"),                   # rule 10, boundary 60
    (-10.0, 6.0, False, "D", "around the scheduled time"),       # rule 11
    (-10.0, 0.0, False, "D", "around the scheduled time"),       # rule 11, hi exactly 0
])
def test_warning_rules(lo, hi, censored, direction, text): ...  # words.warning(dict(outcome="canceled", ...)) == text
```

  Also, by exact value:
  - `warning` is None for `outcome="departed"` even with cancellation fields set.
  - `warning_note`: rules 1 and 2 give "The earliest record already showed it as cancelled."; rules 4 to 7 give "No records for part of that time."; rules 3 and 8 to 11 give None.
  - `warning_sentence`: "none: cancelled about 2 hours after it was scheduled to leave" → "No warning: cancelled about 2 hours after it was scheduled to leave."; "unknown: no records for that time" → "Warning unknown: no records for that time."; "unknown" → "Warning unknown."; "at least 23 hours" → "Warning: at least 23 hours."
  - `main_label`: departed → DEPARTED, landed → LANDED, canceled → CANCELLED, gap/vanished/dropped → UNKNOWN; open with `sched_utc_final` 2026-10-29 22:10 and `last_fetch` 2026-10-29 22:02:45 → UPCOMING; 21:55 → NO FINAL UPDATE; equal → NO FINAL UPDATE; "teleported" raises.
  - The Israel-zone trap: under `israeli_machine`, a flight dict with `sched_local_final` 2026-10-29 23:55 and `sched_utc_final` 2026-10-29 21:55, last fetch 22:02:45, gives NO FINAL UPDATE (only UTC values are passed in).
  - `label_note`: gap → "No records for the time it left the airport's list."; vanished with `sched_utc_final - last_seen_at` = 6 h 20 min → "Removed from the airport's list 6 hours before it was scheduled, with no final status. Not necessarily cancelled; it may have moved to another time."; 1 h 5 min → "… 1 hour before …"; dropped → "Removed from the airport's list with no final status."; others None.
  - `changed_back`: `uncanceled=True` with label LANDED → "Shown as cancelled for a while, then changed back."; with CANCELLED → "Cancelled, changed back, then cancelled again."; `None` and `False` → None.
  - `one_in`: (20, 951) → 50; (1, 22) → 20; (2, 45) → 25 (22.5, halves up); (1, 19) → 19; (2, 25) → 13 (12.5, halves up); (0, 10) → None. `headline(20, 951)` == "So far, 20 of 951 flights with a known outcome were listed as cancelled. That's about 1 in 50."; `headline(0, 951)` is None.
  - `scheduled("D", datetime(2026,10,29,17,10), date(2026,10,29))` == "scheduled to leave 17:10"; "A" → "scheduled to land …"; another page date → "scheduled to leave 29 Oct 17:10".
  - `last_expected`: est 17:09, sched 16:45 → "last expected 17:09"; equal → None; est None → None.
  - `hours(1) == "1 hour"`, `hours(0) == "0 hours"`.

- [ ] **Step 2: Run the tests; they fail** (`ModuleNotFoundError: timeline.words`). Run: `.venv/bin/pytest tests/test_timeline_words.py -q`

- [ ] **Step 3: Implement `src/timeline/words.py`.** `warning` is the spec's first-match table in order; `h(x, down)` is `math.floor(x / 60)`, `h(x, up)` is `math.ceil(x / 60)`. `one_in`: `r = known / cancelled`; `floor(r + 0.5)` below 20, else `5 * floor(r / 5 + 0.5)`.

- [ ] **Step 4: Run the tests; they pass.** Same command.

- [ ] **Step 5: Add mutation entries** (file `WORDS`), each breaking one rule with a one-line replacement: "warning rules out of order" (rule 8 checked before rule 3), "censored range rounded down at the top" (`ceil` → `floor` for `hi`), "first sight treated as censored range" (drop the `hi is None` branch), "around said as less than an hour" (rule 11 text), "NO FINAL UPDATE from local time" (compare `sched_local_final`), "equal time is upcoming" (`>` → `>=`), "one_in without halves up", "changed back on a NULL flag", "warning on a departed flight" (each name prefixed "words: "). Run alone: `.venv/bin/python scripts/mutation_check.py "words: "`. Expected: every entry CAUGHT.

- [ ] **Step 6: Commit**

```bash
git add src/timeline/words.py tests/test_timeline_words.py scripts/mutation_check.py
git commit -m "q18: words.py, labels and warning rules of the redesign"
```

### Task 2: `words.change_lines`: what changed

**Files:**
- Modify: `src/timeline/words.py`
- Test: `tests/test_timeline_words.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `il_time`, `clock` (Task 1).
- Produces: `change_lines(obs: list[dict], direction: str, page_date: date, gap_hours: float) -> list[tuple[str, str]]`: (left column, text) per line, oldest first. `obs` rows carry the model's observation columns (`observed_at`, `prev_observed_at`, `change_kind`, `changed_fields`, `sched_local`, `est_local`, `status`, `terminal`, `counters`, `zone`). `STATUS_WORDS: dict[str, str]`.

- [ ] **Step 1: Write the failing tests.** TO 3459's real history, page date 29 Oct, direction "D", `gap_hours=1`:

```python
def test_to3459_lines():
    assert words.change_lines(TO3459_OBS, "D", date(2026, 10, 29), 1) == [
        ("Earliest record (27 Oct 20:04)", "on time, terminal 1"),
        ("Between 27 Oct 20:24 and 14:29", "Check-in desks 345-348, zone B"),
        ("17:32", "Expected to leave at 17:38 instead"),
        ("18:32", "Expected to leave at 18:45 instead"),
        ("Between 19:16 and 19:32", "Cancelled"),
    ]
```

  with `TO3459_OBS` built from: first at 2026-10-27 18:04:46 UTC (ON TIME, est = sched = 2026-10-29 17:10, terminal 1, no counters, no zone); change at 2026-10-29 12:29:03 (prev 2026-10-27 18:24:46; counters "345-348", zone "B"); 15:32:45 (prev 15:16:45; est 17:38); 16:32:45 (prev 16:16:45; est 18:45); 17:32:45 (prev 17:16:45; status CANCELED). Note the gap line starts at `prev_observed_at` (20:24), not at the earliest-record line (20:04).
  Also:
  - Earliest record with everything: DEPARTED, est 17:09 against sched 16:45, terminal 1, counters "332-338", zone "C" → ("Earliest record (27 Oct 20:04)", "departed, expected to leave at 17:09, terminal 1, check-in desks 332-338, zone C").
  - One record changing est and status: ("16:02", "Expected to land at 19:36 instead, status “final”") for direction "A".
  - Statuses: `STATUS_WORDS` maps ON TIME→"on time", NOT FINAL→"“not final”", FINAL→"“final”", DELAYED→"delayed", LANDING→"landing", LANDED→"landed", DEPARTED→"departed", CANCELED→"cancelled", EARLY→"early"; an unmapped status appears lower-cased.
  - A cancellation seen within a minute of the previous record still gets "Between …".
  - A record whose only change is `status_he` (or a name field) gives no line.
  - Counters changing to None: "No check-in desks".
  - A retime record (`change_kind="retime"`, observed 2026-10-30 20:32:45 UTC, prev 20:16:45; previous record's `sched_local` 2026-10-30 23:30, its own 2026-10-31 01:10; page date 31 Oct): ("30 Oct 22:32", "Moved to a new scheduled time: 30 Oct 23:30 → 01:10"). The left column follows the same time-or-between rule as any change.

- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_words.py -q`
- [ ] **Step 3: Implement `change_lines`.** Phrases in this order within a line: cancellation ("Cancelled"), expected time, status, terminal, check-in desks, zone; joined with ", "; first letter capitalized. The earliest record lists status, expected time (only when it differs from the scheduled time), terminal, desks, zone.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** ("words: gap from the previous line" (use the previous rendered line's time), "words: cancellation given a single time", "words: Hebrew-only change shown", "words: retime not said"); run the filter; all CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: change lines in plain words"`).

### Task 3: `flights.py`: display rows, grouping, counts

**Files:**
- Create: `src/timeline/flights.py`
- Test: `tests/test_timeline_flights.py` (new)
- Modify: `scripts/mutation_check.py` (`FLIGHTS = ("src/timeline/flights.py", ["tests/test_timeline_flights.py"])`)

**Interfaces:**
- Consumes: `timeline.words` (Tasks 1 and 2).
- Produces, in `timeline.flights`:

```python
@dataclass(frozen=True)
class Row:                      # one row of the model's flights table, ready to show
    flight_id: str; airline: str; flight_no: str; airline_name: str; direction: str
    airport: str; city: str; city_he: str | None     # city title-cased (string.capwords)
    day: date                                          # date of sched_local_final
    sched_first: datetime; sched_final: datetime      # Israel wall-clock, as in the model
    label: str; delayed: bool
    warning: str | None; warning_note: str | None; label_note: str | None; changed_back: str | None
    last_expected: str | None
    page: str                                          # "flight/LY5115-D.html"
    anchor: str                                        # "2026-10-28-1630-KUT"
    group_id: str
    lines: tuple[tuple[str, str], ...]                # change_lines for its day

def make_rows(flights: list[dict], obs: list[dict], last_fetch: datetime, gap_hours: float) -> list[Row]
def row_anchor(sched_local_first: datetime, airport: str) -> str
def page_address(airline: str, flight_no: str, direction: str) -> str   # letters, digits, hyphen only
def check_unique(rows: list[Row]) -> None    # ValueError: two numbers on one file, or two rows on one anchor within a page
def group_flights(rows: list[Row]) -> list[tuple[Row, ...]]   # a "flight": same day and group, same label, delayed and warning
def partners(rows: list[Row]) -> dict[str, tuple[Row, ...]]  # flight_id -> the other members of its flight
@dataclass(frozen=True)
class DayInfo: day: date; total: int; cancelled: int; unknown: int; state: str; partial: bool   # state: "past" | "today" | "ahead"
def day_infos(flights_: list[tuple[Row, ...]], last_fetch: datetime, partial_days: set[date]) -> list[DayInfo]   # sorted by day
def headline_counts(flights_: list[tuple[Row, ...]]) -> tuple[int, int]   # (cancelled, known)
def featured(rows: list[Row], censored: dict[str, bool]) -> Row | None
def recent_cancellations(flights_: list[tuple[Row, ...]], n: int = 10) -> list[tuple[Row, ...]]
def number_keys(airline: str, flight_no: str) -> list[str]
def place_keys(city: str, airport: str) -> list[str]
def search_entries(rows: list[Row]) -> list[dict]   # {"n": [...], "p": [...], "t": "LY 001, Tel Aviv to New York" (the flight page's title), "u": "flight/LY001-D.html"}
```

- [ ] **Step 1: Write the failing tests** (flight and observation dicts like v1's `flight()` helper; values exact):
  - `row_anchor(datetime(2026,10,28,16,30), "KUT") == "2026-10-28-1630-KUT"`; `page_address("LY", "5115", "D") == "flight/LY5115-D.html"`; `page_address("6H", "0115A", "A") == "flight/6H0115A-A.html"`; `page_address("A B", "1/2", "D") == "flight/AB12-D.html"`.
  - `check_unique` raises `ValueError` matching "same page" for `("AB","12","D")` and `("A","B12","D")`, and matching "same anchor" for two rows of one number with the same first time and airport; LY 5115 at 16:30 to KUT and to BUS passes.
  - `make_rows`: city "NEW YORK" → "New York"; `delayed` True only for the row whose own observations include DELAYED (the same number on the next day stays False); label, warning and notes come from `words`.
  - `group_flights`: two members of one group with the same label → one flight; same group, one LANDED and one UNKNOWN → two flights; same group, one DELAYED → two flights.
  - `day_infos`: a day with 3 flights, 1 CANCELLED, 1 UNKNOWN → total 3, cancelled 1, unknown 1; with last fetch 2026-10-29 22:30 UTC (00:30 Israel on 30 Oct), 30 Oct is "today", 29 Oct "past", 31 Oct "ahead".
  - `headline_counts`: DEPARTED, LANDED, CANCELLED count as known; UPCOMING, NO FINAL UPDATE, UNKNOWN do not.
  - `featured`: picks the most recent CANCELLED row whose `censored[flight_id]` is False; when none, the CANCELLED row with the most `lines`; ties by `sched_final`, then airline and number; None without cancellations.
  - `recent_cancellations`: newest `sched_final` first, at most n, ties by airline and number.
  - `number_keys("LY","001") == ["ly001","ly1","001","1"]`; `place_keys("New York","JFK") == ["newyork","jfk"]`; `search_entries` for LY 5115 with rows to KUT and BUS has `p == ["batumi","bus","kutaisi","kut"]` (sorted union, deduplicated) and one entry per number and direction, sorted by airline, number, direction.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_flights.py -q`
- [ ] **Step 3: Implement.** "Today" is `words.il_time(last_fetch).date()`. `make_rows` reads `cancel_lead_censored` only through `words`; `featured` takes a `censored` map so the rule is visible in its signature.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** ("flights: today from the UTC date", "flights: delayed from any day of the number", "flights: group split ignores the label", "flights: unknown not counted", "flights: featured ignores censoring", "flights: address collision not refused", "flights: place keys from one row only"); run the filter; all CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: display rows, flights and counts"`).

### Task 4: `views.py`: layout, flight, day, cancellations and how-it-works pages

**Files:**
- Create: `src/timeline/views.py`
- Test: `tests/test_timeline_views.py` (new)
- Modify: `scripts/mutation_check.py` (`VIEWS = ("src/timeline/views.py", ["tests/test_timeline_views.py"])`)

**Interfaces:**
- Consumes: `words` constants and functions; `flights.Row`, `flights.DayInfo`, `flights.partners`.
- Produces, in `timeline.views`:

```python
def d(value) -> str                     # '<span class="d">' + html.escape(str) + '</span>'; "" for None
def layout(title: str, body: str, root: str, head_extra: str = "") -> str
def flight_page(rows: list[Row], partners: dict[str, tuple[Row, ...]], since: date) -> str
def day_page(info: DayInfo, flights_: list[tuple[Row, ...]]) -> str
def cancellations_page(flights_: list[tuple[Row, ...]]) -> str
def how_it_works_page(attribution: str, gaps: list[tuple[datetime, datetime]]) -> str
```

- [ ] **Step 1: Write the failing tests** (rows made with `flights.make_rows` from small dicts):
  - `layout`: `<html lang="en">`, the noindex meta, `<title>` escaped, and a footer holding `SOURCE_SHORT`, `UNOFFICIAL`, `TIMES_NOTE`, links to `{root}how-it-works.html` and `CODE_URL` ("Code on GitHub"), and "Built by " + `BUILT_BY`.
  - `d("<script>")` == `'<span class="d">&lt;script&gt;</span>'`.
  - Flight page for TO 3459 with three rows (27 Oct DEPARTED, last expected 17:09; 29 Oct CANCELLED with TO3459 lines; 1 Nov UPCOMING), `since=date(2026,10,27)`: title text "TO 3459, Tel Aviv to Paris"; "TRANSAVIA FRANCE" inside a data span followed by "(as the airport lists it)"; the airport line "lands at Paris (ORY)" (an arrival's says "leaves from New York (JFK)"); Hebrew city as `<span lang="he" dir="rtl">`; summary "Since 27 October: departed once, cancelled once, one upcoming."; rows newest first; the 29 Oct row is `<details open` with `id="2026-10-29-1710-ORY"`, "No warning: cancelled about 2 hours after it was scheduled to leave.", and the five change lines; the 27 Oct row shows "last expected 17:09"; `DELAY_SENTENCE` appears exactly once.
  - Summary words: counts per label in `LABEL_ORDER`: DEPARTED/LANDED/CANCELLED as "departed once", "landed twice", "cancelled 3 times"; UPCOMING as "one upcoming", "two upcoming", "3 upcoming"; NO FINAL UPDATE as "one with no final update"; UNKNOWN as "one unknown".
  - A number with two cities (LY 5115 to KUT and BUS): title "LY 5115, from Tel Aviv", each row shows its city, no Hebrew city in the header.
  - Codeshare line in a row: "Probably the same flight as DL 7426 and AM 7895 (same time, terminal and check-in desks)." with each number linked to its page and anchor.
  - `label_note`, `changed_back` and `warning_note` lines appear when set.
  - Day page for 29 Oct: `<h1>Thursday 29 October 2026</h1>`; "418 flights · 7 cancelled · 190 unknown" shape ("· N cancelled" and "· N unknown" only when above 0); partial → "Incomplete: some of this day's flights may be missing from the records."; unknown > 0 → "No records for the time 190 of these flights left the airport's list."; departures then arrivals; each row links `../flight/<file>#<anchor>`; no change lines.
  - Cancellations page: newest first, columns date, flight, route with "scheduled to leave/land", warning text.
  - How-it-works page: contains the full `ATTRIBUTION`, each gap as "There are no records from 27 October 20:24 to 29 October 14:29." (Israel time, dates always shown), and the copy in Appendix A of this plan verbatim.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py -q`
- [ ] **Step 3: Implement.** Pure functions returning strings, like v1's `pages.py`. Every data string through `d()`.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** ("views: data not escaped", "views: cancelled row closed", "views: delay sentence on every row", "views: Hebrew city without lang", "views: footer without the short source", "views: noindex dropped", "views: day link without anchor"); run the filter; all CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: flight, day, cancellations and how-it-works pages"`).

### Task 5: `views.front_page` and the chart

**Files:**
- Modify: `src/timeline/views.py`
- Test: `tests/test_timeline_views.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 4's `layout`, `d`; `flights.DayInfo`, `flights.Row`; `words.headline`, `words.warning`.
- Produces:

```python
def chart_svg(days: list[DayInfo]) -> str          # inline SVG, one horizontal bar per day
def search_json(entries: list[dict]) -> str         # json.dumps(sort_keys=True, ensure_ascii=False) with "<" as "<"
def front_page(cancelled: int, known: int, story: Row | None, recent: list[tuple[Row, ...]],
               chart_days: list[DayInfo], all_days: list[DayInfo], entries: list[dict], last_record: datetime) -> str
```

- [ ] **Step 1: Write the failing tests:**
  - `<title>Cancelled flights at Tel Aviv airport (Ben Gurion)</title>`; `<meta name="description" content="…">` with the spec's description and `BUILT_BY`; `og:title`, `og:description`, `og:type` "website"; no `og:image`.
  - `<h1>Cancelled flights at Tel Aviv airport</h1>` and the spec's lede, verbatim.
  - The headline sentence from `words.headline(20, 951)`; absent when `cancelled == 0`.
  - The story box: TO 3459's title line, its change lines, a link to `flight/TO3459-D.html#2026-10-29-1710-ORY`; absent when `story` is None.
  - The search input (hidden until script runs, `hidden` attribute), its placeholder "Flight number or city, e.g. LY 001 or Paris", and `<script type="application/json" id="flights-data">` whose text is `search_json(entries)`; an entry text containing `</script>` appears as `</script>`.
  - Recent cancellations: at most 10 entries, links carry anchors, a link to `cancellations.html`.
  - Chart: one bar per day in `chart_days`; text per day "370 flights · 8 cancelled · 190 unknown" (same shape as the day page); classes `today`, `ahead`, and the word "incomplete" for partial days; each bar inside `<a href="day/2026-10-28.html">`; the SVG's `aria-label` states the days and counts.
  - The day list links every day in `all_days`.
  - "Last updated 30 Oct 2026, 00:02" for a last record at 2026-10-29 22:02:45 UTC.
  - The built-by line: "Built by " + `BUILT_BY` + " · How this works · Code on GitHub" with both links.
  - Review Focus 3: `front_page(0, 900, None, [], days, days, entries, t)` builds and has the search box, chart and day list.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_views.py -q`
- [ ] **Step 3: Implement** `chart_svg`, `search_json` and `front_page` in `views.py`; horizontal bars so 14 or more days fit a phone.
- [ ] **Step 4: Run; pass.** Same command.
- [ ] **Step 5: Mutation entries** ("views: headline at zero", "views: search data not escaped", "views: recent not capped", "views: unknown left off the chart", "views: last updated from the first record"); filter; all CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: front page and chart"`).

### Task 6: Wire `build.py`; retire `pages.py`

**Files:**
- Modify: `src/timeline/build.py`
- Delete: `src/timeline/pages.py`, `tests/test_timeline_pages.py`
- Rewrite: `tests/test_timeline_build.py`
- Modify: `scripts/mutation_check.py` (delete the `PAGES` tuple and every entry using it; keep and update the `SITE` entries that still apply; add new ones)

**Interfaces:**
- Consumes: everything above.
- Produces: `render(flights, obs, snaps) -> dict[str, str]` with keys `index.html`, `how-it-works.html`, `cancellations.html`, `day/YYYY-MM-DD.html`, `flight/<file>.html`, `search.js`, `style.css` (no `methodology.html`). `build()` returns `{"days": …, "flight_pages": …, "flights": …}`; the CLI prints "7 day pages, 949 flight pages, 3125 flight numbers -> site/index.html".

- [ ] **Step 1: Rewrite `tests/test_timeline_build.py`** end to end with `make_site` and `model_helpers` (kept from v1), covering:
  - every `flights` row on exactly one flight page (by anchor) and on exactly one day page (by link);
  - a retime across midnight (23:30 → 00:30) lands on the day of the final time, keeps the anchor of the first, and its line says "Moved to a new scheduled time";
  - LY 5115 twice at 16:30 (KUT, BUS) gives two anchors on one page;
  - a NULL final scheduled time stops the build ("no final scheduled time");
  - the marker refusal, the leftover clearing, and the two-process determinism tests from v1, unchanged in substance;
  - every page has `SOURCE_SHORT`, `UNOFFICIAL`, `TIMES_NOTE` and noindex; `how-it-works.html` has `ATTRIBUTION`; no page contains any of `check.BANNED`;
  - a cancellation end to end: the front page's warning column and the flight page's sentence agree;
  - a pause of three hours: the day page's unknown line and the how-it-works gap line;
  - a partial first day: "incomplete" on the chart and the day page;
  - `site/` contains only `.html`, `.css`, `.js` files besides the marker.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_build.py -q`
- [ ] **Step 3: Implement `render`** with `flights.make_rows`, `check_unique`, `group_flights`, `day_infos` (partial days from the existing `BOARD_KEEPS` / `BOARD_AHEAD` rule), the chart's last 14 days with flights plus all later days, `featured` (censored map from the flights rows), and the views. Delete `pages.py` and its test file; move any import of `pages` (in `check.py`, tests) to `words`.
- [ ] **Step 4: Run the whole timeline suite; pass.** `.venv/bin/pytest tests/test_timeline_*.py -q`
- [ ] **Step 5: Mutation entries** (keep "foreign folder replaced", "only the output folder checked", "undated flights not refused", "partial only at the end/start", "day by first scheduled time"; add "site: methodology page still written", "site: chart without later days", "site: unique check skipped"); filter "site: " and the kept names; all CAUGHT. Run `.venv/bin/python scripts/mutation_check.py` in full once: no STALE entries.
- [ ] **Step 6: Commit** (`git commit -m "q18: build the redesigned site; v1 pages retired"`).

### Task 7: Search across every flight

**Files:**
- Rewrite: `src/timeline/static/search.js`
- Test: `tests/test_timeline_search.py` (new; the v1 Node test moves here)
- Modify: `scripts/mutation_check.py` (`SEARCH` now points at `tests/test_timeline_search.py`)

**Interfaces:**
- Consumes: the `#flights-data` JSON (`search_json`, Task 5) and the `#search` input on the front page.
- Produces: `search.js` exporting `normalise(query)`, `rank(query, entries) -> {shown: entries[], more: number}` (Node `module.exports`).

- [ ] **Step 1: Write the failing Node-driven tests** (skipped visibly without Node), with entries for LY 001 (JFK, New York), LY 0010 (LHR, London), IZ 991 (JFK), 6H 0115A (ETM, Eilat):
  - "ly 001" → LY 001 first (exact), then LY 0010 (number prefix);
  - "1" → exact bare-number matches first ("1" is LY 001's bare number), then prefix matches;
  - "new york" → LY 001 and IZ 991 (places), ordered by airline and number;
  - "" → nothing shown, `more == 0`;
  - 12 matches → 10 shown, `more == 2`;
  - Review Focus 2: "LY+1", "(", "\\" return without throwing.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_search.py -q`
- [ ] **Step 3: Implement `rank`** (plain string comparisons, no regular expressions built from the query) and the page hook: read `#flights-data`, unhide `#search`, render up to 10 links into a results list, then "N more: type more of the number or city" when `more > 0`.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** ("search: places ranked before numbers", "search: no cap", "search: matches anywhere in a key", "search: keeps spaces"); filter; all CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: search every flight from the front page"`).

### Task 8: The upload check's new rules

**Files:**
- Modify: `src/timeline/check.py`
- Test: `tests/test_timeline_check.py`, `tests/test_publish.py` (footer constant)
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `words.SOURCE_SHORT`, `words.UNOFFICIAL`, `words.PLACEHOLDER`, `words.BUILT_BY`, `model.report.ATTRIBUTION`.
- Produces: `scan(site) -> list[tuple[str, str]]` (file, phrase or word) and `missing_notices(site)` with the new rules; `main` unchanged in shape (exit 0, 1, 2).

- [ ] **Step 1: Write the failing tests:**
  - Pronouns as whole words, case-insensitive, any scanned file: "We", "our", "US" (alone) are hits; "were", "hours", "status", "BUS", "AUSTRIAN AIRLINES", "at least 23 hours", "So far, 20 of 951 flights …" are not.
  - "I" as a whole word, case-sensitive, in `.html` pages other than `how-it-works.html`, after removing the text of `BUILT_BY`: a hit on `index.html`, none on `how-it-works.html`, none for "i" lower-case.
  - Data-collection words ("board", "boards", "snapshot", "stored", "observed", "receipt", "receipts") as whole words, case-insensitive, on `.html` pages except `how-it-works.html`.
  - Review Focus 1: text inside `<span class="d">US-BANGLA AIRLINES</span>` and `<span class="d">BOARD AIR</span>` is not a hit for the word rules (the phrase rules still scan everything).
  - "minutes late" and "hours late" join `BANNED`; v1's banned-phrase tests stay.
  - `PLACEHOLDER` anywhere is a hit named "built-by placeholder".
  - Notices: `SOURCE_SHORT` and `UNOFFICIAL` required on every page; `ATTRIBUTION` required on `how-it-works.html` only; the v1 notice tests updated to these constants.
  - A mutation guard test: the whole-word matcher must not match "hours" for "our".
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_check.py tests/test_publish.py -q`
- [ ] **Step 3: Implement.** Word rules use `re.compile(r"\b(?:we|our|us)\b", re.I)` style patterns on the tag-stripped, entity-unescaped text with `<span class="d">[^<]*</span>` removed first.
- [ ] **Step 4: Run; pass.**
- [ ] **Step 5: Mutation entries** ("check: pronouns as substrings", "check: data spans not skipped", "check: I allowed everywhere", "check: data words on how-it-works", "check: placeholder allowed", "check: attribution required everywhere"); filter; all CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: upload check for the new words"`).

### Task 9: The look

**Files:**
- Rewrite: `src/timeline/static/style.css`
- Test: `tests/test_timeline_style.py` (new)
- Modify: `scripts/mutation_check.py` (`STYLE = ("src/timeline/static/style.css", ["tests/test_timeline_style.py"])`)

**Interfaces:**
- Consumes: the class names the views emit (`d`, pill classes, `today`, `ahead`, the story box, the results list); read them from `views.py` before writing CSS.
- Produces: CSS custom properties on `:root` (light) and inside `@media (prefers-color-scheme: dark) { :root { … } }`: `--bg`, `--fg`, `--muted`, `--line`, `--accent`, `--card`, `--cancel-fg`, `--cancel-bg`, `--ok-fg`, `--ok-bg`, `--plain-fg`, `--plain-bg`, `--delay-fg`, `--delay-bg`, `--unknown-fg`.

- [ ] **Step 1: Write the failing test:** parse both blocks' custom properties (hex colors) and assert WCAG contrast ≥ 4.5 for, in each scheme: (`--fg`,`--bg`), (`--muted`,`--bg`), (`--accent`,`--bg`), (`--fg`,`--card`), (`--muted`,`--card`), (`--cancel-fg`,`--cancel-bg`), (`--ok-fg`,`--ok-bg`), (`--plain-fg`,`--plain-bg`), (`--delay-fg`,`--delay-bg`), (`--unknown-fg`,`--bg`). Also assert no `@import`, no `url(` and no `font-face` in the file.
- [ ] **Step 2: Run; fail.** `.venv/bin/pytest tests/test_timeline_style.py -q`
- [ ] **Step 3: Write `style.css`:** one column, max width about 42rem, system font stack, tabular numbers; pills; story box; tables stacking under 600px (no fixed column widths); chart text tokens; change lines keep their time beside them at 375px.
- [ ] **Step 4: Run; pass.** Record each pair and its ratio in `docs/site-redesign.md`, "Deviations" (create the section).
- [ ] **Step 5: Mutation entry** ("style: pale cancel text" (lighten `--cancel-fg`)); filter; CAUGHT.
- [ ] **Step 6: Commit** (`git commit -m "q18: the look, light and dark"`).

### Task 10: Documents and full verification

**Files:**
- Modify: `docs/timeline.md` (the "Pages", "Wording", "How it is built" and "Tests and mutation checks" sections become one pointer each to `docs/site-redesign.md`; the review and history sections stay), `docs/terms.md` ("What it asks of us": clause 6 and 8 paragraphs name `SOURCE_SHORT` and `UNOFFICIAL` on every page and `ATTRIBUTION` on how-it-works; clause 4 names the "Words" rules of `docs/site-redesign.md` and the new check), `docs/publishing.md` (the footer and notices lines), `CLAUDE.md` (the claims-discipline line in plain words; "Current state": the site is v2), `README.md` (replace "when we first saw it" and the quoted "first observed CANCELED on the public board" sentence with the new wording), `docs/site-redesign.md` (Deviations).

- [ ] **Step 1: Update the documents** as listed; every claim in them checked against the code just written.
- [ ] **Step 2: Full test run.** `.venv/bin/pytest --cov=collector --cov=model --cov=timeline --cov-fail-under=95` → all pass, coverage ≥ 95%.
- [ ] **Step 3: Full mutation check, alone.** `.venv/bin/python scripts/mutation_check.py` → "Every mutation was caught."; record the new count.
- [ ] **Step 4: Template lint.** `.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml` → no output.
- [ ] **Step 5: Real build.** `PYTHONPATH=src .venv/bin/python -m model.build --raw data/raw --out data/model`, then `PYTHONPATH=src .venv/bin/python -m timeline.build --model data/model --out site`, then `PYTHONPATH=src .venv/bin/python -m timeline.check site` → exit 1 with only "built-by placeholder" hits (the owner writes that line before any upload). Open `site/index.html`, a flight page and a day page at 375 px and at desktop width, in light and dark: no sideways scroll, nothing unreadable.
- [ ] **Step 6: Commit** (`git commit -m "q18: documents follow the redesign"`).

## Appendix A: "How this works" copy (verbatim; the owner reviews the first-person lines)

> ## Where the data comes from
> The Israel Airports Authority publishes Ben Gurion Airport's list of departures and arrivals on data.gov.il, the Israeli government's open-data site. The list shows each flight from about three days before it is scheduled until about a day after. I built a small program that checks the list every 2 minutes and saves each new version, so a flight's history stays after it drops off the list.
>
> {ATTRIBUTION}
>
> ## What the labels mean
> - DEPARTED and LANDED: the airport's final word on the flight.
> - CANCELLED: the airport's list showed the flight as cancelled.
> - UPCOMING: still on the list; its scheduled time hasn't come yet.
> - NO FINAL UPDATE: its scheduled time has passed, and the list hasn't given a final status yet.
> - UNKNOWN: it left the list without a final status, or while records are missing.
> - DELAYED: shown beside another label when the airport's list said "delayed" at some point.
>
> ## How much warning
> For a cancelled flight, the warning is how long before its scheduled time the list already showed it as cancelled. The list refreshes about every 15 minutes, so the change is known to within that window. Where records are missing, the warning is a range ("between 7 and 50 hours"). When a flight was already cancelled the first time it appeared in the records, only a lower limit is known ("at least 23 hours"). For the same reason, the time of a cancellation is always given as a range. The airline may have told passengers earlier than the list showed.
>
> ## Why there are no delay figures
> The list gives an expected time for each flight. It doesn't say whether that is when the plane leaves the gate or when it takes off. Until that is settled, this site shows the airport's times as they are and doesn't turn them into delay figures.
>
> ## "Final" and "not final"
> The airport also uses the words "final" and "not final". It doesn't publish what they mean, so this site quotes them as they are.
>
> ## Probably the same flight
> Airlines often sell seats on one flight under several flight numbers. When numbers share the same time, terminal and check-in desks, this site lists them as probably the same flight. The list doesn't say so itself, and arrivals with no check-in desks can occasionally be grouped by mistake.
>
> ## Gaps in the records
> Records start on the evening of 27 October 2026. {one sentence per gap: "There are no records from 27 October 20:24 to 29 October 14:29."} A flight that left the list during a gap is marked UNKNOWN.
>
> ## How it's built
> The program runs on AWS Lambda and saves each version once, to storage where it is locked for ten years. A Python data model turns the saved versions into one history per flight, and this site is generated from that model. Every rule has tests, and the tests are themselves checked by breaking the code on purpose and confirming that a test fails. The code is on GitHub.
