"""The whole timeline site, built from small synthetic models (docs/timeline.md)."""
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from model import build as model_build
from model.report import ATTRIBUTION
from model_helpers import at, row, write_snapshot
from timeline import build
from timeline.check import BANNED

UNOFFICIAL = ("Unofficial; not affiliated with or endorsed by the Israel Airports Authority, "
              "data.gov.il or the State of Israel.")


def make_site(tmp_path, snapshots) -> Path:
    raw, model, site = tmp_path / "raw", tmp_path / "model", tmp_path / "site"
    for when, rows in snapshots:
        write_snapshot(raw, when, rows)
    model_build.build(raw, model)
    build.build(model, site)
    return site


def page(site, day):
    return (site / "day" / f"{day}.html").read_text(encoding="utf-8")


def all_pages(site):
    return {p.relative_to(site).as_posix(): p.read_text(encoding="utf-8") for p in sorted(site.rglob("*.html"))}


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


def test_every_page_cites_the_source_says_unofficial_and_stays_out_of_search_engines(site):
    pages = all_pages(site)
    assert {"index.html", "methodology.html", "day/2026-10-28.html"} <= set(pages)
    for name, text in pages.items():
        assert ATTRIBUTION in text and UNOFFICIAL in text, name
        assert '<meta name="robots" content="noindex">' in text, name


def test_no_page_claims_more_than_the_board_showed(site):
    for name, text in all_pages(site).items():
        low = text.lower()
        assert not [b for b in BANNED if b in low], name


def test_a_cancellation_is_told_as_first_observed_on_the_board(site):
    assert ("First observed CANCELED on the public board between 27 Oct 08:00 and 27 Oct 08:15, "
            "at least 25 h before its scheduled time.") in page(site, "2026-10-28")


def test_the_timeline_shows_old_and_new_values_and_our_first_sighting(site):
    text = page(site, "2026-10-28")
    block = text[text.index('id="LY001-D-20261028-1000-JFK"'):]
    block = block[:block.index("</details>")]
    assert "first seen by us" in block and "estimated time, as published" in block
    assert "<tr><td>27 Oct 08:15</td><td>estimated time, as published: 10:00 → 10:30</td></tr>" in block
    assert "First seen 27 Oct 08:00, last seen 27 Oct 08:15. Seen on 2 stored boards." in block


def test_codeshare_numbers_are_listed_together_never_as_one_aircraft(site):
    text = page(site, "2026-10-28")
    assert "listed together with EY 607 (same slot and check-in counters)" in text
    assert "listed together with LY 9614 (same slot and check-in counters)" in text
    assert "same aircraft" not in text.lower()


def test_hebrew_is_marked_right_to_left(site):
    assert '<span lang="he" dir="rtl">מבוטל</span>' in page(site, "2026-10-28")


def test_every_flight_is_on_exactly_one_day_page_with_unique_anchors(site):
    days = [p for p in all_pages(site) if p.startswith("day/")]
    ids = [i for d in days for i in re.findall(r'<details id="([^"]+)" data-k=', all_pages(site)[d])]
    assert sorted(ids) == ["EY607-D-20261028-1200-JFK", "IZ991-D-20261028-1000-ATH", "LY001-D-20261028-1000-JFK",
                           "LY9614-D-20261028-1200-JFK"]


def test_counts_are_flight_numbers_not_flights(site):
    index = all_pages(site)["index.html"]
    assert "flight numbers listed" in index and re.search(r"2026-10-28.*?4 departures, 0 arrivals", index, re.S)


def test_the_search_box_has_keys_and_stays_hidden_without_javascript(site):
    text = page(site, "2026-10-28")
    assert 'data-k="ly001 ly1 001 1 newyork jfk"' in text
    assert '<input id="search" type="search" hidden' in text and '<script src="../search.js" defer></script>' in text
    assert (site / "search.js").exists() and (site / "style.css").exists()


def test_text_from_the_board_is_escaped(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(city_en="<script>alert(1)</script>", sched_local="2026-10-28T10:00:00")])])
    text = page(site, "2026-10-28")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text and "<script>alert" not in text


def test_days_at_the_archive_edges_are_partial(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-26T10:00:00"), row(flight_no="2", sched_local="2026-10-28T10:00:00"),
                                         row(flight_no="3", sched_local="2026-10-31T10:00:00")])])
    assert "partial" in page(site, "2026-10-26") and "partial" in page(site, "2026-10-31")
    assert "partial" not in page(site, "2026-10-28")
    index = all_pages(site)["index.html"]
    assert re.search(r"2026-10-26\.html.*?<td>partial</td>", index) and re.search(r"2026-10-28\.html.*?<td></td>", index)


def test_a_pause_between_stored_boards_is_shown_in_neutral_words(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T10:00:00")]),
                                (at(9), [row(sched_local="2026-10-28T10:00:00", status="DELAYED")])])
    gap = "No new board stored between 27 Oct 08:00 and 27 Oct 11:00: our collection paused, or the board stopped changing."
    assert gap in page(site, "2026-10-28") and gap in all_pages(site)["index.html"]
    assert "between 27 Oct 08:00 and 27 Oct 11:00</td>" in page(site, "2026-10-28")  # when the change was seen


