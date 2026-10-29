Source: Israel Airports Authority flight board, published on data.gov.il (dataset flydata, resource e83f763b-b7d7-479e-b172-ae981ddc6de5). Built by flights-archive from archived snapshots.

## Coverage

| snapshots | first | last | rows min | rows max | stored twice | duplicate rows | key conflicts | unparsed sched | missing est |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 2026-10-27 18:04:46 | 2026-10-29 13:04:45 | 1905 | 2260 | 0 | 0 | 0 | 0 | 0 |

Snapshots dropped: 0 incomplete (fewer rows than the reply's total), 0 identical to the previous one.

Collection gaps over an hour (snapshot, hours since the previous one):

| snapshot | gap h |
|---|---|
| 2026-10-29 12:29:03 | 42.1 |

## Flights

| direction | outcome | flights |
|---|---|---|
| A | open | 638 |
| A | landed | 630 |
| A | gap | 164 |
| A | canceled | 10 |
| D | open | 644 |
| D | departed | 559 |
| D | gap | 218 |
| D | canceled | 9 |

Outcomes: departed / landed / canceled are final statuses; open is still on the latest snapshot; gap left the board during a collection hole (unknown fate); vanished left early with a non-final status and no retime (possible unflagged cancellation); dropped rolled off after its time without a final status.

## Observations

| kind | rows |
|---|---|
| first | 2872 |
| change | 1083 |

Fields that change (one count per changed field, `change` rows only):

| field | changes |
|---|---|
| status | 747 |
| status_he | 747 |
| est_local | 716 |
| counters | 498 |
| zone | 494 |

Status going back from DEPARTED/LANDED to something else: 0 observations.
DST flags (sched ambiguous, sched nonexistent, est ambiguous, est nonexistent): (0, 0, 0, 0).

## Retimes (R4)

Flights with a retime link: 0 (most links in one flight: 0).
Vanished flights that shared the board with a same-number flight within 12 h (retimes R4 cannot link if the board overlaps old and new rows): 0.

## Codeshares (R5, R6)

| basis | group size | flights |
|---|---|---|
| counters | 1 | 663 |
| counters | 2 | 312 |
| counters | 3 | 162 |
| counters | 4 | 156 |
| counters | 5 | 100 |
| counters | 6 | 30 |
| time-only | 1 | 652 |
| time-only | 2 | 308 |
| time-only | 3 | 180 |
| time-only | 4 | 224 |
| time-only | 5 | 85 |

Operating carrier is a guess (group of two or more) for 1557 of 2872 flights.

## Cancellations (R8)

Flights seen CANCELED: 19. Already cancelled when first seen: 11. Later un-cancelled: 0. Lead time usable (not censored by first sight or a collection hole): 0.
No usable cancellation lead time yet.

## Estimated minus scheduled time (meaning unconfirmed)

| direction | final status | flights | median min |
|---|---|---|---|
| A | NOT FINAL | 696 | 0.0 |
| A | LANDED | 630 | -7.0 |
| A | FINAL | 92 | -3.0 |
| A | LANDING | 10 | -4.0 |
| A | CANCELED | 10 | 0.0 |
| A | DELAYED | 4 | 49.0 |
| D | ON TIME | 858 | 0.0 |
| D | DEPARTED | 559 | 20.0 |
| D | CANCELED | 9 | 0.0 |
| D | EARLY | 3 | -180.0 |
| D | DELAYED | 1 | 270.0 |

The datastore's field notes call CHPTOL "AnticipatedTimeLocal"; whether it is gate or runway time is still unknown, so no delay statistics are published from it.
