"""Determinism tests: repeated projection/serialization must be byte-identical."""

from __future__ import annotations

from codestrata.ai.provider_contracts.configuration_projection import project_configuration
from codestrata.ai.provider_contracts.configuration_serialization import (
    serialize_configuration_for_diagnostics,
    serialize_configuration_private,
)
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput


def _sample_input() -> LegacyConfigurationInput:
    return LegacyConfigurationInput(
        provider="openai",
        cli_model_id="gpt-4o",
        openai_api_key_env_name="OPENAI_API_KEY",
        openai_api_key_present=True,
        openai_base_url_configured=True,
        timeout_seconds=45,
        max_retries=2,
        ai_requested=True,
    )


def test_project_configuration_is_deterministic_across_calls() -> None:
    first = project_configuration(_sample_input())
    second = project_configuration(_sample_input())
    first_diag = serialize_configuration_for_diagnostics(first)
    second_diag = serialize_configuration_for_diagnostics(second)
    assert first_diag == second_diag
    assert serialize_configuration_private(first) == serialize_configuration_private(second)


def test_serialized_diagnostic_output_has_sorted_keys() -> None:
    configuration = project_configuration(_sample_input())
    text = serialize_configuration_for_diagnostics(configuration)
    import json

    parsed = json.loads(text)
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_default_configuration_is_stable_across_repeated_resolution() -> None:
    default_input = LegacyConfigurationInput()
    outputs = {
        serialize_configuration_for_diagnostics(project_configuration(default_input))
        for _ in range(5)
    }
    assert len(outputs) == 1
