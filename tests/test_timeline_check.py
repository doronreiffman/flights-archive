"""The banned-phrase check run on the real site before every upload (docs/publishing.md)."""
import subprocess
import sys
from pathlib import Path

import pytest

from model.report import ATTRIBUTION
from timeline import check
from timeline.pages import UNOFFICIAL

SRC = Path(__file__).parent.parent / "src"
FOOTER = f"<footer><p>{ATTRIBUTION}</p><p>{UNOFFICIAL}</p></footer>"


def make(tmp_path, files):
    site = tmp_path / "site"
    for name, text in files.items():
        path = site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return site


def run_cli(site):
    return subprocess.run([sys.executable, "-m", "timeline.check", str(site)], capture_output=True, text=True,
                          env={"PYTHONPATH": str(SRC)})


@pytest.mark.parametrize("html", [
    "<p>Cancelled at 10:00</p>",
    "<p>cancelled <b>at</b> 10:00</p>",
    "<p>cancelled\n    at 10:00</p>",
    "<p>cancelled&nbsp;at 10:00</p>",
    "<p>took&#32;off</p>",
    "<td>Operated</td> <td>by</td>",
])
def test_a_banned_phrase_is_found_through_case_markup_line_breaks_and_entities(tmp_path, html):
    site = make(tmp_path, {"index.html": "<p>ok</p>", "day/2026-10-28.html": html})
    hits = check.scan(site)
    assert [h[0] for h in hits] == ["day/2026-10-28.html"]


def test_text_in_attributes_is_scanned(tmp_path):
    site = make(tmp_path, {"index.html": '<span title="Cancelled at 10:00">x</span>'})
    assert check.scan(site) == [("index.html", "cancelled at")]


def test_a_comparison_and_an_arrow_in_a_script_cannot_hide_a_phrase(tmp_path):
    script = 'if (q.length < 2) return ""; return "Shows flights delayed by the board"; const run = (x) => x;'
    site = make(tmp_path, {"index.html": "<p>ok</p>", "search.js": script})
    assert check.scan(site) == [("search.js", "delayed by")]


def test_markup_inside_a_script_string_cannot_hide_a_phrase(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>", "search.js": 'el.innerHTML = "Cancelled <b>at</b> " + t;'})
    assert check.scan(site) == [("search.js", "cancelled at")]


def test_scripts_and_styles_are_scanned_too(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>", "search.js": "show('delayed by an hour')", "style.css": "p{}"})
    assert check.scan(site) == [("search.js", "delayed by")]


def test_a_clean_site_passes_and_the_cli_exits_zero(tmp_path):
    site = make(tmp_path, {"index.html": "<p>First observed CANCELED on the public board</p>" + FOOTER, "style.css": "p{}"})
    assert check.scan(site) == []
    done = run_cli(site)
    assert done.returncode == 0, done.stderr


def test_the_cli_names_file_and_phrase_and_exits_one(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>" + FOOTER, "day/x.html": "<p>pause in our collection</p>" + FOOTER})
    done = run_cli(site)
    assert done.returncode == 1
    assert "day/x.html" in done.stderr and "pause in our collection" in done.stderr


@pytest.mark.parametrize("files", [{}, {"style.css": "p{}"}])
def test_a_site_with_no_pages_fails_rather_than_passing_empty(tmp_path, files):
    site = make(tmp_path, files)
    site.mkdir(exist_ok=True)
    with pytest.raises(check.NoPages):
        check.scan(site)
    with pytest.raises(check.NoPages):
        check.missing_notices(site)
    assert run_cli(site).returncode == 2
    assert run_cli(tmp_path / "missing").returncode == 2


def test_main_returns_zero_one_or_two_and_names_hits(tmp_path, capsys):
    clean = make(tmp_path / "a", {"index.html": "<p>ok</p>" + FOOTER})
    dirty = make(tmp_path / "b", {"index.html": "<p>delayed by 5 min</p>" + FOOTER})
    assert check.main([str(clean)]) == 0
    assert check.main([str(dirty)]) == 1 and "index.html: 'delayed by'" in capsys.readouterr().err
    assert check.main([str(tmp_path / "missing")]) == 2 and "no HTML pages" in capsys.readouterr().err


def test_a_page_without_the_source_or_the_unofficial_line_is_named(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>" + FOOTER,
                           "day/a.html": f"<footer><p>{ATTRIBUTION}</p></footer>",
                           "day/b.html": f"<footer><p>{UNOFFICIAL}</p></footer>",
                           "style.css": "p{}"})
    assert check.missing_notices(site) == [("day/a.html", "unofficial line"), ("day/b.html", "source line")]


def test_a_page_with_the_old_footer_does_not_pass(tmp_path):
    old = "Unofficial; not affiliated with the Israel Airports Authority."
    site = make(tmp_path, {"index.html": f"<footer><p>{ATTRIBUTION}</p><p>{old}</p></footer>"})
    assert check.missing_notices(site) == [("index.html", "unofficial line")]


def test_the_notices_count_when_markup_or_a_line_break_splits_them(tmp_path):
    split = UNOFFICIAL.replace("endorsed by", "endorsed\n  <b>by</b>")
    site = make(tmp_path, {"index.html": f"<p>{ATTRIBUTION}</p><p>{split}</p>"})
    assert check.missing_notices(site) == []


def test_the_cli_fails_on_a_missing_notice_and_names_it(tmp_path, capsys):
    site = make(tmp_path, {"index.html": f"<footer><p>{ATTRIBUTION}</p></footer>"})
    assert check.main([str(site)]) == 1
    assert "index.html: missing the unofficial line" in capsys.readouterr().err
