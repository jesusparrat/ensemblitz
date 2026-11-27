"""Unit tests for PR 5 separated model explanations, matchups, and v1 schema compatibility."""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

from ensemblitz import contract as K
from ensemblitz import contract_io
from ensemblitz import explain as X
from ensemblitz import pipeline as P
from ensemblitz.features.build import build_features, feature_columns
from ensemblitz.models import gbm
from ensemblitz.models.ensemble import MODEL_COMPONENTS, StackModel
from ensemblitz.models.kalman import KFParams, run_kf

ROOT = Path(__file__).resolve().parents[1]


def _sample_explanation(season_week: int = 12) -> dict:
    return {
        "season_week": season_week,
        "summary": {
            "lead_component": "kf",
            "lead_component_margin_home": 2.4,
            "top_matchup_id": "home_pass",
            "lgbm_top_group": "team_strength",
            "lgbm_top_group_margin_home": 1.9,
            "qb_change_teams": [],
        },
        "stack": {
            "components": ["elo", "kf", "lgbm"],
            "prob_weights": [0.2, 0.5, 0.4],
            "prob_bias": 0.02,
            "logit_contributions": {"elo": 0.12, "kf": 0.35, "lgbm": 0.28},
            "margin_weights": [0.2, 0.5, 0.3],
            "margin_contributions": {"elo": 0.8, "kf": 2.4, "lgbm": 1.5},
        },
        "lgbm_shap": {
            "base_margin": 1.5,
            "pred_margin": 5.0,
            "groups": {
                "pass_game": 0.9,
                "rush_game": 0.3,
                "efficiency": 0.4,
                "qb": 0.2,
                "team_strength": 1.9,
                "situational": -0.2,
            },
        },
        "kalman": {
            "margin": 4.8,
            "hfa": 1.8,
            "home_off": 2.1,
            "away_def_allowed": 0.7,
            "away_off": 0.3,
            "home_def_allowed": -0.5,
            "home_off_vs_away_def": 2.8,
            "away_off_vs_home_def": -0.2,
        },
        "elo": {
            "margin": 4.0,
            "team_margin": 2.08,
            "hfa_margin": 1.92,
            "home_rating": 1560.0,
            "away_rating": 1508.0,
        },
        "matchups": [
            {
                "id": "home_pass",
                "unit": "pass",
                "off_team": "HOU",
                "def_team": "IND",
                "off_epa": 0.14,
                "off_rank": 4,
                "def_epa_allowed": 0.08,
                "def_rank": 24,
                "combined_epa": 0.22,
                "favors": "HOU",
            },
            {
                "id": "away_rush",
                "unit": "rush",
                "off_team": "IND",
                "def_team": "HOU",
                "off_epa": -0.05,
                "off_rank": 22,
                "def_epa_allowed": -0.09,
                "def_rank": 5,
                "combined_epa": -0.14,
                "favors": "HOU",
            },
            {
                "id": "away_pass",
                "unit": "pass",
                "off_team": "IND",
                "def_team": "HOU",
                "off_epa": 0.02,
                "off_rank": 15,
                "def_epa_allowed": -0.08,
                "def_rank": 6,
                "combined_epa": -0.06,
                "favors": "HOU",
            },
            {
                "id": "home_rush",
                "unit": "rush",
                "off_team": "HOU",
                "def_team": "IND",
                "off_epa": 0.01,
                "off_rank": 16,
                "def_epa_allowed": 0.02,
                "def_rank": 19,
                "combined_epa": 0.03,
                "favors": "HOU",
            },
        ],
        "qb_matchup": {
            "home_epa_per_dropback": 0.11,
            "away_epa_per_dropback": -0.02,
            "diff_epa_per_dropback": 0.13,
            "home_dropbacks": 320.0,
            "away_dropbacks": 210.0,
            "home_qb_change": False,
            "away_qb_change": False,
        },
        "injury_context": {
            "source": "nflverse_injuries",
            "cutoff_utc": "2026-11-18T12:00:00Z",
            "included_in_model": False,
            "home": [{"player": "Test Player", "position": "WR", "status": "out", "points": 1.6}],
            "away": [],
        },
    }


