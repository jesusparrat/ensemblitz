"""Margin bands from the headline simulation, and grading of which rank happened."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from ensemblitz import contract as K
from ensemblitz.grade import grade_games, summarize, summary_md
from ensemblitz.outcome_bands import BAND_IDS, band_for_margin, from_margins
from ensemblitz.sim.drive import simulate_games
from ensemblitz.site.build import _bands_view
from ensemblitz.site.i18n import Lang

ROOT = Path(__file__).resolve().parents[1]


def test_band_edges():
    assert band_for_margin(-15) == "away_15"
    assert band_for_margin(-40) == "away_15"
    assert band_for_margin(-14) == "away_8_14"
    assert band_for_margin(-8) == "away_8_14"
    assert band_for_margin(-7) == "away_1_7"
    assert band_for_margin(-1) == "away_1_7"
    assert band_for_margin(0) == "tie"
    assert band_for_margin(1) == "home_1_7"
    assert band_for_margin(7) == "home_1_7"
    assert band_for_margin(8) == "home_8_14"
    assert band_for_margin(14) == "home_8_14"
    assert band_for_margin(15) == "home_15"
    assert band_for_margin(30) == "home_15"


def test_probabilities_and_top3_order():
    margins = np.array([3] * 50 + [10] * 30 + [-2] * 15 + [0] * 5)
    got = from_margins(margins, 100, 2026)
    assert [b["id"] for b in got["bands"]] == list(BAND_IDS)
    by_id = {b["id"]: b["prob"] for b in got["bands"]}
    assert by_id["home_1_7"] == 0.5
    assert by_id["home_8_14"] == 0.3
    assert by_id["away_1_7"] == 0.15
    assert by_id["tie"] == 0.05
    assert by_id["away_15"] == 0.0
    assert abs(sum(by_id.values()) - 1) < 1e-9
    assert got["top3"] == ["home_1_7", "home_8_14", "away_1_7"]
    assert got["n_sims"] == 100
    assert got["seed"] == 2026


def test_equal_rounded_probs_break_ties_by_canonical_order():
    # 10 and 10 of two bands: same probability, earlier band id ranks first.
    margins = np.array([3] * 10 + [20] * 10)
    got = from_margins(margins, 20, 1)
    assert got["top3"][0] == "home_1_7"
    assert got["top3"][1] == "home_15"


def test_headline_simulation_is_deterministic():
    home_exp = np.array([24.5])
    away_exp = np.array([20.0])
    h1, a1 = simulate_games(home_exp, away_exp, n_sims=20000, seed=2026)
    h2, a2 = simulate_games(home_exp, away_exp, n_sims=20000, seed=2026)
    assert np.array_equal(h1, h2)
    assert np.array_equal(a1, a2)
    b1 = from_margins(h1[0] - a1[0], 20000, 2026)
    b2 = from_margins(h2[0] - a2[0], 20000, 2026)
    assert b1 == b2
    assert len(b1["top3"]) == 3
    assert abs(sum(x["prob"] for x in b1["bands"]) - 1) <= 0.01


def _flat(**kw):
    g = {
        "game_id": "2026_01_AAA_BBB",
        "season": 2026,
        "week": 1,
        "home_team": "BBB",
        "away_team": "AAA",
        "kickoff_utc": "2026-09-10T00:00:00Z",
        "generated_at": "2026-09-08T10:00:00Z",
        "pick": "BBB",
        "predicted_margin": 3.0,
        "predicted_total": 44.0,
        "market": {"spread_line": 3.0},
        "home_win_prob": {"ensemble": 0.6, "market": 0.55},
    }
    g.update(kw)
    return g


def _sched(result):
    return pd.DataFrame([{"game_id": "2026_01_AAA_BBB", "result": result, "total": 40.0}])


def test_grading_records_rank_or_outside():
    bands = from_margins(np.array([3] * 70 + [10] * 20 + [-4] * 10), 100, 2026)
    g = _flat(outcome_bands=bands)
    top = grade_games([g], _sched(4.0))[0]
    assert top["outcome_band"] == "home_1_7"
    assert top["outcome_band_rank"] == 1
    second = grade_games([g], _sched(12.0))[0]
    assert second["outcome_band_rank"] == 2
    outside = grade_games([g], _sched(-20.0))[0]
    assert outside["outcome_band"] == "away_15"
    assert outside["outcome_band_rank"] == "outside top 3"
    tie = grade_games([g], _sched(0.0))[0]
    assert tie["outcome_band"] == "tie"
    assert tie["outcome_band_rank"] == "outside top 3"
    plain = grade_games([_flat()], _sched(4.0))[0]
    assert "outcome_band_rank" not in plain


def test_summary_counts_top3():
    rows = [
        {"season": 2026, "week": 1, "outcome_band_rank": 1},
        {"season": 2026, "week": 1, "outcome_band_rank": 2},
        {"season": 2026, "week": 1, "outcome_band_rank": "outside top 3"},
        {"season": 2026, "week": 1, "outcome_band_rank": 1},
    ]
    s = summarize(rows)
    assert s["outcome_bands"]["n"] == 4
    assert s["outcome_bands"]["rank_1"] == 2
    assert s["outcome_bands"]["top1"] == 0.5
    assert s["outcome_bands"]["top2"] == 0.75
    assert s["outcome_bands"]["top3"] == 0.75
    assert s["outcome_bands"]["outside"] == 1
    text = summary_md(s)
    assert "Outside the top 3" in text
    assert "50.0%" in text


def test_card_marks_the_band_that_happened():
    bands = from_margins(np.array([3] * 70 + [10] * 20 + [-4] * 10), 100, 2026)
    view = _bands_view(bands, "HOU", "IND", {"margin": 4})
    assert view["rows"][0]["hit"] is True
    assert view["outside"] is False
    missed = _bands_view(bands, "HOU", "IND", {"margin": -20})
    assert missed["outside"] is True
    assert all(not row["hit"] for row in missed["rows"])
    env = Environment(loader=FileSystemLoader(ROOT / "src/ensemblitz/site/templates"))
    tmpl = env.from_string('{% from "_macros.html" import bands with context %}{{ bands(g) }}')
    es = Lang("es")
    html = tmpl.render(g={"bands": view}, t=es.t, pct=es.pct)
    assert "HOU por 1 a 7" in html
    assert "Esto pasó." in html
    outside_html = tmpl.render(g={"bands": missed}, t=es.t, pct=es.pct)
    assert "fuera de estos tres" in outside_html


def test_old_snapshots_without_the_field_stay_valid():
    seen = 0
    for path in sorted((ROOT / "predictions").rglob("*.json")):
        if path.name == "MANIFEST.json":
            continue
        doc = json.loads(path.read_text())
        try:
            version = K.detect_version(doc)
        except K.ContractError:
            continue
        if version != "1":
            continue
        assert K.validate_week(doc) == []
        assert all("outcome_bands" not in g for g in doc["games"])
        seen += 1
    assert seen >= 1
    v1 = None
    for path in (ROOT / "predictions").rglob("*.json"):
        if path.name == "MANIFEST.json":
            continue
        candidate = json.loads(path.read_text())
        try:
            if K.detect_version(candidate) == "1":
                v1 = candidate
                break
        except K.ContractError:
            continue
    assert v1 is not None
    margins = np.array([3] * 50 + [10] * 30 + [-2] * 20)
    v1["games"][0]["outcome_bands"] = from_margins(margins, 100, 2026)
    assert K.validate_week(v1) == []
    v1["games"][0]["outcome_bands"]["top3"] = ["tie", "tie", "tie"]
    assert any("top3" in e for e in K.validate_week(v1))
