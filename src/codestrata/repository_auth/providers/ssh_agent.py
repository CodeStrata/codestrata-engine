"""SSH-agent credential provider for GitHub SSH URLs."""

from __future__ import annotations

from codestrata.repository_auth.github_urls import parse_github_repository_url
from codestrata.repository_auth.models import (
    AuthenticationMethod,
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
    ResolvedRepositoryCredential,
)


class SshAgentProvider:
    """Rely on the user's existing SSH agent and SSH configuration."""

    provider_id = "ssh_agent"

    def supports(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig | None,
    ) -> bool:
        if authentication_config is None:
            return False
        if authentication_config.type is not AuthenticationProviderType.SSH_AGENT:
            return False
        parsed = parse_github_repository_url(repository_url)
        return parsed.transport == "ssh"

    def resolve(
        self,
        authentication_config: RepositoryAuthenticationConfig,
    ) -> ResolvedRepositoryCredential:
        del authentication_config  # configuration carries no secret material
        return ResolvedRepositoryCredential(
            provider_id=self.provider_id,
            method=AuthenticationMethod.SSH_AGENT,
            secret=None,
            username=None,
        )
