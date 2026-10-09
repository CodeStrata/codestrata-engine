"""Local Git identity digests without mutating the checkout."""

from __future__ import annotations

from pathlib import Path

from codestrata.infrastructure.knowledge_store.git_revision import (
    observe_local_git_state,
    observe_repository_revision,
)
from codestrata.repository_auth.read_only_git import run_readonly_git
from tests.application.incremental.git_repo_helpers import commit_all, init_repo, write


def test_observe_local_state_pins_head_tree_index_and_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    before = observe_local_git_state(repo)
    assert before.head_sha
    assert before.tree_oid
    assert before.branch == "main"
    assert before.dirty is False
    write(repo, "src/app.py", "print(2)\n")
    after = observe_local_git_state(repo)
    assert after.head_sha == before.head_sha
    assert after.tree_oid == before.tree_oid
    assert after.working_tree_digest != before.working_tree_digest
    assert after.dirty is True
    head_after = run_readonly_git(["rev-parse", "HEAD"], cwd=repo).strip()
    branch_after = run_readonly_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).strip()
    assert head_after == before.head_sha
    assert branch_after == "main"
    observed = observe_repository_revision(repo)
    assert observed.revision_id == before.head_sha
    assert observed.dirty is True
