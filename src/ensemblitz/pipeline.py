"""Feature table + out-of-sample component predictions (walk-forward, no leakage)."""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz.data import load
from ensemblitz.features.build import build_features, feature_columns
from ensemblitz.models import gbm, kalman
from ensemblitz.models.ensemble import Ensemble
from ensemblitz.models.market import margin_to_prob, market_prob

log = logging.getLogger(__name__)


def make_features() -> pd.DataFrame:
    games = load.load_schedules()
    games = games[games["season"] >= C.FIRST_SEASON]
    tg, qg = load.load_team_games()
    inj = load.load_injury_counts()
    return build_features(games, tg, qg, inj)


def add_kf(
    feats: pd.DataFrame, last_season: int, tune: bool = True, stored: dict[int, dict] | None = None
) -> tuple[pd.DataFrame, dict]:
    """Add Kalman predictions. For season S the hyper-parameters are tuned on seasons < S only.

    ``stored`` holds hyper-parameters tuned earlier (see ``models/kf_params.json``); a stored
    season is not tuned again, which keeps the weekly run fast and reproducible.
    """
    parts, used = [], {}
    params = kalman.KFParams()
    for s in range(C.FIRST_SEASON, last_season + 1):
        if stored and s in stored:
            params = kalman.KFParams(**stored[s])
        elif tune and s >= C.FIRST_BACKTEST_SEASON:
            params = kalman.tune(feats, before_season=s, start=params)
            log.info("kf tuned for %s: %s", s, params)
        used[s] = params.to_dict()
        kf = kalman.run_kf(feats, params, until_season=s)
        ids = set(feats.loc[feats["season"] == s, "game_id"])
        parts.append(kf[kf["game_id"].isin(ids)])
    kf_all = pd.concat(parts, ignore_index=True)
    return feats.merge(kf_all, on="game_id", how="left"), used


KF_PARAMS_PATH = C.ROOT / "models" / "kf_params.json"


def load_kf_params() -> dict[int, dict]:
    if KF_PARAMS_PATH.exists():
        return {int(k): v for k, v in json.loads(KF_PARAMS_PATH.read_text()).items()}
    return {}


def save_kf_params(used: dict[int, dict]) -> None:
    KF_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KF_PARAMS_PATH.write_text(json.dumps(used, indent=1))


def add_components_static(df: pd.DataFrame) -> pd.DataFrame:
    """Components that need no fitting: market, Elo and KF (probabilities + margins)."""
    df = df.copy()
    df["market_prob"] = market_prob(df)
    df["market_margin"] = df["spread_line"]
    return df


def _train_mask(df: pd.DataFrame, season: int, week: int) -> pd.Series:
    earlier = (df["season"] < season) | ((df["season"] == season) & (df["week"] < week))
    return earlier & df["played"] & df["result"].notna()


def add_gbm_components(
    df: pd.DataFrame, first_season: int = C.WARMUP_SEASON, include_future: bool = False
) -> pd.DataFrame:
    """Walk-forward LightGBM: refit before every (season, week) batch on all earlier games."""
    df = df.copy()
    base, mkt = feature_columns(False), feature_columns(True)
    df["lgbm_margin"] = np.nan
    df["lgbm_mkt_margin"] = np.nan
    for (season, week), batch in df.groupby(["season", "week"], sort=True):
        if season < first_season or (not include_future and not batch["played"].all()):
            continue
        train = df[_train_mask(df, season, week)]
        if len(train) < 200:
            continue
        df.loc[batch.index, "lgbm_margin"] = gbm.fit_predict(train, batch, base, market=False)
        df.loc[batch.index, "lgbm_mkt_margin"] = gbm.fit_predict(train, batch, mkt, market=True)
    df["lgbm_prob"] = margin_to_prob(df["lgbm_margin"])
    df["lgbm_mkt_prob"] = margin_to_prob(df["lgbm_mkt_margin"])
    return df


def add_ensemble_walk_forward(
    df: pd.DataFrame, first: int = C.FIRST_BACKTEST_SEASON, last: int = C.LAST_BACKTEST_SEASON
) -> pd.DataFrame:
    """Refit stack + margin/total blend before every batch using only earlier OOS predictions."""
    df = df.copy()
    for c in (
        "ens_prob",
        "ens_margin",
        "ens_total",
        "model_only_prob",
        "model_only_margin",
        "model_only_total",
    ):
        df[c] = np.nan
    need = ["market_prob", "elo_prob", "kf_prob", "lgbm_prob", "lgbm_mkt_prob"]
    for (season, week), batch in df.groupby(["season", "week"], sort=True):
        if season < first or season > last:
            continue
        pool = df[_train_mask(df, season, week) & (df["season"] >= C.WARMUP_SEASON)]
        pool = pool.dropna(subset=need)
        if len(pool) < 150:
            continue
        ens = Ensemble(pool)
        df.loc[batch.index, ["ens_prob", "ens_margin", "ens_total"]] = ens.predict(batch).to_numpy()
        df.loc[batch.index, "model_only_prob"] = ens.no_market.prob(batch)
        df.loc[batch.index, "model_only_margin"] = ens.no_market.margin(batch)
        df.loc[batch.index, "model_only_total"] = ens.no_market.total(batch)
    return df
