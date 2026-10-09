"""Secure private GitHub repository authentication."""

from codestrata.repository_auth.exceptions import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    CredentialUnavailableError,
    RepositoryAccessCategory,
    RepositoryAccessError,
    UnsupportedAuthenticationConfigurationError,
    UnsupportedRepositoryUrlError,
)
from codestrata.repository_auth.models import (
    AuthenticationMethod,
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
    ResolvedRepositoryCredential,
    SanitizedAuthenticationMetadata,
)
from codestrata.repository_auth.read_only_git import (
    ALLOWED_GIT_COMMANDS,
    ReadOnlyGitError,
    assert_read_only_git_arguments,
    run_readonly_git,
    run_readonly_git_bytes,
)
from codestrata.repository_auth.service import RepositoryAuthenticationService

__all__ = [
    "AuthenticationFailedError",
    "AuthenticationMethod",
    "AuthenticationProviderType",
    "AuthorizationFailedError",
    "CredentialUnavailableError",
    "RepositoryAccessCategory",
    "RepositoryAccessError",
    "RepositoryAuthenticationConfig",
    "ALLOWED_GIT_COMMANDS",
    "ReadOnlyGitError",
    "RepositoryAuthenticationService",
    "assert_read_only_git_arguments",
    "run_readonly_git",
    "run_readonly_git_bytes",
    "ResolvedRepositoryCredential",
    "SanitizedAuthenticationMetadata",
    "UnsupportedAuthenticationConfigurationError",
    "UnsupportedRepositoryUrlError",
]
