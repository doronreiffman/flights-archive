# Open issues

Living list of open blockers, deferred bugs and "fix someday" items. Replace an entry when its state changes; delete it when resolved.

## Data

- **CHPTOL meaning half-settled.** The datastore's field notes (in every `datastore_search` reply, `result.fields`) call it "AnticipatedTimeLocal". Gate vs runway is still unknown: departures run a median +20 min over schedule, arrivals land a median 7 min early. No delay statistics ship until a primary source settles it. Next move: owner, ask data.gov.il or the IAA.
- **Datastore field notes label the city pair backwards.** `CHLOC1TH` is documented as the English city and `CHLOC1T` as Hebrew; the data is the reverse. `src/model/rules.py` `COLUMNS` follows the data. Worth a note to data.gov.il some day.
- **DST fall-back hour.** R1 takes the earlier instant for the repeated 01:00–01:59 hour and flags the row (`sched_ambiguous`). No affected row yet; revisit if a flagged flight ever matters.

## Model (rules marked UNSURE in docs/data-model.md)

- **Retime rule unproven on real data.** R4 (same flight, next snapshot, within 12 h, no collection gap) found 0 links inside the continuous run so far; the 8 candidates seen all straddled the 42 h hole of 2026-10-27/29. Next move: q4.
- **Codeshare `time-only` groups (all arrivals) can merge two real flights** from the same airport at the same scheduled and estimated minute. Measure once a week of data exists: look for groups whose members' statuses diverge.
- **Operating-carrier guess** is the lowest flight number in the group; pure convention, `operating_is_guess` marks it.
- **`vanished` vs `dropped` threshold** is 1 h past the last appearance; with the gap outcome in place neither class has a real example yet.
- **Collection gaps ignore `unchanged` receipts.** R4, R7 and R8 measure gaps by snapshot spacing, so a stall on data.gov.il's side (the board not changing for over an hour) reads as a collection hole. The timeline shows the model's gaps in neutral words ("our collection paused, or the board stopped changing"). Receipts record every full download since 2026-10-29 17:02:50Z; switching the rules to them is q14, the owner's call, and a precondition for publishing coverage gaps (`docs/receipts.md`, "Model changes").

## Collector

- **Timeout fix live but reliability unproven.** The 20 s status check went live 2026-10-29 14:22Z; all four timeouts seen that day predated it. Next move: after about a week, count `TimeoutError` lines in `/flights-archive/collector` since then; delete this entry if there are none, report times to the owner if there are.
- **Reserved concurrency cannot be set.** Round-2 review asked for `ReservedConcurrentExecutions: 1`; this account's Lambda quota in il-central-1 is 5 concurrent executions and AWS refuses any reservation that leaves fewer than 100 unreserved. Overlap is already impossible under the schedule (2 min period, 100 s timeout); only a manual invoke during a scheduled run could overlap. Options if that ever matters: a quota increase, or conditional (If-Match) state writes.
- **Write-once rests on the code, not IAM.** The collector's role may `s3:PutObject` any key under `raw/` and `receipts/`; only the code's `IfNoneMatch` (pinned by a test and a mutation check) stops a replacement, and Object Lock keeps the older version either way. An IAM condition requiring `If-None-Match` would make it a policy fact; the condition key is not yet checked against AWS's documentation. Code review suggestion, 2026-10-29; owner's call.
- **Recovery path untested.** One account, one region, a retained bucket, no restore drill. Round-2 review: write a runbook and test an import of archived objects; a cross-region mirror of archived objects (not of source requests) later, under $1 a month. Owner's call when.
- **Latch policy on a single 429 / 403.** The reviewer suggests requiring two or three consecutive blocks before latching, since one transient 429 halts collection until a manual unblock and the resulting hole breaks R4 and R8. Current code latches on the first. Owner's call; the conservative reading of the license argues for keeping it.

## Repo hygiene (before the repo goes public)

- **The User-Agent's repo URL returns 404 while the repo is private.** The live User-Agent (deployed 2026-10-29) names `https://github.com/doronreiffman/flights-archive`, so data.gov.il cannot follow the link. Either make the repo public (raw data is not in git; check `docs/` and the history first) or point the User-Agent at another contact page and redeploy. Owner's call.

## Governance

- **flydata's own license label has no text.** The dataset is tagged "Other (Open)" with no license URL or text, so we read the general data.gov.il license as governing (`docs/terms.md`). The owner judged it no blocker for publishing the timeline (2026-10-29). If it ever matters, ask data.gov.il which license applies.
- **Claims discipline.** Publish "first observed CANCELED on the public board", never "cancelled at"; no operator, actual-cancellation or delay claims without evidence. CHPTOL meaning still open (q3). The license forbids misleading presentation, and we read this discipline as how we meet that condition (`docs/terms.md`).
- **Forecast evidence gate not yet adopted.** Both outside reviews say per-flight cancellation forecasts are premature: 19 cancelled flights so far, 0 with an uncensored lead time. Round-2 proposes forecasts stay shadow-only until about 400 prospective movement-level positives over at least 60 untouched days, with temporal evaluation and skill over historical-rate baselines; round 1 proposed 4 to 6 weeks of data. Owner picks the gate; until then, no forecast is published.
