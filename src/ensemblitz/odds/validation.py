"""Does the model beat the closing line? Disagreement-threshold analysis on the backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ensemblitz.models.market import ml_to_prob

THRESHOLDS = (0.0, 0.03, 0.05, 0.08)
MODELS = {
    "ens": "Ensemble",
    "lgbm_mkt": "LightGBM (residuo)",
    "lgbm": "LightGBM (sin mercado)",
    "kf": "Kalman",
}
BREAKEVEN_110 = 110 / 210  # 52.38% needed to win at -110


def _ll(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def subset_stats(d: pd.DataFrame, comp: str, t: float) -> dict:
    """Stats on games where |model prob - market prob| > t, betting the side the model likes."""
    d = d.dropna(
        subset=[
            f"{comp}_prob",
            "market_prob",
            "result",
            "spread_line",
            "home_moneyline",
            "away_moneyline",
        ]
    )
    d = d[d["result"] != 0]
    diff = d[f"{comp}_prob"] - d["market_prob"]
    d = d[diff.abs() > t]
    diff = diff[d.index]
    n = len(d)
    if n == 0:
        return {"threshold": t, "n": 0}
    home = (diff > 0).to_numpy()
    y_home = (d["result"] > 0).to_numpy(float)
    side_win = np.where(home, y_home, 1 - y_home)
    p_model = d[f"{comp}_prob"].to_numpy()
    p_mkt = d["market_prob"].to_numpy()
    mkt_side = np.where(home, p_mkt, 1 - p_mkt)
    # flat stake at closing moneyline (with vig)
    price = 1.0 / np.where(home, ml_to_prob(d["home_moneyline"]), ml_to_prob(d["away_moneyline"]))
    roi_ml = float(np.mean(np.where(side_win == 1, price - 1.0, -1.0)))
    # ATS at -110
    cover = (d["result"] - d["spread_line"]).to_numpy()
    nopush = cover != 0
    ats_win = np.where(home, cover > 0, cover < 0)[nopush]
    w, l_ = int(ats_win.sum()), int((~ats_win).sum())
    ats_pct = w / (w + l_) if w + l_ else float("nan")
    se = np.sqrt(ats_pct * (1 - ats_pct) / (w + l_)) if w + l_ else float("nan")
    roi_ats = (w * (100 / 110) - l_) / (w + l_) if w + l_ else float("nan")
    se_hit = np.sqrt(0.25 / n)
    return {
        "threshold": t,
        "n": n,
        "su_hit_rate": float(side_win.mean()),
        "su_hit_ci95": float(1.96 * se_hit),
        "market_expected_hit_rate": float(mkt_side.mean()),
        "log_loss_model": _ll(p_model, y_home),
        "log_loss_market": _ll(p_mkt, y_home),
        "ats_w": w,
        "ats_l": l_,
        "ats_pct": float(ats_pct),
        "ats_ci95": float(1.96 * se),
        "ats_roi_flat_110": float(roi_ats),
        "ml_roi_flat": roi_ml,
    }


def validate(reg: pd.DataFrame) -> dict:
    """Return {"json": ..., "md": ...} for the backtest report."""
    out: dict = {}
    for comp in MODELS:
        out[comp] = [subset_stats(reg, comp, t) for t in THRESHOLDS]
    verdict = _verdict(out)
    md = [
        "## ¿Le ganamos a la línea de cierre?",
        "",
        "Para cada modelo, partidos donde su probabilidad difiere de la del mercado (sin margen) más "
        "de un umbral; se apuesta siempre el lado que el modelo prefiere con 1 unidad plana. "
        "`ATS` = contra el spread a −110 (se necesita 52,4 % para no perder). `ROI ML` = a la "
        "cuota de cierre real de moneyline (con comisión). `IC95` = intervalo de confianza del "
        "porcentaje. `Hit` = acierto directo del lado elegido frente a lo que el mercado esperaba "
        "de ese mismo lado.",
        "",
    ]
    md += [
        "| Modelo | Umbral | N | Hit (esperado mercado) | Log loss modelo / mercado | ATS | ATS % ±IC95 | ROI ATS −110 | ROI ML |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for comp, rows in out.items():
        for r in rows:
            if r["n"] == 0:
                continue
            thr = "todos" if r["threshold"] == 0 else f">{r['threshold'] * 100:.0f} pp"
            md.append(
                f"| {MODELS[comp]} | {thr} | {r['n']} | {r['su_hit_rate'] * 100:.1f}% "
                f"({r['market_expected_hit_rate'] * 100:.1f}%) | {r['log_loss_model']:.3f} / "
                f"{r['log_loss_market']:.3f} | {r['ats_w']}-{r['ats_l']} | {r['ats_pct'] * 100:.1f}% "
                f"±{r['ats_ci95'] * 100:.1f} | {r['ats_roi_flat_110'] * 100:+.1f}% | "
                f"{r['ml_roi_flat'] * 100:+.1f}% |"
            )
    md += ["", f"**Conclusión:** {verdict}"]
    return {"json": {"tables": out, "verdict": verdict}, "md": "\n".join(md)}


def _verdict(out: dict) -> str:
    e_all = out["ens"][0]
    parts = []
    d_ll = e_all["log_loss_model"] - e_all["log_loss_market"]
    parts.append(
        f"en todos los partidos el ensemble tiene log loss {e_all['log_loss_model']:.3f} frente a "
        f"{e_all['log_loss_market']:.3f} del mercado ({d_ll:+.4f}; menor es mejor)"
    )
    wins = []
    for comp, rows in out.items():
        for r in rows[1:]:
            if r["n"] and r["ats_pct"] - r["ats_ci95"] > BREAKEVEN_110:
                wins.append(f"{MODELS[comp]} >{r['threshold'] * 100:.0f} pp")
    if d_ll < 0 and wins:
        parts.append(
            "hay subconjuntos con ATS por encima del punto de equilibrio incluso en el límite "
            "inferior del IC95: " + ", ".join(wins) + ". Hay que confirmarlo fuera de muestra "
            "antes de creérselo"
        )
    else:
        parts.append(
            "ningún modelo supera el punto de equilibrio de 52,4 % ATS con significancia "
            "(IC95 incluye o queda por debajo de él) y ninguno mejora al mercado en log loss de "
            "forma clara: **no hay evidencia de que le ganemos a la línea de cierre**. "
            "El valor de v0.1 está en las probabilidades calibradas y la distribución de "
            "marcadores, no en una ventaja contra el mercado"
        )
    return "; ".join(parts) + "."
