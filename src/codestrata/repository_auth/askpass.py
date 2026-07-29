"""Temporary GIT_ASKPASS helper lifecycle."""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from codestrata.repository_auth.models import (
    ASKPASS_PASSWORD_ENV,
    ASKPASS_USERNAME_ENV,
    ResolvedRepositoryCredential,
)
from codestrata.repository_auth.providers.environment_token import askpass_environment_overrides
from codestrata.security.redaction import Redactor

# Helper reads credentials from inherited child-process environment only.
_ASKPASS_SCRIPT = """#!/bin/sh
prompt="$1"
case "$prompt" in
  *Username*|*username*)
    printf '%s\\n' "${CODESTRATA_GIT_ASKPASS_USERNAME}"
    ;;
  *)
    printf '%s\\n' "${CODESTRATA_GIT_ASKPASS_PASSWORD}"
    ;;
esac
"""


@dataclass
class GitExecutionContext:
    """Scoped Git authentication execution details."""

    provider_id: str
    environment: dict[str, str] = field(default_factory=dict)
    helper_paths: list[str] = field(default_factory=list)
    redactor: Redactor = field(default_factory=Redactor)
    warnings: list[str] = field(default_factory=list)


@contextmanager
def temporary_askpass_context(
    credential: ResolvedRepositoryCredential,
) -> Iterator[GitExecutionContext]:
    """Create a restrictive askpass helper and yield child-process env overrides."""

    temp_directory: str | None = None
    askpass_path: Path | None = None
    secret = credential.get_secret_value()
    redactor = Redactor(secrets=[secret] if secret else [])

    try:
        temp_directory = tempfile.mkdtemp(prefix="codestrata-git-auth-")
        os.chmod(temp_directory, stat.S_IRWXU)
        askpass_path = Path(temp_directory) / "codestrata-askpass.sh"
        askpass_path.write_text(_ASKPASS_SCRIPT, encoding="utf-8")
        os.chmod(askpass_path, stat.S_IRWXU)

        redactor = redactor.with_helper_paths(str(askpass_path), temp_directory)
        environment = askpass_environment_overrides(
            credential,
            askpass_path=str(askpass_path),
        )

        yield GitExecutionContext(
            provider_id=credential.provider_id,
            environment=environment,
            helper_paths=[str(askpass_path), temp_directory],
            redactor=redactor,
        )
    finally:
        _cleanup_paths(
            [askpass_path, Path(temp_directory) if temp_directory else None],
            redactor=redactor,
        )


def _cleanup_paths(
    paths: list[Path | None],
    *,
    redactor: Redactor,
) -> list[str]:
    warnings: list[str] = []
    for path in paths:
        if path is None:
            continue
        try:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                # Directory should only contain the askpass helper.
                for child in path.iterdir():
                    child.unlink(missing_ok=True)
                path.rmdir()
        except OSError:
            warnings.append(
                redactor.redact("Authentication helper cleanup failed for a temporary path.")
            )
    return warnings


# Ensure env key names match models (documentation aid for static checks).
assert ASKPASS_USERNAME_ENV == "CODESTRATA_GIT_ASKPASS_USERNAME"
assert ASKPASS_PASSWORD_ENV == "CODESTRATA_GIT_ASKPASS_PASSWORD"
