# Roadmap

Record of what is on `main`, what stays out of production, and the approved work after that. Phase labels such as PR 1a or PR7 are planning names. GitHub pull request numbers are a different sequence. This file does not change the model, the site, or any published probability.

Checked against `git log origin/main` on 2026-11-28, with `HEAD` at `b80f41e`. Figures below are copied from the cited file in this repository. A figure with no file here is marked **reported**.

## Tip of main vs the last functional change

`HEAD` (`b80f41e`, 2026-11-28) is an automated weekly commit: `chore: weekly predictions and results [skip ci]`.

The last functional change under it is `c5fea6a` (2026-11-28), squash-merged as GitHub **#25**: `fix: split the open margin tail into 15-21 and 22+ (#25)`.

Earlier weekly commits with the same subject are `c62262b` (2026-11-28), directly under #25, and `3cd857e` (2026-11-28), between GitHub **#22** (`8b6f2f3`) and GitHub **#23** (`95f0ad9`). Weekly commits refresh `predictions/` and results. They are not feature merges.

## Merged work

Dates are the committer dates of the commits on `main`. Pull requests **#9** through **#20** are merge commits. **#22**, **#23**, **#24** and **#25** are squash commits on `main`. Issue **#21** is the bug **#22** closes (`Fixes #21` in `8b6f2f3`). It is not a merged pull request in this log.

