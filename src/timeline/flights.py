"""The model's rows made ready to show: display rows, flights, counts, page addresses, anchors and search entries
(docs/site-redesign.md: "Who is a flight", "Labels", "Codeshares", "Names", "Pages", "How it is built").

Pure functions; every text comes from `words`. A "flight" is the members of one codeshare group on one day that
share the main label, the DELAYED flag and the warning; every count here counts flights that way.
"""
from __future__ import annotations

import re
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from . import words

KNOWN = (words.DEPARTED, words.LANDED, words.CANCELLED)  # labels with a known outcome (the headline's Y)


@dataclass(frozen=True)
class Row:
    """One row of the model's flights table (a retime chain is one row), ready to show."""
    flight_id: str
    airline: str
    flight_no: str
    airline_name: str  # as the airport publishes it, double spaces included
    direction: str
    airport: str
    city: str  # title-cased (string.capwords)
    city_he: str | None
    day: date  # the date of sched_final: the day the row is shown on
    sched_first: datetime  # Israel wall-clock, as in the model
    sched_final: datetime
    sched_utc_final: datetime  # the model's naive UTC: past or ahead is decided on it
    label: str
    delayed: bool
    warning: str | None
    warning_note: str | None
    label_note: str | None
    changed_back: str | None
    last_expected: str | None
    page: str  # "flight/LY5115-D.html"
    anchor: str  # "2026-10-28-1630-KUT"
    group_id: str
    lines: tuple[tuple[str, str], ...]  # what changed, for its day


@dataclass(frozen=True)
class DayInfo:
    day: date
    total: int
    cancelled: int
    unknown: int
    state: str  # "past" | "today" | "ahead"
    partial: bool


# --- addresses and anchors -------------------------------------------------------------------------

def _safe(text: str) -> str:
    """Letters, digits and hyphen only (ASCII), so an address or anchor needs no escaping anywhere."""
    return re.sub(r"[^A-Za-z0-9-]", "", text)


def row_anchor(sched_local_first: datetime, airport: str) -> str:
    """A row's link target on its flight page. From the first scheduled time, so it never changes when the flight
    is retimed or a same-number flight appears later; with the airport, so one number leaving twice at one time
    to two airports (LY 5115 on 28 October) gets two."""
    return f"{sched_local_first:%Y-%m-%d-%H%M}-{_safe(airport)}"


def page_address(airline: str, flight_no: str, direction: str) -> str:
    return f"flight/{_safe(f'{airline}{flight_no}-{direction}')}.html"


def check_unique(rows: list[Row]) -> None:
    """Stop the build rather than overwrite a page: two numbers whose addresses match once case is ignored (`AB` +
    `12` and `A` + `B12`; a disk that ignores case, like the owner's Mac's, would write both to one file), or two
    rows of one page on one anchor. Partners share anchor strings across pages, which is fine."""
    numbers: dict[str, dict[tuple[str, str, str], str]] = {}
    for r in rows:
        numbers.setdefault(r.page.lower(), {})[(r.airline, r.flight_no, r.direction)] = r.page
    for nums in numbers.values():
        if len(nums) > 1:
            names = " and ".join(f"{a} {n} ({d}) at {page}" for (a, n, d), page in sorted(nums.items()))
            raise ValueError(f"two flight numbers would share the same page: {names}")
    seen: dict[tuple[str, str], str] = {}
    for r in rows:
        if seen.setdefault((r.page, r.anchor), r.flight_id) != r.flight_id:
            raise ValueError(f"two rows of {r.airline} {r.flight_no} ({r.direction}) would share the same anchor "
                             f"#{r.anchor} on {r.page}")


# --- display rows ----------------------------------------------------------------------------------

def make_rows(flights: list[dict], obs: list[dict], last_fetch: datetime, gap_hours: float) -> list[Row]:
    """One Row per flights-table row, in the order given. Each row's change lines read its own records only, in
    model order (snap_rn) from its earliest, written for the day of its final scheduled time. The label is decided
    on the model's UTC times: the Israel wall-clock time would make 29 October's late-evening flights UPCOMING."""
    by_flight: dict[str, list[dict]] = {}
    for o in obs:
        by_flight.setdefault(o["flight_id"], []).append(o)
    rows = []
    for f in flights:
        own = sorted(by_flight.get(f["flight_id"], []), key=lambda o: o["snap_rn"])
        day = f["sched_local_final"].date()
        label = words.main_label(f["outcome"], f["sched_utc_final"], last_fetch)
        rows.append(Row(
            flight_id=f["flight_id"], airline=f["airline"], flight_no=f["flight_no"],
            airline_name=f["airline_name"], direction=f["direction"], airport=f["airport"],
            city=string.capwords(f["city_en"]), city_he=f["city_he"], day=day,
            sched_first=f["sched_local_first"], sched_final=f["sched_local_final"],
            sched_utc_final=f["sched_utc_final"], label=label,
            delayed=any(o["status"] == "DELAYED" for o in own),
            warning=words.warning(f), warning_note=words.warning_note(f), label_note=words.label_note(f),
            changed_back=words.changed_back(f, label), last_expected=words.last_expected(f, day),
            page=page_address(f["airline"], f["flight_no"], f["direction"]),
            anchor=row_anchor(f["sched_local_first"], f["airport"]), group_id=f["codeshare_group_id"],
            lines=tuple(words.change_lines(own, f["direction"], day, gap_hours))))
    return rows


