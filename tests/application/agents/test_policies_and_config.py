"""Policy and configuration tests for Agent Framework."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.agents.errors import AgentConfigurationError
from codestrata.application.agents.policies import AgentExecutionPolicy, policy_from_settings
from codestrata.config import load_settings


def test_default_policy_bounds() -> None:
    policy = AgentExecutionPolicy()
    assert policy.max_steps == 10
    assert policy.max_findings == 100
    assert policy.dependency_depth == 2
    assert policy.stop_on_blocking_validation is True


def test_invalid_policy_zero_rejected() -> None:
    with pytest.raises((ValidationError, AgentConfigurationError)):
        AgentExecutionPolicy(max_findings=0)


def test_dependency_depth_above_3_rejected() -> None:
    with pytest.raises((ValidationError, AgentConfigurationError)):
        AgentExecutionPolicy(dependency_depth=4)


def test_missing_agents_section_uses_defaults(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.agents.max_steps == 10
    assert settings.agents.dependency_depth == 2
    policy = policy_from_settings(settings)
    assert policy.max_recommendations == 100


def test_custom_agents_section(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"

        [agents]
        max_steps = 8
        max_findings = 50
        dependency_depth = 3
        stop_on_blocking_validation = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.agents.max_steps == 8
    assert settings.agents.max_findings == 50
    assert settings.agents.dependency_depth == 3
    assert settings.agents.stop_on_blocking_validation is False


def test_invalid_agents_toml_rejected(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"

        [agents]
        dependency_depth = 9
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_settings(config)
