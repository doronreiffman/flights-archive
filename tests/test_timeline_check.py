"""The upload check run on the real site before every upload (docs/publishing.md; docs/site-redesign.md,
"Anti-goals", "Footer (every page)" and "Tests and checks")."""
import html
import subprocess
import sys
from pathlib import Path

import pytest

from model.report import ATTRIBUTION
from timeline import check, views, words
from timeline.words import PLACEHOLDER, SOURCE_SHORT, UNOFFICIAL

SRC = Path(__file__).parent.parent / "src"
FOOTER = f"<footer><p>{SOURCE_SHORT} {UNOFFICIAL}</p></footer>"


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


# --- banned phrases --------------------------------------------------------------------------------

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


@pytest.mark.parametrize("text, phrase", [("<p>20 Minutes late</p>", "minutes late"),
                                          ("<p>2 hours\n <b>late</b></p>", "hours late")])
def test_minutes_late_and_hours_late_are_banned(tmp_path, text, phrase):
    site = make(tmp_path, {"index.html": text})
    assert check.scan(site) == [("index.html", phrase)]


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


# --- the built-by placeholder ----------------------------------------------------------------------

@pytest.mark.parametrize("name, text", [
    ("index.html", f"<p>Built by {html.escape(PLACEHOLDER)}</p>"),
    ("day/x.html", f'<meta name="description" content="Built by {html.escape(PLACEHOLDER)}.">'),
    ("how-it-works.html", "<p>Built by [owner&#x27;s\n  wording]</p>"),
    ("search.js", f'const by = "{PLACEHOLDER}";'),
])
def test_the_built_by_placeholder_is_refused_anywhere(tmp_path, name, text):
    site = make(tmp_path, {"index.html": "<p>ok</p>", name: text})
    assert check.scan(site) == [(name, "built-by placeholder")]


def real_pages(tmp_path, monkeypatch, built_by):
    for module in (words, check):
        monkeypatch.setattr(module, "BUILT_BY", built_by)
    return make(tmp_path, {"index.html": views.layout("Flights", "<p>ok</p>", ""),
                           "how-it-works.html": views.how_it_works_page(ATTRIBUTION, [])})


def test_pages_from_the_real_layout_trip_only_the_placeholder(tmp_path, monkeypatch):
    """The real footer meets the notices; until the owner writes the built-by line it holds the placeholder."""
    site = real_pages(tmp_path, monkeypatch, PLACEHOLDER)
    assert check.scan(site) == [("how-it-works.html", "built-by placeholder"), ("index.html", "built-by placeholder")]
    assert check.missing_notices(site) == []


def test_pages_from_the_real_layout_pass_once_the_built_by_line_is_written(tmp_path, monkeypatch):
    site = real_pages(tmp_path, monkeypatch, "Sam Example, who's learning. I'd like to hear from you")
    assert check.scan(site) == []
    assert check.missing_notices(site) == []


# --- we, our, us -----------------------------------------------------------------------------------

@pytest.mark.parametrize("name, text, word", [
    ("day/x.html", "<p>We list flights</p>", "we"),
    ("index.html", "<p>Our list</p>", "our"),
    ("index.html", "<p>Tell US</p>", "us"),
    ("index.html", "<p>first seen by <b>us</b></p>", "us"),
    ("how-it-works.html", "<p>I and we</p>", "we"),
    ("search.js", 'const MORE = " more: ask us";', "us"),
    ("search.js", 'if (a < b) x = "ask us"; const f = (y) => y;', "us"),
    ("style.css", "/* our colours */ p{}", "our"),
])
def test_we_our_and_us_are_found_as_whole_words_in_any_case_in_any_file(tmp_path, name, text, word):
    site = make(tmp_path, {"index.html": "<p>ok</p>", name: text})
    assert check.scan(site) == [(name, word)]


HEADLINE = "So far, 20 of 951 flights with a known outcome were listed as cancelled."
NOT_PRONOUNS = ("were", "hours", "status", "BUS", "AUSTRIAN AIRLINES", "at least 23 hours", HEADLINE, "Ourense", "WEST")


def test_words_that_only_contain_a_pronoun_pass(tmp_path):
    text = " ".join(NOT_PRONOUNS)
    site = make(tmp_path, {"index.html": f"<p>{text}</p>", "search.js": f'const t = "{text}";'})
    assert check.scan(site) == []