def page_title(rows: list[Row]) -> str:
    """The flight page's title, from the rows of one number and direction: "TO 3459, Tel Aviv to Paris",
    "LY 002, from Paris to Tel Aviv". A number with more than one city names none: "LY 5115, from Tel Aviv",
    "LY 5116, to Tel Aviv"."""
    r = rows[0]
    number = f"{r.airline} {r.flight_no}"
    if len({x.city for x in rows}) > 1:
        return f"{number}, from Tel Aviv" if r.direction == "D" else f"{number}, to Tel Aviv"
    return f"{number}, Tel Aviv to {r.city}" if r.direction == "D" else f"{number}, from {r.city} to Tel Aviv"


# --- flights ---------------------------------------------------------------------------------------

def _flight_key(r: Row) -> tuple:
    """What members of one codeshare group must share to be shown and counted as one flight."""
    return r.day, r.group_id, r.label, r.delayed, r.warning


def group_flights(rows: list[Row]) -> list[tuple[Row, ...]]:
    """Rows as flights, in the order of each flight's first row; members in row order."""
    out: dict[tuple, list[Row]] = {}
    for r in rows:
        out.setdefault(_flight_key(r), []).append(r)
    return [tuple(members) for members in out.values()]


def partners(rows: list[Row]) -> dict[str, tuple[Row, ...]]:
    """flight_id -> the other members of its flight (after the split): only they are "probably the same flight"."""
    return {r.flight_id: tuple(p for p in fl if p.flight_id != r.flight_id)
            for fl in group_flights(rows) for r in fl}


# --- counts ----------------------------------------------------------------------------------------

def day_infos(flights_: list[tuple[Row, ...]], last_fetch: datetime, partial_days: set[date]) -> list[DayInfo]:
    """Per day with flights: counts, and past, today or ahead. Today is the Israel date of the last record: at
    22:30 UTC on 29 October it is already 30 October in Israel."""
    today = words.il_time(last_fetch).date()
    labels: dict[date, list[str]] = {}
    for fl in flights_:
        labels.setdefault(fl[0].day, []).append(fl[0].label)
    return [DayInfo(day=day, total=len(ls), cancelled=ls.count(words.CANCELLED), unknown=ls.count(words.UNKNOWN),
                    state="past" if day < today else "today" if day == today else "ahead",
                    partial=day in partial_days)
            for day, ls in sorted(labels.items())]


def headline_counts(flights_: list[tuple[Row, ...]], last_fetch: datetime) -> tuple[int, int]:
    """(cancelled, known) over the flights whose scheduled time has passed (UTC, at or before the last record):
    those labelled CANCELLED, and those labelled DEPARTED, LANDED or CANCELLED."""
    labels = [fl[0].label for fl in flights_ if fl[0].sched_utc_final <= last_fetch]
    return labels.count(words.CANCELLED), sum(label in KNOWN for label in labels)


# --- the featured flight and recent cancellations --------------------------------------------------

def _newest_first(items: list, row: Callable[[object], Row] = lambda r: r) -> list:
    """Latest final scheduled time first; ties by airline and number (then direction, airport and id, so the order
    never depends on the input's)."""
    by_name = sorted(items, key=lambda x: (row(x).airline, row(x).flight_no, row(x).direction, row(x).airport,
                                           row(x).flight_id))
    return sorted(by_name, key=lambda x: row(x).sched_final, reverse=True)  # stable: ties keep the name order


def featured(rows: list[Row], censored: dict[str, bool]) -> Row | None:
    """The front page's story: the most recent cancelled row whose warning is not censored (`censored` from the
    model's cancel_lead_censored; a missing flag counts as censored); if none, the cancelled row with the most
    change lines, the most recent first on a tie."""
    cancelled = [r for r in rows if r.label == words.CANCELLED]
    clean = [r for r in cancelled if censored[r.flight_id] is False]
    if clean:
        return _newest_first(clean)[0]
    if cancelled:
        return sorted(_newest_first(cancelled), key=lambda r: len(r.lines), reverse=True)[0]
    return None


def recent_cancellations(flights_: list[tuple[Row, ...]], n: int = 10) -> list[tuple[Row, ...]]:
    """Cancelled flights, newest scheduled time first (upcoming ones included), at most n; a flight goes by its
    first row."""
    return _newest_first([fl for fl in flights_ if fl[0].label == words.CANCELLED], lambda fl: fl[0])[:n]


# --- search ----------------------------------------------------------------------------------------

def number_keys(airline: str, flight_no: str) -> list[str]:
    """Code and number as published and without leading zeros, then the number alone both ways (people type
    "991"); lower case. Built from the separate fields: codes like 6H and numbers like 0115A cannot be split
    back out of a joined string."""
    code, number = airline.lower(), flight_no.lower()
    bare = number.lstrip("0") or "0"
    return list(dict.fromkeys(k for k in (code + number, code + bare, number, bare) if k))


def place_keys(city: str, airport: str) -> list[str]:
    """City without spaces and airport code, lower case."""
    return list(dict.fromkeys(k for k in (city.lower().replace(" ", ""), airport.lower()) if k))


def search_entries(rows: list[Row]) -> list[dict]:
    """One entry per flight number and direction, sorted by airline, number, direction: its number keys, the
    sorted union of its rows' place keys (a number can fly to two cities), its page title and address."""
    by_number: dict[tuple[str, str, str], list[Row]] = {}
    for r in rows:
        by_number.setdefault((r.airline, r.flight_no, r.direction), []).append(r)
    return [{"n": number_keys(airline, flight_no),
             "p": sorted({k for r in rs for k in place_keys(r.city, r.airport)}),
             "t": page_title(rs), "u": rs[0].page}
            for (airline, flight_no, _), rs in sorted(by_number.items())]
