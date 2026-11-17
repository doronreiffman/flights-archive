"""The site's style sheet (docs/site-redesign.md, "Look"): every text color pair clears WCAG's 4.5:1 in the light and
the dark scheme, the sheet loads nothing from elsewhere (its four fonts come from the site's own folder, pinned here
with their licence), and the rules the pages rely on hold: the hidden search box
stays hidden without JavaScript, published double spaces show, the Hebrew city cannot reorder the English around it,
the chart's text takes its color from the checked tokens and keeps its 12 px, and every label has a pill color."""
import hashlib
import re
from pathlib import Path

import pytest

from timeline import words

SHEET = Path(__file__).parent.parent / "src" / "timeline" / "static" / "style.css"
FONT_DIR = SHEET.parent / "fonts"
# The four faces as committed (docs/site-redesign.md, "Look A"; cut down by the designer, so a font tool would be needed
# to make them again), and the licence of the two IBM Plex releases they come from, the SIL Open Font License 1.1 text
# byte for byte: name -> (bytes, SHA-256).
FONTS = {"sans-cond-300.woff2": (11_484, "e070faf89ddc75682e1bf4b433ba2402141aa7f4e1878dd15b22a2ef51e6bd3f"),
         "sans-cond-400.woff2": (11_440, "b3c68c0f353026db70fa9cbcac91209db1e2a677498564f4b956cdf083c5cb0e"),
         "sans-cond-600.woff2": (11_468, "20cb8090896387a5f1e149bb73dd7cda143d718afaac3fdea9f3538b63658d46"),
         "hebrew-sans-400.woff2": (2_108, "37a0d768ea31da4df80b1c947bd795508c8783f4d3a245bd00960bd4bd798d14")}
LICENCE = {"LICENSE.txt": (4_456, "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da")}
DARK = "@media (prefers-color-scheme: dark)"
TOKENS = ("--bg", "--fg", "--muted", "--line", "--accent", "--card", "--cancel-fg", "--cancel-bg", "--ok-fg",
          "--ok-bg", "--plain-fg", "--plain-bg", "--delay-fg", "--delay-bg", "--unknown-fg", "--band-bg", "--band-fg",
          "--band-muted")
# (text, background). The brief's ten, then the ones the sheet adds: the story box's and the footer's links (accent on
# the card), the warning lines and a cancelled tile's figure (cancel red on the page), a warning line in a flight row
# a link points to (cancel red on the card), and the header band's wordmark and its lede and last-updated line. The chart's text is drawn on the page in tokens checked against --bg below.
PAIRS = (("--fg", "--bg"), ("--muted", "--bg"), ("--accent", "--bg"), ("--fg", "--card"), ("--muted", "--card"),
         ("--cancel-fg", "--cancel-bg"), ("--ok-fg", "--ok-bg"), ("--plain-fg", "--plain-bg"),
         ("--delay-fg", "--delay-bg"), ("--unknown-fg", "--bg"), ("--accent", "--card"), ("--cancel-fg", "--bg"),
         ("--cancel-fg", "--card"), ("--band-fg", "--band-bg"), ("--band-muted", "--band-bg"))
ON_PAGE = {text for text, background in PAIRS if background == "--bg"}


