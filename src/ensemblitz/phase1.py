"""Phase 1: does a per-player injury impact improve the model-only prediction out of sample?

Everything is strict walk-forward over 2018-2025 (the first fits start in 2017):

1. ``mo_margin``   model-only expected margin (Elo + Kalman + LightGBM, no market), phase 0.
2. ``adj``         injury adjustment in spread points: -sum_g beta_g * (X_home,g - X_away,g) where
                   X is the expected points lost (p(miss) x value over replacement, ``impact.py``)
                   and beta_g is a ridge fit on earlier games' residuals (``fit_betas``).
3. margin -> win probability with the empirical discrete margin table (``margin.py``).

Compared on the same games, with paired bootstrap CIs: model-only before (logistic stack) and
after the margin conversion, with and without injuries, and the closing market.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

from ensemblitz import baseline as B
from ensemblitz import config as C
from ensemblitz import impact as I  # noqa: E741
from ensemblitz import margin as MG

FEATS_PATH = C.REPORTS_DIR / "phase1_injury_features.parquet"
HIST_PATH = C.REPORTS_DIR / "phase1_margin_history.parquet"
JSON_PATH = C.REPORTS_DIR / "phase1_injuries.json"
MD_PATH = C.REPORTS_DIR / "PHASE1.md"
PNG_PATH = C.REPORTS_DIR / "phase1_forest.png"
GROUPS = I.BETA_GROUPS
PRIOR_BETA = 0.5
PRIOR_SD = 0.5
SIGMA_E = 13.2
MIN_POOL = 150
FIRST_FIT = 2017
BOOT = 10_000
SEED = 20261
VARIANTS = {
    "A_stack": "Solo modelo, pila logística (fase 0)",
    "B_normal": "Margen del modelo, curva normal",
    "C_discrete": "Margen del modelo, tabla discreta",
    "D_inj": "Margen + lesiones, tabla discreta (candidato)",
    "D_inj_normal": "Margen + lesiones, curva normal",
    "D_total": "Lesiones con un solo coeficiente (exploratorio)",
    "D_binary": "Lesiones sí/no sin probabilidades (exploratorio)",
    "market": "Mercado (cierre sin comisión)",
}


# ------------------------------------------------------------------ inputs
def build_injury_features() -> pd.DataFrame:
    """Compute the per-game injury features from data/ (needs ``ensemblitz update``)."""
    from ensemblitz.data import load

    d = I.load_inputs()
    pg = I.player_games(d["stats"], d["snaps"], d["ids"])
    rows = I.injury_rows(d["inj"], d["snaps"], d["ids"])
    g = load.load_schedules()[["game_id", "season", "week", "home_team", "away_team"]]
    return I.injury_features(g, pg, rows)


def save_inputs(feats: pd.DataFrame) -> None:
    C.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(FEATS_PATH, index=False, compression="zstd")
    MG.history()[["season", "week", "result", "spread_line"]].to_parquet(
        HIST_PATH, index=False, compression="zstd"
    )


def load_inputs_cached() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_parquet(FEATS_PATH), pd.read_parquet(HIST_PATH)


# ------------------------------------------------------------------ fitting
def fit_betas(d: np.ndarray, resid: np.ndarray, lam: float | None = None) -> np.ndarray:
    """Ridge towards PRIOR_BETA for  -resid = D @ beta  (D = home minus away expected points lost)."""
    k = d.shape[1]
    lam = lam if lam is not None else SIGMA_E**2 / PRIOR_SD**2
    a = d.T @ d + lam * np.eye(k)
    b = d.T @ (-resid) + lam * np.full(k, PRIOR_BETA)
    return np.clip(np.linalg.solve(a, b), 0.0, 2.0)


def _diff(df: pd.DataFrame, binary: bool = False) -> np.ndarray:
    t = "b" if binary else ""
    return np.column_stack(
        [df[f"h{t}_{g}"].to_numpy() - df[f"a{t}_{g}"].to_numpy() for g in GROUPS]
    )


def walk_forward(frame: pd.DataFrame, feats: pd.DataFrame, hist: pd.DataFrame) -> tuple:
    """Sequential (season, week) loop producing OOS margins and probabilities for every variant."""
    df = frame.merge(feats, on="game_id", how="inner").sort_values(["season", "week", "game_id"])
    df = df.reset_index(drop=True)
    for c in (
        "adj",
        "adj_total",
        "adj_binary",
        "inj_margin",
        "inj_total_margin",
        "inj_binary_margin",
        "B_normal",
        "C_discrete",
        "D_inj",
        "D_inj_normal",
        "D_total",
        "D_binary",
        "sigma_mo",
        "sigma_inj",
    ):
        df[c] = np.nan
    d_all, d_bin = _diff(df, False), _diff(df, True)
    d_tot = d_all.sum(axis=1, keepdims=True)
    folds = []
    for (season, week), batch in df.groupby(["season", "week"], sort=True):
        if season < FIRST_FIT or week > 18:
            continue
        idx = batch.index.to_numpy()
        ok = batch["model_only_margin"].notna().to_numpy()
        if not ok.any():
            continue
        earlier = ((df["season"] < season) | ((df["season"] == season) & (df["week"] < week))) & df[
            "model_only_margin"
        ].notna()
        pool = df[earlier & df["played"] & df["result"].notna()]
        assert pool.empty or (pool["season"] * 100 + pool["week"]).max() < season * 100 + week
        pi = pool.index.to_numpy()
        resid = (pool["result"] - pool["model_only_margin"]).to_numpy()
        use = len(pool) >= MIN_POOL
        b = fit_betas(d_all[pi], resid) if use else np.full(len(GROUPS), PRIOR_BETA)
        bb = fit_betas(d_bin[pi], resid) if use else np.full(len(GROUPS), PRIOR_BETA)
        bt = fit_betas(d_tot[pi], resid) if use else np.full(1, PRIOR_BETA)
        df.loc[idx, "adj"] = -(d_all[idx] @ b)
        df.loc[idx, "adj_binary"] = -(d_bin[idx] @ bb)
        df.loc[idx, "adj_total"] = -(d_tot[idx] @ bt)
        mo = batch["model_only_margin"].to_numpy()
        df.loc[idx, "inj_margin"] = mo + df.loc[idx, "adj"].to_numpy()
        df.loc[idx, "inj_binary_margin"] = mo + df.loc[idx, "adj_binary"].to_numpy()
        df.loc[idx, "inj_total_margin"] = mo + df.loc[idx, "adj_total"].to_numpy()
        # residual spread of earlier OOS margins (with and without injuries), 13.4 until 150 games
        done = df.loc[earlier & df["played"] & df["inj_margin"].notna()]
        if len(done) >= MIN_POOL:
            s_mo = float(np.std(done["result"] - done["model_only_margin"]))
            s_in = float(np.std(done["result"] - done["inj_margin"]))
        else:
            s_mo = s_in = 13.4
        mdl = MG.fit_before(hist, season, week)
        df.loc[idx, "sigma_mo"], df.loc[idx, "sigma_inj"] = s_mo, s_in
        df.loc[idx, "B_normal"] = ndtr(mo / s_mo)
        df.loc[idx, "C_discrete"] = mdl.prob_home(mo, s_mo)
        df.loc[idx, "D_inj"] = mdl.prob_home(df.loc[idx, "inj_margin"].to_numpy(), s_in)
        df.loc[idx, "D_inj_normal"] = ndtr(df.loc[idx, "inj_margin"].to_numpy() / s_in)
        df.loc[idx, "D_total"] = mdl.prob_home(df.loc[idx, "inj_total_margin"].to_numpy(), s_in)
        df.loc[idx, "D_binary"] = mdl.prob_home(df.loc[idx, "inj_binary_margin"].to_numpy(), s_in)
        folds.append(
            {
                "season": int(season),
                "week": int(week),
                "n_pool": int(len(pool)),
                "betas": dict(zip(GROUPS, np.round(b, 4).tolist(), strict=True)),
                "beta_total": round(float(bt[0]), 4),
                "sigma_mo": round(s_mo, 3),
                "w3": round(float(mdl.w[3]), 3),
                "w7": round(float(mdl.w[7]), 3),
            }
        )
    df["A_stack"] = df["model_only_prob"]
    df["market"] = df["market_prob"]
    return df, folds


# ------------------------------------------------------------------ evaluation
def _ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return B._ll(np.asarray(p, float), y)


def paired(d: pd.DataFrame, y: np.ndarray, pairs: list[tuple[str, str]], n: int = BOOT) -> dict:
    """Paired bootstrap over games of mean(loss_a - loss_b) for log loss, Brier and accuracy."""
    rng = np.random.default_rng(SEED)
    names = sorted({x for p in pairs for x in p})
    ll = {k: _ll(d[k].to_numpy(float), y) for k in names}
    br = {k: (np.clip(d[k].to_numpy(float), 1e-4, 1 - 1e-4) - y) ** 2 for k in names}
    ac = {k: ((d[k].to_numpy(float) > 0.5) == (y == 1)).astype(float) for k in names}
    acc: dict[str, list[np.ndarray]] = {}
    done = 0
    while done < n:
        b = min(1000, n - done)
        ix = rng.integers(0, len(y), size=(b, len(y)), dtype=np.int32)
        for a, c in pairs:
            for tag, src in (("ll", ll), ("br", br), ("ac", ac)):
                acc.setdefault(f"{tag}|{a}|{c}", []).append((src[a][ix] - src[c][ix]).mean(axis=1))
        done += b
    out = {}
    for a, c in pairs:
        r = {}
        for tag, src in (("ll", ll), ("br", br), ("ac", ac)):
            s = np.concatenate(acc[f"{tag}|{a}|{c}"])
            r[tag] = {
                "diff": float((src[a] - src[c]).mean()),
                "ci": [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))],
            }
        r["p_a_better"] = float(
            np.mean(np.concatenate(acc[f"ll|{a}|{c}"]) < 0)
        )  # share of resamples where a has lower log loss
        out[f"{a}__minus__{c}"] = r
    return out


def mse_diff(d: pd.DataFrame, a: str, c: str, n: int = BOOT) -> dict:
    """Paired bootstrap of the squared margin error (more power than win/loss)."""
    rng = np.random.default_rng(SEED + 1)
    ea = (d["result"] - d[a]).to_numpy() ** 2
    ec = (d["result"] - d[c]).to_numpy() ** 2
    diff = ea - ec
    ix = rng.integers(0, len(diff), size=(n, len(diff)), dtype=np.int32)
    s = diff[ix].mean(axis=1)
    return {
        "mse_a": float(ea.mean()),
        "mse_c": float(ec.mean()),
        "diff": float(diff.mean()),
        "ci": [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))],
        "mae_a": float(np.mean(np.sqrt(ea))),
        "mae_c": float(np.mean(np.sqrt(ec))),
    }


def scores(d: pd.DataFrame, y: np.ndarray) -> dict:
    return {k: B.score(d[k].to_numpy(float), y) for k in VARIANTS}


def ols_coefficients(d: pd.DataFrame) -> dict:
    """Unpenalised full-sample fit of -(result - model_only_margin) on the group burdens (diagnostic)."""
    x = _diff(d)
    y = -(d["result"] - d["model_only_margin"]).to_numpy()
    xt = np.column_stack([x, np.ones(len(x))])
    coef, *_ = np.linalg.lstsq(xt, y, rcond=None)
    res = y - xt @ coef
    cov = np.linalg.inv(xt.T @ xt) * (res @ res) / (len(y) - xt.shape[1])
    se = np.sqrt(np.diag(cov))
    out = {
        g: {
            "beta": float(coef[i]),
            "se": float(se[i]),
            "ci95": [float(coef[i] - 1.96 * se[i]), float(coef[i] + 1.96 * se[i])],
            "mean_abs_burden": float(np.abs(x[:, i]).mean()),
            "sd_burden": float(x[:, i].std()),
        }
        for i, g in enumerate(GROUPS)
    }
    tot = x.sum(axis=1)
    xt1 = np.column_stack([tot, np.ones(len(tot))])
    c1, *_ = np.linalg.lstsq(xt1, y, rcond=None)
    r1 = y - xt1 @ c1
    s1 = np.sqrt(np.diag(np.linalg.inv(xt1.T @ xt1) * (r1 @ r1) / (len(y) - 2)))
    out["total"] = {"beta": float(c1[0]), "se": float(s1[0])}
    return out


def ols_vs_market(d: pd.DataFrame) -> dict:
    """Do injuries explain what the closing spread misses? Regress (result - spread) on burdens."""
    x = _diff(d)
    y = -(d["result"] - d["spread_line"]).to_numpy()
    out = {}
    for name, xm in (("grupos", x), ("total", x.sum(axis=1, keepdims=True))):
        xt = np.column_stack([xm, np.ones(len(xm))])
        c, *_ = np.linalg.lstsq(xt, y, rcond=None)
        r = y - xt @ c
        se = np.sqrt(np.diag(np.linalg.inv(xt.T @ xt) * (r @ r) / (len(y) - xt.shape[1])))
        labels = GROUPS if name == "grupos" else ["total"]
        out[name] = {lab: {"beta": float(c[i]), "se": float(se[i])} for i, lab in enumerate(labels)}
    return out


def availability_summary(rows: pd.DataFrame, season: int, week: int) -> dict:
    """p(play) table estimated from every week before (season, week)."""
    av = I.Availability(rows, int(I.tau(season, week)))
    cells = {}
    for lab in ("Out", "Doubtful", "Questionable", "Probable"):
        for pr in ("full", "limited", "dnp"):
            if (lab, pr) in av.l2.index:
                cells[f"{lab}|{pr}"] = {
                    "n": int(av.l2.loc[(lab, pr), "count"]),
                    "p_play": av.p_play(lab, pr, "WR"),
                    "p_play_qb": av.p_play(lab, pr, "QB"),
                    "p_play_cb": av.p_play(lab, pr, "CB"),
                    "p_play_ol": av.p_play(lab, pr, "OL"),
                }
    return {"estimated_before": f"{season} semana {week}", "cells": cells, "base": av.base}


def audit(frame: pd.DataFrame, feats: pd.DataFrame, hist: pd.DataFrame, n_boot: int = BOOT):
    base_wf, _ = B.walk_forward(frame, first=FIRST_FIT)
    wf, folds = walk_forward(base_wf, feats, hist)
    cols = [*VARIANTS, "inj_margin", "model_only_margin", "adj", "spread_line", "result"]
    d = wf[wf["season"].between(C.FIRST_BACKTEST_SEASON, C.LAST_BACKTEST_SEASON)]
    d = d[d["played"] & (d["week"] <= 18) & d["game_id"].str.contains(B.REG_ID)]
    d = d.dropna(subset=cols)
    d = d[d["result"] != 0].reset_index(drop=True)
    y = B.outcomes(d)
    pairs = [
        ("D_inj", "C_discrete"),
        ("C_discrete", "B_normal"),
        ("D_inj", "A_stack"),
        ("C_discrete", "A_stack"),
        ("D_inj", "market"),
        ("C_discrete", "market"),
        ("A_stack", "market"),
        ("D_inj", "D_inj_normal"),
        ("D_total", "C_discrete"),
        ("D_binary", "C_discrete"),
        ("D_binary", "D_inj"),
    ]
    big = d[d["adj"].abs() >= 1.0].reset_index(drop=True)
    res: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_games": int(len(d)),
        "seasons": [int(d["season"].min()), int(d["season"].max())],
        "overall": scores(d, y),
        "paired_bootstrap": paired(d, y, pairs, n_boot),
        "margin_error": {
            "injuries_vs_without": mse_diff(d, "inj_margin", "model_only_margin", n_boot),
            "market_spread_vs_model_only": mse_diff(d, "spread_line", "model_only_margin", n_boot),
        },
        "ats": {
            "without_injuries": B.ats_block(d, "model_only_margin"),
            "with_injuries": B.ats_block(d, "inj_margin"),
        },
        "per_season": {
            int(s): {k: B.score(g[k].to_numpy(float), B.outcomes(g)) for k in VARIANTS}
            for s, g in d.groupby("season")
        },
        "adjustment": {
            "mean_abs_points": float(d["adj"].abs().mean()),
            "p90_abs_points": float(d["adj"].abs().quantile(0.9)),
            "max_abs_points": float(d["adj"].abs().max()),
            "games_abs_ge_1": int(len(big)),
            "games_abs_ge_2": int((d["adj"].abs() >= 2).sum()),
        },
        "subset_big_adjustment": {},
        "ols_full_sample": ols_coefficients(d),
        "ols_vs_market_spread": ols_vs_market(d),
        "betas_by_season_start": {},
        "folds": folds,
    }
    if len(big) >= 100:
        yb = B.outcomes(big)
        res["subset_big_adjustment"] = {
            "n": int(len(big)),
            "paired": paired(big, yb, [("D_inj", "C_discrete")], n_boot),
            "mse": mse_diff(big, "inj_margin", "model_only_margin", n_boot),
        }
    late = d[d["season"] >= 2020].reset_index(drop=True)
    res["exploratory_2020_2025"] = {
        "n": int(len(late)),
        "paired": paired(late, B.outcomes(late), [("D_inj", "C_discrete")], n_boot),
        "note": "periodo elegido después de ver los resultados por temporada: solo orientativo",
    }
    for s in sorted({f["season"] for f in folds if f["season"] >= C.FIRST_BACKTEST_SEASON}):
        f0 = next(f for f in folds if f["season"] == s)
        res["betas_by_season_start"][int(s)] = f0["betas"]
    res["betas_last_fold"] = folds[-1]["betas"]
    res["verdict"] = verdict(res)
    mdl = MG.fit_before(hist, C.LAST_BACKTEST_SEASON + 1, 1)
    res["margin_table"] = margin_table(mdl, hist)
    return res, d


def verdict(res: dict) -> dict:
    pb = res["paired_bootstrap"]["D_inj__minus__C_discrete"]
    lo, hi = pb["ll"]["ci"]
    me = res["margin_error"]["injuries_vs_without"]
    improves = bool(pb["ll"]["diff"] < 0)
    significant = bool(hi < 0)
    return {
        "primary_comparison": "D_inj menos C_discrete (mismos partidos, misma conversión)",
        "log_loss_diff": pb["ll"]["diff"],
        "log_loss_ci": [lo, hi],
        "improves_point_estimate": improves,
        "significant_at_95": significant,
        "margin_mse_diff": me["diff"],
        "margin_mse_ci": me["ci"],
        "margin_mse_significant": bool(me["ci"][1] < 0),
        "wire_into_production": significant,
    }


def margin_table(mdl: MG.MarginModel, hist: pd.DataFrame) -> dict:
    """Win and cover probabilities at the line (table vs normal) and the observed cover rate."""
    lines = [1.5, 2.5, 3.5, 4.5, 6.5, 7.5, 9.5, 10.5]
    m = np.array(lines)
    cover_disc = mdl.prob_cover(m, m)
    obs = []
    for ln in lines:
        g = hist[hist["spread_line"].abs() == ln]
        fav_margin = np.where(g["spread_line"] > 0, g["result"], -g["result"])
        obs.append({"n": int(len(g)), "cover": float(np.mean(fav_margin > ln)) if len(g) else None})
    return {
        "sigma": mdl.sigma,
        "tilt_w": {str(k): float(mdl.w[k]) for k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 17)},
        "expected_margin_lines": lines,
        "p_win_discrete": mdl.prob_home(m).tolist(),
        "p_win_normal": ndtr(m / mdl.sigma).tolist(),
        "p_cover_at_own_line_discrete": cover_disc.tolist(),
        "p_cover_at_own_line_normal": ndtr((m - m) / mdl.sigma).tolist(),
        "observed_favourite_cover": obs,
    }


# ------------------------------------------------------------------ outputs
def write_json(res: dict, path: Path = JSON_PATH) -> None:
    path.write_text(json.dumps(B.finite(res), indent=1, ensure_ascii=False, allow_nan=False) + "\n")


def forest_plot(res: dict, path: Path = PNG_PATH) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [
        ("Lesiones frente a sin lesiones\n(tabla discreta)", "D_inj__minus__C_discrete"),
        ("Tabla discreta frente a curva normal\n(sin lesiones)", "C_discrete__minus__B_normal"),
        ("Candidato frente a pila de la fase 0", "D_inj__minus__A_stack"),
        ("Candidato frente al mercado", "D_inj__minus__market"),
        ("Sin lesiones frente al mercado", "C_discrete__minus__market"),
        ("Pila fase 0 frente al mercado", "A_stack__minus__market"),
    ]
    pb = res["paired_bootstrap"]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for i, (_lab, k) in enumerate(rows[::-1]):
        d = pb[k]["ll"]
        ax.errorbar(
            d["diff"],
            i,
            xerr=[[d["diff"] - d["ci"][0]], [d["ci"][1] - d["diff"]]],
            fmt="o",
            color="#1f6f8b",
            capsize=3,
        )
    ax.axvline(0, color="#999", lw=1, ls="--")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=8)
    ax.set_xlabel("Diferencia de log loss (negativo = el primero es mejor), IC 95 %")
    ax.set_title(f"Fase 1, {res['n_games']} partidos 2018-2025, walk-forward", fontsize=10)
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
