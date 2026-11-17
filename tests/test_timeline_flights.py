"""Display rows, flights, counts, addresses and search entries (docs/site-redesign.md: "Labels", "Names", "Pages",
"How it is built"; docs/flight-lookup.md: "Who is a flight", "Labels", "Warning" and "Codeshares" in "What it changes",
and "Day pages, the chart, the cancellation lists"). Expected values by hand."""
from datetime import date, datetime, timedelta

import pytest

from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import flights, words
from timeline.flights import DayInfo, Row

LAST_FETCH = datetime(2026, 10, 29, 22, 2, 45)  # 00:02 Israel time on 30 October
EL_AL = "EL AL  ISRAEL AIRLINES"  # the double space as the airport publishes it


def local(day, h, m):
    """An airport time (Israel wall-clock, as published) in October 2026."""
    return datetime(2026, 10, day, h, m)


def utc(day, h, m, s=0):
    """A model time (naive UTC) in October 2026; Israel is UTC+2 after the 25 October clock change."""
    return datetime(2026, 10, day, h, m, s)


FIRST_RECORD = utc(27, 18, 4, 46)  # the earliest record's time
RESUMES = frozenset({FIRST_RECORD})  # the records' first list, as build.render passes it: "Already on the list"


def flight(fid, sched=local(29, 16, 45), *, airline="LY", flight_no="001", direction="D", airport="JFK",
           city_en="NEW YORK", city_he="ניו יורק", outcome="departed", group=None, **kw):
    """A row of the model's flights table with the columns flights, words and the counting rule read; `kw` sets any
    other. At its last listing (rule C1's reading) it showed its last expected time at terminal 3 with no desks, and
    it was first seen at the earliest record; one that ended listed as cancelled was first listed so there too."""
    f = {"flight_id": fid, "airline": airline, "flight_no": flight_no, "airline_name": EL_AL,
         "direction": direction, "airport": airport, "city_en": city_en, "city_he": city_he,
         "sched_local_first": sched, "sched_local_final": sched, "sched_utc_final": sched - timedelta(hours=2),
         "est_local_final": sched, "outcome": outcome, "last_seen_at": sched - timedelta(hours=3),
         "cancel_lead_min": None, "cancel_lead_max_min": None, "cancel_lead_censored": None,
         "uncanceled": False, "codeshare_group_id": group or fid} | kw
    est = f["est_local_final"]
    late = None if est is None else (est - f["sched_local_final"]).total_seconds() / 60
    return {"est_minus_sched_min": late, "est_utc_final": None if est is None else est - timedelta(hours=2), "terminal_final": 3,
            "counters_final": "", "first_seen_at": FIRST_RECORD,
            "canceled_first_seen_at": FIRST_RECORD if f["outcome"] == "canceled" else None} | f


def first(f, observed_at=FIRST_RECORD):
    """The flight's earliest record, as the model's observations table has it."""
    return {"flight_id": f["flight_id"], "snap_rn": 1, "observed_at": observed_at, "prev_observed_at": None,
            "change_kind": "first", "changed_fields": [], "sched_local": f["sched_local_first"],
            "est_local": f["sched_local_first"], "status": "ON TIME", "terminal": 3, "counters": "", "zone": ""}


def then(prev, observed_at, kind="change", **new):
    """The flight's next record, 16 minutes after its previous appearance: the previous values with `new` changed."""
    return prev | new | {"snap_rn": prev["snap_rn"] + 1, "observed_at": observed_at,
                         "prev_observed_at": observed_at - timedelta(minutes=16), "change_kind": kind,
                         "changed_fields": list(new)}


def rows(*fs, obs=None, last_fetch=LAST_FETCH, resumes=RESUMES):
    """Display rows for these flights; each has only its earliest record unless `obs` is given."""
    return flights.make_rows(list(fs), [first(f) for f in fs] if obs is None else obs, last_fetch, 1, resumes)


def lists(*fs, obs=None, last_fetch=LAST_FETCH):
    """The lists' flights (rule C1) of these numbers."""
    return flights.group_flights(rows(*fs, obs=obs, last_fetch=last_fetch), list(fs), last_fetch)


def ids(flights_):
    return [[r.flight_id for r in fl.rows] for fl in flights_]


CLEAN = dict(outcome="canceled", cancel_lead_min=400.0, cancel_lead_max_min=416.0, cancel_lead_censored=False)
CENSORED = dict(outcome="canceled", cancel_lead_min=75.95, cancel_lead_max_min=2600.48, cancel_lead_censored=True)


def censored_map(fs):
    return {f["flight_id"]: f["cancel_lead_censored"] for f in fs}


LH = dict(airline="LH", airport="FRA", city_en="FRANKFURT", city_he="פרנקפורט")
OS = dict(airline="OS", direction="A", airport="VIE", city_en="VIENNA", city_he="וינה")


