# Prediction ledger

This is the procedure that keeps published picks append-only. The contract itself is in [`CONTRACT.md`](CONTRACT.md).

## Snapshots

- Every run writes a new file: `predictions/<season>/week<WW>/<generated_at_utc>.json`.
- Existing snapshots are never overwritten. The v0 files `predictions/2026/week11.json` and `week12.json` stay as they were published and are never migrated.
- Re-doing a week that already has a snapshot requires `ensemblitz predict --force`.
- **No option**, including `--force`, writes a new snapshot after the week's first kickoff. Mid-week updates of remaining games are out of scope until a later PR decides otherwise.
- The HTML site and the grader read through `contract_io.load_week`. The site does not re-simulate or recompute probabilities, margins, totals or weights.

## Manifest

`predictions/MANIFEST.json` stores only a map of `path → SHA-256`. It has no `first_commit` field and does not include its own hash. The time of publication is proven by git history: `scripts/verify_integrity.py` looks up the first commit that contained those bytes (by blob, so a copy of a historical file still resolves to the original publication) and checks that it is before kickoff.

`verify_integrity.py` runs in CI and in the weekly job before the commit. It fails on a modified, deleted or substituted artifact. Adding a new week only extends the manifest; existing hashes must not change.

## Historical snapshots

The five published versions of `predictions/2026/week12.json` are stored byte-for-byte under `predictions/2026/week12/`, taken from commits `22f65ff`, `081affe`, `475a36a`, `ae9f088` and `7690ac8`. Week 11 is stored the same way from its four commits. They remain v0 on disk and are read through the v0 reader.

## Historical rectification

If a published number was wrong, do not edit the file and do not use `--force` after kickoff (it is refused). Open a PR that:

1. Explains the error, the affected games and the correction.
2. Adds a **new** snapshot under the week directory (never a rewrite). Mention the rectification in the PR and add the new file's hash to the manifest. The original snapshot stays.
3. Says whether grading should keep using the last snapshot published before kickoff (the default) or record the correction for the official record.

There is no CLI for this yet. It is a manual, reviewed PR.
