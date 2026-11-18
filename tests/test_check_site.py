import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_site", Path(__file__).resolve().parents[1] / "scripts" / "check_site.py"
)
check_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_site)


def test_contrast_tokens_pass():
    assert check_site.check_contrast() == []


def test_ratio_known_values():
    assert round(check_site.ratio("#000000", "#FFFFFF"), 1) == 21.0


def test_em_dash_is_caught(tmp_path):
    (tmp_path / "a.html").write_text("hello \u2014 bye", encoding="utf-8")
    assert any("em dash" in e for e in check_site.check_output(tmp_path))


def _page(tmp_path, name, body, lang="es"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    alt = (
        '<link rel="alternate" hreflang="es" href="a"><link rel="alternate" hreflang="en" href="b">'
    )
    path.write_text(
        f'<html lang="{lang}"><head>{alt}</head><body><a class="lang" href="x">EN</a>{body}</body></html>',
        encoding="utf-8",
    )


def test_clean_page_passes(tmp_path):
    _page(tmp_path, "index.html", "<p>Gana KC</p>")
    assert check_site.check_output(tmp_path) == []


def test_wrong_language_marker_is_caught(tmp_path):
    _page(tmp_path, "en/index.html", "<p>Hi</p>", lang="es")
    assert any("lang" in e for e in check_site.check_output(tmp_path))


def test_jargon_on_week_page_is_caught_but_not_on_method(tmp_path):
    _page(tmp_path, "index.html", "<p>El ensemble dice 3 pp</p>")
    _page(tmp_path, "metodo.html", "<p>El ensemble dice 3 pp</p>")
    errs = check_site.check_output(tmp_path)
    assert any("index.html" in e and "jargon" in e for e in errs)
    assert not any("metodo.html" in e and "jargon" in e for e in errs)


def test_bookmakers_exchanges_and_spanish_team_names_are_caught(tmp_path):
    _page(tmp_path, "index.html", "<p>Betfair Exchange</p><p>Los Cardenales de Arizona</p>")
    errs = " ".join(check_site.check_output(tmp_path))
    assert "bookmaker" in errs and "Spanish team name" in errs


def test_empty_filter_group_and_injury_counts_are_caught(tmp_path):
    _page(tmp_path, "index.html", '<div class="chips" role="group"> </div><p>12 lesionados</p>')
    errs = " ".join(check_site.check_output(tmp_path))
    assert "empty filter group" in errs and "injury-count" in errs


def test_missing_twin_is_caught(tmp_path):
    _page(tmp_path, "metodo.html", "<p>x</p>")
    assert any("missing English twin" in e for e in check_site.check_parity(tmp_path))
    _page(tmp_path, "en/method.html", "<p>x</p>", lang="en")
    assert check_site.check_parity(tmp_path) == []
