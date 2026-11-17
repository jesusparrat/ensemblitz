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

v0.1 simulates *possessions*, not plays. The extension points for later:
`exp_points_*` becomes a per-team rating vector (pass/rush/defence), possession outcomes become
play sequences, and in-game injuries, player health and hourly weather become time-varying
modifiers of those ratings.
