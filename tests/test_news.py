import json

import numpy as np
import pandas as pd

from ensemblitz import news as N
from ensemblitz import players as PL
from ensemblitz.sim import likely_score, simulate_games

VALUES = pd.DataFrame(
    [
        ("aidan hutchinson|EDGE", "Aidan Hutchinson", "DET", "EDGE", 16, 0, 0.86, 2.0, "x"),
        ("jessie bates|S", "Jessie Bates III", "ATL", "S", 17, 0, 0.98, 1.0, "x"),
        ("some qb|QB", "Some QB", "DET", "QB", 16, 0.99, 0, 5.0, "x"),
        ("josh allen|QB", "Josh Allen", "BUF", "QB", 16, 0.99, 0, 6.0, "x"),
        ("josh allen|EDGE", "Josh Allen", "JAX", "EDGE", 16, 0, 0.8, 1.5, "x"),
    ],
    columns=["key", "name", "team", "group", "games", "avg_off", "avg_def", "value_pts", "method"],
)
NOW = "2026-11-17T20:00:00Z"


def _item(
    player="Aidan Hutchinson",
    team="DET",
    position="DE",
    status="out",
    posted="2026-11-17T18:00:00Z",
    **kw,
):
    return {
        "team": team,
        "player": player,
        "position": position,
        "status": status,
        "posted_at": posted,
        "starter": True,
        **kw,
    }


def test_norm_and_lookup_disambiguate_same_name():
    assert PL.norm_name("Jessie Bates III") == "jessie bates"
    assert PL.lookup(VALUES, "jessie bates", "FS")["value_pts"] == 1.0
    assert PL.lookup(VALUES, "Josh Allen", "QB")["value_pts"] == 6.0
    assert PL.lookup(VALUES, "Josh Allen", "DE")["value_pts"] == 1.5
    assert PL.lookup(VALUES, "Nobody Known", "WR") is None


def test_out_lowers_prob_and_status_weights():
    out = N.adjust_game(0.60, 3.0, "DET", "GB", [_item()], VALUES, NOW)
    dbt = N.adjust_game(0.60, 3.0, "DET", "GB", [_item(status="doubtful")], VALUES, NOW)
    qst = N.adjust_game(0.60, 3.0, "DET", "GB", [_item(status="questionable")], VALUES, NOW)
    assert out["applied"] and out["prob_home_after"] < 0.60 and out["margin_after"] == 1.0
    assert abs(dbt["home_points_lost"] - 1.5) < 1e-9 and abs(qst["home_points_lost"] - 0.5) < 1e-9
    away = N.adjust_game(0.60, 3.0, "GB", "DET", [_item()], VALUES, NOW)
    assert away["prob_home_after"] > 0.60  # the visitor losing a player helps the home side


def test_freshness_unknown_player_and_ignored_items():
    old = N.adjust_game(0.6, 3.0, "DET", "GB", [_item(posted="2026-11-10T00:00:00Z")], VALUES, NOW)
    assert abs(old["home_points_lost"] - 0.5) < 1e-9  # 2.0 * 0.25
    fut = N.adjust_game(0.6, 3.0, "DET", "GB", [_item(posted="2026-11-18T00:00:00Z")], VALUES, NOW)
    assert not fut["applied"]
    bench = N.adjust_game(0.6, 3.0, "DET", "GB", [{**_item(), "starter": False}], VALUES, NOW)
    ret = N.adjust_game(0.6, 3.0, "DET", "GB", [_item(status="returning")], VALUES, NOW)
    assert not bench["applied"] and not ret["applied"]
    unk = N.adjust_game(0.6, 3.0, "DET", "GB", [_item("Rookie X", position="WR")], VALUES, NOW)
    assert unk["applied"] and "prior" in unk["items"][0]["source"]


def test_team_cap_and_load_news(tmp_path):
    many = [_item("Some QB", position="QB"), _item(), _item("Josh Allen", position="DE")]
    a = N.adjust_game(0.6, 3.0, "DET", "GB", many, VALUES, NOW)
    assert a["home_points_lost"] <= N.TEAM_CAP
    p = tmp_path / "week11.json"
    p.write_text(json.dumps([{"team": "det", "player": "A", "status": "OUT"}, {"team": "x"}]))
    items = N.load_news(p)
    assert len(items) == 1 and items[0]["team"] == "DET" and items[0]["status"] == "out"
    assert N.load_news(tmp_path / "missing.json") == []


def test_likely_score_agrees_with_pick_and_margin():
    eh, ea = np.array([28.0, 20.0, 17.0]), np.array([16.0, 21.0, 27.0])
    h, a = simulate_games(eh, ea, n_sims=8000, seed=5)
    margin = eh - ea
    r = likely_score(h, a, margin > 0, margin)
    for i in range(3):
        d = r["like_home"][i] - r["like_away"][i]
        assert (d > 0) == (margin[i] > 0) and abs(d - margin[i]) <= 3.5 + 1e-9
        assert ((h[i] == r["like_home"][i]) & (a[i] == r["like_away"][i])).any()
        assert 0 < r["like_prob"][i] < 0.1



def test_apply_news_changes_ensemble_but_not_model_only_headline(monkeypatch):
    from ensemblitz import predict

    rows = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 11,
                "home_team": "DET",
                "away_team": "GB",
                "ens_prob": 0.64,
                "ens_margin": 3.0,
                "nomkt_prob": 0.58,
                "nomkt_margin": 1.5,
            }
        ]
    )
    monkeypatch.setattr(N, "load_news", lambda *args, **kwargs: [_item()])
    monkeypatch.setattr(PL, "load_raw", lambda season: (None, None))
    monkeypatch.setattr(PL, "build_values", lambda *args: VALUES)
    monkeypatch.setattr(
        N,
        "adjust_game",
        lambda prob, margin, *args, **kwargs: {
            "applied": True,
            "prob_home_before": prob,
            "margin_before": margin,
            "prob_home_after": 0.70,
            "margin_after": 4.0,
        },
    )

    audits = predict.apply_news(rows, NOW)
    assert audits[0]["applied"]
    assert rows.loc[0, "ens_prob"] == 0.70
    assert rows.loc[0, "ens_margin"] == 4.0
    assert rows.loc[0, "nomkt_prob"] == 0.58
    assert rows.loc[0, "nomkt_margin"] == 1.5
