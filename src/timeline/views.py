"""The redesigned site's HTML (docs/site-redesign.md, "Pages"): pure functions from display rows to pages.

Every string from the airport's data (flight numbers, airline names, cities, airport codes) goes through `d()`,
which escapes it and marks it as data. A notice beside a label is always the flight page's sentence
(`Notice.sentence`): the upload check reads a page as flat text across tags, so a label followed by the short form
("CANCELLED" then "at least 23 hours") would read as "cancelled at". The short form appears only in the
cancellations table's "Notice given" column, whose previous cell ends with a scheduled time.
"""
from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime

from . import blend, flights, words
from .display import Summary
from .flights import DayInfo, ListFlight, Row
from .rates import Rate


def e(value) -> str:
    """The site's own text, escaped."""
    return html.escape(str(value))


def d(value) -> str:
    """A string from the airport's data, escaped and marked as data; "" for None."""
    return "" if value is None else f'<span class="d">{html.escape(str(value))}</span>'


def _top(root: str, updated: datetime, front: bool) -> str:
    """The top line (docs/site-redesign.md, "Every page"): the site's name, linked to the front page and the page's
    <h1> on the front page only; "Tel Aviv airport"; and when the page was updated, the last sighting. The line reads
    its date and time in Israel time, which stands without scripts; fromhere.js writes the page's age in its place
    from the instant, the model's naive UTC written as the UTC instant it is (docs/flight-lookup.md, "Pages")."""
    tag = "h1" if front else "p"
    instant = f"{updated:%Y-%m-%dT%H:%M:%SZ}"
    return "\n".join(['<header class="mast">',
                      f'<{tag} class="wordmark"><a href="{root}index.html">{e(words.NAME)}</a></{tag}>',
                      f'<p class="where">{e(words.WHERE)}</p>',
                      f'<p class="updated" data-updated="{instant}">{e(words.updated_at(updated))}</p>',
                      "</header>"])


# The Regular and SemiBold faces most text is set in, asked for before the style sheet names them; the Light face waits
# for the sheet, and the Hebrew one for a page with Hebrew on it (docs/site-redesign.md, "Look A", Loading).
PRELOADED = ("sans-cond-400.woff2", "sans-cond-600.woff2")


def layout(title: str, body: str, root: str, updated: datetime, head_extra: str = "", front: bool = False) -> str:
    """A whole page; `root` is the way back to the site's top folder ("" or "../"), `updated` the last sighting (the
    model's naive UTC) and `front` whether this is the front page. Every page loads fromhere.js, which writes the
    page's age into the top line."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{e(title)}</title>\n"
        + "".join(f'<link rel="preload" href="{root}fonts/{name}" as="font" type="font/woff2" crossorigin>\n'
                  for name in PRELOADED)
        + (f"{head_extra}\n" if head_extra else "")
        + f'<script src="{root}fromhere.js" defer></script>\n'
        + f'<link rel="stylesheet" href="{root}style.css">\n</head>\n<body>\n'
        f"{_top(root, updated, front)}\n"
        f"<main>\n{body}\n</main>\n"
        "<footer>\n"
        f"<p>{e(words.SOURCE_SHORT)} {e(words.UNOFFICIAL)} {e(words.TIMES_NOTE)}</p>\n"
        f'<p>{e(words.ESTIMATES)} <a href="{root}how-it-works.html#{words.MEANS_ANCHOR}">{e(words.MEANS)}</a></p>\n'
        f'<p><a href="{root}how-it-works.html">How this works</a> · '
        f'<a href="{e(words.CODE_URL)}">Code on GitHub</a> · Built by {e(words.BUILT_BY)}</p>\n'
        "</footer>\n</body>\n</html>\n")


# --- pieces ----------------------------------------------------------------------------------------

def _short_date(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"  # Thu 29 Oct


def _link(r: Row, root: str) -> str:
    """The flight number, linked to its row on its own page."""
    return f'<a href="{root}{e(r.page)}#{e(r.anchor)}">{d(f"{r.airline} {r.flight_no}")}</a>'


def _numbers(fl: ListFlight, root: str) -> str:
    """The flight's numbers, linked; a number marked cancelled in a flight that is not (flights.others) comes after
    the rest, in brackets, one each: "LH 695 (LH 0691A: cancelled)" (docs/flight-lookup.md, "In lists"). The bracket
    also keeps a place name from following "cancelled"."""
    apart = flights.others([fl])
    named = [_link(r, root) for r in fl.rows if r.flight_id not in apart]
    return " ".join([", ".join(named), *(f"({_link(r, root)}: cancelled)" for r in fl.rows if r.flight_id in apart)])


def _place(r: Row) -> str:
    return f"{d(r.city)} ({d(r.airport)})"  # Paris (ORY)


def _to_or_from(r: Row) -> str:
    return f"{'to' if r.direction == 'D' else 'from'} {_place(r)}"


def _route(r: Row) -> str:
    """The cancellations table's route: "Tel Aviv to Moscow (ZIA), scheduled to leave at 05:35"."""
    way = f"Tel Aviv to {_place(r)}" if r.direction == "D" else f"{_place(r)} to Tel Aviv"
    return f"{way}, {e(words.scheduled(r.direction, r.sched_final, r.day))}"


