"""The redesigned site's pages (docs/site-redesign.md: "Pages", "Words", "Codeshares", "Names"), from display rows
made with flights.make_rows. Expected values by hand; the how-it-works copy is the plan's Appendix A, verbatim."""
import dataclasses
import html
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

import pytest

from counting_helpers import board
from model.report import ATTRIBUTION
from test_blend import AP, made
from test_timeline_flights import CLEAN, LAST_FETCH, RESUMES, ey_ly, first, flight, lh, local, os_pair, then, utc
from test_timeline_words import TO3459_OBS
from test_timeline_words import israeli_machine  # noqa: F401  (a fixture: run as on the owner's Mac)
from timeline import blend, check, counting, display, flights, names, views, words
from timeline.blend import Tally
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


def rows(*fs, obs=None, updated=LAST_FETCH):
    """Display rows for these flights, labelled at the last sighting `updated`; each has only its earliest record
    unless `obs` is given."""
    return flights.make_rows(list(fs), [first(f) for f in fs] if obs is None else obs, updated, 1, RESUMES)


def lists(*fs, obs=None):
    """The lists' flights (rule C1) of these numbers."""
    return flights.group_flights(rows(*fs, obs=obs), list(fs), LAST_FETCH)


def records_of(fs, updated=LAST_FETCH, airport=AP, **airlines) -> blend.Records:
    """These numbers' records as the blend counts them at the last sighting `updated` (blend.records), on the design's
    airport, whose rows and delays all clear the floor, so that every day ahead labelled UPCOMING carries its chances.
    `airlines` puts an airline's counts in place of the ones these rows give it (LO=LOT: LOT's 127 flights)."""
    got = blend.records(list(fs), [], board(updated))
    return dataclasses.replace(got, airport=airport, airlines=got.airlines | airlines)


def page_of(*fs, obs=None, only=None, updated=LAST_FETCH, records=None):
    """The flight page of these numbers' rows, or of the rows with flight_id `only` (one, or a set) among them, at the
    last sighting `updated`. Their flights (C1), partners, twins and records (records_of, unless `records` is given)
    are made of all of them."""
    table = list(fs)
    keep = {only} if isinstance(only, str) else only
    every = rows(*fs, obs=obs, updated=updated)
    listed = flights.group_flights(every, table, updated)
    return views.flight_page([r for r in every if keep is None or r.flight_id in keep], flights.partners(listed, table),
                             flights.others(listed), updated, records or records_of(table, updated),
                             counting.flights(table, updated), {f["flight_id"]: f for f in table})


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
        ("D", AT_LEAST_23, "Friday 30 October · scheduled to leave at 09:00 · CANCELLED Cancelled with at least 23 "
         "hours' notice. It was already cancelled when it first appeared. This flight is marked cancelled. Contact "
         "your airline."),
        ("D", dict(outcome="vanished", last_seen_at=utc(29, 20, 0)),
         "Friday 30 October · scheduled to leave at 09:00 · UNKNOWN The airport removed this flight 11 hours early "
         "without saying why. It may have been cancelled or moved to another time. Check with your airline."),
        ("A", dict(outcome="landed", est_local_final=local(30, 8, 40)),
         "Friday 30 October · scheduled 09:00 · landed around 08:40 · LANDED"),
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
        "Saturday 31 October · scheduled to leave at 09:00 · CANCELLED Cancelled with at least 6 hours' notice. This "
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
    # a later day ahead marked cancelled says so too, not only the top day
    assert MARKED in day_block(pages["days ahead and past"], "2026-10-31-0900-JFK")


def test_the_head_line_carries_its_separators_in_the_text():
    """docs/site-redesign.md, "Flight page", items 3 and 8: "Tuesday 17 November · scheduled to land at 19:45 ·
    UPCOMING", the " · " in the text, so the line reads right without the style sheet and to a screen reader."""
    page = page_of(flight("up", AHEAD, outcome="open"))
    assert ('<p class="head"><span class="date">Friday 30 October</span> · <span class="sched">scheduled to leave at '
            '09:00</span> · <span class="labels"><span class="label l-upcoming">UPCOMING</span></span></p>') in page


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
    assert text(row).startswith("Thursday 29 October · scheduled to leave at 17:10 · CANCELLED")
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
    assert ("Tuesday 27 October · scheduled 16:45 · left around 17:09 · DEPARTED"
            in text(day_block(page, "2026-10-27-1645-ORY")))
    upcoming = day_block(page, "2026-11-01-1830-ORY")
    assert "around" not in upcoming and "expected 1" not in upcoming
    assert text(page).count(words.EXPECTED_NOTE) == 1  # two rows show a landed-around or expected time


def test_expected_on_a_day_with_no_final_word_and_no_note_without_an_expected_time():
    page = page_of(flight("ahead", outcome="open", est_local_final=local(29, 17, 20)),
                   flight("same", local(30, 16, 45), outcome="open"))
    assert "scheduled 16:45 · expected 17:20 · UPCOMING" not in text(page)  # 29 Oct 16:45 Israel time is not ahead
    page = page_of(flight("ahead", local(30, 16, 45), outcome="open", est_local_final=local(30, 17, 20)))
    assert "scheduled 16:45 · expected 17:20 · UPCOMING" in text(page) and words.EXPECTED_NOTE in text(page)
    page = page_of(flight("ahead", local(30, 16, 45), outcome="open"))
    assert "scheduled to leave at 16:45 · UPCOMING" in text(page) and words.EXPECTED_NOTE not in text(page)


def test_no_expected_note_without_an_expected_time():
    page = page_of(flight("on time", est_local_final=None))
    assert "scheduled to leave at 16:45 · DEPARTED" in text(page)
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
        "Wednesday 28 October · scheduled 16:30 · left around 16:30 · to Kutaisi (KUT) · DEPARTED")
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


# --- the headline slot (docs/flight-lookup.md, "Flight page: the headline", "the "Worked out from" line, every form"
# and "the lines in smaller type"; "Pages", Flight page; the plan's Task 11 markup) --------------------------------

NOV_LAST = datetime(2026, 11, 17, 7, 46, 44)  # the 2026-11-17 model's last sighting: 09:46 on 17 November in Israel
LOT = Tally(127, 0, 127, 2, (), None)  # LOT's counts in the design's lines ("LOT POLISH AIRLINES so far: 127 flights")
# Lufthansa's: 183 flights, 11 cancelled between 6 and 10 November, 172 that flew, 7 of them an hour or more late
LUFTHANSA = Tally(183, 11, 172, 7, tuple(sorted(date(2026, 11, 6 + i % 5) for i in range(11))),
                  datetime(2026, 11, 10, 17, 20))
LH694 = dict(airline="LH", flight_no="694", direction="A", airline_name="LUFTHANSA", airport="FRA",
             city_en="FRANKFURT", city_he="פרנקפורט")
LO155_WORKED = ("Worked out from this flight's history (none of its 22 flights was cancelled), LOT's history, and how "
                "soon it leaves.")
LOT_SO_FAR = "LOT POLISH AIRLINES so far: 127 flights · none cancelled · 2 delayed an hour or more"
FRESH = "Updated 17 Nov at 09:46. Things may have changed, so check with your airline."
OFF_ARRIVALS = "All airlines at Ben Gurion: 1.7% cancelled · about 5% of arrivals delayed an hour or more"


def wall(day: date, h: int, m: int) -> datetime:
    """An airport time (Israel wall-clock, UTC+2 from 25 October) on `day`."""
    return datetime(day.year, day.month, day.day, h, m)


