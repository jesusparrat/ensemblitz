import numpy as np
import pandas as pd

from ensemblitz.models.ensemble import ALL_COMPONENTS, Ensemble, fit_stack
from ensemblitz.models.market import margin_to_prob


def _pool(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    truth = rng.normal(0, 6, n)
    result = np.round(truth + rng.normal(0, 13, n))
    df = pd.DataFrame(
        {
            "result": result,
            "total": 44 + rng.normal(0, 10, n),
            "kf_total": 44 + rng.normal(0, 3, n),
            "total_line": 44 + rng.normal(0, 3, n),
        }
    )
    noise = {"market": 1.0, "elo": 4.0, "kf": 4.0, "lgbm": 5.0, "lgbm_mkt": 2.0}
    for c, s in noise.items():
        m = truth + rng.normal(0, s, n)
        df[f"{c}_margin"] = m
        df[f"{c}_prob"] = margin_to_prob(m)
    df["spread_line"] = df["market_margin"]
    return df


def test_weights_are_nonnegative_and_favour_the_best_component():
    m = fit_stack(_pool(), ALL_COMPONENTS)
    assert (m.w >= 0).all() and (m.margin_w >= -1e-9).all()
    assert m.comps[int(np.argmax(m.w))] in ("market", "lgbm_mkt")
    assert abs(m.margin_w.sum() - 1.0) < 1e-6  # anchored on the spread


def test_ensemble_probs_in_range_and_no_market_fallback():
    pool = _pool()
    ens = Ensemble(pool)
    test = _pool(200, seed=5)
    test.loc[:49, "spread_line"] = np.nan
    out = ens.predict(test)
    assert out["ens_prob"].between(0, 1).all() and out["ens_margin"].notna().all()
    assert out["ens_total"].notna().all()


def test_ensemble_not_worse_than_worst_component():
    pool = _pool(2000)
    train, test = pool.iloc[:1500], pool.iloc[1500:]
    out = Ensemble(train).predict(test)
    y = (test["result"] > 0).to_numpy(float)

    def ll(p):
        p = np.clip(np.asarray(p), 1e-4, 1 - 1e-4)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

    assert ll(out["ens_prob"]) < ll(test["lgbm_prob"])
