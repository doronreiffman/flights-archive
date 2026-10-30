# Open issues

Living list of open blockers, deferred bugs and "fix someday" items. Replace an entry when its state changes; delete it when resolved.

## Data

- **CHPTOL meaning half-settled.** The datastore's field notes (in every `datastore_search` reply, `result.fields`) call it "AnticipatedTimeLocal". Gate vs runway is still unknown: departures run a median +20 min over schedule, arrivals land a median 7 min early. No delay statistics ship until a primary source settles it. data.gov.il's contact form looks unmonitored (owner, 2026-10-29); a question was drafted that day covering this, the swapped city-field notes and flydata's "Other (Open)" label. Next move, not urgent (no delay figure is planned): the owner may try the IAA's public-inquiries channel themselves.
- **Datastore field notes label the city pair backwards.** `CHLOC1TH` is documented as the English city and `CHLOC1T` as Hebrew; the data is the reverse. `src/model/rules.py` `COLUMNS` follows the data. Worth a note to data.gov.il some day.
- **DST fall-back hour.** R1 takes the earlier instant for the repeated 01:00–01:59 hour and flags the row (`sched_ambiguous`). No affected row yet; revisit if a flagged flight ever matters.

## Model (rules marked UNSURE in docs/data-model.md)

- **Retime rule unproven on real data.** R4 (same flight, next snapshot, within 12 h, no collection gap) found 0 links inside the continuous run so far; the 8 candidates seen all straddled the 42 h hole of 2026-10-27/29. Next move: q4.
- **Codeshare `time-only` groups (all arrivals) can merge two real flights** from the same airport at the same scheduled and estimated minute. Measure once a week of data exists: look for groups whose members' statuses diverge.
- **Operating-carrier guess** is the lowest flight number in the group; pure convention, `operating_is_guess` marks it.
- **`vanished` vs `dropped` threshold** is 1 h past the last appearance; with the gap outcome in place neither class has a real example yet.
- **Collection gaps ignore `unchanged` receipts.** R4, R7 and R8 measure gaps by snapshot spacing, so a stall on data.gov.il's side (the board not changing for over an hour) reads as a collection hole. The v2 site states a gap as "There are no records from X to Y" (how-it-works) and a flight that left the list during one as UNKNOWN; that is true while every gap is a collection outage, and becomes false once the board stands still between two downloads (receipts would exist). Revisit that wording when q14 starts. Receipts record every full download since 2026-10-29 17:02:50Z; switching the rules to them is q14. The owner chose to publish the site first (2026-10-29; its v1 wording named both causes, the premise that no longer holds for v2); q14 starts with the first `unchanged` receipt, the first arrived 2026-10-30 03:16:45Z (a 15-minute refresh with identical content; no model gap came from it, so the site's only gap sentence is still the 27-29 October outage). q14 is now due (`docs/receipts.md`, "Model changes").

## Collector

