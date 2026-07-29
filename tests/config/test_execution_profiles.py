"""Phase 5.20 execution profile unit and integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.config.effective import build_effective_settings
from codestrata.config.profiles import (
    PROFILE_ENV_VAR,
    ConfigurationProfileError,
    ExecutionProfile,
    merge_profile_configuration,
    resolve_profile_name,
    validate_profile_settings,
)
from codestrata.config.settings import CodestrataSettings, load_settings, load_settings_resolution


def _write_config(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_resolve_profile_precedence_cli_over_env_over_file() -> None:
    name, source = resolve_profile_name(
        cli_profile="bedrock",
        config_data={"profile": "openai"},
        environ={PROFILE_ENV_VAR: "local"},
    )
    assert name == "bedrock"
    assert source == "cli"

    name, source = resolve_profile_name(
        cli_profile=None,
        config_data={"profile": "openai"},
        environ={PROFILE_ENV_VAR: "local"},
    )
    assert name == "local"
    assert source == "environment"

    name, source = resolve_profile_name(
        cli_profile=None,
        config_data={"profile": "enterprise"},
        environ={},
    )
    assert name == "enterprise"
    assert source == "configuration"

    name, source = resolve_profile_name(
        cli_profile=None,
        config_data={},
        environ={},
    )
    assert name == "community"
    assert source == "default"


def test_execution_alias_profile_in_toml() -> None:
    merged, profile, source = merge_profile_configuration(
        {"execution": {"profile": "local"}, "repository": {"path": "."}},
        environ={},
    )
    assert profile == "local"
    assert source == "configuration"
    assert merged["profile"] == "local"
    assert merged["ai"]["embedding_provider"] == "deterministic"


def test_toml_overrides_profile_defaults() -> None:
    merged, profile, _source = merge_profile_configuration(
        {
            "profile": "community",
            "repository": {"path": "."},
            "enterprise": {"enabled": True},
        },
        environ={},
    )
    assert profile == "community"
    assert merged["enterprise"]["enabled"] is True


def test_env_overlays_override_toml(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "community"
        [repository]
        path = "."
        [ai.bedrock]
        model_id = "from-toml"
        """,
    )
    settings = load_settings(
        config,
        environ={
            "CODESTRATA_BEDROCK_MODEL_ID": "from-env",
        },
    )
    assert settings.ai.bedrock.model_id == "from-env"


def test_load_settings_defaults_to_community(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        [repository]
        path = "."
        """,
    )
    settings = load_settings(config, environ={})
    assert settings.profile == ExecutionProfile.COMMUNITY
    assert settings.enterprise.enabled is False
    assert settings.ai.embedding_provider == "deterministic"


def test_enterprise_profile_enables_enterprise(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "enterprise"
        [repository]
        path = "."
        """,
    )
    settings = load_settings(config, environ={})
    assert settings.profile == "enterprise"
    assert settings.enterprise.enabled is True


def test_local_rejects_openai_embedding(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "local"
        [repository]
        path = "."
        [ai]
        embedding_provider = "openai"
        answer_provider = "deterministic_extractive"
        """,
    )
    with pytest.raises(ConfigurationProfileError, match="deterministic embedding"):
        load_settings(config, environ={})


def test_bedrock_requires_region(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "bedrock"
        [repository]
        path = "."
        """,
    )
    with pytest.raises(ConfigurationProfileError, match="AWS region"):
        load_settings(config, environ={})


def test_bedrock_accepts_region_from_env(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "bedrock"
        [repository]
        path = "."
        """,
    )
    settings = load_settings(config, environ={"AWS_REGION": "us-east-1"})
    assert settings.profile == "bedrock"
    assert settings.ai.embedding_provider == "bedrock"


def test_openai_profile_and_strict_key_check(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "openai"
        [repository]
        path = "."
        """,
    )
    settings, active, _source, issues = load_settings_resolution(
        config,
        validate_profile=True,
        strict=False,
        environ={},
    )
    assert active == "openai"
    assert settings.ai.embedding_provider == "openai"
    assert settings.ai.openai.api_key_env == "OPENAI_API_KEY"
    assert not any(item.severity == "error" for item in issues)

    strict_issues = validate_profile_settings(
        settings, profile="openai", strict=True, environ={}
    )
    assert any(item.code == "openai_api_key_absent" for item in strict_issues)


def test_effective_settings_never_includes_secrets(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "openai"
        [repository]
        path = "."
        [knowledge.vector_store]
        connection_string = "postgresql://user:super-secret@localhost/db"
        """,
    )
    settings = load_settings(
        config,
        environ={"OPENAI_API_KEY": "sk-secret-value-do-not-leak"},
    )
    effective = build_effective_settings(
        settings,
        profile=settings.profile,
        profile_source="configuration",
        environ={"OPENAI_API_KEY": "sk-secret-value-do-not-leak"},
    )
    dumped = json.dumps(effective)
    assert "sk-secret-value-do-not-leak" not in dumped
    assert "super-secret" not in dumped
    assert effective["ai"]["openai"]["api_key_env"] == "OPENAI_API_KEY"
    assert effective["ai"]["openai"]["api_key_present"] is True
    assert effective["knowledge"]["vector_store"]["connection_configured"] is True


def test_cli_config_profile_and_validate(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        [repository]
        path = "."
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["config", "profile", "--config", str(config)],
        env={
            "CODESTRATA_PROFILE": None,
            "AWS_PROFILE": None,
            "AWS_REGION": None,
            "AWS_DEFAULT_REGION": None,
        },
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["profile"] == "community"
    assert payload["source"] == "default"

    result = runner.invoke(
        app,
        ["config", "validate", "--config", str(config), "--profile", "local"],
        env={
            "CODESTRATA_PROFILE": None,
            "AWS_PROFILE": None,
            "AWS_REGION": None,
            "AWS_DEFAULT_REGION": None,
        },
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["profile"] == "local"

    result = runner.invoke(
        app,
        ["config", "effective", "--config", str(config), "--profile", "enterprise"],
        env={
            "CODESTRATA_PROFILE": None,
            "AWS_PROFILE": None,
            "AWS_REGION": None,
            "AWS_DEFAULT_REGION": None,
        },
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["profile"]["name"] == "enterprise"
    assert payload["enterprise"]["enabled"] is True


def test_cli_config_validate_rejects_bad_bedrock(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "codestrata.toml",
        """
        profile = "bedrock"
        [repository]
        path = "."
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["config", "validate", "--config", str(config)],
        env={
            "CODESTRATA_PROFILE": None,
            "AWS_PROFILE": None,
            "AWS_REGION": None,
            "AWS_DEFAULT_REGION": None,
        },
    )
    assert result.exit_code == 1
    assert "AWS region" in result.output


def test_model_validate_without_profile_remains_backward_compatible() -> None:
    settings = CodestrataSettings.model_validate({"repository": {"path": "."}})
    assert settings.profile == "community"
    assert settings.ai.provider == "bedrock"
