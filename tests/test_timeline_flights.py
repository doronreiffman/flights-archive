"""Display rows, flights, counts, addresses and search entries (docs/site-redesign.md: "Who is a flight",
"Labels", "Codeshares", "Names", "Pages", "How it is built"). Expected values by hand."""
from datetime import date, datetime, timedelta

import pytest

from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import flights
from timeline.flights import DayInfo, Row

LAST_FETCH = datetime(2026, 10, 29, 22, 2, 45)  # 00:02 Israel time on 30 October
EL_AL = "EL AL  ISRAEL AIRLINES"  # the double space as the airport publishes it


def local(day, h, m):
    """An airport time (Israel wall-clock, as published) in October 2026."""
    return datetime(2026, 10, day, h, m)


def utc(day, h, m, s=0):
    """A model time (naive UTC) in October 2026; Israel is UTC+2 after the 25 October clock change."""
    return datetime(2026, 10, day, h, m, s)


def flight(fid, sched=local(29, 16, 45), *, airline="LY", flight_no="001", direction="D", airport="JFK",
           city_en="NEW YORK", city_he="ניו יורק", outcome="departed", group=None, **kw):
    """A row of the model's flights table with the columns flights and words read; `kw` sets any other."""
    return {"flight_id": fid, "airline": airline, "flight_no": flight_no, "airline_name": EL_AL,
            "direction": direction, "airport": airport, "city_en": city_en, "city_he": city_he,
            "sched_local_first": sched, "sched_local_final": sched, "sched_utc_final": sched - timedelta(hours=2),
            "est_local_final": sched, "outcome": outcome, "last_seen_at": sched - timedelta(hours=3),
            "cancel_lead_min": None, "cancel_lead_max_min": None, "cancel_lead_censored": None,
            "uncanceled": False, "codeshare_group_id": group or fid} | kw


def first(f, observed_at=utc(27, 18, 4, 46)):
    """The flight's earliest record, as the model's observations table has it."""
    return {"flight_id": f["flight_id"], "snap_rn": 1, "observed_at": observed_at, "prev_observed_at": None,
            "change_kind": "first", "changed_fields": [], "sched_local": f["sched_local_first"],
            "est_local": f["sched_local_first"], "status": "ON TIME", "terminal": 3, "counters": "", "zone": ""}


def then(prev, observed_at, kind="change", **new):
    """The flight's next record, 16 minutes after its previous appearance: the previous values with `new` changed."""
    return prev | new | {"snap_rn": prev["snap_rn"] + 1, "observed_at": observed_at,
                         "prev_observed_at": observed_at - timedelta(minutes=16), "change_kind": kind,
                         "changed_fields": list(new)}


def rows(*fs, obs=None, last_fetch=LAST_FETCH):
    """Display rows for these flights; each has only its earliest record unless `obs` is given."""
    return flights.make_rows(list(fs), [first(f) for f in fs] if obs is None else obs, last_fetch, 1)


def ids(flights_):
    return [[r.flight_id for r in fl] for fl in flights_]


CLEAN = dict(outcome="canceled", cancel_lead_min=400.0, cancel_lead_max_min=416.0, cancel_lead_censored=False)
CENSORED = dict(outcome="canceled", cancel_lead_min=75.95, cancel_lead_max_min=2600.48, cancel_lead_censored=True)


def censored_map(fs):
    return {f["flight_id"]: f["cancel_lead_censored"] for f in fs}


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
        sched_final=local(29, 16, 45), label="DEPARTED", delayed=False, warning=None, warning_note=None,
        label_note=None, changed_back=None, last_expected="last expected 17:09", page="flight/LY001-D.html",
        anchor="2026-10-29-1645-JFK", group_id="g1",
        lines=(("Earliest record (27 Oct 20:04)", "on time, terminal 3"),))]


def test_a_retimed_row_is_on_the_day_of_its_final_time_with_the_anchor_of_its_first():
    """Its records reach the change lines in model order (snap_rn) whatever order they arrive in, beside another
    flight's, and its lines are written for the day of its final scheduled time."""
    f = flight("f1", local(29, 0, 30), sched_local_first=local(28, 23, 30))
    start = first(f)
    moved = then(start, utc(28, 20, 32, 45), kind="retime", sched_local=local(29, 0, 30), est_local=local(29, 0, 30))
    row = rows(f, obs=[moved, first(flight("other")), start])[0]
    assert (row.day, row.anchor) == (date(2026, 10, 29), "2026-10-28-2330-JFK")
    assert row.lines == (("Earliest record (27 Oct 20:04)", "on time, terminal 3"),
                         ("28 Oct 22:32", "Moved to a new scheduled time: 28 Oct 23:30 → 00:30"))