def lh(fid, sched, flight_no, outcome="departed", **kw):
    """An LH departure to Frankfurt: LH 0691A beside LH 695 (docs/flight-lookup.md, C2 and "Words")."""
    state = CLEAN if outcome == "canceled" else {"outcome": outcome}
    return flight(fid, sched, flight_no=flight_no, **LH, **state | kw)


def os_pair():
    """OS 083, which landed at 14:00 on 29 October (its last expected time ten minutes early), and OS 1083 of the
    same airline, listed as cancelled with the scheduled time as its last expected one (docs/flight-lookup.md, C1)."""
    sched = local(29, 14, 0)
    return [flight("os083", sched, flight_no="083", outcome="landed", est_local_final=sched - timedelta(minutes=10),
                   **OS),
            flight("os1083", sched, flight_no="1083", **OS, **CLEAN)]


def ey_ly():
    """EY 607 and LY 9614, one cancelled flight at 09:00 on 29 October: EY 607 listed as cancelled 400 minutes before
    its time (at least 6 hours), LY 9614 already 1,400 minutes before (at least 23 hours)."""
    sched = local(29, 9, 0)
    utc_ = sched - timedelta(hours=2)
    return [flight("ey", sched, airline="EY", flight_no="607", **CLEAN,
                   canceled_first_seen_at=utc_ - timedelta(minutes=400)),
            flight("ly", sched, airline="LY", flight_no="9614",
                   **CLEAN | {"cancel_lead_min": 1400.0, "cancel_lead_max_min": 1416.0},
                   canceled_first_seen_at=utc_ - timedelta(minutes=1400))]


# --- addresses and anchors -------------------------------------------------------------------------

def test_row_anchor_from_the_first_scheduled_time_and_the_airport():
    assert flights.row_anchor(datetime(2026, 10, 28, 16, 30), "KUT") == "2026-10-28-1630-KUT"
    assert flights.row_anchor(datetime(2026, 10, 28, 16, 30), "K'T <") == "2026-10-28-1630-KT"


@pytest.mark.parametrize("airline, flight_no, direction, address", [
    ("LY", "5115", "D", "flight/LY5115-D.html"),
    ("6H", "0115A", "A", "flight/6H0115A-A.html"),
    ("A B", "1/2", "D", "flight/AB12-D.html"),  # letters, digits and hyphen only
    ("LY", "001א", "D", "flight/LY001-D.html"),  # ASCII letters only
])
def test_page_address(airline, flight_no, direction, address):
    assert flights.page_address(airline, flight_no, direction) == address


def test_two_numbers_on_one_file_stop_the_build():
    with pytest.raises(ValueError, match="same page"):
        flights.check_unique(rows(flight("a", airline="AB", flight_no="12"), flight("b", airline="A", flight_no="B12")))


def test_two_numbers_differing_only_in_case_stop_the_build():
    """A disk that ignores case (the owner's Mac) would write both pages to one file."""
    with pytest.raises(ValueError, match="same page"):
        flights.check_unique(rows(flight("a", airline="LY"), flight("b", airline="ly")))


def test_two_rows_of_one_number_on_one_anchor_stop_the_build():
    with pytest.raises(ValueError, match="same anchor"):
        flights.check_unique(rows(flight("a"), flight("b")))  # same number, first time and airport


def test_one_number_twice_at_one_time_to_two_airports_passes():
    """LY 5115 left twice at 16:30 on 28 October, to Kutaisi and Batumi: two anchors on one page. Another number
    at that time and airport (a codeshare partner) has the same anchor string on its own page, which is fine."""
    fs = [flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT"),
          flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS"),
          flight("partner", local(28, 16, 30), airline="A9", flight_no="5115", airport="KUT"),
          flight("back", local(28, 16, 30), flight_no="5115", direction="A", airport="KUT")]
    assert flights.check_unique(rows(*fs)) is None


# --- display rows ----------------------------------------------------------------------------------

def test_a_row_ready_to_show():
    f = flight("f1", est_local_final=local(29, 17, 9), group="g1")
    assert rows(f) == [Row(
        flight_id="f1", airline="LY", flight_no="001", airline_name=EL_AL, direction="D", airport="JFK",
        city="New York", city_he="ניו יורק", day=date(2026, 10, 29), sched_first=local(29, 16, 45),
        sched_final=local(29, 16, 45), sched_utc_final=utc(29, 14, 45), label="DEPARTED", delayed=False,
        notice=None, label_note=None, changed_back=None, est_final=local(29, 17, 9), last_seen_at=utc(29, 13, 45),
        page="flight/LY001-D.html", anchor="2026-10-29-1645-JFK", group_id="g1",
        lines=(("Already on the list on 27 Oct at 20:04", "on time, terminal 3"),))]


def test_a_rows_first_line_reads_the_resumes(israeli_machine):
    """make_rows hands its `resumes` to the change lines: a first record at one of them is "Already on the list"; one
    at another time is "First on the list"."""
    a, b = flight("a"), flight("b", flight_no="002")
    got = rows(a, b, obs=[first(a), first(b, observed_at=utc(28, 7, 2, 45))])
    assert [r.lines[0][0] for r in got] == ["Already on the list on 27 Oct at 20:04",
                                            "First on the list on 28 Oct at 09:02"]
    assert rows(a, resumes=frozenset())[0].lines[0][0] == "First on the list on 27 Oct at 20:04"


