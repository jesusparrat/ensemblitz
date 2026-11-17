import numpy as np
import pandas as pd

from ensemblitz.grade import grade_games
from ensemblitz.odds import devig
from ensemblitz.odds.client import flatten
from ensemblitz.odds.validation import subset_stats


def test_devig_sums_to_one_and_removes_margin():
    o = np.array([1.87, 1.95])
    for f in (devig.multiplicative, devig.shin):
        p = f(o)
        assert abs(p.sum() - 1) < 1e-9 and (p > 0).all()
    assert devig.overround(o) > 0
    # Shin takes relatively more margin from the longshot than multiplicative does
    o2 = np.array([1.20, 4.80])
    assert devig.shin(o2)[1] < devig.multiplicative(o2)[1]


def test_flatten_event():
    ev = [
        {
            "id": "e1",
            "commence_time": "2026-11-19T01:15:00Z",
            "home_team": "A",
            "away_team": "B",
            "bookmakers": [
                {
                    "key": "bk",
                    "markets": [
                        {
                            "key": "h2h",
                            "last_update": "x",
                            "outcomes": [{"name": "A", "price": 1.9}, {"name": "B", "price": 2.0}],
                        }
                    ],
                }
            ],
        }
    ]
    df = flatten(ev, "t")
    assert len(df) == 2 and set(df["bookmaker"]) == {"bk"}


def _pred(generated, kickoff):
    return {
        "game_id": "g1",
        "season": 2026,
        "week": 1,
        "home_team": "A",
        "away_team": "B",
        "generated_at": generated,
        "kickoff_utc": kickoff,
        "pick": "A",
        "predicted_margin": 3.0,
        "predicted_total": 44.0,
        "market": {"spread_line": 2.5},
        "home_win_prob": {"ensemble": 0.6, "market": 0.58},
    }


def test_grader_only_grades_picks_made_before_kickoff():
    sched = pd.DataFrame({"game_id": ["g1"], "result": [7.0], "total": [40.0]})
    ok = grade_games([_pred("2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z")], sched)
    late = grade_games([_pred("2026-09-03T00:00:00Z", "2026-09-02T00:00:00Z")], sched)
    assert len(ok) == 1 and ok[0]["ensemble_correct"] == 1 and ok[0]["ats_win"] == 1
    assert late == []


def test_subset_stats_threshold_filters():
    rng = np.random.default_rng(1)
    n = 400
    mk = rng.uniform(0.2, 0.8, n)
    df = pd.DataFrame(
        {
            "market_prob": mk,
            "ens_prob": np.clip(mk + rng.normal(0, 0.04, n), 0.02, 0.98),
            "result": rng.normal(0, 13, n).round() + 0.5,
            "spread_line": 0.0,
            "home_moneyline": -110.0,
            "away_moneyline": -110.0,
        }
    )
    a = subset_stats(df, "ens", 0.0)
    b = subset_stats(df, "ens", 0.05)
    assert 0 < b["n"] < a["n"] and abs(a["ml_roi_flat"]) < 0.3
