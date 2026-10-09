"""``is_engine_owned``: only ``engine/...``; named root surfaces for violation text."""

from __future__ import annotations

from verification.engine_scope.paths import is_engine_owned, named_outside_surface, posix_relpath


def test_engine_owned_accepts_nested_engine_paths() -> None:
    assert is_engine_owned("engine/verification/engine_scope/guard.py")
    assert is_engine_owned("engine")
    assert is_engine_owned(r"engine\tests\foo.py")
    assert is_engine_owned("./engine/docs/implementation/gates/E00.2.md")


def test_engine_owned_rejects_outside_and_lookalikes() -> None:
    assert not is_engine_owned("scripts/release.sh")
    assert not is_engine_owned(".github/workflows/ci.yml")
    assert not is_engine_owned("engine-extra/file.py")
    assert not is_engine_owned("platform/engine/clone.py")
    assert not is_engine_owned("../engine/secret.py")
    assert not is_engine_owned("")
    assert not is_engine_owned(".")


def test_named_surfaces_cover_root_scripts_workflows_lockfiles_and_export() -> None:
    assert named_outside_surface("scripts/foo") == "scripts/"
    assert named_outside_surface(".github/workflows/ci.yml") == ".github/workflows/"
    assert named_outside_surface("public-export-manifest.yaml") == "public-export-manifest.yaml"
    assert named_outside_surface("package-lock.json") == "package-lock.json"
    assert named_outside_surface("uv.lock") == "uv.lock"
    assert named_outside_surface("engine/pyproject.toml") is None


def test_posix_relpath_strips_dot_slash() -> None:
    assert posix_relpath("./engine/a.py") == "engine/a.py"
    assert posix_relpath("\\engine\\a.py") == "engine/a.py"
