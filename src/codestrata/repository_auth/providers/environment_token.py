"""Environment-variable GitHub token credential provider."""

from __future__ import annotations

import os

from pydantic import SecretStr

from codestrata.repository_auth.exceptions import CredentialUnavailableError
from codestrata.repository_auth.github_urls import parse_github_repository_url
from codestrata.repository_auth.models import (
    ASKPASS_PASSWORD_ENV,
    ASKPASS_USERNAME_ENV,
    GITHUB_HTTPS_TOKEN_USERNAME,
    AuthenticationMethod,
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
    ResolvedRepositoryCredential,
)


class EnvironmentTokenProvider:
    """Resolve a GitHub HTTPS token from a configured environment variable."""

    provider_id = "github_token"

    def supports(
        self,
        repository_url: str,
        authentication_config: RepositoryAuthenticationConfig | None,
    ) -> bool:
        if authentication_config is None:
            return False
        if authentication_config.type is not AuthenticationProviderType.GITHUB_TOKEN:
            return False
        parsed = parse_github_repository_url(repository_url)
        return parsed.transport == "https"

    def resolve(
        self,
        authentication_config: RepositoryAuthenticationConfig,
    ) -> ResolvedRepositoryCredential:
        env_name = authentication_config.token_env
        if not env_name:
            raise CredentialUnavailableError(
                "The configured credential environment variable is not available."
            )

        value = os.environ.get(env_name)
        if value is None or not value.strip():
            raise CredentialUnavailableError(
                "The configured credential environment variable is not available."
            )

        return ResolvedRepositoryCredential(
            provider_id=self.provider_id,
            method=AuthenticationMethod.HTTPS_ASKPASS,
            secret=SecretStr(value),
            username=GITHUB_HTTPS_TOKEN_USERNAME,
        )


def askpass_environment_overrides(
    credential: ResolvedRepositoryCredential,
    *,
    askpass_path: str,
) -> dict[str, str]:
    """Build child-process-only environment overrides for GIT_ASKPASS."""

    secret = credential.get_secret_value()
    if secret is None:
        raise CredentialUnavailableError(
            "The configured credential environment variable is not available."
        )

    return {
        "GIT_ASKPASS": askpass_path,
        "GIT_TERMINAL_PROMPT": "0",
        ASKPASS_USERNAME_ENV: credential.username or GITHUB_HTTPS_TOKEN_USERNAME,
        ASKPASS_PASSWORD_ENV: secret,
    }
