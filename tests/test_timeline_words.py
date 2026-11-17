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
    assert str(words.ISRAEL) == "Asia/Jerusalem"


def test_labels_and_their_order():
    assert words.LABEL_ORDER == ("DEPARTED", "LANDED", "CANCELLED", "UPCOMING", "NO NEWS YET", "UNKNOWN")
    assert words.LABEL_ORDER == (words.DEPARTED, words.LANDED, words.CANCELLED, words.UPCOMING,
                                 words.NO_NEWS_YET, words.UNKNOWN)
    assert words.NO_NEWS_YET == "NO NEWS YET"


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
    (datetime(2026, 10, 29, 21, 55), "NO NEWS YET"),
    (LAST_FETCH, "NO NEWS YET"),  # at the last record's time: no longer ahead
])
def test_open_flight_upcoming_until_its_scheduled_time(sched_utc_final, label):
    assert words.main_label("open", sched_utc_final, LAST_FETCH) == label


def test_unknown_outcome_refused():
    with pytest.raises(ValueError, match="unknown outcome"):
        words.main_label("teleported", datetime(2026, 10, 29, 22, 10), LAST_FETCH)


def test_no_news_yet_is_decided_in_utc(israeli_machine):
    """23:55 Israel time is 21:55 UTC, before the 22:02 UTC last record: the evening flights of 29 October
    have no news yet. Comparing the Israel wall-clock value would call them UPCOMING."""
    f = {"outcome": "open", "sched_local_final": datetime(2026, 10, 29, 23, 55),
         "sched_utc_final": datetime(2026, 10, 29, 21, 55)}
    assert words.main_label(f["outcome"], f["sched_utc_final"], LAST_FETCH) == "NO NEWS YET"


SCHED = datetime(2026, 10, 29, 16, 30)


def lnote(outcome, last_seen_at=SCHED - timedelta(hours=9)):
    return {"outcome": outcome, "sched_utc_final": SCHED, "last_seen_at": last_seen_at}


VANISHED_45 = lnote("vanished", SCHED - timedelta(hours=45, minutes=20))
LABEL_NOTE_CASES = [
    (lnote("open"), "NO NEWS YET", False,
     "Its time has passed, and the airport hasn't said how it ended."),
    (lnote("gap"), "UNKNOWN", False, "There's no record of how this flight ended."),
    (VANISHED_45, "UNKNOWN", False,
     "The airport removed this flight 45 hours early without saying why. "
     "It may have been cancelled or moved to another time."),
    (VANISHED_45, "UNKNOWN", True,
     "The airport removed this flight 45 hours early without saying why. "
     "It may have been cancelled or moved to another time. Check with your airline."),
    (lnote("vanished", SCHED - timedelta(hours=1, minutes=5)), "UNKNOWN", False,
     "The airport removed this flight 1 hour early without saying why. "
     "It may have been cancelled or moved to another time."),
    # Question 6g: under an hour reads "less than an hour", never "0 hours" (the model's rule today calls a flight
    # vanished only more than an hour early, so no page shows it yet)
    (lnote("vanished", SCHED - timedelta(minutes=59)), "UNKNOWN", True,
     "The airport removed this flight less than an hour early without saying why. "
     "It may have been cancelled or moved to another time. Check with your airline."),
    (lnote("dropped"), "UNKNOWN", False, "The airport removed this flight without saying why."),
    (lnote("departed"), "DEPARTED", False, None), (lnote("landed"), "LANDED", False, None),
    (lnote("canceled"), "CANCELLED", False, None), (lnote("open"), "UPCOMING", True, None),
]


@pytest.mark.parametrize("f, label, ahead, note", LABEL_NOTE_CASES)
def test_label_note(f, label, ahead, note):
    assert words.label_note(f, label, ahead) == note


CHANGED_BACK_CASES = [
    (True, "LANDED", "Marked cancelled for a while, then back on."),
    (True, "CANCELLED", "Cancelled, back on, then cancelled again."),
    (None, "CANCELLED", None),  # NULL: the earliest record already showed it cancelled, never shown otherwise
    (False, "LANDED", None),
]


@pytest.mark.parametrize("uncanceled, label, line", CHANGED_BACK_CASES)
def test_changed_back_lines(uncanceled, label, line):
    assert words.changed_back({"uncanceled": uncanceled}, label) == line


def test_scheduled():
    assert words.scheduled("D", datetime(2026, 10, 29, 17, 10), DAY) == "scheduled to leave at 17:10"
    assert words.scheduled("A", datetime(2026, 10, 29, 13, 50), DAY) == "scheduled to land at 13:50"
    assert (words.scheduled("D", datetime(2026, 10, 29, 17, 10), date(2026, 10, 30))
            == "scheduled to leave at 29 Oct 17:10")


S, E = datetime(2026, 11, 16, 19, 45), datetime(2026, 11, 16, 19, 55)
PAGE = date(2026, 11, 16)
TIME_LINE_CASES = [
    # a day labelled LANDED or DEPARTED with an expected time, even when the two are the same
    ("A", S, E, "LANDED", "scheduled 19:45 · landed around 19:55"),
    ("D", datetime(2026, 11, 16, 17, 30), datetime(2026, 11, 16, 17, 38), "DEPARTED",
     "scheduled 17:30 · left around 17:38"),
    ("A", S, S, "LANDED", "scheduled 19:45 · landed around 19:45"),
    ("D", S, S, "DEPARTED", "scheduled 19:45 · left around 19:45"),
    # an expected time on another date carries its date
    ("A", datetime(2026, 11, 16, 23, 50), datetime(2026, 11, 17, 0, 10), "LANDED",
     "scheduled 23:50 · landed around 17 Nov 00:10"),
    # a day with no final word whose expected time differs
    ("A", S, E, "UPCOMING", "scheduled 19:45 · expected 19:55"),
    ("D", S, E, "NO NEWS YET", "scheduled 19:45 · expected 19:55"),
    ("A", S, E, "UNKNOWN", "scheduled 19:45 · expected 19:55"),
    # otherwise: no expected time, the same time, or a cancelled day
    ("A", S, S, "UPCOMING", "scheduled to land at 19:45"),
    ("D", S, S, "NO NEWS YET", "scheduled to leave at 19:45"),
    ("A", S, None, "LANDED", "scheduled to land at 19:45"),
    ("D", S, None, "UPCOMING", "scheduled to leave at 19:45"),
    ("D", S, E, "CANCELLED", "scheduled to leave at 19:45"),
]


