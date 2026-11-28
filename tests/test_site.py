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
    assert es.fav("HOU", "IND", 12.5) == "HOU +12,5" and en.fav("HOU", "IND", -3) == "IND +3.0"
    assert (
        es.spread_line("HOU", "IND", 12.5) == "HOU \u221212,5"
        and en.spread_line("HOU", "IND", -3) == "IND \u22123.0"
    )
    assert es.fav("HOU", "IND", 0.0) == "igualado" and en.fav("HOU", "IND", 0.0) == "even"
    # margin_range preserves away -> home histogram axis order in every sign regime
    assert es.margin_range("HOU", "IND", -10, 27) == "IND +10 a HOU +27"
    assert en.margin_range("HOU", "IND", -10, 27) == "IND +10 to HOU +27"
    assert es.margin_range("HOU", "IND", 2, 27) == "HOU +2 a HOU +27"
    assert es.margin_range("HOU", "IND", -27, -2) == "IND +27 a IND +2"
    assert en.margin_range("HOU", "IND", -27, -2) == "IND +27 to IND +2"
    assert es.margin_range("HOU", "IND", 0, 18) == "empate a HOU +18"
    assert en.margin_range("HOU", "IND", -14, 0) == "IND +14 to tie"


PAGES = {
    "es": [
        "index.html",
        "historial.html",
        "metodo.html",
        "verificar.html",
        "jornada/11.html",
        "partido/2026_11_IND_HOU.html",
    ],
    "en": [
        "en/index.html",
        "en/history.html",
        "en/method.html",
        "en/verify.html",
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
    assert "HOU +6,0" in es and "46,8" in es  # margin and total from the same shown points
    en = _text(out, "en/index.html")
    assert "26.4" in en and "HOU +6.0" in en


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
    assert "26,6" in html and "20,7" in html and "HOU +5,9" in html and "47,3" in html


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
    assert "consenso de 1 operadores" in game and "No mostramos cuotas" not in game
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
    dynamic = {
        "comp_",
        "comp_short_",
        "hist.kind_",
        "hist.src_",
        "status_",
        "fact.venue_",
        "grp_",
        "unit_",
        "band.",
    }
    missing = {k for k in used if k not in STRINGS["es"] and k not in dynamic}
    assert not missing, missing
    for pre, keys in (
        ("comp_", ["ensemble_model_only", "elo", "kf", "lgbm", "market", "lgbm_mkt", "ensemble"]),
        ("hist.kind_", ["model_only", "ensemble"]),
        ("hist.src_", ["official", "model_only", "ensemble", "market"]),
        ("status_", ["out", "doubtful", "questionable", "returning", "other"]),
        ("fact.venue_", ["dome", "open", "open_nowx"]),
        (
            "band.",
            [
                "away_22p",
                "away_15_21",
                "away_15",
                "away_8_14",
                "away_4_7",
                "away_1_7",
                "away_1_3",
                "tie",
                "home_1_3",
                "home_1_7",
                "home_4_7",
                "home_8_14",
                "home_15_21",
                "home_15",
                "home_22p",
            ],
        ),
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
    assert "l\u00ednea pre-partido de nflverse" in _text(out, "index.html")


def test_en_pages_use_12h_eastern_time_and_group_snf_on_sunday(tmp_path):
    root = _repo(tmp_path, True, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    # SNF: Monday 01:20Z = Monday 02:20 Madrid (CET), Sunday 8:20 PM ET (EST)
    d["games"][0]["kickoff_utc"] = "2099-11-23T01:20:00Z"
    # Early September EDT game: 17:00Z = 19:00 Madrid (CEST), 1:00 PM ET (EDT)
    d["games"][1]["kickoff_utc"] = "2099-09-14T17:00:00Z"
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")

    es_home = _text(out, "index.html")
    en_home = _text(out, "en/index.html")
    assert "02:20" in es_home and "Lunes 23" in es_home
    assert "8:20 PM" in en_home and "Sunday Nov 22" in en_home
    assert "1:00 PM" in en_home and "ET" in en_home
    assert "Madrid" not in en_home
    en_game = _text(out, "en/game/2026_11_IND_HOU.html")
    assert "Sunday Nov 22, 8:20 PM ET." in en_game and "Madrid" not in en_game


def test_game_page_has_single_market_prob_and_separates_nflverse_ref_line(tmp_path):
    root = _repo(tmp_path, True, False)
    pred_p = root / "predictions/2026/week11.json"
    d = json.loads(pred_p.read_text())
    d["games"][0]["home_win_prob"]["market"] = 0.77  # distinct from ensemble 0.70 and odds 0.62
    pred_p.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    game_es = _text(out, "partido/2026_11_IND_HOU.html")
    # Consensus from Odds API is 62%; nflverse 77% must not appear as a second market row
    assert "62 %" in game_es
    assert "Consenso The Odds API (1 operadores, sin margen)" in game_es
    assert "Descargado el" in game_es
    assert "Línea de referencia (nflverse)" in game_es
    assert "HOU −5,5" in game_es  # literal betting spread uses minus
    assert "HOU +6,0" in game_es  # model margin uses positive winning margin
    assert "IND +9 a HOU +20" in game_es  # away -> home range with team labels
    tech = game_es.split('<details class="tech">', 1)[1]
    assert "Mercado (cierre" not in tech and "77 %" not in tech


def test_market_timestamp_distinguishes_fetched_captured_and_read(tmp_path):
    # Case 1: Odds API report -> fetched ("Descargado" / "Fetched")
    _, out1 = _build(tmp_path / "c1", odds=True, backtest=False)
    assert "Fetched" in _text(out1, "en/game/2026_11_IND_HOU.html")

    # Case 2: nflverse fallback -> read ("Leído" / "Read")
    _, out2 = _build(tmp_path / "c2", odds=False, backtest=False)
    en2 = _text(out2, "en/game/2026_11_IND_HOU.html")
    assert "Pre-game nflverse line" in en2 and "Read " in en2

    # Case 3: v1 snapshot with odds_api_consensus.captured_at_utc and no reports/odds/ -> Captured
    root3 = tmp_path / "c3"
    (root3 / "predictions/2026/week11").mkdir(parents=True)
    v1 = {
        "schema_version": "1",
        "season": 2026,
        "week": 11,
        "generated_at_utc": "2026-11-18T21:41:36Z",
        "data_cutoff_utc": "2026-11-18T12:00:00Z",
        "model_version": "0.1.0",
        "git_sha": "abc1234",
        "reproducible": True,
        "data_snapshot": {},
        "games": [
            {
                "game_id": "2026_11_IND_HOU",
                "home_team": "HOU",
                "away_team": "IND",
                "kickoff_utc": "2099-11-20T01:15:00Z",
                "generated_at_utc": "2026-11-18T21:41:36Z",
                "headline": {
                    "home_win_prob": 0.64,
                    "home_points": 26.4,
                    "away_points": 20.4,
                    "distribution": {
                        "home_points": [17.0, 33.0],
                        "away_points": [13.0, 28.0],
                        "margin_home": [-9.0, 20.0],
                        "total": [32.0, 61.0],
                    },
                    "example_score": {"home": 27, "away": 21, "prob": 0.01},
                },
                "ensemble": {"home_win_prob": 0.70, "margin_home": 5.5, "total": 45.0},
                "components": {"elo": 0.65, "kf": 0.66, "lgbm": 0.68, "lgbm_mkt": 0.70},
                "market": [
                    {
                        "source": "odds_api_consensus",
                        "captured_at_utc": "2026-11-18T20:00:00Z",
                        "is_closing": False,
                        "home_win_prob": 0.62,
                        "margin_home": None,
                        "total_line": None,
                        "n_books": 40,
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
                },
                "absences": {"home": [], "away": []},
            }
        ],
    }
    (root3 / "predictions/2026/week11/20261118T214136Z.json").write_text(json.dumps(v1))
    out3 = build_site(root=root3, out=root3 / "site" / "_build")
    en3 = _text(out3, "en/game/2026_11_IND_HOU.html")
    assert "Captured Nov 18, 2026, 3:00 PM ET" in en3
    # C18 on v1: header uses data_cutoff_utc (7:00 AM ET), footer uses generated_at_utc (4:41 PM ET)
    assert "Data from Nov 18, 2026, 7:00 AM ET" in en3
    assert "Latest picks saved Nov 18, 2026, 4:41 PM ET" in en3


def test_flagged_card_does_not_duplicate_gap_number(tmp_path):
    root = _repo(tmp_path, True, False)
    odds_p = root / "reports/odds/2026_week11.json"
    od = json.loads(odds_p.read_text())
    # +9 pp is below the fixed >= 10 pp threshold, so it must NOT be flagged.
    od["games"][0]["consensus_home_prob_shin"] = 0.55  # 64% vs 55% -> +9
    odds_p.write_text(json.dumps(od))
    out_unflagged = build_site(root=root, out=root / "site" / "_build_9")
    assert "is-flagged" not in _text(out_unflagged, "index.html")

    # +11 pp meets the fixed >= 10 pp threshold and must be flagged without duplicating the gap.
    od["games"][0]["consensus_home_prob_shin"] = 0.53  # 64% vs 53% -> +11
    odds_p.write_text(json.dumps(od))
    out = build_site(root=root, out=root / "site" / "_build")
    es = _text(out, "index.html")
    en = _text(out, "en/index.html")
    assert "is-flagged" in es and "+11" in es and "(nosotros +11)" not in es
    assert "is-flagged" in en and "+11" in en and "(us +11)" not in en


def test_data_stamp_v0_fallback_and_wall_clock_invariance(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from ensemblitz.site import build as B

    # v0 fixture has no data_cutoff_utc -> falls back legitimately to generated_at_utc
    root = _repo(tmp_path, False, False)

    class _Clock1(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 18, 10, 0, 0, tzinfo=UTC)

    class _Clock2(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 19, 22, 30, 0, tzinfo=UTC)

    monkeypatch.setattr(B, "datetime", _Clock1)
    out1 = B.build_site(root=root, out=tmp_path / "out1")
    monkeypatch.setattr(B, "datetime", _Clock2)
    out2 = B.build_site(root=root, out=tmp_path / "out2")

    assert _text(out1, "index.html") == _text(out2, "index.html")
    assert _text(out1, "en/index.html") == _text(out2, "en/index.html")
    assert "Datos del 17 nov 2026, 21:00 (Madrid)" in _text(out1, "index.html")
    assert "Data from Nov 17, 2026, 3:00 PM ET" in _text(out1, "en/index.html")


def test_method_page_reconciles_2133_scored_and_keeps_all_season_metrics(tmp_path):
    root = _repo(tmp_path, False, True)
    repo_root = Path(__file__).resolve().parents[1]
    bl_src = repo_root / "reports" / "baseline_2018_2025.json"
    (root / "reports" / "baseline_2018_2025.json").write_text(bl_src.read_text())
    out = build_site(root=root, out=root / "site" / "_build")
    es = _text(out, "metodo.html")
    en = _text(out, "en/method.html")
    assert "2133 partidos decididos" in es and "2141" in es and "8 empates" in es
    assert "2133 decided" in en and "2141" in en and "8 ties" in en
    assert "Solo modelo (acierto / LL)" in es and "Model only (acc / LL)" in en
    assert "pr2-statistical-audit.md" in es and "pr2-statistical-audit.md" in en


def test_check_site_guards_catch_c6_c7_c15_c2_and_ignore_comments(tmp_path):
    import importlib.util

    repo_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "check_site", repo_root / "scripts" / "check_site.py"
    )
    cs = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cs)

    root = _repo(tmp_path, True, True)
    (root / "reports" / "baseline_2018_2025.json").write_text(
        (repo_root / "reports" / "baseline_2018_2025.json").read_text()
    )
    out = build_site(root=root, out=root / "site" / "_build")
    assert cs.check_output(out) == []

    # HTML comment mentioning "closing" must NOT trigger C7 visible-text guard
    game_en = out / "en/game/2026_11_IND_HOU.html"
    orig_game = game_en.read_text()
    game_en.write_text(orig_game.replace("</body>", "<!-- closing comment --></body>"))
    assert cs.check_output(out) == []

    # Visible "closing" on game page MUST fail C7
    game_en.write_text(orig_game.replace("</body>", "<p>closing line</p></body>"))
    assert any("closing-line wording" in e for e in cs.check_output(out))

    # Visible "Madrid" on English page MUST fail C6
    game_en.write_text(orig_game.replace("</body>", "<p>Madrid time</p></body>"))
    assert any("Madrid timezone text" in e for e in cs.check_output(out))
    game_en.write_text(orig_game)

    # Duplicate gap inside flagged .mkt MUST fail C15
    es_home = out / "index.html"
    orig_home = es_home.read_text()
    es_home.write_text(
        orig_home.replace(
            "</body>",
            '<div class="mkt"><span class="sig">+11</span> Mercado: 56% (nosotros +11)</div></body>',
        )
    )
    assert any("duplicate market gap" in e for e in cs.check_output(out))
    es_home.write_text(orig_home)

    # Unreconciled 2141 without 2133 on metodo.html MUST fail C2
    meth = out / "metodo.html"
    orig_meth = meth.read_text()
    meth.write_text(orig_meth.replace("2133", "XXXX"))
    assert any("2141 without reconciling 2133" in e for e in cs.check_output(out))
    meth.write_text(orig_meth)


def test_method_fallback_without_baseline_never_prints_na_model_only(tmp_path):
    # Only backtest.json present, no baseline_2018_2025.json
    _, out = _build(tmp_path, odds=False, backtest=True)
    es = _text(out, "metodo.html")
    en = _text(out, "en/method.html")
    assert "log loss n/d" not in es and "log loss of n/a" not in en
    assert "reports/backtest.md" in es and "reports/backtest.md" in en


def test_pr4_visual_identity_no_doto_no_kickers_full_bleed_hero_and_signal_bar(tmp_path):
    _, out = _build(tmp_path, odds=True, backtest=True)
    css = (out / "assets/style.css").read_text()
    assert "Doto" not in css and "doto" not in css
    assert not (out / "assets/fonts/doto-latin-wght-normal.woff2").exists()
    assert "--paper: #F3F4F6" in css
    assert ".chipf" not in css
    for page in (
        "index.html",
        "en/index.html",
        "partido/2026_11_IND_HOU.html",
        "historial.html",
        "metodo.html",
    ):
        html = _text(out, page)
        assert 'class="hero-band"' in html, page
        assert not any(
            "<small" in hm.group(1).lower()
            for hm in re.finditer(r"<h1\b[^>]*>(.*?)</h1>", html, re.S | re.I)
        ), page
        assert 'class="chipf"' not in html, page
    # Season/week context preserved naturally below H1 without eyebrow kickers
    assert "Temporada NFL 2026" in _text(out, "index.html")
    assert "2026 NFL season" in _text(out, "en/index.html")
    assert "Jornada 11, temporada 2026." in _text(out, "partido/2026_11_IND_HOU.html")
    assert "Week 11, 2026 season." in _text(out, "en/game/2026_11_IND_HOU.html")


def test_pr4_check_site_guards_fail_when_broken_on_purpose(tmp_path):
    import importlib.util

    repo_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "check_site", repo_root / "scripts" / "check_site.py"
    )
    cs = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cs)

    base_css = (repo_root / "src/ensemblitz/site/static/style.css").read_text()
    assert cs.check_css_rules(base_css) == []

    # Break 1: reintroduce Doto / 3rd font family
    bad_font = base_css + '\n.x { font-family: "Doto", monospace; }\n'
    assert any(
        "forbidden font family" in e or "more than 2 font" in e
        for e in cs.check_css_rules(bad_font)
    )

    # Break 2: font-size below 13px
    bad_size = base_css + "\n.tiny { font-size: 11px; }\n"
    assert any("below 13px" in e for e in cs.check_css_rules(bad_size))

    # Break 3: pill border-radius
    bad_pill = base_css + "\n.badge { border-radius: 999px; }\n"
    assert any("pill border-radius" in e for e in cs.check_css_rules(bad_pill))

    # Break 4: beige token & purple token
    bad_beige = base_css.replace("--paper: #F3F4F6;", "--paper: #F4ECE1;")
    assert any("beige" in e for e in cs.check_css_rules(bad_beige))
    bad_purple = base_css.replace("--ink-2: #4B5260;", "--ink-2: #6D28D9;")
    assert any("purple" in e for e in cs.check_css_rules(bad_purple))

    # Break 5: eyebrow kicker inside <h1> in built HTML
    _, out = _build(tmp_path, odds=True, backtest=False)
    home = out / "index.html"
    orig = home.read_text()
    home.write_text(orig.replace('<h1 id="h">', '<h1 id="h"><small>NFL</small>', 1))
    assert any("eyebrow kicker" in e for e in cs.check_output(out))
    home.write_text(orig)


def test_footer_contains_nflverse_cc_by_attribution(tmp_path: Path) -> None:
    _, out = _build(tmp_path)
    es = (out / "index.html").read_text(encoding="utf-8")
    en = (out / "en" / "index.html").read_text(encoding="utf-8")
    assert "nflverse" in es and "CC-BY 4.0" in es
    assert "nflverse" in en and "CC-BY 4.0" in en


def test_pr5_matchups_placement_two_level_ux_and_check_site(tmp_path: Path) -> None:
    import importlib.util
    import subprocess
    import sys

    spec = importlib.util.spec_from_file_location(
        "test_explain", Path(__file__).resolve().parent / "test_explain.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    _minimal_v1_doc = mod._minimal_v1_doc
    _sample_explanation = mod._sample_explanation

    root = tmp_path / "repo"
    (root / "predictions/2026/week12").mkdir(parents=True)
    v1 = _minimal_v1_doc(with_explanation=True)
    v1["games"][0]["explanation"] = _sample_explanation(season_week=2)  # triggers early-season note
    v1["games"][0]["kickoff_utc"] = "2099-11-29T18:00:00Z"
    (root / "predictions/2026/week12/20261124T180000Z.json").write_text(json.dumps(v1))
    out = root / "site/_build"
    build_site(root=root, out=out)

    es_game = _text(out, "partido/2026_12_IND_HOU.html")
    en_game = _text(out, "en/game/2026_12_IND_HOU.html")
    es_week = _text(out, "index.html")
    en_week = _text(out, "en/index.html")

    # Placement: Matchups to watch immediately after Expected points and before Against the market.
    assert (
        es_game.index("Puntos esperados")
        < es_game.index("Duelos a vigilar")
        < es_game.index("Frente al mercado")
    )
    assert (
        en_game.index("Expected points")
        < en_game.index("Matchups to watch")
        < en_game.index("Against the market")
    )

    # Level 1 visible: plain-language v1 summary + matchups + early-season note + injury provenance cutoff.
    assert "Duelo más marcado" in es_week and "forma reciente" not in es_week
    assert "Biggest unit mismatch" in en_week and "recent form" not in en_week
    assert "Inicio de temporada" in es_game and "Early season" in en_game
    assert "Test Player" in es_game and "no entra en ninguna probabilidad" in es_game
    assert "Test Player" in en_game and "not included in any probability" in en_game

    # Level 2 inside <details class="tech">: separated Stack, LightGBM TreeSHAP, Kalman, and Elo.
    tech_es = es_game.split('<details class="tech">', 1)[1]
    tech_en = en_game.split('<details class="tech">', 1)[1]
    visible_es = es_game.split('<details class="tech">', 1)[0]
    assert "TreeSHAP" in tech_es and "TreeSHAP" not in visible_es
    assert "Agregación exacta del titular" in tech_es
    assert "Descomposición exacta de Kalman" in tech_es
    assert "Descomposición exacta de Elo" in tech_es
    assert "Exact headline stack aggregation" in tech_en
    assert "LightGBM TreeSHAP attributions (LightGBM component only)" in tech_en
    assert "Exact Kalman decomposition" in tech_en
    assert "Exact Elo decomposition" in tech_en

    # Site guard script passes cleanly on v1 rendered output with explanation.
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/check_site.py"),
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_verify_page_lists_manifest_and_discloses_browser_and_attestation_scope(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, True, True)
    manifest = {
        "artifacts": {
            "predictions/2026/week11.json": "a" * 64,
            "predictions/2026/week11/20261118T214136Z.json": "b" * 64,
        }
    }
    (root / "predictions" / "MANIFEST.json").write_text(json.dumps(manifest))
    out = build_site(root=root, out=root / "site" / "_build")

    es_v = _text(out, "verificar.html")
    en_v = _text(out, "en/verify.html")

    # Language twins and manifest entries with SHA-256 and GitHub blob links.
    assert 'href="en/verify.html"' in es_v and 'href="../verificar.html"' in en_v
    for html in (es_v, en_v):
        assert 'id="manifest-data"' in html
        assert "predictions/2026/week11.json" in html
        assert "predictions/2026/week11/20261118T214136Z.json" in html
        assert ("a" * 64) in html and ("b" * 64) in html
        assert "github.com/jesusparrat/ensemblitz/blob/main/predictions/2026/week11.json" in html
        assert (
            "gh attestation verify predictions/MANIFEST.json --repo jesusparrat/ensemblitz" in html
        )
        assert (
            "gh attestation verify predictions/2026/week11/20261118T214136Z.json"
            " --repo jesusparrat/ensemblitz" in html
        )
        assert 'id="verify-file"' in html

    # Explicit Safeguard D disclosures: browser does NOT verify Sigstore signatures;
    # attestations prove artifact integrity and provenance, NOT statistical correctness.
    assert "No verifica firmas Sigstore" in es_v
    assert "No demuestran corrección estadística" in es_v
    assert "does not verify Sigstore signatures" in en_v
    assert "do not prove statistical correctness" in en_v

    # Safeguard H privacy disclosure on both method and verify pages.
    for html in (es_v, en_v, _text(out, "metodo.html"), _text(out, "en/method.html")):
        assert "ens-theme" in html and "ens-lang" in html and "ens-team" in html
    assert "No usar cookies no equivale a carecer de obligaciones" in es_v
    assert "Using zero cookies does not mean zero privacy obligations" in en_v


def test_nav_excludes_code_link_and_footer_keeps_it(tmp_path: Path) -> None:
    _, out = _build(tmp_path)
    for page, labels, code_word in (
        ("index.html", ("Jornada", "Historial", "Método", "Verificar"), "Código"),
        ("verificar.html", ("Jornada", "Historial", "Método", "Verificar"), "Código"),
        ("en/index.html", ("Week", "Record", "Method", "Verify"), "Code"),
        ("en/verify.html", ("Week", "Record", "Method", "Verify"), "Code"),
    ):
        html = _text(out, page)
        nav_m = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        foot_m = re.search(r'<footer class="wrap foot"[^>]*>(.*?)</footer>', html, re.S)
        assert nav_m and foot_m, page
        nav_html, foot_html = nav_m.group(1), foot_m.group(1)
        for label in labels:
            assert label in nav_html, (page, label)
        assert "github.com" not in nav_html and code_word not in nav_html, page
        assert "github.com/jesusparrat/ensemblitz" in foot_html and code_word in foot_html, page


def test_favorite_team_select_copy_link_and_hero_lede(tmp_path: Path) -> None:
    _, out = _build(tmp_path)
    es_home = _text(out, "index.html")
    en_home = _text(out, "en/index.html")
    for html in (es_home, en_home):
        sel_m = re.search(r'<select id="fav-team"[^>]*>(.*?)</select>', html, re.S)
        assert sel_m is not None
        opts = re.findall(r'<option value="([^"]*)">([^<]+)</option>', sel_m.group(1))
        # 1 blank default + 32 official NFL teams
        assert len(opts) == 33
        team_names = {name for val, name in opts if val}
        assert len(team_names) == 32
        assert "Houston Texans" in team_names and "Kansas City Chiefs" in team_names
        assert 'data-home="HOU"' in html and 'data-away="IND"' in html

    # Copy link button with aria-live confirmation on game pages.
    es_game = _text(out, "partido/2026_11_IND_HOU.html")
    en_game = _text(out, "en/game/2026_11_IND_HOU.html")
    assert (
        "data-copy-url" in es_game
        and "Copiar enlace" in es_game
        and 'aria-live="polite"' in es_game
    )
    assert "data-copy-url" in en_game and "Copy link" in en_game and 'aria-live="polite"' in en_game

    # Client-side JS implements ens-team and Web Crypto SHA-256 digest.
    app_js = (out / "assets/app.js").read_text()
    assert "ens-team" in app_js and 'digest("SHA-256"' in app_js

    # Refined homepage hero lede is 2 clear sentences preserving season context.
    for html in (es_home, en_home):
        lede_m = re.search(r'<p class="lede">(.*?)</p>', html, re.S)
        assert lede_m is not None
        sentences = [s.strip() for s in lede_m.group(1).strip().split(".") if s.strip()]
        assert len(sentences) == 2, lede_m.group(1)
