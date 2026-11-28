# Prediction ledger

This is the procedure that keeps published picks append-only and per-game immutable. The contract itself is in [`CONTRACT.md`](CONTRACT.md).

## Snapshots and per-game immutability

- Every run writes a new file: `predictions/<season>/week<WW>/<YYYYMMDDTHHMMSSZ>.json` (colon-free ISO-8601 basic UTC for Windows NTFS compatibility; the `generated_at_utc` field inside the JSON remains extended ISO-8601 `YYYY-MM-DDTHH:MM:SSZ`).
- Existing snapshots are never overwritten. The v0 files `predictions/2026/week11.json` and `week12.json` stay as they were published and are never migrated.
- Re-doing a week that already has a snapshot requires `ensemblitz predict --force`.
- **Per-game kickoff freeze:** while at least one game in `(season, week)` still has `kickoff_utc > now`, a new append-only snapshot may be written. Every game in that week whose `kickoff_utc <= now` is frozen to the v1 form of its record from the latest snapshot published strictly before that game's kickoff. A v0 record is mapped with `contract_io.game_from_v0` (the historical file stays v0 on disk). A v1 record is copied unchanged.
- **Canonical game serialization contract:** per-game immutability is compared with `ledger.canonical_game_v1(game)`, which maps a v0 game through `game_from_v0` and then serializes the v1 record:
  ```python
  json.dumps(v1_game, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
  ```
  This covers every field of that v1 record (headline, probabilities, margin, ensemble, components, market, explanation, absences, context, news adjustment and metadata). Mutating any field of a started game's v1 record, or dropping a started game, fails both `ledger.write_snapshot()` (`WeekLockedError`) and `scripts/verify_integrity.py`.
- **No option**, including `--force`, writes a new snapshot once all games in the week have passed kickoff (`kickoff_utc <= now` for every game).
- **Grading:** `grade.py` selects, per game, the latest snapshot published strictly before `g["kickoff_utc"]` using `(publication_time_utc, artifact.rel)` tie-breaking and per-game `headline_kinds[game_id]`. If no snapshot was published strictly before a game's kickoff, that game is skipped (ungradable) and never falls back to a post-kickoff snapshot.
- The HTML site and the grader read through `contract_io.load_week`. The site does not re-simulate or recompute probabilities, margins, totals or weights.

## Scheduled publication cadence

`.github/workflows/weekly.yml` runs on two scheduled slots (plus `workflow_dispatch`):

- **Tuesday 07:00 UTC:** initial weekly snapshot for the upcoming slate.
- **Friday 22:00 UTC:** mid-week refresh for games whose kickoff is still in the future, freezing Thursday Night Football (and any other already-started game) to the v1 form of its pre-kickoff record.

Friday 22:00 UTC follows the usual Friday injury report for Sunday games. It does not guarantee final-report coverage for Thursday, Monday, Saturday, international, or other non-Sunday games. When no open games remain (for example in the off-season), the workflow skips the Odds API fetch and prediction run cleanly.

## Manifest

`predictions/MANIFEST.json` stores only a map of `path -> SHA-256`. It has no `first_commit` field and does not include its own hash. The time of publication is proven by git history: `scripts/verify_integrity.py` looks up the first commit that contained those bytes (by blob, so a copy of a historical file still resolves to the original publication) and verifies, across all snapshots of each `(season, week)` ordered by publication time, that every game at or past kickoff matches its pre-kickoff record in v1 space (`canonical_game_v1`).

`verify_integrity.py` runs in CI and in the weekly job before the commit. It fails on a modified, deleted, substituted or post-kickoff mutated artifact, and rejects snapshot paths containing `:` so the repository stays cloneable on Windows NTFS. Adding a new snapshot only extends the manifest; existing hashes must not change.

## GitHub Artifact Attestations