@pytest.mark.parametrize("direction, sched, est, label, line", TIME_LINE_CASES)
def test_the_time_lines_four_forms(direction, sched, est, label, line):
    assert words.time_line(direction, sched, est, label, PAGE) == line


def test_the_time_line_names_the_date_of_a_scheduled_time_off_the_page():
    assert words.time_line("D", S, E, "UPCOMING", date(2026, 11, 17)) == "scheduled 16 Nov 19:45 · expected 16 Nov 19:55"


def test_expected_note_and_final_note_are_the_designs_words():
    assert words.EXPECTED_NOTE == (
        "Expected times are the airport's own. Delays under an hour aren't counted, because the airport doesn't "
        "say whether its time means leaving the gate or taking off.")
    assert words.FINAL_NOTE == "“Final” and “not final” are the airport's own words. It doesn't explain them."
    assert words.NOTICE_GIVEN == "Notice given"


# --- notice ----------------------------------------------------------------------------------------

def cancelled(lo, hi, censored, direction="D", outcome="canceled"):
    return {"outcome": outcome, "direction": direction, "cancel_lead_min": lo, "cancel_lead_max_min": hi,
            "cancel_lead_censored": censored}


LATE = "Cancelled with no notice: it was marked cancelled"
GAP = "(There's a gap in the records then.)"
NOTICE_CASES = [
    # rule 1: hi NULL, lo >= 60 (IZ 992)
    (1400.95, None, True, "A", "Cancelled with at least 23 hours' notice. It was already cancelled when it first appeared.",
     "23+ hours"),
    (60.0, None, True, "D", "Cancelled with at least 1 hour's notice. It was already cancelled when it first appeared.",
     "1+ hours"),
    # rule 2: hi NULL, lo < 60 (ASY 991)
    (59.9, None, True, "D", "How much notice is unknown: it was already cancelled when it first appeared.", "unknown"),
    (-59.05, None, True, "D", "How much notice is unknown: it was already cancelled when it first appeared.", "unknown"),
    # rule 3: hi < 0, not censored (TO 3459)
    (-50.0, -10.0, False, "D", f"{LATE} less than an hour after it should have left.", "none"),
    (-50.0, -10.0, False, "A", f"{LATE} less than an hour after it should have landed.", "none"),
    (-60.0, -30.0, False, "D", f"{LATE} about an hour after it should have left.", "none"),  # -lo exactly 60
    (-70.0, -30.0, False, "D", f"{LATE} about an hour after it should have left.", "none"),
    (-150.0, -120.0, False, "D", f"{LATE} about 2 hours after it should have left.", "none"),  # -hi exactly 120
    (-142.75, -126.75, False, "D", f"{LATE} about 2 hours after it should have left.", "none"),
    (-142.75, -126.75, False, "A", f"{LATE} about 2 hours after it should have landed.", "none"),
    # rule 4: hi < 0, censored
    (-200.0, -100.0, True, "D",
     f"Cancelled with no notice: it was only marked cancelled after its scheduled time. {GAP}", "none"),
    # rule 5: censored, lo >= 60 (LY 5410, and LY 5409's shape over 42 hours)
    (445.95, 2970.48, True, "A", f"Cancelled between 7 and 50 hours before its scheduled time. {GAP}", "7 to 50 hours"),
    (75.95, 2600.48, True, "D", f"Cancelled between 1 and 44 hours before its scheduled time. {GAP}", "1 to 44 hours"),
    (60.0, 2000.0, True, "D", f"Cancelled between 1 and 34 hours before its scheduled time. {GAP}", "1 to 34 hours"),
    (60.0, 2520.0, True, "D", f"Cancelled between 1 and 42 hours before its scheduled time. {GAP}", "1 to 42 hours"),
    # rule 6: censored, 0 <= lo < 60
    (0.0, 2000.0, True, "D", f"Cancelled up to 34 hours before its scheduled time. {GAP}", "up to 34 hours"),
    (59.9, 2000.0, True, "D", f"Cancelled up to 34 hours before its scheduled time. {GAP}", "up to 34 hours"),
    # rule 7: censored, lo < 0 (BZ 254)
    (-64.05, 2460.48, True, "D", "How much notice is unknown: there's a gap in the records then.", "unknown"),
    # rule 8: not censored, lo >= 60
    (400.0, 416.0, False, "D", "Cancelled with at least 6 hours' notice.", "6+ hours"),
    (60.0, 75.0, False, "D", "Cancelled with at least 1 hour's notice.", "1+ hours"),
    (1295.0, 1310.0, False, "D", "Cancelled with at least 21 hours' notice.", "21+ hours"),
    # rule 9: not censored, 0 <= lo, hi < 60
    (0.0, 59.0, False, "D", "Cancelled less than an hour before its scheduled time.", "under an hour"),
    # rule 10: not censored, 0 <= lo < 60 <= hi
    (45.0, 74.0, False, "D", "Cancelled about an hour before its scheduled time.", "about an hour"),
    (59.9, 60.0, False, "D", "Cancelled about an hour before its scheduled time.", "about an hour"),
    # rule 11: not censored, lo < 0 <= hi
    (-10.0, 6.0, False, "D", "Cancelled around its scheduled time.", "almost none"),
    (-10.0, 0.0, False, "D", "Cancelled around its scheduled time.", "almost none"),
]


@pytest.mark.parametrize("lo, hi, censored, direction, sentence, short", NOTICE_CASES)
def test_notice_rules(lo, hi, censored, direction, sentence, short):
    assert words.notice(cancelled(lo, hi, censored, direction)) == words.Notice(sentence, short)


