# Drive-level simulator with a clutch window

Generated 2026-11-18T22:37:22+00:00. Walk-forward regular season 2018-2025, 2127 games, 2000 simulations, seed 202603. Rates use only earlier weeks. Command: `ensemblitz pbp --evaluate`.

## Verdict

The simulator is not eligible for production. Failed gates: margin_7, over_under, win_prob_log_loss, ece, top_bin. It stays behind `ensemblitz pbp` and is not connected to the published picks.

Most of a game is one draw per possession: touchdown, field goal, punt, turnover or end of half, opponent-adjusted and shrunk, with a longer drive when leading. Play-by-play is only the last four minutes of the fourth quarter and the last two minutes of the first half, and only when the margin is within 8. A touchdown is 7. In a tied game the field-goal share is raised. That weight was set on 2017 and not touched after.

## Gates

| Gate | Value | Band | Pass |
|---|---|---|---|
| Margin SD | 13.66 | 13.0 to 14.2 | True |
| Share of margins of 3 | 0.130 | 0.13 to 0.15 | True |
| Share of margins of 7 | 0.079 | 0.08 to 0.10 | False |
| Over/under log loss vs linear model | 0.7196 vs 0.6956 | simulator not worse | False |
| Win-prob log loss | 0.6465 | below 0.6344 | False |
| ECE (10 equal-count bins) | 0.0473 | below 0.020 | False |
| Top bin p>=0.80 absolute error | 0.3081 (n=2) | below 0.03 | False |

On the same 2119 games the model-only log loss is 0.6335 and the de-vigged close is 0.6087. Simulator minus model-only log loss is +0.0130 [+0.0046, +0.0214] (10000 paired resamples, seed 202603). Negative would mean the simulator is better.

## Shape and distance to the real margins

Simulated total 43.09 against actual 45.84. Simulated home margin 1.17 against actual 1.57. Actual margin SD 14.31. Actual share of 3 / 7 / 10: 0.144 / 0.085 / 0.049.

Wasserstein-1 between the pooled simulated outcomes and the actual games (lower is closer). The current possession simulator is fed the Kalman total and the model-only margin.

| Distribution | This simulator | Current possession simulator |
|---|---|---|
| Margin | 0.619 | 1.213 |
| Total | 2.758 | 1.160 |

Over/under uses 2091 games that did not land on the total. The linear model is a walk-forward logistic regression of the over on the closing total alone.

## Calibration deciles

| Bin | n | Predicted | Actual |
|---|---|---|---|
| 1 | 211 | 0.347 | 0.303 |
| 2 | 212 | 0.417 | 0.340 |
| 3 | 212 | 0.459 | 0.443 |
| 4 | 212 | 0.491 | 0.439 |
| 5 | 212 | 0.520 | 0.505 |
| 6 | 212 | 0.550 | 0.566 |
| 7 | 212 | 0.579 | 0.590 |
| 8 | 212 | 0.611 | 0.703 |
| 9 | 212 | 0.649 | 0.717 |
| 10 | 212 | 0.716 | 0.797 |

Top bin is every prediction at or above 0.80, not the tenth decile: predicted 0.808, actual 0.500, n=2.

## Not in production

`ensemblitz predict` is unchanged. No site template, stylesheet or string was edited. Neutral site turns off the only site effect, the home touchdown shift. There is no travel, altitude or weather input.
