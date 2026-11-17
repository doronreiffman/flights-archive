"""The whole site, built from small synthetic models through the real model build (docs/site-redesign.md: "Pages",
"How it is built", "Tests and checks")."""
import html
import json
import os
import posixpath
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from model import build as model_build
from model.report import ATTRIBUTION
from counting_helpers import board
from model_helpers import at, row, write_receipt, write_snapshot
from test_timeline_flights import first, flight
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import blend, build, check, counting, flights, names, words
from timeline.check import BANNED


def upload_check(site) -> None:
    """Every site the tests build passes the upload check (docs/flight-lookup.md, "Tests and checks") and prints no
    range: no test model clears the floor anywhere (Review Focus 3)."""
    assert check.scan(site) == []
    assert check.missing_notices(site) == []
    assert [p.name for p in site.rglob("*.html") if "(between" in text(p.read_text(encoding="utf-8"))] == []


def make_site(tmp_path, snapshots) -> Path:
    raw, model, site = tmp_path / "raw", tmp_path / "model", tmp_path / "site"
    for when, rows in snapshots:
        write_snapshot(raw, when, rows)
    model_build.build(raw, model)
    build.build(model, site)
    upload_check(site)
    return site


def read(site, rel):
    return (site / rel).read_text(encoding="utf-8")


def all_pages(site):
    return {p.relative_to(site).as_posix(): p.read_text(encoding="utf-8") for p in sorted(site.rglob("*.html"))}


def text(page: str) -> str:
    """The page as a reader sees it: tags removed, entities unescaped, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", page))).strip()


def chart(page: str) -> str:
    i = page.index('<ol class="chart">')
    return page[i:page.index("</ol>", i)]


def chart_day(index: str, day: str) -> str:
    """One day of the front page's chart: its link and everything inside."""
    return re.search(rf'<a href="day/{day}.html"[^>]*>.*?</a>', chart(index), re.S).group(0)


def chart_counts(index: str, day: str) -> str:
    """The counts the chart prints beside a day's date: "4 flights · 1 cancelled · 1 unknown"."""
    return re.search(r'<span class="counts">([^<]*)', chart_day(index, day)).group(1).rstrip()


def day_count_line(page: str) -> str:
    """A day page's counts as the chart prints them ("4 flights · 1 cancelled · 1 unknown"): the flights and the
    cancelled from its title, the unknown from its unknown line; a zero is left out of both."""
    parts = text(re.search(r"<h1>([^<]*)</h1>", page).group(1)).split(" · ")[1:]
    unknown = re.search(r"For ([\d,]+) of these flights, there's no record of how", text(page))
    return " · ".join(parts + ([f"{unknown.group(1)} unknown"] if unknown else []))


def day_counts(page: str) -> tuple[int, int, int]:
    """A day page's flights, cancelled and unknown, read from its count line (a zero is left out of the line)."""
    line = day_count_line(page)
    found = [re.search(rf"([\d,]+) {word}", line) for word in ("flights?", "cancelled", "unknown")]
    return tuple(int(m.group(1).replace(",", "")) if m else 0 for m in found)


def total_counts(index: str) -> tuple[int, int]:
    """The front page's total: (cancelled, flights with a known result)."""
    m = re.search(r"Since \d+ \w+, ([\d,]+) of ([\d,]+) flights at Ben Gurion (?:was|were) cancelled", text(index))
    return int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))


LY1 = row(sched_local="2026-10-28T10:00:00")
CODESHARE = [row(airline="EY", flight_no="607", sched_local="2026-10-28T12:00:00", counters="12-21"),
             row(airline="LY", flight_no="9614", sched_local="2026-10-28T12:00:00", counters="12-21")]
CANCELS = row(airline="IZ", flight_no="991", sched_local="2026-10-28T10:00:00", airport="ATH", city_en="ATHENS")


@pytest.fixture
def site(tmp_path):
    return make_site(tmp_path, [
        (at(6), [LY1, *CODESHARE, CANCELS]),
        (at(6, 15), [row(sched_local="2026-10-28T10:00:00", est_local="2026-10-28T10:30:00"), *CODESHARE,
                     row(airline="IZ", flight_no="991", sched_local="2026-10-28T10:00:00", airport="ATH", city_en="ATHENS",
                         status="CANCELED", status_he="מבוטל")]),
    ])


# --- the file set ----------------------------------------------------------------------------------

# The four faces and the licence served beside them (docs/site-redesign.md, "Look A"; the owner, 2026-11-17).
FONT_FILES = ("fonts/sans-cond-300.woff2", "fonts/sans-cond-400.woff2", "fonts/sans-cond-600.woff2",
              "fonts/hebrew-sans-400.woff2", "fonts/LICENSE.txt")


def test_the_site_is_the_redesigned_pages_and_nothing_of_v1(site):
    files = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    assert files == {build.MARKER, "index.html", "how-it-works.html", "cancellations.html", "day/2026-10-28.html",
                     "flight/EY607-D.html", "flight/IZ991-D.html", "flight/LY001-D.html", "flight/LY9614-D.html",
                     "search.js", "fromhere.js", "style.css", *FONT_FILES}


def test_fromhere_js_is_written(site):
    """The second script, which every page loads."""
    assert read(site, "fromhere.js") == (build.STATIC / "fromhere.js").read_text(encoding="utf-8")


def test_only_html_css_js_the_four_fonts_and_their_licence_besides_the_marker(site):
    odd = [p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file() and p.name != build.MARKER
           and p.suffix not in {".html", ".css", ".js"}]
    assert sorted(odd) == sorted(FONT_FILES)


def test_the_font_files_and_their_licence_are_written_byte_for_byte(site):
    """The faces are binary and the licence keeps its own line ends (CRLF): neither may go through text."""
    for rel in FONT_FILES:
        assert (site / rel).read_bytes() == (build.STATIC / rel).read_bytes(), rel


PRELOAD = re.compile(r'<link rel="preload" href="([^"]*)" as="font" type="font/woff2" crossorigin>')


