# Prediction contract v1

This is the canonical definition of what ensemblitz publishes in `predictions/`. The machine-readable source of truth is [`schemas/predictions.v1.schema.json`](../schemas/predictions.v1.schema.json). [`src/ensemblitz/contract.py`](../src/ensemblitz/contract.py) validates against it and adds the rules a schema cannot express. If this document and the schema disagree, the schema wins and this document is fixed.

Status: **defined in PR 1a, written and read by the pipeline since PR 1b.** Legacy v0 files stay on disk unchanged and are read through `contract_io.load_week`.

## 1. One file, one snapshot

A v1 document is one prediction run for one `(season, week)`. Top level:

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `"1"` | Contract version. Files without it are v0 (see §7). |
| `model_version` | semver string | Version of the model and simulator code. It must be bumped by any change to features, models, ensemble or simulator. |
| `git_sha` | 40 hex | Commit the run executed. |
| `reproducible` | bool | `true` only for production runs from a clean working tree (see §2). |
| `generated_at_utc` | UTC `Z` | When this snapshot was produced. |
| `data_cutoff_utc` | UTC `Z` | Latest moment covered by the input data (the time of `ensemblitz update`). It is never later than `generated_at_utc`. |
| `data_snapshot` | `{path: sha256}` | SHA-256 of every input parquet under `data/raw/`, keyed by repo-relative POSIX path. |
| `season`, `week` | int | The week predicted. Not repeated inside games: `game_id` encodes them and the validator checks it. |
| `ensemble_weights` | object | Stack weights of the run (`with_market`, `no_market`), as the pipeline already writes them. |
| `games` | list | One record per game (see §4). |

## 2. Provenance and reproducibility

- `contract.provenance(root, production=True)` reads `git rev-parse HEAD` and **requires a clean working tree**: no modified, staged or untracked files. Ignored files such as `data/` and `.venv` do not count. If the tree is dirty it raises `DirtyTreeError`, so a published artifact cannot claim a SHA that does not describe the code that ran.
- Any run outside production (a local run, a test, an experiment) gets `reproducible: false`, even from a clean tree. A development artifact is therefore always flagged and can never pass for a published one.
- `contract.data_snapshot()` hashes `data/raw/*.parquet` (SHA-256, sorted by path). Together with `git_sha` and `uv.lock`, it pins code, environment and data.

## 3. Conventions

### Numbers

- **Margin:** every margin in data is **home points minus away points**. This covers `headline.distribution.margin_home`, `ensemble.margin_home` and `market[].margin_home`.
  - nflverse `spread_line` already uses this sign (positive = home favoured).
  - The Odds API spread `point` is the opposite (negative = home favoured) and is converted with `contract.odds_api_margin_home(point) = -point`.
- **Probability:** every probability is the **home team's** chance of winning, in `[0, 1]`. No `NaN`; a missing value is `null` where the schema allows it.
- **Expected points:** the headline stores `home_points` and `away_points`. Margin and total are derived (`contract.margin_home`, `contract.total`) and never stored a second time. This follows the existing rule that margin and total come from the printed expected points.
- **Pick:** the pick is derived: the home team when `headline.home_win_prob >= 0.5` (`contract.pick`).
- **80% range:** `[q10, q90]` of `n_sims` simulations with a fixed `seed`. The lowest 10% and highest 10% of outcomes fall outside.
- **Example score:** `example_score` is **illustrative**: one plausible score near the expected points, never a forecast of the exact result. Its `prob` is stored so the site can say how unlikely any single score is.

### Display rules (implemented in PR 3; the data never changes for display)

- One notation for a single margin: the favourite and the points it gives, for example `HOU −8.7`.
- A margin range is written **from the same team's perspective** as the number next to it: "HOU by 8.7, 80% range from −10 to +27 for HOU". A home-minus-away range never sits next to a favourite-minus label (audit finding C4).
- Time: data is always UTC. The Spanish site shows **Europe/Madrid** and the English site shows **America/New_York (ET)** (`contract.DISPLAY_TZ`). Today `/en/` still shows Madrid (audit finding C6); PR 3 fixes it.

### Market naming

