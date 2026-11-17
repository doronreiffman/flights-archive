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
from collections.abc import Callable, Sequence
from datetime import date, datetime
from functools import partial

from . import blend, counting, flights, names, words
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
    """A day's first line: the date written out, the time line, the city when the page has more than one, the labels,
    with " · " between them in the text, as the approved lines write them ("Tuesday 17 November · scheduled to land at
    19:45 · UPCOMING"), so the line reads right without the style sheet and to a screen reader."""
    parts = [f'<span class="date">{e(words.long_date(r.day))}</span>',
             f'<span class="sched">{e(words.time_line(r.direction, r.sched_final, r.est_final, r.label, r.day))}</span>']
    if many_places:
        parts.append(f'<span class="place">{_to_or_from(r)}</span>')
    parts.append(f'<span class="labels">{_labels(r.label, r.delayed)}</span>')
    return f'<p class="head">{" · ".join(parts)}</p>'


def _day(r: Row, partners: tuple[Row, ...], other: tuple[str, tuple[Row, ...]] | None, many_places: bool,
         updated: datetime, *, ahead: bool, top: bool, chances: str, support: str, expected_note: bool,
         final_note: bool) -> str:
    """One day, in the order of docs/site-redesign.md ("Flight page", a day's lines) as the plan's markup contract
    places it: the head; the label's line, the notice sentence and the changed-back line; then the twin line or, on a
    day ahead marked cancelled, "This flight is marked cancelled. Contact your airline." (never both: Question 3); the
    day's prepared `chances`, "" for none; on a day ahead, the hidden "has passed" line; the `support` in the top day;
    last, the day's own lines in .own: "Also sold as …", the note on expected times and "What changed", open for a
    cancelled day, with the note on "final" under it. A day `ahead` (scheduled after `updated`, the last sighting, as
    flight_page decides) carries its scheduled time as the UTC instant it is, for the page script."""
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
    if chances:
        out.append(chances)
    if ahead:
        out.append(f'<p class="passed" hidden>{e(words.has_passed(updated))}</p>')
    if top:
        out.append(support)
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


# --- the headline slot (docs/flight-lookup.md, "Flight page: the headline", "the "Worked out from" line, every form"
# and "the lines in smaller type"; "Pages", Flight page; "Left to the builder"; the plan's Task 11 markup) ---------

def _figure(label: str, figure: str) -> str:
    """One chance, its label and its figure, the figure split into its word and its number ("about", "15%")."""
    word, number = figure.split(" ", 1)
    return (f'<span class="fl">{e(label)}</span> '
            f'<span class="fv"><span class="q">{e(word)}</span> <b class="n">{e(number)}</b></span>')


def _figs(headline: tuple[tuple[str, str], tuple[str, str]]) -> list[str]:
    """The two chances of words.headline, each on a line of its own, as the slot under the top day sets them."""
    return [f'<p class="fig">{_figure(*chance)}</p>' for chance in headline]


def _chances(r: Row, updated: datetime, top: bool, cancel: Callable[[int], float | None], delay: float) -> str:
    """A day's prepared chances ("Left to the builder", "At which moment" and "The weight of prepared figures"): one
    pair per stretch still ahead of the day at `updated`, the last sighting (blend.STRETCHES), the cancellation scaled
    by that stretch's own row (`cancel` of its checkpoint), the delay flat; each pair with its stretch's bounds for the
    page script. The first, the stretch the day was in at the last update (above 72 hours, the top one), shows without
    scripts, the rest hidden. The top day sets each chance on a line of its own; a later day sets the two on one
    line."""
    left = (r.sched_utc_final - updated).total_seconds() / 3600
    out = ['<div class="chances">']
    for i, (after, upto, h) in enumerate(s for s in blend.STRETCHES if s[0] < left):
        headline = words.headline(cancel(h), delay, True)
        body = _figs(headline) if top else [
            f'<p class="one">{_figure(*headline[0])}<span class="sep"> · </span>{_figure(*headline[1])}</p>']
        out += [f'<div class="pair" data-after="{after}" data-upto="{upto}"{" hidden" if i else ""}>', *body, "</div>"]
    return "\n".join([*out, "</div>"])


def _so_far(h: words.History, with_week: bool) -> str:
    bold, rest = words.so_far(h, with_week, e, d)
    return f'<p class="s-line"><b>{bold}</b> {rest}</p>'


