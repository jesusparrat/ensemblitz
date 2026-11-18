"""Gates that do not need a full season: symmetry, coherence, stars, leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ensemblitz.sim.drive_fit import _Acc, rates_before
from ensemblitz.sim.hybrid import STARS, Matchup, from_book, simulate, split_probs, with_star_out


def _match(p_home_td: float = 0.22, p_away_td: float = 0.22) -> Matchup:
    def side(td: float) -> np.ndarray:
        rest = np.array([0.14, 0.40, 0.16, 0.08])
        rest = rest / rest.sum() * (1 - td)
        return np.array([td, *rest.tolist()])

    p = np.stack(
        [
            np.broadcast_to(side(p_home_td), (3, 5)),
            np.broadcast_to(side(p_away_td), (3, 5)),
        ]
    )[None].copy()
    return Matchup(
        p=p,
        sec=np.full((1, 2, 3), 140.0),
        is_neutral=np.array([True]),
        ot_both=np.array([False]),
        td_logit=np.zeros((1, 2)),
    )


def _swap(m: Matchup) -> Matchup:
    return Matchup(
        p=m.p[:, ::-1].copy(),
        sec=m.sec[:, ::-1].copy(),
        is_neutral=m.is_neutral.copy(),
        ot_both=m.ot_both.copy(),
        td_logit=m.td_logit[:, ::-1].copy(),
    )


def test_neutral_symmetry():
    m = _match(0.28, 0.16)
    h, a = simulate(m, n_sims=4000, seed=1)
    s = split_probs(h, a)
    np.testing.assert_allclose(s["p_home"] + s["p_away"], 1.0, atol=1e-12)
    hs, as_ = simulate(_swap(m), n_sims=4000, seed=1)
    t = split_probs(hs, as_)
    np.testing.assert_allclose(s["margin"] + t["margin"], 0.0, atol=0.6)
    np.testing.assert_allclose(s["p_home"] + t["p_home"], 1.0, atol=0.03)


def test_probability_margin_coherence():
    for home_td, away_td in ((0.30, 0.16), (0.26, 0.18), (0.18, 0.30)):
        m = _match(home_td, away_td)
        h, a = simulate(m, n_sims=2500, seed=2)
        s = split_probs(h, a)
        assert np.sign(s["p_home"][0] - 0.5) == np.sign(s["margin"][0])
        if home_td > away_td:
            assert s["p_home"][0] > 0.5 and s["margin"][0] > 0
        else:
            assert s["p_home"][0] < 0.5 and s["margin"][0] < 0


def test_star_out_lowers_win_probability():
    base = _match(0.22, 0.22)
    h0, a0 = simulate(base, n_sims=3000, seed=3)
    p0 = split_probs(h0, a0)["p_home"][0]
    for role in STARS:
        h, a = simulate(with_star_out(base, 0, role), n_sims=3000, seed=3)
        p = split_probs(h, a)["p_home"][0]
        assert p < p0, role


def test_leakage_canary_to_1e6():
    def frame(late_td: int) -> pd.DataFrame:
        rows = []
        for week, n_td in ((1, 30), (3, late_td)):
            for i in range(80):
                out = 0 if i < n_td else 2
                rows.append(
                    {
                        "season": 2020,
                        "week": week,
                        "game_id": f"2020_{week:02d}_{i}",
                        "team": "BUF" if i % 2 == 0 else "MIA",
                        "opp": "MIA" if i % 2 == 0 else "BUF",
                        "script": 1,
                        "out": out,
                        "sec": 140.0,
                        "plays": 5,
                        "is_home": int(i % 2 == 0),
                    }
                )
        return pd.DataFrame(rows)

    clean = rates_before(frame(10), 2020, 3)
    dirty = rates_before(frame(70), 2020, 3)
    a = from_book(clean, np.array(["BUF"]), np.array(["MIA"]), np.array([2020]), is_neutral=True)
    b = from_book(dirty, np.array(["BUF"]), np.array(["MIA"]), np.array([2020]), is_neutral=True)
    np.testing.assert_allclose(a.p, b.p, atol=1e-6)
    ha, aa = simulate(a, n_sims=200, seed=9)
    hb, ab = simulate(b, n_sims=200, seed=9)
    np.testing.assert_allclose(ha.astype(float) - hb, 0.0, atol=1e-6)
    np.testing.assert_allclose(aa.astype(float) - ab, 0.0, atol=1e-6)
    # The corruption does move the next week, so the canary is not vacuous.
    later_clean = from_book(
        rates_before(frame(10), 2020, 4),
        np.array(["BUF"]),
        np.array(["MIA"]),
        np.array([2020]),
        True,
    )
    later_dirty = from_book(
        rates_before(frame(70), 2020, 4),
        np.array(["BUF"]),
        np.array(["MIA"]),
        np.array([2020]),
        True,
    )
    assert not np.allclose(later_clean.p, later_dirty.p, atol=1e-3)


def test_accumulator_is_constructible():
    assert _Acc.fresh().off.shape[2] == 5
