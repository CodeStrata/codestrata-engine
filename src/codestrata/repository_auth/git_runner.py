"""Controlled Git subprocess execution."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from codestrata.repository_auth.exceptions import (
    RepositoryAccessCategory,
    RepositoryAccessError,
)
from codestrata.repository_auth.git_errors import classify_clone_failure
from codestrata.security.redaction import Redactor


def build_subprocess_environment(
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Assemble a child environment without mutating the parent process."""

    environment = dict(os.environ)
    if overrides:
        environment.update(overrides)
    return environment


def run_git(
    arguments: Sequence[str],
    *,
    timeout_seconds: float | None = 300,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    redactor: Redactor | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a Git command with shell=False and sanitized failures."""

    active = redactor or Redactor()
    command = ["git", *arguments]

    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
            env=build_subprocess_environment(environment),
            cwd=str(cwd) if cwd is not None else None,
        )
    except FileNotFoundError as error:
        raise RepositoryAccessError(
            "Git is not installed or is not available on PATH.",
            category=RepositoryAccessCategory.CLONE_FAILED,
        ) from error
    except subprocess.TimeoutExpired as error:
        stderr = error.stderr if isinstance(error.stderr, str) else ""
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        raise classify_clone_failure(
            stderr=stderr or "",
            stdout=stdout or "",
            timed_out=True,
            redactor=active,
        ) from error
    except subprocess.CalledProcessError as error:
        raise classify_clone_failure(
            stderr=error.stderr or "",
            stdout=error.stdout or "",
            timed_out=False,
            redactor=active,
        ) from error


def verify_remote_origin_url(
    repository_directory: Path,
    *,
    expected_credential_free_url: str,
    redactor: Redactor | None = None,
) -> str:
    """Ensure remote.origin.url is the original credential-free URL.

    Some Git configurations (for example ``url.*.insteadOf``) may rewrite the
    stored origin to include userinfo. CodeStrata always resets origin to the
    credential-free repository URL after clone.
    """

    active = redactor or Redactor()
    remote_url = _get_remote_origin_url(repository_directory, redactor=active)

    if remote_url != expected_credential_free_url or _has_url_userinfo_credentials(remote_url):
        run_git(
            [
                "-C",
                str(repository_directory),
                "remote",
                "set-url",
                "origin",
                expected_credential_free_url,
            ],
            timeout_seconds=30,
            redactor=active,
        )
        remote_url = _get_remote_origin_url(repository_directory, redactor=active)

    if _has_url_userinfo_credentials(remote_url) or _looks_like_embedded_secret(remote_url):
        raise RepositoryAccessError(
            "Remote validation failed: origin URL must not contain credentials.",
            category=RepositoryAccessCategory.REMOTE_VALIDATION_FAILED,
        )

    return remote_url


def _get_remote_origin_url(
    repository_directory: Path,
    *,
    redactor: Redactor,
) -> str:
    # Read the stored config value. `git remote get-url` can apply insteadOf
    # rewrites and would re-introduce credential-bearing URLs from Git config.
    result = run_git(
        [
            "-C",
            str(repository_directory),
            "config",
            "--get",
            "remote.origin.url",
        ],
        timeout_seconds=30,
        redactor=redactor,
    )
    return (result.stdout or "").strip()


def _has_url_userinfo_credentials(remote_url: str) -> bool:
    if "@" not in remote_url or "://" not in remote_url:
        return False
    before_at = remote_url.split("@", 1)[0]
    if "://" not in before_at:
        return False
    userinfo = before_at.split("://", 1)[1]
    return ":" in userinfo


def _looks_like_embedded_secret(remote_url: str) -> bool:
    lowered = remote_url.lower()
    return (
        "ghp_" in remote_url
        or "github_pat_" in remote_url
        or "gho_" in remote_url
        or "ghu_" in remote_url
        or "ghs_" in remote_url
        or "ghr_" in remote_url
        or "%40" in lowered
    )
