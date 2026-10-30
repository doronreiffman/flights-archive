"""The whole site, built from small synthetic models through the real model build (docs/site-redesign.md: "Pages",
"How it is built", "Tests and checks")."""
import html
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from model import build as model_build
from model.report import ATTRIBUTION
from model_helpers import at, row, write_snapshot
from test_timeline_flights import flight
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import build, flights, words
from timeline.check import BANNED


def make_site(tmp_path, snapshots) -> Path:
    raw, model, site = tmp_path / "raw", tmp_path / "model", tmp_path / "site"
    for when, rows in snapshots:
        write_snapshot(raw, when, rows)
    model_build.build(raw, model)
    build.build(model, site)
    return site


def read(site, rel):
    return (site / rel).read_text(encoding="utf-8")


def all_pages(site):
    return {p.relative_to(site).as_posix(): p.read_text(encoding="utf-8") for p in sorted(site.rglob("*.html"))}


def text(page: str) -> str:
    """The page as a reader sees it: tags removed, entities unescaped, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", page))).strip()


def chart(page: str) -> str:
    i = page.index('<svg class="chart"')
    return page[i:page.index("\n</svg>", i)]


def chart_day(index: str, day: str) -> str:
    """One day of the front page's chart: its link and everything inside."""
    return re.search(rf'<a href="day/{day}.html"[^>]*>.*?</a>', chart(index), re.S).group(0)


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

def test_the_site_is_the_redesigned_pages_and_nothing_of_v1(site):
    files = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    assert files == {build.MARKER, "index.html", "how-it-works.html", "cancellations.html", "day/2026-10-28.html",
                     "flight/EY607-D.html", "flight/IZ991-D.html", "flight/LY001-D.html", "flight/LY9614-D.html",
                     "search.js", "style.css"}


def test_only_html_css_and_js_besides_the_marker(site):
    odd = [p.name for p in site.rglob("*") if p.is_file() and p.name != build.MARKER
           and p.suffix not in {".html", ".css", ".js"}]
    assert odd == []


def test_every_page_carries_the_footer_notices_and_stays_out_of_search_engines(site):
    pages = all_pages(site)
    assert len(pages) == 8
    for name, page in pages.items():
        assert page.startswith('<!doctype html>\n<html lang="en">'), name
        assert '<meta name="robots" content="noindex">' in page, name
        for notice in (words.SOURCE_SHORT, words.UNOFFICIAL, words.TIMES_NOTE):
            assert notice in text(page), (name, notice)
    assert ATTRIBUTION in text(pages["how-it-works.html"])


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
                       for anchor in re.findall(r'<div class="row" id="([^"]+)">', page)]
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
    assert '<div class="row" id="2026-10-28-2330-JFK">' in page
    assert "Moved to a new scheduled time: 28 Oct 23:30 → 00:30" in text(page)


def test_one_number_leaving_twice_at_one_time_gets_two_anchors_on_one_page(tmp_path):
    """LY 5115 left at 16:30 on 28 October twice, to Kutaisi and to Batumi."""
    site = make_site(tmp_path, [(at(6), [
        row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="KUT", city_en="KUTAISI"),
        row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="BUS", city_en="BATUMI")])])
    ids = re.findall(r'<div class="row" id="([^"]+)">', read(site, "flight/LY5115-D.html"))
    assert sorted(ids) == ["2026-10-28-1630-BUS", "2026-10-28-1630-KUT"]
    day = read(site, "day/2026-10-28.html")
    assert "#2026-10-28-1630-BUS" in day and "#2026-10-28-1630-KUT" in day


# --- the build stops rather than lose a row or overwrite a page -------------------------------------

def test_a_flight_without_a_scheduled_time_stops_the_build(tmp_path):
    with pytest.raises(ValueError, match="no final scheduled time"):
        make_site(tmp_path, [(at(6), [row(sched_local="")])])


