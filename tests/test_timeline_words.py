"""Every sentence, label and time helper of the redesigned site (docs/site-redesign.md, "Words"). Expected values by hand."""
import time
from datetime import date, datetime, timedelta

import pytest

from timeline import check, words
from timeline.rates import Rate

DAY = date(2026, 10, 29)


@pytest.fixture
def israeli_machine(monkeypatch):
    """Run as on the owner's Mac: a naive astimezone() would then read UTC values as Israel time."""
    monkeypatch.setenv("TZ", "Asia/Jerusalem")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


# --- constants -------------------------------------------------------------------------------------

def test_fixed_texts_are_the_specs_words():
    assert words.UNOFFICIAL == ("This site is unofficial: it isn't run by, connected to or approved by the Israel "
                                "Airports Authority, data.gov.il or the State of Israel.")
    assert words.SOURCE_SHORT == "Flight data: Israel Airports Authority, published on data.gov.il."
    assert words.TIMES_NOTE == "All times are Israel time."
    assert words.ESTIMATES == "The chances on this site are estimates from past flights, not promises."
    assert (words.MEANS, words.MEANS_ANCHOR) == ("What the numbers mean", "what-the-numbers-mean")
    assert words.PLACEHOLDER == "[owner's wording]"
    assert words.CODE_URL == "https://github.com/doronreiffman/flights-archive"
    assert words.DELAY_SENTENCE == (
        "Expected times are the airport's own. This site doesn't turn them into delay figures, "
        "because the airport doesn't say whether they mean leaving the gate or taking off.")
    assert str(words.ISRAEL) == "Asia/Jerusalem"


def test_labels_and_their_order():
    assert words.LABEL_ORDER == ("DEPARTED", "LANDED", "CANCELLED", "UPCOMING", "NO FINAL UPDATE", "UNKNOWN")
    assert words.LABEL_ORDER == (words.DEPARTED, words.LANDED, words.CANCELLED, words.UPCOMING,
                                 words.NO_FINAL_UPDATE, words.UNKNOWN)


# --- times -----------------------------------------------------------------------------------------

def test_utc_values_become_israel_time_whatever_the_machine_zone(israeli_machine):
    assert words.il_time(datetime(2026, 10, 27, 18, 4, 46)).strftime("%Y-%m-%d %H:%M") == "2026-10-27 20:04"


