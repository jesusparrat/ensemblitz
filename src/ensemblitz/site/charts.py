"""Server-side SVG charts. Styling lives in style.css (classes), so there is no chart library."""

from __future__ import annotations

import numpy as np

W, H = 640, 190
PAD_L, PAD_R, PAD_T, PAD_B = 8, 8, 20, 30


def _svg(body: str, h: int = H, label: str = "") -> str:
    return (
        f'<svg class="chart" viewBox="0 0 {W} {h}" role="img" aria-label="{label}" '
        f'preserveAspectRatio="xMidYMid meet">{body}</svg>'
    )


def histogram(
    values: np.ndarray,
    lo: int,
    hi: int,
    pick_side: str | None,
    marker: float | None,
    marker_label: str,
    left_label: str,
    right_label: str,
    label: str,
    split: float | None = 0.0,
) -> str:
    """Probability histogram of integer outcomes in [lo, hi].

    ``split``: bars right of it are the "home" side. ``pick_side`` ('home'/'away'/None)
    decides which side gets the accent colour.
    """
    v = np.clip(values, lo, hi)
    bins = np.arange(lo, hi + 1)
    counts = np.array([(v == b).sum() for b in bins], float) / len(values)
    top = max(counts.max(), 1e-9)
    n = len(bins)
    bw = (W - PAD_L - PAD_R) / n
    base = H - PAD_B
    ph = base - PAD_T
    out = []
    for i, (b, c) in enumerate(zip(bins, counts, strict=True)):
        x = PAD_L + i * bw
        bh = ph * c / top
        side = None if split is None else ("home" if b > split else "away" if b < split else None)
        cls = "bar-pick" if side and side == pick_side else "bar-other"
        out.append(
            f'<rect class="{cls}" x="{x + 0.5:.1f}" y="{base - bh:.1f}" '
            f'width="{max(bw - 1, 1):.1f}" height="{bh:.1f}"/>'
        )
    out.append(f'<line class="axis" x1="{PAD_L}" x2="{W - PAD_R}" y1="{base}" y2="{base}"/>')
    # ticks every 10 (margin) or 10 (total)
    step = 10
    for t in range((lo // step) * step, hi + 1, step):
        if t < lo:
            continue
        x = PAD_L + (t - lo + 0.5) * bw
        out.append(f'<line class="tick" x1="{x:.1f}" x2="{x:.1f}" y1="{base}" y2="{base + 4}"/>')
        out.append(
            f'<text class="axis-label" x="{x:.1f}" y="{base + 16}" text-anchor="middle">{t}</text>'
        )
    if marker is not None and lo <= marker <= hi:
        x = PAD_L + (marker - lo + 0.5) * bw
        out.append(f'<line class="marker" x1="{x:.1f}" x2="{x:.1f}" y1="{PAD_T - 6}" y2="{base}"/>')
        anchor = "end" if x > W * 0.7 else "start"
        dx = -4 if anchor == "end" else 4
        out.append(
            f'<text class="marker-label" x="{x + dx:.1f}" y="{PAD_T}" '
            f'text-anchor="{anchor}">{marker_label}</text>'
        )
    if left_label:
        out.append(f'<text class="side-label" x="{PAD_L}" y="{H - 2}">{left_label}</text>')
    if right_label:
        out.append(
            f'<text class="side-label" x="{W - PAD_R}" y="{H - 2}" text-anchor="end">'
            f"{right_label}</text>"
        )
    return _svg("".join(out), label=label)


def calibration(points: list[dict], x_label: str, y_label: str, aria: str) -> str:
    """Reliability diagram: predicted vs observed frequency, dot area ~ games in the bin."""
    size = 300
    pad = 34
    s = size - 2 * pad
    out = [f'<rect class="plot-bg" x="{pad}" y="{pad}" width="{s}" height="{s}"/>']
    for t in (0, 0.25, 0.5, 0.75, 1):
        x = pad + t * s
        y = pad + (1 - t) * s
        out.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{pad}" y2="{pad + s}"/>')
        out.append(f'<line class="grid" x1="{pad}" x2="{pad + s}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="axis-label" x="{x:.1f}" y="{pad + s + 16}" text-anchor="middle">'
            f"{int(t * 100)}</text>"
        )
        out.append(
            f'<text class="axis-label" x="{pad - 6}" y="{y + 4:.1f}" text-anchor="end">'
            f"{int(t * 100)}</text>"
        )
    out.append(f'<line class="diag" x1="{pad}" y1="{pad + s}" x2="{pad + s}" y2="{pad}"/>')
    nmax = max(p["n"] for p in points)
    pts = " ".join(f"{pad + p['pred'] * s:.1f},{pad + (1 - p['actual']) * s:.1f}" for p in points)
    out.append(f'<polyline class="calib-line" points="{pts}"/>')
    for p in points:
        r = 2.5 + 5.5 * np.sqrt(p["n"] / nmax)
        out.append(
            f'<circle class="calib-dot" cx="{pad + p["pred"] * s:.1f}" '
            f'cy="{pad + (1 - p["actual"]) * s:.1f}" r="{r:.1f}"/>'
        )
    out.append(
        f'<text class="side-label" x="{pad + s / 2}" y="{size - 4}" text-anchor="middle">'
        f"{x_label}</text>"
    )
    out.append(
        f'<text class="side-label" x="10" y="{pad + s / 2}" text-anchor="middle" '
        f'transform="rotate(-90 10 {pad + s / 2})">{y_label}</text>'
    )
    return (
        f'<svg class="chart chart-square" viewBox="0 0 {size} {size}" role="img" '
        f'aria-label="{aria}">{"".join(out)}</svg>'
    )


def running_lines(series: dict[str, list[float]], label: str) -> str:
    """Cumulative accuracy lines (values in 0..1). First series is drawn in the accent."""
    n = max(len(v) for v in series.values())
    h = 180
    base = h - PAD_B
    top = PAD_T
    out = []
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + (1 - t) * (base - top)
        out.append(
            f'<line class="grid" x1="{PAD_L + 24}" x2="{W - PAD_R}" y1="{y:.1f}" y2="{y:.1f}"/>'
        )
        out.append(
            f'<text class="axis-label" x="{PAD_L + 18}" y="{y + 4:.1f}" text-anchor="end">'
            f"{int(t * 100)}</text>"
        )
    for k, (name, vals) in enumerate(series.items()):
        pts = []
        for i, v in enumerate(vals):
            x = PAD_L + 24 + (W - PAD_R - PAD_L - 24) * (i / max(n - 1, 1))
            y = top + (1 - v) * (base - top)
            pts.append(f"{x:.1f},{y:.1f}")
        out.append(f'<polyline class="line-{k}" points="{" ".join(pts)}"/>')
        out.append(
            f'<text class="side-label" x="{PAD_L + 30 + k * 120}" y="{h - 4}">'
            f'<tspan class="legend-{k}">&#9632;</tspan> {name}</text>'
        )
    return _svg("".join(out), h=h, label=label)
