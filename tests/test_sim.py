import numpy as np

from ensemblitz.sim import SimParams, simulate_games, summarize_sim
from ensemblitz.sim.drive import drive_probabilities

EH = np.array([27.0, 21.0, 17.0])
EA = np.array([20.0, 21.0, 31.0])


def test_probabilities_sum_to_one():
    h, a = simulate_games(EH, EA, n_sims=8000, seed=1)
    p_home, p_away, p_tie = (h > a).mean(1), (a > h).mean(1), (h == a).mean(1)
    np.testing.assert_allclose(p_home + p_away + p_tie, 1.0)
    s = summarize_sim(h, a)
    np.testing.assert_allclose(s["p_home"], p_home + 0.5 * p_tie)


def test_scores_valid_and_mode_is_observed():
    h, a = simulate_games(EH, EA, n_sims=6000, seed=2)
    assert h.dtype.kind == "i" and (h >= 0).all() and (a >= 0).all()
    assert not np.isin(h, [1]).any()  # a single point is impossible
    s = summarize_sim(h, a)
    for i in range(len(EH)):
        assert ((h[i] == s["mode_home"][i]) & (a[i] == s["mode_away"][i])).any()
    assert (s["mode_prob"] > 0).all() and (s["mode_prob"] < 0.2).all()


def test_symmetry_and_means():
    h1, a1 = simulate_games(EH, EA, n_sims=20000, seed=3)
    h2, a2 = simulate_games(EA, EH, n_sims=20000, seed=4)
    p1 = summarize_sim(h1, a1)["p_home"]
    p2 = summarize_sim(h2, a2)["p_home"]
    np.testing.assert_allclose(p1, 1 - p2, atol=0.02)
    np.testing.assert_allclose(h1.mean(1), EH, atol=0.7)
    np.testing.assert_allclose(a1.mean(1), EA, atol=0.7)


def test_deterministic_given_seed():
    a = simulate_games(EH, EA, n_sims=500, seed=9)
    b = simulate_games(EH, EA, n_sims=500, seed=9)
    np.testing.assert_array_equal(a[0], b[0])


def test_drive_probabilities_hit_target():
    p = SimParams()
    td, fg = drive_probabilities(np.array([14.0, 22.0, 35.0]), 11.5, p)
    ppd = td * p.td_points + fg * 3
    np.testing.assert_allclose(ppd * 11.5, [14, 22, 35], rtol=1e-3)
