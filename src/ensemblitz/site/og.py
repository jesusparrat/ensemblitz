"""Static Open Graph (1200x630) PNG card generator using matplotlib.

Explicit scope (Safeguard G):
- Generates one card per language for the homepage: ``og/home-es.png`` and ``og/home-en.png``.
- Generates one card per language for every published weekly page:
  ``og/week-<season>-<ww>-es.png`` and ``og/week-<season>-<ww>-en.png`` (for any number of
  regular-season and postseason weeks; no hard-coded week cap).
- Game pages fall back to their week card; Record and Method pages fall back to the homepage card.

Typography note (Safeguard G):
- The site's self-hosted web fonts in ``static/fonts/`` are ``.woff2`` files. Matplotlib's FreeType
  engine cannot open ``.woff2`` directly, and ``brotli`` is not in ``uv.lock`` (zero new
  dependencies). ``resolve_fonts()`` probes any local ``.ttf``/``.otf`` files first via
  ``FT2Font``; when none are loadable, it deterministically falls back to matplotlib's bundled
  ``DejaVu Sans`` and ``DejaVu Sans Mono`` TrueType files and reports that truthfully.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ft2font import FT2Font
from matplotlib.patches import Rectangle

from ensemblitz.site.i18n import Lang

OG_WIDTH = 1200
OG_HEIGHT = 630
OG_DPI = 100

# DESIGN.md light-mode palette tokens (3 neutrals + 1 yellow signal accent).
PAPER = "#F3F4F6"
SURFACE = "#FFFFFF"
INK = "#111318"
INK_2 = "#4B5260"
INK_3 = "#5C6473"
RULE = "#D4D8DF"
CELL_OFF = "#CFD5DE"
FLAG = "#FFD60A"

STATIC_FONTS_DIR = Path(__file__).parent / "static" / "fonts"


@dataclass(frozen=True)
class FontSelection:
    """Verified TrueType/OpenType fonts actually rendered into OG PNGs."""

    display_family: str
    mono_family: str
    display_regular: Path
    display_bold: Path
    mono_regular: Path
    mono_bold: Path
    used_web_fonts: bool
    woff2_loadable: bool
    fallback_reason: str | None


def _can_load_ft2(path: Path) -> str | None:
    """Return the FreeType family name if matplotlib's FT2Font can open ``path``, else None."""
    if not path.is_file():
        return None
    try:
        return FT2Font(str(path)).family_name
    except Exception:
        return None


@lru_cache(maxsize=1)
def resolve_fonts() -> FontSelection:
    """Verify loadable font files for matplotlib without faking unavailable web fonts."""
    woff2_files = sorted(STATIC_FONTS_DIR.glob("*.woff2")) if STATIC_FONTS_DIR.exists() else []
    woff2_loadable = any(_can_load_ft2(p) is not None for p in woff2_files)

    # Check if local TTF/OTF copies of Archivo and IBM Plex Mono exist and load cleanly.
    local_ttfs = (
        sorted(list(STATIC_FONTS_DIR.glob("*.ttf")) + list(STATIC_FONTS_DIR.glob("*.otf")))
        if STATIC_FONTS_DIR.exists()
        else []
    )
    archivo_reg = next(
        (p for p in local_ttfs if "archivo" in p.name.lower() and _can_load_ft2(p)), None
    )
    archivo_bold = next(
        (
            p
            for p in local_ttfs
            if "archivo" in p.name.lower() and "bold" in p.name.lower() and _can_load_ft2(p)
        ),
        archivo_reg,
    )
    plex_reg = next(
        (p for p in local_ttfs if "ibm-plex-mono" in p.name.lower() and _can_load_ft2(p)), None
    )
    plex_bold = next(
        (
            p
            for p in local_ttfs
            if "ibm-plex-mono" in p.name.lower()
            and ("600" in p.name.lower() or "bold" in p.name.lower())
            and _can_load_ft2(p)
        ),
        plex_reg,
    )
    if archivo_reg and archivo_bold and plex_reg and plex_bold:
        disp_fam = _can_load_ft2(archivo_reg) or "Archivo"
        mono_fam = _can_load_ft2(plex_reg) or "IBM Plex Mono"
        return FontSelection(
            display_family=disp_fam,
            mono_family=mono_fam,
            display_regular=archivo_reg,
            display_bold=archivo_bold,
            mono_regular=plex_reg,
            mono_bold=plex_bold,
            used_web_fonts=True,
            woff2_loadable=woff2_loadable,
            fallback_reason=None,
        )

    # Deterministic fallback: matplotlib's own bundled TrueType fonts (identical across OS/CI).
    mpl_ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    disp_reg = mpl_ttf / "DejaVuSans.ttf"
    disp_bold = mpl_ttf / "DejaVuSans-Bold.ttf"
    mono_reg = mpl_ttf / "DejaVuSansMono.ttf"
    mono_bold = mpl_ttf / "DejaVuSansMono-Bold.ttf"
    for p in (disp_reg, disp_bold, mono_reg, mono_bold):
        if _can_load_ft2(p) is None:
            raise RuntimeError(f"matplotlib bundled font missing or unreadable: {p}")

    return FontSelection(
        display_family="DejaVu Sans",
        mono_family="DejaVu Sans Mono",
        display_regular=disp_reg,
        display_bold=disp_bold,
        mono_regular=mono_reg,
        mono_bold=mono_bold,
        used_web_fonts=False,
        woff2_loadable=woff2_loadable,
        fallback_reason=(
            "Bundled web fonts in static/fonts/ are .woff2 only, which matplotlib FreeType "
            "cannot open directly without brotli; using matplotlib bundled DejaVu Sans and "
            "DejaVu Sans Mono."
        ),
    )


