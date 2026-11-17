import json
from pathlib import Path

import pandas as pd

from ensemblitz.odds.report import build, to_markdown
from ensemblitz.odds.teams import NAME_TO_ABBR

ABBR_TO_NAME = {v: k for k, v in NAME_TO_ABBR.items()}


def _pred():
    ctx = {
        "home_qb_change": 1,
        "away_qb_change": 0,
        "home_rest": 7,
        "away_rest": 7,
        "dome": 0,
        "temp": 50,
        "wind": 5,
        "home_out_lag": 1,
        "away_out_lag": 1,
    }
    g = {
        "game_id": "g",
        "home_team": "HOU",
        "away_team": "IND",
        "kickoff_utc": "2026-11-20T01:15:00Z",
        "home_win_prob": {"ensemble": 0.70},
        "predicted_margin": 6.0,
        "context": ctx,
    }
    return {"season": 2026, "week": 11, "generated_at": "2026-11-17T20:00:00Z", "games": [g]}


def _odds():
    rows = []
    for bk, (ph, pa) in {"a": (1.50, 2.70), "b": (1.52, 2.60)}.items():
        for mk, outs in {
            "h2h": [("Houston Texans", ph, None), ("Indianapolis Colts", pa, None)],
            "spreads": [("Houston Texans", 1.91, -4.5), ("Indianapolis Colts", 1.91, 4.5)],
            "totals": [("Over", 1.91, 44.5), ("Under", 1.91, 44.5)],
        }.items():
            for name, price, pt in outs:
                rows.append(
                    {
                        "event_id": "e",
                        "commence_time": "x",
                        "home_name": "Houston Texans",
                        "away_name": "Indianapolis Colts",
                        "bookmaker": bk,
                        "market": mk,
                        "outcome": name,
                        "price": price,
                        "point": pt,
                        "last_update": "x",
                        "fetched_at": "2026-11-17T20:30:00Z",
                    }
                )
    return pd.DataFrame(rows)


def test_discrepancy_report_flags_and_explains():
    rep = build(_pred(), _odds(), "2026-11-17T20:30:00Z")
    g = rep["games"][0]
    assert g["n_books"] == 2 and g["flag_large_disagreement"]
    assert 0.55 < g["consensus_home_prob_shin"] < 0.70 and g["edge"] > 0.05
    assert g["best_home_price"]["price"] == 1.52 and g["book_spread_home"] == -4.5
    assert any("QB" in r for r in g["likely_reasons"])
    json.dumps(rep)
    assert "HOU" in to_markdown(rep)


def test_missing_key_skips_politely(monkeypatch, tmp_path):
    from ensemblitz.odds import client

    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    monkeypatch.setattr(client, "ODDS_DIR", Path(tmp_path))
    df, msg = client.fetch_odds()
    assert df is None and "skipped" in msg
