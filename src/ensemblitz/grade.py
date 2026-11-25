"""Grade frozen predictions. Only picks generated before kickoff count."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz import contract as K
from ensemblitz import contract_io
from ensemblitz import ledger as L
from ensemblitz.data import load

COMPONENTS = ["market", "elo", "kf", "lgbm", "lgbm_mkt", "ensemble", "ensemble_model_only"]
# Records written before the model-only headline (web v2) published the blended ensemble pick.
LEGACY_HEADLINE = "ensemble"
HEADLINE_COMPONENT = {"model_only": "ensemble_model_only", "ensemble": "ensemble"}


def _view(g: dict, published_at: str | None = None, headline_kind: str | None = None) -> dict:
    """v0 or v1 game → the flat fields the grader already uses.

    ``published_at``, when given, is the ledger/git publication time and is the
    authority for the before-kickoff check. The file's own ``generated_at`` is
    only used when that time is not available (unit tests, a snapshot not yet
    committed).
    """
    if "headline" in g and isinstance(g["headline"], dict):
        h = g["headline"]
        kind = headline_kind or "model_only"
        pm = K.margin_home(h) if kind == "model_only" else g["ensemble"]["margin_home"]
        pt = K.total(h) if kind == "model_only" else g["ensemble"]["total"]
        pick = (
            K.pick(h)
            if kind == "model_only"
            else (g["home_team"] if g["ensemble"]["home_win_prob"] >= 0.5 else g["away_team"])
        )
        nfl = next((q for q in g["market"] if q.get("source") == "nflverse_line"), {})
        hwp = {
            "market": nfl.get("home_win_prob"),
            "elo": g["components"].get("elo"),
            "kf": g["components"].get("kf"),
            "lgbm": g["components"].get("lgbm"),
            "lgbm_mkt": g["components"].get("lgbm_mkt"),
            "ensemble": g["ensemble"]["home_win_prob"],
            "ensemble_model_only": h["home_win_prob"],
        }
        season, week = (None, None)
        parts = g["game_id"].split("_")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            season, week = int(parts[0]), int(parts[1])
        return {
            "game_id": g["game_id"],
            "season": g.get("season", season),
            "week": g.get("week", week),
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "kickoff_utc": g["kickoff_utc"],
            "generated_at": published_at or g.get("generated_at_utc") or g.get("generated_at"),
            "headline": kind,
            "pick": pick,
            "predicted_margin": pm,
            "predicted_total": pt,
            "market": {"spread_line": nfl.get("margin_home")},
            "home_win_prob": hwp,
            "model_only": {
                "margin": K.margin_home(h),
                "total": K.total(h),
                "home_win_prob": h["home_win_prob"],
            },
        }
    out = dict(g)
    if published_at is not None:
        out["generated_at"] = published_at
    return out


def grade_games(
    preds: list[dict],
    schedule: pd.DataFrame,
    published_at: list[str | None] | None = None,
    headline_kind: list[str | None] | None = None,
) -> list[dict]:
    """Return graded rows for finished games whose pick was made before kickoff."""
    res = schedule.set_index("game_id")
    out = []
    for i, raw in enumerate(preds):
        pub = None if published_at is None else published_at[i]
        kind = None if headline_kind is None else headline_kind[i]
        g = _view(raw, pub, kind)
        if g["game_id"] not in res.index:
            continue
        s = res.loc[g["game_id"]]
        if pd.isna(s["result"]) or g["generated_at"] >= g["kickoff_utc"]:
            continue
        margin = float(s["result"])
        headline = g.get("headline", LEGACY_HEADLINE)
        if isinstance(headline, dict):
            headline = "model_only"
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


def run_grade(root: Path | None = None) -> dict:
    """Grade the latest snapshot of each game that was published before kickoff."""
    root = (root or C.ROOT).resolve()
    sched = load.load_schedules()
    # One official pick per game: the latest snapshot published before kickoff.
    by_id: dict[str, tuple[dict, str, str, int, int]] = {}
    for art in L.iter_artifacts(root):
        loaded = contract_io.load_week(art.path)
        published = L.publication_time_utc(art, root)
        for g in loaded.doc["games"]:
            if published >= g["kickoff_utc"]:
                continue
            prev = by_id.get(g["game_id"])
            if prev is None or (published, art.rel) > (prev[1], ""):
                by_id[g["game_id"]] = (
                    g,
                    published,
                    loaded.headline_kind,
                    loaded.doc["season"],
                    loaded.doc["week"],
                )
    # Attach season/week for the grader and group by week for the results files.
    buckets: dict[tuple[int, int], list[tuple[dict, str, str]]] = {}
    for _gid, (g, published, kind, season, week) in by_id.items():
        g = {**g, "season": season, "week": week}
        buckets.setdefault((season, week), []).append((g, published, kind))
    graded: list[dict] = []
    for (season, week), items in sorted(buckets.items()):
        games = [g for g, _, _ in items]
        pubs = [p for _, p, _ in items]
        kinds = [k for _, _, k in items]
        rows = grade_games(games, sched, published_at=pubs, headline_kind=kinds)
        if rows:
            d = C.RESULTS_DIR / str(season)
            d.mkdir(parents=True, exist_ok=True)
            (d / f"week{week:02d}.json").write_text(json.dumps(rows, indent=1))
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
