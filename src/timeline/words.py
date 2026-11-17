"""Every sentence and label of the site, and the time helpers they use (docs/site-redesign.md, "Words").

Pure functions from model values to text. Model times (`*_at`, `*_utc`) are naive UTC; the airport's times
(`*_local`) are Israel wall-clock as published. Ranges and lower bounds only: a notice is never a measured
moment, and no delay is shown under an hour (display.delayed_an_hour).
"""
from __future__ import annotations

import math
import string
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from timeline.rates import Rate, round_middle, round_range

if TYPE_CHECKING:  # display imports this module's label names, so the type is for hints only
    from timeline.display import Summary

ISRAEL = ZoneInfo("Asia/Jerusalem")

UNOFFICIAL = ("This site is unofficial: it isn't run by, connected to or approved by the Israel Airports Authority, "
              "data.gov.il or the State of Israel.")
SOURCE_SHORT = "Flight data: Israel Airports Authority, published on data.gov.il."
TIMES_NOTE = "All times are Israel time."
ESTIMATES = "The chances on this site are estimates from past flights, not promises."
MEANS = "What the numbers mean"  # the footer's link to that section of how-it-works.html
MEANS_ANCHOR = "what-the-numbers-mean"
PLACEHOLDER = "[owner's wording]"  # the upload check refuses a site that still contains it
BUILT_BY = "Doron Reiffman (linkedin.com/in/doronreiffman)"
CODE_URL = "https://github.com/doronreiffman/flights-archive"
EXPECTED_NOTE = ("Expected times are the airport's own. Delays under an hour aren't counted, because the airport "
                 "doesn't say whether its time means leaving the gate or taking off.")
FINAL_NOTE = "“Final” and “not final” are the airport's own words. It doesn't explain them."
NOTICE_GIVEN = "Notice given"  # the column and phone label for a cancellation's notice, in lists

DEPARTED, LANDED, CANCELLED, UPCOMING, NO_NEWS_YET, UNKNOWN = (
    "DEPARTED", "LANDED", "CANCELLED", "UPCOMING", "NO NEWS YET", "UNKNOWN")
LABEL_ORDER = (DEPARTED, LANDED, CANCELLED, UPCOMING, NO_NEWS_YET, UNKNOWN)


# --- times -----------------------------------------------------------------------------------------

def il_time(utc_naive: datetime) -> datetime:
    """A naive UTC value from the model, in Israel time. The UTC mark is explicit: a naive astimezone()
    would read the value in the machine's own zone (on an Israeli Mac, 18:04Z would stay 18:04)."""
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(ISRAEL)


def clock(local: datetime, page_date: date | None) -> str:
    """HH:MM for a time on the page's date, with day and month for any other date (always, without a page date)."""
    return f"{local:%H:%M}" if local.date() == page_date else f"{local.day} {local:%b %H:%M}"


def hours(n: int) -> str:
    return "1 hour" if n == 1 else f"{n} hours"


def _down(minutes: float) -> int:
    """Whole hours rounded down: the lower end of a range (the spec's h(x, down))."""
    return math.floor(minutes / 60)


def _up(minutes: float) -> int:
    """Whole hours rounded up: the upper end of a range (h(x, up))."""
    return math.ceil(minutes / 60)


def _verb(direction: str) -> str:
    return "leave" if direction == "D" else "land"


# --- labels ----------------------------------------------------------------------------------------

def main_label(outcome: str, sched_utc_final: datetime, last_fetch: datetime) -> str:
    """The flight's one main label. Both times are the model's naive UTC: an Israel wall-clock scheduled time
    would turn 29 October's late-evening flights (23:30 to 23:55, last record 22:02 UTC) into UPCOMING."""
    match outcome:
        case "departed":
            return DEPARTED
        case "landed":
            return LANDED
        case "canceled":
            return CANCELLED
        case "open":
            return UPCOMING if sched_utc_final > last_fetch else NO_NEWS_YET
        case "gap" | "vanished" | "dropped":
            return UNKNOWN
    raise ValueError(f"unknown outcome {outcome!r}")


