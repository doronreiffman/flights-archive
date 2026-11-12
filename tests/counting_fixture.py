"""A model built by hand for the figures (docs/flight-lookup.md, C1 to C8; tests/test_counting.py,
test_the_hand_computed_fixture), shaped as `timeline.load.load` returns it: 650 flights over 6 Israel days, 29 October
to 3 November 2026, and 6 airlines.

Downloads every 30 minutes from 28 October 06:00 UTC, none from 02:30 to 07:30 on 31 October (a hole), the last at
4 November 10:00, seen again until 10:16:45 (the last sighting). So the flights scheduled up to 2 November 10:16:45 UTC
are closed (C4), the first days' flights were caught only in their last hours, and the hole takes out closed flights'
checkpoints in every row but the 70-hour one (there it falls on open flights only). Twelve flights are closed and
cancelled, each a case of its own (`cancelled`); the rest are everyday flights with delays, late listings, retimes and
codeshares (`everyday`), and the cases beside them (`others`): open flights, flights with no known result, retimes,
codeshares and the hole's edges.

Plain deterministic Python, so CI runs it. The figures it gives were computed outside the code, with A0's SQL
(docs/flight-lookup-figures.md) run over these same rows. All times are naive UTC; Israel time is UTC+2 throughout.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta

from counting_helpers import board, number, seen

ISRAEL = timedelta(hours=2)
START = datetime(2026, 10, 28, 6)  # the first download
LAST_FETCH = datetime(2026, 11, 4, 10)
LAST = datetime(2026, 11, 4, 10, 16, 45)  # the last sighting
BEFORE_HOLE, AFTER_HOLE = datetime(2026, 10, 31, 2), datetime(2026, 10, 31, 8)  # the downloads either side of the hole
AIRLINES = ("LY", "IZ", "6H", "EY", "W6", "UA")
AIRPORTS = ("ATH", "CDG", "FRA", "LHR", "FCO", "BUD", "WAW")  # everyday flights only; the other cases fly elsewhere


def _fetches() -> list[datetime]:
    out, t = [], START
    while t <= LAST_FETCH:
        if not BEFORE_HOLE < t < AFTER_HOLE:
            out.append(t)
        t += timedelta(minutes=30)
    return out


FETCHES = _fetches()


def _until(fetch: datetime) -> datetime:
    """Each download is seen again (R9) until two minutes before the next one, the last until LAST."""
    return LAST if fetch == LAST_FETCH else fetch + timedelta(minutes=28)


def snapshots() -> list[dict]:
    return board(*((f, _until(f)) for f in FETCHES))


def utc(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute)


def _h(hours: float) -> timedelta:
    return timedelta(hours=hours)


def listing(airline: str, flight_no: str, direction: str, airport: str, sched: datetime, *, outcome: str,
            listed: float = -72, changes: tuple = (), first_sched: datetime | None = None, status: str = "ON TIME",
            terminal: int = 3, desks: str = "", left: datetime | None = None) -> tuple[dict, list[dict]]:
    """One flight number: its flights-table row and its observations. `sched` is its final scheduled time. It is
    first on the list `listed` hours from `sched` (or at the first download), showing `first_sched` (if retimed, else
    `sched`) and `status`. Each change is (hours from `sched`, {observation field: value}); a new scheduled time
    brings its expected time along unless one is given. A number that departed or landed shows it 20 minutes after
    its expected time. A download records the state of the list at its time, when it differs from the last recorded.
    The number's last download is the last one at or before `left` (by default a day after `sched`), and it is last
    seen 28 minutes after it, or at the last sighting."""
    shown = first_sched or sched
    fid = f"{airline}{flight_no}-{sched + ISRAEL:%m%d}"
    events = [(sched + _h(dh), ch) for dh, ch in changes]
    if outcome in ("departed", "landed"):
        est = shown
        for _, ch in sorted(events, key=lambda e: e[0]):
            est = ch.get("est_utc", ch.get("sched_utc", est))
        events.append((est + timedelta(minutes=20), {"status": "DEPARTED" if outcome == "departed" else "LANDED"}))
    events.sort(key=lambda e: e[0])
    first = FETCHES[bisect_left(FETCHES, max(sched + _h(listed), START))]
    last = FETCHES[bisect_right(FETCHES, min(left or sched + _h(24), LAST)) - 1]
    now = {"sched_utc": shown, "est_utc": shown, "status": status, "terminal": terminal, "counters": desks}
    obs, k = [], 0
    for rn, f in enumerate(FETCHES, start=1):
        if not first <= f <= last:
            continue
        while k < len(events) and events[k][0] <= f:
            ch = events[k][1]
            now |= ch
            if "sched_utc" in ch and "est_utc" not in ch:
                now["est_utc"] = ch["sched_utc"]
            k += 1
        if not obs or {key: obs[-1][key] for key in now} != now:
            obs.append(seen(fid, rn, f, **now))
    end = obs[-1]
    assert end["sched_utc"] == sched, (fid, "retimed after it left the list")
    row = number(fid, sched, airline=airline, flight_no=flight_no, direction=direction, airport=airport,
                 sched_local_first=shown + ISRAEL, est_utc_final=end["est_utc"], terminal_final=end["terminal"],
                 counters_final=end["counters"], outcome=outcome, first_seen_at=obs[0]["observed_at"],
                 last_seen_at=_until(last))
    return row, obs


CANCELED = {"status": "CANCELED"}


def cancelled() -> list[tuple[dict, list[dict]]]:
    """The twelve closed cancelled flights. Beside each, the rows it is in, worked out by hand from the downloads:
    a number first shown at the first download (28 Oct 06:00) passes no earlier checkpoint, and none inside the hole
    (31 Oct 02:28 to 08:00)."""
    return [
        # LY 1315, 29 Oct 04:00: first seen 22 hours before, cancelled 2 hours before. 12, 6, 3.
        listing("LY", "1315", "D", "LCA", utc(10, 29, 4), outcome="canceled", desks="51-58", changes=((-2, CANCELED),)),
        # IZ 1211, 30 Oct 09:00: already cancelled when first seen. The total only.
        listing("IZ", "1211", "A", "VIE", utc(10, 30, 9), outcome="canceled", status="CANCELED"),
        # 6H 1503, 1 Nov 09:00: listed on time until an hour after its time (C7). All six.
        listing("6H", "1503", "D", "SOF", utc(11, 1, 9), outcome="canceled", desks="61-66", changes=((1, CANCELED),)),
        # EY 1597, 31 Oct 10:00: cancelled 30 hours before. 70, 48.
        listing("EY", "1597", "D", "AUH", utc(10, 31, 10), outcome="canceled", desks="71-78",
                changes=((-30, CANCELED),)),
        # W6 2741 and UA 9002, one arrival, 31 Oct 14:00 (the same expected time, terminal and no desks): W6 2741
        # cancelled 50 hours before, UA 9002 20 hours before. 70, 48 and 24, by UA 9002.
        listing("W6", "2741", "A", "OTP", utc(10, 31, 14), outcome="canceled", changes=((-50, CANCELED),)),
        listing("UA", "9002", "A", "OTP", utc(10, 31, 14), outcome="canceled", changes=((-20, CANCELED),)),
        # UA 1085, 1 Nov 20:00: cancelled 4 hours before. 70 to 6.
        listing("UA", "1085", "D", "EWR", utc(11, 1, 20), outcome="canceled", desks="81-88", changes=((-4, CANCELED),)),
        # LY 1002, 1 Nov 11:00: cancelled 14 hours before, back on time 8 hours before, cancelled an hour before
        # (C3). 70, 48, 24, 6 and 3; not 12.
        listing("LY", "1002", "A", "JFK", utc(11, 1, 11), outcome="canceled",
                changes=((-14, CANCELED), (-8, {"status": "ON TIME"}), (-1, CANCELED))),
        # IZ 1121, 2 Nov 06:00: first listed 20 hours before, cancelled 5 hours before. 12, 6.
        listing("IZ", "1121", "D", "TBS", utc(11, 2, 6), outcome="canceled", desks="91-98", listed=-20,
                changes=((-5, CANCELED),)),
        # 6H 1061, 2 Nov 10:00: first shown at 09:00, retimed 31 hours before, cancelled 2 hours before. 70 and 48
        # by 09:00, the rest by 10:00: all six.
        listing("6H", "1061", "A", "KRK", utc(11, 2, 10), outcome="canceled", first_sched=utc(11, 2, 9), listed=-73,
                changes=((-31, {"sched_utc": utc(11, 2, 10)}), (-2, CANCELED))),
        # EY 1611, 29 Oct 18:00: first seen 36 hours before, cancelled 7 hours before. 24, 12.
        listing("EY", "1611", "D", "AUH", utc(10, 29, 18), outcome="canceled", desks="71-78",
                changes=((-7, CANCELED),)),
        # W6 4301 and LY 8301, one departure, 30 Oct 12:00, first seen 54 hours before, both cancelled 3.5 hours
        # before. 48, 24, 12, 6.
        listing("W6", "4301", "D", "TBS", utc(10, 30, 12), outcome="canceled", desks="41-46",
                changes=((-3.5, CANCELED),)),
        listing("LY", "8301", "D", "TBS", utc(10, 30, 12), outcome="canceled", desks="41-46",
                changes=((-3.5, CANCELED),)),
        # UA 1091, 31 Oct 15:00: cancelled an hour before; its 12-hour point falls in the hole. 70, 48, 24, 6, 3.
        listing("UA", "1091", "A", "EWR", utc(10, 31, 15), outcome="canceled", changes=((-1, CANCELED),)),
    ]


def others() -> list[tuple[dict, list[dict]]]:
    """The cases beside the everyday flights: 18 flights, 21 numbers."""
    return [
        # Open: scheduled after 2 Nov 10:16:45, so in no rate (C4), cancelled though they are.
        listing("LY", "1341", "D", "LCA", utc(11, 2, 15), outcome="canceled", desks="51-58", changes=((-6, CANCELED),)),
        listing("EY", "1621", "A", "AUH", utc(11, 3, 9), outcome="canceled", changes=((0.5, CANCELED),)),
        # Open by its final time, closed by its first: retimed from 09:30 to 11:00 on 2 Nov.
        listing("UA", "1701", "D", "EWR", utc(11, 2, 11), outcome="departed", desks="81-88",
                first_sched=utc(11, 2, 9, 30), changes=((-11.5, {"sched_utc": utc(11, 2, 11)}),)),
        # No known result (C2), in no rate. IZ 7 and W6 2803 left the list during the hole; 6H 77 was last seen 4
        # hours before its time, UA 31 2.5 hours after it, LY 1009 (open) 4 hours before it.
        listing("IZ", "7", "D", "SOF", utc(10, 31, 5), outcome="gap", desks="91-98", left=BEFORE_HOLE),
        listing("W6", "2803", "A", "OTP", utc(10, 31, 6, 30), outcome="gap", left=BEFORE_HOLE),
        listing("6H", "77", "A", "KRK", utc(11, 1, 12), outcome="vanished", left=utc(11, 1, 7, 30)),
        listing("UA", "31", "D", "EWR", utc(10, 30, 20), outcome="vanished", desks="81-88", left=utc(10, 30, 22)),
        listing("LY", "1009", "D", "LCA", utc(11, 3, 6), outcome="vanished", desks="51-58", left=utc(11, 3, 1, 30)),
        # IZ 1083, cancelled 40 hours before, and IZ 83, which landed 15 minutes early: one flight of one airline
        # (C1), which operated (C2).
        listing("IZ", "1083", "A", "RHO", utc(10, 30, 3), outcome="canceled", changes=((-40, CANCELED),)),
        listing("IZ", "83", "A", "RHO", utc(10, 30, 3), outcome="landed",
                changes=((-2, {"est_utc": utc(10, 30, 2, 45), "status": "EARLY"}),)),
        # EY 1903, first shown 1 Nov 18:00, retimed to 08:00 the same day, 20 hours before its new time: 70 and 48
        # by 18:00, 12, 6 and 3 by 08:00, and no 24-hour point at all.
        listing("EY", "1903", "D", "AUH", utc(11, 1, 8), outcome="departed", desks="71-78",
                first_sched=utc(11, 1, 18), listed=-62, changes=((-20, {"sched_utc": utc(11, 1, 8)}),)),
        # 6H 1801, retimed from 30 Oct 23:30 to 31 Oct 00:40 Israel time: a flight of 31 October.
        listing("6H", "1801", "A", "SKG", utc(10, 30, 22, 40), outcome="landed", first_sched=utc(10, 30, 21, 30),
                changes=((-6, {"sched_utc": utc(10, 30, 22, 40)}),)),
        # LY 5, UA 6801 and EY 9405, one departure; UA 6801 first listed 30 hours before.
        *(listing(al, no, "D", "JFK", utc(10, 30, 19), outcome="departed", desks="21-29", listed=listed,
                  changes=((-1, {"est_utc": utc(10, 30, 19, 25), "status": "DELAYED"}),))
          for al, no, listed in (("LY", "5", -72), ("UA", "6801", -30), ("EY", "9405", -72))),
        # 6H 1121 and W6 1131, the same slot, two terminals: two flights.
        listing("6H", "1121", "D", "LCA", utc(10, 31, 19), outcome="departed", terminal=1, desks="301-310"),
        listing("W6", "1131", "D", "LCA", utc(10, 31, 19), outcome="departed", terminal=3, desks="401-410"),
        # The hole's edges are not inside it: UA 1401's 3-hour point is the last sighting before the hole, 6H 1411's
        # the first download after it.
        listing("UA", "1401", "D", "EWR", utc(10, 31, 5, 28), outcome="departed", desks="81-88"),
        listing("6H", "1411", "A", "SKG", utc(10, 31, 11), outcome="landed"),
        # IZ 1301: cancelled when first seen, back on time 20 hours before its time, departed (C3). Its 12-hour point
        # falls in the hole: 6, 3.
        listing("IZ", "1301", "D", "SOF", utc(10, 31, 18), outcome="departed", desks="91-98", status="CANCELED",
                changes=((-20, {"status": "ON TIME"}),)),
        # W6 1505 shows no status from 26 to 20 hours before (the model has 4 such observations), and is in the
        # 24-hour row like any status but cancelled.
        listing("W6", "1505", "A", "OTP", utc(11, 1, 16), outcome="landed",
                changes=((-26, {"status": ""}), (-20, {"status": "ON TIME"}))),
    ]


def everyday(count: int) -> list[tuple[dict, list[dict]]]:
    """`count` everyday flights: on each Israel day each airline flies 17 (and the first pairs of day and airline an
    18th, up to `count`), 80 minutes apart, departures and arrivals in turn. One in ten codeshares with another
    airline (whose number is the lower one on every other day; half these partners are first listed 30 hours before);
    one in ten is DELAYED from 8 hours before; one in twenty is first listed 30 hours before, one in twenty 9 hours
    before, and one in twenty retimed an hour later 20 hours before. Arrivals show NOT FINAL from 7 hours before,
    departures FINAL from 2 hours before."""
    out = []
    pairs = [(d, a) for d in range(6) for a in range(6)]
    extra = count - 17 * len(pairs)
    assert 0 <= extra <= len(pairs), count
    for p, (d, a) in enumerate(pairs):
        midnight = utc(10, 28, 22) + timedelta(days=d)  # 00:00 in Israel on 29 October, plus d days
        airline = AIRLINES[a]
        for j in range(17 + (p < extra)):
            sched = midnight + timedelta(minutes=35 + 80 * j + 7 * a)
            v = (3 * d + 5 * a + 7 * j) % 20
            direction = "DA"[j % 2]
            desks = f"{20 * a + 1}-{20 * a + 8}" if direction == "D" else ""
            outcome = "departed" if direction == "D" else "landed"
            listed = -30 if v == 1 else -9 if v == 2 else -72
            first_sched = sched - timedelta(hours=1) if v == 5 else None
            if v in (4, 9):
                changes = ((-8, {"est_utc": sched + timedelta(minutes=45), "status": "DELAYED"}),)
            elif direction == "A":
                changes = ((-7, {"status": "NOT FINAL"}),)
            else:
                changes = ((-2, {"status": "FINAL"}),)
            if v == 5:
                changes = ((-20, {"sched_utc": sched}),) + changes
            kw = dict(outcome=outcome, listed=listed, changes=changes, first_sched=first_sched, desks=desks)
            airport = AIRPORTS[(a + j) % len(AIRPORTS)]
            out.append(listing(airline, str(100 * (a + 1) + j), direction, airport, sched, **kw))
            if v in (3, 13):
                partner = AIRLINES[(a + 3) % 6]
                no = str(9000 + 100 * a + j) if d % 2 == 0 else str(10 + j)
                own = kw | {"listed": -30 if v == 13 else listed}
                out.append(listing(partner, no, direction, airport, sched, **own))
    return out


FLIGHTS = 650
SPECIAL_FLIGHTS = 12 + 18  # `cancelled` and `others`, counted as C1 groups them


def model() -> tuple[list[dict], list[dict], list[dict]]:
    """(table, obs, snaps), as `timeline.load.load` returns them."""
    numbers = cancelled() + others() + everyday(FLIGHTS - SPECIAL_FLIGHTS)
    table = [row for row, _ in numbers]
    assert len({r["flight_id"] for r in table}) == len(table)
    obs = sorted((o for _, own in numbers for o in own), key=lambda o: (o["flight_id"], o["snap_rn"]))
    return table, obs, snapshots()
