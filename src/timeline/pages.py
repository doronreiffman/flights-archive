"""Pure functions from model rows to text and HTML for the history timeline (docs/timeline.md).

Model times (`*_at`, `*_utc`) are naive UTC; board times (`*_local`) are Israel wall-clock as published.
Wording follows the claims discipline: what the public board showed and when we saw it, nothing more.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ISRAEL = ZoneInfo("Asia/Jerusalem")


def il_time(utc_naive: datetime) -> datetime:
    """A naive UTC value from the model, in Israel time. The UTC mark is explicit: a naive astimezone()
    would read the value in the machine's own zone (on an Israeli Mac, 18:04Z would stay 18:04)."""
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(ISRAEL)


def fmt(local: datetime | None, page_date: date) -> str:
    """HH:MM for a time on the page's date, with day and month for any other date."""
    if local is None:
        return "none"
    return f"{local:%H:%M}" if local.date() == page_date else f"{local.day} {local:%b %H:%M}"


def fmt_utc(utc_naive: datetime | None, page_date: date) -> str:
    return fmt(None if utc_naive is None else il_time(utc_naive).replace(tzinfo=None), page_date)


def search_keys(airline: str, flight_no: str, city: str, airport: str) -> str:
    """Keys the search box matches by prefix: code and number as published and without leading zeros,
    then city and airport, lower case without spaces. Built from the separate fields: codes like 6H or
    ENT and numbers like 0115A make a combined string impossible to split back."""
    code, number = airline.lower(), flight_no.lower()
    bare = number.lstrip("0") or "0"
    keys = [code + number, code + bare, number, bare,  # the number alone too: people type "991"
            (city or "").lower().replace(" ", ""), (airport or "").lower()]
    return " ".join(dict.fromkeys(k for k in keys if k))


def anchor(airline: str, flight_no: str, direction: str, sched_local_first: datetime, airport: str) -> str:
    """A link target that never changes between builds: number, direction, first scheduled date and time, airport.
    The date matters: a daily 23:30 flight retimed past midnight lands on the next day's page beside that
    day's own 23:30."""
    raw = f"{airline}{flight_no}-{direction}-{sched_local_first:%Y%m%d-%H%M}-{airport}"
    return re.sub(r"[^A-Za-z0-9-]", "", raw)


def _lead(low: float, high: float) -> str:
    """How far ahead of its scheduled time the cancellation showed, from the bracket's two ends: `low` from
    the first CANCELED sighting, `high` from the sighting before it. Only what both ends support."""
    if low >= 60:
        return f"at least {int(low // 60)} h before its scheduled time"
    if high < 0:
        return "after its scheduled time"
    if low >= 0:
        return "less than an hour before its scheduled time" if high < 60 else "before its scheduled time"
    return "around its scheduled time"


def cancellation_sentence(f: dict, page_date: date) -> str | None:
    """Only "first observed CANCELED on the public board", with its bracket; never a cancellation time."""
    seen = f["canceled_first_seen_at"]
    if seen is None:
        return None
    if f["canceled_at_first_sight"]:
        text = f"Already CANCELED the first time we saw it ({fmt_utc(seen, page_date)})."
    elif f["cancel_lead_censored"]:
        # Censored: over an hour without a sighting of this flight (a pause in collection, or the flight was off the board).
        text = (f"First observed CANCELED on the public board at {fmt_utc(seen, page_date)}; we had not seen this flight since "
                f"{fmt_utc(f['cancel_announced_after'], page_date)}, so the change happened somewhere in between.")
    else:
        text = (f"First observed CANCELED on the public board between {fmt_utc(f['cancel_announced_after'], page_date)} "
                f"and {fmt_utc(seen, page_date)}, {_lead(f['cancel_lead_min'], f['cancel_lead_max_min'])}.")
    if f["uncanceled"]:  # NULL (cancelled at first sight, never seen otherwise) counts as false
        text += " Later shown with another status."
    return text


