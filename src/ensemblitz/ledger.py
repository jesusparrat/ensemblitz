"""Append-only prediction ledger: immutable snapshots, SHA-256 manifest, kickoff lock.

Every production run writes a new file. Existing snapshots are never overwritten.
Re-doing a week requires ``--force``. No option writes a new snapshot after the week's
first kickoff; historical corrections follow the procedure in ``docs/LEDGER.md``.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ensemblitz import config as C
from ensemblitz import contract as K

MANIFEST_NAME = "MANIFEST.json"
MANIFEST_REL = f"predictions/{MANIFEST_NAME}"
# Filenames like 2026-11-24T18:26:45Z.json or, on a generated_at collision, with a hash suffix.
SNAPSHOT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)(?:-([0-9a-f]{8}))?\.json$")
# Commits that published predictions/2026/week12.json, in order, as approved for this PR.
WEEK12_HISTORY = ("22f65ff", "081affe", "475a36a", "ae9f088", "7690ac8")
# The same four commits also published week 11 (week 11 was not rewritten in 7690ac8).
WEEK11_HISTORY = ("22f65ff", "081affe", "475a36a", "ae9f088")


class LedgerError(RuntimeError):
    """A ledger operation was refused or a snapshot could not be located."""


class SnapshotExistsError(LedgerError):
    """A week already has a snapshot and ``force`` was not set."""


class WeekLockedError(LedgerError):
    """The week's first kickoff has passed; no new snapshot is allowed."""


@dataclass(frozen=True)
class Artifact:
    path: Path
    rel: str
    season: int
    week: int
    sha256: str
    generated_at_utc: str
    first_kickoff_utc: str
    n_games: int


def predictions_root(root: Path | None = None) -> Path:
    return (root or C.ROOT) / "predictions"


def manifest_path(root: Path | None = None) -> Path:
    return predictions_root(root) / MANIFEST_NAME


def legacy_week_path(season: int, week: int, root: Path | None = None) -> Path:
    """The v0 published file ``predictions/<season>/weekWW.json``, never rewritten."""
    return predictions_root(root) / str(season) / f"week{week:02d}.json"


def week_dir(season: int, week: int, root: Path | None = None) -> Path:
    return predictions_root(root) / str(season) / f"week{week:02d}"


def snapshot_filename(generated_at_utc: str, digest: str, existing: set[str]) -> str:
    """Unique filename for a snapshot. The hash suffix is used only on collision."""
    base = f"{generated_at_utc}.json"
    if base not in existing:
        return base
    return f"{generated_at_utc}-{digest[:8]}.json"


def iter_snapshot_paths(root: Path | None = None) -> list[Path]:
    """Every prediction JSON: legacy weekXX.json and snapshot files under weekXX/."""
    pred = predictions_root(root)
    if not pred.exists():
        return []
    out: list[Path] = []
    for p in pred.rglob("*.json"):
        if p.name == MANIFEST_NAME:
            continue
        rel = p.relative_to(pred)
        parts = rel.parts
        if len(parts) == 2 and re.fullmatch(r"week\d{2}\.json", parts[1]):
            out.append(p)
            continue
        if (
            len(parts) == 3
            and re.fullmatch(r"week\d{2}", parts[1])
            and SNAPSHOT_NAME.match(parts[2])
        ):
            out.append(p)
            continue
        # Ignore anything else (pointers, notes). Integrity treats unexpected
        # JSON under predictions/ as an error separately.
    return sorted(out)


def unexpected_prediction_files(root: Path | None = None) -> list[Path]:
    """JSON files under predictions/ that are not the manifest and not a snapshot."""
    pred = predictions_root(root)
    if not pred.exists():
        return []
    known = set(iter_snapshot_paths(root)) | {manifest_path(root)}
    return sorted(p for p in pred.rglob("*.json") if p not in known)


def _read_header(path: Path) -> tuple[int, int, str, str, int]:
    doc = json.loads(path.read_text())
    games = doc.get("games") or []
    generated = doc.get("generated_at_utc") or doc.get("generated_at")
    kicks = [g["kickoff_utc"] for g in games if g.get("kickoff_utc")]
    first = min(kicks) if kicks else generated
    return int(doc["season"]), int(doc["week"]), generated, first, len(games)


def describe(path: Path, root: Path | None = None) -> Artifact:
    root = (root or C.ROOT).resolve()
    path = path.resolve()
    season, week, generated, first, n = _read_header(path)
    rel = path.relative_to(root).as_posix()
    return Artifact(path, rel, season, week, K.sha256_file(path), generated, first, n)


def iter_artifacts(root: Path | None = None) -> list[Artifact]:
    root = (root or C.ROOT).resolve()
    return [describe(p, root) for p in iter_snapshot_paths(root)]


