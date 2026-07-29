"""Tests for environment-token and SSH-agent credential providers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from codestrata.repository_auth.exceptions import CredentialUnavailableError
from codestrata.repository_auth.models import (
    AuthenticationMethod,
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
)
from codestrata.repository_auth.providers import EnvironmentTokenProvider, SshAgentProvider


def test_token_resolved_lazily_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODESTRATA_TEST_TOKEN", raising=False)
    provider = EnvironmentTokenProvider()
    config = RepositoryAuthenticationConfig(
        type=AuthenticationProviderType.GITHUB_TOKEN,
        token_env="CODESTRATA_TEST_TOKEN",
    )

    with pytest.raises(CredentialUnavailableError):
        provider.resolve(config)

    monkeypatch.setenv("CODESTRATA_TEST_TOKEN", "test-token-value")
    credential = provider.resolve(config)
    assert credential.get_secret_value() == "test-token-value"
    assert "test-token-value" not in repr(credential)
    assert "test-token-value" not in str(credential)
    assert credential.to_public_dict()["provider_id"] == "github_token"
    assert "secret" not in credential.to_public_dict()


def test_blank_environment_variable_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODESTRATA_TEST_TOKEN", "   ")
    provider = EnvironmentTokenProvider()
    with pytest.raises(CredentialUnavailableError):
        provider.resolve(
            RepositoryAuthenticationConfig(
                type=AuthenticationProviderType.GITHUB_TOKEN,
                token_env="CODESTRATA_TEST_TOKEN",
            )
        )


def test_environment_variable_name_is_not_the_credential() -> None:
    provider = EnvironmentTokenProvider()
    config = RepositoryAuthenticationConfig(
        type=AuthenticationProviderType.GITHUB_TOKEN,
        token_env="CODESTRATA_TEST_TOKEN",
    )
    with patch.dict(os.environ, {"CODESTRATA_TEST_TOKEN": "real-secret"}, clear=False):
        credential = provider.resolve(config)
    assert credential.get_secret_value() != "CODESTRATA_TEST_TOKEN"


def test_ssh_agent_provider_has_no_secret() -> None:
    provider = SshAgentProvider()
    credential = provider.resolve(
        RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT)
    )
    assert credential.method is AuthenticationMethod.SSH_AGENT
    assert credential.get_secret_value() is None
    assert provider.supports(
        "git@github.com:org/repo.git",
        RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT),
    )
    assert not provider.supports(
        "https://github.com/org/repo.git",
        RepositoryAuthenticationConfig(type=AuthenticationProviderType.SSH_AGENT),
    )
