"""Append-only ledger: no overwrites, kickoff lock, historical snapshots stay byte-identical."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ensemblitz import contract as K
from ensemblitz import ledger as L

ROOT = Path(__file__).resolve().parents[1]


def _doc(season=2026, week=99, generated="2099-01-01T00:00:00Z", kick="2099-12-01T00:00:00Z"):
    return {
        "schema_version": "1",
        "model_version": "0.1.0",
        "git_sha": "0" * 40,
        "reproducible": False,
        "generated_at_utc": generated,
        "data_cutoff_utc": "2098-12-31T00:00:00Z",
        "data_snapshot": {"data/raw/schedules.parquet": "a" * 64},
        "season": season,
        "week": week,
        "ensemble_weights": {},
        "games": [
            {
                "game_id": f"{season}_{week:02d}_AAA_BBB",
                "home_team": "BBB",
                "away_team": "AAA",
                "kickoff_utc": kick,
                "generated_at_utc": generated,
                "headline": {
                    "home_win_prob": 0.6,
                    "home_points": 24.0,
                    "away_points": 20.0,
                    "distribution": {
                        "n_sims": 10,
                        "seed": 1,
                        "p_home": 0.6,
                        "home_points": [10, 30],
                        "away_points": [10, 30],
                        "margin_home": [-5, 15],
                        "total": [30, 60],
                    },
                    "example_score": {"home": 24, "away": 20, "prob": 0.01},
                },
                "ensemble": {"home_win_prob": 0.6, "margin_home": 4.0, "total": 44.0},
                "components": {"elo": 0.55, "kf": 0.56, "lgbm": 0.58},
                "market": [
                    {
                        "source": "nflverse_line",
                        "captured_at_utc": generated,
                        "is_closing": False,
                        "home_win_prob": 0.58,
                        "margin_home": 3.0,
                        "total_line": 43.5,
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
        ],
    }


def test_write_snapshot_refuses_overwrite(tmp_path: Path) -> None:
    doc = _doc()
    path = L.write_snapshot(doc, root=tmp_path, force=False)
    assert path.exists()
    first = path.read_bytes()
    with pytest.raises(L.SnapshotExistsError):
        L.write_snapshot(
            {**doc, "generated_at_utc": "2099-01-02T00:00:00Z"}, root=tmp_path, force=False
        )
    # --force before kickoff writes a *new* file and leaves the first untouched
    second = L.write_snapshot(
        {**doc, "generated_at_utc": "2099-01-02T00:00:00Z"}, root=tmp_path, force=True
    )
    assert second != path
    assert path.read_bytes() == first
    assert L.load_manifest(tmp_path)[path.relative_to(tmp_path).as_posix()] == K.sha256_file(path)


def test_kickoff_lock_cannot_be_forced(tmp_path: Path) -> None:
    past = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = _doc(kick=past, generated="2099-01-01T00:00:00Z")
    with pytest.raises(L.WeekLockedError):
        L.write_snapshot(doc, root=tmp_path, force=False)
    with pytest.raises(L.WeekLockedError):
        L.write_snapshot(doc, root=tmp_path, force=True)
    assert list(tmp_path.joinpath("predictions").rglob("*.json")) == []


def test_historical_week12_snapshots_are_byte_identical() -> None:
    directory = ROOT / "predictions" / "2026" / "week12"
    found = {p.read_bytes() for p in directory.glob("*.json")}
    found.add((ROOT / "predictions/2026/week12.json").read_bytes())
    for sha in L.WEEK12_HISTORY:
        blob = (
            subprocess.check_output(
                ["git", "rev-parse", f"{sha}:predictions/2026/week12.json"], cwd=ROOT
            )
            .decode()
            .strip()
        )
        raw = subprocess.check_output(["git", "cat-file", "-p", blob], cwd=ROOT)
        assert raw in found, sha
        # and a ledger file exists whose bytes match exactly
        matches = [p for p in directory.glob("*.json") if p.read_bytes() == raw]
        assert matches, sha
        assert hashlib.sha256(matches[0].read_bytes()).digest() == hashlib.sha256(raw).digest()


def test_manifest_has_no_self_hash_or_first_commit() -> None:
    doc = json.loads((ROOT / "predictions" / "MANIFEST.json").read_text())
    assert "first_commit" not in doc
    assert L.MANIFEST_REL not in doc["artifacts"]
    assert "MANIFEST.json" not in doc["artifacts"]
    on_disk = {a.rel: a.sha256 for a in L.iter_artifacts(ROOT)}
    assert doc["artifacts"] == on_disk
