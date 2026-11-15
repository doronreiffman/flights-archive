# Design notes

Written while building the project: each note says what was decided and why, the alternatives rejected, and what an independent review changed. Tags like (q7) are items in the project's work queue, kept outside this repository; the review sections name the model that reviewed and record each finding's fate.

- [operations.md](operations.md): how the collector works, deploying and running it, what it costs.
- [receipts.md](receipts.md): the write-once archive and the receipt written after every download.
- [data-model.md](data-model.md): from raw boards to observations and flights; the rules and what is still uncertain about them.
- [data-quality-2026-10-29.md](data-quality-2026-10-29.md): the first report on real snapshots.
- [site-redesign.md](site-redesign.md): the history site as built (v2): its pages, the wording rules that keep it from claiming more than the airport's list showed, its look and the upload check.
- [timeline.md](timeline.md): the site's first version (v1), the partial-day rule and the decision to publish.
- [terms.md](terms.md): the data.gov.il terms, quoted, and what they ask of the project.
- [publishing.md](publishing.md): hosting the site on S3 and CloudFront, the upload checks, and the cost.
- [flight-lookup.md](flight-lookup.md): the design that put a traveller's own flight first: the counting rules, the "from here" table, the signs and the gate that keep forecasts off the site until the evidence is in.
- [flight-lookup-figures.md](flight-lookup-figures.md): the queries and results behind that design's figures, cited in it as (A1), (A2) and so on.
- [flight-lookup-plan.md](flight-lookup-plan.md): the plan that built it, task by task, with the deviations found along the way.
