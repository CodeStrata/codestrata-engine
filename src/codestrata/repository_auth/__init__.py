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
    "RepositoryAuthenticationService",
    "ResolvedRepositoryCredential",
    "SanitizedAuthenticationMetadata",
    "UnsupportedAuthenticationConfigurationError",
    "UnsupportedRepositoryUrlError",
]
