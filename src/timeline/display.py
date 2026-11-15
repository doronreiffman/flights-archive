"""Rules shown only on pages (docs/flight-lookup.md, C9 and C10; "Words", the count line and the late line;
docs/flight-lookup-figures.md, A3, A17 and A24): a flight's label in lists and its DELAYED mark, a cancelled flight's
warning number, and the front page's figures.

Not part of the frozen rule: it reads the flights and figures of the frozen modules and adds only what pages show.
Pure functions over the rows `timeline.load.load` returns; model times are naive UTC.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from . import counting, words
from .counting import OPERATED, Flight
from .words import CANCELLED, DEPARTED, LANDED, NO_FINAL_UPDATE, UNKNOWN, UPCOMING


def label(f: Flight, by_id: dict[str, dict], last_fetch: datetime) -> str:
    """C10, the first that applies: 1, DEPARTED or LANDED when any of its numbers departed or landed; 2, UPCOMING, or
    NO FINAL UPDATE once its scheduled time is not after `last_fetch` (both naive UTC, as words.main_label reads
    them), while any of its numbers is still listed with a status other than cancelled (outcome "open"); 3, CANCELLED
    when a number ended listed as cancelled; 4, UNKNOWN. Rule 2 comes before rule 3: a flight with one number listed
    as cancelled and another still listed has not been listed as cancelled as a whole (A24)."""
    outcomes = {by_id[fid]["outcome"] for fid in f.numbers}
    if outcomes & OPERATED:
        return DEPARTED if "departed" in outcomes else LANDED
    if "open" in outcomes:
        return UPCOMING if f.key[2] > last_fetch else NO_FINAL_UPDATE  # key[2]: the slot's scheduled time
    if "canceled" in outcomes:
        return CANCELLED
    return UNKNOWN


def delayed(f: Flight, delayed_ids: set[str]) -> bool:
    """C10: DELAYED is added when any of the flight's numbers showed it (`delayed_ids`, by flight_id)."""
    return any(fid in delayed_ids for fid in f.numbers)


def warning_number(f: Flight, by_id: dict[str, dict]) -> str | None:
    """C9: the flight_id whose warning a cancelled flight shows in lists, its number whose cancelled listing came
    first: the earliest `canceled_first_seen_at` among its numbers that ended listed as cancelled (A17), the airline
    and then the flight number deciding a tie, in the lists' name order, as text (flights._newest_first): "LY 1302"
    before "LY 730". None when the flight's result is not cancelled (C2)."""
    if f.result != "cancelled":
        return None
    first = min((by_id[fid] for fid in f.numbers if by_id[fid]["outcome"] == "canceled"),
                key=lambda r: (r["canceled_first_seen_at"], r["airline"], r["flight_no"]))
    return first["flight_id"]


def _late(r: dict) -> str:
    """Where a number's first cancelled listing falls against its scheduled time, from the model's bracket (R8), in
    A17's order: "unplaced" when the bracket is only a bound (already cancelled when first seen, or spanning the
    hole), whatever its ends; "after" when it lies wholly after the time; "holds" when it holds the time; "before"
    otherwise."""
    if r["cancel_lead_censored"]:
        return "unplaced"
    if r["cancel_lead_max_min"] < 0:
        return "after"
    if r["cancel_lead_min"] < 0:
        return "holds"
    return "before"


@dataclass(frozen=True)
class Summary:
    """The front page's figures (docs/flight-lookup.md, "Words": the total, the table, the count line and the late
    line)."""
    figures: counting.Figures  # the total and the table's rows (C1 to C8)
    unknown: int  # closed flights with no known result, counted beside the rates (C4, A3)
    unknown_gap: int  # of them, those with a number that left the list during a hole in the record
    unknown_no_final: int  # the rest: they left the list with no final status
    late_after: int  # closed cancelled flights by where C9's number's first cancelled listing falls (A17)
    late_holds: int
    late_unplaced: int
    late_before: int
    first_record: date  # the Israel date of the first list


def summary(table: list[dict], obs: list[dict], snaps: list[dict]) -> Summary:
    """The front page's figures on the model `load` returns, as of its last sighting. The counting rule runs first,
    so that its named stops (counting.flights, counting.stretches) come before anything here reads a row."""
    figures = counting.figures(table, obs, snaps)
    flights_ = counting.flights(table, counting.last_sighting(snaps))
    by_id = {r["flight_id"]: r for r in table}
    unknown = [f for f in flights_ if f.closed and f.result == "unknown"]
    gap = sum(any(by_id[fid]["outcome"] == "gap" for fid in f.numbers) for f in unknown)  # A3: the hole first
    late = Counter(_late(by_id[warning_number(f, by_id)]) for f in flights_ if f.closed and f.result == "cancelled")
    return Summary(figures=figures, unknown=len(unknown), unknown_gap=gap, unknown_no_final=len(unknown) - gap,
                   late_after=late["after"], late_holds=late["holds"], late_unplaced=late["unplaced"],
                   late_before=late["before"], first_record=words.il_time(snaps[0]["fetched_at"]).date())
