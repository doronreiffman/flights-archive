"""The site's page script, fromhere.js, run under Node (docs/flight-lookup.md: "Pages", `fromhere.js`; "Tests and
checks", `fromhere.js`). `age`, `pick` and `plan` are read against a given clock; the page hook runs against a
stand-in for a built page, made to the flight page's markup (docs/will-it-fly-plan.md, Tasks 10 and 11): the
traveller's day in #now with the slot's support, the later days ahead, the past days."""
import copy
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "src" / "timeline" / "static" / "fromhere.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")

HOUR = 3600 * 1000
MINUTE = 60 * 1000
ZONES = ["Asia/Jerusalem", "UTC", "America/Los_Angeles"]
SCHED = "2026-11-13T08:00:00Z"
# The six stretches as the build writes them: (after, upto] in hours.
BOUNDS = [[48, 72], [24, 48], [12, 24], [6, 12], [3, 6], [0, 3]]
STRETCHES = [tuple(b) for b in BOUNDS]


def node(program: str, payload, tz: str | None = None):
    """Runs `program` under Node with SCRIPT and `payload` in scope; returns its printed JSON."""
    wrapper = (f"const SCRIPT = {json.dumps(str(SCRIPT))};"
               "const payload = JSON.parse(require('fs').readFileSync(0, 'utf8'));" + program)
    env = {**os.environ, **({"TZ": tz} if tz else {})}
    run = subprocess.run(["node", "-e", wrapper], input=json.dumps(payload), capture_output=True, text=True, env=env)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


# --- pick --------------------------------------------------------------------------------------------

def picks(cases: list[tuple], tz: str | None = None) -> list:
    """pick for each (schedIso, hours left, bounds, moreAfter) case; hours left is counted from SCHED's instant."""
    return node("const t = Date.parse(payload.sched);"
                "console.log(JSON.stringify(payload.cases.map(([iso, ms, bounds, more]) =>"
                " require(SCRIPT).pick(iso, t - ms, bounds, more))));",
                {"sched": SCHED, "cases": cases}, tz)


def left(hours: float, bounds=BOUNDS, more=72, iso=SCHED) -> tuple:
    return (iso, round(hours * HOUR), bounds, more)


def test_each_boundary_between_the_six_stretches():
    got = picks([left(72), left(72 + 1 / HOUR), left(48), left(47.5), left(24), left(12), left(6), left(3),
                 left(1 / HOUR), left(0), left(-5)])
    # Each boundary belongs to the lower stretch (after < left <= upto); 1 ms is hours 1/HOUR. More than 72 hours
    # is "more"; a time at or before the clock has passed.
    assert got == [0, "more", 1, 1, 2, 3, 4, 5, 5, "passed", "passed"]
    assert picks([left(48 + 1 / HOUR), left(24 + 1 / HOUR), left(3 + 1 / HOUR)]) == [0, 1, 4]


def test_a_left_out_stretch_shows_none():
    no_24 = [b for b in BOUNDS if b != [12, 24]]
    assert picks([left(20, no_24), left(10, no_24), left(30, no_24)]) == ["none", 2, 1]


def test_more_is_read_from_the_given_top_bound_not_the_top_stretch():
    # The (48, 72] form is left out below the floor; the line still says 72.
    no_top = BOUNDS[1:]
    got = picks([left(60, no_top), left(72, no_top), left(72 + 1 / HOUR, no_top), left(100, no_top)])
    assert got == ["none", "none", "more", "more"]


def test_a_missing_or_unreadable_time_or_top_bound_is_null():
    got = picks([left(10, iso="2026-11-13T08:00:00"), left(10, iso="2026-11-13T08:00:00+02:00"),
                 left(10, iso="soon Z"), left(10, iso=""), left(10, iso=None), left(10, more=None),
                 left(10, more="abc")])
    assert got == [None] * 7


@pytest.mark.parametrize("tz", ZONES)
def test_the_same_pick_under_three_time_zones(tz):
    cases = [left(72), left(72 + 1 / HOUR), left(30), left(0), left(10, iso="2026-11-13T08:00:00")]
    assert picks(cases, tz) == [0, "more", 1, "passed", None]


