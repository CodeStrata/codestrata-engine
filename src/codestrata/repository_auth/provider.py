"""Credential provider protocol for repository authentication."""

from __future__ import annotations

from typing import Protocol

from codestrata.repository_auth.models import (
    RepositoryAuthenticationConfig,
    ResolvedRepositoryCredential,
)


class RepositoryCredentialProvider(Protocol):
    """Provider-neutral credential resolution interface."""

    @property
    def provider_id(self) -> str:
        """Stable provider identifier."""

    def supports(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig | None,
    ) -> bool:
        """Return whether this provider applies to the URL and configuration."""

    def resolve(
        self,
        authentication_config: RepositoryAuthenticationConfig,
    ) -> ResolvedRepositoryCredential:
        """Resolve a runtime-only credential from configuration references."""
