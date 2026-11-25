"""Contract v1: schema, required fields, conventions, provenance and v0 detection."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

from ensemblitz import contract as K

ROOT = Path(__file__).resolve().parents[1]
WEEK11 = ROOT / "predictions" / "2026" / "week11.json"
WEEK12 = ROOT / "predictions" / "2026" / "week12.json"
ODDS12 = ROOT / "reports" / "odds" / "2026_week12.json"
FAKE_SHA = "0" * 40


def _v1_game(g: dict, odds: dict | None) -> dict:
    """Map one real v0 game record to v1 (test-only preview of the PR 1b reader)."""
    mo, hwp, c = g["model_only"], g["home_win_prob"], g["context"]
    s = mo["sim"]
    market = [
        {
            "source": "nflverse_line",
            "captured_at_utc": g["generated_at"],
            "is_closing": False,
            "home_win_prob": hwp["market"],
            "margin_home": g["market"]["spread_line"],
            "total_line": g["market"]["total_line"],
            "home_moneyline": g["market"]["home_moneyline"],
            "away_moneyline": g["market"]["away_moneyline"],
        }
    ]
    if odds:
        market.append(
            {
                "source": "odds_api_consensus",
                "captured_at_utc": odds["fetched"],
                "is_closing": False,
                "home_win_prob": odds["consensus_home_prob_shin"],
                "margin_home": K.odds_api_margin_home(odds.get("book_spread_home")),
                "total_line": odds.get("book_total"),
                "n_books": odds["n_books"],
            }
        )
    na = g["news_adjustment"]
    return {
        "game_id": g["game_id"],
        "home_team": g["home_team"],
        "away_team": g["away_team"],
        "kickoff_utc": g["kickoff_utc"],
        "generated_at_utc": g["generated_at"],
        "headline": {
            "home_win_prob": mo["home_win_prob"],
            "home_points": mo["home_points"],
            "away_points": mo["away_points"],
            "distribution": {
                "n_sims": 20000,
                "seed": 2026,
                "p_home": s["p_home"],
                "home_points": [s["home_q10"], s["home_q90"]],
                "away_points": [s["away_q10"], s["away_q90"]],
                "margin_home": [s["margin_q10"], s["margin_q90"]],
                "total": [s["total_q10"], s["total_q90"]],
            },
            "example_score": mo["example_score"],
        },
        "ensemble": {
            "home_win_prob": hwp["ensemble"],
            "margin_home": g["predicted_margin"],
            "total": g["predicted_total"],
        },
        "components": {k: hwp[k] for k in ("elo", "kf", "lgbm", "lgbm_mkt")},
        "market": market,
        "context": {
            "home_qb_change": bool(c["home_qb_change"]),
            "away_qb_change": bool(c["away_qb_change"]),
            "home_rest_days": c["home_rest"],
            "away_rest_days": c["away_rest"],
            "dome": bool(c["dome"]),
            "weather_known": bool(c["weather_known"]),
            "temp_f": c["temp"],
            "wind_mph": c["wind"],
            "home_out_lag": c["home_out_lag"],
            "away_out_lag": c["away_out_lag"],
        },
        "absences": g["absences"],
        "news_adjustment": {
            "applied": na["applied"],
            "applies_to": "ensemble",
            "margin_points": na["margin_points"],
            "home_points_lost": na["home_points_lost"],
            "away_points_lost": na["away_points_lost"],
            "home_win_prob_before": na["prob_home_before"],
            "margin_home_before": na["margin_before"],
            "items": na["items"],
        },
    }


@pytest.fixture(scope="module")
def v0() -> dict:
    return json.loads(WEEK12.read_text())


@pytest.fixture()
def doc(v0: dict) -> dict:
    """The real 2026 week 12 output expressed in contract v1."""
    odds = json.loads(ODDS12.read_text())
    by_id = {o["game_id"]: {**o, "fetched": odds["odds_fetched_at"]} for o in odds["games"]}
    return {
        "schema_version": "1",
        "model_version": v0["model_version"],
        "git_sha": FAKE_SHA,
        "reproducible": False,
        "generated_at_utc": v0["generated_at"],
        "data_cutoff_utc": v0["generated_at"],
        "data_snapshot": {"data/raw/schedules.parquet": "a" * 64},
        "season": v0["season"],
        "week": v0["week"],
        "ensemble_weights": v0["ensemble_weights"],
        "games": [_v1_game(g, by_id.get(g["game_id"])) for g in v0["games"]],
    }


# ---------------------------------------------------------------- schema
def test_schema_refs_resolve() -> None:
    schema = K.load_schema()
    refs: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                refs.append(node["$ref"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    assert refs
    for r in refs:
        assert isinstance(K._resolve(r, schema), dict), r


def test_real_week12_output_fits_v1(doc: dict) -> None:
    assert K.validate_week(doc) == []
    assert len(doc["games"]) == 16


def test_exact_provenance_field_names() -> None:
    required = set(K.load_schema()["required"])
    assert {
        "schema_version",
        "model_version",
        "git_sha",
        "generated_at_utc",
        "data_cutoff_utc",
        "data_snapshot",
    } <= required


@pytest.mark.parametrize("field", K.load_schema()["required"])
def test_each_required_top_level_field(doc: dict, field: str) -> None:
    del doc[field]
    assert any(f"missing required field {field!r}" in e for e in K.validate_week(doc))


@pytest.mark.parametrize("field", K.load_schema()["$defs"]["game"]["required"])
def test_each_required_game_field(doc: dict, field: str) -> None:
    del doc["games"][0][field]
    assert any(field in e for e in K.validate_week(doc))


def test_no_redundant_or_unknown_fields(doc: dict) -> None:
    doc["games"][0]["pick"] = "LA"  # derived from the headline probability: not stored
    doc["games"][0]["headline"]["margin"] = 5.93  # derived from the two expected points
    errs = K.validate_week(doc)
    assert any("unexpected field 'pick'" in e for e in errs)
    assert any("unexpected field 'margin'" in e for e in errs)


def test_bad_values_rejected(doc: dict) -> None:
    bad = copy.deepcopy(doc)
    bad["schema_version"] = "2"
    bad["git_sha"] = "abc"
    bad["generated_at_utc"] = "2026-11-24T18:26:45+00:00"
    bad["data_snapshot"] = {"data/raw/x.csv": "a" * 64}
    bad["games"][0]["headline"]["home_win_prob"] = math.nan
    bad["games"][0]["market"][0]["source"] = "draftkings"
    errs = K.validate_week(bad)
    for needle in (
        "schema_version",
        "git_sha",
        "generated_at_utc",
        "x.csv",
        "NaN",
        "draftkings",
    ):
        assert any(needle in e for e in errs), needle


def test_semantic_rules(doc: dict) -> None:
    doc["games"][1]["game_id"] = doc["games"][0]["game_id"]
    doc["data_cutoff_utc"] = "2030-01-01T00:00:00Z"
    doc["games"][2]["headline"]["distribution"]["total"] = [60.0, 30.0]
    errs = K.validate_week(doc)
    assert any("duplicated game_id" in e for e in errs)
    assert any("does not match season/week/away/home" in e for e in errs)
    assert any("data_cutoff_utc" in e for e in errs)
    assert any("q10 above q90" in e for e in errs)


# ---------------------------------------------------------------- conventions
def test_margin_sign_is_home_minus_away(doc: dict, v0: dict) -> None:
    for g, old in zip(doc["games"], v0["games"], strict=True):
        h = g["headline"]
        # derived margin equals the v0 stored one (rounding of the stored points only)
        assert K.margin_home(h) == pytest.approx(old["model_only"]["margin"], abs=0.011)
        assert K.total(h) == pytest.approx(old["model_only"]["total"], abs=0.011)
        # positive margin <=> home favoured, for the model and for every market quote
        assert (K.margin_home(h) > 0) == (h["home_win_prob"] > 0.5)
        for q in g["market"]:
            if q["margin_home"] not in (None, 0) and q["home_win_prob"] is not None:
                assert (q["margin_home"] > 0) == (q["home_win_prob"] > 0.5), (g["game_id"], q)
        assert K.pick(g) == old["pick"]


def test_odds_api_sign_is_flipped() -> None:
    assert K.odds_api_margin_home(-12.5) == 12.5
    assert K.odds_api_margin_home(3.0) == -3.0
    assert K.odds_api_margin_home(None) is None


def test_display_time_zones() -> None:
    assert K.DISPLAY_TZ == {"es": "Europe/Madrid", "en": "America/New_York"}
    assert K.MARGIN_CONVENTION == "home_minus_away"


# ---------------------------------------------------------------- versions
def test_v0_files_detected() -> None:
    for p in (WEEK11, WEEK12):
        assert K.detect_version(json.loads(p.read_text())) == "0"


def test_v1_and_garbage(doc: dict) -> None:
    assert K.detect_version(doc) == "1"
    with pytest.raises(K.ContractError):
        K.detect_version({**doc, "schema_version": "2"})
    with pytest.raises(K.ContractError):
        K.detect_version({"games": []})
    with pytest.raises(K.ContractError):
        K.detect_version([])


# ---------------------------------------------------------------- data snapshot
def test_data_snapshot_hashes(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "b.parquet").write_bytes(b"second")
    (raw / "a.parquet").write_bytes(b"first")
    snap = K.data_snapshot(root=tmp_path)
    assert list(snap) == ["data/raw/a.parquet", "data/raw/b.parquet"]
    assert snap["data/raw/a.parquet"] == hashlib.sha256(b"first").hexdigest()
    (raw / "a.parquet").write_bytes(b"changed")
    assert K.data_snapshot(root=tmp_path)["data/raw/a.parquet"] != snap["data/raw/a.parquet"]


def test_data_snapshot_rejects_bad_inputs(tmp_path: Path) -> None:
    with pytest.raises(K.ContractError):
        K.data_snapshot(root=tmp_path)  # nothing to hash
    (tmp_path / "x.csv").write_text("a")
    with pytest.raises(K.ContractError):
        K.data_snapshot([tmp_path / "x.csv"], root=tmp_path)


# ---------------------------------------------------------------- clean tree rule
def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("data/\n")
    (tmp_path / "a.txt").write_text("a")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_tree_production(repo: Path) -> None:
    (repo / "data").mkdir()
    (repo / "data" / "ignored.parquet").write_bytes(b"x")  # ignored files do not count
    p = K.provenance(repo, production=True)
    assert p["reproducible"] is True
    assert len(p["git_sha"]) == 40


@pytest.mark.parametrize("change", ["modified", "untracked"])
def test_dirty_tree_blocks_production(repo: Path, change: str) -> None:
    if change == "modified":
        (repo / "a.txt").write_text("b")
    else:
        (repo / "new.txt").write_text("n")
    with pytest.raises(K.DirtyTreeError):
        K.provenance(repo, production=True)
    assert K.provenance(repo)["reproducible"] is False


def test_dev_artifact_never_reproducible(repo: Path) -> None:
    assert K.provenance(repo, production=False)["reproducible"] is False