| Plan label | GitHub | Commit on `main` | Date | What the commit records |
|---|---|---|---|---|
| PR 1a | [#9](https://github.com/jesusparrat/ensemblitz/pull/9) | `47b1148` | 2026-11-25 | `uv.lock`, Python 3.12, contract v1, governance in `AGENTS.md` |
| PR 1b | [#10](https://github.com/jesusparrat/ensemblitz/pull/10) | `d19d692` | 2026-11-25 | Append-only ledger, SHA-256 manifest, v0/v1 reader, writer on v1 |
| PR 2 | [#11](https://github.com/jesusparrat/ensemblitz/pull/11) | `c908c27` | 2026-11-27 | Statistical audit, stratified block bootstrap, odds governance |
| PR 3 | [#12](https://github.com/jesusparrat/ensemblitz/pull/12) | `97aa1bb` | 2026-11-27 | ET on `/en/`, margin signs, one market figure, no false "closing", 375 px tables |
| PR 4 | [#13](https://github.com/jesusparrat/ensemblitz/pull/13) | `4b2d570` | 2026-11-27 | Visual identity: typography, cool palette, full-bleed hero, CSS/SVG guards |
| PR 4.5 | [#14](https://github.com/jesusparrat/ensemblitz/pull/14) | `5b0f6ee` | 2026-11-27 | NTFS-safe ledger filenames, v1 dry-run hardening, weekly failure alert. The merge body names this PR 4.5 |
| PR 5 | [#15](https://github.com/jesusparrat/ensemblitz/pull/15) | `f9e7015` | 2026-11-27 | Separated explanations, descriptive nflverse EPA match-ups, >=10 pp signal |
| PR 5b | [#16](https://github.com/jesusparrat/ensemblitz/pull/16) | `abce1f3` | 2026-11-27 | Walk-forward calibration experiment for heavy favourites. Not wired |
| PR 6a | [#17](https://github.com/jesusparrat/ensemblitz/pull/17) | `2c6b5fc` | 2026-11-27 | Per-game immutability, grading fix, Sigstore attestations, PBP cache, Node 24 actions |
| PR 6b | [#19](https://github.com/jesusparrat/ensemblitz/pull/19) | `790f2d8` | 2026-11-27 | Verification page, favorite-team filter, copy link. Merged before #18 |
| PR 6c | [#18](https://github.com/jesusparrat/ensemblitz/pull/18) | `18161b4` | 2026-11-27 | Open Graph cards, SEO metadata, sitemap/robots, opt-in GoatCounter |
| (deploy fix, not a phase) | [#20](https://github.com/jesusparrat/ensemblitz/pull/20) | `bfbe088` | 2026-11-27 | Matplotlib moved to runtime dependencies for Pages |
| (v0 freeze mapping) | [#22](https://github.com/jesusparrat/ensemblitz/pull/22) | `8b6f2f3` | 2026-11-28 | Map frozen v0 games with `game_from_v0` before writing a v1 snapshot. Historical files stay v0 |
| (Saturday catch-up) | [#23](https://github.com/jesusparrat/ensemblitz/pull/23) | `95f0ad9` | 2026-11-28 | Saturday 08:00 UTC cron on the weekly workflow |
| (margin bands) | [#24](https://github.com/jesusparrat/ensemblitz/pull/24) | `ee87af3` | 2026-11-28 | Optional `outcome_bands` from the headline simulation: seven bands, graded and shown on the game card |
| (finer margin bands) | [#25](https://github.com/jesusparrat/ensemblitz/pull/25) | `c5fea6a` | 2026-11-28 | New snapshots use eleven bands (1-3, 4-7, 8-14, 15-21, 22+ on each side, plus a tie). Seven-band records still validate and grade on their own edges |

There is no GitHub pull request **#21** in `git log origin/main`. The only `#21` hit is `Fixes #21` inside the **#22** commit.

## Production exclusions (measured)

Wiring rule, from `AGENTS.md`: a change is wired only when the paired 95% confidence interval of log loss against the variant without the change lies strictly below zero. A negative difference means the candidate has lower log loss than the reference. These three stay out.

| Candidate | Paired log-loss difference | 95% CI | Reference | Source in this repo | Decision |
|---|---|---|---|---|---|
| Injuries (with minus without) | −0.0028 | [−0.0056, +0.0000] | model margin without injuries | `reports/PHASE1.md`, principal row | Not wired. The interval touches zero |
| `mo_cap1` (`sum(w) <= 1`) minus `model_only` | −0.0007 | [−0.00190, +0.00052] | `model_only` | `docs/audit/pr5b-calibration-experiment.md`, 2-week block row | Not wired. The interval crosses zero. PR 5b |
| Play-by-play simulator minus model-only | +0.0130 | [+0.0046, +0.0214] | model-only on the same 2119 games | `reports/PBP_SIM.md` (10000 paired resamples, seed 202603) | Not eligible. The interval is entirely above zero |

The injuries line in `reports/PHASE1.md` is the Spanish principal comparison ("Con lesiones menos sin lesiones"): log loss −0,0028, IC 95 % [−0,0056; +0,0000]. The `mo_cap1` point estimate in that audit's summary table is printed as `[-0.0019, +0.0005]`; the 2-week sensitivity row is the unrounded interval in the table above. `reports/PBP_SIM.md` also states the simulator failed the win-prob log-loss gate (0.6465, band "below 0.6344") on the 2127-game run; the paired interval cited here is the 2119-game comparison in that same file.

## Permanent exclusions

Decided, and unchanged by later results:

- Parlays.
- A Rust rewrite.
- Ingesting news from X.

## Approved forward plan

These items are the plan. They are not commits on `main` unless the merged table above already lists them. `git log origin/main` has no `kf_params` provenance audit commit and no week-14 capture schema commit. The finer margin bands shipped in **#25**.

**P0. Week-12 close audit (read-only).** Read the published week-12 snapshots and grades. Do not rewrite a frozen pick.

Pre-close checks passed on 2026-11-28: main state, per-game freeze hashes, MANIFEST continuity from `d19d692`, Sigstore attestations, histograms, and band coverage.

Still PENDING until executed:

- (a) Week-12 grading of the Sunday and Monday games, including the outcome-band rank. Scheduled Tuesday 2026-12-01.
- (b) Saturday catch-up cron (GitHub #23) proven not to create empty commits. First fire Saturday 2026-12-05 (week 13).

**P1. This documentation pull request.** Sync `AGENTS.md` and `docs/CONTRACT.md` with `main`, and add this file. No code, tests, templates, workflows, `predictions/` or `reports/` changes.

**Margin bands.** Merged as GitHub **#25** (`c5fea6a`). New snapshots use eleven bands. Records written with the seven bands from **#24** stay valid and are graded on those edges.

**P2a** and **P2b.1** start after the Tuesday 2026-12-01 week-12 grading close (P0-a). The Saturday 2026-12-05 cron check (P0-b) runs in parallel and does not block them. **P2b.2** still starts clean from week 14.

**P2a. Two-level discrepancy warning.** Editorial only, for a printed gap of 10 percentage points or more. It does not change any probability. Historical backing, verified in `src/ensemblitz/explain.py` (`DISCREPANCY_10PP_HISTORY`) and the English method string in `src/ensemblitz/site/strings.py`: 506 of 2133 decided 2018-2025 games, model-only accuracy 59.9%, market accuracy 65.8%, accuracy gap −5.9 percentage points, 95% CI [−11.5, −0.4]. The code comment records a stratified 2-week block bootstrap (10000 reps, seed 20260, 72 blocks). There is no separate report file for this row.

**P2b.1. `kf_params` provenance audit.** Check that published Kalman parameters are point-in-time. No result is claimed here.

**P2b.2. Point-in-time capture contract, from week 14.** One envelope for raw captures. Common fields: `schema_version`, `record_type`, `source`, `published_at_utc` (nullable), `captured_at_utc`, `game_id`, `team`, `raw_sha256`, `kickoff_utc`, `cutoff_utc`. Typed payloads for injuries, QB starter and weather. Injury and roster payloads include `gsis_id`, `position`, `injury_status`, `practice_status` and `depth_chart_order`. Raw dumps are GitHub Actions artifacts. They are not committed under git. This shape is the approved contract for that work. It is not a schema file on `main` today.

**P3. Player valuation, QB only first.** A preregistered hypotheses document comes before any fit. Gate: the upper bound of the 95% CI of the paired log-loss difference is strictly below 0. The same rule as injuries and `mo_cap1`.

**P4. Product proposal after weeks 13 to 18.** The phase label for that proposal is **PR7**. PR7 is not a GitHub pull request number. GitHub **#7** is the earlier web v2 merge (`aff600c`, 2026-11-18) and is unrelated.

## Collaboration model

Jesús is the sole decision maker and the only person who merges to `main`.

- Neon orchestrates the roadmap and writes one closed prompt per phase.
- Astra audits commits, workflows and statistics independently.
- Grok Bot and Cursor do fast execution near the repo (P0 checks, P2a UI).
- Antigravity runs self-contained branches with heavy tests (P2b.1, P2b.2, P3 experiments).

Rules:

- One executor per branch. Parallel work only when the branches touch disjoint files.
- The repo is the source of truth: `AGENTS.md`, `docs/ROADMAP.md`, and `main`.
- One cross-review round per phase. A blocker needs concrete evidence: a `file:line` citation, a test, or data.
