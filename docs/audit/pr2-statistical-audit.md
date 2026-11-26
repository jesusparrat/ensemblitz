# PR2 Statistical Audit

Generated automatically by `uv run python scripts/audit_pr2.py` (offline, from `reports/baseline_components.parquet` and committed repository artifacts; no nflverse downloads and no calls to The Odds API). Do not hand-edit this file.

- Generated UTC: `2026-11-26T23:05:07+00:00`
- Model version: `0.1.0`
- Scoring seasons: 2018-2025
- Compact JSON summary: `reports/pr2_statistical_audit_summary.json`

## Executive summary

- MARKET clearly outperforms MODEL_ONLY on accuracy, Brier and log loss; paired stratified block CIs stay well above zero under 1-, 2- and 4-week block lengths.
- Point estimates slightly favour MARKET over ENSEMBLE, but the difference is tiny and block-length sensitive (the 95% CI crosses zero on Brier under 1-, 2- and 4-week blocks and on log loss under 1-week blocks); there is no robust separation between MARKET and ENSEMBLE, and no evidence that ENSEMBLE improves upon MARKET.
- The high-confidence (75%+) overconfidence hypothesis reproduces for MODEL_ONLY's own favourites (+4.35 pp, 95% CI strictly above zero across 1-, 2- and 4-week blocks), whereas ENSEMBLE's own 75%+ segment is +0.74 pp with CIs spanning zero under all block lengths.
- Constrained ensemble weight variants (ens_cap1, ens_pool) do not separate from the published ensemble under any block length (all CIs cross zero); no retuning in PR2.

## 1. Population reconciliation (2,141 vs 2,133)

- Rows in regular-season scope: 2141
- Played games: 2141
- Rows with valid probabilities for every compared source: 2141
- Ties excluded from probabilistic scoring: 8
- Rows with missing predictions: 0
- Rows with invalid probabilities: 0
- Final scored population: 2133
- Total excluded from scoring: 8

Exclusions are reconciled at game level rather than assumed to be ties:

- `2018_01_PIT_CLE` (season 2018, week 1): tie
- `2018_02_MIN_GB` (season 2018, week 2): tie
- `2019_01_DET_ARI` (season 2019, week 1): tie
- `2020_03_CIN_PHI` (season 2020, week 3): tie
- `2021_10_DET_PIT` (season 2021, week 10): tie
- `2022_01_IND_HOU` (season 2022, week 1): tie
- `2022_13_WAS_NYG` (season 2022, week 13): tie
- `2025_04_GB_DAL` (season 2025, week 4): tie

## 2. Paired source comparison

- Sources: market, model_only, ens
- Identical game IDs across MODEL_ONLY, MARKET and ENSEMBLE: True
- Paired N: 2133
- SHA-256 of sorted paired game IDs: `6c02e4792fce8c947492fc0d0e9db839b830b12f5cc712655ec55bc4d99cd144`

| Source | N | Accuracy | Brier | Log loss | Calibration slope |
|---|---:|---:|---:|---:|---:|
| MODEL_ONLY | 2133 | 64.79% | 0.22168 | 0.63440 | 0.928 |
| MARKET | 2133 | 66.43% | 0.21108 | 0.60968 | 1.056 |
| ENS | 2133 | 66.24% | 0.21165 | 0.61125 | 0.991 |

### Paired differences vs MARKET (primary: 2-week blocks stratified by season)

Method: paired 2-week block bootstrap stratified by season: contiguous 2-week blocks within each season (never crossing season boundaries) resampled with replacement independently per season. Primary unit: 2-week blocks (72 blocks across 8 seasons), 10,000 replicates, seed `20260`, 95% percentile CI. Sign convention: source minus MARKET (positive values on log loss and Brier mean worse than MARKET).

| Source minus MARKET | Δ log loss | 95% CI | Share better than MARKET | Δ Brier | 95% CI |
|---|---:|---:|---:|---:|---:|
| MODEL_ONLY | +0.02472 | [+0.01731, +0.03242] | 0.00% | +0.01059 | [+0.00724, +0.01401] |
| ENS | +0.00157 | [+0.00006, +0.00301] | 2.05% | +0.00057 | [-0.00005, +0.00117] |

### Block-length sensitivity (1-week, 2-week, 4-week blocks stratified by season)

