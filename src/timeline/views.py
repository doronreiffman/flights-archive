"""The redesigned site's HTML (docs/site-redesign.md, "Pages"): pure functions from display rows to pages.

Every string from the airport's data (flight numbers, airline names, cities, airport codes) goes through `d()`,
which escapes it and marks it as data. A warning beside a label is always the flight page's sentence
(`words.warning_sentence`): the upload check reads a page as flat text across tags, so a label followed by the bare
text ("CANCELLED" then "at least 23 hours") would read as "cancelled at". The bare text appears only in the
cancellations table's Warning column, whose previous cell ends with a scheduled time.
"""
from __future__ import annotations

import html
import json
from collections import Counter
from datetime import date, datetime

from . import flights, words
from .flights import DayInfo, Row

HOME = "Cancelled flights at Tel Aviv airport"
NONE_CANCELLED = "No flights listed as cancelled so far."


def e(value) -> str:
    """The site's own text, escaped."""
    return html.escape(str(value))


def d(value) -> str:
    """A string from the airport's data, escaped and marked as data; "" for None."""
    return "" if value is None else f'<span class="d">{html.escape(str(value))}</span>'


def layout(title: str, body: str, root: str, head_extra: str = "") -> str:
    """A whole page; `root` is the way back to the site's top folder ("" or "../")."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{e(title)}</title>\n"
        + (f"{head_extra}\n" if head_extra else "")
        + f'<link rel="stylesheet" href="{root}style.css">\n</head>\n<body>\n'
        f"<main>\n{body}\n</main>\n"
        "<footer>\n"
        f"<p>{e(words.SOURCE_SHORT)} {e(words.UNOFFICIAL)} {e(words.TIMES_NOTE)}</p>\n"
        f'<p><a href="{root}how-it-works.html">How this works</a> · '
        f'<a href="{e(words.CODE_URL)}">Code on GitHub</a> · Built by {e(words.BUILT_BY)}</p>\n'
        "</footer>\n</body>\n</html>\n")


# --- pieces ----------------------------------------------------------------------------------------

def _back(root: str) -> str:
    return f'<p class="back"><a href="{root}index.html">← {e(HOME)}</a></p>'


def _short_date(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"  # Thu 29 Oct


def _long_date(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"  # Thursday 29 October 2026


def _link(r: Row, root: str) -> str:
    """The flight number, linked to its row on its own page."""
    return f'<a href="{root}{e(r.page)}#{e(r.anchor)}">{d(f"{r.airline} {r.flight_no}")}</a>'


def _numbers(fl: tuple[Row, ...], root: str) -> str:
    return ", ".join(_link(r, root) for r in fl)


def _place(r: Row) -> str:
    return f"{d(r.city)} ({d(r.airport)})"  # Paris (ORY)


def _to_or_from(r: Row) -> str:
    return f"{'to' if r.direction == 'D' else 'from'} {_place(r)}"


def _route(r: Row) -> str:
    """The cancellations table's route: "Tel Aviv to Paris (ORY), scheduled to leave 17:10"."""
    way = f"Tel Aviv to {_place(r)}" if r.direction == "D" else f"{_place(r)} to Tel Aviv"
    return f"{way}, {e(words.scheduled(r.direction, r.sched_final, r.day))}"


def _labels(r: Row) -> str:
    """The main label, and DELAYED beside it when the airport showed it: "LANDED · DELAYED"."""
    pills = [r.label] + (["DELAYED"] if r.delayed else [])
    return " · ".join(f'<span class="label l-{label.lower().replace(" ", "-")}">{e(label)}</span>'
                      for label in pills)


