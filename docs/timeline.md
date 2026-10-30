# History timeline (q7)

Grade: product v1 on a production-lean generator. The generator is deterministic and tested like the model; the pages are plain, accessible HTML. The site is built and viewed locally. Publishing it, or handing out copies, is a separate decision for the owner (see "Publishing").

The redesign (q18, 2026-10-30) replaced v1's pages, words, build and tests: `docs/site-redesign.md`. This file keeps v1's goals, the partial-day rule, the publishing reasoning and the review history; where the two differ, the redesign holds.

## What it is and why it comes first

A static website built from the model's tables. Since the redesign: which flights the airport's list showed as cancelled and how much warning each got, a page per flight number with every day it was scheduled and what changed, and a page per day. v1 was a page per date: pick a date, find a marketed flight number, and see every change the public board showed for it, with a methodology page for the rules. Every page cites the source.

It comes first because it uses what only an archive has: the history that the live board drops about a day after each flight. The outside review (change 3 of the second outside review, whose notes are kept outside the repo) names its readers as technical reviewers and data journalists, and asks to watch five outsiders use it before building anything bigger.

## Goals (v1)

- One page per local scheduled date: every row of the model's `flights` table (one per marketed flight number and retime chain) whose final scheduled time falls on that date, departures and arrivals apart, in scheduled-time order. Counts say "flight numbers listed", never "flights" (about 640 numbers for about 370 aircraft movements a day).
- A day whose board window the archive does not fully cover is labelled partial, on its page and on the index: the first check came after the day's start plus 22 h (the shortest time the board keeps a past flight), or the last check before the day's end minus 72 h (how far ahead it lists).
- Per flight: a summary line that opens into its timeline.
- Find a flight by number with the browser's own find, or with a small search box when JavaScript is on.
- A methodology page and attribution on every page.
- `python -m timeline.build --model data/model --out site` rebuilds the site; the same model gives the same bytes.

## Non-goals (v1)

- Delay figures of any kind: what the estimated time (CHPTOL) measures is unconfirmed (q3). The page shows it as "estimated time, as published".
- Rankings, statistics pages, forecasts, an API, downloads of raw or derived data.
- Live updates; the site is as fresh as the last local build.
- A Hebrew interface (Hebrew status and city names appear beside the English, marked right-to-left).
- Its own definition of collection gaps. The model owns gaps (R4, R7, R8 use snapshot spacing); the page shows the model's and follows when the model switches to receipts (OPEN_ISSUES, "Collection gaps ignore unchanged receipts").
- An A to Z index of flight numbers (600 links a day; find and the search box cover it).
- Hosting, and handing out copies (see "Publishing").

## Anti-goals (a failure even if it works)

- Wording that claims more than the board showed: "cancelled at", "delayed by", "operated by", "took off", or a first sighting by us presented as the flight's first listing. v1's only cancellation claim was "first observed CANCELED on the public board", with its bracket; the redesign keeps its substance in plain words (`docs/site-redesign.md`, "Words").
- Anything that looks like the official board or the Israel Airports Authority: no IAA name in the title, no logos, an "Unofficial; not affiliated with or endorsed by the Israel Airports Authority, data.gov.il or the State of Israel." line on every page (clause 8 of `docs/terms.md`).
- A flight silently missing: every `flights` row appears on exactly one day page; a row with no final scheduled time stops the build (none exist today).

## Pages

Replaced by the redesign: `docs/site-redesign.md`, "Pages".

## Wording

Replaced by the redesign: `docs/site-redesign.md`, "Words".

## How it is built

Replaced by the redesign: `docs/site-redesign.md`, "How it is built" (the marker-file swap: `write_site` and `refuse_foreign` in `src/timeline/build.py`).

## Tests and mutation checks

Replaced by the redesign: `docs/site-redesign.md`, "Tests and checks".

## Five outsiders (from the review)

Observed sessions with the owner watching, not a copy handed out: the point is to see where people misread. Tasks: "find IZ 991 on 29 October and tell me what happened to it", "find a flight that was cancelled and say when that was announced", "is there anything here you would use, and for what?". Watch for: misreading "first observed CANCELED" as the cancellation time, misreading "listed together" as the same aircraft, not finding a flight. The review's stop rule: if fewer than two of five name a real use, keep the collector and the case study and stop product work. The tasks and the watch list quote v1's wording; rewrite them before any session (`docs/site-redesign.md`, "Outside this design").

## Publishing (q15, owner's call)

The owner reads the terms as allowing it (`docs/terms.md`, read 2026-10-29): the pages are derived per-flight timelines with the source cited, and the wording rules keep them from misleading. The owner chose to publish before the model's gaps come from receipts (q14, 2026-10-29): the gap wording already names both causes (v1's; the redesign's says only that there are no records for that time), and no board has yet stayed unchanged between two downloads.