def test_the_day_ahead_sentence_is_decided_in_utc(israeli_machine):
    """A flight removed early, scheduled at 23:55 on 29 October in Israel (21:55 UTC). With the last update at 22:00
    UTC, 00:00 on 30 October in Israel, its time has passed: its line has no "Check with your airline.". With the last
    update at 21:50 UTC it is still ahead and has it. On Israel wall-clock, 23:55 would be ahead of both."""
    f = flight("v", local(29, 23, 55), outcome="vanished", last_seen_at=utc(29, 19, 55))
    note = ("The airport removed this flight 2 hours early without saying why. It may have been cancelled or moved to "
            "another time.")
    assert rows(f, last_fetch=utc(29, 22, 0))[0].label_note == note
    assert rows(f, last_fetch=utc(29, 21, 50))[0].label_note == f"{note} Check with your airline."


def test_delayed_on_a_day_with_no_final_word():
    """docs/flight-lookup.md, "The label DELAYED by the hour rule": the label is drawn from the airport's last expected
    time on a day still ahead too. An UPCOMING row and a NO NEWS YET row, each expected an hour or more late, show
    DELAYED."""
    upcoming = flight("u", local(30, 10, 0), outcome="open", est_local_final=local(30, 11, 0))
    no_news = flight("n", local(29, 20, 0), outcome="open", est_local_final=local(29, 21, 5))
    assert [(r.label, r.delayed) for r in rows(upcoming, no_news)] == [("UPCOMING", True), ("NO NEWS YET", True)]
    assert [(fl.label, fl.delayed) for fl in lists(upcoming, no_news)] == [("UPCOMING", True), ("NO NEWS YET", True)]


def test_a_retimed_row_is_on_the_day_of_its_final_time_with_the_anchor_of_its_first():
    """Its records reach the change lines in model order (snap_rn) whatever order they arrive in, beside another
    flight's, and its lines are written for the day of its final scheduled time."""
    f = flight("f1", local(29, 0, 30), sched_local_first=local(28, 23, 30))
    start = first(f)
    moved = then(start, utc(28, 20, 32, 45), kind="retime", sched_local=local(29, 0, 30), est_local=local(29, 0, 30))
    row = rows(f, obs=[moved, first(flight("other")), start])[0]
    assert (row.day, row.anchor) == (date(2026, 10, 29), "2026-10-28-2330-JFK")
    assert row.lines == (("Already on the list on 27 Oct at 20:04", "on time, terminal 3"),
                         ("28 Oct 22:32", "Moved to a new scheduled time: 28 Oct 23:30 → 00:30"))


def test_delayed_at_59_and_at_60_minutes():
    """The hour rule on the airport's last expected time, a row at a time: 59 minutes is not delayed, 60 is, and the
    next day's flight of the same number is not."""
    on_time = flight("a", local(29, 16, 45), est_local_final=local(29, 17, 44))
    hour = flight("b", local(29, 18, 45), est_local_final=local(29, 19, 45))
    tomorrow = flight("c", local(30, 16, 45), outcome="open")
    assert [(r.label, r.delayed) for r in rows(on_time, hour, tomorrow)] == [
        ("DEPARTED", False), ("DEPARTED", True), ("UPCOMING", False)]


def test_no_expected_time_is_not_delayed():
    f = flight("a", est_local_final=None)
    assert f["est_minus_sched_min"] is None
    assert not rows(f)[0].delayed


def test_the_airports_word_delayed_no_longer_labels():
    """An observation with status DELAYED and an expected time 20 minutes late gives no DELAYED."""
    f = flight("a", est_local_final=local(29, 17, 5))
    start = first(f)
    late = then(start, utc(29, 13, 2, 45), status="DELAYED", est_local=local(29, 17, 5))
    got = rows(f, obs=[start, late])[0]
    assert (got.label, got.delayed) == ("DEPARTED", False)


def test_delayed_never_beside_cancelled_or_unknown():
    """A cancelled or unknown flight keeps an expected time more than an hour late and is still not DELAYED."""
    cancelled = flight("c", local(29, 10, 0), **CLEAN, est_local_final=local(29, 11, 30))
    gone = flight("v", local(29, 12, 0), outcome="vanished", est_local_final=local(29, 13, 30))
    flew = flight("d", local(29, 14, 0), est_local_final=local(29, 15, 30))
    got = rows(cancelled, gone, flew)
    assert [(r.label, r.delayed) for r in got] == [("CANCELLED", False), ("UNKNOWN", False), ("DEPARTED", True)]
    assert [(fl.label, fl.delayed) for fl in lists(cancelled, gone, flew)] == [
        ("CANCELLED", False), ("UNKNOWN", False), ("DEPARTED", True)]