def test_israel_time_across_the_october_clock_change(israeli_machine):
    before, after = words.il_time(datetime(2026, 10, 24, 22, 30)), words.il_time(datetime(2026, 10, 24, 23, 30))
    assert (before.strftime("%d %H:%M"), after.strftime("%d %H:%M")) == ("25 01:30", "25 01:30")
    assert (before.utcoffset().seconds // 3600, after.utcoffset().seconds // 3600) == (3, 2)


def test_clock_carries_the_date_only_off_the_page_date():
    assert words.clock(datetime(2026, 10, 29, 14, 46), DAY) == "14:46"
    assert words.clock(datetime(2026, 10, 28, 23, 30), DAY) == "28 Oct 23:30"
    assert words.clock(datetime(2026, 10, 29, 14, 46), None) == "29 Oct 14:46"


def test_hours():
    assert words.hours(1) == "1 hour"
    assert words.hours(7) == "7 hours"
    assert words.hours(0) == "0 hours"


# --- labels ----------------------------------------------------------------------------------------

LAST_FETCH = datetime(2026, 10, 29, 22, 2, 45)


@pytest.mark.parametrize("outcome, label", [
    ("departed", "DEPARTED"), ("landed", "LANDED"), ("canceled", "CANCELLED"),
    ("gap", "UNKNOWN"), ("vanished", "UNKNOWN"), ("dropped", "UNKNOWN"),
])
def test_main_label_from_the_outcome(outcome, label):
    assert words.main_label(outcome, datetime(2026, 10, 29, 22, 10), LAST_FETCH) == label


@pytest.mark.parametrize("sched_utc_final, label", [
    (datetime(2026, 10, 29, 22, 10), "UPCOMING"),
    (datetime(2026, 10, 29, 21, 55), "NO FINAL UPDATE"),
    (LAST_FETCH, "NO FINAL UPDATE"),  # at the last record's time: no longer ahead
])
def test_open_flight_upcoming_until_its_scheduled_time(sched_utc_final, label):
    assert words.main_label("open", sched_utc_final, LAST_FETCH) == label


def test_unknown_outcome_refused():
    with pytest.raises(ValueError, match="unknown outcome"):
        words.main_label("teleported", datetime(2026, 10, 29, 22, 10), LAST_FETCH)


def test_no_final_update_decided_in_utc(israeli_machine):
    """23:55 Israel time is 21:55 UTC, before the 22:02 UTC last record: the evening flights of 29 October
    have no final update. Comparing the Israel wall-clock value would call them UPCOMING."""
    f = {"outcome": "open", "sched_local_final": datetime(2026, 10, 29, 23, 55),
         "sched_utc_final": datetime(2026, 10, 29, 21, 55)}
    assert words.main_label(f["outcome"], f["sched_utc_final"], LAST_FETCH) == "NO FINAL UPDATE"


SCHED = datetime(2026, 10, 29, 16, 30)


LABEL_NOTE_CASES = [
    ("gap", SCHED - timedelta(hours=9), "No records for the time it left the airport's list."),
    ("vanished", SCHED - timedelta(hours=6, minutes=20),
     "Removed from the airport's list 6 hours before it was scheduled, with no final status. "
     "Not necessarily cancelled; it may have moved to another time."),
    ("vanished", SCHED - timedelta(hours=1, minutes=5),
     "Removed from the airport's list 1 hour before it was scheduled, with no final status. "
     "Not necessarily cancelled; it may have moved to another time."),
    ("dropped", SCHED - timedelta(minutes=20), "Removed from the airport's list with no final status."),
    ("departed", SCHED, None), ("landed", SCHED, None), ("canceled", SCHED, None), ("open", SCHED, None),
]


@pytest.mark.parametrize("outcome, last_seen_at, note", LABEL_NOTE_CASES)
def test_label_note(outcome, last_seen_at, note):
    assert words.label_note({"outcome": outcome, "sched_utc_final": SCHED, "last_seen_at": last_seen_at}) == note


CHANGED_BACK_CASES = [
    (True, "LANDED", "Shown as cancelled for a while, then changed back."),
    (True, "CANCELLED", "Cancelled, changed back, then cancelled again."),
    (None, "CANCELLED", None),  # NULL: the earliest record already showed it cancelled, never shown otherwise
    (False, "LANDED", None),
]


@pytest.mark.parametrize("uncanceled, label, line", CHANGED_BACK_CASES)
def test_changed_back(uncanceled, label, line):
    assert words.changed_back({"uncanceled": uncanceled}, label) == line


def test_scheduled():
    assert words.scheduled("D", datetime(2026, 10, 29, 17, 10), DAY) == "scheduled to leave 17:10"
    assert words.scheduled("A", datetime(2026, 10, 29, 13, 50), DAY) == "scheduled to land 13:50"
    assert words.scheduled("D", datetime(2026, 10, 29, 17, 10), date(2026, 10, 30)) == "scheduled to leave 29 Oct 17:10"


LAST_EXPECTED_CASES = [
    (datetime(2026, 10, 29, 17, 9), datetime(2026, 10, 29, 16, 45), "last expected 17:09"),
    (datetime(2026, 10, 29, 16, 45), datetime(2026, 10, 29, 16, 45), None),
    (None, datetime(2026, 10, 29, 16, 45), None),
    (datetime(2026, 10, 29, 17, 9), None, None),
]


@pytest.mark.parametrize("est, sched, text", LAST_EXPECTED_CASES)
def test_last_expected(est, sched, text):
    assert words.last_expected({"est_local_final": est, "sched_local_final": sched}, DAY) == text


# --- warning ---------------------------------------------------------------------------------------

def cancelled(lo, hi, censored, direction="D", outcome="canceled"):
    return {"outcome": outcome, "direction": direction, "cancel_lead_min": lo, "cancel_lead_max_min": hi,
            "cancel_lead_censored": censored}


WARNING_CASES = [
    (1400.95, None, True, "A", "at least 23 hours"),            # rule 1, IZ 992
    (60.0, None, True, "D", "at least 1 hour"),                  # rule 1 boundary
    (59.9, None, True, "D", "unknown"),                          # rule 2
    (-59.05, None, True, "D", "unknown"),                        # rule 2, ASY 991
    (-50.0, -10.0, False, "D", "none: listed as cancelled less than an hour after it was scheduled to leave"),
    (-70.0, -30.0, False, "D", "none: listed as cancelled about an hour after it was scheduled to leave"),
    (-60.0, -30.0, False, "D", "none: listed as cancelled about an hour after it was scheduled to leave"),   # -lo exactly 60
    (-150.0, -120.0, False, "D", "none: listed as cancelled about 2 hours after it was scheduled to leave"),  # -hi exactly 120
    (-142.75, -126.75, False, "D", "none: listed as cancelled about 2 hours after it was scheduled to leave"),  # TO 3459
    (-142.75, -126.75, False, "A", "none: listed as cancelled about 2 hours after it was scheduled to land"),
    (-200.0, -100.0, True, "D", "none: listed as cancelled after it was scheduled to leave"),                  # rule 4
    (75.95, 2600.48, True, "D", "between 1 and 44 hours"),       # rule 5, LY 5409
    (445.95, 2970.48, True, "A", "between 7 and 50 hours"),      # rule 5, LY 5410
    (60.0, 2000.0, True, "D", "between 1 and 34 hours"),         # rule 5, boundary 60
    (0.0, 2000.0, True, "D", "up to 34 hours"),                  # rule 6, boundary 0
    (-64.05, 2460.48, True, "D", "unknown: no records for that time"),  # rule 7, BZ 254
    (400.0, 416.0, False, "D", "at least 6 hours"),              # rule 8
    (60.0, 75.0, False, "D", "at least 1 hour"),                 # rule 8, boundary 60
    (0.0, 59.0, False, "D", "less than an hour"),                # rule 9, boundary 0
    (45.0, 74.0, False, "D", "about an hour"),                   # rule 10
    (59.9, 60.0, False, "D", "about an hour"),                   # rule 10, boundary 60
    (-10.0, 6.0, False, "D", "around the scheduled time"),       # rule 11
    (-10.0, 0.0, False, "D", "around the scheduled time"),       # rule 11, hi exactly 0
]


@pytest.mark.parametrize("lo, hi, censored, direction, text", WARNING_CASES)
def test_warning_rules(lo, hi, censored, direction, text):
    assert words.warning(cancelled(lo, hi, censored, direction)) == text


def test_no_warning_unless_cancelled():
    assert words.warning(cancelled(400.0, 416.0, False, outcome="departed")) is None
    assert words.warning_note(cancelled(1400.95, None, True, outcome="departed")) is None


EARLIEST = "The earliest record already showed it as cancelled."
PART = "No records for part of that time."


@pytest.mark.parametrize("lo, hi, censored, note", [
    (1400.95, None, True, EARLIEST),     # rule 1
    (59.9, None, True, EARLIEST),        # rule 2
    (-142.75, -126.75, False, None),     # rule 3
    (-200.0, -100.0, True, PART),        # rule 4
    (75.95, 2600.48, True, PART),        # rule 5
    (0.0, 2000.0, True, PART),           # rule 6
    (-64.05, 2460.48, True, None),       # rule 7: its text already says "no records for that time"
    (400.0, 416.0, False, None),         # rule 8
    (0.0, 59.0, False, None),            # rule 9
    (45.0, 74.0, False, None),           # rule 10
    (-10.0, 6.0, False, None),           # rule 11
])
def test_warning_note(lo, hi, censored, note):
    assert words.warning_note(cancelled(lo, hi, censored)) == note


SENTENCE_CASES = [
    ("none: listed as cancelled about 2 hours after it was scheduled to leave",
     "No warning: listed as cancelled about 2 hours after it was scheduled to leave."),
    ("unknown: no records for that time", "Warning unknown: no records for that time."),
    ("unknown", "Warning unknown."),
    ("at least 23 hours", "Warning: at least 23 hours."),
]


@pytest.mark.parametrize("text, sentence", SENTENCE_CASES)
def test_warning_sentence(text, sentence):
    assert words.warning_sentence(text) == sentence


# --- rates -----------------------------------------------------------------------------------------

def rate(cancelled, flights, one_in, lo, hi, floor=True):
    return Rate(cancelled=cancelled, flights=flights, airlines=9, days=9, clears_floor=floor, one_in=one_in,
                one_in_from=lo, one_in_to=hi, se_airline_week=None, se_day=None)


TOTAL = rate(81, 4658, 4658 / 81, 36.3, 91.6)
A35_ROWS = {
    70: (rate(48, 3028, 63.1, 33.2, 120.6), "1 in 65 (between 1 in 30 and 1 in 130)"),
    48: (rate(47, 3316, 70.6, 38.1, 131.4), "1 in 70 (between 1 in 35 and 1 in 140)"),
    24: (rate(35, 3449, 98.5, 49.3, 197.9), "1 in 100 (between 1 in 45 and 1 in 200)"),
    12: (rate(25, 3625, 145.0, 71.4, 295.6), "1 in 150 (between 1 in 70 and 1 in 300)"),
    6: (rate(19, 3704, 194.9, 96.6, 394.4), "1 in 190 (between 1 in 95 and 1 in 400)"),
    3: (rate(16, 3754, 234.6, 119.99, 459.7), "1 in 230 (between 1 in 110 and 1 in 460)"),
}


def test_constants_are_the_approved_words():
    assert words.PAST_ONLY == "This is what happened to past flights. It does not say what will happen to yours."
    assert words.FROM_HERE_HEADING == "From here to the scheduled time"
    assert words.FROM_HERE_FIRST == ("So far, of all flights at the airport that the list still showed normally at "
                                     "each point, this is how many were later listed as cancelled.")
    assert words.FROM_HERE_COLUMNS == ("Time to go", "Flights still listed normally", "Later listed as cancelled",
                                      "That's about")
    assert words.CHECKPOINT_NAMES == {70: "70 hours", 48: "48 hours", 24: "24 hours", 12: "12 hours",
                                      6: "6 hours", 3: "3 hours"}
    assert words.UNDER_TABLE == (
        "Each row is a point in time: the 24-hour row counts flights listed normally 24 hours before their "
        "scheduled time, and how many of them were later listed as cancelled, however late.",
        "Listed normally means any status but cancelled, delayed included.",
        "More than 3 days to go: the airport's list does not show the flight yet. A flight already listed as "
        "cancelled when it reaches the list is not in this table.")
    assert words.TOO_FEW == "too few so far to say"
    assert words.MORE_THAN_3_DAYS == "More than 3 days to go: the airport's list does not show the flight yet."
    assert words.LEAD_INS == {70: "between 2 and 3 days", 48: "between 1 and 2 days", 24: "between 12 and 24 hours",
                              12: "between 6 and 12 hours", 6: "between 3 and 6 hours", 3: "under 3 hours"}
    assert words.BRACKET == "is listed as cancelled"
    assert words.A_FLIGHT == (
        "Flight numbers with the same scheduled time and airport are counted as one flight when the list shows the "
        "same expected time, terminal and check-in desks for them. A number that did not depart or land is counted "
        "with a number of its own airline, or one with its own desks. A flight counts as departed or landed when "
        "any of its numbers did, and as cancelled only when none did and at least one was listed as cancelled.")


def test_total():
    assert words.total(TOTAL) == ("So far, 81 of 4,658 flights with a known outcome were listed as cancelled. "
                                  "That's about 1 in 60 (between 1 in 35 and 1 in 95).")


def test_total_below_the_floor():
    assert words.total(rate(3, 120, 40.0, 10.0, 90.0, floor=False)) == (
        "So far, 3 of 120 flights with a known outcome were listed as cancelled. Too few so far to say.")
    assert words.total(rate(0, 900, None, None, None, floor=False)) == (
        "So far, 0 of 900 flights with a known outcome were listed as cancelled. Too few so far to say.")


def test_a_rate_without_a_range_is_shown_like_one_below_the_floor():
    r = rate(12, 12, 1.0, None, None)
    assert words.one_in_range(r) is None
    assert words.total(r) == "So far, 12 of 12 flights with a known outcome were listed as cancelled. Too few so far to say."


@pytest.mark.parametrize("h", sorted(A35_ROWS))
def test_one_in_range_is_a35s_line(h):
    r, line = A35_ROWS[h]
    assert words.one_in_range(r) == line


def test_one_in_range_total_and_floor():
    assert words.one_in_range(TOTAL) == "1 in 60 (between 1 in 35 and 1 in 95)"
    assert words.one_in_range(rate(3, 120, 40.0, 10.0, 90.0, floor=False)) is None


def test_one_in_range_carries_thousands_separators():
    assert words.one_in_range(rate(10, 11000, 1100.0, 800.0, 1500.0)) == "1 in 1,100 (between 1 in 800 and 1 in 1,500)"


# Every pair whole, by hand: the design's template and lead-ins (docs/flight-lookup.md, "Words") with A35's lines. Each
# names its own checkpoint twice, in its lead-in and in its hours to go (C5).
_SO_FAR = "So far, of all flights at the airport still listed normally with"
PAIRS = {
    70: f"This flight has between 2 and 3 days to go. {_SO_FAR} 70 hours to go, about 1 in 65 (between 1 in 30 and 1 in "
        "130) were later listed as cancelled.",
    48: f"This flight has between 1 and 2 days to go. {_SO_FAR} 48 hours to go, about 1 in 70 (between 1 in 35 and 1 in "
        "140) were later listed as cancelled.",
    24: f"This flight has between 12 and 24 hours to go. {_SO_FAR} 24 hours to go, about 1 in 100 (between 1 in 45 and 1 "
        "in 200) were later listed as cancelled.",
    12: f"This flight has between 6 and 12 hours to go. {_SO_FAR} 12 hours to go, about 1 in 150 (between 1 in 70 and 1 "
        "in 300) were later listed as cancelled.",
    6: f"This flight has between 3 and 6 hours to go. {_SO_FAR} 6 hours to go, about 1 in 190 (between 1 in 95 and 1 in "
       "400) were later listed as cancelled.",
    3: f"This flight has under 3 hours to go. {_SO_FAR} 3 hours to go, about 1 in 230 (between 1 in 110 and 1 in 460) "
       "were later listed as cancelled.",
}


@pytest.mark.parametrize("h", sorted(PAIRS, reverse=True))
def test_pair(h):
    assert words.pair(h, A35_ROWS[h][0]) == PAIRS[h]


def test_no_pair_below_the_floor():
    assert words.pair(24, rate(3, 120, 40.0, 10.0, 90.0, floor=False)) is None


def test_condition_and_has_passed_read_the_update_in_israel_time(israeli_machine):
    updated = datetime(2026, 11, 12, 10, 16, 45)
    assert words.condition(updated) == (
        "The figure is for flights the airport's list showed normally. This page was last updated 12 Nov 2026, "
        "12:16 and cannot say what the list shows now. Check the airport's own list.")
    assert words.has_passed(updated) == (
        "This flight's scheduled time has passed. The row below shows the list as it was on 12 Nov 2026, 12:16.")


class FakeSummary:
    figures = type("F", (), {"total": TOTAL})()
    unknown, unknown_gap, unknown_no_final = 269, 240, 29
    late_after, late_holds, late_unplaced, late_before = 9, 1, 19, 52
    first_record = date(2026, 10, 27)


def test_count_line():
    assert words.count_line(FakeSummary()) == (
        "Counted: 4,658 flights with a known outcome, scheduled up to two days before the last update, in a record "
        "kept since 27 October 2026. Not counted: 269 flights with no known outcome. 240 of them left the list "
        "while nothing was recorded, and 29 left it with no final status.")


def test_count_line_carries_thousands_separators():
    s = FakeSummary()
    s.unknown, s.unknown_gap, s.unknown_no_final = 2690, 2400, 1290
    line = words.count_line(s)
    assert "Not counted: 2,690 flights" in line and "2,400 of them" in line and "and 1,290 left it" in line


def test_total_cancelled_count_carries_thousands_separators():
    assert words.total(rate(1200, 90000, 75.0, 60.0, 90.0)).startswith(
        "So far, 1,200 of 90,000 flights with a known outcome")


def test_late_line_counts_carry_thousands_separators():
    s = FakeSummary()
    s.late_after = 1500
    s.figures = type("F", (), {"total": rate(2500, 90000, 36.0, 30.0, 40.0)})()
    assert words.late_line(s) == ("At least 1,500 of the 2,500 cancelled flights were listed as cancelled only "
                                  "after their scheduled time.")


def test_late_line():
    assert words.late_line(FakeSummary()) == (
        "At least 9 of the 81 cancelled flights were listed as cancelled only after their scheduled time.")
    s = FakeSummary()
    s.late_after = 0
    assert words.late_line(s) is None


def test_another_number():
    for verb in ("departed", "landed", "is still listed"):
        assert words.another_number(verb) == (
            f"Listed as cancelled. Another flight number with the same scheduled time and airport {verb}:")


# --- what changed ----------------------------------------------------------------------------------

def utc(day, h, m, s=0):
    """A model time (naive UTC) in October 2026; Israel is UTC+2 after the 25 October clock change."""
    return datetime(2026, 10, day, h, m, s)


def local(day, h, m):
    """An airport time (Israel wall-clock, as published) in October 2026."""
    return datetime(2026, 10, day, h, m)


def first(observed_at, sched, est=None, status="ON TIME", terminal=1, counters=None, zone=None):
    """A flight's earliest record, as the model's observations table has it; `est` defaults to the scheduled time."""
    return {"observed_at": observed_at, "prev_observed_at": None, "change_kind": "first", "changed_fields": [],
            "sched_local": sched, "est_local": sched if est is None else est, "status": status,
            "terminal": terminal, "counters": counters, "zone": zone}


def then(prev, observed_at, prev_observed_at, kind="change", **new):
    """The flight's next record: the previous values with `new` changed, which changed_fields names."""
    return prev | new | {"observed_at": observed_at, "prev_observed_at": prev_observed_at, "change_kind": kind,
                         "changed_fields": list(new)}


TO_SCHED = local(29, 17, 10)
_to = [first(utc(27, 18, 4, 46), TO_SCHED)]
_to.append(then(_to[-1], utc(29, 12, 29, 3), utc(27, 18, 24, 46), counters="345-348", zone="B"))
_to.append(then(_to[-1], utc(29, 15, 32, 45), utc(29, 15, 16, 45), est_local=local(29, 17, 38)))
_to.append(then(_to[-1], utc(29, 16, 32, 45), utc(29, 16, 16, 45), est_local=local(29, 18, 45)))
_to.append(then(_to[-1], utc(29, 17, 32, 45), utc(29, 17, 16, 45), status="CANCELED", status_he="מבוטלת"))
TO3459_OBS = _to


def test_to3459_lines():
    assert words.change_lines(TO3459_OBS, "D", date(2026, 10, 29), 1) == [
        ("Earliest record (27 Oct 20:04)", "on time, terminal 1"),
        ("Between 27 Oct 20:24 and 14:29", "Check-in desks 345-348, zone B"),
        ("17:32", "Expected to leave at 17:38 instead"),
        ("18:32", "Expected to leave at 18:45 instead"),
        ("Between 19:16 and 19:32", "Cancelled"),
    ]


ON_TIME_LINE = ("Earliest record (27 Oct 20:04)", "on time, terminal 1")
ON_TIME = first(utc(27, 18, 4, 46), local(29, 16, 45))
INBOUND = first(utc(27, 18, 4, 46), local(29, 19, 30), terminal=3)
RETIMED = first(utc(30, 18, 2, 45), local(30, 23, 30))
DESKED = ON_TIME | {"counters": "332-338", "zone": "C"}
CANCELLED_FIRST = ON_TIME | {"status": "CANCELED"}

# (records, direction, page date, the lines): the cases the spec and the brief name, and records the model can give
CHANGE_CASES = [
    # the earliest record with everything: status, expected time (it differs), terminal, desks, zone
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), est=local(29, 17, 9), status="DEPARTED",
            counters="332-338", zone="C")], "D", DAY,
     [("Earliest record (27 Oct 20:04)",
       "departed, expected to leave at 17:09, terminal 1, check-in desks 332-338, zone C")]),
    # empty desks and zone as the real model holds them (''), left out like None
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), counters="", zone="")], "D", DAY, [ON_TIME_LINE]),
    # an unmapped status appears lower-cased
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), status="GATE CLOSED")], "D", DAY,
     [("Earliest record (27 Oct 20:04)", "gate closed, terminal 1")]),
    # one record changing the expected time and the status, an arrival
    ([INBOUND, then(INBOUND, utc(29, 14, 2, 44), utc(29, 13, 46, 44), est_local=local(29, 19, 36),
                    status="FINAL", status_he="סופי")], "A", DAY,
     [("Earliest record (27 Oct 20:04)", "on time, terminal 3"),
      ("16:02", "Expected to land at 19:36 instead, status “final”")]),
    # a cancellation seen within a minute of the previous record is still a range
    ([ON_TIME, then(ON_TIME, utc(29, 17, 32, 45), utc(29, 17, 31, 50), status="CANCELED", status_he="מבוטלת")],
     "D", DAY, [ON_TIME_LINE, ("Between 19:31 and 19:32", "Cancelled")]),
    # exactly the gap after the previous record is still one time; a second more is a range
    ([ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 14, 32, 45), terminal=3)], "D", DAY,
     [ON_TIME_LINE, ("17:32", "Terminal 3")]),
    ([ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 14, 32, 44), terminal=3)], "D", DAY,
     [ON_TIME_LINE, ("Between 16:32 and 17:32", "Terminal 3")]),
    # desks taken away, alone or with the zone, None or ''
    ([DESKED, then(DESKED, utc(29, 15, 32, 45), utc(29, 15, 16, 45), counters=None)], "D", DAY,
     [("Earliest record (27 Oct 20:04)", "on time, terminal 1, check-in desks 332-338, zone C"),
      ("17:32", "No check-in desks")]),
    ([ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 15, 16, 45), counters="", zone="")], "D", DAY,
     [ON_TIME_LINE, ("17:32", "No check-in desks, no check-in zone")]),
    # no expected time or terminal (the model's casts can give NULL): left out, or said, never "None"
    ([ON_TIME | {"est_local": None, "terminal": None}], "D", DAY, [("Earliest record (27 Oct 20:04)", "on time")]),
    ([ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 15, 16, 45), est_local=None, terminal=None)], "D", DAY,
     [ON_TIME_LINE, ("17:32", "No expected time, no terminal")]),
    # cancelled from the earliest record on: "already", so the time reads as the record's, not a cancellation's
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), status="CANCELED", terminal=3)], "D", DAY,
     [("Earliest record (27 Oct 20:04)", "already cancelled, terminal 3")]),
    # a status changed back from cancelled is a plain status line
    ([CANCELLED_FIRST, then(CANCELLED_FIRST, utc(29, 15, 32, 45), utc(29, 15, 16, 45), status="NOT FINAL",
                            status_he="לא סופי")],
     "D", DAY, [("Earliest record (27 Oct 20:04)", "already cancelled, terminal 1"),
                ("17:32", "Status “not final”")]),
    # a retime: the previous record's scheduled time to this one's; an expected time equal to the new
    # scheduled time adds nothing, one that differs is said, with the record's other changes
    ([RETIMED, then(RETIMED, utc(30, 20, 32, 45), utc(30, 20, 16, 45), kind="retime",
                    sched_local=local(31, 1, 10), est_local=local(31, 1, 10))], "D", date(2026, 10, 31),
     [("Earliest record (30 Oct 20:02)", "on time, terminal 1"),
      ("30 Oct 22:32", "Moved to a new scheduled time: 30 Oct 23:30 → 01:10")]),
    ([RETIMED, then(RETIMED, utc(30, 20, 32, 45), utc(30, 20, 16, 45), kind="retime",
                    sched_local=local(31, 1, 10), est_local=local(31, 1, 25), status="NOT FINAL",
                    status_he="לא סופי")], "D", date(2026, 10, 31),
     [("Earliest record (30 Oct 20:02)", "on time, terminal 1"),
      ("30 Oct 22:32",
       "Moved to a new scheduled time: 30 Oct 23:30 → 01:10, expected to leave at 01:25 instead, "
       "status “not final”")]),
]


