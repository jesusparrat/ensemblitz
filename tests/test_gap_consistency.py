"""The gap printed on the page must equal the difference of the percentages printed next to it."""

import json
import re

import numpy as np

from ensemblitz.site.build import build_site, fgap, fpct, gap_pp, shown_pct
from test_site import _repo


def _int(txt: str) -> int:
    return int(re.sub(r"[^\d]", "", txt))


def test_gap_equals_difference_of_displayed_percentages():
    rng = np.random.default_rng(7)
    for a, b in rng.uniform(0.05, 0.95, size=(3000, 2)):
        shown_a, shown_b = _int(fpct(a)), _int(fpct(b))
        assert shown_a == shown_pct(a) and shown_b == shown_pct(b)
        g = gap_pp(a, b)
        assert g == shown_a - shown_b
        txt = fgap(g / 100)
        assert _int(txt) == abs(g)
        assert ("\u2212" in txt) == (g < 0)


def test_rounding_case_that_used_to_disagree():
    # 67 % and 65 % on screen, raw gap 1,0 pp: the page used to print +1,0 pp
    assert gap_pp(0.6651, 0.6549) == 2
    assert fgap(0.02) == "+2\u202fpp"
    assert gap_pp(None, 0.5) is None and fgap(None) == "n/d"


def test_page_prints_integer_gap_matching_its_percentages(tmp_path):
    root = _repo(tmp_path, False, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    g = d["games"][0]
    g["home_win_prob"].update({"market": 0.6549, "ensemble": 0.66, "ensemble_model_only": 0.6651})
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    html = (out / "jornada/11.html").read_text()
    assert "+2\u202fpp" in html and "+1,0\u202fpp" not in html
