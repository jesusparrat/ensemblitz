"""Phase 0 baseline: walk-forward stacking has no leakage, metrics behave, gate catches regressions."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ensemblitz import baseline as B
from ensemblitz.models.market import margin_to_prob

ROOT = Path(__file__).resolve().parents[1]


def _frame(seed: int = 0) -> pd.DataFrame:
    """Synthetic 2016-2019 league with every component column the stacker needs."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2020):
        for week in range(1, 19):
            for g in range(14):
                truth = rng.normal(0, 6)
                result = float(np.round(truth + rng.normal(0, 13)))
                row = {
                    "game_id": f"{season}_{week:02d}_A{g}_H{g}",
                    "season": season,
                    "week": week,
                    "played": True,
                    "result": result,
                    "total": 44 + rng.normal(0, 10),
                    "total_line": 44 + rng.normal(0, 2),
                    "kf_total": 44 + rng.normal(0, 3),
                }
                for c, sd in {"market": 1, "elo": 4, "kf": 4, "lgbm": 5, "lgbm_mkt": 2}.items():
                    m = truth + rng.normal(0, sd)
                    row[f"{c}_margin"] = m
                    row[f"{c}_prob"] = float(margin_to_prob(m))
                row["spread_line"] = row["market_margin"]
                rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def frame():
    return _frame()


@pytest.fixture(scope="module")
def walked(frame):
    return B.walk_forward(frame)


def test_probabilities_are_valid(walked):
    wf, folds = walked
    for c in ("ens", "model_only", "ens_cap1", "ens_pool", "mo_cap1"):
        p = wf[f"{c}_prob"].dropna()
        assert len(p) > 400
        assert ((p >= 0) & (p <= 1)).all(), c
        assert np.isfinite(p).all()
    assert folds and all(f["season"] >= 2018 and f["week"] <= 18 for f in folds)


def test_no_future_week_used_in_a_week_prediction(frame, walked):
    """Scrambling results and components from week W on must not move any earlier prediction."""
    wf, _ = walked
    season, week = 2018, 10
    future = (frame["season"] > season) | ((frame["season"] == season) & (frame["week"] >= week))
    bad = frame.copy()
    rng = np.random.default_rng(1)
    bad.loc[future, "result"] = rng.normal(0, 30, int(future.sum())).round()
    for c in ("market", "elo", "kf", "lgbm", "lgbm_mkt"):
        bad.loc[future, f"{c}_prob"] = rng.uniform(0.05, 0.95, int(future.sum()))
        bad.loc[future, f"{c}_margin"] = rng.normal(0, 8, int(future.sum()))
    wf2, _ = B.walk_forward(bad)
    # the predictions of week W itself use only weeks < W: they must not move either
    # (their own inputs are scrambled, so compare the fits through earlier-week predictions)
    before = ~future
    for c in ("ens_prob", "mo_prob", "ens_cap1_prob", "ens_pool_prob"):
        a, b = wf.loc[before, c].to_numpy(), wf2.loc[before, c].to_numpy()
        assert np.allclose(a, b, equal_nan=True), c


def test_week_prediction_ignores_its_own_result(frame, walked):
    wf, _ = walked
    season, week = 2019, 5
    m = (frame["season"] == season) & (frame["week"] == week)
    bad = frame.copy()
    bad.loc[m, "result"] = 99.0
    wf2, _ = B.walk_forward(bad)
    for c in ("ens_prob", "mo_prob", "ens_cap1_prob", "ens_pool_prob"):
        assert np.allclose(wf.loc[m, c], wf2.loc[m, c]), c


def test_constrained_stacks_respect_their_constraints(frame):
    pool = frame[frame["season"] < 2018]
    comps = ["market", "elo", "kf", "lgbm", "lgbm_mkt"]
    cap = B.fit_logit_stack(pool, comps, "cap1")
    pooled = B.fit_logit_stack(pool, comps, "pool")
    assert cap.w.min() >= -1e-9 and cap.w.sum() <= 1 + 1e-6
    assert pooled.w.min() >= -1e-9 and abs(pooled.w.sum() - 1) < 1e-6 and pooled.b == 0