def test_every_page_preloads_the_regular_and_semibold_files(site):
    """docs/site-redesign.md, "Look A", Loading: every page asks early for the two files most of its text needs, by a
    path from its own folder; the Light file waits for the style sheet, and the Hebrew one for a page with Hebrew on
    it."""
    pages = all_pages(site)
    assert len(pages) == 8
    for name, page in pages.items():
        head = page[:page.index("</head>")]
        hrefs = PRELOAD.findall(head)
        assert [posixpath.normpath(posixpath.join(posixpath.dirname(name), h)) for h in hrefs] == [
            "fonts/sans-cond-400.woff2", "fonts/sans-cond-600.woff2"], name
        assert page.count('rel="preload"') == 2, name


def test_every_page_carries_the_footer_notices_and_stays_out_of_search_engines(site):
    pages = all_pages(site)
    assert len(pages) == 8
    for name, page in pages.items():
        assert page.startswith('<!doctype html>\n<html lang="en">'), name
        assert '<meta name="robots" content="noindex">' in page, name
        for notice in (words.SOURCE_SHORT, words.UNOFFICIAL, words.TIMES_NOTE, words.ESTIMATES, words.MEANS):
            assert notice in text(page), (name, notice)
    assert ATTRIBUTION in text(pages["how-it-works.html"])


# --- every page's top line (docs/site-redesign.md, "Every page") ------------------------------------

def test_the_top_line(site):
    """Every page opens with the site's name, linked to the front page from the page's own folder and the page's <h1>
    on the front page only, then "Tel Aviv airport"."""
    pages = all_pages(site)
    assert len(pages) == 8
    for name, page in pages.items():
        tag, root = ("h1" if name == "index.html" else "p"), "../" * name.count("/")
        assert (f'<body>\n<header class="mast">\n<{tag} class="wordmark"><a href="{root}index.html">Will It Fly?</a>'
                f'</{tag}>\n<p class="where">Tel Aviv airport</p>\n<p class="updated" ') in page, name
        assert page.count('class="wordmark"') == 1 and page.count('<h1 class="wordmark">') == (name == "index.html")


UPDATED_LINE = re.compile(r'<p class="updated" data-updated="([^"]*)">([^<]*)</p>')


def test_every_page_says_when_it_was_updated(tmp_path, israeli_machine):
    """The last sighting, 22:30 UTC on 27 October, is 00:30 on 28 October in Israel. Every page's top line carries it
    as the UTC instant it is, which fromhere.js reads to write the page's age, and as the date and time in Israel time,
    the line that stands without scripts (docs/flight-lookup.md, "Pages", fromhere.js items 3 and 4)."""
    site = make_site(tmp_path, [(at(21), [LY1]), (at(22, 30), [LY1])])
    _, _, snaps = build.load(tmp_path / "model")
    assert counting.last_sighting(snaps) == at(22, 30)
    pages = all_pages(site)
    assert sorted(pages) == ["cancellations.html", "day/2026-10-28.html", "flight/LY001-D.html", "how-it-works.html",
                             "index.html"]
    for name, page in pages.items():
        assert UPDATED_LINE.findall(page) == [("2026-10-27T22:30:00Z", "Updated 28 Oct at 00:30")], name


def test_every_page_loads_fromhere_js(site):
    """fromhere.js writes the page's age on every page (docs/flight-lookup.md, "Pages", fromhere.js item 3): each page
    loads it once, deferred, in its head, by a path from its own folder."""
    pages = all_pages(site)
    assert len(pages) == 8
    for name, page in pages.items():
        found = re.findall(r'<script src="([^"]*fromhere\.js)" defer></script>', page[:page.index("</head>")])
        assert [posixpath.normpath(posixpath.join(posixpath.dirname(name), src)) for src in found] == ["fromhere.js"], name
        assert page.count("fromhere.js") == 1, name


def test_no_page_uses_a_banned_phrase(site):
    for name, page in all_pages(site).items():
        flat = [re.sub(r"\s+", " ", html.unescape(t)).lower() for t in (page, re.sub(r"<[^>]*>", " ", page))]
        assert [b for b in BANNED if any(b in f for f in flat)] == [], name


# --- every row, once -------------------------------------------------------------------------------

MIXED = [
    (at(6), [LY1, *CODESHARE,
             row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="KUT", city_en="KUTAISI"),
             row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="BUS", city_en="BATUMI"),
             row(flight_no="002", sched_local="2026-10-28T23:30:00"),
             row(flight_no="002", direction="A", sched_local="2026-10-29T08:00:00", airport="CDG", city_en="PARIS"),
             row(sched_local="2026-10-29T10:00:00")]),
    (at(6, 15), [LY1, *CODESHARE,
                 row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="KUT", city_en="KUTAISI"),
                 row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="BUS", city_en="BATUMI"),
                 row(flight_no="002", sched_local="2026-10-29T00:30:00"),  # retimed across midnight
                 row(flight_no="002", direction="A", sched_local="2026-10-29T08:00:00", airport="CDG", city_en="PARIS"),
                 row(sched_local="2026-10-29T10:00:00")]),
]


def test_every_flights_row_is_on_one_flight_page_and_on_the_day_page_of_its_final_time(tmp_path):
    site = make_site(tmp_path, MIXED)
    table, _, _ = build.load(tmp_path / "model")
    expected = {(flights.page_address(f["airline"], f["flight_no"], f["direction"]),
                 flights.row_anchor(f["sched_local_first"], f["airport"])): f["sched_local_final"].date()
                for f in table}
    assert len(expected) == len(table) == 8
    pages = all_pages(site)
    on_flight_pages = [(name, anchor) for name, page in pages.items() if name.startswith("flight/")
                       for anchor in re.findall(r'<section class="day" id="([^"]+)"', page)]
    assert sorted(on_flight_pages) == sorted(expected)
    on_day_pages = [(date.fromisoformat(name[4:14]), link) for name, page in pages.items() if name.startswith("day/")
                    for link in re.findall(r'href="\.\./(flight/[^"#]+)#([^"]+)"', page)]
    assert sorted(on_day_pages) == sorted((day, link) for link, day in expected.items())


def test_a_retime_across_midnight_is_on_the_day_of_its_final_time_with_the_anchor_of_its_first(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T23:30:00")]),
                                (at(6, 15), [row(sched_local="2026-10-29T00:30:00")])])
    assert not (site / "day" / "2026-10-28.html").exists()
    assert 'href="../flight/LY001-D.html#2026-10-28-2330-JFK"' in read(site, "day/2026-10-29.html")
    page = read(site, "flight/LY001-D.html")
    assert '<section class="day" id="2026-10-28-2330-JFK" data-sched="2026-10-28T22:30:00Z">' in page
    assert "Moved to a new scheduled time: 28 Oct 23:30 → 00:30" in text(page)


