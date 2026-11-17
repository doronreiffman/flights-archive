"""The front page's search script, run under Node (docs/site-redesign.md, "Front page", item 2; "Search data"). The
script needs no browser for its ranking; the page hook runs against a small stand-in for the page."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_timeline_flights import flight, local, rows
from test_timeline_views import HOSTILE
from timeline import flights, views

SCRIPT = Path(__file__).parent.parent / "src" / "timeline" / "static" / "search.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
MORE = "more. Keep typing to narrow it down."
NONE = "No flight found. Check the number, or try a city. Flights show up here about 3 days before they leave."


def entry(airline: str, number: str, city: str, airport: str) -> dict:
    """A search entry as flights.search_entries writes it, for a departure to `city`."""
    return {"n": flights.number_keys(airline, number), "p": flights.place_keys(city, airport),
            "t": f"{airline} {number} · Tel Aviv to {city}", "u": f"flight/{airline}{number}-D.html"}


# In search_entries' order: airline, then number.
ENTRIES = [entry("6H", "0115A", "Eilat", "ETM"), entry("EY", "607", "Abu Dhabi", "AUH"),
           entry("IZ", "991", "New York", "JFK"), entry("LY", "001", "New York", "JFK"),
           entry("LY", "0010", "London", "LHR")]


def node(program: str, payload) -> dict:
    """Runs `program` under Node with SCRIPT (the script's path) and `payload` in scope; returns its printed JSON."""
    wrapper = (f"const SCRIPT = {json.dumps(str(SCRIPT))};"
               "const payload = JSON.parse(require('fs').readFileSync(0, 'utf8'));" + program)
    run = subprocess.run(["node", "-e", wrapper], input=json.dumps(payload), capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def ranked(query: str, entries: list[dict] = ENTRIES) -> tuple[list[str], int]:
    """The titles rank shows for `query`, in order, and how many more matched."""
    out = node("const r = require(SCRIPT).rank(payload.query, payload.entries);"
               "console.log(JSON.stringify({shown: r.shown.map((e) => e.t), more: r.more}));",
               {"query": query, "entries": entries})
    return out["shown"], out["more"]


def test_an_exact_flight_number_comes_before_numbers_starting_with_it():
    assert ranked("ly 001") == (["LY 001 · Tel Aviv to New York", "LY 0010 · Tel Aviv to London"], 0)
    assert ranked("LY001") == ranked("ly 001") == ranked("  Ly  001 ")


def test_a_bare_number_matches_exactly_before_by_prefix():
    # "1" is LY 001's number without its zeros; LY 0010 ("10") and 6H 0115A ("115a") only start with it.
    assert ranked("1") == (["LY 001 · Tel Aviv to New York", "6H 0115A · Tel Aviv to Eilat",
                            "LY 0010 · Tel Aviv to London"], 0)
    assert ranked("991") == (["IZ 991 · Tel Aviv to New York"], 0)


def test_cities_and_airport_codes_match_by_prefix_ordered_by_airline_and_number():
    new_york = ["IZ 991 · Tel Aviv to New York", "LY 001 · Tel Aviv to New York"]
    assert ranked("new york") == ranked("New York") == ranked("jfk") == ranked("ne") == (new_york, 0)
    assert ranked("york") == ([], 0)  # a key matches from its start, never from inside it


def test_flight_numbers_come_before_places():
    # "e": EY 607's number starts with it; 6H 0115A only by its place (Eilat, ETM), though 6H sorts first.
    assert ranked("e") == (["EY 607 · Tel Aviv to Abu Dhabi", "6H 0115A · Tel Aviv to Eilat"], 0)


def test_an_empty_query_shows_nothing():
    assert ranked("") == ([], 0)
    assert ranked("   ") == ([], 0)


def test_ten_results_at_most_then_how_many_more():
    many = [entry("LY", f"{n:03d}", "London", "LHR") for n in range(1, 13)]
    assert ranked("ly", many) == ([f"LY {n:03d} · Tel Aviv to London" for n in range(1, 11)], 2)
    assert ranked("ly", many[:10]) == ([f"LY {n:03d} · Tel Aviv to London" for n in range(1, 11)], 0)


@pytest.mark.parametrize("query", ["LY+1", "(", "\\", "[", "*", ".", "^", "$", "?", "|"])
def test_pattern_characters_are_matched_as_typed(query):
    assert ranked(query) == ([], 0)
    assert ranked(query, [entry("ZZ", query, "Nowhere", "NOW")]) == ([f"ZZ {query} · Tel Aviv to Nowhere"], 0)


# A stand-in for the front page: the elements the script uses, built like the real ones (the wrapper #find hidden, the
# line in its place shown), and an innerHTML that refuses to be set. It types each of payload.typed into the box and
# prints what the results list holds after each.
PAGE = """
function element(tag, hidden = true) {
  const listeners = {};
  return {
    tag, hidden, value: "", textContent: "", attributes: {}, children: [],
    setAttribute(name, value) { this.attributes[name] = String(value); },
    appendChild(child) { this.children.push(child); return child; },
    replaceChildren(...children) { this.children = children; },
    addEventListener(type, listener) { listeners[type] = listener; },
    fire(type) { listeners[type](); },
    set innerHTML(_) { throw new Error("innerHTML set"); },
  };
}
const page = {"find": element("div"), "find-off": element("p", false), "search": element("input", false),
              "search-results": element("ul"), "flights-data": element("script")};
page["flights-data"].textContent = payload.data;
let ready = () => {};
globalThis.document = {
  getElementById: (id) => page[id] || null,
  createElement: (tag) => element(tag, false),
  addEventListener: (type, listener) => { if (type === "DOMContentLoaded") ready = listener; },
};
require(SCRIPT);
const shown = () => ({find: !page.find.hidden, off: !page["find-off"].hidden});
const before = shown();
let threw = false;
try { ready(); } catch (_) { threw = true; }
const list = page["search-results"];
const results = () => ({
  hidden: list.hidden,
  items: list.children.map((li) => li.children.length
    ? {tag: li.tag, a: li.children[0].tag, href: li.children[0].attributes.href, text: li.children[0].textContent}
    : {tag: li.tag, class: li.attributes.class, text: li.textContent}),
});
const after = [];
const loaded = results();
const page_after = shown();
for (const typed of payload.typed) {
  page.search.value = typed;
  page.search.fire("input");
  after.push(results());
}
console.log(JSON.stringify({before, threw, shown: page_after, loaded, after}));
"""


def typed(entries: list[dict], *queries: str, data: str | None = None) -> dict:
    return node(PAGE, {"data": views.search_json(entries) if data is None else data, "typed": list(queries)})


def link(e: dict) -> dict:
    return {"tag": "li", "a": "a", "href": e["u"], "text": e["t"]}


def test_once_the_data_reads_the_wrapper_shows_and_the_line_in_its_place_goes():
    """Without JavaScript the label, the box and the hint stay hidden in their wrapper and "To find your flight, pick
    its day below." stands in their place; once the script has read the flights, the two change places."""
    out = typed(ENTRIES)
    assert out["before"] == {"find": False, "off": True}
    assert not out["threw"] and out["shown"] == {"find": True, "off": False}
    assert out["loaded"] == {"hidden": True, "items": []}


def test_unreadable_data_leaves_both_as_built():
    out = typed([], data='[{"n": ["ly1"]')
    assert out["threw"] and out["shown"] == {"find": False, "off": True}


def test_the_list_shows_while_something_is_typed():
    out = typed(ENTRIES, "ly 001", "")
    assert out["after"] == [{"hidden": False, "items": [link(ENTRIES[3]), link(ENTRIES[4])]},
                            {"hidden": True, "items": []}]


def test_ten_links_then_a_line_saying_how_many_more():
    """docs/site-redesign.md, "Front page", item 2: "12 more. Keep typing to narrow it down."."""
    many = [entry("LY", f"{n:03d}", "London", "LHR") for n in range(1, 23)]
    out = typed(many, "london", "ly 01")
    assert out["after"][0] == {"hidden": False, "items": [*map(link, many[:10]),
                                                          {"tag": "li", "class": "more", "text": f"12 {MORE}"}]}
    assert out["after"][0]["items"][-1]["text"] == "12 more. Keep typing to narrow it down."
    assert out["after"][1] == {"hidden": False, "items": [*map(link, many[9:19])]}  # LY 010 to 019: ten, no line


def test_the_more_line_writes_its_count_with_thousands_separators():
    """As every count on the site: "1,234 more. Keep typing to narrow it down."."""
    many = [entry("LY", f"{n:04d}", "London", "LHR") for n in range(1, 1245)]  # 1,244: ten shown, 1,234 more
    out = typed(many, "london")
    assert out["after"][0]["items"][-1] == {"tag": "li", "class": "more", "text": f"1,234 {MORE}"}
    assert len(out["after"][0]["items"]) == 11


def test_a_query_that_matches_nothing_says_so():
    """docs/site-redesign.md, "Front page", item 2: one line for a query that finds no flight; nothing for an empty
    box."""
    out = typed(ENTRIES, "zz", "  ", "york")
    assert out["after"] == [{"hidden": False, "items": [{"tag": "li", "class": "none", "text": NONE}]},
                            {"hidden": True, "items": []},
                            {"hidden": False, "items": [{"tag": "li", "class": "none", "text": NONE}]}]


def test_the_results_carry_the_flight_pages_titles():
    """The search list shows each flight by its page's title (docs/site-redesign.md, "Names"), written by
    flights.search_entries: "LH 697 · Tel Aviv to Athens or Frankfurt" for a number that has flown to two cities, the
    newest day's first."""
    lh = dict(airline="LH", flight_no="697")
    found = flights.search_entries(rows(flight("fra", local(28, 9, 0), **lh, airport="FRA", city_en="FRANKFURT"),
                                        flight("ath", local(29, 9, 0), **lh, airport="ATH", city_en="ATHENS")))
    out = typed(found, "lh697", "frankfurt")
    title = {"tag": "li", "a": "a", "href": "flight/LH697-D.html", "text": "LH 697 · Tel Aviv to Athens or Frankfurt"}
    assert out["after"] == [{"hidden": False, "items": [title]}] * 2


def test_a_title_with_markup_from_the_data_stays_text():
    # The JSON as the front page writes it (every "<" escaped), read back by the script and shown as text.
    out = typed([*ENTRIES, HOSTILE], "</scr")
    assert out["after"] == [{"hidden": False, "items": [link(HOSTILE)]}]
