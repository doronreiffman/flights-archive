"""The redesigned site's pages (docs/site-redesign.md: "Pages", "Words", "Codeshares", "Names"), from display rows
made with flights.make_rows. Expected values by hand; the how-it-works copy is the plan's Appendix A, verbatim."""
import html
import re
from datetime import date, datetime

import pytest

from model.report import ATTRIBUTION
from test_timeline_flights import CLEAN, LAST_FETCH, first, flight, local, utc
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
    }


PHRASES = (*check.BANNED, "minutes late", "hours late")
COLLECTION_WORDS = ("board", "snapshot", "stored", "observed", "receipt")


def hits(name: str, page: str) -> list[str]:
    """What the upload check would refuse, and the redesign's word rules: phrases read as timeline.check reads a
    page (lower case, as written and with tags as spaces, entities unescaped, whitespace collapsed), so a label
    beside a text cannot join into one; whole words in the text with tags as spaces."""
    flat = check.flatten(check.strip_tags(page))
    found = [p for p in PHRASES if p in flat or p in check.flatten(page)]
    found += [w for w in ("we", "our", "us") if re.search(rf"\b{w}\b", flat)]
    if name != "how it works":
        found += [w for w in COLLECTION_WORDS if re.search(rf"\b{w}\b", flat)]
        found += ["I"] if re.search(r"\bI\b", re.sub(r"\s+", " ", html.unescape(check.strip_tags(page)))) else []
    return found


def test_hits_finds_a_label_joined_to_a_bare_warning():
    """The reason for the rule: "CANCELLED" then "at least 23 hours" reads as "cancelled at"."""
    assert hits("x", '<span class="label">CANCELLED</span><p>at least 23 hours</p>') == ["cancelled at"]
    assert hits("x", "<p>Our list</p><p>stored</p><p>I</p>") == ["our", "stored", "I"]


@pytest.mark.parametrize("name", list(every_page()))
def test_no_page_trips_the_word_rules(name):
    page = every_page()[name]
    assert "<body>" in page
    assert hits(name, page) == []
