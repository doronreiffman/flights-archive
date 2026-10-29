# flights-archive

Personal portfolio project. Archives the Ben Gurion flight board from data.gov.il (Israel Airports Authority, dataset `flydata`, resource `e83f763b-b7d7-479e-b172-ae981ddc6de5`) and turns it into reliability stats, scored cancellation forecasts, an MCP server + agent with evals, and a dashboard. README.md covers what the collector does, how to deploy it and what it costs.

## Hard rules

- Personal accounts only. Nothing touches the owner's employer: no work systems, accounts, cloud or credentials.
- AWS: profile `flights-sam`, region `il-central-1`, account `137953273942`, and nothing else. Before any AWS command, run `aws sts get-caller-identity --profile flights-sam` and confirm account 137953273942 and user doron-admin. Every other profile on this machine belongs to the employer.
- Ask before anything that writes outside this repo: `sam deploy`, any AWS write, `git push`, enabling or disabling the schedule. Read-only AWS calls (`s3 ls` / `cp` / `sync` from the bucket, `describe-*`, `get-caller-identity`) need no ask.
- The archive bucket `flights-archive-archivebucket-onpwo5ns74tw` is write-once with Object Lock. Never delete, overwrite or bypass retention; the snapshots are the project.
- data.gov.il is the only source. Never call iaa.gov.il (its terms forbid copying). If data.gov.il blocks us, stop and tell the owner: the license excludes data obtained by working around a block (browser User-Agent, IP rotation, anything of the kind).
- Keep credentials, the healthchecks.io ping URL and the owner's email out of the repo; the email appears only inside the User-Agent, where it already is.
- Tests for every component, and a mutation check: break the code on purpose to prove the tests catch it. Before anything ships, a fresh subagent that has not seen your reasoning reviews it.
- Cheap, boring infrastructure; every proposal carries a monthly cost estimate.
- Attribution: cite data.gov.il / Israel Airports Authority wherever the data is shown or published.

## Current state (2026-10-29)

- Collector (Lambda, stack `flights-archive`) live since 2026-10-29 about 14:30 Israel time. Polls `resource_show` every 2 min; downloads via `datastore_search` when `last_modified` moves (the board refreshes every 15 min, about 25 s after the quarter hour) or every 30 min; stores the raw reply gzipped at `raw/date=YYYY-MM-DD/HHMMSSZ-<sha12>/page-000.json.gz` with metadata (fetched-at, resource-last-modified, rows, hashes). `state/collector.json` holds the last timestamp, hash and a "blocked" latch. 68 tests, CI on GitHub.
- Snapshots: first 2026-10-27 18:04Z, a few more from a 10-minute accidental run that evening, continuous since 2026-10-29.
- Next: the data model (observations + flights Parquet tables built from the raw snapshots), then stats, forecasts, MCP server + agent, dashboard.

## The data (measured on 61 snapshots, Oct 12–27)

- Fields: `_id` plus 17. CHOPER / CHOPERD airline code / name, CHFLTN flight number, CHSTOL scheduled time, CHPTOL updated time, CHAORD A (arrival) / D (departure), CHLOC1 IATA airport, CHLOC1D airport name, CHLOC1T / CHLOC1TH city EN / HE, CHLOCCT / CHLOC1CH country EN / HE, CHTERM terminal (int 1 or 3), CHCINT check-in counters, CHCKZN check-in zone, CHRMINE / CHRMINH status EN / HE.
- Statuses seen: ON TIME, NOT FINAL, DEPARTED, LANDED, FINAL, CANCELED, LANDING, DELAYED, EARLY.
- Window: about 22–41 h back, 72 h ahead. 1,900–2,800 rows a snapshot; about 370 physical flights a day; about 2% cancelled (68 of about 3,670 physical flights).
- Times are Israel wall-clock with no offset: convert to UTC. The DST fall-back hour (2026-10-25) is ambiguous.
- `_id` is a row number reset every refresh. Natural key: (airline, flight no., CHSTOL, A/D). A rescheduled flight gets a new CHSTOL: 40 of 56 rows that "vanished" were retimes (same flight no., new time within about 12 h); the other 16 left the board days ahead and may be unflagged cancellations.
- Codeshares: 50–56% of rows share time + direction + airport + CHPTOL + terminal + counters (e.g. EY 607 / LY 9614). No operating-carrier field. That heuristic can wrongly merge arrivals with empty counters.
- Exact duplicate rows occur (LY 9951, 7 snapshots).
- CHPTOL minus CHSTOL: departures median +21 min (66% over 15), arrivals +1 min. Likely takeoff / actual time, not gate. Unconfirmed: publish no delay stats until it is.
- Positioning: others already rank airlines (tlvflights.com since Dec 2025). We lead with how far ahead cancellations are announced (within the 72 h the feed sees), per-flight forecasts with a published Brier score and calibration (skill against a historical-rate baseline), an openly licensed dataset, and the agent.

## Working notes

- Work queue: `.claude/QUEUE.md`. Open issues: `.claude/OPEN_ISSUES.md`. Decisions go to the owner's hub doc: end every session with a list headed "For the decision log" (each decision with its why).
