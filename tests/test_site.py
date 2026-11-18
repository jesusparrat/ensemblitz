import json
import re
from pathlib import Path

from ensemblitz.site.build import build_site
from ensemblitz.site.i18n import Lang
from ensemblitz.site.strings import STRINGS


def _model_only(home_prob: float = 0.64, margin: float = 6.0, total: float = 46.8) -> dict:
    hp, ap = (total + margin) / 2, (total - margin) / 2
    return {
        "home_win_prob": home_prob,
        "margin": margin,
        "total": total,
        "home_points": round(hp, 2),
        "away_points": round(ap, 2),
        "sim": {
            "p_home": home_prob,
            "home_q10": 17.0,
            "home_q90": 33.0,
            "away_q10": 13.0,
            "away_q90": 28.0,
            "margin_q10": -9.0,
            "margin_q90": 20.0,
            "total_q10": 32.0,
            "total_q90": 61.0,
        },
        "example_score": {"home": 27, "away": 21, "prob": 0.01},
    }


def _game(gid: str, home: str, away: str, kick: str, legacy: bool = False) -> dict:
    g = _game_base(gid, home, away, kick)
    if not legacy:
        g.update(
            {
                "headline": "model_only",
                "ensemble_pick": home,
                "model_only": _model_only(),
                "absences": {"home": [], "away": []},
            }
        )
    return g


def _game_base(gid: str, home: str, away: str, kick: str) -> dict:
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
        _game("2026_11_ARI_KC", "KC", "ARI", "2099-11-22T18:00:00Z", legacy=True),
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
                "betfair_ex_eu": {
                    "p_home_shin": 0.6,
                    "p_home_mult": 0.6,
                    "home_price": 1.7,
                    "away_price": 2.3,
                    "edge_vs_ours": 0.1,
                },
                "matchbook": {
                    "p_home_shin": 0.6,
                    "p_home_mult": 0.6,
                    "home_price": 1.7,
                    "away_price": 2.3,
                    "edge_vs_ours": 0.1,
                },
                "bk": {
                    "p_home_shin": 0.62,
                    "p_home_mult": 0.61,
                    "home_price": 1.6,
                    "away_price": 2.5,
                    "edge_vs_ours": 0.08,
                },
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


def _build(tmp_path, odds=True, backtest=True):
    root = _repo(tmp_path, odds, backtest)
    return root, build_site(root=root, out=root / "site" / "_build")


def _text(out, page):
    return (out / page).read_text()


def test_formatters():
    es, en = Lang("es"), Lang("en")
    assert es.n(-12.5) == "\u221212,5" and es.signed(3.0) == "+3,0"
    assert es.pct(0.853) == "85\u202f%" and en.pct(0.853) == "85%" and en.n(-12.5) == "\u221212.5"
    assert (
        es.fav("HOU", "IND", 12.5) == "HOU \u221212,5"
        and en.fav("HOU", "IND", -3) == "IND \u22123.0"
    )
    assert es.fav("HOU", "IND", 0.0) == "igualado" and en.fav("HOU", "IND", 0.0) == "even"


PAGES = {
    "es": [
        "index.html",
        "historial.html",
        "metodo.html",
        "jornada/11.html",
        "partido/2026_11_IND_HOU.html",
    ],
    "en": [
        "en/index.html",
        "en/history.html",
        "en/method.html",
        "en/week/11.html",
        "en/game/2026_11_IND_HOU.html",
    ],
}


def test_site_builds_both_languages(tmp_path):
    _, out = _build(tmp_path)
    for lang, pages in PAGES.items():
        for page in [*pages, "assets/style.css"]:
            assert (out / page).exists(), page
        for page in pages:
            assert f'<html lang="{lang}">' in _text(out, page), page
    # every page links its twin for the switch and for search engines
    home = _text(out, "index.html")
    assert 'hreflang="en"' in home and 'class="lang"' in home and 'data-lang="en"' in home
    assert 'href="en/index.html"' in home
    game_en = _text(out, "en/game/2026_11_IND_HOU.html")
    assert 'href="../../partido/2026_11_IND_HOU.html"' in game_en
    assert "ens-lang" in (out / "assets/theme.js").read_text()
    assert "ens-lang" in (out / "assets/app.js").read_text()