def label_note(f: dict, label: str, ahead: bool) -> str | None:
    """The line under a NO NEWS YET or UNKNOWN label (docs/site-redesign.md, "Labels"); `ahead` is whether the
    flight's day is still ahead of the last sighting, which adds a sentence to a vanished flight's."""
    if label == NO_NEWS_YET:
        return "Its time has passed, and the airport hasn't said how it ended."
    match f["outcome"]:
        case "gap":
            return "There's no record of how this flight ended."
        case "vanished":
            early = _down((f["sched_utc_final"] - f["last_seen_at"]).total_seconds() / 60)
            note = (f"The airport removed this flight {hours(early)} early without saying why. "
                    "It may have been cancelled or moved to another time.")
            return f"{note} Check with your airline." if ahead else note
        case "dropped":
            return "The airport removed this flight without saying why."
    return None


def changed_back(f: dict, label: str) -> str | None:
    """A line under the final label when the flight was marked cancelled, then back on."""
    if not f["uncanceled"]:  # NULL (cancelled from its earliest record on) counts as false
        return None
    if label == CANCELLED:
        return "Cancelled, back on, then cancelled again."
    return "Marked cancelled for a while, then back on."


def scheduled(direction: str, local: datetime, page_date: date | None) -> str:
    return f"scheduled to {_verb(direction)} at {clock(local, page_date)}"


def shows_expected(est: datetime | None, sched: datetime, label: str) -> bool:
    """Whether a day's time line says "landed around", "left around" or "expected" (and so needs EXPECTED_NOTE)."""
    if est is None:
        return False
    return label in (LANDED, DEPARTED) or (label in (UPCOMING, NO_NEWS_YET, UNKNOWN) and est != sched)


def time_line(direction: str, sched: datetime, est: datetime | None, label: str, page_date: date) -> str:
    """A day's time line, from Israel wall-clock times (docs/site-redesign.md, "Labels"). A day that landed or left
    shows both times, even when they are the same; a day with no final word shows the expected time when it differs
    from the scheduled one; no difference is computed on the line."""
    if not shows_expected(est, sched, label):
        return scheduled(direction, sched, page_date)
    if label in (LANDED, DEPARTED):
        said = "left" if direction == "D" else "landed"
        return f"scheduled {clock(sched, page_date)} · {said} around {clock(est, page_date)}"
    return f"scheduled {clock(sched, page_date)} · expected {clock(est, page_date)}"


# --- notice ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Notice:
    """How long before its scheduled time the airport's list already showed the flight as cancelled: the sentence
    for a flight page, and the short form for a list's "Notice given"."""
    sentence: str
    short: str


def _at_least(lo: float) -> str:
    """"Cancelled with at least 23 hours' notice." ("at least" always follows "with"); "1 hour's notice" for one."""
    h = _down(lo)
    return f"Cancelled with at least {h} hour's notice." if h == 1 else f"Cancelled with at least {h} hours' notice."


def notice(f: dict) -> Notice | None:
    """The notice table of docs/site-redesign.md ("Notice"), in order; the first matching rule wins, so each condition
    leaves out what an earlier rule already took. `lo` is from the first record showing the flight cancelled to its
    scheduled time, `hi` from the record before that (None when the earliest record already showed it cancelled)."""
    if f["outcome"] != "canceled":
        return None
    lo, hi, censored = f["cancel_lead_min"], f["cancel_lead_max_min"], f["cancel_lead_censored"]
    gap = "(There's a gap in the records then.)"
    if hi is None:
        if lo >= 60:  # rule 1
            return Notice(f"{_at_least(lo)} It was already cancelled when it first appeared.", f"{_down(lo)}+ hours")
        return Notice("How much notice is unknown: it was already cancelled when it first appeared.", "unknown")
    if hi < 0 and not censored:  # a non-censored range is at most an hour wide; -hi is its nearer end
        should = f"it should have {'left' if f['direction'] == 'D' else 'landed'}"
        if -lo < 60:
            amount = "less than an hour"
        elif -hi < 120:
            amount = "about an hour"
        else:
            amount = f"about {hours(_down(-hi))}"
        return Notice(f"Cancelled with no notice: it was marked cancelled {amount} after {should}.", "none")
    if hi < 0:
        return Notice("Cancelled with no notice: it was only marked cancelled after its scheduled time. " + gap, "none")
    if censored and lo >= 60:
        return Notice(f"Cancelled between {_down(lo)} and {hours(_up(hi))} before its scheduled time. {gap}",
                      f"{_down(lo)} to {hours(_up(hi))}")
    if censored and lo >= 0:
        return Notice(f"Cancelled up to {hours(_up(hi))} before its scheduled time. {gap}",
                      f"up to {hours(_up(hi))}")
    if censored:
        return Notice("How much notice is unknown: there's a gap in the records then.", "unknown")
    if lo >= 60:
        return Notice(_at_least(lo), f"{_down(lo)}+ hours")
    if lo >= 0 and hi < 60:
        return Notice("Cancelled less than an hour before its scheduled time.", "under an hour")
    if lo >= 0:
        return Notice("Cancelled about an hour before its scheduled time.", "about an hour")
    return Notice("Cancelled around its scheduled time.", "almost none")


