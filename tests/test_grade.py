"""Per-game pre-kickoff selection, tie-breaking, headline kinds and no post-kickoff fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ensemblitz import grade as G
from ensemblitz import ledger as L


def _v1_game(
    game_id: str,
    home: str,
    away: str,
    kickoff: str,
    generated: str,
    home_prob: float,
    ens_prob: float | None = None,
) -> dict:
    ep = home_prob if ens_prob is None else ens_prob
    return {
        "game_id": game_id,
        "home_team": home,
        "away_team": away,
        "kickoff_utc": kickoff,
        "generated_at_utc": generated,
        "headline": {
            "home_win_prob": home_prob,
            "home_points": 24.0 if home_prob >= 0.5 else 20.0,
            "away_points": 20.0 if home_prob >= 0.5 else 24.0,
            "distribution": {
                "n_sims": 100,
                "seed": 1,
                "p_home": home_prob,
                "home_points": [14.0, 34.0],
                "away_points": [10.0, 30.0],
                "margin_home": [-6.0, 14.0],
                "total": [34.0, 54.0],
            },
            "example_score": {"home": 24, "away": 20, "prob": 0.02},
        },
        "ensemble": {
            "home_win_prob": ep,
            "margin_home": 4.0 if ep >= 0.5 else -4.0,
            "total": 44.0,
        },
        "components": {"elo": 0.55, "kf": 0.56, "lgbm": home_prob},
        "market": [
            {
                "source": "nflverse_line",
                "captured_at_utc": generated,
                "is_closing": False,
                "home_win_prob": 0.55,
                "margin_home": 2.5,
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


def _v1_doc(season: int, week: int, generated: str, games: list[dict]) -> dict:
    return {
        "schema_version": "1",
        "model_version": "0.1.0",
        "git_sha": "0" * 40,
        "reproducible": False,
        "generated_at_utc": generated,
        "data_cutoff_utc": generated,
        "data_snapshot": {"data/raw/schedules.parquet": "a" * 64},
        "season": season,
        "week": week,
        "ensemble_weights": {},
        "games": games,
    }


def _write_raw(root: Path, rel: str, doc: dict) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n")
    return path


def test_grade_never_falls_back_to_post_kickoff_snapshot(tmp_path: Path) -> None:
    """Red test: a game with only post-kickoff snapshots is ungradable and never graded."""
    late = _v1_doc(
        2026,
        13,
        "2026-12-04T02:00:00Z",
        [
            _v1_game(
                "2026_13_AAA_BBB",
                "BBB",
                "AAA",
                kickoff="2026-12-04T01:15:00Z",
                generated="2026-12-04T02:00:00Z",
                home_prob=0.80,
            ),
            # Exact-at-kickoff (published == kickoff_utc) must also be rejected (strictly before).
            _v1_game(
                "2026_13_CCC_DDD",
                "DDD",
                "CCC",
                kickoff="2026-12-04T02:00:00Z",
                generated="2026-12-04T02:00:00Z",
                home_prob=0.75,
            ),
        ],
    )
    _write_raw(tmp_path, "predictions/2026/week13/20261204T020000Z.json", late)
    assert G.select_pre_kickoff_picks(tmp_path) == {}

    sched = pd.DataFrame(
        [
            {"game_id": "2026_13_AAA_BBB", "result": 7.0, "total": 45.0},
            {"game_id": "2026_13_CCC_DDD", "result": 3.0, "total": 41.0},
        ]
    )
    summary = G.run_grade(root=tmp_path, schedule=sched)
    assert summary["n_graded"] == 0
    assert not (tmp_path / "results" / "2026" / "week13.json").exists()


def test_select_pre_kickoff_picks_tie_breaks_by_published_and_rel(
    tmp_path: Path, monkeypatch
) -> None:
    """Two snapshots with identical publication timestamp pick deterministic max(rel)."""
    ts = "2026-12-01T12:00:00Z"
    doc_a = _v1_doc(
        2026,
        13,
        ts,
        [
            _v1_game(
                "2026_13_AAA_BBB",
                "BBB",
                "AAA",
                kickoff="2026-12-06T18:00:00Z",
                generated=ts,
                home_prob=0.61,
            )
        ],
    )
    doc_b = _v1_doc(
        2026,
        13,
        ts,
        [
            _v1_game(
                "2026_13_AAA_BBB",
                "BBB",
                "AAA",
                kickoff="2026-12-06T18:00:00Z",
                generated=ts,
                home_prob=0.72,
            )
        ],
    )
    # Lexicographically: "...20261201T120000Z.json" > "...20261201T120000Z-11111111.json"
    # because '.' (0x2E) > '-' (0x2D).
    p_dash = _write_raw(tmp_path, "predictions/2026/week13/20261201T120000Z-11111111.json", doc_a)
    p_plain = _write_raw(tmp_path, "predictions/2026/week13/20261201T120000Z.json", doc_b)

    arts = [L.describe(p_plain, tmp_path), L.describe(p_dash, tmp_path)]
    # Reverse iteration order deliberately: the old (prev[1], "") bug let the later
    # iterated artifact win instead of the lexicographically greater rel.
    monkeypatch.setattr(L, "iter_artifacts", lambda _root=None: list(arts))
    picked_rev = G.select_pre_kickoff_picks(tmp_path)
    monkeypatch.setattr(L, "iter_artifacts", lambda _root=None: list(reversed(arts)))
    picked_fwd = G.select_pre_kickoff_picks(tmp_path)

    expected_rel = "predictions/2026/week13/20261201T120000Z.json"
    assert picked_rev["2026_13_AAA_BBB"][2] == expected_rel
    assert picked_fwd["2026_13_AAA_BBB"][2] == expected_rel
    assert picked_rev["2026_13_AAA_BBB"][0]["headline"]["home_win_prob"] == 0.72
    assert picked_fwd["2026_13_AAA_BBB"][0]["headline"]["home_win_prob"] == 0.72


def test_grade_uses_per_game_headline_kinds(tmp_path: Path) -> None:
    """Mixed v0 snapshot: each game is graded under its own headline_kinds[game_id]."""
    ctx = {
        "home_qb_change": 0,
        "away_qb_change": 0,
        "home_rest": 7,
        "away_rest": 7,
        "dome": 0,
        "weather_known": 0,
        "temp": None,
        "wind": None,
        "home_out_lag": 0,
        "away_out_lag": 0,
    }
    doc = {
        "season": 2026,
        "week": 13,
        "generated_at": "2026-12-01T12:00:00Z",
        "games": [
            {
                "game_id": "2026_13_AAA_BBB",
                "season": 2026,
                "week": 13,
                "home_team": "BBB",
                "away_team": "AAA",
                "kickoff_utc": "2026-12-06T18:00:00Z",
                "generated_at": "2026-12-01T12:00:00Z",
                "headline": "model_only",
                "pick": "BBB",
                "predicted_margin": -2.0,
                "predicted_total": 44.0,
                "home_win_prob": {
                    "ensemble": 0.40,
                    "ensemble_model_only": 0.65,
                    "market": 0.50,
                    "elo": 0.65,
                    "kf": 0.65,
                    "lgbm": 0.65,
                },
                "model_only": {
                    "home_win_prob": 0.65,
                    "margin": 4.0,
                    "total": 44.0,
                    "home_points": 24.0,
                    "away_points": 20.0,
                    "sim": {
                        "p_home": 0.65,
                        "home_q10": 14.0,
                        "home_q90": 34.0,
                        "away_q10": 10.0,
                        "away_q90": 30.0,
                        "margin_q10": -6.0,
                        "margin_q90": 14.0,
                        "total_q10": 34.0,
                        "total_q90": 54.0,
                    },
                    "example_score": {"home": 24, "away": 20, "prob": 0.02},
                },
                "market": {"spread_line": 1.0, "total_line": 44.0},
                "context": ctx,
            },
            {
                # Legacy game with no model_only block -> headline_kinds is "ensemble".
                "game_id": "2026_13_CCC_DDD",
                "season": 2026,
                "week": 13,
                "home_team": "DDD",
                "away_team": "CCC",
                "kickoff_utc": "2026-12-06T18:00:00Z",
                "generated_at": "2026-12-01T12:00:00Z",
                "pick": "CCC",
                "predicted_margin": -3.0,
                "predicted_total": 42.0,
                "home_win_prob": {
                    "ensemble": 0.42,
                    "market": 0.45,
                    "elo": 0.42,
                    "kf": 0.42,
                    "lgbm": 0.42,
                },
                "sim": {
                    "p_home": 0.42,
                    "margin_q10": -15.0,
                    "margin_q90": 9.0,
                    "total_q10": 30.0,
                    "total_q90": 54.0,
                },
                "most_likely_score": {"home": 20, "away": 23, "prob": 0.02},
                "market": {"spread_line": -2.0, "total_line": 42.0},
                "context": ctx,
            },
        ],
    }
    _write_raw(tmp_path, "predictions/2026/week13/20261201T120000Z.json", doc)

    picked = G.select_pre_kickoff_picks(tmp_path)
    assert picked["2026_13_AAA_BBB"][3] == "model_only"
    assert picked["2026_13_CCC_DDD"][3] == "ensemble"

    sched = pd.DataFrame(
        [
            {"game_id": "2026_13_AAA_BBB", "result": 7.0, "total": 45.0},
            {"game_id": "2026_13_CCC_DDD", "result": -3.0, "total": 41.0},
        ]
    )
    summary = G.run_grade(root=tmp_path, schedule=sched)
    assert summary["n_graded"] == 2
    rows = json.loads((tmp_path / "results" / "2026" / "week13.json").read_text())
    by_id = {r["game_id"]: r for r in rows}
    assert by_id["2026_13_AAA_BBB"]["headline"] == "model_only"
    assert by_id["2026_13_AAA_BBB"]["pick"] == "BBB"
    assert by_id["2026_13_AAA_BBB"]["headline_correct"] == 1
    assert by_id["2026_13_CCC_DDD"]["headline"] == "ensemble"
    assert by_id["2026_13_CCC_DDD"]["pick"] == "CCC"
    assert by_id["2026_13_CCC_DDD"]["headline_correct"] == 1


def test_grade_thursday_to_friday_picks_per_game_latest_pre_kickoff(tmp_path: Path) -> None:
    """Thu game grades from Tuesday snapshot; Sun game grades from Friday snapshot."""
    tue_thu = _v1_game(
        "2026_13_AAA_BBB",
        "BBB",
        "AAA",
        kickoff="2026-12-04T01:15:00Z",
        generated="2026-12-01T07:00:00Z",
        home_prob=0.62,
    )
    tue_sun = _v1_game(
        "2026_13_CCC_DDD",
        "DDD",
        "CCC",
        kickoff="2026-12-06T18:00:00Z",
        generated="2026-12-01T07:00:00Z",
        home_prob=0.45,
    )
    fri_sun = _v1_game(
        "2026_13_CCC_DDD",
        "DDD",
        "CCC",
        kickoff="2026-12-06T18:00:00Z",
        generated="2026-12-04T22:00:00Z",
        home_prob=0.68,
    )
    _write_raw(
        tmp_path,
        "predictions/2026/week13/20261201T070000Z.json",
        _v1_doc(2026, 13, "2026-12-01T07:00:00Z", [tue_thu, tue_sun]),
    )
    _write_raw(
        tmp_path,
        "predictions/2026/week13/20261204T220000Z.json",
        _v1_doc(2026, 13, "2026-12-04T22:00:00Z", [tue_thu, fri_sun]),
    )

    picked = G.select_pre_kickoff_picks(tmp_path)
    assert picked["2026_13_AAA_BBB"][1] == "2026-12-01T07:00:00Z"
    assert picked["2026_13_CCC_DDD"][1] == "2026-12-04T22:00:00Z"
    assert picked["2026_13_CCC_DDD"][0]["headline"]["home_win_prob"] == 0.68

    sched = pd.DataFrame(
        [
            {"game_id": "2026_13_AAA_BBB", "result": 7.0, "total": 44.0},
            {"game_id": "2026_13_CCC_DDD", "result": 6.0, "total": 46.0},
        ]
    )
    summary = G.run_grade(root=tmp_path, schedule=sched)
    assert summary["n_graded"] == 2
    rows = json.loads((tmp_path / "results" / "2026" / "week13.json").read_text())
    by_id = {r["game_id"]: r for r in rows}
    assert by_id["2026_13_AAA_BBB"]["pick"] == "BBB"
    assert by_id["2026_13_CCC_DDD"]["pick"] == "DDD"
    assert by_id["2026_13_CCC_DDD"]["headline_correct"] == 1
