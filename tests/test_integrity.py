"""SHA-256 integrity and append-only manifest checks against a Git base ref."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_mod():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_integrity", ROOT / "scripts" / "verify_integrity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_snapshot(repo: Path, rel: str, game_id: str = "2026_99_AAA_BBB") -> bytes:
    doc = {
        "season": 2026,
        "week": 99,
        "generated_at": "2026-01-01T00:00:00Z",
        "games": [
            {
                "game_id": game_id,
                "home_team": "BBB",
                "away_team": "AAA",
                "kickoff_utc": "2099-01-01T00:00:00Z",
                "generated_at": "2026-01-01T00:00:00Z",
                "home_win_prob": {"ensemble": 0.6, "market": 0.55},
            }
        ],
    }
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(doc, indent=2) + "\n").encode()
    path.write_bytes(data)
    return data


def _write_manifest(repo: Path, artifacts: dict[str, object]) -> None:
    path = repo / "predictions" / "MANIFEST.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"artifacts": dict(sorted(artifacts.items()))}, indent=1) + "\n")


def _copy_predictions(tmp: Path) -> Path:
    dest = tmp / "repo"
    dest.mkdir()
    shutil.copytree(ROOT / "predictions", dest / "predictions")
    # Real repo so default --base-ref HEAD can be resolved. Only a dummy commit
    # is created, so the copied snapshots stay uncommitted (publication checks
    # skip unknown blobs) and the base manifest is empty (bootstrap).
    _git(dest, "init", "-b", "main")
    _git(dest, "config", "user.name", "Test")
    _git(dest, "config", "user.email", "test@example.com")
    _git(dest, "config", "commit.gpgsign", "false")
    (dest / "README").write_text("init\n")
    _git(dest, "add", "README")
    _git(dest, "commit", "-m", "init")
    return dest


def test_verify_integrity_passes_on_the_repo() -> None:
    assert _load_mod().verify(ROOT) == []


def test_verify_integrity_fails_when_a_byte_is_changed(tmp_path: Path) -> None:
    dest = _copy_predictions(tmp_path)
    target = dest / "predictions" / "2026" / "week12.json"
    data = bytearray(target.read_bytes())
    data[0] ^= 0x01
    target.write_bytes(data)
    errors = _load_mod().verify(dest)
    assert errors, "a modified snapshot must fail the integrity check"
    assert any("sha256 mismatch" in e and "week12.json" in e for e in errors)


def test_verify_integrity_fails_when_an_artifact_is_deleted(tmp_path: Path) -> None:
    dest = _copy_predictions(tmp_path)
    (dest / "predictions" / "2026" / "week11.json").unlink()
    errors = _load_mod().verify(dest)
    assert any("missing on disk" in e and "week11.json" in e for e in errors)


# ---------------------------------------------------------------------------
# Isolated Git-based append-only tests (temporary repos, not project history)
# ---------------------------------------------------------------------------

REL_A = "predictions/2026/week99/20260101T000000Z.json"
REL_B = "predictions/2026/week99/20260102T000000Z.json"


def test_bootstrap_base_has_no_manifest(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "README").write_text("init\n")
    _commit(repo, "init")
    data = _write_snapshot(repo, REL_A)
    _write_manifest(repo, {REL_A: _sha256(data)})
    assert _load_mod().verify(repo, base_ref="HEAD") == []


def test_legitimate_addition_passes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    data_a = _write_snapshot(repo, REL_A, game_id="2026_99_AAA_BBB")
    _write_manifest(repo, {REL_A: _sha256(data_a)})
    _commit(repo, "base manifest")
    data_b = _write_snapshot(repo, REL_B, game_id="2026_99_CCC_DDD")
    _write_manifest(repo, {REL_A: _sha256(data_a), REL_B: _sha256(data_b)})
    assert _load_mod().verify(repo, base_ref="HEAD") == []


def test_historical_hash_replacement_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    data_a = _write_snapshot(repo, REL_A)
    _write_manifest(repo, {REL_A: _sha256(data_a)})
    _commit(repo, "base manifest")
    path = repo / REL_A
    mutated = bytearray(path.read_bytes())
    mutated[0] ^= 0x01
    path.write_bytes(mutated)
    _write_manifest(repo, {REL_A: _sha256(bytes(mutated))})
    errors = _load_mod().verify(repo, base_ref="HEAD")
    assert errors, "replacing a historical hash must fail even when the file matches"
    assert any("historical manifest entry changed" in e and REL_A in e for e in errors)
    assert not any("sha256 mismatch" in e for e in errors)


def test_historical_deletion_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    data_a = _write_snapshot(repo, REL_A, game_id="2026_99_AAA_BBB")
    data_b = _write_snapshot(repo, REL_B, game_id="2026_99_CCC_DDD")
    _write_manifest(repo, {REL_A: _sha256(data_a), REL_B: _sha256(data_b)})
    _commit(repo, "base manifest")
    (repo / REL_B).unlink()
    _write_manifest(repo, {REL_A: _sha256(data_a)})
    errors = _load_mod().verify(repo, base_ref="HEAD")
    assert any("deleted from the manifest" in e and REL_B in e for e in errors)


def test_invalid_base_ref_fails_explicitly(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    data_a = _write_snapshot(repo, REL_A)
    _write_manifest(repo, {REL_A: _sha256(data_a)})
    _commit(repo, "base manifest")
    errors = _load_mod().verify(repo, base_ref="definitely-not-a-ref")
    assert errors, "a nonexistent base ref must fail explicitly"
    assert any("could not be resolved" in e and "definitely-not-a-ref" in e for e in errors)
    # Must not be treated as an empty (bootstrap) base.
    assert not any("historical manifest entry changed" in e for e in errors)


def test_empty_base_manifest_is_handled(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write_manifest(repo, {})
    _commit(repo, "empty manifest")
    data_a = _write_snapshot(repo, REL_A)
    _write_manifest(repo, {REL_A: _sha256(data_a)})
    assert _load_mod().verify(repo, base_ref="HEAD") == []


def test_colon_filename_fails_integrity(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "README").write_text("init\n")
    _commit(repo, "init")
    bad_rel = "predictions/2026/week99/2026-01-01T00:00:00Z.json"
    data = _write_snapshot(repo, bad_rel)
    _write_manifest(repo, {bad_rel: _sha256(data)})
    errors = _load_mod().verify(repo, base_ref="HEAD")
    assert any("Windows NTFS" in e and bad_rel in e for e in errors)


def test_ntfs_migration_requires_identical_sha256() -> None:
    from ensemblitz import ledger as L

    old_rel, new_rel = next(iter(L.LEGACY_NTFS_RENAMES.items()))
    sha = "a" * 64
    other_sha = "b" * 64
    # Exact byte-preserving rename passes.
    assert L.append_only_violations({new_rel: sha}, {old_rel: sha}) == []
    # Altered bytes during rename fail red.
    errs_mutated = L.append_only_violations({new_rel: other_sha}, {old_rel: sha})
    assert any("changed during NTFS rename" in e for e in errs_mutated)
    # Unapproved rename fails red.
    errs_unapproved = L.append_only_violations(
        {"predictions/2026/week99/20260101T000000Z.json": sha},
        {"predictions/2026/week99/2026-01-01T00:00:00Z.json": sha},
    )
    assert any("deleted from the manifest" in e for e in errs_unapproved)


# ---------------------------------------------------------------------------
# Per-game canonical immutability across Tuesday -> Friday snapshots
# ---------------------------------------------------------------------------


def _commit_at(repo: Path, message: str, iso_utc: str) -> None:
    import os

    env = {**os.environ, "GIT_AUTHOR_DATE": iso_utc, "GIT_COMMITTER_DATE": iso_utc}
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _midweek_doc(
    *,
    generated: str,
    thu_market: float = 0.58,
    thu_note: str = "lgbm",
    sun_prob: float = 0.55,
    include_thu: bool = True,
) -> dict:
    thu = {
        "game_id": "2026_99_AAA_BBB",
        "home_team": "BBB",
        "away_team": "AAA",
        "kickoff_utc": "2026-11-27T01:15:00Z",
        "generated_at": "2026-11-24T07:00:00Z",
        "home_win_prob": {"ensemble": 0.62, "market": thu_market},
        "market": {"spread_line": 3.0, "market_prob": thu_market},
        "explanation": {"summary": {"lead_component": thu_note}},
    }
    sun = {
        "game_id": "2026_99_CCC_DDD",
        "home_team": "DDD",
        "away_team": "CCC",
        "kickoff_utc": "2026-11-29T18:00:00Z",
        "generated_at": generated,
        "home_win_prob": {"ensemble": sun_prob, "market": 0.52},
        "market": {"spread_line": 1.5, "market_prob": 0.52},
        "explanation": {"summary": {"lead_component": "elo"}},
    }
    return {
        "season": 2026,
        "week": 99,
        "generated_at": generated,
        "games": ([thu, sun] if include_thu else [sun]),
    }


def _write_doc(repo: Path, rel: str, doc: dict) -> bytes:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(doc, indent=1) + "\n").encode()
    path.write_bytes(data)
    return data


def test_thursday_to_friday_frozen_game_passes_integrity(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    rel_tue = "predictions/2026/week99/20261124T070000Z.json"
    rel_fri = "predictions/2026/week99/20261127T220000Z.json"

    tue_data = _write_doc(repo, rel_tue, _midweek_doc(generated="2026-11-24T07:00:00Z"))
    _write_manifest(repo, {rel_tue: _sha256(tue_data)})
    _commit_at(repo, "tuesday snapshot", "2026-11-24T07:00:00Z")

    # Friday: Thu kicked off at 2026-11-27T01:15Z (preserved identically), Sun updated.
    fri_data = _write_doc(
        repo,
        rel_fri,
        _midweek_doc(generated="2026-11-27T22:00:00Z", sun_prob=0.69),
    )
    _write_manifest(repo, {rel_tue: _sha256(tue_data), rel_fri: _sha256(fri_data)})
    _commit_at(repo, "friday snapshot", "2026-11-27T22:00:00Z")

    assert _load_mod().verify(repo, base_ref="HEAD~1") == []


def test_mutated_started_game_explanation_and_market_fail_integrity(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    rel_tue = "predictions/2026/week99/20261124T070000Z.json"
    rel_fri = "predictions/2026/week99/20261127T220000Z.json"

    tue_data = _write_doc(repo, rel_tue, _midweek_doc(generated="2026-11-24T07:00:00Z"))
    _write_manifest(repo, {rel_tue: _sha256(tue_data)})
    _commit_at(repo, "tuesday snapshot", "2026-11-24T07:00:00Z")

    # Red test 1: mutate ONLY explanation on started Thursday game.
    fri_bad_exp = _write_doc(
        repo,
        rel_fri,
        _midweek_doc(generated="2026-11-27T22:00:00Z", thu_note="kf", sun_prob=0.69),
    )
    _write_manifest(repo, {rel_tue: _sha256(tue_data), rel_fri: _sha256(fri_bad_exp)})
    errs_exp = _load_mod().verify(repo, base_ref="HEAD")
    assert any("mutated after kickoff" in e and "2026_99_AAA_BBB" in e for e in errs_exp)

    # Red test 2: mutate ONLY market on started Thursday game.
    fri_bad_mkt = _write_doc(
        repo,
        rel_fri,
        _midweek_doc(generated="2026-11-27T22:00:00Z", thu_market=0.61, sun_prob=0.69),
    )
    _write_manifest(repo, {rel_tue: _sha256(tue_data), rel_fri: _sha256(fri_bad_mkt)})
    errs_mkt = _load_mod().verify(repo, base_ref="HEAD")
    assert any("mutated after kickoff" in e and "2026_99_AAA_BBB" in e for e in errs_mkt)

    # Red test 3: drop started Thursday game completely.
    fri_dropped = _write_doc(
        repo,
        rel_fri,
        _midweek_doc(generated="2026-11-27T22:00:00Z", include_thu=False, sun_prob=0.69),
    )
    _write_manifest(repo, {rel_tue: _sha256(tue_data), rel_fri: _sha256(fri_dropped)})
    errs_drop = _load_mod().verify(repo, base_ref="HEAD")
    assert any("dropped after kickoff" in e and "2026_99_AAA_BBB" in e for e in errs_drop)


def test_snapshot_after_all_games_started_fails_integrity(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    rel_tue = "predictions/2026/week99/20261124T070000Z.json"
    rel_mon = "predictions/2026/week99/20261130T080000Z.json"

    tue_data = _write_doc(repo, rel_tue, _midweek_doc(generated="2026-11-24T07:00:00Z"))
    _write_manifest(repo, {rel_tue: _sha256(tue_data)})
    _commit_at(repo, "tuesday snapshot", "2026-11-24T07:00:00Z")

    # Monday snapshot after both Thu and Sun kicked off must fail even if games are unchanged.
    mon_doc = _midweek_doc(generated="2026-11-30T08:00:00Z")
    mon_doc["games"][1]["generated_at"] = "2026-11-24T07:00:00Z"
    mon_data = _write_doc(repo, rel_mon, mon_doc)
    _write_manifest(repo, {rel_tue: _sha256(tue_data), rel_mon: _sha256(mon_data)})
    errs = _load_mod().verify(repo, base_ref="HEAD")
    assert any("after all games in the week had passed kickoff" in e for e in errs)
