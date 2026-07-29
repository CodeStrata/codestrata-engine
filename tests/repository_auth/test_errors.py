"""Tests for repository access error classification and cleanup."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.repository_auth.exceptions import (
    AuthenticationFailedError,
    RepositoryAccessCategory,
    RepositoryAccessError,
)
from codestrata.repository_auth.git_errors import classify_clone_failure
from codestrata.repository_auth.models import (
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
)
from codestrata.security.redaction import Redactor
from codestrata.services.scanners import GitHubRepositoryScanner


def test_authentication_failure_classification() -> None:
    error = classify_clone_failure(
        stderr="remote: Invalid username or password.",
        redactor=Redactor(secrets=["secret-token"]),
    )
    assert isinstance(error, AuthenticationFailedError)


def test_ambiguous_not_found_classification() -> None:
    error = classify_clone_failure(stderr="ERROR: Repository not found.")
    assert error.category is RepositoryAccessCategory.ACCESS_AMBIGUOUS
    assert "could not be accessed" in str(error)


def test_timeout_classification() -> None:
    error = classify_clone_failure(stderr="", timed_out=True)
    assert error.category is RepositoryAccessCategory.CLONE_TIMEOUT


def test_errors_never_expose_token_or_helper_paths() -> None:
    token = "ghp_should_not_leak_in_errors"
    helper = "/tmp/codestrata-git-auth-abc/codestrata-askpass.sh"
    redactor = Redactor(secrets=[token], helper_paths=[helper])
    error = classify_clone_failure(
        stderr=(
            f"fatal: Authentication failed for 'https://x:{token}@github.com/o/r' helper={helper}"
        ),
        redactor=redactor,
    )
    text = str(error)
    assert token not in text
    assert helper not in text
    assert "/tmp/" not in text or "[REDACTED]" in redactor.redact(helper)


def test_partial_clone_cleanup_on_failure(tmp_path: Path) -> None:
    clone_directory = tmp_path / "sample-app"
    clone_directory.mkdir()
    (clone_directory / "partial.txt").write_text("x", encoding="utf-8")

    scanner = GitHubRepositoryScanner(workspace_directory=tmp_path)

    with (
        patch(
            "codestrata.repository_auth.git_runner.subprocess.run",
            side_effect=subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "clone"],
                stderr="fatal: could not read Username",
            ),
        ),
        pytest.raises(RepositoryAccessError),
    ):
        scanner.scan("https://github.com/example/sample-app.git")

    assert not clone_directory.exists()


def test_remote_validation_sanitizes_credential_bearing_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "ghp_remote_validation_token"
    monkeypatch.setenv("CODESTRATA_TEST_CLONE_TOKEN", token)
    helper_seen: list[Path] = []
    origin_url = f"https://x-access-token:{token}@github.com/example/sample-app.git"
    calls: list[list[str]] = []

    def run_side_effect(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal origin_url
        calls.append(list(command))
        if command[:2] == ["git", "clone"]:
            env = kwargs["env"]
            assert isinstance(env, dict)
            helper = Path(str(env["GIT_ASKPASS"]))
            helper_seen.append(helper)
            (tmp_path / "sample-app").mkdir(exist_ok=True)
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[-2:] == ["get-url", "origin"] or command[-2:] == [
            "--get",
            "remote.origin.url",
        ]:
            return subprocess.CompletedProcess(command, 0, f"{origin_url}\n", "")
        if len(command) >= 3 and command[-3] == "set-url":
            assert command[-1] == "https://github.com/example/sample-app.git"
            assert token not in command[-1]
            origin_url = command[-1]
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    from unittest.mock import Mock

    from codestrata.models import Repository

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
        authentication=RepositoryAuthenticationConfig(
            type=AuthenticationProviderType.GITHUB_TOKEN,
            token_env="CODESTRATA_TEST_CLONE_TOKEN",
        ),
    )

    with patch(
        "codestrata.repository_auth.git_runner.subprocess.run",
        side_effect=run_side_effect,
    ):
        repository = scanner.scan("https://github.com/example/sample-app.git")

    assert repository.source_url == "https://github.com/example/sample-app.git"
    assert helper_seen
    assert not helper_seen[0].exists()
    assert any(len(call) >= 3 and call[-3] == "set-url" for call in calls)
    assert origin_url == "https://github.com/example/sample-app.git"