def test_one_number_leaving_twice_at_one_time_gets_two_anchors_on_one_page(tmp_path):
    """LY 5115 left at 16:30 on 28 October twice, to Kutaisi and to Batumi."""
    site = make_site(tmp_path, [(at(6), [
        row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="KUT", city_en="KUTAISI"),
        row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="BUS", city_en="BATUMI")])])
    ids = re.findall(r'<section class="day" id="([^"]+)"', read(site, "flight/LY5115-D.html"))
    assert sorted(ids) == ["2026-10-28-1630-BUS", "2026-10-28-1630-KUT"]
    day = read(site, "day/2026-10-28.html")
    assert "#2026-10-28-1630-BUS" in day and "#2026-10-28-1630-KUT" in day


def test_every_link_and_search_address_leads_to_a_written_page_and_an_existing_anchor(tmp_path):
    """Every relative href (pages, the style sheet, #anchors) and every search entry's address, read from the page
    it is on, names a file the build wrote and, after a "#", an id on that page."""
    cancelled = row(airline="IZ", flight_no="991", sched_local="2026-10-28T10:00:00", airport="ATH", city_en="ATHENS",
                    status="CANCELED", status_he="מבוטל")
    site = make_site(tmp_path, [(MIXED[0][0], [*MIXED[0][1], CANCELS]), (MIXED[1][0], [*MIXED[1][1], cancelled])])
    written = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    pages = all_pages(site)
    ids = {name: {html.unescape(i) for i in re.findall(r'\sid="([^"]*)"', page)} for name, page in pages.items()}
    links = [(name, html.unescape(href)) for name, page in pages.items() for href in re.findall(r'\shref="([^"]*)"', page)]
    data = re.search(r'<script type="application/json" id="flights-data">(.*?)</script>', pages["index.html"], re.S)
    entries = json.loads(data.group(1))
    assert len(entries) == sum(name.startswith("flight/") for name in written) == 7
    links += [("index.html", entry["u"]) for entry in entries]
    relative = [(name, href) for name, href in links if not re.match(r"[a-z][a-z0-9+.-]*:", href)]
    assert any(name.startswith("day/") and href.startswith("../flight/") and "#" in href for name, href in relative)
    broken = []
    for name, href in relative:
        path, _, anchor = href.partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) if path else name
        if target not in written or (anchor and anchor not in ids.get(target, set())):
            broken.append((name, href))
    assert broken == []


# --- the build stops rather than lose a row or overwrite a page -------------------------------------

def test_a_flight_without_a_scheduled_time_stops_the_build(tmp_path):
    with pytest.raises(ValueError, match="no final scheduled time"):
        make_site(tmp_path, [(at(6), [row(sched_local="")])])


SNAPS = [{"fetched_at": datetime(2026, 10, 27, 6, 0), "confirmed_until": datetime(2026, 10, 27, 6, 0), "prev": None, "gap_before_s": None}]


def test_two_rows_on_one_anchor_stop_the_build():
    with pytest.raises(ValueError, match="same anchor"):
        build.render([flight("a"), flight("b")], [], SNAPS)  # same number, first time and airport


def test_two_numbers_on_one_page_stop_the_build():
    with pytest.raises(ValueError, match="same page"):
        build.render([flight("a", airline="AB", flight_no="12"), flight("b", airline="A", flight_no="B12")], [], SNAPS)


# --- the pages, end to end -------------------------------------------------------------------------

def test_a_cancellation_reads_the_same_on_the_front_page_and_its_flight_page(site):
    index = read(site, "index.html")
    recent = re.search(r'<tr><td>[^<]*</td><td><a href="flight/IZ991-D.html#2026-10-28-1000-ATH">.*?</tr>', index)
    assert recent.group(0).endswith('<td><span class="pre">Notice given: </span>25+ hours</td></tr>')
    page = read(site, "flight/IZ991-D.html")
    assert '<p class="warn">Cancelled with at least 25 hours&#x27; notice.</p>' in page  # rule 8; the text is escaped
    assert "Between 27 Oct 08:00 and 27 Oct 08:15 Cancelled" in text(page)
    assert '<h3><a href="flight/IZ991-D.html#2026-10-28-1000-ATH">' in index  # the story box
    # IZ 991 is due on 28 October, after the last record: not closed (C4), so not counted yet
    assert ("Since 27 October, 0 of 0 flights at Ben Gurion were cancelled. Not enough flights yet for a percentage."
            in text(index))
    assert '<td><span class="pre">Notice given: </span>25+ hours</td>' in read(site, "cancellations.html")


def test_the_total_counts_closed_flights(tmp_path):
    """The last record is at 08:15 UTC on 29 October, so a flight is closed when it was due by 08:15 UTC on the 27th
    (C4). LY 001, listed as cancelled and due at 08:00 UTC, is closed and counted; LY 002, due at 08:30 UTC, departed
    and its time has passed, but it is not yet closed, so the total leaves it out."""
    ly1, ly2 = dict(sched_local="2026-10-27T10:00:00"), dict(flight_no="002", sched_local="2026-10-27T10:30:00")
    site = make_site(tmp_path, [
        (at(7, 45), [row(**ly1), row(**ly2)]),
        (at(8, 0), [row(**ly1, status="CANCELED"), row(**ly2)]),
        (at(8, 45), [row(**ly1, status="CANCELED"), row(**ly2, status="DEPARTED")]),
        (at(8, 15, day=29), [row(flight_no="003", sched_local="2026-10-30T10:00:00")])])
    assert total_counts(read(site, "index.html")) == (1, 1)


# --- the counts, site-wide (docs/flight-lookup.md, "Tests and checks", words and pages) ---------------