# --- what changed ----------------------------------------------------------------------------------

# The airport's status words, lower case; "final" and "not final" quoted: the airport does not define them.
STATUS_WORDS = {"ON TIME": "on time", "NOT FINAL": "“not final”", "FINAL": "“final”", "DELAYED": "delayed",
                "LANDING": "landing", "LANDED": "landed", "DEPARTED": "departed", "CANCELED": "cancelled",
                "EARLY": "early"}


def _status(status: str) -> str:
    return STATUS_WORDS.get(status, status.lower())


def _cancelled(o: dict) -> bool:
    return "status" in o["changed_fields"] and o["status"] == "CANCELED"


def _listed(o: dict, page_date: date, resumes: frozenset[datetime]) -> str:
    """The first line's left column: when the flight was first on the list, with the date when it is not the page's.
    "Already on the list" when the record is in the records' first list or the first list after a hole (`resumes`):
    the flight was on the airport's list before the records could see it, so "first on the list" would be untrue."""
    local = il_time(o["observed_at"])
    when = f"at {local:%H:%M}" if local.date() == page_date else f"on {local.day} {local:%b} at {local:%H:%M}"
    return f"{'Already' if o['observed_at'] in resumes else 'First'} on the list {when}"


def _earliest(o: dict, direction: str, page_date: date) -> str:
    """What the earliest record has; empty values left out (the model keeps empty desks and zone as '').
    "Already cancelled": the time beside it is when the record was made, never a cancellation time."""
    parts = ["already cancelled" if o["status"] == "CANCELED" else _status(o["status"])]
    if o["est_local"] is not None and o["est_local"] != o["sched_local"]:
        parts.append(f"expected to {_verb(direction)} at {clock(o['est_local'], page_date)}")
    if o["terminal"] is not None:
        parts.append(f"terminal {o['terminal']}")
    if o["counters"]:
        parts.append(f"check-in desks {o['counters']}")
    if o["zone"]:
        parts.append(f"zone {o['zone']}")
    return ", ".join(parts)


def _change(o: dict, before: dict, direction: str, page_date: date) -> str | None:
    """A record's changes, after the record `before` it; None when only the Hebrew status or a name's spelling
    changed. A retime's expected time is said only when it differs from the new scheduled time."""
    changed, retime = o["changed_fields"], o["change_kind"] == "retime"
    parts = []
    if retime:
        parts.append(f"moved to a new scheduled time: {clock(before['sched_local'], page_date)} → "
                     f"{clock(o['sched_local'], page_date)}")
    if _cancelled(o):
        parts.append("cancelled")
    if "est_local" in changed and not (retime and o["est_local"] == o["sched_local"]):
        parts.append(f"expected to {_verb(direction)} at {clock(o['est_local'], page_date)} instead"
                     if o["est_local"] is not None else "no expected time")
    if "status" in changed and not _cancelled(o):
        parts.append(f"status {_status(o['status'])}")
    if "terminal" in changed:
        parts.append(f"terminal {o['terminal']}" if o["terminal"] is not None else "no terminal")
    if "counters" in changed:
        parts.append(f"check-in desks {o['counters']}" if o["counters"] else "no check-in desks")
    if "zone" in changed:
        parts.append(f"zone {o['zone']}" if o["zone"] else "no check-in zone")
    if not parts:
        return None
    text = ", ".join(parts)
    return text[0].upper() + text[1:]