def _all_airlines(airport: blend.Airport, direction: str, ahead: bool) -> str | None:
    """The all-airlines line: with a day ahead, the six prepared forms, one per stretch with its bounds for the page
    script, each with the figure of the row at its far end, hidden, and the "more than 3 days" line, hidden; then the
    form without a time, the total's, which shows without scripts. A row below C8's floor leaves its form out and a
    total below it the form without a time (the plan's decisions). The delay figure has no floor, as the front page's
    delay line has none (the plan's amendment after Task 9's review): a direction with no flight that flew leaves
    every form out. None when no line is left."""
    delay = airport.delay[direction]
    late = words.about(delay.cancelled / delay.flights) if delay.flights else None
    forms = []
    if ahead:
        for after, upto, h in blend.STRETCHES:
            row = airport.rows[h]
            if late and row.clears_floor:
                bold, rest = words.all_airlines(h, words.average(row.cancelled, row.flights), late, direction)
                forms.append(f'<p data-after="{after}" data-upto="{upto}" hidden><b>{e(bold)}</b> {e(rest)}</p>')
        forms.append(f'<p class="more" hidden>{e(words.MORE_THAN_3_DAYS)}</p>')
    if late and airport.total.clears_floor:
        total = words.average(airport.total.cancelled, airport.total.flights)
        bold, rest = words.all_airlines(None, total, late, direction)
        forms.append(f'<p class="off"><b>{e(bold)}</b> {e(rest)}</p>')
    if not forms:
        return None
    return "\n".join([f'<div class="aa" data-more-after="{blend.STRETCHES[0][1]}">', *forms, "</div>"])


def _support(own: words.History, whose: words.History, spoken: str | None, lead: str | None,
             next_flight: tuple | None, ahead: bool, carried: bool, listed_since: bool, airport: blend.Airport,
             direction: str, updated: datetime) -> str:
    """The lines under the chances, in the plan's markup ("Pages", Flight page, "Under the slot, in smaller type"):
    the headline in its "its next flight" form (`next_flight`, words.headline's, None when the page has no chances);
    the "Worked out from" line in its flight-ahead form, when a day ahead carries chances (`carried`, Question 1); the
    same in its no-flight-ahead form; the number's "so far" line, the partner line naming `lead` when the page's
    airline is not the number's own, the airline's "so far" line; the all-airlines line; the freshness line; the link
    "What the numbers mean". With a day ahead the no-flight-ahead parts stand hidden, for the page script to show once
    every day has passed; with none they show. A "so far" line with no flights is left out (Question 6d), and one
    gives its bad week's dates unless the "Worked out from" line a reader sees without scripts gives them."""
    hide = " hidden" if ahead else ""
    worked = {flying: words.worked_out(own, whose, spoken, flying, listed_since, e, d) for flying in (True, False)}
    out = ['<div class="support">']
    if next_flight:
        out += [f'<div class="none-ahead"{hide}>', *_figs(next_flight), "</div>"]
    if carried:
        out.append(f'<p class="worked">{worked[True].text}</p>')
    if next_flight:
        out.append(f'<p class="worked none-ahead"{hide}>{worked[False].text}</p>')
    seen = worked[True] if carried else worked[False] if next_flight and not ahead else None
    if own.flights:
        out.append(_so_far(own, seen is None or not seen.names_number_week))
    if lead:
        out.append(f'<p class="s-line">{words.partner(own.name, lead, spoken, e, d)}</p>')
    if whose.flights:
        out.append(_so_far(whose, seen is None or not seen.names_airline_week))
    aa = _all_airlines(airport, direction, ahead)
    if aa:
        out.append(aa)
    out += [f'<p class="fresh"><span data-updated="{updated:%Y-%m-%dT%H:%M:%SZ}">{e(words.updated_at(updated))}'
            f"</span>. {e(words.FRESH_REST)}</p>",
            f'<p class="means"><a href="../how-it-works.html#{words.MEANS_ANCHOR}">{e(words.MEANS)}</a></p>',
            "</div>"]
    return "\n".join(out)


def _days(rows: list[Row], updated: datetime) -> tuple[list[Row], list[Row]]:
    """A page's days in time order, and the days ahead: scheduled later than `updated`, the last sighting (both the
    model's naive UTC), whatever their label."""
    by_time = sorted(rows, key=_when)
    ahead = [r for r in by_time if r.sched_utc_final > updated]
    return by_time, ahead


