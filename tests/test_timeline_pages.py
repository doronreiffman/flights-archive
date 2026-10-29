"""The timeline's pure pieces (docs/timeline.md): times, sentences, anchors, search keys. Expected values by hand."""
import os
import time
from datetime import date, datetime

import pytest

from timeline import pages

DAY = date(2026, 10, 29)


@pytest.fixture
def israeli_machine(monkeypatch):
    """Run as on the owner's Mac: a naive astimezone() would then read UTC values as Israel time."""
    monkeypatch.setenv("TZ", "Asia/Jerusalem")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_utc_values_become_israel_time_whatever_the_machine_zone(israeli_machine):
    assert pages.il_time(datetime(2026, 10, 27, 18, 4, 46)).strftime("%Y-%m-%d %H:%M") == "2026-10-27 20:04"


def test_israel_time_across_the_october_clock_change(israeli_machine):
    before, after = pages.il_time(datetime(2026, 10, 24, 22, 30)), pages.il_time(datetime(2026, 10, 24, 23, 30))
    assert (before.strftime("%d %H:%M"), after.strftime("%d %H:%M")) == ("25 01:30", "25 01:30")
    assert (before.utcoffset().seconds // 3600, after.utcoffset().seconds // 3600) == (3, 2)


def test_times_carry_their_date_only_when_it_is_not_the_page_date():
    assert pages.fmt(datetime(2026, 10, 29, 14, 46), DAY) == "14:46"
    assert pages.fmt(datetime(2026, 10, 28, 23, 30), DAY) == "28 Oct 23:30"
    assert pages.fmt(None, DAY) == "none"


@pytest.mark.parametrize("airline, number, city, airport, keys", [
    ("LY", "001", "NEW YORK", "JFK", "ly001 ly1 001 1 newyork jfk"),
    ("6H", "0115A", "EILAT", "ETM", "6h0115a 6h115a 0115a 115a eilat etm"),
    ("LY", "0", "X", "Y", "ly0 0 x y"),
    ("ENT", "7350", "WARSAW", "WAW", "ent7350 7350 warsaw waw"),
])
def test_search_keys(airline, number, city, airport, keys):
    assert pages.search_keys(airline, number, city, airport) == keys


def test_anchor_is_built_from_what_never_changes():
    assert pages.anchor("LY", "5115", "D", datetime(2026, 10, 28, 16, 30), "KUT") == "LY5115-D-20261028-1630-KUT"
    assert pages.anchor("6H", "0115A", "A", datetime(2026, 10, 28, 7, 5), "E T<M") == "6H0115A-A-20261028-0705-ETM"


def flight(**kw):
    base = {"outcome": "departed", "last_seen_at": datetime(2026, 10, 29, 13, 2, 45),
            "sched_utc_final": datetime(2026, 10, 29, 20, 0), "canceled_first_seen_at": None,
            "cancel_announced_after": None, "cancel_lead_min": None, "cancel_lead_max_min": None, "canceled_at_first_sight": None,
            "cancel_lead_censored": None, "uncanceled": False}
    return base | kw


CANCELED = dict(outcome="canceled", canceled_first_seen_at=datetime(2026, 10, 29, 13, 2, 45),
                cancel_announced_after=datetime(2026, 10, 29, 12, 46, 45), canceled_at_first_sight=False,
                cancel_lead_censored=False, cancel_lead_min=400.0, cancel_lead_max_min=416.0)


@pytest.mark.parametrize("kw, sentence", [
    (CANCELED, "First observed CANCELED on the public board between 14:46 and 15:02, at least 6 h before its scheduled time."),
    (CANCELED | {"cancel_lead_min": 45.0, "cancel_lead_max_min": 59.0}, "First observed CANCELED on the public board between 14:46 and 15:02, less than an hour before its scheduled time."),
    (CANCELED | {"cancel_lead_min": 45.0, "cancel_lead_max_min": 74.0}, "First observed CANCELED on the public board between 14:46 and 15:02, before its scheduled time."),
    (CANCELED | {"cancel_lead_min": -30.0, "cancel_lead_max_min": -1.0}, "First observed CANCELED on the public board between 14:46 and 15:02, after its scheduled time."),
    (CANCELED | {"cancel_lead_min": -10.0, "cancel_lead_max_min": 6.0}, "First observed CANCELED on the public board between 14:46 and 15:02, around its scheduled time."),
    (CANCELED | {"canceled_first_seen_at": datetime(2026, 10, 29, 12, 29, 3), "cancel_announced_after": datetime(2026, 10, 27, 18, 4, 46),
                 "cancel_lead_censored": True},
     "First observed CANCELED on the public board at 14:29; we had not seen this flight since 27 Oct 20:04, so the change happened somewhere in between."),
    (CANCELED | {"canceled_first_seen_at": datetime(2026, 10, 29, 12, 29, 3), "cancel_announced_after": None,
                 "canceled_at_first_sight": True, "cancel_lead_censored": True, "uncanceled": None},
     "Already CANCELED the first time we saw it (14:29)."),
    (CANCELED | {"outcome": "departed", "uncanceled": True},
     "First observed CANCELED on the public board between 14:46 and 15:02, at least 6 h before its scheduled time. Later shown with another status."),
])
def test_cancellation_sentences(kw, sentence):
    assert pages.cancellation_sentence(flight(**kw), DAY) == sentence


def test_no_cancellation_sentence_without_a_canceled_sighting():
    assert pages.cancellation_sentence(flight(), DAY) is None


@pytest.mark.parametrize("outcome, sentence", [
    ("departed", "Board showed DEPARTED (last seen 15:02)."),
    ("landed", "Board showed LANDED (last seen 15:02)."),
    ("open", "Still on the board when we last stored it (15:02)."),
    ("gap", "Left the board while no new board was stored for over an hour (our collection paused, or the board stopped changing); what happened is unknown."),
    ("vanished", "Left the board 6 h before its scheduled time without a final status; not necessarily cancelled, it may have been retimed."),
    ("dropped", "Left the board without a final status; last seen 15:02, within an hour of its scheduled time or later."),
    ("canceled", None),
])
def test_outcome_sentences(outcome, sentence):
    assert pages.outcome_sentence(flight(outcome=outcome), DAY) == sentence


def test_an_outcome_the_wording_does_not_know_stops_the_build():
    with pytest.raises(ValueError, match="unknown outcome"):
        pages.outcome_sentence(flight(outcome="teleported"), DAY)


def test_a_flight_cancelled_again_says_so():
    f = flight(**CANCELED | {"uncanceled": True})
    assert pages.outcome_sentence(f, DAY) == "Board showed CANCELED again (last seen 15:02)."
    assert pages.outcome_sentence(flight(**CANCELED), DAY) is None
