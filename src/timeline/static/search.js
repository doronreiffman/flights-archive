// Finds flights from the front page's box (docs/site-redesign.md, front-page item 4). The entries come from the
// page's #flights-data JSON (timeline.flights.search_entries, in airline and number order, written by
// views.search_json): {"n": number keys, "p": place keys, "t": title, "u": page address}. Without JavaScript the
// box stays hidden and the day list reaches every flight. Matching is plain string comparison, so any character
// typed is just text.
const LIMIT = 10;
const MORE = " more: type more of the number or city";

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

// Fills the results list with links built through the DOM, never markup, so a title from the data stays text.
function show(list, found) {
  const items = found.shown.map((entry) => {
    const link = document.createElement("a");
    link.setAttribute("href", entry.u);
    link.textContent = entry.t;
    const item = document.createElement("li");
    item.appendChild(link);
    return item;
  });
  if (found.more > 0) {
    const more = document.createElement("li");
    more.setAttribute("class", "more");
    more.textContent = found.more + MORE;
    items.push(more);
  }
  list.replaceChildren(...items);
  list.hidden = items.length === 0;
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const box = document.getElementById("search");
    const list = document.getElementById("search-results");
    const data = document.getElementById("flights-data");
    if (!box || !list || !data) return;
    const entries = JSON.parse(data.textContent); // before the box shows: unreadable data leaves it hidden
    box.hidden = false;
    box.addEventListener("input", () => show(list, rank(box.value, entries)));
  });
}

if (typeof module !== "undefined") module.exports = { normalise, rank };