def test_notice_boundary_60_belongs_to_the_row_that_says_at_least():
    assert words.notice(cancelled(60.0, 75.0, False)).short == "1+ hours"
    assert words.notice(cancelled(59.99, 75.0, False)).short == "about an hour"
    assert words.notice(cancelled(0.0, 59.99, False)).short == "under an hour"
    assert words.notice(cancelled(0.0, 60.0, False)).short == "about an hour"


def test_notice_one_hour_and_one_plus_hours():
    n = words.notice(cancelled(60.0, 75.0, False))
    assert "1 hour's notice" in n.sentence and "1 hours" not in n.sentence and n.short == "1+ hours"
    n = words.notice(cancelled(60.0, None, True))
    assert "1 hour's notice" in n.sentence and n.short == "1+ hours"


def test_no_notice_unless_cancelled():
    assert words.notice(cancelled(400.0, 416.0, False, outcome="departed")) is None
    assert words.notice(cancelled(1400.95, None, True, outcome="open")) is None


def test_the_notice_is_a_frozen_pair():
    n = words.Notice("a", "b")
    assert (n.sentence, n.short) == ("a", "b")
    with pytest.raises(AttributeError):
        n.sentence = "c"


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
    assert words.LEAD_INS == {70: "between 2 and 3 days", 48: "between 1 and 2 days", 24: "between 12 and 24 hours",
                              12: "between 6 and 12 hours", 6: "between 3 and 6 hours", 3: "under 3 hours"}
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


def test_condition_reads_the_update_in_israel_time(israeli_machine):
    updated = datetime(2026, 11, 12, 10, 16, 45)
    assert words.condition(updated) == (
        "The figure is for flights the airport's list showed normally. This page was last updated 12 Nov 2026, "
        "12:16 and cannot say what the list shows now. Check the airport's own list.")


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


def test_also_sold_as_and_the_twin_lines_words():
    """docs/flight-lookup.md, "Flight page: other situations": the words before and after the linked numbers."""
    assert (words.ALSO_SOLD, words.SAME_PLANE) == ("Also sold as", "(probably the same plane).")
    assert words.twin("departed") == ("This number was cancelled, but the flight probably left as", ".")
    assert words.twin("landed") == ("This number was cancelled, but the flight probably landed as", ".")
    assert words.twin("is still listed") == (
        "This number is marked cancelled, but the flight is probably still on, as", ".")
    assert words.twin("has no news yet") == (  # Question 6h
        "This number was cancelled, but the flight may have gone ahead as", ".")
    assert not hasattr(words, "another_number") and not hasattr(words, "BRACKET")


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
# The records' first list (18:04Z on 27 October) and the end of the 42-hour hole (12:29Z on 29 October), as
# build.render gives them: a first record at either reads "Already on the list".
RESUMES = frozenset({utc(27, 18, 4, 46), utc(29, 12, 29, 3)})


def test_to3459_lines():
    assert words.change_lines(TO3459_OBS, "D", date(2026, 10, 29), 1, RESUMES) == [
        ("Already on the list on 27 Oct at 20:04", "on time, terminal 1"),
        ("Between 27 Oct 20:24 and 14:29", "Check-in desks 345-348, zone B"),
        ("17:32", "Expected to leave at 17:38 instead"),
        ("18:32", "Expected to leave at 18:45 instead"),
        ("Between 19:16 and 19:32", "Cancelled"),
    ]


ON_TIME_LINE = ("First on the list on 27 Oct at 20:04", "on time, terminal 1")
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
     [("First on the list on 27 Oct at 20:04",
       "departed, expected to leave at 17:09, terminal 1, check-in desks 332-338, zone C")]),
    # empty desks and zone as the real model holds them (''), left out like None
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), counters="", zone="")], "D", DAY, [ON_TIME_LINE]),
    # an unmapped status appears lower-cased
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), status="GATE CLOSED")], "D", DAY,
     [("First on the list on 27 Oct at 20:04", "gate closed, terminal 1")]),
    # one record changing the expected time and the status, an arrival
    ([INBOUND, then(INBOUND, utc(29, 14, 2, 44), utc(29, 13, 46, 44), est_local=local(29, 19, 36),
                    status="FINAL", status_he="סופי")], "A", DAY,
     [("First on the list on 27 Oct at 20:04", "on time, terminal 3"),
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
     [("First on the list on 27 Oct at 20:04", "on time, terminal 1, check-in desks 332-338, zone C"),
      ("17:32", "No check-in desks")]),
    ([ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 15, 16, 45), counters="", zone="")], "D", DAY,
     [ON_TIME_LINE, ("17:32", "No check-in desks, no check-in zone")]),
    # no expected time or terminal (the model's casts can give NULL): left out, or said, never "None"
    ([ON_TIME | {"est_local": None, "terminal": None}], "D", DAY,
     [("First on the list on 27 Oct at 20:04", "on time")]),
    ([ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 15, 16, 45), est_local=None, terminal=None)], "D", DAY,
     [ON_TIME_LINE, ("17:32", "No expected time, no terminal")]),
    # cancelled from the earliest record on: "already", so the time reads as the record's, not a cancellation's
    ([first(utc(27, 18, 4, 46), local(29, 16, 45), status="CANCELED", terminal=3)], "D", DAY,
     [("First on the list on 27 Oct at 20:04", "already cancelled, terminal 3")]),
    # a status changed back from cancelled is a plain status line
    ([CANCELLED_FIRST, then(CANCELLED_FIRST, utc(29, 15, 32, 45), utc(29, 15, 16, 45), status="NOT FINAL",
                            status_he="לא סופי")],
     "D", DAY, [("First on the list on 27 Oct at 20:04", "already cancelled, terminal 1"),
                ("17:32", "Status “not final”")]),
    # a retime: the previous record's scheduled time to this one's; an expected time equal to the new
    # scheduled time adds nothing, one that differs is said, with the record's other changes
    ([RETIMED, then(RETIMED, utc(30, 20, 32, 45), utc(30, 20, 16, 45), kind="retime",
                    sched_local=local(31, 1, 10), est_local=local(31, 1, 10))], "D", date(2026, 10, 31),
     [("First on the list on 30 Oct at 20:02", "on time, terminal 1"),
      ("30 Oct 22:32", "Moved to a new scheduled time: 30 Oct 23:30 → 01:10")]),
    ([RETIMED, then(RETIMED, utc(30, 20, 32, 45), utc(30, 20, 16, 45), kind="retime",
                    sched_local=local(31, 1, 10), est_local=local(31, 1, 25), status="NOT FINAL",
                    status_he="לא סופי")], "D", date(2026, 10, 31),
     [("First on the list on 30 Oct at 20:02", "on time, terminal 1"),
      ("30 Oct 22:32",
       "Moved to a new scheduled time: 30 Oct 23:30 → 01:10, expected to leave at 01:25 instead, "
       "status “not final”")]),
]


