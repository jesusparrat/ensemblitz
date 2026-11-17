import json
from pathlib import Path

from ensemblitz.site.build import build_site, fnum, fpct, fsigned


def _game(gid: str, home: str, away: str, kick: str) -> dict:
    return {
        "game_id": gid,
        "season": 2026,
        "week": 11,
        "home_team": home,
        "away_team": away,
        "kickoff_utc": kick,
        "generated_at": "2026-11-17T20:00:00Z",
        "model_version": "0.1.0",
        "home_win_prob": {
            "market": 0.7,
            "elo": 0.65,
            "kf": 0.66,
            "lgbm": 0.68,
            "lgbm_mkt": 0.7,
            "ensemble": 0.7,
            "ensemble_model_only": 0.67,
        },
        "pick": home,
        "predicted_margin": 5.5,
        "predicted_total": 45.0,
        "model_only_margin": 4.0,
        "most_likely_score": {"home": 24, "away": 17, "prob": 0.01},
        "sim": {
            "p_home": 0.69,
            "margin_q10": -8,
            "margin_q90": 19,
            "total_q10": 30,
            "total_q90": 60,
        },
        "market": {
            "spread_line": 5.5,
            "total_line": 44.5,
            "home_moneyline": -230,
            "away_moneyline": 190,
        },
        "context": {
            "home_qb_change": 0,
            "away_qb_change": 1,
            "home_rest": 7,
            "away_rest": 7,
            "dome": 0,
            "temp": 50,
            "wind": 6,
            "weather_known": 1,
            "home_out_lag": 2,
            "away_out_lag": 3,
        },
    }


def _repo(tmp: Path, with_odds: bool, with_backtest: bool) -> Path:
    (tmp / "predictions" / "2026").mkdir(parents=True)
    games = [
        _game("2026_11_IND_HOU", "HOU", "IND", "2099-11-20T01:15:00Z"),
        _game("2026_11_ARI_KC", "KC", "ARI", "2099-11-22T18:00:00Z"),
    ]
    (tmp / "predictions/2026/week11.json").write_text(
        json.dumps(
            {"season": 2026, "week": 11, "generated_at": "2026-11-17T20:00:00Z", "games": games}
        )
    )
    if with_odds:
        (tmp / "reports/odds").mkdir(parents=True)
        og = {
            "game_id": "2026_11_IND_HOU",
            "home": "HOU",
            "away": "IND",
            "our_home_prob": 0.7,
            "consensus_home_prob_shin": 0.62,
            "edge": 0.08,
            "n_books": 1,
            "best_home_price": {"book": "bk", "price": 1.6},
            "best_away_price": {"book": "bk", "price": 2.5},
            "ev_per_unit_best": {"home": 0.12, "away": -0.2},
            "best_side": "home",
            "flag_large_disagreement": True,
            "likely_reasons": ["cambio de QB"],
            "books": {
                "bk": {
                    "p_home_shin": 0.62,
                    "p_home_mult": 0.61,
                    "home_price": 1.6,
                    "away_price": 2.5,
                    "edge_vs_ours": 0.08,
                }
            },
            "book_spread_home": -5.5,
            "book_total": 44.5,
        }
        (tmp / "reports/odds/2026_week11.json").write_text(
            json.dumps(
                {
                    "season": 2026,
                    "week": 11,
                    "odds_fetched_at": "2026-11-17T21:00:00Z",
                    "predictions_generated_at": "x",
                    "games": [og],
                }
            )
        )
    if with_backtest:
        (tmp / "reports").mkdir(exist_ok=True)
        src = Path(__file__).resolve().parents[1] / "reports" / "backtest.json"
        (tmp / "reports/backtest.json").write_text(src.read_text())
    return tmp


def test_formatters():
    assert fnum(-12.5) == "−12,5" and fsigned(3.0) == "+3,0" and fpct(0.853) == "85\u202f%"


def test_site_builds_with_odds_and_backtest(tmp_path):
    root = _repo(tmp_path, True, True)
    out = build_site(root=root, out=root / "site" / "_build")
    for page in (
        "index.html",
        "historial.html",
        "metodo.html",
        "jornada/11.html",
        "partido/2026_11_IND_HOU.html",
        "assets/style.css",
    ):
        assert (out / page).exists(), page
    game = (out / "partido/2026_11_IND_HOU.html").read_text()
    assert "<svg" in game and "Bk" in game and "cambio de QB" in game
    home = (out / "index.html").read_text()
    assert "Jornada 11" in home and "IND" in home and "Bandera" in home
    assert "Calibración" in (out / "metodo.html").read_text()


def test_site_builds_with_nothing(tmp_path):
    out = build_site(root=tmp_path, out=tmp_path / "site" / "_build")
    assert "Sin jornada" in (out / "index.html").read_text()
    assert "Todavía no hay picks" in (out / "historial.html").read_text()


def test_history_page_with_graded_picks(tmp_path):
    root = _repo(tmp_path, False, False)
    (root / "results/2026").mkdir(parents=True)
    rows = [
        {
            "game_id": "2026_11_IND_HOU",
            "season": 2026,
            "week": 11,
            "home_team": "HOU",
            "away_team": "IND",
            "result": 7.0,
            "total": 41.0,
            "pick": "HOU",
            "ensemble_correct": 1,
        },
        {
            "game_id": "2026_11_ARI_KC",
            "season": 2026,
            "week": 11,
            "home_team": "KC",
            "away_team": "ARI",
            "result": -3.0,
            "total": 40.0,
            "pick": "KC",
            "ensemble_correct": 0,
        },
    ]
    (root / "results/2026/week11.json").write_text(json.dumps(rows))
    out = build_site(root=root, out=root / "site" / "_build")
    hist = (out / "historial.html").read_text()
    assert "partidos calificados" in hist and "50,0" in hist and "<svg" in hist
    assert "Final: IND 17, HOU 24" in (out / "index.html").read_text()


def test_build_output_has_no_em_dash(tmp_path):
    root = _repo(tmp_path, True, True)
    out = build_site(root=root, out=root / "site" / "_build")
    for page in out.rglob("*.html"):
        html = page.read_text()
        assert "\u2014" not in html, page.name
        assert "Con honestidad" not in html, page.name


def test_weather_hidden_when_not_known(tmp_path):
    root = _repo(tmp_path, False, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    for g in d["games"]:
        g["context"].update({"weather_known": 0, "temp": None, "wind": None})
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    game = (out / "partido/2026_11_IND_HOU.html").read_text()
    assert "°C" not in game and "km/h" not in game


def test_weather_shown_in_metric_units(tmp_path):
    root = _repo(tmp_path, False, False)
    out = build_site(root=root, out=root / "site" / "_build")
    game = (out / "partido/2026_11_IND_HOU.html").read_text()
    assert "10 °C" in game or "10\u202f°C" in game
    assert "km/h" in game and "°F" not in game and "mph" not in game


def test_week_without_odds_or_news_shows_no_repo_paths(tmp_path):
    root = _repo(tmp_path, False, False)
    out = build_site(root=root, out=root / "site" / "_build")
    for page in ("index.html", "jornada/11.html", "partido/2026_11_IND_HOU.html"):
        html = (out / page).read_text()
        assert "reports/odds" not in html and "predictions/" not in html, page
