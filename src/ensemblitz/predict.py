"""Predict upcoming games and freeze the picks as JSON."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz import news as N
from ensemblitz import pipeline as P
from ensemblitz.features.build import feature_columns
from ensemblitz.models import gbm
from ensemblitz.models.ensemble import Ensemble
from ensemblitz.models.market import implied_spread, margin_to_prob
from ensemblitz.sim import SimParams, likely_score, simulate_games, summarize_sim

log = logging.getLogger(__name__)


def pred_path(season: int, week: int) -> Path:
    return C.PRED_DIR / str(season) / f"week{week:02d}.json"


def next_weeks(feats: pd.DataFrame, season: int, n: int = 1) -> list[int]:
    s = feats[(feats["season"] == season) & ~feats["played"]]
    return [int(w) for w in sorted(s["week"].unique())[:n]]


def fill_missing_spread(feats: pd.DataFrame) -> pd.DataFrame:
    """Unplayed games with moneylines but no spread get the spread those moneylines imply.

    nflverse sometimes publishes the moneylines and total of an upcoming game before (or without)
    the spread. Without a spread the stack silently fell back to the no-market model, so the pick
    could sit 16 points away from a market that was right there in the same row (2026 week 12,
    NYJ at MIA). The market components only need a margin, and the moneyline gives one.
    """
    missing = (~feats["played"]) & feats["spread_line"].isna()
    implied = implied_spread(feats["home_moneyline"], feats["away_moneyline"])
    fill = missing & pd.Series(implied, index=feats.index).notna()
    if fill.any():
        feats = feats.copy()
        feats.loc[fill, "spread_line"] = np.round(implied[fill.to_numpy()] * 2) / 2
        log.info("spread implied from moneylines for %d game(s)", int(fill.sum()))
    return feats


def build_frame(season: int) -> pd.DataFrame:
    """Features + every component for all games up to ``season`` (future games included)."""
    feats = P.make_features()
    feats = feats[feats["season"] <= season]
    feats = fill_missing_spread(feats)
    feats, _ = P.add_kf(feats, season, stored=P.load_kf_params())
    feats = P.add_components_static(feats)
    return P.add_gbm_components(feats)


def predict_frame(frame: pd.DataFrame, season: int, weeks: list[int]) -> pd.DataFrame:
    """Components + ensemble + simulator for the given unplayed weeks."""
    df = frame.copy()
    target = df[(df["season"] == season) & df["week"].isin(weeks) & ~df["played"]]
    train = df[df["played"] & df["result"].notna()]
    df.loc[target.index, "lgbm_margin"] = gbm.fit_predict(
        train, target, feature_columns(False), False
    )
    df.loc[target.index, "lgbm_mkt_margin"] = gbm.fit_predict(
        train, target, feature_columns(True), True
    )
    for c in ("lgbm", "lgbm_mkt"):
        df[f"{c}_prob"] = margin_to_prob(df[f"{c}_margin"])
    need = ["market_prob", "elo_prob", "kf_prob", "lgbm_prob", "lgbm_mkt_prob"]
    pool = df[df["played"] & (df["season"] >= C.WARMUP_SEASON)].dropna(subset=need)
    ens = Ensemble(pool)
    out = df.loc[target.index].copy()
    out[["ens_prob", "ens_margin", "ens_total"]] = ens.predict(out).to_numpy()
    nm = ens.no_market
    out["nomkt_prob"] = nm.prob(out)
    out["nomkt_margin"] = nm.margin(out)
    out.attrs["ensemble_weights"] = ens.weights()
    return out


def simulate_rows(rows: pd.DataFrame, n_sims: int = 20000) -> dict[str, np.ndarray]:
    total = rows["ens_total"].to_numpy()
    margin = rows["ens_margin"].to_numpy()
    h, a = simulate_games(
        (total + margin) / 2, (total - margin) / 2, n_sims=n_sims, seed=2026, params=SimParams()
    )
    out = summarize_sim(h, a)
    out.update(likely_score(h, a, rows["ens_prob"].to_numpy() >= 0.5, margin))
    return out


def apply_news(rows: pd.DataFrame, now: str, root: Path | None = None) -> list[dict]:
    """Adjust ensemble prob/margin for players in ``news/``; returns audit records.

    The player value table is only built (two small downloads) if some news file exists.
    """
    cache: dict[tuple[int, int], list[dict]] = {}
    for key in {(int(r.season), int(r.week)) for r in rows.itertuples()}:
        cache[key] = N.load_news(N.news_path(*key, root=root))
    values = None
    if any(cache.values()):
        from ensemblitz import players as PL

        season = int(rows["season"].iloc[0])
        values = PL.build_values(*PL.load_raw(season), season)
    audits = []
    for idx, r in rows.iterrows():
        a = N.adjust_game(
            r["ens_prob"],
            r["ens_margin"],
            r["home_team"],
            r["away_team"],
            cache[(int(r["season"]), int(r["week"]))],
            values,
            as_of=now,
        )
        audits.append(a)
        if a["applied"]:
            rows.loc[idx, "ens_prob"] = a["prob_home_after"]
            rows.loc[idx, "ens_margin"] = a["margin_after"]
    return audits


def _f(x: float | None, nd: int = 4) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def game_record(
    r: pd.Series, sim: dict[str, np.ndarray], i: int, now: str, news_adj: dict | None = None
) -> dict:
    comps = {c: _f(r[f"{c}_prob"]) for c in ("market", "elo", "kf", "lgbm", "lgbm_mkt")}
    comps["ensemble"] = _f(r["ens_prob"])
    if news_adj and news_adj.get("applied"):
        comps["ensemble_pre_news"] = _f(news_adj["prob_home_before"])
    comps["ensemble_model_only"] = _f(r["nomkt_prob"])
    return {
        "game_id": r["game_id"],
        "season": int(r["season"]),
        "week": int(r["week"]),
        "home_team": r["home_team"],
        "away_team": r["away_team"],
        "kickoff_utc": r["kickoff_utc"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": now,
        "model_version": C.MODEL_VERSION,
        "home_win_prob": comps,
        "pick": r["home_team"] if r["ens_prob"] >= 0.5 else r["away_team"],
        "predicted_margin": _f(r["ens_margin"], 2),
        "model_only_margin": _f(r["nomkt_margin"], 2),
        "predicted_total": _f(r["ens_total"], 2),
        "news_adjustment": news_adj or {"applied": False},
        "most_likely_score": {
            "home": int(sim["like_home"][i]),
            "away": int(sim["like_away"][i]),
            "prob": _f(sim["like_prob"][i]),
            "method": "nearest frequent score to the mean of simulations that match the pick and margin band",
            "raw_mode": {
                "home": int(sim["mode_home"][i]),
                "away": int(sim["mode_away"][i]),
                "prob": _f(sim["mode_prob"][i]),
            },
        },
        "sim": {
            "p_home": _f(sim["p_home"][i]),
            "margin_q10": _f(sim["margin_q10"][i], 1),
            "margin_q90": _f(sim["margin_q90"][i], 1),
            "total_q10": _f(sim["total_q10"][i], 1),
            "total_q90": _f(sim["total_q90"][i], 1),
        },
        "market": {
            "spread_line": _f(r["spread_line"], 1),
            "total_line": _f(r["total_line"], 1),
            "home_moneyline": _f(r["home_moneyline"], 0),
            "away_moneyline": _f(r["away_moneyline"], 0),
        },
        "context": {
            "home_qb_change": int(r["h_qb_change"]),
            "away_qb_change": int(r["a_qb_change"]),
            "home_rest": int(r["h_rest"]),
            "away_rest": int(r["a_rest"]),
            "dome": int(r["dome"]),
            "weather_known": int(r["weather_known"]),
            "temp": _f(r["temp"], 0) if r["weather_known"] else None,
            "wind": _f(r["wind"], 0) if r["weather_known"] else None,
            "home_out_lag": int(r["h_out_lag"]),
            "away_out_lag": int(r["a_out_lag"]),
        },
    }


def run_predict(
    season: int, week: int | None = None, n_weeks: int = 1, use_news: bool = True
) -> list[Path]:
    """Write ``predictions/<season>/weekXX.json``. Picks of games already kicked off stay frozen."""
    frame = build_frame(season)
    weeks = [week] if week else next_weeks(frame, season, n_weeks)
    if not weeks:
        log.info("no unplayed weeks in %s", season)
        return []
    rows = predict_frame(frame, season, weeks)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = rows.reset_index(drop=True)
    audits = apply_news(rows, now) if use_news else [None] * len(rows)
    sim = simulate_rows(rows)
    paths = []
    recs = [game_record(r, sim, i, now, audits[i]) for i, r in rows.iterrows()]
    weights = rows.attrs.get("ensemble_weights", {})
    for w in weeks:
        path = pred_path(season, w)
        old = json.loads(path.read_text()) if path.exists() else None
        frozen = {}
        if old:
            frozen = {g["game_id"]: g for g in old["games"] if g["kickoff_utc"] <= now}
        games = [frozen.get(g["game_id"], g) for g in recs if g["week"] == w]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "season": season,
                    "week": w,
                    "generated_at": now,
                    "model_version": C.MODEL_VERSION,
                    "ensemble_weights": weights,
                    "games": games,
                },
                indent=1,
            )
        )
        paths.append(path)
    return paths


__all__ = ["run_predict"]