def change_lines(obs: list[dict], direction: str, page_date: date, gap_hours: float,
                 resumes: frozenset[datetime]) -> list[tuple[str, str]]:
    """What changed, oldest first: (left column, text) for the earliest record and each record that changed
    something shown. The earliest record's left column says when the flight was first on the list, or "already"
    on it when its time is one of `resumes` (the model's naive UTC: the records' first list and each hole's end,
    as build.render gives them). Every other left column is the record's time when it came within `gap_hours` of
    the flight's previous appearance (`prev_observed_at`: an appearance with no change is not a line, so this can
    be later than the previous line), else "Between" that appearance and the record. A cancellation is always a
    range."""
    lines = []
    for i, o in enumerate(obs):
        seen = clock(il_time(o["observed_at"]), page_date)
        if o["change_kind"] == "first":
            lines.append((_listed(o, page_date, resumes), _earliest(o, direction, page_date)))
            continue
        text = _change(o, obs[i - 1], direction, page_date)
        if text is None:
            continue
        after = o["prev_observed_at"]
        if _cancelled(o) or o["observed_at"] - after > timedelta(hours=gap_hours):
            lines.append((f"Between {clock(il_time(after), page_date)} and {seen}", text))
        else:
            lines.append((seen, text))
    return lines


# --- rates (docs/flight-lookup.md, "Words"; docs/flight-lookup-plan.md, Question 4 and Appendix A) ------

PAST_ONLY = "This is what happened to past flights. It does not say what will happen to yours."
FROM_HERE_HEADING = "From here to the scheduled time"
FROM_HERE_FIRST = ("So far, of all flights at the airport that the list still showed normally at each point, "
                   "this is how many were later listed as cancelled.")
FROM_HERE_COLUMNS = ("Time to go", "Flights still listed normally", "Later listed as cancelled", "That's about")
CHECKPOINT_NAMES = {70: "70 hours", 48: "48 hours", 24: "24 hours", 12: "12 hours", 6: "6 hours", 3: "3 hours"}
UNDER_TABLE = (
    "Each row is a point in time: the 24-hour row counts flights listed normally 24 hours before their "
    "scheduled time, and how many of them were later listed as cancelled, however late.",
    "Listed normally means any status but cancelled, delayed included.",
    "More than 3 days to go: the airport's list does not show the flight yet. A flight already listed as "
    "cancelled when it reaches the list is not in this table.",
)
TOO_FEW = "too few so far to say"
LEAD_INS = {70: "between 2 and 3 days", 48: "between 1 and 2 days", 24: "between 12 and 24 hours",
            12: "between 6 and 12 hours", 6: "between 3 and 6 hours", 3: "under 3 hours"}
A_FLIGHT = (
    "Flight numbers with the same scheduled time and airport are counted as one flight when the list shows the "
    "same expected time, terminal and check-in desks for them. A number that did not depart or land is counted "
    "with a number of its own airline, or one with its own desks. A flight counts as departed or landed when any "
    "of its numbers did, and as cancelled only when none did and at least one was listed as cancelled.")


def _n(x: int) -> str:
    return f"{x:,}"


def one_in_range(rate: Rate) -> str | None:
    """"1 in 100 (between 1 in 45 and 1 in 200)" (C8's rounding); None below the floor, and for a rate with no
    range (every flight in it cancelled)."""
    if not rate.clears_floor or rate.one_in is None or rate.one_in_from is None or rate.one_in_to is None:
        return None
    lo, hi = round_range(rate.one_in_from, rate.one_in_to)
    return f"1 in {_n(round_middle(rate.one_in))} (between 1 in {_n(lo)} and 1 in {_n(hi)})"


def total(rate: Rate) -> str:
    first = f"So far, {_n(rate.cancelled)} of {_n(rate.flights)} flights with a known outcome were listed as cancelled."
    figure = one_in_range(rate)
    return f"{first} That's about {figure}." if figure else f"{first} Too few so far to say."


