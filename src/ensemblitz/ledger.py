"""Append-only prediction ledger: immutable snapshots, SHA-256 manifest, per-game kickoff lock.

Every production run writes a new file. Existing snapshots are never overwritten.
Re-doing a week requires ``--force``. While any game in a week has ``kickoff_utc > now``,
a new append-only snapshot may be written, with every game at or past kickoff
(``kickoff_utc <= now``) frozen to its exact canonical JSON record from the latest
snapshot published strictly before that game's kickoff. Once all games in the week have
passed kickoff, no option writes a new snapshot; historical corrections follow the
procedure in ``docs/LEDGER.md``.
"""

from __future__ import annotations

import copy
import hashlib
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
# Filenames use colon-free ISO-8601 basic UTC (20261124T182645Z.json) for NTFS compatibility;
# the regex also recognises the legacy extended form so historical references stay readable.
SNAPSHOT_NAME = re.compile(
    r"^(?:\d{8}T\d{6}Z|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)(?:-([0-9a-f]{8}))?\.json$"
)
# Commits that published predictions/2026/week12.json, in order, as approved for this PR.
WEEK12_HISTORY = ("22f65ff", "081affe", "475a36a", "ae9f088", "7690ac8")
# The same four commits also published week 11 (week 11 was not rewritten in 7690ac8).
WEEK11_HISTORY = ("22f65ff", "081affe", "475a36a", "ae9f088")
# Approved one-time NTFS filename migration (documented in docs/LEDGER.md).
# Each entry maps the historical colon path to its byte-identical colon-free path.
LEGACY_NTFS_RENAMES: dict[str, str] = {
    "predictions/2026/week11/2026-11-17T20:45:59Z.json": (
        "predictions/2026/week11/20261117T204559Z.json"
    ),
    "predictions/2026/week11/2026-11-17T21:23:30Z-cca816c5.json": (
        "predictions/2026/week11/20261117T212330Z-cca816c5.json"
    ),
    "predictions/2026/week11/2026-11-17T21:23:30Z.json": (
        "predictions/2026/week11/20261117T212330Z.json"
    ),
    "predictions/2026/week11/2026-11-18T21:41:36Z.json": (
        "predictions/2026/week11/20261118T214136Z.json"
    ),
    "predictions/2026/week12/2026-11-17T20:45:59Z.json": (
        "predictions/2026/week12/20261117T204559Z.json"
    ),
    "predictions/2026/week12/2026-11-17T21:23:30Z.json": (
        "predictions/2026/week12/20261117T212330Z.json"
    ),
    "predictions/2026/week12/2026-11-17T22:07:00Z.json": (
        "predictions/2026/week12/20261117T220700Z.json"
    ),
    "predictions/2026/week12/2026-11-18T21:41:36Z.json": (
        "predictions/2026/week12/20261118T214136Z.json"
    ),
    "predictions/2026/week12/2026-11-24T18:26:45Z.json": (
        "predictions/2026/week12/20261124T182645Z.json"
    ),
}


class LedgerError(RuntimeError):
    """A ledger operation was refused or a snapshot could not be located."""


class SnapshotExistsError(LedgerError):
    """A week already has a snapshot and ``force`` was not set."""


class WeekLockedError(LedgerError):
    """All games in the week have passed kickoff, or a started game was mutated."""


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
    last_kickoff_utc: str = ""


