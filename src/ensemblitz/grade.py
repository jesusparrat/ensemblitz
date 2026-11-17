"""Grade frozen predictions. Only picks generated before kickoff count."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz.data import load

COMPONENTS = ["market", "elo", "kf", "lgbm", "lgbm_mkt", "ensemble"]


def grade_games(preds: list[dict], schedule: pd.DataFrame) -> list[dict]:
    """Return graded rows for finished games whose pick was made before kickoff."""
    res = schedule.set_index("game_id")
    out = []
    for g in preds:
        if g["game_id"] not in res.index:
            continue
        s = res.loc[g["game_id"]]
        if pd.isna(s["result"]) or g["generated_at"] >= g["kickoff_utc"]:
            continue
        margin = float(s["result"])
        row = {
            "game_id": g["game_id"],
            "season": g["season"],
            "week": g["week"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "result": margin,
            "total": float(s["total"]),
            "pick": g["pick"],
            "predicted_margin": g["predicted_margin"],
            "predicted_total": g["predicted_total"],
            "spread_line": g["market"]["spread_line"],
        }
        if margin != 0:
            y = float(margin > 0)
            for c in COMPONENTS:
                p = g["home_win_prob"].get(c)
                if p is None:
                    continue
                p = float(np.clip(p, 1e-4, 1 - 1e-4))
                row[f"{c}_correct"] = int((p > 0.5) == (y == 1))
                row[f"{c}_logloss"] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)))
        sp, pm = g["market"]["spread_line"], g["predicted_margin"]
        if sp is not None and pm is not None and pm != sp and margin != sp:
            row["ats_win"] = int(((margin - sp) > 0) == (pm > sp))
        out.append(row)
    return out


def run_grade() -> dict:
    sched = load.load_schedules()
    graded: list[dict] = []
    for path in sorted(C.PRED_DIR.glob("*/week*.json")):
        data = json.loads(path.read_text())
        rows = grade_games(data["games"], sched)
        if rows:
            d = C.RESULTS_DIR / str(data["season"])
            d.mkdir(parents=True, exist_ok=True)
            (d / path.name).write_text(json.dumps(rows, indent=1))
            graded += rows
    summary = summarize(graded)
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (C.RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=1))
    (C.RESULTS_DIR / "summary.md").write_text(summary_md(summary))
    return summary


def summarize(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    out: dict = {"n_graded": len(df), "models": {}}
    if df.empty:
        return out
    for c in COMPONENTS:
        if f"{c}_correct" in df:
            d = df.dropna(subset=[f"{c}_correct"])
            out["models"][c] = {
                "n": len(d),
                "accuracy": float(d[f"{c}_correct"].mean()),
                "log_loss": float(d[f"{c}_logloss"].mean()),
            }
    if "ats_win" in df:
        d = df.dropna(subset=["ats_win"])
        out["ats"] = {"w": int(d["ats_win"].sum()), "l": int(len(d) - d["ats_win"].sum())}
    out["weeks"] = sorted({f"{r['season']}-W{r['week']:02d}" for r in rows})
    return out


def summary_md(s: dict) -> str:
    lines = [
        "# Resultados de los picks congelados",
        "",
        f"Partidos calificados (pick generado antes del kickoff): {s['n_graded']}",
        "",
    ]
    if s["models"]:
        lines += ["| Modelo | N | Acierto | Log loss |", "|---|---|---|---|"]
        for c, r in s["models"].items():
            lines.append(f"| {c} | {r['n']} | {r['accuracy'] * 100:.1f}% | {r['log_loss']:.3f} |")
    if "ats" in s:
        lines += ["", f"ATS del ensemble: {s['ats']['w']}-{s['ats']['l']}"]
    return "\n".join(lines) + "\n"


__all__ = ["grade_games", "run_grade"]
