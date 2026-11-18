"""Lightweight checks on the generated site (CI).

Checks: colour contrast of the design tokens, em dashes, language markers on every page,
jargon and old widgets on the week pages, bookmaker and exchange names, half-translated team
names and empty filter groups.

Usage: python scripts/check_site.py [output_dir]   (default: site/_build)
Exits with code 1 if anything fails.
"""

from __future__ import annotations

import re
import sys
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


def _strip_tags(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


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
        text = page.read_text(encoding="utf-8")
        lang = _lang_of(rel)
        if EM_DASH in text:
            errors.append(f"em dash in {rel}")
        m = re.search(r"<html[^>]*\blang=\"([a-z]{2})\"", text)
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
    errors = check_contrast() + check_output(out) + check_parity(out)
    for e in errors:
        print("FAIL:", e)
    if not errors:
        print("check_site: contrast and output are correct")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
