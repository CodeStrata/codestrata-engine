from __future__ import annotations

from pathlib import Path

import pytest

from tests.verification.gitutil import git

ENGINE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def engine_root() -> Path:
    return ENGINE_ROOT


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "engine").mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "scope-fixture")
    git(repo, "config", "user.email", "scope-fixture@example.invalid")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "README.md").write_text("root file\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (repo / "engine" / "ok.md").write_text("in engine\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "init")
    git(repo, "branch", "-M", "main")
    git(repo, "checkout", "-b", "release/engine-next")
    git(repo, "checkout", "-b", "engine/story")
    return repo