@pytest.mark.parametrize("obs, direction, page_date, lines", CHANGE_CASES)
def test_change_lines(obs, direction, page_date, lines):
    assert words.change_lines(obs, direction, page_date, 1, frozenset()) == lines


def test_the_first_lines_four_forms(israeli_machine):
    """docs/site-redesign.md, "What changed": the first line says when the flight was first on the list, with the date
    when it is not the page's; "Already on the list" when its record is the records' first list or the first after a
    hole (`resumes`), since the flight was on the airport's list before the records could see it; and "already
    cancelled" in the status's place, so its time reads as the listing's."""
    def nov(day, h, m, s=0):
        return datetime(2026, 11, day, h, m, s)  # a model time or an airport time; Israel is UTC+2 in November

    first_list, hole_end = utc(27, 18, 4, 46), utc(29, 12, 29, 3)
    resumes = frozenset({first_list, hole_end})
    wz016 = first(nov(17, 7, 32, 45), nov(17, 5, 35), terminal=3)  # WZ 016: first on the list at 09:32
    assert words.change_lines([wz016], "D", date(2026, 11, 17), 1, resumes) == [
        ("First on the list at 09:32", "on time, terminal 3")]
    earlier = first(nov(14, 17, 46, 45), nov(17, 5, 35), status="NOT FINAL", terminal=3)
    assert words.change_lines([earlier], "D", date(2026, 11, 17), 1, resumes) == [
        ("First on the list on 14 Nov at 19:46", "“not final”, terminal 3")]
    landed = first(first_list, local(27, 19, 30), est=local(27, 19, 18), status="LANDED", terminal=3)
    assert words.change_lines([landed], "A", date(2026, 10, 27), 1, resumes) == [
        ("Already on the list at 20:04", "landed, expected to land at 19:18, terminal 3")]
    assert words.change_lines([first(first_list, local(29, 16, 45), terminal=3)], "D", DAY, 1, resumes) == [
        ("Already on the list on 27 Oct at 20:04", "on time, terminal 3")]
    assert words.change_lines([first(hole_end, local(29, 17, 10))], "D", DAY, 1, resumes) == [
        ("Already on the list at 14:29", "on time, terminal 1")]
    assert words.change_lines([first(hole_end + timedelta(seconds=1), local(29, 17, 10))], "D", DAY, 1, resumes) == [
        ("First on the list at 14:29", "on time, terminal 1")]
    cancelled = first(first_list, local(27, 22, 0), status="CANCELED", terminal=3)
    assert words.change_lines([cancelled], "D", date(2026, 10, 27), 1, resumes) == [
        ("Already on the list at 20:04", "already cancelled, terminal 3")]


@pytest.mark.parametrize("changed", [
    {"status_he": "בזמן"}, {"airline_name": "TRANSAVIA  FRANCE"}, {"airport_name": "ORLY"},
    {"city_en": "PARIS"}, {"city_he": "פריז"}, {"country_en": "FRANCE"}, {"country_he": "צרפת"},
])
def test_a_names_only_change_gives_no_line(changed):
    """Hebrew status and name spellings are the airport's own edits; the flight's story did not change."""
    obs = [ON_TIME, then(ON_TIME, utc(29, 15, 32, 45), utc(29, 15, 16, 45), **changed)]
    assert words.change_lines(obs, "D", DAY, 1, frozenset()) == [ON_TIME_LINE]


def test_status_words():
    assert words.STATUS_WORDS == {
        "ON TIME": "on time", "NOT FINAL": "“not final”", "FINAL": "“final”", "DELAYED": "delayed",
        "LANDING": "landing", "LANDED": "landed", "DEPARTED": "departed", "CANCELED": "cancelled", "EARLY": "early",
    }


# --- the words that carry figures (docs/flight-lookup.md, "Words") ------------------------------------------------

def test_rounding():
    assert words.about(0.0099999) == "under 1%"
    assert words.about(0.01) == "about 1%"
    assert words.about(0) == "under 1%"
    assert words.about(0.095003) == "about 10%"
    assert words.about(0.154306) == "about 15%"
    assert words.about(0.125) == "about 13%"
    assert words.about(29 / 200) == "about 15%"  # exact halves in decimal, below the float's
    assert words.about(57 / 200) == "about 29%"
    assert words.about(23 / 40) == "about 58%"
    assert words.about(231 / 2982) == "about 8%"
    assert words.about(149 / 3029) == "about 5%"
    assert words.pct1(3, 2000) == "0.2%"
    assert words.pct1(1, 2000) == "0.1%"
    assert words.pct1(39, 5069) == "0.8%"
    assert words.pct1(104, 6115) == "1.7%"
    assert words.average(39, 5069) == "under 1%"
    assert words.average(71, 4472) == "1.6%"
    assert words.average(1, 100) == "1.0%"  # 1% is not "under 1%"


