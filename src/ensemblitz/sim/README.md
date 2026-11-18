# `ensemblitz.sim`: score simulator (v0.1)

Interface (stable on purpose, so it can be ported to Rust/PyO3 and later to full play-by-play):

```python
simulate_games(exp_points_home, exp_points_away, n_sims=5000, seed=0, params=SimParams())
    -> (home_scores, away_scores)       # int64 arrays, shape (G, n_sims)

summarize_sim(home_scores, away_scores) -> dict[str, ndarray (G,)]
    # p_home, p_tie, margin_{mean,sd,q10,q90}, total_{mean,sd,q10,q90},
    # mode_home, mode_away, mode_prob   (most likely exact final score)
```

Rules for any implementation (the Python one, the Rust one, the play-by-play one):

- Inputs and outputs are plain arrays, no DataFrames, no hidden state; randomness comes only
  from `seed`.
- Same seed + same inputs => same outputs.
- Swapping home/away inputs swaps the outputs (symmetry), up to Monte Carlo noise.
- Scores are non-negative integers. Probabilities sum to 1 (`p_home` counts a tie as half).

v0.1 simulates possessions from expected points. `ensemblitz.sim.hybrid` is the
phase-3 game: the same possession draw for most of the clock, and plays only in the
last four minutes of the fourth quarter (and the last two of the first half) when the
margin is within 8. `ensemblitz pbp --evaluate` writes `reports/PBP_SIM.md`. It is not
what `ensemblitz predict` calls. Arrays in, arrays out, seed controls the randomness.
