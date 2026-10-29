# Queue

Ordered, most important first. One line per item: id (never reused), what, pointer to where its state lives.

## Queue

- [q6] Acquisition receipts: the collector writes a small receipt object after every full fetch (stored or unchanged) and writes it last, so "the board was checked and unchanged at T" and "this multi-page prefix is complete" become archive facts, not log lines. First in line (owner, 2026-10-29). State: OPEN_ISSUES.md, "Acquisition receipts (q6)".
- [q7] Static history timeline: a page where a date and marketed flight number show the flight's status and schedule changes, coverage gaps, first observed CANCELED, with methodology and attribution; raw data stays private. First product (owner, 2026-10-29), ahead of dashboard, rankings, forecasts and MCP. Scope still to be cut with the owner; source is change 3 of `reviews/review-2026-10-29-round-2.md` (local only).
- [q5] Make the model build incremental (date-partitioned `rows/` Parquet, trailing-window rebuild of observations and flights), the precondition for any nightly run. Deferred behind q6 and q7 (owner, 2026-10-29): a 6-day rebuild takes 13 s, far under the 5-minute trigger, and the rules are still moving. State: `docs/data-model.md` "Nightly run", step 1.
- [q2] Nightly model build: second Lambda per `docs/data-model.md` "Nightly run", step 2; needs q5 first and the owner's go, nothing deployed. State: same section.
- [q3] Confirm what CHPTOL measures (gate vs runway) before any delay statistic ships. State: OPEN_ISSUES.md.
- [q4] Rerun the model and data-quality report once a week of continuous snapshots exists; first real retime links, cancellation lead-time brackets and the `vanished` class are all unmeasured until then. State: OPEN_ISSUES.md.

## Done / Dropped

- [q11] Model build ran out of memory on real data (2026-10-29, found while checking q6): the JSON reader reserved 512 MB per file; capped at the collector's 32 MB reply limit. Proof: 3369e2c.
- [q1] Data model v1 (2026-10-29): `src/model/`, 55 tests + 28 mutation checks, independent review folded in, `docs/data-model.md`, `docs/data-quality-2026-10-29.md`. Proof: e73eff5.
- [q8] Outside review round 1 follow-ups (2026-10-29): User-Agent enforced, 20 s status check, quieter alerting, stronger collector tests; deployed 14:22Z. Proof: 9c2d4a4, 2491fd3.
- [q9] Outside review round 2 follow-ups (2026-10-29): same-host redirects, strict `_id` order, block reported when the latch cannot be saved, incomplete snapshots dropped, mutation check in CI; deployed 14:53Z. Proof: 965fe77 and the handoff commit after it.
- [q10] Commit identity (2026-10-29): history rewritten to 83887818+doronreiffman@users.noreply.github.com while private and uncloned; employer profile names moved to untracked `CLAUDE.local.md`. Proof: c40b78a.