def canonical_game_json(game: dict) -> str:
    """Canonical UTF-8 JSON serialization of one game record covering every game-level field.

    Per-game immutability across snapshots is defined strictly over this canonical JSON
    string (sorted keys, compact separators, ``ensure_ascii=False``), covering headline,
    probabilities, margin, pick, market, explanation, absences, context and metadata.
    Never call parsed-dict equality "byte-for-byte".
    """
    return json.dumps(game, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
    """Unique colon-free filename for a snapshot (ISO-8601 basic UTC, NTFS-safe).

    The hash suffix is used only on a timestamp collision. The ``generated_at_utc``
    field inside the JSON remains ISO-8601 extended (with colons).
    """
    stamp = _parse_utc(generated_at_utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{stamp}.json"
    if base not in existing:
        return base
    return f"{stamp}-{digest[:8]}.json"


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


def _read_header(path: Path) -> tuple[int, int, str, str, str, int]:
    doc = json.loads(path.read_text())
    games = doc.get("games") or []
    generated = doc.get("generated_at_utc") or doc.get("generated_at")
    kicks = [g["kickoff_utc"] for g in games if g.get("kickoff_utc")]
    first = min(kicks, key=_parse_utc) if kicks else generated
    last = max(kicks, key=_parse_utc) if kicks else generated
    return int(doc["season"]), int(doc["week"]), generated, first, last, len(games)


def describe(path: Path, root: Path | None = None) -> Artifact:
    root = (root or C.ROOT).resolve()
    path = path.resolve()
    season, week, generated, first, last, n = _read_header(path)
    rel = path.relative_to(root).as_posix()
    return Artifact(path, rel, season, week, K.sha256_file(path), generated, first, n, last)


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
        if a.first_kickoff_utc:
            kicks.append(a.first_kickoff_utc)
    return min(kicks, key=_parse_utc) if kicks else None


def last_kickoff_utc(
    season: int, week: int, root: Path | None = None, games: list[dict] | None = None
) -> str | None:
    kicks = []
    if games:
        kicks.extend(g["kickoff_utc"] for g in games if g.get("kickoff_utc"))
    for a in artifacts_for_week(season, week, root):
        last = a.last_kickoff_utc or a.first_kickoff_utc
        if last:
            kicks.append(last)
    return max(kicks, key=_parse_utc) if kicks else None


def _parse_utc(stamp: str) -> datetime:
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    return datetime.fromisoformat(stamp).astimezone(UTC)


parse_utc = _parse_utc


def week_is_locked(
    season: int,
    week: int,
    now: datetime | None = None,
    root: Path | None = None,
    games: list[dict] | None = None,
) -> bool:
    """True only when every game in the week has passed kickoff (``kickoff_utc <= now``)."""
    last = last_kickoff_utc(season, week, root, games)
    if last is None:
        return False
    now = now or datetime.now(UTC)
    return _parse_utc(last) <= now.astimezone(UTC)


def latest_pre_kickoff_games(
    season: int, week: int, root: Path | None = None
) -> dict[str, tuple[dict, str, str]]:
    """For each game in ``(season, week)``, its raw record from the latest snapshot
    published strictly before that game's ``kickoff_utc``.

    Tie-breaking uses ``(publication_time_utc, artifact.rel)``.
    Returns ``{game_id: (game_dict, published_utc, rel)}``.
    """
    best: dict[str, tuple[datetime, str, str, dict]] = {}
    for art in artifacts_for_week(season, week, root):
        doc = json.loads(art.path.read_text())
        pub = publication_time_utc(art, root)
        pub_dt = _parse_utc(pub)
        for g in doc.get("games") or []:
            kick = g.get("kickoff_utc")
            if not kick:
                continue
            if pub_dt >= _parse_utc(kick):
                continue
            gid = g["game_id"]
            prev = best.get(gid)
            if prev is None or (pub_dt, art.rel) > (prev[0], prev[1]):
                best[gid] = (pub_dt, art.rel, pub, g)
    return {gid: (g, pub, rel) for gid, (_dt, rel, pub, g) in best.items()}


def freeze_started_games(
    season: int,
    week: int,
    games: list[dict],
    *,
    now: datetime | None = None,
    root: Path | None = None,
) -> list[dict]:
    """Freeze every game with ``kickoff_utc <= now`` to its latest pre-kickoff record.

    Also preserves already-started games from earlier pre-kickoff snapshots that are no
    longer in ``games`` (for example a Thursday game already marked played by Friday).
    Raises :class:`WeekLockedError` if all games have passed kickoff or if a started game
    has no prior snapshot published strictly before its kickoff.
    """
    now_utc = (now or datetime.now(UTC)).astimezone(UTC)
    pre_kickoff = latest_pre_kickoff_games(season, week, root=root)
    frozen_out: list[dict] = []
    seen: set[str] = set()

    for gid, (frozen_game, _pub, _rel) in sorted(
        pre_kickoff.items(), key=lambda kv: (kv[1][0].get("kickoff_utc", ""), kv[0])
    ):
        if _parse_utc(frozen_game["kickoff_utc"]) <= now_utc:
            frozen_out.append(copy.deepcopy(frozen_game))
            seen.add(gid)

    for g in games:
        gid = g["game_id"]
        if gid in seen:
            continue
        if _parse_utc(g["kickoff_utc"]) <= now_utc:
            if gid not in pre_kickoff:
                raise WeekLockedError(
                    f"{season} week {week}: game {gid} kicked off at {g['kickoff_utc']} "
                    "with no prior pre-kickoff snapshot."
                )
            frozen_out.append(copy.deepcopy(pre_kickoff[gid][0]))
            seen.add(gid)
        else:
            frozen_out.append(g)
            seen.add(gid)

    if not any(_parse_utc(g["kickoff_utc"]) > now_utc for g in frozen_out):
        last = last_kickoff_utc(season, week, root, frozen_out)
        raise WeekLockedError(
            f"{season} week {week} is locked: all games have passed kickoff (last kickoff {last}). "
            "A historical correction follows docs/LEDGER.md; --force cannot unlock it."
        )
    return frozen_out


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


def resolve_ref(root: Path, ref: str) -> str:
    """Return the resolved SHA of ``ref``. Raise if it cannot be resolved."""
    proc = _git(["rev-parse", "--verify", ref], cwd=root.resolve(), check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode().strip() or proc.stdout.decode().strip()
        raise LedgerError(
            f"base ref {ref!r} could not be resolved" + (f": {detail}" if detail else "")
        )
    return proc.stdout.decode().strip()


def manifest_entries_at_ref(root: Path, ref: str) -> dict:
    """Return the manifest artifacts map at ``ref``.

    The ref is validated first. If it cannot be resolved, raise rather than
    treating the base as empty. If ``predictions/MANIFEST.json`` is absent at
    that ref, return ``{}`` (bootstrap). Entry values are left as parsed JSON
    so the whole entry object can be compared, not only a SHA-256 string.
    """
    root = root.resolve()
    resolve_ref(root, ref)
    probe = _git(["cat-file", "-e", f"{ref}:{MANIFEST_REL}"], cwd=root, check=False)
    if probe.returncode != 0:
        return {}
    proc = _git(["show", f"{ref}:{MANIFEST_REL}"], cwd=root, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode().strip()
        raise LedgerError(
            f"failed to read {MANIFEST_REL} at {ref!r}" + (f": {detail}" if detail else "")
        )
    try:
        doc = json.loads(proc.stdout.decode())
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{MANIFEST_REL} at {ref!r}: invalid JSON ({exc})") from exc
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, dict):
        raise LedgerError(f"{MANIFEST_REL} at {ref!r}: missing artifacts map")
    return artifacts


def append_only_violations(current: dict, base: dict) -> list[str]:
    """The manifest may only grow: every base entry must still exist unchanged.

    Allows only the approved one-time NTFS filename migration listed in
    ``LEGACY_NTFS_RENAMES`` when the renamed path keeps the exact same SHA-256.
    """
    errors: list[str] = []
    for key, base_value in base.items():
        if key in current:
            if current[key] != base_value:
                errors.append(f"{key}: historical manifest entry changed")
            continue
        renamed = LEGACY_NTFS_RENAMES.get(key)
        if renamed and current.get(renamed) == base_value:
            continue
        if renamed and renamed in current:
            errors.append(
                f"{key}: historical manifest entry changed during NTFS rename to {renamed}"
            )
        else:
            errors.append(f"{key}: deleted from the manifest (append-only)")
    return errors


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
    freeze_started: bool = False,
) -> Path:
    """Write a new immutable snapshot and add it to the manifest. Never overwrites.

    Refuses if the week already has a snapshot and ``force`` is false, refuses
    unconditionally once all games in the week have passed kickoff, and enforces
    per-game canonical immutability for every game with ``kickoff_utc <= now``.
    When ``freeze_started=True``, games with ``kickoff_utc <= now`` are automatically
    replaced with their frozen pre-kickoff canonical records before writing.
    """
    root = (root or C.ROOT).resolve()
    season, week = int(doc["season"]), int(doc["week"])
    games = list(doc.get("games") or [])
    now_utc = (now or datetime.now(UTC)).astimezone(UTC)
    if week_is_locked(season, week, now=now_utc, root=root, games=games):
        last = last_kickoff_utc(season, week, root, games)
        raise WeekLockedError(
            f"{season} week {week} is locked: all games have passed kickoff (last kickoff {last}). "
            "A historical correction follows docs/LEDGER.md; --force cannot unlock it."
        )
    existing = artifacts_for_week(season, week, root)
    if existing and not force:
        raise SnapshotExistsError(
            f"{season} week {week} already has {len(existing)} snapshot(s). "
            "Pass --force to write a new one while open games remain."
        )
    if freeze_started:
        games = freeze_started_games(season, week, games, now=now_utc, root=root)
        doc = {**doc, "games": games}

    pre_kickoff = latest_pre_kickoff_games(season, week, root=root)
    incoming_ids = {g["game_id"] for g in games}
    for gid, (frozen_game, _pub, frozen_rel) in pre_kickoff.items():
        if _parse_utc(frozen_game["kickoff_utc"]) <= now_utc and gid not in incoming_ids:
            raise WeekLockedError(
                f"{season} week {week}: started game {gid} is missing from the new snapshot; "
                f"must preserve frozen canonical record from {frozen_rel}."
            )
    for g in games:
        kick = g.get("kickoff_utc")
        if not kick or _parse_utc(kick) > now_utc:
            continue
        gid = g["game_id"]
        if gid not in pre_kickoff:
            raise WeekLockedError(
                f"{season} week {week}: started game {gid} (kickoff {kick}) "
                "has no prior pre-kickoff snapshot."
            )
        frozen_game, _pub, frozen_rel = pre_kickoff[gid]
        if canonical_game_json(g) != canonical_game_json(frozen_game):
            raise WeekLockedError(
                f"{season} week {week}: started game {gid} differs from its frozen canonical "
                f"record in {frozen_rel}."
            )

    generated = doc["generated_at_utc"]
    payload = json.dumps(doc, indent=1) + "\n"
    digest = hashlib.sha256(payload.encode()).hexdigest()
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
            digest = hashlib.sha256(raw).hexdigest()
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
    "LEGACY_NTFS_RENAMES",
    "MANIFEST_REL",
    "WEEK11_HISTORY",
    "WEEK12_HISTORY",
    "Artifact",
    "LedgerError",
    "SnapshotExistsError",
    "WeekLockedError",
    "add_to_manifest",
    "artifacts_for_week",
    "canonical_game_json",
    "describe",
    "first_kickoff_utc",
    "first_publication_utc",
    "freeze_started_games",
    "iter_artifacts",
    "iter_latest",
    "iter_snapshot_paths",
    "last_kickoff_utc",
    "latest_artifact",
    "latest_pre_kickoff_games",
    "legacy_week_path",
    "load_manifest",
    "manifest_path",
    "parse_utc",
    "publication_time_utc",
    "rebuild_historical",
    "refresh_manifest",
    "unexpected_prediction_files",
    "week_dir",
    "week_is_locked",
    "write_manifest",
    "write_snapshot",
]
