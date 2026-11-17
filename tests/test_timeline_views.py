"""The redesigned site's pages (docs/site-redesign.md: "Pages", "Words", "Codeshares", "Names"), from display rows
made with flights.make_rows. Expected values by hand; the how-it-works copy is the plan's Appendix A, verbatim."""
import dataclasses
import html
import json
import re
from collections import Counter
from datetime import date, datetime
from html.parser import HTMLParser

import pytest

from model.report import ATTRIBUTION
from test_timeline_flights import CLEAN, LAST_FETCH, RESUMES, ey_ly, first, flight, lh, local, os_pair, then, utc
from test_timeline_words import A35_ROWS, TO3459_OBS, TOTAL, rate
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import check, counting, display, flights, views, words
from timeline.flights import DayInfo

TO = dict(airline="TO", flight_no="3459", airline_name="TRANSAVIA FRANCE", airport="ORY", city_en="PARIS",
          city_he="פריז")
TO_CANCELLED = dict(outcome="canceled", cancel_lead_min=-142.75, cancel_lead_max_min=-126.75,
                    cancel_lead_censored=False)  # rule 3: "none: listed as cancelled about 2 hours after …"
AT_LEAST_23 = dict(outcome="canceled", cancel_lead_min=1400.95, cancel_lead_max_min=None,
                   cancel_lead_censored=None, uncanceled=None)  # rule 1, IZ 992's shape


def text(page: str) -> str:
    """The page as a reader sees it: tags removed, entities unescaped, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", page))).strip()


def rows(*fs, obs=None):
    """Display rows for these flights; each has only its earliest record unless `obs` is given."""
    return flights.make_rows(list(fs), [first(f) for f in fs] if obs is None else obs, LAST_FETCH, 1, RESUMES)


def lists(*fs, obs=None):
    """The lists' flights (rule C1) of these numbers."""
    return flights.group_flights(rows(*fs, obs=obs), list(fs), LAST_FETCH)


def partners(*fs, obs=None):
    return flights.partners(lists(*fs, obs=obs), list(fs))


def others(*fs, obs=None):
    return flights.others(lists(*fs, obs=obs))


def page_of(*fs, obs=None, only=None, updated=LAST_FETCH):
    """The flight page of these numbers' rows, or of the row with flight_id `only` among them; their flights (C1) are
    made of all of them. `updated` is the last sighting."""
    shown = [r for r in rows(*fs, obs=obs) if only in (None, r.flight_id)]
    return views.flight_page(shown, partners(*fs, obs=obs), others(*fs, obs=obs), updated)


def day_block(page: str, anchor: str) -> str:
    """One day of a flight page, its section from the opening tag to the closing one (sections do not nest)."""
    start = page.index(f'<section class="day" id="{anchor}"')
    return page[start:page.index("</section>", start) + len("</section>")]


@dataclasses.dataclass
class El:
    """An element of a page: its tag, its attributes and its child elements, in page order."""
    tag: str
    attrs: dict
    kids: list

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    @property
    def name(self) -> str:
        """Its id, else its first class, else its tag."""
        return self.attrs.get("id") or (self.classes or [self.tag])[0]

    def walk(self):
        yield self
        for kid in self.kids:
            yield from kid.walk()


VOID = {"br", "hr", "img", "input", "link", "meta", "source", "wbr"}


def tree(page: str) -> El:
    """The page's elements as a tree. A closing tag that does not close the element open last fails the test, so the
    tree is the one a browser builds."""
    root = El("", {}, [])
    stack = [root]

    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            el = El(tag, dict(attrs), [])
            stack[-1].kids.append(el)
            if tag not in VOID:
                stack.append(el)

        def handle_startendtag(self, tag, attrs):
            stack[-1].kids.append(El(tag, dict(attrs), []))

        def handle_endtag(self, tag):
            assert stack[-1].tag == tag, (tag, stack[-1].tag)
            stack.pop()

    Parser().feed(page)
    assert stack == [root]
    return root


def main_of(page: str) -> El:
    (main,) = [el for el in tree(page).walk() if el.tag == "main"]
    return main


def outline(page: str) -> list[tuple[str, list[str]]]:
    """<main>'s children in page order, each by its name, with the ids of the day sections directly inside it."""
    return [(k.name, [d.attrs["id"] for d in k.kids if "day" in d.classes]) for k in main_of(page).kids]


def to3459():
    """TO 3459: departed on 27 October (last expected 17:09), cancelled on 29 October with its real records,
    upcoming on 1 November. Its flights rows, and its records."""
    gone = flight("to27", local(27, 16, 45), est_local_final=local(27, 17, 9), **TO)
    cancelled = flight("to29", local(29, 17, 10), est_local_final=local(29, 18, 45), **TO, **TO_CANCELLED)
    upcoming = flight("to01", datetime(2026, 11, 1, 18, 30), outcome="open", **TO)
    obs = [first(gone), *(o | {"flight_id": "to29", "snap_rn": n} for n, o in enumerate(TO3459_OBS, 1)),
           first(upcoming)]
    return [gone, cancelled, upcoming], obs


def to3459_rows():
    fs, obs = to3459()
    return rows(*fs, obs=obs)


def to3459_page():
    fs, obs = to3459()
    return page_of(*fs, obs=obs)


# LAST_FETCH, 22:02:45 UTC on 29 October, is 00:02 on 30 October in Israel: the instant as itself, the text in
# Israel time
UPDATED = '<p class="updated" data-updated="2026-10-29T22:02:45Z">Updated 30 Oct at 00:02</p>'


def top_line(root: str, front: bool = False, updated: str = UPDATED) -> str:
    """docs/site-redesign.md, "Every page": the site's name linked to the front page (the page's <h1> on the front
    page only), "Tel Aviv airport", and when the page was updated."""
    tag = "h1" if front else "p"
    return (f'<header class="mast">\n<{tag} class="wordmark"><a href="{root}index.html">Will It Fly?</a></{tag}>\n'
            f'<p class="where">Tel Aviv airport</p>\n{updated}\n</header>')


def tiles(page: str) -> list[tuple[str, str]]:
    """The stat tiles as (label, figure) as a reader sees them, in page order."""
    return [(html.unescape(label), text(figure)) for label, figure in re.findall(r"<dt>(.*?)</dt> <dd>(.*?)</dd>", page)]


# --- layout ----------------------------------------------------------------------------------------

def test_layout_head():
    page = views.layout("A <b> & 'c'", "<p>body</p>", "../", LAST_FETCH)
    assert page.startswith('<!doctype html>\n<html lang="en">\n')
    assert '<meta name="robots" content="noindex">' in page
    assert "<title>A &lt;b&gt; &amp; &#x27;c&#x27;</title>" in page
    assert '<link rel="stylesheet" href="../style.css">' in page
    assert "<main>\n<p>body</p>\n</main>" in page


@pytest.mark.parametrize("root", ["", "../"])
@pytest.mark.parametrize("front", [False, True])
def test_layout_top_line(root, front):
    """Every page opens with the top line: the site's name, linked to the front page from the page's own folder, the
    page's <h1> only on the front page; "Tel Aviv airport"; and "Updated" with the last sighting."""
    page = views.layout("t", "<p>body</p>", root, LAST_FETCH, front=front)
    assert top_line(root, front) in page
    assert page.index("<body>") < page.index('<header class="mast">') < page.index("</header>") < page.index("<main>")
    assert page.count("<h1") == front and page.count("<header") == 1
    assert "←" not in page and "Cancelled flights at Tel Aviv airport" not in page


def test_layout_updated_in_israel_time(israeli_machine):
    """The design's example: 07:46 UTC on 17 November is 09:46 in Israel. Without scripts the line reads the date and
    time in Israel time; fromhere.js reads the instant, the model's naive UTC written as the UTC instant it is."""
    page = views.layout("t", "", "", datetime(2026, 11, 17, 7, 46, 12))
    assert '<p class="updated" data-updated="2026-11-17T07:46:12Z">Updated 17 Nov at 09:46</p>' in page
    assert page.count("data-updated") == 1


@pytest.mark.parametrize("root", ["", "../"])
def test_layout_loads_fromhere_js(root):
    """fromhere.js writes the page's age on every page (docs/flight-lookup.md, "Pages", fromhere.js item 3): every page
    loads it, once, deferred, from the page's own folder, in the head."""
    page = views.layout("t", "", root, LAST_FETCH)
    script = f'<script src="{root}fromhere.js" defer></script>'
    assert page.count(script) == 1 and page.index(script) < page.index("</head>")
    assert page.count("<script") == 1


def test_layout_head_extra_goes_in_the_head():
    page = views.layout("t", "", "", LAST_FETCH, head_extra='<meta name="description" content="x">')
    assert page.index('<meta name="description" content="x">') < page.index("</head>")


@pytest.mark.parametrize("page, title", [
    ("day", "Monday 16 November"), ("cancellations", "Cancelled flights"), ("how it works", "How this works")])
def test_each_pages_tab_title(page, title):
    """docs/site-redesign.md, "Every page": the browser tab shows the page's own title."""
    built = {"day": lambda: views.day_page(DayInfo(date(2026, 11, 16), 357, 3, 6, "past", False), [], LAST_FETCH),
             "cancellations": lambda: views.cancellations_page([], LAST_FETCH), "how it works": how}[page]()
    assert re.findall(r"<title>(.*?)</title>", built) == [title]


def test_layout_footer():
    page = views.layout("t", "", "../", LAST_FETCH)
    footer = page[page.index("<footer>"):page.index("</footer>")]
    assert (f"{words.SOURCE_SHORT} {words.UNOFFICIAL} {words.TIMES_NOTE}") in text(footer)
    assert f"{words.ESTIMATES} {words.MEANS}" in text(footer)
    assert f'<a href="../how-it-works.html#{words.MEANS_ANCHOR}">{words.MEANS}</a>' in footer
    assert footer.count("<p>") == 3
    assert '<a href="../how-it-works.html">How this works</a>' in footer
    assert f'<a href="{words.CODE_URL}">Code on GitHub</a>' in footer
    assert f"Built by {words.BUILT_BY}" in text(footer)
    assert footer.index("How this works") < footer.index("Code on GitHub") < footer.index("Built by")


def test_d_escapes_and_marks_data():
    assert views.d("<script>") == '<span class="d">&lt;script&gt;</span>'
    assert views.d(None) == ""


# --- flight page (docs/site-redesign.md, "Flight page"; docs/flight-lookup.md, "Pages", Flight page) ---------------

AHEAD = local(30, 9, 0)  # 07:00 UTC on 30 October, after the last update (22:02 UTC on 29 October): a day ahead
LATER = local(31, 9, 0)
PASSED = ("This flight's time has passed. The page was last updated on 30 Oct at 00:02, so it may not show "
          "what happened.")
SCRIPT = '<script src="../fromhere.js" defer></script>'