def test_pct_range_rounds_outward():
    assert words.pct_range(rate(104, 6115, 58.8, 34.9, 90.1)) == "1.7% (between 1.1% and 2.9%)"
    assert words.pct_range(rate(104, 6115, 58.8, 34.9, 100.0)).endswith("(between 1.0% and 2.9%)")
    assert words.pct_range(rate(104, 6115, 58.8, 100.0, 90.1)).endswith("and 1.0%)")
    assert words.pct_range(rate(3, 120, 40.0, 10.0, 90.0, floor=False)) is None
    assert words.pct_range(rate(12, 12, 1.0, None, None)) is None


def test_the_front_pages_table_words():
    assert words.TABLE_HEADING == "Chance of cancellation, by how soon you fly"
    assert words.TABLE_COLUMNS == ("Your flight is…", "Chance it's cancelled")
    assert words.NOT_ENOUGH == "Not enough flights yet"
    assert words.ROW_NAMES == {70: "3 days away", 48: "2 days away", 24: "1 day away", 12: "12 hours away",
                               6: "6 hours away", 3: "3 hours away"}
    assert words.table_first("1.6%", "0.4%") == ("If your flight is still on 3 days before, there's about a 1.6% "
                                                "chance it gets cancelled. By 3 hours before, it's 0.4%.")
    assert words.under_table(5000, date(2026, 10, 27)) == (
        "These are averages for all airlines, from about 5,000 flights since 27 October. "
        "A delayed flight still counts as “still on”.")
    assert words.DELAY_LEAD == "Chance of a delay of an hour or more:"


def test_the_delay_line():
    assert words.delay_line(231 / 2982, 149 / 3029) == (
        "about 8% for departures and 5% for arrivals. It's about the same however soon you fly.")
    assert words.delay_line(0.001, 149 / 3029) == (  # Question 6e
        "under 1% for departures and about 5% for arrivals. It's about the same however soon you fly.")


def test_the_total_in_both_forms():
    big = rate(104, 6115, 58.8, 34.9, 90.1)
    assert words.total_tiles(big) == [("6,115", "flights"), ("104", "cancelled"), ("1.7%", "")]
    assert words.total_sentence(big, date(2026, 10, 27)) == (
        "Since 27 October, 104 of 6,115 flights at Ben Gurion were cancelled (1.7%).")
    small = rate(3, 420, 140.0, 40.0, 300.0, floor=False)
    assert words.total_tiles(small) == [("420", "flights"), ("3", "cancelled")]
    assert words.total_sentence(small, date(2026, 10, 27)) == (
        "Since 27 October, 3 of 420 flights at Ben Gurion were cancelled. Not enough flights yet for a percentage.")
    one = rate(1, 420, 420.0, None, None, floor=False)  # Question 6f
    assert words.total_sentence(one, date(2026, 10, 27)) == (
        "Since 27 October, 1 of 420 flights at Ben Gurion was cancelled. Not enough flights yet for a percentage.")
    assert words.total_sentence(rate(60, 9000, 150.0, 100.0, 200.0), date(2026, 10, 27)).endswith("(under 1%).")


def test_the_late_and_left_out_lines():
    assert words.late_line(15, 104) == ("Some flights (at least 15 of the 104) were only marked cancelled after "
                                        "their scheduled time had passed.")
    assert words.late_line(1500, 2500) == ("Some flights (at least 1,500 of the 2,500) were only marked cancelled "
                                           "after their scheduled time had passed.")
    assert words.late_line(0, 104) is None
    assert words.left_out(285) == "285 flights are left out because there's no record of how they ended."
    assert words.left_out(1) == "1 flight is left out because there's no record of how it ended."
    assert words.left_out(0) is None


def test_the_headline():
    assert words.headline(0.004, 0.012, True) == (("Chance it's cancelled:", "under 1%"),
                                                 ("Chance it's delayed an hour or more:", "about 1%"))
    assert words.headline(0.154306, 0.03, False) == (
        ("Chance its next flight is cancelled:", "about 15%"),
        ("Chance its next flight is delayed an hour or more:", "about 3%"))


def hist(name, flights, cancelled=0, delayed=0, week=None):
    return words.History(name, flights, cancelled, delayed, week)


LO155 = hist("LO 155", 22)
LOT = hist("LOT POLISH AIRLINES", 127, 0, 2)
LH694 = hist("LH 694", 19, 4, 0, (date(2026, 11, 6), date(2026, 11, 9)))
LH = hist("LUFTHANSA", 183, 11, 7, (date(2026, 11, 6), date(2026, 11, 10)))
FLIGHT_ONLY = "Worked out from this flight's history"


def line(number, airline, spoken, ahead=True, listed_since=True):
    return words.worked_out(number, airline, spoken, ahead, listed_since)


def test_every_worked_out_from_form():
    assert line(LO155, LOT, "LOT") == words.Worked(
        f"{FLIGHT_ONLY} (none of its 22 flights was cancelled), LOT's history, and how soon it leaves.", False, False)
    assert line(hist("LH 695", 21, 3), LH, "Lufthansa").text == (
        f"{FLIGHT_ONLY} (3 of its 21 flights were cancelled), Lufthansa's history, and how soon it leaves.")
    assert line(hist("LH 695", 20, 1), LH, "Lufthansa").text == (
        f"{FLIGHT_ONLY} (1 of its 20 flights was cancelled), Lufthansa's history, and how soon it leaves.")
    assert line(LH694, LH, "Lufthansa") == words.Worked(
        f"{FLIGHT_ONLY}: 4 of its 19 flights were cancelled, all between 6 and 9 November. Also from "
        "Lufthansa's history, and how soon it leaves.", True, False)
    assert line(LO155, LOT, "LOT", ahead=False) == words.Worked(
        f"{FLIGHT_ONLY} (none of its 22 flights was cancelled) and LOT's history.", False, False)
    assert line(hist("LH 695", 21, 3), LH, "Lufthansa", ahead=False).text == (  # Question 6b
        f"{FLIGHT_ONLY} (3 of its 21 flights were cancelled) and Lufthansa's history.")
    assert line(LH694, LH, "Lufthansa", ahead=False, listed_since=True) == words.Worked(
        f"{FLIGHT_ONLY}: 4 of its 19 flights were cancelled, all between 6 and 9 November.", True, False)
    assert line(hist("LH 694", 14, 4, 0, LH694.week), LH, "Lufthansa", ahead=False, listed_since=False).text == (
        f"{FLIGHT_ONLY}: 4 of its 14 flights were cancelled, all between 6 and 9 November. "
        "It hasn't been on the airport's list since.")


