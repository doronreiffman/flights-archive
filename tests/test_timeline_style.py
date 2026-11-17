"""The site's style sheet, look A, "Timetable" (docs/site-redesign.md, "Look"): the six colour tokens in the light and
the dark scheme, every text pair clearing WCAG's 4.5:1 in both, red only for a cancelled thing, a mark before every
label and in the strip, nothing on a phone under 13 px, the sheet's width and gutters, the cancellations table
stacking on a phone while the chance table does not, and a 3 px focus outline. The sheet loads nothing from elsewhere
(its four fonts come from the site's own folder, pinned here with their licence), and the rules the pages rely on hold:
the hidden search box stays hidden without JavaScript, published double spaces show, the Hebrew city cannot reorder
the English around it, and numbers are tabular."""
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
WIDE = "@media (max-width: 1040px)"
PHONE = "@media (max-width: 760px)"
# docs/site-redesign.md, "Look A", "Black and white, and one red": paper, ink, secondary text, hairlines, the tint for
# the row a link points at and a line under the pointer, and the red.
LIGHT = {"--paper": "#ffffff", "--ink": "#111111", "--soft": "#595959", "--hair": "#d6d6d6", "--tint": "#f4f4f2",
         "--red": "#cf2e1e"}
TOKENS = tuple(LIGHT)
# (text, background): every text colour on the paper and on the tint.
PAIRS = (("--ink", "--paper"), ("--ink", "--tint"), ("--soft", "--paper"), ("--soft", "--tint"),
         ("--red", "--paper"), ("--red", "--tint"))


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


def parts(selector: str) -> list[str]:
    return [s.strip() for s in selector.split(",")]


def declared(media: tuple[str, ...], selector: str) -> dict[str, str]:
    """Every declaration of the rules for exactly `selector` inside exactly `media`, later ones winning."""
    merged = {}
    for at, sel, decls in RULES:
        if at == media and selector in parts(sel):
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
    assert contrast("#595959", "#ffffff") == pytest.approx(7.00, abs=0.01)  # the design's figure for the soft text


# --- colour ---------------------------------------------------------------------------------------------------------

def test_the_tokens_in_both_schemes():
    """The light values are the design's; the dark scheme swaps paper and ink and lightens the red (docs/site-redesign.md,
    "Look A", "Dark scheme"). The page's own background is set, so a browser's default never shows through."""
    light, dark = SCHEMES["light"], SCHEMES["dark"]
    assert {token: light.get(token) for token in TOKENS} == LIGHT
    for token in TOKENS:
        assert re.fullmatch(r"#[0-9a-f]{6}", dark.get(token, "")), token
    assert (dark["--paper"], dark["--ink"]) == (light["--ink"], light["--paper"])
    assert luminance(dark["--red"]) > luminance(light["--red"])
    assert declared((), "body").get("background") == "var(--paper)"
    assert declared((), "body").get("color") == "var(--ink)"


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("text,background", PAIRS)
def test_text_pairs_clear_4_5_to_1(scheme, text, background):
    tokens = SCHEMES[scheme]
    ratio = contrast(tokens[text], tokens[background])
    assert ratio >= 4.5, f"{scheme}: {text} {tokens[text]} on {background} {tokens[background]} is {ratio:.2f}:1"


COLOURED = ("color", "background", "background-color", "border", "border-top", "border-bottom", "border-left",
            "border-color", "outline", "fill", "stroke", "box-shadow")


def test_every_colour_is_a_token():
    """No colour depends on a light ground (docs/site-redesign.md, "Dark scheme"): outside the two token lists every
    colour the sheet sets is one of the six tokens, or the text's own colour, so the dark scheme reaches all of it."""
    for at, sel, decls in RULES:
        if sel == ":root":
            continue
        for prop in COLOURED:
            value = decls.get(prop, "")
            assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", value), (at, sel, prop, value)
            for token in re.findall(r"var\((--[a-z-]+)\)", value):
                assert token in TOKENS, (at, sel, prop, value)


# docs/site-redesign.md, "Red only for 'cancelled'": the CANCELLED label, the notice sentence under it, a cancelled
# day's mark in the strip (and its mark in the key), the cancelled part of a day's bar and the total's "cancelled" tile.
CANCELLED_THINGS = ("l-cancelled", "warn", "s-cancelled", "cancelled", "cancel")
RED = "var(--red)"