def outcome_sentence(f: dict, page_date: date) -> str | None:
    last = fmt_utc(f["last_seen_at"], page_date)
    match f["outcome"]:
        case "departed":
            return f"Board showed DEPARTED (last seen {last})."
        case "landed":
            return f"Board showed LANDED (last seen {last})."
        case "open":
            return f"Still on the board when we last stored it ({last})."
        case "gap":
            return ("Left the board while no new board was stored for over an hour "
                    "(our collection paused, or the board stopped changing); what happened is unknown.")
        case "vanished":
            hours = int((f["sched_utc_final"] - f["last_seen_at"]).total_seconds() // 3600)
            return (f"Left the board {hours} h before its scheduled time without a final status; "
                    "not necessarily cancelled, it may have been retimed.")
        case "dropped":
            return f"Left the board without a final status; last seen {last}, within an hour of its scheduled time or later."
        case "canceled":  # the cancellation sentence covers it, unless the board said something else in between
            return f"Board showed CANCELED again (last seen {last})." if f["uncanceled"] else None
    raise ValueError(f"unknown outcome {f['outcome']!r}")


# --- HTML ------------------------------------------------------------------------------------------

UNOFFICIAL = "Unofficial; not affiliated with the Israel Airports Authority."
SITE_NAME = "flights-archive: Ben Gurion board history"
TIMES_NOTE = ("Scheduled and estimated times are the board's, in Israel local time as published. "
              "The times we saw things are Israel time too.")
PARTIAL_NOTE = ("partial: the archive started or ended while this day's flights were still being listed, "
                "so some flight numbers may be missing.")

# (model column, label), in the order a timeline row lists them. status_he travels with status.
FIELDS = (("sched_local", "scheduled"), ("est_local", "estimated time, as published"), ("status", "status"),
          ("terminal", "terminal"), ("counters", "check-in counters"), ("zone", "check-in zone"),
          ("airline_name", "airline name"), ("airport_name", "airport name"), ("city_en", "city"),
          ("city_he", "city (Hebrew)"), ("country_en", "country"), ("country_he", "country (Hebrew)"))
FIRST_FIELDS = ("status", "est_local", "terminal", "counters")
BASIS = {"counters": "same slot and check-in counters",
         "time-only": "same slot and estimated time; no check-in counters to compare"}


def e(value) -> str:
    return html.escape("" if value is None else str(value))


def he(value) -> str:
    return f'<span lang="he" dir="rtl">{e(value)}</span>' if value else ""


def gap_sentence(start_utc: datetime, end_utc: datetime, page_date: date | None) -> str:
    return (f"No new board stored between {fmt_utc(start_utc, page_date)} and {fmt_utc(end_utc, page_date)}: "
            "our collection paused, or the board stopped changing.")


def layout(title: str, body: str, root: str, attribution: str) -> str:
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{e(title)}</title>\n"
        f'<link rel="stylesheet" href="{root}style.css">\n</head>\n<body>\n'
        f'<header><a href="{root}index.html">{e(SITE_NAME)}</a> · <a href="{root}methodology.html">How to read this</a></header>\n'
        f"<main>\n{body}\n</main>\n"
        f"<footer><p>{e(attribution)}</p><p>{e(UNOFFICIAL)}</p></footer>\n"
        f'<script src="{root}search.js" defer></script>\n</body>\n</html>\n')


def _value(col: str, obs: dict, page_date: date) -> str:
    v = obs.get(col)
    if col in ("sched_local", "est_local"):
        return e(fmt(v, page_date))
    if col == "status":
        return e(v or "none") + (" " + he(obs.get("status_he")) if obs.get("status_he") else "")
    if col.endswith("_he"):
        return he(v) or "none"
    return e("none" if v in (None, "") else v)


def _when(obs: dict, page_date: date, gap_hours: float) -> str:
    seen, prev = obs["observed_at"], obs["prev_observed_at"]
    if prev is not None and (seen - prev).total_seconds() > gap_hours * 3600:
        return f"between {fmt_utc(prev, page_date)} and {fmt_utc(seen, page_date)}"
    return fmt_utc(seen, page_date)


def timeline_rows(obs_rows: list[dict], page_date: date, gap_hours: float) -> str:
    """One row per observation; old values come from the flight's previous observation."""
    out, prev = [], None
    for obs in obs_rows:
        if prev is None:
            what = "first seen by us: " + " · ".join(
                f"{dict(FIELDS)[c]} {_value(c, obs, page_date)}" for c in FIRST_FIELDS)
        else:
            changed = set(obs["changed_fields"] or ())
            lines = [f"{label}: {_value(c, prev, page_date)} → {_value(c, obs, page_date)}" for c, label in FIELDS
                     if c in changed or (c == "status" and "status_he" in changed)]
            what = ("retimed: " if obs["change_kind"] == "retime" else "") + "<br>".join(lines)
        out.append(f"<tr><td>{_when(obs, page_date, gap_hours)}</td><td>{what}</td></tr>")
        prev = obs
    return "\n".join(out)