def test_a_short_history_leads_with_its_airline_or_all_airlines():
    assert line(hist("LH 697", 2, 1), LH, "Lufthansa") == words.Worked(
        "Worked out mostly from Lufthansa's history, because LH 697 has only 2 flights so far. "
        "Lufthansa cancelled 11 of its 183 flights, all between 6 and 10 November.", False, True)
    assert line(hist("LO 157", 5), hist("LOT", 127), "LOT", ahead=False).text == (
        "Worked out mostly from LOT's history, because LO 157 has only 5 flights so far. "
        "LOT cancelled none of its 127 flights.")
    assert line(hist("LY 5", 5), hist("EL AL", 1624, 10), "El Al").text == (
        "Worked out mostly from El Al's history, because LY 5 has only 5 flights so far. "
        "El Al cancelled 10 of its 1,624 flights.")
    assert line(hist("IZ 992", 2), hist("ARKIA", 40), None) == words.Worked(
        "Worked out mostly from all airlines at Ben Gurion, because IZ 992 has only 2 flights so far and its "
        "airline only 40.", False, False)
    # no spoken name
    assert line(hist("IZ 992", 22), hist("ARKIA ISRAELI AIRLINES", 140), None).text == (
        f"{FLIGHT_ONLY} (none of its 22 flights was cancelled), its airline's history, and how soon it leaves.")
    assert line(hist("IZ 992", 2), hist("ARKIA ISRAELI AIRLINES", 140), None) == words.Worked(
        "Worked out mostly from its airline's history, because IZ 992 has only 2 flights so far. "
        "ARKIA ISRAELI AIRLINES cancelled none of its 140 flights.", False, False)
    # how many flights
    assert "has only 1 flight so far" in line(hist("LO 157", 1), LOT, "LOT").text
    assert "because LO 157 has no flights so far." in line(hist("LO 157", 0), LOT, "LOT").text
    assert line(hist("XX 123", 0), hist("XX", 0), None).text == (  # Question 6d
        "Worked out from all airlines at Ben Gurion, because XX 123 and its airline have no flights so far.")
    assert "has no flights so far and its airline only 40." in line(hist("XX 123", 0), hist("XX", 40), None).text


def test_the_picker():
    # a flight ahead or none
    assert "how soon it leaves" in line(LO155, LOT, "LOT", ahead=True).text
    assert "how soon it leaves" not in line(LO155, LOT, "LOT", ahead=False).text
    # 13 and 14 flights, under an airline of 100 and of 99
    assert line(hist("LO 157", 13), hist("LOT", 100), "LOT").text.startswith("Worked out mostly from LOT's history")
    assert line(hist("LO 157", 14), hist("LOT", 100), "LOT").text.startswith(FLIGHT_ONLY)
    assert line(hist("LO 157", 14), hist("LOT", 99), "LOT").text.startswith(FLIGHT_ONLY)  # keeps the first forms
    assert line(hist("LO 157", 13), hist("LOT", 99), "LOT").text.startswith(
        "Worked out mostly from all airlines at Ben Gurion")
    # "how soon it leaves" stays out of every "mostly from" form, with a flight ahead or without
    assert "how soon" not in line(hist("LO 157", 13), hist("LOT", 100), "LOT", ahead=True).text
    assert "how soon" not in line(hist("LO 157", 13), hist("LOT", 99), "LOT", ahead=True).text
    # a bad week: with a flight since and with none
    bad = hist("LH 694", 14, 4, 0, LH694.week)
    assert "since" not in line(bad, LH, "Lufthansa", ahead=False, listed_since=True).text
    assert line(bad, LH, "Lufthansa", ahead=False, listed_since=False).text.endswith(
        "It hasn't been on the airport's list since.")
    assert "since" not in line(bad, LH, "Lufthansa", ahead=True, listed_since=False).text
    # a spoken name or none
    assert "Lufthansa's history" in line(bad, LH, "Lufthansa", ahead=True).text
    assert "its airline's history" in line(bad, LH, None, ahead=True).text
    # the dates, named exactly where the line gives them
    got = line(bad, LH, "Lufthansa")
    assert (got.names_number_week, got.names_airline_week) == (True, False)
    short = line(hist("LH 697", 2, 1), LH, "Lufthansa")
    assert (short.names_number_week, short.names_airline_week) == (False, True)
    clean_short = line(hist("LO 157", 5), LOT, "LOT")
    assert (clean_short.names_number_week, clean_short.names_airline_week) == (False, False)
    assert line(LO155, LOT, "LOT").names_number_week is False
    # 14 flights or more, no bad week of its own, under an airline with one: the line does not give the airline's dates
    assert line(hist("LH 695", 21, 3), LH, "Lufthansa") == words.Worked(
        f"{FLIGHT_ONLY} (3 of its 21 flights were cancelled), Lufthansa's history, and how soon it leaves.", False, False)
    # a short history with a bad week of its own: its dates are the "so far" line's (Question 6c)
    own = line(hist("LH 697", 5, 2, 0, LH694.week), LH, "Lufthansa")
    assert own.names_number_week is False and "6 and 9 November" not in own.text


def test_a_bad_weeks_dates():
    def dates(a, b):
        return line(hist("LH 1", 20, 2, 0, (a, b)), LH, "Lufthansa", ahead=False).text
    assert "2 of its 20 flights were cancelled, all on 6 November." in dates(date(2026, 11, 6), date(2026, 11, 6))
    assert "all between 30 October and 2 November." in dates(date(2026, 10, 30), date(2026, 11, 2))
    assert "all between 6 and 9 November." in dates(date(2026, 11, 6), date(2026, 11, 9))


