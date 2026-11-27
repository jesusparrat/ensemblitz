"""Fail if a published prediction snapshot was modified, deleted, substituted or mutated.

Exit 0 when every artifact in predictions/MANIFEST.json matches its SHA-256, every
snapshot on disk is listed, and across all snapshots of each ``(season, week)`` ordered
by publication time, every game past kickoff preserves its exact canonical JSON record
(``ledger.canonical_game_json``) from the latest snapshot published strictly before that
game's kickoff. New weeks or mid-week updates are added by extending the manifest;
existing hashes must not change.

The working-tree manifest is also compared against the artifacts map in ``--base-ref``
(default ``HEAD``). The manifest may only grow: every entry present in the base ref
must still exist and must be completely unchanged. An unresolvable ref is an error;
if the base ref has no manifest, the base map is empty (bootstrap).

Usage: python scripts/verify_integrity.py [--root PATH] [--base-ref REF]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ensemblitz import contract as K  # noqa: E402
from ensemblitz import ledger as L  # noqa: E402


def verify(root: Path, base_ref: str = "HEAD") -> list[str]:
    try:
        base_entries = L.manifest_entries_at_ref(root, base_ref)
    except L.LedgerError as exc:
        return [str(exc)]

    errors: list[str] = []
    manifest_file = L.manifest_path(root)
    if not manifest_file.exists():
        return [f"{L.MANIFEST_REL}: missing"]
    try:
        manifest = L.load_manifest(root)
    except L.LedgerError as exc:
        return [str(exc)]

    if L.MANIFEST_REL in manifest or manifest_file.name in manifest:
        errors.append(f"{L.MANIFEST_REL}: the manifest must not list its own hash")

    raw = json.loads(manifest_file.read_text())
    if "first_commit" in raw:
        errors.append(f"{L.MANIFEST_REL}: first_commit is forbidden")

    current_entries = raw.get("artifacts")
    if isinstance(current_entries, dict):
        errors.extend(L.append_only_violations(current_entries, base_entries))

    paths = {p.relative_to(root).as_posix(): p for p in L.iter_snapshot_paths(root)}
    for rel, digest in manifest.items():
        if ":" in rel:
            errors.append(f"{rel}: snapshot path contains ':' (incompatible with Windows NTFS)")
        path = paths.get(rel) or (root / rel)
        if not path.exists():
            errors.append(f"{rel}: listed in the manifest but missing on disk")
            continue
        actual = K.sha256_file(path)
        if actual != digest:
            errors.append(f"{rel}: sha256 mismatch (manifest {digest[:12]}…, file {actual[:12]}…)")

    for rel in sorted(set(paths) - set(manifest)):
        errors.append(f"{rel}: present on disk but not in the manifest")

    for path in L.unexpected_prediction_files(root):
        errors.append(f"{path.relative_to(root).as_posix()}: unexpected file under predictions/")

    # Structural checks only for files that still match their hash (or are unlisted).
    ok_paths = []
    for rel, path in paths.items():
        if rel in manifest and K.sha256_file(path) != manifest[rel]:
            continue
        ok_paths.append(path)

    # Collect valid snapshots per (season, week) for cross-snapshot per-game immutability.
    by_week: dict[tuple[int, int], list[tuple[str, str, dict, bool]]] = {}
    for path in ok_paths:
        rel = path.relative_to(root).as_posix()
        try:
            doc = json.loads(path.read_text())
            version = K.detect_version(doc)
        except (K.ContractError, json.JSONDecodeError, OSError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        if version == K.SCHEMA_VERSION:
            errors.extend(f"{rel}: {e}" for e in K.validate_week(doc))
        try:
            art = L.describe(path, root)
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        git_pub = L.first_publication_utc(path=path, root=root)
        pub = git_pub or art.generated_at_utc
        by_week.setdefault((art.season, art.week), []).append((pub, rel, doc, git_pub is not None))

    for (_season, _week), entries in sorted(by_week.items()):
        entries.sort(key=lambda item: (L.parse_utc(item[0]), item[1]))
        # game_id -> (canonical_json, kickoff_utc, source_rel)
        frozen: dict[str, tuple[str, str, str]] = {}
        for pub, rel, doc, _in_git in entries:
            pub_dt = L.parse_utc(pub)
            games = doc.get("games") or []
            seen_ids: set[str] = set()
            has_open_game = False

            for g in games:
                gid = g.get("game_id")
                kick = g.get("kickoff_utc")
                if not gid or not kick:
                    continue
                seen_ids.add(gid)
                kick_dt = L.parse_utc(kick)
                canon = L.canonical_game_json(g)
                if pub_dt < kick_dt:
                    has_open_game = True
                    frozen[gid] = (canon, kick, rel)
                else:
                    if gid not in frozen:
                        errors.append(
                            f"{rel}: game {gid} published at {pub}, which is not before "
                            f"kickoff {kick} (no prior pre-kickoff snapshot)"
                        )
                    else:
                        expected_canon, _kick_str, prev_rel = frozen[gid]
                        if canon != expected_canon:
                            errors.append(
                                f"{rel}: started game {gid} (kickoff {kick}) mutated after "
                                f"kickoff; canonical record differs from {prev_rel}"
                            )

            for gid, (_expected_canon, kick_str, prev_rel) in sorted(frozen.items()):
                if L.parse_utc(kick_str) <= pub_dt and gid not in seen_ids:
                    errors.append(
                        f"{rel}: started game {gid} (kickoff {kick_str}) dropped after "
                        f"kickoff; must preserve canonical record from {prev_rel}"
                    )

            if games and not has_open_game:
                errors.append(
                    f"{rel}: published at {pub}, after all games in the week had passed kickoff"
                )
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument(
        "--base-ref",
        default="HEAD",
        help="Git ref whose manifest is the append-only baseline (default: HEAD).",
    )
    args = p.parse_args()
    root = args.root.resolve()
    errors = verify(root, base_ref=args.base_ref)
    for e in errors:
        print("FAIL", e)
    print("verify_integrity:", "FAILED" if errors else "ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