| Block length | Blocks | Comparison | Δ log loss 95% CI | Δ Brier 95% CI |
|---|---:|---|---:|---:|
| 1-week | 144 | MODEL_ONLY minus MARKET | [+0.01733, +0.03233] | [+0.00732, +0.01390] |
| 1-week | 144 | ENSEMBLE minus MARKET | [-0.00006, +0.00321] | [-0.00010, +0.00124] |
| 1-week | 144 | ens_cap1 minus ENSEMBLE | [-0.00195, +0.00066] | [-0.00074, +0.00020] |
| 1-week | 144 | ens_pool minus ENSEMBLE | [-0.00227, +0.00050] | [-0.00083, +0.00020] |
| 2-week | 72 | MODEL_ONLY minus MARKET | [+0.01731, +0.03242] | [+0.00724, +0.01401] |
| 2-week | 72 | ENSEMBLE minus MARKET | [+0.00006, +0.00301] | [-0.00005, +0.00117] |
| 2-week | 72 | ens_cap1 minus ENSEMBLE | [-0.00206, +0.00081] | [-0.00077, +0.00025] |
| 2-week | 72 | ens_pool minus ENSEMBLE | [-0.00235, +0.00060] | [-0.00084, +0.00022] |
| 4-week | 40 | MODEL_ONLY minus MARKET | [+0.01812, +0.03172] | [+0.00772, +0.01366] |
| 4-week | 40 | ENSEMBLE minus MARKET | [+0.00009, +0.00300] | [-0.00004, +0.00116] |
| 4-week | 40 | ens_cap1 minus ENSEMBLE | [-0.00192, +0.00065] | [-0.00071, +0.00020] |
| 4-week | 40 | ens_pool minus ENSEMBLE | [-0.00215, +0.00044] | [-0.00077, +0.00017] |

Interpretation: MARKET beats MODEL_ONLY clearly across all three block lengths on both log loss and Brier. For ENSEMBLE vs MARKET, point estimates favour MARKET slightly (+0.00157 log loss, +0.00057 Brier), but the Brier 95% CI crosses zero under 1-, 2- and 4-week blocks and the log-loss 95% CI crosses zero under 1-week blocks (while sitting near zero at +0.00006 under 2-week blocks). Accordingly, PR2 does not claim a robust separation between MARKET and ENSEMBLE; it concludes that ENSEMBLE does not demonstrate a predictive edge over MARKET.

The resampling share below zero is descriptive and not a conventional hypothesis-test p-value.

## 3. High-confidence favourites (75%+)

Each source is evaluated on its own 75%+ favourite subset (different sample sizes), with 2-week stratified block bootstrap CIs and 1-week / 4-week sensitivity:

| Source | N | Mean predicted | Actual | Overconfidence | 2-week 95% CI | 1-week 95% CI | 4-week 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| MODEL_ONLY | 396 | 80.86% | 76.52% | +4.35 pp | [+0.60, +8.04] pp | [+0.64, +8.04] pp | [+1.59, +7.17] pp |
| MARKET | 470 | 80.93% | 82.34% | -1.41 pp | [-5.04, +2.26] pp | [-4.87, +2.21] pp | [-4.99, +2.32] pp |
| ENS | 525 | 81.31% | 80.57% | +0.74 pp | [-2.58, +4.07] pp | [-2.55, +3.92] pp | [-2.36, +3.90] pp |

Same-game comparison on the 525 games where ENSEMBLE assigns >=75% to its favourite: actual win rate 80.57% (2-week stratified 95% CI: [77.28%, 83.79%]). On those identical games, mean predicted probability for the ENSEMBLE favourite is MODEL_ONLY 76.82%, MARKET 80.08%, ENSEMBLE 81.31%.

## 4. Ensemble weights and constrained variants

- Published ENSEMBLE weight sum exceeds 1 in 100.00% of folds (mean 1.091, range 1.032 to 1.240).
- MODEL_ONLY weight sum exceeds 1 in 97.22% of folds (mean 1.074, range 0.991 to 1.233).
- Constrained variants (`ens_cap1`, `ens_pool`) show slightly lower point-estimate loss, but every paired 95% CI vs ENSEMBLE crosses zero across 1-, 2- and 4-week blocks.
- Decision: no weight or hyperparameter retuning in PR2.

## 5. MODEL_ONLY against the spread (ATS)

- Record vs closing spread: 1024-1057-52 (49.21%, Wilson 95% CI [47.06%, 51.35%]).
- Exact binomial test vs 52.38% (-110 break-even): p = 0.0040.
- No ATS profitability edge is present; MODEL_ONLY must not be framed as positive EV.