def count_line(s: Summary) -> str:
    since = f"{s.first_record.day} {s.first_record:%B %Y}"
    return (f"Counted: {_n(s.figures.total.flights)} flights with a known outcome, scheduled up to two days before "
            f"the last update, in a record kept since {since}. Not counted: {_n(s.unknown)} flights with no known "
            f"outcome. {_n(s.unknown_gap)} of them left the list while nothing was recorded, and "
            f"{_n(s.unknown_no_final)} left it with no final status.")


def pair(h: int, rate: Rate) -> str | None:
    figure = one_in_range(rate)
    if figure is None:
        return None
    return (f"This flight has {LEAD_INS[h]} to go. So far, of all flights at the airport still listed normally "
            f"with {h} hours to go, about {figure} were later listed as cancelled.")


def _updated(updated: datetime) -> str:
    local = il_time(updated)
    return f"{local.day} {local:%b %Y, %H:%M}"


def condition(updated: datetime) -> str:
    return (f"The figure is for flights the airport's list showed normally. This page was last updated "
            f"{_updated(updated)} and cannot say what the list shows now. Check the airport's own list.")


# --- other numbers of one flight (docs/flight-lookup.md, "Flight page: other situations") -----------------------

ALSO_SOLD = "Also sold as"  # then the partners' numbers, linked, and SAME_PLANE
SAME_PLANE = "(probably the same plane)."
_TWIN = {"departed": ("This number was cancelled, but the flight probably left as", "."),
         "landed": ("This number was cancelled, but the flight probably landed as", "."),
         "is still listed": ("This number is marked cancelled, but the flight is probably still on, as", ".")}


def twin(verb: str) -> tuple[str, str]:
    """The twin line's words before and after the linked numbers, for what the flight's other numbers did
    (flights.others: "departed", "landed" or "is still listed")."""
    return _TWIN[verb]


# --- numbers (docs/flight-lookup.md, "Words": How numbers are written) --------------------------------------------

def pct1(k: int, n: int) -> str:
    """k of n as a percentage to one decimal, halves up, worked in integers so that 3 of 2,000 is 0.2%, not the
    float's 0.1% (the table, the tiles)."""
    tenths = (2000 * k + n) // (2 * n)
    return f"{tenths // 10}.{tenths % 10}%"


def average(k: int, n: int) -> str:
    """"under 1%" below 1%, else the table's one decimal (the all-airlines figures, the total's sentence)."""
    return "under 1%" if 100 * k < n else pct1(k, n)


def about(x: float) -> str:
    """A share as a chance: "under 1%" below 0.01, else "about N%", whole, halves up; never "0%"."""
    return "under 1%" if x < 0.01 else f"about {math.floor(x * 100 + 0.5)}%"


def _outward(one_in: float, up: bool) -> str:
    tenths = round(1000 / one_in, 6)  # the end's share in tenths of a percent, past float noise
    tenths = math.ceil(tenths) if up else math.floor(tenths)
    return f"{tenths // 10}.{tenths % 10}%"


def pct_range(rate: Rate) -> str | None:
    """"1.7% (between 1.1% and 2.9%)": one decimal, the ends outward; None below the floor and for a rate with no
    range (as one_in_range)."""
    if one_in_range(rate) is None:
        return None
    return (f"{pct1(rate.cancelled, rate.flights)} (between {_outward(rate.one_in_to, False)} "
            f"and {_outward(rate.one_in_from, True)})")


def _fill(text: Callable[[str], str], template: str, **names: str) -> str:
    """A sentence whose fixed words go through `text` and whose names (already marked by `data`) stand as given:
    the views pass html.escape and views.d, the tests the identity."""
    out = []
    for literal, field, _, _ in string.Formatter().parse(template):
        out.append(text(literal))
        if field is not None:
            out.append(names[field])
    return "".join(out)


def _flights(n: int) -> str:
    return "1 flight" if n == 1 else f"{_n(n)} flights"


def _day_month(day: date) -> str:
    return f"{day.day} {day:%B}"


# --- the front page: the table and the total ---------------------------------------------------------------------

