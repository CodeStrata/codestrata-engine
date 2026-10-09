"""Temporary monorepo shape: engine/ plus the named outside surfaces the guard rejects."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.verification.engine_scope.git_fixtures import run_git


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    (repo / "engine").mkdir()
    (repo / "engine" / "README.md").write_text("engine\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "release.sh").write_text("echo live\n", encoding="utf-8")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (repo / "public-export-manifest.yaml").write_text("version: 1\n", encoding="utf-8")
    (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-m", "baseline")
    return repo
