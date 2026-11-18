# Flight board archive: cancelled flights at Tel Aviv airport

[![CI](https://github.com/doronreiffman/flights-archive/actions/workflows/ci.yml/badge.svg)](https://github.com/doronreiffman/flights-archive/actions/workflows/ci.yml) ![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white) ![DuckDB](https://img.shields.io/badge/DuckDB-Parquet-FFF000?logo=duckdb&logoColor=black) ![AWS SAM](https://img.shields.io/badge/AWS%20SAM-Lambda%20%C2%B7%20S3%20%C2%B7%20CloudFront-232F3E)

Keeps the history of the Ben Gurion airport flight board, which overwrites itself every 15 minutes: every version kept for 10 years, with a receipt for every download since 29 October 2026.

**Live site:** [dt4564wsgvijr.cloudfront.net](https://dt4564wsgvijr.cloudfront.net) · **Design notes:** [docs/](docs/README.md) · **Run it yourself:** [docs/operations.md](docs/operations.md)

**Stack:** Python 3.13 · AWS SAM (Lambda, EventBridge Scheduler, S3 Object Lock, CloudWatch, SNS) · DuckDB and Parquet · a static site (HTML, CSS, a little JavaScript, self-hosted fonts) on S3 + CloudFront · GitHub Actions

Built by Doron Reiffman ([LinkedIn](https://www.linkedin.com/in/doronreiffman)).

![The front page of Will It Fly?: "Find your flight" over a search box for a flight number or city; the chance of cancellation by how soon you fly, for all airlines, from 1.6% three days away down to 0.5% three hours away, and about 8% of departures and 5% of arrivals delayed an hour or more; then the total since 27 October: 6,353 flights, 107 cancelled, 1.7%.](docs/img/front-page.png)

![The page for BZ 317 from Vienna: its flight on Wednesday 18 November, scheduled to land at 19:15, with "Chance it's cancelled: about 4%" and "Chance it's delayed an hour or more: about 17%", worked out mostly from Bluebird Airways' history because BZ 317 has only 12 flights so far; then its record so far (12 flights, 1 cancelled, 3 delayed an hour or more) and its days as a strip: 11 landed, 1 cancelled, 2 upcoming.](docs/img/timeline.png)

*The front page and one flight's page, as uploaded on 18 November 2026.*

## At a glance

| | |
|---|---|
| Collecting since | 27 October 2026; continuous since 29 October |
| Checks the board | every 2 minutes; downloads it when it changed |
| Boards archived | 559, covering 6,015 flight listings (4 November 2026) |
| Kept for | 10 years, write-once (S3 Object Lock) |
| Tests | 1,686, plus 744 planted bugs, all caught |
| Cost | about $1 to $2 for the archive's first year, before the alarms (at most $0.70 a month more, likely free) |

## Why

The Israel Airports Authority publishes the airport's live departures and arrivals board as open data on data.gov.il. The board shows about one to two days back and three days ahead, and every refresh replaces the last one. When a flight goes from ON TIME to CANCELED, the board itself keeps no record of what it said before.

This project keeps that record. It saves every version of the board, writes down what it saved and when, and turns the archive into a history for each flight: what the board said, when each change appeared on it, and, for a cancelled flight, how much notice there was. That history answers questions the live board can't. The first is how far ahead cancellations appear.

## What it does today

- **Collector**, live on AWS. A Lambda function in Tel Aviv checks every 2 minutes whether the board changed and downloads it when it did, about 4 times an hour. The archive starts on 27 October 2026 and has been continuous since 29 October.
- **Archive.** Every board is stored exactly as received, and every version is kept for 10 years under S3 Object Lock (governance mode); the collector never overwrites a stored file. After every download it also writes a receipt: when it ran, what it got, which code version wrote it. As of 4 November 2026: 559 boards, covering 6,015 flight listings (a flight sold under several numbers counts once per number).
- **Data model.** DuckDB turns the archive into Parquet tables: every change to every flight, retimed flights linked to their new slot where the board allows it, flight numbers that share a slot, times and check-in counters grouped as likely codeshares, and each first CANCELED sighting bracketed between the last board without it and the first board with it.
- **Will It Fly?**, the history site, live at [dt4564wsgvijr.cloudfront.net](https://dt4564wsgvijr.cloudfront.net). A page for every flight number with the chance it's cancelled and the chance it's delayed an hour or more, from a simple blend of the number's, its airline's and the whole airport's records, each with what it was worked out from; then the number's days as a strip, and each change the airport's list showed. A delay counts only at an hour or more, since the airport doesn't say whether its times mean leaving the gate or taking off. Also a page per day, every cancellation with its notice (a range or a lower bound where the records allow), and a search box. Static pages, rebuilt and uploaded by hand; search engines are asked not to list them, so visitors arrive by link.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/flow-dark.png">
  <img alt="How it works: every 2 minutes the collector, an AWS Lambda function in Tel Aviv, checks whether data.gov.il's flight board changed; a new board and its receipt go into the archive on S3, kept 10 years; a sync feeds the data model (DuckDB to Parquet), which builds the history site's static pages; a checked upload, by hand, puts them on S3 and CloudFront." src="docs/img/flow-light.png">
</picture>

## Engineering choices worth a look

- **Nothing stored is ever replaced, and every download leaves a receipt.** The snapshots are the project, so the collector writes each file once, S3 keeps every version, and the model trusts only boards with a receipt, or from before receipts began. [docs/receipts.md](docs/receipts.md)
- **A polite collector that stops cold.** It identifies itself on every request, downloads the full board only when it changed (or every 30 minutes as a safety check), and on any sign of being blocked it stops and waits for a person. The data license excludes data obtained by working around a block. [docs/operations.md](docs/operations.md)
- **Three clocks.** Board times are Israel wall-clock with no offset, our times are UTC, and the October clock change repeats an hour. Each conversion rule is written down and tested, including under an Israeli time zone. [docs/data-model.md](docs/data-model.md)
- **Claims no stronger than the evidence.** The board is all we see, so the site says a flight was "cancelled", or "marked cancelled" where a sentence says when, never "cancelled at": a cancellation's time is always a range ("between 19:16 and 19:32"), and its notice a range or a lower bound ("at least 23 hours"). A flight's chance reads "about" or "under", never "0%", and its page says what the chance was worked out from. A check before every upload refuses a page that uses a banned phrasing or lacks the source line, and a flight page that gives a chance without its "Worked out from" line. [docs/flight-lookup.md](docs/flight-lookup.md), [docs/site-redesign.md](docs/site-redesign.md), [docs/terms.md](docs/terms.md)
- **Tests that are themselves tested.** 1,686 tests, and 744 deliberate bugs that a [script](scripts/mutation_check.py) plants one at a time to prove a test catches each (as of 18 November 2026). Both run in CI on every push.
- **Cheap, boring infrastructure.** About $1 to $2 in the archive's first year ([operations.md](docs/operations.md#cost)) and under $0.05 a month for the site at a few uploads a month ([publishing.md](docs/publishing.md#cost-monthly)), each estimate written down with its sources.

## What's next

- **A tested model** in place of the simple blend: one figure per flight for cancellation and one for delay, with a public check of how accurate it is.
- **A site that rebuilds itself every night**, so its pages no longer wait for a hand upload.
- **Five watched sessions** with outside readers, at least two of them not technical, to find the lines people misread before the site is launched.

## Data and license

Source: Israel Airports Authority flight board, published on [data.gov.il](https://data.gov.il) (dataset `flydata`), used under the [data.gov.il terms of use](https://data.gov.il/he/terms-of-use). The clauses that bear on this project are quoted in [docs/terms.md](docs/terms.md). This is an unofficial project, not affiliated with or endorsed by the Israel Airports Authority, data.gov.il or the State of Israel. The raw archive is not published.

The site's fonts are cut down from IBM Plex Sans Condensed and IBM Plex Sans Hebrew, under the SIL Open Font License 1.1; the licence's text is in [src/timeline/static/fonts/LICENSE.txt](src/timeline/static/fonts/LICENSE.txt), and the site serves it beside the fonts.

## Operating it

Deploying the collector, the alerts, clearing a block, development and costs: [docs/operations.md](docs/operations.md). If the collector reports `BLOCKED`, see [If it's blocked](docs/operations.md#if-its-blocked).
