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


def test_snapshot_filename_is_ntfs_safe() -> None:
    name = L.snapshot_filename("2026-11-24T18:26:45Z", "deadbeef" * 8, set())
    assert name == "20261124T182645Z.json"
    assert ":" not in name
    collided = L.snapshot_filename("2026-11-24T18:26:45Z", "deadbeef" * 8, {name})
    assert collided == "20261124T182645Z-deadbeef.json"
    assert ":" not in collided


def test_open_next_weeks_skips_locked_week_with_unplayed_mnf(tmp_path: Path) -> None:
    import pandas as pd

    from ensemblitz.predict import open_next_weeks

    feats = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 12,
                "played": True,
                "kickoff_utc": pd.Timestamp("2026-11-26T01:00:00Z"),
            },
            {
                "season": 2026,
                "week": 12,
                "played": False,  # MNF score not yet posted
                "kickoff_utc": pd.Timestamp("2026-12-01T01:15:00Z"),
            },
            {
                "season": 2026,
                "week": 13,
                "played": False,
                "kickoff_utc": pd.Timestamp("2026-12-04T01:15:00Z"),
            },
        ]
    )
    now = datetime(2026, 12, 1, 7, 0, tzinfo=UTC)
    assert open_next_weeks(feats, 2026, n=1, now=now, root=tmp_path) == [13]


def _two_game_doc(
    *,
    generated: str,
    thu_prob: float = 0.62,
    sun_prob: float = 0.55,
    thu_market_prob: float = 0.58,
    thu_lead: str = "lgbm",
    sun_lead: str = "elo",
) -> dict:
    base = _doc(season=2026, week=98, generated=generated, kick="2099-11-26T01:15:00Z")
    thu = json.loads(json.dumps(base["games"][0]))
    thu["game_id"] = "2026_98_AAA_BBB"
    thu["kickoff_utc"] = "2099-11-26T01:15:00Z"
    thu["headline"]["home_win_prob"] = thu_prob
    thu["market"][0]["home_win_prob"] = thu_market_prob
    thu["explanation"] = {
        "summary": {
            "lead_component": thu_lead,
            "lead_component_margin_home": 3.2,
            "top_matchup_id": "home_pass",
            "lgbm_top_group": "pass_game",
            "lgbm_top_group_margin_home": 1.8,
            "qb_change_teams": [],
        }
    }

    sun = json.loads(json.dumps(base["games"][0]))
    sun["game_id"] = "2026_98_CCC_DDD"
    sun["away_team"] = "CCC"
    sun["home_team"] = "DDD"
    sun["kickoff_utc"] = "2099-11-29T18:00:00Z"
    sun["headline"]["home_win_prob"] = sun_prob
    sun["explanation"] = {
        "summary": {
            "lead_component": sun_lead,
            "lead_component_margin_home": 1.4,
            "top_matchup_id": "away_rush",
            "lgbm_top_group": "efficiency",
            "lgbm_top_group_margin_home": 0.9,
            "qb_change_teams": [],
        }
    }
    base["games"] = [thu, sun]
    return base


def test_canonical_game_json_is_key_order_invariant_and_covers_all_fields() -> None:
    g1 = _two_game_doc(generated="2099-11-24T07:00:00Z")["games"][0]
    g2 = {k: g1[k] for k in reversed(list(g1.keys()))}
    assert L.canonical_game_json(g1) == L.canonical_game_json(g2)

    # Mutating any nested field (market or explanation) changes canonical output.
    g_mkt = json.loads(json.dumps(g1))
    g_mkt["market"][0]["home_win_prob"] = 0.59
    assert L.canonical_game_json(g1) != L.canonical_game_json(g_mkt)

    g_exp = json.loads(json.dumps(g1))
    g_exp["explanation"]["summary"]["lead_component"] = "kf"
    assert L.canonical_game_json(g1) != L.canonical_game_json(g_exp)


