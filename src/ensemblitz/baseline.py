"""Phase 0 baseline: strict walk-forward audit of model-only, market and stacked ensemble.

Three things are scored on exactly the same games (2018-2025 regular season, ties excluded):

* ``market``     closing no-vig probability (moneyline, spread as fallback);
* ``model_only`` stack of Elo, Kalman and LightGBM *without* any market input (what the site
                 calls "ensemble_model_only");
* ``ens``        the published stack (market + models + LightGBM residual on the market).

Every stack is refitted before each (season, week) using only games of earlier weeks, and the
fit asserts that no pool game is from the same or a later week. Component predictions
(Elo, Kalman, LightGBM) come from the existing walk-forward pipeline.

The slim ``reports/baseline_components.parquet`` keeps those component predictions so the stacking
layer can be re-audited in seconds (CI) without nflverse data. ``--full`` recomputes everything.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import binomtest

from ensemblitz import config as C
from ensemblitz import metrics as M
from ensemblitz.models.ensemble import ALL_COMPONENTS, PROB_EPS, Ensemble, StackModel

COMPS = ["market", "elo", "kf", "lgbm", "lgbm_mkt"]
REG_ID = r"^\d{4}_\d{2}_"
CACHE_PATH = C.REPORTS_DIR / "baseline_components.parquet"
JSON_PATH = C.REPORTS_DIR / "baseline_2018_2025.json"
MD_PATH = C.REPORTS_DIR / "BASELINE.md"
PNG_PATH = C.REPORTS_DIR / "baseline_calibration.png"
CACHE_COLS = (
    ["game_id", "season", "week", "played", "result", "spread_line", "total_line", "total"]
    + ["kf_total"]
    + [f"{c}_{k}" for c in COMPS for k in ("prob", "margin")]
)
SCORED = ["market", "model_only", "ens"]
VARIANTS = ["ens_cap1", "ens_pool", "mo_cap1"]
NAMES = {
    "market": "Mercado (cierre sin comisión)",
    "model_only": "Solo modelo (sin mercado)",
    "ens": "Ensemble publicado",
    "ens_cap1": "Ensemble, pesos con suma ≤ 1",
    "ens_pool": "Ensemble, suma = 1 y sin sesgo (sin extremizar)",
    "mo_cap1": "Solo modelo, pesos con suma ≤ 1",
}
FAV_BINS = [0.5, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.0]
TOL_LOG_LOSS = 0.0015
TOL_BRIER = 0.0007
BOOT_N = 10_000
BOOT_SEED = 20260


def _logit(p: np.ndarray) -> np.ndarray:
    return logit(np.clip(np.asarray(p, float), PROB_EPS, 1 - PROB_EPS))


# ------------------------------------------------------------------ data
def components_from_pipeline() -> pd.DataFrame:
    """Recompute the walk-forward component predictions from nflverse data in ``data/``."""
    from ensemblitz import pipeline as P

    feats = P.make_features()
    feats, _ = P.add_kf(feats, int(feats["season"].max()), stored=P.load_kf_params())
    feats = P.add_components_static(feats)
    feats = P.add_gbm_components(feats)
    return slim(feats)


def slim(feats: pd.DataFrame) -> pd.DataFrame:
    d = feats[feats["season"].between(C.WARMUP_SEASON, C.LAST_BACKTEST_SEASON)]
    # Playoff games stay: the production stacker trains on them too, so the pool is identical.
    return (
        d[d["played"]][CACHE_COLS].sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    )


def save_cache(df: pd.DataFrame, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, compression="zstd")


def load_cache(path: Path = CACHE_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


# ------------------------------------------------------------------ constrained stacks
def fit_logit_stack(
    pool: pd.DataFrame, comps: list[str], mode: str, l2: float = 0.002
) -> StackModel:
    """Logit stack with a constraint on the weights, same loss and L2 as the production stack.

    mode ``cap1``: weights >= 0, sum <= 1, free bias in [-1, 1] (cannot extremize).
    mode ``pool``: weights >= 0, sum == 1, bias 0 (plain logit pooling: no extremizing, no Platt).
    """
    pool = pool[pool["result"] != 0].dropna(subset=[f"{c}_prob" for c in comps] + ["result"])
    y = (pool["result"] > 0).to_numpy(float)
    x = np.column_stack([_logit(pool[f"{c}_prob"].to_numpy()) for c in comps])
    k = len(comps)

    def loss(t: np.ndarray) -> float:
        z = x @ t[:k] + (t[k] if mode == "cap1" else 0.0)
        return float(np.mean(np.logaddexp(0, z) - y * z) + l2 * np.sum(t[:k] ** 2))

    cons = (
        {"type": "ineq", "fun": lambda t: 1.0 - np.sum(t[:k])}
        if mode == "cap1"
        else {"type": "eq", "fun": lambda t: np.sum(t[:k]) - 1.0}
    )
    bounds = [(0, 1)] * k + [(-1, 1) if mode == "cap1" else (0, 0)]
    res = minimize(
        loss, np.r_[np.full(k, 1.0 / k), 0.0], method="SLSQP", bounds=bounds, constraints=[cons]
    )
    z = np.zeros(k)
    return StackModel(comps, res.x[:k], float(res.x[k]), z, z)


# ------------------------------------------------------------------ walk-forward
def walk_forward(
    df: pd.DataFrame, first: int = C.FIRST_BACKTEST_SEASON
) -> tuple[pd.DataFrame, list]:
    """Refit every stack before each (season, week) with earlier games only.

    Returns the frame with ``mo_*`` / ``ens*_*`` columns and one record of coefficients per fold.
    """
    df = df.copy().reset_index(drop=True)
    for c in ("mo_prob", "mo_margin", "ens_prob", "ens_margin", *[f"{v}_prob" for v in VARIANTS]):
        df[c] = np.nan
    need = [f"{c}_prob" for c in COMPS]
    folds: list[dict] = []
    for (season, week), batch in df.groupby(["season", "week"], sort=True):
        if season < first or week > 18:
            continue
        earlier = (df["season"] < season) | ((df["season"] == season) & (df["week"] < week))
        pool = df[earlier & df["played"] & df["result"].notna() & (df["season"] >= C.WARMUP_SEASON)]
        pool = pool.dropna(subset=need)
        if len(pool) < 150:
            continue
        # Hard leakage guard: nothing in the pool may be from this week or later.
        last_in_pool = pool[["season", "week"]].apply(tuple, axis=1).max()
        assert last_in_pool < (season, week), f"leakage in fold {season}/{week}"
        ens = Ensemble(pool)
        full, nm = ens.full, ens.no_market
        df.loc[batch.index, "ens_prob"] = full.prob(batch)
        df.loc[batch.index, "ens_margin"] = full.margin(batch)
        df.loc[batch.index, "mo_prob"] = nm.prob(batch)
        df.loc[batch.index, "mo_margin"] = nm.margin(batch)
        v1 = fit_logit_stack(pool, ALL_COMPONENTS, "cap1")
        v2 = fit_logit_stack(pool, ALL_COMPONENTS, "pool")
        v3 = fit_logit_stack(pool, ["elo", "kf", "lgbm"], "cap1")
        df.loc[batch.index, "ens_cap1_prob"] = v1.prob(batch)
        df.loc[batch.index, "ens_pool_prob"] = v2.prob(batch)
        df.loc[batch.index, "mo_cap1_prob"] = v3.prob(batch)
        folds.append(
            {
                "season": int(season),
                "week": int(week),
                "n_pool": int(len(pool)),
                "ens": _coef(full),
                "model_only": _coef(nm),
                "ens_cap1": _coef(v1),
                "ens_pool": _coef(v2),
                "mo_cap1": _coef(v3),
            }
        )
    for src, dst in (("mo", "model_only"), ("ens", "ens")):
        df[f"{dst}_prob"] = df[f"{src}_prob"]
    df["model_only_margin"] = df["mo_margin"]
    return df, folds


def _coef(m: StackModel) -> dict:
    return {
        "components": m.comps,
        "weights": [round(float(w), 4) for w in m.w],
        "sum_weights": round(float(np.sum(m.w)), 4),
        "bias": round(float(m.b), 4),
    }


# ------------------------------------------------------------------ metrics
def scoring_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Games 2018-2025 where every scored probability exists (ties out of the probabilistic score)."""
    cols = [f"{c}_prob" for c in [*SCORED, *VARIANTS]]
    d = df[df["season"].between(C.FIRST_BACKTEST_SEASON, C.LAST_BACKTEST_SEASON)]
    d = d[d["played"] & (d["week"] <= 18) & d["game_id"].str.contains(REG_ID)].dropna(
        subset=cols + ["result"]
    )
    return d[d["result"] != 0].reset_index(drop=True)


