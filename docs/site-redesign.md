# Site redesign (q18), updated for "Will It Fly?" (q27)

Grade: production-lean, same as the v1 site (`docs/timeline.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript.
The 2026-11-17 update keeps the grade.

Status: design v2, 2026-10-30. Worked out with me over mockups, then a builder check and a full outside review (summary at the end; the review's full text is in commit f360540). Built 2026-10-30 (plan: `docs/site-redesign-plan.md`; what building changed: "Deviations" at the end); published 2026-10-30 (`docs/publishing.md`). It replaces the "Pages", "Wording", "How it is built" and "Tests and mutation checks" sections of `docs/timeline.md`, which now point here.

Updated 2026-11-17 for q27. That day I decided the redesign, "Will It Fly?" in look A (`docs/flight-lookup.md`, "Decided 2026-11-17", D10 to D12); the design work was agents', and a Fable agent brought this document to my decisions. The update was reviewed the same day by a fresh Opus reviewer, and its findings are folded in (`docs/flight-lookup.md`, "Update"). Built to [will-it-fly-plan.md](will-it-fly-plan.md): at the hand check on 2026-11-17 I looked at the built pages, light and dark, and a whole-branch review followed the same day. Where the build departs from this text is in the plan's "Deviations". Until q27's first upload, the live site follows the earlier text of this file (commit 7c0d374) and the look under "The look of 2026-11-04". Later the same day I answered every open word and question the update had listed (`docs/flight-lookup.md`, D13); the two things it left open (`docs/flight-lookup.md`, "Words", "Still open") were settled at the hand check.

Mockups I approved for look and wording, with real data from the 2026-10-30 00:02 build: `docs/site-redesign/front-page-mockup.html` and `docs/site-redesign/flight-page-mockup.html` (open in a browser; the heading above each card is mockup chrome). Where a mockup and the rules below differ, the rules win. Known differences: the mockups title-case airline and airport names, leave out "last expected", the earliest-record and gap lines, "Times are Israel time" (front page), "Last updated", the story box's place in the page list, and use a footer that would fail the check.
Those mockups show the site as designed on 2026-10-30. The 2026-11-17 design was worked out on four rounds of mockups by a Fable designer, kept outside the repository; the rules below carry what they settled.

## Why

The site is my portfolio piece for a job search: a recruiter or hiring manager clicks through from a CV or LinkedIn and should understand it in seconds. My test (2026-10-30): if it is useful to a traveler looking up a flight, it is impressive to a hirer; "it doesn't necessarily have to be useful in day to day life, just impressive, clean, simple". The v1 site fails both: its front page is a table of dates, and its sentences ("First observed CANCELED on the public board", "first seen by us", "stored boards") mean nothing to someone who has never heard of the flight board.

2026-11-17 (q27). The test above already ran through the traveller. That day I judged the built pages as one traveller would: nervous, not technical, on a phone, asking about their own flight. The pages led with the airport-wide figures and their background, and I found their language very confusing. So the site is renamed "Will It Fly?", reorganised around the traveller's own flight, reworded line by line for a reader who is not technical, and given a look of its own (`docs/flight-lookup.md`, D10 to D12).

## Goals

- Anyone understands what the site is and what they can do on it within a few seconds, with no prior knowledge of the airport, data.gov.il or this project.
- The front page leads with "Find your flight" over a plain search box. The airport-wide figures, one cancellation's story and the lists follow.
- A flight page answers for the traveller's own flight first: its days still ahead come first, soonest first, with the nearest day's chances on a phone's first screen; then the flight number's days as a strip; then past days, newest first.
- Every line a traveller reads passes my test (2026-11-17): a 60-year-old checking her daughter's flight reads it aloud without pausing.
- A hiring reader can see who built it and reach the code from every page's footer.
- Clean on a phone (390 px wide, the width the mockups were measured at) and a laptop, light by default with a dark mode. Look A's dark scheme ships with q27 (my decision, 2026-11-17); the mockups are light only, so its values are derived by the look's rule and shown to me at the hand check.
- Looks right with a few weeks of data and fills in as data grows, with no redesign.

## Non-goals

- Delays under an hour ("N minutes late", averages of minutes): what the airport's expected time measures (leaving the gate or taking off) is still unconfirmed (q3). Since 2026-11-17 a delay of an hour or more is counted and shown, with a line saying what "delayed" means (`docs/flight-lookup.md`, "The blend", Delays).
- A tested forecast, or a sign applied to a flight (`docs/flight-lookup.md`, "The blend" and "The gate"). The chance a flight page shows is a simple first blend, and the site says so.
- A table that ranks airlines, and route comparisons. An airline's counts show only on its own flights' pages.
- Live updates. The site is as fresh as the last build and publish, and the front page and every flight page say how old they are.
- New file types beyond fonts. The upload sends `.html`, `.css` and `.js` and, for look A, four `.woff2` font files and their licence, `fonts/LICENSE.txt` ("Look"). Still no images and no JSON files: the chart is inline SVG; the search data is JSON inside a script. A link-preview image (`.png`) is a launch item (q17), not this design.

## Anti-goals (a failure even if it works)

- A line my reader would pause on (the test under "Goals"). As before, data-collection words ("board", "snapshot", "stored", "observed", "receipt", "first seen by us") stay off every page other than "How this works". "Record" is allowed ("there's no record of how this flight ended").
- The site speaking as an institution: "we", "our" and "us" are banned on every page (my decision, 2026-10-30). "I" is allowed only on "How this works" and in the built-by line, so a reader sees who built it (my decision, 2026-10-30). Everywhere else each sentence states a fact about a flight.
- Overclaiming. Plain words, but only what the airport's list supports: notice is a range or a lower bound, never a measured moment ("at least 21 hours' notice", "between 7 and 50 hours"); a cancellation never gets a single clock time, only "Between 19:16 and 19:32"; no "took off", "operated by", "delayed by", "minutes late"; "probably" where something is inferred ("probably the same plane"); a flight's chance reads "about" or "under" and is never "0%"; an expected time is the airport's own. The words changed on 2026-11-17; this discipline did not.
- Looking official: no IAA name in the title, no logos; the source line and the unofficial line on every page (`docs/terms.md`, clauses 6 and 8).
- Shipping the built-by placeholder: the upload check refuses a site that still contains it.

## Words (approved by me, 2026-11-17; they replace the words of 2026-10-30 where the two differ)

The words that carry figures (the chances, the table, the total, the disclaimer) are in `docs/flight-lookup.md`, "Words", with how they were reached. This section and "Pages" hold the rest. The q27 build shows these words (`docs/will-it-fly-plan.md`). Every line in the tables below was run, for this update, against the upload check's banned phrases and its "we", "our" and "us" rule as the code had them then, and passes; the lines marked "Question 6" of the plan were run against the built check for the plan's Task 17, and pass. Lines I approved later the same day, for the cases the first approval left open (`docs/flight-lookup.md`, D13), are marked "approved by me, 2026-11-17".

- The site's name is "Will It Fly?", with "Tel Aviv airport" beside it. It replaces "Cancelled flights at Tel Aviv airport".
- "Cancelled": not "CANCELED" and, since 2026-11-17, not "listed as cancelled". Where a sentence says when, it says "marked cancelled". "How this works" says once what it means: the airport's list marked the flight cancelled.
- "Notice", not "warning": how long before its scheduled time the airport's list marked a flight cancelled. Lists head the column "Notice given".
- "Scheduled to leave at HH:MM" for departures, "scheduled to land at HH:MM" for arrivals. The approved words already had "scheduled to land at 19:45"; round 4 carried "at" into the story's line and the route cells ("scheduled to leave at 05:35"). Never "due".
- Times are Israel time; the footer of every page says "All times are Israel time."
- Notice is given in whole hours: lower ends rounded down, upper ends rounded up (unchanged: hours only, no switch to days, so a range never mixes units). The time left to a flight is named in days and hours ("3 days away", "6 to 12 hours before a flight").
- The airport's status words appear in lower case in the change lines: on time, delayed, landing, landed, departed, cancelled, early. "Final" and "not final" are the airport's words with no published definition; they appear in quotes, and a page that quotes them says once: "“Final” and “not final” are the airport's own words. It doesn't explain them." The note stands under the first list of changes that is already open and quotes them or, when none is open, under the first that quotes them.
- An airline's name stands as the airport publishes it, with no note beside it: "(as the airport lists it)" is dropped on every page. Inside a sentence it takes a spoken name ("Names").

### Who is a "flight"

Replaced by rules C1 to C4 in `docs/flight-lookup.md`: what a flight is, its result, and which flights make a rate. The split described next is retired. Before `docs/flight-lookup.md`, a flight was a codeshare group (`codeshare_group_id`): the flight numbers the model groups for one scheduled day. A group's members are shown and counted together only when they share the same main label, the same DELAYED flag and the same warning text; otherwise each member is its own flight. Every count on the site counted flights this way.

### Labels

In a list, a flight gets its label by C10 in `docs/flight-lookup.md`; a number's own label on its own page is as below.

Each flight on each day gets one main label, plus an optional second one. A label is capitals with a mark before it, so it never rests on its colour ("Look").

| Model outcome | Label | Line under it on the flight page |
|---|---|---|
| `departed` | DEPARTED | none |
| `landed` | LANDED | none |
| `canceled` | CANCELLED | the notice sentence (below) |
| `open`, `sched_utc_final` after the last sighting of the board (`confirmed_until` of the last snapshot) | UPCOMING | none; the day's chances stand in the headline slot or on the day (`docs/flight-lookup.md`, "Pages", Flight page) |
| `open`, `sched_utc_final` at or before that sighting | NO NEWS YET (was NO FINAL UPDATE) | "Its time has passed, and the airport hasn't said how it ended." |
| `gap` | UNKNOWN | "There's no record of how this flight ended." |
| `vanished` | UNKNOWN | "The airport removed this flight 45 hours early without saying why. It may have been cancelled or moved to another time." On a day still ahead it adds: "Check with your airline." Less than an hour early: "The airport removed this flight less than an hour early without saying why. …" (Question 6g of the plan, approved 2026-11-17) |
| `dropped` | UNKNOWN | "The airport removed this flight without saying why." |

Both sides of the UPCOMING comparison are the model's naive UTC values; comparing the Israel wall-clock `sched_local_final` instead turns the 9 evening flights of 29 October (scheduled 23:30 to 23:55 Israel time, last record 22:02 UTC) into UPCOMING.

Second label: DELAYED, by the hour rule (my decision, 2026-11-17): a day is labelled DELAYED when the airport's expected time is an hour or more after the scheduled time, the rule the counts and the chances use (`docs/flight-lookup.md`, "The blend", Delays). Shown beside the main label: "LANDED · DELAYED". No line stands under it. Until then the label was added whenever the airport's own records showed the status DELAYED, whatever the minutes; that word still shows in a list of changes ("Status delayed").

Expected times and past days. When the airport's last expected time differs from the scheduled time, a day with no final word yet (ahead, NO NEWS YET or UNKNOWN) shows both: "scheduled 19:45 · expected 19:55" (it was "scheduled to leave 16:45 · last expected 17:09"). A past day that landed or left reads, approved by me, 2026-11-17: "Monday 16 November · scheduled 19:45 · landed around 19:55 · LANDED", and a departure "scheduled 17:30 · left around 17:38 · DEPARTED" (times made up). The scheduled time stays, because it is how the reader knows the flight, and both times show even when they are the same ("scheduled 19:45 · landed around 19:45"). No difference is computed on the line. "Landed around" and "left around" are my fix after round 4, where the reader paused at "expected" on a day marked LANDED; I confirmed their place on 2026-11-17. A page carries one note, once, on the first day that shows "expected", "landed around" or "left around": "Expected times are the airport's own. Delays under an hour aren't counted, because the airport doesn't say whether its time means leaving the gate or taking off."

`uncanceled` NULL counts as false (it is NULL for the flights whose earliest record already showed them cancelled and that were never seen otherwise). When true, a line goes under whatever the final label is: "Marked cancelled for a while, then back on." If the final label is CANCELLED again: "Cancelled, back on, then cancelled again." The notice shows only under a final CANCELLED and comes from the model's cancellation fields as they are.

### Notice (was "Warning"; cancelled flights only)

In a list, a cancelled flight shows the notice of the number marked cancelled first (C9 in `docs/flight-lookup.md`); a number's own page keeps its own notice, as below.

How long before its scheduled time the airport's list already showed the flight as cancelled. The rules are those of 2026-10-30; only the words changed. Inputs: `lo` = `cancel_lead_min` (minutes from the first record showing it cancelled to the scheduled time), `hi` = `cancel_lead_max_min` (from the last record before that one; NULL when the earliest record already showed the flight cancelled), `cancel_lead_censored` (more than an hour between those two records). `h(x)` is whole hours. The first matching rule wins:

| # | Case | Sentence, on the flight page and beside the label on a day page | In lists, under "Notice given" |
|---|---|---|---|
| 1 | `hi` is NULL, `lo` ≥ 60 | "Cancelled with at least 23 hours' notice. It was already cancelled when it first appeared." (h(lo, down)) | "23+ hours" |
| 2 | `hi` is NULL, `lo` < 60 | "How much notice is unknown: it was already cancelled when it first appeared." | "unknown" |
| 3 | `hi` < 0, not censored | "Cancelled with no notice: it was marked cancelled about 2 hours after it should have left." For an arrival, "should have landed". The amount follows the 2026-10-30 rule: "less than an hour" when −lo < 60; else "about an hour" when −hi < 120; else "about h(−hi, down) hours". The two shorter amounts ("…less than an hour after it should have left.", "…about an hour after it should have left.") are approved by me, 2026-11-17 | "none" |
| 4 | `hi` < 0, censored | "Cancelled with no notice: it was only marked cancelled after its scheduled time. (There's a gap in the records then.)" | "none" |
| 5 | censored, `lo` ≥ 60 | "Cancelled between 7 and 50 hours before its scheduled time. (There's a gap in the records then.)" (h(lo, down) and h(hi, up)) | "7 to 50 hours" |
| 6 | censored, 0 ≤ `lo` < 60 | "Cancelled up to 5 hours before its scheduled time. (There's a gap in the records then.)" (h(hi, up)) | "up to 5 hours" |
| 7 | censored, `lo` < 0 | "How much notice is unknown: there's a gap in the records then." | "unknown" |
| 8 | not censored, `lo` ≥ 60 | "Cancelled with at least 21 hours' notice." (h(lo, down)) | "21+ hours" |
| 9 | not censored, 0 ≤ `lo`, `hi` < 60 | "Cancelled less than an hour before its scheduled time." | "under an hour" |
| 10 | not censored, 0 ≤ `lo` < 60 ≤ `hi` | "Cancelled about an hour before its scheduled time." | "about an hour" |
| 11 | not censored, `lo` < 0 ≤ `hi` | "Cancelled around its scheduled time." | "almost none" |

- "1 hours" reads "1 hour": "Cancelled with at least 1 hour's notice."; in lists, "1+ hours" (approved by me, 2026-11-17). Boundaries: 0 and 60 belong to the row whose condition says "≥".
- Rule 11's list form was "around its time" until round 4: under "Notice given" the reader expects an amount, so the list says "almost none" and the flight page keeps its sentence.
- "At least" always follows "with": "Cancelled with at least …". "Cancelled at least …" would read as the banned "cancelled at".
- On a phone the cancellations table stacks and its column heads are hidden, so each notice there is led by "Notice given: ". It was "Warning: ".
- The examples' numbers are real cases of the 2026-10-30 model: IZ 992 (rule 1, 23 hours), LY 5410 (rule 5, 7 and 50 hours), TO 3459 (rule 3, about 2 hours after).

### What changed (the opened day on a flight page)

One line per change, oldest first, the time in a left column. My word on 2026-11-17 was to keep the list as built, "already plain", with one fix after round 4: its first line, "First on the list at 09:32", in place of "Earliest record (09:32)". I confirmed that place the same day. On a phone a list of changes reads as lines ("Between 8 Nov 08:46 and 8 Nov 09:02 Cancelled"), not as two narrow columns.

- First line: "First on the list at 09:32 · on time, terminal 3". Of the built "Earliest record (09:32)" the round-4 reader would have said "first seen at 09:32". After the time comes what the first record has, of status, expected time (when it differs from the scheduled time), terminal, check-in desks and zone; empty ones are left out. Three more forms, approved by me, 2026-11-17:
  - A first record on another day than the flight's carries its date: "First on the list on 14 Nov at 19:46 · “not final”, terminal 3".
  - A first record that is the records' own first list, or the first after a gap, says "already": "Already on the list at 20:04 · landed, expected to land at 19:18, terminal 3"; with a date, "Already on the list on 27 Oct at 20:04 · on time, terminal 3". The flight was on the airport's list before the records could see it, so "first on the list" would be untrue for it.
  - A first record that already shows the flight cancelled reads "already cancelled" in the status's place ("Already on the list at 20:04 · already cancelled, terminal 3"), so its time reads as the listing's, never as a cancellation time.
- A change whose record came within an hour of the flight's previous appearance (`prev_observed_at`: the last sighting of that appearance, an unchanged download included, R9): that record's time, "17:32 · Expected to leave at 17:38 instead". An appearance with no change is not a line, so the previous line can be older than `prev_observed_at`.
- More than an hour (`GAP_HOURS`) since `prev_observed_at`: "Between 27 Oct 20:24 and 14:29 · Check-in desks 345-348, zone B" (TO 3459, on its 29 October row). A time in the change list carries its date only when it differs from the row's day.
- The cancellation: always a range, "Between 19:16 and 19:32 · Cancelled", never a single time.
- A retime: "Moved to a new scheduled time: 30 Oct 23:30 → 01:10" (on a 31 October row).
- Plain field names: expected time, status, terminal, check-in desks, check-in zone. A field that empties says so: "no expected time", "no terminal", "no check-in desks", "no check-in zone" (each line starts with a capital: "No check-in desks"). Changes to the airline, airport, city or country names are left out (provisional; they are spelling changes on the airport's side).

### Codeshares

A number's partners are the other numbers of its flight under C1 in `docs/flight-lookup.md` that the list showed with the same expected time, terminal and check-in desks (`partners()` in `src/timeline/flights.py`). A number joined by its airline or desks alone is not one; when it is marked cancelled in a flight that is not, it gets the twin line (`docs/flight-lookup.md`, "Words", Flight page: other situations).

Per day, among that day's lines on the flight page: "Also sold as LY 9255 (probably the same plane)." With two partners: "Also sold as LY 9252 and LY 9255 (probably the same plane)." With three or more: "Also sold as LY 9252, LY 9255 and DL 7426 (probably the same plane)." (approved by me, 2026-11-17). It replaces "Probably the same flight as DL 7426 and AM 7895 (same time, terminal and check-in desks)."; the reason leaves the flight page for "How this works". Each number links to its own page at that day's anchor. Partners change between days: of the 725 flight numbers scheduled on more than one day, 64 had two different non-empty partner lists (79 if a day with no partners counts as a list of its own), 2026-10-30. "Probably": the grouping is inferred, and arrivals with no desks can merge two flights.

### Names

- Airline names exactly as the airport publishes them, double spaces included ("ARKIA  ISRAELI  AIRLINES", "K.L.M.", "ROYAL AUSTALIAN AIR FORCE"). My call of 2026-10-30 stands: title case mangles the published names, and correcting them would change the source's text. The note "(as the airport lists it)" is dropped (round 4). Inside a sentence an airline takes a spoken name from a short list kept by hand ("LOT", "Lufthansa", "El Al"), and "its airline" when it has none (approved by me, 2026-11-17). The build proposed the list, and I approved it at the hand check, 2026-11-17 (`docs/flight-lookup.md`, "Still open").
- Airports by city and code: "Warsaw (WAW)". Cities title-cased (every current city is plain capitals).
- A flight's title, on its page, in the search list and in the story box: "LO 155 · Warsaw to Tel Aviv" for an arrival, "WZ 016 · Tel Aviv to Moscow" for a departure.
- A number that has gone to more than one city names them (round 4; the built title, "LH 697, from Tel Aviv", left the reader asking "to where?"): "LH 697 · Tel Aviv to Athens or Frankfurt"; three cities, "Tel Aviv to Athens, Larnaca or Munich"; more, "Tel Aviv to Vitoria, Pristina or 3 other cities"; an arrival, "LH 682 · Munich or Frankfurt to Tel Aviv". The newest day's city comes first. 27 numbers in the 2026-11-17 build have more than one city.
- Two titles of that build carry the airport's own odd data: "H4 238 · Tel Aviv to Bucharest", where one day goes to a second airport, whose city the list cuts short as "Bucharest (bane" (BBU), and the other days to Bucharest (OTP); and "UA 091A · Newark or Ben Gurion to Tel Aviv". The mockups name a city once when one name is the beginning of the other, and so does the build.

### Still open

Every line this section listed as without approved words on 2026-11-17 has them now, in the sections above and in "Pages". What remained is listed in `docs/flight-lookup.md` ("Words", "Still open"): the list of spoken names for airlines and the text of "How this works", sections 2 to 10. Both were for my approval at the hand check during the build, and I approved both there on 2026-11-17.

## Pages

Every page: `<meta name="robots" content="noindex">` until the launch decision (q17), the top line, the footer, `lang="en"`. The words that carry figures are in `docs/flight-lookup.md`, "Words", and are named here by their place.

### Every page

| Where | Words |
|---|---|
| Top | **Will It Fly?** · Tel Aviv airport |
| Under it, on every page | Updated 3 hours ago |
| The same, without scripts | Updated 17 Nov at 09:46 |
| Browser tab | the page's own title |
| Footer | "Footer", below |

The site's name links to the front page; on the front page it is the page's `<h1>`.

"Updated" stands on every page (my decision, 2026-11-17). The first approval named the front page and flight pages; my terms reading says every page says when it was last updated (`docs/terms.md`, clause 4), and so does the disclaimer. The page's age is written by the page's script from the time of the last sighting of the board (`docs/flight-lookup.md`, "Pages", `fromhere.js`); the build writes the date-and-time form, which stands when scripts are off. The script works the age out when the page loads, and again each time the page is shown again, so a tab left open does not keep an old age. Its forms (the third is the first approval's; the others are approved by me, 2026-11-17):

| How old the page is | Words |
|---|---|
| Under an hour | Updated less than an hour ago |
| From 1 hour | Updated 1 hour ago |
| From 2 to 23 hours, in whole hours rounded down | Updated 3 hours ago |
| From 24 hours | Updated more than a day ago |
| From 48 hours, in whole days rounded down | Updated more than 2 days ago |

"More than" keeps an old page from sounding fresher than it is.

The browser tab and a shared link show the page's own title (approved by me, 2026-11-17): "Will It Fly? Tel Aviv airport (Ben Gurion), unofficial" on the front page, a flight's title on its page ("LO 155 · Warsaw to Tel Aviv"), and "Monday 16 November", "Cancelled flights" and "How this works" on the others.

### Front page (`index.html`)

Top to bottom:

1. The top line.
2. Find your flight.

   | Where | Words |
   |---|---|
   | Headline, the label over the box | **Find your flight** |
   | In the box | Flight number or city, like LY 001 or Paris |
   | Under the box | Your flight number is on your ticket or booking email. |
   | Search, many matches | 12 more. Keep typing to narrow it down. |
   | Search, nothing found | No flight found. Check the number, or try a city. Flights show up here about 3 days before they leave. |
   | Without scripts, in the box's place | To find your flight, pick its day below. |

   The label is the largest line on the first screen. The order of results is unchanged: exact flight number (code and number, or number alone), then flight numbers starting with the query, then cities and airport codes starting with it; within each, by airline and number; up to 10 results as links to flight pages, each by its title. The search needs JavaScript. Without it the box, its label and its hint are hidden, and in the box's place stands "To find your flight, pick its day below.", whose last words link to the day list (item 8), which reaches every flight (approved by me, 2026-11-17). `search.js` writes the two search lines; today it writes "N more: type more of the number or city" and nothing when no flight matches.
3. The introduction: "Look up your flight to see the chance it's cancelled or delayed an hour or more. Based on every flight at Ben Gurion Airport since 27 October."
4. "Chance of cancellation, by how soon you fly": the table of six rows, the line under it and the delay line (`docs/flight-lookup.md`, "Words", Front page: the table).
5. The total: three tiles, the sentence, the late line and the left-out line (`docs/flight-lookup.md`, "Words", Front page: the total).
6. One flight's story, under the heading "A recent cancellation, step by step": the flight's title as a link to its page ("WZ 016 · Tel Aviv to Moscow"), its day ("Tuesday 17 November · scheduled to leave at 05:35"), and its full list of changes in the "What changed" words. Which flight is unchanged: among flights labelled CANCELLED by C10, the most recent with a non-censored notice (rules 3, 8 to 11); if none, the one with the most change lines; ties by scheduled time, then flight number; told through the number of C9. One more rule (my decision, 2026-11-17): the picker skips a flight first listed after its own scheduled time. On 17 November the story was WZ 016, scheduled to leave at 05:35 and first on the list at 09:32, whose steps make no sense read aloud. The picker is in `src/timeline/flights.py`, which is not a frozen file.
7. "Recent cancellations": the 10 most recent cancelled flights by scheduled time, upcoming ones included. Columns: Date · Flight · Route · Notice given. A route reads "Tel Aviv to Moscow (ZIA), scheduled to leave at 05:35". Each row links to its day on the flight page. Under it the link "All cancelled flights". With none: "No cancelled flights so far." On a narrow screen each entry stacks (flight and date, then route, then "Notice given: " and the notice).
8. "Flights each day": one line per day for the last 14 days with flights plus the days ahead, each a link to its day page, with the day's flights drawn as a thin bar and the numbers in text beside it ("370 flights · 8 cancelled · 190 unknown"), never in colour alone. Marks beside a day: "today" for the day of the last record (Israel date); "upcoming" for a later day (it was "ahead"); "upcoming · not all listed yet" for a later day the `partial` rule flags; "some flights missing" for a past day it flags (it was "incomplete"). Under it, "Pick a day:" and every day the site has, linked, so no flight is out of reach without JavaScript. The round-4 reader paused at "unknown" in a day's line ("Unknown what?"). It stands as approved: it is the label UNKNOWN's own word, and a plainer one would have to change in every place at once.
9. Footer. The built-by line that stood above it is dropped: it is in the footer's links.

In the `<head>`: `<title>` "Will It Fly? Tel Aviv airport (Ben Gurion), unofficial" (approved by me, 2026-11-17; "Every page"); `<meta name="description">` and Open Graph `og:title`, `og:description`, `og:type` (no image). The description, not shown on the page: "Look up a flight at Ben Gurion Airport to see the chance it's cancelled or delayed an hour or more. Unofficial. Built by [owner's wording]."

### Flight page (`flight/<airline><number>-<D|A>.html`, one per flight number and direction)

Top to bottom:

1. The top line.
2. The title and the line under it.

   | Where | Words |
   |---|---|
   | Title | **LO 155 · Warsaw to Tel Aviv** |
   | Under the title | LOT POLISH AIRLINES · from Warsaw (WAW) · ורשה |
   | Under the title, a number with more than one city | LUFTHANSA |
   | Under the title, a departure with one city | [AIRLINE] · to Paris (ORY) · [the city in Hebrew] |

   The Hebrew city is `<span lang="he" dir="rtl">`, when the page has one city. A departure names where it goes, "to Paris (ORY)", as each day of a number with several cities does ("to Athens (ATH)"). Under the title that form is approved by me, 2026-11-17.
3. The traveller's day, the nearest day still ahead: "**Tuesday 17 November** · scheduled to land at 19:45 · UPCOMING". When no day is ahead: "LH 694 isn't on the airport's list right now. The last one was on Tuesday 10 November." While that last flight is still on the airport's list the line reads "LH 694 has no upcoming flight on the airport's list right now. The last one was on Tuesday 10 November." (`docs/flight-lookup.md`, "Words", Flight page: other situations).
4. The headline slot: the two chances and the "Worked out from" line, closed by a heavy rule (`docs/flight-lookup.md`, "Words" and "Pages").
5. In smaller type: the number's "so far" line, its airline's, the all-airlines line, the freshness line ("Updated 3 hours ago. Things may have changed, so check with your airline.") and the link "What the numbers mean".
6. What belongs to the traveller's day alone: "Also sold as …" and its "What changed" list. The day stands once, here at the top; its mark in the strip links here.
7. The strip, "LO 155, day by day": one mark per day of the number, with its key (`docs/flight-lookup.md`, "Words").
8. The later days still ahead, soonest first. Each: its date, "scheduled to land at 19:45", its label, its chances on one line (the cancellation chance alone on a day already DELAYED), then its own lines.
9. The past days, newest first.

A day's lines, in order: the date written out ("Monday 16 November"); the time line ("scheduled to land at 19:20"; with an expected time, or on a past day that landed or left, the forms under "Labels"); the city when the page has more than one ("to Athens (ATH)"); the main label and the second label; the label's line; the notice sentence under CANCELLED; the changed-back line; the twin line; "Also sold as …" (a day can carry both); the note on expected times, once a page; then "What changed" in a `<details>` element, open for a cancelled day and closed otherwise.

- One day per row of the model's `flights` table (a retime chain is one row), on the day of `sched_local_final`. A retimed row says "Moved to a new scheduled time" with both times.
- Anchors: every row has one, in full form from `sched_local_first` and the airport, `#2026-10-28-1630-KUT`, so it never changes when a same-number flight appears later (IZ 992 has two rows on 30 October; LY 5115 left twice at 16:30 on 28 October, to Batumi and Kutaisi). Every link to a row carries its anchor. A link to a closed row scrolls to it; the design does not promise the browser opens it.
- On a phone the two chances stack, each the label over its number, straight after the traveller's day. On the round-4 mockup of LO 155 at 390 x 844 the day, both chances, the "Worked out from" line and the three lines in smaller type end at 807 px, above the fold; the freshness line crosses it (the designer's measurement).