def page_flight(rows: list[Row], updated: datetime, flights_: list[counting.Flight]) -> counting.Flight:
    """The flight (C1) whose grouping airline (C8) is the page's: the traveller's day's, the nearest day ahead of
    `updated` whatever its label, else the newest day's ("Left to the builder", "A flight number's airline" and "Which
    airline on a later day ahead"). One airline per page: its records work out every day's chances, its "so far" line
    stands under the number's, and the partner line stands when it is not the number's own. `flights_` holds at least
    the flights of `rows`."""
    by_time, ahead = _days(rows, updated)
    return counting.flight_of(flights_)[(ahead[0] if ahead else by_time[-1]).flight_id]


def flight_page(rows: list[Row], partners: dict[str, tuple[Row, ...]],
                others: dict[str, tuple[str, tuple[Row, ...]]], updated: datetime, records: blend.Records,
                flights_: list[counting.Flight], by_id: dict[str, dict]) -> str:
    """One flight number and direction (docs/site-redesign.md, "Flight page"; docs/flight-lookup.md, "Pages", Flight
    page), in the plan's markup contract: the title and the line under it; #now, holding the traveller's day, the
    nearest day ahead whatever its label, or, with no day ahead, the line saying the number is not on the airport's
    list and the support; the strip; .later, the later days ahead, soonest first; .past, the past days, newest first,
    written even when it holds none. A day is ahead when its scheduled time is later than `updated`, the last sighting
    (both the model's naive UTC). `partners` and `others` are flights.partners and flights.others of the lists. The
    line under the title names the place when the page has one, and the Hebrew city when it has one city; otherwise
    each day names its own.

    The chances (blend) are worked out from the number's record (per number and direction), the page's airline's
    (page_flight) and the airport's, all from `records`; `flights_` holds the page's flights (C1) and `by_id` the
    flights table by flight_id, for the partner line's number, C8's lead of the traveller's (or newest) day's flight.
    Each day ahead labelled UPCOMING carries its prepared chances; any other day ahead carries none, and neither does
    a page whose airport has no rate to start from (Question 1's structure). ValueError when the partner line's airline
    has no spoken name (build.render stops first, naming every one)."""
    by_time, ahead = _days(rows, updated)
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

    grouped = page_flight(rows, updated, flights_)
    airline, spoken = grouped.airline, names.spoken(grouped.airline)
    mine, theirs = records.numbers[(latest.airline, latest.flight_no, latest.direction)], records.airlines[airline]
    cancel = partial(blend.cancel_chance, mine, theirs, records.airport)
    next_flight = cancel(blend.row_for(None))  # no flight ahead: the 70-hour row
    delay = blend.delay_chance(mine, theirs, records.airport, latest.direction)
    chances = next_flight is not None and delay is not None
    carries = {r.flight_id for r in ahead if chances and r.label == words.UPCOMING}
    lead = None
    if airline != latest.airline:  # "LY 9255 is also sold as LO 155, so the numbers here are worked out from LOT's …"
        if spoken is None:
            raise ValueError(f"{number}'s partner line names {airline}, which has no spoken name (timeline/names.py)")
        grouping = blend.lead(grouped, by_id)
        lead = f"{grouping['airline']} {grouping['flight_no']}"
    last = mine.last_cancelled
    support = _support(
        words.History(number, mine.flights, mine.cancelled, mine.delayed, blend.bad_week(mine)),
        words.History(records.published[airline], theirs.flights, theirs.cancelled, theirs.delayed,
                      blend.bad_week(theirs)),
        spoken, lead, words.headline(next_flight, delay, False) if chances else None, bool(ahead), bool(carries),
        last is None or any(r.sched_utc_final > last and r.last_seen_at > last for r in rows), records.airport, latest.direction, updated)

    def day(r: Row, is_ahead: bool, top: bool = False) -> str:
        prepared = _chances(r, updated, top, cancel, delay) if r.flight_id in carries else ""
        return _day(r, partners.get(r.flight_id, ()), others.get(r.flight_id), many_places, updated, ahead=is_ahead,
                    top=top, chances=prepared, support=support, expected_note=r is expected, final_note=r is final)

    if ahead:
        now = [day(ahead[0], True, top=True)]
    else:  # still listed: the latest flight's last sighting is the page's last update
        still = latest.last_seen_at >= updated
        now = [f'<p class="none-line">{words.not_listed(number, latest.day, still, e, d)}</p>', support]
    body = ['<div class="flight-h">', f"<h1>{d(title)}</h1>", f'<p class="who">{" · ".join(who)}</p>', "</div>",
            '<div id="now">', *now, "</div>", _strip(by_time, number),
            '<div class="later">', *(day(r, True) for r in later), "</div>",
            '<div class="past">', *(day(r, False) for r in past), "</div>"]
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