def _minimal_v1_doc(with_explanation: bool = False) -> dict:
    game = {
        "game_id": "2026_12_IND_HOU",
        "home_team": "HOU",
        "away_team": "IND",
        "kickoff_utc": "2026-11-29T18:00:00Z",
        "generated_at_utc": "2026-11-24T18:00:00Z",
        "headline": {
            "home_win_prob": 0.72,
            "home_points": 26.5,
            "away_points": 20.5,
            "distribution": {
                "n_sims": 20000,
                "seed": 2026,
                "p_home": 0.71,
                "home_points": [14.0, 39.0],
                "away_points": [9.0, 33.0],
                "margin_home": [-10.0, 23.0],
                "total": [30.0, 65.0],
            },
            "example_score": {"home": 27, "away": 20, "prob": 0.01},
        },
        "ensemble": {"home_win_prob": 0.74, "margin_home": 6.5, "total": 46.5},
        "components": {"elo": 0.65, "kf": 0.73, "lgbm": 0.71, "lgbm_mkt": 0.73},
        "market": [
            {
                "source": "nflverse_line",
                "captured_at_utc": "2026-11-24T18:00:00Z",
                "is_closing": False,
                "home_win_prob": 0.75,
                "margin_home": 6.5,
                "total_line": 46.5,
                "home_moneyline": -280.0,
                "away_moneyline": 230.0,
            }
        ],
        "context": {
            "home_qb_change": False,
            "away_qb_change": False,
            "home_rest_days": 7,
            "away_rest_days": 7,
            "dome": True,
            "weather_known": True,
            "temp_f": 70.0,
            "wind_mph": 0.0,
            "home_out_lag": 1,
            "away_out_lag": 2,
        },
        "absences": {"home": [], "away": []},
        "news_adjustment": {"applied": False, "applies_to": "ensemble"},
    }
    if with_explanation:
        game["explanation"] = _sample_explanation()
    return {
        "schema_version": "1",
        "model_version": "0.2.0",
        "git_sha": "0" * 40,
        "reproducible": False,
        "generated_at_utc": "2026-11-24T18:00:00Z",
        "data_cutoff_utc": "2026-11-24T12:00:00Z",
        "data_snapshot": {"data/raw/schedules.parquet": "a" * 64},
        "season": 2026,
        "week": 12,
        "ensemble_weights": {
            "with_market": {
                "components": ["market", "elo", "kf", "lgbm", "lgbm_mkt"],
                "prob_weights": [0.9, 0.0, 0.05, 0.05, 0.0],
                "bias": 0.0,
                "margin_weights": [1.0, 0.0, 0.0, 0.0, 0.0],
            },
            "no_market": {
                "components": ["elo", "kf", "lgbm"],
                "prob_weights": [0.2, 0.5, 0.4],
                "bias": 0.02,
                "margin_weights": [0.2, 0.5, 0.3],
            },
        },
        "games": [game],
    }


def test_lgbm_groups_exact_partition() -> None:
    expected = feature_columns(include_market=False)
    flat = [c for cols in X.LGBM_GROUPS.values() for c in cols]
    assert len(flat) == len(set(flat)), "duplicate feature in LGBM_GROUPS"
    assert set(flat) == set(expected), f"mismatch: {set(flat) ^ set(expected)}"


def test_additive_identities_for_stack_lgbm_kalman_and_elo(league) -> None:
    games, tg, qg = league
    feats = build_features(games, tg, qg)
    kf = run_kf(games, KFParams())
    df = feats.merge(kf, on="game_id", how="left")
    df = P.add_components_static(df)
    base_cols = feature_columns(include_market=False)

    last_s = int(df["season"].max())
    last_w = int(df.loc[df["season"] == last_s, "week"].max())
    train = df[P._train_mask(df, last_s, last_w)]
    batch = df[(df["season"] == last_s) & (df["week"] == last_w)].copy()

    pred, contrib = gbm.fit_predict_with_contrib(train, batch, base_cols, market=False)
    pred_plain = gbm.fit_predict(train, batch, base_cols, market=False)
    np.testing.assert_allclose(pred, pred_plain, atol=1e-12)

    batch["lgbm_margin"] = pred
    batch["lgbm_prob"] = expit(pred / 13.5)
    stack = StackModel(
        comps=list(MODEL_COMPONENTS),
        w=np.array([0.2, 0.45, 0.4]),
        b=0.03,
        margin_w=np.array([0.2, 0.5, 0.3]),
        total_w=np.array([1.0]),
        total_cols=["kf_total"],
    )
    batch["nomkt_prob"] = stack.prob(batch)
    batch["nomkt_margin"] = stack.margin(batch)

    for idx, row in batch.iterrows():
        # Raw TreeSHAP exact sum identity before grouping/rounding
        raw_c = contrib.loc[idx]
        assert abs(float(raw_c.sum()) - float(row["lgbm_margin"])) < 1e-6

        expl = X.build_game_explanation(
            row,
            raw_c,
            stack,
            {"home": [], "away": []},
            "2026-11-24T12:00:00Z",
        )
        # 1. Stack logit + margin exact identities
        st = expl["stack"]
        z = sum(st["logit_contributions"].values()) + st["prob_bias"]
        assert abs(float(expit(z)) - float(row["nomkt_prob"])) < 1e-3
        assert abs(sum(st["margin_contributions"].values()) - float(row["nomkt_margin"])) < 0.01

        # 2. LightGBM TreeSHAP grouped additive identity (LightGBM only)
        sh = expl["lgbm_shap"]
        assert abs(sh["base_margin"] + sum(sh["groups"].values()) - sh["pred_margin"]) < 0.01

        # 3. Kalman exact additive identity (Kalman only)
        k = expl["kalman"]
        assert (
            abs(k["hfa"] + k["home_off_vs_away_def"] - k["away_off_vs_home_def"] - k["margin"])
            < 0.01
        )

        # 4. Elo exact additive identity (Elo only)
        e = expl["elo"]
        assert abs(e["team_margin"] + e["hfa_margin"] - e["margin"]) < 0.01
        if int(row["neutral"]) == 1:
            assert e["hfa_margin"] == 0.0


