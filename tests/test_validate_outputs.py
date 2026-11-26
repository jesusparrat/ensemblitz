"""Tests for scripts/validate_outputs.py odds-report schema and governance checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_outputs", ROOT / "scripts" / "validate_outputs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _valid_report() -> dict:
    return {
        "season": 2026,
        "week": 11,
        "market_source": "The Odds API",
        "market_type": "h2h",
        "consensus_method": "unweighted mean of per-operator Shin no-vig probabilities",
        "odds_fetched_at": "2026-11-17T20:54:38Z",
        "predictions_generated_at": "2026-11-17T22:07:57Z",
        "games": [
            {
                "game_id": "2026_11_IND_HOU",
                "home": "HOU",
                "away": "IND",
                "kickoff_utc": "2026-11-20T01:15:00Z",
                "model_only_home_prob": 0.7452,
                "consensus_home_prob_shin": 0.8577,
                "gap_model_only": -0.1125,
                "n_books": 42,
                "flag_large_disagreement": True,
            }
        ],
    }


def test_validate_odds_report_accepts_valid_schema():
    mod = _load_validator()
    assert mod.validate_odds_report(_valid_report(), "2026_week11.json") == []


def test_validate_odds_report_fails_on_missing_required_fields():
    mod = _load_validator()
    rep = _valid_report()
    del rep["games"][0]["model_only_home_prob"]
    errs = mod.validate_odds_report(rep, "2026_week11.json")
    assert any("missing required field model_only_home_prob" in e for e in errs)

    rep_none = _valid_report()
    rep_none["games"][0]["consensus_home_prob_shin"] = None
    errs_none = mod.validate_odds_report(rep_none, "2026_week11.json")
    assert any("missing required field consensus_home_prob_shin" in e for e in errs_none)


def test_validate_odds_report_fails_on_forbidden_legacy_fields():
    mod = _load_validator()
    rep = _valid_report()
    rep["games"][0]["our_home_prob"] = 0.80
    rep["games"][0]["books"] = {"pinnacle": {"home_price": 1.2}}
    errs = mod.validate_odds_report(rep, "2026_week11.json")
    assert any("forbidden odds fields" in e for e in errs)
