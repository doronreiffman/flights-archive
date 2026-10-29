# Open issues

Living list of open blockers, deferred bugs and "fix someday" items. Replace an entry when its state changes; delete it when resolved.

## Data

- **CHPTOL meaning unconfirmed.** Departures run a median +21 min over CHSTOL, arrivals +1 min, which looks like takeoff / actual time rather than gate time. No delay statistics get published until a primary source settles it. Next move: owner, find the field definition on data.gov.il or in IAA material.
- **DST fall-back hour is ambiguous.** Board times are Israel wall-clock with no offset; the repeated 01:00–02:00 hour on 2026-10-25 cannot be resolved from the field alone. Next move: data model picks a rule and marks affected rows.
