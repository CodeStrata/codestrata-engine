"""Classify sanitized Git clone failures."""

from __future__ import annotations

import re

from codestrata.repository_auth.exceptions import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    RepositoryAccessCategory,
    RepositoryAccessError,
)
from codestrata.security.redaction import Redactor

_AUTH_FAILURE = re.compile(
    r"(?i)(authentication failed|invalid username or password|could not read username|"
    r"terminal prompts disabled|permission denied \(publickey\)|"
    r"publickey|no supported authentication)",
)
_AUTHZ_FAILURE = re.compile(
    r"(?i)(access denied|permission denied(?! \(publickey\))|not authorized|"
    r"write access|protected branch)",
)
_NOT_FOUND = re.compile(
    r"(?i)(repository not found|remote:.*not found)",
)
_TIMEOUT = re.compile(r"(?i)(timed out|timeout)")


def classify_clone_failure(
    *,
    stderr: str,
    stdout: str = "",
    timed_out: bool = False,
    redactor: Redactor | None = None,
) -> RepositoryAccessError:
    """Map Git output to a sanitized repository access error."""

    active = redactor or Redactor()
    combined = active.redact(f"{stderr}\n{stdout}".strip())

    if timed_out or _TIMEOUT.search(combined):
        return RepositoryAccessError(
            "Cloning the repository timed out.",
            category=RepositoryAccessCategory.CLONE_TIMEOUT,
        )

    auth_match = _AUTH_FAILURE.search(combined)
    not_found = _NOT_FOUND.search(combined)
    authz_match = _AUTHZ_FAILURE.search(combined)

    # GitHub often returns "not found" for private repositories without access.
    if auth_match and not_found:
        return RepositoryAccessError(
            "The repository could not be accessed. "
            "Verify the repository URL and credential permissions.",
            category=RepositoryAccessCategory.ACCESS_AMBIGUOUS,
        )

    if auth_match:
        return AuthenticationFailedError()

    if authz_match:
        return AuthorizationFailedError()

    if not_found:
        # Without stronger signals, treat as ambiguous rather than certain absence.
        return RepositoryAccessError(
            "The repository could not be accessed. "
            "Verify the repository URL and credential permissions.",
            category=RepositoryAccessCategory.ACCESS_AMBIGUOUS,
        )

    return RepositoryAccessError(
        "Unable to clone the GitHub repository.",
        category=RepositoryAccessCategory.CLONE_FAILED,
    )
