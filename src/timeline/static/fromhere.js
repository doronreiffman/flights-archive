// Picks which prepared sentence of a flight page's from-here block to show (docs/flight-lookup.md, "Pages", Flight
// page). The build writes the scheduled time as a UTC instant in the block's data-sched, the block's top bound in
// hours in data-more-after, and each prepared pair as an li with data-after and data-upto. This script compares the
// instant with the visitor's clock, so the visitor's time zone does not matter. It writes no text: it only hides and
// shows what the page already holds. Without JavaScript the block shows every pair as a list.
const HOUR = 3600 * 1000;

// The index of the pair with after < hours left <= upto; "more" above moreAfter; "passed" at zero or less; "none"
// when no pair in `bounds` fits (the fitting pair was left out below the floor); null for an unreadable time or bound.
function pick(schedIso, nowMs, bounds, moreAfter) {
  if (typeof schedIso !== "string" || !schedIso.endsWith("Z")) return null; // no Z would be read as local time
  const sched = Date.parse(schedIso);
  if (Number.isNaN(sched) || !Number.isFinite(moreAfter)) return null;
  const hours = (sched - nowMs) / HOUR;
  if (hours <= 0) return "passed";
  if (hours > moreAfter) return "more";
  const index = bounds.findIndex(([after, upto]) => hours > after && hours <= upto);
  return index === -1 ? "none" : index;
}

// A missing attribute is null, which Number would read as 0: it must stay unreadable.
function number(text) {
  return text === null || text.trim() === "" ? NaN : Number(text);
}

function apply(block) {
  const pairs = [...block.querySelectorAll("li")];
  const bounds = pairs.map((li) => [number(li.getAttribute("data-after")), number(li.getAttribute("data-upto"))]);
  if (bounds.some((pair) => !Number.isFinite(pair[0]) || !Number.isFinite(pair[1]))) return;
  const result = pick(block.getAttribute("data-sched"), Date.now(), bounds, number(block.getAttribute("data-more-after")));
  if (result === null) return;
  if (result === "passed") {
    block.hidden = true;
    const line = block.nextElementSibling;
    if (line && line.classList.contains("passed")) line.hidden = false;
  } else if (result === "none") {
    block.hidden = true; // the condition line speaks of the figure, which "none" does not show
  } else if (result === "more") {
    pairs.forEach((li) => { li.hidden = true; });
    const line = block.querySelector(".more");
    if (line) line.hidden = false;
  } else {
    pairs.forEach((li, i) => { li.hidden = i !== result; });
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("div.pairs").forEach(apply);
  });
}

if (typeof module !== "undefined") module.exports = { pick };
