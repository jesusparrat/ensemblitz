import numpy as np
import pandas as pd

from ensemblitz.metrics import ats
from ensemblitz.models.market import implied_spread, market_prob
from ensemblitz.predict import fill_missing_spread


def test_implied_spread_sign_and_size():
    s = implied_spread(pd.Series([-250.0, 150.0, -110.0]), pd.Series([210.0, -170.0, -110.0]))
    assert s[0] > 0 > s[1] and abs(s[2]) < 0.01
    assert 4 < s[0] < 9


def test_fill_missing_spread_only_touches_unplayed_games_without_spread():
    df = pd.DataFrame(
        {
            "played": [False, False, True, False],
            "spread_line": [np.nan, 3.5, np.nan, np.nan],
            "home_moneyline": [-170.0, -170.0, -170.0, np.nan],
            "away_moneyline": [145.0, 145.0, 145.0, np.nan],
        }
    )
    out = fill_missing_spread(df)
    assert out.loc[0, "spread_line"] > 0 and out.loc[0, "spread_line"] % 0.5 == 0
    assert out.loc[1, "spread_line"] == 3.5
    assert np.isnan(out.loc[2, "spread_line"]) and np.isnan(out.loc[3, "spread_line"])
    assert np.isnan(df.loc[0, "spread_line"])  # no muta la entrada


def test_nflverse_spread_sign_fallback_is_home_minus_away():
    lines = pd.DataFrame(
        {
            "home_moneyline": [np.nan, np.nan],
            "away_moneyline": [np.nan, np.nan],
            "spread_line": [3.5, -3.5],
        }
    )
    probabilities = market_prob(lines)
    assert probabilities[0] > 0.5
    assert probabilities[1] < 0.5


def test_ats_grading_uses_home_margin_spread_convention():
    frame = pd.DataFrame(
        {
            "result": [5.0, -4.0],
            "spread_line": [3.0, -3.0],
            "model_margin": [4.0, -4.0],
        }
    )
    scored = ats(frame, "model_margin")
    assert scored["w"] == 2
    assert scored["l"] == 0
    assert scored["push"] == 0