def closing_model() -> list:
    """Records from 07:30 to 09:10 UTC on 26 October, then none until 12:00 UTC on 29 October: a flight due by 12:00
    UTC on the 27th is closed (C4). 26 October holds four flights of five numbers: LY 001 departed; EY 607 and
    LY 9614, one flight (C1), which departed though EY 607 was listed as cancelled (C2); IZ 991, listed as cancelled;
    LY 003, which left the list in the gap (unknown). 27 October holds LY 004, which left in the gap. 28 October holds
    two flights not yet closed: LY 006, which departed, and UA 090 with LY 8090, one flight (C1), whose UA 090 was
    listed as cancelled while LY 8090 is still listed: C2's result is cancelled, C10's label NO NEWS YET (its time
    has passed at the last record). LY 005 is still ahead, on 30 October. No closed flight has a number still listed
    (Question 3's case is left out)."""
    auh = dict(sched_local="2026-10-26T11:00:00", airport="AUH", city_en="ABU DHABI", counters="12-21")
    ey, ly9614 = dict(airline="EY", flight_no="607", **auh), dict(flight_no="9614", **auh)
    iz = dict(airline="IZ", flight_no="991", sched_local="2026-10-26T11:00:00", airport="ATH", city_en="ATHENS",
              counters="34-41")
    ly1, ly3 = dict(sched_local="2026-10-26T10:00:00"), dict(flight_no="003", sched_local="2026-10-26T12:00:00")
    ly6 = dict(flight_no="006", sched_local="2026-10-28T16:00:00", airport="CDG", city_en="PARIS")
    ewr = dict(sched_local="2026-10-28T18:00:00", airport="EWR", city_en="NEWARK", counters="50-55")
    ua, ly8090 = dict(airline="UA", flight_no="090", **ewr), dict(flight_no="8090", **ewr)
    later = [row(flight_no="004", sched_local="2026-10-27T10:00:00"), row(**ly6), row(**ua), row(**ly8090)]
    ly5 = row(flight_no="005", sched_local="2026-10-30T10:00:00")
    return [
        (at(7, 30, day=26), [row(**ly1), row(**ey), row(**ly9614), row(**iz), row(**ly3), *later, ly5]),
        (at(8, 15, day=26), [row(**ly1, status="DEPARTED"), row(**ey, status="CANCELED"), row(**ly9614),
                             row(**iz, status="CANCELED"), row(**ly3), *later, ly5]),
        (at(9, 10, day=26), [row(**ly1, status="DEPARTED"), row(**ey, status="CANCELED"),
                             row(**ly9614, status="DEPARTED"), row(**iz, status="CANCELED"), row(**ly3), *later, ly5]),
        (at(12, 0, day=29), [row(**ly6, status="DEPARTED"), row(**ua, status="CANCELED"), row(**ly8090), ly5])]


def test_the_chart_counts_equal_the_day_pages(tmp_path):
    """The chart counts flights as the day pages do (C1, labelled by C10): 26 October is four flights, not five
    numbers, and EY 607's cancelled listing inside a flight that departed is not a cancelled flight; on 28 October,
    UA 090 with LY 8090 is labelled NO NEWS YET, not cancelled, though C2's result is cancelled."""
    site = make_site(tmp_path, closing_model())
    index, pages = read(site, "index.html"), all_pages(site)
    days = sorted(name[4:14] for name in pages if name.startswith("day/"))
    assert days == ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-30"]
    assert {day: chart_counts(index, day) for day in days} == {day: day_count_line(pages[f"day/{day}.html"])
                                                               for day in days}
    assert chart_counts(index, "2026-10-26") == "4 flights · 1 cancelled · 1 unknown"
    assert chart_counts(index, "2026-10-28") == "2 flights"


def test_over_days_whose_flights_are_all_closed_the_day_pages_sum_to_the_total(tmp_path):
    """26 and 27 October are closed whole at the last record; LY 006 (28 October) has departed but is not closed, and
    LY 005 (30 October) is ahead, so neither day is in the sum and neither flight is in the total. Every closed flight
    is on the two days, so the total is theirs."""
    site = make_site(tmp_path, closing_model())
    table, _, snaps = build.load(tmp_path / "model")
    closed: dict[date, list[bool]] = {}
    for f in counting.flights(table, counting.last_sighting(snaps)):
        closed.setdefault(f.day, []).append(f.closed)
    whole = [day for day, flags in sorted(closed.items()) if all(flags)]
    assert whole == [date(2026, 10, 26), date(2026, 10, 27)]
    assert not any(any(flags) for day, flags in closed.items() if day not in whole)
    pages = all_pages(site)
    counts = [day_counts(pages[f"day/{day}.html"]) for day in whole]
    cancelled, known = sum(c for _, c, _ in counts), sum(n - u for n, _, u in counts)
    assert total_counts(read(site, "index.html")) == (cancelled, known) == (1, 3)


def test_a_closed_flight_still_listed(tmp_path):
    """LY 001 and LY 9614, one flight (C1), were due at 08:00 UTC on 27 October. LY 001 was listed as cancelled and
    LY 9614 is still listed normally at the last record, 48 hours and 15 minutes later: the flight is closed. Its
    label is C10's, NO NEWS YET, and the total counts it as cancelled, by C2 (Question 3). So its day page counts
    no cancelled flight while the total counts one."""
    ly1, ly9614 = dict(sched_local="2026-10-27T10:00:00"), dict(flight_no="9614", sched_local="2026-10-27T10:00:00")
    site = make_site(tmp_path, [(at(7, 45), [row(**ly1), row(**ly9614)]),
                                (at(8, 0), [row(**ly1, status="CANCELED"), row(**ly9614)]),
                                (at(8, 15, day=29), [row(**ly9614)])])
    day = read(site, "day/2026-10-27.html")
    assert re.findall(r'<span class="labels">(.*?)</span></li>', day) == [
        '<span class="label l-no-news-yet">NO NEWS YET</span>']
    assert day_counts(day) == (1, 0, 0)
    assert total_counts(read(site, "index.html")) == (1, 1)


def test_a_fresh_small_model_passes_the_upload_check(tmp_path):
    """Review Focus 3: a model too small to clear the floor anywhere prints no range, says "Not enough flights yet",
    and passes the upload check. Its departures flew but no arrival did, so the delay line, the one figure with no
    floor, has no arrivals' figure to give and is left out: no percentage stands on the page."""
    site = make_site(tmp_path, closing_model())
    upload_check(site)
    pages = all_pages(site)
    assert [name for name, page in pages.items() if "(between" in text(page)] == []
    assert "Not enough flights yet for a percentage." in text(pages["index.html"])
    assert "Chance of a delay" not in text(pages["index.html"]) and "%" not in text(pages["index.html"])


# --- what the build hands to the pages (each page's own words are pinned in tests/test_timeline_views.py) ------------

