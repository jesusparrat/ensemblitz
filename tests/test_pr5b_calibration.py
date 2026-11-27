"""Tests for PR 5b isolated walk-forward calibration experiment."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        "audit_pr5b_calibration", ROOT / "scripts" / "audit_pr5b_calibration.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_pr5b_summary_artifact_is_consistent_and_nan_free() -> None:
    summary_path = ROOT / "reports" / "pr5b_calibration_summary.json"
    report_path = ROOT / "docs" / "audit" / "pr5b-calibration-experiment.md"
    assert summary_path.exists()
    assert report_path.exists()
    raw = summary_path.read_text(encoding="utf-8")
    assert "NaN" not in raw and "Infinity" not in raw
    doc = json.loads(raw)
    assert doc["n_games"] == 2133
    assert doc["decision"] == "not_wired"
    for key in ("model_only", "mo_cap1", "mo_pool", "mo_temp", "mo_platt", "mo_iso", "market"):
        v = doc["variants"][key]
        assert math.isfinite(v["log_loss"])
        assert math.isfinite(v["brier"])
    # Isotonic regression must show significant degradation (lower CI > 0)
    assert doc["variants"]["mo_iso"]["paired_vs_model_only"]["2w"]["delta_log_loss_ci95"][0] > 0.0
    # Report must contain zero em dashes
    assert "\u2014" not in report_path.read_text(encoding="utf-8")


def test_pr5b_walk_forward_variants_have_no_future_leakage() -> None:
    mod = _load_mod()
    raw = pd.read_parquet(ROOT / "reports" / "baseline_components.parquet")
    cut = (2023, 6)
    alt = raw.copy()
    after = (alt["season"] > cut[0]) | ((alt["season"] == cut[0]) & (alt["week"] >= cut[1]))
    alt.loc[after, "result"] = -alt.loc[after, "result"]

    base_out = mod.run_walk_forward_variants(raw)
    alt_out = mod.run_walk_forward_variants(alt)

    before = (base_out["season"] < cut[0]) | (
        (base_out["season"] == cut[0]) & (base_out["week"] < cut[1])
    )
    cols = [
        "model_only_prob",
        "mo_cap1_prob",
        "mo_pool_prob",
        "mo_temp_prob",
        "mo_platt_prob",
        "mo_iso_prob",
    ]
    pd.testing.assert_frame_equal(
        base_out.loc[before, cols].reset_index(drop=True),
        alt_out.loc[before, cols].reset_index(drop=True),
    )
    # Non-vacuous check: later predictions DO change when future outcomes flip
    later = (base_out["season"] > cut[0]) & base_out["mo_temp_prob"].notna()
    assert not np.allclose(
        base_out.loc[later, "mo_temp_prob"].to_numpy(),
        alt_out.loc[later, "mo_temp_prob"].to_numpy(),
    )
