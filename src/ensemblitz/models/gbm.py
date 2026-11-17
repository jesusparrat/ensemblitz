"""Gradient boosting on the pre-game feature table (LightGBM, small and heavily regularised)."""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

PARAMS = dict(
    objective="regression",
    n_estimators=220,
    learning_rate=0.03,
    num_leaves=5,
    max_depth=3,
    min_child_samples=40,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.7,
    reg_lambda=15.0,
    verbose=-1,
    n_jobs=4,
    random_state=7,
)


def fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, cols: list[str], market: bool
) -> np.ndarray:
    """Predict the home margin.

    With ``market=True`` the model learns the residual of the closing spread and returns
    ``spread + residual`` (rows without a spread come back as NaN).
    """
    if market:
        train = train[train["spread_line"].notna()]
        y = train["result"] - train["spread_line"]
    else:
        y = train["result"]
    model = lgb.LGBMRegressor(**PARAMS)
    model.fit(train[cols], y)
    pred = model.predict(test[cols])
    if market:
        pred = np.where(test["spread_line"].notna(), pred + test["spread_line"].to_numpy(), np.nan)
    return pred