def test_thursday_to_friday_publication_preserves_every_started_game_field(tmp_path: Path) -> None:
    tue_now = datetime(2099, 11, 24, 7, 0, tzinfo=UTC)
    fri_now = datetime(2099, 11, 27, 22, 0, tzinfo=UTC)

    tue_doc = _two_game_doc(
        generated="2099-11-24T07:00:00Z",
        thu_prob=0.62,
        sun_prob=0.55,
        thu_market_prob=0.58,
        thu_lead="lgbm",
        sun_lead="elo",
    )
    p1 = L.write_snapshot(tue_doc, root=tmp_path, force=False, now=tue_now)
    tue_bytes = p1.read_bytes()

    # On Friday, Thursday's game has started (and could even be omitted because played=True).
    # Candidate Sunday game has updated probability and explanation.
    fri_candidates = _two_game_doc(
        generated="2099-11-27T22:00:00Z",
        thu_prob=0.99,  # would mutate if not frozen
        sun_prob=0.71,
        thu_market_prob=0.91,
        thu_lead="kf",
        sun_lead="kf",
    )
    # Test both when Thu is omitted (already marked played) and when passed fresh.
    frozen_from_sun_only = L.freeze_started_games(
        2026, 98, [fri_candidates["games"][1]], now=fri_now, root=tmp_path
    )
    assert len(frozen_from_sun_only) == 2
    assert L.canonical_game_json(frozen_from_sun_only[0]) == L.canonical_game_json(
        tue_doc["games"][0]
    )

    fri_doc = {
        **fri_candidates,
        "games": L.freeze_started_games(
            2026, 98, fri_candidates["games"], now=fri_now, root=tmp_path
        ),
    }
    p2 = L.write_snapshot(fri_doc, root=tmp_path, force=True, now=fri_now)
    assert p2 != p1
    assert p1.read_bytes() == tue_bytes

    written_fri = json.loads(p2.read_text())
    by_id = {g["game_id"]: g for g in written_fri["games"]}
    assert L.canonical_game_json(by_id["2026_98_AAA_BBB"]) == L.canonical_game_json(
        tue_doc["games"][0]
    )
    assert by_id["2026_98_AAA_BBB"]["market"] == tue_doc["games"][0]["market"]
    assert by_id["2026_98_AAA_BBB"]["explanation"] == tue_doc["games"][0]["explanation"]
    assert by_id["2026_98_CCC_DDD"]["headline"]["home_win_prob"] == 0.71
    assert by_id["2026_98_CCC_DDD"]["explanation"]["summary"]["lead_component"] == "kf"


def test_write_snapshot_rejects_mutated_started_game_fields(tmp_path: Path) -> None:
    tue_now = datetime(2099, 11, 24, 7, 0, tzinfo=UTC)
    fri_now = datetime(2099, 11, 27, 22, 0, tzinfo=UTC)
    tue_doc = _two_game_doc(generated="2099-11-24T07:00:00Z")
    L.write_snapshot(tue_doc, root=tmp_path, force=False, now=tue_now)

    # Red test 1: mutating started game's explanation fails even with force=True.
    bad_exp = _two_game_doc(generated="2099-11-27T22:00:00Z")
    bad_exp["games"][0] = json.loads(json.dumps(tue_doc["games"][0]))
    bad_exp["games"][0]["explanation"]["summary"]["lead_component"] = "kf"
    with pytest.raises(L.WeekLockedError, match="differs from its frozen canonical"):
        L.write_snapshot(bad_exp, root=tmp_path, force=True, now=fri_now)

    # Red test 2: mutating started game's market quote fails even with force=True.
    bad_mkt = _two_game_doc(generated="2099-11-27T22:00:00Z")
    bad_mkt["games"][0] = json.loads(json.dumps(tue_doc["games"][0]))
    bad_mkt["games"][0]["market"][0]["home_win_prob"] = 0.65
    with pytest.raises(L.WeekLockedError, match="differs from its frozen canonical"):
        L.write_snapshot(bad_mkt, root=tmp_path, force=True, now=fri_now)

    # Red test 3: dropping the started game fails even with force=True.
    dropped = _two_game_doc(generated="2099-11-27T22:00:00Z")
    dropped["games"] = [dropped["games"][1]]
    with pytest.raises(L.WeekLockedError, match="missing from the new snapshot"):
        L.write_snapshot(dropped, root=tmp_path, force=True, now=fri_now)

    # Red test 4: once ALL games have passed kickoff, writing fails even with freeze_started=True.
    mon_now = datetime(2099, 12, 1, 7, 0, tzinfo=UTC)
    with pytest.raises(L.WeekLockedError, match="all games have passed kickoff"):
        L.write_snapshot(tue_doc, root=tmp_path, force=True, now=mon_now, freeze_started=True)


