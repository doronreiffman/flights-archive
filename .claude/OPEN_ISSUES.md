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

## Collector

- **Reserved concurrency cannot be set.** Round-2 review asked for `ReservedConcurrentExecutions: 1`; this account's Lambda quota in il-central-1 is 5 concurrent executions and AWS refuses any reservation that leaves fewer than 100 unreserved. Overlap is already impossible under the schedule (2 min period, 100 s timeout); only a manual invoke during a scheduled run could overlap. Options if that ever matters: a quota increase, or conditional (If-Match) state writes.
- **Recovery path untested.** One account, one region, a retained bucket, no restore drill. Round-2 review: write a runbook and test an import of archived objects; a cross-region mirror of archived objects (not of source requests) later, under $1 a month. Owner's call when.
- **Latch policy on a single 429 / 403.** The reviewer suggests requiring two or three consecutive blocks before latching, since one transient 429 halts collection until a manual unblock and the resulting hole breaks R4 and R8. Current code latches on the first. Owner's call; the conservative reading of the license argues for keeping it.

## Repo hygiene (before the repo goes public)

- **Seven commits carry the placeholder email `<email for public commits>`.** Future commits use 83887818+doronreiffman@users.noreply.github.com (`.git/config`, set 2026-10-29). Rewriting the seven and force-pushing the private remote needs the owner's explicit confirmation.
- **Employer profile names in CLAUDE.md** were put there on the owner's instruction; they are names only, but the reviewer suggests moving them to an untracked `CLAUDE.local.md` before publishing. Owner's call.
- **The User-Agent's repo URL returns 404 while the repo is private.** Either make the repo public or use another contact URL; owner's call.

## Governance

- **Raw redistribution is not cleared.** The brief positions "an openly licensed dataset"; the round-2 review says the data.gov.il terms were not re-read for redistribution and robots.txt is not authorization. Until the owner re-reads the terms (or asks data.gov.il), raw stays private and only code, methodology and narrowly scoped derived aggregates are candidates for publication, described as lower-risk, not cleared. Owner's call.
- **Claims discipline.** Publish "first observed CANCELED on the public board", never "cancelled at"; no operator, actual-cancellation or delay claims without evidence. CHPTOL meaning still open (q3).
