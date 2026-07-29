"""Tests for the GitHub repository scanner."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codestrata.models import Repository
from codestrata.repository_auth.exceptions import (
    RepositoryAccessError,
    UnsupportedRepositoryUrlError,
)
from codestrata.repository_auth.models import (
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
)
from codestrata.services.scanners import GitHubRepositoryScanner


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )


def test_github_scanner_clones_and_scans_repository(tmp_path: Path) -> None:
    local_scanner = Mock()
    local_scanner.scan.return_value = Repository(
        name="sample-app",
        path=tmp_path / "workspace" / "sample-app",
        files=["pom.xml"],
        total_files=1,
    )

    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path / "workspace",
        branch="main",
        local_scanner=local_scanner,
    )

    repository_url = "https://github.com/example/sample-app.git"
    clone_directory = tmp_path / "workspace" / "sample-app"

    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            _completed(),
            _completed(f"{repository_url}\n"),
        ]
        repository = scanner.scan(repository_url)

    first_call = run_mock.call_args_list[0]
    assert first_call.args[0] == [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        "main",
        "--single-branch",
        repository_url,
        str(clone_directory),
    ]
    assert first_call.kwargs["shell"] is False
    assert first_call.kwargs["check"] is True
    assert "GIT_ASKPASS" not in first_call.kwargs["env"]

    local_scanner.scan.assert_called_once_with(clone_directory)
    assert repository.name == "sample-app"
    assert repository.source_url == repository_url
    assert repository.default_branch == "main"


def test_github_scanner_rejects_non_github_url(tmp_path: Path) -> None:
    scanner = GitHubRepositoryScanner(workspace_directory=tmp_path)

    with pytest.raises(UnsupportedRepositoryUrlError, match="Only GitHub"):
        scanner.scan("https://gitlab.com/example/sample-app.git")


def test_github_scanner_rejects_invalid_github_path(tmp_path: Path) -> None:
    scanner = GitHubRepositoryScanner(workspace_directory=tmp_path)

    with pytest.raises(
        UnsupportedRepositoryUrlError,
        match="owner and repository name",
    ):
        scanner.scan("https://github.com/example")


def test_github_scanner_reports_clone_failure(tmp_path: Path) -> None:
    scanner = GitHubRepositoryScanner(workspace_directory=tmp_path)
    clone_error = subprocess.CalledProcessError(
        returncode=128,
        cmd=["git", "clone"],
        stderr="Repository not found",
    )

    with (
        patch(
            "codestrata.repository_auth.git_runner.subprocess.run",
            side_effect=clone_error,
        ),
        pytest.raises(
            RepositoryAccessError,
            match="could not be accessed",
        ),
    ):
        scanner.scan("https://github.com/example/missing-app.git")


def test_github_scanner_accepts_ssh_urls(tmp_path: Path) -> None:
    local_scanner = Mock()
    local_scanner.scan.return_value = Repository(
        name="sample-app",
        path=tmp_path / "sample-app",
        files=[],
        total_files=0,
    )
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        local_scanner=local_scanner,
        authentication=RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT),
    )
    clone_url = "git@github.com:example/sample-app.git"

    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [_completed(), _completed(f"{clone_url}\n")]
        repository = scanner.scan(clone_url)

    assert repository.source_url == clone_url
    assert "GIT_ASKPASS" not in run_mock.call_args_list[0].kwargs["env"]


def test_https_with_ssh_agent_is_rejected(tmp_path: Path) -> None:
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        authentication=RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT),
    )
    with pytest.raises(RepositoryAccessError, match="ssh_agent authentication"):
        scanner.scan("https://github.com/example/sample-app.git")


def test_ssh_with_github_token_is_rejected(tmp_path: Path) -> None:
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_GITHUB_TOKEN",
        ),
    )
    with pytest.raises(RepositoryAccessError, match="github_token authentication"):
        scanner.scan("git@github.com:example/sample-app.git")