def test_a_list_flight_is_delayed_when_any_number_is():
    """LH 695 an hour late beside LH 0691A, listed as cancelled: the departed flight is DELAYED; it is not when no
    number is; and a second number that is delayed is enough, though the first is the cancelled one."""
    late = lh("lh695", local(29, 9, 0), "695", est_local_final=local(29, 10, 0))
    gone = lh("lh0691a", local(29, 9, 0), "0691A", "canceled")
    on_time = lh("lh697", local(30, 9, 0), "697")
    on_time_b = lh("lh0699a", local(30, 9, 0), "0699A", "canceled")
    third = lh("lh0701a", local(31, 9, 0), "0701A", "canceled")
    third_late = lh("lh701", local(31, 9, 0), "701", est_local_final=local(31, 10, 0))
    got = lists(late, gone, on_time, on_time_b, third, third_late)
    assert [(ids([fl])[0], fl.label, fl.delayed) for fl in got] == [
        (["lh695", "lh0691a"], "DEPARTED", True), (["lh697", "lh0699a"], "DEPARTED", False),
        (["lh0701a", "lh701"], "DEPARTED", True)]


def test_label_notice_and_notes_come_from_words():
    gone = flight("v", outcome="vanished", last_seen_at=utc(27, 15, 25))  # 47 h 20 min before 14:45 UTC on 29 Oct
    ahead = flight("w", local(31, 9, 0), outcome="vanished", last_seen_at=utc(29, 21, 0))
    cancelled = flight("c", **CENSORED | {"cancel_lead_min": 1400.95, "cancel_lead_max_min": None, "uncanceled": None})
    back = flight("b", direction="A", outcome="landed", uncanceled=True)
    got = [(r.label, r.notice, r.label_note, r.changed_back) for r in rows(gone, ahead, cancelled, back)]
    early = ("The airport removed this flight {} hours early without saying why. "
             "It may have been cancelled or moved to another time.")
    assert got == [
        ("UNKNOWN", None, early.format(47), None),
        ("UNKNOWN", None, early.format(34) + " Check with your airline.", None),  # still ahead of the last record
        ("CANCELLED", words.Notice("Cancelled with at least 23 hours' notice. It was already cancelled when it "
                                   "first appeared.", "23+ hours"), None, None),
        ("LANDED", None, None, "Marked cancelled for a while, then back on."),
    ]


def test_a_row_keeps_the_airports_last_expected_time_and_last_record():
    f = flight("a", est_local_final=local(29, 17, 9), last_seen_at=utc(29, 12, 0))
    r = rows(f)[0]
    assert (r.est_final, r.last_seen_at) == (local(29, 17, 9), utc(29, 12, 0))


def test_no_news_yet_decided_in_utc(israeli_machine):
    """23:55 Israel time is 21:55 UTC, before the 22:02 UTC last record: no news yet. Deciding with the
    Israel wall-clock value would call it UPCOMING."""
    f = flight("late", local(29, 23, 55), outcome="open")
    assert (f["sched_local_final"], f["sched_utc_final"]) == (local(29, 23, 55), utc(29, 21, 55))
    got = flights.make_rows([f], [first(f)], LAST_FETCH, 1, RESUMES)[0]
    assert (got.label, got.label_note) == ("NO NEWS YET", "Its time has passed, and the airport hasn't said how it ended.")


# --- flights ---------------------------------------------------------------------------------------

def test_lists_group_by_c1():
    """A list's flights are rule C1's (counting.flights), in the order of each flight's first row, its numbers in row
    order: OS 1083, listed as cancelled, joins OS 083 of its own airline though their codeshare groups differ; IZ 991,
    listed as cancelled at other desks, stays apart from LY 003, DL 7426 and AM 7895, which departed (A11)."""
    desks = dict(counters_final="78-99", group="g")
    os083, os1083 = os_pair()
    fs = [flight("ly003", local(29, 9, 0), flight_no="003", **desks),
          flight("iz991", local(29, 9, 0), airline="IZ", flight_no="991", counters_final="34-41", **CLEAN),
          os083,
          flight("dl", local(29, 9, 0), airline="DL", flight_no="7426", **desks),
          os1083,
          flight("am", local(29, 9, 0), airline="AM", flight_no="7895", **desks)]
    assert ids(lists(*fs)) == [["ly003", "dl", "am"], ["iz991"], ["os083", "os1083"]]
    assert [fl.day for fl in lists(*fs)] == [date(2026, 10, 29)] * 3


def test_codeshare_members_with_one_label_are_one_flight():
    a = flight("a", airline="EY", flight_no="607", group="g")
    b = flight("b", airline="LY", flight_no="9614", group="g")
    assert ids(lists(a, b)) == [["a", "b"]]


def test_one_group_id_on_two_days_is_two_flights():
    a, b = flight("a", local(29, 9, 0), group="g"), flight("b", local(30, 9, 0), group="g")  # both DEPARTED
    assert ids(lists(a, b)) == [["a"], ["b"]]


