"""Stacked ensemble: win probability (logit stack with Platt-style bias) and margin/total blends.

Everything is fitted on a *pool* of earlier out-of-sample predictions, so no weight ever sees the
games it is applied to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize, nnls
from scipy.special import expit, logit

PROB_EPS = 1e-4
MODEL_COMPONENTS = ["elo", "kf", "lgbm"]
ALL_COMPONENTS = ["market", "elo", "kf", "lgbm", "lgbm_mkt"]
MIN_POOL = 150


def _logit(p: np.ndarray) -> np.ndarray:
    return logit(np.clip(p, PROB_EPS, 1 - PROB_EPS))


@dataclass
class StackModel:
    comps: list[str]
    w: np.ndarray  # win-prob weights on logits (>= 0)
    b: float  # bias (Platt intercept)
    margin_w: np.ndarray  # blend weights on component margins
    total_w: np.ndarray  # blend weights on [kf_total, total_line]
    total_cols: list[str] = field(default_factory=list)

    def prob(self, df: pd.DataFrame) -> np.ndarray:
        x = np.column_stack([_logit(df[f"{c}_prob"].to_numpy()) for c in self.comps])
        return expit(x @ self.w + self.b)

    def margin(self, df: pd.DataFrame) -> np.ndarray:
        return np.column_stack([df[f"{c}_margin"].to_numpy() for c in self.comps]) @ self.margin_w

    def total(self, df: pd.DataFrame) -> np.ndarray:
        cols = [df[c].to_numpy() for c in self.total_cols]
        return np.column_stack(cols) @ self.total_w


def fit_stack(pool: pd.DataFrame, comps: list[str], l2: float = 0.002) -> StackModel:
    """Fit on played, non-tied pool games."""
    pool = pool[pool["result"] != 0].dropna(subset=[f"{c}_prob" for c in comps] + ["result"])
    y = (pool["result"] > 0).to_numpy(float)
    x = np.column_stack([_logit(pool[f"{c}_prob"].to_numpy()) for c in comps])
    k = len(comps)

    def loss(theta: np.ndarray) -> float:
        z = x @ theta[:k] + theta[k]
        ll = np.mean(np.logaddexp(0, z) - y * z)
        return float(ll + l2 * np.sum(theta[:k] ** 2))

    theta0 = np.r_[np.full(k, 1.0 / k), 0.0]
    res = minimize(loss, theta0, method="L-BFGS-B", bounds=[(0, 3)] * k + [(-1, 1)])
    w, b = res.x[:k], float(res.x[k])

    m = np.column_stack([pool[f"{c}_margin"].to_numpy() for c in comps])
    if "market" in comps:
        # Anchor on the spread: result - spread = sum_k w_k (margin_k - spread), w >= 0.
        j = comps.index("market")
        others = [i for i in range(k) if i != j]
        dev = m[:, others] - m[:, [j]]
        w_dev, _ = nnls(dev, pool["result"].to_numpy(float) - m[:, j])
        if w_dev.sum() > 1.0:
            w_dev = w_dev / w_dev.sum()
        mw = np.zeros(k)
        mw[others] = w_dev
        mw[j] = 1.0 - w_dev.sum()
    else:
        mw, _ = nnls(m, pool["result"].to_numpy(float))
    tcols = ["kf_total"] + (["total_line"] if "market" in comps else [])
    tp = pool.dropna(subset=tcols + ["total"])
    tw, _ = nnls(tp[tcols].to_numpy(float), tp["total"].to_numpy(float))
    return StackModel(comps, w, b, mw, tw, tcols)


class Ensemble:
    """Two stack models: one with the market components and one for games without a line."""

    def __init__(self, pool: pd.DataFrame) -> None:
        self.full = fit_stack(pool[pool["spread_line"].notna()], ALL_COMPONENTS)
        self.no_market = fit_stack(pool, MODEL_COMPONENTS)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(
            index=df.index, columns=["ens_prob", "ens_margin", "ens_total"], dtype=float
        )
        has = df["spread_line"].notna().to_numpy()
        for mask, model in ((has, self.full), (~has, self.no_market)):
            if mask.any():
                sub = df[mask]
                out.loc[sub.index, "ens_prob"] = model.prob(sub)
                out.loc[sub.index, "ens_margin"] = model.margin(sub)
                out.loc[sub.index, "ens_total"] = model.total(sub)
        return out

    def weights(self) -> dict[str, dict[str, list[float] | float]]:
        def d(m: StackModel) -> dict:
            return {
                "components": m.comps,
                "prob_weights": np.round(m.w, 3).tolist(),
                "bias": round(m.b, 3),
                "margin_weights": np.round(m.margin_w, 3).tolist(),
            }

        return {"with_market": d(self.full), "no_market": d(self.no_market)}