def artifacts_for_week(season: int, week: int, root: Path | None = None) -> list[Artifact]:
    return [a for a in iter_artifacts(root) if a.season == season and a.week == week]


def latest_artifact(season: int, week: int, root: Path | None = None) -> Artifact | None:
    """The current published snapshot for a week (latest generated_at, then path)."""
    arts = artifacts_for_week(season, week, root)
    if not arts:
        return None
    return max(arts, key=lambda a: (a.generated_at_utc, a.rel))


def iter_latest(root: Path | None = None) -> list[Artifact]:
    latest: dict[tuple[int, int], Artifact] = {}
    for a in iter_artifacts(root):
        key = (a.season, a.week)
        cur = latest.get(key)
        if cur is None or (a.generated_at_utc, a.rel) > (cur.generated_at_utc, cur.rel):
            latest[key] = a
    return [latest[k] for k in sorted(latest)]


def first_kickoff_utc(
    season: int, week: int, root: Path | None = None, games: list[dict] | None = None
) -> str | None:
    kicks = []
    if games:
        kicks.extend(g["kickoff_utc"] for g in games if g.get("kickoff_utc"))
    for a in artifacts_for_week(season, week, root):
        kicks.append(a.first_kickoff_utc)
    return min(kicks) if kicks else None


def _parse_utc(stamp: str) -> datetime:
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    return datetime.fromisoformat(stamp).astimezone(UTC)


def week_is_locked(
    season: int,
    week: int,
    now: datetime | None = None,
    root: Path | None = None,
    games: list[dict] | None = None,
) -> bool:
    first = first_kickoff_utc(season, week, root, games)
    if first is None:
        return False
    now = now or datetime.now(UTC)
    return _parse_utc(first) <= now.astimezone(UTC)


def load_manifest(root: Path | None = None) -> dict[str, str]:
    """Path → SHA-256. The manifest does not list itself and has no commit field."""
    path = manifest_path(root)
    if not path.exists():
        return {}
    doc = json.loads(path.read_text())
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, dict):
        raise LedgerError(f"{MANIFEST_REL}: missing artifacts map")
    if "first_commit" in doc or any("first_commit" in k for k in artifacts):
        raise LedgerError(f"{MANIFEST_REL}: first_commit is forbidden")
    return {str(k): str(v) for k, v in artifacts.items()}


def write_manifest(artifacts: dict[str, str], root: Path | None = None) -> Path:
    """Write the manifest with only the SHA-256 of each artifact, sorted by path."""
    path = manifest_path(root)
    if MANIFEST_REL in artifacts or path.name in artifacts:
        raise LedgerError("the manifest must not include its own hash")
    for digest in artifacts.values():
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise LedgerError(f"invalid sha256 in manifest: {digest!r}")
    body = {"artifacts": dict(sorted(artifacts.items()))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1) + "\n")
    return path


def refresh_manifest(root: Path | None = None) -> dict[str, str]:
    """Rebuild the manifest from the snapshots currently on disk (all of them)."""
    root = (root or C.ROOT).resolve()
    artifacts = {a.rel: a.sha256 for a in iter_artifacts(root)}
    write_manifest(artifacts, root)
    return artifacts


def add_to_manifest(rel: str, digest: str, root: Path | None = None) -> dict[str, str]:
    arts = load_manifest(root)
    arts[rel] = digest
    write_manifest(arts, root)
    return arts


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=False,
    )


def git_blob_sha(path: Path, root: Path | None = None) -> str:
    proc = _git(["hash-object", str(path)], cwd=(root or C.ROOT).resolve())
    return proc.stdout.decode().strip()


def first_publication_utc(
    digest: str | None = None, path: Path | None = None, root: Path | None = None
) -> str | None:
    """Committer time of the first git commit that contained this file's bytes.

    Looked up by git blob (so a copy of a historical week12.json in the ledger
    folder still resolves to the original publication, not this PR). Returns
    None when the blob is not in the repository (an uncommitted new snapshot).
    """
    root = (root or C.ROOT).resolve()
    if path is None:
        return None
    blob = git_blob_sha(path, root)
    proc = _git(
        ["log", "--all", "--reverse", "--pretty=format:%cI", "--find-object", blob],
        cwd=root,
        check=False,
    )
    if proc.returncode != 0:
        return None
    lines = [ln.strip() for ln in proc.stdout.decode().splitlines() if ln.strip()]
    if not lines:
        return None
    # %cI is ISO-8601 with offset; normalise to Z.
    return _parse_utc(lines[0]).strftime("%Y-%m-%dT%H:%M:%SZ")