def names_a_cancelled_thing(selector: str) -> bool:
    return any(re.search(rf"\.{cls}(?![\w-])", selector) for cls in CANCELLED_THINGS)


def test_red_only_for_cancelled():
    """Every rule that uses the red names a cancelled thing in each of its selectors; and each of those things is red."""
    red = [(at, sel) for at, sel, decls in RULES if any(RED in value for value in decls.values())]
    assert red
    for at, sel in red:
        for part in parts(sel):
            assert names_a_cancelled_thing(part), (at, part)
    assert declared((), ".l-cancelled").get("color") == RED
    assert declared((), ".warn").get("color") == RED
    assert declared((), ".s-cancelled i").get("background") == RED
    assert declared((), ".chart .cancelled").get("fill") == RED
    assert declared((), ".stat.cancel").get("color") == RED


# --- marks ----------------------------------------------------------------------------------------------------------

def shape(decls: dict[str, str]) -> tuple[str, str, str | None]:
    """A mark's (form, fill, border style) from its merged declarations."""
    style = decls.get("border-style") or next(
        (w for w in decls.get("border", "").split() if w in ("solid", "dashed", "dotted")), None)
    round_ = decls.get("border-radius") == "50%"
    turned = "rotate(45deg)" in decls.get("transform", "")
    form = "circle" if round_ else "diamond" if turned else "square"
    filled = decls.get("background", "none") not in ("none", "transparent")
    return form, "filled" if filled else "open", style


FILLED_DOT, RING, DOTTED_RING = ("circle", "filled", "solid"), ("circle", "open", "solid"), ("circle", "open", "dotted")
RED_SQUARE, DASHED_SQUARE, DIAMOND = ("square", "filled", "solid"), ("square", "open", "dashed"), ("diamond", "filled",
                                                                                                  "solid")
# docs/site-redesign.md, "Look A", "Labels": the mark before each label, never colour alone.
LABEL_MARKS = {"DEPARTED": FILLED_DOT, "LANDED": FILLED_DOT, "UPCOMING": RING, "NO NEWS YET": DOTTED_RING,
               "CANCELLED": RED_SQUARE, "UNKNOWN": DASHED_SQUARE, "DELAYED": DIAMOND}
# "The strip": one mark per day, its shape by its label; the key draws the same mark before each count.
STRIP_MARKS = {"DEPARTED": FILLED_DOT, "LANDED": FILLED_DOT, "UPCOMING": RING, "CANCELLED": RED_SQUARE,
               "UNKNOWN": DASHED_SQUARE, "NO NEWS YET": DOTTED_RING}


def kind(label: str) -> str:
    return label.lower().replace(" ", "-")  # as views._kind writes it


def test_every_label_and_strip_kind_is_listed():
    assert set(LABEL_MARKS) == {*words.LABEL_ORDER, "DELAYED"}
    assert set(STRIP_MARKS) == set(words.LABEL_ORDER)


@pytest.mark.parametrize("label", LABEL_MARKS)
def test_every_label_has_its_mark(label):
    """views._labels writes `label l-<kind>`; the mark is drawn before the capitals in the label's own colour, red for
    CANCELLED and grey for UNKNOWN."""
    base = declared((), ".label::before")
    assert base.get("content") == '""' and base.get("border", "").endswith("currentColor")
    mark = base | declared((), f".l-{kind(label)}::before")
    assert shape(mark) == LABEL_MARKS[label]
    colour = declared((), f".l-{kind(label)}").get("color")
    assert colour == {"CANCELLED": RED, "UNKNOWN": "var(--soft)"}.get(label), colour


@pytest.mark.parametrize("label", STRIP_MARKS)
def test_every_strip_mark_and_its_key(label):
    """The strip's `a.s-<kind>` draws its shape on the empty `<i>`; the key's `span.k.s-<kind>` holds words only and
    draws the same shape before them."""
    expected = STRIP_MARKS[label]
    strip = declared((), ".strip i") | declared((), f".s-{kind(label)} i")
    key = declared((), ".k::before") | declared((), f".k.s-{kind(label)}::before")
    assert key.get("content") == '""'
    assert shape(strip) == shape(key) == expected
    if label == "CANCELLED":
        assert strip["background"] == key["background"] == RED
    if label == "UNKNOWN":
        assert strip["border-color"] == key["border-color"] == "var(--soft)"


