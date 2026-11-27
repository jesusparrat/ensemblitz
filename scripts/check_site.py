"""Lightweight checks on the generated site (CI).

Checks: colour contrast of the design tokens, <=2 font families (no Doto/Arial), zero <13px
text in CSS/SVG, zero pills or eyebrow kickers, no beige/purple palette tokens, em dashes,
language markers on every page, jargon and old widgets on the week pages, bookmaker and exchange
names, half-translated team names, empty filter groups, ET on /en/ (no Madrid), no false closing
labels outside method pages, no duplicate gap text on flagged cards, and reconciled population
counts on method pages.

Usage: python scripts/check_site.py [output_dir]   (default: site/_build)
Exits with code 1 if anything fails.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "src/ensemblitz/site/static/style.css"
EM_DASH = "\u2014"

# (foreground, background, minimum). 4.5 normal text, 3.0 non-text elements and large text.
PAIRS = [
    ("ink", "paper", 4.5),
    ("ink", "surface", 4.5),
    ("ink-2", "paper", 4.5),
    ("ink-2", "surface", 4.5),
    ("ink-3", "paper", 4.5),
    ("ink-3", "surface", 4.5),
    ("on-flag", "flag", 4.5),
    ("flag", "paper", 3.0),  # dark theme only, a mark without text
    ("cell-off", "paper", 1.0),  # decorative; the value is always in text
]

# Words that belong on the method page, never on a week page.
JARGON = {
    "es": [
        "ensemble",
        r"\bpp\b",
        "sin comisión",
        "20.000",
        "simulaciones",
        "cómo leer",
        "marcador típico",
    ],
    "en": [
        "ensemble",
        r"\bpp\b",
        "no vig",
        "no-vig",
        "20,000",
        "simulations",
        "how to read",
        "typical score",
    ],
}
# Raw injury-count sentences ("12 lesionados", "3 injuries") are banned everywhere.
INJURY_COUNT = re.compile(r"\b\d+\s+(lesionad|lesion|injur|baja)", re.I)
# Only the consensus line is shown, never a bookmaker or an exchange.
BOOKS = re.compile(
    r"betfair|matchbook|pinnacle|bet365|bwin|codere|william hill|unibet|draftkings|fanduel|"
    r"betmgm|betway|888sport|marathonbet|sportium|kirolbet|luckia|betsson|1xbet|bovada",
    re.I,
)
# Spanish team names that must never appear (official English names are used in both languages).
SPANISH_TEAMS = re.compile(
    r"cardenales|halcones|cuervos|\bosos\b|vaqueros|delfines|\bleones\b|potros|jaguares|jefes|"
    r"cargadores|carneros|vikingos|patriotas|\bsantos\b|gigantes|nueva york|nueva orleans|"
    r"los ángeles|filadelfia|nueva inglaterra|bahía de tampa|comandantes|\bacereros\b",
    re.I,
)
# Closing-line wording is only valid on historical method pages (2018-2025 closing backtest).
CLOSING_WORD = re.compile(r"\b(cierre|closing)\b", re.I)
METHOD_PAGES = frozenset({"metodo.html", "en/method.html"})


class _VisibleTextParser(HTMLParser):
    """Extract only visible user-facing text (skipping scripts, styles, comments, and attributes)."""

    SKIP_TAGS = frozenset({"script", "style", "noscript", "title"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        # Ignore HTML comments so metadata/comments never trigger visible-text guards.
        return


def _lum(hexcol: str) -> float:
    h = hexcol.lstrip("#")
    ch = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _tokens(block: str) -> dict[str, str]:
    return {k: v.upper() for k, v in re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", block)}


def themes(css: str) -> dict[str, dict[str, str]]:
    light = _tokens(re.search(r":root\s*\{(.*?)\}", css, re.S).group(1))
    dark_block = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S).group(1)
    return {"light": light, "dark": {**light, **_tokens(dark_block)}}


def check_contrast() -> list[str]:
    errors = []
    for name, toks in themes(CSS.read_text()).items():
        for fg, bg, minimum in PAIRS:
            if name == "light" and fg == "flag":
                continue
            r = ratio(toks[fg], toks[bg])
            if r < minimum:
                errors.append(f"contrast {name}: {fg} on {bg} = {r:.2f} (minimum {minimum})")
    return errors


GENERIC_FONTS = frozenset(
    {
        "inherit",
        "sans-serif",
        "serif",
        "monospace",
        "system-ui",
        "-apple-system",
        "ui-monospace",
        "ui-sans-serif",
        "segoe ui",
        "menlo",
    }
)


def _rgb(hexcol: str) -> tuple[int, int, int]:
    h = hexcol.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def check_css_rules(css_text: str | None = None) -> list[str]:
    """Enforce PR 4 hard rules on CSS: <=2 font families, >=13px, no pills, no beige/purple."""
    css = CSS.read_text() if css_text is None else css_text
    errors: list[str] = []

    # 1. Max 2 custom font families; ban Doto and Arial everywhere.
    custom_fonts: set[str] = set()
    for decl in re.findall(r"font-family\s*:\s*([^;}{]+)", css, re.I):
        for raw in decl.split(","):
            name = raw.strip().strip("\"'")
            if not name or name.startswith("var("):
                continue
            low = name.lower()
            if low in ("doto", "arial"):
                errors.append(f"css: forbidden font family {name!r}")
            if low not in GENERIC_FONTS:
                custom_fonts.add(name)
    if len(custom_fonts) > 2:
        errors.append(f"css: more than 2 font families ({sorted(custom_fonts)})")

    # 2. Zero font sizes below 13px in CSS.
    for m in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", css, re.I):
        sz = float(m.group(1))
        if sz < 13.0:
            errors.append(f"css: font-size below 13px ({m.group(0)})")
    for m in re.finditer(r"font\s*:[^;}{]*?\b(\d+(?:\.\d+)?)px", css, re.I):
        sz = float(m.group(1))
        if sz < 13.0:
            errors.append(f"css: font shorthand below 13px ({m.group(0).strip()})")

    # 3. No pills and no legacy .chipf badge boxes.
    if re.search(r"\.chipf\b", css):
        errors.append("css: legacy .chipf badge selector still present")
    for m in re.finditer(r"border-radius\s*:\s*(\d+(?:\.\d+)?)(px|%)", css, re.I):
        val, unit = float(m.group(1)), m.group(2)
        if (unit == "px" and val >= 20) or (unit == "%" and val >= 50):
            errors.append(f"css: pill border-radius forbidden ({m.group(0)})")

    # 4. No beige or purple tokens in light/dark palettes.
    for mode, toks in themes(css).items():
        for name, hx in toks.items():
            if name == "flag":
                continue
            r, g, b = _rgb(hx)
            luma = _lum(hx)
            # Warm beige: light-to-mid neutral shifted clearly yellow/brown (R > B and G > B).
            if luma > 0.35 and (r - b) >= 6 and (g - b) >= 4:
                errors.append(f"palette {mode}: beige/warm token {name}={hx}")
            # Purple/violet: both red and blue clearly elevated above green.
            if (b - g) >= 10 and (r - g) >= 6:
                errors.append(f"palette {mode}: purple token {name}={hx}")
    return errors


def _strip_tags(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return " ".join(parser.parts)


def _lang_of(rel: Path) -> str:
    return "en" if rel.parts[0] == "en" else "es"


def check_parity(out: Path) -> list[str]:
    """Every Spanish page has its English twin."""
    from ensemblitz.site.build import ROUTES

    errors = []
    pages = {p.relative_to(out).as_posix() for p in out.rglob("*.html")}
    for kind, es_tpl in ROUTES["es"].items():
        pat = re.compile("^" + re.escape(es_tpl).replace(r"\{\}", "(.+)") + "$")
        for rel in sorted(pages):
            m = pat.match(rel)
            if m:
                twin = ROUTES["en"][kind].format(*m.groups())
                if twin not in pages:
                    errors.append(f"{rel}: missing English twin {twin}")
    return errors


def check_output(out: Path) -> list[str]:
    errors = []
    pages = sorted(out.rglob("*.html"))
    if not pages:
        return [f"no HTML in {out}"]
    for page in pages:
        rel = page.relative_to(out)
        rel_posix = rel.as_posix()
        text = page.read_text(encoding="utf-8")
        lang = _lang_of(rel)
        if EM_DASH in text:
            errors.append(f"em dash in {rel}")
        m = re.search(r'<html[^>]*\blang="([a-z]{2})"', text)
        if not m or m.group(1) != lang:
            errors.append(f"{rel}: <html lang> should be {lang!r}")
        alts = set(re.findall(r'rel="alternate" hreflang="([a-z-]+)"', text))
        if not {"es", "en"} <= alts:
            errors.append(f"{rel}: missing hreflang alternates for es and en")
        if 'class="lang"' not in text:
            errors.append(f"{rel}: missing language switch")
        visible = _strip_tags(text)
        if INJURY_COUNT.search(visible):
            errors.append(f"{rel}: raw injury-count sentence")
        if BOOKS.search(visible):
            errors.append(f"{rel}: bookmaker or exchange name ({BOOKS.search(visible).group(0)})")
        if SPANISH_TEAMS.search(visible):
            errors.append(f"{rel}: Spanish team name ({SPANISH_TEAMS.search(visible).group(0)})")
        # C6: English pages must use ET, never Madrid time.
        if lang == "en":
            if re.search(r"\bmadrid\b", visible, re.I):
                errors.append(f"{rel}: Madrid timezone text on English page")
            if re.search(r"\b\d{1,2}:\d{2}\b", visible) and not re.search(r"\bET\b", visible):
                errors.append(f"{rel}: time shown on English page without ET label")
        # C7: Closing-line wording is forbidden in visible text outside historical method pages.
        if rel_posix not in METHOD_PAGES and CLOSING_WORD.search(visible):
            hit = CLOSING_WORD.search(visible).group(0)
            errors.append(f"{rel}: closing-line wording outside method page ({hit})")
        # C2: Method pages mentioning 2141 must reconcile it with 2133 decided games.
        if rel_posix in METHOD_PAGES:
            has_2141 = bool(re.search(r"\b2[.,]?141\b", visible))
            has_2133 = bool(re.search(r"\b2[.,]?133\b", visible))
            if has_2141 and not has_2133:
                errors.append(f"{rel}: mentions 2141 without reconciling 2133 decided games")
        # PR 4: No eyebrow kickers (<small> inside <h1>), no legacy .chipf, no <13px inline SVG.
        if any(
            re.search(r"<small\b", hm.group(1), re.I)
            for hm in re.finditer(r"<h1\b[^>]*>(.*?)</h1>", text, re.S | re.I)
        ):
            errors.append(f"{rel}: eyebrow kicker (<small> inside <h1>) forbidden")
        if 'class="chipf"' in text:
            errors.append(f"{rel}: legacy .chipf badge class still present")
        for m_svg in re.finditer(r'font-size\s*=\s*"(\d+(?:\.\d+)?)"', text, re.I):
            if float(m_svg.group(1)) < 13.0:
                errors.append(f"{rel}: inline SVG font-size below 13px ({m_svg.group(0)})")
        # C15: Flagged cards must not repeat the difference in parentheses next to the signal bar.
        for mkt in re.finditer(r'<div class="mkt"[^>]*>(.*?)</div>', text, re.S):
            if 'class="sig"' in mkt.group(1):
                mkt_vis = _strip_tags(mkt.group(1))
                if re.search(r"\((nosotros|us)\s", mkt_vis, re.I):
                    errors.append(f"{rel}: duplicate market gap on flagged card")
        for grp in re.finditer(r'<div class="chips"[^>]*>(.*?)</div>', text, re.S):
            if "<button" not in grp.group(1):
                errors.append(f"{rel}: empty filter group")
        if "pbar" in text and re.search(r'class="(cells|cell)\b', text):
            errors.append(f"{rel}: segmented bar still present")
        is_week = rel.name == "index.html" or rel.parts[-2:-1] in (("jornada",), ("week",))
        if is_week:
            low = visible.lower()
            for pat in JARGON[lang]:
                if re.search(pat, low):
                    errors.append(f"{rel}: jargon on a week page ({pat})")
    for asset in (out / "assets").rglob("*.[jc]s*"):
        if EM_DASH in asset.read_text(encoding="utf-8", errors="ignore"):
            errors.append(f"em dash in {asset.relative_to(out)}")
    return errors


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site/_build"
    errors = check_contrast() + check_css_rules() + check_output(out) + check_parity(out)
    for e in errors:
        print("FAIL:", e)
    if not errors:
        print("check_site: contrast and output are correct")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
