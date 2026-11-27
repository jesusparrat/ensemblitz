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


def _fit_model(train: pd.DataFrame, cols: list[str], market: bool) -> lgb.LGBMRegressor:
    if market:
        train = train[train["spread_line"].notna()]
        y = train["result"] - train["spread_line"]
    else:
        y = train["result"]
    model = lgb.LGBMRegressor(**PARAMS)
    model.fit(train[cols], y)
    return model


def fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, cols: list[str], market: bool
) -> np.ndarray:
    """Predict the home margin.

    With ``market=True`` the model learns the residual of the closing spread and returns
    ``spread + residual`` (rows without a spread come back as NaN).
    """
    model = _fit_model(train, cols, market)
    pred = model.predict(test[cols])
    if market:
        pred = np.where(test["spread_line"].notna(), pred + test["spread_line"].to_numpy(), np.nan)
    return pred


def fit_predict_with_contrib(
    train: pd.DataFrame, test: pd.DataFrame, cols: list[str], market: bool = False
) -> tuple[np.ndarray, pd.DataFrame]:
    """Predict home margin and return exact LightGBM TreeSHAP feature contributions.

    Uses LightGBM's built-in C++ ``pred_contrib=True`` (no extra dependencies). The returned
    DataFrame has one column per feature in ``cols`` plus ``_base_margin``; each row sums
    identically to the raw LightGBM prediction (before adding ``spread_line`` if ``market=True``).
    """
    model = _fit_model(train, cols, market)
    raw_pred = model.predict(test[cols])
    contrib = np.asarray(model.predict(test[cols], pred_contrib=True), dtype=float)
    contrib_df = pd.DataFrame(contrib, columns=[*cols, "_base_margin"], index=test.index)
    pred = (
        np.where(test["spread_line"].notna(), raw_pred + test["spread_line"].to_numpy(), np.nan)
        if market
        else raw_pred
    )
    return pred, contrib_df
