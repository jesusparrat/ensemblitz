"""Freeze a legacy v0 pre-kickoff game into a v1 snapshot without rewriting the file."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ensemblitz import contract as K
from ensemblitz import contract_io as IO
from ensemblitz import ledger as L

ROOT = Path(__file__).resolve().parents[1]
WEEK12_V0 = ROOT / "predictions" / "2026" / "week12" / "20261124T182645Z.json"
FRI_NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)
FRI_STAMP = "2026-11-27T22:00:00Z"
SAT_NOW = datetime(2026, 11, 28, 4, 0, tzinfo=UTC)
SAT_STAMP = "2026-11-28T04:00:00Z"


def _verify_mod():
    spec = importlib.util.spec_from_file_location(
        "verify_integrity_v0_freeze", ROOT / "scripts" / "verify_integrity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README").write_text("init\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "init")
    return repo


def _v0_week(*games: dict) -> dict:
    """Week header in the shape of predictions/2026/week12/20261124T182645Z.json."""
    raw = json.loads(WEEK12_V0.read_text())
    return {
        "season": raw["season"],
        "week": raw["week"],
        "generated_at": raw["generated_at"],
        "model_version": raw["model_version"],
        "ensemble_weights": raw["ensemble_weights"],
        "games": list(games),
    }


def _v1_game(v0_game: dict, generated: str, prob: float) -> dict:
    """A fresh v1 record for the same matchup. ``prob`` marks games that were not frozen."""
    return {
        "game_id": v0_game["game_id"],
        "home_team": v0_game["home_team"],
        "away_team": v0_game["away_team"],
        "kickoff_utc": v0_game["kickoff_utc"],
        "generated_at_utc": generated,
        "headline": {
            "home_win_prob": prob,
            "home_points": 24.0,
            "away_points": 20.0,
            "distribution": {
                "n_sims": 10,
                "seed": 1,
                "p_home": prob,
                "home_points": [10.0, 30.0],
                "away_points": [10.0, 30.0],
                "margin_home": [-5.0, 15.0],
                "total": [30.0, 60.0],
            },
            "example_score": {"home": 24, "away": 20, "prob": 0.01},
        },
        "ensemble": {"home_win_prob": prob, "margin_home": 4.0, "total": 44.0},
        "components": {"elo": 0.51, "kf": 0.52, "lgbm": 0.53, "lgbm_mkt": 0.54},
        "market": [
            {
                "source": "nflverse_line",
                "captured_at_utc": generated,
                "is_closing": False,
                "home_win_prob": 0.5,
                "margin_home": 1.0,
                "total_line": 44.0,
            }
        ],
        "context": {
            "home_qb_change": False,
            "away_qb_change": False,
            "home_rest_days": 7,
            "away_rest_days": 7,
            "dome": False,
            "weather_known": False,
            "temp_f": None,
            "wind_mph": None,
            "home_out_lag": 0,
            "away_out_lag": 0,
        },
        "absences": {"home": [], "away": []},
        "news_adjustment": {"applied": False, "applies_to": "ensemble"},
    }


def _v1_week(v0_doc: dict, games: list[dict], generated: str) -> dict:
    return {
        "schema_version": "1",
        "model_version": v0_doc["model_version"],
        "git_sha": "0" * 40,
        "reproducible": False,
        "generated_at_utc": generated,
        "data_cutoff_utc": v0_doc["generated_at"],
        "data_snapshot": {"data/raw/schedules.parquet": "a" * 64},
        "season": v0_doc["season"],
        "week": v0_doc["week"],
        "ensemble_weights": v0_doc["ensemble_weights"],
        "games": games,
    }


def _assert_frozen_probs(frozen: dict, v0_game: dict) -> None:
    mo = v0_game["model_only"]
    hwp = v0_game["home_win_prob"]
    assert frozen["headline"]["home_win_prob"] == mo["home_win_prob"]
    assert frozen["ensemble"]["home_win_prob"] == hwp["ensemble"]
    assert frozen["ensemble"]["margin_home"] == v0_game["predicted_margin"]
    assert frozen["ensemble"]["total"] == v0_game["predicted_total"]
    for key in ("elo", "kf", "lgbm", "lgbm_mkt"):
        assert frozen["components"][key] == hwp[key]
    assert frozen["market"][0]["home_win_prob"] == hwp["market"]
    assert L.canonical_game_v1(frozen) == L.canonical_game_v1(v0_game)


def _place_v0(repo: Path, doc: dict, name: str = "20261124T182645Z.json") -> Path:
    dest = repo / "predictions" / "2026" / "week12" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1) + "\n")
    return dest


def test_midweek_run_freezes_v0_thursday_into_valid_v1(tmp_path: Path) -> None:
    raw = json.loads(WEEK12_V0.read_text())
    by_src = {g["game_id"]: g for g in raw["games"]}
    thu = by_src["2026_12_GB_LA"]
    sun = by_src["2026_12_ATL_MIN"]
    assert IO.is_v0_game(thu)
    assert "generated_at" in thu and "home_win_prob" in thu and "model_version" in thu

    repo = _init_repo(tmp_path)
    v0_doc = _v0_week(thu, sun)
    v0_path = _place_v0(repo, v0_doc)
    v0_bytes = v0_path.read_bytes()
    L.refresh_manifest(repo)

    fresh = [_v1_game(thu, FRI_STAMP, 0.11), _v1_game(sun, FRI_STAMP, 0.73)]
    frozen_games = L.freeze_started_games(2026, 12, fresh, now=FRI_NOW, root=repo)
    doc = _v1_week(v0_doc, frozen_games, FRI_STAMP)
    assert K.validate_week(doc) == []

    by_id = {g["game_id"]: g for g in doc["games"]}
    assert not IO.is_v0_game(by_id["2026_12_GB_LA"])
    _assert_frozen_probs(by_id["2026_12_GB_LA"], thu)
    assert by_id["2026_12_ATL_MIN"]["headline"]["home_win_prob"] == 0.73

    written = L.write_snapshot(doc, root=repo, force=True, now=FRI_NOW)
    assert written.exists()
    assert v0_path.read_bytes() == v0_bytes
    assert K.validate_week(json.loads(written.read_text())) == []
    assert _verify_mod().verify(repo, base_ref="HEAD") == []

    mutated = json.loads(json.dumps(doc))
    mutated["games"][0]["ensemble"]["home_win_prob"] = 0.99
    with pytest.raises(L.WeekLockedError, match="differs from its frozen canonical"):
        L.write_snapshot(
            {**mutated, "generated_at_utc": "2026-11-27T23:00:00Z"},
            root=repo,
            force=True,
            now=FRI_NOW,
        )


def test_real_week12_v0_freezes_at_saturday_cutoff(tmp_path: Path) -> None:
    """Offline: the published week-12 v0 file, frozen as of 2026-11-28T04:00Z."""
    original = WEEK12_V0.read_bytes()
    raw = json.loads(original)
    repo = _init_repo(tmp_path)
    dest = repo / "predictions" / "2026" / "week12" / WEEK12_V0.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WEEK12_V0, dest)
    L.refresh_manifest(repo)

    fresh = [_v1_game(g, SAT_STAMP, 0.42) for g in raw["games"]]
    frozen_games = L.freeze_started_games(2026, 12, fresh, now=SAT_NOW, root=repo)
    doc = _v1_week(raw, frozen_games, SAT_STAMP)
    assert K.validate_week(doc) == []

    v0_by_id = {g["game_id"]: g for g in raw["games"]}
    started = 0
    for game in doc["games"]:
        src = v0_by_id[game["game_id"]]
        if src["kickoff_utc"] <= SAT_STAMP:
            started += 1
            _assert_frozen_probs(game, src)
        else:
            assert game["headline"]["home_win_prob"] == 0.42
    assert started == 5

    written = L.write_snapshot(doc, root=repo, force=True, now=SAT_NOW)
    assert K.validate_week(json.loads(written.read_text())) == []
    assert dest.read_bytes() == original
    assert WEEK12_V0.read_bytes() == original
    assert _verify_mod().verify(repo, base_ref="HEAD") == []
