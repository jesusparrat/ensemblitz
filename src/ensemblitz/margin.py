"""Spread -> win probability with the empirical, discrete distribution of NFL margins.

A normal curve treats -2.5 to -3.5 like -4.5 to -5.5. In the NFL the final margin lands on 3 about
twice as often as the curve says, and on 7, 6, 10 and 14 more often too. Model:

    P(margin = k | expected margin m)  proportional to  w(|k|) x [Phi((k+.5-m)/s) - Phi((k-.5-m)/s)]

with ``w`` the observed / expected frequency of each absolute margin, estimated on earlier
games only (closing spread as the expected margin), shrunk towards 1 and lightly smoothed away
from the key numbers. ``s`` is the residual spread of whatever margin is converted.
Home win probability excludes ties: P(k > 0) / (P(k > 0) + P(k < 0)).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import ndtr

from ensemblitz import config as C

K = 45  # margins beyond +-45 are folded into the edge cells
KEYS = (3, 6, 7, 10, 14, 17)
SHRINK = 12.0  # pseudo-games pulling w towards 1
KS = np.arange(-K, K + 1)


def _cell_probs(m: np.ndarray, s: float) -> np.ndarray:
    """(n_games, 2K+1) discretised normal masses; edge cells absorb the tails."""
    lo = np.r_[-np.inf, KS[:-1] + 0.5]
    hi = np.r_[KS[1:] - 0.5, np.inf]
    mm = np.asarray(m, float)[:, None]
    return ndtr((hi[None, :] - mm) / s) - ndtr((lo[None, :] - mm) / s)


@dataclass
class MarginModel:
    w: np.ndarray  # tilt per |k| = 0..K
    sigma: float

    def dist(self, m: np.ndarray, sigma: float | None = None) -> np.ndarray:
        """(n_games, 2K+1) probabilities of every margin, with mean matched to ``m``.

        The centre of the normal part is shifted until the tilted distribution has mean ``m``:
        the closing spread is an unbiased margin forecast, and the tilt alone would move it.
        """
        s = sigma or self.sigma
        m = np.asarray(m, float)
        mu = m.copy()
        wk = self.w[np.abs(KS)][None, :]
        for _ in range(8):
            p = _cell_probs(mu, s) * wk
            p /= p.sum(axis=1, keepdims=True)
            err = m - p @ KS
            mu = mu + err
            if np.max(np.abs(err)) < 1e-4:
                break
        p = _cell_probs(mu, s) * wk
        return p / p.sum(axis=1, keepdims=True)

    def prob_home(self, m: np.ndarray, sigma: float | None = None) -> np.ndarray:
        p = self.dist(m, sigma)
        home, away = p[:, KS > 0].sum(axis=1), p[:, KS < 0].sum(axis=1)
        return home / (home + away)

    def prob_cover(self, m: np.ndarray, line: np.ndarray, sigma: float | None = None) -> np.ndarray:
        """P(home margin > line): the probability that matters at key numbers."""
        p = self.dist(m, sigma)
        return np.array([p[i, ln < KS].sum() for i, ln in enumerate(np.atleast_1d(line))])


def fit(spread: np.ndarray, result: np.ndarray, sigma: float | None = None) -> MarginModel:
    """Estimate the tilt from earlier games (spread = expected home margin, result = actual)."""
    spread, result = np.asarray(spread, float), np.asarray(result, float)
    s = sigma or float(np.std(result - spread))
    cells = np.clip(np.round(result), -K, K).astype(int) + K
    obs = np.bincount(cells, minlength=2 * K + 1).astype(float)
    exp = _cell_probs(spread, s).sum(axis=0)
    w = np.ones(K + 1)
    for a in range(1, K + 1):
        o = obs[K + a] + obs[K - a]
        e = exp[K + a] + exp[K - a]
        w[a] = (o + SHRINK) / (e + SHRINK)
    # light smoothing away from key numbers keeps the table from chasing noise
    sm = w.copy()
    for a in range(2, K):
        if a not in KEYS and (a - 1) not in KEYS and (a + 1) not in KEYS:
            sm[a] = 0.25 * w[a - 1] + 0.5 * w[a] + 0.25 * w[a + 1]
    sm[0] = 1.0
    return MarginModel(sm, s)


def history() -> pd.DataFrame:
    """All completed regular-season games with closing spread (1999 on): season, week, result."""
    parts = []
    h = C.RAW_DIR / "schedules_history.parquet"
    if h.exists():
        parts.append(pd.read_parquet(h))
    cur = pd.read_parquet(C.RAW_DIR / "schedules.parquet")
    parts.append(cur[["game_id", "season", "week", "game_type", "result", "spread_line"]])
    d = pd.concat(parts, ignore_index=True)
    d = d[(d["game_type"] == "REG") & d["result"].notna() & d["spread_line"].notna()]
    return d.sort_values(["season", "week"]).reset_index(drop=True)


def fit_before(hist: pd.DataFrame, season: int, week: int) -> MarginModel:
    earlier = (hist["season"] < season) | ((hist["season"] == season) & (hist["week"] < week))
    h = hist[earlier]
    return fit(h["spread_line"].to_numpy(), h["result"].to_numpy())
