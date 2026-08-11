"""Tests for AIProviderConfiguration / ProviderCredentialRequirement."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.adapter_configuration import (
    BedrockAdapterConfiguration,
    OpenAIAdapterConfiguration,
)
from codestrata.ai.provider_contracts.configuration_models import (
    AIProviderConfiguration,
    ProviderCredentialRequirement,
)
from codestrata.ai.provider_contracts.configuration_projection import UNWIRED_LIMITATIONS
from codestrata.ai.provider_contracts.configuration_sources import FieldSource, SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import ExecutionOptions


def _valid_bedrock_kwargs() -> dict[str, object]:
    return {
        "configuration_version": "1.0",
        "provider_id": ProviderId.BEDROCK,
        "model_reference": ProviderModelReference("amazon.nova-lite-v1:0"),
        "capability_id": CapabilityId.MODERNIZATION_ADVISOR,
        "execution_options": ExecutionOptions(),
        "adapter_configuration": BedrockAdapterConfiguration(),
        "source_trace": (
            FieldSource("provider_id", SourceCategory.DEFAULT),
            FieldSource("model_reference", SourceCategory.DEFAULT),
        ),
        "credential_requirements": (
            ProviderCredentialRequirement(
                provider_id=ProviderId.BEDROCK,
                credential_kind="aws_default_chain",
                required=True,
                source_category=SourceCategory.DEFAULT,
                availability_status="unknown",
            ),
        ),
        "limitations": UNWIRED_LIMITATIONS,
    }


def test_valid_configuration_constructs() -> None:
    configuration = AIProviderConfiguration(**_valid_bedrock_kwargs())
    assert configuration.provider_id is ProviderId.BEDROCK
    assert configuration.ai_requested is None


def test_configuration_rejects_adapter_provider_mismatch() -> None:
    kwargs = {**_valid_bedrock_kwargs(), "adapter_configuration": OpenAIAdapterConfiguration()}
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)


def test_configuration_rejects_missing_provider_id_source_trace() -> None:
    kwargs = {
        **_valid_bedrock_kwargs(),
        "source_trace": (FieldSource("model_reference", SourceCategory.DEFAULT),),
    }
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)


def test_configuration_rejects_missing_model_reference_source_trace() -> None:
    kwargs = {
        **_valid_bedrock_kwargs(),
        "source_trace": (FieldSource("provider_id", SourceCategory.DEFAULT),),
    }
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)


def test_configuration_rejects_credential_requirement_provider_mismatch() -> None:
    kwargs = {
        **_valid_bedrock_kwargs(),
        "credential_requirements": (
            ProviderCredentialRequirement(
                provider_id=ProviderId.OPENAI,
                credential_kind="api_key",
                required=True,
                source_category=SourceCategory.ENVIRONMENT,
                availability_status="present",
            ),
        ),
    }
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)


def test_configuration_rejects_empty_limitations() -> None:
    kwargs = {**_valid_bedrock_kwargs(), "limitations": ()}
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)


def test_configuration_rejects_unsupported_configuration_version() -> None:
    kwargs = {**_valid_bedrock_kwargs(), "configuration_version": "99.0"}
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)


def test_configuration_ai_requested_accepts_bool_or_none() -> None:
    kwargs = {**_valid_bedrock_kwargs(), "ai_requested": True}
    configuration = AIProviderConfiguration(**kwargs)
    assert configuration.ai_requested is True


def test_configuration_ai_requested_rejects_non_bool() -> None:
    kwargs = {**_valid_bedrock_kwargs(), "ai_requested": "yes"}
    with pytest.raises(ProviderContractValidationError):
        AIProviderConfiguration(**kwargs)  # type: ignore[arg-type]


def test_provider_credential_requirement_rejects_unknown_credential_kind() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCredentialRequirement(
            provider_id=ProviderId.OPENAI,
            credential_kind="oauth_token",
            required=True,
            source_category=SourceCategory.ENVIRONMENT,
            availability_status="present",
        )


def test_provider_credential_requirement_rejects_unknown_availability_status() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderCredentialRequirement(
            provider_id=ProviderId.OPENAI,
            credential_kind="api_key",
            required=True,
            source_category=SourceCategory.ENVIRONMENT,
            availability_status="maybe",
        )


def test_configuration_is_immutable() -> None:
    configuration = AIProviderConfiguration(**_valid_bedrock_kwargs())
    with pytest.raises(AttributeError):
        configuration.provider_id = ProviderId.OPENAI  # type: ignore[misc]