Flight pages: 1,076 in the local build of 2026-11-17; each grows by a row a day.

### Day page (`day/YYYY-MM-DD.html`)

Reached from "Flights each day" and the day list.

| Where | Words |
|---|---|
| Title and counts | Monday 16 November · 357 flights · 3 cancelled |
| Part of the day missing | Some flights from this day may be missing: the records don't cover the whole day. |
| Unknown outcomes | For 6 of these flights, there's no record of how they ended. |
| Title and counts, one flight (Question 6f of the plan, approved 2026-11-17) | Monday 16 November · 1 flight · 1 cancelled |
| Unknown outcomes, one flight (Question 6f of the plan, approved 2026-11-17) | For 1 of these flights, there's no record of how it ended. |
| Empty list | No departures recorded. · No arrivals recorded. |
| A number with its own status | (LH 0691A: cancelled) |

Then departures and arrivals in scheduled order, one row per flight, as built: time, numbers, route, labels, and the notice sentence for a cancelled flight. Each row links to the flight page at its anchor. No change lines here, so day pages stay small. "Unknown" counts the UNKNOWN label only, as before. A count of 0 leaves out its part of the title, or the unknown line (Question 6f of the plan, approved 2026-11-17).

### Cancelled flights (`cancellations.html`)

| Where | Words |
|---|---|
| Title | Cancelled flights |
| Introduction | Every cancelled flight since 27 October, newest first. |
| Under it | "Notice given" is how long before the scheduled time the airport marked the flight cancelled. Airlines may tell passengers sooner. |
| Columns | Date · Flight · Route · Notice given |

