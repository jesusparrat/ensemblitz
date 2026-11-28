# Results of the frozen picks

Graded games (pick saved before kickoff): 18

Since web v2 the headline pick is the model on its own (`ensemble_model_only`). Earlier picks were the blended ensemble; each graded row records which one it was.

| Source | N | Acierto | Log loss |
|---|---|---|---|
| market | 18 | 66.7% | 0.619 |
| elo | 18 | 61.1% | 0.594 |
| kf | 18 | 61.1% | 0.612 |
| lgbm | 18 | 61.1% | 0.590 |
| lgbm_mkt | 18 | 66.7% | 0.583 |
| model blended with the market | 18 | 66.7% | 0.625 |
| model only (headline) | 18 | 61.1% | 0.606 |

Against the spread (headline margin): 11-6
