"""Comprobaciones ligeras sobre la web generada (CI): contraste, raya larga, rutas del repo.

Uso: python scripts/check_site.py [carpeta_de_salida]   (por defecto site/_build)
Sale con código 1 si algo falla.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "src/ensemblitz/site/static/style.css"
EM_DASH = "\u2014"

# (primer plano, fondo, mínimo). 4.5 texto normal, 3.0 elementos no textuales y texto grande.
PAIRS = [
    ("ink", "paper", 4.5),
    ("ink", "surface", 4.5),
    ("ink-2", "paper", 4.5),
    ("ink-2", "surface", 4.5),
    ("ink-3", "paper", 4.5),
    ("ink-3", "surface", 4.5),
    ("on-flag", "flag", 4.5),
    ("flag", "paper", 3.0),  # solo en oscuro, marca sin texto
    ("cell-off", "paper", 1.0),  # decorativa, el valor siempre va en texto
]


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
    return {"claro": light, "oscuro": {**light, **_tokens(dark_block)}}


def check_contrast() -> list[str]:
    errors = []
    for name, toks in themes(CSS.read_text()).items():
        for fg, bg, minimum in PAIRS:
            if name == "claro" and fg == "flag":
                continue
            r = ratio(toks[fg], toks[bg])
            if r < minimum:
                errors.append(f"contraste {name}: {fg} sobre {bg} = {r:.2f} (mínimo {minimum})")
    return errors


def check_output(out: Path) -> list[str]:
    errors = []
    pages = sorted(out.rglob("*.html"))
    if not pages:
        return [f"no hay HTML en {out}"]
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if EM_DASH in text:
            errors.append(f"raya larga en {page.relative_to(out)}")
    for asset in (out / "assets").rglob("*.[jc]s*"):
        if EM_DASH in asset.read_text(encoding="utf-8", errors="ignore"):
            errors.append(f"raya larga en {asset.relative_to(out)}")
    return errors


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site/_build"
    errors = check_contrast() + check_output(out)
    for e in errors:
        print("FALLO:", e)
    if not errors:
        print("check_site: contraste y salida correctos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