def test_a_list_labels_a_flight_by_c10():
    """LH 0691A, listed as cancelled, with LH 695, which departed, is one flight labelled DEPARTED (C10, rule 1),
    and DELAYED because LH 695 is an hour late; with LH 695 still listed it is UPCOMING (rule 2 before rule 3)."""
    gone = [lh("lh0691a", local(29, 9, 0), "0691A", "canceled"),
            lh("lh695", local(29, 9, 0), "695", est_local_final=local(29, 10, 0))]
    ahead = [lh("lh0691a-31", local(31, 9, 0), "0691A", "canceled"), lh("lh695-31", local(31, 9, 0), "695", "open")]
    assert [(r.label, r.delayed) for r in rows(*gone, *ahead)] == [
        ("CANCELLED", False), ("DEPARTED", True), ("CANCELLED", False), ("UPCOMING", False)]
    assert [(fl.label, fl.delayed) for fl in lists(*gone, *ahead)] == [("DEPARTED", True), ("UPCOMING", False)]


def test_a_cancelled_flights_notice_is_c9s():
    """A cancelled flight leads with its number listed as cancelled first (C9), whose notice the lists show: LY
    9614, though EY 607 comes first in the row. A flight whose result is not cancelled (C2) leads with its first
    row."""
    got = lists(*ey_ly(), lh("lh0691a", local(29, 10, 0), "0691A", "canceled"), lh("lh695", local(29, 10, 0), "695"))
    assert [(ids([fl])[0], fl.label, fl.lead.flight_id, fl.lead.notice.short) for fl in got] == [
        (["ey", "ly"], "CANCELLED", "ly", "23+ hours"),
        (["lh0691a", "lh695"], "DEPARTED", "lh0691a", "6+ hours")]
    assert [r.notice.short for r in got[0].rows] == ["6+ hours", "23+ hours"]


def test_partners_share_time_terminal_and_desks():
    """Only the numbers of a flight that the list showed with the same last expected time, terminal and check-in
    desks are "probably the same flight", whatever each number's own label: OS 1083 joins OS 083's flight by airline
    (C1) but is not its partner; AF 8350, which left the list during a hole (UNKNOWN), is a partner of LY 003, DL 7426
    and AM 7895, which departed."""
    desks = dict(counters_final="78-99", group="g")
    fs = [*os_pair(), flight("ly003", local(29, 9, 0), flight_no="003", **desks),
          flight("dl", local(29, 9, 0), airline="DL", flight_no="7426", **desks),
          flight("am", local(29, 9, 0), airline="AM", flight_no="7895", **desks),
          flight("af", local(29, 9, 0), airline="AF", flight_no="8350", outcome="gap", **desks)]
    lists_ = lists(*fs)
    assert ids(lists_) == [["os083", "os1083"], ["ly003", "dl", "am", "af"]]
    assert [r.label for r in lists_[1].rows] == ["DEPARTED", "DEPARTED", "DEPARTED", "UNKNOWN"]
    got = {fid: [p.flight_id for p in ps] for fid, ps in flights.partners(lists_, fs).items()}
    assert got == {"os083": [], "os1083": [], "ly003": ["dl", "am", "af"], "dl": ["ly003", "am", "af"],
                   "am": ["ly003", "dl", "af"], "af": ["ly003", "dl", "am"]}


def test_partners_read_a_missing_terminal_and_empty_desks_as_equal():
    """As rule C1 reads them (counting._shown): a missing terminal equals a missing one, and no desks equal empty
    desks."""
    fs = [flight("a", airline="EY", flight_no="607", terminal_final=None, counters_final=None),
          flight("b", airline="LY", flight_no="9614", terminal_final=None, counters_final="")]
    got = {fid: [p.flight_id for p in ps] for fid, ps in flights.partners(lists(*fs), fs).items()}
    assert got == {"a": ["b"], "b": ["a"]}


def test_others_name_who_departed_landed_is_still_listed_or_has_no_news_yet():
    """For each number listed as cancelled in a flight that is not (C2, C10): the numbers that departed, landed, are
    still listed ahead of their time (UPCOMING) or have no news yet (NO NEWS YET, Question 6h: the flight may have gone
    ahead), and only those. LH 697, still listed beside LH 695, is not named for the flight that departed. A cancelled
    flight's numbers, and numbers not listed as cancelled, get none."""
    fs = [lh("lh0691a", local(29, 9, 0), "0691A", "canceled"), lh("lh695", local(29, 9, 0), "695"),
          lh("lh697", local(29, 9, 0), "697", "open"),
          *os_pair(),
          lh("lh0691a-31", local(31, 9, 0), "0691A", "canceled"), lh("lh695-31", local(31, 9, 0), "695", "open"),
          lh("lh0691a-late", local(29, 23, 55), "0691A", "canceled"), lh("lh695-late", local(29, 23, 55), "695", "open"),
          *ey_ly()]
    assert [fl.label for fl in lists(*fs)] == ["DEPARTED", "LANDED", "UPCOMING", "NO NEWS YET", "CANCELLED"]
    got = {fid: (verb, [r.flight_id for r in named]) for fid, (verb, named) in flights.others(lists(*fs)).items()}
    assert got == {"lh0691a": ("departed", ["lh695"]), "os1083": ("landed", ["os083"]),
                   "lh0691a-31": ("is still listed", ["lh695-31"]),
                   "lh0691a-late": ("has no news yet", ["lh695-late"])}


