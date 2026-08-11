"""Build an ``AIProviderConfiguration`` from an injected ``LegacyConfigurationInput``.

This is the one place in the configuration package that assembles every
other piece — provider/model resolution, adapter configuration, credential
requirements, and source trace — into the final immutable
``AIProviderConfiguration``. Like every other function in this package, it
takes only already-extracted plain values (via ``LegacyConfigurationInput``)
and performs no filesystem access, no environment variable reads, and
constructs no provider client.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.adapter_configuration import (
    build_bedrock_adapter_configuration,
    build_openai_adapter_configuration,
)
from codestrata.ai.provider_contracts.configuration_models import (
    AIProviderConfiguration,
    ProviderCredentialRequirement,
)
from codestrata.ai.provider_contracts.configuration_policy import CONTRACT_VERSION
from codestrata.ai.provider_contracts.configuration_sources import FieldSource, SourceCategory
from codestrata.ai.provider_contracts.configuration_validation import (
    validate_ai_provider_configuration,
)
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput
from codestrata.ai.provider_contracts.model_configuration import (
    resolve_model_reference,
    resolve_provider_id,
)
from codestrata.ai.provider_contracts.requests import ExecutionOptions

# Slice 11.3 always represents an unwired configuration snapshot. These four
# limitations are recorded on every AIProviderConfiguration this module
# builds; see engine/docs/ai-provider-configuration.md for what each means.
UNWIRED_LIMITATIONS: tuple[str, ...] = (
    "configuration_not_wired",
    "providers_not_migrated",
    "credential_resolution_deferred",
    "timeout_retry_execution_deferred",
)


def _build_execution_options(input_data: LegacyConfigurationInput) -> ExecutionOptions:
    timeout_seconds = (
        float(input_data.timeout_seconds) if input_data.timeout_seconds is not None else None
    )
    return ExecutionOptions(timeout_seconds=timeout_seconds)


def _build_credential_requirements(
    provider_id: ProviderId, input_data: LegacyConfigurationInput
) -> tuple[ProviderCredentialRequirement, ...]:
    if provider_id is ProviderId.OPENAI:
        return (
            ProviderCredentialRequirement(
                provider_id=ProviderId.OPENAI,
                credential_kind="api_key",
                required=True,
                source_category=SourceCategory.ENVIRONMENT,
                availability_status=(
                    "present" if input_data.openai_api_key_present else "absent"
                ),
            ),
        )

    requirements = [
        ProviderCredentialRequirement(
            provider_id=ProviderId.BEDROCK,
            credential_kind="aws_default_chain",
            required=True,
            source_category=SourceCategory.DEFAULT,
            availability_status="unknown",
        ),
    ]
    if input_data.bedrock_profile_configured:
        requirements.append(
            ProviderCredentialRequirement(
                provider_id=ProviderId.BEDROCK,
                credential_kind="aws_profile",
                required=False,
                source_category=SourceCategory.CONFIGURATION_FILE,
                availability_status="present",
            )
        )
    return tuple(requirements)


def project_configuration(input_data: LegacyConfigurationInput) -> AIProviderConfiguration:
    """Build the resolved ``AIProviderConfiguration`` for ``input_data``.

    Mirrors, as pure data transformation, the real resolution order used by
    ``create_assess_ai_provider``/``resolve_assess_model_id``: provider
    selection first, then model resolution for that provider, then the
    provider-specific adapter configuration and credential requirements.
    """

    if not isinstance(input_data, LegacyConfigurationInput):
        raise TypeError(
            f"input_data must be a LegacyConfigurationInput, got {type(input_data).__name__}"
        )

    provider_id, provider_source = resolve_provider_id(file_provider=input_data.provider)
    model_reference, model_source = resolve_model_reference(
        provider_id=provider_id,
        cli_model_id=input_data.cli_model_id,
        env_model_id=input_data.env_model_id,
        file_model_id=input_data.file_model_id,
    )

    if provider_id is ProviderId.OPENAI:
        adapter_configuration = build_openai_adapter_configuration(
            api_key_env_name=input_data.openai_api_key_env_name,
            api_key_present=input_data.openai_api_key_present,
            base_url_configured=input_data.openai_base_url_configured,
            max_retries=input_data.max_retries,
        )
    else:
        adapter_configuration = build_bedrock_adapter_configuration(
            region_configured=input_data.bedrock_region_configured,
            profile_configured=input_data.bedrock_profile_configured,
            max_retries=input_data.max_retries,
        )

    configuration = AIProviderConfiguration(
        configuration_version=CONTRACT_VERSION,
        provider_id=provider_id,
        model_reference=model_reference,
        capability_id=CapabilityId.MODERNIZATION_ADVISOR,
        execution_options=_build_execution_options(input_data),
        adapter_configuration=adapter_configuration,
        source_trace=(
            FieldSource("provider_id", provider_source),
            FieldSource("model_reference", model_source),
        ),
        credential_requirements=_build_credential_requirements(provider_id, input_data),
        limitations=UNWIRED_LIMITATIONS,
        ai_requested=input_data.ai_requested,
    )
    validate_ai_provider_configuration(configuration)
    return configuration


__all__ = [
    "UNWIRED_LIMITATIONS",
    "project_configuration",
]