def _kind(label: str) -> str:
    """A label as a class name's end: "NO NEWS YET" is "no-news-yet"."""
    return label.lower().replace(" ", "-")


def _labels(label: str, delayed: bool) -> str:
    """The main label, and DELAYED beside it when the airport showed it: "LANDED · DELAYED"."""
    pills = [label] + (["DELAYED"] if delayed else [])
    return " · ".join(f'<span class="label l-{_kind(label)}">{e(label)}</span>' for label in pills)


def _names(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _changes(r: Row) -> str:
    """What changed, oldest first, the time in a left column."""
    items = [f'<li><span class="t">{e(left)}</span> {e(what)}</li>' for left, what in r.lines]
    return "\n".join(['<ol class="changes">', *items, "</ol>"])


# --- flight page -----------------------------------------------------------------------------------

def _when(r: Row) -> tuple:
    """A day's place in time: its scheduled instant (the model's UTC), then its airport and row, so that two flights at
    one time (LY 5115 to Batumi and to Kutaisi at 16:30 on 28 October) keep one order whatever order the rows come in."""
    return r.sched_utc_final, r.airport, r.flight_id


def _quotes_final(r: Row) -> bool:
    """Whether a day's list of changes quotes the airport's "final" or "not final"."""
    quoted = (words.STATUS_WORDS["FINAL"], words.STATUS_WORDS["NOT FINAL"])
    return any(q in what for _, what in r.lines for q in quoted)


def _head(r: Row, many_places: bool) -> str:
    """A day's first line: the date written out, the time line, the city when the page has more than one, the labels."""
    parts = [f'<span class="date">{e(words.long_date(r.day))}</span>',
             f'<span class="sched">{e(words.time_line(r.direction, r.sched_final, r.est_final, r.label, r.day))}</span>']
    if many_places:
        parts.append(f'<span class="place">{_to_or_from(r)}</span>')
    parts.append(f'<span class="labels">{_labels(r.label, r.delayed)}</span>')
    return f'<p class="head">{" ".join(parts)}</p>'


def _day(r: Row, partners: tuple[Row, ...], other: tuple[str, tuple[Row, ...]] | None, many_places: bool,
         updated: datetime, *, top: bool, expected_note: bool, final_note: bool) -> str:
    """One day, in the order of docs/site-redesign.md ("Flight page", a day's lines) as the plan's markup contract
    places it: the head; the label's line, the notice sentence and the changed-back line; then the twin line or, on a
    day ahead marked cancelled, "This flight is marked cancelled. Contact your airline." (never both: Question 3); the
    place of the chances on a day labelled UPCOMING; on a day ahead, the hidden "has passed" line; the support in the
    top day; last, the day's own lines in .own: "Also sold as …", the note on expected times and "What changed", open
    for a cancelled day, with the note on "final" under it. A day ahead (scheduled after `updated`, the last sighting)
    carries its scheduled time as the UTC instant it is, for the page script."""
    ahead = r.sched_utc_final > updated
    sched = f' data-sched="{r.sched_utc_final:%Y-%m-%dT%H:%M:%SZ}"' if ahead else ""  # the model's naive UTC, as itself
    out = [f'<section class="day" id="{e(r.anchor)}"{sched}>', _head(r, many_places)]
    if r.label_note:
        out.append(f'<p class="note">{e(r.label_note)}</p>')
    if r.notice:
        out.append(f'<p class="warn">{e(r.notice.sentence)}</p>')
    if r.changed_back:
        out.append(f'<p class="note">{e(r.changed_back)}</p>')
    if other:  # the twin line: "This number was cancelled, but the flight probably left as LH 695."
        before, after = words.twin(other[0])
        out.append(f'<p class="note">{e(before)} {_names([_link(p, "../") for p in other[1]])}{e(after)}</p>')
    elif ahead and r.label == words.CANCELLED:
        bold, rest = words.MARKED_CANCELLED
        out.append(f'<p class="marked"><b>{e(bold)}</b> {e(rest)}</p>')
    if r.label == words.UPCOMING:
        out.append('<div class="chances"></div>')
    if ahead:
        out.append(f'<p class="passed" hidden>{e(words.has_passed(updated))}</p>')
    if top:
        out.append('<div class="support"></div>')
    out.append('<div class="own">')
    if partners:  # "Also sold as LY 9252 and LY 9255 (probably the same plane)."
        out.append(f'<p class="note">{e(words.ALSO_SOLD)} {_names([_link(p, "../") for p in partners])} '
                   f"{e(words.SAME_PLANE)}</p>")
    if expected_note:
        out.append(f'<p class="note expected">{e(words.EXPECTED_NOTE)}</p>')
    if r.lines:
        out.append("<details open>" if r.label == words.CANCELLED else "<details>")
        out += ["<summary>What changed</summary>", _changes(r)]
        if final_note:
            out.append(f'<p class="note quoted">{e(words.FINAL_NOTE)}</p>')
        out.append("</details>")
    out += ["</div>", "</section>"]
    return "\n".join(out)


def _strip(by_time: list[Row], number: str) -> str:
    """The strip of days (docs/flight-lookup.md, "Flight page: the strip of days"): one mark per row, oldest first,
    each a link to its day, its shape by its label (the class), named by its day and label for a screen reader and as
    a tooltip, the day of the month under it and the month's name over the first mark of each month. The key counts
    the strip's own marks, each kind beside its mark."""
    counts = Counter(r.label for r in by_time)
    kinds = [label for label in words.LABEL_ORDER if counts[label]]
    key = '<span class="sep"> · </span>'.join(f'<span class="k s-{_kind(label)}">{e(part)}</span>'
                                               for label, part in zip(kinds, words.strip_key(counts)))
    marks, month = [], None
    for r in by_time:
        name = e(words.mark_name(r.day, r.label))
        li = "<li>" if (r.day.year, r.day.month) == month else f'<li class="mo" data-mo="{r.day:%b}">'
        month = (r.day.year, r.day.month)
        marks.append(f'{li}<a class="s-{_kind(r.label)}" href="#{e(r.anchor)}" aria-label="{name}" title="{name}">'
                     f"<i></i><b>{r.day.day}</b></a></li>")
    return "\n".join(['<section class="record">', f"<h2>{words.strip_heading(number, e, d)}</h2>",
                      f'<p class="key">{key}</p>', '<ol class="strip">', *marks, "</ol>", "</section>"])


def flight_page(rows: list[Row], partners: dict[str, tuple[Row, ...]],
                others: dict[str, tuple[str, tuple[Row, ...]]], updated: datetime) -> str:
    """One flight number and direction (docs/site-redesign.md, "Flight page"; docs/flight-lookup.md, "Pages", Flight
    page), in the plan's markup contract: the title and the line under it; #now, holding the traveller's day, the
    nearest day ahead whatever its label, or, with no day ahead, the line saying the number is not on the airport's
    list and the support; the strip; .later, the later days ahead, soonest first; .past, the past days, newest first,
    written even when it holds none. A day is ahead when its scheduled time is later than `updated`, the last sighting
    (both the model's naive UTC). `partners` and `others` are flights.partners and flights.others of the lists. The
    places of the chances and the support stand empty for the headline's figures (the plan's Task 11). The line under
    the title names the place when the page has one, and the Hebrew city when it has one city; otherwise each day
    names its own."""
    by_time = sorted(rows, key=_when)
    ahead = [r for r in by_time if r.sched_utc_final > updated]
    later = ahead[1:]
    past = [r for r in reversed(by_time) if r.sched_utc_final <= updated]
    latest = by_time[-1]
    title = flights.page_title(rows)
    number = f"{latest.airline} {latest.flight_no}"
    many_places = len({(r.city, r.airport) for r in rows}) > 1
    who = [d(latest.airline_name)]  # an airline's published name is that of its latest row
    if not many_places:
        who.append(_to_or_from(latest))
    if len({r.city for r in rows}) == 1 and latest.city_he:
        who.append(f'<span lang="he" dir="rtl">{d(latest.city_he)}</span>')
    in_order = ahead + past  # the days in page order
    expected = next((r for r in in_order if words.shows_expected(r.est_final, r.sched_final, r.label)), None)
    quoting = [r for r in in_order if _quotes_final(r)]  # the first open list that quotes them, else the first
    final = next((r for r in quoting if r.label == words.CANCELLED), quoting[0] if quoting else None)

    def day(r: Row, top: bool = False) -> str:
        return _day(r, partners.get(r.flight_id, ()), others.get(r.flight_id), many_places, updated, top=top,
                    expected_note=r is expected, final_note=r is final)

    if ahead:
        now = [day(ahead[0], top=True)]
    else:  # still listed: the latest flight's last sighting is the page's last update
        still = latest.last_seen_at >= updated
        now = [f'<p class="none-line">{words.not_listed(number, latest.day, still, e, d)}</p>',
               '<div class="support"></div>']
    body = ['<div class="flight-h">', f"<h1>{d(title)}</h1>", f'<p class="who">{" · ".join(who)}</p>', "</div>",
            '<div id="now">', *now, "</div>", _strip(by_time, number),
            '<div class="later">', *(day(r) for r in later), "</div>",
            '<div class="past">', *(day(r) for r in past), "</div>"]
    return layout(title, "\n".join(body), "../", updated)


# --- day page --------------------------------------------------------------------------------------

def _day_row(fl: ListFlight) -> str:
    """A flight's line: its numbers, labelled as one (C10); a cancelled one with C9's number's notice."""
    r = fl.lead
    parts = [f'<span class="t">{words.clock(r.sched_final, r.day)}</span>',
             f'<span class="nums">{_numbers(fl, "../")}</span>', f'<span class="route">{_to_or_from(r)}</span>',
             f'<span class="labels">{_labels(fl.label, fl.delayed)}</span>']
    if fl.label == words.CANCELLED:
        parts.append(f'<span class="warn">{e(r.notice.sentence)}</span>')
    return f"<li>{' '.join(parts)}</li>"


def day_page(info: DayInfo, flights_: list[ListFlight], updated: datetime) -> str:
    """One day's flights (docs/site-redesign.md, "Day page"): the title with the day's counts, the line for a day the
    records may not hold whole and the line for its UNKNOWN flights, each left out when it has nothing to say; then
    departures and arrivals in scheduled order, each number linked to its row. `updated` is the last sighting."""
    body = [f"<h1>{e(words.day_title(info.day, info.total, info.cancelled))}</h1>"]
    if info.partial:
        body.append(f'<p class="note">{e(words.PART_MISSING)}</p>')
    unknown = words.unknown_line(info.unknown)
    if unknown:  # every UNKNOWN flight; each flight page's label note gives its reason
        body.append(f'<p class="note">{e(unknown)}</p>')
    for direction, heading, empty in (("D", "Departures", words.NO_DEPARTURES), ("A", "Arrivals", words.NO_ARRIVALS)):
        fls = sorted((fl for fl in flights_ if fl.rows[0].direction == direction),
                     key=lambda fl: (fl.rows[0].sched_final, fl.rows[0].airline, fl.rows[0].flight_no,
                                     fl.rows[0].airport, fl.rows[0].flight_id))
        body.append(f"<h2>{heading}</h2>")
        body.append('<ul class="flights">\n' + "\n".join(_day_row(fl) for fl in fls) + "\n</ul>" if fls
                    else f"<p>{e(empty)}</p>")
    return layout(words.long_date(info.day), "\n".join(body), "../", updated)


# --- cancelled flights -----------------------------------------------------------------------------

def _cancellations_table(cancelled: list[ListFlight], root: str) -> str:
    """Date, flight, route with the scheduled time, and the notice's list form, C9's number's: the cell before it
    ends with a time, so no label runs into it. The notice's phone prefix, "Notice given: ", stands in its own span,
    for the sheet to show only where the table stacks and its column heads are hidden."""
    rows = [f"<tr><td>{_short_date(fl.day)}</td><td>{_numbers(fl, root)}</td><td>{_route(fl.lead)}</td>"
            f'<td><span class="pre">{e(words.NOTICE_GIVEN)}: </span>{e(fl.lead.notice.short)}</td></tr>'
            for fl in cancelled]
    heads = "".join(f"<th>{e(head)}</th>" for head in words.CANCELLED_COLUMNS)
    return ('<div class="table-card">\n<table class="cancellations">\n'
            f"<thead><tr>{heads}</tr></thead>\n<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>\n</div>")


def cancellations_page(flights_: list[ListFlight], updated: datetime) -> str:
    """Every cancelled flight among `flights_`, newest first (docs/site-redesign.md, "Cancelled flights"), under the
    title, the introduction and the line on "Notice given". `updated` is the last sighting."""
    cancelled = flights.recent_cancellations(flights_, n=len(flights_))
    table = _cancellations_table(cancelled, "") if cancelled else f"<p>{e(words.NONE_CANCELLED)}</p>"
    body = [f"<h1>{e(words.CANCELLED_TITLE)}</h1>", f"<p>{e(words.CANCELLED_INTRO)}</p>",
            f'<p class="note">{e(words.CANCELLED_UNDER)}</p>', table]
    return layout(words.CANCELLED_TITLE, "\n".join(body), "", updated)


# --- how this works --------------------------------------------------------------------------------

def _gap(start: datetime, end: datetime) -> str:
    """A stretch with no records, from the model's naive UTC times, in Israel time with the dates."""
    a, b = words.il_time(start), words.il_time(end)
    return f"There are no records from {a.day} {a:%B %H:%M} to {b.day} {b:%B %H:%M}."


def how_it_works_page(attribution: str, gaps: Sequence[tuple[datetime, datetime]], tag: str,
                      counting_start: datetime, updated: datetime) -> str:
    """Appendix A of docs/site-redesign-plan.md, with Appendix A of docs/flight-lookup-plan.md placed after "Probably
    the same flight", verbatim; the only page that may say "I" and name how the data is collected. `gaps` are (start,
    end) in the model's naive UTC. `tag` is the frozen code's tag (record.TAG), linked to its code; `counting_start`
    (record.COUNTING_START, the model's naive UTC) is written as its Israel date, as the lede writes a date. `updated`
    is the last sighting."""
    gap_sentences = "".join(f" {_gap(a, b)}" for a, b in gaps)
    start = words.il_time(counting_start)
    tagged = f'<a href="{e(f"{words.CODE_URL}/tree/{tag}")}">{e(tag)}</a>'
    body = f"""<h1>How this works</h1>
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
<p>For a cancelled flight, the warning is how long before its scheduled time the list already showed it as cancelled. The list refreshes about every 15 minutes, so the change is usually known to within that window, and always to within an hour. For the same reason, the time of a cancellation is always given as a range. Where records are missing, the warning is a range ("between 7 and 50 hours"). When a flight was already cancelled the first time it appeared in the records, only a lower limit is known ("at least 23 hours"); "at least" is also used when the change was seen an hour or more ahead, rounded down. The airline may have told passengers earlier than the list showed.</p>
<h2>Why there are no delay figures</h2>
<p>The list gives an expected time for each flight. It doesn't say whether that is when the plane leaves the gate or when it takes off. Until that is settled, this site shows the airport's times as they are and doesn't turn them into delay figures.</p>
<h2>"Final" and "not final"</h2>
<p>The airport also uses the words "final" and "not final". It doesn't publish what they mean, so this site quotes them as they are.</p>
<h2>Probably the same flight</h2>
<p>Airlines often sell seats on one flight under several flight numbers. When numbers share the same time, terminal and check-in desks, this site lists them as probably the same flight. The list doesn't say so itself, and arrivals with no check-in desks can occasionally be grouped by mistake.</p>
<h2>A flight</h2>
<p>{e(words.A_FLIGHT)}</p>
<h2>What is counted</h2>
<p>A flight is counted two days after its scheduled time, so that all the flights of one hour are counted together, whatever happened to them. A flight that left the list with no final status, or while nothing was recorded, has no known outcome. It is left out of every figure, and how many there are is given beside the figures.</p>
<h2>Why every figure is a range</h2>
<p>Cancellations come in runs: an airline cancels several flights in the same week, and a bad day hits many flights at once. So each figure comes with a range wide enough to allow for both. A figure is shown only when it rests on at least 10 cancelled flights, from at least 5 airlines and 5 days; below that, the page gives the counts and says there are too few so far to say.</p>
<h2>Why three days</h2>
<p>The airport's list shows a flight from about three days before its scheduled time, so the table starts at 70 hours to go. A flight that is already listed as cancelled when it first appears is almost never seen, so every figure is about flights that reached the list normally.</p>
<h2>Why the later rows hold more flights</h2>
<p>Flights whose first days on the list fell before the records began, or in the gap from 27 to 29 October, were seen only in their last hours. They are in the later rows of the table and not in the earlier ones.</p>
<h2>Signs under test</h2>
<p>No figure is given for one flight yet. I am testing four signs that might go with a later cancellation: a flight of the same airline from the same airport, scheduled to land 30 minutes to 12 hours before a departure, listed as cancelled; the same flight number's previous flight listed as cancelled; another flight of the same airline, scheduled within a day either side, listed as cancelled; and a flight number first listed less than two days before its scheduled time. The rules were fixed beforehand, in the code tagged {tagged}. The counted flights are those first listed from {start.day} {start:%B %Y}, the counting start; the 24-hour row is the table's row for 24 hours to go, and its checkpoint is that moment.</p>
<p>A sign may change what this site shows only when both of these hold:</p>
<ol>
<li>The count. Take the counted flights of the 24-hour row in the order of the scheduled time they showed at the checkpoint. The gate is reached at the first such time that is at least 60 days after the counting start and by which 200 of those flights were later listed as cancelled. The days and the count are taken over every counted flight in the row.</li>
<li>The sign has passed its test, read on the counted flights scheduled up to that time.</li>
</ol>
<p>The lift is the rate with the sign over the rate without it. Its range is 2.5 standard errors of its logarithm either side, grouped as the ranges above are. 2.5, not 2, because four signs are tested at once. A sign passes when it clears the floor (10 cancelled flights with the sign, from 5 airlines and 5 days) and the whole range lies above 1. A sign that fails stays failed for this version.</p>
<h2>Gaps in the records</h2>
<p>Records start on the evening of 27 October 2026.{gap_sentences} A flight that left the list during a gap is marked UNKNOWN.</p>
<h2>How it's built</h2>
<p>The program runs on AWS Lambda and saves each version once, to storage where it is locked for ten years. A Python data model turns the saved versions into one history per flight, and this site is generated from that model. Every rule has tests, and the tests are themselves checked by breaking the code on purpose and confirming that a test fails. The code is <a href="{e(words.CODE_URL)}">on GitHub</a>.</p>"""
    return layout("How this works", body, "", updated)


# --- front page ------------------------------------------------------------------------------------

RECENT = 10  # cancellations on the front page; the rest are on cancellations.html


def search_json(entries: list[dict]) -> str:
    """The search entries as JSON for a script element: every "<" escaped, so a name containing "</script>" cannot
    end the element."""
    return json.dumps(entries, sort_keys=True, ensure_ascii=False).replace("<", "\\u003c")


def _section(kind: str, heading: str | None, body: list[str]) -> str:
    """A section of the front page: its heading, when it has one, then its matter."""
    return "\n".join([f'<section class="sec {kind}">', *([f"<h2>{e(heading)}</h2>"] if heading else []),
                      '<div class="sec-b">', *body, "</div>", "</section>"])


def _search() -> str:
    """"Find your flight" (docs/site-redesign.md, "Front page", item 2): the label, the box, its results and the hint in
    one wrapper, hidden until search.js has read the flights, so that none of them shows without the others; in the
    box's place without scripts, the line whose last words link to the day list."""
    before, link, after = words.FIND_OFF
    return "\n".join(['<div class="find" id="find" hidden>',
                      f'<label class="find-l" for="search">{e(words.FIND_LABEL)}</label>',
                      f'<input id="search" type="search" placeholder="{e(words.SEARCH_HINT)}" '
                      'aria-label="Find a flight by number or city">',
                      '<ul id="search-results" hidden></ul>',
                      f'<p class="find-hint">{e(words.FIND_HINT)}</p>',
                      "</div>",
                      f'<p class="find-off" id="find-off">{e(before)}<a href="#days">{e(link)}</a>{e(after)}</p>'])


def _pct(rate: Rate) -> str:
    """A row's figure: its share to one decimal (the table's form)."""
    return words.pct1(rate.cancelled, rate.flights)


def _about_500(shown: list[Rate]) -> int:
    """The mean of the rows' flights to the nearest 500, halves up, worked in integers."""
    total, n = sum(r.flights for r in shown), len(shown)
    return (2 * total + 500 * n) // (1000 * n) * 500


def chance_table(summary: Summary, airport: blend.Airport) -> str:
    """"Chance of cancellation, by how soon you fly" (docs/flight-lookup.md, "Front page: the table"), from the
    airport's rates (blend.Airport: the frozen rows and the delays): the heading; the first line, from the first and
    the last row, left out when either is below C8's floor; the six rows of C5's points, each its share to one
    decimal, or "Not enough flights yet" below the floor; the line under it, its flights the mean of the rows shown
    to the nearest 500, left out when no row is shown; the delay line, each direction's delays of an hour or more
    over its flights that flew, left out while either direction's delays are below the floor (C8 reads a delay
    rate's delayed flights). Plain HTML, no script."""
    rows = [(name, airport.rows[h]) for h, name in words.ROW_NAMES.items()]
    (_, first), (_, last) = rows[0], rows[-1]
    shown = [r for _, r in rows if r.clears_floor]
    body = []
    if first.clears_floor and last.clears_floor:
        body.append(f'<p class="intro">{e(words.table_first(_pct(first), _pct(last)))}</p>')
    body += ['<table class="fromhere">',
             "<thead><tr>" + "".join(f"<th>{e(head)}</th>" for head in words.TABLE_COLUMNS) + "</tr></thead>",
             "<tbody>",
             *(f'<tr><td class="togo">{e(name)}</td>'
               f'<td class="pc">{e(_pct(r) if r.clears_floor else words.NOT_ENOUGH)}</td></tr>' for name, r in rows),
             "</tbody>", "</table>"]
    if shown:
        body.append(f'<p class="under">{e(words.under_table(_about_500(shown), summary.first_record))}</p>')
    departures, arrivals = airport.delay["D"], airport.delay["A"]
    if departures.clears_floor and arrivals.clears_floor:
        line = words.delay_line(departures.cancelled / departures.flights, arrivals.cancelled / arrivals.flights)
        body.append(f'<p class="late"><b>{e(words.DELAY_LEAD)}</b> {e(line)}</p>')
    return _section("s-fromhere", words.TABLE_HEADING, body)


def _total(summary: Summary, total: Rate) -> str:
    """The total (docs/flight-lookup.md, "Front page: the total"): the tiles, the cancelled one in the cancelled
    colour, the third the percentage alone and left out below C8's floor (words.total_tiles); the sentence, which
    says why below it; the late line and the left-out line, each left out at zero."""
    tiles = [f'<span class="stat{" cancel" if label == "cancelled" else ""}"><b>{e(figure)}</b>'
             f'{f" {e(label)}" if label else ""}</span>' for figure, label in words.total_tiles(total)]
    notes = [words.late_line(summary.late_after, total.cancelled), words.left_out(summary.unknown)]
    return _section("s-total", None, ['<p class="stats">', *tiles, "</p>",
                                      f"<p>{e(words.total_sentence(total, summary.first_record))}</p>",
                                      *(f'<p class="note">{e(note)}</p>' for note in notes if note)])


def _story(story: tuple[Row, str]) -> str:
    """One cancelled flight's story (docs/site-redesign.md, "Front page", item 6): the told row and its flight page's
    title, linked to the row; its day and scheduled time; its list of changes."""
    r, title = story
    return _section("story", words.STORY_HEADING, [
        f'<h3><a href="{e(r.page)}#{e(r.anchor)}">{d(title)}</a></h3>',
        f'<p class="when">{e(words.long_date(r.day))} · {e(words.scheduled(r.direction, r.sched_final, r.day))}</p>',
        _changes(r)])


def _marks(info: DayInfo) -> str:
    """The words beside a day (docs/site-redesign.md, "Front page", item 8): "today" for the Israel date of the last
    record, "upcoming" for a later day; for a day the partial rule flags, "not all listed yet" on a later day and
    "some flights missing" on any other. "" for none."""
    marks = {"today": ["today"], "ahead": ["upcoming"]}.get(info.state, [])
    if info.partial:
        marks.append("not all listed yet" if info.state == "ahead" else "some flights missing")
    return " · ".join(marks)


def _counts(info: DayInfo) -> str:
    """A day's flights in plain numbers, zeros left out: "370 flights · 8 cancelled · 190 unknown", as the day page's
    title and its unknown line give them (words.day_title, words.unknown_line)."""
    parts = [(info.cancelled, "cancelled"), (info.unknown, "unknown")]
    return " · ".join([words._flights(info.total), *(f"{words._n(n)} {what}" for n, what in parts if n)])


def chart(days: list[DayInfo]) -> str:
    """"Flights each day" (docs/site-redesign.md, "Front page", item 8, and "Look A"): a list of links, one per day, to
    its day page. Each holds the date, the counts in text with the marks beside them, and a thin bar on one scale, the
    busiest day filling its width: the day's flights as a line, the cancelled part as a block at its start and the
    unknown part beside it, each left out at none (the sheet draws the block red and the unknown part outlined). The
    bar is hidden from screen readers, so a link's name is its date, counts and marks: never colour alone. The link's
    classes carry the day's state (past, today, ahead) and partial."""
    top = max((info.total for info in days), default=1)
    items = []
    for info in days:
        marks = _marks(info)
        mark = f' <span class="mark">{e(marks)}</span>' if marks else ""
        parts = [f'<rect class="rest" x="0" y="3.5" width="{info.total}" height="2"/>']
        if info.cancelled:
            parts.append(f'<rect class="cancelled" x="0" y="0" width="{info.cancelled}" height="9"/>')
        if info.unknown:
            parts.append(f'<rect class="unknown" x="{info.cancelled}" y="0" width="{info.unknown}" height="9"/>')
        classes = " ".join([info.state] + ["partial"] * info.partial)
        items.append(f'<li><a href="day/{info.day:%Y-%m-%d}.html" class="{classes}">'
                     f'<span class="date">{_short_date(info.day)}</span> '
                     f'<span class="counts">{e(_counts(info))}{mark}</span>'
                     f'<svg class="bar" width="100%" height="9" viewBox="0 0 {top} 9" preserveAspectRatio="none" '
                     f'aria-hidden="true">{"".join(parts)}</svg></a></li>')
    return "\n".join(['<ol class="chart">', *items, "</ol>"])


def day_list(days: list[DayInfo]) -> str:
    """"Pick a day:" and every day the site has, linked, so that no flight is out of reach without JavaScript; the list
    is where the line in the search box's place leads."""
    return "\n".join([f'<p class="days-h">{e(words.PICK_A_DAY)}</p>', '<ol class="days" id="days">',
                      *(f'<li><a href="day/{x.day:%Y-%m-%d}.html">{_short_date(x.day)}</a></li>' for x in days),
                      "</ol>"])


def front_page(summary: Summary, airport: blend.Airport, story: tuple[Row, str] | None, recent: list[ListFlight],
               chart_days: list[DayInfo], all_days: list[DayInfo], entries: list[dict], last_record: datetime) -> str:
    """The front page, top to bottom as docs/site-redesign.md ("Front page") lists it. The caller chooses: the figures
    beside the airport's rates (display.summary), the airport's rates (blend.Airport), the story (the told row and
    its flight page's title; None for none), the recent cancellations newest first (at most RECENT shown), the
    chart's days and every day for the list under it, the search entries, and the last record's time (the model's
    naive UTC)."""
    about = words.description()
    head = "\n".join([f'<meta name="description" content="{e(about)}">',
                      f'<meta property="og:title" content="{e(words.TITLE)}">',
                      f'<meta property="og:description" content="{e(about)}">',
                      '<meta property="og:type" content="website">',
                      '<script src="search.js" defer></script>'])
    body = [_search(), f'<p class="lede">{e(words.intro(summary.first_record))}</p>', chance_table(summary, airport),
            _total(summary, airport.total)]
    if story is not None:
        body.append(_story(story))
    recent_part = _cancellations_table(recent[:RECENT], "") if recent else f"<p>{e(words.NONE_CANCELLED)}</p>"
    body += [_section("s-recent", words.RECENT_HEADING,
                      [recent_part, f'<p class="all"><a href="cancellations.html">{e(words.ALL_CANCELLED)}</a></p>']),
             _section("s-days", words.CHART_HEADING, [chart(chart_days), day_list(all_days)])]
    # The search data last in <main>, so the table above renders before it has arrived; search.js is deferred and
    # finds it by id.
    body.append(f'<script type="application/json" id="flights-data">{search_json(entries)}</script>')
    return layout(words.TITLE, "\n".join(body), "", last_record, head, front=True)
