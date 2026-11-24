# Results of the frozen picks

Graded games (pick saved before kickoff): 13

Since web v2 the headline pick is the model on its own (`ensemble_model_only`). Earlier picks were the blended ensemble; each graded row records which one it was.

| Source | N | Acierto | Log loss |
|---|---|---|---|
| market | 13 | 69.2% | 0.536 |
| elo | 13 | 69.2% | 0.550 |
| kf | 13 | 69.2% | 0.570 |
| lgbm | 13 | 69.2% | 0.526 |
| lgbm_mkt | 13 | 69.2% | 0.529 |
| model blended with the market | 13 | 69.2% | 0.550 |
| model only (headline) | 13 | 69.2% | 0.557 |

Against the spread (headline margin): 8-5
