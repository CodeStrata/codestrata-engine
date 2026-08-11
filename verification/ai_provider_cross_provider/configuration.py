"""Configuration, model resolution, authentication, and capability matrix checks."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.adapter_configuration import (
    BedrockAdapterConfiguration,
    OpenAIAdapterConfiguration,
)
from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.providers.factory import resolve_assess_model_id
from codestrata.config.settings import AiSettings, DEFAULT_BEDROCK_MODEL_ID
from verification.ai_provider_cross_provider.contract import (
    BEDROCK_DEFAULT_MODEL_ID,
    OPENAI_DEFAULT_ANSWER_MODEL,
)
from verification.ai_provider_cross_provider.fixtures import settings_for
from verification.ai_provider_cross_provider.models import CheckResult


def check_openai_adapter_configuration_redacts_secrets() -> CheckResult:
    config = OpenAIAdapterConfiguration(
        api_key_env_name="OPENAI_API_KEY",
        api_key_present=True,
        base_url="https://example.invalid/v1",
        base_url_configured=True,
        max_retries=3,
    )
    redacted = config.redacted()
    rendered = str(redacted)
    ok = (
        "https://example.invalid/v1" not in rendered
        and redacted.get("base_url_configured") is True
        and "api_key_present" in redacted
    )
    return CheckResult(
        name="openai_adapter_configuration_redacts_base_url_and_omits_key_values",
        category="configuration",
        ok=ok,
        detail="redacted view carries presence and env-name only",
    )


def check_bedrock_adapter_configuration_redacts_profile_region() -> CheckResult:
    config = BedrockAdapterConfiguration(
        region_configured=True,
        profile_configured=True,
        max_retries=3,
    )
    redacted = config.redacted()
    ok = (
        redacted.get("region_configured") is True
        and redacted.get("profile_configured") is True
        and "region" not in redacted
        and "profile" not in redacted
    )
    return CheckResult(
        name="bedrock_adapter_configuration_exposes_presence_booleans_only",
        category="configuration",
        ok=ok,
        detail="no profile/region string fields on redacted view",
    )


def check_adapter_configuration_types_are_isolated() -> CheckResult:
    openai = OpenAIAdapterConfiguration()
    bedrock = BedrockAdapterConfiguration()
    ok = type(openai) is not type(bedrock) and openai.redacted()["adapter_kind"] == "openai"
    return CheckResult(
        name="openai_and_bedrock_adapter_configurations_remain_separate_types",
        category="configuration",
        ok=ok,
        detail="no flattened shared config bag",
    )


def check_model_defaults() -> CheckResult:
    bedrock = resolve_assess_model_id(cli_model_id=None, settings=settings_for("bedrock"))
    openai = resolve_assess_model_id(cli_model_id=None, settings=settings_for("openai"))
    ok = (
        bedrock == BEDROCK_DEFAULT_MODEL_ID == DEFAULT_BEDROCK_MODEL_ID
        and openai == OPENAI_DEFAULT_ANSWER_MODEL
        and AiSettings().openai.answer_model == OPENAI_DEFAULT_ANSWER_MODEL
    )
    return CheckResult(
        name="provider_model_defaults_remain_nova_lite_and_gpt_4o_mini",
        category="model_resolution",
        ok=ok,
        detail="defaults match Slice 11.1 baseline constants",
        evidence={
            "bedrock_default_present": True,
            "openai_default_present": True,
            # Never emit the model string values into evidence that could leak
            # into reports as "custom fixture models" — only presence/equality.
            "bedrock_matches_constant": bedrock == BEDROCK_DEFAULT_MODEL_ID,
            "openai_matches_constant": openai == OPENAI_DEFAULT_ANSWER_MODEL,
        },
    )


def check_capability_profiles_share_advisor_and_differ_on_json() -> CheckResult:
    openai = OPENAI_CAPABILITY_PROFILE
    bedrock = BEDROCK_CAPABILITY_PROFILE
    ok = (
        openai.provider_id is ProviderId.OPENAI
        and bedrock.provider_id is ProviderId.BEDROCK
        and openai.supported_capability_ids == (CapabilityId.MODERNIZATION_ADVISOR,)
        and bedrock.supported_capability_ids == (CapabilityId.MODERNIZATION_ADVISOR,)
        and openai.supports_structured_json is True
        and bedrock.supports_structured_json is False
        and openai.supports_streaming is False
        and bedrock.supports_streaming is False
        and "prompt_instruction_only" in bedrock.limitations
    )
    return CheckResult(
        name="capability_profiles_share_advisor_and_differ_on_structured_json",
        category="capabilities",
        ok=ok,
        detail="OpenAI native JSON mode; Bedrock prompt-instruction only",
    )


def check_capability_discovery_is_static() -> CheckResult:
    # Re-importing catalogs must not construct clients; profiles are constants.
    from codestrata.ai.provider_contracts import capability_catalogs as catalogs

    ok = (
        catalogs.OPENAI_CAPABILITY_PROFILE is OPENAI_CAPABILITY_PROFILE
        and catalogs.BEDROCK_CAPABILITY_PROFILE is BEDROCK_CAPABILITY_PROFILE
    )
    return CheckResult(
        name="capability_catalogs_are_static_constants_without_network",
        category="capabilities",
        ok=ok,
        detail="discovery is catalog lookup only",
    )


def run_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_openai_adapter_configuration_redacts_secrets(),
        check_bedrock_adapter_configuration_redacts_profile_region(),
        check_adapter_configuration_types_are_isolated(),
    ]
    return checks, {"configuration_models": ["OpenAIAdapterConfiguration", "BedrockAdapterConfiguration"]}


def run_model_resolution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [check_model_defaults()]
    return checks, {
        "bedrock_default_constant": BEDROCK_DEFAULT_MODEL_ID == DEFAULT_BEDROCK_MODEL_ID,
        "openai_default_constant": OPENAI_DEFAULT_ANSWER_MODEL == "gpt-4o-mini",
    }


def run_capability_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_capability_profiles_share_advisor_and_differ_on_json(),
        check_capability_discovery_is_static(),
    ]
    matrix = {
        "openai": {
            "supports_structured_json": True,
            "supports_streaming": False,
            "capability": "modernization_advisor",
        },
        "bedrock": {
            "supports_structured_json": False,
            "supports_streaming": False,
            "structured_json_mechanism": "prompt_instruction_only",
            "capability": "modernization_advisor",
        },
    }
    return checks, matrix


def run_authentication_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    """Authentication mechanisms remain provider-specific; contracts hold no secrets."""

    from codestrata.ai.provider_contracts.adapter_configuration import (
        OpenAIAdapterConfiguration,
    )

    openai = OpenAIAdapterConfiguration(api_key_env_name="OPENAI_API_KEY", api_key_present=False)
    bedrock = BedrockAdapterConfiguration(profile_configured=False, region_configured=False)
    ok = (
        "api_key" not in openai.redacted()
        and openai.redacted().get("api_key_present") is False
        and "profile" not in bedrock.redacted()
    )
    check = CheckResult(
        name="common_configuration_objects_never_carry_credential_values",
        category="authentication",
        ok=ok,
        detail="OpenAI env-name/presence; Bedrock profile/region presence only",
    )
    return [check], {
        "openai_mechanism": "environment_variable_name",
        "bedrock_mechanism": "aws_default_credential_chain_and_optional_profile",
    }


__all__ = [
    "run_authentication_checks",
    "run_capability_checks",
    "run_configuration_checks",
    "run_model_resolution_checks",
]
