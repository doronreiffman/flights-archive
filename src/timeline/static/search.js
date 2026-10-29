// Narrows a day's flights to those with a search key that starts with what was typed
// (docs/timeline.md). The page is complete without it; keys are built by timeline.pages.search_keys.
function normalise(query) {
  return query.toLowerCase().replace(/\s+/g, "");
}

function matches(query, keys) {
  const q = normalise(query);
  return q === "" || keys.split(" ").some((key) => key.startsWith(q));
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const box = document.getElementById("search");
    if (!box) return;
    box.hidden = false;
    box.addEventListener("input", () => {
      for (const flight of document.querySelectorAll("details[data-k]")) {
        flight.hidden = !matches(box.value, flight.dataset.k);
      }
    });
  });
}

if (typeof module !== "undefined") module.exports = { normalise, matches };
