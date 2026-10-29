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