SNAPS = [{"fetched_at": datetime(2026, 10, 27, 6, 0), "prev": None, "gap_before_s": None}]


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
    assert recent.group(0).endswith("<td>at least 25 hours</td></tr>")
    page = read(site, "flight/IZ991-D.html")
    assert '<p class="warn">Warning: at least 25 hours.</p>' in page
    assert "Between 27 Oct 08:00 and 27 Oct 08:15 Cancelled" in text(page)
    assert '<h2><a href="flight/IZ991-D.html#2026-10-28-1000-ATH">' in index  # the story box
    assert "So far, 1 of 1 flights with a known outcome were listed as cancelled." in text(index)
    assert "<td>at least 25 hours</td>" in read(site, "cancellations.html")


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
    story = index[index.index('<section class="story">'):index.index("</section>")]
    assert '<a href="flight/IZ991-D.html#2026-10-28-1000-ATH">' in story


def test_a_pause_of_three_hours(tmp_path):
    """No record between 08:00 and 11:00 Israel time: a flight last seen before the pause has no known outcome."""
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T10:00:00"),
                                         row(flight_no="002", sched_local="2026-10-28T11:00:00")]),
                                (at(9), [row(flight_no="002", sched_local="2026-10-28T11:00:00")])])
    assert '<p class="note">No known outcome for 1 of these flights.</p>' in read(site, "day/2026-10-28.html")
    assert ("There are no records from 27 October 08:00 to 27 October 11:00."
            in text(read(site, "how-it-works.html")))


def test_days_at_the_edges_of_the_records_are_incomplete(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-26T10:00:00"),
                                         row(flight_no="002", sched_local="2026-10-28T10:00:00"),
                                         row(flight_no="003", sched_local="2026-10-31T10:00:00")])])
    index = read(site, "index.html")
    for day in ("2026-10-26", "2026-10-31"):  # records start too late for the first, end too early for the last
        assert "incomplete" in text(chart_day(index, day))
        assert "Incomplete: some of this day's flights may be missing" in read(site, f"day/{day}.html")
    assert "incomplete" not in text(chart_day(index, "2026-10-28"))
    assert "Incomplete" not in read(site, "day/2026-10-28.html")


def test_the_chart_shows_the_last_14_days_with_flights_and_every_later_day(tmp_path):
    """Records on 27 October (today); flights from 10 to 30 October, none on 20 or 28 October."""
    days = [d for d in range(10, 31) if d not in (20, 28)]
    site = make_site(tmp_path, [(at(6), [row(flight_no=f"{d:03}", sched_local=f"2026-10-{d}T10:00:00") for d in days])])
    index = read(site, "index.html")
    drawn = re.findall(r'<a href="day/([\d-]+)\.html" class=', chart(index))
    assert drawn == [f"2026-10-{d}" for d in (13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 29, 30)]
    listed = re.findall(r'<a href="day/([\d-]+)\.html">', index[index.index('<p class="days">'):])
    assert listed == [f"2026-10-{d}" for d in days]


def test_times_are_israel_time_from_the_first_and_last_records(tmp_path, israeli_machine):
    """The first record, 22:30 UTC on 26 October, is 00:30 on 27 October in Israel; the last, 08:15 on 27 October."""
    site = make_site(tmp_path, [(at(22, 30, day=26), [LY1]), (at(6, 15), [LY1])])
    assert "Since 27 October: one upcoming." in text(read(site, "flight/LY001-D.html"))
    assert "Last updated 27 Oct 2026, 08:15" in text(read(site, "index.html"))


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
    assert outs[0] == outs[1] and len(outs[0]) == 11


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_the_search_box_matches_by_prefix_ignoring_case_and_spaces():
    script = Path(__file__).parent.parent / "src" / "timeline" / "static" / "search.js"
    probe = (f"const s = require({str(script)!r});"
             "console.log(JSON.stringify(['LY 1', 'ly001', '6H 115A', 'new york', 'jfk', 'LY2', '', 'ly1 0', 'york', '001', '1'].map("
             "q => s.matches(q, 'ly001 ly1 001 1 newyork jfk'))))")
    out = subprocess.run(["node", "-e", probe], check=True, capture_output=True, text=True).stdout.strip()
    assert out == "[true,true,false,true,true,false,true,false,false,true,true]"


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