# --- counts ----------------------------------------------------------------------------------------

def test_days_count_flights_and_today_is_the_israel_date_of_the_last_record(israeli_machine):
    """22:30 UTC on 29 October is 00:30 Israel time on 30 October: 30 October is today."""
    last = utc(29, 22, 30)
    fs = [flight("ahead", local(31, 10, 0), outcome="open"),
          flight("c1", local(29, 9, 0), airline="EY", flight_no="607", group="g", **CLEAN),
          flight("c2", local(29, 9, 0), airline="LY", flight_no="9614", group="g", **CLEAN),
          flight("unknown", local(29, 11, 0), flight_no="002", outcome="gap"),
          flight("departed", local(29, 16, 45)),
          flight("today", local(30, 10, 0), outcome="open")]
    got = flights.day_infos(lists(*fs, last_fetch=last), last, {date(2026, 10, 29)})
    assert got == [DayInfo(date(2026, 10, 29), total=3, cancelled=1, unknown=1, state="past", partial=True),
                   DayInfo(date(2026, 10, 30), total=1, cancelled=0, unknown=0, state="today", partial=False),
                   DayInfo(date(2026, 10, 31), total=1, cancelled=0, unknown=0, state="ahead", partial=False)]


def test_day_counts_and_the_chart_count_c10_flights(israeli_machine):
    """A day, and the chart that draws its counts, counts flights (C1) by their list label (C10): EY 607 and LY 9614,
    listed as cancelled at one time, terminal and desks, are one cancelled flight, and LH 0691A, listed as cancelled
    inside a flight that departed, adds no cancellation."""
    fs = [*ey_ly(), lh("lh0691a", local(29, 10, 0), "0691A", "canceled"), lh("lh695", local(29, 10, 0), "695"),
          flight("unknown", local(29, 14, 0), outcome="gap")]
    assert flights.day_infos(lists(*fs), LAST_FETCH, set()) == [
        DayInfo(date(2026, 10, 29), total=3, cancelled=1, unknown=1, state="past", partial=False)]


# --- the featured flight and recent cancellations --------------------------------------------------

def test_featured_is_the_most_recent_cancellation_with_a_clean_warning():
    fs = [flight("old", local(28, 9, 0), **CLEAN), flight("new", local(29, 9, 0), **CLEAN),
          flight("newer, censored", local(30, 9, 0), **CENSORED), flight("departed", local(31, 9, 0))]
    assert flights.featured(lists(*fs), censored_map(fs)).flight_id == "new"


def test_without_a_clean_warning_the_cancellation_with_the_most_lines():
    long_, short = flight("long", local(28, 9, 0), **CENSORED), flight("short", local(30, 9, 0), **CENSORED)
    a0 = first(long_)
    a1 = then(a0, utc(27, 20, 2, 45), counters="345-348")
    a2 = then(a1, utc(28, 5, 2, 45), status="CANCELED")
    got = flights.featured(lists(long_, short, obs=[a0, a1, a2, first(short)]), censored_map([long_, short]))
    assert (got.flight_id, len(got.lines)) == ("long", 3)


def test_featured_ties_by_scheduled_time_then_airline_and_number():
    """Flights at one time to different airports (one airport would make them one flight, C1)."""
    fs = [flight("LY 002", local(29, 9, 0), flight_no="002", airport="ATH", **CLEAN),
          flight("IZ 991", local(29, 9, 0), airline="IZ", flight_no="991", airport="BUS", **CLEAN),
          flight("LY 001", local(29, 9, 0), flight_no="001", airport="CDG", **CLEAN)]
    assert flights.featured(lists(*fs), censored_map(fs)).flight_id == "IZ 991"
    gs = [flight("older", local(28, 9, 0), flight_no="001", **CENSORED),
          flight("LY 009", local(29, 9, 0), flight_no="009", airport="ATH", **CENSORED),
          flight("LY 003", local(29, 9, 0), flight_no="003", airport="BUS", **CENSORED)]
    assert flights.featured(lists(*gs), censored_map(gs)).flight_id == "LY 003"  # same number of lines


def test_no_cancellation_no_featured_flight():
    assert flights.featured(lists(flight("departed")), {"departed": None}) is None


def test_the_story_picks_among_c10_cancellations_through_c9():
    """A number listed as cancelled inside a flight that departed is never the story, however recent; a cancelled
    flight's story is told through its number listed as cancelled first (C9), not its first row."""
    inside = [lh("lh0691a", local(30, 9, 0), "0691A", "canceled"), lh("lh695", local(30, 9, 0), "695")]
    assert flights.featured(lists(*inside), censored_map(inside)) is None
    fs = [*ey_ly(), *inside]
    assert flights.featured(lists(*fs), censored_map(fs)).flight_id == "ly"