- Each market figure is a `market[]` quote with an explicit `source`:
  - `nflverse_line`: spread, total and moneylines in the nflverse schedule read for the prediction run. The home moneyline is de-vigged against the away moneyline when both exist; otherwise the home-perspective `spread_line` is converted to a probability. In nflverse, `spread_line > 0` means the home team is favoured.
  - `odds_api_consensus`: aggregate head-to-head probability from The Odds API, with `n_books`. The stored Shin value is the unweighted arithmetic mean of the per-operator Shin no-vig probabilities, not a pooled Shin calculation. For this source, `margin_home` and `total_line` are null; only the aggregate probability and operator count are retained.
- `captured_at_utc` records when the quote was read into the snapshot. For The Odds API this is the cache's `fetched_at`; for nflverse it is the prediction-run read time, not an independently verified source-side quote timestamp. `data_cutoff_utc` is the latest observed time covered by the input data. `is_closing` is `true` only for a verified closing line. A line saved with a pre-game prediction is **not** "closing", and the site must not call it that (audit finding C7).
- One quote per source per game. The site shows one market figure per page, and its source is named (audit finding C5).
- Individual operator prices, operator names, best prices and expected value are not part of the contract (see AGENTS.md, Odds data governance).

### Headline and ensemble

- `headline` is the published number: the model on its own (Elo, Kalman and LightGBM stacked), with no market input.
- `ensemble` is a reference only: the model blended with the market. When a market line exists, its margin is anchored on the spread. In 2026 weeks 11 and 12 the fitted margin weights were `[1, 0, 0, 0, 0]`, so `ensemble.margin_home` equals the nflverse spread exactly (audit finding C1). It must never be presented as a model output.
- `components` holds the home win probability of each fitted model (`elo`, `kf`, `lgbm`, `lgbm_mkt`). The market is not a component in the contract; it lives in `market[]`.
- `news_adjustment.applies_to` records which block news moved. The current writer adjusts only the market-anchored ensemble probability and margin; the model-only headline remains unchanged. The backtest does not evaluate news adjustments because no historical point-in-time news archive is part of its scoring inputs.

## 4. Game record

Required fields:
- `game_id` (`SSSS_WW_AWAY_HOME`), `home_team`, `away_team`, `kickoff_utc` and `generated_at_utc`. `generated_at_utc` is per game because a game frozen at kickoff keeps the time of the run that saved it.
- `headline`: `home_win_prob`, `home_points`, `away_points`, `distribution`, `example_score`.
  - `distribution` holds `n_sims`, `seed`, `p_home`, the four ranges and an optional `histogram` that PR 1b fills so the site stops re-simulating (finding C8).
- `ensemble`, `components`, `market[]`.
- `context`: rest days, QB change, dome, weather. Units are in the names: `temp_f`, `wind_mph`.
- `absences`: context only, not part of any number.
- `news_adjustment`.

Unknown fields are rejected (`additionalProperties: false`), so a new field means a schema change, reviewed in a PR.

## 5. Validation

```python
from ensemblitz import contract

errors = contract.validate_week(doc)  # [] when valid
```

- Validation runs the JSON Schema subset in `contract.py`: `type`, `required`, `properties`, `patternProperties`, `additionalProperties`, `enum`, `const`, `pattern`, `minimum`/`maximum`, `items`, `anyOf` and local `$ref`. No new dependency.
- It then adds semantic checks:
  - unique `game_id`, consistent with `season`, `week` and the teams;
  - no game generated after its snapshot;
  - `q10 <= q90`;
  - one market quote per source;
  - `data_cutoff_utc <= generated_at_utc`.
  - `data_cutoff_utc` is the latest observed time in the input data, not the clock of `ensemblitz update`.
- `tests/test_contract.py` maps the real 2026 week 12 output (16 games, with its Odds API consensus) into v1 and validates it. This proves the schema describes what the pipeline actually produces.

## 6. Mapping from v0 (2026 weeks 11 and 12)