def test_the_whole_word_matcher_does_not_find_our_in_hours(tmp_path):
    site = make(tmp_path, {"index.html": "<p>24 hours</p>"})
    assert check.scan(site) == []


# --- I ---------------------------------------------------------------------------------------------

def test_i_is_refused_outside_how_it_works(tmp_path):
    site = make(tmp_path, {"index.html": "<p>I built this</p>", "day/x.html": "<p>I&#x27;m here</p>",
                           "how-it-works.html": "<p>I built a small program.</p>"})
    assert check.scan(site) == [("day/x.html", "I"), ("index.html", "I")]


def test_lower_case_i_and_i_inside_words_pass(tmp_path):
    site = make(tmp_path, {"index.html": "<p>i, Incomplete, AIR INDIA, LY 001 Is</p>"})
    assert check.scan(site) == []


def test_i_is_allowed_in_the_built_by_line(tmp_path, monkeypatch):
    built_by = "Sam Example.\n  I write code & I'm learning"  # escaped on the page, its line break collapsed
    monkeypatch.setattr(check, "BUILT_BY", built_by)
    line = f"<p>Built by {html.escape(built_by)}</p>"
    site = make(tmp_path, {"index.html": line, "day/x.html": line + "<p>I</p>"})
    assert check.scan(site) == [("day/x.html", "I")]


def test_an_empty_built_by_line_removes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "BUILT_BY", "")
    site = make(tmp_path, {"index.html": "<p>Is it</p>"})
    assert check.scan(site) == []


# --- data-collection words -------------------------------------------------------------------------

@pytest.mark.parametrize("text, word", [("board", "board"), ("Boards", "boards"), ("SNAPSHOT", "snapshot"),
                                        ("snapshots", "snapshots"), ("stored", "stored"), ("Observed", "observed"),
                                        ("receipt", "receipt"), ("receipts", "receipts")])
def test_data_collection_words_are_refused_outside_how_it_works(tmp_path, text, word):
    site = make(tmp_path, {"index.html": "<p>ok</p>", "day/x.html": f"<p>the {text}.</p>",
                           "how-it-works.html": f"<p>the {text}.</p>"})
    assert check.scan(site) == [("day/x.html", word)]


def test_words_that_only_contain_a_data_word_pass(tmp_path):
    site = make(tmp_path, {"index.html": "<p>boarding, keyboard, restored, unobserved, earliest record, records</p>"})
    assert check.scan(site) == []


def test_how_it_works_may_say_i_and_name_the_collection(tmp_path):
    page = f"<p>I built a program that checks the board and stored each snapshot.</p><p>{ATTRIBUTION}</p>"
    site = make(tmp_path, {"index.html": "<p>ok</p>", "how-it-works.html": page})
    assert check.scan(site) == []


