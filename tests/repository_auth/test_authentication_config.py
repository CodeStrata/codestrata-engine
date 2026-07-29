"""Tests for repository authentication configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.config import load_settings
from codestrata.repository_auth.models import (
    AuthenticationProviderType,
    RepositoryAuthenticationConfig,
)


def _auth_table(body: str) -> dict[str, object]:
    payload = tomllib.loads(f"[authentication]\n{body}")["authentication"]
    assert isinstance(payload, dict)
    return payload


def test_no_authentication_section(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.repository.authentication is None


def test_valid_github_token_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [repository.authentication]
        type = "github_token"
        token_env = "CODESTRATA_GITHUB_TOKEN"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.repository.authentication is not None
    assert settings.repository.authentication.type is AuthenticationProviderType.GITHUB_TOKEN
    assert settings.repository.authentication.token_env == "CODESTRATA_GITHUB_TOKEN"


def test_valid_ssh_agent_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "git@github.com:example/sample-app.git"

        [repository.authentication]
        type = "ssh_agent"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.repository.authentication is not None
    assert settings.repository.authentication.type is AuthenticationProviderType.SSH_AGENT


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ('type = "github_token"', "token_env"),
        ('type = "github_token"\ntoken_env = ""', "token_env"),
        ('type = "github_token"\ntoken_env = "123INVALID"', "environment-variable"),
        ('type = "oauth"', "type"),
        (
            'type = "github_token"\ntoken_env = "CODESTRATA_GITHUB_TOKEN"\ntoken = "ghp_secret"',
            "Extra inputs",
        ),
        (
            'type = "github_token"\ntoken_env = "CODESTRATA_GITHUB_TOKEN"\npassword = "secret"',
            "Extra inputs",
        ),
        ('type = "ssh_agent"\nprivate_key = "-----BEGIN"', "Extra inputs"),
    ],
)
def test_invalid_authentication_configuration(body: str, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        RepositoryAuthenticationConfig.model_validate(_auth_table(body))


def test_existing_codestrata_compatibility(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "https://github.com/spring-projects/spring-petclinic"
        branch = "main"

        [workspace]
        directory = ".codestrata/workspace"
        clean_before_clone = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.repository.authentication is None
    assert settings.repository.branch == "main"


def test_ssh_repository_url_accepted_in_settings(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        url = "ssh://git@github.com/example/sample-app.git"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert "github.com" in settings.repository.url
