# Shared state handoff

Short, factual status of `main`. This is the shared state entry point for agents. Update it in every functional PR before merge. Automated `weekly.yml` commits never modify this file. Keep it to 40 lines or fewer. Never write merge SHAs, author attribution, or self-references to the PR being merged; refer to PRs by number and title.

## Last functional merge

GitHub **#25**, `fix: split the open margin tail into 15-21 and 22+`. New snapshots use eleven final-margin bands.

## Last weekly publication

`b80f41e` (2026-11-28T12:50:27Z), automated `weekly.yml` commit: `chore: weekly predictions and results [skip ci]`. Week 12 snapshot `predictions/2026/week12/20261128T124938Z.json`.

## Active phase

**P0. Week-12 close audit (read-only).** Pre-close checks passed on 2026-11-28. Still pending:

- Week-12 grading of the Sunday and Monday games, including the outcome-band rank. Tuesday 2026-12-01.
- Saturday catch-up cron (GitHub #23) proven not to create empty commits. First fire Saturday 2026-12-05 (week 13).

## Next authorized phases

- **P2a. Two-level discrepancy warning** (UI, Cursor) and **P2b.1. `kf_params` provenance audit** (Antigravity) may run in parallel on disjoint files after the Tuesday 2026-12-01 week-12 grading passes. They do not wait for the Saturday 2026-12-05 cron check, which closes P0 in parallel and blocks neither.
- **P2b.2. Point-in-time capture contract** starts clean from week 14.
- Then **P3. Player valuation, QB only first**, with the log-loss gate (upper bound of the 95% CI of the paired log-loss difference strictly below 0).
- Then **P4. Product proposal after weeks 13 to 18** (phase label PR7).

## Token

`ENSEMBLITZ_GITHUB_TOKEN` is a fine-grained PAT scoped to this repo. It expires 2027-02-26. Renew it before then. It replaced the token that was due to expire on 2026-12-17.

Last updated: 2026-11-28