def test_a_number_listed_as_cancelled_in_a_flight_that_departed_names_the_number_that_did(tmp_path):
    """EY 607 was listed as cancelled; LY 9614, of the same flight (C1), departed. EY 607's page names LY 9614, linked
    to its row; LY 9614's page has no such line. Neither that flight nor UA 090 with LY 8090 (UA 090 listed as
    cancelled, LY 8090 still listed) is in either cancellation list, the front page's recent table or the page of all
    cancellations; IZ 991, listed as cancelled alone, is in both (D4, C10)."""
    site = make_site(tmp_path, closing_model())
    page = read(site, "flight/EY607-D.html")
    assert "This number was cancelled, but the flight probably left as LY 9614." in text(page)
    assert ('probably left as <a href="../flight/LY9614-D.html#2026-10-26-1100-AUH"><span class="d">LY 9614</span></a>.'
            "</p>") in page
    assert "This number" not in text(read(site, "flight/LY9614-D.html"))
    index = read(site, "index.html")
    recent = text(index[index.index("<h2>Recent cancellations</h2>"):index.index('<a href="cancellations.html">')])
    for listed in (recent, text(read(site, "cancellations.html"))):
        assert "IZ 991" in listed and "EY 607" not in listed and "UA 090" not in listed, listed


def first_line(page: str, anchor: str) -> str:
    """A flight page row's first change line, as a reader sees it."""
    row = page[page.index(f'<section class="day" id="{anchor}"'):]
    return text(re.search(r"<li>(.*?)</li>", row).group(1))


def test_the_records_first_list_reads_already_on_the_list(tmp_path, israeli_machine):
    """docs/site-redesign.md, "What changed": LY 001 is in the records' first list (08:00 on 27 October in Israel), LY
    002 first in the list after a hole of 2 hours 45 minutes (11:00), so both were on the airport's list before the
    records could see them: "Already on the list". LY 003, first in the list at 08:15 with nothing missed before it,
    is "First on the list". A model built through model.build: each first record's time is its snapshot's fetch time,
    the first snapshot's or a hole's end (counting.holes), so the pages and the counting rule read the same lists."""
    ly2 = row(flight_no="002", sched_local="2026-10-27T13:00:00")
    ly3 = row(flight_no="003", sched_local="2026-10-28T09:00:00")
    site = make_site(tmp_path, [(at(6), [LY1]), (at(6, 15), [LY1, ly3]), (at(9), [LY1, ly2, ly3])])
    table, obs, snaps = build.load(tmp_path / "model")
    seen = {f["flight_no"]: min(o["observed_at"] for o in obs if o["flight_id"] == f["flight_id"]) for f in table}
    assert [s["fetched_at"] for s in snaps] == [at(6), at(6, 15), at(9)]
    assert [end for _, end in counting.holes(snaps)] == [at(9)]
    assert seen == {"001": snaps[0]["fetched_at"], "002": at(9), "003": snaps[1]["fetched_at"]}
    assert first_line(read(site, "flight/LY001-D.html"), "2026-10-28-1000-JFK") == (
        "Already on the list on 27 Oct at 08:00 on time, terminal 3, check-in desks 1-5, zone A")
    assert first_line(read(site, "flight/LY002-D.html"), "2026-10-27-1300-JFK") == (
        "Already on the list at 11:00 on time, terminal 3, check-in desks 1-5, zone A")
    assert first_line(read(site, "flight/LY003-D.html"), "2026-10-28-0900-JFK") == (
        "First on the list on 27 Oct at 08:15 on time, terminal 3, check-in desks 1-5, zone A")


def test_how_it_works_names_the_frozen_tag_and_the_counting_start(tmp_path, israeli_machine):
    """The tag of the frozen code, linked to that code, and the counting start as its Israel date (record.TAG and
    record.COUNTING_START, 22:00 UTC on 15 November: 00:00 on 16 November in Israel), not the records' first day."""
    page = read(make_site(tmp_path, [(at(6), [LY1]), (at(6, 15), [LY1])]), "how-it-works.html")
    assert '<a href="https://github.com/doronreiffman/flights-archive/tree/record-v1">record-v1</a>' in page
    assert "The rules were fixed beforehand, in the code tagged record-v1." in text(page)
    assert "The counted flights are those first listed from 16 November 2026, the counting start;" in text(page)


def test_a_day_ahead_carries_its_instant_and_its_passed_line_as_of_the_last_sighting(tmp_path, israeli_machine):
    """LY 001, still listed and due at 10:00 on 28 October in Israel, is the traveller's day: its scheduled time stands
    as the UTC instant it is, and its hidden "has passed" line names the last sighting (08:15 on 27 October in Israel),
    not the first record (08:00)."""
    site = make_site(tmp_path, [(at(6), [LY1]), (at(6, 15), [LY1])])
    table, _, snaps = build.load(tmp_path / "model")
    (ly1,) = table
    sched = f"{ly1['sched_utc_final']:%Y-%m-%dT%H:%M:%SZ}"
    assert sched == "2026-10-28T08:00:00Z"
    page = read(site, "flight/LY001-D.html")
    assert f'<div id="now">\n<section class="day" id="2026-10-28-1000-JFK" data-sched="{sched}">' in page
    last = words.il_time(counting.last_sighting(snaps))
    assert f"{last.day} {last:%b} at {last:%H:%M}" == "27 Oct at 08:15"
    assert ('<p class="passed" hidden>This flight&#x27;s time has passed. The page was last updated on 27 Oct at 08:15, '
            "so it may not show what happened.</p>") in page


def test_the_two_not_listed_lines(tmp_path, israeli_machine):
    """docs/flight-lookup.md, "Flight page: other situations", on a model built through model.build, so that each
    number's last sighting is the model's own: with no flight ahead, a number whose last flight the last update still
    lists (its last_seen_at is the last sighting) "has no upcoming flight on the airport's list right now"; one whose
    last flight has left the list "isn't on the airport's list right now". LY 001, due at 08:00 on 27 October in Israel
    (06:00 UTC), is still listed at 06:15 UTC with no news; LY 002, due at 07:00, left the list after 06:00."""
    ly1 = row(sched_local="2026-10-27T08:00:00")
    ly2 = row(flight_no="002", sched_local="2026-10-27T07:00:00")
    site = make_site(tmp_path, [(at(6), [ly1, ly2]), (at(6, 15), [ly1])])
    table, _, snaps = build.load(tmp_path / "model")
    assert {f["flight_no"]: f["last_seen_at"] for f in table} == {"001": counting.last_sighting(snaps), "002": at(6)}
    still, gone = read(site, "flight/LY001-D.html"), read(site, "flight/LY002-D.html")
    for page, number in ((still, "LY 001"), (gone, "LY 002")):
        assert f'<div id="now">\n<p class="none-line"><span class="d">{number}</span> ' in page
        assert '<section class="day"' not in page[page.index('<div id="now">'):page.index('<section class="record">')]
    assert ("LY 001 has no upcoming flight on the airport's list right now. The last one was on Tuesday 27 "
            "October.") in text(still)
    assert "LY 002 isn't on the airport's list right now. The last one was on Tuesday 27 October." in text(gone)
    assert "isn't on" not in text(still) and "has no upcoming" not in text(gone)


