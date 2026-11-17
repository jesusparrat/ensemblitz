"""Market-implied probabilities."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import ndtr, ndtri

MARGIN_SD = 13.5  # NFL final margin standard deviation around the closing spread


def ml_to_prob(ml: pd.Series | np.ndarray) -> np.ndarray:
    """American moneyline -> implied probability (with vig)."""
    ml = np.asarray(ml, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ml < 0, -ml / (-ml + 100.0), 100.0 / (ml + 100.0))


def margin_to_prob(margin: np.ndarray | pd.Series, sd: float = MARGIN_SD) -> np.ndarray:
    return ndtr(np.asarray(margin, dtype=float) / sd)


def market_prob(df: pd.DataFrame) -> np.ndarray:
    """No-vig home win probability from moneylines; falls back to the spread, NaN if no line."""
    ph = ml_to_prob(df["home_moneyline"])
    pa = ml_to_prob(df["away_moneyline"])
    novig = ph / (ph + pa)
    spread = margin_to_prob(df["spread_line"])
    return np.where(np.isnan(novig), spread, novig)


def implied_spread(home_ml: pd.Series | np.ndarray, away_ml: pd.Series | np.ndarray) -> np.ndarray:
    """Home margin whose normal win probability matches the no-vig moneyline probability."""
    ph = ml_to_prob(home_ml)
    pa = ml_to_prob(away_ml)
    return MARGIN_SD * ndtri(ph / (ph + pa))
