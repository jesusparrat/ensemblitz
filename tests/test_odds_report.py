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
        "home_win_prob": {"ensemble": 0.70, "ensemble_model_only": 0.70},
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
    assert 0.55 < g["consensus_home_prob_shin"] < 0.70
    assert g["model_only_home_prob"] == 0.70
    assert g["gap_model_only"] > 0.05 and g["n_books"] == 2
    assert any("QB" in r for r in g["likely_reasons"])
    forbidden = {
        "our_home_prob",
        "edge",
        "best_home_price",
        "best_away_price",
        "ev_per_unit_best",
        "best_side",
        "books",
        "book_spread_home",
        "book_total",
        "consensus_home_prob_mult",
        "our_margin_minus_book",
        "our_cover_prob_home",
    }
    assert forbidden.isdisjoint(g)
    encoded = json.dumps(rep)
    assert all(x not in encoded for x in ("bookmaker", "best_home_price", "ev_per_unit_best"))
    md = to_markdown(rep)
    assert "HOU" in md and "Modelo propio" in md
    assert "EV" not in md and "Mejor precio" not in md


def test_missing_key_skips_politely(monkeypatch, tmp_path):
    from ensemblitz.odds import client

    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    monkeypatch.setattr(client, "ODDS_DIR", Path(tmp_path))
    df, msg = client.fetch_odds()
    assert df is None and "skipped" in msg


def test_consensus_quote_exposes_only_aggregate_probability_and_count():
    from ensemblitz.odds.report import consensus_for_teams

    quote = consensus_for_teams(_odds(), "HOU", "IND")
    assert quote is not None
    assert set(quote) == {"consensus_home_prob_shin", "n_books", "fetched_at"}
    assert quote["n_books"] == 2


def test_prediction_market_quote_publishes_only_aggregate_h2h_fields():
    from ensemblitz import predict

    row = pd.Series(
        {
            "home_team": "HOU",
            "away_team": "IND",
            "market_prob": 0.84,
            "spread_line": 12.5,
            "total_line": 44.5,
            "home_moneyline": -700,
            "away_moneyline": 500,
        }
    )
    quote = {
        "consensus_home_prob_shin": 0.8577,
        "n_books": 42,
        "fetched_at": "2026-11-17T20:54:38Z",
    }
    market = predict._market_block(row, "2026-11-17T22:07:57Z", {("HOU", "IND"): quote})
    api_quote = next(x for x in market if x["source"] == "odds_api_consensus")
    assert api_quote["home_win_prob"] == 0.8577
    assert api_quote["n_books"] == 42
    assert api_quote["margin_home"] is None
    assert api_quote["total_line"] is None
    assert set(api_quote) == {
        "source",
        "captured_at_utc",
        "is_closing",
        "home_win_prob",
        "margin_home",
        "total_line",
        "n_books",
    }
