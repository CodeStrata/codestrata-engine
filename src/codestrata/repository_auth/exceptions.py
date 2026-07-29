"""Repository authentication exceptions."""

from __future__ import annotations

from enum import StrEnum


class RepositoryAccessCategory(StrEnum):
    """Internal classification for repository access failures."""

    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    REPOSITORY_NOT_FOUND = "repository_not_found"
    UNSUPPORTED_REPOSITORY_URL = "unsupported_repository_url"
    UNSUPPORTED_AUTHENTICATION_CONFIGURATION = "unsupported_authentication_configuration"
    CLONE_FAILED = "clone_failed"
    CLONE_TIMEOUT = "clone_timeout"
    REMOTE_VALIDATION_FAILED = "remote_validation_failed"
    WORKSPACE_CLEANUP_FAILED = "workspace_cleanup_failed"
    ACCESS_AMBIGUOUS = "access_ambiguous"


class RepositoryAccessError(Exception):
    """Sanitized repository access failure."""

    def __init__(
        self,
        message: str,
        *,
        category: RepositoryAccessCategory,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message

    def __str__(self) -> str:
        return self.message


class CredentialUnavailableError(RepositoryAccessError):
    """Configured credential reference could not be resolved."""

    def __init__(
        self,
        message: str = ("The configured credential environment variable is not available."),
    ) -> None:
        super().__init__(
            message,
            category=RepositoryAccessCategory.CREDENTIAL_UNAVAILABLE,
        )


class AuthenticationFailedError(RepositoryAccessError):
    """Git rejected the supplied credentials."""

    def __init__(
        self,
        message: str = ("GitHub authentication failed. Verify the configured credential."),
    ) -> None:
        super().__init__(
            message,
            category=RepositoryAccessCategory.AUTHENTICATION_FAILED,
        )


class AuthorizationFailedError(RepositoryAccessError):
    """Credentials authenticated but lack repository access."""

    def __init__(
        self,
        message: str = ("The credential does not have access to this repository."),
    ) -> None:
        super().__init__(
            message,
            category=RepositoryAccessCategory.AUTHORIZATION_FAILED,
        )


class UnsupportedRepositoryUrlError(RepositoryAccessError):
    """Repository URL scheme or host is not supported."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            category=RepositoryAccessCategory.UNSUPPORTED_REPOSITORY_URL,
        )


class UnsupportedAuthenticationConfigurationError(RepositoryAccessError):
    """Authentication type is incompatible with the repository URL."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            category=RepositoryAccessCategory.UNSUPPORTED_AUTHENTICATION_CONFIGURATION,
        )