| v0 field | v1 field | Note |
|---|---|---|
| (absent) | `schema_version`, `git_sha`, `reproducible`, `data_cutoff_utc`, `data_snapshot` | New provenance |
| `generated_at` (file and game) | `generated_at_utc` | Renamed: always UTC |
| `model_version` (file and game) | `model_version` (file only) | Not repeated per game |
| `season`, `week` in each game | only at file level | Encoded in `game_id` |
| `home_win_prob.{elo,kf,lgbm,lgbm_mkt}` | `components.*` | |
| `home_win_prob.market` and `market.{spread_line,total_line,*_moneyline}` | `market[]` with `source: nflverse_line` | Sign unchanged (home minus away) |
| `reports/odds/...consensus_home_prob_shin`, `book_spread_home`, `book_total`, `n_books` | `market[]` with `source: odds_api_consensus` | `book_spread_home` negated |
| `home_win_prob.ensemble`, `predicted_margin`, `predicted_total` | `ensemble.*` | |
| `home_win_prob.ensemble_model_only`, `model_only.home_win_prob` | `headline.home_win_prob` | Was stored twice |
| `model_only.{home_points,away_points}` | `headline.{home_points,away_points}` | |
| `model_only.margin`, `model_only.total`, `model_only_margin` | derived | Was stored three times |
| `model_only.sim.*_q10/_q90`, `p_home` | `headline.distribution` | Ranges as `[q10, q90]` |
| `model_only.example_score` | `headline.example_score` | Illustrative |
| `pick`, `ensemble_pick`, `headline: "model_only"` | derived / dropped | Pick derived from the headline probability |
| `sim` (ensemble), `most_likely_score` (ensemble, with `raw_mode`) | dropped | Never shown since web v2; still in the v0 files in git |
| `news_adjustment.{prob_home_before,margin_before}` | `news_adjustment.{home_win_prob_before,margin_home_before}` | The "after" values are the `ensemble` block |
| `context.{home_rest,away_rest,temp,wind}` | `context.{home_rest_days,away_rest_days,temp_f,wind_mph}` | Units in the name. 0/1 flags become booleans |

`contract.detect_version(doc)` returns `"0"` for the legacy files and `"1"` for v1, and raises on anything else. `contract_io.load_week(path)` maps both to the v1 model without rewriting the file.

## 7. Ledger, integrity and the reader (PR 1b)

The procedure is in [`LEDGER.md`](LEDGER.md). In short:

1. **Ledger.** Every run writes a new, never-overwritten snapshot at `predictions/<season>/week<WW>/<generated_at_utc>.json`. Re-doing a week requires `--force`. No option, including `--force`, writes a new snapshot after the week's first kickoff. Historical corrections follow the rectification procedure in `LEDGER.md`.
2. **Historical snapshots.** The five versions of `predictions/2026/week12.json` from commits `22f65ff`, `081affe`, `475a36a`, `ae9f088` and `7690ac8` are stored byte for byte under `predictions/2026/week12/`. Week 11 is stored the same way from its own commits. They stay v0 on disk and are read through the v0 reader. The original `week11.json` and `week12.json` are not rewritten.
3. **Manifest.** `predictions/MANIFEST.json` stores **only the SHA-256 of each artifact** (path → hash). There is **no `first_commit` field and no self-hash**. Publication time is proven by git history: `scripts/verify_integrity.py` finds the first commit that contained those bytes (by blob) and checks that its committer time is before kickoff.
4. **Integrity check.** `verify_integrity.py` recomputes every hash, fails on a modified, deleted or substituted artifact, and validates v1 files with `contract.validate_week`. It runs in `ci.yml` and in `weekly.yml` before the commit. Adding a new week only extends the manifest.
5. **Reader.** `contract_io.load_week(path)` returns the v1 model for v0 and v1 files. `grade.py` and `site/build.py` read only through it. The site does not call the simulator: printed ranges come from the stored quantiles, and charts come from `headline.distribution.histogram` when it is present (v0 files have no histogram, so those game pages have no chart).
6. **Writer.** `predict.py` writes v1 with `contract.provenance(production=True)` in the weekly workflow and `production=False` locally, plus `contract.data_snapshot()` and `contract.data_cutoff_utc()`.
7. **Odds.** The weekly job fetches The Odds API *before* `predict`, so the consensus line is frozen in `market[]` with the snapshot. The comparison report is written afterwards from the cache, without a second API call.