def test_the_lines_in_smaller_type():
    assert words.so_far(LO155, False) == ("LO 155 so far:", "22 flights · none cancelled · none delayed an hour or more")
    assert words.so_far(hist("LH 694", 14, 4), False) == (
        "LH 694 so far:", "14 flights · 4 cancelled · none delayed an hour or more")
    assert words.so_far(hist("LH 697", 2, 1), False) == (
        "LH 697 so far:", "2 flights · 1 cancelled · none delayed an hour or more")
    assert words.so_far(LOT, False) == (
        "LOT POLISH AIRLINES so far:", "127 flights · none cancelled · 2 delayed an hour or more")
    assert words.so_far(LH, False) == ("LUFTHANSA so far:", "183 flights · 11 cancelled · 7 delayed an hour or more")
    assert words.so_far(LH, True) == (
        "LUFTHANSA so far:", "183 flights · 11 cancelled, all between 6 and 10 November · 7 delayed an hour or more")
    assert words.so_far(hist("LH 697", 5, 2, 0, LH694.week), True) == (  # Question 6c
        "LH 697 so far:", "5 flights · 2 cancelled, all between 6 and 9 November · none delayed an hour or more")
    assert words.so_far(hist("LY", 1624, 10, 1000), True)[1] == (
        "1,624 flights · 10 cancelled · 1,000 delayed an hour or more")
    assert words.so_far(hist("LY 9", 1), False)[1].startswith("1 flight ·")
    assert words.partner("LY 9255", "LO 155", "LOT") == (
        "LY 9255 is also sold as LO 155, so the numbers here are worked out from LOT's history.")


def test_names_go_through_data_and_the_rest_through_text():
    def data(s):
        return f"<{s}>"

    def text(s):
        return s.replace("'", "’")
    assert words.partner("LY 9255", "LO 155", "LOT", text, data) == (
        "<LY 9255> is also sold as <LO 155>, so the numbers here are worked out from <LOT>’s history.")
    assert words.worked_out(LO155, LOT, "LOT", True, True, text, data).text == (
        "Worked out from this flight’s history (none of its 22 flights was cancelled), <LOT>’s history, "
        "and how soon it leaves.")
    assert words.worked_out(hist("IZ 992", 2), hist("ARKIA", 140), None, True, True, text, data).text == (
        "Worked out mostly from its airline’s history, because <IZ 992> has only 2 flights so far. "
        "<ARKIA> cancelled none of its 140 flights.")
    assert words.so_far(LH, False, text, data)[0] == "<LUFTHANSA> so far:"
    assert words.not_listed("LH 694", date(2026, 11, 10), False, text, data).startswith("<LH 694> isn’t on")
    assert words.strip_heading("LO 155", text, data) == "<LO 155>, day by day"


def test_the_six_stretches_of_the_all_airlines_line():
    assert words.STRETCH_NAMES == {70: "2 to 3 days", 48: "1 to 2 days", 24: "12 to 24 hours", 12: "6 to 12 hours",
                                   6: "3 to 6 hours", 3: "less than 3 hours"}
    figures = {70: "1.6%", 48: "1.4%", 24: "1.1%", 12: "under 1%", 6: "under 1%", 3: "under 1%"}
    for h, name in words.STRETCH_NAMES.items():
        assert words.all_airlines(h, figures[h], "about 5%", "A") == (
            f"All airlines at Ben Gurion, {name} before a flight:",
            f"{figures[h]} cancelled · about 5% of arrivals delayed an hour or more")
    assert words.all_airlines(None, "1.7%", "about 5%", "A") == (
        "All airlines at Ben Gurion:", "1.7% cancelled · about 5% of arrivals delayed an hour or more")
    assert words.all_airlines(None, "1.7%", "about 8%", "D")[1] == (
        "1.7% cancelled · about 8% of departures delayed an hour or more")
    assert words.all_airlines(12, "under 1%", "under 1%", "A")[1] == (  # Question 6e
        "under 1% cancelled · under 1% of arrivals delayed an hour or more")


def test_updated_at_is_israel_time(israeli_machine):
    assert words.updated_at(datetime(2026, 11, 17, 7, 46, 12)) == "Updated 17 Nov at 09:46"
    assert words.updated_at(datetime(2026, 7, 5, 7, 46)) == "Updated 5 Jul at 10:46"  # summer time, UTC+3


def test_has_passed_reads_the_update_in_israel_time(israeli_machine):
    assert words.has_passed(datetime(2026, 11, 17, 7, 46)) == (
        "This flight's time has passed. The page was last updated on 17 Nov at 09:46, so it may not show "
        "what happened.")


def test_freshness_and_other_situations():
    assert words.FRESH_REST == "Things may have changed, so check with your airline."
    assert words.MORE_THAN_3_DAYS == ("Your flight is more than 3 days away. Flights show up on the airport's list "
                                      "about 3 days ahead, so check back closer to the date.")
    assert words.MARKED_CANCELLED == ("This flight is marked cancelled.", "Contact your airline.")
    last = date(2026, 11, 10)
    assert words.not_listed("LH 694", last, False) == (
        "LH 694 isn't on the airport's list right now. The last one was on Tuesday 10 November.")
    assert words.not_listed("LH 694", last, True) == (
        "LH 694 has no upcoming flight on the airport's list right now. The last one was on Tuesday 10 November.")


def test_the_strip_key_names_each_kind_with_its_count():
    assert words.strip_key({"LANDED": 22, "UPCOMING": 3}) == ["landed 22", "upcoming 3"]
    assert words.strip_key({"LANDED": 1000}) == ["landed 1,000"]
    assert words.strip_key({"UNKNOWN": 1, "CANCELLED": 4, "LANDED": 10, "DEPARTED": 0}) == [
        "landed 10", "cancelled 4", "unknown 1"]  # LH 694, in LABEL_ORDER, a zero left out