TABLE_HEADING = "Chance of cancellation, by how soon you fly"
TABLE_COLUMNS = ("Your flight is…", "Chance it's cancelled")
NOT_ENOUGH = "Not enough flights yet"
ROW_NAMES = {70: "3 days away", 48: "2 days away", 24: "1 day away", 12: "12 hours away", 6: "6 hours away",
             3: "3 hours away"}
DELAY_LEAD = "Chance of a delay of an hour or more:"


def table_first(first: str, last: str) -> str:
    return f"If your flight is still on 3 days before, there's about a {first} chance it gets cancelled. By 3 hours before, it's {last}."


def under_table(mean_flights: int, since: date) -> str:
    return (f"These are averages for all airlines, from about {_n(mean_flights)} flights since {_day_month(since)}. "
            "A delayed flight still counts as “still on”.")


def delay_line(departures: float, arrivals: float) -> str:
    """"about 8% for departures and 5% for arrivals": the second "about" is dropped after a first one."""
    first, second = about(departures), about(arrivals)
    if first.startswith("about "):
        second = second.removeprefix("about ")
    return f"{first} for departures and {second} for arrivals. It's about the same however soon you fly."


def total_tiles(rate: Rate) -> list[tuple[str, str]]:
    """(figure, label) per tile; the third tile is the percentage alone, so its label is empty. Below the floor
    there are two tiles."""
    tiles = [(_n(rate.flights), "flights"), (_n(rate.cancelled), "cancelled")]
    if rate.clears_floor:
        tiles.append((pct1(rate.cancelled, rate.flights), ""))
    return tiles


def total_sentence(rate: Rate, since: date) -> str:
    were = "was" if rate.cancelled == 1 else "were"
    first = f"Since {_day_month(since)}, {_n(rate.cancelled)} of {_n(rate.flights)} flights at Ben Gurion {were} cancelled"
    if rate.clears_floor:
        return f"{first} ({average(rate.cancelled, rate.flights)})."
    return f"{first}. Not enough flights yet for a percentage."


def late_line(late: int, cancelled: int) -> str | None:
    if late == 0:
        return None
    return (f"Some flights (at least {_n(late)} of the {_n(cancelled)}) were only marked cancelled after their "
            "scheduled time had passed.")


def left_out(n: int) -> str | None:
    if n == 0:
        return None
    if n == 1:
        return "1 flight is left out because there's no record of how it ended."
    return f"{_n(n)} flights are left out because there's no record of how they ended."


# --- the flight page: the headline, "Worked out from", the lines in smaller type ---------------------------------

def headline(cancel: float, delay: float, ahead: bool) -> tuple[tuple[str, str], tuple[str, str]]:
    """(label, figure) for the cancellation and the delay; without a flight ahead both say "its next flight"."""
    it = "it's" if ahead else "its next flight is"
    return ((f"Chance {it} cancelled:", about(cancel)), (f"Chance {it} delayed an hour or more:", about(delay)))


@dataclass(frozen=True)
class History:
    """A number's or an airline's counted flights. `week` is the first and last Israel day of a bad week: set when
    two or more of its cancelled flights all fall within 7 days."""
    name: str
    flights: int
    cancelled: int
    delayed: int
    week: tuple[date, date] | None


@dataclass(frozen=True)
class Worked:
    """A "Worked out from" line, and whether it already gives the number's and the airline's bad-week dates."""
    text: str
    names_number_week: bool
    names_airline_week: bool


MOSTLY_BELOW_NUMBER, MOSTLY_BELOW_AIRLINE = 14, 100  # fewer counted flights than this: the next record leads


def _all_in(week: tuple[date, date]) -> str:
    first, last = week
    if first == last:
        return f"all on {_day_month(first)}"
    if (first.year, first.month) == (last.year, last.month):
        return f"all between {first.day} and {_day_month(last)}"
    return f"all between {_day_month(first)} and {_day_month(last)}"


def _bracket(h: History) -> str:
    if h.cancelled == 0:
        return f"(none of its {_n(h.flights)} flights was cancelled)"
    if h.cancelled == 1:
        return f"(1 of its {_n(h.flights)} flights was cancelled)"
    return f"({_n(h.cancelled)} of its {_n(h.flights)} flights were cancelled)"


