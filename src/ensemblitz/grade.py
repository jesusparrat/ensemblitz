"""Grade frozen predictions. Only picks generated before kickoff count."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz.data import load

COMPONENTS = ["market", "elo", "kf", "lgbm", "lgbm_mkt", "ensemble", "ensemble_model_only"]
# Records written before the model-only headline (web v2) published the blended ensemble pick.
LEGACY_HEADLINE = "ensemble"
HEADLINE_COMPONENT = {"model_only": "ensemble_model_only", "ensemble": "ensemble"}


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
        headline = g.get("headline", LEGACY_HEADLINE)
        mo = g.get("model_only")
        pm = mo["margin"] if mo else g["predicted_margin"]
        row = {
            "game_id": g["game_id"],
            "season": g["season"],
            "week": g["week"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "result": margin,
            "total": float(s["total"]),
            "headline": headline,
            "pick": g["pick"],
            "predicted_margin": pm,
            "predicted_total": mo["total"] if mo else g["predicted_total"],
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
            # the graded headline: whichever number was published as the pick
            hc = HEADLINE_COMPONENT.get(headline, "ensemble")
            row["headline_correct"] = row.get(f"{hc}_correct")
        sp = g["market"]["spread_line"]
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
    if "headline_correct" in df:
        d = df.dropna(subset=["headline_correct"])
        out["headline"] = {
            h: {"n": len(x), "accuracy": float(x["headline_correct"].mean())}
            for h, x in d.groupby("headline")
        }
    out["weeks"] = sorted({f"{r['season']}-W{r['week']:02d}" for r in rows})
    return out


LABELS = {
    "ensemble_model_only": "model only (headline)",
    "ensemble": "model blended with the market",
    "market": "market",
}


def summary_md(s: dict) -> str:
    lines = [
        "# Results of the frozen picks",
        "",
        f"Graded games (pick saved before kickoff): {s['n_graded']}",
        "",
        "Since web v2 the headline pick is the model on its own (`ensemble_model_only`). "
        "Earlier picks were the blended ensemble; each graded row records which one it was.",
        "",
    ]
    if s["models"]:
        lines += ["| Source | N | Acierto | Log loss |", "|---|---|---|---|"]
        for c, r in s["models"].items():
            lines.append(
                f"| {LABELS.get(c, c)} | {r['n']} | {r['accuracy'] * 100:.1f}% | {r['log_loss']:.3f} |"
            )
    if "ats" in s:
        lines += ["", f"Against the spread (headline margin): {s['ats']['w']}-{s['ats']['l']}"]
    return "\n".join(lines) + "\n"


__all__ = ["grade_games", "run_grade"]
