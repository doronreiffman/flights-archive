"""Every sentence and label of the site, and the time helpers they use (docs/site-redesign.md, "Words").

Pure functions from model values to text. Model times (`*_at`, `*_utc`) are naive UTC; the airport's times
(`*_local`) are Israel wall-clock as published. Ranges and lower bounds only: a warning is never a measured
moment, and nothing here turns an expected time into a delay.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ISRAEL = ZoneInfo("Asia/Jerusalem")

UNOFFICIAL = ("Unofficial; not affiliated with or endorsed by the Israel Airports Authority, "
              "data.gov.il or the State of Israel.")
SOURCE_SHORT = "Flight data: Israel Airports Authority, published on data.gov.il."
TIMES_NOTE = "Times are Israel time."
PLACEHOLDER = "[owner's wording]"  # the upload check refuses a site that still contains it
BUILT_BY = PLACEHOLDER
CODE_URL = "https://github.com/doronreiffman/flights-archive"
DELAY_SENTENCE = ("Expected times are the airport's own. This site doesn't turn them into delay figures, "
                  "because the airport doesn't say whether they mean leaving the gate or taking off.")

DEPARTED, LANDED, CANCELLED, UPCOMING, NO_FINAL_UPDATE, UNKNOWN = (
    "DEPARTED", "LANDED", "CANCELLED", "UPCOMING", "NO FINAL UPDATE", "UNKNOWN")
LABEL_ORDER = (DEPARTED, LANDED, CANCELLED, UPCOMING, NO_FINAL_UPDATE, UNKNOWN)


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
            return UPCOMING if sched_utc_final > last_fetch else NO_FINAL_UPDATE
        case "gap" | "vanished" | "dropped":
            return UNKNOWN
    raise ValueError(f"unknown outcome {outcome!r}")


def label_note(f: dict) -> str | None:
    """The line under an UNKNOWN label: why the outcome is unknown."""
    match f["outcome"]:
        case "gap":
            return "No records for the time it left the airport's list."
        case "vanished":
            ahead = _down((f["sched_utc_final"] - f["last_seen_at"]).total_seconds() / 60)
            return (f"Removed from the airport's list {hours(ahead)} before it was scheduled, with no final status. "
                    "Not necessarily cancelled; it may have moved to another time.")
        case "dropped":
            return "Removed from the airport's list with no final status."
    return None


def changed_back(f: dict, label: str) -> str | None:
    """A line under the final label when the flight was shown as cancelled, then as something else."""
    if not f["uncanceled"]:  # NULL (cancelled from its earliest record on) counts as false
        return None
    if label == CANCELLED:
        return "Cancelled, changed back, then cancelled again."
    return "Shown as cancelled for a while, then changed back."


def scheduled(direction: str, local: datetime, page_date: date | None) -> str:
    return f"scheduled to {_verb(direction)} {clock(local, page_date)}"


def last_expected(f: dict, page_date: date | None) -> str | None:
    """The airport's last expected time, shown beside the scheduled one when they differ. No difference is computed."""
    est, sched = f["est_local_final"], f["sched_local_final"]
    if est is None or sched is None or est == sched:
        return None
    return f"last expected {clock(est, page_date)}"


# --- warning ---------------------------------------------------------------------------------------