def test_calibration_slope_is_one_for_calibrated_probabilities():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.1, 0.9, 40_000)
    y = (rng.uniform(size=p.size) < p).astype(float)
    a, b = B.calib_slope(p, y)
    assert abs(a) < 0.05 and abs(b - 1) < 0.05
    # overconfident forecasts (pushed away from 0.5) have slope below 1
    q = 1 / (1 + np.exp(-2 * np.log(p / (1 - p))))
    assert B.calib_slope(q, y)[1] < 0.7


def test_bootstrap_ci_contains_point_estimate(frame, walked):
    wf, _ = walked
    d = B.scoring_frame(wf)
    y = B.outcomes(d)
    bs = B.bootstrap(d, y, n=300)
    for k, v in bs["diff_vs_market"].items():
        if "_minus_" in k:
            continue
        lo, hi = v["log_loss_ci"]
        assert lo <= v["log_loss"] <= hi, k


def test_heavy_favourite_bins_partition_games(walked):
    wf, _ = walked
    d = B.scoring_frame(wf)
    y = B.outcomes(d)
    p = d["ens_prob"].to_numpy(float)
    assert sum(r["n"] for r in B.favourite_bins(p, y)) == len(y)
    assert sum(r["n"] for r in B.deciles(p, y)) == len(y)


def test_finite_replaces_nan_with_null():
    out = B.finite({"a": float("nan"), "b": [np.float64("inf"), 1.0], "c": np.int64(2)})
    assert out == {"a": None, "b": [None, 1.0], "c": 2}
    json.dumps(out, allow_nan=False)


def test_committed_baseline_is_valid_json_and_consistent():
    path = ROOT / "reports" / "baseline_2018_2025.json"
    if not path.exists():
        pytest.skip("baseline not generated")

    def bad(c):
        raise ValueError(c)

    res = json.loads(path.read_text(), parse_constant=bad)
    g = res["gate"]
    for k in ("model_only", "ens", "market"):
        assert g[k]["log_loss"] == res["overall"][k]["log_loss"]
        assert 0.0 < g[k]["accuracy"] < 1.0
    assert res["n_games"] == g["n_games"]


def test_cached_components_probabilities_in_unit_interval():
    path = B.CACHE_PATH
    if not path.exists():
        pytest.skip("component cache not generated")
    df = B.load_cache()
    for c in B.COMPS:
        p = df[f"{c}_prob"].dropna()
        assert ((p >= 0) & (p <= 1)).all(), c


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "check_baseline", ROOT / "scripts/check_baseline.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_baseline"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gate_passes_on_identical_numbers_and_fails_on_regression(monkeypatch, capsys):
    gate = _load_gate()
    base = {
        "gate": {
            "tolerance_log_loss": 0.0015,
            "tolerance_brier": 0.0007,
            "n_games": 100,
            "model_only": {"log_loss": 0.63, "brier": 0.22},
            "ens": {"log_loss": 0.61, "brier": 0.21},
            "market": {"log_loss": 0.60, "brier": 0.21},
        }
    }
    same = {"n_games": 100, **{k: dict(v) for k, v in base["gate"].items() if isinstance(v, dict)}}
    monkeypatch.setattr(gate, "load_baseline", lambda ref: (base, "test"))
    monkeypatch.setattr(B, "load_cache", lambda: pd.DataFrame())
    monkeypatch.setattr(B, "gate_metrics", lambda df: same)
    monkeypatch.setattr(sys, "argv", ["check_baseline.py"])
    assert gate.main() == 0

    worse = json.loads(json.dumps(same))
    worse["ens"]["log_loss"] += 0.01
    monkeypatch.setattr(B, "gate_metrics", lambda df: worse)
    assert gate.main() == 1
    assert "ens log_loss" in capsys.readouterr().err

    slightly = json.loads(json.dumps(same))
    slightly["model_only"]["brier"] += 0.0003  # inside the tolerance
    monkeypatch.setattr(B, "gate_metrics", lambda df: slightly)
    assert gate.main() == 0
