"""The gap printed on the page must equal the difference of the percentages printed next to it."""

import json
import re

import numpy as np

from ensemblitz.site.build import build_site, gap_pts, shown_pct
from ensemblitz.site.i18n import Lang
from test_site import _repo


def _int(txt: str) -> int:
    return int(re.sub(r"[^\d]", "", txt))


def test_gap_equals_difference_of_displayed_percentages():
    rng = np.random.default_rng(7)
    es, en = Lang("es"), Lang("en")
    for a, b in rng.uniform(0.05, 0.95, size=(3000, 2)):
        for L in (es, en):
            assert _int(L.pct(a)) == shown_pct(a) and _int(L.pct(b)) == shown_pct(b)
        g = gap_pts(a, b)
        assert g == shown_pct(a) - shown_pct(b)
        txt = es.signed(g, 0)
        assert _int(txt) == abs(g)
        assert ("\u2212" in txt) == (g < 0)


def test_rounding_case_that_used_to_disagree():
    # 67 % and 65 % on screen, raw gap 1,0: the old page printed +1,0 pp
    assert gap_pts(0.6651, 0.6549) == 2
    assert gap_pts(None, 0.5) is None


def test_page_prints_integer_gap_matching_its_percentages(tmp_path):
    root = _repo(tmp_path, False, False)
    path = root / "predictions/2026/week11.json"
    d = json.loads(path.read_text())
    g = d["games"][0]
    g["home_win_prob"].update({"market": 0.6549, "ensemble": 0.66})
    g["model_only"]["home_win_prob"] = 0.6651
    g["home_win_prob"]["ensemble_model_only"] = 0.6651
    path.write_text(json.dumps(d))
    out = build_site(root=root, out=root / "site" / "_build")
    html = (out / "jornada/11.html").read_text()
    assert "Mercado: 65\u202f% (nosotros +2)" in html and "+1,0" not in html
    assert "Market: 65% (us +2)" in (out / "en/week/11.html").read_text()
