# Flight lookup (q21), updated for "Will It Fly?" (q27)

Grade: production-lean, the site's grade (`docs/site-redesign.md`): deterministic, tested, mutation-checked; plain static HTML, CSS and a little JavaScript. The design assumes it. The owner confirms it (decision D1).
The 2026-11-17 update keeps the grade: no decision of that day changes it.

Cost: nothing new on AWS, so $0 a month added. Version 1 is built by the existing local build and published by the existing hand upload, which costs about half a cent an upload (`docs/publishing.md`, "Cost (monthly)": $0.0055 per 1,000 PUT requests, AWS Price List API, il-central-1, read 2026-10-29; not re-read for this design). Nothing here needs a schedule, a function or a bucket.
The 2026-11-17 update adds no AWS service either. Its four font files add four requests to an upload, far under a cent (`docs/site-redesign.md`, "How it is built").

Status: design v3, 2026-11-12. Written by a Fable agent after a blind-spot pass on the same data, then revised after two reviews ("Review" at the end). The owner skipped the design questions, so every call that is the owner's is listed first, each with a recommendation. Calls the design made on its own are marked "(designer's call)". Approved by me, 2026-11-12, with D1 to D9 as recommended. Built to [flight-lookup-plan.md](flight-lookup-plan.md): the build is done, and it passed its final checks and a whole-branch review on 2026-11-15.

Updated 2026-11-17 for q27, not built. That day I decided the redesign, "Will It Fly?" ("Decided 2026-11-17" below); the design work was agents', and a Fable agent brought this document to my decisions. The update was reviewed the same day by a fresh Opus reviewer, and its findings are folded in ("Update" at the end). Until q27 is built, the code and the live site follow the 2026-11-12 text of this file (commit 9eefe61). The counting rules C1 to C10, "Signs", "The gate", the re-test and "The record" are frozen as tag `record-v1`, and no rule in them is changed. Two things inside those sections are new text: a dated note on page words at the head of "Counting method", and "What is honest now, and what is public" inside "The gate", which is rewritten.

Figures: every figure comes from a query run for this document on the model built 2026-11-12 from lists up to 2026-11-12 10:16:45Z. The queries and their results are in [flight-lookup-figures.md](flight-lookup-figures.md), cited as (A1), (A2) and so on.

Figures dated 2026-11-17 are not in the figures file. They come from the model built that day from lists up to 09:46 Israel time, read in two places: the front page of that day's local build (the total, the six rows and the counts beside them), and a delay measurement made the same day on the same model with the frozen counting code, cited as "the delay measurement" (its script and output are kept outside the repository). The chances shown as examples in "Words" come from a rough first blend with untested weights: they show how a line reads and are not results.

What it changes in `docs/site-redesign.md`. Everything not listed there stands.
- "Who is a flight": replaced by rules C1 to C4.
- "Labels": a flight in a list gets its label by C10. A number's own label on its own page is unchanged.
- "Warning": in a list, a cancelled flight shows the warning of its number that was listed as cancelled first (C9).
- "Codeshares": the sentence stays. Its partners are the other numbers of the flight under C1 that the list showed with the same expected time, terminal and check-in desks (`partners()` in `src/timeline/flights.py`), with the reason words in "Words".
- Front page: the headline counts closed flights and carries a range; the search box moves up; the new block follows it. The story box picks among flights labelled CANCELLED by C10 and shows the number of C9. Until this design was built, `featured` in `flights.py` picked by a number's own label, which could feature a number listed as cancelled inside a flight that departed.
- The "1 in N" rounding gains steps above 100 (C8).
- "Look": two scripts, `search.js` and `fromhere.js`.
- Tests: the codeshare-split test is retired with the split it tested; the headline tests are rewritten.
- The non-goal "Cancellation odds or forecasts": replaced by "The gate".

What my 2026-11-17 decisions change, in this document and in `docs/site-redesign.md`:
- A flight page leads with a chance for that flight ("The blend"). D2's "No figure for one flight", the non-goal on a figure for one flight and the anti-goal on one number's record are overturned.
- Percentages replace "1 in N". Ranges leave the traveller's pages for "How this works".
- Delays of an hour or more are shown. The non-goal "Delay figures of any kind" becomes "delays under an hour".
- "Listed as cancelled" becomes "cancelled"; "warning" becomes "notice"; every traveller page's words are rewritten ("Words" here and in `docs/site-redesign.md`).
- The flight page's order, the strip of a number's days, and two changes to `fromhere.js`: it moves the next day ahead to the top when one passes, and it writes "Updated N hours ago".
- The upload check: "chance" and the percent sign are allowed, and a flight page with a chance must carry its "Worked out from" line ("Tests and checks").
- Look A, with its font files (`docs/site-redesign.md`, "Look").
- Not changed: C1 to C10, the signs, their test, the gate, the re-test, the record and the frozen files.
- Not done by this update, and now behind it: `docs/publishing.md` (three uploads by file type; the file types the check reads), `docs/timeline.md` (the q13 script), `README.md` and `docs/README.md` (their lines on this site), and the text of "How this works" in the two plans' appendices.
- Already done: `docs/terms.md` carries my reading for the "Will It Fly?" pages (2026-11-17: its opening line and its clause 4 paragraph). Only its clause 8 line still quotes the unofficial line the built site carries; the build changes that with the footer.

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

### Decided 2026-11-17 (q27)

Three decisions of mine that day, in order. Where they differ, the later one stands.

**D10. The site is reorganised around a traveller's own flight, in look A ("Timetable").** "Find your flight" over a plain search box leads the front page. A flight page puts its days still ahead first, soonest first, with the nearest day's answer on a phone's first screen, then the flight number's days as a strip, then past days, newest first. `fromhere.js` moves the next day ahead to the top when one passes by the visitor's clock, because uploads are by hand and pages age. Why: I judged a first round of three looks against a nervous traveller asking about their own flight, and found the pages led with the airport-wide table and its background. Look A over C, the designer's pick: one drawing per answer, and red keeps one meaning. Over B: the quietest, least tuned to a phone reader. The look is in `docs/site-redesign.md`, "Look".

**D11. "Will It Fly?": plain words, percentages, and the flight's own record first.** The site is renamed, and its traveller pages take plain words a non-technical reader follows. Figures are percentages. Ranges leave the traveller's pages for "How this works". One disclaimer, "What the numbers mean", is linked from every page. Pages say "cancelled", not "listed as cancelled". Delays show only at an hour or more by the airport's expected time. A number counted with another airline's flight shows that airline's record ("counted with …"). The flight page's script may write "Updated N hours ago". Why: the reader I am writing for is a nervous, non-technical traveller (my words then: "look at it from a 60 year old mom's perspective"); the 2026-11-12 words read like a statistics report; an airport-wide figure on every flight's page leaves no point in having a page per flight; a percentage is what that reader can act on; and airlines differ about tenfold (El Al 0.6% and Lufthansa 6.0% of counted flights to 2026-11-17), so the airport's average misleads either way. Rejected: counts only for a flight's record; the airport's figure as the headline; a hard "no figure for one flight before the gate".

**D12. A flight's headline is one blended chance, not a switch between records.** A flight page's headline gives one chance it's cancelled and one it's delayed an hour or more, from a simple blend ("The blend"). A "Worked out from" line under the headline names what it rests on. The history lines below give counts, not percentages. A chance is never "0%". This replaces D11's first form, in which the headline switched between records (the flight's own from 14 flights, else its airline's from 100, else the airport's) and a clean record read "0% so far". Why: the third round of words read to me as "absolute gibberish to a normal human". The site speaks in odds now, as a simple blend, and a tested model replaces the blend later (q28): "it doesn't matter so much at this point how accurate the numbers are, it just needs to read the way I want it to read in the future."