def _names(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _newest_first(rows: list[Row]) -> list[Row]:
    by_place = sorted(rows, key=lambda r: (r.airport, r.flight_id))
    return sorted(by_place, key=lambda r: r.sched_final, reverse=True)  # stable: ties keep the airport order


def _count_parts(info: DayInfo) -> list[str]:
    """A day's flights in plain numbers, zeros left out: ["418 flights", "7 cancelled", "190 unknown"]."""
    parts = [f"{info.total} flight" + ("" if info.total == 1 else "s")]
    if info.cancelled:
        parts.append(f"{info.cancelled} cancelled")
    if info.unknown:
        parts.append(f"{info.unknown} unknown")
    return parts


def _counts(info: DayInfo) -> str:
    """The day page's count line: "418 flights · 7 cancelled · 190 unknown"; the chart says the same."""
    return " · ".join(_count_parts(info))


def _changes(r: Row) -> str:
    """What changed, oldest first, the time in a left column."""
    items = [f'<li><span class="t">{e(left)}</span> {e(what)}</li>' for left, what in r.lines]
    return "\n".join(['<ol class="changes">', *items, "</ol>"])


# --- flight page -----------------------------------------------------------------------------------

_DID = {words.DEPARTED: "departed", words.LANDED: "landed", words.CANCELLED: "cancelled"}
_ARE = {words.UPCOMING: "upcoming", words.NO_FINAL_UPDATE: "with no final update", words.UNKNOWN: "unknown"}


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def _how_many(n: int) -> str:
    return {1: "one", 2: "two"}.get(n, str(n))


def _summary(rows: list[Row], since: date) -> str:
    """"Since 27 October: departed once, cancelled once, one upcoming.", in the labels' order."""
    counts = Counter(r.label for r in rows)
    parts = [f"{_DID[label]} {_times(counts[label])}" if label in _DID else f"{_how_many(counts[label])} {_ARE[label]}"
             for label in words.LABEL_ORDER if counts[label]]
    return f"Since {since.day} {since:%B}: {', '.join(parts)}."


def _flight_row(r: Row, partners: tuple[Row, ...], many_places: bool) -> str:
    when = " · ".join(t for t in (words.scheduled(r.direction, r.sched_final, r.day), r.last_expected) if t)
    head = [f'<span class="date">{_short_date(r.day)}</span>', f'<span class="sched">{e(when)}</span>']
    if many_places:
        head.append(f'<span class="place">{_to_or_from(r)}</span>')
    head.append(_labels(r))
    out = [f'<div class="row" id="{e(r.anchor)}">', f'<p class="head">{" ".join(head)}</p>']
    if r.label_note:
        out.append(f'<p class="note">{e(r.label_note)}</p>')
    if r.warning:
        sentence = " ".join(t for t in (words.warning_sentence(r.warning), r.warning_note) if t)
        out.append(f'<p class="warn">{e(sentence)}</p>')
    if r.changed_back:
        out.append(f'<p class="note">{e(r.changed_back)}</p>')
    if partners:
        out.append(f'<p class="note">Probably the same flight as {_names([_link(p, "../") for p in partners])} '
                   "(same time, terminal and check-in desks).</p>")
    if r.lines:
        out.append("<details open>" if r.label == words.CANCELLED else "<details>")
        out += ["<summary>What changed</summary>", _changes(r), "</details>"]
    out.append("</div>")
    return "\n".join(out)


def flight_page(rows: list[Row], partners: dict[str, tuple[Row, ...]], since: date) -> str:
    """One flight number and direction: every row of it, newest first. `since` is the day records start.
    The header names the place when the page has one (the Hebrew city when it has one city); otherwise each
    row names its own."""
    newest = _newest_first(rows)
    top = newest[0]
    title = flights.page_title(rows)
    many_places = len({(r.city, r.airport) for r in rows}) > 1
    who = [f"{d(top.airline_name)} (as the airport lists it)"]
    if not many_places:
        who.append(f"{'lands at' if top.direction == 'D' else 'leaves from'} {_place(top)}")
    if len({r.city for r in rows}) == 1 and top.city_he:
        who.append(f'<span lang="he" dir="rtl">{d(top.city_he)}</span>')
    body = [_back("../"), f"<h1>{d(title)}</h1>", f'<p class="who">{" · ".join(who)}</p>',
            f'<p class="summary">{e(_summary(rows, since))}</p>']
    if any(r.last_expected for r in rows):
        body.append(f'<p class="note">{e(words.DELAY_SENTENCE)}</p>')
    body += [_flight_row(r, partners.get(r.flight_id, ()), many_places) for r in newest]
    return layout(title, "\n".join(body), "../")


# --- day page --------------------------------------------------------------------------------------

def _day_row(fl: tuple[Row, ...]) -> str:
    r = fl[0]
    parts = [f'<span class="t">{words.clock(r.sched_final, r.day)}</span>', _numbers(fl, "../"), _to_or_from(r),
             _labels(r)]
    if r.warning:
        parts.append(f'<span class="warn">{e(words.warning_sentence(r.warning))}</span>')
    return f"<li>{' '.join(parts)}</li>"


def day_page(info: DayInfo, flights_: list[tuple[Row, ...]]) -> str:
    """One day's flights: departures, then arrivals, in scheduled order; each number links to its row."""
    body = [_back("../"), f"<h1>{_long_date(info.day)}</h1>", f'<p class="count">{_counts(info)}</p>']
    if info.partial:
        body.append("<p class=\"note\">Incomplete: some of this day's flights may be missing from the records.</p>")
    if info.unknown:  # every UNKNOWN flight; each flight page's label note gives its reason
        body.append(f'<p class="note">No known outcome for {info.unknown} of these flights.</p>')
    for direction, heading in (("D", "Departures"), ("A", "Arrivals")):
        fls = sorted((fl for fl in flights_ if fl[0].direction == direction),
                     key=lambda fl: (fl[0].sched_final, fl[0].airline, fl[0].flight_no, fl[0].airport,
                                     fl[0].flight_id))
        body.append(f"<h2>{heading}</h2>")
        body.append('<ul class="flights">\n' + "\n".join(_day_row(fl) for fl in fls) + "\n</ul>" if fls
                    else "<p>None.</p>")
    return layout(_long_date(info.day), "\n".join(body), "../")


# --- all cancellations -----------------------------------------------------------------------------

def _cancellations_table(cancelled: list[tuple[Row, ...]], root: str) -> str:
    """Date, flight, route with the scheduled time, and the bare warning text: the cell before it ends with a
    time, so no label runs into it."""
    rows = [f"<tr><td>{_short_date(fl[0].day)}</td><td>{_numbers(fl, root)}</td><td>{_route(fl[0])}</td>"
            f"<td>{e(fl[0].warning)}</td></tr>" for fl in cancelled]
    return ('<table class="cancellations">\n<thead><tr><th>Date</th><th>Flight</th><th>Route</th><th>Warning</th>'
            "</tr></thead>\n<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>")


def cancellations_page(flights_: list[tuple[Row, ...]]) -> str:
    """Every cancelled flight among `flights_`, newest first."""
    cancelled = flights.recent_cancellations(flights_, n=len(flights_))
    table = _cancellations_table(cancelled, "") if cancelled else f"<p>{NONE_CANCELLED}</p>"
    body = [_back(""), "<h1>All cancellations</h1>", "<p>Every flight listed as cancelled, newest first.</p>", table]
    return layout("All cancellations", "\n".join(body), "")


# --- how this works --------------------------------------------------------------------------------

def _gap(start: datetime, end: datetime) -> str:
    """A stretch with no records, from the model's naive UTC times, in Israel time with the dates."""
    a, b = words.il_time(start), words.il_time(end)
    return f"There are no records from {a.day} {a:%B %H:%M} to {b.day} {b:%B %H:%M}."


def how_it_works_page(attribution: str, gaps: list[tuple[datetime, datetime]]) -> str:
    """The plan's Appendix A, verbatim; the only page that may say "I" and name how the data is collected.
    `gaps` are (start, end) in the model's naive UTC."""
    gap_sentences = "".join(f" {_gap(a, b)}" for a, b in gaps)
    body = f"""{_back("")}
<h1>How this works</h1>
<h2>Where the data comes from</h2>
<p>The Israel Airports Authority publishes Ben Gurion Airport's list of departures and arrivals on data.gov.il, the Israeli government's open-data site. The list shows each flight from about three days before it is scheduled until about a day after. I built a small program that checks the list every 2 minutes and saves each new version, so a flight's history stays after it drops off the list.</p>
<p>{e(attribution)}</p>
<h2>What the labels mean</h2>
<ul>
<li>DEPARTED and LANDED: the airport's final word on the flight.</li>
<li>CANCELLED: the airport's list showed the flight as cancelled.</li>
<li>UPCOMING: still on the list; its scheduled time hasn't come yet.</li>
<li>NO FINAL UPDATE: its scheduled time has passed, and the list hasn't given a final status yet.</li>
<li>UNKNOWN: it left the list without a final status, or while records are missing.</li>
<li>DELAYED: shown beside another label when the airport's list said "delayed" at some point.</li>
</ul>
<h2>How much warning</h2>
<p>For a cancelled flight, the warning is how long before its scheduled time the list already showed it as cancelled. The list refreshes about every 15 minutes, so the change is known to within that window. Where records are missing, the warning is a range ("between 7 and 50 hours"). When a flight was already cancelled the first time it appeared in the records, only a lower limit is known ("at least 23 hours"). For the same reason, the time of a cancellation is always given as a range. The airline may have told passengers earlier than the list showed.</p>
<h2>Why there are no delay figures</h2>
<p>The list gives an expected time for each flight. It doesn't say whether that is when the plane leaves the gate or when it takes off. Until that is settled, this site shows the airport's times as they are and doesn't turn them into delay figures.</p>
<h2>"Final" and "not final"</h2>
<p>The airport also uses the words "final" and "not final". It doesn't publish what they mean, so this site quotes them as they are.</p>
<h2>Probably the same flight</h2>
<p>Airlines often sell seats on one flight under several flight numbers. When numbers share the same time, terminal and check-in desks, this site lists them as probably the same flight. The list doesn't say so itself, and arrivals with no check-in desks can occasionally be grouped by mistake.</p>
<h2>Gaps in the records</h2>
<p>Records start on the evening of 27 October 2026.{gap_sentences} A flight that left the list during a gap is marked UNKNOWN.</p>
<h2>How it's built</h2>
<p>The program runs on AWS Lambda and saves each version once, to storage where it is locked for ten years. A Python data model turns the saved versions into one history per flight, and this site is generated from that model. Every rule has tests, and the tests are themselves checked by breaking the code on purpose and confirming that a test fails. The code is <a href="{e(words.CODE_URL)}">on GitHub</a>.</p>"""
    return layout("How this works", body, "")


# --- front page ------------------------------------------------------------------------------------

TITLE = f"{HOME} (Ben Gurion)"
LEDE = ("A record of flights in and out of Ben Gurion Airport, kept since 27 October 2026, "
        "and which ones were cancelled.")


def description() -> str:
    """The front page's description, read when the page is built; a built-by line that ends with a full stop
    does not get a second one."""
    return ("Which flights in and out of Tel Aviv's Ben Gurion Airport were cancelled, and how much warning "
            f"there was. Built by {words.BUILT_BY.removesuffix('.')}.")


SEARCH_HINT = "Flight number or city, e.g. LY 001 or Paris"
RECENT = 10  # cancellations on the front page; the rest are on cancellations.html

# The chart's sizes, in px: text keeps its own size on any screen, and only the bars stretch (a share of the width).
_DATE_W = 84  # the date column; the counts and the bar start here
_DAY_H = 34  # one day: the date and counts, then the bar with one mark under the date
_MARK_H = 12  # each further mark under the date


def search_json(entries: list[dict]) -> str:
    """The search entries as JSON for a script element: every "<" escaped, so a name containing "</script>" cannot
    end the element."""
    return json.dumps(entries, sort_keys=True, ensure_ascii=False).replace("<", "\\u003c")


def _marks(info: DayInfo) -> list[str]:
    """The words under a day's date: "today" for the Israel date of the last record, "ahead" for later days,
    "incomplete" for a day the partial rule flags."""
    return [word for word, on in (("today", info.state == "today"), ("ahead", info.state == "ahead"),
                                  ("incomplete", info.partial)) if on]


def chart_svg(days: list[DayInfo]) -> str:
    """One horizontal bar per day, top to bottom, each linked to its day page: the date with its marks, the counts in
    text ("370 flights · 8 cancelled · 190 unknown", as on the day page), and the bar in three parts (cancelled,
    unknown, the rest) on one scale, the busiest day filling the bar's width. The classes carry the look: the day's
    state (past, today, ahead) and partial; the parts cancelled, unknown, rest. The accessible name states every
    day's counts, so the numbers never rest on color."""
    top = max((info.total for info in days), default=1)
    out, said, y = [], [], 0
    for info in days:
        parts = _count_parts(info)
        name, marks = _short_date(info.day), _marks(info)
        said.append(f"{', '.join([name, *marks])}: {', '.join(parts)}.")
        shares = (("cancelled", info.cancelled), ("unknown", info.unknown),
                  ("rest", info.total - info.cancelled - info.unknown))
        bars, x = [], 0
        for cls, n in shares:
            if n:
                bars.append(f'<rect class="{cls}" x="{x}" y="0" width="{n}" height="8"/>')
            x += n
        classes = " ".join([info.state] + ["partial"] * info.partial)
        out += [f'<a href="day/{info.day:%Y-%m-%d}.html" class="{classes}">',
                f'<text x="0" y="{y + 11}" class="date">{name}</text>',
                f'<text x="{_DATE_W}" y="{y + 11}">{" · ".join(parts)}</text>',
                f'<svg class="bar" x="{_DATE_W}" y="{y + 15}" width="72%" height="8" viewBox="0 0 {top} 8" '
                f'preserveAspectRatio="none">{"".join(bars)}</svg>',
                *(f'<text x="0" y="{y + 23 + _MARK_H * i}" class="mark">{mark}</text>' for i, mark in enumerate(marks)),
                "</a>"]
        y += _DAY_H + _MARK_H * max(len(marks) - 1, 0)
    label = " ".join(["Flights each day.", *said])
    # role="group", not "img": an image's children are hidden from screen readers, and these are links.
    return "\n".join([f'<svg class="chart" width="100%" height="{y}" font-size="12" role="group" '
                      f'aria-label="{e(label)}">', *out, "</svg>"])


def _story(r: Row) -> str:
    """One cancelled flight's story: its title linked to its row, the day and scheduled time, and what changed."""
    return "\n".join(['<section class="story">',
                      f'<h2><a href="{e(r.page)}#{e(r.anchor)}">{d(flights.page_title([r]))}</a></h2>',
                      f"<p>{_long_date(r.day)}, {e(words.scheduled(r.direction, r.sched_final, r.day))}</p>",
                      _changes(r), "</section>"])


def front_page(cancelled: int, known: int, story: Row | None, recent: list[tuple[Row, ...]],
               chart_days: list[DayInfo], all_days: list[DayInfo], entries: list[dict], last_record: datetime) -> str:
    """The front page, top to bottom as docs/site-redesign.md lists it. The caller chooses: the headline's counts,
    the story (None for none), the recent cancellations newest first (at most RECENT shown), the chart's days and
    every day for the list under it, the search entries, and the last record's time (the model's naive UTC)."""
    about = description()
    head = "\n".join([f'<meta name="description" content="{e(about)}">',
                      f'<meta property="og:title" content="{e(TITLE)}">',
                      f'<meta property="og:description" content="{e(about)}">',
                      '<meta property="og:type" content="website">',
                      '<script src="search.js" defer></script>'])
    body = [f"<h1>{e(HOME)}</h1>", f'<p class="lede">{e(LEDE)}</p>']
    headline = words.headline(cancelled, known)
    if headline:
        body.append(f'<p class="headline">{e(headline)}</p>')
    if story is not None:
        body.append(_story(story))
    updated = words.il_time(last_record)
    day_links = " · ".join(f'<a href="day/{x.day:%Y-%m-%d}.html">{_short_date(x.day)}</a>' for x in all_days)
    body += [f'<input id="search" type="search" hidden placeholder="{e(SEARCH_HINT)}" '
             'aria-label="Find a flight by number or city">',
             '<ul id="search-results" hidden></ul>',
             f'<script type="application/json" id="flights-data">{search_json(entries)}</script>',
             "<h2>Recent cancellations</h2>",
             _cancellations_table(recent[:RECENT], "") if recent else f"<p>{NONE_CANCELLED}</p>",
             '<p><a href="cancellations.html">All cancellations</a></p>',
             "<h2>Flights each day</h2>",
             chart_svg(chart_days),
             f'<p class="days">Every day: {day_links}</p>',
             f'<p class="updated">Last updated {updated.day} {updated:%b %Y, %H:%M}</p>',
             f'<p class="built">Built by {e(words.BUILT_BY)} · <a href="how-it-works.html">How this works</a> · '
             f'<a href="{e(words.CODE_URL)}">Code on GitHub</a></p>']
    return layout(TITLE, "\n".join(body), "", head)
