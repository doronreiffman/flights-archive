"""The redesigned site's pages (docs/site-redesign.md: "Pages", "Words", "Codeshares", "Names"), from display rows
made with flights.make_rows. Expected values by hand; the how-it-works copy is the plan's Appendix A, verbatim."""
import html
import json
import re
from datetime import date, datetime

import pytest

from model.report import ATTRIBUTION
from test_timeline_flights import CLEAN, LAST_FETCH, first, flight, local, then, utc
from test_timeline_words import TO3459_OBS
from timeline import check, flights, views, words
from timeline.flights import DayInfo

SINCE = date(2026, 10, 27)
TO = dict(airline="TO", flight_no="3459", airline_name="TRANSAVIA FRANCE", airport="ORY", city_en="PARIS",
          city_he="פריז")
TO_CANCELLED = dict(outcome="canceled", cancel_lead_min=-142.75, cancel_lead_max_min=-126.75,
                    cancel_lead_censored=False)  # rule 3: "none: cancelled about 2 hours after …"
AT_LEAST_23 = dict(outcome="canceled", cancel_lead_min=1400.95, cancel_lead_max_min=None,
                   cancel_lead_censored=None, uncanceled=None)  # rule 1, IZ 992's shape


def text(page: str) -> str:
    """The page as a reader sees it: tags removed, entities unescaped, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", page))).strip()


def rows(*fs, obs=None):
    """Display rows for these flights; each has only its earliest record unless `obs` is given."""
    return flights.make_rows(list(fs), [first(f) for f in fs] if obs is None else obs, LAST_FETCH, 1)


def page_of(*fs, obs=None):
    rs = rows(*fs, obs=obs)
    return views.flight_page(rs, flights.partners(rs), SINCE)


def row_block(page: str, anchor: str) -> str:
    """One row of a flight page, from its opening tag to the next row's."""
    start = page.index(f'<div class="row" id="{anchor}">')
    end = page.find('<div class="row"', start + 1)
    return page[start:] if end == -1 else page[start:end]


def to3459_rows():
    """TO 3459: departed on 27 October (last expected 17:09), cancelled on 29 October with its real records,
    upcoming on 1 November."""
    gone = flight("to27", local(27, 16, 45), est_local_final=local(27, 17, 9), **TO)
    cancelled = flight("to29", local(29, 17, 10), est_local_final=local(29, 18, 45), **TO, **TO_CANCELLED)
    upcoming = flight("to01", datetime(2026, 11, 1, 18, 30), outcome="open", **TO)
    obs = [first(gone), *(o | {"flight_id": "to29", "snap_rn": n} for n, o in enumerate(TO3459_OBS, 1)),
           first(upcoming)]
    return rows(gone, cancelled, upcoming, obs=obs)


def to3459_page():
    rs = to3459_rows()
    return views.flight_page(rs, flights.partners(rs), SINCE)


# --- layout ----------------------------------------------------------------------------------------

def test_layout_head():
    page = views.layout("A <b> & 'c'", "<p>body</p>", "../")
    assert page.startswith('<!doctype html>\n<html lang="en">\n')
    assert '<meta name="robots" content="noindex">' in page
    assert "<title>A &lt;b&gt; &amp; &#x27;c&#x27;</title>" in page
    assert '<link rel="stylesheet" href="../style.css">' in page
    assert "<main>\n<p>body</p>\n</main>" in page


def test_layout_head_extra_goes_in_the_head():
    page = views.layout("t", "", "", head_extra='<meta name="description" content="x">')
    assert page.index('<meta name="description" content="x">') < page.index("</head>")


def test_layout_footer():
    page = views.layout("t", "", "../")
    footer = page[page.index("<footer>"):page.index("</footer>")]
    assert (f"{words.SOURCE_SHORT} {words.UNOFFICIAL} {words.TIMES_NOTE}") in text(footer)
    assert '<a href="../how-it-works.html">How this works</a>' in footer
    assert f'<a href="{words.CODE_URL}">Code on GitHub</a>' in footer
    assert f"Built by {words.BUILT_BY}" in text(footer)
    assert footer.index("How this works") < footer.index("Code on GitHub") < footer.index("Built by")


def test_d_escapes_and_marks_data():
    assert views.d("<script>") == '<span class="d">&lt;script&gt;</span>'
    assert views.d(None) == ""


# --- flight page -----------------------------------------------------------------------------------

def test_flight_page_head():
    page = to3459_page()
    assert "<title>TO 3459, Tel Aviv to Paris</title>" in page
    assert '<h1><span class="d">TO 3459, Tel Aviv to Paris</span></h1>' in page
    assert '<a href="../index.html">← Cancelled flights at Tel Aviv airport</a>' in page
    assert '<span class="d">TRANSAVIA FRANCE</span> (as the airport lists it)' in page
    assert "TRANSAVIA FRANCE (as the airport lists it) · lands at Paris (ORY) · פריז" in text(page)
    assert '<span lang="he" dir="rtl"><span class="d">פריז</span></span>' in page
    assert '<link rel="stylesheet" href="../style.css">' in page
    assert "Since 27 October: departed once, cancelled once, one upcoming." in text(page)


def test_an_arrival_leaves_from_its_airport():
    page = page_of(flight("in", local(29, 5, 0), flight_no="002", direction="A"))
    assert "<title>LY 002, from New York to Tel Aviv</title>" in page
    assert "leaves from New York (JFK)" in text(page)
    assert "lands at" not in page