def test_the_story_skips_a_flight_first_listed_after_its_scheduled_time():
    """docs/site-redesign.md, front page item 6 (the owner's decision, 2026-11-17): WZ 016, scheduled to leave at 05:35
    and first on the list at 09:32, makes no story read aloud; the next cancellation is told instead. A flight first
    listed exactly at its scheduled time is kept. Each list flight carries its first sighting and its slot's time."""
    wz016 = flight("wz016", local(30, 5, 35), airline="WZ", flight_no="016", airport="VKO", city_en="MOSCOW",
                   **CLEAN, first_seen_at=utc(30, 7, 32, 45), canceled_first_seen_at=utc(30, 7, 32, 45))
    older = flight("older", local(29, 9, 0), **CLEAN)
    got = lists(wz016, older)
    assert [(fl.first_seen, fl.sched_utc) for fl in got] == [(utc(30, 7, 32, 45), utc(30, 3, 35)),
                                                              (FIRST_RECORD, utc(29, 7, 0))]
    assert flights.featured(got, censored_map([wz016, older])).flight_id == "older"
    assert flights.featured(lists(wz016), censored_map([wz016])) is None
    # another airport: at WZ 016's airport it would be WZ 016's flight (C1)
    on_time = flight("at its time", local(30, 5, 35), airline="WZ", flight_no="018", airport="DME", city_en="MOSCOW",
                     **CLEAN, first_seen_at=utc(30, 3, 35), canceled_first_seen_at=utc(30, 3, 35))
    fs = [wz016, on_time, older]
    assert flights.featured(lists(*fs), censored_map(fs)).flight_id == "at its time"


def test_recent_cancellations_newest_first_at_most_n():
    fs = [flight(f"c{h}", local(29, h, 0), flight_no=f"{h:03}", **CLEAN) for h in range(8, 20)]  # 12, 08:00 to 19:00
    fs += [flight("IZ 991", local(29, 19, 0), airline="IZ", flight_no="991", airport="ATH", **CLEAN),
           flight("departed", local(29, 21, 0))]  # IZ 991 ties with c19 by time (another airport): IZ first
    flights_ = lists(*fs)
    assert ids(flights.recent_cancellations(flights_)) == [["IZ 991"], ["c19"], ["c18"], ["c17"], ["c16"],
                                                           ["c15"], ["c14"], ["c13"], ["c12"], ["c11"]]
    assert ids(flights.recent_cancellations(flights_, n=2)) == [["IZ 991"], ["c19"]]


def test_cancellation_lists_leave_out_a_flight_with_a_number_listed_as_cancelled():
    """docs/flight-lookup.md, D4: a number listed as cancelled inside a flight that departed, landed or is still listed
    leaves the cancellation lists, which hold flights labelled CANCELLED (C10). LH 0691A beside LH 695, which departed,
    and the same pair two days later with LH 695 still listed, are both newer than EY 607 with LY 9614, the one
    cancelled flight; neither is listed, however many the list may hold."""
    fs = [*ey_ly(), lh("lh0691a", local(29, 20, 0), "0691A", "canceled"), lh("lh695", local(29, 20, 0), "695"),
          lh("lh0691a-31", local(31, 9, 0), "0691A", "canceled"), lh("lh695-31", local(31, 9, 0), "695", "open")]
    flights_ = lists(*fs)
    assert [(ids([fl])[0], fl.label, [r.label for r in fl.rows]) for fl in flights_] == [
        (["ey", "ly"], "CANCELLED", ["CANCELLED", "CANCELLED"]),
        (["lh0691a", "lh695"], "DEPARTED", ["CANCELLED", "DEPARTED"]),
        (["lh0691a-31", "lh695-31"], "UPCOMING", ["CANCELLED", "UPCOMING"])]
    assert ids(flights.recent_cancellations(flights_)) == [["ey", "ly"]]
    assert ids(flights.recent_cancellations(flights_, n=len(flights_))) == [["ey", "ly"]]


# --- search ----------------------------------------------------------------------------------------

def test_number_keys():
    assert flights.number_keys("LY", "001") == ["ly001", "ly1", "001", "1"]
    assert flights.number_keys("IZ", "991") == ["iz991", "991"]
    assert flights.number_keys("6H", "0115A") == ["6h0115a", "6h115a", "0115a", "115a"]


def test_place_keys():
    assert flights.place_keys("New York", "JFK") == ["newyork", "jfk"]