def outcomes(d: pd.DataFrame) -> np.ndarray:
    return (d["result"] > 0).to_numpy(float)


def _ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calib_slope(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Logistic recalibration y ~ a + b * logit(p). b < 1: overconfident; b > 1: underconfident."""
    x = _logit(p)
    t = np.array([0.0, 1.0])
    for _ in range(25):
        z = t[0] + t[1] * x
        mu = expit(z)
        g = np.array([np.sum(y - mu), np.sum((y - mu) * x)])
        w = mu * (1 - mu)
        h = np.array([[np.sum(w), np.sum(w * x)], [np.sum(w * x), np.sum(w * x * x)]])
        step = np.linalg.solve(h + 1e-9 * np.eye(2), g)
        t = t + step
        if np.max(np.abs(step)) < 1e-9:
            break
    return float(t[0]), float(t[1])


def score(p: np.ndarray, y: np.ndarray) -> dict:
    a, b = calib_slope(p, y)
    return {
        "n": int(len(y)),
        "accuracy": float(np.mean((p > 0.5) == (y == 1))),
        "brier": float(np.mean((np.clip(p, 1e-4, 1 - 1e-4) - y) ** 2)),
        "log_loss": float(np.mean(_ll(p, y))),
        "calibration_intercept": a,
        "calibration_slope": b,
    }


def deciles(p: np.ndarray, y: np.ndarray, q: int = 10) -> list[dict]:
    """Equal-count deciles of the predicted home-win probability."""
    order = np.argsort(p, kind="stable")
    out = []
    for i, idx in enumerate(np.array_split(order, q)):
        out.append(
            {
                "decile": i + 1,
                "n": int(len(idx)),
                "pred": float(p[idx].mean()),
                "actual": float(y[idx].mean()),
                "lo": float(p[idx].min()),
                "hi": float(p[idx].max()),
            }
        )
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return float(c - h), float(c + h)


def favourite_bins(p: np.ndarray, y: np.ndarray) -> list[dict]:
    """Calibration of the side the model favours: bins of max(p, 1-p) against how often it won."""
    pf = np.maximum(p, 1 - p)
    yf = np.where(p >= 0.5, y, 1 - y)
    out = []
    for lo, hi in zip(FAV_BINS[:-1], FAV_BINS[1:], strict=True):
        m = (pf >= lo) & (pf < hi) if hi < 1 else (pf >= lo)
        n = int(m.sum())
        if n == 0:
            continue
        k = int(yf[m].sum())
        l_, h_ = wilson(k, n)
        out.append(
            {
                "bin": f"{lo * 100:.0f}-{hi * 100:.0f}%" if hi < 1 else f"{lo * 100:.0f}%+",
                "n": n,
                "pred": float(pf[m].mean()),
                "actual": k / n,
                "actual_lo": l_,
                "actual_hi": h_,
                "log_loss": float(np.mean(_ll(pf[m], yf[m]))),
            }
        )
    return out


def heavy_fav(p: np.ndarray, y: np.ndarray, thr: float = 0.75) -> dict:
    pf = np.maximum(p, 1 - p)
    yf = np.where(p >= 0.5, y, 1 - y)
    m = pf >= thr
    n = int(m.sum())
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "pred": float(pf[m].mean()),
        "actual": float(yf[m].mean()),
        "overconfidence_pp": float((pf[m].mean() - yf[m].mean()) * 100),
        "log_loss": float(np.mean(_ll(pf[m], yf[m]))),
    }


def heavy_fav_same_games(d: pd.DataFrame, y: np.ndarray, thr: float = 0.75) -> dict:
    """Games where the published ensemble gives its favourite ``thr`` or more.

    On exactly those games, what did each source give to the ensemble's favourite and how often
    did that side win? This isolates extremizing from differences in which games land in a bin.
    """
    pe = d["ens_prob"].to_numpy(float)
    m = np.maximum(pe, 1 - pe) >= thr
    fav_home = pe >= 0.5
    n = int(m.sum())
    out: dict = {"threshold": thr, "n": n}
    yf = np.where(fav_home, y, 1 - y)[m]
    k = int(yf.sum())
    lo, hi = wilson(k, n)
    out["actual"] = k / n if n else None
    out["actual_ci95"] = [lo, hi]
    for key in [*SCORED, "ens_cap1", "ens_pool"]:
        p = d[f"{key}_prob"].to_numpy(float)
        pf = np.where(fav_home, p, 1 - p)[m]
        out[key] = {
            "pred_mean": float(pf.mean()) if n else None,
            "overconfidence_pp": float((pf.mean() - yf.mean()) * 100) if n else None,
            "log_loss": float(np.mean(_ll(pf, yf))) if n else None,
        }
    return out


def input_correlation(d: pd.DataFrame) -> dict:
    cols = {c: _logit(d[f"{c}_prob"].to_numpy()) for c in COMPS}
    m = pd.DataFrame(cols).corr()
    return {a: {b: float(m.loc[a, b]) for b in COMPS} for a in COMPS}


def bootstrap(d: pd.DataFrame, y: np.ndarray, n: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """Paired bootstrap over games: 95% CIs for each metric and for differences vs the market."""
    rng = np.random.default_rng(seed)
    keys = [*SCORED, *VARIANTS]
    p = {k: np.clip(d[f"{k}_prob"].to_numpy(float), 1e-4, 1 - 1e-4) for k in keys}
    ll = {k: _ll(p[k], y) for k in keys}
    br = {k: (p[k] - y) ** 2 for k in keys}
    nn = len(y)
    acc = {k: ((p[k] > 0.5) == (y == 1)).astype(float) for k in keys}
    store: dict[str, list[np.ndarray]] = {}
    done = 0
    while done < n:
        b = min(1000, n - done)
        idx = rng.integers(0, nn, size=(b, nn), dtype=np.int32)
        for k in keys:
            store.setdefault(f"ll_{k}", []).append(ll[k][idx].mean(axis=1))
            store.setdefault(f"br_{k}", []).append(br[k][idx].mean(axis=1))
            store.setdefault(f"ac_{k}", []).append(acc[k][idx].mean(axis=1))
        done += b
    s = {k: np.concatenate(v) for k, v in store.items()}

    def ci(a: np.ndarray) -> list[float]:
        return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]

    out: dict = {"n_boot": n, "seed": seed, "levels": {}, "diff_vs_market": {}}
    for k in keys:
        out["levels"][k] = {
            "log_loss_ci": ci(s[f"ll_{k}"]),
            "brier_ci": ci(s[f"br_{k}"]),
            "accuracy_ci": ci(s[f"ac_{k}"]),
        }
    for k in keys:
        if k == "market":
            continue
        dl, db = s[f"ll_{k}"] - s["ll_market"], s[f"br_{k}"] - s["br_market"]
        obs_l = float(ll[k].mean() - ll["market"].mean())
        obs_b = float(br[k].mean() - br["market"].mean())
        out["diff_vs_market"][k] = {
            "log_loss": obs_l,
            "log_loss_ci": ci(dl),
            "log_loss_p_better_than_market": float(np.mean(dl < 0)),
            "brier": obs_b,
            "brier_ci": ci(db),
        }
    # ens vs the constrained variants (is the constraint better out of sample?)
    for k in ("ens_cap1", "ens_pool"):
        dl = s[f"ll_{k}"] - s["ll_ens"]
        out["diff_vs_market"][f"{k}_minus_ens"] = {
            "log_loss": float(ll[k].mean() - ll["ens"].mean()),
            "log_loss_ci": ci(dl),
            "brier": float(br[k].mean() - br["ens"].mean()),
            "brier_ci": ci(s[f"br_{k}"] - s["br_ens"]),
        }
    return out


def ats_block(d: pd.DataFrame, margin_col: str) -> dict:
    """ATS against the closing spread betting the side the model prefers."""

    def one(x: pd.DataFrame) -> dict:
        r = M.ats(x, margin_col)
        w, l_ = r["w"], r["l"]
        n = w + l_
        lo, hi = wilson(w, n)
        return {
            "w": w,
            "l": l_,
            "push": r["push"],
            "win_pct": r["win_pct"] if n else None,
            "ci95": [lo, hi] if n else None,
            "p_vs_50": float(binomtest(w, n, 0.5).pvalue) if n else None,
            "p_vs_breakeven_52_38": float(binomtest(w, n, 0.5238).pvalue) if n else None,
        }

    x = d.dropna(subset=[margin_col, "spread_line"])
    big = x[(x[margin_col] - x["spread_line"]).abs() >= 3]
    return {
        "all": one(x),
        "disagree_3pts_or_more": one(big),
        "per_season": {int(s): one(g) for s, g in x.groupby("season")},
    }


def weight_summary(folds: list[dict]) -> dict:
    out: dict = {}
    for key in ("ens", "model_only", "ens_cap1", "ens_pool", "mo_cap1"):
        sums = np.array([f[key]["sum_weights"] for f in folds])
        out[key] = {
            "sum_weights_mean": float(sums.mean()),
            "sum_weights_min": float(sums.min()),
            "sum_weights_max": float(sums.max()),
            "share_of_folds_sum_gt_1": float(np.mean(sums > 1.0001)),
        }
    # coefficients of the first fold of every season (trained on all earlier seasons only)
    out["by_season_start"] = {}
    for s in sorted({f["season"] for f in folds}):
        f0 = next(f for f in folds if f["season"] == s)
        out["by_season_start"][int(s)] = {
            k: f0[k] for k in ("ens", "model_only", "ens_cap1", "ens_pool", "mo_cap1")
        }
    out["last_fold"] = {k: folds[-1][k] for k in ("ens", "model_only", "ens_cap1", "ens_pool")}
    out["market_weight_share_ens"] = _market_share(folds, residual=False)
    out["market_plus_residual_share_ens"] = _market_share(folds, residual=True)
    return out


def _market_share(folds: list[dict], residual: bool) -> float:
    """Average share of the logit weight on the market (and on the LightGBM residual vs market)."""
    sh = []
    for f in folds:
        w = dict(zip(f["ens"]["components"], f["ens"]["weights"], strict=True))
        tot = sum(w.values())
        if tot > 0:
            sh.append((w["market"] + (w["lgbm_mkt"] if residual else 0.0)) / tot)
    return float(np.mean(sh))


# ------------------------------------------------------------------ full audit
def audit(df: pd.DataFrame, n_boot: int = BOOT_N) -> tuple[dict, pd.DataFrame]:
    wf, folds = walk_forward(df)
    d = scoring_frame(wf)
    y = outcomes(d)
    keys = [*SCORED, *VARIANTS]
    res: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_version": C.MODEL_VERSION,
        "n_games": int(len(d)),
        "seasons": [int(d["season"].min()), int(d["season"].max())],
        "protocol": (
            "Walk-forward estricto: cada pila se reajusta antes de cada (temporada, semana) solo "
            "con partidos de semanas anteriores (con una aserción de no fuga). Los componentes "
            "Elo, Kalman y LightGBM ya salen del pipeline walk-forward. Empates fuera de las "
            "métricas probabilísticas."
        ),
        "overall": {k: score(d[f"{k}_prob"].to_numpy(float), y) for k in keys},
        "per_season": {},
        "deciles": {k: deciles(d[f"{k}_prob"].to_numpy(float), y) for k in SCORED},
        "favourite_bins": {k: favourite_bins(d[f"{k}_prob"].to_numpy(float), y) for k in keys},
        "heavy_favourites_75": {k: heavy_fav(d[f"{k}_prob"].to_numpy(float), y) for k in keys},
        "heavy_favourites_on_ens_games": heavy_fav_same_games(d, y),
        "input_logit_correlation": input_correlation(d),
        "bootstrap": bootstrap(d, y, n_boot),
        "ats_model_only": ats_block(d, "model_only_margin"),
        "stack_coefficients": weight_summary(folds),
        "folds": folds,
    }
    for s, g in d.groupby("season"):
        yy = outcomes(g)
        res["per_season"][int(s)] = {
            k: score(g[f"{k}_prob"].to_numpy(float), yy) for k in (*SCORED, "ens_cap1", "ens_pool")
        }
    res["extremizing"] = extremizing_verdict(res)
    res["gate"] = {
        "tolerance_log_loss": TOL_LOG_LOSS,
        "tolerance_brier": TOL_BRIER,
        "n_games": res["n_games"],
        **{
            k: {m: res["overall"][k][m] for m in ("log_loss", "brier", "accuracy")}
            for k in ("model_only", "ens", "market")
        },
    }
    return res, d


def extremizing_verdict(res: dict) -> dict:
    o, hf = res["overall"], res["heavy_favourites_on_ens_games"]
    bd = res["bootstrap"]["diff_vs_market"]
    sums = res["stack_coefficients"]["ens"]
    out = {
        "ens_sum_weights_mean": sums["sum_weights_mean"],
        "ens_sum_weights_min": sums["sum_weights_min"],
        "ens_sum_weights_max": sums["sum_weights_max"],
        "ens_sum_gt_1_share_of_folds": sums["share_of_folds_sum_gt_1"],
        "calibration_slope": {k: o[k]["calibration_slope"] for k in [*SCORED, *VARIANTS]},
        "heavy_fav_n": hf["n"],
        "heavy_fav_actual": hf["actual"],
        "heavy_fav_actual_ci95": hf["actual_ci95"],
        "heavy_fav_overconfidence_pp": {
            k: hf[k]["overconfidence_pp"] for k in [*SCORED, "ens_cap1", "ens_pool"]
        },
        "ens_overconfident_beyond_ci": bool(
            hf["n"] and hf["ens"]["pred_mean"] > hf["actual_ci95"][1]
        ),
    }
    for k in ("ens_cap1", "ens_pool"):
        d = bd[f"{k}_minus_ens"]
        out[k] = {
            "log_loss_minus_ens": d["log_loss"],
            "log_loss_ci": d["log_loss_ci"],
            "brier_minus_ens": d["brier"],
            "lower_log_loss": bool(d["log_loss"] < 0),
            "lower_brier": bool(d["brier"] < 0),
            "slope_closer_to_1": bool(
                abs(o[k]["calibration_slope"] - 1) < abs(o["ens"]["calibration_slope"] - 1)
            ),
            "significant": bool(d["log_loss_ci"][1] < 0 or d["log_loss_ci"][0] > 0),
        }
    return out


# ------------------------------------------------------------------ outputs
def finite(o: object) -> object:
    if isinstance(o, dict):
        return {str(k): finite(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [finite(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    return None if isinstance(o, float) and not np.isfinite(o) else o


def write_json(res: dict, path: Path = JSON_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(finite(res), indent=1, ensure_ascii=False, allow_nan=False) + "\n")


def reliability_plot(res: dict, path: Path = PNG_PATH) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"market": "#222222", "model_only": "#c0392b", "ens": "#1f6f8b"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    ax = axes[0]
    ax.plot([0, 1], [0, 1], color="#999999", lw=1, ls="--")
    for k in SCORED:
        t = res["deciles"][k]
        ax.plot(
            [r["pred"] for r in t],
            [r["actual"] for r in t],
            marker="o",
            ms=4,
            lw=1.4,
            color=colors[k],
            label=NAMES[k],
        )
    ax.set_xlabel("Probabilidad prevista de victoria local (media del decil)")
    ax.set_ylabel("Frecuencia real de victoria local")
    ax.set_title("Calibración por deciles (10 grupos de igual tamaño)", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)
    ax = axes[1]
    ax.plot([0.5, 1], [0.5, 1], color="#999999", lw=1, ls="--")
    for k in SCORED:
        t = res["favourite_bins"][k]
        x = [r["pred"] for r in t]
        yv = [r["actual"] for r in t]
        err = [
            [r["actual"] - r["actual_lo"] for r in t],
            [r["actual_hi"] - r["actual"] for r in t],
        ]
        ax.errorbar(
            x, yv, yerr=err, marker="o", ms=4, lw=1.2, capsize=2, color=colors[k], label=NAMES[k]
        )
    ax.axvspan(0.75, 1.0, color="#f1c40f", alpha=0.12)
    ax.set_xlabel("Probabilidad prevista del favorito")
    ax.set_ylabel("Frecuencia real de victoria del favorito (IC 95 %)")
    ax.set_title("Favoritos: zona sombreada = 75 % o más", fontsize=10)
    ax.grid(alpha=0.25)
    ax.set_xlim(0.5, 0.95)
    ax.set_ylim(0.4, 1.0)
    fig.suptitle(
        f"ensemblitz, {res['seasons'][0]}-{res['seasons'][1]}, {res['n_games']} partidos, walk-forward",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def gate_metrics(df: pd.DataFrame) -> dict:
    """Fast recomputation for the CI gate (no bootstrap, no variants beyond what scoring needs)."""
    wf, _ = walk_forward(df)
    d = scoring_frame(wf)
    y = outcomes(d)
    return {
        "n_games": int(len(d)),
        **{
            k: {
                m: score(d[f"{k}_prob"].to_numpy(float), y)[m]
                for m in ("log_loss", "brier", "accuracy")
            }
            for k in ("model_only", "ens", "market")
        },
    }