def test_flight_rows_newest_first():
    page = to3459_page()
    assert (page.index('id="2026-11-01-1830-ORY"') < page.index('id="2026-10-29-1710-ORY"')
            < page.index('id="2026-10-27-1645-ORY"'))


def test_the_cancelled_row_is_open_with_its_warning_and_changes():
    row = row_block(to3459_page(), "2026-10-29-1710-ORY")
    assert "<details open>" in row
    assert text(row).startswith("Thu 29 Oct scheduled to leave 17:10 · last expected 18:45 CANCELLED")
    assert "No warning: cancelled about 2 hours after it was scheduled to leave." in text(row)
    assert [text(li) for li in re.findall(r"<li>(.*?)</li>", row)] == [
        "Earliest record (27 Oct 20:04) on time, terminal 1",
        "Between 27 Oct 20:24 and 14:29 Check-in desks 345-348, zone B",
        "17:32 Expected to leave at 17:38 instead",
        "18:32 Expected to leave at 18:45 instead",
        "Between 19:16 and 19:32 Cancelled",
    ]


def test_other_rows_are_closed():
    page = to3459_page()
    for anchor in ("2026-10-27-1645-ORY", "2026-11-01-1830-ORY"):
        row = row_block(page, anchor)
        assert "<details>" in row and "<details open" not in row


def test_last_expected_beside_the_scheduled_time_and_the_delay_sentence_once():
    page = to3459_page()
    assert ("Tue 27 Oct scheduled to leave 16:45 · last expected 17:09 DEPARTED"
            in text(row_block(page, "2026-10-27-1645-ORY")))
    assert "last expected" not in row_block(page, "2026-11-01-1830-ORY")
    assert text(page).count(words.DELAY_SENTENCE) == 1  # two rows show a last expected time


def test_no_delay_sentence_without_a_last_expected_time():
    page = page_of(flight("on time"))
    assert "scheduled to leave 16:45 DEPARTED" in text(page)
    assert "last expected" not in page and words.DELAY_SENTENCE not in text(page)


def test_a_row_without_records_has_no_details():
    rs = rows(flight("bare"), obs=[])
    row = row_block(views.flight_page(rs, flights.partners(rs), SINCE), "2026-10-29-1645-JFK")
    assert "DEPARTED" in row and "<details" not in row


def summary_rows(kinds):
    """One row per kind, each on its own day: departed, landed, cancelled, upcoming, no final update, unknown."""
    made = {"departed": {}, "landed": {"outcome": "landed"}, "cancelled": CLEAN, "upcoming": {"outcome": "open"},
            "no final update": {"outcome": "open"}, "unknown": {"outcome": "gap"}}
    fs = []
    for i, kind in enumerate(kinds):
        sched = datetime(2026, 11, 1 + i, 9, 0) if kind == "upcoming" else local(1 + i, 9, 0)
        fs.append(flight(f"f{i}", sched, **made[kind]))
    return fs


@pytest.mark.parametrize("kinds, summary", [
    (["departed"], "departed once"),
    (["departed", "departed"], "departed twice"),
    (["landed", "landed"], "landed twice"),
    (["cancelled"] * 3, "cancelled 3 times"),
    (["upcoming"], "one upcoming"),
    (["upcoming"] * 2, "two upcoming"),
    (["upcoming"] * 3, "3 upcoming"),
    (["no final update"], "one with no final update"),
    (["no final update"] * 2, "two with no final update"),
    (["unknown"], "one unknown"),
    (["unknown", "upcoming", "no final update", "cancelled", "landed", "departed"],  # in the labels' order
     "departed once, landed once, cancelled once, one upcoming, one with no final update, one unknown"),
])
def test_summary_counts_each_label_in_order(kinds, summary):
    assert f"Since 27 October: {summary}." in text(page_of(*summary_rows(kinds)))