def publication_time_utc(artifact: Artifact, root: Path | None = None) -> str:
    """Git first-seen time of the bytes, falling back to the document's generated_at."""
    found = first_publication_utc(path=artifact.path, root=root)
    return found or artifact.generated_at_utc


def write_snapshot(
    doc: dict,
    *,
    root: Path | None = None,
    force: bool = False,
    now: datetime | None = None,
) -> Path:
    """Write a new immutable snapshot and add it to the manifest. Never overwrites.

    Refuses if the week already has a snapshot and ``force`` is false, and refuses
    unconditionally once the week's first kickoff has passed.
    """
    root = (root or C.ROOT).resolve()
    season, week = int(doc["season"]), int(doc["week"])
    games = doc.get("games") or []
    now = now or datetime.now(UTC)
    if week_is_locked(season, week, now=now, root=root, games=games):
        first = first_kickoff_utc(season, week, root, games)
        raise WeekLockedError(
            f"{season} week {week} is locked: first kickoff {first} has passed. "
            "A historical correction follows docs/LEDGER.md; --force cannot unlock it."
        )
    existing = artifacts_for_week(season, week, root)
    if existing and not force:
        raise SnapshotExistsError(
            f"{season} week {week} already has {len(existing)} snapshot(s). "
            "Pass --force to write a new one (only before the first kickoff)."
        )
    generated = doc["generated_at_utc"]
    payload = json.dumps(doc, indent=1) + "\n"
    digest = __import__("hashlib").sha256(payload.encode()).hexdigest()
    names = {p.name for p in week_dir(season, week, root).glob("*.json")}
    name = snapshot_filename(generated, digest, names)
    dest = week_dir(season, week, root) / name
    if dest.exists():
        raise SnapshotExistsError(f"refusing to overwrite {dest.relative_to(root)}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(payload)
    # Confirm we wrote exactly the bytes we hashed.
    if K.sha256_file(dest) != digest:
        dest.unlink()
        raise LedgerError("snapshot hash changed at write time")
    add_to_manifest(dest.relative_to(root).as_posix(), digest, root)
    return dest


def _cat_blob(repo: Path, rev: str, rel: str) -> bytes:
    blob = _git(["rev-parse", f"{rev}:{rel}"], cwd=repo).stdout.decode().strip()
    return _git(["cat-file", "-p", blob], cwd=repo).stdout


def rebuild_historical(root: Path | None = None, repo: Path | None = None) -> list[Path]:
    """Copy the approved historical week 11 and week 12 snapshots, byte for byte.

    Existing legacy ``weekXX.json`` files are left untouched. The current content of
    each is also stored under the week directory so all five week-12 versions (and
    the four week-11 versions) live in the ledger.
    """
    root = (root or C.ROOT).resolve()
    repo = (repo or root).resolve()
    written: list[Path] = []
    plans = (
        (2026, 12, WEEK12_HISTORY, "predictions/2026/week12.json"),
        (2026, 11, WEEK11_HISTORY, "predictions/2026/week11.json"),
    )
    for season, week, commits, rel in plans:
        directory = week_dir(season, week, root)
        directory.mkdir(parents=True, exist_ok=True)
        names: set[str] = {p.name for p in directory.glob("*.json")}
        for rev in commits:
            raw = _cat_blob(repo, rev, rel)
            header = json.loads(raw)
            generated = header["generated_at"]
            digest = __import__("hashlib").sha256(raw).hexdigest()
            name = snapshot_filename(generated, digest, names)
            dest = directory / name
            if dest.exists():
                if dest.read_bytes() != raw:
                    raise LedgerError(
                        f"{dest.relative_to(root)} already exists with different bytes"
                    )
            else:
                dest.write_bytes(raw)
            if dest.read_bytes() != raw:
                raise LedgerError(f"{dest.relative_to(root)} is not byte-identical to {rev}:{rel}")
            names.add(dest.name)
            written.append(dest)
    refresh_manifest(root)
    return written


__all__ = [
    "MANIFEST_REL",
    "WEEK11_HISTORY",
    "WEEK12_HISTORY",
    "Artifact",
    "LedgerError",
    "SnapshotExistsError",
    "WeekLockedError",
    "add_to_manifest",
    "artifacts_for_week",
    "describe",
    "first_kickoff_utc",
    "first_publication_utc",
    "iter_artifacts",
    "iter_latest",
    "iter_snapshot_paths",
    "latest_artifact",
    "legacy_week_path",
    "load_manifest",
    "manifest_path",
    "publication_time_utc",
    "rebuild_historical",
    "refresh_manifest",
    "unexpected_prediction_files",
    "week_dir",
    "week_is_locked",
    "write_manifest",
    "write_snapshot",
]
