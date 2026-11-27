"""v0 and v1 reader: published weeks 11 and 12 map to the same pick, probability and margin."""

from __future__ import annotations

import json
from pathlib import Path

from ensemblitz import contract as K
from ensemblitz import contract_io

ROOT = Path(__file__).resolve().parents[1]
WEEK11 = ROOT / "predictions" / "2026" / "week11.json"
WEEK12 = ROOT / "predictions" / "2026" / "week12.json"
ODDS12 = ROOT / "reports" / "odds" / "2026_week12.json"


def _v0(path: Path) -> dict:
    return json.loads(path.read_text())


def test_detects_v0_and_does_not_rewrite(tmp_path: Path) -> None:
    src = WEEK12.read_bytes()
    dest = tmp_path / "week12.json"
    dest.write_bytes(src)
    loaded = contract_io.load_week(dest)
    assert loaded.version == "0"
    assert dest.read_bytes() == src
    assert K.detect_version(json.loads(src)) == "0"


def test_week12_matches_published_pick_prob_margin() -> None:
    raw = _v0(WEEK12)
    odds = json.loads(ODDS12.read_text())
    loaded = contract_io.load_week(WEEK12, odds)
    assert loaded.headline_kind == "model_only"
    assert len(loaded.doc["games"]) == 16
    for old, new in zip(raw["games"], loaded.doc["games"], strict=True):
        mo = old["model_only"]
        assert new["game_id"] == old["game_id"]
        assert new["headline"]["home_win_prob"] == mo["home_win_prob"]
        assert abs(K.margin_home(new["headline"]) - mo["margin"]) <= 0.011
        assert abs(K.total(new["headline"]) - mo["total"]) <= 0.011
        assert K.pick(new) == old["pick"]
        assert new["headline"]["distribution"]["margin_home"] == [
            mo["sim"]["margin_q10"],
            mo["sim"]["margin_q90"],
        ]
        cons = contract_io.market_quote(new, "odds_api_consensus")
        if any(o["game_id"] == old["game_id"] for o in odds["games"]):
            assert cons is not None
            assert cons["n_books"]


def test_week11_matches_published_pick_prob_margin() -> None:
    raw = _v0(WEEK11)
    loaded = contract_io.load_week(WEEK11)
    assert loaded.headline_kind == "model_only"
    assert len(loaded.doc["games"]) == 13
    for old, new in zip(raw["games"], loaded.doc["games"], strict=True):
        mo = old["model_only"]
        assert new["headline"]["home_win_prob"] == mo["home_win_prob"]
        assert abs(K.margin_home(new["headline"]) - mo["margin"]) <= 0.011
        assert K.pick(new) == old["pick"]


def test_pre_v2_snapshot_is_read_as_ensemble_headline() -> None:
    from ensemblitz import ledger as L

    # First published week 12: no model_only block, the published number was the ensemble.
    path = ROOT / "predictions" / "2026" / "week12" / "20261117T204559Z.json"
    loaded = contract_io.load_week(path)
    assert loaded.version == "0"
    assert loaded.headline_kind == "ensemble"
    raw = json.loads(path.read_text())
    g0, n0 = loaded.doc["games"][0], raw["games"][0]
    assert n0.get("model_only") is None
    assert g0["headline"]["home_win_prob"] == n0["home_win_prob"]["ensemble"]
    assert g0["ensemble"]["margin_home"] == n0["predicted_margin"]
    assert all(k == "ensemble" for k in loaded.headline_kinds.values())
    assert L.WEEK12_HISTORY[0] == "22f65ff"


def test_latest_pick_before_kickoff_matches_graded_week11() -> None:
    results = json.loads((ROOT / "results" / "2026" / "week11.json").read_text())
    assert len(results) == 13
    for row in results:
        found = contract_io.latest_pick_before_kickoff(row["game_id"], ROOT)
        assert found is not None, row["game_id"]
        loaded, game, published = found
        assert published < game["kickoff_utc"]
        assert K.pick(game) == row["pick"]
        assert loaded.headline_kind == row["headline"]