def test_search_entries_one_per_number_and_direction():
    fs = [flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
          flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI"),
          flight("kut again", local(29, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
          flight("back", local(28, 20, 0), flight_no="5116", direction="A", airport="KUT", city_en="KUTAISI"),
          flight("back again", local(29, 20, 0), flight_no="5116", direction="A", airport="BUS", city_en="BATUMI"),
          flight("in", local(29, 5, 0), direction="A"),
          flight("out", local(29, 16, 45)),
          flight("athens", local(29, 9, 0), airline="IZ", flight_no="991", direction="A", airport="ATH",
                 city_en="ATHENS")]
    assert flights.search_entries(rows(*fs)) == [
        {"n": ["iz991", "991"], "p": ["ath", "athens"], "t": "IZ 991 · Athens to Tel Aviv",
         "u": "flight/IZ991-A.html"},
        {"n": ["ly001", "ly1", "001", "1"], "p": ["jfk", "newyork"], "t": "LY 001 · New York to Tel Aviv",
         "u": "flight/LY001-A.html"},
        {"n": ["ly001", "ly1", "001", "1"], "p": ["jfk", "newyork"], "t": "LY 001 · Tel Aviv to New York",
         "u": "flight/LY001-D.html"},
        {"n": ["ly5115", "5115"], "p": ["batumi", "bus", "kut", "kutaisi"],
         "t": "LY 5115 · Tel Aviv to Kutaisi or Batumi",
         "u": "flight/LY5115-D.html"},
        {"n": ["ly5116", "5116"], "p": ["batumi", "bus", "kut", "kutaisi"],
         "t": "LY 5116 · Batumi or Kutaisi to Tel Aviv",
         "u": "flight/LY5116-A.html"},
    ]


def one_a_day(flight_no, *cities, direction="D"):
    """One row of this number a day for each (city, airport), the first city on the newest day (31 October)."""
    return [flight(f"{flight_no}-{i}", local(31 - i, 10, 0), flight_no=flight_no, direction=direction, airport=airport,
                   city_en=city) for i, (city, airport) in enumerate(cities)]


def test_titles():
    """docs/site-redesign.md, "Names": the number, then where it goes, the newest day's city first; two or three
    cities joined with "or", more named two and counted; a city whose name begins another's named once, as the
    shorter, at the place of the newer of the two; one city through two airports is one city. The search entries
    carry the same titles."""
    def title(*fs):
        return flights.page_title(rows(*fs))

    assert title(flight("lo", flight_no="155", airline="LO", direction="A", airport="WAW", city_en="WARSAW")) == (
        "LO 155 · Warsaw to Tel Aviv")
    assert title(flight("wz", flight_no="016", airline="WZ", airport="VKO", city_en="MOSCOW")) == (
        "WZ 016 · Tel Aviv to Moscow")
    assert title(flight("orly", flight_no="002", airport="ORY", city_en="PARIS"),
                 flight("cdg", local(30, 16, 45), flight_no="002", airport="CDG", city_en="PARIS")) == (
        "LY 002 · Tel Aviv to Paris")
    two = one_a_day("697", ("ATHENS", "ATH"), ("FRANKFURT", "FRA"), ("ATHENS", "ATH"))
    assert title(*two) == "LY 697 · Tel Aviv to Athens or Frankfurt"
    assert title(*reversed(two)) == "LY 697 · Tel Aviv to Athens or Frankfurt"  # by date, not by row order
    arrival = one_a_day("682", ("MUNICH", "MUC"), ("FRANKFURT", "FRA"), direction="A")
    assert title(*arrival) == "LY 682 · Munich or Frankfurt to Tel Aviv"
    three = one_a_day("699", ("ATHENS", "ATH"), ("LARNACA", "LCA"), ("MUNICH", "MUC"))
    assert title(*three) == "LY 699 · Tel Aviv to Athens, Larnaca or Munich"
    five = one_a_day("777", ("VITORIA", "VIT"), ("PRISTINA", "PRN"), ("ATHENS", "ATH"), ("LARNACA", "LCA"),
                      ("MUNICH", "MUC"))
    assert title(*five) == "LY 777 · Tel Aviv to Vitoria, Pristina or 3 other cities"
    assert title(*five[:4]) == "LY 777 · Tel Aviv to Vitoria, Pristina or 2 other cities"
    bucharest = one_a_day("238", ("BUCHAREST (BANE", "OTP"), ("ATHENS", "ATH"), ("BUCHAREST", "OTP"))
    assert title(*bucharest) == "LY 238 · Tel Aviv to Bucharest or Athens"
    assert title(*bucharest[1:]) == "LY 238 · Tel Aviv to Athens or Bucharest"
    shorter_newer = one_a_day("239", ("BUCHAREST", "OTP"), ("ATHENS", "ATH"), ("BUCHAREST (BANE", "OTP"))
    assert title(*shorter_newer) == "LY 239 · Tel Aviv to Bucharest or Athens"
    assert [e["t"] for e in flights.search_entries(rows(*five, *bucharest, *arrival))] == [
        "LY 238 · Tel Aviv to Bucharest or Athens", "LY 682 · Munich or Frankfurt to Tel Aviv",
        "LY 777 · Tel Aviv to Vitoria, Pristina or 3 other cities"]