def flight_block(f: dict, obs_rows: list[dict], page_date: date, partners: list[dict], same_number: list[dict],
                 gap_hours: float) -> str:
    to_from = "to" if f["direction"] == "D" else "from"
    orig = f" (originally {fmt(f['sched_local_first'], page_date)})" if f["sched_local_first"] != f["sched_local_final"] else ""
    sentences = " ".join(s for s in (cancellation_sentence(f, page_date), outcome_sentence(f, page_date)) if s)
    notes = []
    if partners:
        names = ", ".join(f"{p['airline']} {p['flight_no']}" for p in partners)
        notes.append(f"listed together with {names} ({BASIS.get(f['codeshare_basis'], 'same slot')})")
    for o in same_number:
        notes.append(f"Same number also listed at {fmt(o['sched_local_final'], page_date)} "
                     f"({'to' if o['direction'] == 'D' else 'from'} {o['airport']})")
    boards = f["snapshots_seen"]
    return (
        f'<details id="{anchor(f["airline"], f["flight_no"], f["direction"], f["sched_local_first"], f["airport"])}" '
        f'data-k="{e(search_keys(f["airline"], f["flight_no"], f["city_en"], f["airport"]))}">\n'
        f'<summary><span class="t">{e(fmt(f["sched_local_final"], page_date) + orig)}</span> '
        f'<b>{e(f["airline"])} {e(f["flight_no"])}</b> {to_from} {e(f["city_en"])} ({e(f["airport"])}) '
        f'<span class="o">{e(sentences)}</span></summary>\n'
        + "".join(f'<p class="note">{e(n)}</p>\n' for n in notes)
        + '<table><thead><tr><th>When we saw it</th><th>What the board showed</th></tr></thead><tbody>\n'
        + timeline_rows(obs_rows, page_date, gap_hours)
        + "\n</tbody></table>\n"
        f'<p class="seen">First seen {e(fmt_utc(f["first_seen_at"], page_date))}, last seen '
        f'{e(fmt_utc(f["last_seen_at"], page_date))}. Seen on {boards} stored board{"" if boards == 1 else "s"}.</p>\n'
        "</details>")


def day_page(day: date, flights: list[dict], obs_by_flight: dict, by_group: dict, gaps: list[tuple],
             partial: bool, last_check: datetime, attribution: str, gap_hours: float) -> str:
    by_number: dict[tuple, list[dict]] = {}
    for f in flights:
        by_number.setdefault((f["airline"], f["flight_no"], f["direction"]), []).append(f)
    sections = []
    for direction, title in (("D", "Departures"), ("A", "Arrivals")):
        blocks = []
        for f in (f for f in flights if f["direction"] == direction):
            partners = [p for p in by_group.get(f["codeshare_group_id"], []) if p["flight_id"] != f["flight_id"]]
            same = [o for o in by_number[(f["airline"], f["flight_no"], f["direction"])] if o["flight_id"] != f["flight_id"]]
            blocks.append(flight_block(f, obs_by_flight.get(f["flight_id"], []), day, partners, same, gap_hours))
        sections.append(f"<h2>{title}</h2>\n" + ("\n".join(blocks) if blocks else "<p>None listed.</p>"))
    n_dep = sum(f["direction"] == "D" for f in flights)
    head = [f"<h1>{day:%A %d %B %Y}</h1>",
            f"<p>{n_dep} departures and {len(flights) - n_dep} arrivals: flight numbers listed on the board "
            "(a flight sold under several numbers counts once per number).</p>"]
    if partial:
        head.append(f'<p class="partial">{e(PARTIAL_NOTE)}</p>')
    head += [f"<p>{e(gap_sentence(a, b, day))}</p>" for a, b in gaps]
    head += [f"<p>Built from boards stored up to {e(fmt_utc(last_check, None))}. {e(TIMES_NOTE)}</p>",
             '<input id="search" type="search" hidden placeholder="Flight number or city" '
             'aria-label="Show only flights matching a number or city">']
    return layout(f"{day:%d %B %Y} · {SITE_NAME}", "\n".join(head + sections), "../", attribution)