def test_a_number_with_two_cities():
    """LY 5115 left at 16:30 on 28 October to Kutaisi and to Batumi: no city in the title, each row its own."""
    page = page_of(flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
                   flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI"))
    assert '<h1><span class="d">LY 5115, from Tel Aviv</span></h1>' in page
    assert "to Kutaisi (KUT)" in text(row_block(page, "2026-10-28-1630-KUT"))
    assert "to Batumi (BUS)" in text(row_block(page, "2026-10-28-1630-BUS"))
    assert 'lang="he"' not in page and "lands at" not in page


def test_one_city_through_two_airports_names_each_rows_airport():
    paris = dict(flight_no="002", city_en="PARIS", city_he="פריז")
    page = page_of(flight("orly", airport="ORY", **paris), flight("cdg", local(30, 16, 45), airport="CDG", **paris))
    assert '<h1><span class="d">LY 002, Tel Aviv to Paris</span></h1>' in page
    assert '<span lang="he" dir="rtl"><span class="d">פריז</span></span>' in page
    assert "to Paris (ORY)" in text(row_block(page, "2026-10-29-1645-ORY"))
    assert "to Paris (CDG)" in text(row_block(page, "2026-10-30-1645-CDG"))


def codeshare_page(*numbers):
    """LY 001's page on a day it shares with these (airline, number) partners."""
    fs = [flight("ly", group="g")] + [flight(a + n, airline=a, flight_no=n, group="g") for a, n in numbers]
    rs = rows(*fs)
    return views.flight_page(rs[:1], flights.partners(rs), SINCE)


def test_codeshare_line_links_each_partner_to_its_row():
    page = codeshare_page(("DL", "7426"), ("AM", "7895"))
    assert ("Probably the same flight as DL 7426 and AM 7895 (same time, terminal and check-in desks)."
            in text(page))
    assert '<a href="../flight/DL7426-D.html#2026-10-29-1645-JFK"><span class="d">DL 7426</span></a>' in page
    assert '<a href="../flight/AM7895-D.html#2026-10-29-1645-JFK"><span class="d">AM 7895</span></a>' in page


@pytest.mark.parametrize("numbers, names", [
    ([("DL", "7426")], "DL 7426"),
    ([("DL", "7426"), ("AM", "7895"), ("AF", "8350")], "DL 7426, AM 7895 and AF 8350"),
])
def test_codeshare_names(numbers, names):
    assert f"Probably the same flight as {names} (same time" in text(codeshare_page(*numbers))


def test_no_codeshare_line_without_partners():
    page = to3459_page()
    assert '<div class="row" id="2026-10-29-1710-ORY">' in page and "Probably" not in page


def test_notes_under_a_row():
    page = page_of(flight("gone", local(28, 9, 0), outcome="vanished", last_seen_at=utc(28, 0, 40)),  # 6 h 20 min
                   flight("back", local(29, 9, 0), uncanceled=True),
                   flight("cancelled", local(30, 9, 0), **AT_LEAST_23))
    assert ("Removed from the airport's list 6 hours before it was scheduled, with no final status. "
            "Not necessarily cancelled; it may have moved to another time."
            in text(row_block(page, "2026-10-28-0900-JFK")))
    assert "Shown as cancelled for a while, then changed back." in text(row_block(page, "2026-10-29-0900-JFK"))
    assert ("Warning: at least 23 hours. The earliest record already showed it as cancelled."
            in text(row_block(page, "2026-10-30-0900-JFK")))


def test_delayed_beside_the_main_label():
    f = flight("late", direction="A", outcome="landed")
    start = first(f)
    late = start | {"snap_rn": 2, "observed_at": utc(29, 13, 2, 45), "prev_observed_at": utc(29, 12, 46, 45),
                    "change_kind": "change", "changed_fields": ["status"], "status": "DELAYED"}
    row = row_block(page_of(f, obs=[start, late]), "2026-10-29-1645-JFK")
    assert "LANDED · DELAYED" in text(row)


def test_airport_data_is_escaped():
    page = page_of(flight("x", airline_name="<B>&CO", city_en="<SCRIPT>", city_he="<i>"))
    assert "<script" not in page.lower() and "<b>" not in page.lower()
    assert '<span class="d">&lt;B&gt;&amp;CO</span>' in page
    assert '<span class="d">&lt;script&gt;</span>' in page  # string.capwords leaves "<script>" as it is
    assert '<span lang="he" dir="rtl"><span class="d">&lt;i&gt;</span></span>' in page


# --- day page --------------------------------------------------------------------------------------

DAY = date(2026, 10, 29)


def day_flights():
    fs = [flight("in", local(29, 5, 0), flight_no="002", direction="A", outcome="landed"),
          flight("late", local(29, 20, 0), flight_no="003"),
          flight("to", local(29, 17, 10), **TO, **TO_CANCELLED),
          flight("dl", local(29, 9, 0), airline="DL", flight_no="7426", group="g"),
          flight("am", local(29, 9, 0), airline="AM", flight_no="7895", group="g")]
    return flights.group_flights(rows(*fs))


def day_page(total=418, cancelled=7, unknown=190, partial=True):
    return views.day_page(DayInfo(DAY, total, cancelled, unknown, "past", partial), day_flights())


def test_day_page_head():
    page = day_page()
    assert "<title>Thursday 29 October 2026</title>" in page
    assert "<h1>Thursday 29 October 2026</h1>" in page
    assert '<a href="../index.html">← Cancelled flights at Tel Aviv airport</a>' in page
    assert '<p class="count">418 flights · 7 cancelled · 190 unknown</p>' in page
    assert "Incomplete: some of this day's flights may be missing from the records." in text(page)
    assert '<p class="note">No known outcome for 190 of these flights.</p>' in page
    assert '<link rel="stylesheet" href="../style.css">' in page


@pytest.mark.parametrize("total, cancelled, unknown, line", [
    (418, 0, 190, "418 flights · 190 unknown"),
    (418, 7, 0, "418 flights · 7 cancelled"),
    (1, 0, 0, "1 flight"),
])
def test_day_count_line_leaves_out_zeros(total, cancelled, unknown, line):
    assert f'<p class="count">{line}</p>' in day_page(total, cancelled, unknown)


def test_day_page_unknown_line_for_one_flight():
    """Vanished and dropped flights have records of leaving, so the line says only that the outcome is unknown;
    each flight page gives the reason."""
    assert '<p class="note">No known outcome for 1 of these flights.</p>' in day_page(unknown=1)


def test_day_page_without_partial_or_unknown_lines():
    page = text(day_page(unknown=0, partial=False))
    assert "418 flights · 7 cancelled" in page and "TO 3459" in page
    assert "Incomplete" not in page and "No known outcome" not in page


def test_day_page_departures_then_arrivals_in_scheduled_order():
    page = text(day_page())
    order = ["Departures", "09:00 DL 7426, AM 7895 to New York (JFK) DEPARTED",
             "17:10 TO 3459 to Paris (ORY) CANCELLED No warning: cancelled about 2 hours after it was scheduled "
             "to leave.", "20:00 LY 003 to New York (JFK) DEPARTED",
             "Arrivals", "05:00 LY 002 from New York (JFK) LANDED"]
    assert [page.index(part) for part in order] == sorted(page.index(part) for part in order)


def test_day_rows_link_each_number_to_its_row():
    page = day_page()
    for href in ("../flight/TO3459-D.html#2026-10-29-1710-ORY", "../flight/DL7426-D.html#2026-10-29-0900-JFK",
                 "../flight/AM7895-D.html#2026-10-29-0900-JFK", "../flight/LY002-A.html#2026-10-29-0500-JFK"):
        assert f'<a href="{href}">' in page


def test_day_page_has_no_change_lines():
    page = day_page()
    assert "TO 3459" in text(page)
    assert "Earliest record" not in page and "<details" not in page


# --- all cancellations -----------------------------------------------------------------------------

def cells(page: str) -> list[list[str]]:
    return [[text(c) for c in re.findall(r"<t[hd]>(.*?)</t[hd]>", tr)] for tr in re.findall(r"<tr>(.*?)</tr>", page)]


def cancellations_page():
    fs = [flight("to", local(29, 17, 10), **TO, **TO_CANCELLED),
          flight("departed", local(29, 18, 0)),
          flight("iz", local(30, 13, 50), airline="IZ", flight_no="992", direction="A", **AT_LEAST_23),
          flight("ey", local(28, 9, 0), airline="EY", flight_no="607", group="g", **CLEAN),
          flight("ly", local(28, 9, 0), airline="LY", flight_no="9614", group="g", **CLEAN)]
    return views.cancellations_page(flights.group_flights(rows(*fs)))


def test_cancellations_newest_first():
    page = cancellations_page()
    assert "<title>All cancellations</title>" in page and "<h1>All cancellations</h1>" in page
    assert cells(page) == [
        ["Date", "Flight", "Route", "Warning"],
        ["Fri 30 Oct", "IZ 992", "New York (JFK) to Tel Aviv, scheduled to land 13:50", "at least 23 hours"],
        ["Thu 29 Oct", "TO 3459", "Tel Aviv to Paris (ORY), scheduled to leave 17:10",
         "none: cancelled about 2 hours after it was scheduled to leave"],
        ["Wed 28 Oct", "EY 607, LY 9614", "Tel Aviv to New York (JFK), scheduled to leave 09:00", "at least 6 hours"],
    ]


def test_cancellations_link_each_number_to_its_row():
    page = cancellations_page()
    for href in ("flight/IZ992-A.html#2026-10-30-1350-JFK", "flight/TO3459-D.html#2026-10-29-1710-ORY",
                 "flight/EY607-D.html#2026-10-28-0900-JFK", "flight/LY9614-D.html#2026-10-28-0900-JFK"):
        assert f'<a href="{href}">' in page
    assert '<link rel="stylesheet" href="style.css">' in page


def test_no_cancellations_yet():
    page = views.cancellations_page(flights.group_flights(rows(flight("departed"))))
    assert "<table" not in page and "No flights listed as cancelled so far." in text(page)


# --- how this works --------------------------------------------------------------------------------

GAP = (utc(27, 18, 24, 46), utc(29, 12, 29, 3))
LATER_GAP = (utc(31, 8, 2, 45), utc(31, 11, 32, 45))

APPENDIX_A = [  # docs/site-redesign-plan.md, "Appendix A", verbatim
    '## Where the data comes from',
    "The Israel Airports Authority publishes Ben Gurion Airport's list of departures and arrivals on data.gov.il, the Israeli government's open-data site. The list shows each flight from about three days before it is scheduled until about a day after. I built a small program that checks the list every 2 minutes and saves each new version, so a flight's history stays after it drops off the list.",
    '{ATTRIBUTION}',
    '## What the labels mean',
    "- DEPARTED and LANDED: the airport's final word on the flight.",
    "- CANCELLED: the airport's list showed the flight as cancelled.",
    "- UPCOMING: still on the list; its scheduled time hasn't come yet.",
    "- NO FINAL UPDATE: its scheduled time has passed, and the list hasn't given a final status yet.",
    '- UNKNOWN: it left the list without a final status, or while records are missing.',
    '- DELAYED: shown beside another label when the airport\'s list said "delayed" at some point.',
    '## How much warning',
    'For a cancelled flight, the warning is how long before its scheduled time the list already showed it as cancelled. The list refreshes about every 15 minutes, so the change is known to within that window. Where records are missing, the warning is a range ("between 7 and 50 hours"). When a flight was already cancelled the first time it appeared in the records, only a lower limit is known ("at least 23 hours"). For the same reason, the time of a cancellation is always given as a range. The airline may have told passengers earlier than the list showed.',
    '## Why there are no delay figures',
    "The list gives an expected time for each flight. It doesn't say whether that is when the plane leaves the gate or when it takes off. Until that is settled, this site shows the airport's times as they are and doesn't turn them into delay figures.",
    '## "Final" and "not final"',
    'The airport also uses the words "final" and "not final". It doesn\'t publish what they mean, so this site quotes them as they are.',
    '## Probably the same flight',
    "Airlines often sell seats on one flight under several flight numbers. When numbers share the same time, terminal and check-in desks, this site lists them as probably the same flight. The list doesn't say so itself, and arrivals with no check-in desks can occasionally be grouped by mistake.",
    '## Gaps in the records',
    'Records start on the evening of 27 October 2026. {one sentence per gap: "There are no records from 27 October 20:24 to 29 October 14:29."} A flight that left the list during a gap is marked UNKNOWN.',
    "## How it's built",
    'The program runs on AWS Lambda and saves each version once, to storage where it is locked for ten years. A Python data model turns the saved versions into one history per flight, and this site is generated from that model. Every rule has tests, and the tests are themselves checked by breaking the code on purpose and confirming that a test fails. The code is on GitHub.',
]


def appendix_text(gap_sentences: str) -> str:
    """Appendix A as a reader sees it on the page: markdown marks gone, placeholders filled."""
    lines = [re.sub(r"^(## |- )", "", line) for line in APPENDIX_A]
    joined = " ".join(lines).replace("{ATTRIBUTION}", ATTRIBUTION)
    return re.sub(r"\{one sentence per gap: [^}]*\}", gap_sentences, joined)


def test_how_it_works_is_appendix_a_verbatim():
    page = views.how_it_works_page(ATTRIBUTION, [GAP])
    assert "<title>How this works</title>" in page and "<h1>How this works</h1>" in page
    assert appendix_text("There are no records from 27 October 20:24 to 29 October 14:29.") in text(page)
    assert f'<a href="{words.CODE_URL}">' in page
    assert '<link rel="stylesheet" href="style.css">' in page


def test_how_it_works_one_sentence_per_gap_in_israel_time_with_dates():
    page = text(views.how_it_works_page(ATTRIBUTION, [GAP, LATER_GAP]))
    assert ("Records start on the evening of 27 October 2026. There are no records from 27 October 20:24 to "
            "29 October 14:29. There are no records from 31 October 10:02 to 31 October 13:32. A flight that left "
            "the list during a gap is marked UNKNOWN.") in page


def test_how_it_works_without_gaps():
    page = text(views.how_it_works_page(ATTRIBUTION, []))
    assert "Records start on the evening of 27 October 2026. A flight that left the list" in page


def test_how_it_works_carries_the_full_attribution_and_the_footer():
    page = views.how_it_works_page(ATTRIBUTION, [GAP])
    assert ATTRIBUTION in text(page)
    assert all(t in text(page) for t in (words.SOURCE_SHORT, words.UNOFFICIAL, words.TIMES_NOTE))


# --- front page ------------------------------------------------------------------------------------

CHART_DAYS = [DayInfo(date(2026, 10, 27), 348, 4, 12, "past", True),
              DayInfo(date(2026, 10, 28), 370, 8, 190, "past", False),
              DayInfo(date(2026, 10, 29), 418, 7, 0, "past", False),
              DayInfo(date(2026, 10, 30), 289, 1, 0, "today", False),
              DayInfo(date(2026, 10, 31), 161, 0, 0, "ahead", False),
              DayInfo(date(2026, 11, 1), 40, 0, 0, "ahead", True)]
ALL_DAYS = [DayInfo(date(2026, 10, 26), 120, 0, 3, "past", True), *CHART_DAYS]  # 26 Oct: not on the chart
HOSTILE = {"n": ["zz1"], "p": ["</script><b>"], "t": "ZZ 1, Tel Aviv to </script>`'\"", "u": "flight/ZZ1-D.html"}
DESCRIPTION = ("Which flights in and out of Tel Aviv's Ben Gurion Airport were cancelled, and how much warning "
               f"there was. Built by {words.BUILT_BY.removesuffix('.')}.")
ASY_UNKNOWN = dict(airline="ASY", flight_no="991", outcome="canceled", cancel_lead_min=30.0, cancel_lead_max_min=None,
                   cancel_lead_censored=None, uncanceled=None)  # rule 2: "unknown"


def entries():
    return [*flights.search_entries(to3459_rows()), HOSTILE]


def recent_default():
    """TO 3459 (no warning) and IZ 992 (at least 23 hours), newest first."""
    rs = rows(flight("to", local(29, 17, 10), **TO, **TO_CANCELLED),
              flight("iz", local(30, 13, 50), airline="IZ", flight_no="992", direction="A", **AT_LEAST_23))
    return flights.recent_cancellations(flights.group_flights(rs))


def twelve_cancelled():
    """LY 100 to LY 111, cancelled departures on 28 October, an hour apart from 06:00; newest first."""
    fs = [flight(f"c{i}", local(28, 6 + i, 0), flight_no=str(100 + i), **CLEAN) for i in range(12)]
    return flights.recent_cancellations(flights.group_flights(rows(*fs)), n=12)


def front(cancelled=20, known=951, story="TO 3459", recent=None, chart_days=None, all_days=None, data=None,
          last=LAST_FETCH):
    story_row = to3459_rows()[1] if story == "TO 3459" else story
    return views.front_page(cancelled, known, story_row, recent_default() if recent is None else recent,
                            CHART_DAYS if chart_days is None else chart_days,
                            ALL_DAYS if all_days is None else all_days, entries() if data is None else data, last)


def unknown_only_front():
    """Review Focus 3: the only cancellation's warning is unknown (ASY 991's shape, cancelled from its earliest
    record), so it is the story by the fallback rule."""
    f = flight("asy", local(29, 13, 30), **ASY_UNKNOWN)
    r = rows(f, obs=[first(f) | {"status": "CANCELED"}])[0]
    return front(1, 900, story=r, recent=[(r,)])


def delayed_story_front():
    """A story whose change lines include the airport's "delayed"."""
    f = flight("late", local(29, 23, 0), outcome="canceled", cancel_lead_min=358.0, cancel_lead_max_min=374.0,
               cancel_lead_censored=False)
    start = first(f)
    late = then(start, utc(29, 13, 2, 45), status="DELAYED")
    gone = then(late, utc(29, 15, 2, 45), status="CANCELED")
    r = rows(f, obs=[start, late, gone])[0]
    return front(1, 900, story=r, recent=[(r,)])


def meta(page: str, attribute: str) -> str:
    """The content of the head's <meta> with this name or property, unescaped."""
    return html.unescape(re.search(rf'<meta {attribute} content="([^"]*)">', page).group(1))


def section(page: str, start: str, end: str) -> str:
    i = page.index(start)
    return page[i:page.index(end, i)]


def chart_day(chart: str, day: str) -> str:
    """One day of the chart: its link and everything inside."""
    return re.search(rf'<a href="day/{day}.html"[^>]*>.*?</a>', chart, re.S).group(0)


def test_front_page_head():
    page = front()
    head = page[:page.index("</head>")]
    assert "<title>Cancelled flights at Tel Aviv airport (Ben Gurion)</title>" in head
    assert meta(head, 'name="description"') == DESCRIPTION
    assert meta(head, 'property="og:title"') == "Cancelled flights at Tel Aviv airport (Ben Gurion)"
    assert meta(head, 'property="og:description"') == DESCRIPTION
    assert meta(head, 'property="og:type"') == "website"
    assert "og:image" not in page
    assert '<script src="search.js" defer></script>' in head
    assert '<link rel="stylesheet" href="style.css">' in head


@pytest.mark.parametrize("built_by", ["Doron Reiffman.", "Doron Reiffman"])
def test_description_ends_with_one_full_stop_whatever_the_built_by_line_ends_with(monkeypatch, built_by):
    monkeypatch.setattr(words, "BUILT_BY", built_by)
    head = front()[:front().index("</head>")]
    for attribute in ('name="description"', 'property="og:description"'):
        assert meta(head, attribute).endswith("there was. Built by Doron Reiffman."), attribute


def test_front_page_title_and_lede():
    page = front()
    assert "<h1>Cancelled flights at Tel Aviv airport</h1>" in page
    assert ('<p class="lede">A record of flights in and out of Ben Gurion Airport, kept since 27 October 2026, and '
            "which ones were cancelled.</p>") in page


def test_front_page_headline():
    page = front(20, 951)
    assert ('<p class="headline">So far, 20 of 951 flights with a known outcome were listed as cancelled. '
            "That's about 1 in 50.</p>") in html.unescape(page)
    assert words.headline(20, 951) in text(page)


def test_no_headline_without_cancellations():
    page = front(0, 900, story=None, recent=[])
    assert 'class="headline"' not in page and "So far" not in page


def test_the_story_box():
    box = section(front(), '<section class="story">', "</section>")
    assert ('<h2><a href="flight/TO3459-D.html#2026-10-29-1710-ORY"><span class="d">TO 3459, Tel Aviv to Paris'
            "</span></a></h2>") in box
    assert "Thursday 29 October 2026, scheduled to leave 17:10" in text(box)
    assert [text(li) for li in re.findall(r"<li>(.*?)</li>", box)] == [
        "Earliest record (27 Oct 20:04) on time, terminal 1",
        "Between 27 Oct 20:24 and 14:29 Check-in desks 345-348, zone B",
        "17:32 Expected to leave at 17:38 instead",
        "18:32 Expected to leave at 18:45 instead",
        "Between 19:16 and 19:32 Cancelled",
    ]
    assert '<ol class="changes">' in box and '<span class="t">Between 19:16 and 19:32</span>' in box


def test_no_story_box_without_a_story():
    assert 'class="story"' not in front(story=None)


def test_search_box_hidden_until_the_script_runs():
    page = front()
    box = re.search(r'<input id="search"[^>]*>', page).group(0)
    assert re.search(r"\shidden[\s>]", box)
    assert 'placeholder="Flight number or city, e.g. LY 001 or Paris"' in box
    assert f'{box}\n<ul id="search-results" hidden></ul>' in page  # ruling 2: the results list right after it


def test_search_data_in_the_page():
    data = entries()
    page = front(data=data)
    assert f'<script type="application/json" id="flights-data">{views.search_json(data)}</script>' in page
    inside = re.search(r'<script type="application/json" id="flights-data">(.*?)</script>', page, re.S).group(1)
    assert json.loads(inside) == data  # a name containing </script> does not end the element
    assert "\\u003c/script>" in inside and "</script" not in inside


def test_search_json():
    assert views.search_json([{"t": "</script>", "n": ["a"]}]) == '[{"n": ["a"], "t": "\\u003c/script>"}]'
    assert views.search_json([{"t": "פריז"}]) == '[{"t": "פריז"}]'  # not \\u escapes: half the bytes


def test_recent_cancellations():
    page = front()
    table = section(page, '<table class="cancellations">', "</table>")
    assert cells(table) == [
        ["Date", "Flight", "Route", "Warning"],
        ["Fri 30 Oct", "IZ 992", "New York (JFK) to Tel Aviv, scheduled to land 13:50", "at least 23 hours"],
        ["Thu 29 Oct", "TO 3459", "Tel Aviv to Paris (ORY), scheduled to leave 17:10",
         "none: cancelled about 2 hours after it was scheduled to leave"],
    ]
    assert '<a href="flight/IZ992-A.html#2026-10-30-1350-JFK">' in table
    assert '<a href="flight/TO3459-D.html#2026-10-29-1710-ORY">' in table
    assert page.index("<h2>Recent cancellations</h2>") < page.index(table)
    assert '<p><a href="cancellations.html">All cancellations</a></p>' in page


def test_recent_cancellations_at_most_ten():
    page = front(recent=twelve_cancelled())
    shown = [row[1] for row in cells(page)[1:]]
    assert shown == [f"LY {n}" for n in range(111, 101, -1)]  # the first ten given, in their order


def test_chart_one_bar_per_day_inside_its_link():
    chart = views.chart_svg(CHART_DAYS)
    assert chart.count('<svg class="bar"') == len(CHART_DAYS) == chart.count("<a href=")
    for info in CHART_DAYS:
        assert '<svg class="bar"' in chart_day(chart, f"{info.day:%Y-%m-%d}")


def test_chart_counts_beside_each_bar():
    chart = views.chart_svg(CHART_DAYS)
    assert "Wed 28 Oct 370 flights · 8 cancelled · 190 unknown" in text(chart_day(chart, "2026-10-28"))
    assert "Thu 29 Oct 418 flights · 7 cancelled" in text(chart_day(chart, "2026-10-29"))
    assert "unknown" not in chart_day(chart, "2026-10-29")
    assert "Sat 31 Oct 161 flights" in text(chart_day(chart, "2026-10-31"))


def test_chart_counts_equal_the_day_pages():
    chart = views.chart_svg(CHART_DAYS)
    for info in CHART_DAYS:
        line = re.search(r'<p class="count">(.*?)</p>', views.day_page(info, [])).group(1)
        assert line in text(chart_day(chart, f"{info.day:%Y-%m-%d}"))


def test_chart_bar_in_three_parts():
    """Cancelled, unknown, the rest, in flights on one scale: the longest day fills the bar's width."""
    chart = views.chart_svg(CHART_DAYS)
    day = chart_day(chart, "2026-10-28")
    assert 'viewBox="0 0 418 8"' in day
    assert re.findall(r'<rect class="(\w+)" x="(\d+)" y="0" width="(\d+)" height="8"/>', day) == [
        ("cancelled", "0", "8"), ("unknown", "8", "190"), ("rest", "198", "172")]
    assert re.findall(r'<rect class="(\w+)" x="(\d+)" y="0" width="(\d+)"', chart_day(chart, "2026-10-31")) == [
        ("rest", "0", "161")]


def test_chart_today_ahead_and_incomplete():
    chart = views.chart_svg(CHART_DAYS)
    classes = {day: re.search(rf'<a href="day/{day}.html" class="([^"]*)">', chart).group(1)
               for day in ("2026-10-27", "2026-10-28", "2026-10-30", "2026-10-31", "2026-11-01")}
    assert classes == {"2026-10-27": "past partial", "2026-10-28": "past", "2026-10-30": "today",
                       "2026-10-31": "ahead", "2026-11-01": "ahead partial"}
    assert "incomplete" in text(chart_day(chart, "2026-10-27"))
    assert "today" in text(chart_day(chart, "2026-10-30"))
    assert "ahead" in text(chart_day(chart, "2026-10-31"))
    assert text(chart_day(chart, "2026-11-01")).endswith("ahead incomplete")
    plain = text(chart_day(chart, "2026-10-28"))
    assert not any(word in plain for word in ("incomplete", "today", "ahead"))


def test_chart_accessible_name_states_the_days_and_counts():
    chart = views.chart_svg(CHART_DAYS)
    label = html.unescape(re.search(r'<svg class="chart"[^>]* aria-label="([^"]*)"', chart).group(1))
    assert label == (
        "Flights each day. Tue 27 Oct, incomplete: 348 flights, 4 cancelled, 12 unknown. "
        "Wed 28 Oct: 370 flights, 8 cancelled, 190 unknown. Thu 29 Oct: 418 flights, 7 cancelled. "
        "Fri 30 Oct, today: 289 flights, 1 cancelled. Sat 31 Oct, ahead: 161 flights. "
        "Sun 1 Nov, ahead, incomplete: 40 flights.")


def test_front_page_draws_the_chart_days_and_lists_every_day():
    page = front()
    chart = section(page, '<svg class="chart"', "\n</svg>")
    assert chart.count('<svg class="bar"') == len(CHART_DAYS)
    assert "day/2026-10-26.html" not in chart  # every day, but only the chosen days on the chart
    assert page.index("<h2>Flights each day</h2>") < page.index('<svg class="chart"')
    days = section(page, '<p class="days">', "</p>")
    assert re.findall(r'<a href="(day/[\d-]+\.html)">', days) == [f"day/{x.day:%Y-%m-%d}.html" for x in ALL_DAYS]
    assert '<a href="day/2026-10-26.html">Mon 26 Oct</a>' in days


def test_last_updated_in_israel_time():
    assert '<p class="updated">Last updated 30 Oct 2026, 00:02</p>' in front(last=datetime(2026, 10, 29, 22, 2, 45))


def test_built_by_line():
    page = front()
    line = section(page, '<p class="built">', "</p>")
    assert text(line) == f"Built by {words.BUILT_BY} · How this works · Code on GitHub"
    assert '<a href="how-it-works.html">How this works</a>' in line
    assert f'<a href="{words.CODE_URL}">Code on GitHub</a>' in line


def test_front_page_order():
    page = front()
    order = ["<h1>", 'class="lede"', 'class="headline"', 'class="story"', '<input id="search"',
             'id="search-results"', 'id="flights-data"', "Recent cancellations", 'href="cancellations.html"',
             "Flights each day", '<svg class="chart"', 'class="days"', 'class="updated"', 'class="built"', "<footer>"]
    assert [page.index(part) for part in order] == sorted(page.index(part) for part in order)


def test_front_page_without_cancellations():
    """Review Focus 3: headline and story left out, everything else present."""
    page = views.front_page(0, 900, None, [], CHART_DAYS, CHART_DAYS, entries(), LAST_FETCH)
    assert 'class="headline"' not in page and 'class="story"' not in page
    assert '<input id="search"' in page and '<ul id="search-results" hidden></ul>' in page
    assert 'id="flights-data"' in page and '<svg class="chart"' in page and '<p class="days">' in page
    assert "<h2>Recent cancellations</h2>" in page and "No flights listed as cancelled so far." in text(page)
    assert "<table" not in page
    assert "Last updated 30 Oct 2026, 00:02" in text(page)
    assert all(t in text(page) for t in (words.SOURCE_SHORT, words.UNOFFICIAL, words.TIMES_NOTE))


def test_front_page_whose_only_cancellation_has_an_unknown_warning():
    """Review Focus 3: it still builds, with the flight as its story."""
    page = unknown_only_front()
    assert "So far, 1 of 900 flights with a known outcome were listed as cancelled." in text(page)
    box = section(page, '<section class="story">', "</section>")
    assert "Earliest record (27 Oct 20:04) already cancelled, terminal 3" in text(box)
    assert cells(page)[1][-1] == "unknown"


# --- the upload check's phrases on every page these tests build ------------------------------------

def every_page() -> dict[str, str]:
    rs = to3459_rows()
    return {
        "layout": views.layout("t", "", ""),
        "TO 3459": to3459_page(),
        "arrival": page_of(flight("in", local(29, 5, 0), flight_no="002", direction="A")),
        "two cities": page_of(flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
                              flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI")),
        "codeshare": codeshare_page(("DL", "7426"), ("AM", "7895")),
        "every label": page_of(*summary_rows(["departed", "landed", "cancelled", "upcoming", "no final update",
                                              "unknown"])),
        "notes": page_of(flight("gone", local(28, 9, 0), outcome="vanished", last_seen_at=utc(28, 0, 40)),
                         flight("back", local(29, 9, 0), uncanceled=True),
                         flight("again", local(30, 9, 0), **AT_LEAST_23 | {"uncanceled": True}),
                         flight("at least", local(31, 9, 0), **AT_LEAST_23)),
        "day": day_page(),
        "day, a cancellation at least 23 hours ahead": views.day_page(
            DayInfo(date(2026, 10, 30), 1, 1, 0, "today", False),
            flights.group_flights(rows(flight("iz", local(30, 13, 50), airline="IZ", flight_no="992", **AT_LEAST_23)))),
        "cancellations": cancellations_page(),
        "how it works": views.how_it_works_page(ATTRIBUTION, [GAP, LATER_GAP]),
        "TO 3459 rows on a day": views.day_page(DayInfo(DAY, 1, 1, 0, "past", False), flights.group_flights(rs[1:2])),
        "front page": front(),
        "front page, ten cancellations": front(recent=twelve_cancelled()),
        "front page, no cancellations": views.front_page(0, 900, None, [], CHART_DAYS, ALL_DAYS, entries(),
                                                         LAST_FETCH),
        "front page, a warning unknown": unknown_only_front(),
        "front page, a delayed story": delayed_story_front(),
    }


def hits(name: str, page: str) -> list[str]:
    """What the upload check would refuse, the built-by placeholder aside: phrases read as timeline.check reads a
    page (lower case, as written and with tags as spaces, entities unescaped, whitespace collapsed), so a label
    beside a text cannot join into one; the word rules through the check's own code, so the two cannot drift
    ("how it works" is the explainer page, every other name an ordinary page)."""
    flat = check.flatten(check.strip_tags(page))
    found = [p for p in check.BANNED if p in flat or p in check.flatten(page)]
    return found + check._word_hits(check.EXPLAINER if name == "how it works" else "page.html", page)


def test_hits_finds_a_label_joined_to_a_bare_warning():
    """The reason for the rule: "CANCELLED" then "at least 23 hours" reads as "cancelled at"."""
    assert hits("x", '<span class="label">CANCELLED</span><p>at least 23 hours</p>') == ["cancelled at"]
    assert sorted(hits("x", "<p>Our list</p><p>stored</p><p>I</p>")) == ["I", "our", "stored"]
    assert hits("x", "<p>snapshots, receipts and boards</p>") == ["boards", "receipts", "snapshots"]


@pytest.mark.parametrize("name", list(every_page()))
def test_no_page_trips_the_word_rules(name):
    page = every_page()[name]
    assert "<body>" in page
    assert hits(name, page) == []


BUILT_BY_WITH_I = "Doron Reiffman. I built this to learn"


def test_a_built_by_line_saying_i_passes_the_helper_and_the_upload_check(tmp_path, monkeypatch):
    """The owner's wording may say "I": timeline.check takes the built-by line out before its "I" rule, and so
    does hits(). Both modules are patched, as the owner's one edit to words.py reaches both."""
    for module in (words, check):
        monkeypatch.setattr(module, "BUILT_BY", BUILT_BY_WITH_I)
    pages = every_page()
    for i, (name, page) in enumerate(pages.items()):
        assert f"Built by {BUILT_BY_WITH_I}" in page, name
        assert hits(name, page) == [], name
        (tmp_path / (check.EXPLAINER if name == "how it works" else f"page-{i}.html")).write_text(page, encoding="utf-8")
    assert check.scan(tmp_path) == [] and check.missing_notices(tmp_path) == []
    assert check.main([str(tmp_path)]) == 0