def test_the_story_is_the_latest_cancellation_with_a_known_warning(tmp_path):
    """IZ 991 showed cancelled within 15 minutes of its last ON TIME record: a known warning. LY 002, a day later,
    showed cancelled after almost three hours without records, so its warning is only a range, though it has
    more lines."""
    iz = dict(airline="IZ", flight_no="991", sched_local="2026-10-28T10:00:00", airport="ATH", city_en="ATHENS")
    ly = dict(flight_no="002", sched_local="2026-10-29T10:00:00")
    site = make_site(tmp_path, [(at(6), [row(**iz), row(**ly)]),
                                (at(6, 15), [row(**iz, status="CANCELED"), row(**ly, counters="6-9")]),
                                (at(9), [row(**iz, status="CANCELED"), row(**ly, counters="6-9", status="CANCELED")])])
    index = read(site, "index.html")
    start = index.index('<section class="sec story">')
    story = index[start:index.index("</section>", start)]
    assert '<a href="flight/IZ991-D.html#2026-10-28-1000-ATH">' in story


def test_the_story_skips_a_flight_first_listed_after_its_scheduled_time(tmp_path):
    """docs/site-redesign.md, "Front page", item 6 (the owner's decision, 2026-11-17), in a build: LY 002, due at 07:30
    UTC, first appears at 07:45 and is marked cancelled at 08:00, a known warning and the latest cancellation; its
    steps make no sense read aloud, so IZ 991, due at 07:00 and marked cancelled at 06:15, is told instead."""
    iz = dict(airline="IZ", flight_no="991", sched_local="2026-10-27T09:00:00", airport="ATH", city_en="ATHENS")
    ly = dict(flight_no="002", sched_local="2026-10-27T09:30:00")
    quarters = [at(6, 15), at(6, 30), at(6, 45), at(7), at(7, 15), at(7, 30)]
    site = make_site(tmp_path, [(at(6), [row(**iz)]), *((t, [row(**iz, status="CANCELED")]) for t in quarters),
                                (at(7, 45), [row(**iz, status="CANCELED"), row(**ly)]),
                                (at(8), [row(**iz, status="CANCELED"), row(**ly, status="CANCELED")])])
    table, _, _ = build.load(tmp_path / "model")
    late = next(f for f in table if f["flight_no"] == "002")
    assert (late["first_seen_at"], late["sched_utc_final"]) == (at(7, 45), at(7, 30))
    assert late["cancel_lead_censored"] is False  # a known warning: without the skip it would be the story
    index = read(site, "index.html")
    story = index[index.index('<section class="sec story">'):]
    assert re.search(r"<h3><a href=\"([^\"]*)\"", story).group(1) == "flight/IZ991-D.html#2026-10-27-0900-ATH"


def test_the_story_box_is_titled_as_its_flight_page_and_the_search_list(tmp_path):
    """docs/site-redesign.md, "Names": a flight's title is the same on its page, in the search list and in the story
    box. LY 002 was cancelled to Athens on 28 October and is due to Larnaca on 29 October: its page names both, the
    newest first, where its cancelled day alone would read "LY 002 · Tel Aviv to Athens"."""
    ath = dict(flight_no="002", sched_local="2026-10-28T10:00:00", airport="ATH", city_en="ATHENS")
    lca = row(flight_no="002", sched_local="2026-10-29T10:00:00", airport="LCA", city_en="LARNACA")
    site = make_site(tmp_path, [(at(6), [row(**ath), lca]), (at(6, 15), [row(**ath, status="CANCELED"), lca])])
    index, page = read(site, "index.html"), read(site, "flight/LY002-D.html")
    story = index[index.index('<section class="sec story">'):]
    titled = re.search(r'<h3><a href="flight/LY002-D.html#2026-10-28-1000-ATH">(.*?)</a></h3>', story).group(1)
    assert titled == re.search(r"<h1>(.*?)</h1>", page).group(1) == (
        '<span class="d">LY 002 · Tel Aviv to Larnaca or Athens</span>')
    entries = json.loads(re.search(r'id="flights-data">(.*?)</script>', index, re.S).group(1))
    assert [e["t"] for e in entries if e["u"] == "flight/LY002-D.html"] == ["LY 002 · Tel Aviv to Larnaca or Athens"]


def delay_model(listed_late: int) -> tuple[list[dict], list[dict], list[dict]]:
    """100 departures and 100 arrivals, closed and flown, from 7 airlines, 28 October to 3 November, each first listed
    30 hours before its time, so in the rows from 24 hours down; one in ten of each an hour late. `listed_late` more
    departures, never late, first appear an hour before their time and so are in no row: they lower the departures'
    own delay rate and leave the rows' as they are."""
    table, obs = [], []

    def add(i: int, direction: str, number: int, ahead: timedelta, late: bool, airport: str, city: str) -> None:
        sched = datetime(2026, 10, 28, 2) + i * 1.5 * timedelta(hours=1)  # Israel time, UTC+2
        f = flight(f"{direction}{number}", sched, airline="A" + "BCDEFGH"[i % 7], flight_no=str(number),
                   direction=direction, airport=airport, city_en=city,
                   est_local_final=sched + timedelta(minutes=60 if late else 0),
                   first_seen_at=sched - timedelta(hours=2) - ahead, last_seen_at=sched - timedelta(hours=3))
        table.append(f)
        obs.append(first(f, observed_at=f["first_seen_at"]) | {"sched_utc": f["sched_utc_final"],
                                                                "est_utc": f["sched_utc_final"]})

    for i in range(100):
        add(i, "D", 100 + i, timedelta(hours=30), i % 10 == 0, "ATH", "ATHENS")
        add(i, "A", 500 + i, timedelta(hours=30), i % 10 == 0, "ATH", "ATHENS")
    for i in range(listed_late):
        add(i, "D", 800 + i, timedelta(hours=1), False, "LCA", "LARNACA")
    return table, obs, board(datetime(2026, 11, 10))


