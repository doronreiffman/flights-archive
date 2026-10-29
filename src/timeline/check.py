"""Scan a built site for wording that claims more than the board showed (docs/timeline.md, "Wording").

    PYTHONPATH=src .venv/bin/python -m timeline.check site

Runs before every upload (scripts/publish.sh). Each file is read as written (attributes, a script's
`<` comparisons) and with tags stripped (markup inside a page or a script string), a phrase in either
counting; entities are unescaped and whitespace
collapsed in both, so an entity or a line break cannot either. Exit 0 clean, 1 on a hit,
2 when there are no pages to check.
"""
import html
import re
import sys
from pathlib import Path

BANNED = ("cancelled at", "canceled at", "delayed by", "operated by", "took off", "pause in our collection")
SCANNED = {".html", ".css", ".js"}  # every file type scripts/publish.sh uploads


class NoPages(Exception):
    """The folder has no HTML pages, so a clean scan would prove nothing."""


def flatten(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).lower()


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]*>", " ", text)


def scan(site: Path) -> list[tuple[str, str]]:
    files = sorted(p for p in Path(site).rglob("*") if p.is_file() and p.suffix in SCANNED)
    if not any(p.suffix == ".html" for p in files):
        raise NoPages(f"no HTML pages under {site}")
    hits = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        versions = (flatten(raw), flatten(strip_tags(raw)))
        hits += [(path.relative_to(site).as_posix(), phrase) for phrase in BANNED if any(phrase in v for v in versions)]
    return hits


def main(argv: list[str]) -> int:
    try:
        hits = scan(Path(argv[0]))
    except NoPages as err:
        print(err, file=sys.stderr)
        return 2
    for name, phrase in hits:
        print(f"{name}: {phrase!r}", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
