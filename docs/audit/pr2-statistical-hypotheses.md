# PR 2 — Statistical audit hypotheses and methodology

**Status:** pre-implementation plan  
**Branch:** `feat/pr2-statistical-audit`  
**Base:** `d19d69254c061e5c8735c1efd25d2764e7edfab6`

This document records the questions, hypotheses, evidence requirements, and decision rules for PR 2. It does not assert that any hypothesis has been confirmed. Numerical claims are leads to reproduce, not accepted results.

## 1. Goals and boundaries

PR 2 establishes whether historical evaluation is statistically defensible, whether predictions use only information available at their prediction cutoff, and whether model, market, and ensemble results are correctly attributed.

**In scope**
1. Reconcile historical evaluation populations and exclusions.
2. Compare MODEL_ONLY and MARKET on identical games using paired probabilistic scores and justified temporal uncertainty estimates.
3. Audit calibration, including high-confidence favourites.
4. Audit temporal leakage in Elo, Kalman, `models/kf_params.json`, opponent adjustments, features, LightGBM fitting, and hyperparameter/model selection.
5. Distinguish historical nflverse market data from timestamped pre-kickoff Odds API snapshots.
6. Audit `apply_news` and preserve MODEL_ONLY versus ensemble identity.
7. Remove bookmaker-level prices, bookmaker identifiers, and EV/edge outputs from current odds reports where their use is not justified; retain only permitted aggregate consensus information and bookmaker count.
8. Test the canonical home-minus-away margin convention and source conversions.
9. Update affected report consumers/tests and provide structured results.
10. Review data-use constraints and repository contribution-language conventions.

**Out of scope**
- No model retuning, refitting changes, feature redesign, weight changes, or hyperparameter changes.
- No changing the evaluation population after inspecting results to improve scores.
- No HTML, visual design, responsive layout, or timezone presentation changes (PR 3).
- No Odds API requests, refreshes, or manual odds downloads.
- No Git history rewriting, force-pushes, or changes to frozen prediction snapshots or historical manifest entries.
- Statistical superiority over the market is not a completion criterion.

If leakage or another defect is found, document and quantify its impact where possible. Do not silently repair it through retuning in PR 2.

## 2. Reconcile 2,133 vs 2,141 games

The current reports show `n_games=2141` in `reports/backtest.json`, while probabilistic metrics and `reports/baseline_2018_2025.json` use 2,133 observations. Do not assume the difference represents eight ties without reconciling game identities.

Required work:
- Identify exact game keys in each population and produce set differences.
- For every additional or excluded game, record season, week, game ID, outcome, probability availability, and exclusion reason.
- Inspect `baseline.scoring_frame()`, metric scoring, and backtest population construction.
- Distinguish total games considered, valid predictions, decided games, ties, missing inputs, and other exclusions.
- Ensure MODEL_ONLY and MARKET comparisons use identical eligible rows.

Acceptance: the discrepancy is explained by reproducible game-level reconciliation. Report fields state exactly what each count represents.

## 3. Paired MODEL_ONLY vs MARKET evaluation

Evaluate both sources on the same game IDs and calculate per-game paired score differences.

Metrics:
- Brier score and Log Loss as primary probabilistic metrics.
- Accuracy as a secondary metric, with threshold stated.
- Calibration and reliability summaries.

Use and document one sign convention for paired differences; recommended is MODEL_ONLY minus MARKET, so a negative difference favours MODEL_ONLY for loss metrics.

Do not assume game-level observations are independent. Inspect temporal dependence and justify a resampling unit (e.g. week or season/block), handling of incomplete blocks and season boundaries. Resample paired observations together. Predeclare replicate count, seed, confidence level, interval method, stratification if any, and number of independent blocks. The previously discussed 10,000 replicates and seed 20260 are candidates, not mandatory if inappropriate for the dependence structure. If uncertainty cannot be estimated robustly, state the limitation.

Acceptance: paired populations, differences, and intervals are reproducible; method and assumptions are disclosed. Do not overstate statistical significance.

## 4. Calibration and high-confidence favourites

A previous diagnostic suggested approximately **4.3 percentage points of overconfidence** for favourite probabilities at or above 75%. This is a hypothesis to reproduce, not an established result. A prior summary indicated a candidate segment of 396 observations, average predicted favourite probability around 80.86%, and observed win frequency around 76.52%; recompute from the canonical population.