def home_card_rel(lang: str) -> str:
    """Relative output path for the homepage OG PNG."""
    return f"og/home-{lang}.png"


def week_card_rel(season: int, week: int, lang: str) -> str:
    """Relative output path for a published weekly page OG PNG."""
    return f"og/week-{season}-{week:02d}-{lang}.png"


def _featured_games(games: list[dict], limit: int = 3) -> list[dict]:
    """Select up to ``limit`` notable games deterministically: flagged gaps first, then confidence."""
    ordered = sorted(
        games,
        key=lambda g: (
            0 if g.get("flag") else 1,
            -abs(g.get("diff") or 0),
            -float(g.get("p_win") or 0.5),
            str(g.get("id") or ""),
        ),
    )
    return ordered[:limit]


def _draw_brand_mark(ax, x0: float, y0: float, scale: float = 1.0) -> None:
    """Draw the 5-bar ensemblitz mark (4 ink bars + 1 tall yellow signal bar)."""
    # Coordinates mirror base.html SVG viewBox="0 0 34 22".
    bars = [
        (0, 0, 5, 12, INK),
        (7, 0, 5, 12, INK),
        (14, 0, 5, 12, INK),
        (21, 0, 5, 22, FLAG),
        (28, 0, 5, 12, INK),
    ]
    for bx, by, bw, bh, color in bars:
        ax.add_patch(
            Rectangle(
                (x0 + bx * scale, y0 + by * scale),
                bw * scale,
                bh * scale,
                facecolor=color,
                edgecolor="none",
            )
        )