def test_a_delay_row_off_by_more_than_a_point_stops_the_build():
    """"It's about the same however soon you fly." holds only while every row's delays (where they clear the floor)
    are within a point of their direction's own (the plan's decision): render reads the records once and stops the
    build when one is not. Here departures in the rows run 10% late against 5% for all departures."""
    even = build.render(*delay_model(0))
    assert ("Chance of a delay of an hour or more: about 10% for departures and 10% for arrivals. It's about the same "
            "however soon you fly.") in text(even["index.html"])
    off = delay_model(100)
    airport = blend.records(*off).airport
    assert [(airport.delay[d].cancelled, airport.delay[d].flights) for d in "DA"] == [(10, 200), (10, 100)]
    with pytest.raises(ValueError, match=r"departures in the 24 hours row, 10 of 100"):
        build.render(*off)


def test_no_page_prints_0_percent():
    """docs/flight-lookup.md, "How numbers are written": a chance is never "0%", and no other figure reads so either.
    On a model with no cancelled flight the blend gives exactly zero, which reads "under 1%"."""
    files = build.render(*delay_model(0))
    pages = {name: text(page) for name, page in files.items() if name.endswith(".html")}
    assert [(name, m) for name, page in pages.items() for m in re.findall(r"(?<![\d.])0(?:\.0+)?%", page)] == []
    assert "Chance its next flight is cancelled: under 1%" in pages["flight/AB100-D.html"]


def paired(*numbers: tuple[str, str, str, int]) -> tuple[list[dict], list[dict], list[dict]]:
    """A model of departures to New York, each (airline, number, the partner's airline and number or "", day of
    October at 09:00), every one listed from 30 hours before its time; a partner shares its slot, expected time,
    terminal and desks, so C1 makes them one flight, which C8 groups under the number with the lower digits."""
    table = []
    for airline, number, partner, day in numbers:
        for code, no in [(airline, number), *([partner.split()] if partner else [])]:
            table.append(flight(f"{code}{no}-{day}", datetime(2026, 10, day, 9, 0), airline=code, flight_no=no))
    obs = [first(f, observed_at=f["sched_utc_final"] - timedelta(hours=30)) | {
        "sched_utc": f["sched_utc_final"], "est_utc": f["sched_utc_final"]} for f in table]
    return table, obs, board(datetime(2026, 10, 30, 12, 0))


def test_a_partner_airline_with_no_spoken_name_stops_the_build():
    """Review Focus 2 and Question 5: a partner line always names its airline by its spoken name, so the build stops,
    naming every airline that one needs and that has none, sorted (ZZ 1 groups LY 9001's flight on 27 October, XA 2
    LY 9002's on 28 October). Only the page's airline counts, the traveller's day's or the newest day's: LY 9003,
    grouped under ZZ 3 on 27 October and on its own on 28 October, needs none; nor does QQ 5, whose own page takes the
    "its airline" forms."""
    assert [names.spoken(code) for code in ("ZZ", "XA", "QQ")] == [None] * 3
    with pytest.raises(ValueError, match=r"no spoken name for XA, ZZ\b"):
        build.render(*paired(("ZZ", "1", "LY 9001", 27), ("XA", "2", "LY 9002", 28)))
    files = build.render(*paired(("ZZ", "3", "LY 9003", 27), ("LY", "9003", "", 28), ("QQ", "5", "", 26)))
    assert "is also sold as" not in text(files["flight/LY9003-D.html"])
    assert "Worked out mostly from all airlines at Ben Gurion, because QQ 5 has only 1 flight so far and its airline " \
           "only 1." in text(files["flight/QQ5-D.html"])


def test_how_it_works_reads_the_figures_the_front_page_reads():
    """build.render hands "How this works" the front page's figures (docs/flight-lookup.md, "How this works"): on the
    delay model, 200 closed flights that flew, none cancelled and none left out, each first listed 30 hours before its
    time, so in the rows from 24 hours down; one in ten of each direction an hour late, which clears the floor; the
    records' one list made at 02:00 on 10 November in Israel."""
    model = delay_model(0)
    page = text(build.render(*model)["how-it-works.html"])
    delay = blend.records(*model).airport.delay
    assert ("Among departures that flew, about 10% were delayed an hour or more. Among arrivals, about 10%. "
            "What this can't do yet. This is a simple first version, and the record only goes back to 10 November "
            "2026.") in page
    assert "left out of every figure: 0 so far." in page
    assert "the “3 days away” row holds 0 flights and the “3 hours away” row holds 200." in page
    assert ("Here they all are: All flights: 200 flights · 0 cancelled · Not enough flights yet 3 days away: 0 flights "
            "still on then · 0 cancelled later · Not enough flights yet 2 days away: 0 flights still on then · 0 "
            "cancelled later · Not enough flights yet 1 day away: 200 flights still on then · 0 cancelled later · Not "
            "enough flights yet 12 hours away: 200 flights") in page
    assert words.pct_range(delay["D"]).startswith("10.0% (between ")
    assert (f"Departures delayed an hour or more: {words.pct_range(delay['D'])} Arrivals delayed an hour or more: "
            f"{words.pct_range(delay['A'])} Why the ranges are wide.") in page
    assert "Records start on the evening of 10 November 2026. A flight that left the list" in page


def test_a_pause_of_three_hours(tmp_path):
    """No record between 08:00 and 11:00 Israel time: a flight last seen before the pause has no known outcome."""
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T10:00:00"),
                                         row(flight_no="002", sched_local="2026-10-28T11:00:00")]),
                                (at(9), [row(flight_no="002", sched_local="2026-10-28T11:00:00")])])
    assert "For 1 of these flights, there's no record of how it ended." in text(read(site, "day/2026-10-28.html"))
    assert ("There are no records from 27 October 08:00 to 27 October 11:00."
            in text(read(site, "how-it-works.html")))