def test_unit_matchups_descriptive_sign_ranks_and_tiebreaking(league) -> None:
    games, tg, qg = league
    feats = build_features(games, tg, qg)
    # Week 1 of first season: all teams start at prior 0.0 -> deterministic alphabetical ranks!
    s0 = int(feats["season"].min())
    w1 = feats[(feats["season"] == s0) & (feats["week"] == 1)]
    teams_sorted = sorted(set(feats["home_team"]).union(set(feats["away_team"])))
    for row in w1.itertuples(index=False):
        assert row.h_off_pass_rank == teams_sorted.index(row.home_team) + 1
        assert row.h_def_pass_rank == teams_sorted.index(row.home_team) + 1

    # Descriptive sign check: good offense (+0.15) vs weak defense (+0.10 allowed) -> +0.25 favors offense
    synth = pd.Series(
        {
            "home_team": "HOU",
            "away_team": "IND",
            "h_off_pass": 0.15,
            "a_def_pass": 0.10,
            "h_off_pass_rank": 2,
            "a_def_pass_rank": 29,
            "a_off_pass": -0.10,
            "h_def_pass": -0.12,
            "a_off_pass_rank": 28,
            "h_def_pass_rank": 3,
            "h_off_rush": 0.02,
            "a_def_rush": 0.01,
            "h_off_rush_rank": 14,
            "a_def_rush_rank": 18,
            "a_off_rush": 0.0,
            "h_def_rush": 0.0,
            "a_off_rush_rank": 16,
            "h_def_rush_rank": 16,
        }
    )
    m = X.unit_matchups(synth)
    assert len(m) == 4
    by_id = {x["id"]: x for x in m}
    assert by_id["home_pass"]["combined_epa"] == 0.25
    assert by_id["home_pass"]["favors"] == "HOU"
    assert by_id["away_pass"]["combined_epa"] == -0.22
    assert by_id["away_pass"]["favors"] == "HOU"
    # Sorted descending by |combined_epa|
    assert [x["id"] for x in m[:2]] == ["home_pass", "away_pass"]


def test_contract_compatibility_matrix() -> None:
    # 1. Existing v1 snapshot WITHOUT explanation stays valid.
    assert K.validate_week(_minimal_v1_doc(with_explanation=False)) == []

    # 2. New v1 snapshot WITH valid explanation is valid.
    valid = _minimal_v1_doc(with_explanation=True)
    assert K.validate_week(valid) == []

    # 3. Existing v0 snapshot loads cleanly with explanation absent.
    loaded_v0 = contract_io.load_week(ROOT / "predictions" / "2026" / "week12.json")
    assert loaded_v0.version == "0"
    assert all("explanation" not in g for g in loaded_v0.doc["games"])

    # 4. Missing required nested field fails validation.
    missing_nested = copy.deepcopy(valid)
    del missing_nested["games"][0]["explanation"]["lgbm_shap"]["base_margin"]
    errs = K.validate_week(missing_nested)
    assert any("base_margin" in e for e in errs)

    # 5. NaN inside explanation fails validation.
    nan_doc = copy.deepcopy(valid)
    nan_doc["games"][0]["explanation"]["kalman"]["hfa"] = float("nan")
    errs = K.validate_week(nan_doc)
    assert any("NaN" in e for e in errs)

    # 6. Invalid values (rank out of range, included_in_model=True) fail validation.
    bad_rank = copy.deepcopy(valid)
    bad_rank["games"][0]["explanation"]["matchups"][0]["off_rank"] = 33
    assert any("above 32" in e for e in K.validate_week(bad_rank))

    bad_inj = copy.deepcopy(valid)
    bad_inj["games"][0]["explanation"]["injury_context"]["included_in_model"] = True
    assert any("must be False" in e for e in K.validate_week(bad_inj))

    # 7. Unexpected additionalProperties inside explanation fails validation.
    extra_prop = copy.deepcopy(valid)
    extra_prop["games"][0]["explanation"]["lgbm_shap"]["unexpected"] = 1.0
    assert any("unexpected field" in e for e in K.validate_week(extra_prop))