def _written(day: date) -> str:
    """A date written out with its year, as the page writes a date: "27 October 2026"."""
    return f"{day.day} {day:%B %Y}"


def _shares(airport: blend.Airport) -> str:
    """Section 3's two sentences on the first and the last row, each its share to one decimal, as the table writes it;
    "" when either is below C8's floor, as the front page's first line is left out."""
    first, last = airport.rows[70], airport.rows[3]
    if not (first.clears_floor and last.clears_floor):
        return ""
    return (f" Of flights still on 3 days before, {_pct(first)} were cancelled later. Of flights still on 3 hours "
            f"before, {_pct(last)}.")


def _delays(airport: blend.Airport) -> str:
    """Section 3's two sentences on delays of an hour or more over flights that flew, each direction "about" or
    "under 1%" as the front page's delay line writes it; "" while a direction has no flight that flew, the one case
    the front page leaves its line out (the line has no floor: docs/will-it-fly-plan.md, Deviations, Task 9's
    review)."""
    departures, arrivals = airport.delay["D"], airport.delay["A"]
    if not (departures.flights and arrivals.flights):
        return ""
    return (f" Among departures that flew, {words.about(departures.cancelled / departures.flights)} were delayed an "
            f"hour or more. Among arrivals, {words.about(arrivals.cancelled / arrivals.flights)}.")


def _figures(airport: blend.Airport) -> tuple[str, list[str]]:
    """Section 5: the sentence that reads the total's range ("" when it has none), and the list's lines. Each figure is
    its percentage with its range (words.pct_range: one decimal, the ends outward); the total and a row with none, below
    C8's floor, read "Not enough flights yet". The two delay lines stand only when both have a range."""
    total = words.pct_range(airport.total)
    reads = (f" For all flights it reads {total}: first the figure, then the low end and the high end of its range."
             if total else "")
    lines = [f"All flights: {words._n(airport.total.flights)} flights · {words._n(airport.total.cancelled)} cancelled "
             f"· {total or words.NOT_ENOUGH}"]
    for h, name in words.ROW_NAMES.items():
        r = airport.rows[h]
        lines.append(f"{name}: {words._n(r.flights)} flights still on then · {words._n(r.cancelled)} cancelled later "
                     f"· {words.pct_range(r) or words.NOT_ENOUGH}")
    departures, arrivals = words.pct_range(airport.delay["D"]), words.pct_range(airport.delay["A"])
    if departures and arrivals:
        lines += [f"Departures delayed an hour or more: {departures}", f"Arrivals delayed an hour or more: {arrivals}"]
    return reads, lines


def _items(tag: str, items: list[str]) -> str:
    return "\n".join([f"<{tag}>", *(f"<li>{item}</li>" for item in items), f"</{tag}>"])