def test_the_strip_words():
    assert words.strip_heading("LO 155") == "LO 155, day by day"
    assert words.mark_name(date(2026, 11, 17), "UPCOMING") == "Tuesday 17 November, upcoming"


def figure_texts() -> list[str]:
    """What the figure-carrying lines say over this section's cases, for the upload check."""
    day = date(2026, 10, 27)
    big = rate(104, 6115, 58.8, 34.9, 90.1)
    small = rate(3, 420, 140.0, 40.0, 300.0, floor=False)
    texts = [words.TABLE_HEADING, *words.TABLE_COLUMNS, words.NOT_ENOUGH, *words.ROW_NAMES.values(),
             words.table_first("1.6%", "0.4%"), words.under_table(5000, day), words.DELAY_LEAD,
             words.delay_line(0.077, 0.049), words.delay_line(0.001, 0.049), words.pct_range(big),
             words.total_sentence(big, day), words.total_sentence(small, day), words.late_line(15, 104),
             words.left_out(285), words.left_out(1), words.FRESH_REST, words.MORE_THAN_3_DAYS,
             *words.MARKED_CANCELLED, words.has_passed(datetime(2026, 11, 17, 7, 46)),
             words.updated_at(datetime(2026, 11, 17, 7, 46)),
             words.not_listed("LH 694", date(2026, 11, 10), False), words.not_listed("LH 694", date(2026, 11, 10), True),
             words.strip_heading("LO 155"), *words.strip_key({"LANDED": 22, "CANCELLED": 4}),
             words.mark_name(date(2026, 11, 17), "UPCOMING"), words.partner("LY 9255", "LO 155", "LOT"),
             *(t for h in words.STRETCH_NAMES for t in words.all_airlines(h, "under 1%", "about 5%", "D"))]
    for h in words.STRETCH_NAMES.values():
        texts.append(h)
    for q, w, spoken in [(LO155, LOT, "LOT"), (LH694, LH, "Lufthansa"), (hist("LH 697", 2, 1), LH, "Lufthansa"),
                         (hist("IZ 992", 2), hist("ARKIA", 40), None), (hist("XX 1", 0), hist("XX", 0), None),
                         (hist("IZ 992", 2), hist("ARKIA", 140), None)]:
        for ahead in (True, False):
            texts.append(words.worked_out(q, w, spoken, ahead, False).text)
        texts += words.so_far(q, True)
    return texts


# --- the upload check ------------------------------------------------------------------------------

def site_texts() -> list[str]:
    """Every fixed text of the module, and what each sentence function says over this file's cases."""
    texts = [words.UNOFFICIAL, words.SOURCE_SHORT, words.TIMES_NOTE, words.PLACEHOLDER, words.BUILT_BY,
             words.CODE_URL, words.EXPECTED_NOTE, words.FINAL_NOTE, words.NOTICE_GIVEN, *words.LABEL_ORDER]
    for lo, hi, censored, direction, *_ in NOTICE_CASES:
        n = words.notice(cancelled(lo, hi, censored, direction))
        texts += [n.sentence, n.short]
    texts += [words.label_note(f, label, ahead) for f, label, ahead, _ in LABEL_NOTE_CASES]
    texts += [words.changed_back({"uncanceled": u}, label) for u, label, _ in CHANGED_BACK_CASES]
    texts += [words.time_line(d, sc, es, label, PAGE) for d, sc, es, label, _ in TIME_LINE_CASES]
    texts += [words.total(TOTAL), words.pair(24, A35_ROWS[24][0]), words.count_line(FakeSummary()),
              words.PAST_ONLY, words.A_FLIGHT, words.ALSO_SOLD, words.SAME_PLANE,
              words.FROM_HERE_FIRST, *words.UNDER_TABLE, *words.LEAD_INS.values(),
              words.condition(datetime(2026, 11, 12, 10, 16, 45)),
              words.FROM_HERE_HEADING, *words.FROM_HERE_COLUMNS, *words.CHECKPOINT_NAMES.values(), words.TOO_FEW,
              words.total(rate(3, 120, 40.0, 10.0, 90.0, floor=False)),
              *(" OS 083".join(words.twin(verb)) for verb in ("departed", "landed", "is still listed", "has no news yet"))]
    texts += [words.scheduled(d, datetime(2026, 10, 29, 17, 10), DAY) for d in ("D", "A")]
    texts += list(words.STATUS_WORDS.values())
    texts += figure_texts()
    # a day's lines as the page reads them: left column and text, line after line, as one run
    for obs, direction, page_date in [(TO3459_OBS, "D", DAY), *((o, d, p) for o, d, p, _ in CHANGE_CASES)]:
        texts.append(" ".join(f"{left} {text}" for left, text in words.change_lines(obs, direction, page_date, 1,
                                                                                    RESUMES)))
    return [t for t in texts if t is not None]


def test_no_text_trips_the_upload_check():
    """These texts go on every kind of page; a banned phrase in one would stop every upload. Lower-cased
    substrings, as timeline.check matches them."""
    texts = site_texts()
    assert len(texts) > 60  # the cases above, not an empty list
    phrases = (*check.BANNED, "minutes late", "hours late")
    assert [(t, p) for t in texts for p in phrases if p in t.lower()] == []


@pytest.mark.parametrize("name, possessive", [
    ("British Airways", "British Airways' history"), ("Smartwings", "Smartwings' history"),
    ("Lufthansa", "Lufthansa's history"), ("SAS", "SAS's history"), ("El Al", "El Al's history")])
def test_a_name_ending_in_a_lowercase_s_takes_a_bare_apostrophe(name, possessive):
    assert possessive in words.worked_out(LO155, LOT, name, True, True).text
    assert words.partner("LY 9255", "LO 155", name).endswith(f"worked out from {possessive}.")
    assert words.worked_out(LO155, LOT, name, True, True, lambda s: s.replace("'", "’"),
                            lambda s: f"<{s}>").text.count(f"<{name}>" + possessive.removeprefix(name).replace("'", "’")) == 1
