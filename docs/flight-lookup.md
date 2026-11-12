# Flight lookup: the front page leads with "from here" (q21)

Grade: production-lean, the site's grade (`docs/site-redesign.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript. The design assumes it. The owner confirms it (decision D1).

Cost: nothing new on AWS, so $0 a month added. Version 1 is built by the existing local build and published by the existing hand upload, which costs about half a cent an upload (`docs/publishing.md`, "Cost (monthly)": $0.0055 per 1,000 PUT requests, AWS Price List API, il-central-1, read 2026-10-29; not re-read for this design). Nothing here needs a schedule, a function or a bucket.

Status: design v3, 2026-11-12. Written by a Fable agent after a blind-spot pass on the same data, then revised after two reviews ("Review" at the end). The owner skipped the design questions, so every call that is the owner's is listed first, each with a recommendation. Calls the design made on its own are marked "(designer's call)". Approved by me, 2026-11-12, with D1 to D9 as recommended. No code and no plan yet.

Figures: every figure comes from a query run for this document on the model built 2026-11-12 from lists up to 2026-11-12 10:16:45Z. The queries and their results are in [flight-lookup-figures.md](flight-lookup-figures.md), cited as (A1), (A2) and so on.

What it changes in `docs/site-redesign.md`. Everything not listed there stands.
- "Who is a flight": replaced by rules C1 to C4.
- "Labels": a flight in a list gets its label by C10. A number's own label on its own page is unchanged.
- "Warning": in a list, a cancelled flight shows the warning of its number that was listed as cancelled first (C9).
- "Codeshares": the sentence stays. Its partners are the other numbers of the flight under C1 (`partners()` in `src/timeline/flights.py`), with the reason words in "Words".
- Front page: the headline counts closed flights and carries a range; the search box moves up; the new block follows it. The story box picks among flights labelled CANCELLED by C10 and shows the number of C9. Today `featured` in `flights.py` picks by a number's own label, which could feature a number listed as cancelled inside a flight that departed.
- The "1 in N" rounding gains steps above 100 (C8).
- "Look": two scripts, `search.js` and `fromhere.js`.
- Tests: the codeshare-split test is retired with the split it tested; the headline tests are rewritten.
- The non-goal "Cancellation odds or forecasts": replaced by "The gate".

## Decisions for the owner

Each is the owner's because it changes what gets built or what the public sees. I approved all nine as recommended, 2026-11-12.

**D1. Grade.** Recommendation: production-lean, as the rest of the site. Alternative: a quick prototype with fewer tests. The public sees the same pages either way; the difference is how sure anyone can be that the figures are counted as the page says.

**D2. What the front page leads with before the gate.** Recommendation: a record, by time to go, of how often a flight still listed normally was later listed as cancelled, with a range on every figure and a line saying it is the past and not a promise ("Pages"). No figure for one flight. Whether this lead is enough to end the launch hold is the owner's call; the design's view is that it is. Alternatives:
- Keep today's headline until the gate. The public sees a total and nothing to act on, for at least 60 days of counting.
- Show a per-flight figure now. It would rest on 1 to 11 cancelled flights per sign (A25). Not recommended.

**D3. The gate, and a pass mark the recorded method does not set.** The owner's decision of 2026-11-05 says every signal "is fixed in advance and measured before use (its lift with an interval, the model's score with and without it), then re-tested on later months held out". It names two measurements and gives neither a pass mark. Recommendation:
- The count: 200 cancelled flights in the 24-hour row, over at least 60 days, among flights first listed after the counting start.
- The lift gets the pass mark: its range must lie wholly above 1 ("Signs").
- The score with and without the sign is measured on the same flights and published beside the result. It is not a pass mark.
- The re-test is the same test on later flights. A sign that fails it loses its place.

This changes the recorded method in one way: it makes the lift the judge and the score a report. The reason is how often each would pass for a sign that is real, in a simulation of a 24-hour row with 200 cancelled flights (A31):

| A real sign that shows on | at this many times the rate | The lift's test passes | A score pass mark would pass |
|---|---|---|---|
| 1 flight in 100 | 10 | 97% | 30% |
| 1 flight in 100 | 5 | 49% | 12% |
| 14 flights in 100 | 3 | 100% | 46% |
| 14 flights in 100 | 2 | 92% | 26% |
| 14 flights in 100, more often where the rate is high | 2 | 100% | 99% |

The score pass mark here is the first draft's: the split's Brier score better than the table's by two standard errors, with the true rates known in advance, which is its best case. Alternatives:
- Give the score that pass mark too, at 200. For four of the five signs above it would pass in 12% to 46% of rows, so a real sign would more often be turned away than shown.
- Both pass marks at 400 in the row, about 111 days at today's pace. The score's then passes in 30% to 89% for those four, and the lift's in 99% to 100% (A31). The public waits about twice as long.
- 75 in the row over 30 days. The lift's test then passes in 23%, 1%, 94% and 55% for those four (A31): sooner, but blind to a rare sign.

**D4. One counting method for the whole site.** Recommendation: rules C1 to C10. Numbers at the same time and airport are one flight when the list shows them as one (same expected time, terminal and check-in desks), or when one of them did not depart or land and shares the other's airline or desks. A flight is cancelled only when none of its numbers departed or landed. What the public sees change:
- The total moves from 106 of 5,367 flights, about 1 in 50 (A36), to 81 of 4,658, about 1 in 60 (A2, A35).
- 16 numbers listed as cancelled sit inside 14 flights that departed or landed, 12 of them closed (A13). They leave the cancellation lists, are named in their flight's row, and keep CANCELLED on their own pages. Where such a pair was really two aircraft, a cancellation goes unlisted and uncounted.
- A number of another airline at other desks stays a flight of its own: IZ 991, listed as cancelled, is not folded into LY 003, which departed (A11).
- Among numbers that departed or landed, the grouping is exactly the model's own (A10), so "Probably the same flight as" names the same partners as today.
- Day counts and the chart follow.

