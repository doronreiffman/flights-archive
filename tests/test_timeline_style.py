"""The site's style sheet (docs/site-redesign.md, "Look"): every text color pair clears WCAG's 4.5:1 in the light and
the dark scheme, the sheet loads nothing from elsewhere, and the rules the pages rely on hold: the hidden search box
stays hidden without JavaScript, published double spaces show, the Hebrew city cannot reorder the English around it,
the chart's text takes its color from the checked tokens and keeps its 12 px, and every label has a pill color."""
import re
from pathlib import Path

import pytest

from timeline import words

SHEET = Path(__file__).parent.parent / "src" / "timeline" / "static" / "style.css"
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


def test_nothing_loaded_from_elsewhere():
    """No web fonts, no images, no other sheets: the site uploads .html, .css and .js only."""
    css = SHEET.read_text(encoding="utf-8").lower()
    for banned in ("@import", "url(", "font-face"):
        assert banned not in css


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