def test_only_the_top_level_how_it_works_page_is_exempt(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>", "day/how-it-works.html": "<p>I saw the board</p>"})
    assert check.scan(site) == [("day/how-it-works.html", "I"), ("day/how-it-works.html", "board")]


# --- the airport's data (Review Focus 1, ruling 19) ------------------------------------------------

DATA_PAGE = ('<h1><span class="d">US 1, from Our Town to Tel Aviv</span></h1>'
             '<p><span class="d">US-BANGLA AIRLINES</span> · <span class="d">BOARD AIR</span> '
             '<span lang="he" dir="rtl"><span class="d">I WE</span></span></p>'
             '<script type="application/json" id="flights-data">[{"p": ["board", "us"], "t": "WE 1, I"}]</script>')


def test_the_word_rules_skip_the_airports_data(tmp_path):
    site = make(tmp_path, {"index.html": DATA_PAGE})
    assert check.scan(site) == []


def test_the_same_names_outside_the_data_are_found(tmp_path):
    page = '<p class="d">US-BANGLA AIRLINES</p><span class="x">BOARD AIR</span><script>const t = "I WE";</script>'
    site = make(tmp_path, {"index.html": page})
    assert check.scan(site) == [("index.html", "us"), ("index.html", "we"), ("index.html", "I"),
                                ("index.html", "board")]


def test_the_phrase_rules_still_read_the_airports_data(tmp_path):
    page = ('<span class="d">TOOK OFF AIR</span>'
            '<script type="application/json" id="flights-data">[{"t": "LY 1, delayed by"}]</script>')
    site = make(tmp_path, {"index.html": page})
    assert check.scan(site) == [("index.html", "delayed by"), ("index.html", "took off")]


def test_the_word_rules_skip_the_title_and_the_phrase_rules_read_it(tmp_path):
    """A flight page's <title> is its page_title: the airport's data with a few fixed words."""
    site = make(tmp_path, {"index.html": "<title>WE 12, Tel Aviv to US</title><p>ok</p>",
                           "day/x.html": "<title>LY 1, delayed by WE</title><p>ok</p>"})
    assert check.scan(site) == [("day/x.html", "delayed by")]


def test_a_data_span_with_markup_inside_is_read(tmp_path):
    site = make(tmp_path, {"index.html": '<span class="d">US <b>1</b></span>'})
    assert check.scan(site) == [("index.html", "us")]


# --- the whole site --------------------------------------------------------------------------------

def test_a_clean_site_passes_and_the_cli_exits_zero(tmp_path):
    site = make(tmp_path, {"index.html": f"<p>{HEADLINE}</p>" + FOOTER,
                           "how-it-works.html": f"<p>I check the board.</p><p>{ATTRIBUTION}</p>" + FOOTER,
                           "style.css": "p{}"})
    assert check.scan(site) == []
    assert check.missing_notices(site) == []
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
    words = make(tmp_path / "c", {"index.html": "<p>We stored it</p>" + FOOTER})
    assert check.main([str(clean)]) == 0
    assert check.main([str(dirty)]) == 1 and "index.html: 'delayed by'" in capsys.readouterr().err
    assert check.main([str(words)]) == 1
    assert capsys.readouterr().err.splitlines() == ["index.html: 'we'", "index.html: 'stored'"]
    assert check.main([str(tmp_path / "missing")]) == 2 and "no HTML pages" in capsys.readouterr().err


# --- notices ---------------------------------------------------------------------------------------

def test_a_page_without_the_source_or_the_unofficial_line_is_named(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>" + FOOTER,
                           "day/a.html": f"<footer><p>{SOURCE_SHORT}</p></footer>",
                           "day/b.html": f"<footer><p>{UNOFFICIAL}</p></footer>",
                           "style.css": "p{}"})
    assert check.missing_notices(site) == [("day/a.html", "unofficial line"), ("day/b.html", "source line")]


def test_the_full_attribution_is_required_on_how_it_works_only(tmp_path):
    site = make(tmp_path, {"index.html": "<p>ok</p>" + FOOTER, "day/a.html": FOOTER,
                           "how-it-works.html": "<p>How this works</p>" + FOOTER})
    assert check.missing_notices(site) == [("how-it-works.html", "full source line")]
    (site / "how-it-works.html").write_text(f"<p>{ATTRIBUTION}</p>" + FOOTER, encoding="utf-8")
    assert check.missing_notices(site) == []


def test_the_full_attribution_does_not_stand_in_for_the_footer_lines(tmp_path):
    site = make(tmp_path, {"how-it-works.html": f"<p>{ATTRIBUTION}</p>"})
    assert check.missing_notices(site) == [("how-it-works.html", "source line"),
                                           ("how-it-works.html", "unofficial line")]


def test_a_page_with_the_old_footer_does_not_pass(tmp_path):
    old = "Unofficial; not affiliated with the Israel Airports Authority."
    site = make(tmp_path, {"index.html": f"<footer><p>{SOURCE_SHORT}</p><p>{old}</p></footer>"})
    assert check.missing_notices(site) == [("index.html", "unofficial line")]


def test_the_notices_count_when_markup_or_a_line_break_splits_them(tmp_path):
    split = UNOFFICIAL.replace("endorsed by", "endorsed\n  <b>by</b>")
    source = SOURCE_SHORT.replace("published on", "published\n<a href='x'>on</a>")
    site = make(tmp_path, {"index.html": f"<p>{source}</p><p>{split}</p>"})
    assert check.missing_notices(site) == []


def test_the_cli_fails_on_a_missing_notice_and_names_it(tmp_path, capsys):
    site = make(tmp_path, {"index.html": f"<footer><p>{SOURCE_SHORT}</p></footer>"})
    assert check.main([str(site)]) == 1
    assert "index.html: missing the unofficial line" in capsys.readouterr().err
