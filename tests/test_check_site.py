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
    (tmp_path / "a.html").write_text("hola \u2014 adiós", encoding="utf-8")
    assert any("raya larga" in e for e in check_site.check_output(tmp_path))