def _render_card(
    dest: Path,
    *,
    title: str,
    subtitle: str,
    header_right: str,
    games: list[dict],
    L: Lang,
    flag_pp: int,
    domain_label: str,
) -> Path:
    """Render one deterministic 1200x630 OG card PNG following DESIGN.md tokens."""
    fonts = resolve_fonts()
    fp_disp_bold = FontProperties(fname=str(fonts.display_bold))
    fp_disp_reg = FontProperties(fname=str(fonts.display_regular))
    fp_mono_bold = FontProperties(fname=str(fonts.mono_bold))
    fp_mono_reg = FontProperties(fname=str(fonts.mono_regular))

    fig = Figure(figsize=(OG_WIDTH / OG_DPI, OG_HEIGHT / OG_DPI), dpi=OG_DPI, facecolor=PAPER)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0, OG_WIDTH)
    ax.set_ylim(0, OG_HEIGHT)
    ax.axis("off")

    # Background canvas (--paper).
    ax.add_patch(Rectangle((0, 0), OG_WIDTH, OG_HEIGHT, facecolor=PAPER, edgecolor="none"))

    # Full-bleed top hero band (--surface) with 1px bottom --ink rule.
    band_bottom = 390
    ax.add_patch(
        Rectangle(
            (0, band_bottom), OG_WIDTH, OG_HEIGHT - band_bottom, facecolor=SURFACE, edgecolor="none"
        )
    )
    ax.add_patch(Rectangle((0, band_bottom), OG_WIDTH, 2, facecolor=INK, edgecolor="none"))

    # Brand mark + wordmark in top-left.
    pad_x = 64
    _draw_brand_mark(ax, pad_x, 558, scale=1.35)
    ax.text(
        pad_x + 56,
        558,
        "ensemblitz",
        fontproperties=fp_disp_bold,
        fontsize=24,
        color=INK,
        va="bottom",
        ha="left",
    )

    # Top-right season / metadata readout.
    ax.text(
        OG_WIDTH - pad_x,
        562,
        header_right,
        fontproperties=fp_mono_bold,
        fontsize=15,
        color=INK_2,
        va="bottom",
        ha="right",
    )

    # Main headline + subtitle inside the white hero band (no eyebrow kicker above title).
    title_size = 44 if len(title) > 12 else 54
    ax.text(
        pad_x,
        466,
        title,
        fontproperties=fp_disp_bold,
        fontsize=title_size,
        color=INK,
        va="baseline",
        ha="left",
    )
    ax.text(
        pad_x,
        420,
        subtitle,
        fontproperties=fp_disp_reg,
        fontsize=21,
        color=INK_2,
        va="baseline",
        ha="left",
    )

    # Right side of hero band: numeric summary counters (games & flagged disagreements).
    n_games = len(games)
    flagged = [g for g in games if g.get("flag")]
    n_flags = len(flagged)
    if n_games > 0:
        # Games counter block.
        stat_x1 = 740
        ax.text(
            stat_x1,
            476,
            f"{n_games}",
            fontproperties=fp_mono_bold,
            fontsize=46,
            color=INK,
            va="baseline",
            ha="left",
        )
        ax.text(
            stat_x1,
            436,
            L.text("og.games_label"),
            fontproperties=fp_disp_reg,
            fontsize=14,
            color=INK_2,
            va="baseline",
            ha="left",
        )

        # Market disagreement counter with 4px left vertical yellow signal bar (never yellow text).
        stat_x2 = 910
        if n_flags > 0:
            ax.add_patch(Rectangle((stat_x2 - 16, 430), 6, 86, facecolor=FLAG, edgecolor="none"))
        else:
            ax.add_patch(Rectangle((stat_x2 - 16, 430), 2, 86, facecolor=RULE, edgecolor="none"))
        ax.text(
            stat_x2,
            476,
            f"{n_flags:02d}",
            fontproperties=fp_mono_bold,
            fontsize=46,
            color=INK,
            va="baseline",
            ha="left",
        )
        ax.text(
            stat_x2,
            436,
            L.text("og.flags_label", n=flag_pp),
            fontproperties=fp_disp_reg,
            fontsize=14,
            color=INK_2,
            va="baseline",
            ha="left",
        )

    # Middle body on --paper: up to 3 featured matchups in crisp rows.
    featured = _featured_games(games, limit=3)
    if featured:
        ax.text(
            pad_x,
            344,
            L.text("og.featured_label"),
            fontproperties=fp_mono_bold,
            fontsize=13,
            color=INK_3,
            va="baseline",
            ha="left",
        )
        row_h = 68
        row_gap = 12
        top_y = 326
        row_w = OG_WIDTH - 2 * pad_x
        for idx, g in enumerate(featured):
            ry = top_y - (idx + 1) * row_h - idx * row_gap
            is_flag = bool(g.get("flag"))
            bg = SURFACE if is_flag else PAPER
            ax.add_patch(
                Rectangle((pad_x, ry), row_w, row_h, facecolor=bg, edgecolor=RULE, linewidth=1)
            )
            if is_flag:
                ax.add_patch(Rectangle((pad_x, ry), 6, row_h, facecolor=FLAG, edgecolor="none"))

            matchup_txt = f"{g['away']} {L.text('card.at')} {g['home']}"
            ax.text(
                pad_x + 22,
                ry + row_h / 2,
                matchup_txt,
                fontproperties=fp_disp_bold,
                fontsize=24,
                color=INK,
                va="center",
                ha="left",
            )

            # Winner and win probability in monospace.
            win_txt = f"{L.text('card.wins', team=g['fav'])}  {L.pct(g['p_win'])}"
            ax.text(
                pad_x + 360,
                ry + row_h / 2,
                win_txt,
                fontproperties=fp_mono_bold,
                fontsize=20,
                color=INK,
                va="center",
                ha="left",
            )

            # Continuous probability bar (DESIGN.md: --cell-off track, --ink fill, 50% tick).
            bar_x = pad_x + 650
            bar_w = 150
            bar_h = 10
            bar_y = ry + (row_h - bar_h) / 2
            ax.add_patch(
                Rectangle((bar_x, bar_y), bar_w, bar_h, facecolor=CELL_OFF, edgecolor="none")
            )
            fill_w = max(0.0, min(1.0, float(g["p_win"]))) * bar_w
            ax.add_patch(Rectangle((bar_x, bar_y), fill_w, bar_h, facecolor=INK, edgecolor="none"))
            ax.add_patch(
                Rectangle(
                    (bar_x + bar_w * 0.5, bar_y - 4),
                    1.5,
                    bar_h + 8,
                    facecolor=INK_3,
                    edgecolor="none",
                )
            )

            # Positive winning margin readout on right.
            margin_txt = (
                L.fav(g["home"], g["away"], g["margin"]) if g.get("margin_ok") else L.text("even")
            )
            ax.text(
                OG_WIDTH - pad_x - 20,
                ry + row_h / 2,
                margin_txt,
                fontproperties=fp_mono_reg,
                fontsize=18,
                color=INK_2,
                va="center",
                ha="right",
            )
    else:
        # Empty state card (no published predictions yet).
        ax.add_patch(
            Rectangle((pad_x, 150), OG_WIDTH - 2 * pad_x, 170, facecolor=SURFACE, edgecolor=RULE)
        )
        ax.add_patch(Rectangle((pad_x, 150), 6, 170, facecolor=FLAG, edgecolor="none"))
        ax.text(
            pad_x + 32,
            235,
            L.text("og.home_empty"),
            fontproperties=fp_disp_bold,
            fontsize=28,
            color=INK,
            va="center",
            ha="left",
        )

    # Bottom hairline + concise footer tagline and domain.
    ax.add_patch(
        Rectangle((pad_x, 76), OG_WIDTH - 2 * pad_x, 1.5, facecolor=RULE, edgecolor="none")
    )
    ax.text(
        pad_x,
        38,
        L.text("og.tagline"),
        fontproperties=fp_disp_reg,
        fontsize=15,
        color=INK_2,
        va="baseline",
        ha="left",
    )
    ax.text(
        OG_WIDTH - pad_x,
        38,
        domain_label,
        fontproperties=fp_mono_reg,
        fontsize=14,
        color=INK_3,
        va="baseline",
        ha="right",
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    # Strip matplotlib Software metadata for clean, byte-for-byte deterministic PNG output.
    fig.savefig(dest, format="png", dpi=OG_DPI, metadata={"Software": None})
    return dest


def generate_og_cards(
    out: Path,
    L: Lang,
    week_pages: dict[tuple[int, int], list[dict]],
    current: tuple[int, int] | None,
    *,
    flag_pp: int,
    domain_label: str,
) -> list[Path]:
    """Generate homepage and every published week OG PNG for one language."""
    written: list[Path] = []
    if current is not None and current in week_pages:
        cur_season, cur_week = current
        cur_games = week_pages[current]
        home_sub = L.text("og.home_sub", week=cur_week, season=cur_season)
        header_right = f"NFL {cur_season} | W{cur_week:02d}"
    else:
        cur_games = []
        home_sub = L.text("og.home_empty")
        header_right = "NFL"

    written.append(
        _render_card(
            out / home_card_rel(L.code),
            title=L.text("og.home_title"),
            subtitle=home_sub,
            header_right=header_right,
            games=cur_games,
            L=L,
            flag_pp=flag_pp,
            domain_label=domain_label,
        )
    )

    for (season, week), games in sorted(week_pages.items()):
        written.append(
            _render_card(
                out / week_card_rel(season, week, L.code),
                title=L.text("og.week_title", week=week),
                subtitle=L.text("og.week_sub", season=season),
                header_right=f"NFL {season} | W{week:02d}",
                games=games,
                L=L,
                flag_pp=flag_pp,
                domain_label=domain_label,
            )
        )
    return written
