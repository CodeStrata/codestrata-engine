"""Tests for SSH URL handling and authentication compatibility."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codestrata.models import Repository
from codestrata.repository_auth.exceptions import UnsupportedAuthenticationConfigurationError
from codestrata.repository_auth.github_urls import parse_github_repository_url
from codestrata.repository_auth.models import (
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
)
from codestrata.repository_auth.service import RepositoryAuthenticationService
from codestrata.services.scanners import GitHubRepositoryScanner


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )


def test_scp_and_ssh_uri_parsing() -> None:
    scp = parse_github_repository_url("git@github.com:org/repo.git")
    uri = parse_github_repository_url("ssh://git@github.com/org/repo.git")
    assert scp.transport == "ssh"
    assert uri.transport == "ssh"
    assert scp.owner == "org"
    assert uri.repository == "repo"


def test_ssh_agent_does_not_create_helpers_or_read_token_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODESTRATA_GITHUB_TOKEN", "should-not-be-read")
    local_scanner = Mock()
    local_scanner.scan.return_value = Repository(
        name="repo",
        path=tmp_path / "repo",
        files=[],
        total_files=0,
    )
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        local_scanner=local_scanner,
        authentication=RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT),
    )
    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            _completed(),
            _completed("git@github.com:org/repo.git\n"),
        ]
        scanner.scan("git@github.com:org/repo.git")

    env = run_mock.call_args_list[0].kwargs["env"]
    assert "GIT_ASKPASS" not in env
    assert "CODESTRATA_GIT_ASKPASS_PASSWORD" not in env
    assert "GIT_SSH_COMMAND" not in env


def test_ssh_without_explicit_auth_uses_existing_agent_behavior(
    tmp_path: Path,
) -> None:
    local_scanner = Mock()
    local_scanner.scan.return_value = Repository(
        name="repo",
        path=tmp_path / "repo",
        files=[],
        total_files=0,
    )
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        local_scanner=local_scanner,
    )
    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            _completed(),
            _completed("ssh://git@github.com/org/repo.git\n"),
        ]
        scanner.scan("ssh://git@github.com/org/repo.git")

    assert "GIT_ASKPASS" not in run_mock.call_args_list[0].kwargs["env"]


def test_incompatible_auth_combinations() -> None:
    service = RepositoryAuthenticationService()
    with pytest.raises(UnsupportedAuthenticationConfigurationError):
        service.validate_compatibility(
            "https://github.com/org/repo.git",
            RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT),
        )
    with pytest.raises(UnsupportedAuthenticationConfigurationError):
        service.validate_compatibility(
            "git@github.com:org/repo.git",
            RepositoryAuthenticationConfig(
                type=AuthenticationProviderType.GITHUB_TOKEN,
                token_env="CODESTRATA_GITHUB_TOKEN",
            ),
        )