Every cancelled flight, newest first, as in the front page's table.

### How this works (`how-it-works.html`)

Plain words, short sections, written to the same reading test; "I" allowed. It opens:

> Ben Gurion Airport publishes its list of departures and arrivals on data.gov.il, the government's open-data site. Since 27 October 2026, a small program I built has checked that list every 2 minutes and saved each new version. From that history, this site works out the chance that a flight is cancelled or delayed an hour or more. It's my own project, not an official airport site, and it isn't live: each page says when it was last updated.

Its first section is "What the numbers mean", the disclaimer every page links to. That text, the outline of the sections after it, and the rules for drafting them are in `docs/flight-lookup.md` ("Words", "Pages"). Sections 2 to 10 are drafted in the build and approved by me at the hand check (my decision, 2026-11-17). The page still carries the full `ATTRIBUTION`, the gaps in the records from the model, and the code link.

### Footer (every page)

Approved by me, 2026-11-17, and built with q27.

| Line | Words |
|---|---|
| First | Flight data: Israel Airports Authority, published on data.gov.il. This site is unofficial: it isn't run by, connected to or approved by the Israel Airports Authority, data.gov.il or the State of Israel. All times are Israel time. |
| Second | The chances on this site are estimates from past flights, not promises. What the numbers mean |
| Links | How this works · Code on GitHub · Built by [owner's wording] |

- The first sentence is `SOURCE_SHORT`, unchanged. The second is `UNOFFICIAL` (both in `src/timeline/words.py`), whose fixed words were "Unofficial; not affiliated with or endorsed by the Israel Airports Authority, data.gov.il or the State of Israel." The denials are the same, in plainer words: "connected to" and "approved by" for "affiliated with" and "endorsed by", and "run by" added. The line answers a licence clause (`docs/terms.md`, clause 8). That clause's line in `docs/terms.md` quotes the line the built site carries.
- "What the numbers mean" links to that section of "How this works".
- The full `ATTRIBUTION` (dataset name and resource ID; `src/model/report.py`, unchanged for the report) stays on "How this works". `timeline.check` requires `SOURCE_SHORT`, `UNOFFICIAL` and, since q27, `ESTIMATES` (the second line's first sentence) on every page, and `ATTRIBUTION` on `how-it-works.html`, so a page built with the earlier unofficial line fails it.
- The built-by text and the GitHub address come from one place, `BUILT_BY` and `CODE_URL` in `words.py`; the upload check still refuses the marker that stood there before I wrote the line.

## Look

### Look A, "Timetable" (decided 2026-11-17, built with q27)

My pick among three looks by a Fable designer (`docs/flight-lookup.md`, D10): a printed timetable. One condensed sans-serif, black ink on white paper, a twelve-column sheet with heavy and hairline rules, and one red that means one thing. The values below are the round-4 mockup's.

- **Typefaces.** IBM Plex Sans Condensed in three weights (Light for the large figures, Regular, SemiBold), and IBM Plex Sans Hebrew Regular for the Hebrew city names. Self-hosted WOFF2 files, cut down to the characters the site prints: 11,484 + 11,440 + 11,468 bytes for the three Latin files and 2,108 for the Hebrew one, 36,500 in all (measured for this update on the mockup's four files). Each Latin file maps 200 characters, the Hebrew file 34, of which 30 are Hebrew. The files carry IBM's copyright and the SIL Open Font License 1.1 notice under family names of their own, "FA Sans Condensed" and "FA Hebrew Sans" (read from the files for this update). The releases are `@ibm/plex-sans-condensed@2.0.0` and `@ibm/plex-sans-hebrew@1.1.0`, both under the SIL Open Font License 1.1 with the Reserved Font Name "Plex". A cut-down file is a Modified Version, which may not take that name as its primary font name, so the files' own family names are required (read at the source during the build: the plan's "Deviations", Task 7). The files carry a link to the licence, not its text, so its text is committed beside them (`src/timeline/static/fonts/LICENSE.txt`) and served beside them (`fonts/LICENSE.txt`; the plan's Question 7, answered 2026-11-17).
- **Loading.** Four `@font-face` rules with `font-display: swap`. The Hebrew face is limited to the Hebrew block (`unicode-range: U+0590-05FF`), so only a page with Hebrew on it fetches that file. Pages preload the Regular and SemiBold files. Nothing comes from another origin. Behind the faces: "Arial Narrow", "Roboto Condensed", "Helvetica Neue", Arial, sans-serif.
- **Black and white, and one red.** Paper #ffffff, ink #111111 (18.88:1), secondary text #595959 (7.00:1 on paper, 6.36:1 on the tint), hairlines #d6d6d6, a tint #f4f4f2 for the row a link points at and a line under the pointer, red #cf2e1e (5.17:1 on paper, 4.69:1 on the tint). The ratios were recomputed for this update with the WCAG 2 formula `tests/test_timeline_style.py` uses. Links are ink with an underline.
- **Red only for "cancelled".** The CANCELLED label, the notice sentence under it, a "Cancelled" line in a list of changes, a cancelled day's mark in the strip, the cancelled part of a day's bar and the total's "cancelled" tile. Nothing else is coloured, and the site's name is no longer red.
- **The sheet.** 1,160 px wide at most, twelve columns with 24 px between them, 40 px side gutters (28 px at 1,040 px and below, 20 px at 760 px and below). A section's heading takes the first three columns and its matter the other nine; on a narrow screen they stack. No cards, no shadows, no rounded corners. Rules do the grouping: 6 px under the top line, 3 px at each section, 2 px under a table's head, hairlines between lines.
- **Type.** Sentences are set as sentences. Capitals with letter spacing stay only on the status labels; column heads, "Updated 3 hours ago", "What changed" and "Pick a day" are ordinary words in the heavier weight. Tabular numbers everywhere. Nothing on a phone is smaller than 13 px.
- **Labels** are capitals with a mark before them, never colour alone: a filled dot for DEPARTED and LANDED, a ring for UPCOMING, a dotted ring for NO NEWS YET, a red square for CANCELLED, a dashed grey square for UNKNOWN, a small diamond for DELAYED.
- **The headline slot.** The two chances side by side on a laptop, stacked on a phone, each the label over its number: the number large in the Light weight, "about" or "under" smaller before it. The "Worked out from" line under them, then a 3 px rule that closes the slot, so whatever fills it later has the same place and the same edges.
- **The strip.** One mark per day: a filled circle for landed or departed, a ring for upcoming, a red square for cancelled, a dashed square for unknown, a dotted ring for no news yet; the day of the month under each mark, the month's name over the first mark of each month. Each mark is a link with a name.
- **"Flights each day"** is a list of links, so a long line wraps on a phone: the date, the counts in text, and a thin bar with the cancelled part as a red block standing on it and the unknown part outlined. The day list under it is set as a calendar, seven days to a row (three on a phone).
- **On a phone.** No sideways scrolling. The cancellations table stacks. A list of changes reads as lines. The top line keeps the site's name and "Tel Aviv airport" on one line with "Updated" under them. The total's three figures shrink with the screen and keep one line at 360 px and wider; narrower, the row wraps (measured with headless Chrome in the build: the plan's "Deviations", Task 13).
- **Keyboard focus** shows a 3 px outline in ink.
- **Dark scheme.** It ships with q27 (my decision, 2026-11-17). The mockups are light only, so its values are derived by the look's rule and shown to me at the hand check: paper and ink swap and the red lightens (the designer's example, #ff6b5a on #121212, is 6.69:1); no colour depends on a light ground. As built: paper #111111, ink #ffffff, secondary text #9e9e9e, hairlines #333333, tint #1e1e1c, red #ff6b5a. The red is 6.75:1 on the paper and 5.97:1 on the tint, the secondary text 7.05:1 and 6.23:1 (the same formula as above).

No framework, no images, nothing loaded from elsewhere, no script but `search.js` (the front page) and `fromhere.js`. Charts are SVG written by Python.

### The look of 2026-11-04, replaced by look A in q27

Restyled 2026-11-04 from the tidy single column of v2 into a data-product look. No sentence, label, number or claim changed; text moved into new layout elements, and counts gained thousands separators.

- **Header band on every page**: a deep blue band with the site's name as a wordmark linking to the front page (on inner pages it replaced the back link "← Cancelled flights at Tel Aviv airport"). On the front page the band holds the title (the page's `<h1>`), the lede and the "Last updated" line.
- **Stat tiles**: the front page's total as up to three tiles, each labelled with the total sentence's own words ("flights with a known outcome", "listed as cancelled", "that's about"; the last, with its range in smaller type right after "1 in N", is left out below the floor), the sentence itself verbatim under them; a day page's count line as tiles ("flights", "cancelled", "unknown", zeros left out as in the line), the line under them. Only numbers already on the page; the cancelled figure takes the cancelled red. Counts carry thousands separators (2,674) in the tiles and the total sentence alike.
- **Layout**: one column, 1000 px wide at most, 24 px side gutters (16 px at 600 px and below); running text keeps to about 46rem. The band and the footer run the full width.
- **Cards**: the tiles, the story box, the cancellations table, the chart, a flight page's rows and a day page's lists sit in cards with a 1 px border and a 10 to 12 px radius, a 1 px shadow in light mode and none in dark.
- **Type**: the system font stack (-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif), tabular numbers everywhere. No framework, no web fonts, no images, nothing loaded from elsewhere, no script but `search.js` (the front page) and `fromhere.js` (a flight page with a block). The chart is SVG written by Python, restyled (in a card) and drawn as before.
- **Colors** as CSS custom properties: a cool grey scale, one accent (a deep blue, for links and the chart's bars) and the label colors (cancelled red, departed and landed green, upcoming grey, delayed amber, unknown a dashed outline). Light by default, a dark set under `prefers-color-scheme: dark`, with an explicit page background. Every text color pair clears 4.5:1 in both schemes (list below, checked by `tests/test_timeline_style.py`).
- **Labels** are small rounded pills with text, never color alone. The chart's accessible name states the counts. Links are underlined (the band's wordmark only under the pointer); keyboard focus shows a 2 px outline.
- **Tables and lists**: a header row on the card color, subtle row lines. A day page sets each flight's time, numbers, route and labels in columns from 760 px up; narrower, the time keeps its column and the rest wraps beside it. Flight numbers never break at their space, in the tables and the day lists.
- **At 390 px**: no sideways scrolling; the cancellations table stacks (flight and date, then route, then warning) rather than scrolling, as v2 settled, and its card scrolls on its own only if something is still too wide; change lines keep their time beside them; the tiles stay in one row.

Text color on background, light scheme then dark (WCAG 2 ratio, 4.5:1 required):

- `--fg` on `--bg`: light #14171c on #ffffff, 17.96:1; dark #e7e9ee on #0e1117, 15.56:1
- `--muted` on `--bg`: light #5a6170 on #ffffff, 6.22:1; dark #9aa3b2 on #0e1117, 7.43:1
- `--accent` on `--bg`: light #1d4ab0 on #ffffff, 7.90:1; dark #8fb5ff on #0e1117, 9.20:1
- `--fg` on `--card`: light #14171c on #f5f7fa, 16.74:1; dark #e7e9ee on #161b24, 14.21:1
- `--muted` on `--card`: light #5a6170 on #f5f7fa, 5.79:1; dark #9aa3b2 on #161b24, 6.79:1
- `--cancel-fg` on `--cancel-bg` (CANCELLED pill): light #b3261e on #fdecea, 5.72:1; dark #ffb3ab on #4d1c18, 8.22:1
- `--ok-fg` on `--ok-bg` (DEPARTED, LANDED): light #1b6e34 on #e6f4ea, 5.56:1; dark #8fd8a2 on #173a24, 7.51:1
- `--plain-fg` on `--plain-bg` (UPCOMING, NO FINAL UPDATE): light #454b57 on #eceef2, 7.54:1; dark #d4d7de on #2a303b, 9.20:1
- `--delay-fg` on `--delay-bg` (DELAYED): light #8a4f00 on #fff1db, 5.89:1; dark #ffcf85 on #3f2c0c, 9.21:1
- `--unknown-fg` on `--bg` (UNKNOWN, a dashed outline pill): light #5a6170 on #ffffff, 6.22:1; dark #9aa3b2 on #0e1117, 7.43:1
- `--accent` on `--card` (the story box's and the footer's links): light #1d4ab0 on #f5f7fa, 7.36:1; dark #8fb5ff on #161b24, 8.40:1
- `--cancel-fg` on `--bg` (warning lines, a cancelled tile's figure): light #b3261e on #ffffff, 6.54:1; dark #ffb3ab on #0e1117, 11.06:1
- `--cancel-fg` on `--card` (a warning line in a flight row a link points to): light #b3261e on #f5f7fa, 6.09:1; dark #ffb3ab on #161b24, 10.10:1
- `--band-fg` on `--band-bg` (the wordmark): light #ffffff on #12306a, 12.68:1; dark #f1f4fa on #0c1a36, 15.67:1
- `--band-muted` on `--band-bg` (the band's lede and last-updated line): light #c5d1ea on #12306a, 8.26:1; dark #aebcd8 on #0c1a36, 9.03:1
- Chart text: as in v2, counts in `--fg`, marks in `--muted`, a focused or pointed-at date in `--accent`, all on `--bg` (the chart's card), and the SVG's own 12 px.

## How it is built

- Same pipeline: `python -m timeline.build --model data/model --out site`, DuckDB over the model's Parquet files, the marker-file swap, `timeline.check` before upload, `scripts/publish.sh`. The pages are pure functions from rows to HTML, in four modules: `words.py` (labels and sentences), `display.py` (a flight's label and DELAYED mark in lists, a cancelled flight's warning number, the front page's figures), `flights.py` (display rows, flights, counts, addresses, search entries) and `views.py` (the HTML).
- Search data: one entry per flight number and direction, with keys from `flights.number_keys` and `flights.place_keys`, the place keys taken as the union over that number's rows (a number can have two cities) and its page address. Written as JSON inside a `<script type="application/json">` element on the front page, with `<` escaped as `\u003c` so a name containing `</script>` cannot end the element.
- Page addresses unique per file, and the build stops if two flight numbers would map to the same file (`AB` + `12` against `A` + `B12`). Anchors unique per page (codeshare partners share anchor strings across pages, which is fine).
- Same model, same bytes (determinism across processes, as now). The build time is the last sighting of the board (`confirmed_until` of the last snapshot), never the clock.
- Cost: no new AWS service. Hosting as estimated in `docs/publishing.md`, "Cost (monthly)": storage well under a cent a month for the 3.9 MB site of 2026-10-30, and about half a cent of requests per upload, since each upload sends every file (961 that day).

What q27 adds (built):

- **Font files.** The four `.woff2` files and their licence live in `src/timeline/static/fonts/`, and the build writes them byte for byte into the site's `fonts/` folder, beside the style sheet, which names them in its `@font-face` rules. They are committed as they stand: cutting them down again needs a font tool that the build does not depend on.
- **Upload.** `scripts/publish.sh` uploads by an allowlist, one `aws s3 sync` per file type with its content type set, not guessed, because the responses send `nosniff`: before q27, `*.html`, `*.css` and `*.js`. The font files need a fourth, `*.woff2` as `font/woff2`, the type the mockups' preload tags name, and their licence a fifth, `*.txt` as `text/plain; charset=utf-8`. `tests/test_publish.py` and step 5 of `docs/publishing.md` follow.
- **The upload check** reads text. Its `SCANNED` set stays `.html`, `.css` and `.js`, although the upload then sends two more types; the font files and their licence are pinned by tests instead ("Tests and checks").
- **The scripts.** `search.js` writes the two new search lines. `fromhere.js` moves the next day ahead to the top and writes "Updated N hours ago", and works both out again each time the page is shown again (`docs/flight-lookup.md`, "Pages").
- **`docs/terms.md`.** My reading for these pages is already there (2026-11-17, its clause 4 paragraph). Two of its lines follow the build: the clause 8 line, which quotes `UNOFFICIAL`, and the end of the clause 4 paragraph, which describes the upload check's rules as they stand.
- **Cost.** No new AWS service. Each upload sends five more files, the four fonts and their licence: five more PUT requests at $0.0055 per 1,000, about $0.00003, and 40,956 bytes more storage (`docs/publishing.md`, "Cost (monthly)"; prices not re-read for this update). An upload stays about half a cent. The mockup pages weigh about what the built ones do: the front page 146,117 bytes against 147,000 in the v2 build of 2026-11-17 and 146,420 in the q27 build of 2026-11-18, the style sheet 22,787 against 14,203 and 27,668 (measured for this update).

## Tests and checks

Kept from v1, rewritten to the new words: every `flights` row on exactly one flight page and on one day page (the day of `sched_local_final`, including a retime across midnight); anchors and addresses stable and unique, the build stops on a collision; HTML escaping (a city named `<script>` stays text); Israel time across the October clock change, run under an Israeli time zone; a NULL final scheduled time stops the build; `--out` without the marker refused; determinism across `PYTHONHASHSEED`; `noindex` on every page.

Retired: the full `ATTRIBUTION` on every page (now `SOURCE_SHORT` and `UNOFFICIAL` everywhere, `ATTRIBUTION` on how-it-works); counts as flight numbers (now flights as defined above); a Hebrew status word with `lang="he"` (now the Hebrew city with `lang="he" dir="rtl"`); "listed together" and "flight numbers listed" (now "Probably the same flight as" and flights); every v1 exact sentence; the codeshare split on label, DELAYED or warning (rules C1 to C4 of `docs/flight-lookup.md` replace it); the headline tests (the 1-in-N rounding with its tie, left out at 0), replaced by the total's tests below.

New, each with a `scripts/mutation_check.py` entry:

- one exact-text test per warning rule 1 to 11, including the 0 and 60 boundaries and a 42-hour censored bracket (LY 5409's shape);
- one per label row; NO FINAL UPDATE decided in UTC (a test run under Asia/Jerusalem with a flight at 23:55 Israel time and a last record at 22:02 UTC); DELAYED from the row's own records; "last expected" and the delay sentence; `uncanceled` NULL as false and both changed-back lines;
- "What changed": the gap line from `prev_observed_at`; the cancellation as a range;
- the total's tiles and sentence (`tests/test_timeline_views.py`) and the rounding, range and floor behind them (`tests/test_rates.py`, `tests/test_timeline_words.py`; `docs/flight-lookup.md`, "Tests and checks");
- the chart's counts equal the day pages'; today, ahead and incomplete days; every day linked;
- the featured-flight rule; the recent-cancellations order and the cap of 10;
- a number with two cities (title without a city, rows with theirs); two rows of one number on one day (two anchors, links carry them);
- search: the order, the cap and the "N more" line; the union of keys; a name containing `</script>`, a quote and a backtick stays inside the JSON (run under Node, as the current search test);
- `timeline.check`: "we", "our", "us" as whole words, case-insensitive, on every page; "I" as a whole word outside `how-it-works.html` and the built-by line; "board", "snapshot", "stored", "observed", "receipt" as whole words on every page except `how-it-works.html`; "minutes late" and "hours late"; the existing banned phrases kept; the built-by marker refused. A test that "were", "hours", "status", "BUS", "AUSTRIAN AIRLINES" and "at least 23 hours" pass, and a mutation that turns the word match back into a substring match so that test fails.

What q27 changes (built). The lists above describe the tests as they stand; each sentence, label and rule that changes takes its exact-text test and its mutation entry with it.

- **The no-font rule.** `tests/test_timeline_style.py` (`test_nothing_loaded_from_elsewhere`, which the build replaced with `test_fonts_load_only_from_the_sites_own_folder`) refused `@import`, `url(` and `font-face` anywhere in the sheet. New rule: `@import` is still refused; a `url(` may stand only inside an `@font-face` rule and must name a `.woff2` file of the site's own fonts folder that exists among the static files; no address with a scheme or a host, no `data:` address, no image. Mutations: a sheet that names a font on another host, and one that names an image, must fail.
- **The font files**: their four names, sizes and SHA-256 pinned, and the licence's, so a changed or missing file fails a test and not an upload.
- **The style tests for the built look** are rewritten for look A: the colour tokens and the text pairs that must clear 4.5:1, in the light scheme and in the dark one; a mark for every label, NO NEWS YET included; the header band's test goes with the band; the from-here table no longer stacks on a phone.
- **One exact-text test** per label line, per notice rule 1 to 11 in both its forms, for "First on the list at", for each title form (one, two, three and five cities; a cut-short second spelling; an arrival), for "Also sold as" with one and with two numbers, for the footer's three lines, the page description and each page's lines in "Pages".
- **The flight page's order**: the nearest day ahead at the top, once; the strip; later days ahead soonest first; past days newest first; the two once-a-page notes in their places.
- **Search** (run under Node): the "more" line, the "No flight found" line, and titles in the new form.
- **The lines and rules of my answer of 2026-11-17**: the first line's forms (a time; a date; "Already on the list" for a first record in the records' first list or the first after a gap; "already cancelled"); a past day's time line, the same time twice included; DELAYED at 59 and at 60 minutes; "Updated" on every page; the line that stands in the search box's place without scripts; the story picker skipping a flight first listed after its own scheduled time; each page's browser-tab title.
- **Publish**: five uploads, each with its content type (`tests/test_publish.py`).
- **Retired** with the words they tested: "(as the airport lists it)", "last expected", the 2026-10-30 warning texts, the built-by line above the footer, the header band.
- **The upload check's rules**: `docs/flight-lookup.md`, "Tests and checks".

## Left to the builder

Markup and CSS; exact colors and spacing within the look rules; the chart's drawing; how "Show details" looks; section order on "How this works"; anything marked "provisional" that turns out awkward in code, as long as the words and rules hold.

For q27:

- The dark scheme's values, within the look's rule (paper and ink swapped, a lighter red) and the 4.5:1 test in both schemes. No mockup shows it; it shipped with q27, and I looked at it at the hand check (2026-11-17).
- The day page, the cancelled-flights page and "How this works" in look A. The mockups show the front page and three flight pages only; the other pages take the same parts (the top line, sections under a heavy rule, tables, labels).
- Where the font files sit in the built site, how long a browser may keep them, and whether the licence text is committed beside them (it is: `src/timeline/static/fonts/LICENSE.txt`).
- How the search label and hint hide with the box when scripts are off. The mockups use one style rule (`:has()`); a wrapper that the script shows is sturdier.
- How a second spelling of one city is folded into a title (the mockups: a name that is the beginning of another is named once).
- Whether a title is marked whole as the airport's data. The upload check's word rules skip such spans, and the title now holds the site's own words ("to", "or", "other cities").
- Dates: written out on a flight page and a day page ("Tuesday 17 November"), short in lists ("Tue 17 Nov"), as on the mockups.
- Which first records read "Already on the list". Recommended: a first record in the records' first list, or in the first list after a gap that the model marks.

## Outside this design, for me

The questions this section held, from 2026-10-30 and from the q27 update, are settled (`docs/flight-lookup.md`, D13). What is left is mine to do:

- Done at the hand check during the build, 2026-11-17 (the plan's "Deviations", Task 15): I looked at the built pages at phone width and on a desktop, light and dark, and approved the list of spoken names and the text of "How this works", sections 2 to 10.
- Freshness: the scheduled rebuild comes next after q27 (q5, then q2 and q23). Until then every page says how old it is.
- The link-preview image (q17) waits for the new look, and `noindex` stays until the launch decision.
- The five outsider sessions (q13), on the script I approved on 2026-11-17 (`docs/flight-lookup.md`, "Five outsiders").

Settled on 2026-11-17: the dark scheme ships with q27; the round-4 mockups stay out of the repository; the typeface's release and licence are read at their source, as a task of the plan; `docs/publishing.md`, `README.md` and `docs/README.md` are brought up by one docs task at the plan's end.

## Unverified

- Settled by the first upload (2026-11-18): a page served through the site's CloudFront distribution loads its font files from its own address. The live `.woff2` files come back with the content type `font/woff2` and are byte-identical to the build, and a headless Chrome render of the live BZ 317 page (the README's screenshot) differs visibly from a local render of the same page with the font files removed, which falls back to the stack's next typeface.
- How look A reads on Windows and Android when the font files fail to load: the designer rendered the fallback on a Mac only.
- The page weights and first-screen measurements of the mockups are the designer's, apart from the file sizes named above.

## Review (2026-10-30)

Builder check (Opus; Fable was over its limit): five points, all folded in (footer vs the word check, codeshares per day, the changed-back wording, names, anchors).

Outside review (reviewer chosen by me; full text in commit f360540): 0 critical, 13 significant, 11 minor, 8 nits, 11 direction findings. Facts checked against the model before folding in (190 of 370 flights on 28 October without a known outcome; 9 open flights before the last record; 4 numbers with two cities; 13 numbers twice on one day; LY 5409's 76-minute to 43-hour bracket; README's old wording).

Folded in: every significant and minor finding, and the nits, except as follows.
- Headline denominator: kept at 951 (all days). The reviewer read "since 27 October" as excluding 26 October's flights; those were recorded from 27 October on, and the lede now says "kept since 27 October".
- "Final" and "not final": the reviewer's gloss is a guess; the site quotes the airport's words and says they are undefined.
- Warning wording uses hours only (no days), so ranges never mix units.

Direction, with my decisions of 2026-10-30:
- D3 (lead with one flight's changes instead of cancellations): I kept cancellations as the lead; D9's point is taken by putting one flight's full story directly under the headline.
- D7 ("I" on How this works): adopted by me, with the built-by line.
- D5 (launch gate): I dropped "first cancellation-warning figures" from the launch gate; launch once the site is live and this redesign is done. Hosting was then still waiting on AWS account verification (q15), so building this does not delay it.
- D1, D6, D11: adopted as the code link and built-by line on the front page and the preview title and description; the name is mine to write. The full page set stays (D6 agrees it is cheap).
- D4: the delay sentence adopted. Settling "expected time" by my own observation at the airport is not adopted: one flight settles nothing.
- D2: my premise stays; the success question for observed sessions moves to q13 (D10).
- D8: adopted (published names with a note, unknown counts on the chart, NO FINAL UPDATE, the Hebrew city with `lang`).

## Deviations

Contrast (Task 9, `src/timeline/static/style.css`; checked by `tests/test_timeline_style.py`, WCAG 2 ratio, 4.5:1 required). The v2 build's values; the 2026-11-04 restyle changed most of them, and the current list is in "Look". Text color on background, light scheme then dark:

- `--fg` on `--bg`: light #18181a on #ffffff, 17.73:1; dark #ececee on #151517, 15.46:1
- `--muted` on `--bg`: light #6b6b70 on #ffffff, 5.30:1; dark #a3a3a8 on #151517, 7.26:1
- `--accent` on `--bg`: light #0a66c2 on #ffffff, 5.69:1; dark #7ab8ff on #151517, 8.80:1
- `--fg` on `--card`: light #18181a on #f4f4f6, 16.14:1; dark #ececee on #232327, 13.27:1
- `--muted` on `--card`: light #6b6b70 on #f4f4f6, 4.83:1; dark #a3a3a8 on #232327, 6.23:1
- `--cancel-fg` on `--cancel-bg` (CANCELLED pill): light #b3261e on #fdecea, 5.72:1; dark #ffb3ab on #4d1c18, 8.22:1
- `--ok-fg` on `--ok-bg` (DEPARTED, LANDED): light #1b6e34 on #e6f4ea, 5.56:1; dark #8fd8a2 on #173a24, 7.51:1
- `--plain-fg` on `--plain-bg` (UPCOMING, NO FINAL UPDATE): light #4a4a4f on #ececf0, 7.48:1; dark #d4d4da on #303035, 8.89:1
- `--delay-fg` on `--delay-bg` (DELAYED): light #8a4f00 on #fff1db, 5.89:1; dark #ffcf85 on #3f2c0c, 9.21:1
- `--unknown-fg` on `--bg` (UNKNOWN, a dashed outline pill): light #6b6b70 on #ffffff, 5.30:1; dark #a3a3a8 on #151517, 7.26:1
- `--accent` on `--card` (the story box's link; added to the brief's ten): light #0a66c2 on #f4f4f6, 5.18:1; dark #7ab8ff on #232327, 7.55:1
- `--cancel-fg` on `--bg` (the warning lines; added): light #b3261e on #ffffff, 6.54:1; dark #ffb3ab on #151517, 10.67:1
- Chart text: counts in `--fg`, the "today", "ahead" and "incomplete" marks in `--muted`, a date under the pointer or keyboard focus in `--accent`, all on `--bg`, so the first three lines cover it; the test fails if any chart text fill is another token. The SVG's `font-size="12"` is left alone (no CSS font rule on the chart).

Other look calls (Task 9):

- The mockup's red pill (#d1352b on #fdecea, 4.32:1) fails the bar and was darkened as above. Its grey (#6e6e73) passes on the story box at 4.66:1; it was darkened slightly too, for margin.
- On a phone (600 px and below) each cancellations-table entry stacks as flight and date, then route, then warning; the column headings are hidden there, so the sheet writes a muted "Warning: " before the warning text.
- Pale chart bars (40% opacity): days "ahead" and "incomplete" days. "Today" is drawn like past days.

Building (Tasks 1 to 10 of the plan), where the code settles or changes what the sections above say:

- **`pages.py` became three modules**: `words.py`, `flights.py` and `views.py` (see "How it is built"); the references above follow.
- **"What changed" examples follow the code**: a date only where it differs from the row's day, the retime line, the earliest line's fields, "already cancelled", and the "no …" forms for an emptied field.
- **A warning beside a label is always a sentence** ("Warning: at least 23 hours."), on day pages and flight rows. The bare text ("at least 23 hours") appears only in the Warning column of the cancellations tables, whose previous cell ends with a scheduled time: the upload check reads a page as flat text across tags, so "CANCELLED" followed by "at least 23 hours" would read as the banned "cancelled at".
- **"Unknown" on the chart and the day pages counts the UNKNOWN label only.** NO FINAL UPDATE flights are pending, not lost, and sit in "the rest".
- **The upload check's word rules skip the airport's data**: the contents of `<span class="d">` (`views.d()`), the front page's search JSON and each page's `<title>`; the phrase rules still read everything. Plurals ("boards", "snapshots", "receipts") count as data-collection words. Check-in desks, zone and terminal are escaped but not marked as data, so a zone named "I" would stop an upload, loudly; the 2026-10-30 model's zones are A, B, C, D and G.
- **Addresses are compared ignoring case**: the build also stops when two numbers' page addresses differ only in case, because my Mac's disk would write both to one file.
- **Titles**: a two-city arrival reads "LY 5116, to Tel Aviv"; the front page's story box names its own row's city even for a two-city number, since it shows one flight on one day.

## Deferred review findings (2026-10-30)

Minor findings from the ten task reviews and the final review that the final review judged safe to leave; none blocks launch.

- Tests: the featured() docstring says a missing censored flag counts as censored (only None does); the time-zone fixture is imported from a sibling test module (conftest.py would be cleaner); the style test guards one exact selector, so a broader `nowrap` rule would pass; the contrast test checks token pairs, not the rules that use them; items with tests but no mutation entry: the flight-cell wrap, the description's full stop, link integrity.
- Code: search.js puts its functions on the page's global scope and throws (harmlessly, box stays hidden) on malformed search data; `load()` reads seven observation columns the pages no longer use; the day-page address is formatted in three places (the link test pins it); the CLI prints 3,125 table rows as "flight numbers".
- Check: the word rules do not read attribute text (meta description, aria-label, placeholder); the `<title>` mask would also skip a future SVG `<title>`; "hours late" also matches "hours later" (fails loudly).
- Docs: README.md described v1's layout and gave the dated 289 tests / 156 mutations; both refreshed on 2026-11-01 (q17).

