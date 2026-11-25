# PR2 Statistical Audit

Status: implementation and static code review recorded; the season-block statistical report must be regenerated from the committed component cache before its confidence intervals are treated as final.

Run offline from the repository root:

```bash
uv run python scripts/audit_pr2.py
```

The command reads `reports/baseline_components.parquet`, does not download nflverse data, and does not call The Odds API. It writes the machine-readable result to `reports/pr2_statistical_audit.json` and replaces this document with the run's exact population reconciliation, paired metrics, season-block intervals and game-level exclusions.

## Findings established from the committed artifacts and code

### Population

The committed `reports/backtest.json` reports 2,141 played regular-season rows, while the paired baseline report scores 2,133 games. The difference is eight rows, but this audit does not assume they are all ties. The offline command above enumerates each excluded game and its reason (tie, missing prediction, or invalid probability), then hashes the exact paired game-ID population.

The legacy point estimates on 2,133 games are:

| Source | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| MODEL_ONLY | 64.79% | 0.22168 | 0.63440 |
| MARKET | 66.43% | 0.21108 | 0.60968 |
| ENSEMBLE | 66.24% | 0.21165 | 0.61125 |

These are committed point estimates, not new PR2 calculations. The old confidence intervals used an independent-game bootstrap and are superseded for inference by the season-block method. Do not use the old intervals to make significance claims.

### Uncertainty method

The revised paired bootstrap samples complete seasons with replacement, retaining every eligible game in each selected season. This preserves within-season dependence and uses the same sampled seasons for all sources and paired differences. There are only eight season clusters (2018-2025), so the resulting intervals are necessarily coarse. They are descriptive uncertainty bounds, not high-powered tests. The report also computes season-block intervals for the 75%+ favourite calibration segment.

### Temporal leakage review

- **Elo and opponent-adjusted ratings:** `features.build` computes all features for a season/week batch before updating state with that batch's results. Opponent adjustments use ratings captured before the game. The existing perturbation test verifies that changing results and team-game data from a cutoff onward does not move earlier features.
- **Kalman:** `run_kf` predicts a whole week before applying that week's results. `kalman.tune` slices to seasons strictly earlier than `before_season`; PR2 adds a regression test for this cutoff. However, `models/kf_params.json` contains no per-season training-window metadata. The stored values therefore cannot be independently proven to have been generated with the intended cutoff.
- **LightGBM and stack selection:** `pipeline._train_mask` includes only played games from earlier seasons/weeks; the stack is refitted before each week using earlier out-of-sample component predictions. PR2 adds a direct guard test for the LightGBM training mask. The repository does not preserve a reproducible history of manual hyperparameter or feature selection, so it cannot prove those choices were not influenced by later seasons.
- **Potential point-in-time leakage:** historical `home_qb_id`/`away_qb_id`, `temp` and `wind` fields feed QB and LightGBM features, but the repository has no point-in-time snapshots or availability timestamps for them. Actual starter identity and observed game weather may differ from what was knowable at forecast time. This is a potential availability leak, not a demonstrated result-leak bug. Its impact is not quantified here because that would require point-in-time source data and a controlled re-evaluation; PR2 does not retune the model.
- **Processed-data provenance:** prediction provenance hashes `data/raw/*.parquet`, while features also read derived `data/processed/team_games.parquet` and `qb_games.parquet`. Those files are derivable from raw data but are not directly hashed, leaving stale-cache reproducibility risk.
- **Injuries:** the current feature builder uses week t-1 or t-2 injury counts, not the current week's report. Historical publication timestamps are not retained in the feature cache.

### Market source and IND-HOU discrepancy

For 2026 week 11, IND @ HOU:

- nflverse stored home probability: **84.00%**, from the no-vig home/away moneylines **-700 / +500**.
- The Odds API mean-Shin probability: **85.77%**, across **42 operators**.
- The legacy mean-multiplicative probability was **84.07%**.
- Odds data was fetched at **2026-11-17 20:54:38Z**; the prediction was generated at **22:07:57Z**; kickoff was **2026-11-20 01:15:00Z**.

The difference is explained by distinct sources and de-vig methods, not by a sign conversion: the no-vig moneyline calculation gives 84%, the mean of per-operator Shin probabilities gives 85.77%, and the mean multiplicative method gives 84.07%. The Odds API snapshot predates the prediction by 1h 13m 19s. Neither value is a closing quote. The historical baseline uses nflverse closing schedule lines; the live Odds API quote is a separate pre-kickoff capture.

The report generator now compares the independent model-only headline with the aggregate mean-Shin probability. It no longer computes an edge against the market-anchored ensemble.

### News adjustment

The prediction writer adjusts only ensemble probability and margin. The model-only headline remains unchanged, and v1 records `news_adjustment.applies_to = "ensemble"`. Historical news is not included in the baseline because no point-in-time archive is available. Frozen snapshots remain unchanged.

### Odds-data governance

The public standard The Odds API terms reviewed on 2026-11-26 permit user-facing dashboards and derived values while prohibiting redistribution as a standalone raw-data feed. Current `reports/odds/` outputs now retain only aggregate mean-Shin probability, capture timestamp, and operator count. Individual prices, operator identifiers, best prices, EV and ensemble-relative edge are removed from current report outputs. Account-specific terms may differ; this is not a legal opinion.

### Margin sign convention

Canonical margin is home minus away. nflverse `spread_line` is positive when the home team is favoured. The Odds API spread point uses the opposite sign and is converted with `contract.odds_api_margin_home(point) = -point`. Regression tests already cover the Odds API conversion; PR2 adds a test for the nflverse spread fallback.

### Governance

`AGENTS.md` is already written in English, so no language migration was needed. This phase does not retune weights or hyperparameters, rewrite frozen snapshots, make The Odds API calls, change site HTML, or change visual design. The dynamic population and season-block results are generated by `scripts/audit_pr2.py`.