def test_delayed_only_for_the_row_whose_own_records_show_it():
    """The next day's flight of the same number stays undelayed, and a later status does not undo it."""
    today, tomorrow = flight("today", local(29, 16, 45)), flight("tomorrow", local(30, 16, 45), outcome="open")
    start = first(today)
    late = then(start, utc(29, 13, 2, 45), status="DELAYED")
    gone = then(late, utc(29, 15, 2, 45), status="DEPARTED")
    got = rows(today, tomorrow, obs=[start, late, gone, first(tomorrow)])
    assert [(r.label, r.delayed) for r in got] == [("DEPARTED", True), ("UPCOMING", False)]


def test_label_warning_and_notes_come_from_words():
    gone = flight("v", outcome="vanished", last_seen_at=utc(29, 8, 25))  # 6 h 20 min before 14:45 UTC
    cancelled = flight("c", **CENSORED | {"cancel_lead_min": 1400.95, "cancel_lead_max_min": None, "uncanceled": None})
    back = flight("b", direction="A", outcome="landed", uncanceled=True)
    got = [(r.label, r.warning, r.warning_note, r.label_note, r.changed_back) for r in rows(gone, cancelled, back)]
    assert got == [
        ("UNKNOWN", None, None, "Removed from the airport's list 6 hours before it was scheduled, with no final "
                                "status. Not necessarily cancelled; it may have moved to another time.", None),
        ("CANCELLED", "at least 23 hours", "The earliest record already showed it as cancelled.", None, None),
        ("LANDED", None, None, None, "Shown as cancelled for a while, then changed back."),
    ]


def test_no_final_update_decided_in_utc(israeli_machine):
    """23:55 Israel time is 21:55 UTC, before the 22:02 UTC last record: no final update. Deciding with the
    Israel wall-clock value would call it UPCOMING."""
    f = flight("late", local(29, 23, 55), outcome="open")
    assert (f["sched_local_final"], f["sched_utc_final"]) == (local(29, 23, 55), utc(29, 21, 55))
    assert flights.make_rows([f], [first(f)], LAST_FETCH, 1)[0].label == "NO FINAL UPDATE"


# --- flights ---------------------------------------------------------------------------------------

def test_codeshare_members_with_one_label_are_one_flight():
    a = flight("a", airline="EY", flight_no="607", group="g")
    b = flight("b", airline="LY", flight_no="9614", group="g")
    assert ids(flights.group_flights(rows(a, b))) == [["a", "b"]]


def test_members_with_different_labels_are_separate_flights():
    a = flight("a", airline="EY", direction="A", outcome="landed", group="g")
    b = flight("b", airline="LY", direction="A", outcome="gap", group="g")
    assert ids(flights.group_flights(rows(a, b))) == [["a"], ["b"]]


def test_a_member_shown_delayed_is_its_own_flight():
    a, b = flight("a", airline="EY", group="g"), flight("b", airline="LY", group="g")
    start = first(a)
    assert ids(flights.group_flights(rows(a, b, obs=[start, then(start, utc(29, 13, 2, 45), status="DELAYED"),
                                                     first(b)]))) == [["a"], ["b"]]


def test_members_with_different_warnings_are_separate_flights():
    a = flight("a", airline="EY", group="g", **CLEAN)  # at least 6 hours
    b = flight("b", airline="LY", group="g", **CLEAN | {"cancel_lead_min": 45.0, "cancel_lead_max_min": 74.0})
    assert ids(flights.group_flights(rows(a, b))) == [["a"], ["b"]]


def test_one_group_id_on_two_days_is_two_flights():
    a, b = flight("a", local(29, 9, 0), group="g"), flight("b", local(30, 9, 0), group="g")  # both DEPARTED
    assert ids(flights.group_flights(rows(a, b))) == [["a"], ["b"]]


def test_partners_are_the_other_members_of_the_flight_after_the_split():
    fs = [flight("a", airline="DL", flight_no="7426", group="g"), flight("b", airline="AM", flight_no="7895", group="g"),
          flight("c", airline="LY", flight_no="001", group="g", outcome="gap"), flight("d", flight_no="002")]
    got = {fid: [p.flight_id for p in ps] for fid, ps in flights.partners(rows(*fs)).items()}
    assert got == {"a": ["b"], "b": ["a"], "c": [], "d": []}


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
    got = flights.day_infos(flights.group_flights(rows(*fs, last_fetch=last)), last, {date(2026, 10, 29)})
    assert got == [DayInfo(date(2026, 10, 29), total=3, cancelled=1, unknown=1, state="past", partial=True),
                   DayInfo(date(2026, 10, 30), total=1, cancelled=0, unknown=0, state="today", partial=False),
                   DayInfo(date(2026, 10, 31), total=1, cancelled=0, unknown=0, state="ahead", partial=False)]


