"""Tests for standalone configuration validators and project_configuration()."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_projection import project_configuration
from codestrata.ai.provider_contracts.configuration_validation import (
    validate_ai_provider_configuration,
    validate_configuration_is_unwired,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput


def test_validate_ai_provider_configuration_accepts_projected_configuration() -> None:
    configuration = project_configuration(LegacyConfigurationInput())
    validate_ai_provider_configuration(configuration)


def test_validate_ai_provider_configuration_rejects_non_configuration() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_ai_provider_configuration(object())  # type: ignore[arg-type]


def test_validate_configuration_is_unwired_accepts_projected_configuration() -> None:
    configuration = project_configuration(LegacyConfigurationInput())
    validate_configuration_is_unwired(configuration)


def test_project_configuration_rejects_wrong_input_type() -> None:
    with pytest.raises(TypeError):
        project_configuration({"provider": "bedrock"})  # type: ignore[arg-type]


def test_project_configuration_openai_end_to_end() -> None:
    input_data = LegacyConfigurationInput(
        provider="openai",
        cli_model_id=None,
        env_model_id="env-model-id",
        file_model_id="file-model-id",
        openai_api_key_env_name="OPENAI_API_KEY",
        openai_api_key_present=True,
        openai_base_url_configured=True,
        timeout_seconds=60,
        max_retries=3,
        ai_requested=True,
    )
    configuration = project_configuration(input_data)
    validate_ai_provider_configuration(configuration)
    assert configuration.model_reference.value == "env-model-id"
    assert configuration.adapter_configuration.api_key_present is True
    assert configuration.adapter_configuration.base_url_configured is True
    assert configuration.credential_requirements[0].credential_kind == "api_key"


def test_project_configuration_bedrock_with_profile_adds_second_credential() -> None:
    input_data = LegacyConfigurationInput(
        provider="bedrock", bedrock_profile_configured=True, bedrock_region_configured=True
    )
    configuration = project_configuration(input_data)
    kinds = {item.credential_kind for item in configuration.credential_requirements}
    assert kinds == {"aws_default_chain", "aws_profile"}
    assert configuration.adapter_configuration.region_configured is True
