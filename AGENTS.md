# Instructions for agents

## Style and design

- Language: the site is bilingual (Spanish by default, English under `/en/`). All UI strings live in `src/ensemblitz/site/strings.py`, both languages with identical keys. Repository docs, code comments, commit messages and the README are in English. PR descriptions are written in Spanish for Jesús. Times in Europe/Madrid, Spanish uses decimal commas, °C and km/h.
- Team names are the official English names in both languages (`site/names.py`). No half-translations.
- Design: follow `DESIGN.md`. Do not change tokens, fonts or the visual direction without Jesús approving it.
- Antislop: rules in `.cursor/rules/antislop.mdc` and the MIT copy in `third_party/antislop/` (keep the `LICENSE`). No em dash in written text or in the site output.
- Never show repository paths, internal bookmaker keys or imputed figures presented as real data on the site. Never show individual bookmaker prices or an expected value: the only market figure is the consensus.
- A derived figure is computed from the same values that are displayed. The difference between two percentages on the site is the subtraction of the two printed integers (`gap_pts` in `site/build.py`); margin and total follow from the printed expected points of each team.
- The headline number is the model on its own (no market). The market is a reference. The blended ensemble stays in the data for comparison and for the record of older picks.

## Branches and pull requests

- Never touch `main` directly. Each change goes on a new branch (`feat/...`, `fix/...`) with a pull request. It is not merged until Jesús says so.
- One PR, one topic. Description in Spanish: what changes, why, and which checks were passed (with the numbers).

## Mandatory checks before calling a change done

Run all of them, in this order, and paste the result in the PR. If one fails, fix the cause; do not disable the check or widen its tolerance so it passes.

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
