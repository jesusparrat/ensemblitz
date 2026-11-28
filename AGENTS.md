# Instructions for agents

## Style and design

- Language: the site is bilingual (Spanish by default, English under `/en/`). All UI strings live in `src/ensemblitz/site/strings.py`, both languages with identical keys. Code, comments, repository docs, commit messages, PR titles, PR descriptions and the README are in English. Spanish is used for discussion with the user and for the Spanish site (legacy generated reports under `reports/` remain in Spanish unless migrated). Times in Europe/Madrid on `/es/` and ET on `/en/`, Spanish uses decimal commas, °C and km/h.
- Team names are the official English names in both languages (`site/names.py`). No half-translations.
- Design: follow `DESIGN.md`. Do not change tokens, fonts or the visual direction without Jesús approving it.
- Antislop: rules in `.cursor/rules/antislop.mdc` and the MIT copy in `third_party/antislop/` (keep the `LICENSE`). No em dash in written text or in the site output.
- Never show repository paths, internal bookmaker keys or imputed figures presented as real data on the site. Never show individual bookmaker prices or an expected value: the only market figure is the consensus.
- A derived figure is computed from the same values that are displayed. The difference between two percentages on the site is the subtraction of the two printed integers (`gap_pts` in `site/build.py`); margin and total follow from the printed expected points of each team.
- The headline number is the model on its own (no market). The market is a reference. The blended ensemble stays in the data for comparison and for the record of older picks.

## Branches and pull requests

- Never touch `main` directly. Each change goes on a new branch (`feat/...`, `fix/...`) with a pull request. It is not merged until Jesús says so.
- One PR, one topic. Title and description in English: what changes, why, and which checks were passed (with the numbers).

## Mandatory checks before calling a change done

Run all of them, in this order, and paste the result in the PR. The environment comes from `uv.lock` and `.python-version` (Python 3.12, the same as CI): `make install` once, then run each command inside `.venv` or with `uv run --frozen`. If one fails, fix the cause; do not disable the check or widen its tolerance so it passes.

```bash
ruff check . && ruff format --check .
pytest -q
ensemblitz site && python scripts/check_site.py
python scripts/validate_outputs.py --site site/_build
python scripts/check_baseline.py            # in a PR: add --ref origin/main
```

`make check` chains them. `python scripts/check_baseline.py` re-stacks the cached predictions in seconds and fails if the log loss or Brier of the ensemble or of the model without market get worse than the tolerance (0.0015 and 0.0007) against the baseline. If the change touches features, Kalman, LightGBM or data, also run `ensemblitz update && python scripts/check_baseline.py --full`, which recomputes everything from nflverse (what the weekly `baseline-full.yml` workflow does).

A model change that improves the baseline is accepted by regenerating the artefacts (`ensemblitz baseline --full`) and explaining the improvement in the PR with its confidence interval. A change that worsens it is not merged unless Jesús explicitly decides so.

`scripts/check_site.py` also guards the site: contrast of every token pair, em dashes, language markers on every page, jargon on week pages, bookmaker and exchange names, half-translated team names and empty filter groups.

## No information leakage (hard rule)

- Everything used to predict a game comes from games and data **before** its week. Ratings, Elo, Kalman, LightGBM, ensemble weights, per-player impact and injury status: strict walk-forward, refitted before each (season, week).
- Hyper-parameters are fitted on past seasons only. Nothing is chosen by looking at 2018 to 2025 and then evaluated on 2018 to 2025.
- Injuries: use the report status (`report_status`, `practice_status`), never the final inactive list nor the player's performance in the same week or later. A per-player value is computed from earlier weeks only.
- Any new code that fits something with results carries a test that changes results and inputs from week W on and checks that no prediction of earlier weeks moves (see `tests/test_baseline.py` and `tests/test_features_leakage.py`).
- Picks are frozen before kickoff and not rewritten. Grading records which number was the headline when the pick was saved.

## Verify your work

- Do not assume something works because the code looks right: run it and read the output. Every behaviour change carries its test; every figure in a report comes from a command, not from memory.
- Before claiming that a model improves, compare against the baseline (`reports/BASELINE.md`) with a confidence interval. With about 2,000 games, differences of 0.002 in log loss are noise.
- When a new check should fail, show it once (break it on purpose and watch it go red) before trusting it.
- JSON outputs without `NaN` (use `null`). `validate_outputs.py` checks it.
- Quota and cost: do not launch long or parallel jobs without need. Cheap check first (`pytest -q`, `check_baseline.py` in fast mode), then the expensive one.

