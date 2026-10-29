# History timeline (q7)

Grade: product v1 on a production-lean generator. The generator is deterministic and tested like the model; the pages are plain, accessible HTML. v1 is built and viewed locally. Publishing it, or handing out copies, is a separate decision for the owner (see "Publishing").

## What it is and why it comes first

A static website built from the model's tables. Pick a date, find a marketed flight number, and see the flight's story on the public board: every change to its status, estimated time, terminal and check-in counters with when we first saw it, retimes, the other flight numbers listed in the same slot, pauses in collection, and how its board story ended. A methodology page explains the rules and their limits. Every page cites the source.

It comes first because it uses what only an archive has: the history that the live board drops about a day after each flight. The outside review (change 3 of `reviews/review-2026-10-29-round-2.md`) names its readers as technical reviewers and data journalists, and asks to watch five outsiders use it before building anything bigger.

## Goals

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

- Wording that claims more than the board showed: "cancelled at", "delayed by", "operated by", "took off", or a first sighting by us presented as the flight's first listing. The only cancellation claim is "first observed CANCELED on the public board", with its bracket.
- Anything that looks like the official board or the Israel Airports Authority: no IAA name in the title, no logos, an "Unofficial; not affiliated with the Israel Airports Authority" line on every page.
- A flight silently missing: every `flights` row appears on exactly one day page; a row with no final scheduled time stops the build (none exist today).

## Pages

- `index.html`: the dates covered, newest first, with flight numbers listed per direction, the partial label where it applies, and the model's collection gaps; links to each day and to the methodology.
- `day/YYYY-MM-DD.html`:
  - Header: date, counts, partial label, the gaps that overlap this day's board window, the last check in this build.
  - A search box (works only with JavaScript; the page is complete without it).
  - Departures, then arrivals. Each flight is a `<details>` element with a stable anchor: airline and number, direction, first scheduled time, airport, kept to letters, digits and hyphens, for example `#LY5115-D-1630-KUT`. It never changes between builds, and the build stops if two flights on a page ever share one.
  - Summary line: scheduled time ("originally 28 Oct 23:30" after a retime, with the date when it differs from the page's), flight number, "listed together with" the other numbers of its codeshare group, city and airport, the outcome sentence. If the same number appears again that day: "Same number also listed at 13:30 (to KUT)".
  - Timeline table, one row per observation, ordered by board: when we saw it (Israel time, with the date when it differs from the page's; "between X and Y" when the previous sighting was more than an hour earlier), what changed, old value to new value (the old value is the previous observation of the same flight). The first row is "first seen by us" and lists the initial status, estimated time, terminal and counters.
  - Footer per flight: first and last seen, and how many stored boards it appeared on.
- `methodology.html`: in plain words, what the board is, how often we check, what each outcome means, the cancellation bracket and its censoring, "listed together" as an inference, the unknowns (CHPTOL, the operating carrier), receipts and legacy snapshots, partial days, and the attribution.
- `search.js` and `style.css`, shared.

## Wording

The cancellation sentence depends on `canceled_first_seen_at`, not on the outcome, because a flight cancelled and later shown with another status ends as departed, landed or open. The outcome sentence follows it.

Cancellation sentence (only when `canceled_first_seen_at` is set):

| case | sentence |
|---|---|
| already CANCELED at our first sighting (`canceled_at_first_sight`) | Already CANCELED the first time we saw it (HH:MM). |
| bracket spans a gap (censored, not first sight) | First observed CANCELED on the public board at HH:MM; the change happened after HH:MM, during a pause in our collection. |
| uncensored, lead time 0 or more | First observed CANCELED on the public board between HH:MM and HH:MM, at least N h before its scheduled time. (N is `cancel_lead_min` in whole hours, rounded down; "less than an hour" below 60 min.) |
| uncensored, negative lead time | First observed CANCELED on the public board between HH:MM and HH:MM, after its scheduled time. |
| `uncanceled` true (NULL counts as false) | adds: Later shown with another status. |

Outcome sentence:

| outcome | sentence |
|---|---|
| departed | Board showed DEPARTED (last seen HH:MM). |
| landed | Board showed LANDED (last seen HH:MM). |
| canceled | (the cancellation sentence covers it) |
| open | Still on the board at the last check (HH:MM). |
| gap | Left the board during a pause in our collection; what happened is unknown. |
| vanished | Left the board N h before its scheduled time without a final status; not necessarily cancelled, it may have been retimed. |
| dropped | Left the board without a final status; last seen HH:MM, within an hour of its scheduled time or later. |

Gaps, in the model's terms (consecutive stored boards more than `GAP_HOURS` apart): "No new board stored between X and Y: our collection paused, or the board stopped changing."

Times: board times (scheduled, estimated) are Israel wall-clock as published. The model's own times are naive UTC; the generator marks them UTC explicitly before converting to Asia/Jerusalem (a naive `astimezone` uses the machine's zone: on an Israeli Mac it turns 18:04Z into 18:04 instead of 20:04). Each page says which times are which.

## How it is built

- `src/timeline/` (not `site`, which is a Python standard module): `build.py` (command line, writing files), `pages.py` (pure functions from rows to HTML strings, escaped with `html.escape`), `static/search.js`, `static/style.css`. The attribution text is one constant shared with `model.report`.
- Reads `data/model/{flights,observations,snapshots}.parquet` with DuckDB (session time zone UTC), like `model.report`. No new Python dependency, no npm, no framework.
- Writes into a temporary folder beside `--out`, then swaps it in. An existing `--out` is replaced only if it carries the generator's marker file (`.timeline-site`), so `--out data` can never delete the archive copy. `site/` goes into `.gitignore`.
- Search keys are built in Python, from the airline and number fields as published (no parsing of a combined string; codes like `6H`, `ENT` and numbers like `0115A` exist): each flight gets `data-k` with the code plus number as published and without leading zeros, for example `ly001 ly1`, plus the city and airport. `search.js` (about 15 lines) lowercases the query, removes spaces and shows flights with a key that starts with it, so typing narrows the list.
- `<meta name="robots" content="noindex">` on every page.

## Tests and mutation checks

Python (pytest), on small synthetic models built with the existing helpers:
- every page carries the attribution and the unofficial line;
- one exact-sentence test per cancellation case (first sight at the archive start, bracket across a gap, positive lead, negative lead, cancelled then DEPARTED) and per outcome; no page contains, in any letter case, "cancelled at", "canceled at", "delayed by", "operated by", "took off";
- old to new values; "between X and Y" after a long pause; "first seen by us"; "originally" with its date after a retime across midnight; "listed together with"; "same number also listed";
- Israel time across the October clock change, run with the process time zone set to Asia/Jerusalem so the naive-conversion trap fails the test on any machine;
- every flight on exactly one day page; partial-day labels at the archive's start and end; anchors unique and unchanged when a same-number flight is added; a NULL final scheduled time stops the build;
- text from the board is escaped (a city named `<script>` stays text); Hebrew marked `dir="rtl"`;
- `--out` without the marker is refused;
- two builds in separate processes with different `PYTHONHASHSEED` give identical files.

JavaScript: one pytest test runs `search.js`'s matching function under Node (skipped, visibly, where Node is missing; GitHub's Ubuntu runners have it). No Node step in CI and no second mutation runner. CI adds `--cov=timeline`. Each rule gets an entry in `scripts/mutation_check.py`.

