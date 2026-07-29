"""Tests for authenticated HTTPS Git clone behavior."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codestrata.models import Repository
from codestrata.repository_auth.exceptions import (
    CredentialUnavailableError,
    RepositoryAccessError,
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


def test_https_token_clone_uses_askpass_without_embedding_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "ghp_test_token_value_not_for_commits"
    monkeypatch.setenv("CODESTRATA_TEST_CLONE_TOKEN", token)

    local_scanner = Mock()
    clone_directory = tmp_path / "workspace" / "sample-app"
    local_scanner.scan.return_value = Repository(
        name="sample-app",
        path=clone_directory,
        files=["README.md"],
        total_files=1,
    )

    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path / "workspace",
        branch="main",
        local_scanner=local_scanner,
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_TEST_CLONE_TOKEN",
        ),
    )

    repository_url = "https://github.com/example/sample-app.git"
    helper_paths: list[str] = []

    def run_side_effect(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        env = kwargs["env"]
        assert isinstance(env, dict)
        if command[:2] == ["git", "clone"]:
            assert kwargs["shell"] is False
            assert token not in command
            assert token not in " ".join(map(str, command))
            assert repository_url in command
            assert env.get("GIT_ASKPASS")
            assert env.get("GIT_TERMINAL_PROMPT") == "0"
            assert env.get("CODESTRATA_GIT_ASKPASS_PASSWORD") == token
            assert "CODESTRATA_GIT_ASKPASS_PASSWORD" not in os.environ
            helper = Path(str(env["GIT_ASKPASS"]))
            helper_paths.append(str(helper))
            helper_paths.append(str(helper.parent))
            assert helper.exists()
            mode = helper.stat().st_mode
            assert mode & stat.S_IRWXU == stat.S_IRWXU
            assert mode & (stat.S_IRWXG | stat.S_IRWXO) == 0
            assert not str(helper).startswith(str(clone_directory))
            return _completed()

        assert command[:2] == ["git", "-C"]
        assert token not in " ".join(map(str, command))
        return _completed(f"{repository_url}\n")

    with patch(
        "codestrata.repository_auth.git_runner.subprocess.run",
        side_effect=run_side_effect,
    ):
        repository = scanner.scan(repository_url)

    assert repository.source_url == repository_url
    assert token not in str(repository.model_dump())
    for path in helper_paths:
        assert not Path(path).exists()


def test_helper_deleted_after_git_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "ghp_failure_token_value"
    monkeypatch.setenv("CODESTRATA_TEST_CLONE_TOKEN", token)
    seen_helpers: list[Path] = []

    def run_side_effect(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["git", "clone"]:
            env = kwargs["env"]
            assert isinstance(env, dict)
            helper = Path(str(env["GIT_ASKPASS"]))
            seen_helpers.append(helper)
            raise subprocess.CalledProcessError(
                returncode=128,
                cmd=command,
                stderr=f"Authentication failed for {token}",
            )
        return _completed()

    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_TEST_CLONE_TOKEN",
        ),
    )

    with (
        patch(
            "codestrata.repository_auth.git_runner.subprocess.run",
            side_effect=run_side_effect,
        ),
        pytest.raises(RepositoryAccessError) as exc_info,
    ):
        scanner.scan("https://github.com/example/sample-app.git")

    assert token not in str(exc_info.value)
    assert seen_helpers
    assert not seen_helpers[0].exists()
    assert not seen_helpers[0].parent.exists()


def test_helper_deleted_after_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "ghp_timeout_token_value"
    monkeypatch.setenv("CODESTRATA_TEST_CLONE_TOKEN", token)
    seen_helpers: list[Path] = []

    def run_side_effect(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["git", "clone"]:
            env = kwargs["env"]
            assert isinstance(env, dict)
            helper = Path(str(env["GIT_ASKPASS"]))
            seen_helpers.append(helper)
            raise subprocess.TimeoutExpired(cmd=command, timeout=1)
        return _completed()

    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_TEST_CLONE_TOKEN",
        ),
    )

    with (
        patch(
            "codestrata.repository_auth.git_runner.subprocess.run",
            side_effect=run_side_effect,
        ),
        pytest.raises(RepositoryAccessError, match="timed out"),
    ):
        scanner.scan("https://github.com/example/sample-app.git")

    assert seen_helpers
    assert not seen_helpers[0].exists()


def test_missing_token_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODESTRATA_MISSING_TOKEN", raising=False)
    scanner = GitHubRepositoryScanner(
        workspace_directory=tmp_path,
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_MISSING_TOKEN",
        ),
    )
    with pytest.raises(CredentialUnavailableError, match="not available"):
        scanner.scan("https://github.com/example/sample-app.git")


def test_public_clone_does_not_resolve_authentication(tmp_path: Path) -> None:
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
    )
    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            _completed(),
            _completed("https://github.com/example/sample-app.git\n"),
        ]
        scanner.scan("https://github.com/example/sample-app.git")

    env = run_mock.call_args_list[0].kwargs["env"]
    assert "GIT_ASKPASS" not in env
    assert "CODESTRATA_GIT_ASKPASS_PASSWORD" not in env


def test_repository_path_with_spaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "ghp_spaces_token_value"
    monkeypatch.setenv("CODESTRATA_TEST_CLONE_TOKEN", token)
    workspace = tmp_path / "work space"
    local_scanner = Mock()
    local_scanner.scan.return_value = Repository(
        name="sample-app",
        path=workspace / "sample-app",
        files=[],
        total_files=0,
    )
    scanner = GitHubRepositoryScanner(
        workspace_directory=workspace,
        local_scanner=local_scanner,
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_TEST_CLONE_TOKEN",
        ),
    )
    with patch("codestrata.repository_auth.git_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            _completed(),
            _completed("https://github.com/example/sample-app.git\n"),
        ]
        scanner.scan("https://github.com/example/sample-app.git")

    clone_args = run_mock.call_args_list[0].args[0]
    assert str(workspace / "sample-app") in clone_args