def _whose(spoken: str | None, text: Callable[[str], str], data: Callable[[str], str]) -> str:
    return _fill(text, "{s}'s history", s=data(spoken)) if spoken else text("its airline's history")


def worked_out(number: History, airline: History, spoken: str | None, ahead: bool, listed_since: bool,
               text: Callable[[str], str] = str, data: Callable[[str], str] = str) -> Worked:
    """The line under a headline, in the form docs/flight-lookup.md picks: a number with 14 counted flights or more
    leads; below that its airline does ("mostly from"), and below 100 flights of its own, all airlines. `spoken` is
    the airline's spoken name, None for "its airline"; `listed_since` is whether a flight of the number is
    scheduled after its last cancelled one."""
    num = data(number.name)
    if number.flights >= MOSTLY_BELOW_NUMBER:
        whose = _whose(spoken, text, data)
        if number.week is not None:
            line = text(f"Worked out from this flight's history: {_n(number.cancelled)} of its {_n(number.flights)} "
                        f"flights were cancelled, {_all_in(number.week)}.")
            if ahead:
                line += text(" Also from ") + whose + text(", and how soon it leaves.")
            elif not listed_since:
                line += text(" It hasn't been on the airport's list since.")
            return Worked(line, True, False)
        line = text(f"Worked out from this flight's history {_bracket(number)}")
        if ahead:
            return Worked(line + text(", ") + whose + text(", and how soon it leaves."), False, False)
        return Worked(line + text(" and ") + whose + text("."), False, False)
    have = "has no flights so far" if number.flights == 0 else f"has only {_flights(number.flights)} so far"
    if airline.flights < MOSTLY_BELOW_AIRLINE:
        if number.flights == 0 and airline.flights == 0:
            return Worked(_fill(text, "Worked out from all airlines at Ben Gurion, because {n} and its airline have "
                                      "no flights so far.", n=num), False, False)
        return Worked(_fill(text, "Worked out mostly from all airlines at Ben Gurion, because {n} {have} and its "
                                  "airline only {a}.", n=num, have=text(have), a=_n(airline.flights)), False, False)
    who = data(spoken or airline.name)
    first = _fill(text, "Worked out mostly from {p}, because {n} {have}.", p=_whose(spoken, text, data), n=num, have=text(have))
    if airline.cancelled == 0:
        second = text(" ") + who + text(f" cancelled none of its {_n(airline.flights)} flights.")
    else:
        tail = f", {_all_in(airline.week)}" if airline.week is not None else ""
        second = text(" ") + who + text(f" cancelled {_n(airline.cancelled)} of its {_n(airline.flights)} flights{tail}.")
    return Worked(first + second, False, airline.week is not None)


def so_far(h: History, with_week: bool, text: Callable[[str], str] = str,
           data: Callable[[str], str] = str) -> tuple[str, str]:
    """(bold part, rest) of a "so far" line; `with_week` adds the bad week's dates to the cancelled count."""
    cancelled = "none cancelled" if h.cancelled == 0 else f"{_n(h.cancelled)} cancelled"
    if with_week and h.week is not None and h.cancelled:
        cancelled += f", {_all_in(h.week)}"
    delayed = ("none delayed an hour or more" if h.delayed == 0
               else f"{_n(h.delayed)} delayed an hour or more")
    return _fill(text, "{n} so far:", n=data(h.name)), text(f"{_flights(h.flights)} · {cancelled} · {delayed}")


def partner(number: str, lead: str, spoken: str, text: Callable[[str], str] = str,
            data: Callable[[str], str] = str) -> str:
    """The line above an airline's "so far" line on the page of a number sold with another airline's flight."""
    return _fill(text, "{a} is also sold as {b}, so the numbers here are worked out from {s}'s history.",
                 a=data(number), b=data(lead), s=data(spoken))


STRETCH_NAMES = {70: "2 to 3 days", 48: "1 to 2 days", 24: "12 to 24 hours", 12: "6 to 12 hours", 6: "3 to 6 hours",
                 3: "less than 3 hours"}


