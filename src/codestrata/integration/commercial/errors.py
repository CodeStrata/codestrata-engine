"""Platform integration errors."""

from __future__ import annotations


class PlatformIntegrationError(Exception):
    """Base error for Engine → Platform communication failures."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str | None = None,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.retryable = retryable
        self.status_code = status_code


class PlatformUnavailableError(PlatformIntegrationError):
    """Platform could not be reached or returned a retryable failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(
            message,
            reason_code="platform_unavailable",
            retryable=True,
            status_code=status_code,
        )


class PlatformConflictError(PlatformIntegrationError):
    """Duplicate registration or assessment conflict."""

    def __init__(self, message: str, *, reason_code: str = "conflict") -> None:
        super().__init__(message, reason_code=reason_code, retryable=False, status_code=409)


class PlatformPermanentError(PlatformIntegrationError):
    """Non-retryable Platform rejection (validation, auth placeholder, etc.)."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "permanent_failure",
        status_code: int | None = None,
    ) -> None:
        super().__init__(
            message,
            reason_code=reason_code,
            retryable=False,
            status_code=status_code,
        )
