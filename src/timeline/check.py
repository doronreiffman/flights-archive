"""Check a built site before upload (docs/site-redesign.md, "Anti-goals" and "Footer (every page)"): no wording
that claims more than the airport's list showed, no voice of an institution, no data-collection words outside
how-it-works.html, not the built-by placeholder, and the source line and the unofficial line on every page
(docs/terms.md, clauses 6 and 8), with the full attribution on how-it-works.html.

    PYTHONPATH=src .venv/bin/python -m timeline.check site

Runs before every upload (scripts/publish.sh). Phrases (BANNED, the placeholder) are looked for in each file as
written (attributes, a script's `<` comparisons) and with tags stripped (markup inside a page or a script string),
a phrase in either counting; entities are unescaped and whitespace collapsed in both, so an entity or a line break
cannot hide one either. Words ("we", "our", "us"; "I"; "board" and the like) are matched whole, in the page's text
with tags stripped, after the airport's data and the page titles that carry it are blanked out (DATA): an airline
named "US-BANGLA AIRLINES" must not stop an upload. Attributes hold the airport's codes in addresses and anchors,
so they are not read for words; a script or a style sheet has no attributes and is also read as written. A page
built before a footer change lacks the current wording and fails. Exit 0 clean, 1 on a hit or a missing line, 2
when there are no pages to check.
"""
import html
import re
import sys
from pathlib import Path

from model.report import ATTRIBUTION
from timeline.words import BUILT_BY, PLACEHOLDER, SOURCE_SHORT, UNOFFICIAL

BANNED = ("cancelled at", "canceled at", "delayed by", "operated by", "took off", "minutes late", "hours late",
          "pause in our collection")
SCANNED = {".html", ".css", ".js"}  # every file type scripts/publish.sh uploads
EXPLAINER = "how-it-works.html"  # the one page that may say "I" and name how the data is collected
NOTICES = {"source line": SOURCE_SHORT, "unofficial line": UNOFFICIAL}  # on every page
EXPLAINER_NOTICES = {"full source line": ATTRIBUTION}  # on EXPLAINER only

PRONOUNS = re.compile(r"\b(?:we|our|us)\b", re.I)  # every file
I_WORD = re.compile(r"\bI\b")  # pages other than EXPLAINER, outside the built-by line
# pages other than EXPLAINER, the built-by line included
COLLECTION = re.compile(r"\b(?:board|boards|snapshot|snapshots|stored|observed|receipt|receipts)\b", re.I)
# The airport's data, which the word rules skip: views.d()'s spans (escaped, so no "<" inside), the front page's
# search data (every "<" escaped) and each page's <title> (escaped; a flight page's title is the airline code, number
# and city with a few fixed words). A span with markup inside, or any other element, is read like the site's text.
DATA = re.compile(r'<span class="d">[^<]*</span>'
                  r'|<script type="application/json" id="flights-data">[^<]*</script>'
                  r'|<title>[^<]*</title>')


class NoPages(Exception):
    """The folder has no HTML pages, so a clean scan would prove nothing."""


def plain(text: str) -> str:
    """Text with entities unescaped and whitespace collapsed; case kept, for the "I" rule."""
    return re.sub(r"\s+", " ", html.unescape(text))


def flatten(text: str) -> str:
    return plain(text).lower()


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]*>", " ", text)


def _without_built_by(text: str) -> str:
    """The text with every copy of the built-by line's wording taken out ("I" is allowed there). The page escapes
    the wording and the text being read is unescaped, so only its whitespace is collapsed here."""
    built_by = re.sub(r"\s+", " ", BUILT_BY).strip()
    return text.replace(built_by, " ") if built_by else text


def _found(pattern: re.Pattern, texts: list[str]) -> list[str]:
    return sorted({m.group(0).lower() for text in texts for m in pattern.finditer(text)})


def _word_hits(name: str, raw: str) -> list[str]:
    masked = DATA.sub(" ", raw)
    text = plain(strip_tags(masked))
    texts = [text] if name.endswith(".html") else [text, plain(masked)]
    hits = _found(PRONOUNS, texts)
    if name.endswith(".html") and name != EXPLAINER:
        hits += ["I"] if I_WORD.search(_without_built_by(text)) else []
        hits += _found(COLLECTION, texts)
    return hits


def scan(site: Path) -> list[tuple[str, str]]:
    files = sorted(p for p in Path(site).rglob("*") if p.is_file() and p.suffix in SCANNED)
    if not any(p.suffix == ".html" for p in files):
        raise NoPages(f"no HTML pages under {site}")
    hits = []
    for path in files:
        name, raw = path.relative_to(site).as_posix(), path.read_text(encoding="utf-8")
        versions = (flatten(raw), flatten(strip_tags(raw)))
        hits += [(name, phrase) for phrase in BANNED if any(phrase in v for v in versions)]
        if any(flatten(PLACEHOLDER) in v for v in versions):
            hits.append((name, "built-by placeholder"))
        hits += [(name, word) for word in _word_hits(name, raw)]
    return hits


def missing_notices(site: Path) -> list[tuple[str, str]]:
    pages = sorted(p for p in Path(site).rglob("*.html") if p.is_file())
    if not pages:
        raise NoPages(f"no HTML pages under {site}")
    missing = []
    for path in pages:
        name = path.relative_to(site).as_posix()
        text = flatten(strip_tags(path.read_text(encoding="utf-8")))
        wanted = NOTICES | (EXPLAINER_NOTICES if name == EXPLAINER else {})
        missing += [(name, which) for which, notice in wanted.items() if flatten(notice) not in text]
    return missing


def main(argv: list[str]) -> int:
    try:
        hits = scan(Path(argv[0]))
        missing = missing_notices(Path(argv[0]))
    except NoPages as err:
        print(err, file=sys.stderr)
        return 2
    for name, phrase in hits:
        print(f"{name}: {phrase!r}", file=sys.stderr)
    for name, which in missing:
        print(f"{name}: missing the {which}", file=sys.stderr)
    return 1 if hits or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
