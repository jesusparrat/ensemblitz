"""Site reads published artifacts only: no re-simulation, deterministic HTML."""

from __future__ import annotations

import inspect
from pathlib import Path

from ensemblitz.site import build as B
from ensemblitz.site.build import build_site
from test_site import _repo


def test_site_module_does_not_import_or_call_the_simulator() -> None:
    source = inspect.getsource(B)
    assert "simulate_games" not in source
    assert "SimParams" not in source
    import ensemblitz.site.build as mod

    assert not hasattr(mod, "simulate_games")


def test_two_builds_of_the_fixture_repo_are_identical(tmp_path: Path) -> None:
    root = _repo(tmp_path, True, True)
    a = build_site(root=root, out=root / "site" / "_a")
    b = build_site(root=root, out=root / "site" / "_b")
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel


def test_two_builds_of_the_published_site_are_identical(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    a = build_site(root=repo, out=tmp_path / "a")
    b = build_site(root=repo, out=tmp_path / "b")
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel
