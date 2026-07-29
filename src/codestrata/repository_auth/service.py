"""Repository authentication orchestration service."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from codestrata.repository_auth.askpass import GitExecutionContext, temporary_askpass_context
from codestrata.repository_auth.exceptions import UnsupportedAuthenticationConfigurationError
from codestrata.repository_auth.github_urls import ParsedGitHubUrl, parse_github_repository_url
from codestrata.repository_auth.models import (
    AuthenticationMethod,
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
    ResolvedRepositoryCredential,
)
from codestrata.repository_auth.provider import RepositoryCredentialProvider
from codestrata.repository_auth.providers import EnvironmentTokenProvider, SshAgentProvider
from codestrata.security.redaction import Redactor


class RepositoryAuthenticationService:
    """Select providers, validate compatibility, and scope Git auth contexts."""

    def __init__(
        self,
        providers: Sequence[RepositoryCredentialProvider] | None = None,
    ) -> None:
        self._providers: list[RepositoryCredentialProvider] = list(
            providers
            or [
                EnvironmentTokenProvider(),
                SshAgentProvider(),
            ]
        )

    def parse_repository_url(self, repository_url: str) -> ParsedGitHubUrl:
        """Validate and normalize a GitHub repository URL."""

        return parse_github_repository_url(repository_url)

    def validate_compatibility(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig | None,
    ) -> ParsedGitHubUrl:
        """Reject incompatible URL and authentication combinations."""

        parsed = parse_github_repository_url(repository_url)
        if authentication_config is None:
            return parsed

        auth_type = authentication_config.type
        if auth_type is AuthenticationProviderType.GITHUB_TOKEN and parsed.transport != "https":
            raise UnsupportedAuthenticationConfigurationError(
                "github_token authentication requires an HTTPS GitHub repository URL."
            )
        if auth_type is AuthenticationProviderType.SSH_AGENT and parsed.transport != "ssh":
            raise UnsupportedAuthenticationConfigurationError(
                "ssh_agent authentication requires an SSH GitHub repository URL."
            )
        return parsed

    def resolve_credential(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig | None,
    ) -> ResolvedRepositoryCredential | None:
        """Resolve a runtime credential when authentication is configured."""

        self.validate_compatibility(repository_url, authentication_config)
        if authentication_config is None:
            return None

        provider = self._select_provider(repository_url, authentication_config)
        return provider.resolve(authentication_config)

    @contextmanager
    def git_execution_context(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig | None,
    ) -> Iterator[GitExecutionContext]:
        """Yield a scoped Git execution context with cleanup guarantees."""

        self.validate_compatibility(repository_url, authentication_config)

        if authentication_config is None:
            yield GitExecutionContext(
                provider_id="none",
                environment={},
                redactor=Redactor(),
            )
            return

        credential = self.resolve_credential(repository_url, authentication_config)
        if credential is None:
            yield GitExecutionContext(
                provider_id="none",
                environment={},
                redactor=Redactor(),
            )
            return

        if credential.method is AuthenticationMethod.HTTPS_ASKPASS:
            with temporary_askpass_context(credential) as context:
                yield context
            return

        # SSH agent: no helper files and no token environment variables.
        yield GitExecutionContext(
            provider_id=credential.provider_id,
            environment={},
            redactor=Redactor(),
        )

    def _select_provider(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig,
    ) -> RepositoryCredentialProvider:
        for provider in self._providers:
            if provider.supports(repository_url, authentication_config):
                return provider

        raise UnsupportedAuthenticationConfigurationError(
            "No credential provider supports the configured authentication settings."
        )