Required:
- Define the favourite probability threshold and tie handling.
- Report N, mean predicted probability, observed win frequency, calibration gap, wins/losses, and suitable uncertainty intervals.
- Document treatment of ties and missing predictions.
- Provide full-population calibration bins with boundaries and counts.
- Treat sparse or unstable bins cautiously.

Acceptance: reproduce, revise with explanation, or reject the 4.3 pp figure. Mark the result inconclusive if evidence is insufficient.

## 5. Temporal leakage audit

For each evaluated game, every feature, fitted parameter, opponent adjustment, and model-selection decision must use only information available before that game's prediction cutoff. Distinguish feature leakage, fitting leakage, tuning leakage, and post-outcome contamination.

### Elo
- Trace initialization, update order, chronology, offseason carryover, and retrospective recalculation.
- Verify ratings are pre-game and exclude the game itself and all later results.
- Check that historical ratings are not regenerated using the full dataset before walk-forward evaluation.

### Kalman and `models/kf_params.json`
- Determine how/when the parameter file is generated, its data window, provenance, and timestamp.
- Inspect state initialization and filtering versus smoothing. Full-sample fitting or smoothing that uses future observations is invalid for pre-game predictions unless isolation is demonstrated.
- Check whether parameters generated from later seasons are reused for earlier historical predictions.

### Opponent adjustments
- Trace source observations and timestamps for opponent-strength and schedule adjustments.
- Verify that adjustments use only prior opponent performance, not end-of-season/full-season ratings containing future games.
- Inspect rolling windows, aggregates, normalization, imputation, and season-level statistics.

### Features and LightGBM walk-forward
- Inspect rolling, cumulative, lagged, target-derived, and opponent-derived features.
- Verify game-level cutoffs, including same-week games and kickoff ordering; a week-only cutoff may be insufficient.
- Confirm preprocessing, imputation, scaling, feature selection, and training are fit only on each fold's training data.
- Inspect walk-forward splits, label availability, training windows, and fit timestamps relative to evaluated games/seasons.
- Audit hyperparameter/model selection for use of evaluation-window or future outcomes.
- Check for validation/test reuse and accidental use of a full-history fit to generate historical predictions.

For each component, record code path, data inputs, cutoff, and evidence. Classify findings as **No leakage identified**, **Potential leakage**, or **Confirmed leakage**. If confirmed, quantify affected games/seasons and impact where a controlled diagnostic is possible. Do not retune or alter weights in PR 2.

Acceptance: all listed components are covered with evidence; saying only that the pipeline is walk-forward is insufficient.

## 6. Market source semantics and IND–HOU

Distinguish:
1. **Historical nflverse market data**, including the documented semantics and provenance of `spread_line` and moneyline-derived probabilities.
2. **Odds API snapshots**, which are aggregate market observations captured at a specific pre-kickoff time.

A pre-kickoff snapshot is not automatically a closing line. Never label it “closing” unless source and timestamp establish that it is the closing observation.

Investigate the cited **IND–HOU 86% vs 84%** discrepancy. For each value establish source/field, team perspective, market type, raw/no-vig/consensus/model-derived status, capture timestamp and timezone, time relative to kickoff, and whether the values refer to the same market observation. Do not compare them as equivalent until definitions are confirmed.

Report metadata should distinguish sources (suggested labels: `historical_nflverse` and `odds_api_snapshot`) and include source, market type, capture timestamp, timezone normalization, and pre-kickoff status where verifiable. Inspect current consumers before finalizing field names. HTML display is deferred to PR 3.

## 7. News adjustments and prediction identity

The canonical headline prediction remains MODEL_ONLY. News-adjusted ensemble values must not silently overwrite or masquerade as the model-only prediction.

Audit `apply_news` and consumers:
- fields adjusted (probability and/or margin);
- whether adjustment applies to ensemble only;
- source, timestamp, and scope metadata;
- whether backtest metrics compare equivalent definitions.

Document existing behavior or make justified additive report metadata changes. Preserve v0/v1 readers where possible. Do not alter frozen snapshots or manifest history.

## 8. Odds governance and circular EV

Per-bookmaker prices, bookmaker names, best-price selections, and EV/edge fields must not be published merely because they can be calculated. EV/edge based on a market-anchored and/or news-adjusted ensemble is not independent validation of that market and may be circular or misleading as an objective betting edge.