def index_page(days: list[dict], gaps: list[tuple], first_check: datetime, last_check: datetime, attribution: str) -> str:
    rows = "\n".join(
        f'<tr><td><a href="day/{d["day"]:%Y-%m-%d}.html">{d["day"]:%Y-%m-%d}</a></td>'
        f'<td>{d["dep"]} departures, {d["arr"]} arrivals</td><td>{"partial" if d["partial"] else ""}</td></tr>'
        for d in sorted(days, key=lambda d: d["day"], reverse=True))
    body = [f"<h1>{e(SITE_NAME)}</h1>",
            "<p>What the public flight board at Ben Gurion airport showed about each flight, and when we saw it. "
            "Pick a day; each flight opens into its timeline.</p>",
            f"<p>Boards stored from {e(fmt_utc(first_check, None))} to {e(fmt_utc(last_check, None))} (Israel time). "
            "Counts are flight numbers listed on the board; a flight sold under several numbers counts once per number.</p>",
            "<table><thead><tr><th>Day</th><th>Flight numbers listed</th><th></th></tr></thead><tbody>",
            rows, "</tbody></table>", "<h2>Stretches with no new board stored</h2>"]
    body += [f"<p>{e(gap_sentence(a, b, None))}</p>" for a, b in gaps] or ["<p>None over an hour.</p>"]
    return layout(SITE_NAME, "\n".join(body), "", attribution)


def methodology_page(attribution: str, gap_hours: float, retime_hours: float) -> str:
    body = f"""<h1>How to read this</h1>
<h2>What this is</h2>
<p>An unofficial archive of the public flight board for Ben Gurion airport, which the Israel Airports Authority publishes on data.gov.il. The board shows each flight from about three days ahead until about a day after; this archive keeps what it showed after the flight leaves the board.</p>
<h2>How we collect</h2>
<p>Every two minutes we ask data.gov.il whether the board has changed, and download it when it has (about every 15 minutes) or at least every 30 minutes. Each download whose content is new is stored unchanged; "last stored" below means the last board we stored. A page shows a change at the first stored board on which we saw it; the board itself may have changed a little earlier.</p>
<h2>What a flight's timeline shows</h2>
<p>One flight number (an airline and number) on one scheduled date. The first row is what the board showed the first time we saw it, which is not necessarily when the flight first appeared on the board: most flights in the earliest days were first seen when the archive started. Each later row is a change, with the old and new values. If the flight is moved to a new scheduled time, the timeline follows it when the new time appears on the very next board within {retime_hours:g} hours; the summary then says when it was originally scheduled.</p>
<h2>Cancellations</h2>
<p>We report when the board first showed CANCELED, and the stored board before it that did not: the change happened between the two. That is when the cancellation appeared on the public board, not when the airline decided it. A lead time is given only as far as both ends support it. When we had not seen the flight for more than {gap_hours:g} hour before the CANCELED sighting, or it was already CANCELED the first time we saw it, we give no lead time.</p>
<h2>How a timeline ends</h2>
<p>The board's final words, DEPARTED or LANDED, are its status, not measured times. A flight that left the board early without a final status was not necessarily cancelled: it may have been moved to a new time that we could not link. A flight that left the board while no new board was stored for over an hour has an unknown ending.</p>
<h2>Listed together</h2>
<p>Several flight numbers often share one slot: same direction, airport, scheduled and estimated time, terminal and check-in counters. We show them as listed together. The board does not say which airline flies the aircraft, and arrivals with no counters to compare can occasionally group two different flights.</p>
<h2>Estimated times</h2>
<p>The board's estimated time is shown as published. What it measures (gate or runway) is not confirmed, so this site gives no delay figures.</p>
<h2>Pauses and partial days</h2>
<p>A pause is a stretch of more than {gap_hours:g} hour with no new board stored: our collection stopped, or the board did not change. A day is partial when the archive started or ended while that day's flights were still being listed, so some flight numbers may be missing. On any day, what the board showed before we first saw a flight, or during a pause, is missing.</p>
<h2>Receipts</h2>
<p>Since 29 October 2026 every full download leaves a write-once receipt, so a stored board is used only once its receipt shows it was stored completely. Boards stored before then are used as they are.</p>
<h2>Source</h2>
<p>{e(attribution)} {e(UNOFFICIAL)}</p>"""
    return layout(f"How to read this · {SITE_NAME}", body, "", attribution)
