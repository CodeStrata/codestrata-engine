"""Refuse mutating and network Git verbs before a subprocess starts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.repository_auth.read_only_git import (
    ALLOWED_GIT_COMMANDS,
    ReadOnlyGitError,
    assert_read_only_git_arguments,
    run_readonly_git,
    run_readonly_git_bytes,
)


@pytest.mark.parametrize(
    "arguments",
    [
        ["fetch", "origin"],
        ["pull"],
        ["clone", "https://github.com/example/repo.git"],
        ["checkout", "main"],
        ["switch", "topic"],
        ["reset", "--hard"],
        ["merge", "other"],
        ["rebase", "main"],
        ["apply", "change.patch"],
        ["commit", "-m", "x"],
        ["submodule", "update"],
        ["ls-remote", "origin"],
        ["hash-object", "-w", "file.txt"],
        ["symbolic-ref", "-d", "refs/heads/tmp"],
    ],
)
def test_mutating_and_network_git_verbs_are_refused(arguments: list[str]) -> None:
    with pytest.raises(ReadOnlyGitError):
        assert_read_only_git_arguments(arguments)
    with patch("codestrata.repository_auth.read_only_git.run_git") as mocked:
        with pytest.raises(ReadOnlyGitError):
            run_readonly_git(arguments, cwd=Path("."))
        mocked.assert_not_called()


def test_allowed_verbs_are_explicit() -> None:
    assert "diff" in ALLOWED_GIT_COMMANDS
    assert "ls-tree" in ALLOWED_GIT_COMMANDS
    assert "cat-file" in ALLOWED_GIT_COMMANDS
    assert "fetch" not in ALLOWED_GIT_COMMANDS
    assert "checkout" not in ALLOWED_GIT_COMMANDS
    assert "archive" not in ALLOWED_GIT_COMMANDS
    assert assert_read_only_git_arguments(["-C", "/tmp", "rev-parse", "HEAD"]) == "rev-parse"
    with pytest.raises(ReadOnlyGitError):
        run_readonly_git_bytes(["checkout", "main"], cwd=Path("."))
