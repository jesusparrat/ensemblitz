"""Walk-forward backtest 2018-2025 and its report."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz import metrics as M
from ensemblitz import pipeline as P
from ensemblitz.sim import SimParams, simulate_games, summarize_sim

log = logging.getLogger(__name__)

COMPONENTS = ["market", "elo", "kf", "lgbm", "lgbm_mkt", "sim", "ens"]
LABELS = {
    "market": "Mercado (cierre)",
    "elo": "Elo (MOV)",
    "kf": "Kalman (fuerza dinámica)",
    "lgbm": "LightGBM (sin mercado)",
    "lgbm_mkt": "LightGBM (residuo vs mercado)",
    "sim": "Simulador (params Kalman)",
    "ens": "Ensemble",
}


def add_sim_component(df: pd.DataFrame, n_sims: int = 3000, chunk: int = 60) -> pd.DataFrame:
    """Simulator fed by the Kalman expected points (a score-distribution check, not stacked)."""
    df = df.copy()
    df["sim_prob"] = np.nan
    df["sim_margin"] = np.nan
    idx = df.index[
        df["kf_pts_h"].notna() & df["played"] & (df["season"] >= C.FIRST_BACKTEST_SEASON)
    ]
    for i in range(0, len(idx), chunk):
        sl = idx[i : i + chunk]
        h, a = simulate_games(
            df.loc[sl, "kf_pts_h"].to_numpy(),
            df.loc[sl, "kf_pts_a"].to_numpy(),
            n_sims=n_sims,
            seed=i,
            params=SimParams(),
        )
        s = summarize_sim(h, a)
        df.loc[sl, "sim_prob"] = s["p_home"]
        df.loc[sl, "sim_margin"] = s["margin_mean"]
    return df


def run(last: int = C.LAST_BACKTEST_SEASON, refit: bool = False) -> tuple[pd.DataFrame, dict]:
    feats = P.make_features()
    feats, kf_params = P.add_kf(
        feats, int(feats["season"].max()), stored=None if refit else P.load_kf_params()
    )
    P.save_kf_params(kf_params)
    feats = P.add_components_static(feats)
    feats = P.add_gbm_components(feats)
    feats = P.add_ensemble_walk_forward(feats, last=last)
    feats = add_sim_component(feats)
    test = feats[
        feats["season"].between(C.FIRST_BACKTEST_SEASON, last)
        & feats["played"]
        & (feats["game_id"].str.contains(r"^\d{4}_\d{2}_"))
    ]
    reg = test[test["week"] <= 18]
    C.PROC_DIR.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(C.PROC_DIR / "backtest_frame.parquet", index=False)
    results = build_results(reg, kf_params)
    return reg, results


def build_results(reg: pd.DataFrame, kf_params: dict | None = None) -> dict:
    res: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_version": C.MODEL_VERSION,
        "n_games": int(len(reg)),
        "seasons": [int(reg.season.min()), int(reg.season.max())],
        "overall": {},
        "per_season": {},
        "calibration": {},
        "kf_params": kf_params or {},
    }
    for c in COMPONENTS:
        sub = reg.dropna(subset=[f"{c}_prob", f"{c}_margin"])
        res["overall"][c] = M.summarize(sub, c)
    mk = reg.dropna(subset=["ens_prob", "ens_total"])
    res["total_mae"] = {
        "ens": float(np.mean(np.abs(mk["ens_total"] - mk["total"]))),
        "market_total_line": float(np.mean(np.abs(mk["total_line"] - mk["total"]))),
        "kf": float(np.mean(np.abs(mk["kf_total"] - mk["total"]))),
    }
    for s, d in reg.groupby("season"):
        res["per_season"][int(s)] = {
            c: M.summarize(d.dropna(subset=[f"{c}_prob"]), c)
            for c in ("market", "kf", "lgbm", "ens")
        }
    res["calibration"] = {c: M.calibration_table(reg, f"{c}_prob") for c in ("ens", "market")}
    return res


def _finite(o: object) -> object:
    """NaN/Inf are not valid JSON (browsers and strict parsers reject them): store null."""
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_finite(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    return None if isinstance(o, float) and not np.isfinite(o) else o


def _json_default(o: object) -> object:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


def _fmt(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}"


def write_report(results: dict, extra_md: str = "") -> None:
    C.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (C.REPORTS_DIR / "backtest.json").write_text(
        json.dumps(_finite(results), indent=2, default=_json_default, allow_nan=False)
    )
    ov = results["overall"]
    lines = [
        "# Backtest walk-forward",
        "",
        f"Temporadas {results['seasons'][0]}–{results['seasons'][1]}, {results['n_games']} partidos "
        f"de temporada regular. Para cada semana, todo (ratings, Kalman, LightGBM, pesos del "
        f"ensemble) se calcula solo con partidos anteriores. Generado: {results['generated_at']}.",
        "",
        "## Global por modelo",
        "",
        "| Modelo | Acierto | Brier | Log loss | MAE margen | ATS (G-P) | ATS % |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in COMPONENTS:
        r = ov[c]
        a = r["ats"]
        ats_txt = "—" if c == "market" else f"{a['w']}-{a['l']}-{a['push']}"
        ats_pct = "—" if c == "market" else f"{a['win_pct'] * 100:.1f}%"
        lines.append(
            f"| {LABELS[c]} | {r['accuracy'] * 100:.1f}% | {_fmt(r['brier'])} | {_fmt(r['log_loss'])} | "
            f"{_fmt(r['mae_margin'], 2)} | {ats_txt} | {ats_pct} |"
        )
    tm = results["total_mae"]
    lines += [
        "",
        f"MAE del total de puntos: ensemble {tm['ens']:.2f}, línea de total del mercado "
        f"{tm['market_total_line']:.2f}, Kalman {tm['kf']:.2f}.",
        "",
        "## Por temporada (acierto / Brier / log loss / ATS%)",
        "",
        "| Temporada | Mercado | Kalman | LightGBM | Ensemble |",
        "|---|---|---|---|---|",
    ]
    for s, d in results["per_season"].items():
        cells = []
        for c in ("market", "kf", "lgbm", "ens"):
            r = d[c]
            ats_pct = "—" if c == "market" else f"{r['ats']['win_pct'] * 100:.1f}%"
            cells.append(
                f"{r['accuracy'] * 100:.1f}% / {_fmt(r['brier'])} / {_fmt(r['log_loss'])} / "
                f"{ats_pct}"
            )
        lines.append(f"| {s} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Calibración del ensemble",
        "",
        "| Tramo | N | Prob. media | Acierto real |",
        "|---|---|---|---|",
    ]
    for r in results["calibration"]["ens"]:
        lines.append(
            f"| {r['bin']} | {r['n']} | {r['pred'] * 100:.1f}% | {r['actual'] * 100:.1f}% |"
        )
    if extra_md:
        lines += ["", extra_md]
    lines += [
        "",
        "ATS = contra el spread de cierre, apostando el lado que el modelo prefiere "
        "(G = ganadas, P = perdidas, empates = push). El ensemble coincide con el spread en muchos partidos (el mercado pesa casi todo), y ahí no hay apuesta, por eso su N es menor. El simulador usa los puntos esperados "
        "del Kalman y no entra en el ensemble.",
    ]
    (C.REPORTS_DIR / "backtest.md").write_text("\n".join(lines) + "\n")
