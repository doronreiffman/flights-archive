"""The flight page's from-here script, run under Node (docs/flight-lookup.md: "Pages", Flight page; "Tests and checks").
`pick` chooses by the visitor's clock; the page hook runs against a small stand-in for the block."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "src" / "timeline" / "static" / "fromhere.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")

HOUR = 3600 * 1000
SCHED = "2026-11-13T08:00:00Z"
# The six pairs as the build writes them: (after, upto] in hours.
BOUNDS = [[48, 72], [24, 48], [12, 24], [6, 12], [3, 6], [0, 3]]


def node(program: str, payload, tz: str | None = None) -> dict:
    """Runs `program` under Node with SCRIPT and `payload` in scope; returns its printed JSON."""
    wrapper = (f"const SCRIPT = {json.dumps(str(SCRIPT))};"
               "const payload = JSON.parse(require('fs').readFileSync(0, 'utf8'));" + program)
    env = {**os.environ, **({"TZ": tz} if tz else {})}
    run = subprocess.run(["node", "-e", wrapper], input=json.dumps(payload), capture_output=True, text=True, env=env)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def picks(cases: list[tuple], tz: str | None = None) -> list:
    """pick for each (schedIso, hours left, bounds, moreAfter) case; hours left is counted from SCHED's instant."""
    return node("const t = Date.parse(payload.sched);"
                "console.log(JSON.stringify(payload.cases.map(([iso, ms, bounds, more]) =>"
                " require(SCRIPT).pick(iso, t - ms, bounds, more))));",
                {"sched": SCHED, "cases": cases}, tz)


def left(hours: float, bounds=BOUNDS, more=72, iso=SCHED) -> tuple:
    return (iso, round(hours * HOUR), bounds, more)


def test_each_boundary_between_lead_ins():
    got = picks([left(72), left(72 + 1 / HOUR), left(48), left(47.5), left(24), left(12), left(6), left(3),
                 left(1 / HOUR), left(0), left(-5)])
    # Each boundary belongs to the lower pair (after < left <= upto); 1 ms is hours 1/HOUR.
    assert got == [0, "more", 1, 1, 2, 3, 4, 5, 5, "passed", "passed"]
    assert picks([left(48 + 1 / HOUR), left(24 + 1 / HOUR), left(3 + 1 / HOUR)]) == [0, 1, 4]


def test_a_left_out_pair_shows_none():
    no_24 = [b for b in BOUNDS if b != [12, 24]]
    assert picks([left(20, no_24), left(10, no_24), left(30, no_24)]) == ["none", 2, 1]


def test_more_is_read_from_the_blocks_top_bound_not_the_top_pair():
    # The (48, 72] pair is left out below the floor; the block still says 72.
    no_top = BOUNDS[1:]
    got = picks([left(60, no_top), left(72, no_top), left(72 + 1 / HOUR, no_top), left(100, no_top)])
    assert got == ["none", "none", "more", "more"]


def test_a_missing_or_unreadable_time_or_top_bound_is_null():
    got = picks([left(10, iso="2026-11-13T08:00:00"), left(10, iso="2026-11-13T08:00:00+02:00"),
                 left(10, iso="soon Z"), left(10, iso=""), left(10, iso=None), left(10, more=None),
                 left(10, more="abc")])
    assert got == [None] * 7


@pytest.mark.parametrize("tz", ["Asia/Jerusalem", "UTC", "America/Los_Angeles"])
def test_the_same_result_under_three_time_zones(tz):
    cases = [left(72), left(72 + 1 / HOUR), left(30), left(0), left(10, iso="2026-11-13T08:00:00")]
    assert picks(cases, tz) == [0, "more", 1, "passed", None]


