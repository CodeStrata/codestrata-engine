"""Configuration bridge: unchanged config keys, redacted views, no environment reads."""

from __future__ import annotations

import json
from types import SimpleNamespace

from codestrata.ai.provider_adapters.openai import configuration
from codestrata.ai.provider_adapters.openai.factory import OPENAI_RETRY_POLICY
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config.settings import OpenAISettings


def test_default_api_key_env_name_is_unchanged() -> None:
    assert configuration.DEFAULT_API_KEY_ENV_NAME == "OPENAI_API_KEY"
    assert configuration.resolve_api_key_env_name(None) == "OPENAI_API_KEY"
    assert configuration.resolve_api_key_env_name(OpenAISettings()) == "OPENAI_API_KEY"


def test_custom_api_key_env_name_is_honored() -> None:
    settings = OpenAISettings(api_key_env="MY_KEY_VAR")

    assert configuration.resolve_api_key_env_name(settings) == "MY_KEY_VAR"


def test_blank_api_key_env_name_falls_back_to_the_default() -> None:
    """Settings validation already forbids a blank name; the fallback is defensive."""

    assert (
        configuration.resolve_api_key_env_name(SimpleNamespace(api_key_env="   "))  # type: ignore[arg-type]
        == "OPENAI_API_KEY"
    )


def test_base_url_is_normalized_to_none_when_blank() -> None:
    assert configuration.resolve_base_url(None) is None
    assert configuration.resolve_base_url(OpenAISettings()) is None
    assert configuration.resolve_base_url(OpenAISettings(base_url="  ")) is None
    assert (
        configuration.resolve_base_url(OpenAISettings(base_url=" https://gw.internal "))
        == "https://gw.internal"
    )


def test_default_timeout_matches_the_pre_migration_default() -> None:
    runtime = configuration.build_runtime_configuration()

    assert runtime.client_inputs.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert DEFAULT_TIMEOUT_SECONDS == 60.0


def test_runtime_configuration_carries_client_inputs_and_adapter_configuration() -> None:
    runtime = configuration.build_runtime_configuration(
        openai_settings=OpenAISettings(api_key_env="MY_KEY_VAR", base_url="https://gw.internal"),
        timeout_seconds=42.0,
    )

    assert runtime.api_key_env_name == "MY_KEY_VAR"
    assert runtime.client_inputs.base_url == "https://gw.internal"
    assert runtime.client_inputs.timeout_seconds == 42.0
    assert runtime.adapter_configuration.api_key_env_name == "MY_KEY_VAR"


def test_api_key_presence_defaults_to_false_because_nothing_reads_the_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-be-read")

    runtime = configuration.build_runtime_configuration()

    assert runtime.adapter_configuration.api_key_present is False


def test_client_inputs_repr_hides_the_base_url() -> None:
    inputs = configuration.OpenAIClientInputs(
        api_key_env_name="OPENAI_API_KEY",
        base_url="https://private-gateway.example.internal/v1",
        timeout_seconds=60.0,
    )

    rendered = repr(inputs)

    assert "private-gateway" not in rendered
    assert "base_url_configured=True" in rendered
    assert "OPENAI_API_KEY" in rendered


def test_redacted_view_never_contains_the_base_url_value() -> None:
    runtime = configuration.build_runtime_configuration(
        openai_settings=OpenAISettings(base_url="https://private-gateway.example.internal/v1")
    )

    serialized = json.dumps(runtime.redacted(), sort_keys=True)

    assert "private-gateway" not in serialized
    assert '"base_url_configured": true' in serialized


def test_redacted_view_reports_max_retries_as_presence_only() -> None:
    runtime = configuration.build_runtime_configuration(
        openai_settings=OpenAISettings(max_retries=3)
    )

    view = runtime.redacted()

    assert view["max_retries_declared"] is True
    assert 3 not in view.values()


def test_declared_max_retries_is_not_wired_into_the_executor_policy() -> None:
    """``[ai.openai].max_retries`` stays diagnostic-only: CR-1 keeps one attempt."""

    runtime = configuration.build_runtime_configuration(
        openai_settings=OpenAISettings(max_retries=3)
    )

    assert runtime.adapter_configuration.max_retries == 3
    assert OPENAI_RETRY_POLICY.maximum_attempts == 1
