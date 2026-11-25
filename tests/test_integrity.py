"""SHA-256 integrity: a flipped byte is detected; a clean tree passes."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _copy_predictions(tmp: Path) -> Path:
    dest = tmp / "repo"
    dest.mkdir()
    shutil.copytree(ROOT / "predictions", dest / "predictions")
    # a fake .git so hash-object still works if called; publication checks skip unknown blobs
    (dest / ".git").mkdir()
    return dest


def test_verify_integrity_passes_on_the_repo() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_integrity", ROOT / "scripts" / "verify_integrity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.verify(ROOT) == []


def test_verify_integrity_fails_when_a_byte_is_changed(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_integrity", ROOT / "scripts" / "verify_integrity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    dest = _copy_predictions(tmp_path)
    target = dest / "predictions" / "2026" / "week12.json"
    data = bytearray(target.read_bytes())
    data[0] ^= 0x01
    target.write_bytes(data)
    errors = mod.verify(dest)
    assert errors, "a modified snapshot must fail the integrity check"
    assert any("sha256 mismatch" in e and "week12.json" in e for e in errors)


def test_verify_integrity_fails_when_an_artifact_is_deleted(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_integrity", ROOT / "scripts" / "verify_integrity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    dest = _copy_predictions(tmp_path)
    (dest / "predictions" / "2026" / "week11.json").unlink()
    errors = mod.verify(dest)
    assert any("missing on disk" in e and "week11.json" in e for e in errors)