## 6. Leakage and temporal-validity review

### Walk-forward state and stacking

features.build computes every game's features for a (season, week) batch before updating ratings with that batch's results; Elo and opponent-adjusted EPA state are therefore pre-week. pipeline._train_mask admits only played games from earlier seasons/weeks. pipeline.add_ensemble_walk_forward refits stacks on those earlier out-of-sample component predictions. models.kalman.run_kf also predicts a whole week before applying that week's results.

### Kalman hyperparameters

kalman.tune explicitly slices season < before_season before likelihood optimisation. A regression test guards that cutoff. However models/kf_params.json has no per-season training-window metadata; the checked-in values cannot be independently proven to have been generated by that code path.

### LightGBM

The walk-forward component path uses _train_mask and refits before each season/week. The repository contains no reproducible hyperparameter/feature-selection history, so it cannot prove that manual model selection was not influenced by later seasons.

### Point-in-time availability risk

Historical schedule fields home_qb_id/away_qb_id and temp/wind feed QB-rate/change and LightGBM features. The repository does not retain point-in-time snapshots or availability timestamps for those fields. Actual starter identity and observed game weather may differ from what was knowable at forecast time. This is a potential availability leakage risk, not a demonstrated result-leakage bug; its impact is not quantified in PR2 because doing so requires point-in-time inputs and a separate controlled re-evaluation.

### Processed-data provenance

contract.data_snapshot hashes data/raw/*.parquet, while feature construction also reads data/processed/team_games.parquet and qb_games.parquet. Those processed files are derived from raw inputs but are not directly hashed in the prediction provenance; stale derived caches remain a reproducibility risk.

### Injury features

The feature builder uses Out/Doubtful counts from week t-1 or t-2, not the current week. This avoids direct same-week injury-report leakage, although source publication timestamps are not retained in the historical feature cache.

## 7. Market source and capture semantics

IND @ HOU (`2026_11_IND_HOU`): nflverse no-vig moneyline probability 84.00% (moneylines -700.0/500.0); The Odds API mean-Shin probability 85.77% across 42 operators (legacy multiplicative mean 84.07%). Odds capture `2026-11-17T20:54:38Z`; prediction generation `2026-11-17T22:07:57Z`; kickoff `2026-11-20T01:15:00Z`.

The nflverse value is the no-vig probability from -700/+500 moneylines (84.00%). The Odds API value is the unweighted mean of 42 operator-level Shin probabilities (85.77%); the legacy unweighted multiplicative mean was 84.07%. The Odds API cache was fetched at 20:54:38Z and the prediction was generated at 22:07:57Z. These are different sources and de-vig methods, captured at different times; neither is a closing quote, and the Odds API cache predates the prediction by 1h 13m 19s.

The historical baseline uses the nflverse schedule closing line, while the live Odds API value is a separate pre-kickoff snapshot. These must not be combined or labelled as a single closing quote. The Odds API Shin consensus is an unweighted arithmetic mean of per-operator Shin de-vigged probabilities, not a pooled market calculation.

## 8. News adjustment, odds governance and margin convention

- **News adjustment:** `apply_news` updates only ENSEMBLE probability and margin. The MODEL_ONLY headline remains untouched (`news_adjustment.applies_to = ensemble`). News is absent from the historical backtest because no point-in-time archive exists.
- **Odds-data governance:** Public standard terms reviewed 2026-11-26 permit derived values in user-facing dashboards provided the data is not the primary redistributed product, while prohibiting redistribution as a standalone raw feed (https://the-odds-api.com/terms-and-conditions.html; account-specific terms may differ). Current `reports/odds/` outputs retain only aggregate mean-Shin probability, capture timestamp, operator count, and model-only gap. Individual prices, operator identifiers, best prices, EV and ensemble-relative edge have been removed.
- **Margin sign convention:** Canonical margin is home minus away. nflverse `spread_line` is positive when home is favoured. The Odds API spread point uses the opposite sign and is converted by `contract.odds_api_margin_home(point) = -point`. Regression tests cover both directions and the nflverse spread fallback.

## 9. Governance and non-goals

`AGENTS.md` specifies English for code, comments, repository docs, commit messages, PR titles and PR descriptions, reserving Spanish for user discussion and the Spanish site. This audit does not retune weights, alter model hyperparameters, edit frozen prediction snapshots or `predictions/MANIFEST.json`, rewrite git history, call The Odds API, or modify site HTML. Potential point-in-time risks are documented rather than silently patched.