def test_headline_is_the_model_alone_not_the_ensemble(tmp_path):
    _, out = _build(tmp_path)
    es = _text(out, "index.html")
    # model-only 64 %; the blended ensemble in the fixture says 70 % and must not be the headline
    # first card is the model-only game; the second is a legacy pick that kept its old headline
    assert "Gana HOU" in es
    assert re.findall(r'class="board"[^>]*>(\d+)<', es) == ["64", "70"]
    assert "Mercado: 62" in es  # the market is a reference with our difference next to it
    game = _text(out, "partido/2026_11_IND_HOU.html")
    assert "Modelo mezclado con el mercado" in game  # kept for comparison, named plainly


def test_card_shows_points_with_one_decimal_range_margin_total(tmp_path):
    _, out = _build(tmp_path)
    es = _text(out, "index.html")
    assert "26,4" in es and "20,4" in es  # (46.8 + 6) / 2 and (46.8 - 6) / 2
    assert "(17\u201333)" in es and "(13\u201328)" in es
    assert "HOU \u22126,0" in es and "46,8" in es  # margin and total from the same shown points
    en = _text(out, "en/index.html")
    assert "26.4" in en and "HOU \u22126.0" in en


def test_margin_and_total_equal_the_shown_points(tmp_path):
    root = _repo(tmp_path, False, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    d["games"][0]["model_only"].update(
        {"margin": 5.84, "total": 47.33, "home_points": 26.59, "away_points": 20.75}
    )
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    html = _text(out, "index.html")
    # 26,6 and 20,7 are shown: margin 5,9 and total 47,3 must follow from them
    assert "26,6" in html and "20,7" in html and "HOU \u22125,9" in html and "47,3" in html


def test_front_page_has_no_jargon_and_no_old_widgets(tmp_path):
    _, out = _build(tmp_path)
    banned = [
        "ensemble",
        "20.000",
        "sin comisión",
        "Cómo leer",
        "marcador típico",
        "Marcador típico",
        "cells",
        "ensamble",
    ]
    for page in ("index.html", "jornada/11.html"):
        html = _text(out, page)
        for word in banned:
            assert word not in html, (page, word)
        assert not re.search(r"\d+\s?pp\b", html), page
    banned_en = ["ensemble", "20,000", "typical score", "How to read", "cells"]
    for page in ("en/index.html", "en/week/11.html"):
        html = _text(out, page)
        for word in banned_en:
            assert word not in html, (page, word)


def test_jargon_lives_on_the_method_page(tmp_path):
    _, out = _build(tmp_path)
    es, en = _text(out, "metodo.html"), _text(out, "en/method.html")
    assert "ensemble" in es.lower() and "20.000" in es and "Calibración" in es
    assert "ensemble" in en.lower() and "20,000" in en and "Calibration" in en
    assert "modelo solo" in es.lower() and "model on its own" in en


def test_exact_score_only_as_a_labelled_example_on_the_game_page(tmp_path):
    _, out = _build(tmp_path)
    assert "27" not in re.findall(r"class=\"board\"[^>]*>(\d+)<", _text(out, "index.html"))
    game = _text(out, "partido/2026_11_IND_HOU.html")
    assert "marcador de ejemplo: IND 21, HOU 27" in game
    assert "example score: IND 21, HOU 27" in _text(out, "en/game/2026_11_IND_HOU.html")
    home = _text(out, "index.html")
    assert "IND 21" not in home and "21\u201327" not in home


def test_filter_group_is_never_empty(tmp_path):
    _, out = _build(tmp_path)
    for page in ("index.html", "en/index.html", "jornada/11.html"):
        html = _text(out, page)
        for m in re.finditer(r'<div class="chips"[^>]*>(.*?)</div>', html, re.S):
            assert "<button" in m.group(1), page
    # with nothing to filter there is no filter group at all
    root = _repo(tmp_path / "x", False, False)
    p = root / "predictions/2026/week11.json"
    d = json.loads(p.read_text())
    for g in d["games"]:
        g["home_win_prob"]["market"] = 0.66
        if "model_only" in g:
            g["model_only"]["home_win_prob"] = 0.66
        g["home_win_prob"]["ensemble"] = 0.66
    p.write_text(json.dumps(d))
    out2 = build_site(root=root, out=root / "site" / "_build")
    assert "Filtrar partidos" not in _text(out2, "index.html")
    assert "chips" not in _text(out2, "index.html").replace(".chips", "")


def test_no_raw_injury_counts_and_absences_are_context_in_points(tmp_path):
    root = _repo(tmp_path, False, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    d["games"][0]["context"].update({"home_out_lag": 1, "away_out_lag": 5})
    d["games"][0]["absences"] = {
        "home": [],
        "away": [{"player": "Pat Example", "position": "QB", "status": "out", "points": 4.3}],
    }
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    for page in ("index.html", "jornada/11.html", "partido/2026_11_IND_HOU.html"):
        html = _text(out, page)
        assert "frente a" not in html and "5 frente" not in html, page
    home, game = _text(out, "index.html"), _text(out, "partido/2026_11_IND_HOU.html")
    assert (
        "Pat Example" in home
        and "4,3 pts" in home
        and "no est\u00e1 incluido en el n\u00famero" in home
    )
    assert "4,3 puntos de margen por partido" in game and "no entra en las cifras" in game
    # a game with no notable absence mentions none
    assert "Bajas notables" not in _text(out, "partido/2026_11_ARI_KC.html")


def test_no_bookmaker_prices_or_exchanges_anywhere(tmp_path):
    _, out = _build(tmp_path)
    for page in out.rglob("*.html"):
        html = page.read_text().lower()
        for word in (
            "betfair",
            "matchbook",
            "smarkets",
            "mejor cuota",
            "best price",
            "valor esperado:",
        ):
            assert word not in html, (page.name, word)
        assert "bk" not in re.sub(r"[^a-z]", " ", html).split(), page.name
    game = _text(out, "partido/2026_11_IND_HOU.html")
    assert "consenso de 1 casas" in game and "No mostramos cuotas" not in game
    assert "No mostramos cuotas de casas" in _text(out, "metodo.html")


def test_team_names_are_official_english_in_both_languages(tmp_path):
    _, out = _build(tmp_path)
    for page in out.rglob("*.html"):
        html = page.read_text()
        for bad in (
            "Nueva York",
            "Los \u00c1ngeles",
            "Filadelfia",
            "Nueva Inglaterra",
            "Nueva Orleans",
        ):
            assert bad not in html, (page.name, bad)
    assert "Indianapolis Colts" in _text(out, "index.html")
    assert "Houston Texans" in _text(out, "en/index.html")


def test_every_template_and_code_key_exists_in_both_languages():
    assert set(STRINGS["es"]) == set(STRINGS["en"])
    here = Path(__file__).resolve().parents[1] / "src/ensemblitz/site"
    used: set[str] = set()
    for f in (here / "templates").glob("*.html"):
        used |= set(re.findall(r"\bt[x]?\('([A-Za-z0-9_.]+)'", f.read_text()))
    used |= set(
        re.findall(r"L\.t(?:ext)?\(\s*\"([A-Za-z0-9_.]+)\"", (here / "build.py").read_text())
    )
    dynamic = {"comp_", "hist.kind_", "hist.src_", "status_", "fact.venue_"}
    missing = {k for k in used if k not in STRINGS["es"] and k not in dynamic}
    assert not missing, missing
    for pre, keys in (
        ("comp_", ["ensemble_model_only", "elo", "kf", "lgbm", "market", "lgbm_mkt", "ensemble"]),
        ("hist.kind_", ["model_only", "ensemble"]),
        ("hist.src_", ["official", "model_only", "ensemble", "market"]),
        ("status_", ["out", "doubtful", "questionable", "returning", "other"]),
        ("fact.venue_", ["dome", "open", "open_nowx"]),
    ):
        for k in keys:
            assert pre + k in STRINGS["es"], pre + k


def test_no_em_dash_in_any_string():
    for lang, table in STRINGS.items():
        for k, v in table.items():
            assert "\u2014" not in v, (lang, k)


def test_site_builds_with_nothing(tmp_path):
    out = build_site(root=tmp_path, out=tmp_path / "site" / "_build")
    assert "Sin jornada" in _text(out, "index.html")
    assert "No week yet" in _text(out, "en/index.html")
    assert "Todav\u00eda no hay partidos terminados" in _text(out, "historial.html")


def test_legacy_pick_is_labelled_and_has_no_ranges(tmp_path):
    _, out = _build(tmp_path, False, False)
    game = _text(out, "partido/2026_11_ARI_KC.html")
    assert "antes del cambio de modelo" in game
    assert "antes del cambio de modelo" in _text(out, "index.html")
    assert "antes del cambio de modelo" not in _text(out, "partido/2026_11_IND_HOU.html")


def _graded(root, rows):
    (root / "results/2026").mkdir(parents=True)
    (root / "results/2026/week11.json").write_text(json.dumps(rows))


def test_history_grades_each_pick_against_its_own_headline(tmp_path):
    root = _repo(tmp_path, False, False)
    base = {"season": 2026, "week": 11, "total": 41.0}
    rows = [
        {
            **base,
            "game_id": "2026_11_IND_HOU",
            "home_team": "HOU",
            "away_team": "IND",
            "result": 7.0,
            "pick": "HOU",
            "headline": "model_only",
            "headline_correct": 1,
            "ensemble_model_only_correct": 1,
            "ensemble_correct": 1,
            "market_correct": 1,
        },
        {
            **base,
            "game_id": "2026_11_ARI_KC",
            "home_team": "KC",
            "away_team": "ARI",
            "result": -3.0,
            "total": 40.0,
            "pick": "KC",
            "ensemble_correct": 0,  # a pick saved before the change: no headline fields
            "ensemble_model_only_correct": 1,
            "market_correct": 0,
        },
    ]
    _graded(root, rows)
    out = build_site(root=root, out=root / "site" / "_build")
    hist = _text(out, "historial.html")
    assert "1/2" in hist  # official: model_only hit, legacy ensemble pick missed
    assert "modelo solo" in hist and "mezcla con el mercado (anterior)" in hist
    assert "<svg" in hist
    assert "Final: IND 17, HOU 24" in _text(out, "index.html")
    hist_en = _text(out, "en/history.html")
    assert "blend with the market (earlier)" in hist_en and "model alone" in hist_en


def test_build_output_has_no_em_dash(tmp_path):
    _, out = _build(tmp_path)
    for page in out.rglob("*.html"):
        assert "\u2014" not in page.read_text(), page.name


def test_weather_hidden_when_not_known(tmp_path):
    root = _repo(tmp_path, False, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    for g in d["games"]:
        g["context"].update({"weather_known": 0, "temp": None, "wind": None})
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    game = _text(out, "partido/2026_11_IND_HOU.html")
    assert "\u00b0C" not in game and "km/h" not in game


def test_weather_shown_in_metric_units(tmp_path):
    _, out = _build(tmp_path, False, False)
    game = _text(out, "partido/2026_11_IND_HOU.html")
    assert (
        "10\u202f\u00b0C" in game and "km/h" in game and "\u00b0F" not in game and "mph" not in game
    )


def test_week_without_odds_or_news_shows_no_repo_paths(tmp_path):
    _, out = _build(tmp_path, False, False)
    for page in ("index.html", "jornada/11.html", "partido/2026_11_IND_HOU.html"):
        html = _text(out, page)
        assert "reports/odds" not in html and "predictions/" not in html, page
    assert "l\u00ednea de cierre de nflverse" in _text(out, "index.html")
