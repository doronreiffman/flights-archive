// The site's page script (docs/flight-lookup.md, "Pages", `fromhere.js`). The build writes every time it reads as a
// UTC instant in a data- attribute: the page's last update in data-updated, a day's scheduled time in data-sched. It
// compares them with the visitor's clock, so the visitor's time zone does not matter. Uploads are by hand, so a page
// can be a day or more old when it is read; this script keeps an old page reading right, and works it out again each
// time the page is shown again, so a tab left open does too.
//
// The page's age is the one text it writes, into each [data-updated] element (docs/site-redesign.md, "Every page").
// Everything else it does is hide, show and move what the page already holds. On a flight page: each day still
// ahead shows the pair of chances for its own time left; a day passed by the visitor's clock reads its "time has
// passed" line and goes to the past days, and the next day still ahead moves to the top with the lines under the
// chances; the all-airlines line shows the form for the top day's stretch. Without JavaScript the page stands as
// built: the age as a date and time, each day's pair for the time left at the last update, the all-airlines line in
// its form without a time.
const HOUR = 3600 * 1000;

// The instant in ms; null for anything but a string ending in "Z" that Date.parse reads (no Z would be read as
// local time).
function instant(iso) {
  if (typeof iso !== "string" || !iso.endsWith("Z")) return null;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : ms;
}

// The "Updated" line for a page last updated at `updatedIso`, read at `nowMs`, in whole hours rounded down; null for
// an unreadable time. A visitor's clock behind the upload gives a negative age, which reads as under an hour.
function age(updatedIso, nowMs) {
  const updated = instant(updatedIso);
  if (updated === null) return null;
  const hours = Math.floor((nowMs - updated) / HOUR);
  if (hours < 1) return "Updated less than an hour ago";
  if (hours === 1) return "Updated 1 hour ago";
  if (hours < 24) return `Updated ${hours} hours ago`;
  if (hours < 48) return "Updated more than a day ago";
  return `Updated more than ${Math.floor(hours / 24)} days ago`;
}

// The index of the stretch with after < hours left <= upto; "more" above moreAfter; "passed" at zero or less;
// "none" when no stretch in `bounds` fits (its form was left out below the floor); null for an unreadable time or
// top bound.
function pick(schedIso, nowMs, bounds, moreAfter) {
  const sched = instant(schedIso);
  if (sched === null || !Number.isFinite(moreAfter)) return null;
  const hours = (sched - nowMs) / HOUR;
  if (hours <= 0) return "passed";
  if (hours > moreAfter) return "more";
  const index = bounds.findIndex(([after, upto]) => hours > after && hours <= upto);
  return index === -1 ? "none" : index;
}

// Which of a flight page's days ahead at the last update (their data-sched, in page order: the top day, then the
// later days, soonest first) have passed by the visitor's clock, and the first still ahead (null when none is);
// null when any time is unreadable. A day passes at its scheduled time, as in pick.
function plan(scheds, nowMs) {
  const times = scheds.map(instant);
  if (times.includes(null)) return null;
  const passed = [];
  times.forEach((t, i) => { if (t <= nowMs) passed.push(i); });
  const top = times.findIndex((t) => t > nowMs);
  return { passed, top: top === -1 ? null : top };
}

// A missing attribute is null, which Number would read as 0: it must stay unreadable.
function number(text) {
  return text === null || text.trim() === "" ? NaN : Number(text);
}

// The children of `el` with class `cls`, in page order; none for a missing `el`.
function kids(el, cls) {
  return el ? [...el.children].filter((child) => child.classList.contains(cls)) : [];
}

function kid(el, cls) {
  return kids(el, cls)[0] || null;
}

// Each element's (after, upto] in hours; null when any bound is unreadable.
function stretches(els) {
  const bounds = els.map((el) => [number(el.getAttribute("data-after")), number(el.getAttribute("data-upto"))]);
  return bounds.every(([after, upto]) => Number.isFinite(after) && Number.isFinite(upto)) ? bounds : null;
}

// A day still ahead shows the pair for its own time left. Its pairs run from the stretch it was in at the last update
// down to the last 3 hours, the first showing as built. Above the first pair's top (above 72 hours, or with a
// visitor's clock behind the upload), for a stretch with no pair, or with an unreadable bound, the pairs stay as
// built: the first pair stays.
function showPair(day, nowMs) {
  const pairs = kids(kid(day, "chances"), "pair");
  const bounds = stretches(pairs);
  if (!pairs.length || bounds === null) return;
  const result = pick(day.getAttribute("data-sched"), nowMs, bounds, bounds[0][1]);
  if (typeof result === "number") pairs.forEach((pair, i) => { pair.hidden = i !== result; });
}