The owner picked S3 + CloudFront (2026-10-29): a few cents a month at most. (A second reason given then, that the repo could stay private, lapsed when the owner chose to make the repo public, q16.) Options as priced that day for under 1 GB and about 1,000 page views a month:

- A private S3 bucket in il-central-1 behind CloudFront, in this account, on the default cloudfront.net address: well under a cent a month for today's 2.4 MB site, at most about $0.03 for a site near 1 GB; a custom domain would add its own cost. S3 storage is $0.025 per GB-month (AWS price list for il-central-1, published 2026-10-15); CloudFront stays inside its always-free 1 TB and 10 million requests a month (CloudFront FAQ). CloudFront's flat-rate Free plan ($0, 1M requests, 100 GB) is the other way; whether this account qualifies needs a console check.
- GitHub Pages: free from a public repo. From a private repo it needs a paid plan (Pro; its current price is unconfirmed), and the site is public either way.

## Cost

Nothing new in AWS: the build is local and reads the local model. Hosting: see "Publishing".

## What to know

- Publishing per-flight history is the step that turns a private archive into redistribution; the terms were read on 2026-10-29 (`docs/terms.md`).
- Three clocks meet on every page: board times (Israel wall-clock, no offset), our times (UTC, shown as Israel time) and the clock change on the last Sunday of October. The naive-conversion trap is real on this Mac and invisible on CI, so it is tested under an Israeli time zone.
- The board's words are not facts about the flight. DEPARTED is the board's status, not a take-off time; a flight that vanished was not necessarily cancelled; our first sighting is not the flight's first listing (most flights so far were first seen at the archive's start or right after its 42-hour hole).
- "Listed together" is an inference from the same slot, estimated time, terminal and counters; arrivals with no counters can merge two real flights (OPEN_ISSUES, Model).
- The first days are partial: the archive began on 27 October and had a 42-hour hole.

## Design review (2026-10-29, Opus; Fable was over its limit and gates shipping)

Accepted: wording fixed for first sightings, `dropped`, `vanished`, negative leads and cancellations followed by another status; partial days; gaps left to the model, in neutral words; no zip before the terms are read, observed sessions instead; anchors always in full form from the first scheduled time and airport; a same-number line; Israel-time conversion with explicit UTC, tested under an Israeli zone; "between X and Y" after a long pause; counts as flight numbers listed; search keys built in Python, no Node in CI; a session plan with the stop rule; a safe `--out`; determinism across processes; case-insensitive banned phrases and exact sentences per case; stored boards, not checks; right-to-left Hebrew; a stop on a missing scheduled time; `--cov=timeline`; no A to Z strip; one attribution constant.

## Code review (2026-10-29, Opus; Fable was over its limit)

Fixed: anchors carry the first scheduled date (a retime past midnight beside the next day's flight of the same time stopped the whole build); the lead time uses both ends of the bracket, so "less than an hour" and "after" are said only when both ends support them, with "before" and "around" otherwise; the censored sentence no longer assumes a pause in collection; "partial" and the methodology now say only what the code checks (some flight numbers may be missing); a flight cancelled again says so; the vanished statistic from the early sample is gone; "last stored" instead of "last check"; the number alone is a search key ("991"); `<out>.building` and `<out>.old` are touched only with the marker, and the swap moves the old site aside first; tests and mutation entries for the five behaviours no test caught (the retimed label, the between threshold, pauses only on the days they touch, partial on the index, the footer's last-seen time); the clock-change test runs under an Israeli zone.

## Handoff review (2026-10-29, Opus; the owner's Fable waiver covers q7)

Fixed: the `gap` outcome, the index heading and the methodology no longer blame our collection for a stretch the board may have caused ("pause in our collection" joins the banned phrases); the model stops when a snapshot from after receipts began has none (`RECEIPTS_SINCE`); the swap's docstring says a crash can leave neither site for a moment.

## Deviations

- **The index says what its counts are.** The first build put "Flight numbers listed" only in a column header; the test for counts caught it, and the index now says that counts are flight numbers, a flight sold under several numbers counting once per number.
- **Four guard tests beyond the plan**: a retimed flight's anchor uses its first scheduled time; an anchor does not change when the same number appears again; two flights sharing an anchor stop the build (through `render`); a search query that tells "starts with" from "contains" (`york`). I wrote then that a valid model cannot produce a shared anchor; the code review showed it can (a retime past midnight), and anchors now carry the date.
- **One folder check, `refuse_foreign`**, called before any work and again before the swap.
- **The site on real data** (21 boards, 27 to 29 October): 7 day pages, 3,018 flight numbers each on one page, 2.3 MB; 26 October and 1 November are partial; 31 October's low count is a Saturday, not a gap.