Proposed PR 2 changes:
- Remove bookmaker-level prices and bookmaker identifiers from generated odds reports.
- Remove per-bookmaker edge/EV, best-price, best-side, and related quote-dependent fields.
- Remove corresponding bookmaker-level data from current generated files under `reports/odds/` in branch HEAD.
- Preserve aggregate consensus probability and bookmaker count only if source terms and aggregation semantics permit their use.
- Update every consumer and test; inspect consumers before changing the report contract.
- Make no Odds API requests and do not refresh quote data.

Removing data from current HEAD does not erase historical commits or resolve obligations arising from previous collection/publication. Document relevant files/data categories, known source/plan terms and use restrictions, and proposed remediation before cleanup. Do not rewrite Git history or force-push by default. Technical removal is not legal clearance. If terms do not clearly permit aggregate consensus or bookmaker count, flag and pause that part for a decision.

Acceptance: current generated reports and consumers no longer publish or require bookmaker-level prices, bookmaker names, or circular EV/edge fields. Permitted aggregate fields have explicit provenance. History remains untouched.

## 9. Canonical margin sign convention

Canonical definition: `margin_home = predicted home score - predicted away score`. Positive favours home; negative favours away.

Trace market ingestion, model/ensemble margin, contract serialization, and report conversion. Verify nflverse `spread_line` semantics from source documentation. Verify the Odds API spread conversion applies the required opposite-sign mapping into the canonical convention.

Add regression tests for both conversion directions and positive, negative, and zero cases. Verify probabilities and margins are not independently sign-flipped. HTML display corrections remain in PR 3.

Acceptance: internal and serialized margin fields follow the canonical convention; source-boundary conversions are explicit and tested.

## 10. Structured reports and consumers

Inspect all consumers before report schema changes, including site build and tests. Prefer additive, unambiguous report-level fields; do not change prediction snapshot schemas unless strictly necessary and separately justified.

Reports should identify:
- total games, valid predictions, decided games, ties excluded, missing/invalid predictions, and other exclusions;
- exact N for each metric and source;
- MODEL_ONLY, MARKET, and ENSEMBLE separately;
- paired-comparison population and difference sign;
- calibration segment definitions and sample sizes;
- market source, market type, and capture-time semantics;
- audit limitations and unresolved questions.

Potential destinations are `reports/baseline_2018_2025.json` and `reports/backtest.json`; choose after inspecting consumers and avoiding duplicated sources of truth. Update all consumers/tests in the same PR for any breaking change. No HTML rendering changes in PR 2.

## 11. Contract, snapshots, and integrity

- Do not edit, regenerate, reorder, or replace frozen prediction snapshots.
- Do not modify historical `MANIFEST.json` entries or weaken `verify_integrity.py`.
- Prefer report-level audit metadata over prediction-contract changes.
- If a contract change is essential, make it additive, explicitly versioned, and test it against v0 and v1 readers.
- Preserve append-only ledger semantics and all integrity gates.

## 12. Repository governance

Review `AGENTS.md` for consistency with English-language documentation and code conventions. If the PR-description language convention is updated, keep it narrowly scoped and consistent with the user's review workflow.

## 13. Deliverables and completion gates

Deliverables:
1. This pre-implementation hypotheses/methodology document.
2. Reproducible population reconciliation and statistical results in structured reports.
3. Leakage audit with code/data provenance and impact assessment.
4. Market-source attribution and resolution of the IND–HOU comparison.
5. Removal of unsupported bookmaker-level/circular EV outputs, with consumers/tests updated and source-use constraints documented.
6. Margin-sign regression tests.
7. Final findings report, proposed path `docs/audit/pr2-statistical-audit.md`.

Completion gates:
- Every metric has a defined, reproducible population.
- MODEL_ONLY and MARKET are paired on identical game IDs.
- Temporal uncertainty methodology is justified and disclosed.
- All leakage components in Section 5 are audited.
- No confirmed leakage is silently repaired through PR 2 retuning.
- Market source/timestamps are explicit; snapshots are not mislabeled as closing lines.
- No bookmaker-level prices, bookmaker names, or circular EV/edge fields remain in current generated reports or consumers.
- Margin conversions have regression coverage.
- Reports and consumers agree on field semantics.
- Snapshot/manifest integrity checks remain intact.
- No Odds API request, history rewrite, force-push, or unapproved public UI change occurs.

An inconclusive statistical result is acceptable when limitations are explicit. PR 2 establishes what the evidence supports; it does not force a favourable model verdict.