def how_it_works_page(summary: Summary, airport: blend.Airport, attribution: str,
                      gaps: Sequence[tuple[datetime, datetime]], tag: str, counting_start: datetime,
                      updated: datetime) -> str:
    """"How this works" (docs/site-redesign.md, "How this works"; docs/flight-lookup.md, "How this works"): the
    approved opening, then ten sections. The first is "What the numbers mean" (words.WHAT_THE_NUMBERS_MEAN), at the
    anchor every page's footer links to; sections 2 to 10 are as drafted for the owner's approval at the hand check,
    with the front page's figures in their places: `summary` (display.summary: the left-out counts and the first
    record's Israel date) and `airport` (blend.Airport: the frozen total and rows, and the delays). The only page that
    may say "I" and name how the data is collected. `gaps` are (start, end) in the model's naive UTC. `tag` is the
    frozen code's tag (record.TAG), linked to its code; `counting_start` (record.COUNTING_START, the model's naive
    UTC) is written as its Israel date. `updated` is the last sighting. The quoted words take curly quotes."""
    gap_sentences = "".join(f" {_gap(a, b)}" for a, b in gaps)
    start = words.il_time(counting_start)
    tagged = f'<a href="{e(f"{words.CODE_URL}/tree/{tag}")}">{e(tag)}</a>'
    since = _written(summary.first_record)
    means = "\n".join("<p>" + " ".join(f"<b>{e(lead)}</b> {e(rest)}" for lead, rest in pairs) + "</p>"
                      for pairs in words.WHAT_THE_NUMBERS_MEAN)
    reads, figures = _figures(airport)
    left_out = _items("ul", [
        "Flights that dropped off the list during a gap in the records (see “Gaps in the records”, below): "
        f"{words._n(summary.unknown_gap)}",
        f"Flights that dropped off without the airport saying how they ended: {words._n(summary.unknown_no_final)}"])
    labels = _items("ul", [
        "DEPARTED and LANDED: the airport's final word on the flight.",
        "CANCELLED: the airport's list marked the flight cancelled.",
        "UPCOMING: still on the list, with its scheduled time still ahead when the page was last updated.",
        "NO NEWS YET: its scheduled time has passed, and the airport hasn't said how it ended.",
        "UNKNOWN: there's no record of how the flight ended. It dropped off the list during a gap in the records, or "
        "the airport removed it without saying why."])
    gate = _items("ol", [
        "The count. Take the counted flights of the 24-hour row in the order of the scheduled time they showed at the "
        "checkpoint. The gate is reached at the first such time that is at least 60 days after the counting start and "
        "by which 200 of those flights were later listed as cancelled. The days and the count are taken over every "
        "counted flight in the row.",
        "The sign has passed its test, read on the counted flights scheduled up to that time."])
    body = f"""<h1>How this works</h1>
<p>{e(words.HOW_OPENING)}</p>
<section id="{words.MEANS_ANCHOR}">
<h2>{e(words.MEANS)}</h2>
{means}
</section>
<section>
<h2>Where the information comes from</h2>
<p>The airport's list of departures and arrivals is published by the Israel Airports Authority, on data.gov.il.</p>
<p>A flight shows up on that list about 3 days before its scheduled time. About a day after, it drops off, and the list no longer says what happened to it.</p>
<p>That is why this site keeps its own copies. Each new version of the list is saved, so a flight's history is still there after the flight drops off. Everything on this site is worked out from those saved versions.</p>
<p>The terms of data.gov.il ask anyone who uses its information to say where it came from. Here is the source in full:</p>
<p>{e(attribution)}</p>
<p>The part in brackets is the list's own name and ID on data.gov.il, for anyone who wants to look it up.</p>
<p>Airline names are spelled the way the airport's list spells them, even where the spelling looks odd. Inside a sentence, some airlines go by their everyday names, like {d("El Al")} or {d("Lufthansa")}.</p>
</section>
<section>
<h2>How a flight's chance is worked out</h2>
<p>The short version is in “What the numbers mean”, above. This is the longer one.</p>
<p><b>It only counts what the airport's list has shown.</b> A flight's chance comes from three histories: the flight number's own, its airline's, and all flights at Ben Gurion. Each is a count of flights that flew and flights that were marked cancelled. The site doesn't look at the weather or the news.</p>
<p><b>The flight's own history comes first.</b> But a flight number with only a few flights can't say much on its own. So the site pretends that every flight number has 14 more flights behind it, cancelled as often as its airline's figure says. A flight number with a long history mostly speaks for itself. One with fewer than 14 flights gets most of its chance from its airline's figure. The “Worked out from” line on its page then says the chance was worked out mostly from its airline or, when its airline has few flights too, mostly from all airlines.</p>
<p><b>The airline's figure is worked out the same way.</b> The site pretends that every airline has 100 more flights, cancelled as often as all flights at Ben Gurion. A big airline's own flights easily outweigh those 100. An airline with fewer than 100 flights leans mostly on the figure for all airlines.</p>
<p><b>Why 14 and 100.</b> 14 is two weeks of a daily flight, so every day of the week is in it twice. And once an airline has 100 flights, a single flight can't move its figure by more than one point: from 5% to 6%, say. Both numbers are a starting choice. They haven't been tested yet.</p>
<p><b>Then, how soon the flight leaves.</b> The closer a flight gets, the fewer cancellations are still to come.{_shares(airport)} So a flight's chance is adjusted for the time it has left. If flights this close to leaving are cancelled half as often as flights in general, the flight's chance is halved. When the time left falls between two rows of the front page's table, the site uses the row with more time to go: with 10 hours left, the “12 hours away” row. A page with no flight ahead uses the “3 days away” row.</p>
<p><b>A chance is never zero.</b> Even a flight number with no cancelled flight takes a share of its airline's figure. Below 1%, a chance reads “under 1%”. A flight number with a clean history can still show a higher chance, when its airline cancels often. A flight number with no flights yet gets its airline's figure, and an airline with none gets the figure for all flights.</p>
<p><b>The chance of a delay is worked out the same way,</b> counting flights delayed an hour or more in place of cancelled flights. Three things differ. It counts only flights that flew. It starts from all departures or all arrivals at Ben Gurion, whichever the flight is. And it isn't adjusted for how soon the flight leaves, because the chance of a delay is about the same however soon you fly.{_delays(airport)}</p>
<p><b>What this can't do yet.</b> This is a simple first version, and the record only goes back to {since}. One bad week can move a short history a long way. That is why a flight's page gives the dates when one bad week is behind its figures. The adjustment for how soon a flight leaves is the same for every airline and every flight. And so far the record holds no really bad day at the airport. A storm, a strike or a security closure is when you'd most want this site, and it's when these numbers are most wrong. A tested version is planned to take this one's place.</p>
</section>
<section>
<h2>The table for all flights, and who is counted</h2>
<p><b>What the table shows.</b> The table on the front page looks at six moments before a flight's scheduled time: 3 days, 2 days, 1 day, 12 hours, 6 hours and 3 hours. For each one it takes every flight that was still on then, and gives the share that were cancelled later.</p>
<p><b>“Still on”</b> means on the list with any status but cancelled. A delayed flight counts as still on. <b>“Cancelled later”</b> means any time after that moment, however late, even after the scheduled time. The time left is measured from the scheduled time the list showed at that moment, because that is the only time a traveller has.</p>
<p><b>The same table on a flight's page.</b> A flight's page has a line such as “All airlines at Ben Gurion, 6 to 12 hours before a flight”. The cancelled share in that line is the table's figure for 12 hours before. It means that this share of the flights still on 12 hours before were cancelled some time after that. It doesn't mean they were cancelled during those six hours.</p>
<p><b>Why it starts at 3 days.</b> The airport's list shows a flight only for its last 3 days, so there is nothing to count before that. The first row, “3 days away”, is really 70 hours before, a little short of 3 days, so that every flight that showed up on the list at the usual time is in it. A flight further off isn't on the list yet. That says nothing about whether it will fly. A flight that is already cancelled when it first shows up is almost never seen, so the table is about flights that reached the list normally.</p>
<p><b>Who is counted.</b> For the table and the total, a flight is counted two days after its scheduled time. That way, all the flights of one hour are counted at the same moment, whether they flew or were cancelled. A flight's own page doesn't wait. Its counts, for the flight number and for its airline, take in every flight whose ending is known: one that departed or landed, and one that is marked cancelled, even when its scheduled time is still ahead. So a flight cancelled ahead of time is counted at once, while flights due at the same time are counted only once they have flown. For up to 3 days, that can make an airline's figure too high.</p>
<p><b>Who is left out.</b> Flights with no record of how they ended are left out of every figure: {words._n(summary.unknown)} so far. They are of two kinds:</p>
{left_out}
<p>A flight of the second kind may have been cancelled, or moved to another time. The list doesn't say. If some were cancelled, the true share of cancelled flights is higher than the figures here.</p>
<p><b>One flight, several numbers.</b> Airlines sell seats on each other's flights, so one plane can be on the list under several flight numbers. The list never says which numbers belong together, so the site works it out. Numbers with the same scheduled time and the same airport count as one flight when the list shows the same expected time, terminal and check-in desks for them. A flight's page then says “Also sold as”, with the words “probably the same plane”, because this is worked out and not stated. An arrival with no check-in desks listed can now and then be joined to another flight by mistake.</p>
<p><b>When a number is cancelled and the plane still flies.</b> Sometimes one number is marked cancelled while the flight goes ahead under another. A number that never departed or landed is counted together with another number at the same time and airport when the two share an airline or check-in desks. The flight counts as flown when any of its numbers departed or landed. It counts as cancelled only when none did and at least one ended up marked cancelled. On the cancelled number's own page, that day keeps its cancelled mark, with a line saying the flight probably left or landed under the other number. In that number's counts and in its chance, the day counts as flown. If the two numbers were really two planes, one cancellation goes uncounted. The list can't settle that.</p>
<p><b>Whose history counts.</b> The list doesn't say which airline flies a plane that is sold under several numbers. The site files such a flight under one airline: the one with the lowest flight number. The flight's chance leans on that airline's history, and the page says so. It says nothing about who flies the plane.</p>
<p><b>A flight that is cancelled and then put back on</b> counts as whatever it ended as.</p>
<p><b>Why the later rows hold more flights.</b> A flight is in a row only when the records show it on the list at that moment. Flights already on the list when the records began, or that were on it during a gap in the records, are missing from the earlier rows. So are flights that the airport added to the list late. That is why the “3 days away” row holds {words._n(airport.rows[70].flights)} flights and the “3 hours away” row holds {words._n(airport.rows[3].flights)}. Every row's counts are in the next section.</p>
</section>
<section>
<h2>How sure the numbers are</h2>
<p><b>The figures for all flights each have a range.</b> A percentage worked out from past flights is never exact. Its range shows how far luck alone could have moved it.{reads} The other pages show only the first figure, to keep them simple. Here they all are:</p>
{_items("ul", figures)}
<p><b>Why the ranges are wide.</b> Cancellations come in bunches: an airline cancels several flights in the same week, and a bad day hits many flights at once. So each range is worked out twice, once allowing for an airline's bad week and once for a bad day at the airport, and the wider of the two is used.</p>
<p><b>When there are too few flights.</b> The total and each row of the table get a percentage only when they rest on at least 10 cancelled flights, from at least 5 airlines and at least 5 days. The delay figures are held to the same rule, with 10 delayed flights. A row with too few reads “Not enough flights yet”.</p>
<p><b>Why a flight's own chance has no range.</b> The chance on a flight's page isn't a measured figure like the ones above. It's a mix of three histories, using the numbers 14 and 100, which haven't been tested yet. A flight number's own history is often short: one with 6 flights and none cancelled could be a flight that is never cancelled, or one that is cancelled a third of the time. In place of a range, the “Worked out from” line at the top of a flight's page says what the chance rests on: whose history, how many flights, and the dates of a bad week. The lines below it give plain counts, so you can see how much, or how little, is behind the chance.</p>
</section>
<section>
<h2>What “cancelled”, “delayed” and “notice” mean</h2>
<p><b>“Cancelled”</b> means the airport's list marked the flight cancelled. The record knows when the list changed, not when the airline decided. Some flights are only marked cancelled after their scheduled time has passed.</p>
<p><b>A cancellation never gets an exact time.</b> The program sees the list as it was before the change and as it was after. So a list of changes reads “Between 19:16 and 19:32 · Cancelled”, and never names one exact minute.</p>
<p><b>“Notice given”</b> is how long before its scheduled time a flight was marked cancelled. It's given in whole hours: “Cancelled with at least 21 hours' notice.” The 21 is rounded down, so it doesn't claim more notice than there was. Where there's a gap in the records, it's a range: “Cancelled between 7 and 50 hours before its scheduled time.” When a flight was already cancelled the first time it appeared in the records, the page says so, and the notice may have been much longer. “No notice” means the flight was only marked cancelled after its scheduled time. The airline may have told its passengers earlier than the list showed.</p>
<p><b>“Delayed”</b> means the airport's own expected time was an hour or more after the scheduled time. The time used is the last expected time the airport gave.</p>
<p><b>Why only an hour or more.</b> The airport doesn't say whether its expected time means leaving the gate or taking off. Most departures show an expected time 15 to 59 minutes after the scheduled time. That looks like the way the airport writes its times, not like real lateness. So nothing under an hour is counted as a delay, or labelled as one.</p>
<p><b>The chance of a delay counts only flights that flew.</b> A cancelled flight isn't counted as delayed. So the two chances answer two different questions. Will the flight be cancelled? And if it flies, will it be an hour or more behind schedule?</p>
<p><b>When the airport moves a flight to a new scheduled time,</b> the delay is measured from the new time. So moving a flight to a later time doesn't by itself count as a delay.</p>
</section>
<section>
<h2>What the labels mean</h2>
<p>Each flight on each day has one main label:</p>
{labels}
<p>A second label can stand beside the first, as in “LANDED · DELAYED”. DELAYED means the airport's expected time was an hour or more after the scheduled time.</p>
<p>In a list of flights, a flight sold under several numbers gets one label. It's DEPARTED or LANDED when any of its numbers departed or landed. It's CANCELLED only when none of its numbers is still on. Each number keeps its own label on its own page.</p>
<p>A flight's list of changes shows the airport's own words, in small letters: on time, delayed, landing, landed, departed, cancelled, early. There, “delayed” is the airport's own word, shown whenever its list used it. Only the label DELAYED means an hour or more.</p>
<p>{e(words.FINAL_NOTE)}</p>
</section>
<section>
<h2>Gaps in the records</h2>
<p>Records start on the evening of {since}.{gap_sentences} A flight that left the list during a gap is marked UNKNOWN.</p>
<p>A gap also blurs anything that changed during it. Such a change can only be placed between the last saved version before the gap and the first one after it. So its line in a list of changes starts “Between”. A cancellation's notice may then be a wide range, or unknown, with the words “(There's a gap in the records then.)”. A day that the records don't fully cover is marked “some flights missing”.</p>
</section>
<section>
<h2>What is being tested next</h2>
<p>A sign is an early clue: something the airport's list shows about a flight that might go with a later cancellation. Four signs are being tested. The chances on this site don't use any of them yet. None will be used until it passes the test below, and the result will be reported here whether the signs pass or fail.</p>
<p>The rest of this section gives the test in its exact words, for readers who want them. In it, “the 24-hour row” is the row the front page calls “1 day away”, and “listed as cancelled” means marked cancelled on the airport's list.</p>
<p>I am testing four signs that might go with a later cancellation: a flight of the same airline from the same airport, scheduled to land 30 minutes to 12 hours before a departure, listed as cancelled; the same flight number's previous flight listed as cancelled; another flight of the same airline, scheduled within a day either side, listed as cancelled; and a flight number first listed less than two days before its scheduled time. The rules were fixed beforehand, in the code tagged {tagged}. The counted flights are those first listed from {_written(start)}, the counting start; the 24-hour row is the table's row for 24 hours to go, and its checkpoint is that moment.</p>
<p>A sign may change what this site shows only when both of these hold:</p>
{gate}
<p>The lift is the rate with the sign over the rate without it. Its range is 2.5 standard errors of its logarithm either side, grouped as the ranges above are. 2.5, not 2, because four signs are tested at once. A sign passes when it clears the floor (10 cancelled flights with the sign, from 5 airlines and 5 days) and the whole range lies above 1. A sign that fails stays failed for this version.</p>
</section>
<section>
<h2>How it's built</h2>
<p><b>Collecting.</b> The program runs on AWS Lambda and saves each version once, to storage where it is locked for ten years. The lock is S3 Object Lock in governance mode, set on each saved version for 3,650 days from the moment it is saved. The saved versions aren't published. This site shows only what is worked out from them.</p>
<p><b>From saved versions to pages.</b> A Python data model turns the saved versions into one history per flight, and this site is generated from that model. The model is kept as Parquet files, and the site's build reads them with DuckDB. The same data always gives the same pages, byte for byte: the build uses no clock and no random numbers.</p>
<p><b>The pages</b> are plain HTML and CSS with two small scripts. One runs the search box. The other works out how old the page is, and how long is left before a flight, from the clock on your own device. Every page can still be read with scripts turned off, and nothing is loaded from any other site. I upload the pages by hand. Before each upload, a check reads every page and refuses the upload if it finds wording that claims more than the airport's list showed.</p>
<p><b>The ranges</b> are two standard errors either side of a figure on the logit scale, so they never fall below zero. The standard error is the larger of two grouped ones: flights grouped by airline and week, and by day.</p>
<p><b>Tests.</b> Every rule has tests, and the tests are themselves checked by breaking the code on purpose and confirming that a test fails.</p>
<p><b>What is frozen.</b> The counting rules and the sign test are fixed in the code tagged {tagged}. The mix behind a flight's chance is separate code and no part of that freeze.</p>
<p>The code is <a href="{e(words.CODE_URL)}">on GitHub</a>.</p>
</section>"""
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
    box's place without scripts, the line whose last words link to the day list. The box is named by its visible
    label (no aria-label: WCAG 2.5.3) and described by the hint; the results are announced as the script writes
    them."""
    before, link, after = words.FIND_OFF
    return "\n".join(['<div class="find" id="find" hidden>',
                      f'<label class="find-l" for="search">{e(words.FIND_LABEL)}</label>',
                      f'<input id="search" type="search" placeholder="{e(words.SEARCH_HINT)}" '
                      'aria-describedby="find-hint">',
                      '<ul id="search-results" aria-live="polite" hidden></ul>',
                      f'<p class="find-hint" id="find-hint">{e(words.FIND_HINT)}</p>',
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
    over its flights that flew, with no floor (Question 6e's "under 1%" is for a small archive), left out only while
    a direction has no flight that flew, as there is no figure to give. Plain HTML, no script."""
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
    if departures.flights and arrivals.flights:
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
    """"Pick a day:" and every day the site has, linked, so that no flight is out of reach without JavaScript. The
    line in the search box's place leads to the wrapper, so "Pick a day:" stays in view above the list."""
    return "\n".join(['<div class="pick" id="days">', f'<p class="days-h">{e(words.PICK_A_DAY)}</p>',
                      '<ol class="days">',
                      *(f'<li><a href="day/{x.day:%Y-%m-%d}.html">{_short_date(x.day)}</a></li>' for x in days),
                      "</ol>", "</div>"])


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
