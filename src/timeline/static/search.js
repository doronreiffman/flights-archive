// Finds flights from the front page's box (docs/site-redesign.md, "Front page", item 2). The entries come from the
// #flights-data JSON at the end of the page's main column (timeline.flights.search_entries, in airline and number
// order, written by views.search_json): {"n": number keys, "p": place keys, "t": title, "u": page address}. Without
// JavaScript the wrapper #find (the label, the box and the hint) stays hidden and #find-off, whose link leads to the
// day list, stands in its place; once the data reads, the two change places. Matching is plain string comparison,
// so any character typed is just text.
const LIMIT = 10;
const MORE = " more. Keep typing to narrow it down.";
const NONE = "No flight found. Check the number, or try a city. Flights show up here about 3 days before they leave.";

function normalise(query) {
  return query.toLowerCase().replace(/\s+/g, "");
}

function starts(keys, q) {
  return keys.some((key) => key.startsWith(q));
}

// Exact flight numbers, then flight numbers starting with the query, then cities and airport codes starting
// with it; each group keeps the entries' order. Up to LIMIT shown, and how many more matched.
function rank(query, entries) {
  const q = normalise(query);
  if (q === "") return { shown: [], more: 0 };
  const exact = [], numbers = [], places = [];
  for (const entry of entries) {
    if (entry.n.includes(q)) exact.push(entry);
    else if (starts(entry.n, q)) numbers.push(entry);
    else if (starts(entry.p, q)) places.push(entry);
  }
  const found = [...exact, ...numbers, ...places];
  const shown = found.slice(0, LIMIT);
  return { shown, more: found.length - shown.length };
}

// A count with thousands separators, as every count on the site is written: 1,234.
function count(n) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function line(cls, text) {
  const item = document.createElement("li");
  item.setAttribute("class", cls);
  item.textContent = text;
  return item;
}

// Fills the results list with links built through the DOM, never markup, so a title from the data stays text; then
// how many more matched, or, for a query that found nothing, the line saying so. An empty box shows nothing.
function show(list, query, found) {
  const items = found.shown.map((entry) => {
    const link = document.createElement("a");
    link.setAttribute("href", entry.u);
    link.textContent = entry.t;
    const item = document.createElement("li");
    item.appendChild(link);
    return item;
  });
  if (found.more > 0) items.push(line("more", count(found.more) + MORE));
  else if (items.length === 0 && normalise(query) !== "") items.push(line("none", NONE));
  list.replaceChildren(...items);
  list.hidden = items.length === 0;
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const find = document.getElementById("find");
    const off = document.getElementById("find-off");
    const box = document.getElementById("search");
    const list = document.getElementById("search-results");
    const data = document.getElementById("flights-data");
    if (!find || !off || !box || !list || !data) return;
    const entries = JSON.parse(data.textContent); // before the wrapper shows: unreadable data leaves the page as built
    find.hidden = false;
    off.hidden = true;
    box.addEventListener("input", () => show(list, box.value, rank(box.value, entries)));
  });
}

if (typeof module !== "undefined") module.exports = { normalise, rank };