def test_the_month_over_a_mark_comes_from_its_attribute():
    assert declared((), ".strip .mo::before").get("content") == "attr(data-mo)"


def test_the_day_bars_take_their_colours_from_the_tokens():
    """An SVG shape the sheet does not fill is black, lost on the dark paper: each part of a day's bar is filled from
    the tokens."""
    assert declared((), ".chart .rest").get("fill") == "var(--ink)"
    assert declared((), ".chart .cancelled").get("fill") == RED
    assert declared((), ".chart .unknown").get("fill") == "var(--paper)"
    assert declared((), ".chart .unknown").get("stroke") == "var(--ink)"


# --- type -----------------------------------------------------------------------------------------------------------

PHONE_WIDTH = 390


def applies(media: tuple[str, ...], width: int) -> bool:
    """Whether every at-rule in `media` holds on a screen `width` px wide, in either colour scheme."""
    for at in media:
        if at == DARK:
            continue
        m = re.fullmatch(r"@media \((max|min)-width: (\d+)px\)", at)
        assert m, f"a media query the test does not read: {at}"
        bound = int(m.group(2))
        if (m.group(1) == "max" and width > bound) or (m.group(1) == "min" and width < bound):
            return False
    return True


def applies_on_a_phone(media: tuple[str, ...]) -> bool:
    return applies(media, PHONE_WIDTH)


SIZE = re.compile(r"(?:^|\s)(\d*\.?\d+)(rem|px|em|%)(?=/|\s|$)")
CLAMP = re.compile(r"clamp\(([^)]*)\)")


def length(token: str, width: int) -> float:
    """A rem, px or vw length in px on a screen `width` px wide."""
    m = re.fullmatch(r"(\d*\.?\d+)(rem|px|vw)", token.strip())
    assert m, token
    value, unit = float(m.group(1)), m.group(2)
    return {"rem": value * 16, "px": value, "vw": value * width / 100}[unit]


def font_px(value: str, width: int) -> float | None:
    """The size a `font-size` or `font` value sets on a screen `width` px wide; None for one relative to its parent."""
    m = CLAMP.search(value)
    if m:
        lo, mid, hi = (length(t, width) for t in m.group(1).split(","))
        return min(max(lo, mid), hi)
    m = SIZE.search(value)
    assert m, value
    return None if m.group(2) in ("em", "%") else length(m.group(1) + m.group(2), width)


def test_nothing_on_a_phone_under_13_px():
    """docs/site-redesign.md, "Type": every size that can apply at 390 px is 13 px or more, a size that shrinks with
    the screen included at its floor; a size relative to its parent never shrinks it, and the root keeps the
    browser's 16 px that a rem counts from."""
    assert "font-size" not in declared((), "html") and "font-size" not in declared((), ":root")
    sizes = []
    for at, sel, decls in RULES:
        if not applies_on_a_phone(at) or sel == "@font-face":
            continue
        for prop in ("font-size", "font"):
            if prop in decls:
                sizes.append((sel, decls[prop]))
    assert sizes
    for sel, value in sizes:
        floor = font_px(value, 0)  # a clamp() at its floor
        if floor is None:
            m = SIZE.search(value)
            assert float(m.group(1)) / (100 if m.group(2) == "%" else 1) >= 1, f"{sel}: {value}"
        else:
            assert floor >= 13, f"{sel}: {value}"


def test_the_total_fits_a_phone():
    """docs/site-redesign.md, "On a phone": no sideways scrolling. The total's three figures keep their own line each
    (nowrap), so on a phone they shrink with the screen and the row wraps rather than run past the edge. Measured
    with headless Chrome: "12,345", "234" and "1.7%" fit one line at 360 px with the figures at 36 px."""
    assert declared((), ".stat b").get("white-space") == "nowrap"
    row = declared((PHONE,), ".stats")
    assert (row.get("display"), row.get("flex-wrap")) == ("flex", "wrap")
    figure = declared((PHONE,), ".stat b")["font-size"]
    assert CLAMP.search(figure) and "vw" in figure
    assert font_px(figure, 360) <= 36
    assert font_px(figure, 320) >= 32  # still a figure, not a footnote