def test_days_at_the_edges_of_the_records_are_marked(tmp_path):
    """The records start too late for 26 October, a past day: "some flights missing". They end too early for 31
    October, a later day: "upcoming · not all listed yet" (docs/site-redesign.md, "Front page", item 8)."""
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-26T10:00:00"),
                                         row(flight_no="002", sched_local="2026-10-28T10:00:00"),
                                         row(flight_no="003", sched_local="2026-10-31T10:00:00")])])
    index = read(site, "index.html")
    marks = {day: re.findall(r'<span class="mark">([^<]*)</span>', chart_day(index, day))
             for day in ("2026-10-26", "2026-10-28", "2026-10-31")}
    assert marks == {"2026-10-26": ["some flights missing"], "2026-10-28": ["upcoming"],
                     "2026-10-31": ["upcoming · not all listed yet"]}
    for day in ("2026-10-26", "2026-10-31"):
        assert words.PART_MISSING in text(read(site, f"day/{day}.html"))
    assert "may be missing" not in read(site, "day/2026-10-28.html")


def test_the_chart_shows_the_last_14_days_with_flights_and_every_later_day(tmp_path):
    """Records on 27 October (today); flights from 10 to 30 October, none on 20 or 28 October."""
    days = [d for d in range(10, 31) if d not in (20, 28)]
    site = make_site(tmp_path, [(at(6), [row(flight_no=f"{d:03}", sched_local=f"2026-10-{d}T10:00:00") for d in days])])
    index = read(site, "index.html")
    drawn = re.findall(r'<a href="day/([\d-]+)\.html" class=', chart(index))
    assert drawn == [f"2026-10-{d}" for d in (13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 29, 30)]
    listed = re.findall(r'<a href="day/([\d-]+)\.html">', index[index.index('<div class="pick" id="days">'):])
    assert listed == [f"2026-10-{d}" for d in days]


def test_times_are_israel_time_from_the_first_and_last_records(tmp_path, israeli_machine):
    """The first record, 22:30 UTC on 26 October, is 00:30 on 27 October in Israel; the last, 08:15 on 27 October."""
    site = make_site(tmp_path, [(at(22, 30, day=26), [LY1]), (at(6, 15), [LY1])])
    assert "Based on every flight at Ben Gurion Airport since 27 October." in text(read(site, "index.html"))
    assert "Updated 27 Oct at 08:15" in text(read(site, "index.html"))


def test_text_from_the_airport_is_escaped(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(city_en="<script>alert(1)</script>", sched_local="2026-10-28T10:00:00")])])
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in read(site, "flight/LY001-D.html")
    assert not [name for name, page in all_pages(site).items() if "<script>alert" in page]


# --- the output folder -----------------------------------------------------------------------------

def test_an_output_folder_the_generator_did_not_make_is_never_replaced(tmp_path, site):
    model = tmp_path / "model"
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.txt").write_text("archive copy")
    with pytest.raises(SystemExit, match="not made by timeline.build"):
        build.build(model, precious)
    assert (precious / "keep.txt").read_text() == "archive copy"
    (site / "stale.html").write_text("old")
    build.build(model, site)  # its own output is replaced whole
    assert not (site / "stale.html").exists() and (site / "index.html").exists()


def test_the_same_model_gives_the_same_bytes_in_separate_processes(tmp_path, site):
    model = tmp_path / "model"
    outs = []
    for seed in ("1", "2"):
        out = tmp_path / f"site-{seed}"
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=os.pathsep.join(["src", "tests"]))
        subprocess.run([sys.executable, "-m", "timeline.build", "--model", str(model), "--out", str(out)],
                       check=True, env=env, cwd=Path(__file__).parent.parent, capture_output=True)
        outs.append({p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()})
    assert outs[0] == outs[1] and len(outs[0]) == 17


def test_cli_builds_the_site_and_refuses_a_missing_model(tmp_path, site, capsys):
    out = tmp_path / "cli-site"
    assert build.build(tmp_path / "model", out) == {"days": 1, "flight_pages": 4, "flights": 4}
    assert build.main(["--model", str(tmp_path / "model"), "--out", str(out)]) == 0
    assert f"1 day pages, 4 flight pages, 4 flight numbers -> {out}/index.html" in capsys.readouterr().out
    assert (out / "index.html").exists()
    assert build.main(["--model", str(tmp_path / "nope"), "--out", str(out)]) == 2
    assert "no model under" in capsys.readouterr().err


def test_leftovers_of_an_interrupted_build_are_cleared(tmp_path, site):
    for name in ("site.building", "site.old"):  # a crash before or during the swap
        leftover = tmp_path / name
        leftover.mkdir()
        (leftover / build.MARKER).write_text("")
        (leftover / "junk.html").write_text("half-written")
    build.build(tmp_path / "model", site)
    assert not (tmp_path / "site.building").exists() and not (tmp_path / "site.old").exists()
    assert not (site / "junk.html").exists() and (site / "index.html").exists()


@pytest.mark.parametrize("name", ["site.building", "site.old"])
def test_a_folder_named_like_a_leftover_but_not_ours_is_left_alone(tmp_path, site, name):
    other = tmp_path / name
    other.mkdir()
    (other / "keep.txt").write_text("someone else's")
    with pytest.raises(SystemExit, match="not made by timeline.build"):
        build.build(tmp_path / "model", site)
    assert (other / "keep.txt").read_text() == "someone else's" and (site / "index.html").exists()


def test_the_gap_sentence_and_last_updated_follow_the_receipts(tmp_path):
    """A hole between two snapshots that unchanged downloads bridge is no gap, and the records end at the last download."""
    raw, rec, model, site = tmp_path / "raw", tmp_path / "receipts", tmp_path / "model", tmp_path / "site"
    s1 = write_snapshot(raw, at(6), [LY1])
    write_receipt(rec, s1)
    for when in (at(6, 30), at(7)):
        write_receipt(rec, s1, action="unchanged", when=when)
    s2 = write_snapshot(raw, at(8, 15), [LY1])
    write_receipt(rec, s2)
    write_receipt(rec, s2, action="unchanged", when=at(8, 45))
    model_build.build(raw, model, rec)
    build.build(model, site)
    upload_check(site)
    assert "There are no records from 27 October 09:00 to 27 October 10:15." in text(read(site, "how-it-works.html"))
    assert "Updated 27 Oct at 10:45" in text(read(site, "index.html"))
