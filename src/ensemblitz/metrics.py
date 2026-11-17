"""Evaluation metrics (ties are excluded from win/loss metrics)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def score_probs(df: pd.DataFrame, prob_col: str) -> dict[str, float]:
    d = df[(df["result"] != 0)].dropna(subset=[prob_col, "result"])
    y = (d["result"] > 0).to_numpy(float)
    p = np.clip(d[prob_col].to_numpy(float), 1e-4, 1 - 1e-4)
    return {
        "n": int(len(d)),
        "accuracy": float(np.mean((p > 0.5) == (y == 1))),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
    }


def ats(df: pd.DataFrame, margin_col: str) -> dict[str, float | int]:
    """Against-the-spread record betting the side the model likes versus the closing spread."""
    d = df.dropna(subset=[margin_col, "spread_line", "result"])
    d = d[d[margin_col] != d["spread_line"]]
    bet_home = d[margin_col] > d["spread_line"]
    cover = d["result"] - d["spread_line"]
    win = ((cover > 0) & bet_home) | ((cover < 0) & ~bet_home)
    push = cover == 0
    w, p = int(win.sum()), int(push.sum())
    n = len(d)
    l_ = n - w - p
    return {"w": w, "l": l_, "push": p, "win_pct": float(w / (w + l_)) if w + l_ else float("nan")}


def margin_mae(df: pd.DataFrame, margin_col: str) -> float:
    d = df.dropna(subset=[margin_col, "result"])
    return float(np.mean(np.abs(d[margin_col] - d["result"])))


def calibration_table(df: pd.DataFrame, prob_col: str, bins: int = 10) -> list[dict]:
    d = df[(df["result"] != 0)].dropna(subset=[prob_col, "result"]).copy()
    d["y"] = (d["result"] > 0).astype(float)
    d["bin"] = pd.cut(d[prob_col], np.linspace(0, 1, bins + 1), include_lowest=True)
    t = d.groupby("bin", observed=True).agg(
        n=("y", "size"), pred=(prob_col, "mean"), actual=("y", "mean")
    )
    return [
        {"bin": str(i), "n": int(r.n), "pred": float(r.pred), "actual": float(r.actual)}
        for i, r in t.iterrows()
    ]


def summarize(df: pd.DataFrame, comp: str) -> dict:
    out = score_probs(df, f"{comp}_prob")
    out["mae_margin"] = margin_mae(df, f"{comp}_margin")
    out["ats"] = ats(df, f"{comp}_margin")
    return out
