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
- **Collection gaps ignore `unchanged` receipts.** R4, R7 and R8 measure gaps by snapshot spacing, so a stall on data.gov.il's side (the board not changing for over an hour) reads as our own collection hole. Receipts now record every full download; switching the gap rules to them is an owner's call, and a precondition for q7 publishing coverage gaps (`docs/receipts.md`, "Model changes").

## Collector

- **Acquisition receipts (q6) built and reviewed, not deployed.** Design `docs/receipts.md` (design review and code review by Opus 2026-10-29; the owner waived the Fable gate for this change; both reviews' outcomes and the Deviations are logged there). Collector writes `receipts/date=D/HHMMSSZ-<sha12>.json` after the pages and before state, write-once and locked; IAM statement `WriteOnceArchive` covers `raw/*` and `receipts/*`; the model keeps `receipted`/`legacy`, drops `orphan`/`superseded`/`pending`, stops on anything else; `scripts/sync.sh` syncs receipts then raw. Commits local, not pushed. Next: push and `sam deploy` (from a clean tree) on the owner's go. After deploy: `aws s3 ls` on `receipts/` shows new objects about every 15 min, log lines carry `receipt` and `code_sha256` (matching the committed `src/collector/`), and the first receipt becomes the legacy cutover by itself.
- **Small collector change not yet deployed.** A refused redirect now closes its response before raising (`src/collector/core.py`, `_SameHostRedirects`). No behaviour change on the live path; it ships with q6's deploy.
- **Timeout fix live but reliability unproven.** The 20 s status check went live 2026-10-29 14:22Z; all four timeouts seen that day predated it. Next move: after about a week, count `TimeoutError` lines in `/flights-archive/collector` since then; delete this entry if there are none, report times to the owner if there are.
- **Reserved concurrency cannot be set.** Round-2 review asked for `ReservedConcurrentExecutions: 1`; this account's Lambda quota in il-central-1 is 5 concurrent executions and AWS refuses any reservation that leaves fewer than 100 unreserved. Overlap is already impossible under the schedule (2 min period, 100 s timeout); only a manual invoke during a scheduled run could overlap. Options if that ever matters: a quota increase, or conditional (If-Match) state writes.
- **Write-once rests on the code, not IAM.** The collector's role may `s3:PutObject` any key under `raw/` and `receipts/`; only the code's `IfNoneMatch` (pinned by a test and a mutation check) stops a replacement, and Object Lock keeps the older version either way. An IAM condition requiring `If-None-Match` would make it a policy fact; the condition key is not yet checked against AWS's documentation. Code review suggestion, 2026-10-29; owner's call.
- **Recovery path untested.** One account, one region, a retained bucket, no restore drill. Round-2 review: write a runbook and test an import of archived objects; a cross-region mirror of archived objects (not of source requests) later, under $1 a month. Owner's call when.
- **Latch policy on a single 429 / 403.** The reviewer suggests requiring two or three consecutive blocks before latching, since one transient 429 halts collection until a manual unblock and the resulting hole breaks R4 and R8. Current code latches on the first. Owner's call; the conservative reading of the license argues for keeping it.

## Repo hygiene (before the repo goes public)

- **The User-Agent's repo URL returns 404 while the repo is private.** The live User-Agent (deployed 2026-10-29) names `https://github.com/doronreiffman/flights-archive`, so data.gov.il cannot follow the link. Either make the repo public (raw data is not in git; check `docs/` and the history first) or point the User-Agent at another contact page and redeploy. Owner's call.

## Governance

- **Raw redistribution is not cleared.** The brief positions "an openly licensed dataset"; the round-2 review says the data.gov.il terms were not re-read for redistribution and robots.txt is not authorization. Until the owner re-reads the terms (or asks data.gov.il), raw stays private and only code, methodology and narrowly scoped derived aggregates are candidates for publication, described as lower-risk, not cleared. Owner's call.
- **Claims discipline.** Publish "first observed CANCELED on the public board", never "cancelled at"; no operator, actual-cancellation or delay claims without evidence. CHPTOL meaning still open (q3).
- **Forecast evidence gate not yet adopted.** Both outside reviews say per-flight cancellation forecasts are premature: 19 cancelled flights so far, 0 with an uncensored lead time. Round-2 proposes forecasts stay shadow-only until about 400 prospective movement-level positives over at least 60 untouched days, with temporal evaluation and skill over historical-rate baselines; round 1 proposed 4 to 6 weeks of data. Owner picks the gate; until then, no forecast is published.