# A stand-in for a flight page: the block, its pairs, its .more line and the passed line after it, with just what the
# script reads, and a document that refuses to have anything written to it. It runs the hook on each payload page.
PAGE = """
function element(tag, attrs, children) {
  const el = {
    tag, hidden: false, children: children || [], next: null,
    getAttribute(name) { return name in (attrs || {}) ? attrs[name] : null; },
    querySelectorAll(sel) { return this.children.filter((c) => c.tag === sel); },
    querySelector(sel) { return this.children.find((c) => c.cls === sel.slice(1)) || null; },
    classList: { contains: (name) => el.cls === name },
    get nextElementSibling() { return this.next; },
    set innerHTML(_) { throw new Error("innerHTML set"); },
    set textContent(_) { throw new Error("textContent set"); },
  };
  return el;
}
function build(spec) {
  const lis = spec.pairs.map(([after, upto]) => element("li", {"data-after": String(after), "data-upto": String(upto)}));
  const more = element("p"); more.cls = "more"; more.hidden = true;
  const condition = element("p"), record = element("p");
  const attrs = {};
  if (spec.sched !== null) attrs["data-sched"] = spec.sched;
  if (spec.moreAfter !== null) attrs["data-more-after"] = spec.moreAfter;
  const block = element("div", attrs, [...lis, more, condition, record]);
  block.cls = "pairs";
  const passed = element("p"); passed.cls = "passed"; passed.hidden = true;
  block.next = passed;
  return {block, lis, more, condition, record, passed};
}
const pages = payload.pages.map(build);
let ready = () => {};
globalThis.document = {
  querySelectorAll: (sel) => sel === "div.pairs" ? pages.map((p) => p.block) : [],
  addEventListener: (type, listener) => { if (type === "DOMContentLoaded") ready = listener; },
};
Date.now = () => payload.now;
require(SCRIPT);
ready();
console.log(JSON.stringify(pages.map((p) => ({
  pairs: p.lis.map((li) => !li.hidden), more: !p.more.hidden, block: !p.block.hidden,
  condition: !p.condition.hidden, record: !p.record.hidden, passed: !p.passed.hidden,
}))));
"""

def sched_ms() -> int:
    return node("console.log(JSON.stringify(Date.parse(payload)))", SCHED)


def page(hours: float, pairs=BOUNDS, sched=SCHED, more_after="72") -> dict:
    return {"pairs": pairs, "sched": sched, "moreAfter": more_after, "_hours": hours}


def shown(spec: dict) -> list[dict]:
    """What the hook leaves showing on a one-block page whose clock stands `_hours` before the scheduled time."""
    spec = dict(spec)
    now = sched_ms() - round(spec.pop("_hours") * HOUR)
    return node(PAGE, {"pages": [spec], "now": now})


ALL = {"pairs": [True] * 6, "more": False, "block": True, "condition": True, "record": True, "passed": False}


def test_one_pair_shows_and_the_rest_are_hidden():
    (out,) = shown(page(30))
    assert out == {**ALL, "pairs": [False, True, False, False, False, False]}


def test_more_than_three_days_shows_the_more_line_and_no_pair():
    (out,) = shown(page(100))
    assert out == {**ALL, "pairs": [False] * 6, "more": True}


def test_a_passed_time_hides_the_block_and_shows_the_passed_line():
    (out,) = shown(page(-2))
    assert out["block"] is False and out["passed"] is True
    (out,) = shown(page(0))
    assert out["block"] is False and out["passed"] is True


def test_none_hides_the_whole_block_and_not_the_passed_line():
    (out,) = shown(page(20, pairs=[b for b in BOUNDS if b != [12, 24]]))
    assert out["block"] is False and out["passed"] is False and out["more"] is False


def test_a_missing_or_unreadable_attribute_leaves_the_list_showing():
    for bad in (page(30, sched=None), page(30, sched="2026-11-13T08:00:00"), page(30, sched="tomorrow"),
                page(30, more_after=None), page(30, more_after="lots")):
        (out,) = shown(bad)
        assert out == ALL, bad


def test_an_unreadable_pair_bound_leaves_the_list_showing():
    (out,) = shown(page(30, pairs=[[48, 72], ["x", 48], [24, 48]]))
    assert out == {**ALL, "pairs": [True] * 3}


def test_the_script_writes_no_text():
    # The stand-in throws on innerHTML or textContent being set; a run that completes proves neither was.
    (out,) = shown(page(30))
    assert out["pairs"].count(True) == 1