def _warning_rule(f: dict) -> tuple[int, str]:
    """The spec's warning table, in order; the first matching rule wins, so each condition leaves out what an
    earlier rule already took. `lo` is from the first record showing the flight cancelled to its scheduled time,
    `hi` from the record before that (None when the earliest record already showed it cancelled); hi >= lo."""
    lo, hi, censored = f["cancel_lead_min"], f["cancel_lead_max_min"], f["cancel_lead_censored"]
    after = f"after it was scheduled to {_verb(f['direction'])}"
    if hi is None:
        return (1, f"at least {hours(_down(lo))}") if lo >= 60 else (2, "unknown")
    if hi < 0 and not censored:  # a non-censored range is at most an hour wide; -hi is its nearer end
        if -lo < 60:
            return 3, f"none: listed as cancelled less than an hour {after}"
        if -hi < 120:
            return 3, f"none: listed as cancelled about an hour {after}"
        return 3, f"none: listed as cancelled about {hours(_down(-hi))} {after}"
    if hi < 0:
        return 4, f"none: listed as cancelled {after}"
    if censored and lo >= 60:
        return 5, f"between {_down(lo)} and {hours(_up(hi))}"
    if censored and lo >= 0:
        return 6, f"up to {hours(_up(hi))}"
    if censored:
        return 7, "unknown: no records for that time"
    if lo >= 60:
        return 8, f"at least {hours(_down(lo))}"
    if lo >= 0 and hi < 60:
        return 9, "less than an hour"
    if lo >= 0:
        return 10, "about an hour"
    return 11, "around the scheduled time"


def warning(f: dict) -> str | None:
    """How long before its scheduled time the airport's list already showed the flight as cancelled."""
    if f["outcome"] != "canceled":
        return None
    return _warning_rule(f)[1]


def warning_note(f: dict) -> str | None:
    """The flight page's extra sentence for a warning that rests on missing records."""
    if f["outcome"] != "canceled":
        return None
    rule = _warning_rule(f)[0]
    if rule in (1, 2):
        return "The earliest record already showed it as cancelled."
    if 4 <= rule <= 6:  # rule 7's own text already says "no records for that time"
        return "No records for part of that time."
    return None


def warning_sentence(text: str) -> str:
    """A warning text as the flight page's sentence."""
    if text.startswith("none: "):
        return f"No warning: {text.removeprefix('none: ')}."
    if text.startswith("unknown: "):
        return f"Warning unknown: {text.removeprefix('unknown: ')}."
    if text == "unknown":
        return "Warning unknown."
    return f"Warning: {text}."


# --- what changed ----------------------------------------------------------------------------------

# The airport's status words, lower case; "final" and "not final" quoted: the airport does not define them.
STATUS_WORDS = {"ON TIME": "on time", "NOT FINAL": "“not final”", "FINAL": "“final”", "DELAYED": "delayed",
                "LANDING": "landing", "LANDED": "landed", "DEPARTED": "departed", "CANCELED": "cancelled",
                "EARLY": "early"}


def _status(status: str) -> str:
    return STATUS_WORDS.get(status, status.lower())


def _cancelled(o: dict) -> bool:
    return "status" in o["changed_fields"] and o["status"] == "CANCELED"


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


def change_lines(obs: list[dict], direction: str, page_date: date, gap_hours: float) -> list[tuple[str, str]]:
    """What changed, oldest first: (left column, text) for the earliest record and each record that changed
    something shown. The left column is the record's time when it came within `gap_hours` of the flight's
    previous appearance (`prev_observed_at`: an appearance with no change is not a line, so this can be later
    than the previous line), else "Between" that appearance and the record. A cancellation is always a range."""
    lines = []
    for i, o in enumerate(obs):
        seen = clock(il_time(o["observed_at"]), page_date)
        if o["change_kind"] == "first":
            lines.append((f"Earliest record ({seen})", _earliest(o, direction, page_date)))
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


# --- headline --------------------------------------------------------------------------------------

def one_in(cancelled: int, known: int) -> int | None:
    """N in "about 1 in N": below 20 the nearest whole number, from 20 up the nearest multiple of 5; halves up."""
    if cancelled == 0:
        return None
    r = known / cancelled
    return math.floor(r + 0.5) if r < 20 else 5 * math.floor(r / 5 + 0.5)


def headline(cancelled: int, known: int) -> str | None:
    n = one_in(cancelled, known)
    if n is None:
        return None
    return (f"So far, {cancelled} of {known} flights with a known outcome were listed as cancelled. "
            f"That's about 1 in {n}.")