def run_of(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def lo155(ahead=(17, 18, 19), **kw) -> list[dict]:
    """LO 155 (docs/flight-lookup.md, "Flight page: the headline"): landed at 19:45 on each of the 22 days from 26
    October to 16 November, and listed for 19:45 on each November day of `ahead`. `kw` sets any other column."""
    landed = [flight(f"lo{d:%m%d}", wall(d, 19, 45), outcome="landed", **LO | kw)
              for d in run_of(date(2026, 10, 26), 22)]
    return landed + [flight(f"lo11{d}", wall(date(2026, 11, d), 19, 45), outcome="open", **LO | kw) for d in ahead]


def lo155_page(fs=None) -> str:
    fs = lo155() if fs is None else fs
    return page_of(*fs, updated=NOV_LAST, records=records_of(fs, NOV_LAST, LO=LOT))


def lh694(*extra: dict) -> list[dict]:
    """LH 694 (docs/flight-lookup.md, "Flight page: the headline"): landed at 19:20 on each of the 10 days from 27
    October to 5 November, and cancelled on each day from 6 to 9 November; then `extra`."""
    landed = [flight(f"lh{d:%m%d}", wall(d, 19, 20), outcome="landed", **LH694) for d in run_of(date(2026, 10, 27), 10)]
    cancelled = [flight(f"lh{d:%m%d}", wall(d, 19, 20), **LH694, **CLEAN) for d in run_of(date(2026, 11, 6), 4)]
    return landed + cancelled + list(extra)


def lh694_page(*extra: dict) -> str:
    fs = lh694(*extra)
    return page_of(*fs, updated=NOV_LAST, records=records_of(fs, NOV_LAST, LH=LUFTHANSA))


def div(page: str, opening: str) -> str:
    """The element that `opening` starts, a <div>, through its own closing tag (the divs inside it counted)."""
    start, depth = page.index(opening), 0
    for m in re.finditer(r"<(/?)div\b[^>]*>", page[page.index(opening):]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return page[start:start + m.end()]
    raise AssertionError(f"{opening} is not closed")


def lines(part: str) -> list[tuple[str, bool]]:
    """Each paragraph of a part as a reader sees it, and whether it is hidden, by its own `hidden` or by an element
    around it."""
    out: list[list] = []
    stack: list[tuple[str, bool]] = []

    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in VOID:
                return
            stack.append((tag, "hidden" in dict(attrs) or any(h for _, h in stack)))
            if tag == "p":
                out.append(["", stack[-1][1]])

        def handle_endtag(self, tag):
            stack.pop()

        def handle_data(self, data):
            if any(t == "p" for t, _ in stack):
                out[-1][0] += data

    Parser(convert_charrefs=True).feed(part)
    return [(re.sub(r"\s+", " ", t).strip(), h) for t, h in out]


def shown(part: str) -> list[str]:
    """What a part says without scripts: its paragraphs that are not hidden."""
    return [t for t, h in lines(part) if not h]


def pairs(day: str) -> list[tuple[int, int, bool, str]]:
    """A day's prepared chances: each pair's stretch, whether it is hidden, and what it says."""
    return [(int(a), int(u), bool(h), text(body)) for a, u, h, body in
            re.findall(r'<div class="pair" data-after="(\d+)" data-upto="(\d+)"( hidden)?>\n(.*?)\n</div>', day, re.S)]


def test_the_slot_with_a_day_ahead():
    """LO 155 on 17 November, 10 hours before it lands (docs/flight-lookup.md, "Flight page: the headline", first row,
    and "the lines in smaller type"): the two chances for that time left, under 1% and about 1%, in the markup the page
    script reads; the "Worked out from" line; then, in smaller type, the number's, its airline's and all airlines'
    lines, the freshness line and the link. "Chance it's" keeps the plain apostrophe the upload check matches."""
    page = lo155_page()
    top = day_block(page, "2026-11-17-1945-WAW")
    assert ('<div class="chances">\n<div class="pair" data-after="6" data-upto="12">\n'
            '<p class="fig"><span class="fl">Chance it&#x27;s cancelled:</span> <span class="fv"><span class="q">under'
            '</span> <b class="n">1%</b></span></p>\n'
            '<p class="fig"><span class="fl">Chance it&#x27;s delayed an hour or more:</span> <span class="fv">'
            '<span class="q">about</span> <b class="n">1%</b></span></p>\n</div>\n'
            '<div class="pair" data-after="3" data-upto="6" hidden>\n') in top
    assert shown(div(top, '<div class="chances">')) == ["Chance it's cancelled: under 1%",
                                                       "Chance it's delayed an hour or more: about 1%"]
    assert shown(div(top, '<div class="support">')) == [
        LO155_WORKED, "LO 155 so far: 22 flights · none cancelled · none delayed an hour or more", LOT_SO_FAR,
        OFF_ARRIVALS, FRESH, "What the numbers mean"]
    assert '<p class="worked">Worked out from this flight&#x27;s history (none of its 22 flights was cancelled), ' \
           '<span class="d">LOT</span>&#x27;s history, and how soon it leaves.</p>' in top
    assert '<p class="s-line"><b><span class="d">LO 155</span> so far:</b> 22 flights · none cancelled' in top
    # the ASCII apostrophe (U+0027), which the upload check's lowercase match reads; never a curly one
    flat = check.flatten(check.strip_tags(page))
    assert check.CHANCE.search(flat) and "chance it's cancelled:" in flat and "’" not in text(top)
    assert check.WORKED_OUT.search(check.plain(check.strip_tags(page)))


def test_the_slot_with_none_ahead():
    """LH 694, its last flight on 9 November (docs/flight-lookup.md, "Flight page: the headline", second row; "Pages",
    Flight page): the not-listed line, then both chances in their "its next flight" forms, on the 70-hour row (about
    15% and about 3%), shown without scripts; the "Worked out from" line in its no-flight-ahead form, here with the
    bad week's dates and "It hasn't been on the airport's list since."; no flight-ahead line; the all-airlines line in
    its form without a time, alone."""
    page = lh694_page()
    assert shown(div(page, '<div id="now">')) == [
        "LH 694 isn't on the airport's list right now. The last one was on Monday 9 November.",
        "Chance its next flight is cancelled: about 15%",
        "Chance its next flight is delayed an hour or more: about 3%",
        "Worked out from this flight's history: 4 of its 14 flights were cancelled, all between 6 and 9 November. It "
        "hasn't been on the airport's list since.",
        "LH 694 so far: 14 flights · 4 cancelled · none delayed an hour or more",
        "LUFTHANSA so far: 183 flights · 11 cancelled, all between 6 and 10 November · 7 delayed an hour or more",
        OFF_ARRIVALS, FRESH, "What the numbers mean"]
    assert [h for _, h in lines(div(page, '<div id="now">'))] == [False] * 9
    assert '<div class="none-ahead">\n<p class="fig"><span class="fl">Chance its next flight is cancelled:</span>' in page
    assert '<p class="worked none-ahead">' in page and '<p class="worked">' not in page
    assert '<div class="aa" data-more-after="72">\n<p class="off">' in page and 'class="more"' not in page
    # its last flight removed early on 10 November is scheduled after the last cancelled one: no "since"
    gone = lh694_page(flight("lh1110", wall(date(2026, 11, 10), 19, 20), outcome="vanished",
                             last_seen_at=datetime(2026, 11, 8, 9, 20), **LH694))
    assert ("Worked out from this flight's history: 4 of its 14 flights were cancelled, all between 6 and 9 "
            "November.") in shown(div(gone, '<div id="now">'))
    assert "since" not in text(div(gone, '<div class="support">'))
    assert "The last one was on Tuesday 10 November." in text(gone)


@pytest.mark.parametrize("later", [False, True])
@pytest.mark.parametrize("direction, kw", [
    ("D", AT_LEAST_23), ("D", dict(outcome="vanished", last_seen_at=utc(29, 20, 0))),
    ("A", dict(outcome="landed", est_local_final=local(30, 8, 40)))], ids=["cancelled", "removed", "landed"])
def test_the_slot_when_the_traveller_day_carries_no_chances(direction, kw, later):
    """Questions 1 and 2: a traveller's day marked cancelled, removed early or landed early carries no chances. With a
    later day ahead carrying its own, the slot keeps the "Worked out from" line in its flight-ahead form under that
    day's own lines, so the page passes the upload check's rule; with none, the page has no flight-ahead line. Either
    way the "its next flight" headline and its line stand hidden, for the script to show once every day has passed."""
    fs = [flight("top", AHEAD, direction=direction, **kw)]
    if later:
        fs.append(flight("later", LATER, direction=direction, outcome="open"))
    page = page_of(*fs)
    top = day_block(page, "2026-10-30-0900-JFK")
    assert 'class="chances"' not in top
    support = div(top, '<div class="support">')
    assert ('<p class="worked">' in support) == later
    if later:
        assert shown(support)[0].startswith("Worked out")
        assert pairs(day_block(page, "2026-10-31-0900-JFK"))
    else:
        assert not any(t.startswith("Worked out") for t in shown(support))
    assert '<div class="none-ahead" hidden>' in support and '<p class="worked none-ahead" hidden>' in support
    flat = check.flatten(check.strip_tags(page))
    assert check.CHANCE.search(flat) and check.WORKED_OUT.search(check.plain(check.strip_tags(page)))


def test_a_later_day_carries_its_chances_and_no_line_of_its_own():
    """docs/flight-lookup.md, "Flight page: the headline", fourth row, and "Pages": LO 155 on 18 and 19 November, each a
    later day ahead labelled UPCOMING, carries its own two chances on one line, for its own time left (34 and 58
    hours), from the page's records, with no "Worked out from" line and no lines in smaller type of its own."""
    page = lo155_page()
    for anchor, first_pair, n in (("2026-11-18-1945-WAW", (24, 48), 5), ("2026-11-19-1945-WAW", (48, 72), 6)):
        day = day_block(page, anchor)
        got = pairs(day)
        assert len(got) == n and got[0][:3] == (*first_pair, False) and all(h for *_, h, _ in got[1:])
        assert {t for *_, t in got} == {"Chance it's cancelled: under 1% · Chance it's delayed an hour or more: "
                                        "about 1%"}
        assert ('<p class="one"><span class="fl">Chance it&#x27;s cancelled:</span> <span class="fv"><span class="q">'
                'under</span> <b class="n">1%</b></span><span class="sep"> · </span><span class="fl">Chance it&#x27;s '
                'delayed an hour or more:</span> <span class="fv"><span class="q">about</span> <b class="n">1%</b>'
                '</span></p>') in day
        assert 'class="worked' not in day and 'class="support"' not in day and 'class="s-line"' not in day


def test_prepared_pairs_only_for_stretches_still_ahead():
    """docs/flight-lookup.md, "Left to the builder", "At which moment" and "The weight of prepared figures": a day 31
    hours ahead at the last update holds one pair per stretch still ahead of it, five, from (24, 48] down; that one
    shows without scripts, the rest hidden. Each pair is scaled by its own row, the nearest checkpoint at or above its
    stretch (LH 694's 16.5% by 48 hours' 0.852 is 14%, and down to 4% on the 3-hour row); the delay is flat."""
    page = lh694_page(flight("lh1118", wall(date(2026, 11, 18), 16, 50), outcome="open", **LH694))  # 14:50 UTC
    got = pairs(day_block(page, "2026-11-18-1650-FRA"))
    assert [(a, u, h) for a, u, h, _ in got] == [(24, 48, False), (12, 24, True), (6, 12, True), (3, 6, True),
                                                  (0, 3, True)]
    assert [t for *_, t in got] == [f"Chance it's cancelled: about {p}% Chance it's delayed an hour or more: about 3%"
                                    for p in (14, 10, 7, 6, 4)]


def ended(page: str) -> int:
    """The strip key's departed, landed and cancelled marks, added up."""
    return sum(int(n) for n in re.findall(r"(?:departed|landed|cancelled) (\d+)", text(key(page))))


def test_the_counts_agree():
    """docs/flight-lookup.md, "How numbers are written": every count on a page uses the same flights, each whose
    ending is known, so the "so far" line, the "Worked out from" line and the strip's departed, landed and cancelled
    marks agree. LO 155: 22 (C4's closed flights would be 20); LH 694: 14, its removed day in neither."""
    page = lo155_page(lo155())
    assert "LO 155 so far: 22 flights" in text(page) and "(none of its 22 flights was cancelled)" in text(page)
    assert text(key(page)) == "landed 22 · upcoming 3" and ended(page) == 22
    page = lh694_page(flight("lh1110", wall(date(2026, 11, 10), 19, 20), outcome="vanished",
                             last_seen_at=datetime(2026, 11, 8, 9, 20), **LH694))
    assert "LH 694 so far: 14 flights" in text(page) and "4 of its 14 flights were cancelled" in text(page)
    assert text(key(page)) == "landed 10 · cancelled 4 · unknown 1" and ended(page) == 14


def test_a_twin_day_counts_as_flown_and_keeps_its_mark():
    """docs/flight-lookup.md, "How numbers are written", the exception, and Question 4: LH 0691A, marked cancelled on 29
    October while its flight left as LH 695, counts that day as flown in its "so far" line (C2), while its strip keeps
    the number's own mark, with the twin line under that day. So does a number that left the list with no final word
    while its flight left: the key and the "so far" count differ by that day."""
    own = [lh(f"a{d}", local(d, 9, 0), "0691A") for d in (26, 27, 28)]
    for kind, mark_ in (("canceled", "cancelled 1"), ("gap", "unknown 1")):
        page = page_of(*own, lh("a29", local(29, 9, 0), "0691A", kind), lh("b29", local(29, 9, 0), "695"),
                       only={"a26", "a27", "a28", "a29"})
        assert "LH 0691A so far: 4 flights · none cancelled · none delayed an hour or more" in text(page), kind
        assert text(key(page)) == f"departed 3 · {mark_}", kind
    assert "This number was cancelled, but the flight probably left as LH 695." in text(day_block(
        page_of(*own, lh("a29", local(29, 9, 0), "0691A", "canceled"), lh("b29", local(29, 9, 0), "695"),
                only={"a26", "a27", "a28", "a29"}), "2026-10-29-0900-FRA"))


def ly001(cancelled_on: set[date]) -> list[dict]:
    """LY 001 to New York at 16:45 on each of the 20 days from 27 October to 15 November, cancelled on the days given,
    and listed for 18 November."""
    fs = [flight(f"ly{d:%m%d}", wall(d, 16, 45), **(CLEAN if d in cancelled_on else {}))
          for d in run_of(date(2026, 10, 27), 20)]
    return fs + [flight("ly1118", wall(date(2026, 11, 18), 16, 45), outcome="open")]


def test_a_bad_week_names_its_dates_and_a_spread_one_does_not():
    """docs/flight-lookup.md, "the "Worked out from" line, every form": when one week holds all of a record's cancelled
    flights, two or more, the line names its dates, and the number's "so far" line does not repeat them; its airline's
    line, whose dates the line does not give, carries them. Cancellations over weeks get the bracket and no dates."""
    week = ly001({date(2026, 11, 6), date(2026, 11, 7), date(2026, 11, 9)})
    support = shown(div(page_of(*week, updated=NOV_LAST, records=records_of(week, NOV_LAST)), '<div class="support">'))
    assert support[:3] == [
        "Worked out from this flight's history: 3 of its 20 flights were cancelled, all between 6 and 9 November. "
        "Also from El Al's history, and how soon it leaves.",
        "LY 001 so far: 20 flights · 3 cancelled · none delayed an hour or more",
        "EL AL ISRAEL AIRLINES so far: 20 flights · 3 cancelled, all between 6 and 9 November · none delayed an hour "
        "or more"]
    spread = ly001({date(2026, 10, 28), date(2026, 11, 5), date(2026, 11, 14)})
    support = shown(div(page_of(*spread, updated=NOV_LAST, records=records_of(spread, NOV_LAST)),
                        '<div class="support">'))
    assert support[:3] == [
        "Worked out from this flight's history (3 of its 20 flights were cancelled), El Al's history, and how soon it "
        "leaves.",
        "LY 001 so far: 20 flights · 3 cancelled · none delayed an hour or more",
        "EL AL ISRAEL AIRLINES so far: 20 flights · 3 cancelled · none delayed an hour or more"]


LH697 = dict(airline="LH", flight_no="697", airline_name="LUFTHANSA", airport="FRA", city_en="FRANKFURT")


def test_the_airlines_line_carries_its_dates_where_the_worked_out_line_does_not():
    """docs/flight-lookup.md, "the lines in smaller type": the airline's line names its bad week where the "Worked out
    from" line shown does not: on LH 694's page, whose own history leads, and not on LH 697's, whose line is worked out
    mostly from Lufthansa's and names them. A page with no line shown (its only day ahead is marked cancelled)
    names them on the airline's line."""
    assert ("LUFTHANSA so far: 183 flights · 11 cancelled, all between 6 and 10 November · 7 delayed an hour or more"
            in shown(div(lh694_page(), '<div class="support">')))
    fs = [flight("lh1105", wall(date(2026, 11, 5), 9, 0), **LH697),
          flight("lh1106", wall(date(2026, 11, 6), 9, 0), **LH697, **CLEAN)]
    page = page_of(*fs, updated=NOV_LAST, records=records_of(fs, NOV_LAST, LH=LUFTHANSA))
    assert shown(div(page, '<div class="support">'))[:5] == [
        "Chance its next flight is cancelled: about 10%", "Chance its next flight is delayed an hour or more: about 5%",
        "Worked out mostly from Lufthansa's history, because LH 697 has only 2 flights so far. Lufthansa cancelled 11 "
        "of its 183 flights, all between 6 and 10 November.",
        "LH 697 so far: 2 flights · 1 cancelled · none delayed an hour or more",
        "LUFTHANSA so far: 183 flights · 11 cancelled · 7 delayed an hour or more"]
    gone = [*fs, flight("lh1118", wall(date(2026, 11, 18), 9, 0), **LH697, **AT_LEAST_23)]
    page = page_of(*gone, updated=NOV_LAST, records=records_of(gone, NOV_LAST, LH=LUFTHANSA))
    assert not any(t.startswith("Worked out") for t in shown(div(page, '<div class="support">')))
    assert ("LUFTHANSA so far: 183 flights · 11 cancelled, all between 6 and 10 November · 7 delayed an hour or more"
            in shown(div(page, '<div class="support">')))


def ly9255(days: list[date], with_lo: set[date], ahead=()) -> list[dict]:
    """LY 9255 at 19:45 from Warsaw, landed on each of `days` and listed for each November day of `ahead`; on the days
    of `with_lo`, sold with LO 155 (the same time, terminal and desks), whose flight C8 groups under LOT."""
    sold = dict(LO, airline="LY", flight_no="9255", airline_name="EL AL  ISRAEL AIRLINES")
    out = []
    for d, outcome in [*((d, "landed") for d in days), *((date(2026, 11, n), "open") for n in ahead)]:
        out.append(flight(f"ly{d:%m%d}", wall(d, 19, 45), outcome=outcome, **sold))
        if d in with_lo:
            out.append(flight(f"lo{d:%m%d}", wall(d, 19, 45), outcome=outcome, **LO))
    return out


def page_9255(fs: list[dict], **airlines) -> str:
    keep = {f["flight_id"] for f in fs if f["flight_no"] == "9255"}
    return page_of(*fs, only=keep, updated=NOV_LAST, records=records_of(fs, NOV_LAST, **airlines))


def test_the_partner_line():
    """docs/flight-lookup.md, "the lines in smaller type" (D13): LY 9255, sold with LO 155, whose flight C8 groups under
    LOT, reads "LY 9255 is also sold as LO 155, so the numbers here are worked out from LOT's history." as a line of
    its own, above "LOT POLISH AIRLINES so far: …", the airline its chances are worked out from. LO 155's own page has
    no such line."""
    every = run_of(date(2026, 10, 26), 22)
    fs = ly9255(every, {*every, date(2026, 11, 17)}, ahead=(17,))
    support = div(page_9255(fs, LO=LOT), '<div class="support">')
    assert shown(support) == [
        LO155_WORKED, "LY 9255 so far: 22 flights · none cancelled · none delayed an hour or more",
        "LY 9255 is also sold as LO 155, so the numbers here are worked out from LOT's history.", LOT_SO_FAR,
        OFF_ARRIVALS, FRESH, "What the numbers mean"]
    assert ('<p class="s-line"><span class="d">LY 9255</span> is also sold as <span class="d">LO 155</span>, so the '
            'numbers here are worked out from <span class="d">LOT</span>&#x27;s history.</p>') in support
    lo = [f for f in fs if f["airline"] == "LO"]
    own = page_of(*fs, only={f["flight_id"] for f in lo}, updated=NOV_LAST, records=records_of(fs, NOV_LAST, LO=LOT))
    assert "is also sold as" not in text(own) and LOT_SO_FAR in text(own)


# El Al's counts in place of the rows': cancellations spread over October, so its pull is far from LOT's
EL_AL_HEAVY = Tally(300, 90, 210, 0, tuple(sorted(date(2026, 10, 1) + timedelta(days=i % 30) for i in range(90))),
                    datetime(2026, 10, 30, 17, 45))


def test_one_airline_per_page_when_the_grouping_differs_by_day():
    """Review Focus 2 ("Left to the builder", "Which airline on a later day ahead"): one airline per page, C8's
    grouping airline of the traveller's day, or of the newest day when none is ahead, for the "so far" line, the
    headline and every later day's chances. LY 9255 sold with LO 155 on 17 November and alone on 18 November reads
    LOT's history on both days, with the partner line; alone on 17 November and with LO 155 on 18 November, El Al's,
    without it."""
    history = run_of(date(2026, 11, 13), 4)  # four flights: the airline's history leads
    with_lot = page_9255(ly9255(history, {date(2026, 11, 17)}, ahead=(17, 18)), LO=LOT, LY=EL_AL_HEAVY)
    alone = page_9255(ly9255(history, {date(2026, 11, 18)}, ahead=(17, 18)), LO=LOT, LY=EL_AL_HEAVY)
    # LY 9255's four flights pulled towards LOT's clean record, or towards El Al's, each day by its own time left
    for page, figures in ((with_lot, ("under 1%", "under 1%")), (alone, ("about 8%", "about 15%"))):
        for anchor, figure in zip(("2026-11-17-1945-WAW", "2026-11-18-1945-WAW"), figures):
            assert pairs(day_block(page, anchor))[0][3].startswith(f"Chance it's cancelled: {figure}"), anchor
    assert "is also sold as LO 155" in text(with_lot) and LOT_SO_FAR in text(with_lot)
    assert "is also sold as" not in text(alone) and "EL AL ISRAEL AIRLINES so far: 300 flights" in text(alone)
    assert "Worked out mostly from LOT's history" in text(with_lot)
    assert "Worked out mostly from El Al's history" in text(alone)
    # no day ahead: the newest day's grouping
    newest_lot = page_9255(ly9255(history, {date(2026, 11, 16)}), LO=LOT, LY=EL_AL_HEAVY)
    newest_alone = page_9255(ly9255(history, {date(2026, 11, 15)}), LO=LOT, LY=EL_AL_HEAVY)
    assert "is also sold as LO 155" in text(newest_lot) and "is also sold as" not in text(newest_alone)


def test_a_partner_line_needs_a_spoken_name():
    """Question 5: the partner line always names its airline by its spoken name, never "its airline's history"; a page
    whose grouping airline has none stops, naming it (build.render stops first, naming every one)."""
    assert names.spoken("ZZ") is None
    fs = [flight("zz", airline="ZZ", flight_no="1"), flight("ly", flight_no="9001")]
    with pytest.raises(ValueError, match=r"\bZZ\b"):
        page_of(*fs, only="ly")
    assert "its airline" in text(page_of(*fs, only="zz"))  # its own page takes the "its airline" forms


def test_the_all_airlines_forms_and_bounds():
    """docs/flight-lookup.md, "the lines in smaller type": six prepared forms, one per stretch, each with its bounds
    for the script and the figure of the point at its far end, hidden; the "more than 3 days" line, hidden; the form
    without a time, the total's 1.7%, shown. A departure's page reads "of departures". A row below the floor leaves its
    form out, a total below the floor the form without a time; the delay figure has no floor, and a direction with no
    flight that flew leaves every form out; with no day ahead only the form without a time stands."""
    page = page_of(flight("up", AHEAD, outcome="open"))
    delayed = "about 8% of departures delayed an hour or more"
    assert div(page, '<div class="aa"') == "\n".join([
        '<div class="aa" data-more-after="72">',
        *(f'<p data-after="{a}" data-upto="{u}" hidden><b>All airlines at Ben Gurion, {name} before a flight:</b> '
          f'{figure} cancelled · {delayed}</p>'
          for a, u, name, figure in ((48, 72, "2 to 3 days", "1.6%"), (24, 48, "1 to 2 days", "1.4%"),
                                     (12, 24, "12 to 24 hours", "1.1%"), (6, 12, "6 to 12 hours", "under 1%"),
                                     (3, 6, "3 to 6 hours", "under 1%"), (0, 3, "less than 3 hours", "under 1%"))),
        f'<p class="more" hidden>{html.escape(words.MORE_THAN_3_DAYS)}</p>',
        f'<p class="off"><b>All airlines at Ben Gurion:</b> 1.7% cancelled · {delayed}</p>',
        "</div>"])
    thin = airport(rows={12: made(39, 5069, airlines=4)})
    fs = [flight("up", AHEAD, outcome="open")]
    page = page_of(*fs, records=records_of(fs, airport=thin))
    assert 'data-after="6" data-upto="12"' not in div(page, '<div class="aa"')
    assert len(re.findall(r"<p data-after=", page)) == 5
    page = page_of(*fs, records=records_of(fs, airport=airport(total=FEW)))
    assert 'class="off"' not in page and len(re.findall(r"<p data-after=", page)) == 6
    # the delay figure has no floor (the plan's amendment after Task 9's review): 1 of 50 departures that flew reads
    # "about 2%"; a direction with none that flew leaves every form out, and the "more than 3 days" line stands alone
    page = page_of(*fs, records=records_of(fs, airport=airport(delay={"D": made(1, 50)})))
    assert ("All airlines at Ben Gurion: 1.7% cancelled · about 2% of departures delayed an hour or more"
            in shown(div(page, '<div class="aa"')))
    page = page_of(*fs, records=records_of(fs, airport=airport(delay={"D": made(0, 0)})))
    assert re.findall(r'<div class="aa" data-more-after="72">\n<p class="more" hidden>[^<]*</p>\n</div>', page)
    none = page_of(flight("d", local(28, 9, 0)))
    assert div(none, '<div class="aa"') == ('<div class="aa" data-more-after="72">\n<p class="off"><b>All airlines at '
                                            f'Ben Gurion:</b> 1.7% cancelled · {delayed}</p>\n</div>')


def test_the_freshness_line_without_scripts(israeli_machine):
    """docs/flight-lookup.md, "the lines in smaller type": "Updated 17 Nov at 09:46. Things may have changed, so check
    with your airline.", its first part in Israel time from the last update's UTC instant, which the page script
    reads to write the page's age; then the link "What the numbers mean", last in the slot."""
    fresh = ('<p class="fresh"><span data-updated="2026-11-17T07:46:44Z">Updated 17 Nov at 09:46</span>. Things may '
             'have changed, so check with your airline.</p>\n<p class="means"><a href="../how-it-works.html#what-the-'
             'numbers-mean">What the numbers mean</a></p>\n</div>')
    for page in (lo155_page(), lh694_page()):
        assert fresh in page


def test_the_slot_holds_every_name_the_page_script_reads():
    """The plan's Task 11 markup, which fromhere.js reads: in .support, the hidden "its next flight" headline, the
    flight-ahead line, the no-flight-ahead line, the "so far" lines, .aa, .fresh and .means, in that order; with no
    day ahead, the no-flight-ahead parts shown and no flight-ahead line. A number with no flights yet has no "so far"
    line (Question 6d), nor an airline with none."""
    def names_in(page: str) -> list[tuple[str, bool]]:
        (support,) = [el for el in tree(page).walk() if "support" in el.classes]
        return [(" ".join(k.classes), "hidden" in k.attrs) for k in support.kids]

    fs = [flight("up", AHEAD, outcome="open"), flight("past", local(28, 9, 0))]
    assert names_in(page_of(*fs)) == [("none-ahead", True), ("worked", False), ("worked none-ahead", True),
                                      ("s-line", False), ("s-line", False), ("aa", False), ("fresh", False),
                                      ("means", False)]
    assert names_in(page_of(fs[1])) == [("none-ahead", False), ("worked none-ahead", False), ("s-line", False),
                                        ("s-line", False), ("aa", False), ("fresh", False), ("means", False)]
    assert names_in(page_of(fs[0])) == [("none-ahead", True), ("worked", False), ("worked none-ahead", True),
                                        ("aa", False), ("fresh", False), ("means", False)]
    assert ("Worked out from all airlines at Ben Gurion, because LY 001 and its airline have no flights so far."
            in text(page_of(fs[0])))


def test_a_page_with_no_counted_flight_at_the_airport_carries_no_chances():
    """A first archive, with no closed flight yet: the blend has no rate to start from (blend.cancel_chance gives None),
    so no day carries chances, the slot holds no headline and no "Worked out from" line, and the "so far" lines,
    the freshness line and the link stand (Question 1's structure, no new words)."""
    bare = blend.Airport(total=made(0, 0), rows=dict.fromkeys(counting.CHECKPOINTS, made(0, 0)), delay=AP.delay)
    fs = [flight("up", AHEAD, outcome="open"), flight("past", local(28, 9, 0))]
    page = page_of(*fs, records=records_of(fs, airport=bare))
    assert "Chance" not in text(page) and "Worked out" not in text(page) and 'class="chances"' not in page
    assert shown(div(page, '<div class="support">'))[:2] == [
        "LY 001 so far: 1 flight · none cancelled · none delayed an hour or more",
        "EL AL ISRAEL AIRLINES so far: 1 flight · none cancelled · none delayed an hour or more"]


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


# --- front page (docs/site-redesign.md, "Front page"; docs/flight-lookup.md, "Front page: the table", "Front page: the
# total" and "Pages", Front page) --------------------------------------------------------------------------------

CHART_DAYS = [DayInfo(date(2026, 10, 27), 348, 4, 12, "past", True),
              DayInfo(date(2026, 10, 28), 370, 8, 190, "past", False),
              DayInfo(date(2026, 10, 29), 418, 7, 0, "past", False),
              DayInfo(date(2026, 10, 30), 289, 1, 0, "today", False),
              DayInfo(date(2026, 10, 31), 161, 0, 0, "ahead", False),
              DayInfo(date(2026, 11, 1), 40, 0, 0, "ahead", True)]
ALL_DAYS = [DayInfo(date(2026, 10, 26), 120, 0, 3, "past", True), *CHART_DAYS]  # 26 Oct: not on the chart
HOSTILE = {"n": ["zz1"], "p": ["</script><b>"], "t": "ZZ 1, Tel Aviv to </script>`'\"", "u": "flight/ZZ1-D.html"}
TITLE = "Will It Fly? Tel Aviv airport (Ben Gurion), unofficial"
DESCRIPTION = ("Look up a flight at Ben Gurion Airport to see the chance it's cancelled or delayed an hour or more. "
               f"Unofficial. Built by {words.BUILT_BY.removesuffix('.')}.")
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


def airport(total=None, rows=None, delay=None) -> blend.Airport:
    """The design's airport (tests/test_blend.py's AP, docs/flight-lookup.md:307-315 and :340): the total 104 of 6,115;
    the 2026-11-17 rows, 71 of 4,472 down to 23 of 5,195; delays of an hour or more in 231 of 2,982 departures that
    flew and 149 of 3,029 arrivals. Any of its rates can be replaced."""
    return blend.Airport(total=AP.total if total is None else total, rows=AP.rows | (rows or {}),
                         delay=AP.delay | (delay or {}))


def summary_of(ap: blend.Airport = AP, late_after: int = 15, unknown: int = 285) -> display.Summary:
    """The figures beside the airport's rates (display.Summary): by default the design's, 15 flights marked cancelled
    only after their time and 285 left out (docs/flight-lookup.md, "Front page: the total"), records since 27
    October."""
    return display.Summary(
        figures=counting.Figures(total=ap.total, rows=tuple((h, ap.rows[h]) for h in counting.CHECKPOINTS)),
        unknown=unknown, unknown_gap=0, unknown_no_final=unknown, late_after=late_after, late_holds=0,
        late_unplaced=0, late_before=0, first_record=date(2026, 10, 27))


FEW = made(3, 420)  # 3 cancelled: below the floor
BELOW = airport(FEW, {h: made(2, 100 + h) for h in counting.CHECKPOINTS},
                {"D": made(1, 50), "A": made(0, 40)})  # a fresh archive: no rate clears the floor
NONE_YET = airport(made(0, 900), dict.fromkeys(counting.CHECKPOINTS, made(0, 800)), {"D": made(0, 0), "A": made(0, 0)})


def told(rs: list, i: int) -> tuple:
    """The story as build.render hands it over: the told row and the title of its flight page, over every row of its
    number."""
    return rs[i], flights.page_title(rs)


def front(ap=AP, s=None, story="TO 3459", recent=None, chart_days=None, all_days=None, data=None, last=LAST_FETCH):
    story_ = told(to3459_rows(), 1) if story == "TO 3459" else story
    return views.front_page(summary_of(ap) if s is None else s, ap, story_,
                            recent_default() if recent is None else recent,
                            CHART_DAYS if chart_days is None else chart_days,
                            ALL_DAYS if all_days is None else all_days, entries() if data is None else data, last)


def unknown_only_front():
    """Review Focus 3: the only cancellation's warning is unknown (ASY 991's shape, cancelled from its earliest
    record), so it is the story by the fallback rule."""
    f = flight("asy", local(29, 13, 30), **ASY_UNKNOWN)
    obs = [first(f) | {"status": "CANCELED"}]
    return front(airport(made(1, 900)), story=told(rows(f, obs=obs), 0), recent=lists(f, obs=obs))


def delayed_story_front():
    """A story whose change lines include the airport's "delayed"."""
    f = flight("late", local(29, 23, 0), outcome="canceled", cancel_lead_min=358.0, cancel_lead_max_min=374.0,
               cancel_lead_censored=False)
    start = first(f)
    late = then(start, utc(29, 13, 2, 45), status="DELAYED")
    gone = then(late, utc(29, 15, 2, 45), status="CANCELED")
    obs = [start, late, gone]
    return front(airport(made(1, 900)), story=told(rows(f, obs=obs), 0), recent=lists(f, obs=obs))


def meta(page: str, attribute: str) -> str:
    """The content of the head's <meta> with this name or property, unescaped."""
    return html.unescape(re.search(rf'<meta {attribute} content="([^"]*)">', page).group(1))


def section(page: str, start: str, end: str) -> str:
    i = page.index(start)
    return page[i:page.index(end, i)]


def body_of(page: str) -> str:
    return page[page.index("<body>"):]


def test_the_description_and_title():
    """docs/site-redesign.md, "Front page", the <head>: the tab's title and Open Graph's, the description (not shown on
    the page) with the built-by wording in place of "[owner's wording]", no image."""
    page = front()
    head = page[:page.index("</head>")]
    assert re.findall(r"<title>(.*?)</title>", page) == [TITLE]
    assert meta(head, 'property="og:title"') == TITLE
    assert meta(head, 'name="description"') == meta(head, 'property="og:description"') == DESCRIPTION
    assert meta(head, 'property="og:type"') == "website"
    assert "og:image" not in page
    assert "Unofficial. Built by" not in text(body_of(page))
    assert '<script src="search.js" defer></script>' in head
    assert '<link rel="stylesheet" href="style.css">' in head


@pytest.mark.parametrize("built_by", ["Doron Reiffman.", "Doron Reiffman"])
def test_description_ends_with_one_full_stop_whatever_the_built_by_line_ends_with(monkeypatch, built_by):
    monkeypatch.setattr(words, "BUILT_BY", built_by)
    head = front()[:front().index("</head>")]
    for attribute in ('name="description"', 'property="og:description"'):
        assert meta(head, attribute).endswith("an hour or more. Unofficial. Built by Doron Reiffman."), attribute


def test_front_page_order():
    """docs/site-redesign.md, "Front page", items 1 to 9: the top line; "Find your flight", and the line that stands in
    its place without scripts; the introduction; the chance table; the total; the story; recent cancellations;
    "Flights each day" and the day list; the footer. The built-by line that stood above the footer is gone: it is in
    the footer's links (:198). The search data last in the main column."""
    page = front()
    order = ['<h1 class="wordmark">', 'class="updated"', "</header>", '<div class="find" id="find"',
             '<p class="find-off" id="find-off">', '<p class="lede">',
             "<h2>Chance of cancellation, by how soon you fly</h2>",
             '<table class="fromhere">', '<p class="stats">', "Since 27 October, 104 of 6,115 flights",
             "<h2>A recent cancellation, step by step</h2>", "<h2>Recent cancellations</h2>",
             '<table class="cancellations">', 'href="cancellations.html"', "<h2>Flights each day</h2>",
             '<ol class="chart">', '<p class="days-h">', '<ol class="days" id="days">', 'id="flights-data"', "</main>",
             "<footer>"]
    at = [page.index(part) for part in order]
    assert at == sorted(at)
    assert 'class="built"' not in page and text(body_of(page)).count("Built by") == 1  # the footer's
    assert page.count("<h1") == 1


def test_the_introduction():
    page = front()
    assert ('<p class="lede">Look up your flight to see the chance it&#x27;s cancelled or delayed an hour or more. '
            "Based on every flight at Ben Gurion Airport since 27 October.</p>") in page


# "Find your flight" (docs/site-redesign.md, "Front page", item 2; the plan's wrapper, "What this plan decided")
FIND = ('<div class="find" id="find" hidden>\n'
        '<label class="find-l" for="search">Find your flight</label>\n'
        '<input id="search" type="search" placeholder="Flight number or city, like LY 001 or Paris" '
        'aria-label="Find a flight by number or city">\n'
        '<ul id="search-results" hidden></ul>\n'
        '<p class="find-hint">Your flight number is on your ticket or booking email.</p>\n'
        "</div>\n"
        '<p class="find-off" id="find-off">To find your flight, <a href="#days">pick its day below</a>.</p>')


def test_without_scripts_the_search_is_replaced_by_the_day_list_link():
    """The search needs JavaScript. Its label, box and hint stand in one wrapper that search.js shows, so none of them
    shows without the others; in the box's place stands "To find your flight, pick its day below.", whose last words
    link to the day list, which reaches every flight."""
    page = front()
    assert FIND in page and page.count('id="find"') == 1
    els = {el.attrs["id"]: el for el in main_of(page).walk() if "id" in el.attrs}
    assert "hidden" in els["find"].attrs and "hidden" not in els["find-off"].attrs
    assert "hidden" not in els["search"].attrs  # the wrapper hides it
    assert [k.tag for k in els["find"].kids] == ["label", "input", "ul", "p"]
    assert els["days"].tag == "ol" and "day/2026-10-26.html" in section(page, 'id="days"', "</ol>")


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


def test_the_table_comes_before_the_search_data():
    """The search data (about 130 KB on a full archive) is the main column's last element, so the chance table
    renders before it has arrived; search.js is deferred and finds it by id. One copy only."""
    page = front()
    assert page.count('id="flights-data"') == 1
    assert page.index('<table class="fromhere">') < page.index('id="flights-data"')
    data = re.search(r'<script type="application/json" id="flights-data">.*?</script>', page, re.S).group(0)
    assert f"{data}\n</main>" in page


# --- the chance table ----------------------------------------------------------------------------------------------

FIRST_LINE = ("If your flight is still on 3 days before, there's about a 1.6% chance it gets cancelled. By 3 hours "
              "before, it's 0.4%.")
UNDER = ("These are averages for all airlines, from about 5,000 flights since 27 October. A delayed flight still "
         "counts as “still on”.")
DELAY = ("Chance of a delay of an hour or more: about 8% for departures and 5% for arrivals. It's about the same "
         "however soon you fly.")
HEADS = ["Your flight is…", "Chance it's cancelled"]
DESIGN_ROWS = [["3 days away", "1.6%"], ["2 days away", "1.4%"], ["1 day away", "1.1%"], ["12 hours away", "0.8%"],
               ["6 hours away", "0.6%"], ["3 hours away", "0.4%"]]


def chance(ap: blend.Airport = AP) -> str:
    return views.chance_table(summary_of(ap), ap)


def lines_of(part: str) -> list[str]:
    """The headings and lines of a part, as a reader sees them, in order."""
    return [text(inner) for _, inner in re.findall(r"<(h2|p)[^>]*>(.*?)</\1>", part)]


def table_cells(part: str) -> list[list[str]]:
    """The chance table's heads and rows, as a reader sees each cell."""
    table = section(part, '<table class="fromhere">', "</table>")
    return [[text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr)] for tr in re.findall(r"<tr>(.*?)</tr>", table)]


def test_the_chance_table():
    """docs/flight-lookup.md, "Front page: the table", on the 2026-11-17 model, in order: the heading, the first line
    from the first and the last row, the column heads, the six rows to one decimal (C5's points), the line under it
    (the rows' mean, 4,922.8 flights, to the nearest 500) and the delay line (7.7% and 4.9%). Plain HTML: no
    script."""
    part = chance()
    assert lines_of(part) == ["Chance of cancellation, by how soon you fly", FIRST_LINE, UNDER, DELAY]
    assert table_cells(part) == [HEADS, *DESIGN_ROWS]
    assert (part.index('<p class="intro">') < part.index('<table class="fromhere">') < part.index('<p class="under">')
            < part.index('<p class="late">'))
    assert "<b>Chance of a delay of an hour or more:</b> about 8% for departures" in part
    assert "<script" not in part


def test_the_chance_table_on_the_front_page():
    assert lines_of(chance()) == lines_of(section(front(), '<section class="sec s-fromhere">', "</section>"))


def test_a_row_below_the_floor_reads_not_enough_flights_yet():
    got = table_cells(chance(airport(rows={12: made(8, 5069)})))
    assert got[4] == ["12 hours away", "Not enough flights yet"]
    assert got[1:4] + got[5:] == DESIGN_ROWS[:3] + DESIGN_ROWS[4:]
    assert FIRST_LINE in text(chance(airport(rows={12: made(8, 5069)})))  # a middle row: the first line stays


@pytest.mark.parametrize("h", [70, 3])
def test_the_first_line_is_left_out_when_the_first_or_the_last_row_is_below_the_floor(h):
    """Approved by the owner, 2026-11-17: the rows speak for themselves."""
    part = chance(airport(rows={h: made(9, 5000)}))
    assert lines_of(part) == ["Chance of cancellation, by how soon you fly", UNDER, DELAY]
    assert "Not enough flights yet" in [row[1] for row in table_cells(part)]


def test_the_line_under_the_table_takes_the_mean_of_the_rows_shown_to_the_nearest_500():
    """"About 5,000 flights" (docs/flight-lookup.md:880, the plan's decision): the mean of the rows shown, halves up. A
    row below the floor shows no figure, so its flights are not in it: (4,472 + 4,760 + 4,892 + 5,149 + 5,195) / 5 is
    4,893.6, where every row's 64,468 / 6 would read "about 10,500"."""
    assert UNDER in text(chance())
    assert "from about 5,000 flights since" in text(chance(airport(rows={12: made(8, 40000)})))
    rows_of = lambda n: dict.fromkeys(counting.CHECKPOINTS, made(10, n))  # noqa: E731
    assert "from about 4,500 flights since" in text(chance(airport(rows=rows_of(4749))))
    assert "from about 5,000 flights since" in text(chance(airport(rows=rows_of(4750))))
    assert "from about 12,500 flights since" in text(chance(airport(rows=rows_of(12250))))


def test_with_no_row_shown_the_line_under_the_table_is_left_out():
    part = chance(BELOW)
    assert [row[1] for row in table_cells(part)[1:]] == ["Not enough flights yet"] * 6
    assert lines_of(part) == ["Chance of cancellation, by how soon you fly"]


def test_the_delay_line_from_the_delay_rates():
    """Each direction's delays of an hour or more over its flights that flew: 7.7% and 4.9% read "about 8%" and "5%";
    under 1% reads so (Question 6e)."""
    assert lines_of(chance())[-1] == DELAY
    assert lines_of(chance(airport(delay={"D": made(12, 2000)})))[-1] == (
        "Chance of a delay of an hour or more: under 1% for departures and about 5% for arrivals. It's about the "
        "same however soon you fly.")


@pytest.mark.parametrize("direction", ["D", "A"])
def test_the_delay_line_is_left_out_while_a_directions_delays_are_below_the_floor(direction):
    """A delay rate is C8's (docs/flight-lookup.md:340), so, as a row of the table and the total, it shows a figure
    only once its delayed flights clear the floor; with no flight that flew there is none to show."""
    for thin in (made(9, 100), made(0, 0)):
        assert "Chance of a delay" not in text(chance(airport(delay={direction: thin})))


# --- the total -----------------------------------------------------------------------------------------------------

def total_of(page: str) -> str:
    return section(page, '<section class="sec s-total">', "</section>")


def tiles(part: str) -> list[tuple[str, str]]:
    """The total's tiles as (figure, label), as a reader sees them, in order."""
    found = re.findall(r'<span class="stat[^"]*"><b>(.*?)</b>(.*?)</span>', part)
    return [(text(figure), text(label)) for figure, label in found]


def total_lines(part: str) -> list[str]:
    return [text(inner) for inner in re.findall(r'<p(?: class="note")?>(.*?)</p>', part)]


LATE = "Some flights (at least 15 of the 104) were only marked cancelled after their scheduled time had passed."
LEFT_OUT = "285 flights are left out because there's no record of how they ended."


def test_the_total():
    """docs/flight-lookup.md, "Front page: the total": three tiles, the cancelled one in the cancelled colour and the
    third the percentage alone; the sentence; the late line; the left-out line."""
    part = total_of(front())
    assert tiles(part) == [("6,115", "flights"), ("104", "cancelled"), ("1.7%", "")]
    assert ('<p class="stats">\n<span class="stat"><b>6,115</b> flights</span>\n'
            '<span class="stat cancel"><b>104</b> cancelled</span>\n'
            '<span class="stat"><b>1.7%</b></span>\n</p>') in part
    assert total_lines(part) == ["Since 27 October, 104 of 6,115 flights at Ben Gurion were cancelled (1.7%).", LATE,
                                 LEFT_OUT]


def test_the_total_below_the_floor():
    """Approved by the owner, 2026-11-17: no third tile, and the sentence says why."""
    part = total_of(front(airport(FEW)))
    assert tiles(part) == [("420", "flights"), ("3", "cancelled")]
    assert total_lines(part)[0] == (
        "Since 27 October, 3 of 420 flights at Ben Gurion were cancelled. Not enough flights yet for a percentage.")
    assert "%" not in text(part)


def test_the_late_and_left_out_lines_are_left_out_at_zero():
    part = total_of(front(s=summary_of(late_after=0, unknown=0)))
    assert total_lines(part) == ["Since 27 October, 104 of 6,115 flights at Ben Gurion were cancelled (1.7%)."]
    assert "None" not in text(part)
    one = total_of(front(s=summary_of(late_after=1, unknown=1)))  # Question 6f
    assert total_lines(one)[1:] == [
        "Some flights (at least 1 of the 104) were only marked cancelled after their scheduled time had passed.",
        "1 flight is left out because there's no record of how it ended."]


def test_the_total_without_cancellations():
    part = total_of(front(NONE_YET, story=None, recent=[]))
    assert tiles(part) == [("900", "flights"), ("0", "cancelled")]
    assert total_lines(part)[0] == (
        "Since 27 October, 0 of 900 flights at Ben Gurion were cancelled. Not enough flights yet for a percentage.")


# --- the story and recent cancellations ----------------------------------------------------------------------------

def story_of(page: str) -> str:
    return section(page, '<section class="sec story">', "</section>")


def test_the_story_box():
    """docs/site-redesign.md, "Front page", item 6: the heading; the flight's title linked to its row; its day and
    scheduled time; its full list of changes in the "What changed" words."""
    box = story_of(front())
    assert "<h2>A recent cancellation, step by step</h2>" in box
    assert ('<h3><a href="flight/TO3459-D.html#2026-10-29-1710-ORY"><span class="d">TO 3459 · Tel Aviv to Paris'
            "</span></a></h3>") in box
    assert re.findall(r'<p class="when">(.*?)</p>', box) == ["Thursday 29 October · scheduled to leave at 17:10"]
    assert [text(li) for li in re.findall(r"<li>(.*?)</li>", box)] == [
        "Already on the list on 27 Oct at 20:04 on time, terminal 1",
        "Between 27 Oct 20:24 and 14:29 Check-in desks 345-348, zone B",
        "17:32 Expected to leave at 17:38 instead",
        "18:32 Expected to leave at 18:45 instead",
        "Between 19:16 and 19:32 Cancelled",
    ]
    assert '<ol class="changes">' in box and '<span class="t">Between 19:16 and 19:32</span>' in box


def test_the_story_box_holds_its_flight_pages_title_and_the_designs_day():
    """WZ 016, the design's example: "Tuesday 17 November · scheduled to leave at 05:35". The title is the one the
    build hands over, its flight page's own over every row of the number (docs/site-redesign.md, "Names"), which can
    name more cities than the told row's."""
    wz = flight("wz", datetime(2026, 11, 17, 5, 35), airline="WZ", flight_no="016", airport="ZIA", city_en="MOSCOW",
                **CLEAN)
    box = story_of(front(story=(rows(wz)[0], "WZ 016 · Tel Aviv to Moscow or Sochi")))
    assert ('<h3><a href="flight/WZ016-D.html#2026-11-17-0535-ZIA"><span class="d">WZ 016 · Tel Aviv to Moscow or '
            "Sochi</span></a></h3>") in box
    assert re.findall(r'<p class="when">(.*?)</p>', box) == ["Tuesday 17 November · scheduled to leave at 05:35"]


def test_no_story_box_without_a_story():
    page = front(story=None)
    assert 'class="sec story"' not in page and "step by step" not in page


def test_recent_cancellations():
    """docs/site-redesign.md, "Front page", item 7: the heading, the table with its "Notice given" column, each row
    linked to its day on the flight page, then "All cancelled flights"."""
    page = front()
    part = section(page, '<section class="sec s-recent">', "</section>")
    assert "<h2>Recent cancellations</h2>" in part
    table = section(part, '<table class="cancellations">', "</table>")
    assert cells(table) == [
        ["Date", "Flight", "Route", "Notice given"],
        ["Fri 30 Oct", "IZ 992", "New York (JFK) to Tel Aviv, scheduled to land at 13:50", "Notice given: 23+ hours"],
        ["Thu 29 Oct", "TO 3459", "Tel Aviv to Paris (ORY), scheduled to leave at 17:10", "Notice given: none"],
    ]
    assert '<a href="flight/IZ992-A.html#2026-10-30-1350-JFK">' in table
    assert '<a href="flight/TO3459-D.html#2026-10-29-1710-ORY">' in table
    assert part.index(table) < part.index('<p class="all"><a href="cancellations.html">All cancelled flights</a></p>')


def test_recent_cancellations_at_most_ten():
    page = front(recent=twelve_cancelled())
    shown = [row[1] for row in cells(section(page, '<table class="cancellations">', "</table>"))[1:]]
    assert shown == [f"LY {n}" for n in range(111, 101, -1)]  # the first ten given, in their order


# --- "Flights each day" and the day list ---------------------------------------------------------------------------

def chart_day(chart: str, day: str) -> str:
    """One day of the chart: its item and everything inside."""
    return re.search(rf'<li><a href="day/{day}.html"[^>]*>.*?</a></li>', chart, re.S).group(0)


def spoken(item: str) -> str:
    """A link's name as a screen reader gives it: its text, without what is hidden from it."""
    return text(re.sub(r'<svg [^>]*aria-hidden="true".*?</svg>', "", item, flags=re.S))


def test_the_chart_is_a_list_of_links():
    """docs/site-redesign.md, "Front page", item 8, and "Look A": one item per day, a link to its day page holding the
    date, the counts in text and its marks, then a thin bar. The bar is hidden from screen readers, so each link's
    name states the day's counts, never in colour alone."""
    chart = views.chart(CHART_DAYS)
    assert chart.startswith('<ol class="chart">\n<li><a href="day/2026-10-27.html"') and chart.endswith("</li>\n</ol>")
    items = re.findall(r"<li>(.*?)</li>", chart, re.S)
    assert [re.match(r'<a href="(day/[\d-]+\.html)"', item).group(1) for item in items] == [
        f"day/{info.day:%Y-%m-%d}.html" for info in CHART_DAYS]
    for item in items:
        assert item.count('<svg class="bar"') == 1 and item.endswith("</svg></a>")
        assert re.search(r'<span class="date">[^<]+</span> <span class="counts">', item)
    assert [spoken(item) for item in items] == [
        "Tue 27 Oct 348 flights · 4 cancelled · 12 unknown some flights missing",
        "Wed 28 Oct 370 flights · 8 cancelled · 190 unknown",
        "Thu 29 Oct 418 flights · 7 cancelled",
        "Fri 30 Oct 289 flights · 1 cancelled today",
        "Sat 31 Oct 161 flights upcoming",
        "Sun 1 Nov 40 flights upcoming · not all listed yet"]


def test_the_charts_marks():
    """Beside a day: "today" for the Israel date of the last record; "upcoming" for a later day; "upcoming · not all
    listed yet" for a later day the partial rule flags; "some flights missing" for a past day it flags. The link's
    classes carry the day's state and partial."""
    chart = views.chart(CHART_DAYS)
    days = [f"{info.day:%Y-%m-%d}" for info in CHART_DAYS]
    assert {day: re.findall(r'<span class="mark">(.*?)</span>', chart_day(chart, day)) for day in days} == {
        "2026-10-27": ["some flights missing"], "2026-10-28": [], "2026-10-29": [], "2026-10-30": ["today"],
        "2026-10-31": ["upcoming"], "2026-11-01": ["upcoming · not all listed yet"]}
    assert {day: re.search(r'<a href="[^"]*" class="([^"]*)">', chart_day(chart, day)).group(1) for day in days} == {
        "2026-10-27": "past partial", "2026-10-28": "past", "2026-10-29": "past", "2026-10-30": "today",
        "2026-10-31": "ahead", "2026-11-01": "ahead partial"}
    assert '<span class="counts">289 flights · 1 cancelled <span class="mark">today</span></span>' in chart


def test_the_bar():
    """One scale, the busiest day (418 flights) filling the bar's width: the day's flights as a thin line, the cancelled
    part as a block at its start and the unknown part beside it (the sheet draws them red and outlined); a part with
    none is left out."""
    chart = views.chart(CHART_DAYS)
    day = chart_day(chart, "2026-10-28")
    assert ('<svg class="bar" width="100%" height="9" viewBox="0 0 418 9" preserveAspectRatio="none" '
            'aria-hidden="true">') in day
    assert re.findall(r'<rect class="(\w+)" x="([\d.]+)" y="([\d.]+)" width="(\d+)" height="(\d+)"/>', day) == [
        ("rest", "0", "3.5", "370", "2"), ("cancelled", "0", "0", "8", "9"), ("unknown", "8", "0", "190", "9")]
    assert re.findall(r'<rect class="(\w+)"', chart_day(chart, "2026-10-31")) == ["rest"]
    assert re.findall(r'<rect class="(\w+)" x="(\d+)"', chart_day(chart, "2026-10-29")) == [("rest", "0"),
                                                                                           ("cancelled", "0")]


def day_page_counts(page: str) -> str:
    """A day page's counts as the chart prints them: the flights and the cancelled from its title, the unknown from
    its unknown line ("370 flights · 8 cancelled · 190 unknown"); a zero is left out of both."""
    parts = text(re.search(r"<h1>(.*?)</h1>", page).group(1)).split(" · ")[1:]
    unknown = re.search(r"For ([\d,]+) of these flights, there's no record of how", text(page))
    return " · ".join(parts + ([f"{unknown.group(1)} unknown"] if unknown else []))


def test_the_charts_counts_equal_the_day_pages_thousands_included():
    """The chart's counts read as the day pages' title and unknown line, thousands separators and "1 flight" too."""
    days = [*CHART_DAYS, DayInfo(date(2026, 12, 24), 3500, 1001, 1100, "ahead", False),
            DayInfo(date(2026, 12, 25), 1, 1, 0, "ahead", False)]
    chart = views.chart(days)
    for info in days:
        counts = re.search(r'<span class="counts">([^<]*)', chart_day(chart, f"{info.day:%Y-%m-%d}")).group(1)
        assert counts.rstrip() == day_page_counts(views.day_page(info, [], LAST_FETCH))
    assert "3,500 flights · 1,001 cancelled · 1,100 unknown" in chart and "1 flight · 1 cancelled" in chart


def test_the_day_list():
    """"Pick a day:" and every day the site has, linked, so that no flight is out of reach without JavaScript; the list
    is the target of the line in the search box's place."""
    got = views.day_list(ALL_DAYS)
    assert got.startswith('<p class="days-h">Pick a day:</p>\n<ol class="days" id="days">\n') and got.endswith("</ol>")
    assert re.findall(r'<li><a href="(day/[\d-]+\.html)">([^<]*)</a></li>', got) == [
        (f"day/{x.day:%Y-%m-%d}.html", f"{x.day:%a} {x.day.day} {x.day:%b}") for x in ALL_DAYS]
    assert '<li><a href="day/2026-10-26.html">Mon 26 Oct</a></li>' in got


def test_the_front_page_draws_the_chart_days_and_lists_every_day():
    page = front()
    part = section(page, '<section class="sec s-days">', "</section>")
    assert "<h2>Flights each day</h2>" in part
    assert views.chart(CHART_DAYS) in part and views.day_list(ALL_DAYS) in part
    assert "day/2026-10-26.html" not in section(part, '<ol class="chart">', "</ol>")  # every day, but only the chosen


def test_the_front_page_is_updated_at_the_last_record(israeli_machine):
    """The front page's top line says when the last record is, not the default of these tests."""
    page = front(last=datetime(2026, 11, 17, 7, 46, 12))
    assert '<p class="updated" data-updated="2026-11-17T07:46:12Z">Updated 17 Nov at 09:46</p>' in page


# --- review focus 3: an archive too small for figures -------------------------------------------------------------

def test_front_page_without_cancellations(israeli_machine):
    """Review Focus 3: the story left out; the table's rows and the total with their below-the-floor words;
    everything else present."""
    page = views.front_page(summary_of(NONE_YET), NONE_YET, None, [], CHART_DAYS, CHART_DAYS, entries(), LAST_FETCH)
    assert 'class="sec story"' not in page
    assert '<table class="fromhere">' in page and "Since 27 October, 0 of 900 flights" in text(page)
    assert FIND in page and '<ol class="days" id="days">' in page
    assert 'id="flights-data"' in page and '<ol class="chart">' in page
    assert "<h2>Recent cancellations</h2>" in page and "<p>No cancelled flights so far.</p>" in page
    assert 'class="cancellations"' not in page and "All cancelled flights" in text(page)
    assert UPDATED in page
    assert all(t in text(page) for t in (words.SOURCE_SHORT, words.UNOFFICIAL, words.TIMES_NOTE))


def test_a_model_below_the_floor_everywhere():
    """Review Focus 3: a fresh archive clears the floor nowhere. No figure anywhere on the page: each row reads "Not
    enough flights yet", the total says why it has no percentage, and the late line, at zero, is left out."""
    page = front(BELOW, s=summary_of(BELOW, late_after=0))
    assert "%" not in text(page) and "None" not in text(page)
    assert [row[1] for row in table_cells(page)[1:]] == ["Not enough flights yet"] * 6
    assert "Not enough flights yet for a percentage." in text(page)


def test_front_page_whose_only_cancellation_has_an_unknown_warning():
    """Review Focus 3: it still builds, with the flight as its story."""
    page = unknown_only_front()
    assert "Since 27 October, 1 of 900 flights at Ben Gurion was cancelled." in text(page)
    box = story_of(page)
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
        "front page, no cancellations": views.front_page(summary_of(NONE_YET), NONE_YET, None, [], CHART_DAYS,
                                                         ALL_DAYS, entries(), LAST_FETCH),
        "front page, a warning unknown": unknown_only_front(),
        "front page, a delayed story": delayed_story_front(),
        "front page, below the floor everywhere": front(BELOW, s=summary_of(BELOW, late_after=0)),
        "front page, the first and a middle row below the floor": front(airport(rows={70: made(8, 4472),
                                                                                     24: made(8, 4892)})),
        "front page, a day of every mark": front(chart_days=[*CHART_DAYS, DayInfo(date(2026, 11, 2), 9, 0, 0,
                                                                                   "today", True)]),
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
