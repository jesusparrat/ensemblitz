"""Most likely final-margin bands from the headline score simulation.

Margins are home points minus away points, the same integers the simulator returns.
A tie (margin 0) is its own band. Regulation ties that survive overtime stay in that
band; they are not folded into a 1-7 band.

Bands, in canonical order:

- ``away_15``: away by 15 or more (margin <= -15)
- ``away_8_14``: away by 8 to 14
- ``away_1_7``: away by 1 to 7
- ``tie``: margin 0
- ``home_1_7``: home by 1 to 7
- ``home_8_14``: home by 8 to 14
- ``home_15``: home by 15 or more (margin >= 15)

Probabilities are the share of the same draws (``n_sims``, fixed seed), rounded to
4 decimals. Rank uses that rounded probability, then the canonical order above, so
two runs with the same seed produce the same top 3.
"""

from __future__ import annotations

import numpy as np

# (id, inclusive lo or None, inclusive hi or None)
BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("away_15", None, -15),
    ("away_8_14", -14, -8),
    ("away_1_7", -7, -1),
    ("tie", 0, 0),
    ("home_1_7", 1, 7),
    ("home_8_14", 8, 14),
    ("home_15", 15, None),
)
BAND_IDS: tuple[str, ...] = tuple(b[0] for b in BANDS)
OUTSIDE = "outside top 3"


def band_for_margin(margin: int) -> str:
    """Band id for an integer home margin."""
    m = int(margin)
    if m <= -15:
        return "away_15"
    if m <= -8:
        return "away_8_14"
    if m <= -1:
        return "away_1_7"
    if m == 0:
        return "tie"
    if m <= 7:
        return "home_1_7"
    if m <= 14:
        return "home_8_14"
    return "home_15"


def from_margins(margins: np.ndarray, n_sims: int, seed: int) -> dict:
    """All seven bands plus the top 3, from one game's simulated home margins."""
    v = np.asarray(margins, dtype=np.int64).reshape(-1)
    n = int(v.size)
    if n != int(n_sims):
        raise ValueError(f"expected {n_sims} margins, got {n}")
    # Same cuts as band_for_margin. Index 3 is the tie.
    ids = np.full(n, 3, dtype=np.int8)
    ids = np.where(v <= -15, 0, ids)
    ids = np.where((v >= -14) & (v <= -8), 1, ids)
    ids = np.where((v >= -7) & (v <= -1), 2, ids)
    ids = np.where((v >= 1) & (v <= 7), 4, ids)
    ids = np.where((v >= 8) & (v <= 14), 5, ids)
    ids = np.where(v >= 15, 6, ids)
    counts = np.bincount(ids, minlength=7)
    out_bands = [{"id": BAND_IDS[i], "prob": round(int(counts[i]) / n, 4)} for i in range(7)]
    order = {bid: i for i, bid in enumerate(BAND_IDS)}
    ranked = sorted(out_bands, key=lambda b: (-b["prob"], order[b["id"]]))
    return {
        "n_sims": int(n_sims),
        "seed": int(seed),
        "bands": out_bands,
        "top3": [b["id"] for b in ranked[:3]],
    }


def rank_of(band_id: str, top3: list[str]) -> int | str:
    """1, 2, 3, or ``outside top 3``."""
    if band_id in top3:
        return top3.index(band_id) + 1
    return OUTSIDE