def test_open_next_weeks_keeps_midweek_open_and_has_open_games(tmp_path: Path) -> None:
    import pandas as pd

    from ensemblitz.predict import has_open_games, open_next_weeks

    feats = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 12,
                "played": True,
                "kickoff_utc": pd.Timestamp("2026-11-26T01:00:00Z"),
            },
            {
                "season": 2026,
                "week": 12,
                "played": False,
                "kickoff_utc": pd.Timestamp("2026-11-29T18:00:00Z"),
            },
        ]
    )
    # Friday 22:00 UTC: Thursday started, Sunday still open -> week 12 stays open!
    fri = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)
    assert open_next_weeks(feats, 2026, n=1, now=fri, root=tmp_path) == [12]
    assert has_open_games(2026, now=fri, root=tmp_path, schedules=feats) is True

    # Monday 08:00 UTC: all games past kickoff -> no open weeks or open games.
    mon = datetime(2026, 11, 30, 8, 0, tzinfo=UTC)
    assert open_next_weeks(feats, 2026, n=1, now=mon, root=tmp_path) == []
    assert has_open_games(2026, now=mon, root=tmp_path, schedules=feats) is False


def test_run_predict_freezes_started_thursday_game_on_friday(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
    import pandas as pd

    from ensemblitz import predict as PR

    tue_now = datetime(2099, 11, 24, 7, 0, tzinfo=UTC)
    fri_now = datetime(2099, 11, 27, 22, 0, tzinfo=UTC)

    def _row(gid: str, home: str, away: str, kick: str, played: bool, prob: float) -> dict:
        return {
            "game_id": gid,
            "season": 2026,
            "week": 13,
            "home_team": home,
            "away_team": away,
            "kickoff_utc": pd.Timestamp(kick),
            "played": played,
            "market_prob": 0.55,
            "elo_prob": prob,
            "kf_prob": prob,
            "lgbm_prob": prob,
            "lgbm_mkt_prob": prob,
            "ens_prob": prob,
            "ens_margin": 3.0 if prob >= 0.5 else -3.0,
            "ens_total": 44.0,
            "nomkt_prob": prob,
            "nomkt_margin": 3.0 if prob >= 0.5 else -3.0,
            "nomkt_total": 44.0,
            "spread_line": 2.5,
            "total_line": 44.0,
            "home_moneyline": -130.0,
            "away_moneyline": 110.0,
            "h_qb_change": 0,
            "a_qb_change": 0,
            "h_rest": 7,
            "a_rest": 7,
            "dome": 0,
            "weather_known": 0,
            "temp": np.nan,
            "wind": np.nan,
            "h_out_lag": 0,
            "a_out_lag": 0,
        }

    stack = {
        "components": ["elo", "kf", "lgbm"],
        "prob_weights": [0.3, 0.3, 0.4],
        "bias": 0.0,
        "margin_weights": [0.3, 0.3, 0.4],
    }
    weights = {"with_market": stack, "no_market": stack}

    def _fake_sim(rows: pd.DataFrame, n_sims: int = 100) -> dict:
        n = len(rows)
        return {
            "n_sims": n_sims,
            "seed": 2026,
            "mo_p_home": rows["nomkt_prob"].to_numpy(),
            "mo_home_q10": np.full(n, 14.0),
            "mo_home_q90": np.full(n, 34.0),
            "mo_away_q10": np.full(n, 10.0),
            "mo_away_q90": np.full(n, 30.0),
            "mo_margin_q10": np.full(n, -6.0),
            "mo_margin_q90": np.full(n, 14.0),
            "mo_total_q10": np.full(n, 34.0),
            "mo_total_q90": np.full(n, 54.0),
            "mo_like_home": np.full(n, 24, dtype=int),
            "mo_like_away": np.full(n, 20, dtype=int),
            "mo_like_prob": np.full(n, 0.02),
        }

    state = {"mode": "tue"}

    def _fake_build(_season: int) -> pd.DataFrame:
        if state["mode"] == "tue":
            return pd.DataFrame(
                [
                    _row("2026_13_AAA_BBB", "BBB", "AAA", "2099-11-27T01:15:00Z", False, 0.62),
                    _row("2026_13_CCC_DDD", "DDD", "CCC", "2099-11-29T18:00:00Z", False, 0.54),
                ]
            )
        # On Friday, Thursday's game is already played=True and Sunday shifted to 0.71.
        return pd.DataFrame(
            [
                _row("2026_13_AAA_BBB", "BBB", "AAA", "2099-11-27T01:15:00Z", True, 0.99),
                _row("2026_13_CCC_DDD", "DDD", "CCC", "2099-11-29T18:00:00Z", False, 0.71),
            ]
        )

    def _fake_predict(frame: pd.DataFrame, season: int, weeks: list[int]) -> pd.DataFrame:
        out = frame[
            (frame["season"] == season) & frame["week"].isin(weeks) & ~frame["played"]
        ].copy()
        out.attrs["ensemble_weights"] = weights
        out.attrs["no_market_stack"] = None
        out.attrs["lgbm_contrib"] = None
        return out

    monkeypatch.setattr(PR, "build_frame", _fake_build)
    monkeypatch.setattr(PR, "predict_frame", _fake_predict)
    monkeypatch.setattr(PR, "simulate_rows", _fake_sim)
    monkeypatch.setattr(PR, "_absences", lambda _rows: {})
    monkeypatch.setattr(PR, "_odds_quotes", lambda: {})
    monkeypatch.setattr(
        K,
        "provenance",
        lambda _root=None, production=False: {"git_sha": "0" * 40, "reproducible": False},
    )
    monkeypatch.setattr(K, "data_cutoff_utc", lambda root=None, now=None: "2099-11-24T00:00:00Z")
    monkeypatch.setattr(
        K, "data_snapshot", lambda root=None: {"data/raw/schedules.parquet": "a" * 64}
    )

    # Tuesday run writes both games
    p_tue = PR.run_predict(2026, use_news=False, force=False, root=tmp_path, now=tue_now)
    assert len(p_tue) == 1
    tue_doc = json.loads(p_tue[0].read_text())

    # Friday run re-predicts only unplayed Sunday game and freezes Thursday's exact canonical record
    state["mode"] = "fri"
    p_fri = PR.run_predict(2026, use_news=False, force=True, root=tmp_path, now=fri_now)
    assert len(p_fri) == 1
    assert p_fri[0] != p_tue[0]
    fri_doc = json.loads(p_fri[0].read_text())
    assert K.validate_week(fri_doc) == []

    tue_by_id = {g["game_id"]: g for g in tue_doc["games"]}
    fri_by_id = {g["game_id"]: g for g in fri_doc["games"]}
    assert L.canonical_game_json(fri_by_id["2026_13_AAA_BBB"]) == L.canonical_game_json(
        tue_by_id["2026_13_AAA_BBB"]
    )
    assert fri_by_id["2026_13_CCC_DDD"]["headline"]["home_win_prob"] == 0.71