## Optional `outcome_bands` (margin bands)

New v1 snapshots may include `outcome_bands` on each game. Existing v1 and v0 snapshots without the field stay valid. The writer fills it from the headline simulation (`headline.distribution.n_sims`, seed `2026`, the model-only score draws). It is not a second simulation.

Eleven bands of integer home margin (home points minus away points). A tie, margin 0, is its own band, including a game that is still tied after overtime. The bands, in order, are `away_22p` (away by 22 or more), `away_15_21`, `away_8_14`, `away_4_7`, `away_1_3`, `tie`, `home_1_3`, `home_4_7`, `home_8_14`, `home_15_21`, `home_22p` (home by 22 or more). Each band stores a probability rounded to 4 decimals. `top3` is those ids sorted by that probability, then by the order above. Grading records `outcome_band` and `outcome_band_rank` (`1`, `2`, `3`, or `outside top 3`) only when the frozen pick carried the field.

Snapshots already written with the earlier seven bands stay valid and are graded with the ids stored on that record: `away_15` (away by 15 or more), `away_8_14`, `away_1_7`, `tie`, `home_1_7`, `home_8_14`, `home_15` (home by 15 or more). A later reader does not recut those probabilities onto the eleven-band set.

## Optional `explanation` block (PR 5)

New v1 snapshots include an optional `explanation` object on each game. Existing v1 snapshots without `explanation` and legacy v0 snapshots remain valid (backward compatibility with existing snapshots; older consumers expecting strict unknown-key rejection should upgrade). The site formats `explanation` without recomputing attributions, rankings or injury values.

Each diagnostic layer is kept mathematically separate:

- **`stack`:** exact `model_only` stack aggregation over `["elo", "kf", "lgbm"]`. Win probability is `expit(sum_c w_c * logit(p_c) + prob_bias)` and margin is `sum_c mw_c * margin_c` (NNLS blend).
- **`lgbm_shap`:** exact LightGBM C++ TreeSHAP contributions (`pred_contrib=True`) grouped into 6 semantic buckets (`pass_game`, `rush_game`, `efficiency`, `qb`, `team_strength`, `situational`) such that `base_margin + sum(groups) == pred_margin`. Applies to the LightGBM component only, never the full stack.
- **`kalman`:** exact state-space margin decomposition `hfa + (home_off + away_def_allowed) - (away_off + home_def_allowed) == margin` (Kalman component only).
- **`elo`:** exact Elo margin decomposition `team_margin + hfa_margin == margin`, where `team_margin = (home_rating - away_rating) / 25.0` (Elo component only).
- **`matchups`:** four descriptive pre-game unit-vs-unit comparisons (`home_pass`, `away_pass`, `home_rush`, `away_rush`) computed from `features/build.py` opponent-adjusted EPA per play (`off_epa`, higher is better offense) and opponent-adjusted EPA allowed per play (`def_epa_allowed`, lower is better defense, higher is worse defense). Each game batch updates `off[u]` with `obs - opponent_pre_def[u]` and `dfn[u]` with `obs - opponent_pre_off[u]` under exponential decay (`decay=0.92`, prior shrinkage `150` pass plays / `100` rush plays, preseason retention `0.55`). Ranks `1..32` are computed strictly before each week batch with deterministic alphabetical tie-breaking; early-season weeks carry strong shrinkage towards zero. The descriptive indicator `combined_epa = off_epa + def_epa_allowed` is positive when the matchup tilts toward the offense and negative when it tilts toward the defense; it is a descriptive comparison only, not a causal effect or predicted margin contribution.
- **`qb_matchup`:** pre-game decayed QB EPA per dropback (`qb_rate`, `decay=0.97`, prior `200` dropbacks, preseason retention `0.80`; not opponent-adjusted), decayed dropback volume and starter-change flags. No player names are invented when absent from the source schedule.
- **`injury_context`:** serialized contextual injury diagnostics from `impact.py` (`source: "nflverse_injuries"`, `cutoff_utc`, `included_in_model: false`, `home`, `away`). Contextual only and never included in probabilities.