- **Timeout fix live but reliability unproven.** The 20 s status check went live 2026-10-29 14:22Z. Since then: one `TimeoutError` on `resource_show` at 21:01:05Z (the next run, 21:02:45Z, took the 21:00:55 refresh, nothing lost) and one HTTP 404 on `resource_show` at 16:16:45Z (data.gov.il skipped its 16:15 refresh: last-modified stayed 16:01:02 until 16:30:48, nothing lost). Next move: on or after 2026-11-05 14:22Z, count `TimeoutError` and other ERROR lines in `/flights-archive/collector` since 14:22Z and give the owner the times and rate; delete this entry if none beyond these. Since then, also: `TimeoutError` at 2026-10-30 03:27:05Z and 06:41:05Z, and "datastore_search: zero rows" at 08:30:45Z (data.gov.il answered with an empty list; the collector refused it); the snapshot rhythm held through all three (03:18 → 03:32, 06:30 → 06:46, 08:32), nothing lost.
- **Reserved concurrency cannot be set.** Round-2 review asked for `ReservedConcurrentExecutions: 1`; this account's Lambda quota in il-central-1 is 5 concurrent executions and AWS refuses any reservation that leaves fewer than 100 unreserved. Overlap is already impossible under the schedule (2 min period, 100 s timeout); only a manual invoke during a scheduled run could overlap. Options if that ever matters: a quota increase, or conditional (If-Match) state writes.
- **Write-once rests on the code, not IAM.** The collector's role may `s3:PutObject` any key under `raw/` and `receipts/`; only the code's `IfNoneMatch` (pinned by a test and a mutation check) stops a replacement, and Object Lock keeps the older version either way. An IAM condition requiring `If-None-Match` would make it a policy fact; the condition key is not yet checked against AWS's documentation. Code review suggestion, 2026-10-29; owner's call.
- **The blocked message points at the README.** `src/collector/core.py:277` says to clear the latch "(see README)"; the steps moved to `docs/operations.md`, one link from the README. Owner, 2026-10-29: leave it until the collector is next redeployed for another reason, then point it at `docs/operations.md` with a test.
- **Recovery path untested.** One account, one region, a retained bucket, no restore drill. Round-2 review: write a runbook and test an import of archived objects; a cross-region mirror of archived objects (not of source requests) later, under $1 a month. Owner's call when.
- **Latch policy on a single 429 / 403.** The reviewer suggests requiring two or three consecutive blocks before latching, since one transient 429 halts collection until a manual unblock and the resulting hole breaks R4 and R8. Current code latches on the first. Owner's call; the conservative reading of the license argues for keeping it.

## Site (v2, q18)

- **Owner's calls from the final review (2026-10-30):** (a) a flight cancelled, changed back, then cancelled again has its warning measured from the first cancellation (the spec's choice; the tables show only that warning); (b) a "no flight matches" line and back-button restore in search were offered, not built; (c) on phones the stacked warning cell reads "Warning: none: listed as cancelled …"; (d) look at the site at 375 px and in dark mode before the first upload (chart text near the right edge, pale bars, the stacked table, dark mode).
- **A check-in zone named "I" would stop an upload** (the "I" rule reads change lines; zones today: A, B, C, D, G). It fails loudly; handle it then.
- **Deferred minor review findings**, none blocking: `docs/site-redesign.md`, "Deferred review findings".

## Site (q15)

- **Live and reached by link only.** First upload 2026-10-30 (961 files, 5.9 MB on disk) to https://dt4564wsgvijr.cloudfront.net; every page carries `noindex` and the repo is still private (q17 decides both). Freshness is by hand: `sh scripts/sync.sh`, model build, timeline build, `sh scripts/publish.sh`, each upload on the owner's go with the terms page date read that day. A scheduled rebuild is q2/q5.

## Repo hygiene (before the repo goes public)

- **The User-Agent's repo URL returns 404 while the repo is private.** The live User-Agent (deployed 2026-10-29) names `https://github.com/doronreiffman/flights-archive`, so data.gov.il cannot follow the link. Resolves when the owner flips the repo public at launch (q17); the clean repo is ready (q16 done, 2026-10-29).

## Governance

- **flydata's own license label has no text.** The dataset is tagged "Other (Open)" with no license URL or text, so we read the general data.gov.il license as governing (`docs/terms.md`). The owner judged it no blocker for publishing the timeline (2026-10-29). If it ever matters, ask data.gov.il which license applies.
- **Claims discipline.** Plain words (`docs/site-redesign.md`, "Words"): a warning is a range or a bound, never one measured figure; a cancellation's time is always a range; the headline says "listed as cancelled"; no operator, actual-cancellation or delay claims without evidence; `src/timeline/check.py` enforces the banned phrases and words before every upload. CHPTOL meaning still open (q3). The license forbids misleading presentation, and we read this discipline as how we meet that condition (`docs/terms.md`).
- **Forecast evidence gate not yet adopted.** Both outside reviews say per-flight cancellation forecasts are premature: 19 cancelled flights so far, 0 with an uncensored lead time. Round-2 proposes forecasts stay shadow-only until about 400 prospective movement-level positives over at least 60 untouched days, with temporal evaluation and skill over historical-rate baselines; round 1 proposed 4 to 6 weeks of data. Owner picks the gate; until then, no forecast is published.
