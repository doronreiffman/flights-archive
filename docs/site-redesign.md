# Site redesign (q18)

Grade: production-lean, same as the v1 site (`docs/timeline.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript.

Status: design, 2026-10-30, worked out with the owner over mockups. Not built. When built, it replaces the "Pages", "Wording" and parts of "How it is built" in `docs/timeline.md`, and that file is rewritten to match.

Mockups the owner approved, with real data from the 2026-10-30 00:02 build: `docs/site-redesign/front-page-mockup.html` and `docs/site-redesign/flight-page-mockup.html` (open in a browser; the heading above each card is mockup chrome, not part of the page).

## Why

The site is the owner's portfolio piece: a recruiter or hiring manager clicks through from a CV or LinkedIn and should understand it in seconds. The owner's test (2026-10-30): if it is useful to a traveler looking up a flight, it is impressive to a hirer. The v1 site fails both: its front page is a table of dates, and its sentences ("First observed CANCELED on the public board", "first seen by us", "stored boards") mean nothing to someone who has never heard of the flight board.

## Goals

- Anyone understands what the site is and what they can do on it within a few seconds, with no prior knowledge of the airport, data.gov.il or this project.
- The front page leads with cancellations: how many, which ones recently, how much warning there was.
- Searching a flight number lands on that flight's page: every day it was scheduled, what happened, how much warning a cancellation got, and what changed along the way.
- Looks clean and modern on a phone and a laptop, light by default with a dark mode.
- Looks right with one week of data and fills in as data grows, with no redesign.

## Non-goals

- Delay figures of any kind ("N minutes late", averages): what the airport's expected time measures (leaving the gate or taking off) is still unknown (q3; `.claude/OPEN_ISSUES.md`, Data).
- Cancellation odds or forecasts: not enough history (`OPEN_ISSUES`, Governance, forecast gate).
- Airline or route comparisons: a week of data cannot support them fairly. A later section, once the data can.
- Live updates. The site is as fresh as the last build and publish.
- New file types (fonts, images, JSON): the upload allowlist and the phrase check cover `.html`, `.css`, `.js` only. The chart is inline SVG; the search data is a `.js` file or inline in a page.

## Anti-goals (a failure even if it works)

- A sentence a stranger cannot follow: data-collection words ("board", "snapshot", "stored", "observed", "first seen by us", "receipt") on any page other than "How this works".
- The site talking about itself in the first person: no "we", "our", "us" anywhere, the "How this works" page included (owner, 2026-10-30). Each sentence states a fact about a flight. The limits of the records go on "How this works", in the third person ("Records start on 27 October 2026").
- Overclaiming. Plain words, but only what the airport's list supports: warning times are lower bounds ("at least 23 hours"); a cancellation's time is never given as a single moment; no "took off", "operated by", "delayed by", "minutes late"; "probably" where something is inferred.
- Looking official: no IAA name in the title, no logos; the source line and the unofficial line stay on every page (`docs/terms.md`, clauses 6 and 8).

## Words (owner, 2026-10-30)

These replace the "Wording" section of `docs/timeline.md`. They relax the CLAUDE.md claims-discipline line ("first observed CANCELED on the public board") into plain words while keeping its substance: lower bounds, no single cancellation time, no delay or operator claims. CLAUDE.md's line and `docs/terms.md` (clause 4 paragraph, which names the wording rules as how the site avoids misleading presentation) are updated when this ships.

- "Cancelled", not "CANCELED" or "listed as cancelled". "How this works" says once what it means: the airport's own list showed the flight as cancelled. The front page headline keeps "listed as cancelled" (the approved mockup).
- "Scheduled to leave HH:MM" for departures, "scheduled to land HH:MM" for arrivals. Never "due".
- Times are Israel time; each page says so once, in the footer.
- Durations in plain units, rounded down: "at least 23 hours", "at least 3 days", "about 2 hours after".

### Labels

Each flight on each day gets one main label, colored, plus an optional second one.

| Model outcome | Label | Color | Line under it on the flight page |
|---|---|---|---|
| `departed` | DEPARTED | green | none |
| `landed` | LANDED | green | none |
| `canceled` | CANCELLED | red | the warning line (below) |
| `open`, scheduled time after the build | UPCOMING | grey | none |
| `open`, scheduled time before the build | IN PROGRESS | grey | "No final update yet." (my call) |
| `gap` | UNKNOWN | grey outline | "No records for the time it left the airport's list." |
| `vanished` | UNKNOWN | grey outline | "Removed from the airport's list N hours before it was scheduled, with no final status. Not necessarily cancelled; it may have moved to another time." |
| `dropped` | UNKNOWN | grey outline | "Removed from the airport's list with no final status." |

Second label: DELAYED in amber when the airport itself showed the status DELAYED at any point (20 flight numbers since 27 October). Shown beside the main label, for example "LANDED · DELAYED". It is the airport's word; it carries no minutes.

When the airport's last expected time differs from the scheduled time, the flight's row shows both: "scheduled to leave 16:45 · last expected 17:09". No difference is computed or shown.

A flight shown as cancelled and later shown with another status (`uncanceled` true) gets its final label and the line "Shown as cancelled for a while, then changed back." If its final label is CANCELLED again, the line is "Cancelled, changed back, then cancelled again." (My call; the first wording contained the banned phrase "cancelled at".)

### Warning (cancelled flights only)

How long before the scheduled time the airport's list already showed the flight as cancelled. From the model's bracket: `cancel_lead_min` (from the first time it was seen cancelled), `cancel_lead_max_min` (from the last time it was seen not cancelled), `cancel_lead_censored`, `canceled_at_first_sight`. Say only what the bracket supports:

| Case | Text |
|---|---|
| low end at least 60 minutes (any case) | "at least N hours" (N rounded down; "at least N days" from 48 hours) |
| not censored, both ends between 0 and 60 minutes | "less than an hour" |
| not censored, low end between 0 and 60, high end 60 or more | "at least N minutes" (my call; N rounded down, minimum 1) |
| censored or seen cancelled at first sight, low end between 0 and 60 | "at least N minutes" (same) |
| not censored, low end negative, high end 0 or more | "around the scheduled time" |
| not censored, high end negative | "none: cancelled about N hours after it was scheduled to leave" (or "to land"; N from the two ends, rounded down; "about an hour" and "less than an hour" below 2 hours) |
| censored or seen cancelled at first sight, low end negative | "unknown: no records for that time" |

The front page's table shows the warning text alone in a "Warning" column; the flight page shows it as a sentence ("No warning: cancelled 2 hours after it was scheduled to leave.", "At least 23 hours of warning.").

### What changed (the opened day on a flight page)

One line per change, oldest first, time on the left:

- First line: "Earliest record: on time, terminal 1, check-in desks 332-338" (status, terminal, desks; whatever the first record has).
- A change seen within an hour of the previous record: the time of the record that showed it ("17:32 · Expected to leave at 17:38 instead").
- More than an hour since the previous record (`GAP_HOURS`): "Sometime between 27 Oct 20:24 and 29 Oct 14:29 · Check-in desks set to 345-348, zone B".
- The cancellation line: "19:32 · Cancelled (sometime after 19:16)".
- A retime: "Moved to a new scheduled time: 23:30 → 01:10 on 31 Oct".
- Field names in plain words: expected time, status, terminal, check-in desks, check-in zone. Name changes of the airline, airport, city or country are left out (my call; they are spelling fixes on the airport's side).

Statuses in these lines are in plain words, lower case: on time, not final, final, delayed, landing, landed, departed, cancelled, early. No Hebrew status words (my call). The Hebrew city name appears once, in the flight page's header, marked `dir="rtl"`.

### Codeshares

The model groups flight numbers that share a time, terminal and check-in desks (`codeshare_group_id`), day by day: partners change between days (64 of the 725 numbers seen on more than one day had different partners on different days, 2026-10-30). So the line belongs to each day, inside that day's row on the flight page: "Probably the same flight as DL 7426 and AM 7895 (same time, terminal and check-in desks)." Each number links to its own page. (My call: "probably" because the grouping is inferred and arrivals with no desks can occasionally merge two flights; `OPEN_ISSUES`, Model.)

Counts of flights count each group once. Where a group's members have different outcomes, its members are counted and listed separately (my call; the safe side of the "time-only" merge risk).

## Pages

### Front page (`index.html`)

Top to bottom, as in the front-page mockup:

1. Title "Cancelled flights at Tel Aviv airport". One line under it: "A record of flights in and out of Ben Gurion Airport since 27 October 2026, and which ones were cancelled."
2. Headline: "So far: X of Y flights were listed as cancelled. That's about 1 in N." Y counts flights (groups once) whose ending is known (departed, landed, cancelled); X the cancelled ones among them. N rounded to the nearest 5 from 20 up, to the nearest whole number below (my call). Left out while X is 0.
3. Search box: "Flight number or city, e.g. LY 001 or Paris". Results are links to flight pages, up to 10, best first. It needs JavaScript; without it the box is hidden and the day pages (from the chart) reach every flight.
4. "Recent cancellations": the 10 most recent cancelled flights by scheduled time, upcoming ones included; columns date, flight, route with "scheduled to leave/land", warning. Each links to its flight page, opened at that day. A link "All cancellations" below.
5. "Flights each day": an inline SVG bar chart, one bar per day for the last 14 days with flights plus the days still ahead; each bar's count of flights and, on it, "N cancelled". Days still ahead are pale; a day the records only partly cover (the existing `partial` rule) is pale and labelled "incomplete". Each bar links to its day page.
6. "Last updated 30 Oct 2026, 00:02" (the last record, Israel time).
7. Footer (every page).

### Flight page (`flight/<airline><number>-<D|A>.html`, one per flight number and direction)

As in the flight-page mockup:

- Back link to the front page.
- Title: "TO 3459, Tel Aviv to Paris". Under it the airline name exactly as published ("TRANSAVIA FRANCE"), the airport by city and code ("lands at Paris (ORY)") and the city in Hebrew. (My call: the airport's names come with legal suffixes, dots and misspellings, such as "K.L.M.", "SWISS INT`L  AIRLINES", "KENIA AIRWAYS"; mechanical title case mangles them and fixing them by hand would change the source's text, so airline names are shown as published and airport names are replaced by city and code. Cities are title-cased: they are plain words.)
- Summary: "Since 27 October: departed once, cancelled once, one upcoming." Counts per main label, in label order, with plain words for each.
- One row per scheduled day, newest first: date, "scheduled to leave HH:MM" (with "last expected HH:MM" when different), main label, second label. A cancelled day shows its warning line and opens by default; other days open on click ("Show details") into "What changed". A `<details>` element is fine; it works without JavaScript.
- Each day row has a stable anchor in full form, from the first scheduled time and the airport: `#2026-10-28-1630-KUT`. Always the full form, so an anchor never changes when a second flight with the same number appears later (LY 5115 left at 16:30 on 28 October twice, to Batumi and to Kutaisi). The address and anchors never change between builds; the build stops if two rows would share one.

Flight pages: 949 today; each grows by a row a day.

### Day page (`day/YYYY-MM-DD.html`)

Secondary; reached from the chart. Title "Thursday 29 October 2026", counts ("418 flights: 7 cancelled"), then departures and arrivals in scheduled order, one row per flight (group): time, numbers, route, labels, warning for cancelled ones. Each row links to the flight page at that day. No per-change detail here (it lives on flight pages), so day pages stay small.

### All cancellations (`cancellations.html`)

Every cancelled flight, newest first, same columns as the front page's table.

### How this works (`how-it-works.html`, replaces `methodology.html`)

Plain words, third person, short sections: where the data comes from (the airport's public flight list, published on data.gov.il, checked every 2 minutes); what each label means; what "warning" means and why it says "at least"; why there are no delay figures yet; "probably the same flight"; gaps in the records (records start 27 October 2026 in the evening; none from 27 October 20:24 to 29 October 14:29; any later gap from the model); how it is built, for the technical reader (in a few lines: an AWS Lambda every 2 minutes, write-once storage, a Python model, this site, tests and mutation testing), with a link to the GitHub repository; the source line and the unofficial line.

### Footer (every page)

Owner, 2026-10-30: a short source line, "Flight data: Israel Airports Authority, published on data.gov.il." (a new constant beside `UNOFFICIAL`), then the existing `UNOFFICIAL` line verbatim, then "How this works", then "Built by [owner's wording]" (the owner writes this line; a placeholder until then). The full `ATTRIBUTION` (dataset name and resource ID; `src/model/report.py`, unchanged for the report) moves to "How this works". `timeline.check` then requires the short line and `UNOFFICIAL` on every page and `ATTRIBUTION` on `how-it-works.html`; `docs/terms.md` (clauses 6 and 8) and `docs/publishing.md` are updated to match when this ships.

## Look

- One column, max width about 42rem, generous spacing; the system font stack; numbers tabular.
- Colors as CSS custom properties, light by default, a dark set under `prefers-color-scheme: dark`; both pass WCAG AA contrast for text (my call).
- Labels are small rounded pills with text, never color alone.
- Works at 375 px wide without sideways scrolling.
- No framework, no web fonts, no images; the chart is SVG written by Python.

## How it is built

- Same pipeline: `python -m timeline.build --model data/model --out site`, reading the model's Parquet files with DuckDB, the marker-file swap, `timeline.check` before upload, `scripts/publish.sh`. `pages.py` stays pure functions from rows to HTML.
- The search data: one entry per flight number with its search keys (`pages.search_keys`, unchanged) and its page address, as a `.js` file or inline in the front page (builder's call). About 950 entries today.
- Same model, same bytes (determinism across processes, as now).
- The build time is the last record's time, never the clock.

## Tests and checks

The v1 tests' guarantees carry over, rewritten for the new sentences: every model flight appears on exactly one flight page and one day page; anchors and addresses stable and unique, the build stops on a collision; escaping (a city named `<script>` stays text); Hebrew marked `dir="rtl"`; Israel time across the October clock change under an Israeli time zone; a NULL final scheduled time stops the build; `--out` without the marker refused; determinism across `PYTHONHASHSEED`.

New, each with a `scripts/mutation_check.py` entry:

- one exact-text test per warning case and per label row above, the DELAYED second label, "last expected", "changed back";
- the headline numbers and the 1-in-N rounding; left out at 0 cancellations;
- the chart's counts match the day pages; pale and "incomplete" days;
- codeshare grouping, including the split when members' outcomes differ;
- the recent-cancellations order and the cap of 10;
- `timeline.check`: add "we", "our", "us" as whole words, case-insensitive; "minutes late", "hours late"; keep the existing banned phrases (the new texts contain none of them); and the data-collection words from the anti-goals, on every page except `how-it-works.html` (the only page that carries the full source line, which names the "flight board").
- `search.js`: the existing Node test, extended to the cross-page results.

## Left to the builder

Markup and CSS details; the search data's format; exact spacing and colors within the look above; how "Show details" opens; the order of sections on "How this works"; anything marked "my call" above that turns out awkward in code, as long as the words and rules hold.

## Outside this design, for the owner

- Freshness: the site shows "Last updated" and is rebuilt and published by hand (`scripts/publish.sh`). A portfolio page that says "Last updated 30 Oct" in December looks abandoned; a scheduled rebuild is q2/q5 territory.
- Link previews: LinkedIn shows a card from the page's title, description and preview image (Open Graph tags). Without an image the post has no picture; an image means a `.png`, a new file type for the allowlist and the check. Fits q17 (launch).
- Search engines: every page carries `noindex`. Whether the launched site should be findable is a launch decision (q17).
- The five outsider sessions (q13): their tasks quote v1 wording, and their stop rule ("fewer than two of five name a real use") was written for a product. Worth revisiting after this ships.

## Portfolio additions (2026-10-30)

Additions for the hiring reader, after the review below. The pages above stay the base. These amend the front page. Anything under "When the records can support it" is written down here so it is not forgotten, and it stays off the public pages until its gate is met: no "coming soon", no empty chart.

A live board, flight alerts, and a second copy of a site that already shows today's list are not on this list. They would make a worse version of something a traveler already has.

### On the first screen

The data for these is already in the 2026-10-30 model.

1. **One flight, already open.** Under the title, TO 3459 on Thursday 29 October, in the grey box's words plus the line that box skips. Expected time 17:38, then 18:45, then "Between 19:16 and 19:32 it was listed as cancelled." Before that, the gap line: check-in desks 345-348, zone B, sometime between 27 Oct 20:24 and 29 Oct 14:29. The cancellation count moves under this, not above it. The title matches the story ("What the Tel Aviv airport list said"), and the lede still names Ben Gurion. The count keeps "listed as cancelled" and says it is of flights whose listing has already ended.

2. **A wide warning is a span.** Where the two ends of a cancellation are far apart, the warning column and the flight page say the span: LY 5409 is "somewhere between 1 hour and 43 hours; records skip that stretch", not "at least 1 hour". LY 5410 is the same shape, 7 hours to 49 hours. A flight already cancelled at its first record says so in the same sentence as the lower bound (IZ 992: "already cancelled at the first record, at least 23 hours before it was scheduled to land"). "At least N hours" on its own is only for a tight bracket, one list-refresh wide. This replaces the warning table's first row ("low end at least 60 minutes, any case") for censored and first-sight flights. Same exact-text tests as the other warning cases.

3. **Who built it, on that screen.** The built-by line is the owner's words, and it is on the front page, not only in the footer once the owner has written it. A link to the repository sits beside it. The link-preview title is the page title; the description is one sentence ("Every change on the public departures and arrivals list at Ben Gurion Airport, kept since 27 October 2026. Unofficial."). An image still waits on a new file type (q17). "I" is allowed on How this works and in the built-by line only. "We", "our" and "us" stay banned everywhere, including there. That narrows the anti-goal above, which currently asks for the third person on How this works too.

4. **Four lines beside the flight, in words the front page is allowed to use.** "Receipt", "snapshot", "stored" and "board" stay on How this works. The front page can say: the public list is checked every 2 minutes; each version is kept for 10 years and never replaced; a note of every download is kept since 29 October 2026; tests plant one bug at a time to prove a test catches it. How this works names the receipt, the Lambda and the repository in the same plain words, as "I".

5. **The date on the page moves by itself, once the site is public.** "Last updated" comes from the last record, as already specified, and a schedule rebuilds and publishes so the line cannot sit on 30 October in December. The model half is the nightly run in `docs/data-model.md` (under $0.05 a month, not deployed, q5 then q2). Publishing the site on that schedule is one upload and one CloudFront invalidation a day, inside the free invalidation quota. It is an AWS write and needs the owner's go. It does not block building the pages.

The phone table and the unknown share on a day's bar are fixes to the look, not new sections. Wednesday 28 October is 190 groups with no known ending out of 370, and the bar has to say so. At 375 px the warning sits under the route.

### When the records can support it

The public site does not mention these until the gate. The per-flight warning sentence is the only cancellation number until then.

- **How far ahead a cancellation shows up.** A plain distribution of warning times, uncensored flights only, with the censored count beside it so a hole cannot masquerade as a short warning. Today there is one uncensored cancellation, TO 3459, and the list showed it cancelled about two hours after it was scheduled to leave. The other 19 are censored. q4 (a rerun on or after 5 November 2026, a week of continuous collection) is the first time to measure this, not the day to publish a chart: a week may still be a handful of flights, and none of them has yet been caught changing to cancelled in advance. Publish the chart when the uncensored set is large enough that a few holes do not decide the shape. The owner sets that count. The same flight, once one exists, is the README screenshot q17 asks for.

- **A forecast with a public score.** The chance a flight will be listed as cancelled, scored in public against the historical rate, with a Brier score and a calibration check, on flights the score did not learn from. The gate is not adopted yet (`OPEN_ISSUES`, Governance): round 2 of the outside review said about 400 cancellations over at least 60 untouched days. Today there are 20 cancellations and one uncensored lead, and that lead is after the scheduled time. Publish the score even if it shows no skill. Until the gate, the site has no forecast and does not say one is planned.

- **Delay figures, after the expected time has a meaning.** This is not waiting on more rows. The list already has an expected time; what is unknown is whether it means leaving the gate or taking off (q3). Until a primary source settles that, the flight page shows the expected time and one sentence: it is the airport's figure, and the site does not turn it into minutes late, because the list does not say which moment it is. After that, a summary is allowed in those words ("the list's expected time, which is the gate time, runs a typical N minutes after the scheduled time"), still with no "delayed by" and no claim about takeoff unless the source was takeoff.

- **Airline and route comparisons.** Already a non-goal above. A later section, and only once the window is long enough that one thin week, the hole, and codeshare merges cannot pick the winner. No ranking before that.

- **An agent that answers questions about this archive.** Only after the forecast exists, and only with a published eval of the answers against the same records. An agent before that eval is a claim the site cannot check. The site does not mention one until the eval is there to show.

## Review findings

Reviewed 2026-10-30, read-only, against the model whose last record is 2026-10-29 22:02:45 UTC (30 Oct 00:02:45 Israel, the build the mockups name). Checked in that model: 3,125 flight rows, 2,044 codeshare groups, 949 flight-number pages. Outcomes: open 1,294 rows / 853 groups, landed 766 / 494, departed 663 / 437, gap 382 / 240, canceled 20 / 20. No `vanished`, `dropped`, true `uncanceled`, or retime. The two mockups were opened in Chrome at 375px and 800px wide. Dark mode is not in either file, so it was not rendered.

### Critical

No finding at this bar. The quoted counts that can be checked (20 of 951, the chart's 348 / 370 / 418 / 289 / 161 / 403, 949 pages, 20 DELAYED flight numbers, 64 of 725) match the model under the definitions in the findings below. The test sketches are incomplete, and one of them will lock in a misleading sentence; they do not contradict themselves on a type or an import.

### Significant

**Wide brackets are written as a measured warning.** Warning table, first row ("low end at least 60 minutes (any case)"); the line above it, "Say only what the bracket supports." On this model the first row fires for eight of the twenty cancellations, and none of the eight is a tight bracket. LY 5409 (Thu 29 Oct, on the approved front page) runs from 76 minutes to 43 hours and the row produces "at least 1 hour". LY 5410, the second row of that table, runs from 7 hours to 49 hours and produces "at least 7 hours". Both brackets are about 42 hours wide because they cross the collection hole. The other six were already cancelled at the first record of that flight, so the high end is null: IZ 992's "at least 23 hours" is a real lower bound, and it still reads as a warning that was watched happening. Five of the ten most recent cancellations, the table the front page is specified to show, are "unknown: no records for that time". The only uncensored cancellation is TO 3459, and the list showed it cancelled after the scheduled time. A page built to this rule looks, in the same week the goals say it must look right, like a warning statistic with a hole in it. Fix: a censored bracket with both ends quotes both ends ("somewhere between 1 hour and 43 hours; records skip that stretch"). A flight already cancelled at its first record says that in the same sentence as the lower bound ("already cancelled at the first record, at least 23 hours before it was scheduled to land"). The bare "at least N hours" stays for an uncensored bracket, where the two ends are one list-refresh apart.

**The warning rows leave brackets with no sentence, and two sentences that overclaim.** Warning table; flight-page examples in the same section ("No warning: cancelled 2 hours after…", "At least 23 hours of warning."). Read as a set of cases rather than an ordered list, the first row also matches every later row whose low end is at least an hour, so an exact-text test per row has no single expected string until the order is fixed. Nothing names the boundary at 0 minutes or at 60. "At least N minutes, minimum 1" turns a lower bound of 0.4 minutes into "at least 1 minute", which the bracket does not support. "About N hours after" says N comes "from the two ends" and does not say what happens when one end is under an hour and the other is over two; the only live example (TO 3459, 127 to 143 minutes after) happens to fall in one bucket, so a test on real data will not catch the hole. The flight-page examples then drop the table's "about" and rename "none" to "No warning". Fix: write the rows as an ordered first-match list, with 0 and 60 included on the low side of "between 0 and 60"; delete the minimum of 1 minute; define N for the after-case as the smaller of the two ends, rounded down, and use "less than an hour" only when both ends are under an hour; make the column text and the flight-page sentence the same words.

**The cancellation line puts a single clock time on the change.** Anti-goals ("a cancellation's time is never given as a single moment"); "What changed", the cancellation line "19:32 · Cancelled (sometime after 19:16)". Those times are TO 3459's real ones: the list showed CANCELED at 19:32, and the previous appearance was 19:16. The parenthetical is the bracket. The left-hand time is the moment a stranger will repeat. The grey box under the same mockup's table already has the sentence that keeps the rule: "Between 19:16 and 19:32 it was listed as cancelled." Fix: use that between-sentence for the cancellation line, and do not give it a single time in the clock column. Other changes keep their clock time.

**"IN PROGRESS" overclaims, and the comparison that chooses it is unspecified.** Labels table, the two `open` rows. Nine flights are still on the list with a scheduled time before the last record. All nine are on the evening of 29 Oct, between 23:30 and 23:55, and the list's own last word is ON TIME, EARLY (LY 5194), or DELAYED (KL 461 and the four numbers in its group, scheduled 23:55). "In progress" is a guess about the aircraft. "No final update yet", the line under the label, is the part that is true; it should be the label. The same nine are also a timezone trap. Their UTC scheduled time is before 22:02 UTC, so they are "before the build". Their Israel wall-clock time, 23:55, is after 22:02 if the two naive columns are compared directly, so every one of them becomes UPCOMING. The design says "scheduled time after the build" and never says both instants are UTC. Fix: compare `sched_utc_final` with the last snapshot's `fetched_at`. Treat an equal time as "no final update yet". Name the label NO FINAL UPDATE, and keep DELAYED beside it when the list used that word.

**The headline, the chart and the day line count different populations, and the hole is invisible.** Front page items 2 and 5; day page ("418 flights: 7 cancelled"); "the existing `partial` rule". 20 and 951 are right if 951 is groups whose outcome is departed, landed or canceled: 437 + 494 + 20. That 951 includes 26 Oct (55 such groups, zero cancellations). The lede says "since 27 October", and the mockup's chart starts on Tue 27. Drop 26 Oct from the denominator and the rate is 20 of 896, about 1 in 45, not 1 in 50. The bars sum to 1,989 groups. A reader who adds them up cannot reach 951, because the bars include open and gap flights and the headline leaves them out. Wed 28 Oct is 190 gap groups out of 370. The bar says 370 and "8 cancelled", so the other 362 read as flights that went. The partial rule does not save it: the only partial day in this model is 26 Oct. The 27th, the 28th and the future days are all "full". The parenthetical "a day the records only partly cover (the existing partial rule)" describes the rule as something it does not check. The day page, as specified, has no partial line and no gap line, so the page a bar links to repeats the same two numbers. Fix: the headline says "of flights whose listing has already ended". The bar's count is the same groups, and a day with gap flights prints that count ("190 with no known ending"). 26 Oct is on the chart, pale, and labelled incomplete, on the day page too. The partial rule stays what `build.py` computes; the hole stays the model's gap outcome, named on the day.

**The approved mockups and the written rules disagree on the flight they both use.** Front-page and flight-page sections ("as in the mockup"); footer; labels, "last expected"; "What changed". For TO 3459 the model and several rules are the same flight, and the mockup omits what the rules require:

- 27 Oct is scheduled 16:45, last expected 17:09. That pair is the design's own example of showing both times. The mockup's row shows 16:45 only.
- 29 Oct's last expected time is 18:45, against 17:10. The row shows 17:10 only.
- The first record is 27 Oct 20:04, on time, terminal 1, no desks. The next line is the gap the design quotes verbatim: desks 345-348, zone B, between 27 Oct 20:24 and 29 Oct 14:29. The opened day in the mockup starts at 17:32.
- The header says "Transavia France" and "lands at Paris Orly". The rule is the published name `TRANSAVIA FRANCE` and "Paris (ORY)", plus the Hebrew city once. Published names that title case will mangle are already in the model: `CHINA EASTERN AIRLINES Co. Ltd`, `K.L.M.`, `SWISS INT`L  AIRLINES`, `ARKIA  ISRAELI  AIRLINES` (double spaces). IZ 992, the first row of the table, carries the Arkia string.
- The mockup footer is "Flight data from the Israel Airports Authority, via data.gov.il. Not an official site." The footer section requires the short source line plus `UNOFFICIAL` verbatim. The mockup footer would fail the check the design tells `timeline.check` to run.
- "Times are Israel time" is on the flight mockup only. The words section puts it on every page; the footer bullets do not mention it.
- "Last updated" is front-page item 6 and is not on the mockup.

Fix: pick the written rules where they are stricter, and change the mockups so a builder can copy them. Keep published airline strings, including the double spaces and `Co. Ltd`. One short note beside the name ("as the airport published it") stops a reader from thinking the capitals are a bug.

**The chart is specified both as the way to reach every flight and as a 14-day window.** Front page item 3 and item 5; goal "fills in as data grows, with no redesign." With seven days of flights, a 14-day window can still link every day, including 26 Oct. The mockup already drops 26 Oct, and those 81 flight rows then have no page a person can open without JavaScript except by guessing a URL. Past day 15 the same thing happens to every older departed flight. "All cancellations" saves the cancelled ones only. Fix: the front page links every day the model has, or it grows an "earlier days" list. The 14-day picture can stay as the picture. Delete the sentence that says the chart reaches every flight, unless that sentence becomes true.

**Search has no order, and the cap of 10 hides the example the box gives.** Front page item 3 ("best first", "up to 10"). "Best" is not defined. Sixty flight numbers have city Paris. Two hundred and fourteen are LY. The box's own examples, "LY 001" and "Paris", both overflow the cap, and there is no "show more". `pages.search_keys` takes one city. Four flight numbers have two cities, so one call of the unchanged function drops a city from the index. Fix: define the order (exact number, then prefix of the number, then city), show the count when more than 10 match, and build the keys as the union across that number's rows. The no-JavaScript path is the day list, which depends on the previous finding.

**One page title cannot name two cities, and "opened at that day" is ambiguous for thirteen flights.** Flight page title; "Each links to its flight page, opened at that day"; the LY 5115 anchor example. Four numbers use two airports: LY 5115 and LY 5116 (Batumi and Kutaisi, the anchor example), IZ 419, 6H 890. The title pattern "TO 3459, Tel Aviv to Paris" has nowhere to put the second city. Separately, thirteen number-and-direction pairs occur twice on one day. IZ 992, the first row of the recent-cancellations table, is one of them: 10:25 still listed NOT FINAL, and 13:50 cancelled. The anchors differ. A link "to that day" does not. Fix: the title carries a city only when the number has one; each row carries its own city. Every link to a row includes that row's anchor.

**A retime across midnight has no day, and the test plan and the page section disagree.** Flight page ("one row per scheduled day"); tests ("exactly one flight page and one day page"); anchor "from the first scheduled time". This model has zero retimes, which is why nothing on the mockups forces the choice. v1 already broke on this case and put the flight on the day of the final scheduled time, with the anchor taken from the first. The new test sentence requires one day page. "One row per scheduled day" reads as two rows when the clock crosses midnight. Fix: one flights-table row is one row, on the day of `sched_local_final`, anchor from `sched_local_first`, and the row says "Moved to a new scheduled time" with both clock times. Say that the carried midnight tests are kept, rewritten to that sentence. The first real retime will otherwise stop the build or land on two days.

**The phrase check will reject the new pages if "we" is added the way banned phrases work today.** Tests, the `timeline.check` bullet. `check.py` rejects a phrase with `phrase in text` after lowercasing. "we" is inside "were" in the headline. "our" is inside "hours" in every warning. "us" is inside "status", and inside published strings a whole-word match correctly ignores: BUS, AUSTRIAN AIRLINES, BRUSSELS, CYPRUS AIRWAYS, DUSSELDORF, VILNIUS, TUS AIRWAYS, ROYAL AUSTALIAN AIR FORCE. No airline, city or airport in this model is the word we, our or us. "board", "snapshot", "stored", "observed" and "receipt" do not occur in those strings either. The whole-word rule in the design is the right rule, and it is safe on this data. The obvious implementation, appending the words to `BANNED`, is not. Fix: a word-boundary match for the pronouns, a test that the headline, "at least 23 hours", "status", "BUS" and "AUSTRIAN AIRLINES" all pass, and a mutation that switches the check back to a substring so that test fails. Keep "board" off every page except `how-it-works.html`, where `ATTRIBUTION` contains "flight board".

**The test list keeps v1 guarantees this design reverses, and misses the branches that will ship wrong.** "Tests and checks"; footer paragraph on `timeline.check`. "The v1 tests' guarantees carry over" includes, in the current tests, a full `ATTRIBUTION` on every page, counts as flight numbers, and a Hebrew status word (`מבוטל`) marked `lang="he"`. This design moves `ATTRIBUTION` to one page, counts groups, and forbids Hebrew statuses. A builder who takes the preamble literally will put the old site back. The named new tests never mention: the UTC comparison for UPCOMING, a wide censored bracket, the 0-minute and 60-minute boundaries, the false-positive phrase fixtures above, `noindex`, a search key that survives `</script>` and a backtick, which day a midnight retime uses, a number with two cities, IZ 992's two anchors on one day, or 26 Oct labelled incomplete on its own page. `docs/terms.md` still cites the phrases "listed together" and "flight numbers listed" as what the upload check proves. The design already says that paragraph is updated when this ships; the tests have to drop those phrases in the same change. Fix: list the v1 tests that are retired, and add the cases in this paragraph, each with a mutation entry. `noindex` stays in the carryover list so a footer rewrite does not drop it.

**The approved mockup already fails the look rules.** "Look"; front-page table. At 800px the page is readable. At 375px the recent-cancellations table is not: the route and the warning share a crushed column, and "at least 23 hours" does not remain a readable phrase. The flight page wraps instead, and the warning and the change lines break away from their clock times. The card padding is 36px a side and the date and flight columns do not wrap, which is why. "All cancellations" uses the same table. Contrast on the mockup's own colours: the red pill `#d1352b` on `#fdecea` is about 4.3:1, under the 4.5:1 AA bar for 12px text; "1 cancelled" in `#0a66c2` on the pale bar is about 3.3:1. The solid blue bars with white type pass. No dark palette exists to check, so the sentence "both pass WCAG AA" is an intention. "N cancelled" inside the bar is already tight at six bars and will not fit the 14 the chart section requires. Fix: on a narrow screen stack the warning under the route, and don't set a fixed column width. Pick pill and chart colours that clear 4.5:1 in both schemes, and write both schemes down. Put the cancelled count beside the bar, or as a red segment, once there are more than a handful of days.

### Minor

**The gap line starts at the previous appearance, which is not a line.** "What changed", the desks example. For TO 3459 the desks change at 29 Oct 14:29, and `prev_observed_at` is 27 Oct 20:24, the last list the flight appeared on before the hole. The previous change line is 20:04. A builder who measures the gap from the previous rendered line will start it 20 minutes early and will still match a casual reading of "the previous record". Fix: name `prev_observed_at`, and say an appearance that changed nothing is not its own line.

**`uncanceled` null is the common case, and the label table says the line under DEPARTED is "none".** Labels, the paragraph after the table. Eleven of the twenty cancellations have `uncanceled` null (already cancelled at first sight, never seen as anything else). Zero flights have it true. The paragraph adds "Shown as cancelled for a while, then changed back" for any final label, which includes a departed flight the table says has no line under it. Fix: null counts as false, same as v1. When the flag is true, the changed-back line is added under whatever the final label is, including UNKNOWN, and the warning line stays only on a final CANCELLED, worded from the first episode, with the "cancelled again" sentence beside it.

**A codeshare row splits only when the outcomes differ.** Codeshares. No group in this model has two outcomes, and no group disagrees on whether a member was DELAYED (12 groups contain a DELAYED member, and every member agrees). Every cancellation is a group of one, so the headline's 20 does not depend on the split. The hole is later: two members both cancelled, with different brackets, or one of them DELAYED, still share a row and one warning. Fix: split the row when the main label, the DELAYED flag, or the warning sentence differs. "At any point" for DELAYED means that flight row's own observations; a number that was delayed on Monday stays plain on Tuesday. Today those two scopes are the same 20 rows, so a test has to be synthetic.

**"Final" and "not final" will be the words a stranger cannot follow.** "What changed", the status list. The observations are ON TIME 1,659, NOT FINAL 1,238, LANDED 769, DEPARTED 663, FINAL 280, LANDING 220, DELAYED 27, CANCELED 20, EARLY 4. "Final" reads as "the flight is over". Fix: gloss them once in the change log ("not final: the airport had not closed the listing") or on How this works, and keep the words, since they are the list's words.

**"1 in N" can be rounded two ways, and the live number hides that.** Front page item 2. 951 / 20 = 47.55, and the nearer multiple of 5 is 50, so the mockup matches the "from 20 up" reading. "To the nearest whole number below" can mean "when the ratio is under 20" or "always round down". A ratio of 22.5 has no named tie break. Fix: under 20, round to the nearest integer, halves upward; from 20, round to the nearest multiple of 5, halves upward.

**Page addresses have a collision check only if someone reuses the anchor check.** Flight page URL; "the build stops if two rows would share one." No two identities share `flight/<airline><number>-<D|A>.html` today, and every code and number is letters and digits. The anchor `#date-time-airport` omits the flight number, and codeshare partners share the time and the airport, so they share the anchor string across pages. A site-wide uniqueness check will stop the build on ordinary partners. Fix: uniqueness of anchors is per page; uniqueness of addresses is per file, and a concatenated airline and number that collides (`AB` + `12` against `A` + `B12`) stops the build too.

**The new search file is a script, and the escaping test is an HTML test.** Tests, the `<script>` city; "How it is built", search data "a `.js` file or inline". Current search keys are plain letters. `SWISS INT`L  AIRLINES` has a backtick, and it is a published name, not a search key. An inline script that includes airline names, or a later city with an apostrophe, breaks out of a JavaScript string. `html.escape` does not stop that. Fix: build the search data with a JSON string embedded in a script, and test a name that contains `</script>`, a quote and a backtick.

**Hebrew loses the language tag v1 marks.** Flight page header; tests, "Hebrew marked `dir="rtl"`". The current test also requires `lang="he"`, on a status word this design drops. A city span with only `dir="rtl"` is announced in the page's English voice. Fix: `<span lang="he" dir="rtl">` on the city, and retire the assertion that a Hebrew status appears.

**The current day is neither "still ahead" nor "incomplete".** Chart. At 00:02 on 30 Oct the mockup pales Friday with Saturday and Sunday ("pale: still to come"). The partial rule calls Friday full. One flight that day has already landed, and one is cancelled. Fix: a day that has started is drawn as today, with its cancellations, and "still ahead" starts tomorrow.

**The ship list updates the rules and forgets the page a hirer reads first.** "Words", the paragraph that updates CLAUDE.md and `docs/terms.md`. README.md still says "when we first saw it" and "first observed CANCELED on the public board", and it is the public landing page of the repo (q17). Fix: add README.md to the same update, or the two public surfaces will contradict on the day both go out.

**A link to a closed day does not open it.** Flight page, `<details>`. Cancelled days carry `open`, so the recent-cancellations links expand them. A day-page link to a departed day scrolls to a shut row. Whether the browser opens a closed `details` for a fragment is doubtful and differs by browser. Fix: the anchor sits on the row, the summary states the label, and the design does not promise the details are expanded except where `open` is set.

### Nit

**The chart's accessible name says the cancellations are red.** Front-page mockup, the SVG `aria-label`. The bars are blue. The cancelled counts are white type, or blue type on the pale bars. Fix: the name describes the counts, and the colour is not the only carrier.

**The mockup shows five recent cancellations and the text says ten.** Those five are the five most recent by scheduled time, so the crop is faithful and it hides how many of the next rows are "unknown". Fix: either show ten in the mockup or say the picture is cropped.

**The grey box sits inside the front-page card.** The subtitle calls it what a click would show. The page list does not include it. It is the only place on the approved front page that shows a list changing. Fix: mark it as mockup chrome, or add it to the page list. The direction section argues for adding it.

**The footer bullets omit the times sentence the words section requires.** Easy to drop because the front mockup also omits it. Fix: add the sentence to the footer list.

**"64 of the 725" is right only for one comparison.** Codeshares. 725 is the count of airline, number and direction seen on more than one scheduled day. 64 is how many of those have two different non-empty partner sets. Counting a day with no partners as its own set raises it to 79. Fix: half a sentence on which comparison, so a later recount does not "correct" a right number.

**The after-case never switches to days, and the before-case does at 48 hours.** The list only keeps a flight for about a day after it was scheduled, so "about 3 days after" may be unreachable. Fix: one clause, or a comment that the board window makes it moot.

**The short source line has no name.** Footer, "a new constant beside `UNOFFICIAL`". Fix: name it next to `UNOFFICIAL`, since `timeline.check` has to import it.

**No cost line.** The redesign adds no AWS service. Hosting stays the estimate in `docs/publishing.md` (under about $0.05 a month). Fix: one sentence in "How it is built", because every proposal in this repo carries a figure.

### Direction findings

**D1. A public site is the right proof, and it is the wrong first screen.** The link from a CV opens whatever this design puts at the top. An HR reader decides from that screen and from the link preview. A hiring engineer opens the repository and looks for whether the hard parts are real (the write-once archive, the receipt, the tests that are themselves tested). A data-team lead looks for whether the numbers are ones a careful person would publish. The design spends the first screen on a traveler's task and puts the engineering in a footer link on How this works. The README already has the engineering, in the first person the site forbids, and the site will contradict it. Evidence: the mockup at 800px, which is clean and says nothing about how it was built; README.md "Engineering choices". Recommendation: change. Keep the site. Make the first screen show the work, and make the README use the same sentences the site is allowed to use. A README with screenshots and no site is a weaker proof, because the thing a hirer can click is the proof. A site that looks like a product brochure, with the person missing, is a weaker portfolio.

**D2. Useful to a traveler is a bad test for this data, and it will backfire on a hirer who tries it.** The other side of the premise: a traveler with a flight tomorrow already has a live board. The one named in CLAUDE.md, tlvflights.com, is in Hebrew, updates through the day, prints delay minutes, and leads with the board itself (fetched 2026-10-30; it also prints the source's "Kenia Airways", so the ugly names are the source's). This site is static, English, rebuilt by hand, and withholds the delay number. A hirer who types a flight number and gets UNKNOWN, IN PROGRESS or no delay will think the project does not work. What actually impresses each reader: HR, one picture they can describe in a sentence and a name attached to it; an engineer, the archive that cannot be overwritten and the test that plants bugs on purpose; a data lead, a cancellation time that is a bracket, and a delay number that is absent on purpose. Recommendation: change the premise. Build the page so a traveler can follow one flight's history. Judge success by whether a hirer can say what was built and what was refused. Do not judge it by whether someone uses it on the way to the airport.

**D3. "Cancelled flights" is the weakest honest headline available this week.** About 2% of ended flights are cancelled here (20 of 951), which matches the older sample in CLAUDE.md, and the warning column on the approved data is five "unknown"s out of the ten most recent, two wide brackets written as "at least 1 hour" and "at least 7 hours", two real lower bounds from a first sighting, and one cancellation that appeared after the scheduled time. A stranger does not know why a cancellation rate at a foreign airport is this person's work. Honest hooks that can be shipped on this model: "What the Tel Aviv airport list said, and when it changed", with TO 3459's evening (expected 17:38, then 18:45, then listed as cancelled between 19:16 and 19:32) as the first thing on the page. The rate can sit under that, labelled as flights whose listing has ended. "Ben Gurion" belongs in the title a link preview will show; the lede has it, and the `<title>` a recruiter sees does not. Recommendation: change the hook. Keep the cancellations. Stop leading with them until a week of continuous collection contains a cancellation that was seen going from a normal status to cancelled, which this model does not.

**D4. Withholding delay minutes is right, and hiding the reason makes the page look unfinished.** The flight page already shows the list's expected time moving (17:10 to 17:38 to 18:45 on TO 3459). That is the interesting part, and it does not require knowing whether the time is the gate or the runway. Printing "95 minutes late" would be the overclaim q3 exists to stop. Settling the meaning cheaply, inside the rule that data.gov.il is the only source: a person who flies from the airport can note whether the published expected time matched pushback or takeoff. That is the owner's observation, not a fetch of iaa.gov.il, and it is still one flight. It is not a reason to wait before this redesign. The impressive sentence is the restraint, and How this works is one click further than a hirer goes. Recommendation: change the presentation, keep the numbers off. One sentence under the expected time: the figure is the airport's, and this site does not turn it into a delay because the list does not say whether it means leaving the gate or taking off. A scored forecast, later, in public, is a second impressive thing. It is not a substitute for that sentence now, and it is not something to sketch on this week's twenty cancellations.

**D5. The launch gate waits on a statistic the feed has not produced, and the site cannot be shown until hosting works.** Continuous collection starts 29 Oct. The only uncensored cancellation, TO 3459, was seen changing from on time to cancelled that evening, about two hours after it was scheduled to leave. q17's screenshot is specified as a flight cancelled in advance during continuous collection, and there is still no such flight. Building nine hundred pages before the CloudFront account verification lands spends the review cycles on copy while the portfolio has no URL. Once there is a URL, a hand-built "Last updated 30 Oct" in December is worse than v1 sitting unpublished. A nightly rebuild is the right next piece after the site is live, and it is q2/q5, with the cost of one small scheduled job. It should not block the redesign, and the redesign should not block getting a URL. Recommendation: change the sequence. Hosting first, then a first screen that can be screenshotted honestly today. Drop "first warning figures" from the launch gate. The only change seen so far was after the scheduled time, and an in-advance cancellation is still absent, so the 5 November rerun is not what makes the page honest. Keep the gate "the site is live and the last-updated line is from a build, not from a memory."

**D6. The minimum that impresses is one screen, one flight, and a way to see the code. The 949 pages are cheap and are not the risk.** Generating a page per number is the same loop the build already runs; cutting them saves little. All-cancellations is the front table again. Day pages earn a place only as the way to reach a flight without JavaScript, which means every day stays linked (the chart finding). What is missing, and would raise the impression more than another page: a link-preview title and description (the image can wait, since a `.png` changes the allowlist); a code link on the front page, not only on How this works; the worked example, which the mockup already drew and the page list left out; the person's name. The placeholder "Built by [your name]" shipping by accident is a worse first impression than no site. Recommendation: change the order of attention. Specify the preview text and the code link in this design. Keep the generator's full page set. Design the first screen and the phone table before polishing the 949th page.

**D7. The hedges that survived are the right ones, and the new labels overclaim. "I" should be allowed on one page.** "Probably the same flight", "not necessarily cancelled", "unknown", and "at least" on a tight bracket are plain and still true. "Listed as cancelled" survives only in the headline. The day line "7 cancelled", the pill CANCELLED, and "IN PROGRESS" are stronger than the list. The no-we rule is right: it was a reaction to a fake institution ("we have", "first seen by us"). How this works is the page where a hirer learns who did the work. Third person there ("Records start on 27 October 2026") hides the candidate. The ban, as written, names we, our and us, so "I" is technically free, and the third-person instruction spends that freedom. Recommendation: change. Keep we, our and us banned on every page, including How this works. Allow "I" on How this works and in the built-by line only.

**D8. The first click shows the raw name, the hole, and a label the list did not use.** IZ 992 is the first row of the approved table, and its airline string is `ARKIA  ISRAELI  AIRLINES`. ASY 991, the fifth row, is `ROYAL AUSTALIAN AIR FORCE`, misspelling included. The mockup that was approved title-cases Transavia and never shows those rows' names. Cities can be title-cased: every current city is plain capitals. Wednesday's bar hides a 51% unknown share (190 of 370). IN PROGRESS, on the only nine flights that qualify, contradicts ON TIME, EARLY and DELAYED. Hebrew city names are specified and absent from the mockup; with `lang="he"` they are a small courtesy, and they are not a second interface. English is the right language for the hiring readers named in the goals. Recommendation: change the chart and the open-flight label (findings above). Keep published airline strings, with the one-line note that they are the airport's. Put the Hebrew city in the header as specified, and look at it once on a phone so the right-to-left span does not reorder the English around it.

**D9. The distinctive thing is a list that was overwritten, and the front page does not show one change.** tlvflights.com shows the live board and a delay. The large trackers show live position and history of a different kind. Neither is a public, cited archive of what this airport's list said at 17:32 and at 19:32, with the gap between records left visible. That is the whole of the difference, and it is the grey box in the mockup, which the page list does not include. A cancellation rate is something those other sites already imply. Recommendation: change. Put one real flight's changes on the front page, in the grey box's words ("Between 19:16 and 19:32 it was listed as cancelled"), including the gap line the box currently skips. A visitor should see the difference without a click.

**D10. The five sessions are aimed at a product decision this project is no longer making.** The stop rule, fewer than two of five naming a real use, would shut down a portfolio piece for failing as a consumer product. The tasks quote v1 wording ("when that was announced") that this design exists to retire. Evidence needed is small and cheap: five people, the owner watching, after the first screen exists, asked what the site is, who made it, and what they think that person can do. A traveler-use question can stay as a probe. It cannot stay as a stop. Recommendation: change the script before any session, not after launch. The design already says the rule is worth revisiting, and it schedules that revisit too late.

**D11. The person who built it is missing from the thing a hirer opens.** The built-by line is a placeholder. The code link is on How this works. `noindex` is correct until launch and does not stop a pasted link from previewing. The preview, with no description specified, will use the title "Cancelled flights at Tel Aviv airport" and whatever sentence a scraper takes next, which may be the unofficial disclaimer. There is no picture (the design is right that a picture is a new file type; it is wrong to leave the title and description unspecified, because those are free). q18 was a visual pass on the day pages. This design is a different product, and that is justified only if the new first screen does the hiring job. Recommendation: change. Write the preview title and description in this design, in the same plain words as the page, with the person's name in them. Keep `noindex` until the launch decision.

**Top 5 changes toward the purpose**

1. Put one real flight's changes on the first screen, in the grey box's words, including the gap and the expected-time slips, and stop leading with a cancellation rate. On this week's data the rate's warning column is mostly "unknown" or a lower bound standing in for a 42-hour hole, and the change story is the only thing a visitor cannot already get from a live board.
2. Rewrite the warning rule so LY 5409 cannot become "at least 1 hour". A wide or open-ended bracket has to say so in the same sentence, or the page's main number is a false impression under the terms the design says it keeps.
3. Make the person visible: "I" on How this works, a code link on the front page, and a link-preview title and description that name the work. The built-by placeholder and a title about cancelled flights are what a hiring reader will actually see.
4. Fix the phone table and the unknown days before calling the look done. The approved front page already fails at 375px, and Wednesday's bar reads as 362 flights that flew when 190 groups have no known ending.
5. Get a public URL before adding more surface, and drop the advance-warning figures from the launch gate. Nine hundred flight pages do not help a hirer who cannot open the site, and no cancellation in the archive was caught in advance. TO 3459, which changed after its scheduled time, is already enough to show.
