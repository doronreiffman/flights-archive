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
    assert words.MORE_THAN_3_DAYS == "More than 3 days to go: the airport's list does not show the flight yet."
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


def test_also_sold_as_and_the_twin_lines_words():
    """docs/flight-lookup.md, "Flight page: other situations": the words before and after the linked numbers."""
    assert (words.ALSO_SOLD, words.SAME_PLANE) == ("Also sold as", "(probably the same plane).")
    assert words.twin("departed") == ("This number was cancelled, but the flight probably left as", ".")
    assert words.twin("landed") == ("This number was cancelled, but the flight probably landed as", ".")
    assert words.twin("is still listed") == (
        "This number is marked cancelled, but the flight is probably still on, as", ".")
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
              words.late_line(FakeSummary()), words.PAST_ONLY, words.A_FLIGHT, words.ALSO_SOLD, words.SAME_PLANE,
              words.FROM_HERE_FIRST, *words.UNDER_TABLE, *words.LEAD_INS.values(),
              words.condition(datetime(2026, 11, 12, 10, 16, 45)), words.has_passed(datetime(2026, 11, 12, 10, 16, 45)),
              words.FROM_HERE_HEADING, *words.FROM_HERE_COLUMNS, *words.CHECKPOINT_NAMES.values(), words.TOO_FEW,
              words.total(rate(3, 120, 40.0, 10.0, 90.0, floor=False)),
              *(" OS 083".join(words.twin(verb)) for verb in ("departed", "landed", "is still listed"))]
    texts += [words.scheduled(d, datetime(2026, 10, 29, 17, 10), DAY) for d in ("D", "A")]
    texts += list(words.STATUS_WORDS.values())
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