## Five outsiders (from the review)

Observed sessions on the owner's machine, not a copy handed out (the terms reading comes first). Tasks: "find IZ 991 on 29 October and tell me what happened to it", "find a flight that was cancelled and say when that was announced", "is there anything here you would use, and for what?". Watch for: misreading "first observed CANCELED" as the cancellation time, misreading "listed together" as the same aircraft, not finding a flight. The review's stop rule: if fewer than two of five name a real use, keep the collector and the case study and stop product work.

## Publishing (not in v1, owner's call)

The pages contain per-flight timelines derived from the board, not raw replies. The open issue "Raw redistribution is not cleared" says only code, methodology and narrowly scoped derived aggregates are candidates for publication until the owner re-reads the data.gov.il terms. Per-flight timelines are more detailed than aggregates, so publishing and handing out copies both wait for that reading. When it is cleared, the cheapest fits are a private S3 bucket behind CloudFront in this account, or GitHub Pages if the repo goes public (it is private today); both need their price checked then. Before publishing, the model's gaps should come from receipts (OPEN_ISSUES).

## Cost

Nothing new in AWS: the build is local and reads the local model. Hosting cost is part of the publishing decision.

## What to know

- Publishing per-flight history is the step that turns a private archive into redistribution; the terms come first.
- Three clocks meet on every page: board times (Israel wall-clock, no offset), our times (UTC, shown as Israel time) and the clock change on the last Sunday of October. The naive-conversion trap is real on this Mac and invisible on CI, so it is tested under an Israeli time zone.
- The board's words are not facts about the flight. DEPARTED is the board's status, not a take-off time; a flight that vanished was not necessarily cancelled; our first sighting is not the flight's first listing (most flights so far were first seen at the archive's start or right after its 42-hour hole).
- "Listed together" is an inference from the same slot, estimated time, terminal and counters; arrivals with no counters can merge two real flights (OPEN_ISSUES, Model).
- The first days are partial: the archive began on 27 October and had a 42-hour hole.

## Design review (2026-10-29, Opus; Fable was over its limit and gates shipping)

Accepted: wording fixed for first sightings, `dropped`, `vanished`, negative leads and cancellations followed by another status; partial days; gaps left to the model, in neutral words; no zip before the terms are read, observed sessions instead; anchors always in full form from the first scheduled time and airport; a same-number line; Israel-time conversion with explicit UTC, tested under an Israeli zone; "between X and Y" after a long pause; counts as flight numbers listed; search keys built in Python, no Node in CI; a session plan with the stop rule; a safe `--out`; determinism across processes; case-insensitive banned phrases and exact sentences per case; stored boards, not checks; right-to-left Hebrew; a stop on a missing scheduled time; `--cov=timeline`; no A to Z strip; one attribution constant.

## Deviations

- **The index says what its counts are.** The first build put "Flight numbers listed" only in a column header; the test for counts caught it, and the index now says that counts are flight numbers, a flight sold under several numbers counting once per number.
- **Four guard tests beyond the plan**: a retimed flight's anchor uses its first scheduled time; an anchor does not change when the same number appears again; two flights sharing an anchor stop the build (through `render`, since a valid model cannot produce it); a search query that tells "starts with" from "contains" (`york`).
- **One folder check, `refuse_foreign`**, called before any work and again before the swap.
- **The site on real data** (21 boards, 27 to 29 October): 7 day pages, 3,018 flight numbers each on one page, 2.3 MB; 26 October and 1 November are partial; 31 October's low count is a Saturday, not a gap.