@pytest.mark.parametrize("obs, direction, page_date, lines", CHANGE_CASES)
def test_change_lines(obs, direction, page_date, lines):
    assert words.change_lines(obs, direction, page_date, 1) == lines


@pytest.mark.parametrize("changed", [
    {"status_he": "בזמן"}, {"airline_name": "TRANSAVIA  FRANCE"}, {"airport_name": "ORLY"},
    {"city_en": "PARIS"}, {"city_he": "פריז"}, {"country_en": "FRANCE"}, {"country_he": "צרפת"},
])
def test_a_names_only_change_gives_no_line(changed):
    """Hebrew status and name spellings are the airport's own edits; the flight's story did not change."""
    obs = [ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 15, 16, 45), **changed)]
    assert words.change_lines(obs, "D", DAY, 1) == [ON_TIME_LINE]


def test_status_words():
    assert words.STATUS_WORDS == {
        "ON TIME": "on time", "NOT FINAL": "“not final”", "FINAL": "“final”", "DELAYED": "delayed",
        "LANDING": "landing", "LANDED": "landed", "DEPARTED": "departed", "CANCELED": "cancelled", "EARLY": "early",
    }


# --- the upload check ------------------------------------------------------------------------------

def site_texts() -> list[str]:
    """Every fixed text of the module, and what each sentence function says over this file's cases."""
    texts = [words.UNOFFICIAL, words.SOURCE_SHORT, words.TIMES_NOTE, words.PLACEHOLDER, words.BUILT_BY,
             words.CODE_URL, words.DELAY_SENTENCE, *words.LABEL_ORDER]
    for lo, hi, censored, direction, _ in WARNING_CASES:
        f = cancelled(lo, hi, censored, direction)
        texts += [words.warning(f), words.warning_note(f), words.warning_sentence(words.warning(f))]
    texts += [words.warning_sentence(text) for text, _ in SENTENCE_CASES]
    texts += [words.label_note({"outcome": o, "sched_utc_final": SCHED, "last_seen_at": seen})
              for o, seen, _ in LABEL_NOTE_CASES]
    texts += [words.changed_back({"uncanceled": u}, label) for u, label, _ in CHANGED_BACK_CASES]
    texts += [words.total(TOTAL), words.pair(24, A35_ROWS[24][0]), words.count_line(FakeSummary()),
              words.late_line(FakeSummary()), words.another_number("departed"), words.PAST_ONLY, words.A_FLIGHT,
              words.FROM_HERE_FIRST, *words.UNDER_TABLE, *words.LEAD_INS.values(),
              words.condition(datetime(2026, 11, 12, 10, 16, 45)), words.has_passed(datetime(2026, 11, 12, 10, 16, 45)),
              words.FROM_HERE_HEADING, *words.FROM_HERE_COLUMNS, *words.CHECKPOINT_NAMES.values(), words.TOO_FEW,
              words.BRACKET, words.total(rate(3, 120, 40.0, 10.0, 90.0, floor=False)),
              words.another_number("landed"), words.another_number("is still listed")]
    texts += [words.last_expected({"est_local_final": est, "sched_local_final": sched}, DAY)
              for est, sched, _ in LAST_EXPECTED_CASES]
    texts += [words.scheduled(d, datetime(2026, 10, 29, 17, 10), DAY) for d in ("D", "A")]
    texts += list(words.STATUS_WORDS.values())
    # a day's lines as the page reads them: left column and text, line after line, as one run
    for obs, direction, page_date in [(TO3459_OBS, "D", DAY), *((o, d, p) for o, d, p, _ in CHANGE_CASES)]:
        texts.append(" ".join(f"{left} {text}" for left, text in words.change_lines(obs, direction, page_date, 1)))
    return [t for t in texts if t is not None]


def test_no_text_trips_the_upload_check():
    """These texts go on every kind of page; a banned phrase in one would stop every upload. Lower-cased
    substrings, as timeline.check matches them."""
    texts = site_texts()
    assert len(texts) > 60  # the cases above, not an empty list
    phrases = (*check.BANNED, "minutes late", "hours late")
    assert [(t, p) for t in texts for p in phrases if p in t.lower()] == []
