# Queue

Ordered, most important first. One line per item: id (never reused), what, pointer to where its state lives.

## Queue

- [q13] Five observed outsider sessions with the history timeline, watched by the owner: tasks, what to watch for and the stop rule (fewer than two of five name a real use: keep the collector and the case study, stop product work) in `docs/timeline.md`, "Five outsiders". Owner runs them; the agent rebuilds the site on fresh data first. Added 2026-10-29.
- [q14] Owner's call: measure collection gaps from all receipts (stored and unchanged) instead of snapshot spacing in R4, R7 and R8, so a board that stops changing is not our outage; the timeline follows the model. Precondition for publishing coverage gaps. State: OPEN_ISSUES.md, Model, "Collection gaps ignore unchanged receipts". Added 2026-10-29.
- [q15] Publish the history timeline, after q14: a private S3 bucket behind CloudFront in this account (owner's pick, 2026-10-29), then build and upload on the owner's go. Before the first upload: the footer also says the site is not endorsed by data.gov.il or the State; before each upload: scan the real site for the banned phrases, and the owner checks the terms page's update date (`docs/terms.md`). Options and prices: `docs/timeline.md`, "Publishing". Added 2026-10-29.
- [q4] Rerun the model and data-quality report once a week of continuous snapshots exists; first real retime links, cancellation lead-time brackets and the `vanished` class are all unmeasured until then. State: OPEN_ISSUES.md.
- [q3] Confirm what CHPTOL measures (gate vs runway) before any delay statistic ships. State: OPEN_ISSUES.md.
- [q5] Make the model build incremental (date-partitioned `rows/` Parquet, trailing-window rebuild of observations and flights), the precondition for any nightly run. Deferred behind q6 and q7 (owner, 2026-10-29): a 6-day rebuild takes 13 s, far under the 5-minute trigger, and the rules are still moving. State: `docs/data-model.md` "Nightly run", step 1.
- [q2] Nightly model build: second Lambda per `docs/data-model.md` "Nightly run", step 2; needs q5 first and the owner's go, nothing deployed. State: same section.

## Done / Dropped

- [q12] data.gov.il terms read (2026-10-29): the general license allows copying, publishing and derived works, commercial or not, with the source cited, no misleading presentation and no implied official status; flydata's "Other (Open)" label has no text of its own. The owner cleared the history timeline for publishing; raw stays unpublished. Quotes checked against the owner's saved copy: `docs/terms.md`.
- [q7] History timeline v1 (2026-10-29): static site from the model, local only (`src/timeline/`, `docs/timeline.md`); design, code and handoff reviews by Opus (Fable over its limit; the owner's waiver covers q7), all findings fixed; publishing and the five outsider sessions wait on the owner (terms reading; `docs/timeline.md`, "Five outsiders", "Publishing"). Proof: 52cafaf, dd9cd79, CI green.
- [q6] Acquisition receipts (2026-10-29): write-once receipt after every full download, model trusts only receipted or legacy snapshots, `scripts/sync.sh`; design and code reviewed by Opus (Fable gate waived by the owner). Deployed 17:01Z; first receipt `receipts/date=2026-10-29/170250Z-c8bbbcbb6376.json` (the legacy cutover), locked to 2036. Proof: 4f2da20, 3e3b836.
- [q11] Model build ran out of memory on real data (2026-10-29, found while checking q6): the JSON reader reserved 512 MB per file; capped at the collector's 32 MB reply limit. Proof: 3369e2c.
- [q1] Data model v1 (2026-10-29): `src/model/`, 55 tests + 28 mutation checks, independent review folded in, `docs/data-model.md`, `docs/data-quality-2026-10-29.md`. Proof: e73eff5.
- [q8] Outside review round 1 follow-ups (2026-10-29): User-Agent enforced, 20 s status check, quieter alerting, stronger collector tests; deployed 14:22Z. Proof: 9c2d4a4, 2491fd3.
- [q9] Outside review round 2 follow-ups (2026-10-29): same-host redirects, strict `_id` order, block reported when the latch cannot be saved, incomplete snapshots dropped, mutation check in CI; deployed 14:53Z. Proof: 965fe77 and the handoff commit after it.
- [q10] Commit identity (2026-10-29): history rewritten to 83887818+doronreiffman@users.noreply.github.com while private and uncloned; employer profile names moved to untracked `CLAUDE.local.md`. Proof: c40b78a.
