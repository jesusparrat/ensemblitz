"""The published number is the model on its own; grading says which number it graded."""

import pandas as pd

from ensemblitz.grade import grade_games


def _game(**kw):
    g = {
        "game_id": "2026_01_AAA_BBB",
        "season": 2026,
        "week": 1,
        "home_team": "BBB",
        "away_team": "AAA",
        "kickoff_utc": "2026-09-10T00:00:00Z",
        "generated_at": "2026-09-08T10:00:00Z",
        "pick": "BBB",
        "predicted_margin": -3.0,
        "predicted_total": 44.0,
        "market": {"spread_line": 3.0},
        # the model alone picks home, the blended ensemble picks away
        "home_win_prob": {"ensemble": 0.40, "ensemble_model_only": 0.60, "market": 0.45},
    }
    g.update(kw)
    return g


def _sched(result):
    return pd.DataFrame([{"game_id": "2026_01_AAA_BBB", "result": result, "total": 40.0}])


def test_model_only_headline_is_graded_on_the_model_alone():
    g = _game(
        headline="model_only",
        model_only={"margin": 2.0, "total": 45.0, "home_win_prob": 0.6},
    )
    (row,) = grade_games([g], _sched(7.0))  # home wins
    assert row["headline"] == "model_only"
    assert row["headline_correct"] == 1  # model alone said home
    assert row["ensemble_correct"] == 0  # the old blend said away
    assert row["predicted_margin"] == 2.0


def test_legacy_record_is_graded_as_the_ensemble():
    g = _game(pick="AAA")  # saved before the change: no headline key
    (row,) = grade_games([g], _sched(7.0))
    assert row["headline"] == "ensemble"
    assert row["headline_correct"] == 0
    assert row["predicted_margin"] == -3.0


def test_pick_saved_after_kickoff_is_not_graded():
    g = _game(generated_at="2026-09-10T00:00:00Z", headline="model_only")
    assert grade_games([g], _sched(7.0)) == []