// A passed day hides its chances and reads its "time has passed" line.
function markPassed(day) {
  const chances = kid(day, "chances");
  if (chances) chances.hidden = true;
  const line = kid(day, "passed");
  if (line) line.hidden = false;
}

// The all-airlines line with a day ahead: the form for the top day's stretch, the "more than 3 days" line above the
// line's top bound, nothing for a stretch whose form was left out; the form without a time hides. An unreadable
// attribute leaves the line as built.
function showStretch(line, schedIso, nowMs) {
  const forms = [...line.children].filter((el) => !el.classList.contains("more") && !el.classList.contains("off"));
  const bounds = stretches(forms);
  if (bounds === null) return;
  const result = pick(schedIso, nowMs, bounds, number(line.getAttribute("data-more-after")));
  if (result === null) return;
  const shown = result === "more" ? kid(line, "more") : typeof result === "number" ? forms[result] : null;
  [...line.children].forEach((el) => { el.hidden = el !== shown; });
}

// No day ahead: the no-flight-ahead headline and "Worked out from" line show, and the flight-ahead line hides. The
// all-airlines line (`line`, when the page has one) shows its form without a time alone, as built, whatever form an
// earlier run showed while a day was still ahead.
function showNoneAhead(support, line) {
  kids(support, "none-ahead").forEach((el) => { el.hidden = false; });
  kids(support, "worked").forEach((el) => { if (!el.classList.contains("none-ahead")) el.hidden = true; });
  if (line) [...line.children].forEach((el) => { el.hidden = !el.classList.contains("off"); });
}

// A flight page's days (docs/flight-lookup.md, "Pages", Flight page). #now holds the traveller's day with the
// support (the lines under its chances); .later holds the later days ahead, soonest first; .past the past days,
// newest first. A page built with no day ahead has no day in #now and is left as built.
function arrange(nowMs) {
  const now = document.getElementById("now");
  const top = kid(now, "day");
  if (!top) return;
  const parts = [...now.parentElement.children];
  const later = parts.find((el) => el.classList.contains("later"));
  const past = parts.find((el) => el.classList.contains("past"));
  const days = [top, ...kids(later, "day")];
  const steps = plan(days.map((d) => d.getAttribute("data-sched")), nowMs);
  if (steps === null) return;
  const ahead = steps.top === null ? null : days[steps.top];
  const head = ahead || days[days.length - 1]; // the day that stands in #now: the first ahead, else the latest passed
  const leaving = steps.passed.map((i) => days[i]).filter((d) => d !== head);
  if (leaving.length && !past) return; // nowhere to move them: the page stays as built
  days.forEach((d, i) => { if (steps.passed.includes(i)) markPassed(d); else showPair(d, nowMs); });
  const support = kid(top, "support");
  if (head !== top) {
    if (support) head.insertBefore(support, kid(head, "own"));
    now.insertBefore(head, top);
  }
  // Each to the head of .past in page order, so the latest ends first.
  leaving.forEach((d) => { past.insertBefore(d, kid(past, "day")); });
  if (!support) return;
  const line = kid(support, "aa");
  if (ahead) {
    if (line) showStretch(line, ahead.getAttribute("data-sched"), nowMs);
  } else {
    showNoneAhead(support, line);
  }
}

// The page's age, and on a flight page its days, at the visitor's clock now. Run when the page loads, and again
// whenever it is shown again: a page the browser brings back from memory (pageshow), a tab come back to
// (visibilitychange, once visible). Each step reads the page as it stands, so a second run moves only what has
// changed since the first, and a second run at the same clock changes nothing.
function refresh() {
  const nowMs = Date.now();
  document.querySelectorAll("[data-updated]").forEach((el) => {
    const text = age(el.getAttribute("data-updated"), nowMs);
    if (text !== null) el.textContent = text;
  });
  arrange(nowMs);
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", refresh);
  window.addEventListener("pageshow", refresh);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refresh(); });
}

if (typeof module !== "undefined") module.exports = { age, pick, plan };