def rules(css: str) -> list[tuple[tuple[str, ...], str, dict[str, str]]]:
    """(enclosing at-rules, selector, declarations) for every rule, comments dropped and whitespace collapsed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, stack, buf = [], [], ""
    for ch in css:
        if ch == "{":
            stack.append(" ".join(buf.split()))
            buf = ""
        elif ch == "}":
            if buf.strip():
                decls = dict(part.split(":", 1) for part in buf.split(";") if part.strip())
                out.append((tuple(stack[:-1]), stack[-1], {k.strip(): " ".join(v.split()) for k, v in decls.items()}))
            stack.pop()
            buf = ""
        else:
            buf += ch
    return out


RULES = rules(SHEET.read_text(encoding="utf-8"))


def declared(media: tuple[str, ...], selector: str) -> dict[str, str]:
    """Every declaration of the rules for exactly `selector` inside exactly `media`, later ones winning."""
    merged = {}
    for at, sel, decls in RULES:
        if at == media and selector in (s.strip() for s in sel.split(",")):
            merged |= decls
    return merged


SCHEMES = {"light": declared((), ":root"), "dark": declared((DARK,), ":root")}


def luminance(hex_color: str) -> float:
    """WCAG 2 relative luminance of "#rgb" or "#rrggbb"."""
    h = hex_color.lstrip("#")
    h = "".join(c * 2 for c in h) if len(h) == 3 else h
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_formula_known_values():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#777", "#fff") == pytest.approx(4.48, abs=0.01)  # the classic just-fails grey


@pytest.mark.parametrize("scheme", SCHEMES)
def test_every_token_is_a_hex_color_in_both_schemes(scheme):
    tokens = SCHEMES[scheme]
    for token in TOKENS:
        assert re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", tokens.get(token, "")), (scheme, token)


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("text,background", PAIRS)
def test_text_pairs_clear_4_5_to_1(scheme, text, background):
    tokens = SCHEMES[scheme]
    ratio = contrast(tokens[text], tokens[background])
    assert ratio >= 4.5, f"{scheme}: {text} {tokens[text]} on {background} {tokens[background]} is {ratio:.2f}:1"


FACES = [decls for _, sel, decls in RULES if sel == "@font-face"]
URL = re.compile(r"""url\(\s*(["']?)(.*?)\1\s*\)""", re.I)


def test_the_four_font_files_are_pinned():
    """A changed or missing file fails here, not at an upload. Hidden files (a Finder .DS_Store) are never built."""
    found = {p.name: (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
             for p in FONT_DIR.iterdir() if not p.name.startswith(".")}
    assert found == FONTS | LICENCE


def test_fonts_load_only_from_the_sites_own_folder():
    """docs/site-redesign.md, "Tests and checks": no other sheet (`@import`); a `url(` only inside an `@font-face` rule,
    naming one of the four files of the site's own fonts folder, so no address with a scheme or a host, no `data:`
    address and no image; nor an image named without `url(` (`image-set`)."""
    css = re.sub(r"/\*.*?\*/", "", SHEET.read_text(encoding="utf-8"), flags=re.S).lower()
    assert "@import" not in css
    assert not re.search(r"\bimage(?:-set)?\(", css)
    in_faces = [m.group(2) for face in FACES for value in face.values() for m in URL.finditer(value)]
    assert css.count("url(") == len(in_faces) == len(FONTS)
    assert sorted(in_faces) == sorted(f"fonts/{name}" for name in FONTS)


def test_the_hebrew_face_is_limited_to_the_hebrew_block():
    """Only a page with Hebrew on it fetches the Hebrew file, and every face lets the text show in a fallback until
    its file arrives (docs/site-redesign.md, "Look A", Loading)."""
    assert len(FACES) == len(FONTS)
    assert all(face.get("font-display") == "swap" for face in FACES)
    ranges = {URL.search(face["src"]).group(2): face.get("unicode-range") for face in FACES}
    assert ranges == {"fonts/sans-cond-300.woff2": None, "fonts/sans-cond-400.woff2": None,
                      "fonts/sans-cond-600.woff2": None, "fonts/hebrew-sans-400.woff2": "U+0590-05FF"}


def test_the_text_is_set_in_the_four_faces_before_the_designs_fallbacks():
    """docs/site-redesign.md, "Look A": the condensed face in Light, Regular and SemiBold, the Hebrew one in Regular,
    and behind them "Arial Narrow", "Roboto Condensed", "Helvetica Neue", Arial, sans-serif."""
    faces = {(face["font-family"], face["font-weight"], URL.search(face["src"]).group(2)) for face in FACES}
    assert faces == {('"FA Sans Cond"', "300", "fonts/sans-cond-300.woff2"),
                     ('"FA Sans Cond"', "400", "fonts/sans-cond-400.woff2"),
                     ('"FA Sans Cond"', "600", "fonts/sans-cond-600.woff2"),
                     ('"FA Hebrew Sans"', "400", "fonts/hebrew-sans-400.woff2")}
    assert SCHEMES["light"]["--sans"] == ('"FA Sans Cond", "FA Hebrew Sans", "Arial Narrow", "Roboto Condensed", '
                                          '"Helvetica Neue", Arial, sans-serif')
    assert declared((), "body")["font"].endswith(" var(--sans)")


def test_hidden_attribute_wins_over_any_display_rule():
    """The search box and its results carry `hidden` until the script shows them; a display rule on either would
    override the attribute, so without JavaScript an empty box would show."""
    assert declared((), "[hidden]").get("display") == "none !important"


def test_published_double_spaces_show():
    """Airline names keep the airport's spacing ("ARKIA  ISRAELI  AIRLINES")."""
    assert declared((), ".d").get("white-space") == "pre-wrap"


def test_flight_numbers_in_the_table_never_break():
    """Each number is a `.d` span whose own pre-wrap would let "LY 5410" break at its space when the table squeezes
    the column; `pre` keeps the published spacing and stops the break."""
    assert declared((), ".cancellations td:nth-child(2) .d").get("white-space") == "pre"


def test_flight_numbers_on_a_day_page_never_break():
    """The day list's numbers are `.d` spans too: "LY 005" must not split across two lines in its column."""
    assert declared((), ".flights .nums .d").get("white-space") == "pre"


def test_band_text_takes_the_band_colors():
    """The band's text sits on --band-bg, so it must take the band's own checked tokens, not the page's."""
    assert declared((), ".band").get("background") == "var(--band-bg)"
    assert declared((), ".wordmark a").get("color") == "var(--band-fg)"
    assert declared((), ".band .lede").get("color") == "var(--band-muted)"
    assert declared((), ".band .updated").get("color") == "var(--band-muted)"


def test_a_long_codeshare_list_wraps_after_its_commas():
    """Only the numbers are kept whole: the flight cell itself sets no nowrap, on any screen, so a long list of
    codeshare numbers wraps after a comma instead of widening the table past a phone's width."""
    cell = [decls for _, sel, decls in RULES if ".cancellations td:nth-child(2)" in (s.strip() for s in sel.split(","))]
    assert cell and all(decls.get("white-space") != "nowrap" for decls in cell)


PHONE = "@media (max-width: 600px)"


def test_the_from_here_table_stacks_on_a_phone_as_the_cancellations_table_does():
    """docs/flight-lookup.md, "Pages", Front page: on a narrow screen each row of the table stacks, as the
    cancellations table's do. Its heads are hidden there, so each cell prints its column's head (views writes it as
    `data-label`) before it."""
    for part in ("", " tbody", " td"):
        assert declared((PHONE,), f".cancellations{part}").get("display") == "block", part
        assert declared((PHONE,), f".fromhere{part}").get("display") == "block", part
    assert declared((PHONE,), ".fromhere tr").get("display") == "block"
    assert declared((PHONE,), ".fromhere thead").get("clip-path") == "inset(50%)"
    assert declared((PHONE,), ".fromhere td::before").get("content") == 'attr(data-label) ": "'


def test_hebrew_city_is_isolated():
    assert declared((), '[dir="rtl"]').get("unicode-bidi") == "isolate"


def test_chart_text_takes_checked_colors_and_keeps_its_size():
    """The SVG's text is black unless the sheet fills it, unreadable in dark mode; each fill is a token checked
    against the page. The 12 px comes from the SVG's own font-size attribute, which a CSS font rule would override."""
    chart = [(sel, decls) for at, sel, decls in RULES if ".chart" in sel]
    text_fills = [(sel, decls["fill"]) for sel, decls in chart if re.search(r"\btext\b", sel) and "fill" in decls]
    assert ".chart text" in {sel for sel, _ in text_fills}
    for sel, fill in text_fills:
        token = re.fullmatch(r"var\((--[a-z-]+)\)", fill)
        assert token and token.group(1) in ON_PAGE, (sel, fill)
    for sel, decls in chart:
        assert not {"font", "font-size"} & decls.keys(), sel


@pytest.mark.parametrize("label", [*words.LABEL_ORDER, "DELAYED"])
def test_every_label_has_a_pill_color(label):
    """views._labels writes `label l-<name>`; a label with no rule would show as bare text."""
    cls = "l-" + label.lower().replace(" ", "-")
    assert any(re.search(rf"\.{cls}\b", sel) and "color" in decls for _, sel, decls in RULES), cls