def test_a_pause_is_shown_only_on_days_whose_board_window_it_touches(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T10:00:00"), row(flight_no="2", sched_local="2026-11-05T10:00:00")]),
                                (at(9), [row(sched_local="2026-10-28T10:00:00", status="DELAYED"),
                                         row(flight_no="2", sched_local="2026-11-05T10:00:00")])])
    assert "No new board stored" in page(site, "2026-10-28") and "No new board stored" not in page(site, "2026-11-05")


def test_a_retime_across_midnight_shows_the_original_date(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T23:30:00")]),
                                (at(6, 15), [row(sched_local="2026-10-29T00:30:00")])])
    assert "(originally 28 Oct 23:30)" in page(site, "2026-10-29") and "retimed: scheduled: 28 Oct 23:30 → 00:30" in page(site, "2026-10-29")
    assert not (site / "day" / "2026-10-28.html").exists()


def test_a_retime_past_midnight_beside_the_next_days_flight_of_the_same_time(tmp_path):
    """A daily 23:30 flight retimed to 00:30 lands on the next day's page beside that day's own 23:30."""
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T23:30:00"), row(sched_local="2026-10-29T23:30:00")]),
                                (at(6, 15), [row(sched_local="2026-10-29T00:30:00"), row(sched_local="2026-10-29T23:30:00")])])
    ids = re.findall(r'<details id="([^"]+)"', page(site, "2026-10-29"))
    assert sorted(ids) == ["LY001-D-20261028-2330-JFK", "LY001-D-20261029-2330-JFK"]


def test_a_number_listed_twice_in_a_day_points_to_the_other_listing(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="KUT"),
                                         row(flight_no="5115", sched_local="2026-10-28T16:30:00", airport="BUS")])])
    text = page(site, "2026-10-28")
    assert "Same number also listed at 16:30 (to KUT)" in text and "Same number also listed at 16:30 (to BUS)" in text


def test_a_flight_without_a_scheduled_time_stops_the_build(tmp_path):
    with pytest.raises(ValueError, match="no final scheduled time"):
        make_site(tmp_path, [(at(6), [row(sched_local="")])])


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
    assert outs[0] == outs[1] and len(outs[0]) >= 5


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_the_search_box_matches_by_prefix_ignoring_case_and_spaces():
    script = Path(__file__).parent.parent / "src" / "timeline" / "static" / "search.js"
    probe = (f"const s = require({str(script)!r});"
             "console.log(JSON.stringify(['LY 1', 'ly001', '6H 115A', 'new york', 'jfk', 'LY2', '', 'ly1 0', 'york', '001', '1'].map("
             "q => s.matches(q, 'ly001 ly1 001 1 newyork jfk'))))")
    out = subprocess.run(["node", "-e", probe], check=True, capture_output=True, text=True).stdout.strip()
    assert out == "[true,true,false,true,true,false,true,false,false,true,true]"


def test_a_retimed_flight_keeps_the_anchor_of_its_first_scheduled_time(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T23:30:00")]),
                                (at(6, 15), [row(sched_local="2026-10-29T00:30:00")])])
    assert '<details id="LY001-D-20261028-2330-JFK"' in page(site, "2026-10-29")


def test_an_anchor_does_not_change_when_the_same_number_appears_again(tmp_path):
    alone = make_site(tmp_path / "a", [(at(6), [row(sched_local="2026-10-28T10:00:00")])])
    twice = make_site(tmp_path / "b", [(at(6), [row(sched_local="2026-10-28T10:00:00"),
                                                row(sched_local="2026-10-28T18:00:00", airport="BUS")])])
    assert '<details id="LY001-D-20261028-1000-JFK"' in page(alone, "2026-10-28")
    assert '<details id="LY001-D-20261028-1000-JFK"' in page(twice, "2026-10-28")


def test_two_flights_sharing_an_anchor_stop_the_build():
    f = {"flight_id": "a", "airline": "LY", "flight_no": "001", "direction": "D", "airport": "JFK",
         "sched_local_first": datetime(2026, 10, 28, 10, 0), "sched_local_final": datetime(2026, 10, 28, 10, 0),
         "codeshare_group_id": "g"}
    snaps = [{"fetched_at": datetime(2026, 10, 27, 6, 0), "prev": None, "gap_before_s": None}]
    with pytest.raises(ValueError, match="share an anchor"):
        build.render([f, f | {"flight_id": "b"}], [], snaps)


def test_cli_builds_the_site_and_refuses_a_missing_model(tmp_path, site, capsys):
    out = tmp_path / "cli-site"
    assert build.main(["--model", str(tmp_path / "model"), "--out", str(out)]) == 0
    assert "1 day pages, 4 flight numbers" in capsys.readouterr().out and (out / "index.html").exists()
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


def test_a_hebrew_field_change_shows_both_values_right_to_left(tmp_path):
    site = make_site(tmp_path, [(at(6), [row(sched_local="2026-10-28T10:00:00", city_he="ניו יורק")]),
                                (at(6, 15), [row(sched_local="2026-10-28T10:00:00", city_he="ניו-יורק")])])
    assert ('city (Hebrew): <span lang="he" dir="rtl">ניו יורק</span> → <span lang="he" dir="rtl">ניו-יורק</span>'
            in page(site, "2026-10-28"))