Alternatives: count by direction, airport and scheduled time alone (76 of 4,614, A9; it folds IZ 991 into LY 003's flight, and ENT 229 and ENT 359, at different desks, into one). Or use the new method on the new block only, and show two different totals on one page.

**D5. Start the record by freezing the signs, their test and the gate, as code.** Recommendation: tag the first commit in which the counting rules, the four signs, the sign test and the gate run from the model as tested code, with the counting start written into it, and push the tag (the owner's go). Nothing is frozen before that code exists ("The record"). Alternatives:
- Tag this document now. Its SQL is prose, so the frozen rule would not be exact.
- Wait for a scheduled job that writes each day's figures to write-once storage. That needs q5 and q2 first, and the days until then are not counted.

The public sees nothing different until the gate. The difference is how soon it can open.

**D6. If the count is reached and no sign passes.** Recommendation: say so on "How this works", with the figures. Alternative: say nothing. A test that came out empty is still a finding, and silence would look like the test was never run.

**D7. The new words.** The sentences in "Words" are new. I approved them with this design, 2026-11-12; the site's earlier words were approved on 2026-10-30.

**D8. The browse view waits.** Recommendation: not built in version 1. Sorting by risk needs a per-flight figure, and filters alone repeat what the day pages and the search already do. Alternative: build filters by airline, destination, terminal and day now, with no risk column.

**D9. The stop rule for the five sessions (q13).** Recommendation: if two or more of five outsiders read the rate as a promise about their own flight, the words change before launch or the table moves below the total. Whether anyone names a use is a probe, not a stop. Alternative: the rule in `docs/timeline.md`, which stops product work when fewer than two of five name a real use. `docs/site-redesign.md` records a review's proposal to drop that rule and leaves it open.

## Why

My direction, 2026-11-05: the front page and the flight pages lead with a lookup. A traveller finds their flight and sees the chance it will be listed as cancelled between now and departure, as a range beside a typical flight at the same point, with tested signs, a browse view and a published accuracy record. I am holding the launch until the front page leads with something a traveller can act on. Today it leads with a total, which nobody can act on.

A blind-spot pass on 2026-11-12 found what stands in the way: a hand-uploaded site has no "now", no evidence gate had been chosen, the counting unit moves the total by a third (A9), and two weeks hold too few cancelled flights to tell one flight from another (A25). This design delivers the part of the direction the data supports today: the typical flight at the same point, as a range, with the traveller's own clock supplying "now". It fixes in advance how signs are tested.

What a traveller can act on in version 1:

- How much a normal listing means at each point in the last three days. With 70 hours to go, about 1 in 65 flights still listed normally were later listed as cancelled; with 3 hours to go, about 1 in 230 (A6, A35).
- When to look again. Listings change late: at least 9 of the 81 cancelled flights were listed as cancelled only after their scheduled time (A17).
- Their own flight number's record, which the flight page already shows.

## What the list can and cannot show

Measured on this model. These facts shape the rules below.

- A flight is on the airport's list only for its last three days. A number first appears a median 71.9 hours before its scheduled time and never more than 72.0 (A18).
- A flight already listed as cancelled when it reaches the list is almost never seen: 2 of 7,092 numbers first listed on time (A19). Every figure here is about a late listing, for a flight that reached the list normally.
- A departed or landed number leaves the list about a day after its time: a median of about 24 hours, 43.3 at the most. A cancelled number has left as early as 54.6 hours before its time and as late as 51.4 after (A18).
- 29 flights left the list with no final status, 27 of them before their scheduled time (A3). The list does not say whether they were cancelled.
- The record has one hole, 42 hours long, from 27 to 29 October 2026 (A30). 240 flights left the list during it (A3).
- The record holds no bad day. From 30 October to 9 November the busiest day had 10 cancelled flights and the quietest 1 (A23). A storm, a strike or a security closure is when a traveller most wants this page, and it is when these figures are most wrong.

## Goals

- A traveller with a flight in the next three days learns, in a few seconds, how often a flight in the same position was later listed as cancelled, and how firm that figure is.
- Every rate on the site is counted one way, written down as rules a reader can run.
- Every rate carries a range that allows for cancellations coming in runs.
- The page stays true between hand uploads.
- The test a sign must pass is fixed, as code, before any flight it will be scored on is listed.

## Non-goals

- A figure for one flight, or a sign applied to a flight. Four candidate signs are defined and tested unpublished. "How this works" names them; no page shows one against a flight, or its figures, before it passes.
- Three parts of the 2026-11-05 direction, each for a stated reason:
  - Reschedule odds, earlier or later. The model's retime rule (R4) is still marked UNSURE in `docs/data-model.md`, and 43 of 7,657 numbers had their time changed while listed (A22).
  - How far ahead each airline's cancellations show. No airline has enough: the largest group on the 24-hour row holds 8 cancelled flights (A8). The list also names no operator, so "this airline" would be a guess.
  - "Is today unusual", for the airport or an airline. The record holds no unusual day to measure against (A23), and the answer needs the list as it is now, which a hand-uploaded site does not have. Sign S3 is the airline half of this idea, under test.
- A browse view (D8), airline or route comparisons, a table by direction.
- Delay figures of any kind: what the airport's expected time measures is still unknown (q3).
- Live data, a scheduled rebuild (q5, q2, q23), new file types.

## Anti-goals (a failure even if it works)

- A reader taking a rate as a promise about their flight. The words stay in the past tense, and q13 tests for this misreading.
- A rate with no range, anywhere on the site.
- A rate drawn from one flight number's own record. That record is a median of 6 flights long (A21), and none cancelled in 6 cannot tell "never" from "1 in 3" (the usual 95% bound for none in six is 39%). It stays counts only.
- A figure that silently means something else when the upload is old.
- Everything `docs/site-redesign.md` already lists: collection words on reader pages, "we", overclaiming, looking official.

## Counting method

Rules C1 to C10. "Number" means one airline flight number on one scheduled day, a row of the model's `flights` table. "Slot" means one direction, airport and scheduled time. The figures file's setup (A0) is rules C1 to C8 in SQL; C9 and C10 are display rules.

**C1. A flight.** Two numbers in one slot are the same flight when either of these holds, read at each number's last listing:
- They show the same expected time, terminal and check-in desks. This is the model's own codeshare key (R5, `docs/data-model.md`) and the site's reason for "Probably the same flight".
- At least one of them did not depart or land, and they have the same airline or the same desks. Such a number is read as a second listing of its airline's flight, or as a partner at the same desks that was listed as cancelled alone.

Two terminals, or two different desk ranges, never tie. Ties chain: if A is tied to B and B to C, the three are one flight. A chain never joins two numbers that both departed or landed unless they share expected time, terminal and desks; if it would, the numbers that did not depart or land stand alone. No chain has needed that yet (A12). (designer's call)

What the rule does, on closed flights:
- Among numbers that departed or landed it is R5 exactly: no flight holds two R5 groups and no R5 group is split (A10). The expected time is what separates two aircraft at the same desks. Of 4,315 pairs that both departed or landed from one slot, terminal and desks, 4,292 show the same minute and 23 do not (A10b).
- It splits 48 slots (A10). EY 596 and EY 610, each with its own partner, are two flights. So are ENT 229 and ENT 359 at two desk ranges, the two pairs to KRK at desks 38-41 and 78-99, and 6H 570 and BZ 701, whose last expected times were 99 minutes apart (A11b).
- A second listing by the same airline joins the first: OS 1083, listed as cancelled, beside OS 083, which landed.
- Another airline's number at other desks, or at none, is its own flight. IZ 991, listed as cancelled with desks 34-41, is not folded into LY 003, DL 7426 and AM 7895, which departed from desks 78-99 (A11).

What it cannot tell, with counts:
- A number that did not fly is joined to its airline's or its desks' flight on a reading, not on the list's word. 14 numbers listed as cancelled sit inside 12 closed flights that departed or landed (A13). Where such a pair was two aircraft, a cancellation goes uncounted.
- It cannot tell a mis-keyed second listing from another airline's flight. ASY 991 beside IZ 991, and UN WZ932 beside WZ 932, count as cancelled flights of their own (A11). That they are mis-keyed is this design's reading: UNVERIFIED.
- LH 0683A, listed as cancelled at desks 28-33, beside LH 685 at desks 34-45, which left the list with no final status, are two flights: one cancelled, one unknown (A11).
- If one aircraft's partners ever showed expected times a minute apart they would count twice. The list cannot confirm that the 23 pairs above are separate aircraft.

Measured the other ways, on the same closed flights (A9): 109 of 7,244 per flight number (1 in 66); 95 of 4,671 per R5 group (1 in 49); 76 of 4,614 by slot alone (1 in 61); 81 of 4,658 by this rule (1 in 58). All sit inside the total's range.

**C2. A flight's result.** Operated, when any of its numbers departed or landed. Cancelled, when none did and at least one ended listed as cancelled. Unknown otherwise. So a number listed as cancelled inside a flight that operated is not a cancelled flight: OS 1083 on four days, LH 0691A on two (A14). The count can be off either way: beside the cases under C1, 1 of the 81 cancelled flights holds a second number that left the list with no final status (A15).

**C3. The last status counts.** A number listed as cancelled and later changed back counts as what it ended as; 7 numbers so far (A16). A flight cancelled, changed back and cancelled again is one cancelled flight. A number with a letter in it (LH 0691A) counts like any other. A number listed as cancelled on several days is a flight on each day: 10 numbers so far, one of them on four days (A16). The range (C8) is what allows for such runs.

**C4. Only closed flights make a rate.** A flight is closed 48 hours after its scheduled time. That is longer than any departed or landed number has stayed on the list (43.3 hours, A18), so every flight of the same hour enters the count together, whatever its result. Flights with an unknown result are left out of every rate and shown as a count beside it: 269 so far, 240 that left during the hole and 29 that left with no final status (A3). If all 29 were cancellations the total would be 110 of 4,687, about 1 in 43, where the method gives 1 in 57.5 (A4). There is no window: the record runs from the first list in the archive. (designer's call)

**C5. Checkpoints.** Six points before the scheduled time: 70, 48, 24, 12, 6 and 3 hours. A row is named by its point ("with 24 hours to go"), never as a stretch, so nobody reads it as "cancelled during these hours". The first is at 70 hours, not 72, so that every flight listed on time is in it. (designer's call)

**C6. Who is in a row, and the clock.** A flight is in a row when one of its numbers was on the list exactly that many hours before the scheduled time the list showed at that moment, with a status other than cancelled.
- "Listed normally" therefore means any status but cancelled, DELAYED included.
- The clock is the time shown then, not the final one, because that is the only clock a traveller has; 43 of 7,657 numbers had their time changed while listed (A22). If a number passed the same point twice, the first passing counts.
- A number first listed with less time left is not in that row. A flight already listed as cancelled when first seen is in the total and in no row.
- A moment inside the hole is not a checkpoint: nobody knows what the list showed.
- A known limit: the model records changes, not absences. 7 of 10,023 numbers were missing from 6 to 106 lists between their first and last sighting, and count as listed throughout (A20).

**C7. "Later listed as cancelled".** A flight in a row counts when its result is cancelled (C2), however late the listing came, the time after the scheduled time included.

**C8. The range, the floor and the rounding.** (designer's call)
- The rate is cancelled flights over flights. Its range is two standard errors either side on the log-odds scale, so it never falls below zero. A standard error is the usual measure of how far a rate would wander by luck.
- The standard error is not the textbook one, which treats each flight as its own coin toss. Flights are grouped twice: by airline and week (weeks start on Sunday, as in Israel), and by Israel day. Each grouping treats a group as one draw. The larger standard error is used. The first allows for an airline's run of cancellations, the second for a bad day. On the 24-hour row the airline-and-week figure is 2.07 times the textbook one (A6).
- In symbols, for G groups, group g holding k_g cancelled of n_g flights, N flights in all and r the overall rate: se = sqrt(G / (G - 1) x sum over g of (k_g - r x n_g) squared) / N. The ends are the rate's log-odds plus and minus 2 x se / (r x (1 - r)), turned back into rates.
- A flight's airline, for this grouping only, is that of its number with the lowest numeric part, the alphabetically first airline on a tie. It is never shown and claims nothing about who operates the flight.
- Groups whose number grows with time were chosen on purpose. Grouping by airline alone gives a range that never narrows, because airlines differ for good.
- The floor: a rate and its range are shown only when they rest on at least 10 cancelled flights, from at least 5 airlines and at least 5 days. Below that the page shows the two counts and "too few so far to say".
- Rounding. "1 in N" uses steps of 1 below 20, 5 from 20 to 99, 10 from 100 to 999 and 100 above. The middle figure goes to the nearest step, halves up. The ends of the range are rounded outward, so the printed range is never narrower than the computed one.

**C9. A cancelled flight's warning.** In a list of flights it is the warning of the number whose cancelled listing came first, as the existing rule takes the first cancellation. On a number's own page it is that number's own.

**C10. A flight's label in lists.** The first of these that applies:
1. DEPARTED or LANDED, when any of its numbers departed or landed.
2. UPCOMING, or NO FINAL UPDATE once the scheduled time has passed, while any of its numbers is still listed with a status other than cancelled.
3. CANCELLED, when a number is, or ended, listed as cancelled. By then no number is listed otherwise: the flight is listed as cancelled as a whole.
4. UNKNOWN.

DELAYED is added when any number showed it. Day counts, the chart and the cancellation lists count flights with these labels. A number's own page keeps that number's own label. Rule 2 before rule 3 matters: 13 closed flights had one number showing cancelled while another was still listed and yet to depart or land, for 11.5 to 72 hours, and 12 of them then departed or landed (A24).

### The figures under the method

All closed flights in the record, scheduled 26 October to 10 November 2026 (A5).

The total: 81 of 4,658 flights with a known result were listed as cancelled, 1 in 57.5, range 1 in 36.3 to 1 in 91.6 (A2). Shown as "about 1 in 60 (between 1 in 35 and 1 in 95)".

"From here" (A6, shown as in A35):

| Time to go | Flights still listed normally | Later listed as cancelled | 1 in | Range, 1 in | Shown as |
|---|---|---|---|---|---|
| 70 hours | 3,028 | 48 | 63.1 | 33.2 to 120.6 | 1 in 65 (between 1 in 30 and 1 in 130) |
| 48 hours | 3,316 | 47 | 70.6 | 38.1 to 131.4 | 1 in 70 (between 1 in 35 and 1 in 140) |
| 24 hours | 3,449 | 35 | 98.5 | 49.3 to 197.9 | 1 in 100 (between 1 in 45 and 1 in 200) |
| 12 hours | 3,625 | 25 | 145.0 | 71.4 to 295.6 | 1 in 150 (between 1 in 70 and 1 in 300) |
| 6 hours | 3,704 | 19 | 194.9 | 96.6 to 394.4 | 1 in 190 (between 1 in 95 and 1 in 400) |
| 3 hours | 3,754 | 16 | 234.6 | 120.0 to 459.7 | 1 in 230 (between 1 in 120 and 1 in 460) |

Every row clears the floor: the thinnest has 16 cancelled flights from 11 airlines on 10 days (A6). The later rows hold more flights because the record's first days caught flights only in their last hours. Leaving out any one airline's flights moves the 24-hour row between 1 in 77.5 and 1 in 123.8, inside its range (A8).

Departures and arrivals are counted together. Apart they are thinner, and their difference sits inside the ranges: on the 24-hour row, 22 of 1,720 departures and 13 of 1,729 arrivals (A7). (designer's call)

## Words (approved by me, 2026-11-12; D7)

These add to the "Words" of `docs/site-redesign.md`, which stand. The claims discipline is unchanged: "listed as cancelled", never a cancellation's clock time, no operator, actual-cancellation or delay claims. Every sentence below was run against the upload check's banned phrases and word rules, and passes.

- A rate is always "1 in N" with its range in the same breath: "about 1 in 100 (between 1 in 45 and 1 in 200)". Never a percentage. Never the words chance, odds, probability, likely, risk, forecast or predict on a reader page before the gate.
- A rate is always about the past, and about all flights at the airport: "so far", "of all flights at the airport", "were later listed as cancelled".
- The block's heading: "From here to the scheduled time".
- Its first line: "So far, of all flights at the airport that the list still showed normally at each point, this is how many were later listed as cancelled."
- Column heads: "Time to go", "Flights still listed normally", "Later listed as cancelled", "That's about". The first column reads "70 hours", "48 hours", "24 hours", "12 hours", "6 hours", "3 hours".
- The record line, on every page that shows a rate (constant `PAST_ONLY`): "This is what happened to past flights. It does not say what will happen to yours."
- Under the table, three lines. "Each row is a point in time: the 24-hour row counts flights listed normally 24 hours before their scheduled time, and how many of them were later listed as cancelled, however late." "Listed normally means any status but cancelled, delayed included." "More than 3 days to go: the airport's list does not show the flight yet. A flight already listed as cancelled when it reaches the list is not in this table."
- The count line: "Counted: 4,658 flights with a known outcome, scheduled up to two days before the last update, in a record kept since 27 October 2026. Not counted: 269 flights with no known outcome. 240 of them left the list while nothing was recorded, and 29 left it with no final status."
- The late line: "At least 9 of the 81 cancelled flights were listed as cancelled only after their scheduled time." The model brackets each listing between two sightings; 9 brackets lie wholly after the time, 1 holds it, and 19 cannot be placed (A17).
- The total, replacing today's headline: "So far, 81 of 4,658 flights with a known outcome were listed as cancelled. That's about 1 in 60 (between 1 in 35 and 1 in 95)."
- On a flight page, for an upcoming flight still listed normally, one prepared pair per checkpoint: "This flight has between 12 and 24 hours to go. So far, of all flights at the airport still listed normally with 24 hours to go, about 1 in 100 (between 1 in 45 and 1 in 200) were later listed as cancelled." The lead-ins: "between 2 and 3 days", "between 1 and 2 days", "between 12 and 24 hours", "between 6 and 12 hours", "between 3 and 6 hours", "under 3 hours". The figure is the one for the nearest point at or above the time left, so it leans high. A flight with more than 70 hours to go gets the 70-hour figure, the earliest there is.
- Its condition: "The figure is for flights the airport's list showed normally. This page was last updated 12 Nov 2026, 12:16 and cannot say what the list shows now. Check the airport's own list."
- When the scheduled time has passed since the upload: "This flight's scheduled time has passed. The row below shows the list as it was on 12 Nov 2026, 12:16."
- A number's own record is the page's existing summary line ("Since 27 October: departed once, cancelled once, one upcoming."). It is not restated with other counts.
- A number listed as cancelled whose flight is not: "Listed as cancelled. Another flight number with the same scheduled time and airport departed: LH 695." ("landed" for arrivals; "is still listed: OS 083" while that number is upcoming.) It claims nothing about aircraft.
- In a list row, a number whose own status differs is named in brackets, with "is": "(LH 0691A is listed as cancelled)". The bracket keeps a place name from following "cancelled", which the upload check would read as a banned phrase.
- The partner sentence keeps its words and its reason, "(same time, terminal and check-in desks)". It names the partners that share those three with the number, which for numbers that departed or landed are today's partners (A10). A partner tied by airline or desks alone gets the "Another flight number" line.
- "A flight" on "How this works": "Flight numbers with the same scheduled time and airport are counted as one flight when the list shows the same expected time, terminal and check-in desks for them. A number that did not depart or land is counted with a number of its own airline, or one with its own desks."

## Pages

### Front page

Top to bottom. Items not named keep their words and rules from `docs/site-redesign.md`.

1. The header band, unchanged: title, lede, "Last updated".
2. The search box, moved up from fourth place: "Flight number or city".
3. "From here to the scheduled time": the first line, the table of six points, the record line, the three lines under the table, the count line and the late line.
4. The total, as stat tiles and a sentence, as today. The tile that shows "1 in 60" prints its range right after it, in exactly the form " (between 1 in 35 and 1 in 95)"; it may be smaller type. Any other form fails the new upload check.
5. One flight's story, as today, picked among flights labelled CANCELLED by C10 and told through the number of C9.
6. Recent cancellations, "Flights each day", the built-by line and the footer, as today, counted by C1 to C10.

The table is plain HTML and needs no JavaScript. On a narrow screen each row stacks, as the cancellations table does.

### Flight page

- For each row labelled UPCOMING: a "from here" block above its change list. It holds the six prepared pairs, then the condition line, then the record line.
- A small script, `fromhere.js`, reads the row's scheduled time, which the build writes as a UTC instant in a `data-` attribute, and compares it with the visitor's clock. It shows the one pair whose lead-in fits the time left. It writes no text and no number of its own: every sentence is already in the page, where the upload check reads it. Both sides are UTC instants, so the visitor's time zone does not matter.
- With more than 72 hours to go it shows the "More than 3 days" line. When the scheduled time has passed it hides the block and shows the "has passed" line.
- Without JavaScript the block shows the table's six rows as a list.
- A row already labelled CANCELLED gets no block. A row listed as cancelled whose flight is not (C2, C10) gets the "Another flight number" line.
- Everything else as today, each row with that number's own label and warning.

### Day pages, the chart, the cancellation lists

Counted and grouped by C1, labelled by C10. A row names every number of the flight, with the bracket for a number whose own status differs. A cancelled flight's warning follows C9.

### How this works

New short sections, "I" allowed as now: what a flight is (C1, C2), what is not counted and why (C4), why every figure is a range (C8, in plain words: cancellations come in runs, by airline and by day), why three days is the limit, why the later rows hold more flights. One more, on the test: no figure is shown for one flight yet; four named signs are being tested on flights listed after the test was fixed; the gate is quoted in full.

## Signs

A sign is something the list shows about a flight at a given moment that might go with a later cancellation. My decision of 2026-11-05, in full: every signal the cancellation odds use "is fixed in advance and measured before use (its lift with an interval, the model's score with and without it), then re-tested on later months held out". This section fixes the signs and how each part of that sentence is carried out. D3 is where it proposes a pass mark the sentence does not set.

A sign is read for one number, at that number's checkpoint moment, from what the list showed then and nothing later. A number is "listed as cancelled as a whole" at a moment when it shows cancelled and no number tied to it then shows anything else. Tied then is C1 read at that moment, by direct ties only, since a chain needs the grouping at the end; a number that has left the list keeps the last status it showed. A flight carries S1, S2 or S3 in a row when any of its numbers in that row shows it, and S4 when every one of them does. The exact definitions are SQL in the figures file (A0b).

The four candidates at the 24-hour checkpoint (A25):

| Sign | Flights with the sign, later listed as cancelled | Without the sign | How many times the rate |
|---|---|---|---|
| S1. A number of the same airline from the same airport, scheduled to land 30 minutes to 12 hours before this departure, is on the list and listed as cancelled as a whole. Departures only. | 2 of 5 | 20 of 1,715 | too few so far to say |
| S2. Of the same flight number's other flights known at that moment, the latest one scheduled before this one is, or ended, listed as cancelled as a whole. | 4 of 30 | 31 of 3,419 | too few so far to say |
| S3. Another number of the same airline, in another slot scheduled within 24 hours either side, is on the list and listed as cancelled as a whole. | 11 of 491 | 24 of 2,958 | too few so far to say |
| S4. The number was first listed under 48 hours before its scheduled time. Numbers first seen when the records began or resumed do not count as late. | 1 of 11 | 34 of 3,438 | too few so far to say |

Version 1 uses none of them. None clears the floor of C8: S1, S2 and S4 rest on 1 to 4 cancelled flights, and S3's 11 come from 4 airlines. At 12 hours S3 does clear it, at 1.8 times the rate with a range of 0.5 to 6.3, which includes no difference (A25).

**The inbound check, so far.** The question left open on 2026-11-05 was whether the inbound flight is listed as cancelled before the departure, or only together with it. Of 41 cancelled departures whose listing can be timed, a matching inbound was listed first for 4, in the same download for 4, and not at all for 33 (A27). Read as of the moment, 5 departures carried the sign a day ahead: 2 were later listed as cancelled, both Frankfurt departures on consecutive days, and 3 departed. Six hours ahead 8 carried it: 1 was later listed as cancelled and 7 departed (A26). Those are 13 readings of 10 departures. They suggest a head start is rare; they settle nothing.

**Dropped.** Two signs from the 5 November look were re-measured and are not candidates. The status DELAYED a day ahead: 0 of 3 flights with it were later listed as cancelled. No check-in desks listed a day ahead: 2 of 303 departures, against 20 of 1,417 with desks (A25).

**A sign's test: the lift with an interval.**
- Counted flights: those whose first sighting, for every one of their numbers, is at or after the counting start.
- The test reads the 24-hour row of counted flights, up to the moment the gate is reached and no further ("The gate"). When the test is run does not change what it reads.
- The lift is the rate with the sign over the rate without it. Its range is 2.5 standard errors of its logarithm either side, grouped as in C8. 2.5, not 2, because four signs are tested at once.
- A sign passes when it clears the floor (10 cancelled flights with the sign, from 5 airlines and 5 days) and the whole range lies above 1.
- No repeats. A sign that fails stays failed for this version. Testing it again takes a new version, a new counting start and only flights listed after it.
- The exact form is the `ratio` query of the figures file. A29 runs the whole test as a dry run on flights already seen, which decides nothing.

**The score with and without the sign.** Measured on the same flights at the same moment, and published beside the result with its range: the Brier score of the 24-hour row's one rate, and of the two rates the sign splits it into. A Brier score is the average squared gap between a stated rate and what happened, lower being better. It is not a pass mark (D3). A bare score says little: saying the row's rate for every flight scores 0.01004 and saying "never" scores 0.01015, and "never" is right for 99.0% of flights (A33).

The figures in the table above were seen before any freeze. They decide nothing.

## The gate

A sign may change what the site shows only when both hold (D3):

1. The count. Take the counted flights of the 24-hour row in the order of the scheduled time they showed at the checkpoint. The gate is reached at the first such time that is at least 60 days after the counting start and by which 200 of those flights were later listed as cancelled. The days and the count are taken over every counted flight in the row.
2. The sign has passed its test, read on the counted flights scheduled up to that time.

What opens. The table's 24-hour row is split in two for that sign, "with" and "without", each a rate with its range, computed on counted flights only. Another row is split the same way when both halves clear the floor there. This is the same kind of statement as the table: what happened to past flights in the same position. Two signs that pass split the table separately; no combined figure is shown until a combined row clears the floor on its own. A flight's own page can say which half applies only when the site knows what the list shows now, which needs the scheduled rebuild (q23).

Why 200, in the row. The test is scored on the 24-hour row, so the count is taken there. The outside review's figure of about 400 counted all cancelled flights; the row holds 32 of every 58 (A28), so 200 in the row is about 360 in all. At today's pace of 3.6 a day the row reaches 200 in about 56 days, so the 60 days are what binds (A28, A31).

How often the tests would pass. D3's table is from a simulation (A31). Each simulated row is built from the real row's airline-and-week groups. Each group's rate is raised or lowered as a whole, by as much as makes the simulated rate's grouped error match the measured one. Each test then uses its own grouped error. On today's S2 and S3 the lift's grouped error is 1.25 to 1.62 times the textbook one (A25); in the simulation it is 1.4 to 1.6 times for the sign that follows its group and about 1 for the others. The floor's airline and day counts and the day grouping are not simulated.

### The re-test, and the accuracy record

"Then re-tested on later months held out." When a sign's split is first uploaded, a second counting start is set at the next Israel midnight. The same test runs once more on flights first listed after it, when the gate's count is reached again. A sign that fails loses its split, and "How this works" says so. The re-test is the same code, so it is frozen with the rest.

The published accuracy record of my 2026-11-05 direction is what these runs leave behind: each test's lift with its range, the score with and without the sign, and how each published half compared with what then happened. That last check is coarse and should be read so: a with-sign rate resting on 18 cancelled flights has a range of about 2.7 times either side, so it catches a rate that is wrong by about that much and nothing finer (A32).

### What is honest now, and what is public

At this size the data supports a rate with its range for the airport as a whole, by time to go; counts that say what they leave out (C2, C4); and counts only for one flight number. It supports nothing by airline, route, weekday or direction, and nothing about a bad day.

| | Public | Unpublished |
|---|---|---|
| Now | The table and the total with their ranges; the counting method; the gate in full; the names of the four signs under test | Any figure for one flight; any sign's counts on the site; the test's running counts, which stay in local files |
| After the gate | The test's result either way (D6), with the lift and the scores; a split table for a sign that passed | A flight-page line for a sign, until the site is rebuilt on a schedule |

## The record

The idea tested for this design: the raw archive and its receipts are write-once and timestamped, so what a fixed, dated rule would have said about any listed flight at any moment can be recomputed later. Freezing the rule might then replace a daily job that freezes each day's figures.

The design's answer: it does, for the sign test, on three conditions.

**Condition 1. What is frozen is code in a tagged commit.** The frozen rule is the model code, rules C1 to C8, the four signs, the sign test with its score, the gate and the re-test, as tested code. The SQL in the figures file is documentation that the code is checked against; a tag on a document would freeze a description, not a rule. So the tag waits for that code (D5).

**Condition 2. A version survives housekeeping.** A later change starts a new version with its own tag and its own counting start, and the old version stays as it was. One exception, because the tagged code may stop being runnable: the model build stops on a snapshot with no receipt, an unknown receipt version or a misplaced receipt, and clearing each takes a code edit (`src/model/rules.py`); the full build may also outgrow the machine. A change that only admits or drops named snapshots, or changes how the build is computed, continues the version when every figure for flights closed before the change is identical under both.

**Condition 3. Reading the model "as of" a moment must equal building it from the archive cut at that moment.** This is known not to hold everywhere, and is otherwise untested: UNVERIFIED. The known cases:
- The retime rule (R4) takes each key's last sighting over the whole archive (`link_retimes` in `src/model/rules.py`). A number that leaves the list and comes back is therefore treated as listed throughout, and a cut build can link a retime the full build does not. 7 numbers have left and come back so far (A20).
- R2's repeated store and R9's last sighting read one download ahead.
- The flight a number belongs to (C1) and its result (C2) are read at the end. That is right for counting results. It also decides which numbers' signs a flight carries, so a sign's reading for a number is as of the moment and its flight is not.

The first task of the plan is a test that cuts a synthetic archive at several moments and compares, with these cases in it: a number that leaves and returns, a retime at the cut, and a number whose flight changes after the moment. Where the two differ, the record has to be computed from cut builds. That means a build for every moment read, thousands of them, and neither the time nor the memory one build needs has been measured; the plan sizes it if the test fails.

What counts. The counting start is an Israel midnight written into the tagged commit, later than the moment the tag is pushed. Nothing about a counted flight was visible when the rule was fixed.

What makes the freeze checkable. The tag is public, in the repository this site links to. The archive is private, so a reader cannot recompute the record either way; a daily file in a private bucket would be no more checkable than a tag. What a reader can check is that the rule existed before the flights it was scored on. CI runs on every push with no filter (`.github/workflows/ci.yml`), so pushing the tag should start a public run that the hosting service dates itself. That it starts such a run for a tag push is UNVERIFIED; the owner confirms when pushing.

What it does not replace. Telling a traveller which half of a split their flight is in needs a fresh build, because it depends on what the list shows now. That is the scheduled rebuild (q23), needed when a sign has passed and not before.

## Keeping the figures current

Uploads are by hand (`docs/publishing.md`). Version 1 stays true between them:

- The table is a record up to a stated moment. An old upload shows an older record, not a wrong one. "Last updated" says how old.
- "How long until the scheduled time" comes from the visitor's clock, not from the upload.
- The sentence about a flight says what it is a figure for, names the upload's time and sends the reader to the airport's own list.
- A flight listed since the last upload has no row on its number's page. The front page's table still serves that traveller.

A fresher site is outside version 1. It needs q5 first, then q2 and q23, each on the owner's go; `docs/data-model.md` already makes the incremental build the precondition, and how much memory the full build needs today has not been measured. Frequent uploads are not free with today's script: at 15-minute uploads, about $16.47 a month in upload requests and 2,880 invalidations against 1,000 free (A34; prices from `docs/publishing.md`, not re-read; the price of an invalidation beyond the free ones is not in the repository: UNVERIFIED). That estimate belongs to q23's design.

## How it is built

- The same pipeline: `python -m timeline.build --model data/model --out site`, pure functions from rows to HTML, the marker-file swap, `timeline.check` before upload, `scripts/publish.sh`.
- Counting (C1 to C10), the "as of" reading (C6) and the signs are one new pure module beside `flights.py`, which stops grouping by codeshare group and calls it. The pages and the sign test share it.
- The range (C8) is one pure function: counts per group in, rate and two ends out. No random numbers, so the same model still gives the same bytes.
- `words.py` gains the sentences and the rounding; `views.py` the table, the block and the tile's range; `check.py` the rules below.
- `fromhere.js` is the second script on the site. It selects a prepared pair and nothing more.
- The sign test is a separate entry point that reads the same module and writes a local report. The tag of D5 is the first commit in which it runs.
- Cost: no new AWS service, as at the top; an upload stays about half a cent.

## Tests and checks

Each with a `scripts/mutation_check.py` entry, as the project's rules require.

Counting:
- C1: the same expected time, terminal and desks tie; two departed numbers of one airline at the same desks with different expected times do not; two desk ranges never tie; two terminals never tie; a cancelled number ties to its airline's departed number, and to another airline's at the same desks, and not to another airline's at other desks; a chain of three is one flight; a chain that would join two departed numbers apart leaves the others alone.
- C2: operated beats cancelled; cancelled needs no number that departed or landed; all else unknown.
- C3: changed back counts as its last status; cancelled twice counts once; a lettered number counts; the same number on two days is two flights.
- C4: a flight scheduled 47 hours before the last sighting makes no rate and one at 48 does; unknown results are left out and counted beside.
- C6: the clock is the time shown at the moment (a retime that moves a flight across a point); a number first listed past a point is not in its row; a moment in a hole is not a checkpoint; already cancelled at the point is not in the row; a DELAYED number is; the first passing counts.
- C7: a flight listed as cancelled after its scheduled time counts in every row it was in.
- C9: the earliest listing gives the warning, in lists and in the story box.
- C10: a flight with one number cancelled and another still listed is UPCOMING, then DEPARTED when that number departs; it is CANCELLED only when no number is listed otherwise. A mutation that puts rule 3 before rule 2 must fail.
- The late line from the bracket: wholly after, holding the time, and censored.
- A synthetic fixture with hand-computed counts, rates and ranges, in CI. The real model is not in the repository, so the figures file is reproduced by a local check that is run before the tag and not in CI.

The range:
- A hand-computed case for each grouping, and one where each is the larger. A week that starts on Sunday.
- The log-odds ends, never below zero.
- The floor at 9, 10 and 11 cancelled flights, at 4 and 5 airlines, at 4 and 5 days.
- Rounding at every step boundary; the ends rounded outward; halves up.

Signs and the test:
- Each sign present and absent for a number; "as a whole" with a tied number still listed, and with one that left as departed; a number first seen after the moment is ignored; S2's "latest one before" read as of the moment after a retime; a flight carries S1 when one number shows it and S4 only when all do.
- The test: counted flights only; flights scheduled after the gate was reached are not read, whenever it is run; the floor; a range that touches 1 fails; a second run does not replace the first; the re-test counts only from its own start.
- The cut-archive comparison of "The record", condition 3, with its three cases.

Words and pages:
- One exact-text test per new sentence.
- The block appears on UPCOMING rows only; a cancelled row has none.
- The chart's counts equal the day pages'. Over days whose flights are all closed, the day pages' cancelled and known-outcome counts sum to the total's for those days.
- The scheduled instant written for `fromhere.js` equals the model's UTC time for the row, tested under an Israeli time zone (the naive-conversion trap noted in `docs/timeline.md`).
- Same model, same bytes.

`fromhere.js`, run under Node as the search test is:
- each boundary between lead-ins; more than 72 hours; a passed time;
- a missing or unreadable attribute leaves the no-script list showing;
- the same result under three time zones.

The upload check (`src/timeline/check.py`) newly enforces, on the real site before every upload:
- The whole words chance, chances, odds, probability, likely, unlikely, risk, forecast, forecasts, predict, predicts and prediction are refused on every page except `how-it-works.html`, case-insensitive. The airport's own strings are skipped as today.
- Every "1 in N" in a page's text is either followed at once by " (between 1 in A and 1 in B)" or sits inside such a range. Anything else is refused.
- A percent sign in the text of an HTML page is refused.
- A page whose text holds "1 in N" must hold the record line, `PAST_ONLY`.
- Tests: "1 in 100 (between 1 in 45 and 1 in 200)", "risky" inside an airline's name, "100%" inside the stylesheet and `width="72%"` inside the chart's SVG pass. So does a list row that reads "(LH 0691A is listed as cancelled)" before "Athens". A mutation for each rule.
- Today's pages already pass the first and third rules: the local build of 2026-11-04 holds none of the refused words and no percent sign in its text (checked with grep for this document; the chart's percentages are attributes).

## Five outsiders (q13)

The script in `docs/timeline.md` quotes v1's words and has to be rewritten, as `docs/site-redesign.md` says. What the sessions test for this design:

Tasks, the owner watching and saying nothing:
1. "You are flying tomorrow afternoon. Here is the site. Tell me what it tells you about your flight." (A flight scheduled about a day ahead is picked just before the session.)
2. "What does '1 in 100 (between 1 in 45 and 1 in 200)' mean? Say it in your own words."
3. "Is there anything you would do differently after reading this?"
4. "What is this site, who made it, and what do you think that person can do?"

What to watch for:
- Reading the rate as a promise about their own flight. This is the misreading the design most fears.
- Reading a row as "cancelled during these hours".
- Skipping the range, or reading it as two more facts.
- Reading "listed as cancelled" as "the flight did not fly".
- Taking the page as live or official.
- Concluding that a flight more than three days out is safe.
- Not finding the flight.

What follows is decision D9.

## The launch post's figure

The post's drafts hold older numbers. The figure to quote is the 24-hour row of the front page's table: of all flights still listed normally 24 hours before their scheduled time, how many were later listed as cancelled, with its range. On this model: 35 of 3,449, about 1 in 100, between 1 in 45 and 1 in 200 (A6, A35). The figure moves with every upload, so the post takes it from the live front page on the day it goes out.

## Left to the builder

Markup and CSS within the look rules of `docs/site-redesign.md`; how the table stacks on a phone; how the six prepared pairs are hidden and shown; module and function names; the order of sections on "How this works"; lines for this document and its figures file in `docs/README.md`.

## Suggested, not in scope

- A line on when cancellations are first listed (how many inside the last 12 hours).
- The table by direction, once each direction clears the floor in every row.
- A fifth sign for a bad day at the whole airport. It cannot be tested until the record holds one.
- Uploading only changed files.
- Publishing the derived tables, so a reader could recompute the record.
- A "when is your flight" picker on the front page.

## Outside this design, for the owner

- The tag and its push (D5), and confirming that the push starts a dated public run.
- The order q5, q2, q23.
- The terms reading. `docs/terms.md` records the owner's reading for the history pages. A rate over past flights is a derived count of the same kind; the owner confirms it covers this.
- The five sessions (q13) and the launch post.
- q3, on which every delay figure still waits.
- The README's counts and screenshots after the first upload.

## Unverified

- The model read "as of" a moment equals the model built from the archive cut at that moment, outside the known cases ("The record", condition 3). What cut builds would cost if it does not.
- That the hosting service starts a public run when a tag is pushed.
- The upload price, the free invalidations and "every build rewrites every file" come from `docs/publishing.md`; the 1,040 files are the local build of 2026-11-04. None was re-read from AWS. The price of an invalidation beyond the free ones is not in the repository.
- How much memory the full model build needs.
- Whether a number listed as cancelled inside a flight that departed or landed is a second listing or a second aircraft, whether ASY 991 and UN WZ932 are mis-keyed listings, and whether the 23 pairs with different expected times are separate aircraft (C1). The list does not say.
- Whether the 29 flights that left the list with no final status were cancelled.
- The simulation (A31) assumes today's rate, pace and group sizes continue, and that runs come by airline and week only.
- The outside review's gate is quoted from notes kept outside the repo.

## Review (2026-11-12)

Two reviews, each with its own queries on the same model. Each finding was checked against its source before it was folded in.

A fresh Fable review of the first draft found that:
- The label order showed a flight as CANCELLED while one of its numbers was still listed normally. C10 now puts UPCOMING first (A24).
- The first gate gave a Brier-score comparison a pass mark that a real sign seldom clears at the gate's own count. The gate became a count in the row the test is scored on, plus the sign's own test.
- The rule to be frozen was not exact. The tag now waits for tested code, and the open choices are closed in "Signs" and "The gate".
- Counting by slot alone folded another airline's cancelled flight into one that departed. C1 was rewritten.
- "Closed" meant "has left the list", which let flights removed early enter the count ahead of their hour. C4 now closes every flight 48 hours after its scheduled time. The first draft's total, 80 of 4,928, became 81 of 4,640.
- The "as of" reasoning was wrong in a known case, and a build-memory figure quoted from the commissioning session was an error. Condition 3 lists the known cases; the memory figure is gone.
- Smaller fixes: the late line, counts under the floor, the uncounted flights, rows named by their point in time, three absent parts of the direction, decision D9, per-airline counts removed, the appendix in its own file.

An Opus re-review of the second draft rebuilt the counts in plain Python, matched them, and found that:
- The simulation behind D3 widened both tests by the overall rate's grouping factor, which belongs to neither. It was redone with runs in the draws and each test's own grouped error (A31). A score pass mark would pass in 12% to 46% of rows for most signs, not almost never. D3 now names the signs and adds weaker ones.
- The owner's 2026-11-05 decision was quoted in part. It is quoted in full, D3 is put as a pass mark the decision does not set, and the re-test on later flights is a real one.
- The second draft's C1 still joined numbers the list shows apart. C1 now follows the model's key for numbers that departed or landed (A10) and ties a number that did not fly by airline or desks. The total became 81 of 4,658.
- A proposed sentence held a phrase the upload check bans. It was reworded, and every proposed sentence was run against the check's rules.
- Smaller fixes: the test no longer depends on the day it is run; the gate's days and count are taken on one set of flights; D5 and Condition 1 name the same things; signs are read per number as of the moment; the story box and the list warning are listed among the changes.