def test_headline_counts_flights_with_a_known_outcome():
    fs = [flight("departed", local(29, 8, 0)), flight("landed", local(29, 9, 0), direction="A", outcome="landed"),
          flight("c1", local(29, 10, 0), airline="EY", flight_no="607", group="g", **CLEAN),
          flight("c2", local(29, 10, 0), airline="LY", flight_no="9614", group="g", **CLEAN),
          flight("upcoming", local(30, 10, 0), outcome="open"),
          flight("no final update", local(29, 23, 55), outcome="open"),
          flight("unknown", local(29, 11, 0), outcome="gap")]
    assert [r.label for r in rows(*fs)] == ["DEPARTED", "LANDED", "CANCELLED", "CANCELLED", "UPCOMING",
                                            "NO FINAL UPDATE", "UNKNOWN"]
    assert flights.headline_counts(flights.group_flights(rows(*fs))) == (1, 3)


# --- the featured flight and recent cancellations --------------------------------------------------

def test_featured_is_the_most_recent_cancellation_with_a_clean_warning():
    fs = [flight("old", local(28, 9, 0), **CLEAN), flight("new", local(29, 9, 0), **CLEAN),
          flight("newer, censored", local(30, 9, 0), **CENSORED), flight("departed", local(31, 9, 0))]
    assert flights.featured(rows(*fs), censored_map(fs)).flight_id == "new"


def test_without_a_clean_warning_the_cancellation_with_the_most_lines():
    long_, short = flight("long", local(28, 9, 0), **CENSORED), flight("short", local(30, 9, 0), **CENSORED)
    a0 = first(long_)
    a1 = then(a0, utc(27, 20, 2, 45), counters="345-348")
    a2 = then(a1, utc(28, 5, 2, 45), status="CANCELED")
    got = flights.featured(rows(long_, short, obs=[a0, a1, a2, first(short)]), censored_map([long_, short]))
    assert (got.flight_id, len(got.lines)) == ("long", 3)


def test_featured_ties_by_scheduled_time_then_airline_and_number():
    fs = [flight("LY 002", local(29, 9, 0), flight_no="002", **CLEAN),
          flight("IZ 991", local(29, 9, 0), airline="IZ", flight_no="991", **CLEAN),
          flight("LY 001", local(29, 9, 0), flight_no="001", **CLEAN)]
    assert flights.featured(rows(*fs), censored_map(fs)).flight_id == "IZ 991"
    gs = [flight("older", local(28, 9, 0), flight_no="001", **CENSORED),
          flight("LY 009", local(29, 9, 0), flight_no="009", **CENSORED),
          flight("LY 003", local(29, 9, 0), flight_no="003", **CENSORED)]
    assert flights.featured(rows(*gs), censored_map(gs)).flight_id == "LY 003"  # same number of lines


def test_no_cancellation_no_featured_flight():
    assert flights.featured(rows(flight("departed")), {"departed": None}) is None


def test_recent_cancellations_newest_first_at_most_n():
    fs = [flight(f"c{h}", local(29, h, 0), flight_no=f"{h:03}", **CLEAN) for h in range(8, 20)]  # 12, 08:00 to 19:00
    fs += [flight("IZ 991", local(29, 19, 0), airline="IZ", flight_no="991", **CLEAN),  # ties with c19: IZ first
           flight("departed", local(29, 21, 0))]
    flights_ = flights.group_flights(rows(*fs))
    assert ids(flights.recent_cancellations(flights_)) == [["IZ 991"], ["c19"], ["c18"], ["c17"], ["c16"],
                                                           ["c15"], ["c14"], ["c13"], ["c12"], ["c11"]]
    assert ids(flights.recent_cancellations(flights_, n=2)) == [["IZ 991"], ["c19"]]


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
        {"n": ["iz991", "991"], "p": ["ath", "athens"], "t": "IZ 991, from Athens to Tel Aviv",
         "u": "flight/IZ991-A.html"},
        {"n": ["ly001", "ly1", "001", "1"], "p": ["jfk", "newyork"], "t": "LY 001, from New York to Tel Aviv",
         "u": "flight/LY001-A.html"},
        {"n": ["ly001", "ly1", "001", "1"], "p": ["jfk", "newyork"], "t": "LY 001, Tel Aviv to New York",
         "u": "flight/LY001-D.html"},
        {"n": ["ly5115", "5115"], "p": ["batumi", "bus", "kut", "kutaisi"], "t": "LY 5115, from Tel Aviv",
         "u": "flight/LY5115-D.html"},
        {"n": ["ly5116", "5116"], "p": ["batumi", "bus", "kut", "kutaisi"], "t": "LY 5116, to Tel Aviv",
         "u": "flight/LY5116-A.html"},
    ]


def test_page_title_names_the_city_when_the_number_has_one():
    """One city through two airports is still one city."""
    fs = [flight("orly", flight_no="002", airport="ORY", city_en="PARIS"),
          flight("cdg", local(30, 16, 45), flight_no="002", airport="CDG", city_en="PARIS")]
    assert flights.page_title(rows(*fs)) == "LY 002, Tel Aviv to Paris"
