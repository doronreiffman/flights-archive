# Queue

Ordered, most important first. One line per item: id (never reused), what, pointer to where its state lives.

## Queue

- [q5] Make the model build incremental (date-partitioned `rows/` Parquet, trailing-window rebuild of observations and flights), the precondition for any nightly run. Round-2 review says defer: a 6-day rebuild takes 13 s, far under the 5-minute trigger, and the rules are still moving. Owner decides the order against q6 and q7. State: `docs/data-model.md` "Nightly run", step 1.
- [q2] Nightly model build: second Lambda per `docs/data-model.md` "Nightly run", step 2; needs q5 first and the owner's go, nothing deployed. State: same section.
- [q6] Acquisition receipts: the collector writes a small receipt object after every full fetch (stored or unchanged) and writes it last, so "the board was checked and unchanged at T" and "this multi-page prefix is complete" become archive facts, not log lines. Round-2 review's first change; needs a design note with cost, then a deploy on the owner's go. State: OPEN_ISSUES.md.
- [q7] Static history timeline: a page where a date and marketed flight number show the flight's status and schedule changes, coverage gaps, first observed CANCELED, with methodology and attribution; raw data stays private. Round-2 review's proposed first product, ahead of dashboard, rankings, forecasts and MCP. State: owner's call on scope.
- [q3] Confirm what CHPTOL measures (gate vs runway) before any delay statistic ships. State: OPEN_ISSUES.md.
- [q4] Rerun the model and data-quality report once a week of continuous snapshots exists; first real retime links, cancellation lead-time brackets and the `vanished` class are all unmeasured until then. State: OPEN_ISSUES.md.

## Done / Dropped

- [q1] Data model v1 (2026-10-29): `src/model/`, 55 tests + 28 mutation checks, independent review folded in, `docs/data-model.md`, `docs/data-quality-2026-10-29.md`. Proof: the commit that adds them.
