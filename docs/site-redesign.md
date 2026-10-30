# Site redesign (q18)

Grade: production-lean, same as the v1 site (`docs/timeline.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript.

Status: design v2, 2026-10-30. Worked out with the owner over mockups, then a builder check and a full outside review (summary at the end; the review's full text is in commit f360540). Not built. When built, it replaces the "Pages", "Wording" and parts of "How it is built" in `docs/timeline.md`, and that file is rewritten to match.

Mockups the owner approved for look and wording, with real data from the 2026-10-30 00:02 build: `docs/site-redesign/front-page-mockup.html` and `docs/site-redesign/flight-page-mockup.html` (open in a browser; the heading above each card is mockup chrome). Where a mockup and the rules below differ, the rules win. Known differences: the mockups title-case airline and airport names, leave out "last expected", the earliest-record and gap lines, "Times are Israel time" (front page), "Last updated", the story box's place in the page list, and use a footer that would fail the check.

## Why

The site is the owner's portfolio piece for a job search: a recruiter or hiring manager clicks through from a CV or LinkedIn and should understand it in seconds. The owner's test (2026-10-30): if it is useful to a traveler looking up a flight, it is impressive to a hirer; "it doesn't necessarily have to be useful in day to day life, just impressive, clean, simple". The v1 site fails both: its front page is a table of dates, and its sentences ("First observed CANCELED on the public board", "first seen by us", "stored boards") mean nothing to someone who has never heard of the flight board.

## Goals

- Anyone understands what the site is and what they can do on it within a few seconds, with no prior knowledge of the airport, data.gov.il or this project.
- The front page leads with cancellations (how many, which ones recently, how much warning), then shows one real flight's story: the thing a live flight board cannot show.
- Searching a flight number lands on that flight's page: every day it was scheduled, what happened, how much warning a cancellation got, and what changed along the way.
- A hiring reader can see who built it and reach the code from the front page.
- Clean on a phone (375 px) and a laptop, light by default with a dark mode.
- Looks right with one week of data and fills in as data grows, with no redesign.

## Non-goals

- Delay figures of any kind ("N minutes late", averages): what the airport's expected time measures (leaving the gate or taking off) is still unknown (q3; `.claude/OPEN_ISSUES.md`, Data). Pages say so in one plain sentence.
- Cancellation odds or forecasts: not enough history (`OPEN_ISSUES`, Governance, forecast gate).
- Airline or route comparisons: a week of data cannot support them fairly. A later section, once the data can.
- Live updates. The site is as fresh as the last build and publish.
- New file types (fonts, images, JSON files): the upload allowlist and the phrase check cover `.html`, `.css`, `.js` only. The chart is inline SVG; the search data is JSON inside a script. A link-preview image (`.png`) is a launch item (q17), not this design.

## Anti-goals (a failure even if it works)

- A sentence a stranger cannot follow: data-collection words ("board", "snapshot", "stored", "observed", "receipt", "first seen by us") on any page other than "How this works". "Record" is allowed ("earliest record", "no records for that time").
- The site speaking as an institution: "we", "our" and "us" are banned on every page (owner, 2026-10-30). "I" is allowed only on "How this works" and in the built-by line, so a reader sees who built it (owner, 2026-10-30). Everywhere else each sentence states a fact about a flight.
- Overclaiming. Plain words, but only what the airport's list supports: a warning is a range or a lower bound, never a measured moment; a cancellation never gets a single clock time, only "between HH:MM and HH:MM"; no "took off", "operated by", "delayed by", "minutes late"; "probably" where something is inferred.
- Looking official: no IAA name in the title, no logos; the source line and the unofficial line on every page (`docs/terms.md`, clauses 6 and 8).
- Shipping the built-by placeholder: the upload check refuses a site that still contains it.

## Words (owner, 2026-10-30)

These replace the "Wording" section of `docs/timeline.md`. They put the CLAUDE.md claims-discipline line ("first observed CANCELED on the public board") into plain words while keeping its substance: ranges and lower bounds, no single cancellation time, no delay or operator claims. When this ships, CLAUDE.md's claims line, `docs/terms.md` (the clause 4 paragraph names the wording rules as how the site avoids misleading presentation) and README.md (which still quotes "when we first saw it" and "first observed CANCELED on the public board") are updated in the same change.

- "Cancelled", not "CANCELED". "How this works" says once what it means: the airport's own list showed the flight as cancelled. The front-page headline says "listed as cancelled" (the approved mockup).
- "Scheduled to leave HH:MM" for departures, "scheduled to land HH:MM" for arrivals. Never "due".
- Times are Israel time; the footer of every page says "Times are Israel time."
- Durations in hours, whole numbers: lower ends rounded down, upper ends rounded up (my call: hours only, no switch to days, so ranges never mix units).
- The airport's status words appear in lower case in the change lines: on time, delayed, landing, landed, departed, cancelled, early. "Final" and "not final" are the airport's words with no published definition; they appear in quotes ("status “final”"), and "How this works" says the airport does not define them (my call; the reviewer's gloss was a guess).

### Who is a "flight"

A flight is a codeshare group (`codeshare_group_id`): the flight numbers the model groups for one scheduled day. A group's members are shown and counted together only when they share the same main label, the same DELAYED flag and the same warning text; otherwise each member is its own flight. Every count on the site counts flights this way. No group in the 2026-10-30 model needs splitting (every cancellation is a group of one), so the split is tested on synthetic data.

### Labels

Each flight on each day gets one main label, colored, plus an optional second one.

| Model outcome | Label | Line under it on the flight page |
|---|---|---|
| `departed` | DEPARTED | none |
| `landed` | LANDED | none |
| `canceled` | CANCELLED | the warning (below) |
| `open`, `sched_utc_final` after the last record's `fetched_at` | UPCOMING | none |
| `open`, `sched_utc_final` at or before the last record's `fetched_at` | NO FINAL UPDATE | none (the label says it) |
| `gap` | UNKNOWN | "No records for the time it left the airport's list." |
| `vanished` | UNKNOWN | "Removed from the airport's list N hours before it was scheduled, with no final status. Not necessarily cancelled; it may have moved to another time." |
| `dropped` | UNKNOWN | "Removed from the airport's list with no final status." |

Both sides of the UPCOMING comparison are the model's naive UTC values; comparing the Israel wall-clock `sched_local_final` instead turns the 9 evening flights of 29 October (scheduled 23:30 to 23:55 Israel time, last record 22:02 UTC) into UPCOMING.

Second label: DELAYED, when the airport itself showed the status DELAYED in this flight row's own records (20 flight numbers since 27 October). Shown beside the main label: "LANDED · DELAYED", "NO FINAL UPDATE · DELAYED". It is the airport's word and carries no minutes.

When the airport's last expected time differs from the scheduled time, the flight's row shows both: "scheduled to leave 16:45 · last expected 17:09". No difference is computed. Each flight page that shows a "last expected" carries one sentence, once: "Expected times are the airport's own. This site doesn't turn them into minutes late, because the airport doesn't say whether they mean leaving the gate or taking off."

`uncanceled` NULL counts as false (it is NULL for the 11 flights already cancelled at their earliest record and never seen otherwise). When true, a line goes under whatever the final label is: "Shown as cancelled for a while, then changed back." If the final label is CANCELLED again: "Cancelled, changed back, then cancelled again." The warning shows only under a final CANCELLED and comes from the model's cancellation fields as they are.

### Warning (cancelled flights only)

How long before its scheduled time the airport's list already showed the flight as cancelled. Inputs: `lo` = `cancel_lead_min` (minutes from the first record showing it cancelled to the scheduled time), `hi` = `cancel_lead_max_min` (from the last record before that one; NULL when the flight was already cancelled at its earliest record), `cancel_lead_censored` (more than an hour between those two records). `h(x)` is whole hours; "leave" or "land" by direction. The first matching rule wins:

| # | Case | Warning text |
|---|---|---|
| 1 | `hi` is NULL, `lo` ≥ 60 | "at least h(lo, down) hours" |
| 2 | `hi` is NULL, `lo` < 60 | "unknown" |
| 3 | `hi` < 0, not censored | "none: cancelled less than an hour after it was scheduled to leave" when −lo < 60; "none: cancelled about an hour after …" when −hi < 60 ≤ −lo; otherwise "none: cancelled about h(−hi, down) hours after …" (−hi is the nearer end; a non-censored range is at most an hour wide) |
| 4 | `hi` < 0, censored | "none: cancelled after it was scheduled to leave" |
| 5 | censored, `lo` ≥ 60 | "between h(lo, down) and h(hi, up) hours" |
| 6 | censored, 0 ≤ `lo` < 60 | "up to h(hi, up) hours" |
| 7 | censored, `lo` < 0 | "unknown: no records for that time" |
| 8 | not censored, `lo` ≥ 60 | "at least h(lo, down) hours" |
| 9 | not censored, 0 ≤ `lo`, `hi` < 60 | "less than an hour" |
| 10 | not censored, 0 ≤ `lo` < 60 ≤ `hi` | "about an hour" |
| 11 | not censored, `lo` < 0 ≤ `hi` | "around the scheduled time" |

"1 hours" reads "1 hour". Boundaries: 0 and 60 belong to the row whose condition says "≥". On the 2026-10-30 model: IZ 992 "at least 23 hours" (rule 1), LY 5410 "between 7 and 50 hours" (5), LY 5409 "between 1 and 44 hours" (5), TO 3459 "none: cancelled about 2 hours after it was scheduled to leave" (3), ASY 991 "unknown" (2), BZ 254 "unknown: no records for that time" (7).

The same text appears in the front page's "Warning" column, on the all-cancellations page, and on the flight page as "Warning: …." The flight page adds, for rules 1 and 2, "It was already cancelled at the earliest record."; for rules 4 to 7, "No records for part of that time."

### What changed (the opened day on a flight page)

One line per change, oldest first, the time in a left column:

- First line: "Earliest record (27 Oct 20:04) · on time, terminal 1" (status, terminal, check-in desks: what the first record has).
- A change whose record came within an hour of the flight's previous appearance (`prev_observed_at`): that record's time, "17:32 · Expected to leave at 17:38 instead". An appearance with no change is not a line, so the previous line can be older than `prev_observed_at`.
- More than an hour (`GAP_HOURS`) since `prev_observed_at`: "Between 27 Oct 20:24 and 29 Oct 14:29 · Check-in desks 345-348, zone B".
- The cancellation: always a range, "Between 19:16 and 19:32 · Cancelled", never a single time.
- A retime: "Moved to a new scheduled time: 23:30 → 01:10 on 31 Oct".
- Plain field names: expected time, status, terminal, check-in desks, check-in zone. Changes to the airline, airport, city or country names are left out (my call; they are spelling changes on the airport's side).

### Codeshares

Per day, inside that day's row on the flight page: "Probably the same flight as DL 7426 and AM 7895 (same time, terminal and check-in desks)." Each number links to its own page at that day's anchor. Partners change between days: of the 725 flight numbers scheduled on more than one day, 64 had two different non-empty partner lists (79 if a day with no partners counts as a list of its own), 2026-10-30. "Probably": the grouping is inferred, and arrivals with no desks can merge two flights (`OPEN_ISSUES`, Model).

### Names

Airline names exactly as the airport publishes them, double spaces included ("ARKIA  ISRAELI  AIRLINES", "K.L.M.", "ROYAL AUSTALIAN AIR FORCE"), with a small note beside them: "(as the airport lists it)". Airports by city and code: "Paris (ORY)". Cities title-cased (every current city is plain capitals). My call: title case mangles the published names, and correcting them would change the source's text.

## Pages

Every page: `<meta name="robots" content="noindex">` until the launch decision (q17), the footer, `lang="en"`.

### Front page (`index.html`)

Top to bottom:

1. Title "Cancelled flights at Tel Aviv airport". Under it: "A record of flights in and out of Ben Gurion Airport, kept since 27 October 2026, and which ones were cancelled."
2. Headline: "So far, X of Y flights with a known outcome were listed as cancelled. That's about 1 in N." Y counts flights (above) whose label is DEPARTED, LANDED or CANCELLED, on every day the site has (26 October's flights were recorded from the evening of 27 October on); X the CANCELLED ones. N = Y / X: below 20 rounded to the nearest whole number, from 20 up to the nearest multiple of 5, halves upward. Left out while X is 0. Today: 20 of 951, about 1 in 50.
3. One flight's story: a grey box with one cancelled flight's full change list in the "What changed" words, including the earliest record and any gap line, and a link to its flight page. Which flight (my call): the most recent cancelled flight with a non-censored warning (rules 3, 8 to 11); if none, the cancelled flight with the most change lines; ties by scheduled time, then flight number. Today: TO 3459.
4. Search box: "Flight number or city, e.g. LY 001 or Paris". Order: exact flight number (code and number, or number alone), then flight numbers starting with the query, then cities and airport codes starting with it; within each, by airline and number. Up to 10 results as links to flight pages, then "N more: type more of the number or city" when more match. It needs JavaScript; without it the box is hidden, and the day list (item 6) reaches every flight.
5. "Recent cancellations": the 10 most recent cancelled flights by scheduled time, upcoming ones included: date, flight, route with "scheduled to leave/land HH:MM", warning. Each links to its row's anchor on the flight page. "All cancellations" below. On a narrow screen each entry stacks (flight and date, then route, then warning); no fixed column widths.
6. "Flights each day": an inline SVG chart of the last 14 days with flights plus the days ahead. Each day shows its flights in three parts (cancelled, no known outcome, the rest) with the numbers in text beside the bar ("370 flights · 8 cancelled · 190 unknown"), never in color alone. The day of the last record (Israel date) is "today", drawn like past days; later days are pale, "ahead". A day the existing `partial` rule flags is pale and labelled "incomplete". Each day links to its day page. Under the chart, a compact list of every day the site has, linked, so no flight is out of reach without JavaScript.
7. "Last updated 30 Oct 2026, 00:02" (the last record, Israel time).
8. A line for the hiring reader: "Built by [owner's wording] · How this works · Code on GitHub".
9. Footer.

In the `<head>`: `<title>` "Cancelled flights at Tel Aviv airport (Ben Gurion)"; `<meta name="description">` and Open Graph `og:title`, `og:description`, `og:type` (no image), so a pasted link previews with plain words. The description: "Which flights in and out of Tel Aviv's Ben Gurion Airport were cancelled, and how much warning there was. Built by [owner's wording]." (The owner writes the name part.)

### Flight page (`flight/<airline><number>-<D|A>.html`, one per flight number and direction)

- Back link to the front page.
- Title: "TO 3459, Tel Aviv to Paris" (arrivals "from Paris to Tel Aviv"). A number with more than one city (LY 5115, LY 5116, IZ 419, 6H 890 on 2026-10-30) has no city in the title ("LY 5115, from Tel Aviv"), and each row shows its own city.
- Under the title: the airline name as published with "(as the airport lists it)", the airport ("lands at Paris (ORY)"), and the city in Hebrew, `<span lang="he" dir="rtl">`, when the page has one city.
- Summary: "Since 27 October: departed once, cancelled once, one upcoming." Counts per main label in the labels table's order.
- One row per row of the model's `flights` table (a retime chain is one row), on the day of `sched_local_final`, newest first: date, "scheduled to leave HH:MM" (with "last expected HH:MM" when different), the city when the page has more than one, main label, second label, warning line, codeshare line, then "What changed" in a `<details>` element: open for a cancelled row, closed otherwise. A retimed row says "Moved to a new scheduled time" with both times.
- Anchors: every row has one, in full form from `sched_local_first` and the airport, `#2026-10-28-1630-KUT`, so it never changes when a same-number flight appears later (IZ 992 has two rows on 30 October; LY 5115 left twice at 16:30 on 28 October, to Batumi and Kutaisi). Every link to a row carries its anchor. A link to a closed row scrolls to it; the design does not promise the browser opens it.
- The delay sentence (Labels) once, when any row shows "last expected".

Flight pages: 949 today; each grows by a row a day.

### Day page (`day/YYYY-MM-DD.html`)

Reached from the chart and the day list. Title "Thursday 29 October 2026"; a count line in the chart's words ("418 flights · 7 cancelled · N unknown"); the "incomplete" line when the `partial` rule flags the day; when the day has UNKNOWN flights, "No records for the time N of these flights left the airport's list."; then departures and arrivals in scheduled order, one row per flight: time, numbers, route, labels, warning for cancelled ones. Each row links to the flight page at its anchor. No change lines here, so day pages stay small.

### All cancellations (`cancellations.html`)

Every cancelled flight, newest first, as in the front page's table.

### How this works (`how-it-works.html`, replaces `methodology.html`)

Plain words, short sections; "I" allowed. Where the data comes from (the airport's public flight list, published on data.gov.il, the full `ATTRIBUTION`) and how often it is checked (every 2 minutes); what each label means; what the warning means, why it is a range or "at least", and why a cancellation's time is a range; why there are no delay figures yet; "final" and "not final"; "probably the same flight"; gaps in the records (records start the evening of 27 October 2026; none from 27 October 20:24 to 29 October 14:29; any later gap from the model); how it is built, for the technical reader (a few lines: an AWS Lambda every 2 minutes, write-once storage, a Python model, this site, tests and mutation testing), with the code link.

### Footer (every page)

Owner, 2026-10-30: "Flight data: Israel Airports Authority, published on data.gov.il." (new constant `SOURCE_SHORT`, beside `UNOFFICIAL` in `pages.py`), then `UNOFFICIAL` verbatim, then "Times are Israel time.", then "How this works", "Code on GitHub", "Built by [owner's wording]". The full `ATTRIBUTION` (dataset name and resource ID; `src/model/report.py`, unchanged for the report) is on "How this works". `timeline.check` requires `SOURCE_SHORT` and `UNOFFICIAL` on every page and `ATTRIBUTION` on `how-it-works.html`; `docs/terms.md` (clauses 6 and 8) and `docs/publishing.md` change to match when this ships.

The built-by text and the GitHub address come from one place in `pages.py`; until the owner writes the line it holds a marker the upload check refuses.

## Look

- One column, max width about 42rem, generous spacing; the system font stack; tabular numbers. Smaller side padding on phones.
- Colors as CSS custom properties, light by default, a dark set under `prefers-color-scheme: dark`. Every text color pair, pills and chart text included, clears 4.5:1 in both schemes; the builder records the pairs and their ratios in this doc's Deviations. (The mockup's red pill, about 4.3:1, does not.)
- Labels are small rounded pills with text, never color alone. The chart's accessible name states the counts.
- At 375 px: no sideways scrolling, tables stack, change lines keep their time beside them.
- No framework, no web fonts, no images; the chart is SVG written by Python.

## How it is built

- Same pipeline: `python -m timeline.build --model data/model --out site`, DuckDB over the model's Parquet files, the marker-file swap, `timeline.check` before upload, `scripts/publish.sh`. `pages.py` stays pure functions from rows to HTML.
- Search data: one entry per flight number and direction, with keys from `pages.search_keys` taken as the union over that number's rows (a number can have two cities) and its page address. Written as JSON inside a `<script type="application/json">` element on the front page, with `<` escaped as `<` so a name containing `</script>` cannot end the element.
- Page addresses unique per file, and the build stops if two flight numbers would map to the same file (`AB` + `12` against `A` + `B12`). Anchors unique per page (codeshare partners share anchor strings across pages, which is fine).
- Same model, same bytes (determinism across processes, as now). The build time is the last record's time, never the clock.
- Cost: no new AWS service. Hosting as estimated in `docs/timeline.md` "Publishing": well under a cent a month for today's 2.4 MB site, about $0.03 at most for a site near 1 GB.

## Tests and checks

Kept from v1, rewritten to the new words: every `flights` row on exactly one flight page and on one day page (the day of `sched_local_final`, including a retime across midnight); anchors and addresses stable and unique, the build stops on a collision; HTML escaping (a city named `<script>` stays text); Israel time across the October clock change, run under an Israeli time zone; a NULL final scheduled time stops the build; `--out` without the marker refused; determinism across `PYTHONHASHSEED`; `noindex` on every page.

Retired: the full `ATTRIBUTION` on every page (now `SOURCE_SHORT` and `UNOFFICIAL` everywhere, `ATTRIBUTION` on how-it-works); counts as flight numbers (now flights as defined above); a Hebrew status word with `lang="he"` (now the Hebrew city with `lang="he" dir="rtl"`); "listed together" and "flight numbers listed" (now "Probably the same flight as" and flights); every v1 exact sentence.

New, each with a `scripts/mutation_check.py` entry:

- one exact-text test per warning rule 1 to 11, including the 0 and 60 boundaries and a 42-hour censored bracket (LY 5409's shape);
- one per label row; NO FINAL UPDATE decided in UTC (a test run under Asia/Jerusalem with a flight at 23:55 Israel time and a last record at 22:02 UTC); DELAYED from the row's own records; "last expected" and the delay sentence; `uncanceled` NULL as false and both changed-back lines;
- "What changed": the gap line from `prev_observed_at`; the cancellation as a range;
- the headline numbers, the 1-in-N rounding with its tie, left out at 0;
- the chart's counts equal the day pages'; today, ahead and incomplete days; every day linked;
- the featured-flight rule; the recent-cancellations order and the cap of 10;
- the codeshare split on label, DELAYED or warning;
- a number with two cities (title without a city, rows with theirs); two rows of one number on one day (two anchors, links carry them);
- search: the order, the cap and the "N more" line; the union of keys; a name containing `</script>`, a quote and a backtick stays inside the JSON (run under Node, as the current search test);
- `timeline.check`: "we", "our", "us" as whole words, case-insensitive, on every page; "I" as a whole word outside `how-it-works.html` and the built-by line; "board", "snapshot", "stored", "observed", "receipt" as whole words on every page except `how-it-works.html`; "minutes late" and "hours late"; the existing banned phrases kept; the built-by marker refused. A test that "were", "hours", "status", "BUS", "AUSTRIAN AIRLINES" and "at least 23 hours" pass, and a mutation that turns the word match back into a substring match so that test fails.

## Left to the builder

Markup and CSS; exact colors and spacing within the look rules; the chart's drawing; how "Show details" looks; section order on "How this works"; anything marked "my call" that turns out awkward in code, as long as the words and rules hold.

## Outside this design, for the owner

- Freshness: "Last updated" comes from a hand-run build and publish (`scripts/publish.sh`). A portfolio page showing a weeks-old date looks abandoned; a scheduled rebuild is q2/q5.
- Link-preview image: a `.png`, a new file type for the allowlist and the check (q17).
- Search engines: `noindex` stays until the launch decision (q17).
- The five outsider sessions (q13): their tasks quote v1 wording, and their stop rule ("fewer than two of five name a real use") was written for a product. The review proposes asking each person what the site is, who made it and what they think that person can do, with a traveler-use question kept as a probe, not a stop. Rewrite the script before any session.

## Review (2026-10-30)

Builder check (Opus; Fable was over its limit): five points, all folded in (footer vs the word check, codeshares per day, the changed-back wording, names, anchors).

Outside review (reviewer chosen by the owner; full text in commit f360540): 0 critical, 13 significant, 11 minor, 8 nits, 11 direction findings. Facts checked against the model before folding in (190 of 370 flights on 28 October without a known outcome; 9 open flights before the last record; 4 numbers with two cities; 13 numbers twice on one day; LY 5409's 76-minute to 43-hour bracket; README's old wording).

Folded in: every significant and minor finding, and the nits, except as follows.
- Headline denominator: kept at 951 (all days). The reviewer read "since 27 October" as excluding 26 October's flights; those were recorded from 27 October on, and the lede now says "kept since 27 October".
- "Final" and "not final": the reviewer's gloss is a guess; the site quotes the airport's words and says they are undefined.
- Warning wording uses hours only (no days), so ranges never mix units.

Direction, with the owner's decisions of 2026-10-30:
- D3 (lead with one flight's changes instead of cancellations): the owner kept cancellations as the lead; D9's point is taken by putting one flight's full story directly under the headline.
- D7 ("I" on How this works): adopted by the owner, with the built-by line.
- D5 (launch gate): the owner dropped "first cancellation-warning figures" from the launch gate; launch once the site is live and this redesign is done. Hosting still waits on AWS account verification (q15), so building this does not delay it.
- D1, D6, D11: adopted as the code link and built-by line on the front page and the preview title and description; the name is the owner's to write. The full page set stays (D6 agrees it is cheap).
- D4: the delay sentence adopted. Settling "expected time" by the owner's own observation at the airport is not adopted: one flight settles nothing.
- D2: the owner's premise stays; the success question for observed sessions moves to q13 (D10).
- D8: adopted (published names with a note, unknown counts on the chart, NO FINAL UPDATE, the Hebrew city with `lang`).
