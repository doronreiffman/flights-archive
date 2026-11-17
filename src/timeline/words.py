"""Every sentence and label of the site, and the time helpers they use (docs/site-redesign.md, "Words").

Pure functions from model values to text. Model times (`*_at`, `*_utc`) are naive UTC; the airport's times
(`*_local`) are Israel wall-clock as published. Ranges and lower bounds only: a notice is never a measured
moment, and no delay is shown under an hour (display.delayed_an_hour).
"""
from __future__ import annotations

import math
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
MORE_THAN_3_DAYS = "More than 3 days to go: the airport's list does not show the flight yet."
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


def late_line(s: Summary) -> str | None:
    if s.late_after == 0:
        return None
    return (f"At least {_n(s.late_after)} of the {_n(s.figures.total.cancelled)} cancelled flights were listed as "
            f"cancelled only after their scheduled time.")


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


def has_passed(updated: datetime) -> str:
    return (f"This flight's scheduled time has passed. The row below shows the list as it was on "
            f"{_updated(updated)}.")


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
