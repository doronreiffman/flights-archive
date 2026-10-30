"""Every sentence, label and time helper of the redesigned site (docs/site-redesign.md, "Words"). Expected values by hand."""
import time
from datetime import date, datetime, timedelta

import pytest

from timeline import words

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
    assert words.UNOFFICIAL == ("Unofficial; not affiliated with or endorsed by the Israel Airports Authority, "
                                "data.gov.il or the State of Israel.")
    assert words.SOURCE_SHORT == "Flight data: Israel Airports Authority, published on data.gov.il."
    assert words.TIMES_NOTE == "Times are Israel time."
    assert words.PLACEHOLDER == "[owner's wording]"
    assert words.BUILT_BY == words.PLACEHOLDER
    assert words.CODE_URL == "https://github.com/doronreiffman/flights-archive"
    assert words.DELAY_SENTENCE == (
        "Expected times are the airport's own. This site doesn't turn them into minutes late, "
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


@pytest.mark.parametrize("outcome, last_seen_at, note", [
    ("gap", SCHED - timedelta(hours=9), "No records for the time it left the airport's list."),
    ("vanished", SCHED - timedelta(hours=6, minutes=20),
     "Removed from the airport's list 6 hours before it was scheduled, with no final status. "
     "Not necessarily cancelled; it may have moved to another time."),
    ("vanished", SCHED - timedelta(hours=1, minutes=5),
     "Removed from the airport's list 1 hour before it was scheduled, with no final status. "
     "Not necessarily cancelled; it may have moved to another time."),
    ("dropped", SCHED - timedelta(minutes=20), "Removed from the airport's list with no final status."),
    ("departed", SCHED, None), ("landed", SCHED, None), ("canceled", SCHED, None), ("open", SCHED, None),
])
def test_label_note(outcome, last_seen_at, note):
    assert words.label_note({"outcome": outcome, "sched_utc_final": SCHED, "last_seen_at": last_seen_at}) == note


@pytest.mark.parametrize("uncanceled, label, line", [
    (True, "LANDED", "Shown as cancelled for a while, then changed back."),
    (True, "CANCELLED", "Cancelled, changed back, then cancelled again."),
    (None, "CANCELLED", None),  # NULL: already cancelled at the earliest record, never shown otherwise
    (False, "LANDED", None),
])
def test_changed_back(uncanceled, label, line):
    assert words.changed_back({"uncanceled": uncanceled}, label) == line


def test_scheduled():
    assert words.scheduled("D", datetime(2026, 10, 29, 17, 10), DAY) == "scheduled to leave 17:10"
    assert words.scheduled("A", datetime(2026, 10, 29, 13, 50), DAY) == "scheduled to land 13:50"
    assert words.scheduled("D", datetime(2026, 10, 29, 17, 10), date(2026, 10, 30)) == "scheduled to leave 29 Oct 17:10"


@pytest.mark.parametrize("est, sched, text", [
    (datetime(2026, 10, 29, 17, 9), datetime(2026, 10, 29, 16, 45), "last expected 17:09"),
    (datetime(2026, 10, 29, 16, 45), datetime(2026, 10, 29, 16, 45), None),
    (None, datetime(2026, 10, 29, 16, 45), None),
    (datetime(2026, 10, 29, 17, 9), None, None),
])
def test_last_expected(est, sched, text):
    assert words.last_expected({"est_local_final": est, "sched_local_final": sched}, DAY) == text


# --- warning ---------------------------------------------------------------------------------------

def cancelled(lo, hi, censored, direction="D", outcome="canceled"):
    return {"outcome": outcome, "direction": direction, "cancel_lead_min": lo, "cancel_lead_max_min": hi,
            "cancel_lead_censored": censored}


@pytest.mark.parametrize("lo, hi, censored, direction, text", [
    (1400.95, None, True, "A", "at least 23 hours"),            # rule 1, IZ 992
    (60.0, None, True, "D", "at least 1 hour"),                  # rule 1 boundary
    (59.9, None, True, "D", "unknown"),                          # rule 2
    (-59.05, None, True, "D", "unknown"),                        # rule 2, ASY 991
    (-50.0, -10.0, False, "D", "none: cancelled less than an hour after it was scheduled to leave"),
    (-70.0, -30.0, False, "D", "none: cancelled about an hour after it was scheduled to leave"),
    (-142.75, -126.75, False, "D", "none: cancelled about 2 hours after it was scheduled to leave"),  # TO 3459
    (-142.75, -126.75, False, "A", "none: cancelled about 2 hours after it was scheduled to land"),
    (-200.0, -100.0, True, "D", "none: cancelled after it was scheduled to leave"),                  # rule 4
    (75.95, 2600.48, True, "D", "between 1 and 44 hours"),       # rule 5, LY 5409
    (445.95, 2970.48, True, "A", "between 7 and 50 hours"),      # rule 5, LY 5410
    (0.0, 2000.0, True, "D", "up to 34 hours"),                  # rule 6, boundary 0
    (-64.05, 2460.48, True, "D", "unknown: no records for that time"),  # rule 7, BZ 254
    (400.0, 416.0, False, "D", "at least 6 hours"),              # rule 8
    (0.0, 59.0, False, "D", "less than an hour"),                # rule 9, boundary 0
    (45.0, 74.0, False, "D", "about an hour"),                   # rule 10
    (59.9, 60.0, False, "D", "about an hour"),                   # rule 10, boundary 60
    (-10.0, 6.0, False, "D", "around the scheduled time"),       # rule 11
    (-10.0, 0.0, False, "D", "around the scheduled time"),       # rule 11, hi exactly 0
])
def test_warning_rules(lo, hi, censored, direction, text):
    assert words.warning(cancelled(lo, hi, censored, direction)) == text


def test_no_warning_unless_cancelled():
    assert words.warning(cancelled(400.0, 416.0, False, outcome="departed")) is None
    assert words.warning_note(cancelled(1400.95, None, True, outcome="departed")) is None


EARLIEST = "It was already cancelled at the earliest record."
PART = "No records for part of that time."


@pytest.mark.parametrize("lo, hi, censored, note", [
    (1400.95, None, True, EARLIEST),     # rule 1
    (59.9, None, True, EARLIEST),        # rule 2
    (-142.75, -126.75, False, None),     # rule 3
    (-200.0, -100.0, True, PART),        # rule 4
    (75.95, 2600.48, True, PART),        # rule 5
    (0.0, 2000.0, True, PART),           # rule 6
    (-64.05, 2460.48, True, PART),       # rule 7
    (400.0, 416.0, False, None),         # rule 8
    (0.0, 59.0, False, None),            # rule 9
    (45.0, 74.0, False, None),           # rule 10
    (-10.0, 6.0, False, None),           # rule 11
])
def test_warning_note(lo, hi, censored, note):
    assert words.warning_note(cancelled(lo, hi, censored)) == note


@pytest.mark.parametrize("text, sentence", [
    ("none: cancelled about 2 hours after it was scheduled to leave",
     "No warning: cancelled about 2 hours after it was scheduled to leave."),
    ("unknown: no records for that time", "Warning unknown: no records for that time."),
    ("unknown", "Warning unknown."),
    ("at least 23 hours", "Warning: at least 23 hours."),
])
def test_warning_sentence(text, sentence):
    assert words.warning_sentence(text) == sentence


# --- headline --------------------------------------------------------------------------------------

@pytest.mark.parametrize("cancelled_n, known, n", [
    (20, 951, 50),
    (1, 22, 20),
    (2, 45, 25),   # 22.5: halves up to the next multiple of 5
    (1, 19, 19),
    (2, 25, 13),   # 12.5: halves up
    (0, 10, None),
])
def test_one_in(cancelled_n, known, n):
    assert words.one_in(cancelled_n, known) == n


def test_headline():
    assert words.headline(20, 951) == ("So far, 20 of 951 flights with a known outcome were listed as cancelled. "
                                       "That's about 1 in 50.")
    assert words.headline(0, 951) is None