I settled the design on the fourth round of mockups (a Fable designer's, in look A, kept outside the repository), and approved three fixes after it: on a page with no flight ahead the headline reads "Chance its next flight is cancelled"; "First on the list at 09:32"; and, for past days, "Landed around 19:55" and "Left around 17:38". My approval records the last two as phrases. Where they stand (the first in place of "Earliest record (09:32)" at the head of a list of changes, the others in place of "scheduled 19:45 · expected 19:55" on a past day) is a reading that awaits my confirmation. What the three leave open is under "Words", "No approved words yet", here and in `docs/site-redesign.md`.

What this does to D1 to D9:
- D1 stands.
- D2 is overturned for the pages: a flight page leads with a chance for that flight. The record by time left stays on the front page, as percentages.
- D3 to D6 stand untouched: the gate, the counting method, the freeze and the published result. The gate still decides when a sign may change what the site shows. The blend uses no sign.
- D7: the words of 2026-11-12 are replaced ("Words").
- D8 stands: no browse view.
- D9: its stop rule was written for the table. A new one is proposed and not approved ("Five outsiders").

## Why

My direction, 2026-11-05: the front page and the flight pages lead with a lookup. A traveller finds their flight and sees the chance it will be listed as cancelled between now and departure, as a range beside a typical flight at the same point, with tested signs, a browse view and a published accuracy record. I am holding the launch until the front page leads with something a traveller can act on. Today it leads with a total, which nobody can act on.

A blind-spot pass on 2026-11-12 found what stands in the way: a hand-uploaded site has no "now", no evidence gate had been chosen, the counting unit moves the total by a third (A9), and two weeks hold too few cancelled flights to tell one flight from another (A25). This design delivers the part of the direction the data supports today: the typical flight at the same point, as a range, with the traveller's own clock supplying "now". It fixes in advance how signs are tested.

What a traveller can act on in version 1:

- How much a normal listing means at each point in the last three days. With 70 hours to go, about 1 in 65 flights still listed normally were later listed as cancelled; with 3 hours to go, about 1 in 230 (A6, A35).
- When to look again. Listings change late: at least 9 of the 81 cancelled flights were listed as cancelled only after their scheduled time (A17).
- Their own flight number's record, which the flight page already shows.

My decisions of 2026-11-17 (q27). Judging the built pages as a nervous traveller would read them, I found they led with the airport-wide table and its background, in words that read like a statistics report. The reader I now write for is a non-technical traveller. My test: a 60-year-old checking her daughter's flight reads every line aloud without pausing. Three things follow. The pages are reorganised around the traveller's own flight (D10). They speak in percentages, and a flight's page leads with figures for that flight (D11). And the headline is a chance from a simple blend, with a tested model to take its place (q28): for now the pages have to read the way they will read then (D12).

What a traveller can act on after q27:

- The chance their flight is cancelled and the chance it is delayed an hour or more, each with what it was worked out from.
- Their flight number's own days, drawn as a strip, and its airline's counts.
- How old the page is, and a plain line sending them to their airline.
- As before, when to look again: cancellations are marked late (at least 15 of 104 only after the scheduled time, on the 2026-11-17 model).

## What the list can and cannot show

Measured on this model. These facts shape the rules below.

- A flight is on the airport's list only for its last three days. A number first appears a median 71.9 hours before its scheduled time and never more than 72.0 (A18).
- A flight already listed as cancelled when it reaches the list is almost never seen: 2 of 7,092 numbers first listed on time (A19). Every figure here is about a late listing, for a flight that reached the list normally.
- A departed or landed number leaves the list about a day after its time: a median of about 24 hours, 43.3 at the most. A cancelled number has left as early as 54.6 hours before its time and as late as 51.4 after (A18).
- 29 flights left the list with no final status, 27 of them before their scheduled time (A3). The list does not say whether they were cancelled.
- The record has one hole, 42 hours long, from 27 to 29 October 2026 (A30). 240 flights left the list during it (A3).
- The record holds no bad day. From 30 October to 9 November the busiest day had 10 cancelled flights and the quietest 1 (A23). A storm, a strike or a security closure is when a traveller most wants this page, and it is when these figures are most wrong.

## Goals

- A traveller with a flight in the next three days learns, in a few seconds on a phone, the chance it is cancelled and the chance it is delayed an hour or more, and what each chance was worked out from.
- Every line a traveller reads passes my test: a 60-year-old checking her daughter's flight reads it aloud without pausing.
- Every figure on the site is counted one way, written down as rules a reader can run: C1 to C10 for flights and their results, "The blend" for a flight's chance.
- A chance says in words what it rests on: whose history, how many flights, and the dates of a bad week. The ranges that allow for cancellations coming in runs are on "How this works".
- The page stays true between hand uploads: it says how old it is, the time left comes from the visitor's clock, and the next day ahead moves to the top when one passes.
- The test a sign must pass is fixed, as code, before any flight it will be scored on is listed.
- The blend is compared with what happened in the last week before it ships.

## Non-goals

- A sign applied to a flight. Four candidate signs are defined and tested unpublished. "How this works" names them; no page shows one against a flight, or its figures, before it passes. The blend uses none.
- A tested forecast. The blend is a simple first version with untested weights. The tested model, with its public accuracy record, is q28.
- Three parts of the 2026-11-05 direction, each for a stated reason:
  - Reschedule odds, earlier or later. The model's retime rule (R4) is still marked UNSURE in `docs/data-model.md`, and 43 of 7,657 numbers had their time changed while listed (A22).
  - How far ahead each airline's cancellations show. No airline has enough: the largest group on the 24-hour row holds 8 cancelled flights (A8). The airline's history a flight page shows since 2026-11-17 is a count of its flights, not a statement of how early its cancellations show. The list names no operator, so that airline is the one C8 groups the flight under.
  - "Is today unusual", for the airport or an airline. The record holds no unusual day to measure against (A23), and the answer needs the list as it is now, which a hand-uploaded site does not have. Sign S3 is the airline half of this idea, under test.
- A browse view (D8), a table that ranks airlines, route comparisons, a table by direction. An airline's history shows only on its own flights' pages.
- Delays under an hour, in any line, figure or picture: what the airport's expected time measures is still unconfirmed ("The blend", Delays).
- A range on a traveller's page.
- Live data, a scheduled rebuild (q5, q2, q23), and new file types beyond look A's four font files (`docs/site-redesign.md`).

## Anti-goals (a failure even if it works)

- A reader taking a chance as a promise about their flight. Every chance reads "about" or "under" and says what it was worked out from, every page's footer says the chances are estimates and not promises, and q13 tests for this misreading.
- "0%" as a chance, anywhere. A clean history reads "under 1%".
- A chance on a flight page with no "Worked out from" line on that page.
- One bad week read as a steady rate. Where a record's cancellations all fall in one week, its line names the dates.
- A number's own cancelled-of-flights standing alone as its chance. That record is a median of 6 flights long (A21), and none cancelled in 6 cannot tell "never" from "1 in 3" (the usual 95% bound for none in six is 39%); one cancelled in two would read as 50%. The blend's pull towards the airline is the answer to this, and the history line gives counts only.
- A delay under an hour shown as a delay. 65.8% of counted departures show an expected time 15 to 59 minutes after the scheduled one (the delay measurement), which looks like how the airport writes its times, not lateness.
- A page that hides its age, or a figure that silently means something else when the upload is old.
- A line my reader would pause on.
- Everything `docs/site-redesign.md` already lists: collection words on reader pages, "we", overclaiming, looking official.

## Counting method

Rules C1 to C10. "Number" means one airline flight number on one scheduled day, a row of the model's `flights` table. "Slot" means one direction, airport and scheduled time. The figures file's setup (A0) is rules C1 to C8 in SQL; C9 and C10 are display rules.

**Page words in this section, since 2026-11-17.** The rules are frozen and unchanged. A few of their sentences say what a page prints, and my decisions of that day changed the printing, not the counting:
- C5: the front page names the six points "3 days away" to "3 hours away". A flight page's all-airlines line names the stretch the flight is in ("6 to 12 hours before a flight") and gives the figure of the point at its far end. C5's own reason speaks against naming a stretch: a reader may take it as "cancelled during these hours". The line stands as I approved it and the rule is untouched; the misreading is on the watch list of "Five outsiders".
- C8: a row below the floor reads "Not enough flights yet" where it read "too few so far to say". The pages print percentages, written by the rules in "Words", so the "1 in N" rounding serves only a page that still prints "1 in N". The airline a flight is grouped under was never shown; a flight page now names it as the airline whose history the flight's chance leans on ("The blend"), and it still claims nothing about who operates the flight.
- C9: the "warning" is called "notice".
- C10: NO FINAL UPDATE is called NO NEWS YET.
- "The figures under the method": the "Shown as" forms are those of 2026-11-12 and of the site as built. The 2026-11-17 counts and their percentages are in "The blend".

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
| 3 hours | 3,754 | 16 | 234.6 | 120.0 to 459.7 | 1 in 230 (between 1 in 110 and 1 in 460) |

The 3-hour row's range starts at 1 in 119.99 before rounding (120.0 at one decimal). C8 rounds the ends outward, so it shows as 1 in 110. Corrected 2026-11-12: the first version printed 1 in 120.

Every row clears the floor: the thinnest has 16 cancelled flights from 11 airlines on 10 days (A6). The later rows hold more flights because the record's first days caught flights only in their last hours. Leaving out any one airline's flights moves the 24-hour row between 1 in 77.5 and 1 in 123.8, inside its range (A8).

Departures and arrivals are counted together. Apart they are thinner, and their difference sits inside the ranges: on the 24-hour row, 22 of 1,720 departures and 13 of 1,729 arrivals (A7). (designer's call)

## The blend (decided 2026-11-17, D12)

A flight page's headline gives one chance that the flight is cancelled and one that it is delayed an hour or more. Both come from a simple blend of three records: the flight number's, its airline's and the airport's. It is a first version, to be replaced in the same slot by a tested model (q28). It uses no sign and is no part of the frozen record: it is new code beside the frozen modules, and its counts are new measurements.

**The rule, for cancellation.** In order:

1. The airport's rate: cancelled flights over flights, all airlines.
2. The airline's rate, pulled towards the airport's as if the airline had 100 more flights at the airport's rate.
3. The flight number's rate, pulled towards its airline's as if the number had 14 more flights at the airline's rate.
4. The result is scaled by the airport's time-left curve: multiplied by the rate of the table's row for the time left, over the all-flights rate.

In symbols, with k cancelled of n flights for the number (f), its airline (a) and the airport (0), and r_h the rate of the row for the time left: r_0 = k_0 / n_0; r_a = (k_a + 100 x r_0) / (n_a + 100); r_f = (k_f + 14 x r_a) / (n_f + 14); the chance is r_f x r_h / r_0.

**For delay.** Steps 1 to 3 the same way, counting flights delayed an hour or more in place of cancelled flights. No step 4: delays are flat across the time left ("Delays" below).

**The weights.** 14 and 100 reuse the thresholds of the rule the blend replaced. They are not tested. The reasons given for them then: 14 is two weeks of a daily flight, so every day of the week is in it twice; at 100 flights one flight moves an airline's figure by a point at most. On the 2026-11-17 model 292 of 1,044 flight numbers had 14 or more counted flights (counted for the plain-words proposal of that day, not recounted: "Unverified").

**What follows from the rule.** A chance is never zero: a number with no cancelled flight still takes a share of its airline's rate, so a clean history reads "under 1%" and never "0%". A number with no flights yet takes its airline's rate, and an airline with none takes the airport's.

**The time-left curve on the 2026-11-17 model** (the local build of that day, front page; the last column computed for this update):

| Row | Flights still on then | Cancelled later | Rate | Over the all-flights rate |
|---|---|---|---|---|
| 3 days away (the 70-hour point of C5) | 4,472 | 71 | 1.6% | 0.934 |
| 2 days away (48 hours) | 4,760 | 69 | 1.4% | 0.852 |
| 1 day away (24 hours) | 4,892 | 52 | 1.1% | 0.625 |
| 12 hours away | 5,069 | 39 | 0.8% | 0.452 |
| 6 hours away | 5,149 | 31 | 0.6% | 0.354 |
| 3 hours away | 5,195 | 23 | 0.4% | 0.260 |
| All flights (the total, C4) | 6,115 | 104 | 1.7% | 1 |

The rows and the total are the frozen counting's own (C4 to C7): the blend reads them and changes nothing in them.

**Worked examples.** Computed for this update from the counts on the round-4 mockups, with the rule above. They are examples of a rough first blend, not results.

| Flight | Counts | Before the scaling | Scaled | Reads |
|---|---|---|---|---|
| LO 155, cancelled | the number 0 of 22; LOT 0 of 127; the airport 104 of 6,115 | 0.29% | 0.25% on the 48-hour row, 0.27% on the 70-hour row | "under 1%" |
| LH 694, cancelled | the number 4 of 14; Lufthansa 11 of 183 | 16.5% | 15.4% on the 70-hour row | "about 15%" |
| LH 697, cancelled | the number 1 of 2; Lufthansa 11 of 183 | 10.2% | 9.5% on the 70-hour row | "about 10%" |
| LO 155, delayed | the number 0 of 22 that flew; LOT 2 of 127; arrivals 149 of 3,029 | 1.2% | not scaled | "about 1%" |
| LH 694, delayed | the number 0 of 10 that flew; Lufthansa 7 of 172 that flew; arrivals 149 of 3,029 | 2.6% | not scaled | "about 3%" |
| LH 697, delayed | the number 0 of 1 that flew; Lufthansa 7 of 172 that flew; departures 231 of 2,982 | 5.1% | not scaled | "about 5%" |

LO 155's three values (0.25%, 0.27% and 1.2%) are the ones the mockups' designer recorded for its days of 18 and 19 November, 31 and 55 hours ahead when the mockup was frozen. So the examples follow four readings that my decision's text leaves open: the row is the nearest point at or above the time left, as the 2026-11-12 rule had it; a page with no flight ahead takes the 70-hour row; for delay the airport's rate is the direction's own, arrivals or departures; and a delay is counted over flights that flew. They are recommended under "Left to the builder", not decided. The mockups' airline counts (LOT 127, Lufthansa 183) were counted on closed flights (C4) in an earlier round and were not recounted when LO 155's own count moved from 20 to 22.

### Delays: only an hour or more

What the airport's expected time measures is half settled. The datastore's field notes, sent with every reply, call it "AnticipatedTimeLocal". Whether it is a gate time or a runway time is unconfirmed. I allowed delay figures on 2026-11-17 with a disclaimer that says what "delayed" means ("Words", "What the numbers mean").

The delay measurement, on the counted flights of the 2026-11-17 model (closed, with a known result):

- A flight's delay is the airport's final expected time minus its scheduled time (the model's `est_minus_sched_min`), read from its numbers that departed or landed. Every one of the model's 6,725 flights that departed or landed shows one value across its numbers.
- 2,001 of 3,040 counted departures (65.8%) show an expected time 15 to 59 minutes after the scheduled one, against 484 of 3,075 arrivals (15.7%). That looks like the time's convention, gate against runway, not lateness. So nothing under an hour is counted or shown.
- Delayed an hour or more: 231 of 2,982 departures that flew (7.7%; grouped range by C8, 6.4% to 9.4%) and 149 of 3,029 arrivals (4.9%; 3.8% to 6.3%).
- It is flat across the time left: over the six rows, departures run 7.5% to 7.8% and arrivals 4.7% to 4.9%. This is why the blend does not scale a delay, and why the front page says "It's about the same however soon you fly."
- 48 counted flights hold a number whose scheduled time was moved while listed. The measurement counts their delay against the last scheduled time, so a flight moved to a later time is not counted as delayed.

The label DELAYED is a different thing: the airport's own status word, shown whatever the minutes (`docs/site-redesign.md`, "Labels"). The two meanings on one site are an open question ("Outside this design").

### Before it ships: the back-test

Part of my decision: before the blend ships, it predicts the last week from the weeks before it, and the prediction is compared with what happened, to catch a blend that is badly off. No pass mark is set. How the comparison is run is under "Left to the builder"; what counts as badly off is mine ("Outside this design").

### Limits, stated

- The weights are untested, and the record is three weeks long.
- One bad week moves a short record a long way: LH 694's four cancelled flights of 6 to 9 November give "about 15%". The "Worked out from" line names the week so that the figure is not read alone.
- The time-left curve is the airport's, applied to every airline and every flight alike.
- An airline's history is counted under C8's grouping airline. The list names no operator.
- As on 2026-11-12, the record holds no bad day. A storm, a strike or a security closure is when a traveller most wants this page, and it is when these figures are most wrong.

## Words (approved by me, 2026-11-17; they replace the words of 2026-11-12)

These add to the "Words" of `docs/site-redesign.md`, which holds every page's frame, the labels, the notice sentences and the lists. This section holds the words that carry figures. They replace the words I approved on 2026-11-12 (D7): "1 in N" with its range, never a percentage, "listed as cancelled", the record line and the condition line. The built site shows those until q27 is built.

How they were reached: a plain-words proposal (kept outside the repository, as the mockups are), a third round of mockups by a Fable designer that set it in look A, and a second pass on the words after I called that round "absolute gibberish to a normal human". I settled the design on the fourth round of mockups and approved three fixes after it. The test for every line is mine: a 60-year-old checking her daughter's flight on her phone reads it aloud, and if she would pause, the line is rewritten.

Every figure in the examples is from the 2026-11-17 model. The chances among them come from a rough first blend: examples of how a line reads, not results. Every line in this section's tables was run, for this update, against the upload check's banned phrases and its "we", "our" and "us" rule as the code has them today, and passes. The lines fail today's check only where my decisions change it: the words "chance" and "chances", and the percent sign ("Tests and checks").

### How numbers are written

- A chance reads "Chance it's cancelled: about 15%". "About", because it is an estimate.
- Below 1%: "under 1%" in sentences and headlines. The front page's table keeps one decimal (0.8%), where the numbers line up.
- From 1% to 10%: whole numbers in headlines ("about 3%"), one decimal in the table and in the averages for all airlines (1.6%). The approved lines write the delay averages whole, with "about" ("about 8% for departures and 5% for arrivals").
- Never "0%" as a chance: the blend never gives zero, and "under 1%" covers a clean history.
- A bad week is named with its dates.
- Every count on a page uses the same flights: each flight whose ending is known. So the history line, the "Worked out from" line and the strip agree (LO 155: 22, not the 20 flights that are also two days past, C4).
- History lines give counts, not percentages ("22 flights · none cancelled"). The chance is the headline's job.
- No range on a traveller's page.
- "Cancelled", not "listed as cancelled". Where a sentence says when, it says "marked cancelled": the record knows when the airport's list changed, not when the airline decided.
- A delay is "an hour or more", always in those words. Nothing under an hour is shown.

### Front page: the table

| Where | Words |
|---|---|
| Heading | Chance of cancellation, by how soon you fly |
| First line | If your flight is still on 3 days before, there's about a 1.6% chance it gets cancelled. By 3 hours before, it's 0.4%. |
| Column heads | Your flight is… · Chance it's cancelled |
| Rows | 3 days away · 2 days away · 1 day away · 12 hours away · 6 hours away · 3 hours away, each with its percentage to one decimal. On the 2026-11-17 model: 1.6% · 1.4% · 1.1% · 0.8% · 0.6% · 0.4% |
| A row with too few flights | Not enough flights yet |
| Under the table | These are averages for all airlines, from about 5,000 flights since 27 October. A delayed flight still counts as "still on". |
| The delay line | **Chance of a delay of an hour or more:** about 8% for departures and 5% for arrivals. It's about the same however soon you fly. |

The rows are C5's six points: "3 days away" is the 70-hour point. The first line takes its two figures from the first and the last row. The delay line's figures are the delay measurement's 7.7% and 4.9%.

### Front page: the total

| Where | Words |
|---|---|
| Tiles | 6,115 flights · 104 cancelled · 1.7% |
| Sentence | Since 27 October, 104 of 6,115 flights at Ben Gurion were cancelled (1.7%). |
| Late cancellations | Some flights (at least 15 of the 104) were only marked cancelled after their scheduled time had passed. |
| Left out | 285 flights are left out because there's no record of how they ended. |

The total counts closed flights with a known result, as before (C2, C4). The late line counts as before: the model brackets each cancelled listing between two sightings, and the line counts the brackets that lie wholly after the scheduled time (A17). The two kinds of left-out flight (on this model, 240 that left the list while nothing was recorded and 45 that left it with no final status) move to "How this works".

### Flight page: the headline

One slot, under the traveller's day. Later the tested model fills the same slot (q28).

| Flight | Headline | The line under it |
|---|---|---|
| LO 155: a clean history, a flight ahead | **Chance it's cancelled: under 1%** · **Chance it's delayed an hour or more: about 1%** | Worked out from this flight's history (none of its 22 flights was cancelled), LOT's history, and how soon it leaves. |
| LH 694: one bad week, no flight ahead | **Chance its next flight is cancelled: about 15%** · **Chance it's delayed an hour or more: about 3%** | Worked out from this flight's history: 4 of its 14 flights were cancelled, all between 6 and 9 November. It hasn't been on the airport's list since. |
| LH 697: only 2 flights so far, no flight ahead | **Chance its next flight is cancelled: about 10%** · **Chance it's delayed an hour or more: about 5%** | Worked out mostly from Lufthansa's history, because LH 697 has only 2 flights so far. Lufthansa cancelled 11 of its 183 flights, all between 6 and 10 November. |
| A later day still ahead (LO 155 on 18 and 19 November), on the day itself | Chance it's cancelled: under 1% · Chance it's delayed an hour or more: about 1% | none of its own |

"Chance its next flight is cancelled" is my fix after round 4: under "LH 694 isn't on the airport's list right now", the reader asked what "it" was. The delay headline on these two pages is approved as it stands, "Chance it's delayed an hour or more: about 3%" (LH 694) and "about 5%" (LH 697): neither page has a flight ahead. Open is only whether that line, too, takes "its next flight" ("No approved words yet").

In the third line "only 2 flights so far" replaced "has flown only twice so far" in round 4: one of the two was cancelled, so it flew once.

### Flight page: the lines in smaller type

| Line | Words |
|---|---|
| This flight | **LO 155 so far:** 22 flights · none cancelled · none delayed an hour or more |
| | **LH 694 so far:** 14 flights · 4 cancelled · none delayed an hour or more |
| | **LH 697 so far:** 2 flights · 1 cancelled · none delayed an hour or more |
| Its airline | **LOT POLISH AIRLINES so far:** 127 flights · none cancelled · 2 delayed an hour or more |
| | **LUFTHANSA so far:** 183 flights · 11 cancelled · 7 delayed an hour or more |
| All airlines, by the time left | **All airlines at Ben Gurion, 6 to 12 hours before a flight:** under 1% cancelled · about 5% of arrivals delayed an hour or more |
| All airlines, no flight ahead, or scripts off | **All airlines at Ben Gurion:** 1.7% cancelled · about 5% of arrivals delayed an hour or more |
| Freshness | Updated 3 hours ago. Things may have changed, so check with your airline. |
| Link | What the numbers mean |

- The all-airlines line has six forms, one per stretch of time left: "2 to 3 days", "1 to 2 days", "12 to 24 hours", "6 to 12 hours", "3 to 6 hours" and "less than 3 hours", each followed by "before a flight:". Only "6 to 12 hours before a flight:" is approved (round 4). The other five are proposed, not approved: the round-4 mockup holds them, hidden, on the same pattern. Each form gives the figure of the point at its far end, so it leans high: 1.6%, 1.4%, 1.1%, then "under 1%" three times on the 2026-11-17 model. "Before a flight" was added in round 4: read aloud, "before" alone left the reader asking "before what?".
- A departure's page reads "about 8% of departures delayed an hour or more" (LH 697 on the mockup).
- The form without a time takes the front page's total, 1.7%.
- Without scripts the freshness line gives the date and time in place of the hours: "Updated 17 Nov at 09:46." and then the same second sentence. That line is composed from two approved ones: the no-script "Updated 17 Nov at 09:46" (`docs/site-redesign.md`, "Every page") and the freshness line.

### Flight page: the strip of days

| Where | Words |
|---|---|
| Heading | LO 155, day by day |
| Key | ● landed 22 · ○ upcoming 3 |
| Under each mark | the day of the month (26, 27, 28 …) |
| Each mark's name, for a screen reader and as a tooltip | Tuesday 17 November, upcoming |

The key counts the strip's own marks, so it matches them, and it names each kind of mark in words (LH 694: "landed 10 · cancelled 4 · unknown 1"). A month's name stands over the first mark of each month. The strip took the place of the summary line ("Since 27 October: landed 22 times, 3 upcoming.").

### Flight page: other situations

| Situation | Words |
|---|---|
| The flight's time has passed | This flight's time has passed. The page was last updated at 09:46, so it may not show what happened. |
| More than 3 days away | Your flight is more than 3 days away. Flights show up on the airport's list about 3 days ahead, so check back closer to the date. |
| Not on the list now | LH 694 isn't on the airport's list right now. The last one was on Tuesday 10 November. |
| Upcoming, already cancelled | **This flight is marked cancelled.** Contact your airline. |
| Also sold under another number | Also sold as LY 9255 (probably the same plane). |
| The same, two other numbers | Also sold as LY 9252 and LY 9255 (probably the same plane). |
| A number cancelled while its twin flew | This number was cancelled, but the flight probably left as LH 695. |

"Also sold as" names the partners of the 2026-11-12 rule: the other numbers of the flight under C1 that the list showed with the same expected time, terminal and check-in desks. The twin line is for a number marked cancelled whose flight is not (C2, C10). Both say "probably" because the grouping is inferred. "How this works" is where a reader learns why one flight has several numbers (section 4 of its outline).

### In lists

| Where | Words |
|---|---|
| A number whose own status differs from its flight's, in a list row | (LH 0691A: cancelled) |

The bracket still keeps a place name from following "cancelled", which the upload check would read as a banned phrase.

### What the numbers mean

The disclaimer. It is the first section of "How this works", and every page links to it: the footer's second line, and the link under a flight page's lines.

> **They're estimates from past flights.** Since 27 October 2026, this site has kept a record of every flight on Ben Gurion Airport's public list. A "2% chance of cancellation" means that among past flights like yours, about 2 in 100 were cancelled. It's not a promise about your flight.
>
> **How a flight's chance is worked out.** It starts from the flight's own history. When that history is short, it leans on the airline's history, and beyond that on all flights at Ben Gurion. Then it's adjusted for how soon the flight leaves, because the closer a flight gets, the less likely it is to be cancelled. This is a simple first version. A fuller one, with more factors and a public check of how accurate it is, is on the way.
>
> **Bad weeks come in bunches.** An airline can cancel many flights in a few days, because of a strike, a storm or a security alert. When one bad week is behind a flight's number, the page says when it happened.
>
> **"Cancelled"** means the airport's list marked the flight cancelled. **"Notice given"** is how long before the scheduled time that happened. The airline may have told passengers earlier.
>
> **"Delayed"** means the airport's own expected time was an hour or more after the scheduled time. Smaller delays aren't counted, because the airport doesn't say whether its times mean leaving the gate or taking off.
>
> **The pages aren't live.** Each page says when it was last updated. Your flight may have changed since, so always check with your airline.
>
> **Unofficial.** Flight data: Israel Airports Authority, published on data.gov.il. This site isn't run by, connected to or approved by them or the State of Israel.

### No approved words yet

Each item is a line a traveller would read, or a case that has no line. None is written here. Each waits for me ("Outside this design, for the owner").

1. **Whether the delay headline takes "its next flight".** On a page with no flight ahead the cancellation headline reads "Chance its next flight is cancelled" (my fix). The delay headline there is approved as "Chance it's delayed an hour or more". Open is only whether it, too, should say "its next flight".
2. **The "Worked out from" line beyond its three examples.** The approved lines cover a clean history with a flight ahead, one bad week with no flight ahead, and a number with 2 flights whose airline had one bad week. There are no words for: a flight ahead whose history holds cancellations that are not all in one week; a flight ahead whose history holds one bad week (what follows the dates, where LH 694's line says it has not been on the list since); a single cancelled flight; a clean history with no flight ahead (LO 155's line ends "and how soon it leaves"); a short history whose airline has no cancellation, or cancellations spread over several weeks; an airline with few flights of its own, where the airport's history carries the weight.
3. **A number counted with another airline's flights.** D11 says its page shows the record of the airline it is counted with, worded "counted with …". No whole line is approved, for the airline's "so far" line or for the "Worked out from" line on such a page (LY 9255, counted with LOT's LO 155).
4. **An airline's name inside a sentence.** The examples say "LOT's history" and "Lufthansa cancelled 11 of its 183 flights". The airport publishes "LOT POLISH AIRLINES" and "LUFTHANSA", and the "so far" line prints those. Nothing says how the short name is made for the other airlines.
5. **"Updated N hours ago" outside whole hours.** Approved: "Updated 3 hours ago". No words for under an hour, for one hour, or for a day and more.
6. **The "time has passed" line on an older page.** "The page was last updated at 09:46" gives a clock time with no date.
7. **The last day ahead passing by the visitor's clock.** With no later day to move up, nothing says what the slot shows.
8. **No flight ahead while the last one is still on the list.** A flight stays on the airport's list for about a day after its time. During that day "LH 694 isn't on the airport's list right now" would be untrue for a number with no next flight listed.
9. **The twin line's other cases.** Approved: "This number was cancelled, but the flight probably left as LH 695." No words for an arrival, or for a twin that is still ahead.
10. **Below the floor.** The total when it rests on too few cancelled flights for a percentage (C8), and the table's first line when its first or last row reads "Not enough flights yet".
11. **"How this works" after its first section and its opening paragraph** ("Pages").
12. **An airline's bad week where the flight's own history leads.** My terms reading says a page gives the dates when one bad week is behind a flight's or an airline's cancellations (`docs/terms.md`, clause 4). The approved lines give an airline's dates only in the "Worked out mostly from" form; the airline's "so far" line has none.
13. **Proposed on the mockup, not approved.** Five of the six forms of the all-airlines line ("Flight page: the lines in smaller type").

## Pages

Every page's order and frame are in `docs/site-redesign.md`, "Pages". This section says which figures stand where, how they are worked out, and what the scripts do.

### Front page

- "Find your flight" and the search box lead (`docs/site-redesign.md`). Then the table, then the total.
- The table: six rows from C5's points, each the share of the flights still on at that point that were cancelled later (C6, C7), as a percentage to one decimal. A row that does not clear C8's floor reads "Not enough flights yet". The table is plain HTML and needs no JavaScript.
- Gone from under the table: the range, the record line, the three explaining lines, the count line. What they said moves to "How this works".
- The delay line: for each direction, flights delayed an hour or more over flights that flew.
- The total: tiles, sentence, the late line and the left-out line.
- The story box, the recent cancellations, "Flights each day" and the day list follow, counted by C1 to C10 as before.

### Flight page

**Days ahead.** A day is ahead when its scheduled time is later than the page's last update, whatever its label, so a day already marked cancelled but not yet due stays at the top (the rule of the round-2 structure D10 took). The nearest day ahead is the traveller's day and stands at the top, once. The strip follows it. The later days ahead come after the strip, soonest first, then the past days, newest first. The build sets this order.

**The headline slot.** One slot under the traveller's day, closed by a heavy rule: the two chances, then the "Worked out from" line.
- The traveller's day is labelled UPCOMING: "Chance it's cancelled" and "Chance it's delayed an hour or more", from the blend for that day's time left.
- No day is ahead: the line "LH 694 isn't on the airport's list right now. The last one was on Tuesday 10 November." stands where the day would, and the headline reads "Chance its next flight is cancelled".
- The traveller's day is already marked cancelled: "This flight is marked cancelled. Contact your airline." and its notice sentence. On 2026-11-12 a cancelled row got no figures; whether the slot shows any here is not in my 2026-11-17 words ("Outside this design").
- A later day ahead labelled UPCOMING carries its two chances on the day itself, on one line, for its own time left, with no "Worked out from" line of its own.

**Under the slot, in smaller type.** The number's "so far" line, its airline's "so far" line, the all-airlines line, the freshness line and the link "What the numbers mean". Then what belongs to the traveller's day alone: "Also sold as …" and its "What changed" list.

**The strip.** One mark per day of the flight number, oldest first, each a link to that day on the page. The traveller's day's mark links to the top. A mark never rests on colour: its shape differs by label, the key names each shape in words with its count, the day of the month stands under it, and the link carries the day and the label as its name (`docs/site-redesign.md`, "Look").

**`fromhere.js` today.** It reads each block's scheduled time, which the build writes as a UTC instant in a `data-` attribute, compares it with the visitor's clock, and shows the one prepared sentence that fits the time left. Over 72 hours it shows the "more than 3 days" line; once the time has passed it hides the block and shows the "has passed" line. It writes no text and no number of its own. Both sides are UTC instants, so the visitor's time zone does not matter. All of that stands. After q27:

1. **The all-airlines line.** The page holds the six prepared forms; the script shows the one for the stretch the flight is in, with the bounds of 2026-11-12: over 48 and up to 72 hours, over 24 and up to 48, over 12 and up to 24, over 6 and up to 12, over 3 and up to 6, up to 3. Over 72 hours it shows "Your flight is more than 3 days away. …" in the line's place.
2. **A day that passes (D10).** When the traveller's day has passed by the visitor's clock, the script moves the next day ahead to the top, with that day's own chances and lines, and the passed day reads "This flight's time has passed. …". Uploads are by hand, so a page can be a day or more old when it is read.
3. **The page's age (D11).** The script writes "Updated N hours ago", in the line at the top of the page and in the freshness line, from the instant of the page's last update, which the build writes as a UTC instant in a `data-` attribute. This is the one exception to the rule that the script writes no text and no number of its own. Every other sentence and number is already in the page, where the upload check reads it.
4. **Without scripts.** The build's order stands. The age reads as a date and time, "Updated 17 Nov at 09:46". The all-airlines line shows its form without a time. The "more than 3 days" and "time has passed" lines stay hidden.

Whether the two chances also follow the visitor's clock is under "Left to the builder".

### Day pages, the chart, the cancelled-flights lists

Counted and grouped by C1, labelled by C10, as before. A row names every number of the flight, with the bracket for a number whose own status differs. A cancelled flight's notice follows C9. Their words are in `docs/site-redesign.md`.

### How this works

Plain words, written to the same reading test; "I" allowed as now. The page opens with the paragraph in `docs/site-redesign.md` ("Pages"). Its first section is "What the numbers mean". After that it keeps the outline of the plain-words proposal, and may say more for the curious reader than a traveller's page does:

1. What the numbers mean (the disclaimer; every page links here).
2. Where the information comes from, with the full source line.
3. How a flight's chance is worked out: the blend, its weights, and that they are not tested yet.
4. All flights by time left: who is counted and who is left out (C4, with the two kinds of left-out flight), one flight under several numbers (C1, C2), why three days is the limit, why the later rows hold more flights.
5. How sure the numbers are: the ranges of the airport's figures (C8) and, in the proposal's outline, of each airline's, in a table; why a flight number gets none.
6. What "cancelled", "delayed" and "notice" mean here.
7. What the labels mean.
8. Gaps in the records.
9. What is being tested next: the four named signs and their test, with the gate quoted in full, as on the built page. Its opening sentence there, "No figure is given for one flight yet.", becomes untrue and goes.
10. How it's built, for the technical reader, and the code link.

Only the opening paragraph and section 1 have approved words. Sections 2 to 10 on the built page were written for the 2026-11-12 rules, and several of their sentences become untrue (no delay figures; every figure a range; the labels' old names). Their new words, the form the ranges take there, and whether section 5 lists airlines side by side (the site's only table of airlines, against the non-goal of ranking them) are mine to approve.

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

What the data supports has not changed since 2026-11-12, except for delays. It supports a rate with its range for the airport as a whole, by time left; since the delay measurement, the share of flights delayed an hour or more, by direction; counts that say what they leave out (C2, C4); and counts for one flight number. It supports no tested figure by airline, route or weekday, and nothing about a bad day.

What changed on 2026-11-17 is what the pages say. A flight page now gives a chance for one flight. That chance is the blend: a first estimate with untested weights, and the pages say so ("This is a simple first version."). What keeps it honest is what my terms reading of the same day rests on (`docs/terms.md`, clause 4): every figure says what it is and what it rests on.

- A chance is an estimate from past flights, not a promise. Every page says so in its footer and links to "What the numbers mean", which defines "cancelled" and "delayed".
- A flight page that gives a chance says what it was worked out from: the flight's own history with its counts, its airline's history, and how soon it leaves. History lines give counts, not percentages.
- A chance is never "0%". A clean history reads "under 1%".
- When one bad week is behind a flight's or an airline's cancellations, the page gives its dates.
- Delays under an hour are never counted.
- Every page says when it was last updated, and a flight page tells the reader to check with their airline.
- A cancellation never gets a clock time. How much notice it gave is a range or a bound.
- The ranges behind the figures are on "How this works", not on the traveller's pages.

Two lines of that reading ask for more than the approved words give so far: "Updated" on every page, where the approved words name the front page and flight pages, and an airline's bad week with its dates wherever it bears on a chance. Both are under "No approved words yet" (the first in `docs/site-redesign.md`). Beyond the reading: the blend is compared with the last week before it ships, and the tested model, with a public check of its accuracy, takes its place (q28).

| | Public | Unpublished |
|---|---|---|
| Now (2026-11-12, as built) | The table and the total with their ranges; the counting method; the gate in full; the names of the four signs under test | Any figure for one flight; any sign's counts on the site; the test's running counts, which stay in local files |
| After q27 | A chance for each flight from the blend, with what it was worked out from; the flight number's and its airline's counts; the table and the total as percentages; delays of an hour or more; on "How this works", the blend, the ranges, the counting method, the gate in full and the names of the four signs | A sign applied to a flight; any sign's counts on the site; the test's running counts, which stay in local files |
| After the gate | The test's result either way (D6), with the lift and the scores; a split table for a sign that passed | A flight-page line for a sign, until the site is rebuilt on a schedule |

Whether the back-test's result is published is not decided ("Outside this design").

## The record

The idea tested for this design: the raw archive and its receipts are write-once and timestamped, so what a fixed, dated rule would have said about any listed flight at any moment can be recomputed later. Freezing the rule might then replace a daily job that freezes each day's figures.

The design's answer: it does, for the sign test, on three conditions.

**Condition 1. What is frozen is code in a tagged commit.** The frozen rule is the model code, rules C1 to C8, the four signs, the sign test with its score, the gate and the re-test, as tested code. The SQL in the figures file is documentation that the code is checked against; a tag on a document would freeze a description, not a rule. So the tag waits for that code (D5).

**Condition 2. A version survives housekeeping.** A later change starts a new version with its own tag and its own counting start, and the old version stays as it was. One exception, because the tagged code may stop being runnable: the model build stops on a snapshot with no receipt, an unknown receipt version or a misplaced receipt, and clearing each takes a code edit (`src/model/rules.py`); the counting code stops, naming them, on a number with no scheduled time, direction, airport, airline or flight number, or an observation with no scheduled time (`src/timeline/counting.py`; my call, 2026-11-12, where A0 leaves out a number with no scheduled time, direction or airport: a change in how the airport writes its times must stop the record, not drop every new flight unnoticed); the full build may also outgrow the machine. A change that only admits or drops named snapshots, or changes how the build is computed, continues the version when every figure for flights closed before the change is identical under both.

**Condition 3. Reading the model "as of" a moment must equal building it from the archive cut at that moment.** This is known not to hold everywhere, and is otherwise untested: UNVERIFIED. The known cases:
- The retime rule (R4) takes each key's last sighting over the whole archive (`link_retimes` in `src/model/rules.py`). A number that leaves the list and comes back is therefore treated as listed throughout, and a cut build can link a retime the full build does not. 7 numbers have left and come back so far (A20).
- R2's repeated store and R9's last sighting read one download ahead.
- The flight a number belongs to (C1) and its result (C2) are read at the end. That is right for counting results. It also decides which numbers' signs a flight carries, so a sign's reading for a number is as of the moment and its flight is not.

The first task of the plan is a test that cuts a synthetic archive at several moments and compares, with these cases in it: a number that leaves and returns, a retime at the cut, and a number whose flight changes after the moment. Where the two differ, the record has to be computed from cut builds. That means a build for every moment read, thousands of them, and neither the time nor the memory one build needs has been measured; the plan sizes it if the test fails.

**Measured and ruled, 2026-11-12** (the plan's Task 1). The test found the known cases and one more: a build cut while a collection gap is still going on cannot know it is in one, which matters only to a record computed from cut builds. On the model of 2026-11-12, reading a moment by A0's rule and reading it as what the last download before the moment showed give the same table: no flight enters or leaves any row, although A0's rule uses the next download to know that a number had left. The differences from cut builds are the cases listed above. 7 checkpoint moments of the 7 numbers that left the list and came back fell while they were off it, so a cut build would leave those flights out of those rows: at most 3 flights in a row, none of them cancelled. A cut build would also link 3 of those numbers as retimes, at no checkpoint moment. C1's inputs read at the end are compared in the plan's Task 6. A record from cut builds would take about 86 builds per Israel day, about 124 to 365 hours of machine time over 60 days on this machine. My call: the record reads the full model by A0's rule, with these differences as its stated limits, and is not computed from cut builds. Apart from the table, these figures were measured once by the build and not rechecked: UNVERIFIED.

What counts. The counting start is an Israel midnight written into the tagged commit, later than the moment the tag is pushed. Nothing about a counted flight was visible when the rule was fixed.

When a later run differs. Each run reads the archive as it stands then, so a run after the gate can give a result other than the stored one: through the limits under condition 3, or through housekeeping under condition 2. The first stored result stands and is the one published. A later run that differs is shown beside it, with its cause, and never replaces it (my call, 2026-11-15). The code keeps the stored result as it is, prints both and fails (`main` in `src/timeline/record.py`).

What makes the freeze checkable. The tag is public, in the repository this site links to. The archive is private, so a reader cannot recompute the record either way; a daily file in a private bucket would be no more checkable than a tag. What a reader can check is that the rule existed before the flights it was scored on. CI runs on every push with no filter (`.github/workflows/ci.yml`), so pushing the tag starts a public run that the hosting service dates itself. The tag `record-v1` was pushed on 2026-11-15 at 06:31:08 UTC, and GitHub started CI run 43685805035 for it (created 06:31:09 UTC, conclusion success).

What it does not replace. Telling a traveller which half of a split their flight is in needs a fresh build, because it depends on what the list shows now. That is the scheduled rebuild (q23), needed when a sign has passed and not before.

## Keeping the figures current

Uploads are by hand (`docs/publishing.md`). After q27 the pages stay true between them this way:

- The table and the total are a record up to a stated moment. An old upload shows an older record, not a wrong one.
- The front page and every flight page say how old they are: "Updated N hours ago", worked out on the visitor's clock; without scripts, the date and time of the update.
- "How long until the scheduled time" comes from the visitor's clock, not from the upload.
- When a day passes by the visitor's clock, the next day ahead moves to the top.
- The freshness line sends the reader to their airline ("Things may have changed, so check with your airline."). The 2026-11-12 line sent them to the airport's own list.
- A flight listed since the last upload has no row on its number's page. The front page's table still serves that traveller, and the search's "No flight found" line says that flights show up about 3 days before they leave.

A fresher site is outside version 1. It needs q5 first, then q2 and q23, each on the owner's go; `docs/data-model.md` already makes the incremental build the precondition, and how much memory the full build needs today has not been measured. Frequent uploads are not free with today's script: at 15-minute uploads, about $16.47 a month in upload requests and 2,880 invalidations against 1,000 free (A34; prices from `docs/publishing.md`, not re-read; the price of an invalidation beyond the free ones is not in the repository: UNVERIFIED). That estimate belongs to q23's design.

## How it is built

- The same pipeline: `python -m timeline.build --model data/model --out site`, pure functions from rows to HTML, the marker-file swap, `timeline.check` before upload, `scripts/publish.sh`.
- Counting (C1 to C10), the "as of" reading (C6) and the signs are one new pure module beside `flights.py`, which stops grouping by codeshare group and calls it. The pages and the sign test share it.
- The range (C8) is one pure function: counts per group in, rate and two ends out. No random numbers, so the same model still gives the same bytes.
- `words.py` gains the sentences and the rounding; `views.py` the table, the block and the tile's range; `check.py` the rules below.
- `fromhere.js` is the second script on the site. It selects a prepared pair and nothing more.
- The sign test is a separate entry point that reads the same module and writes a local report. The tag of D5 is the first commit in which it runs.
- Cost: no new AWS service, as at the top; an upload stays about half a cent.

### What q27 adds (not built)

- The blend is one new pure module beside `flights.py` and `display.py`. It reads the frozen modules' flights and results (`counting.flights`, C1 and C2) and the table's rows (`counting.figures`), and adds its own counts per flight number and per airline: flights, cancelled, delayed an hour or more. It is not a frozen file, and no frozen file may import it; `tests/test_frozen.py` already fails when a frozen module imports another module of the site.
- No frozen file changes: `src/model/`, `src/timeline/load.py`, `counting.py`, `rates.py` and `record.py` stay as tagged. If the build finds it needs a change there, it stops and asks me ("The record", condition 2).
- A flight's delay is read as the delay measurement read it: the model's `est_minus_sched_min` of its numbers that departed or landed.
- `words.py` gains the new sentences, the rules of "How numbers are written" and the notice sentences. `views.py` gains the new order, the slot, the strip and the lists. `check.py` takes the rules below.
- `fromhere.js` gains the move of the next day ahead and the "Updated" line. `search.js` writes its two new lines (`docs/site-redesign.md`, "Pages").
- The back-test is a separate local entry point, like the figures check: it needs the real model, which is not in the repository.
- Same model, same bytes, as before: the blend uses no random numbers and no clock. The page's age is worked out in the browser.
- Cost: no new AWS service. The font files are costed in `docs/site-redesign.md`.

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

The lists above stand: the counting, the range and the sign test are frozen. The lists below are rewritten for q27.

The blend:
- Hand-computed cases: a number with no flights takes its airline's rate; an airline with none takes the airport's; each pull at its weight (14 and 100); the scaling by each of the six rows; a delay is not scaled.
- A clean history gives a chance above zero, and no page prints "0%" as a chance.
- Which flights are counted ("Left to the builder"), with a flight on each side of the line.
- A mutation for each weight, for swapping them, for dropping the scaling and for scaling a delay.
- A synthetic fixture with hand-computed chances, in CI. The back-test runs on the real model, locally and not in CI; its code is tested on a synthetic archive in which the last week is known.

How numbers are written:
- Just under and at 1% ("under 1%", "about 1%"); whole numbers in a headline; one decimal in the table; the halves; never "0%".
- The six stretches of the all-airlines line and their figures; "under 1%" in the line where the table prints 0.8%.

Words and pages:
- One exact-text test per sentence in "Words", in each of its forms.
- The slot: on a page with a day ahead, with none, and with a day ahead already marked cancelled. A later day ahead carries its chances and no "Worked out from" line.
- The counts agree: the "so far" line, the "Worked out from" line and the strip's key give the same number of flights (LO 155's shape: 22).
- A bad week: cancellations inside one week name its dates; spread wider, they do not.
- The table: a row below the floor reads "Not enough flights yet". The chart's counts equal the day pages'. Over days whose flights are all closed, the day pages' cancelled and known-outcome counts sum to the total's for those days.
- The scheduled instant and the update instant written for `fromhere.js` equal the model's UTC times, tested under an Israeli time zone (the naive-conversion trap noted in `docs/timeline.md`).
- Same model, same bytes.

`fromhere.js`, run under Node as the search test is:
- each boundary between the six stretches; more than 72 hours; a passed time;
- a passed day with a later day ahead: that day is at the top with its own lines; two passed days; the last day ahead passed;
- "Updated N hours ago" from the update instant, the same under three time zones; an unreadable instant leaves the date-and-time form standing;
- the script writes no text but the "Updated" line (today's test fails on any text written, and is rewritten to allow that one);
- a missing or unreadable attribute leaves the no-script page standing.

The upload check. What `src/timeline/check.py` does today, and what q27 changes:

| Rule today | After q27 |
|---|---|
| Banned phrases (`BANNED`: "cancelled at", "canceled at", "delayed by", "operated by", "took off", "minutes late", "hours late", "pause in our collection"), in every `.html`, `.css` and `.js` file, as written and with tags stripped | Unchanged. The approved words are written round them: "Cancelled with at least 21 hours' notice." and not "cancelled at least". |
| The built-by placeholder is refused | Unchanged |
| "we", "our", "us" as whole words, in every file | Unchanged |
| "I" as a whole word outside `how-it-works.html` and the built-by line | Unchanged |
| "board", "snapshot", "stored", "observed", "receipt" and their plurals outside `how-it-works.html` | Unchanged |
| The odds words (`ODDS_WORDS`: chance, chances, odds, probability, probable, likely, unlikely, risk, risks, risky, forecast, forecasts, forecasting, predict, predicts, predicted, prediction) outside `how-it-works.html`, after the airport's own strings are skipped | "chance" and "chances" are allowed: the headline says "Chance it's cancelled" and the footer "The chances on this site". My decision names only "chance", so the other words stay refused on a traveller's page (a reading: "Left to the builder"). |
| A percent sign in the text of an HTML page | Allowed |
| Every "1 in N" in a page's text is followed at once by "(between 1 in A and 1 in B)", or sits inside such a range | The plain-words proposal meant a twin rule, every percentage with its base, to take this rule's place, and D11 recorded that twin; it is not carried (under this table). No traveller's page prints "1 in N" any more. Recommended: this rule is kept, so that a "1 in N" on "How this works" still carries its range. |
| A page whose text holds "1 in N" must hold the record line (`PAST_ONLY`) | The record line leaves the pages. Recommended: this rule goes, and the footer's second line ("The chances on this site are estimates from past flights, not promises.") joins the lines required on every page. |
| The source line and the unofficial line on every page; the full source line on `how-it-works.html` | The rule stands. The unofficial line's fixed words change to the approved footer's (`docs/site-redesign.md`, "Footer"), so a page built before the change fails, as the check intends. |
| No rule | New: a flight page whose text holds a chance must hold a "Worked out from" line. The rule is per page, not per chance: a later day ahead carries chances with no line of its own. The front page's table needs none. |

Two check rules that D11 recorded are not carried. "Thresholds enforced" (no flight's own percentage under 14 flights, no airline's under 100): D12 replaced the thresholds with the blend's weights, so no threshold is left to enforce. "Every percentage has its base": the approved words' own list of the check's changes ("chance" allowed, a percent sign allowed, the "Worked out from" line, the banned phrases kept) leaves it out, and approved lines carry no base beside them ("Chance it's cancelled: about 15%"; "under 1% cancelled · about 5% of arrivals delayed an hour or more"). What a chance rests on is said by its "Worked out from" line, which the new rule requires.

Its tests:
- "chance" and "chances" pass on a traveller's page; "odds" and "likely" are still refused there; `how-it-works.html` stays exempt.
- "1.7%" in a page's text passes. The two tests that refuse a percent sign are retired.
- A flight page with "Chance it's cancelled" or "Chance its next flight is cancelled" and no "Worked out from" line is refused; with the line it passes; so does one with a later day's chances beside one line.
- A page with the 2026-10-30 unofficial line fails.
- Lines that come near a banned phrase pass: "Cancelled with at least 21 hours' notice." after the label CANCELLED, and a list row that reads "(LH 0691A: cancelled)" before "to Athens".
- A mutation for each rule.
- Not checked by the upload check: the text `fromhere.js` writes on the page. The check reads the script file itself for banned phrases and pronouns, and the Node tests pin the text it writes.

## Five outsiders (q13)

The script in `docs/timeline.md` quotes v1's words, and the tasks I approved on 2026-11-12 quote "1 in N" with its range. Both have to be rewritten for the new pages. Proposed for this update, not approved:

Tasks, the owner watching and saying nothing:
1. "Your daughter is flying tomorrow afternoon. Here is the site, on your phone. Tell me what it tells you about her flight." (A flight scheduled about a day ahead is picked just before the session.)
2. "What does 'Chance it's cancelled: about 15%' mean? Say it in your own words." (On the page of a number with one bad week, picked before the session.)
3. "How old is what you are looking at, and how do you know?"
4. "Is there anything you would do differently after reading this?"
5. "What is this site, who made it, and what do you think that person can do?"

What to watch for:
- Reading a chance as a promise about the flight, either way: "under 1%" as "it will fly", "about 15%" as "it will be cancelled".
- Reading a bad week's figure as what will happen next time, or missing the dates in the line under it.
- Taking the page as live, or missing "Updated N hours ago".
- Skipping the "Worked out from" line, or not following it.
- Reading "delayed an hour or more" as any delay, or mixing it with the label DELAYED.
- Reading the all-airlines line ("6 to 12 hours before a flight: under 1% cancelled") as cancelled during those hours.
- Pausing on any line read aloud. Each pause is noted with its line: this is my reading test, run on real readers.
- Taking the page as official.
- Not finding the flight, or concluding that a flight more than three days out is safe.

The stop rule is decision D9, approved on 2026-11-12 for the table: if two or more of five read the rate as a promise about their own flight, the words change before launch or the table moves below the total. Its remedy no longer fits a page that leads with a chance. Proposed in the plain-words proposal, not approved, and waiting for me: stop if two of five think the page is live, or read a bad week's figure as what will happen next time. Until I rule, D9 stands as written.

## The launch post's figure

The post's drafts hold older numbers and the "1 in N" form. The figure to quote is still the table's row for one day before the scheduled time, now as the page prints it: of flights still on 1 day before, the share cancelled later. On the 2026-11-17 model: 52 of 4,892, 1.1%. The figure moves with every upload, so the post takes it from the live front page on the day it goes out. The post waits for the redesign (my call, 2026-11-17).

## Left to the builder

Markup and CSS within the look rules of `docs/site-redesign.md`; how the table stacks on a phone; how the six prepared pairs are hidden and shown; module and function names; the order of sections on "How this works"; lines for this document and its figures file in `docs/README.md`.

For q27, each with a recommendation. None adds or rewords a sentence a traveller reads; where one would, it is under "Outside this design".

- **Which row scales a chance.** Recommended: the nearest point at or above the time left, as on 2026-11-12 and as the examples have it; the 70-hour row above 70 hours and on a page with no flight ahead.
- **At which moment.** The time left shrinks as a page ages, and the curve falls with it: LH 694's example runs from 15.4% on the 70-hour row to 4.3% on the 3-hour row. Recommended: the page holds the two chances once per row still ahead of the flight at the last update, and the script shows the pair for the visitor's clock, as it does the all-airlines line; without scripts, the pair for the time left at the last update. The cheaper way is one pair, for the time left at the last update: on this model's curve, which falls all the way to the flight's time, it never reads low, and on an old page it can read several times too high.
- **The weight of prepared figures.** If the two chances are held once per row, a day ahead carries up to six pairs. Recommended: only the rows still ahead of that day at the last update; the plan measures the largest flight page before and after, and reports it. For scale, a round-3 mockup that held six prepared sentences on each of three days ahead weighed 36,611 bytes against the built page's 27,557 (the designer's measurement).
- **Which flights a "so far" line and the blend count.** My words rule: each flight whose ending is known, so that the line, the "Worked out from" line and the strip agree. That is wider than C4's closed flights (LO 155: 22 against 20). Recommended: the number's and the airline's counts follow the words rule, so that a chance is worked out from the counts the page shows; the airport's rate stays the frozen total, the figure the front page shows and the curve divides by. The cost: a flight ahead that is already marked cancelled is counted before the other flights of its hour, which leans an airline's rate high for up to three days. The other way, counting a flight only once its scheduled time has passed, removes that lean and breaks the agreement only on a page with a cancelled day ahead. The back-test is the check on either.
- **The delay's parts.** Recommended, as the examples have them: the airport's delay rate is the direction's own; every delay count is over flights that flew, the 14 and the 100 added flights included; an airline's delay count covers both directions.
- **A flight number's airline.** Recommended: C8's grouping airline of the flight the headline is for: the traveller's day, or the latest day when none is ahead.
- **Which airline on a later day ahead.** A number's partners can change from day to day, and with them the airline C8 groups its flight under. Recommended: one airline per page, that of the traveller's day at the last update, for the "so far" line, the headline and every later day's chances. A page then names one airline, and a day that moves to the top brings no new one.
- **A number's record: per number and direction.** A flight page is one flight number and one direction, and its strip shows that page's days. Recommended: the number's counts are those days, so the "so far" line, the "Worked out from" line and the strip agree. A number that runs both ways then has two records.
- **The airline's counts and the number's own flights.** Recommended: the airline's counts are its whole counts, the number's own flights included, so that a chance is worked out from the count the airline's "so far" line prints (Lufthansa: 183). The cost: a number's own flights weigh twice, once in each pull, which matters only for a small airline.
- **The delay chance rests on flights that flew.** The cancellation chance counts every flight with a known ending; the delay chance counts only those that flew. It is the chance of a delay if the flight flies, and the two chances do not share a base. Recommended: kept, as the examples and the delay measurement have it, and said on "How this works" where "delayed" is defined (its words are mine to approve).
- **"Worked out mostly from" the airline.** Recommended: when the number has fewer than 14 counted flights, the point below which the airline's part outweighs its own. LH 694 at 14 reads "from this flight's history"; LH 697 at 2 reads "mostly from Lufthansa's".
- **When a bad week is named.** Recommended, from the plain-words proposal: when all of a record's cancelled flights, two or more, fall within 7 days.
- **Which days carry chances.** Recommended: days ahead labelled UPCOMING, as the 2026-11-12 block did.
- **A row below the floor.** Recommended: the scaling uses the nearest earlier row that clears it, and none when no row does; the all-airlines line for that stretch is left out.
- **Rounding.** Recommended: to the nearest, halves up, as C8 rounds; whole numbers above 10% as below it; "under 1%" for every value below 1, whatever it would round to.
- **"About 5,000 flights."** The six rows hold 4,472 to 5,195 flights. Recommended: the mean of the rows shown, to the nearest 500.
- **"It's about the same however soon you fly."** Recommended: the build stops, naming the row, when a row's delay rate differs from its direction's overall rate by more than a point, so the sentence cannot outlive its truth unseen.
- **The back-test's mechanics.** Recommended: the last 7 Israel days of closed flights; the blend's counts cut at the start of that week; each flight's chance on the 24-hour row; the report gives expected against actual cancelled and delayed flights, in all and for the tenth of flights the blend put highest.
- **The upload check's three readings** ("Tests and checks"): the other odds words stay refused, the "1 in N" rule stays, the footer's second line is required on every page.
- **The scripts.** Which script writes "Updated N hours ago" on the front page, which loads only `search.js` today; how the prepared lines are hidden and shown, and how the no-script page is left standing without the stylesheet's `:has()` rule the mockups lean on; the wrapper the search script shows, so that the label and the hint never show without the box; where a passed day's lines go once the next day has moved up (recommended: to the head of the past days, under its "time has passed" line).
- Module and function names for the blend; where the back-test's report is written.

## Suggested, not in scope

- A line on when cancellations are first listed (how many inside the last 12 hours).
- The table by direction, once each direction clears the floor in every row.
- A fifth sign for a bad day at the whole airport. It cannot be tested until the record holds one.
- Uploading only changed files.
- Publishing the derived tables, so a reader could recompute the record.
- A "when is your flight" picker on the front page.
- A check that refuses a bare "0%" in a page's text.
- Marking today in the strip by the visitor's clock.
- A cut-off for a long strip. It wraps; the round-2 designer measured 14 marks a row on a 390 px phone.
- Splitting the delay line at three hours. The delay measurement has it: departures 6.7% delayed 1 to 3 hours and 0.9% 3 hours or more; arrivals 3.9% and 0.9%.
- One bar for the all-airlines line (flew within an hour of schedule, delayed an hour or more, cancelled). Its three parts would have to be counted on one set of flights.

## Outside this design, for the owner

- The tag and its push (D5), and confirming that the push starts a dated public run.
- The order q5, q2, q23.
- The terms reading: done. `docs/terms.md` records my reading for rates over past flights and, since 2026-11-17, for the "Will It Fly?" pages (its clause 4 paragraph).
- The five sessions (q13) and the launch post.
- q3: what the airport's expected time measures is still unconfirmed. Since 2026-11-17 delay figures no longer wait for it: they are shown at an hour or more, with the disclaimer.
- The README's counts and screenshots after the first upload.

For q27:
- Every item under "Words", "No approved words yet", and its twin list in `docs/site-redesign.md`. The plan cannot build those lines until they have words.
- D9's stop rule ("Five outsiders"): the proposal waits for my yes or my own rule.
- The back-test: what "badly off" means, and whether its result is published. Recommended: the comparison comes to me before the first upload and I judge it; no pass mark is frozen for a first version.
- A day ahead that is already marked cancelled, or that the airport removed early: whether the slot shows chances. Recommended: none, as on 2026-11-12.
- A number marked cancelled on a day its flight flew under another number (16 numbers in 14 flights on the 2026-11-12 model, A13). Its strip shows that day as cancelled (C10: a number's own page keeps its own label), while the site's one counting method counts the flight as flown (C2, D4). Which of the two its "so far" line and its chance follow changes its figures, and the words rule that the counts agree cannot hold both ways. Recommended: the flight's result (C2). A listing that its flight flew past is then no cancellation, as everywhere else on the site, and such a number's chance is not raised by days on which the flight flew. The cost: on these pages the "so far" line counts fewer cancelled days than the strip marks, and the twin line under each such day is what explains it.
- The two meanings of "delayed": the label DELAYED and "delayed an hour or more" (`docs/site-redesign.md`, "Labels").
- The name. A bootcamp demo called "Will it Fly??" predicts delays; noted when I chose the name.
- `README.md`, `docs/README.md`, `docs/publishing.md` and the q13 script in `docs/timeline.md`, which this update leaves behind it.
- Whether the round-4 mockups go into the repository, as the 2026-10-30 ones did.

## Unverified

- The size of the differences between the record and cut builds, apart from the table, and what cut builds would cost: measured once by the build ("The record", condition 3, "Measured and ruled").
- The upload price, the free invalidations and "every build rewrites every file" come from `docs/publishing.md`; the 1,040 files are the local build of 2026-11-04. None was re-read from AWS. The price of an invalidation beyond the free ones is not in the repository.
- How much memory the full model build needs.
- Whether a number listed as cancelled inside a flight that departed or landed is a second listing or a second aircraft, whether ASY 991 and UN WZ932 are mis-keyed listings, and whether the 23 pairs with different expected times are separate aircraft (C1). The list does not say.
- Whether the 29 flights that left the list with no final status were cancelled.
- The simulation (A31) assumes today's rate, pace and group sizes continue, and that runs come by airline and week only.
- The outside review's gate is quoted from notes kept outside the repo.
- The delay measurement was run once, on 2026-11-17, with the frozen counting code. Its output was read for this update and not rebuilt.
- The counts in the examples (LO 155, LOT, LH 694, LH 697, Lufthansa) and "292 of 1,044 flight numbers" come from the mockups and the plain-words proposal, not from a query run for this update.
- That the mockups' rough first blend is the rule written here rests on three values that the rule reproduces (0.25%, 0.27% and 1.2% for LO 155) and on the three headline figures. No source states the four readings they imply.
- Whether weights of 14 and 100 suit a three-week record. The back-test is the first check.
- That "First on the list at 09:32" and "Landed around 19:55" answer two lines the round-4 reader still paused on is a reading of my approval, which records the phrases and not their place (`docs/site-redesign.md`, "No approved words yet").

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

## Update (2026-11-17)

A Fable agent brought this document and `docs/site-redesign.md` to my three decisions of 2026-11-17 (D10 to D12), from the approved words, the round-4 mockups and the three fixes after them. Figures were re-read from that day's local build and the delay measurement; the examples' arithmetic and the font files' sizes were computed for the update. Nothing of it is built.

Review, 2026-11-17. A fresh Opus reviewer read both documents against their sources. Each finding was checked against the files before it was folded in:
- The terms reading was already recorded (`docs/terms.md`, my reading of that day); both documents had it as still to do.
- The delay headline on a page with no flight ahead was listed as open. It is approved; only its "its next flight" form is open.
- Where "First on the list at 09:32" and "Landed around 19:55" stand was written as fact. It is a reading that awaits my confirmation.
- Two check rules of D11 were dropped without a reason. The reason now stands beside the check's table.
- "What is honest now" was rewritten inside a frozen section without the status line saying so, and the C5 note did not say that the approved all-airlines line names a stretch.
- Lines taken from the mockups, or composed from approved forms, were not marked as such.
- "I redesigned the site" claimed agents' design work for me.
- Five builder-level gaps in the blend had no entry, and one that changes a figure had no recommendation.