def test_tabular_numbers():
    assert declared((), "body").get("font-variant-numeric") == "tabular-nums"
    for at, sel, decls in RULES:
        assert "font-feature-settings" not in decls, sel
        assert decls.get("font-variant-numeric", "tabular-nums") == "tabular-nums", sel


# --- the sheet ------------------------------------------------------------------------------------------------------

def test_the_sheet():
    """docs/site-redesign.md, "The sheet": 1,160 px wide at most, twelve columns with 24 px between them, 40 px side
    gutters, 28 px at 1,040 px and below, 20 px at 760 px and below."""
    light = SCHEMES["light"]
    assert (light.get("--w"), light.get("--gut"), light.get("--gap")) == ("1160px", "40px", "24px")
    assert declared((WIDE,), ":root") == {"--gut": "28px"}
    assert declared((PHONE,), ":root").get("--gut") == "20px"
    edge = "max(var(--gut), calc((100% - var(--w)) / 2))"
    for part in ("main", "footer", ".mast"):
        assert declared((), part).get("padding-left") == declared((), part).get("padding-right") == edge, part
    for grid in (".sec", "#now", ".record"):
        assert declared((), grid).get("grid-template-columns") == "repeat(12, minmax(0, 1fr))", grid
        assert declared((), grid).get("column-gap") == "var(--gap)", grid


def test_no_has_selector():
    """`:has()` is left out: the search label and hint hide with their wrapper (#find), which the script shows."""
    assert not any(":has(" in sel for _, sel, _ in RULES)


def test_hidden_wins():
    """The search wrapper and every prepared line carry `hidden` until the script shows them; a display rule would
    override the attribute, so the attribute's rule wins over all of them, and no other display rule claims as much."""
    assert declared((), "[hidden]").get("display") == "none !important"
    others = [sel for _, sel, decls in RULES if "!important" in decls.get("display", "") and sel != "[hidden]"]
    assert others == []


def test_published_double_spaces_show():
    """Airline names keep the airport's spacing ("ARKIA  ISRAELI  AIRLINES")."""
    assert declared((), ".d").get("white-space") == "pre-wrap"


def test_hebrew_city_is_isolated():
    assert declared((), '[dir="rtl"]').get("unicode-bidi") == "isolate"


def test_a_3_px_focus_outline():
    """docs/site-redesign.md, "Keyboard focus": a 3 px outline in ink on every link, "What changed" and the search
    box, and no rule anywhere thins or removes it."""
    assert declared((), "a:focus-visible").get("outline") == "3px solid var(--ink)"
    assert declared((), "summary:focus-visible").get("outline") == "3px solid var(--ink)"
    assert declared((), "#search:focus-visible").get("outline") == "3px solid var(--ink)"
    for at, sel, decls in RULES:
        for prop in ("outline", "outline-width", "outline-style"):
            if prop in decls:
                assert decls[prop] == "3px solid var(--ink)", (at, sel, prop, decls[prop])


def test_flight_numbers_in_the_table_never_break():
    """Each number is a `.d` span whose own pre-wrap would let "LY 5410" break at its space when the table squeezes
    the column; `pre` keeps the published spacing and stops the break."""
    assert declared((), ".cancellations td:nth-child(2) .d").get("white-space") == "pre"


def test_flight_numbers_on_a_day_page_never_break():
    """The day list's numbers are `.d` spans too: "LY 005" must not split across two lines in its column."""
    assert declared((), ".flights .nums .d").get("white-space") == "pre"


def test_a_long_codeshare_list_wraps_after_its_commas():
    """Only the numbers are kept whole: the flight cell itself sets no nowrap, on any screen, so a long list of
    codeshare numbers wraps after a comma instead of widening the table past a phone's width."""
    cell = [decls for _, sel, decls in RULES if ".cancellations td:nth-child(2)" in parts(sel)]
    assert cell and all(decls.get("white-space") != "nowrap" for decls in cell)