## Phase 1 (injuries)

- The rule for wiring something into production is the paired confidence interval of log loss against the variant without the change: only if the 95% CI is below zero. A borderline improvement is documented and not wired. Current result in `reports/PHASE1.md` (injuries: not significant, not wired).
- Variants tried after seeing the results are marked exploratory and do not decide.
- Because injuries are not wired, the site shows notable absences as context, in points of player value, and says they are not part of any number.

## Useful map

- `src/ensemblitz/baseline.py` and `baseline_report.py`: Phase 0 audit. `ensemblitz baseline [--full]` regenerates `reports/baseline_*.json|png`, `reports/BASELINE.md` and `reports/baseline_components.parquet`.
- `scripts/audit_injuries.py`: audit of the nflverse injury reports (needs network); result in `reports/injury_audit.json`.
- `src/ensemblitz/impact.py`, `margin.py`, `phase1.py`, `phase1_report.py`: per-player injury impact (value over replacement, probability of playing, discrete margin table). `ensemblitz phase1 [--full]` regenerates `reports/phase1_*` and `reports/PHASE1.md`. Not wired into production. `impact.notable_absences` feeds the context lines on the site.
- `src/ensemblitz/site/`: `build.py` (data and pages), `i18n.py` (language formats), `strings.py` (UI strings), `templates/`, `static/`.
- `src/ensemblitz/contract.py`, `contract_io.py`, `ledger.py`, `schemas/predictions.v1.schema.json`, `docs/CONTRACT.md`, `docs/LEDGER.md`: prediction contract v1, the v0/v1 reader, and the append-only ledger.
- `docs/ROADMAP.md`: merged history, measured production exclusions, and the approved forward plan.

## Governance and fixed rules

### Work rules

- One topic per PR, on its own branch from the latest `main`. Nothing is merged without Jesús saying so. No force-push to `main`, no direct commits.
- Each PR description (in English) lists: what changes, why, the files, the checks with their numbers and what is left for later.
- The environment is locked: dependencies change only by editing `pyproject.toml` and committing the regenerated `uv.lock` in the same PR. CI runs `uv lock --check` and `uv sync --frozen`; `UV_FROZEN=1` keeps `uv run` from re-resolving.
- No paid or quota-consuming call (The Odds API, agents) without need; prefer cached data.

### Review of every PR

- Technical review: checks above, tests for every behaviour change, a check broken once on purpose when it is new.
- Statistical review: any figure comes from a command; model changes go through the baseline gate with a confidence interval.
- Product and visual review: screenshots at 375 px and desktop in both languages when the site changes; DESIGN.md rules apply.
- NFL fan review: the "why" and the context must make sense to someone who follows the league.

### Architecture principles

- **Single source of truth.** The prediction files under `predictions/`, described by the contract v1 (`docs/CONTRACT.md`), are the only source of every published number. Reports and the site are representations of them.
- **The site only formats.** `site/build.py` must not simulate, refit or derive new figures. Allowed: formatting, the documented subtraction of printed integers (`gap_pts`), and margin and total from the printed expected points. Charts come from the stored `headline.distribution.histogram`.
- **One convention per quantity.** Margins in data are home minus away. Probabilities are the home team's. Timestamps are UTC with `Z`. The display uses Europe/Madrid on `/es/` and America/New_York (ET) on `/en/`. A market figure always names its source and is called "closing" only when it is the closing line.
- **Append-only picks.** A published snapshot is never edited. Each run writes a new snapshot with SHA-256 in `predictions/MANIFEST.json`, and git history proves the time of publication (no commit field inside the manifest). Procedure: `docs/LEDGER.md`.
- **Provenance.** Published artifacts carry `git_sha` from a clean tree (`contract.provenance(production=True)`), `data_snapshot` hashes and a `model_version` that is bumped by any model or simulator change. Local artifacts are flagged `reproducible: false`.

### Current weekly publication

`.github/workflows/weekly.yml` runs only on `main`. Three crons, plus `workflow_dispatch`:

- **Tuesday 07:00 UTC:** first snapshot of the upcoming slate.
- **Friday 22:00 UTC:** refresh after the usual Friday injury report, for games that have not kicked off. It does not guarantee a final report for Thursday, Monday, Saturday, international, or other non-Sunday games.
- **Saturday 08:00 UTC:** catch-up when the Friday run is delayed or skipped (GitHub #23). Started games stay frozen. An empty diff does not commit.

Per-game freeze: a new snapshot may be appended while any game in the week still has `kickoff_utc` in the future. Every game already at or past kickoff is copied from the latest snapshot published strictly before that kickoff. A v0 record is mapped with `contract_io.game_from_v0` into the v1 document; the historical file stays v0 on disk (GitHub #22, which closes issue #21). Once every game in the week is at or past kickoff, no option, including `--force`, writes another snapshot.

New snapshots are contract v1. `contract_io.load_week` reads v0 and v1. Legacy v0 files are not rewritten.

After the weekly commit and push, `actions/attest` writes Sigstore-backed SLSA provenance for `predictions/MANIFEST.json` and for each new snapshot file. Attestations prove those bytes and which workflow run produced them. They do not prove calibration or model validity. Procedure: `docs/LEDGER.md`.

Optional `outcome_bands` on a new v1 game (GitHub #25, `c5fea6a`) stores eleven final-margin bands and the three most likely, taken from the headline simulation: 1 to 3, 4 to 7, 8 to 14, 15 to 21, and 22 or more on each side, plus a tie. Records written with the seven-band set from GitHub #24 stay valid and are graded with the ids stored on the record. It is not a second model. Grading records which rank happened when the frozen pick carried the field. Field rules: `docs/CONTRACT.md`.

Merged history, measured exclusions and the forward plan: `docs/ROADMAP.md`.

### Official sequence

The list below is the original plan. What merged, and what comes next, is `docs/ROADMAP.md`.

1. **PR 1a:** `uv.lock`, a single Python version, contract v1 (schema, `contract.py`, tests), this governance section.
2. **PR 1b:** append-only ledger (including the five historical snapshots of `week12.json` rebuilt from git without changes), SHA-256 manifest, `verify_integrity.py`, v0/v1 reader, writer on v1, site without re-simulation.
3. **PR 2:** statistical audit in the open: 2133 vs 2141 games, model-only 64.8% vs market 66.4%, stratified 2-week block bootstrap (+ 1-week/4-week sensitivity), the ensemble margin equal to the spread, market naming, news adjustment scope, and odds data governance below.
4. **PR 3:** site and data fixes: ET on `/en/`, one sign convention per row, one market figure per page, tables at 375 px, no false "closing".
5. **PR 4:** visual system: DESIGN.md from references, three mock-ups to choose from, typographic team badges generated in code, UI icons.
6. **PR 5:** the published "why": separated component explanations, and descriptive unit match-ups from nflverse opponent-adjusted EPA per play (offense EPA and EPA allowed). The site labels them "Matchups to watch". An earlier draft of this line named NGS, PFR and FTN; those sources are not in the implementation.
7. **PR 6:** product work later split into 6a (per-game ledger and attestations), 6b (verification page, favorite-team filter, copy link) and 6c (Open Graph, SEO, opt-in analytics). The broader product proposal after weeks 13 to 18 is phase label PR7 in `docs/ROADMAP.md`, which is not a GitHub pull request number.

### Fixed rules

- The headline number is the model on its own. The market is shown only as a reference.
- The site is bilingual: Spanish at the root, English under `/en/`, with the same content.
- Everything is public: code, data outputs, reports and the method.
- No official NFL logos or derivatives of them: team badges are typographic and generated in code.
- No copying of armchairlogan, in code, text or design. It is a reference for clarity only.
- Out of scope, by decision: parlays, a Rust rewrite, and ingesting news from X.

### Odds data governance (PR 2)

The public The Odds API terms reviewed on 2026-11-26 (https://the-odds-api.com/terms-and-conditions.html) permit displaying data and derived values in user-facing websites, dashboards and analytical tools, provided the data is not the primary product being sold or redistributed. They prohibit redistribution as a standalone raw-data feed. This review is based on the publicly posted standard terms, not an account-specific legal opinion; any plan-specific agreement or source restriction takes precedence.

Public repository outputs may retain only the aggregate head-to-head Shin probability (an unweighted mean of the per-operator no-vig probabilities), its capture timestamp and the number of contributing operators. Do not publish individual prices, operator names or keys, best prices, per-operator tables, EV, or an edge computed against the market-anchored ensemble. Historical commits are not rewritten; remediation applies to current files and future outputs. Do not make paid or quota-consuming API calls for an audit.
