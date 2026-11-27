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


def test_explanations_ranks_and_shap_use_only_past(league):
    from scipy.special import expit

    from ensemblitz import explain as X
    from ensemblitz.features.build import feature_columns
    from ensemblitz.models import gbm
    from ensemblitz.models.ensemble import MODEL_COMPONENTS, StackModel

    games, tg, qg = league
    g2, t2, q2 = _perturb(games, tg, qg)

    def _run_expl(gm, tgm, qgm):
        f = build_features(gm, tgm, qgm)
        kf = run_kf(gm, KFParams())
        df = f.merge(kf, on="game_id", how="left")
        df = pipeline.add_components_static(df)
        target_s, target_w = CUT[0], CUT[1] - 1
        train = df[pipeline._train_mask(df, target_s, target_w)]
        batch = df[(df["season"] == target_s) & (df["week"] == target_w)].copy()
        cols = feature_columns(include_market=False)
        pred, contrib = gbm.fit_predict_with_contrib(train, batch, cols, market=False)
        batch["lgbm_margin"] = pred
        batch["lgbm_prob"] = expit(pred / 13.5)
        stack = StackModel(
            comps=list(MODEL_COMPONENTS),
            w=np.array([0.2, 0.5, 0.3]),
            b=0.0,
            margin_w=np.array([0.2, 0.5, 0.3]),
            total_w=np.array([1.0]),
            total_cols=["kf_total"],
        )
        batch["nomkt_prob"] = stack.prob(batch)
        batch["nomkt_margin"] = stack.margin(batch)
        return [
            X.build_game_explanation(
                row, contrib.loc[idx], stack, {"home": [], "away": []}, "2021-10-01T12:00:00Z"
            )
            for idx, row in batch.iterrows()
        ]

    base_expl = _run_expl(games, tg, qg)
    alt_expl = _run_expl(g2, t2, q2)
    assert base_expl, "target pre-cut batch must be non-empty"
    assert base_expl == alt_expl


def test_injury_notable_absences_uses_only_past():
    from ensemblitz import impact as I

    players = [
        ("00-0099001", "StarRe00", "Star Receiver", 12, 9.5, 0.95),
        ("00-0099002", "DeptRe01", "Depth WR 1", 3, -1.2, 0.35),
        ("00-0099003", "DeptRe02", "Depth WR 2", 3, -1.0, 0.35),
        ("00-0099004", "DeptRe03", "Depth WR 3", 2, -0.8, 0.30),
        ("00-0099005", "DeptRe04", "Depth WR 4", 2, -0.9, 0.30),
        ("00-0099006", "DeptRe05", "Depth WR 5", 2, -1.1, 0.30),
    ]
    stats_rows = []
    snap_rows = []
    for wk in range(1, 7):
        for pid, pfr, name, tgt, epa, pct in players:
            stats_rows.append(
                {
                    "player_id": pid,
                    "player_display_name": name,
                    "season": 2024,
                    "week": wk,
                    "season_type": "REG",
                    "position": "WR",
                    "attempts": 0,
                    "sacks_suffered": 0,
                    "passing_epa": 0.0,
                    "carries": 0,
                    "rushing_epa": 0.0,
                    "targets": tgt,
                    "receiving_epa": epa,
                    "def_sacks": 0,
                    "def_qb_hits": 0,
                    "def_tackles_for_loss": 0,
                    "def_fumbles_forced": 0,
                    "def_interceptions": 0,
                    "def_pass_defended": 0,
                    "def_tackles_solo": 0,
                    "def_tackle_assists": 0,
                }
            )
            snap_rows.append(
                {
                    "pfr_player_id": pfr,
                    "season": 2024,
                    "week": wk,
                    "game_type": "REG",
                    "position": "WR",
                    "offense_pct": pct,
                    "defense_pct": 0.0,
                    "offense_snaps": int(pct * 60),
                    "defense_snaps": 0,
                    "st_snaps": 0,
                }
            )
    ids = pd.DataFrame([{"gsis_id": pid, "pfr_id": pfr} for pid, pfr, *_ in players])
    inj = pd.DataFrame(
        [
            {
                "gsis_id": "00-0099001",
                "season": 2024,
                "week": 4,
                "game_type": "REG",
                "team": "HOU",
                "position": "WR",
                "report_status": "Out",
                "practice_status": "Did Not Participate In Practice",
            }
        ]
    )
    base_data = {
        "stats": pd.DataFrame(stats_rows),
        "snaps": pd.DataFrame(snap_rows),
        "ids": ids,
        "inj": inj,
    }
    alt_stats = base_data["stats"].copy()
    alt_stats.loc[alt_stats["week"] >= 4, "receiving_epa"] = -99.0
    alt_snaps = base_data["snaps"].copy()
    alt_snaps.loc[alt_snaps["week"] >= 4, "offense_pct"] = 0.0
    alt_inj = pd.concat(
        [
            inj,
            pd.DataFrame(
                [
                    {
                        "gsis_id": "00-0099002",
                        "season": 2024,
                        "week": 5,
                        "game_type": "REG",
                        "team": "HOU",
                        "position": "WR",
                        "report_status": "Out",
                        "practice_status": "Did Not Participate In Practice",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    alt_data = {"stats": alt_stats, "snaps": alt_snaps, "ids": ids, "inj": alt_inj}
    base_ab = I.notable_absences(2024, 4, min_pts=0.1, data=base_data)
    alt_ab = I.notable_absences(2024, 4, min_pts=0.1, data=alt_data)
    assert base_ab.get("HOU"), "pre-cut injury fixture must produce a notable absence"
    assert base_ab == alt_ab