def test_the_cancellations_table_stacks_on_a_phone_and_the_chance_table_does_not():
    """docs/site-redesign.md, "On a phone": each cancellation stacks, its heads hidden, and the page's own "Notice
    given: " shows before the notice there and nowhere else; the sheet prints no column head of its own. The chance
    table ("Your flight is…", "Chance it's cancelled") keeps its two columns at every width."""
    for part in ("", " tbody", " td"):
        assert declared((PHONE,), f".cancellations{part}").get("display") == "block", part
    assert declared((PHONE,), ".cancellations tr").get("display") == "flex"
    assert declared((PHONE,), ".cancellations thead").get("clip-path") == "inset(50%)"
    assert declared((), ".cancellations .pre").get("display") == "none"
    assert declared((PHONE,), ".cancellations .pre").get("display") == "inline"
    printed = [decls["content"] for _, _, decls in RULES if "content" in decls]
    assert not [c for c in printed if "data-label" in c or "Notice" in c]
    stacking = {"display", "position", "clip-path", "content", "float"}
    assert not [(at, sel) for at, sel, decls in RULES if ".fromhere" in sel and stacking & decls.keys()]
    # Nor does any rule a phone reads set the display of a table's parts, by element, outside the cancellations table.
    table_part = re.compile(r"(?:^|[\s>+~])(?:table|thead|tbody|tr|th|td)(?![\w-])")
    for at, sel, decls in RULES:
        if applies_on_a_phone(at) and "display" in decls:
            for part in parts(sel):
                assert not table_part.search(part) or ".cancellations" in part, (at, part)


def test_the_masthead_dot_is_not_read_aloud():
    """The dot between the site's name and "Tel Aviv airport" is drawn by the sheet; its empty alternative text keeps
    a screen reader from reading it."""
    assert declared((), ".where::before").get("content") == '"\\00b7" / ""'


def test_links_are_ink():
    """docs/site-redesign.md, "Look A": links are ink with an underline, inside the soft lines too ("Also sold as",
    the footer)."""
    assert declared((), "a").get("color") == "var(--ink)"
    link = re.compile(r"(?:^|[\s>+~])a(?:[:.\[]|$)")
    for at, sel, decls in RULES:
        for part in parts(sel):
            if link.search(part) and "color" in decls:
                assert decls["color"] == "var(--ink)", (at, part)


def test_the_heavier_weight_words():
    """docs/site-redesign.md, "Type": column heads, "Updated …", "What changed" and "Pick a day" are ordinary words in
    the heavier weight."""
    for sel in ("th", ".updated", "summary", ".days-h"):
        assert declared((), sel).get("font-weight") == "600", sel


def names(part: str) -> tuple[set[str], set[str], set[str]]:
    """The classes, ids and element names a selector needs on a page, its :not(), attributes and pseudo parts aside."""
    part = re.sub(r":not\([^)]*\)", "", part)
    part = re.sub(r"\[[^\]]*\]", "", part)
    part = re.sub(r"::?[\w-]+(?:\([^)]*\))?", "", part)
    return (set(re.findall(r"\.([\w-]+)", part)), set(re.findall(r"#([\w-]+)", part)),
            set(re.findall(r"(?:^|[\s>+~])([a-z][a-z0-9]*)", part)))


@pytest.mark.parametrize("width", [1280, 1040, 390, 360])
def test_find_your_flight_is_the_largest_line_on_the_front_page(width):
    """The plan's Task 9: "Find your flight" is the largest line on the front page's first screen. Every rule whose
    classes, ids and element names all stand on a front page (the views tests' own) counts, wherever on the page
    it falls, so the label outsizes the total's figures too."""
    from test_timeline_views import front  # the front page the views tests build
    page = front()
    on_page = ({c for m in re.finditer(r'class="([^"]*)"', page) for c in m.group(1).split()},
               set(re.findall(r'\bid="([^"]*)"', page)), set(re.findall(r"<([a-z][a-z0-9]*)[\s>/]", page)))
    sizes = {}
    for at, sel, decls in RULES:
        if sel.startswith("@") or not applies(at, width):
            continue
        for part in parts(sel):
            if all(need <= have for need, have in zip(names(part), on_page)):
                for prop in ("font-size", "font"):
                    if prop in decls and font_px(decls[prop], width) is not None:
                        sizes[part] = font_px(decls[prop], width)
    find = sizes.pop(".find-l")
    assert sizes and all(size < find for size in sizes.values()), (find, max(sizes.items(), key=lambda kv: kv[1]))


# --- fonts (Task 7) -------------------------------------------------------------------------------------------------

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