# --- plan --------------------------------------------------------------------------------------------

def sched_in(hours: float) -> str:
    """The instant `hours` after SCHED, written as the build writes it."""
    return (datetime(2026, 11, 13, 8, tzinfo=timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def planned(scheds: list, tz: str | None = None):
    """plan over `scheds`, read at the instant SCHED."""
    return node("console.log(JSON.stringify(require(SCRIPT).plan(payload.scheds, Date.parse(payload.at))))",
                {"scheds": scheds, "at": SCHED}, tz)


@pytest.mark.parametrize("tz", ZONES)
def test_plan_reads_the_days_passed_and_the_first_still_ahead(tz):
    # A day passes at its scheduled time; one minute ahead is still ahead.
    assert planned([sched_in(-3), sched_in(0), sched_in(1 / 60), sched_in(30)], tz) == {"passed": [0, 1], "top": 2}
    assert planned([sched_in(5), sched_in(30)], tz) == {"passed": [], "top": 0}
    assert planned([sched_in(-30), sched_in(-1)], tz) == {"passed": [0, 1], "top": None}


def test_plan_is_null_when_any_time_is_unreadable():
    for bad in ("2026-11-13T09:00:00", "2026-11-13T09:00:00+02:00", "soon Z", "", None):
        assert planned([sched_in(5), bad]) is None, bad
        assert planned([bad, sched_in(5)]) is None, bad


# --- age ---------------------------------------------------------------------------------------------

UPDATED = datetime(2026, 11, 17, 9, 46, tzinfo=timezone.utc)
UPDATED_ISO = "2026-11-17T09:46:00Z"
UPDATED_MS = int(UPDATED.timestamp()) * 1000
BUILT_AGE = "Updated 17 Nov at 09:46"  # the build's date-and-time form, which stands without scripts
UNREADABLE = ["2026-11-17T09:46:00", "2026-11-17T09:46:00+02:00", "soon Z", ""]

# (milliseconds since the last update, the line), each boundary from both sides (docs/site-redesign.md, "Every page").
AGES = [(-5 * HOUR, "Updated less than an hour ago"),  # a visitor's clock behind the upload
        (0, "Updated less than an hour ago"),
        (59 * MINUTE, "Updated less than an hour ago"),
        (HOUR - 1, "Updated less than an hour ago"),
        (HOUR, "Updated 1 hour ago"),
        (2 * HOUR - 1, "Updated 1 hour ago"),
        (2 * HOUR, "Updated 2 hours ago"),
        (3 * HOUR - 1, "Updated 2 hours ago"),
        (23 * HOUR, "Updated 23 hours ago"),
        (24 * HOUR - 1, "Updated 23 hours ago"),
        (24 * HOUR, "Updated more than a day ago"),
        (47 * HOUR, "Updated more than a day ago"),
        (48 * HOUR - 1, "Updated more than a day ago"),
        (48 * HOUR, "Updated more than 2 days ago"),
        (72 * HOUR - 1, "Updated more than 2 days ago"),
        (72 * HOUR, "Updated more than 3 days ago"),
        (168 * HOUR, "Updated more than 7 days ago")]


def aged(isos: list, ms: int, tz: str | None = None) -> list:
    return node("const {age} = require(SCRIPT);"
                "console.log(JSON.stringify(payload.isos.map((iso) => age(iso, payload.at))))",
                {"isos": isos, "at": ms}, tz)


# --- the stand-in page -------------------------------------------------------------------------------

# A stand-in for a built page: elements with just what the script may use (getElementById, children, parentElement,
# classList, getAttribute, hidden, insertBefore, appendChild, firstElementChild and querySelectorAll("[data-updated]")).
# Setting text outside a [data-updated] element, or any markup anywhere, throws. Moving an element takes it out of
# its old place, as in a browser. Each element carries a serial number `n`, so an element can be followed as it moves.
HARNESS = """
const writes = [];
let serial = 0;
const label = (el) => `${el.tag}${el.attrs.id ? "#" + el.attrs.id : ""}${el.attrs.class ? "." + el.attrs.class : ""}`;
function write(el, how, value) {
  if (!("data-updated" in el.attrs)) throw new Error(`${how} set on ${label(el)}`);
  el.text = String(value);
  writes.push(el.n);
}
function make(spec, parent) {
  const [tag, attrs, body] = spec;
  const own = { ...attrs };
  const hidden = "hidden" in own;
  delete own.hidden;
  const el = {
    tag, attrs: own, hidden, n: serial++, parentElement: parent, kids: [], text: typeof body === "string" ? body : "",
    get children() { return this.kids; },
    get firstElementChild() { return this.kids[0] || null; },
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; },
    classList: { contains: (name) => (own.class || "").split(" ").includes(name) },
    insertBefore(child, ref) {
      if (arguments.length < 2) throw new TypeError("insertBefore takes two arguments");
      if (ref !== null && ref.parentElement !== this) throw new Error(`insertBefore: ${label(ref)} is not a child`);
      if (child === ref) return child;
      if (child.parentElement) child.parentElement.kids.splice(child.parentElement.kids.indexOf(child), 1);
      this.kids.splice(ref === null ? this.kids.length : this.kids.indexOf(ref), 0, child);
      child.parentElement = this;
      return child;
    },
    appendChild(child) { return this.insertBefore(child, null); },
    set textContent(value) { write(this, "textContent", value); },
    set innerText(value) { write(this, "innerText", value); },
    set innerHTML(_) { throw new Error(`innerHTML set on ${label(this)}`); },
    set outerHTML(_) { throw new Error(`outerHTML set on ${label(this)}`); },
  };
  if (Array.isArray(body)) el.kids = body.map((child) => make(child, el));
  return el;
}
const root = make(payload.page, null);
function* walk(el) { yield el; for (const kid of el.kids) yield* walk(kid); }
let ready = null;
globalThis.document = {
  getElementById: (id) => [...walk(root)].find((el) => el.attrs.id === id) || null,
  querySelectorAll(selector) {
    if (selector !== "[data-updated]") throw new Error(`querySelectorAll(${selector})`);
    return [...walk(root)].filter((el) => "data-updated" in el.attrs);
  },
  addEventListener(type, listener) { if (type === "DOMContentLoaded") ready = listener; },
};
const dump = (el) => ({ tag: el.tag, n: el.n, attrs: { ...el.attrs }, hidden: el.hidden, text: el.text,
                        children: el.kids.map(dump) });
const built = dump(root);
Date.now = () => payload.now;
require(SCRIPT);
ready();
console.log(JSON.stringify({ built, after: dump(root), writes }));
"""

MORE = "Your flight is more than 3 days away. Flights show up on the airport's list about 3 days ahead."
OFF = "Of all flights from Tel Aviv, about 2% were cancelled."
WORKED = "Worked out from LO 155's 22 flights, LOT's flights and all flights."
WORKED_NONE = "Worked out from LO 155's 22 flights, for its next flight."
NOT_LISTED = "isn't on the airport's list"


def hidden(attrs: dict, flag: bool) -> dict:
    return {**attrs, "hidden": ""} if flag else attrs


def chances(hours: float) -> list:
    """A day's pairs as the build writes them: one per stretch still ahead `hours` before the day, the first showing."""
    ahead = [(a, u) for a, u in STRETCHES if a < hours]
    return ["div", {"class": "chances"},
            [["div", hidden({"class": "pair", "data-after": str(a), "data-upto": str(u)}, i > 0),
              [["p", {"class": "fig"}, f"Chance it's cancelled, {a} to {u} hours: about 2%"]]]
             for i, (a, u) in enumerate(ahead)]]


def support(updated: str | None = UPDATED_ISO, left_out=(), ahead: bool = True) -> list:
    """The slot's lines under the chances, as built with a day ahead, or with none (`ahead` false)."""
    forms = [["p", {"data-after": str(a), "data-upto": str(u), "hidden": ""}, f"All airlines, {a} to {u} hours."]
             for a, u in STRETCHES if (a, u) not in left_out]
    aa = ["div", {"class": "aa", "data-more-after": "72"},
          ([*forms, ["p", {"class": "more", "hidden": ""}, MORE]] if ahead else []) + [["p", {"class": "off"}, OFF]]]
    fresh = ["span", {} if updated is None else {"data-updated": updated}, BUILT_AGE]
    return ["div", {"class": "support"},
            [["div", hidden({"class": "none-ahead"}, ahead), [["p", {"class": "fig"}, "Chance its next flight..."]]],
             *([["p", {"class": "worked"}, WORKED]] if ahead else []),
             ["p", hidden({"class": "worked none-ahead"}, ahead), WORKED_NONE],
             ["p", {"class": "s-line"}, "So far, 1 of LO 155's 22 flights was cancelled."],
             aa,
             ["p", {"class": "fresh"}, [fresh]],
             ["p", {"class": "means"}, [["a", {"href": "../how-it-works.html#what-the-numbers-mean"}, "What..."]]]]]


def day(anchor: str, hours: float | None = None, with_chances: bool = True, with_support: list | None = None) -> list:
    """A section.day: a day ahead at the last update, `hours` before it, or a past day (no `hours`, no data-sched)."""
    kids = [["p", {"class": "head"}, f"The day {anchor}"]]
    if hours is not None:
        kids += [chances(hours)] if with_chances else [["p", {}, "This flight is marked cancelled."]]
        kids.append(["p", {"class": "passed", "hidden": ""}, "This flight's time has passed."])
    kids += [with_support] if with_support else []
    kids.append(["div", {"class": "own"}, [["p", {}, f"What changed on {anchor}"]]])
    attrs = {"class": "day", "id": anchor} | ({} if hours is None else {"data-sched": instant(hours)})
    return ["section", attrs, kids]


def instant(hours: float) -> str:
    """The instant `hours` after the last update, written as the build writes it."""
    return (UPDATED + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def frame(*parts: list, updated: str | None = UPDATED_ISO) -> list:
    """A page: the "Updated" line under the top line, then the page's own parts."""
    top_line = ["p", {"class": "updated"} | ({} if updated is None else {"data-updated": updated}), BUILT_AGE]
    return ["body", {}, [top_line, ["main", {}, list(parts)]]]


def flight_page(top: float = 2, later=(), past=("p1", "p2"), left_out=(), updated: str | None = UPDATED_ISO,
                no_chances=()) -> list:
    """A flight page at its last update: the traveller's day `top` hours ahead in #now with the support, the strip,
    a later day ahead for each of `later` (hours ahead, soonest first; None leaves out .later), the past days (None
    leaves out .past). A day named in `no_chances` is ahead without chances (marked cancelled, or not UPCOMING)."""
    parts = [["div", {"class": "flight-h"}, [["h1", {}, "LO 155 · Warsaw to Tel Aviv"]]],
             ["div", {"id": "now"}, [day("t", top, "t" not in no_chances, support(updated, left_out))]],
             ["section", {"class": "record"}, [["ol", {"class": "strip"}, []]]]]
    if later is not None:
        parts.append(["div", {"class": "later"},
                      [day(f"l{i}", h, f"l{i}" not in no_chances) for i, h in enumerate(later)]])
    if past is not None:
        parts.append(["div", {"class": "past"}, [day(a) for a in past]])
    return frame(*parts, updated=updated)


def no_day_page() -> list:
    """A flight page built with no day ahead: the not-listed line and the support in its no-flight-ahead form."""
    return frame(["div", {"id": "now"}, [["p", {"class": "none-line"}, f"LO 155 {NOT_LISTED} right now."],
                                         support(ahead=False)]],
                 ["section", {"class": "record"}, []], ["div", {"class": "later"}, []],
                 ["div", {"class": "past"}, [day("p1")]])


def other_page() -> list:
    """A page that is not a flight page: a day page."""
    return frame(["h1", {}, "Monday 16 November"], ["ul", {"class": "flights"}, [["li", {}, "LO 155"]]])


def run(page: list, clock_hours: float, tz: str | None = None) -> tuple[dict, dict, list]:
    """The page as built, the page after the hook ran with the visitor's clock `clock_hours` after the last update,
    and the serial numbers of the elements whose text the script set."""
    out = node(HARNESS, {"page": page, "now": UPDATED_MS + round(clock_hours * HOUR)}, tz)
    return out["built"], out["after"], out["writes"]


def walk(el: dict):
    yield el
    for kid in el["children"]:
        yield from walk(kid)


def classes(el: dict) -> list[str]:
    return el["attrs"].get("class", "").split()


def part(tree: dict, name: str) -> dict:
    """The element with id `name`, else the first with class `name`."""
    els = list(walk(tree))
    return next((el for el in els if el["attrs"].get("id") == name), None) or next(el for el in els
                                                                                    if name in classes(el))


def has(tree: dict, name: str) -> bool:
    return any(el["attrs"].get("id") == name or name in classes(el) for el in walk(tree))


def days(tree: dict, name: str) -> list[str]:
    """The ids of the days in #now, .later or .past, in page order."""
    return [kid["attrs"]["id"] for kid in part(tree, name)["children"] if "day" in classes(kid)]


def layout(el: dict) -> list[str]:
    """The first class (else the tag) of each child of `el`, in page order."""
    return [(classes(kid) or [kid["tag"]])[0] for kid in el["children"]]


def kid(el: dict, cls: str) -> dict:
    (found,) = [k for k in el["children"] if cls in classes(k)]
    return found


def bounds(el: dict) -> tuple[int, int]:
    return int(el["attrs"]["data-after"]), int(el["attrs"]["data-upto"])


def pairs_shown(tree: dict, anchor: str) -> list[tuple[int, int]]:
    return [bounds(p) for p in kid(part(tree, anchor), "chances")["children"] if not p["hidden"]]


def aa_shown(tree: dict) -> list:
    """What shows in the all-airlines line: a form's bounds, "more" or "off"."""
    return [classes(el)[0] if classes(el) else bounds(el) for el in part(tree, "aa")["children"] if not el["hidden"]]


def slot(tree: dict) -> dict:
    """Which of the support's two kinds of line show: the no-flight-ahead parts and the flight-ahead line."""
    lines = part(tree, "support")["children"]
    return {"none-ahead": [not el["hidden"] for el in lines if "none-ahead" in classes(el)],
            "flight-ahead worked": [not el["hidden"] for el in lines if classes(el) == ["worked"]]}


def passed_shown(tree: dict, anchor: str) -> bool:
    return not kid(part(tree, anchor), "passed")["hidden"]


def chances_shown(tree: dict, anchor: str) -> bool:
    return not kid(part(tree, anchor), "chances")["hidden"]


def ages(tree: dict) -> list[str]:
    """The top "Updated" line and, on a flight page, the freshness line's."""
    lines = [part(tree, "updated")["text"]]
    if has(tree, "fresh"):
        lines.append(part(tree, "fresh")["children"][0]["text"])
    return lines


def blank_ages(tree: dict) -> dict:
    tree = copy.deepcopy(tree)
    for el in walk(tree):
        if "data-updated" in el["attrs"]:
            el["text"] = ""
    return tree


def with_attr(page: list, pick_el, name: str, value: str | None) -> list:
    """`page` with attribute `name` set to `value` (removed for None) on every element `pick_el` picks."""
    page = copy.deepcopy(page)

    def specs(spec):
        yield spec
        if isinstance(spec[2], list):
            for child in spec[2]:
                yield from specs(child)
    for spec in specs(page):
        if pick_el(spec[1]):
            if value is None:
                spec[1].pop(name, None)
            else:
                spec[1][name] = value
    return page


def by_id(anchor: str):
    return lambda attrs: attrs.get("id") == anchor


# --- the page's age ----------------------------------------------------------------------------------

@pytest.mark.parametrize("tz", ZONES)
def test_the_age_at_each_boundary(tz):
    got = node("const {age} = require(SCRIPT);"
               "console.log(JSON.stringify(payload.cases.map((ms) => age(payload.updated, payload.at + ms))))",
               {"updated": UPDATED_ISO, "at": UPDATED_MS, "cases": [ms for ms, _ in AGES]}, tz)
    assert got == [line for _, line in AGES]
    # On a page, the top line and the flight page's freshness line both read it; on any page, the top line.
    _, after, _ = run(flight_page(), 3.5, tz)
    assert ages(after) == ["Updated 3 hours ago"] * 2
    _, after, _ = run(other_page(), -2, tz)
    assert ages(after) == ["Updated less than an hour ago"]


def test_an_unreadable_update_instant_leaves_the_date_and_time():
    assert aged([*UNREADABLE, None], UPDATED_MS + 5 * HOUR) == [None] * 5
    for bad in [*UNREADABLE, None]:  # None: the attribute is missing
        _, after, writes = run(flight_page(updated=bad), 5)
        assert ages(after) == [BUILT_AGE] * 2 and writes == [], bad
        _, after, _ = run(frame(updated=bad), 5)
        assert ages(after) == [BUILT_AGE], bad


# --- the flight page's days --------------------------------------------------------------------------

def test_with_no_day_passed_each_day_ahead_shows_the_pair_for_its_own_time_left():
    # Five hours after the last update: the top day 4 hours ahead, the later days 21 and 75 hours ahead.
    built, after, _ = run(flight_page(top=9, later=(26, 80)), 5)
    assert (days(after, "now"), days(after, "later"), days(after, "past")) == (["t"], ["l0", "l1"], ["p1", "p2"])
    assert pairs_shown(built, "t") == [(6, 12)] and pairs_shown(after, "t") == [(3, 6)]
    assert pairs_shown(after, "l0") == [(12, 24)]
    assert pairs_shown(after, "l1") == [(48, 72)]  # above 72 hours its first pair stays
    assert aa_shown(after) == [(3, 6)]  # the top day's stretch; the form without a time hides
    assert slot(after) == {"none-ahead": [False, False], "flight-ahead worked": [True]}
    assert not any(passed_shown(after, d) for d in ("t", "l0", "l1"))


def test_more_than_72_hours_keeps_the_first_pair_and_shows_the_more_line():
    _, after, _ = run(flight_page(top=80), 0)
    assert pairs_shown(after, "t") == [(48, 72)]
    assert aa_shown(after) == ["more"]
    # A visitor's clock behind the upload: 50 hours left of a day built 30 hours ahead, past its first pair's top.
    _, after, _ = run(flight_page(top=30), -20)
    assert pairs_shown(after, "t") == [(24, 48)]
    assert aa_shown(after) == [(48, 72)]
    assert ages(after) == ["Updated less than an hour ago"] * 2


def test_a_stretch_left_out_shows_no_all_airlines_line():
    _, after, _ = run(flight_page(top=20, left_out=[(12, 24)]), 0)
    assert pairs_shown(after, "t") == [(12, 24)]
    assert aa_shown(after) == []


def test_a_passed_day_with_a_later_day_ahead():
    # Five hours after the last update: the top day passed 3 hours ago; the later days are 21 and 45 hours ahead.
    built, after, _ = run(flight_page(top=2, later=(26, 50)), 5)
    assert (days(after, "now"), days(after, "later"), days(after, "past")) == (["l0"], ["l1"], ["t", "p1", "p2"])
    # That day is at the top with its own pair, the support block inside it before its own lines.
    assert pairs_shown(after, "l0") == [(12, 24)] and pairs_shown(after, "l1") == [(24, 48)]
    assert layout(part(after, "l0")) == ["head", "chances", "passed", "support", "own"]
    assert layout(part(after, "t")) == ["head", "chances", "passed", "own"]
    assert kid(part(after, "l0"), "support")["n"] == kid(part(built, "t"), "support")["n"]
    # The passed day reads "time has passed", its chances hidden.
    assert passed_shown(after, "t") and not chances_shown(after, "t")
    assert not passed_shown(after, "l0") and chances_shown(after, "l0")
    # The slot speaks of that day: its stretch, the flight-ahead line.
    assert aa_shown(after) == [(12, 24)]
    assert slot(after) == {"none-ahead": [False, False], "flight-ahead worked": [True]}


def test_a_passed_day_without_chances_reads_its_passed_line():
    # A day ahead marked cancelled carries no chances; once passed it reads "time has passed" all the same.
    _, after, _ = run(flight_page(top=2, later=(26, 50), no_chances=("t", "l1")), 5)
    assert days(after, "now") == ["l0"] and days(after, "past") == ["t", "p1", "p2"]
    assert passed_shown(after, "t") and not passed_shown(after, "l1")
    assert pairs_shown(after, "l0") == [(12, 24)]


def test_two_passed_days():
    # Six hours after the last update: the top day and the first later day passed; the next is 24 hours ahead.
    _, after, _ = run(flight_page(top=2, later=(4, 30)), 6)
    assert (days(after, "now"), days(after, "later"), days(after, "past")) == (["l1"], [], ["l0", "t", "p1", "p2"])
    assert passed_shown(after, "t") and passed_shown(after, "l0")
    assert not chances_shown(after, "t") and not chances_shown(after, "l0")
    assert layout(part(after, "l1")) == ["head", "chances", "passed", "support", "own"]
    assert pairs_shown(after, "l1") == [(12, 24)] and aa_shown(after) == [(12, 24)]


def test_the_last_day_ahead_passed():
    built, after, _ = run(flight_page(top=2), 3)
    assert (days(after, "now"), days(after, "past")) == (["t"], ["p1", "p2"])
    assert passed_shown(after, "t") and not chances_shown(after, "t")
    assert layout(part(after, "t")) == layout(part(built, "t"))
    # The no-flight-ahead headline and "Worked out from" line show, the flight-ahead line hides, and the all-airlines
    # line reads its form without a time. Nothing says "isn't on the airport's list": the page holds no such line,
    # and the script writes no text but the age (test_the_script_writes_no_text_but_the_updated_line, "the last
    # passed").
    assert slot(after) == {"none-ahead": [True, True], "flight-ahead worked": [False]}
    assert aa_shown(after) == ["off"]


def test_the_last_of_several_days_ahead_passed():
    # Eight hours after the last update every day ahead has passed: the latest stays at the top, with the support.
    _, after, _ = run(flight_page(top=2, later=(5,)), 8)
    assert (days(after, "now"), days(after, "later"), days(after, "past")) == (["l0"], [], ["t", "p1", "p2"])
    assert passed_shown(after, "l0") and passed_shown(after, "t")
    assert layout(part(after, "l0")) == ["head", "chances", "passed", "support", "own"]
    assert slot(after) == {"none-ahead": [True, True], "flight-ahead worked": [False]}
    assert aa_shown(after) == ["off"]  # nothing says "isn't on the airport's list", as above ("the last of two passed")


def test_a_page_a_week_old():
    _, after, _ = run(flight_page(top=2, later=(26, 50)), 168)
    assert ages(after) == ["Updated more than 7 days ago"] * 2
    assert (days(after, "now"), days(after, "later"), days(after, "past")) == (["l1"], [], ["l0", "t", "p1", "p2"])
    assert all(passed_shown(after, d) for d in ("t", "l0", "l1"))
    assert slot(after) == {"none-ahead": [True, True], "flight-ahead worked": [False]} and aa_shown(after) == ["off"]


# --- what the script leaves alone --------------------------------------------------------------------

SCENES = [pytest.param(flight_page(top=9, later=(26, 80)), 5, id="none passed"),
          pytest.param(flight_page(top=2, later=(26, 50)), 5, id="one passed"),
          pytest.param(flight_page(top=2, later=(4, 30)), 6, id="two passed"),
          pytest.param(flight_page(top=2), 3, id="the last passed"),
          pytest.param(flight_page(top=2, later=(5,)), 8, id="the last of two passed"),
          pytest.param(flight_page(top=80), 0, id="over 72 hours"),
          pytest.param(flight_page(top=2, later=(26, 50)), 168, id="a week old"),
          pytest.param(no_day_page(), 5, id="no day ahead"),
          pytest.param(other_page(), 5, id="a day page")]


@pytest.mark.parametrize("page,clock", SCENES)
def test_the_script_writes_no_text_but_the_updated_line(page, clock):
    # The stand-in throws on text set anywhere else, and on markup set anywhere; a run that completes proves neither.
    built, after, writes = run(page, clock)
    dated = sorted(el["n"] for el in walk(built) if "data-updated" in el["attrs"])
    assert sorted(writes) == dated
    before = {el["n"]: el["text"] for el in walk(built)}
    now = {el["n"]: el["text"] for el in walk(after)}
    assert now.keys() == before.keys()  # nothing made, nothing taken away
    assert sorted(n for n in now if now[n] != before[n]) == dated


def test_a_page_with_no_day_ahead_changes_nothing_but_its_age():
    for clock in (-5, 0, 5, 100):
        for name, page in (("no day ahead", no_day_page()), ("a day page", other_page())):
            built, after, _ = run(page, clock)
            assert blank_ages(after) == blank_ages(built), (clock, name)
            assert set(ages(after)) == set(aged([UPDATED_ISO], UPDATED_MS + clock * HOUR)), (clock, name)


def test_a_missing_or_unreadable_attribute_leaves_the_page_as_built():
    # An unreadable scheduled time on any day ahead: no day moves, nothing hides or shows. Five hours on, the top
    # day would have passed.
    page = flight_page(top=2, later=(26, 50))
    for anchor in ("t", "l0", "l1"):
        for bad in [*UNREADABLE, None]:
            built, after, _ = run(with_attr(page, by_id(anchor), "data-sched", bad), 5)
            assert blank_ages(after) == blank_ages(built), (anchor, bad)
    # An unreadable bound on a pair that does not fit leaves that day's pairs as built; the rest is read.
    page = flight_page(top=30)
    for name in ("data-after", "data-upto"):
        for bad in ("x", "", "  ", None):
            fit = lambda a: "pair" in a.get("class", "") and a.get("data-after") == "6"  # noqa: E731
            built, after, _ = run(with_attr(page, fit, name, bad), 10)
            assert pairs_shown(after, "t") == pairs_shown(built, "t") == [(24, 48)], (name, bad)
            assert aa_shown(after) == [(12, 24)]
    # An unreadable top bound of the all-airlines line, or a bound of one of its forms: the line as built.
    for pick_el, name in ((lambda a: a.get("class") == "aa", "data-more-after"),
                          (lambda a: a.get("data-upto") == "72" and "class" not in a, "data-upto"),
                          (lambda a: a.get("data-after") == "0" and "class" not in a, "data-after")):
        for bad in ("lots", "", "  ", None):
            built, after, _ = run(with_attr(page, pick_el, name, bad), 10)
            assert part(after, "aa") == part(built, "aa"), (name, bad)
            assert pairs_shown(after, "t") == [(12, 24)]


def test_a_page_without_the_past_list_is_left_as_built_when_a_day_must_move_there():
    built, after, _ = run(flight_page(top=2, later=(26,), past=None), 5)
    assert blank_ages(after) == blank_ages(built)
    # With nothing to move there, the rest is read: the only day ahead has passed, and there is no later list.
    _, after, _ = run(flight_page(top=2, later=None, past=None), 3)
    assert passed_shown(after, "t") and slot(after)["none-ahead"] == [True, True]


def test_a_day_that_passes_moves_into_an_empty_past_list():
    # The build writes .past on every flight page, empty for a number with no past day yet: a day that passes is its
    # first.
    _, after, _ = run(flight_page(top=2, later=(26,), past=()), 5)
    assert (days(after, "now"), days(after, "later"), days(after, "past")) == (["l0"], [], ["t"])
    assert passed_shown(after, "t") and not chances_shown(after, "t")
    assert layout(part(after, "l0")) == ["head", "chances", "passed", "support", "own"]
