"""Most likely final-margin bands from the headline score simulation.

Margins are home points minus away points, the same integers the simulator returns.
A tie (margin 0) is its own band. Regulation ties that survive overtime stay in that
band; they are not folded into a 1-3 band.

Current bands, in canonical order:

- ``away_22p``: away by 22 or more (margin <= -22)
- ``away_15_21``: away by 15 to 21
- ``away_8_14``: away by 8 to 14
- ``away_4_7``: away by 4 to 7
- ``away_1_3``: away by 1 to 3
- ``tie``: margin 0
- ``home_1_3``: home by 1 to 3
- ``home_4_7``: home by 4 to 7
- ``home_8_14``: home by 8 to 14
- ``home_15_21``: home by 15 to 21
- ``home_22p``: home by 22 or more (margin >= 22)

Snapshots already written use the earlier seven-band set (``away_15``, ``away_8_14``,
``away_1_7``, ``tie``, ``home_1_7``, ``home_8_14``, ``home_15``). Grading and display
of those records use the band ids stored on the record.

Probabilities are the share of the same draws (``n_sims``, fixed seed), rounded to
4 decimals. Rank uses that rounded probability, then the canonical order of the set
being written, so two runs with the same seed produce the same top 3.
"""

from __future__ import annotations

import numpy as np

# (id, inclusive lo or None, inclusive hi or None)
BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("away_22p", None, -22),
    ("away_15_21", -21, -15),
    ("away_8_14", -14, -8),
    ("away_4_7", -7, -4),
    ("away_1_3", -3, -1),
    ("tie", 0, 0),
    ("home_1_3", 1, 3),
    ("home_4_7", 4, 7),
    ("home_8_14", 8, 14),
    ("home_15_21", 15, 21),
    ("home_22p", 22, None),
)
# Frozen on snapshots written before the eleven-band set. Do not use for new writes.
LEGACY_BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("away_15", None, -15),
    ("away_8_14", -14, -8),
    ("away_1_7", -7, -1),
    ("tie", 0, 0),
    ("home_1_7", 1, 7),
    ("home_8_14", 8, 14),
    ("home_15", 15, None),
)
BAND_IDS: tuple[str, ...] = tuple(b[0] for b in BANDS)
LEGACY_BAND_IDS: tuple[str, ...] = tuple(b[0] for b in LEGACY_BANDS)
CANONICAL_SETS: tuple[tuple[str, ...], ...] = (BAND_IDS, LEGACY_BAND_IDS)
_BY_IDS: dict[tuple[str, ...], tuple[tuple[str, int | None, int | None], ...]] = {
    BAND_IDS: BANDS,
    LEGACY_BAND_IDS: LEGACY_BANDS,
}
OUTSIDE = "outside top 3"
OPEN_TAILS = frozenset({"home_22p", "away_22p", "home_15", "away_15"})


def spec_for_ids(
    band_ids: list[str] | tuple[str, ...],
) -> tuple[tuple[str, int | None, int | None], ...] | None:
    """The band set whose canonical ids match ``band_ids``, or ``None``."""
    return _BY_IDS.get(tuple(band_ids))


def band_for_margin(margin: int, band_ids: list[str] | tuple[str, ...] | None = None) -> str:
    """Band id for an integer home margin.

    ``band_ids`` is the canonical id list stored on a record. Omit it when writing
    a new snapshot: that uses the current eleven-band set. A record that stored the
    seven-band ids is graded with those edges.
    """
    spec = BANDS if band_ids is None else spec_for_ids(band_ids)
    if spec is None:
        raise ValueError("unknown outcome band set")
    m = int(margin)
    for bid, lo, hi in spec:
        if (lo is None or m >= lo) and (hi is None or m <= hi):
            return bid
    raise ValueError(f"margin {m} is outside every band")


def from_margins(margins: np.ndarray, n_sims: int, seed: int) -> dict:
    """All eleven current bands plus the top 3, from one game's simulated home margins."""
    v = np.asarray(margins, dtype=np.int64).reshape(-1)
    n = int(v.size)
    if n != int(n_sims):
        raise ValueError(f"expected {n_sims} margins, got {n}")
    ids = np.full(n, -1, dtype=np.int8)
    for i, (_bid, lo, hi) in enumerate(BANDS):
        mask = np.ones(n, dtype=bool)
        if lo is not None:
            mask &= v >= lo
        if hi is not None:
            mask &= v <= hi
        ids = np.where(mask, i, ids)
    if int((ids < 0).sum()):
        raise ValueError("a simulated margin fell outside every band")
    counts = np.bincount(ids, minlength=len(BANDS))
    out_bands = [
        {"id": BAND_IDS[i], "prob": round(int(counts[i]) / n, 4)} for i in range(len(BANDS))
    ]
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
