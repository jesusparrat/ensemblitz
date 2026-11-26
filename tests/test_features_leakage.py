from types import SimpleNamespace

import numpy as np
import pandas as pd

from ensemblitz import pipeline
from ensemblitz.features.build import build_features
from ensemblitz.models import kalman
from ensemblitz.models.kalman import KFParams, run_kf

CUT = (2021, 4)  # perturb everything from this (season, week) on


def _after(df: pd.DataFrame) -> pd.Series:
    return (df["season"] > CUT[0]) | ((df["season"] == CUT[0]) & (df["week"] >= CUT[1]))


def _perturb(games, tg, qg):
    g, t, q = games.copy(), tg.copy(), qg.copy()
    m = _after(g)
    g.loc[m, ["home_score", "away_score"]] = g.loc[m, ["away_score", "home_score"]].to_numpy() + 17
    g.loc[m, "result"] = g.loc[m, "home_score"] - g.loc[m, "away_score"]
    late = set(g.loc[m, "game_id"])
    t.loc[t["game_id"].isin(late), ["epa_pass", "epa_rush"]] += 25.0
    q.loc[q["game_id"].isin(late), "epa_db"] -= 30.0
    return g, t, q


def test_features_use_only_past(league):
    games, tg, qg = league
    base = build_features(games, tg, qg)
    g2, t2, q2 = _perturb(games, tg, qg)
    alt = build_features(g2, t2, q2)
    early = ~_after(base)
    cols = [c for c in base.columns if c not in ("result", "total", "home_score", "away_score")]
    pd.testing.assert_frame_equal(
        base.loc[early, cols].reset_index(drop=True), alt.loc[early, cols].reset_index(drop=True)
    )
    # and the perturbation does change later features (the test is not vacuous)
    late = _after(base) & (base["week"] > CUT[1])
    assert not np.allclose(base.loc[late, "elo_diff"], alt.loc[late, "elo_diff"])


def test_own_result_never_in_own_features(league):
    games, tg, qg = league
    base = build_features(games, tg, qg)
    g2 = games.copy()
    i = len(g2) // 2
    g2.loc[i, ["home_score", "result"]] = [60, 60 - g2.loc[i, "away_score"]]
    alt = build_features(g2, tg, qg)
    drop = ["result", "total", "home_score", "away_score"]
    pd.testing.assert_series_equal(base.drop(columns=drop).iloc[i], alt.drop(columns=drop).iloc[i])


def test_unplayed_games_do_not_update_state(league):
    games, tg, qg = league
    g2 = games.copy()
    m = _after(g2)
    g2.loc[m, ["played", "result", "total", "home_score", "away_score"]] = [
        False,
        np.nan,
        np.nan,
        np.nan,
        np.nan,
    ]
    full = build_features(games, tg, qg)
    fut = build_features(g2, tg, qg)
    # first unplayed batch has identical features whether or not its results exist
    first = (fut["season"] == CUT[0]) & (fut["week"] == CUT[1])
    cols = ["elo_diff", "h_off_pass", "a_def_rush", "h_qb_rate"]
    np.testing.assert_allclose(full.loc[first, cols].to_numpy(), fut.loc[first, cols].to_numpy())


def test_kalman_predictions_use_only_past(league):
    games, tg, qg = league
    base = run_kf(games, KFParams())
    g2, _, _ = _perturb(games, tg, qg)
    alt = run_kf(g2, KFParams())
    ids = games.loc[~_after(games), "game_id"]
    a = base[base["game_id"].isin(ids)].reset_index(drop=True)
    b = alt[alt["game_id"].isin(ids)].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_kalman_tuning_truncates_at_the_requested_season(monkeypatch, league):
    games, _, _ = league
    seen = {}

    def fake_minimize(fun, x0, args, **kwargs):
        seen["max_season"] = int(args[0]["season"].max())
        return SimpleNamespace(x=x0)

    monkeypatch.setattr(kalman, "minimize", fake_minimize)
    kalman.tune(games, before_season=CUT[0], maxiter=1)
    assert seen["max_season"] < CUT[0]


def test_lightgbm_training_mask_excludes_current_and_future_weeks(league):
    games, _, _ = league
    mask = pipeline._train_mask(games, CUT[0], CUT[1])
    train = games.loc[mask]
    assert not train.empty
    assert train["played"].all() and train["result"].notna().all()
    assert (
        (train["season"] < CUT[0]) | ((train["season"] == CUT[0]) & (train["week"] < CUT[1]))
    ).all()