def all_airlines(h: int | None, cancel: str, delay: str, direction: str) -> tuple[str, str]:
    """(bold part, rest) of the all-airlines line: `h` is the checkpoint of the stretch, None without a time left;
    `cancel` and `delay` are the figures as written ("under 1%", "1.6%", "about 5%")."""
    when = "" if h is None else f", {STRETCH_NAMES[h]} before a flight"
    of = "departures" if direction == "D" else "arrivals"
    return (f"All airlines at Ben Gurion{when}:", f"{cancel} cancelled · {delay} of {of} delayed an hour or more")


# --- freshness and other situations ------------------------------------------------------------------------------

def updated_at(t: datetime) -> str:
    local = il_time(t)
    return f"Updated {local.day} {local:%b} at {local:%H:%M}"


# --- every page's top line, the day page and the cancelled-flights page (docs/site-redesign.md, "Pages") ---------

NAME = "Will It Fly?"  # the site's name, linked to the front page on every page
WHERE = "Tel Aviv airport"  # beside the name


def long_date(day: date) -> str:
    """A date written out, as on a flight page and a day page: "Monday 16 November"."""
    return f"{day:%A} {_day_month(day)}"


def day_title(day: date, total: int, cancelled: int) -> str:
    """"Monday 16 November · 357 flights · 3 cancelled": a count of 0 leaves its part out (Question 6f)."""
    counts = [(total, _flights(total)), (cancelled, f"{_n(cancelled)} cancelled")]
    return " · ".join([long_date(day), *(part for n, part in counts if n)])


PART_MISSING = "Some flights from this day may be missing: the records don't cover the whole day."


def unknown_line(n: int) -> str | None:
    """The day page's line for its flights labelled UNKNOWN; none at 0 (Question 6f)."""
    if n == 0:
        return None
    if n == 1:
        return "For 1 of these flights, there's no record of how it ended."
    return f"For {_n(n)} of these flights, there's no record of how they ended."


NO_DEPARTURES = "No departures recorded."
NO_ARRIVALS = "No arrivals recorded."
CANCELLED_TITLE = "Cancelled flights"
CANCELLED_INTRO = "Every cancelled flight since 27 October, newest first."
CANCELLED_UNDER = ("“Notice given” is how long before the scheduled time the airport marked the flight cancelled. "
                   "Airlines may tell passengers sooner.")
CANCELLED_COLUMNS = ("Date", "Flight", "Route", NOTICE_GIVEN)
NONE_CANCELLED = "No cancelled flights so far."  # the cancelled-flights page and the front page's recent list


FRESH_REST = "Things may have changed, so check with your airline."
MORE_THAN_3_DAYS = ("Your flight is more than 3 days away. Flights show up on the airport's list about 3 days "
                    "ahead, so check back closer to the date.")
MARKED_CANCELLED = ("This flight is marked cancelled.", "Contact your airline.")


def has_passed(updated: datetime) -> str:
    local = il_time(updated)
    return (f"This flight's time has passed. The page was last updated on {local.day} {local:%b} at {local:%H:%M}, "
            "so it may not show what happened.")


def not_listed(number: str, last: date, still_listed: bool, text: Callable[[str], str] = str,
               data: Callable[[str], str] = str) -> str:
    """No flight ahead: the number is off the airport's list, or its last flight is still on it."""
    state = "has no upcoming flight on the airport's list right now" if still_listed else (
        "isn't on the airport's list right now")
    return _fill(text, "{n} " + state + f". The last one was on {last:%A} {_day_month(last)}.", n=data(number))


# --- the strip of days -------------------------------------------------------------------------------------------

def strip_heading(number: str, text: Callable[[str], str] = str, data: Callable[[str], str] = str) -> str:
    return _fill(text, "{n}, day by day", n=data(number))


def strip_key(counts: dict[str, int]) -> list[str]:
    """"landed 22", "upcoming 3": each kind of mark with its count, in LABEL_ORDER, none for a count of 0."""
    return [f"{label.lower()} {counts[label]}" for label in LABEL_ORDER if counts.get(label)]


def mark_name(day: date, label: str) -> str:
    """A mark's name for a screen reader and a tooltip: "Tuesday 17 November, upcoming"."""
    return f"{day:%A} {_day_month(day)}, {label.lower()}"
