# Design notes

Written while building the project: each note says what was decided and why, the alternatives rejected, and what an independent review changed. Tags like (q7) are items in the project's work queue (`.claude/QUEUE.md`); the review sections name the model that reviewed and record each finding's fate.

- [operations.md](operations.md): how the collector works, deploying and running it, what it costs.
- [receipts.md](receipts.md): the write-once archive and the receipt written after every download.
- [data-model.md](data-model.md): from raw boards to observations and flights; the rules and what is still uncertain about them.
- [data-quality-2026-10-29.md](data-quality-2026-10-29.md): the first report on real snapshots.
- [site-redesign.md](site-redesign.md): the history site as built (v2): its pages, the wording rules that keep it from claiming more than the airport's list showed, its look and the upload check.
- [timeline.md](timeline.md): the site's first version (v1), the partial-day rule and the decision to publish.
- [terms.md](terms.md): the data.gov.il terms, quoted, and what they ask of the project.
- [publishing.md](publishing.md): hosting the site on S3 and CloudFront, the upload checks, and the cost.
