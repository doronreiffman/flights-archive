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

- **One deploy pending, owner's go needed.** Four changes are in code and tests but not live: status-check timeout 10 s to 20 s (`SHOW_TIMEOUT`, after four timeouts in about fifty runs on 2026-10-29, all right after a board refresh); no `/fail` ping on transient errors (healthchecks.io's grace period decides); the error alarm needs errors in two consecutive 5-minute windows; and the User-Agent parameter now rejects a value without a URL and an email. The live `USER_AGENT` is truncated to `flights-archive/0.1` because the README's deploy command lacked inner quotes, so the live collector has been identifying itself without a contact since go-live; the README command is fixed. Deploy: `sam build`, then the README's step 4 command with `ScheduleState=ENABLED`, then confirm the live value with `aws lambda get-function-configuration`.
- **Latch policy on a single 429 / 403.** The reviewer suggests requiring two or three consecutive blocks before latching, since one transient 429 halts collection until a manual unblock and the resulting hole breaks R4 and R8. Current code latches on the first. Owner's call; the conservative reading of the license argues for keeping it.

## Repo hygiene (before the repo goes public)

- **Commit author email is the literal placeholder `<email for public commits>`** on every commit (`.git/config` `user.email`). Owner picks an address (GitHub's noreply form `<id>+doronreiffman@users.noreply.github.com` keeps the real one private), then the history is rewritten with it; rewriting needs the owner's explicit confirmation.
- **`gh` active account is the employer's**, which also serves git pushes; `gh auth switch -u doronreiffman` is the owner's to run. Until then nothing can be pushed from this machine.
- **Employer profile names in CLAUDE.md** were put there on the owner's instruction; they are names only, but the reviewer suggests moving them to an untracked `CLAUDE.local.md` before publishing. Owner's call.
- **The User-Agent's repo URL returns 404 while the repo is private.** Either make the repo public or use another contact URL; owner's call.
