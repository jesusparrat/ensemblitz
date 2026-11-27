"""Tests for PR 6c: Open Graph PNG generation, SEO metadata, sitemap/robots, and opt-in analytics."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from matplotlib.ft2font import FT2Font
from PIL import Image

from ensemblitz.site import build as B
from ensemblitz.site import og
from test_site import _game, _repo


def _extract_meta(html: str, attr: str, name: str) -> str | None:
    m = re.search(rf'<meta\s+{attr}="{re.escape(name)}"\s+content="([^"]*)"', html)
    return m.group(1) if m else None


def _extract_csp(html: str) -> str:
    m = re.search(r'<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"', html)
    assert m is not None, "missing CSP meta tag"
    return m.group(1)


def test_font_resolution_reports_honestly_without_faking_woff2() -> None:
    sel = og.resolve_fonts()
    for path in (sel.display_regular, sel.display_bold, sel.mono_regular, sel.mono_bold):
        assert path.is_file(), path
        assert FT2Font(str(path)).family_name
    # Bundled static/fonts/ are .woff2 only (not loadable by matplotlib FT2Font without brotli).
    assert sel.woff2_loadable is False
    assert sel.used_web_fonts is False
    assert sel.display_family == "DejaVu Sans"
    assert sel.mono_family == "DejaVu Sans Mono"
    assert sel.fallback_reason is not None and ".woff2" in sel.fallback_reason


def test_og_cards_exact_1200x630_tokens_and_deterministic_bytes(tmp_path: Path) -> None:
    root = _repo(tmp_path, with_odds=True, with_backtest=False)
    out1 = B.build_site(root=root, out=tmp_path / "out1")
    out2 = B.build_site(root=root, out=tmp_path / "out2")

    expected_cards = [
        "og/home-es.png",
        "og/home-en.png",
        "og/week-2026-11-es.png",
        "og/week-2026-11-en.png",
    ]
    for rel in expected_cards:
        p1, p2 = out1 / rel, out2 / rel
        assert p1.is_file(), rel
        assert p1.read_bytes() == p2.read_bytes(), f"non-deterministic PNG bytes: {rel}"
        with Image.open(p1) as img:
            assert img.format == "PNG"
            assert img.size == (1200, 630), (rel, img.size)
            rgb = img.convert("RGB")
            colors = {c for _, c in rgb.getcolors(maxcolors=2_000_000) or []}
            # DESIGN.md tokens: paper #F3F4F6, surface #FFFFFF, ink #111318, flag #FFD60A
            assert (243, 244, 246) in colors
            assert (255, 255, 255) in colors
            assert (17, 19, 24) in colors
            assert (255, 214, 10) in colors


def test_og_cards_scale_to_18_regular_plus_postseason_weeks(tmp_path: Path) -> None:
    root = tmp_path / "season19"
    (root / "predictions" / "2026").mkdir(parents=True)
    for wk in range(1, 20):  # 18 regular-season weeks + Wild Card week 19
        g = _game(f"2026_{wk:02d}_IND_HOU", "HOU", "IND", f"2099-09-{wk:02d}T18:00:00Z")
        g["week"] = wk
        (root / f"predictions/2026/week{wk:02d}.json").write_text(
            json.dumps(
                {
                    "season": 2026,
                    "week": wk,
                    "generated_at": "2026-09-01T12:00:00Z",
                    "games": [g],
                }
            )
        )

    out = B.build_site(root=root, out=tmp_path / "site")
    for lang in ("es", "en"):
        home_png = out / f"og/home-{lang}.png"
        assert home_png.is_file()
        with Image.open(home_png) as img:
            assert img.size == (1200, 630)
        for wk in range(1, 20):
            wk_png = out / f"og/week-2026-{wk:02d}-{lang}.png"
            assert wk_png.is_file(), wk_png.name
            with Image.open(wk_png) as img:
                assert img.size == (1200, 630), (wk_png.name, img.size)

    wk18_es = (out / "jornada/18.html").read_text(encoding="utf-8")
    wk19_en = (out / "en/week/19.html").read_text(encoding="utf-8")
    assert _extract_meta(wk18_es, "property", "og:image") == (
        "https://jesusparrat.github.io/ensemblitz/og/week-2026-18-es.png"
    )
    assert _extract_meta(wk19_en, "property", "og:image") == (
        "https://jesusparrat.github.io/ensemblitz/og/week-2026-19-en.png"
    )


def test_empty_site_generates_home_og_cards_sitemap_and_robots(tmp_path: Path) -> None:
    out = B.build_site(root=tmp_path, out=tmp_path / "out")
    for lang in ("es", "en"):
        p = out / f"og/home-{lang}.png"
        assert p.is_file()
        with Image.open(p) as img:
            assert img.size == (1200, 630)
    assert (out / "sitemap.xml").is_file()
    assert (out / "robots.txt").is_file()
    home = (out / "index.html").read_text(encoding="utf-8")
    assert (
        _extract_meta(home, "property", "og:image")
        == "https://jesusparrat.github.io/ensemblitz/og/home-es.png"
    )


def test_seo_metadata_canonical_hreflang_sitemap_robots_and_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SITE_BASE_URL", "https://example.org/nfl///")
    root = _repo(tmp_path, with_odds=True, with_backtest=False)
    out = B.build_site(root=root, out=tmp_path / "out")
    base = "https://example.org/nfl"

    expected_urls: dict[str, tuple[str, str]] = {
        "index.html": (f"{base}/", f"{base}/og/home-es.png"),
        "en/index.html": (f"{base}/en/", f"{base}/og/home-en.png"),
        "jornada/11.html": (f"{base}/jornada/11.html", f"{base}/og/week-2026-11-es.png"),
        "en/week/11.html": (f"{base}/en/week/11.html", f"{base}/og/week-2026-11-en.png"),
        "partido/2026_11_IND_HOU.html": (
            f"{base}/partido/2026_11_IND_HOU.html",
            f"{base}/og/week-2026-11-es.png",
        ),
        "en/game/2026_11_IND_HOU.html": (
            f"{base}/en/game/2026_11_IND_HOU.html",
            f"{base}/og/week-2026-11-en.png",
        ),
        "historial.html": (f"{base}/historial.html", f"{base}/og/home-es.png"),
        "en/history.html": (f"{base}/en/history.html", f"{base}/og/home-en.png"),
        "metodo.html": (f"{base}/metodo.html", f"{base}/og/home-es.png"),
        "en/method.html": (f"{base}/en/method.html", f"{base}/og/home-en.png"),
    }

    for rel, (canon, og_img) in expected_urls.items():
        html = (out / rel).read_text(encoding="utf-8")
        assert f'<link rel="canonical" href="{canon}">' in html, rel
        assert re.search(
            r'<link rel="alternate" hreflang="es" href="https://example\.org/nfl/', html
        )
        assert re.search(
            r'<link rel="alternate" hreflang="en" href="https://example\.org/nfl/', html
        )
        assert re.search(
            r'<link rel="alternate" hreflang="x-default" href="https://example\.org/nfl/', html
        )
        assert _extract_meta(html, "property", "og:type") == "website"
        assert _extract_meta(html, "property", "og:url") == canon
        assert _extract_meta(html, "property", "og:image") == og_img
        assert _extract_meta(html, "property", "og:image:width") == "1200"
        assert _extract_meta(html, "property", "og:image:height") == "630"
        assert _extract_meta(html, "property", "og:title")
        assert _extract_meta(html, "property", "og:description")
        assert _extract_meta(html, "name", "twitter:card") == "summary_large_image"
        assert _extract_meta(html, "name", "twitter:image") == og_img
        assert "\u2014" not in html, rel

    # Validate sitemap.xml parses cleanly and lists every rendered HTML page with absolute URLs.
    sitemap_text = (out / "sitemap.xml").read_text(encoding="utf-8")
    tree = ET.fromstring(sitemap_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = {el.text for el in tree.findall("sm:url/sm:loc", ns)}
    all_html = list(out.rglob("*.html"))
    assert len(locs) == len(all_html)
    for canon, _ in expected_urls.values():
        assert canon in locs

    # Validate robots.txt points to the absolute sitemap URL.
    robots = (out / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *" in robots
    assert "Allow: /" in robots
    assert f"Sitemap: {base}/sitemap.xml" in robots


@pytest.mark.parametrize("bad_url", ["javascript:alert(1)", "/relative/path", "ftp://example.org"])
def test_invalid_site_base_url_is_rejected(bad_url: str) -> None:
    with pytest.raises(ValueError, match="SITE_BASE_URL"):
        B.resolve_base_url(bad_url)


def test_analytics_disabled_by_default_zero_script_and_strict_csp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ENSEMBLITZ_GOATCOUNTER_CODE", raising=False)
    root = _repo(tmp_path, with_odds=False, with_backtest=False)
    out = B.build_site(root=root, out=tmp_path / "out")

    for page in out.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        csp = _extract_csp(html)
        assert "&#39;" not in csp, page.name
        assert "script-src 'self';" in csp, page.name
        assert "connect-src 'none';" in csp, page.name
        assert "gc.zgo.at" not in html, page.name
        assert "goatcounter.com" not in html, page.name

    # Method page documents disabled state and Safeguard H privacy notice honestly.
    meth_es = (out / "metodo.html").read_text(encoding="utf-8")
    meth_en = (out / "en/method.html").read_text(encoding="utf-8")
    assert "analítica externa está desactivada" in meth_es
    assert "No usar cookies no equivale a estar exento de obligaciones de privacidad" in meth_es
    assert "External analytics is disabled" in meth_en
    assert "Using no cookies does not mean zero privacy" in meth_en


def test_analytics_enabled_injects_exact_script_and_scoped_csp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENSEMBLITZ_GOATCOUNTER_CODE", "ensemblitz-nfl")
    root = _repo(tmp_path, with_odds=False, with_backtest=False)
    out = B.build_site(root=root, out=tmp_path / "out")

    expected_script = (
        '<script data-goatcounter="https://ensemblitz-nfl.goatcounter.com/count" '
        'async src="https://gc.zgo.at/count.js"></script>'
    )
    for page in out.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert expected_script in html, page.name
        csp = _extract_csp(html)
        assert "&#39;" not in csp, page.name
        assert "script-src 'self' https://gc.zgo.at;" in csp, page.name
        assert "connect-src https://ensemblitz-nfl.goatcounter.com;" in csp, page.name
        assert "*" not in csp, page.name

    meth_es = (out / "metodo.html").read_text(encoding="utf-8")
    meth_en = (out / "en/method.html").read_text(encoding="utf-8")
    assert "ensemblitz-nfl.goatcounter.com" in meth_es
    assert "No usar cookies no equivale a estar exento de obligaciones de privacidad" in meth_es
    assert "ensemblitz-nfl.goatcounter.com" in meth_en
    assert "Using no cookies does not mean zero privacy" in meth_en


@pytest.mark.parametrize(
    "bad_code",
    ["UpperCase", "bad_underscore", "has space", "foo/bar", "a.b", "x;script-src *", "a'b"],
)
def test_analytics_rejects_invalid_goatcounter_codes(bad_code: str) -> None:
    with pytest.raises(ValueError, match="ENSEMBLITZ_GOATCOUNTER_CODE"):
        B.resolve_goatcounter_code(bad_code)


def test_pages_workflow_wires_optional_goatcounter_var() -> None:
    wf = (Path(__file__).resolve().parents[1] / ".github/workflows/pages.yml").read_text(
        encoding="utf-8"
    )
    assert "ENSEMBLITZ_GOATCOUNTER_CODE: ${{ vars.GOATCOUNTER_CODE }}" in wf
