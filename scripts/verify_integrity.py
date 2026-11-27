"""Fail if a published prediction snapshot was modified, deleted or substituted.

Exit 0 when every artifact in predictions/MANIFEST.json matches its SHA-256, every
snapshot on disk is listed, and (when git history is available) each blob was first
committed before the kickoff of the games it contains. New weeks are added by
extending the manifest; existing hashes must not change.

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
        pub = L.first_publication_utc(path=path, root=root)
        if pub is None:
            continue  # not yet committed: weekly job verifies hashes before the commit
        if art.first_kickoff_utc and pub >= art.first_kickoff_utc:
            errors.append(
                f"{rel}: first published at {pub}, which is not before kickoff {art.first_kickoff_utc}"
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