def test_flight_page_head():
    page = to3459_page()
    assert "<title>TO 3459 · Tel Aviv to Paris</title>" in page
    assert top_line("../") in page
    assert '<link rel="stylesheet" href="../style.css">' in page


LO = dict(airline="LO", flight_no="155", direction="A", airline_name="LOT POLISH AIRLINES", airport="WAW",
          city_en="WARSAW", city_he="ורשה")


def who(page: str) -> str:
    """The line under the title, as written."""
    return re.search(r'<p class="who">(.*?)</p>', page).group(1)


def test_the_title_and_the_line_under_it():
    """docs/site-redesign.md, "Flight page" and "Names": the title, then the airline as the airport publishes it and,
    when the page has one city, where the flight comes from or goes to ("from Warsaw (WAW)", "to Paris (ORY)") and the
    city in Hebrew, marked as Hebrew. A number with more than one city names its airline alone. "(as the airport lists
    it)" is dropped (round 4)."""
    arrival = page_of(flight("lo", local(29, 19, 45), **LO))
    assert ('<div class="flight-h">\n<h1><span class="d">LO 155 · Warsaw to Tel Aviv</span></h1>\n'
            '<p class="who"><span class="d">LOT POLISH AIRLINES</span> · from <span class="d">Warsaw</span> '
            '(<span class="d">WAW</span>) · <span lang="he" dir="rtl"><span class="d">ורשה</span></span></p>\n'
            "</div>") in arrival
    assert "<title>LO 155 · Warsaw to Tel Aviv</title>" in arrival
    departure = to3459_page()
    assert '<h1><span class="d">TO 3459 · Tel Aviv to Paris</span></h1>' in departure
    assert text(who(departure)) == "TRANSAVIA FRANCE · to Paris (ORY) · פריז"
    assert '<span lang="he" dir="rtl"><span class="d">פריז</span></span>' in who(departure)
    cities = page_of(flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
                     flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI"))
    assert '<h1><span class="d">LY 5115 · Tel Aviv to Batumi or Kutaisi</span></h1>' in cities
    assert who(cities) == '<span class="d">EL AL  ISRAEL AIRLINES</span>'
    for page in (arrival, departure, cities):
        assert "as the airport lists it" not in page and "lands at" not in page and "leaves from" not in page


def test_the_flight_page_order():
    """docs/flight-lookup.md, "Pages", Flight page, "Days ahead": a day is ahead when its scheduled time is later than
    the page's last update. The nearest stands at the top, once, in #now; the strip follows; then the later days ahead,
    soonest first; then the past days, newest first, whatever order the rows come in. 23:55 on 29 October in Israel is
    21:55 UTC, before the last update, so that day is past; 00:30 on 30 October (22:30 UTC) is the nearest ahead."""
    fs = [flight("d28", local(28, 9, 0)), flight("n01", datetime(2026, 11, 1, 9, 0), outcome="open"),
          flight("d27", local(27, 9, 0)), flight("n31", LATER, outcome="open"),
          flight("x29", local(29, 23, 55), outcome="open"), flight("n30", local(30, 0, 30), outcome="open"),
          flight("m30", AHEAD, outcome="open")]
    page = page_of(*fs)
    assert outline(page) == [
        ("flight-h", []), ("now", ["2026-10-30-0030-JFK"]), ("record", []),
        ("later", ["2026-10-30-0900-JFK", "2026-10-31-0900-JFK", "2026-11-01-0900-JFK"]),
        ("past", ["2026-10-29-2355-JFK", "2026-10-28-0900-JFK", "2026-10-27-0900-JFK"])]
    for r in rows(*fs):
        assert page.count(f'id="{r.anchor}"') == 1, r.anchor


MARKED = '<p class="marked"><b>This flight is marked cancelled.</b> Contact your airline.</p>'


def test_a_day_ahead_stays_at_the_top_whatever_its_label():
    """Question 2 and docs/flight-lookup.md, "Pages", Flight page: a day ahead stays the traveller's day whatever its
    label, above a later day still labelled UPCOMING, which keeps the place of its chances. The traveller's day has
    none: marked cancelled, it shows its notice sentence and "This flight is marked cancelled. Contact your airline.";
    removed early, its UNKNOWN line; landed early, a past day's time line. Its hidden "has passed" line comes next."""
    cases = [
        ("D", AT_LEAST_23, "Friday 30 October scheduled to leave at 09:00 CANCELLED Cancelled with at least 23 hours' "
         "notice. It was already cancelled when it first appeared. This flight is marked cancelled. Contact your "
         "airline."),
        ("D", dict(outcome="vanished", last_seen_at=utc(29, 20, 0)),
         "Friday 30 October scheduled to leave at 09:00 UNKNOWN The airport removed this flight 11 hours early without "
         "saying why. It may have been cancelled or moved to another time. Check with your airline."),
        ("A", dict(outcome="landed", est_local_final=local(30, 8, 40)),
         "Friday 30 October scheduled 09:00 · landed around 08:40 LANDED"),
    ]
    for direction, kw, lines in cases:
        page = page_of(flight("top", AHEAD, direction=direction, **kw),
                       flight("later", LATER, direction=direction, outcome="open"))
        assert outline(page)[1:] == [("now", ["2026-10-30-0900-JFK"]), ("record", []),
                                     ("later", ["2026-10-31-0900-JFK"]), ("past", [])], lines
        top = day_block(page, "2026-10-30-0900-JFK")
        assert text(top).startswith(f"{lines} {PASSED}"), text(top)
        assert 'data-sched="2026-10-30T07:00:00Z"' in top and 'class="chances"' not in top
        assert '<div class="chances">' in day_block(page, "2026-10-31-0900-JFK")
        assert (MARKED in top) == (kw is AT_LEAST_23), lines


def test_a_day_ahead_marked_cancelled_while_its_twin_is_still_on():
    """Question 3: LH 0691A is marked cancelled on 31 October while its flight is still on as LH 695. Its day shows
    the CANCELLED label, its notice sentence and the twin line, no chances, and not "This flight is marked cancelled.
    Contact your airline.", which would say the opposite of the twin line."""
    fs = [lh("lh0691a-31", LATER, "0691A", "canceled"), lh("lh695-31", LATER, "695", "open")]
    page = page_of(*fs, only="lh0691a-31")
    assert outline(page)[1] == ("now", ["2026-10-31-0900-FRA"])
    day = day_block(page, "2026-10-31-0900-FRA")
    assert text(day).startswith(
        "Saturday 31 October scheduled to leave at 09:00 CANCELLED Cancelled with at least 6 hours' notice. This "
        f"number is marked cancelled, but the flight is probably still on, as LH 695. {PASSED}"), text(day)
    assert 'class="marked"' not in page and "Contact your airline" not in text(page)
    assert 'class="chances"' not in day


def test_a_number_marked_cancelled_whose_twin_has_no_news_yet():
    """Question 6h: LH 695, due at 23:55 on 29 October, has no news yet at the last update; LH 0691A of its flight was
    marked cancelled. The flight may have gone ahead: "probably still on" is for a twin still ahead."""
    fs = [lh("lh0691a-late", local(29, 23, 55), "0691A", "canceled"), lh("lh695-late", local(29, 23, 55), "695", "open")]
    page = page_of(*fs, only="lh0691a-late")
    assert ('<p class="note">This number was cancelled, but the flight may have gone ahead as '
            '<a href="../flight/LH695-D.html#2026-10-29-2355-FRA"><span class="d">LH 695</span></a>.</p>') in page
    assert "probably still on" not in text(page) and 'class="marked"' not in page


def test_with_no_day_ahead_the_not_listed_line_stands_in_its_place():
    """docs/site-redesign.md, "Flight page", item 3: with no day ahead, #now holds the line saying the number is not on
    the airport's list, with the day of its last flight, and the support; every day is a past day. LY 001's last flight
    was last seen three hours before its time, long before the last update: it is off the list (the model-built case
    of each form is in tests/test_timeline_build.py)."""
    page = page_of(flight("d27", local(27, 9, 0)), flight("d28", local(28, 9, 0)))
    now = [k for k in main_of(page).kids if k.name == "now"][0]
    assert [k.name for k in now.kids] == ["none-line", "support"]
    assert ('<div id="now">\n<p class="none-line"><span class="d">LY 001</span> isn&#x27;t on the airport&#x27;s list '
            "right now. The last one was on Wednesday 28 October.</p>\n") in page
    assert outline(page)[1:] == [("now", []), ("record", []), ("later", []),
                                 ("past", ["2026-10-28-0900-JFK", "2026-10-27-0900-JFK"])]
    still = page_of(flight("d28", local(28, 9, 0), last_seen_at=LAST_FETCH))
    assert ("LY 001 has no upcoming flight on the airport's list right now. The last one was on Wednesday 28 "
            "October.") in text(still)


# The markup contract (the plan's Task 10, "Interfaces"), which the page script reads: each name, where it stands.
CONTRACT_MAIN = ["flight-h", "now", "record", "later", "past"]
CONTRACT_TITLE = ["h1", "who"]
CONTRACT_STRIP = ["h2", "key", "strip"]
CONTRACT_DAY_AHEAD = ["head", "chances", "passed", "support", "own"]  # in this order; chances and support not always
CONTRACT_NONE_AHEAD = ["none-line", "support"]
SCHED = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


def test_the_page_holds_every_name_of_the_contract():
    """The plan's markup contract: <main> holds the title block, #now, the strip, .later and .past, in that order, so
    .later and .past are siblings of #now, and .past stands even with no day in it. Each day ahead (in #now and .later)
    is a section.day with data-sched, a UTC instant, holding its own p.passed (hidden) and .own, last; .chances stands
    on a day labelled UPCOMING only and .support in the top day only, both in the contract's order. A past day carries
    neither data-sched nor p.passed. Every [data-updated] holds text only. With no day ahead, #now holds the not-listed
    line and the support."""
    fs = [flight("up", AHEAD, outcome="open"), flight("gone", LATER, **AT_LEAST_23),
          flight("up2", datetime(2026, 11, 1, 9, 0), outcome="open"), flight("past", local(28, 9, 0))]
    labels = {r.anchor: r.label for r in rows(*fs)}
    pages = {"days ahead and past": page_of(*fs), "no day ahead": page_of(fs[3]),
             "no past day": page_of(fs[0])}
    for name, page in pages.items():
        main = main_of(page)
        assert [k.name for k in main.kids] == CONTRACT_MAIN, name
        title, now, record, later, past = main.kids
        assert [k.name for k in title.kids] == CONTRACT_TITLE, name
        assert [k.name for k in record.kids] == CONTRACT_STRIP, name
        assert all(d.tag == "section" and "day" in d.classes for d in [*later.kids, *past.kids]), name
        if not now.kids or now.kids[0].name == "none-line":
            assert [k.name for k in now.kids] == CONTRACT_NONE_AHEAD and later.kids == [], name
        ahead = [*now.kids, *later.kids] if now.kids[0].tag == "section" else []
        for i, day in enumerate(ahead):
            kids = [k.name for k in day.kids if k.name in CONTRACT_DAY_AHEAD]
            wanted = [n for n in CONTRACT_DAY_AHEAD
                      if (n != "chances" or labels[day.attrs["id"]] == words.UPCOMING) and (n != "support" or i == 0)]
            assert kids == wanted, (name, day.attrs["id"], kids)
            assert day.kids[0].name == "head" and day.kids[-1].name == "own", (name, day.attrs["id"])
            assert SCHED.fullmatch(day.attrs["data-sched"]), day.attrs
            (passed,) = [k for k in day.kids if k.name == "passed"]
            assert "hidden" in passed.attrs
        for day in past.kids:
            assert "data-sched" not in day.attrs and day.kids[-1].name == "own", (name, day.attrs)
            assert not {"passed", "chances", "support"} & {k.name for k in day.kids}, (name, day.attrs)
        updated = [el.kids for el in tree(page).walk() if "data-updated" in el.attrs]
        assert updated and all(kids == [] for kids in updated), name
    assert [len(k.kids) for k in main_of(pages["days ahead and past"]).kids[3:]] == [2, 1]
    assert main_of(pages["no past day"]).kids[4].kids == []


def test_the_scheduled_instant_is_the_models_utc(israeli_machine):
    """data-sched is the day's sched_utc_final, written as the UTC instant it is: 10:00 on 13 November in Israel is
    08:00 UTC, on any machine."""
    page = page_of(flight("up", datetime(2026, 11, 13, 10, 0), outcome="open"))
    assert '<section class="day" id="2026-11-13-1000-JFK" data-sched="2026-11-13T08:00:00Z">' in page


def test_each_day_ahead_holds_its_passed_line_hidden(israeli_machine):
    """docs/flight-lookup.md, "Flight page: other situations": the "has passed" line, with the date and time of the last
    update in Israel time, stands hidden in each day ahead, for the page script to show once the day has passed."""
    page = page_of(flight("up", AHEAD, outcome="open"), flight("up2", LATER, outcome="open"), flight("d", local(28, 9, 0)))
    for anchor in ("2026-10-30-0900-JFK", "2026-10-31-0900-JFK"):
        assert f'<p class="passed" hidden>{html.escape(PASSED)}</p>' in day_block(page, anchor)
    assert 'class="passed"' not in day_block(page, "2026-10-28-0900-JFK")


def test_the_cancelled_row_is_open_with_its_notice_and_changes():
    row = day_block(to3459_page(), "2026-10-29-1710-ORY")
    assert "<details open>" in row
    assert text(row).startswith("Thursday 29 October scheduled to leave at 17:10 CANCELLED")
    assert 'class="marked"' not in row  # "This flight is marked cancelled. Contact your airline." is for a day ahead
    assert "Cancelled with no notice: it was marked cancelled about 2 hours after it should have left." in text(row)
    assert [text(li) for li in re.findall(r"<li>(.*?)</li>", row)] == [
        "Already on the list on 27 Oct at 20:04 on time, terminal 1",
        "Between 27 Oct 20:24 and 14:29 Check-in desks 345-348, zone B",
        "17:32 Expected to leave at 17:38 instead",
        "18:32 Expected to leave at 18:45 instead",
        "Between 19:16 and 19:32 Cancelled",
    ]


def test_other_rows_are_closed():
    page = to3459_page()
    for anchor in ("2026-10-27-1645-ORY", "2026-11-01-1830-ORY"):
        row = day_block(page, anchor)
        assert "<details>" in row and "<details open" not in row


def test_landed_around_beside_the_scheduled_time_and_the_expected_note_once():
    page = to3459_page()
    assert ("Tuesday 27 October scheduled 16:45 · left around 17:09 DEPARTED"
            in text(day_block(page, "2026-10-27-1645-ORY")))
    upcoming = day_block(page, "2026-11-01-1830-ORY")
    assert "around" not in upcoming and "expected 1" not in upcoming
    assert text(page).count(words.EXPECTED_NOTE) == 1  # two rows show a landed-around or expected time


def test_expected_on_a_day_with_no_final_word_and_no_note_without_an_expected_time():
    page = page_of(flight("ahead", outcome="open", est_local_final=local(29, 17, 20)),
                   flight("same", local(30, 16, 45), outcome="open"))
    assert "scheduled 16:45 · expected 17:20 UPCOMING" not in text(page)  # 29 Oct 16:45 Israel time is not ahead
    page = page_of(flight("ahead", local(30, 16, 45), outcome="open", est_local_final=local(30, 17, 20)))
    assert "scheduled 16:45 · expected 17:20 UPCOMING" in text(page) and words.EXPECTED_NOTE in text(page)
    page = page_of(flight("ahead", local(30, 16, 45), outcome="open"))
    assert "scheduled to leave at 16:45 UPCOMING" in text(page) and words.EXPECTED_NOTE not in text(page)


def test_no_expected_note_without_an_expected_time():
    page = page_of(flight("on time", est_local_final=None))
    assert "scheduled to leave at 16:45 DEPARTED" in text(page)
    assert "around" not in text(day_block(page, "2026-10-29-1645-JFK")) and words.EXPECTED_NOTE not in text(page)


def own_of(page: str, anchor: str) -> str:
    """A day's own lines, from its .own block to the end of the day."""
    day = day_block(page, anchor)
    return day[day.index('<div class="own">'):]


def test_the_two_once_a_page_notes_in_their_places():
    """docs/site-redesign.md, "Labels" and "Words": the note on expected times stands once, on the first day in page
    order that shows "expected", "landed around" or "left around", among its own lines and before "What changed"; the
    note on "final" and "not final" stands once, under the first list of changes that is already open and quotes them,
    or, when no open list quotes them, under the first that does."""
    page = page_of(flight("top", AHEAD, outcome="open"),  # no expected time: its own is its scheduled one
                   flight("later", LATER, outcome="open", est_local_final=local(31, 9, 20)),
                   flight("past", local(28, 9, 0), est_local_final=local(28, 9, 10)))
    assert text(page).count(words.EXPECTED_NOTE) == 1
    assert own_of(page, "2026-10-31-0900-JFK").startswith(
        f'<div class="own">\n<p class="note expected">{html.escape(words.EXPECTED_NOTE)}</p>\n<details>')
    page = page_of(flight("top", AHEAD, outcome="open", est_local_final=local(30, 9, 5)),
                   flight("past", local(28, 9, 0), est_local_final=local(28, 9, 10)))
    assert text(page).count(words.EXPECTED_NOTE) == 1
    assert words.EXPECTED_NOTE in text(own_of(page, "2026-10-30-0900-JFK"))

    def quoting(f):
        return first(f) | {"status": "NOT FINAL"}  # “not final” on the first line of what changed

    note = f'</ol>\n<p class="note quoted">{html.escape(words.FINAL_NOTE)}</p>\n</details>'
    fs = [flight("d29", local(29, 9, 0)), flight("c28", local(28, 9, 0), **CLEAN), flight("c27", local(27, 9, 0), **CLEAN)]
    page = page_of(*fs, obs=[quoting(f) for f in fs])  # 29 October's list is closed; 28 and 27 October's are open
    assert text(page).count(words.FINAL_NOTE) == 1 and note in day_block(page, "2026-10-28-0900-JFK")
    fs = [flight("d29", local(29, 9, 0)), flight("d28", local(28, 9, 0)), flight("c27", local(27, 9, 0), **CLEAN)]
    page = page_of(*fs, obs=[quoting(fs[0]), quoting(fs[1]), first(fs[2])])  # the open list does not quote them
    assert text(page).count(words.FINAL_NOTE) == 1 and note in day_block(page, "2026-10-29-0900-JFK")
    assert words.FINAL_NOTE not in text(to3459_page())


def test_a_row_without_records_has_no_details():
    row = day_block(page_of(flight("bare"), obs=[]), "2026-10-29-1645-JFK")
    assert "DEPARTED" in row and "<details" not in row


def label_rows(kinds):
    """One row per label, each on its own day: DEPARTED, LANDED, CANCELLED, UPCOMING (4 November), NO NEWS YET or
    UNKNOWN."""
    made = {words.DEPARTED: {}, words.LANDED: {"outcome": "landed"}, words.CANCELLED: CLEAN,
            words.UPCOMING: {"outcome": "open"}, words.NO_NEWS_YET: {"outcome": "open"},
            words.UNKNOWN: {"outcome": "gap"}}
    fs = []
    for i, kind in enumerate(kinds):
        sched = datetime(2026, 11, 1 + i, 9, 0) if kind == words.UPCOMING else local(1 + i, 9, 0)
        fs.append(flight(f"f{i}", sched, **made[kind]))
    return fs


def test_a_number_with_two_cities():
    """LY 5115 left at 16:30 on 28 October to Kutaisi and to Batumi: both cities in the title, each row its own."""
    page = page_of(flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
                   flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI"))
    assert '<h1><span class="d">LY 5115 · Tel Aviv to Batumi or Kutaisi</span></h1>' in page
    assert text(day_block(page, "2026-10-28-1630-KUT")).startswith(
        "Wednesday 28 October scheduled 16:30 · left around 16:30 to Kutaisi (KUT) DEPARTED")
    assert "to Batumi (BUS)" in text(day_block(page, "2026-10-28-1630-BUS"))
    assert 'lang="he"' not in page


def test_one_city_through_two_airports_names_each_rows_airport():
    paris = dict(flight_no="002", city_en="PARIS", city_he="פריז")
    page = page_of(flight("orly", airport="ORY", **paris), flight("cdg", local(30, 16, 45), airport="CDG", **paris))
    assert '<h1><span class="d">LY 002 · Tel Aviv to Paris</span></h1>' in page
    assert '<span lang="he" dir="rtl"><span class="d">פריז</span></span>' in page
    assert "to Paris (ORY)" in text(day_block(page, "2026-10-29-1645-ORY"))
    assert "to Paris (CDG)" in text(day_block(page, "2026-10-30-1645-CDG"))


def codeshare_page(*numbers):
    """LY 001's page on a day it shares with these (airline, number) partners."""
    fs = [flight("ly", group="g")] + [flight(a + n, airline=a, flight_no=n, group="g") for a, n in numbers]
    return page_of(*fs, only="ly")


LINK = '<a href="../flight/{page}#2026-10-29-1645-JFK"><span class="d">{number}</span></a>'


@pytest.mark.parametrize("numbers, names", [
    ([("LY", "9255")], "LY 9255"),
    ([("LY", "9252"), ("LY", "9255")], "LY 9252 and LY 9255"),
    ([("LY", "9252"), ("LY", "9255"), ("DL", "7426")], "LY 9252, LY 9255 and DL 7426"),
])
def test_also_sold_as_with_one_two_and_three_numbers(numbers, names):
    """docs/site-redesign.md, "Codeshares": one line among the day's own lines, each partner linked to its own page at
    that day's anchor, the reason left to "How this works"."""
    page = codeshare_page(*numbers)
    assert f"Also sold as {names} (probably the same plane)." in text(page)
    links = [LINK.format(page=f"{a}{n}-D.html", number=f"{a} {n}") for a, n in numbers]
    line = f'<p class="note">Also sold as {views._names(links)} (probably the same plane).</p>'
    assert line in own_of(page, "2026-10-29-1645-JFK")
    assert "Probably the same flight" not in page and "same time, terminal" not in page


def test_no_codeshare_line_without_partners():
    page = to3459_page()
    assert '<section class="day" id="2026-10-29-1710-ORY">' in page and "Also sold as" not in page


def test_notes_under_a_row():
    page = page_of(flight("gone", local(28, 9, 0), outcome="vanished", last_seen_at=utc(28, 0, 40)),  # 6 h 20 min
                   flight("back", local(29, 9, 0), uncanceled=True),
                   flight("cancelled", local(30, 9, 0), **AT_LEAST_23))
    assert ("The airport removed this flight 6 hours early without saying why. "
            "It may have been cancelled or moved to another time."
            in text(day_block(page, "2026-10-28-0900-JFK")))
    assert "Marked cancelled for a while, then back on." in text(day_block(page, "2026-10-29-0900-JFK"))
    assert ("Cancelled with at least 23 hours' notice. It was already cancelled when it first appeared."
            in text(day_block(page, "2026-10-30-0900-JFK")))


def test_delayed_beside_the_main_label():
    """An expected time an hour after the scheduled one; the airport's own word DELAYED is not what labels."""
    row = day_block(page_of(flight("late", direction="A", outcome="landed", est_local_final=local(29, 17, 45))),
                    "2026-10-29-1645-JFK")
    assert "LANDED · DELAYED" in text(row) and "scheduled 16:45 · landed around 17:45" in text(row)
    assert ('<span class="labels"><span class="label l-landed">LANDED</span> · '
            '<span class="label l-delayed">DELAYED</span></span>') in row
    row = day_block(page_of(flight("close", direction="A", outcome="landed", est_local_final=local(29, 17, 44))),
                    "2026-10-29-1645-JFK")
    assert "DELAYED" not in text(row)


def test_airport_data_is_escaped():
    page = page_of(flight("x", airline_name="<B>&CO", city_en="<SCRIPT>", city_he="<i>"))
    assert page.count(SCRIPT) == 1  # the page's own script, which every page loads
    assert "<script" not in page.replace(SCRIPT, "").lower() and "<b>&" not in page.lower()
    assert '<span class="d">&lt;B&gt;&amp;CO</span>' in page
    assert '<span class="d">&lt;script&gt;</span>' in page  # string.capwords leaves "<script>" as it is
    assert '<span lang="he" dir="rtl"><span class="d">&lt;i&gt;</span></span>' in page


# --- the strip of days (docs/flight-lookup.md, "Flight page: the strip of days") ---------------------

def strip(page: str) -> str:
    start = page.index('<section class="record">')
    return page[start:page.index("</section>", start) + len("</section>")]


def marks(page: str) -> list[str]:
    return re.findall(r"<li\b.*?</li>", strip(page))


def mark(kind: str, anchor: str, name: str, day: int, month: str | None = None) -> str:
    li = f'<li class="mo" data-mo="{month}">' if month else "<li>"
    return f'{li}<a class="s-{kind}" href="#{anchor}" aria-label="{name}" title="{name}"><i></i><b>{day}</b></a></li>'


def key(page: str) -> str:
    return re.search(r'<p class="key">(.*?)</p>', page).group(1)


def test_the_strip_marks_every_day_oldest_first_and_links_it():
    """Under the heading "TO 3459, day by day", one mark per day of the number, oldest first, each a link to that day
    on the page (the traveller's day's to the top), named by its day and label for a screen reader and as a tooltip,
    the day of the month under it. Each label has its own mark."""
    page = to3459_page()
    assert '<section class="record">\n<h2><span class="d">TO 3459</span>, day by day</h2>\n' in page
    assert marks(page) == [
        mark("departed", "2026-10-27-1645-ORY", "Tuesday 27 October, departed", 27, "Oct"),
        mark("cancelled", "2026-10-29-1710-ORY", "Thursday 29 October, cancelled", 29),
        mark("upcoming", "2026-11-01-1830-ORY", "Sunday 1 November, upcoming", 1, "Nov")]
    assert outline(page)[1] == ("now", ["2026-11-01-1830-ORY"])
    every = page_of(*label_rows(words.LABEL_ORDER))
    found = re.findall(r'<a class="s-([a-z-]+)" href="#([^"]+)" aria-label="([^"]+)"', strip(every))
    assert [(kind, name) for kind, _, name in found] == [
        ("departed", "Thursday 1 October, departed"), ("landed", "Friday 2 October, landed"),
        ("cancelled", "Saturday 3 October, cancelled"), ("no-news-yet", "Monday 5 October, no news yet"),
        ("unknown", "Tuesday 6 October, unknown"), ("upcoming", "Wednesday 4 November, upcoming")]
    days = [el.attrs["id"] for el in tree(every).walk() if "day" in el.classes]
    assert sorted(anchor for _, anchor, _ in found) == sorted(days) and len(days) == 6


def test_the_strip_key_counts_its_own_marks():
    """The key names each kind of mark in words with its count, in the labels' order, each beside its mark, so that it
    matches the marks (LH 694's "landed 10 · cancelled 4 · unknown 1"); a kind with no mark is left out."""
    arrival = dict(direction="A", airline="LH", flight_no="694", airport="FRA", city_en="FRANKFURT")
    fs = [*(flight(f"l{d}", local(d, 19, 20), outcome="landed", **arrival) for d in (20, 21, 22)),
          *(flight(f"c{d}", local(d, 19, 20), **CLEAN, **arrival) for d in (23, 24)),
          flight("u25", local(25, 19, 20), outcome="gap", **arrival)]
    page = page_of(*fs)
    assert key(page) == ('<span class="k s-landed">landed 3</span><span class="sep"> · </span>'
                         '<span class="k s-cancelled">cancelled 2</span><span class="sep"> · </span>'
                         '<span class="k s-unknown">unknown 1</span>')
    assert '<section class="record">\n<h2><span class="d">LH 694</span>, day by day</h2>\n<p class="key">' in page
    assert Counter(re.findall(r'<a class="s-([a-z-]+)"', strip(page))) == {"landed": 3, "cancelled": 2, "unknown": 1}


def test_two_flights_on_one_day_are_two_marks():
    """Review Focus 5: one mark per row of the model's flights table, not per date. LY 5115 left twice at 16:30 on 28
    October, to Batumi and to Kutaisi; IZ 992 is listed twice on 30 October. Each row has its own mark, linked to its
    own day, and the key counts both."""
    page = page_of(flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
                   flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI"))
    assert marks(page) == [mark("departed", "2026-10-28-1630-BUS", "Wednesday 28 October, departed", 28, "Oct"),
                           mark("departed", "2026-10-28-1630-KUT", "Wednesday 28 October, departed", 28)]
    assert text(key(page)) == "departed 2"
    iz = dict(airline="IZ", flight_no="992", airport="ATH", city_en="ATHENS")
    page = page_of(flight("iz2", local(30, 13, 50), outcome="open", **iz),
                   flight("iz1", local(30, 6, 50), outcome="open", **iz))
    assert [re.search(r'href="#([^"]+)"', m).group(1) for m in marks(page)] == [
        "2026-10-30-0650-ATH", "2026-10-30-1350-ATH"]
    assert text(key(page)) == "upcoming 2"


def test_the_months_name_over_its_first_mark():
    """A month's name stands over the first mark of each month and over no other: the page's first mark, whatever its
    day, and 1 November's."""
    page = page_of(*(flight(f"o{d}", local(d, 9, 0)) for d in (29, 30, 31)),
                   *(flight(f"n{d}", datetime(2026, 11, d, 9, 0), outcome="open") for d in (1, 2)))
    assert [re.match(r"<li[^>]*>", m).group(0) for m in marks(page)] == [
        '<li class="mo" data-mo="Oct">', "<li>", "<li>", '<li class="mo" data-mo="Nov">', "<li>"]


# --- the twin lines (docs/flight-lookup.md, "Flight page: other situations") -------------------------

def test_the_twin_lines():
    """docs/flight-lookup.md, "Flight page: other situations": a number marked cancelled whose flight is not (C2, C10)
    names the flight's numbers that departed, landed or are still listed, each linked to its row and joined as "Also
    sold as" joins them. A number that shares the time, terminal and desks keeps its "Also sold as" line too. The
    flight's other numbers, and a cancelled flight's, get no such line."""
    fs = [lh("lh0691a", local(29, 9, 0), "0691A", "canceled"), lh("lh695", local(29, 9, 0), "695")]
    page = page_of(*fs, only="lh0691a")
    assert "This number was cancelled, but the flight probably left as LH 695." in text(page)
    assert ('<p class="note">This number was cancelled, but the flight probably left as '
            '<a href="../flight/LH695-D.html#2026-10-29-0900-FRA"><span class="d">LH 695</span></a>.</p>') in page
    assert "Also sold as LH 695 (probably the same plane)." in text(page)
    two = page_of(*fs, lh("lh697", local(29, 9, 0), "697"), only="lh0691a")
    assert "but the flight probably left as LH 695 and LH 697." in text(two)
    landed = page_of(*os_pair(), only="os1083")
    assert "This number was cancelled, but the flight probably landed as OS 083." in text(landed)
    assert ('probably landed as <a href="../flight/OS083-A.html#2026-10-29-1400-VIE"><span class="d">OS 083</span>'
            "</a>.</p>") in landed
    ahead = page_of(lh("lh0691a-31", local(31, 9, 0), "0691A", "canceled"),
                    lh("lh695-31", local(31, 9, 0), "695", "open"), only="lh0691a-31")
    assert "This number is marked cancelled, but the flight is probably still on, as LH 695." in text(ahead)
    assert ('still on, as <a href="../flight/LH695-D.html#2026-10-31-0900-FRA"><span class="d">LH 695</span></a>.'
            "</p>") in ahead
    for other in (page_of(*fs, only="lh695"), page_of(*ey_ly(), only="ey")):
        assert "This number" not in text(other)


def test_the_partner_sentence_names_only_time_terminal_and_desks_partners():
    """docs/flight-lookup.md, "Words": the partner sentence names the numbers that share the time, terminal and
    check-in desks, whatever their own label (AF 8350 left the list during a hole). OS 1083, joined to OS 083's flight
    by airline alone (C1) at another expected time, is neither's partner: it gets the twin line."""
    desks = dict(counters_final="78-99", group="g")
    fs = [*os_pair(), flight("ly003", local(29, 9, 0), flight_no="003", **desks),
          flight("dl", local(29, 9, 0), airline="DL", flight_no="7426", **desks),
          flight("am", local(29, 9, 0), airline="AM", flight_no="7895", **desks),
          flight("af", local(29, 9, 0), airline="AF", flight_no="8350", outcome="gap", **desks)]
    assert "Also sold as DL 7426, AM 7895 and AF 8350 (probably the same plane)." in text(page_of(*fs, only="ly003"))
    for fid in ("os083", "os1083"):
        assert "Also sold as" not in text(page_of(*fs, only=fid)), fid
    assert "the flight probably landed as OS 083." in text(page_of(*fs, only="os1083"))


def test_every_flight_page_loads_fromhere_js_once():
    """The script writes the page's age and keeps an old page reading right, so it loads, once, on a flight page with
    a day ahead and on one without."""
    for page in (page_of(flight("up", AHEAD, outcome="open")),
                 page_of(*label_rows([words.DEPARTED, words.CANCELLED, words.NO_NEWS_YET, words.UNKNOWN]))):
        assert page.count(SCRIPT) == 1 and page.index(SCRIPT) < page.index("</head>")
        assert "<script" not in page.replace(SCRIPT, "")


# --- day page --------------------------------------------------------------------------------------

DAY = date(2026, 10, 29)


def day_flights():
    fs = [flight("in", local(29, 5, 0), flight_no="002", direction="A", outcome="landed"),
          flight("late", local(29, 20, 0), flight_no="003"),
          flight("to", local(29, 17, 10), **TO, **TO_CANCELLED),
          flight("dl", local(29, 9, 0), airline="DL", flight_no="7426", group="g"),
          flight("am", local(29, 9, 0), airline="AM", flight_no="7895", group="g")]
    return lists(*fs)


def day_page(total=418, cancelled=7, unknown=190, partial=True, day=DAY, flights_=None):
    return views.day_page(DayInfo(day, total, cancelled, unknown, "past", partial),
                          day_flights() if flights_ is None else flights_, LAST_FETCH)


MONDAY = date(2026, 11, 16)  # the design's day
PART_MISSING = "Some flights from this day may be missing: the records don't cover the whole day."


def test_day_page_head():
    """docs/site-redesign.md, "Day page", top to bottom: the title with its counts, the partial-day line and the
    unknown line, each under the one before; the date alone in the browser tab."""
    page = day_page()
    assert "<title>Thursday 29 October</title>" in page
    assert top_line("../") in page
    lines = [text(inner) for inner in re.findall(r"<(?:h1|p)[^>]*>(.*?)</(?:h1|p)>", section(page, "<main>", "<h2>"))]
    assert lines == ["Thursday 29 October · 418 flights · 7 cancelled", PART_MISSING,
                     "For 190 of these flights, there's no record of how they ended."]
    assert f'<p class="note">{html.escape(PART_MISSING)}</p>' in page
    assert '<link rel="stylesheet" href="../style.css">' in page
    assert "<dl" not in page and 'class="count"' not in page  # the title carries the counts


@pytest.mark.parametrize("total, cancelled, title", [
    (357, 3, "Monday 16 November · 357 flights · 3 cancelled"),
    (357, 0, "Monday 16 November · 357 flights"),
    (1, 1, "Monday 16 November · 1 flight · 1 cancelled"),  # Question 6f
    (1, 0, "Monday 16 November · 1 flight"),
])
def test_the_day_title_leaves_out_a_zero(total, cancelled, title):
    page = day_page(total, cancelled, day=MONDAY)
    assert f"<h1>{title}</h1>" in page
    assert re.findall(r"<title>(.*?)</title>", page) == ["Monday 16 November"]


@pytest.mark.parametrize("unknown, line", [
    (6, "For 6 of these flights, there's no record of how they ended."),
    (1, "For 1 of these flights, there's no record of how it ended."),  # Question 6f
])
def test_the_unknown_line(unknown, line):
    """"Unknown" counts the UNKNOWN label only; each flight page's label note gives its reason."""
    assert f'<p class="note">{html.escape(line)}</p>' in day_page(unknown=unknown)


def test_day_page_without_partial_or_unknown_lines():
    """A count of 0 leaves its line out (Question 6f), and a whole day has no partial-day line."""
    page = text(day_page(unknown=0, partial=False))
    assert "Thursday 29 October · 418 flights · 7 cancelled" in page and "TO 3459" in page
    assert "may be missing" not in page and "no record of how" not in page


def test_the_empty_lists():
    """A direction with no flight that day says so under its heading."""
    only_arrivals = text(day_page(1, 0, 0, False, flights_=lists(
        flight("in", local(29, 5, 0), flight_no="002", direction="A", outcome="landed"))))
    assert "Departures No departures recorded. Arrivals 05:00 LY 002 from New York (JFK) LANDED" in only_arrivals
    assert "No arrivals recorded." not in only_arrivals
    only_departures = text(day_page(1, 0, 0, False, flights_=lists(flight("out", local(29, 20, 0), flight_no="003"))))
    assert "Departures 20:00 LY 003 to New York (JFK) DEPARTED Arrivals No arrivals recorded." in only_departures
    assert "No departures recorded." not in only_departures
    page = day_page(0, 0, 0, False, flights_=[])
    assert ('<h2>Departures</h2>\n<p>No departures recorded.</p>\n<h2>Arrivals</h2>\n<p>No arrivals recorded.</p>'
            in page)


def test_day_page_departures_then_arrivals_in_scheduled_order():
    page = text(day_page())
    order = ["Departures", "09:00 DL 7426, AM 7895 to New York (JFK) DEPARTED",
             "17:10 TO 3459 to Paris (ORY) CANCELLED Cancelled with no notice: it was marked cancelled about 2 hours "
             "after it should have left.", "20:00 LY 003 to New York (JFK) DEPARTED",
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
    assert "on the list" not in text(page) and "<details" not in page


def bracket_day():
    """Two flights to Frankfurt (C1), both DEPARTED (C10). At 09:00, LH 0691A and LH 0693A, listed as cancelled, beside
    LH 695 and LH 697, which departed; in row order LH 0691A comes first, so it is the flight's first row. At 11:00,
    the design's own case: LH 0691A, listed as cancelled, beside LH 695, which departed."""
    fs = [lh("lh0691a", local(29, 9, 0), "0691A", "canceled"), lh("lh0693a", local(29, 9, 0), "0693A", "canceled"),
          lh("lh695", local(29, 9, 0), "695"), lh("lh697", local(29, 9, 0), "697"),
          lh("lh0691a-11", local(29, 11, 0), "0691A", "canceled"), lh("lh695-11", local(29, 11, 0), "695")]
    return views.day_page(DayInfo(DAY, 2, 0, 0, "past", False), lists(*fs), LAST_FETCH)


def test_the_bracket_in_a_list_row():
    """docs/flight-lookup.md, "In lists": a number whose own status differs from its flight's is named in brackets,
    "(LH 0691A: cancelled)", one bracket each, after the flight's other numbers and before the route; the row takes
    the flight's label, not its first row's."""
    page = bracket_day()
    assert "11:00 LH 695 (LH 0691A: cancelled) to Frankfurt (FRA) DEPARTED" in text(page)
    assert ("09:00 LH 695, LH 697 (LH 0691A: cancelled) (LH 0693A: cancelled) to Frankfurt (FRA) DEPARTED"
            in text(page))
    assert ('(<a href="../flight/LH0691A-D.html#2026-10-29-1100-FRA"><span class="d">LH 0691A</span></a>: cancelled)'
            in page)
    assert "is listed as cancelled" not in page
    assert "CANCELLED" not in text(page)
    for number in ("695", "697", "0691A", "0693A"):
        assert f'<a href="../flight/LH{number}-D.html#2026-10-29-0900-FRA"><span class="d">LH {number}</span></a>' in page


def test_a_flight_that_departed_shows_no_warning_in_a_list_row():
    """The flight's first row, LH 0691A, has a warning of its own (at least 6 hours); the flight departed, so its row
    shows none: a list row's warning is a cancelled flight's (C9)."""
    row = re.search(r"<li>.*?</li>", bracket_day()).group(0)
    assert "LH 0691A" in text(row)
    assert "Warning" not in row and 'class="warn"' not in row


# --- all cancellations -----------------------------------------------------------------------------

def cells(page: str) -> list[list[str]]:
    return [[text(c) for c in re.findall(r"<t[hd]>(.*?)</t[hd]>", tr)] for tr in re.findall(r"<tr>(.*?)</tr>", page)]


def cancellations_page():
    """Three cancelled flights among others. LH 0691A, listed as cancelled beside LH 695, which departed, and the same
    pair on 31 October with LH 695 still listed, are not cancelled flights (docs/flight-lookup.md, D4 and C10)."""
    fs = [flight("to", local(29, 17, 10), **TO, **TO_CANCELLED),
          flight("departed", local(29, 18, 0)),
          flight("iz", local(30, 13, 50), airline="IZ", flight_no="992", direction="A", **AT_LEAST_23),
          flight("ey", local(28, 9, 0), airline="EY", flight_no="607", group="g", **CLEAN),
          flight("ly", local(28, 9, 0), airline="LY", flight_no="9614", group="g", **CLEAN),
          lh("lh0691a", local(29, 20, 0), "0691A", "canceled"), lh("lh695", local(29, 20, 0), "695"),
          lh("lh0691a-31", local(31, 9, 0), "0691A", "canceled"), lh("lh695-31", local(31, 9, 0), "695", "open")]
    return views.cancellations_page(lists(*fs), LAST_FETCH)


CANCELLED_UNDER = ("“Notice given” is how long before the scheduled time the airport marked the flight cancelled. "
                   "Airlines may tell passengers sooner.")


def test_the_cancelled_flights_page_head():
    """docs/site-redesign.md, "Cancelled flights": the title, the introduction and the line under it, then the table."""
    page = cancellations_page()
    assert "<title>Cancelled flights</title>" in page and top_line("") in page
    lines = [text(inner) for inner in re.findall(r"<(?:h1|p)[^>]*>(.*?)</(?:h1|p)>",
                                                 section(page, "<main>", '<div class="table-card">'))]
    assert lines == ["Cancelled flights", "Every cancelled flight since 27 October, newest first.", CANCELLED_UNDER]
    assert f'<p class="note">{html.escape(CANCELLED_UNDER)}</p>' in page


def test_cancellations_newest_first():
    """Only the flights labelled CANCELLED: neither LH flight, though each is newer than TO 3459. The columns are
    Date · Flight · Route · Notice given, and each notice is the list form, led on a phone by "Notice given: "."""
    page = cancellations_page()
    assert cells(page) == [
        ["Date", "Flight", "Route", "Notice given"],
        ["Fri 30 Oct", "IZ 992", "New York (JFK) to Tel Aviv, scheduled to land at 13:50", "Notice given: 23+ hours"],
        ["Thu 29 Oct", "TO 3459", "Tel Aviv to Paris (ORY), scheduled to leave at 17:10", "Notice given: none"],
        ["Wed 28 Oct", "EY 607, LY 9614", "Tel Aviv to New York (JFK), scheduled to leave at 09:00",
         "Notice given: 6+ hours"],
    ]
    assert "LH 0691A" not in text(page) and "LH 695" not in text(page)


def test_the_route_and_the_phone_prefix():
    """The design's row: WZ 016, cancelled with no notice. The phone prefix stands in its own span, so the sheet can
    show it only where the table stacks and its column heads are hidden."""
    wz = flight("wz", datetime(2026, 11, 17, 5, 35), airline="WZ", flight_no="016", airport="ZIA", city_en="MOSCOW",
                **TO_CANCELLED)
    page = views.cancellations_page(lists(wz), LAST_FETCH)
    assert cells(page)[1] == ["Tue 17 Nov", "WZ 016", "Tel Aviv to Moscow (ZIA), scheduled to leave at 05:35",
                              "Notice given: none"]
    assert '<td><span class="pre">Notice given: </span>none</td></tr>' in page


@pytest.mark.parametrize("lead, short", [
    (dict(cancel_lead_min=1400.95, cancel_lead_max_min=None, cancel_lead_censored=None), "23+ hours"),  # rule 1
    (dict(cancel_lead_min=30.0, cancel_lead_max_min=None, cancel_lead_censored=None), "unknown"),  # rule 2
    (dict(cancel_lead_min=-142.75, cancel_lead_max_min=-126.75, cancel_lead_censored=False), "none"),  # rule 3
    (dict(cancel_lead_min=420.0, cancel_lead_max_min=2995.0, cancel_lead_censored=True), "7 to 50 hours"),  # rule 5
    (dict(cancel_lead_min=30.0, cancel_lead_max_min=290.0, cancel_lead_censored=True), "up to 5 hours"),  # rule 6
    (dict(cancel_lead_min=60.0, cancel_lead_max_min=76.0, cancel_lead_censored=False), "1+ hours"),  # rule 8
    (dict(cancel_lead_min=10.0, cancel_lead_max_min=26.0, cancel_lead_censored=False), "under an hour"),  # rule 9
    (dict(cancel_lead_min=50.0, cancel_lead_max_min=66.0, cancel_lead_censored=False), "about an hour"),  # rule 10
    (dict(cancel_lead_min=-5.0, cancel_lead_max_min=11.0, cancel_lead_censored=False), "almost none"),  # rule 11
])
def test_the_list_forms_of_the_notice(lead, short):
    """docs/site-redesign.md, "Notice": under "Notice given" a list shows the short form, never the sentence."""
    page = views.cancellations_page(lists(flight("c", local(29, 9, 0), outcome="canceled", **lead)), LAST_FETCH)
    assert cells(page)[1][-1] == f"Notice given: {short}"
    assert f'<span class="pre">Notice given: </span>{html.escape(short)}</td>' in page


def test_cancellations_link_each_number_to_its_row():
    page = cancellations_page()
    for href in ("flight/IZ992-A.html#2026-10-30-1350-JFK", "flight/TO3459-D.html#2026-10-29-1710-ORY",
                 "flight/EY607-D.html#2026-10-28-0900-JFK", "flight/LY9614-D.html#2026-10-28-0900-JFK"):
        assert f'<a href="{href}">' in page
    assert '<link rel="stylesheet" href="style.css">' in page


def test_no_cancellations_yet():
    page = views.cancellations_page(lists(flight("departed")), LAST_FETCH)
    assert "<table" not in page and '<p>No cancelled flights so far.</p>' in page


def test_cancellations_show_c9s_notice():
    """EY 607 and LY 9614, one cancelled flight (C1): LY 9614 was listed as cancelled first, so the lists show its
    notice, 23+ hours, not that of EY 607, the first row (6+ hours)."""
    fl = lists(*ey_ly())
    assert cells(views.cancellations_page(fl, LAST_FETCH))[1] == [
        "Thu 29 Oct", "EY 607, LY 9614", "Tel Aviv to New York (JFK), scheduled to leave at 09:00",
        "Notice given: 23+ hours"]
    day = views.day_page(DayInfo(DAY, 1, 1, 0, "past", False), fl, LAST_FETCH)
    assert "09:00 EY 607, LY 9614 to New York (JFK) CANCELLED Cancelled with at least 23 hours' notice." in text(day)


# --- how this works --------------------------------------------------------------------------------

GAP = (utc(27, 18, 24, 46), utc(29, 12, 29, 3))
LATER_GAP = (utc(31, 8, 2, 45), utc(31, 11, 32, 45))

APPENDIX_A = [  # docs/site-redesign-plan.md, "Appendix A", with docs/flight-lookup-plan.md's placed in it, verbatim
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
    'For a cancelled flight, the warning is how long before its scheduled time the list already showed it as cancelled. The list refreshes about every 15 minutes, so the change is usually known to within that window, and always to within an hour. For the same reason, the time of a cancellation is always given as a range. Where records are missing, the warning is a range ("between 7 and 50 hours"). When a flight was already cancelled the first time it appeared in the records, only a lower limit is known ("at least 23 hours"); "at least" is also used when the change was seen an hour or more ahead, rounded down. The airline may have told passengers earlier than the list showed.',
    '## Why there are no delay figures',
    "The list gives an expected time for each flight. It doesn't say whether that is when the plane leaves the gate or when it takes off. Until that is settled, this site shows the airport's times as they are and doesn't turn them into delay figures.",
    '## "Final" and "not final"',
    'The airport also uses the words "final" and "not final". It doesn\'t publish what they mean, so this site quotes them as they are.',
    '## Probably the same flight',
    "Airlines often sell seats on one flight under several flight numbers. When numbers share the same time, terminal and check-in desks, this site lists them as probably the same flight. The list doesn't say so itself, and arrivals with no check-in desks can occasionally be grouped by mistake.",
    # docs/flight-lookup-plan.md, "Appendix A", placed after "Probably the same flight"
    '## A flight',
    'Flight numbers with the same scheduled time and airport are counted as one flight when the list shows the same expected time, terminal and check-in desks for them. A number that did not depart or land is counted with a number of its own airline, or one with its own desks. A flight counts as departed or landed when any of its numbers did, and as cancelled only when none did and at least one was listed as cancelled.',
    '## What is counted',
    'A flight is counted two days after its scheduled time, so that all the flights of one hour are counted together, whatever happened to them. A flight that left the list with no final status, or while nothing was recorded, has no known outcome. It is left out of every figure, and how many there are is given beside the figures.',
    '## Why every figure is a range',
    'Cancellations come in runs: an airline cancels several flights in the same week, and a bad day hits many flights at once. So each figure comes with a range wide enough to allow for both. A figure is shown only when it rests on at least 10 cancelled flights, from at least 5 airlines and 5 days; below that, the page gives the counts and says there are too few so far to say.',
    '## Why three days',
    "The airport's list shows a flight from about three days before its scheduled time, so the table starts at 70 hours to go. A flight that is already listed as cancelled when it first appears is almost never seen, so every figure is about flights that reached the list normally.",
    '## Why the later rows hold more flights',
    'Flights whose first days on the list fell before the records began, or in the gap from 27 to 29 October, were seen only in their last hours. They are in the later rows of the table and not in the earlier ones.',
    '## Signs under test',
    "No figure is given for one flight yet. I am testing four signs that might go with a later cancellation: a flight of the same airline from the same airport, scheduled to land 30 minutes to 12 hours before a departure, listed as cancelled; the same flight number's previous flight listed as cancelled; another flight of the same airline, scheduled within a day either side, listed as cancelled; and a flight number first listed less than two days before its scheduled time. The rules were fixed beforehand, in the code tagged [{TAG}]({CODE_URL}/tree/{TAG}). The counted flights are those first listed from {START}, the counting start; the 24-hour row is the table's row for 24 hours to go, and its checkpoint is that moment.",
    'A sign may change what this site shows only when both of these hold:',
    '1. The count. Take the counted flights of the 24-hour row in the order of the scheduled time they showed at the checkpoint. The gate is reached at the first such time that is at least 60 days after the counting start and by which 200 of those flights were later listed as cancelled. The days and the count are taken over every counted flight in the row.',
    '2. The sign has passed its test, read on the counted flights scheduled up to that time.',
    'The lift is the rate with the sign over the rate without it. Its range is 2.5 standard errors of its logarithm either side, grouped as the ranges above are. 2.5, not 2, because four signs are tested at once. A sign passes when it clears the floor (10 cancelled flights with the sign, from 5 airlines and 5 days) and the whole range lies above 1. A sign that fails stays failed for this version.',
    '## Gaps in the records',
    'Records start on the evening of 27 October 2026. {one sentence per gap: "There are no records from 27 October 20:24 to 29 October 14:29."} A flight that left the list during a gap is marked UNKNOWN.',
    "## How it's built",
    'The program runs on AWS Lambda and saves each version once, to storage where it is locked for ten years. A Python data model turns the saved versions into one history per flight, and this site is generated from that model. Every rule has tests, and the tests are themselves checked by breaking the code on purpose and confirming that a test fails. The code is on GitHub.',
]


TAG = "record-v1"
COUNTING_START = datetime(2026, 11, 15, 22)  # naive UTC: 00:00 on 16 November in Israel


def how(gaps=(GAP,)) -> str:
    return views.how_it_works_page(ATTRIBUTION, list(gaps), TAG, COUNTING_START, LAST_FETCH)


def appendix_text(gap_sentences: str) -> str:
    """Appendix A as a reader sees it on the page: markdown marks gone (a link reads as its text), placeholders
    filled: the tag, and the counting start as its Israel date, written as the lede writes a date."""
    lines = [re.sub(r"^(## |- |\d\. )", "", line) for line in APPENDIX_A]
    joined = " ".join(lines).replace("{ATTRIBUTION}", ATTRIBUTION)
    joined = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", joined)  # a link reads as its text
    joined = joined.replace("{TAG}", TAG).replace("{START}", "16 November 2026")
    return re.sub(r"\{one sentence per gap: [^}]*\}", gap_sentences, joined)


def test_how_it_works_is_appendix_a_verbatim(israeli_machine):
    """Both appendices, in order, each heading a section heading; the tag links to its code, and the gate's two
    conditions are a numbered list."""
    page = how()
    assert "<title>How this works</title>" in page and "<h1>How this works</h1>" in page
    assert appendix_text("There are no records from 27 October 20:24 to 29 October 14:29.") in text(page)
    assert [html.unescape(h) for h in re.findall(r"<h2>(.*?)</h2>", page)] == [
        line[3:] for line in APPENDIX_A if line.startswith("## ")]
    assert f'in the code tagged <a href="{words.CODE_URL}/tree/record-v1">record-v1</a>.' in page
    assert "<ol>\n<li>The count. Take" in page and "up to that time.</li>\n</ol>" in page
    assert f'<a href="{words.CODE_URL}">' in page
    assert '<link rel="stylesheet" href="style.css">' in page


def test_how_it_works_one_sentence_per_gap_in_israel_time_with_dates():
    page = text(how([GAP, LATER_GAP]))
    assert ("Records start on the evening of 27 October 2026. There are no records from 27 October 20:24 to "
            "29 October 14:29. There are no records from 31 October 10:02 to 31 October 13:32. A flight that left "
            "the list during a gap is marked UNKNOWN.") in page


def test_how_it_works_without_gaps():
    page = text(how([]))
    assert "Records start on the evening of 27 October 2026. A flight that left the list" in page


def test_how_it_works_carries_the_full_attribution_and_the_footer():
    page = how()
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
    fs = [flight("to", local(29, 17, 10), **TO, **TO_CANCELLED),
          flight("iz", local(30, 13, 50), airline="IZ", flight_no="992", direction="A", **AT_LEAST_23)]
    return flights.recent_cancellations(lists(*fs))


def twelve_cancelled():
    """LY 100 to LY 111, cancelled departures on 28 October, an hour apart from 06:00; newest first."""
    fs = [flight(f"c{i}", local(28, 6 + i, 0), flight_no=str(100 + i), **CLEAN) for i in range(12)]
    return flights.recent_cancellations(lists(*fs), n=12)


def figures(total=TOTAL, by_point=None, late_after=9):
    """The front page's figures (display.Summary): by default the design's, its total (A2), its table (A6, the 3-hour
    row as C8 rounds it), and A3's and A17's counts; `by_point` maps each checkpoint to its rate."""
    by_point = {h: r for h, (r, _) in A35_ROWS.items()} if by_point is None else by_point
    return display.Summary(
        figures=counting.Figures(total=total, rows=tuple((h, by_point[h]) for h in counting.CHECKPOINTS)),
        unknown=269, unknown_gap=240, unknown_no_final=29, late_after=late_after, late_holds=1, late_unplaced=19,
        late_before=52, first_record=date(2026, 10, 27))


SUMMARY = figures()
FEW = rate(3, 120, 40.0, 10.0, 90.0, floor=False)  # 3 cancelled: below the floor
BELOW = figures(FEW, {h: rate(2, 100 + h, 50.0 + h / 2, 10.0, 300.0, floor=False) for h in counting.CHECKPOINTS},
                late_after=0)  # a fresh archive: no rate clears the floor
NONE_YET = figures(rate(0, 900, None, None, None, floor=False),
                   {h: rate(0, 800, None, None, None, floor=False) for h in counting.CHECKPOINTS}, late_after=0)
COUNT_LINE = ("Counted: 4,658 flights with a known outcome, scheduled up to two days before the last update, in a "
              "record kept since 27 October 2026. Not counted: 269 flights with no known outcome. 240 of them left "
              "the list while nothing was recorded, and 29 left it with no final status.")
LATE_LINE = "Some flights (at least 9 of the 81) were only marked cancelled after their scheduled time had passed."
HEADS = ["Time to go", "Flights still listed normally", "Later listed as cancelled", "That's about"]


def front(summary=SUMMARY, story="TO 3459", recent=None, chart_days=None, all_days=None, data=None, last=LAST_FETCH):
    story_row = to3459_rows()[1] if story == "TO 3459" else story
    return views.front_page(summary, story_row, recent_default() if recent is None else recent,
                            CHART_DAYS if chart_days is None else chart_days,
                            ALL_DAYS if all_days is None else all_days, entries() if data is None else data, last)


def unknown_only_front():
    """Review Focus 3: the only cancellation's warning is unknown (ASY 991's shape, cancelled from its earliest
    record), so it is the story by the fallback rule."""
    f = flight("asy", local(29, 13, 30), **ASY_UNKNOWN)
    obs = [first(f) | {"status": "CANCELED"}]
    return front(figures(rate(1, 900, 900.0, None, None, floor=False)), story=rows(f, obs=obs)[0],
                 recent=lists(f, obs=obs))


def delayed_story_front():
    """A story whose change lines include the airport's "delayed"."""
    f = flight("late", local(29, 23, 0), outcome="canceled", cancel_lead_min=358.0, cancel_lead_max_min=374.0,
               cancel_lead_censored=False)
    start = first(f)
    late = then(start, utc(29, 13, 2, 45), status="DELAYED")
    gone = then(late, utc(29, 15, 2, 45), status="CANCELED")
    obs = [start, late, gone]
    return front(figures(rate(1, 900, 900.0, None, None, floor=False)), story=rows(f, obs=obs)[0],
                 recent=lists(f, obs=obs))


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


def test_front_page_top_line_and_lede():
    """The top line holds the site's name as the page's one <h1>; the lede opens the main column."""
    page = front()
    assert top_line("", front=True) in page
    assert ('<main>\n<p class="lede">A record of flights in and out of Ben Gurion Airport, kept since 27 October 2026, '
            "and which ones were cancelled.</p>") in page
    assert page.count("<header") == 1 and page.count("<h1") == 1


def test_front_page_total():
    """The total replaces the headline: the design's sentence, with the range in the same breath."""
    page = front()
    assert ('<p class="total">So far, 81 of 4,658 flights with a known outcome were listed as cancelled. '
            "That's about 1 in 60 (between 1 in 35 and 1 in 95).</p>") in html.unescape(page)


def test_front_page_tiles_show_the_totals_counts():
    """The total's figures as tiles, each labelled with the sentence's own words, and the sentence under them."""
    page = front()
    assert tiles(page) == [("flights with a known outcome", "4,658"), ("listed as cancelled", "81"),
                           ("that's about", "1 in 60 (between 1 in 35 and 1 in 95)")]
    assert '<div class="stat cancel"><dt>listed as cancelled</dt> <dd>81</dd></div>' in page
    assert page.index('<dl class="stats">') < page.index('class="total"')


def test_front_page_tiles_and_sentence_share_their_rounding_and_separators():
    """1 in 1,120.8, its range 812.3 to 1,530.2: C8 rounds the middle to 1,100 and the ends outward, in the tile and
    the sentence alike, every count and N with its thousands separator."""
    page = front(figures(rate(12, 13450, 13450 / 12, 812.3, 1530.2)))
    assert tiles(page) == [("flights with a known outcome", "13,450"), ("listed as cancelled", "12"),
                           ("that's about", "1 in 1,100 (between 1 in 810 and 1 in 1,600)")]
    assert ("So far, 12 of 13,450 flights with a known outcome were listed as cancelled. That's about 1 in 1,100 "
            "(between 1 in 810 and 1 in 1,600)." in text(page))


def test_the_tile_prints_its_range_right_after_it():
    """docs/flight-lookup.md, "Pages", item 4: "1 in 60", then " (between 1 in 35 and 1 in 95)" right after it, in
    smaller type."""
    page = front()
    assert "<dd>1 in 60<small> (between 1 in 35 and 1 in 95)</small></dd>" in page
    assert "1 in 60 (between 1 in 35 and 1 in 95)" in text(section(page, '<dl class="stats">', "</dl>"))


def test_below_the_floor_no_third_tile():
    """Question 4f: below the floor the "that's about" tile is left out, and the sentence says so (Question 4d)."""
    page = front(figures(FEW))
    assert tiles(page) == [("flights with a known outcome", "120"), ("listed as cancelled", "3")]
    assert ('<p class="total">So far, 3 of 120 flights with a known outcome were listed as cancelled. '
            "Too few so far to say.</p>") in page


def test_the_total_without_cancellations():
    """Question 4d: with none cancelled the total still gives its two counts, then "Too few so far to say."."""
    page = front(NONE_YET, story=None, recent=[])
    assert tiles(page) == [("flights with a known outcome", "900"), ("listed as cancelled", "0")]
    assert ("So far, 0 of 900 flights with a known outcome were listed as cancelled. Too few so far to say."
            in text(page))


def block(page: str) -> str:
    """The front page's "From here to the scheduled time", from its heading to the total's tiles."""
    return section(page, "<h2>From here to the scheduled time</h2>", '<dl class="stats">')


def table_cells(page: str) -> list[list[str]]:
    """The from-here table's heads and rows, as a reader sees each cell."""
    table = section(page, '<table class="fromhere">', "</table>")
    return [[text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr)] for tr in re.findall(r"<tr>(.*?)</tr>", table)]


def test_the_block():
    """docs/flight-lookup.md, "Pages", item 3, in order: the heading and the first line, the table of six points (A6,
    shown as C8 rounds it), the record line, the three lines under the table, the count line and the late line.
    Plain HTML: no script."""
    part = block(front())
    lines = [text(inner) for _, inner in re.findall(r"<(h2|p)[^>]*>(.*?)</\1>", part)]
    assert lines == ["From here to the scheduled time", words.FROM_HERE_FIRST, words.PAST_ONLY, *words.UNDER_TABLE,
                     COUNT_LINE, LATE_LINE]
    assert part.index(words.FROM_HERE_FIRST) < part.index('<table class="fromhere">') < part.index(words.PAST_ONLY)
    assert table_cells(part) == [
        HEADS,
        ["70 hours", "3,028", "48", "1 in 65 (between 1 in 30 and 1 in 130)"],
        ["48 hours", "3,316", "47", "1 in 70 (between 1 in 35 and 1 in 140)"],
        ["24 hours", "3,449", "35", "1 in 100 (between 1 in 45 and 1 in 200)"],
        ["12 hours", "3,625", "25", "1 in 150 (between 1 in 70 and 1 in 300)"],
        ["6 hours", "3,704", "19", "1 in 190 (between 1 in 95 and 1 in 400)"],
        ["3 hours", "3,754", "16", "1 in 230 (between 1 in 110 and 1 in 460)"],
    ]
    assert "<script" not in part


def test_every_cell_carries_its_columns_head():
    """On a phone the table stacks and its heads are hidden (style.css): each cell names its column for the sheet to
    print before it."""
    body = section(front(), '<table class="fromhere">', "</table>").split("<tbody>")[1]
    for tr in re.findall(r"<tr>(.*?)</tr>", body):
        assert [html.unescape(h) for h in re.findall(r'<td data-label="([^"]*)">', tr)] == HEADS


def test_a_row_below_the_floor_shows_its_counts_and_too_few_so_far_to_say():
    by_point = {h: r for h, (r, _) in A35_ROWS.items()} | {3: rate(8, 3754, 469.25, 200.0, 1000.0, floor=False)}
    got = table_cells(front(figures(by_point=by_point)))
    assert got[6] == ["3 hours", "3,754", "8", "too few so far to say"]
    assert got[3] == ["24 hours", "3,449", "35", "1 in 100 (between 1 in 45 and 1 in 200)"]


def test_a_model_below_the_floor_everywhere():
    """Review Focus 3: a fresh archive clears the floor nowhere. No range, and no "1 in N", anywhere on the page; each
    row and the total say "too few so far to say", and the late line, at zero, is left out."""
    page = front(BELOW)
    assert "(between" not in page and not re.search(r"1 in \d", text(page))
    assert [row[3] for row in table_cells(page)[1:]] == [words.TOO_FEW] * 6
    assert "Too few so far to say." in text(page)
    assert "At least" not in text(page) and "None" not in text(page)


def test_the_story_box():
    box = section(front(), '<section class="story">', "</section>")
    assert ('<h2><a href="flight/TO3459-D.html#2026-10-29-1710-ORY"><span class="d">TO 3459 · Tel Aviv to Paris'
            "</span></a></h2>") in box
    assert "Thursday 29 October 2026, scheduled to leave at 17:10" in text(box)
    assert [text(li) for li in re.findall(r"<li>(.*?)</li>", box)] == [
        "Already on the list on 27 Oct at 20:04 on time, terminal 1",
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
        ["Date", "Flight", "Route", "Notice given"],
        ["Fri 30 Oct", "IZ 992", "New York (JFK) to Tel Aviv, scheduled to land at 13:50", "Notice given: 23+ hours"],
        ["Thu 29 Oct", "TO 3459", "Tel Aviv to Paris (ORY), scheduled to leave at 17:10", "Notice given: none"],
    ]
    assert '<a href="flight/IZ992-A.html#2026-10-30-1350-JFK">' in table
    assert '<a href="flight/TO3459-D.html#2026-10-29-1710-ORY">' in table
    assert page.index("<h2>Recent cancellations</h2>") < page.index(table)
    assert '<p><a href="cancellations.html">All cancellations</a></p>' in page


def test_recent_cancellations_at_most_ten():
    page = front(recent=twelve_cancelled())
    shown = [row[1] for row in cells(section(page, '<table class="cancellations">', "</table>"))[1:]]
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


def day_page_counts(page: str) -> str:
    """A day page's counts as the chart prints them: the flights and the cancelled from its title, the unknown from
    its unknown line ("370 flights · 8 cancelled · 190 unknown"); a zero is left out of both."""
    parts = text(re.search(r"<h1>(.*?)</h1>", page).group(1)).split(" · ")[1:]
    unknown = re.search(r"For ([\d,]+) of these flights, there's no record of how", text(page))
    return " · ".join(parts + ([f"{unknown.group(1)} unknown"] if unknown else []))


def test_chart_counts_equal_the_day_pages():
    chart = views.chart_svg(CHART_DAYS)
    for info in CHART_DAYS:
        line = day_page_counts(views.day_page(info, [], LAST_FETCH))
        assert line.startswith(f"{info.total} flights")
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


def test_the_front_page_is_updated_at_the_last_record(israeli_machine):
    """The front page's top line says when the last record is, not the default of these tests."""
    page = front(last=datetime(2026, 11, 17, 7, 46, 12))
    assert '<p class="updated" data-updated="2026-11-17T07:46:12Z">Updated 17 Nov at 09:46</p>' in page


def test_built_by_line():
    page = front()
    line = section(page, '<p class="built">', "</p>")
    assert text(line) == f"Built by {words.BUILT_BY} · How this works · Code on GitHub"
    assert '<a href="how-it-works.html">How this works</a>' in line
    assert f'<a href="{words.CODE_URL}">Code on GitHub</a>' in line


def test_front_page_order():
    """docs/flight-lookup.md, "Pages", Front page: the top line, the search box (moved up), the block, the total's tiles
    and sentence, the story, recent cancellations, the chart, the day list and the built-by line; the search data
    last in the main column."""
    page = front()
    order = ['<h1 class="wordmark">', 'class="where"', 'class="updated"', "</header>", 'class="lede"',
             '<input id="search"', 'id="search-results"', "<h2>From here to the scheduled time</h2>",
             '<table class="fromhere">', 'class="stats"', 'class="total"', 'class="story"', "Recent cancellations",
             'href="cancellations.html"', "Flights each day", '<svg class="chart"', 'class="days"', 'class="built"',
             'id="flights-data"', "</main>", "<footer>"]
    assert [page.index(part) for part in order] == sorted(page.index(part) for part in order)


def test_the_table_comes_before_the_search_data():
    """The search data (about 130 KB on a full archive) is the main column's last element, so the from-here table
    renders before it has arrived; search.js is deferred and finds it by id. One copy only."""
    page = front()
    assert page.count('id="flights-data"') == 1
    assert page.index('<table class="fromhere">') < page.index('id="flights-data"')
    data = re.search(r'<script type="application/json" id="flights-data">.*?</script>', page, re.S).group(0)
    assert page.index(f"{data}\n</main>") > page.index('class="built"')


def test_front_page_without_cancellations():
    """Review Focus 3: the story left out; the block and the total with their counts and "too few so far to say";
    everything else present."""
    page = views.front_page(NONE_YET, None, [], CHART_DAYS, CHART_DAYS, entries(), LAST_FETCH)
    assert 'class="story"' not in page
    assert '<table class="fromhere">' in page and "So far, 0 of 900 flights" in text(page)
    assert '<input id="search"' in page and '<ul id="search-results" hidden></ul>' in page
    assert 'id="flights-data"' in page and '<svg class="chart"' in page and '<p class="days">' in page
    assert "<h2>Recent cancellations</h2>" in page and "<p>No cancelled flights so far.</p>" in page
    assert 'class="cancellations"' not in page
    assert UPDATED in page
    assert all(t in text(page) for t in (words.SOURCE_SHORT, words.UNOFFICIAL, words.TIMES_NOTE))


def test_front_page_whose_only_cancellation_has_an_unknown_warning():
    """Review Focus 3: it still builds, with the flight as its story."""
    page = unknown_only_front()
    assert "So far, 1 of 900 flights with a known outcome were listed as cancelled." in text(page)
    box = section(page, '<section class="story">', "</section>")
    assert "Already on the list on 27 Oct at 20:04 already cancelled, terminal 3" in text(box)
    assert cells(section(page, '<table class="cancellations">', "</table>"))[1][-1] == "Notice given: unknown"


# --- the upload check's phrases on every page these tests build ------------------------------------

def every_page() -> dict[str, str]:
    to, to_obs = to3459()
    return {
        "layout": views.layout("t", "", "", LAST_FETCH),
        "layout, the front page's top line": views.layout("t", "", "", LAST_FETCH, front=True),
        "TO 3459": to3459_page(),
        "arrival": page_of(flight("in", local(29, 5, 0), flight_no="002", direction="A")),
        "two cities": page_of(flight("kut", local(28, 16, 30), flight_no="5115", airport="KUT", city_en="KUTAISI"),
                              flight("bus", local(28, 16, 30), flight_no="5115", airport="BUS", city_en="BATUMI")),
        "codeshare": codeshare_page(("DL", "7426"), ("AM", "7895")),
        "every label": page_of(*label_rows(words.LABEL_ORDER)),
        "notes": page_of(flight("gone", local(28, 9, 0), outcome="vanished", last_seen_at=utc(28, 0, 40)),
                         flight("back", local(29, 9, 0), uncanceled=True),
                         flight("again", local(30, 9, 0), **AT_LEAST_23 | {"uncanceled": True}),
                         flight("at least", local(31, 9, 0), **AT_LEAST_23)),
        "day": day_page(),
        "day, a cancellation at least 23 hours ahead": views.day_page(
            DayInfo(date(2026, 10, 30), 1, 1, 0, "today", False),
            lists(flight("iz", local(30, 13, 50), airline="IZ", flight_no="992", **AT_LEAST_23)), LAST_FETCH),
        "day, no flights, every line": day_page(0, 0, 1, True, flights_=[]),
        "cancellations": cancellations_page(),
        "how it works": how([GAP, LATER_GAP]),
        "TO 3459 rows on a day": views.day_page(DayInfo(DAY, 1, 1, 0, "past", False), lists(to[1], obs=to_obs),
                                                LAST_FETCH),
        "front page": front(),
        "front page, ten cancellations": front(recent=twelve_cancelled()),
        "front page, no cancellations": views.front_page(NONE_YET, None, [], CHART_DAYS, ALL_DAYS, entries(),
                                                         LAST_FETCH),
        "front page, a warning unknown": unknown_only_front(),
        "front page, a delayed story": delayed_story_front(),
        "front page, below the floor everywhere": front(BELOW),
        "front page, a row below the floor": front(figures(by_point={h: r for h, (r, _) in A35_ROWS.items()}
                                                           | {3: rate(8, 3754, 469.25, 200.0, 1000.0, floor=False)})),
        "a day ahead marked cancelled": page_of(flight("top", AHEAD, **AT_LEAST_23), flight("up", LATER, outcome="open")),
        "a day ahead removed early": page_of(flight("top", AHEAD, outcome="vanished", last_seen_at=utc(29, 20, 0))),
        "a day ahead landed early": page_of(flight("top", AHEAD, direction="A", outcome="landed",
                                                   est_local_final=local(30, 8, 40))),
        "no day ahead, off the list": page_of(flight("d28", local(28, 9, 0))),
        "no day ahead, still listed": page_of(flight("d28", local(28, 9, 0), last_seen_at=LAST_FETCH)),
        "a strip across two months": page_of(flight("o31", LATER), flight("n01", datetime(2026, 11, 1, 9, 0),
                                                                          outcome="open")),
        "the notes on quoted words": page_of(*(fs := [flight("d29", local(29, 9, 0)),
                                                     flight("c28", local(28, 9, 0), **CLEAN)]),
                                             obs=[first(f) | {"status": "NOT FINAL"} for f in fs]),
        "another flight number departed": page_of(lh("lh0691a", local(29, 9, 0), "0691A", "canceled"),
                                                  lh("lh695", local(29, 9, 0), "695"), only="lh0691a"),
        "another flight number landed": page_of(*os_pair(), only="os1083"),
        "another flight number still listed": page_of(lh("lh0691a-31", local(31, 9, 0), "0691A", "canceled"),
                                                      lh("lh695-31", local(31, 9, 0), "695", "open"),
                                                      only="lh0691a-31"),
        "another flight number with no news yet": page_of(lh("lh0691a-late", local(29, 23, 55), "0691A", "canceled"),
                                                          lh("lh695-late", local(29, 23, 55), "695", "open"),
                                                          only="lh0691a-late"),
        "day, numbers listed as cancelled in a flight that departed": bracket_day(),
        "cancellations, a warning by C9": views.cancellations_page(lists(*ey_ly()), LAST_FETCH),
        "cancellations, none": views.cancellations_page([], LAST_FETCH),
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