After `validate_outputs.py`, `verify_integrity.py --base-ref HEAD`, and the commit/push succeed in `.github/workflows/weekly.yml`, the workflow invokes `actions/attest` (v4, pinned by commit SHA) to generate signed SLSA build provenance attestations for **both**:

1. The finalized `predictions/MANIFEST.json`.
2. Every exact new snapshot file added to `predictions/MANIFEST.json` by that run.

Neither file is modified after attestation. Anyone can verify either artifact independently with the GitHub CLI:

```bash
gh attestation verify predictions/MANIFEST.json --owner jesusparrat
gh attestation verify predictions/<season>/week<WW>/<YYYYMMDDTHHMMSSZ>.json --owner jesusparrat
```

**Scope of attestations:** attestations prove **artifact integrity** (exact file bytes) and **workflow provenance** (which repository, commit and GitHub Actions workflow run produced those files). They do **not** prove statistical correctness, calibration, feature quality or model validity.

## Historical snapshots

The five published versions of `predictions/2026/week12.json` are stored byte-for-byte under `predictions/2026/week12/`, taken from commits `22f65ff`, `081affe`, `475a36a`, `ae9f088` and `7690ac8`. Week 11 is stored the same way from its four commits. They remain v0 on disk and are read through the v0 reader.

### One-time NTFS filename migration (PR 4.5)

The initial ledger commit stored those nine historical copies using extended ISO-8601 filenames containing `:` (for example `2026-11-17T20:45:59Z.json`), which Windows NTFS refuses to check out (`core.protectNTFS`). With explicit approval from the repository owner, PR 4.5 performed a single byte-preserving rename of those nine paths to basic ISO-8601 (`YYYYMMDDTHHMMSSZ.json`):

| Previous path | Migrated path | SHA-256 (unchanged) |
|---|---|---|
| `predictions/2026/week11/2026-11-17T20:45:59Z.json` | `predictions/2026/week11/20261117T204559Z.json` | `ce08340046c0...` |
| `predictions/2026/week11/2026-11-17T21:23:30Z-cca816c5.json` | `predictions/2026/week11/20261117T212330Z-cca816c5.json` | `cca816c53cef...` |
| `predictions/2026/week11/2026-11-17T21:23:30Z.json` | `predictions/2026/week11/20261117T212330Z.json` | `f65bcee44ad2...` |
| `predictions/2026/week11/2026-11-18T21:41:36Z.json` | `predictions/2026/week11/20261118T214136Z.json` | `2196b6016ec7...` |
| `predictions/2026/week12/2026-11-17T20:45:59Z.json` | `predictions/2026/week12/20261117T204559Z.json` | `3230d81646e2...` |
| `predictions/2026/week12/2026-11-17T21:23:30Z.json` | `predictions/2026/week12/20261117T212330Z.json` | `256a896323d1...` |
| `predictions/2026/week12/2026-11-17T22:07:00Z.json` | `predictions/2026/week12/20261117T220700Z.json` | `1d01bf9c9544...` |
| `predictions/2026/week12/2026-11-18T21:41:36Z.json` | `predictions/2026/week12/20261118T214136Z.json` | `47c7603df3d9...` |
| `predictions/2026/week12/2026-11-24T18:26:45Z.json` | `predictions/2026/week12/20261124T182645Z.json` | `b67b41eb079a...` |

No byte inside any snapshot changed, every SHA-256 in `predictions/MANIFEST.json` stayed identical, and `first_publication_utc()` still resolves each blob to its original pre-kickoff commit.

## Historical rectification

If a published number was wrong, do not edit the file and do not use `--force` after kickoff (it is refused). Open a PR that:

1. Explains the error, the affected games and the correction.
2. Adds a **new** snapshot under the week directory (never a rewrite). Mention the rectification in the PR and add the new file's hash to the manifest. The original snapshot stays.
3. Says whether grading should keep using the last snapshot published before kickoff (the default) or record the correction for the official record.

There is no CLI for this yet. It is a manual, reviewed PR.
