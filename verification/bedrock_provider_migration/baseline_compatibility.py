"""Slice 11.1 baseline behavior the Bedrock migration must preserve exactly.

Everything here is asserted against the *live* migrated code, never against a
recorded fixture, so a drift shows up as a failing check rather than a stale
expectation.
"""

from __future__ import annotations

import inspect
from typing import Any

from codestrata.ai.providers import bedrock as wrapper_module
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS, ModelInvocationOptions
from codestrata.config.settings import BedrockSettings, CodestrataSettings
from verification.bedrock_provider_migration.contract import (
    BEDROCK_CONFIG_KEYS,
    BEDROCK_DEFAULT_MODEL_ID,
    BEDROCK_PROVIDER_NAME,
    DEFAULT_PROVIDER,
    EXPECTED_TIMEOUT_SECONDS,
    WRAPPER_CONSTRUCTOR_PARAMETERS,
    WRAPPER_REQUIRED_EXPORTS,
    WRAPPER_REQUIRED_PRIVATE_HELPERS,
)
from verification.bedrock_provider_migration.models import CheckResult


def wrapper_class() -> type:
    """Resolve the wrapper class from the live module, not an import-time alias.

    A test elsewhere in the suite reloads ``ai/providers/bedrock.py`` to prove
    no AWS client is built at import time, which replaces the class object.
    Reading it through the module keeps these checks order-independent.
    """

    return wrapper_module.BedrockAIModelProvider


def check_the_wrapper_keeps_its_public_surface() -> CheckResult:
    missing = sorted(
        name for name in WRAPPER_REQUIRED_EXPORTS if not hasattr(wrapper_module, name)
    )
    return CheckResult(
        name="the_bedrock_module_still_exports_its_pre_migration_public_surface",
        category="baseline_compatibility",
        ok=not missing,
        detail=f"missing_exports={missing}",
        evidence={"expected_exports": list(WRAPPER_REQUIRED_EXPORTS)},
    )


def check_the_wrapper_keeps_the_helpers_the_baseline_imports() -> CheckResult:
    """SV.11.1 imports these private helpers by name; both must still resolve."""

    missing = sorted(
        name for name in WRAPPER_REQUIRED_PRIVATE_HELPERS if not hasattr(wrapper_module, name)
    )
    return CheckResult(
        name="the_bedrock_module_still_exposes_the_helpers_the_baseline_suite_imports",
        category="baseline_compatibility",
        ok=not missing,
        detail=f"missing_helpers={missing}",
        evidence={"expected_helpers": list(WRAPPER_REQUIRED_PRIVATE_HELPERS)},
    )


def check_the_constructor_signature_is_unchanged() -> CheckResult:
    actual = tuple(inspect.signature(wrapper_class().__init__).parameters)
    return CheckResult(
        name="the_bedrock_provider_constructor_signature_is_unchanged",
        category="baseline_compatibility",
        ok=actual == WRAPPER_CONSTRUCTOR_PARAMETERS,
        detail=f"parameters={list(actual)}",
    )


def check_the_wrapper_still_implements_the_legacy_interface() -> CheckResult:
    return CheckResult(
        name="the_bedrock_wrapper_still_implements_the_legacy_ai_model_provider_interface",
        category="baseline_compatibility",
        ok=issubclass(wrapper_class(), AIModelProvider),
        detail="the enrichment seam is the legacy interface, not the contracts",
    )


def check_the_provider_name_is_unchanged() -> CheckResult:
    return CheckResult(
        name="the_bedrock_provider_name_constant_is_unchanged",
        category="baseline_compatibility",
        ok=wrapper_module.BEDROCK_PROVIDER_NAME == BEDROCK_PROVIDER_NAME,
        detail=f"provider_name={wrapper_module.BEDROCK_PROVIDER_NAME}",
    )


def check_the_default_provider_is_bedrock() -> CheckResult:
    settings = CodestrataSettings.model_validate({"repository": {"path": "."}})
    return CheckResult(
        name="an_unconfigured_run_still_selects_bedrock",
        category="baseline_compatibility",
        ok=settings.ai.provider == DEFAULT_PROVIDER,
        detail=f"default_provider={settings.ai.provider}",
    )


def check_the_default_model_id_is_unchanged() -> CheckResult:
    from codestrata.config import DEFAULT_BEDROCK_MODEL_ID

    return CheckResult(
        name="the_default_bedrock_model_id_is_still_amazon_nova_lite",
        category="baseline_compatibility",
        ok=DEFAULT_BEDROCK_MODEL_ID == BEDROCK_DEFAULT_MODEL_ID,
        detail=f"default_model_id={DEFAULT_BEDROCK_MODEL_ID}",
    )


def check_the_bedrock_config_keys_are_unchanged() -> CheckResult:
    actual = tuple(sorted(BedrockSettings.model_fields))
    return CheckResult(
        name="the_ai_bedrock_settings_block_keys_are_unchanged",
        category="baseline_compatibility",
        ok=actual == BEDROCK_CONFIG_KEYS,
        detail=f"config_keys={list(actual)}",
        evidence={"expected_keys": list(BEDROCK_CONFIG_KEYS)},
    )


def check_the_default_timeout_is_unchanged() -> CheckResult:
    ok = (
        DEFAULT_TIMEOUT_SECONDS == EXPECTED_TIMEOUT_SECONDS
        and BedrockSettings().timeout_seconds == int(EXPECTED_TIMEOUT_SECONDS)
    )
    return CheckResult(
        name="the_default_invocation_timeout_is_still_sixty_seconds",
        category="baseline_compatibility",
        ok=ok,
        detail=(
            f"models_default={DEFAULT_TIMEOUT_SECONDS} "
            f"settings_default={BedrockSettings().timeout_seconds}"
        ),
    )


def check_a_nonpositive_timeout_is_still_rejected_at_construction() -> CheckResult:
    """The one construction-time failure the migration deliberately kept."""

    from codestrata.ai.providers.exceptions import AIProviderConfigurationError

    try:
        wrapper_class()(timeout_seconds=0)
    except AIProviderConfigurationError as error:
        raised, message = True, str(error)
    else:
        raised, message = False, ""
    return CheckResult(
        name="a_nonpositive_timeout_still_raises_a_configuration_error_from_the_constructor",
        category="baseline_compatibility",
        ok=raised and message == "timeout_seconds must be positive",
        detail=f"raised={raised}",
    )


def check_an_empty_model_id_is_still_rejected_at_invoke() -> CheckResult:
    from codestrata.ai.providers.exceptions import AIProviderConfigurationError
    from verification.bedrock_provider_migration import fixtures

    provider = wrapper_class()(client=fixtures.Client())
    try:
        provider.invoke(fixtures.model_request(), ModelInvocationOptions(model_id="   "))
    except AIProviderConfigurationError as error:
        raised, message = True, str(error)
    else:
        raised, message = False, ""
    return CheckResult(
        name="a_blank_model_id_still_raises_a_configuration_error_from_invoke",
        category="baseline_compatibility",
        ok=raised and message == "model_id must be a nonempty string",
        detail=f"raised={raised}",
    )


def check_no_anthropic_payload_helper_was_reintroduced() -> CheckResult:
    """The pre-Converse Anthropic payload builders must stay removed."""

    offenders = sorted(
        name
        for name in ("ANTHROPIC_BEDROCK_VERSION", "build_anthropic_bedrock_payload")
        if hasattr(wrapper_module, name)
    )
    return CheckResult(
        name="no_anthropic_specific_payload_helper_was_reintroduced",
        category="baseline_compatibility",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def run_baseline_compatibility_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_wrapper_keeps_its_public_surface(),
        check_the_wrapper_keeps_the_helpers_the_baseline_imports(),
        check_the_constructor_signature_is_unchanged(),
        check_the_wrapper_still_implements_the_legacy_interface(),
        check_the_provider_name_is_unchanged(),
        check_the_default_provider_is_bedrock(),
        check_the_default_model_id_is_unchanged(),
        check_the_bedrock_config_keys_are_unchanged(),
        check_the_default_timeout_is_unchanged(),
        check_a_nonpositive_timeout_is_still_rejected_at_construction(),
        check_an_empty_model_id_is_still_rejected_at_invoke(),
        check_no_anthropic_payload_helper_was_reintroduced(),
    ]
    matrix: dict[str, Any] = {
        "bedrock_config_keys": list(BEDROCK_CONFIG_KEYS),
        "constructor_parameters": list(WRAPPER_CONSTRUCTOR_PARAMETERS),
        "default_model_id": BEDROCK_DEFAULT_MODEL_ID,
        "default_provider": DEFAULT_PROVIDER,
        "default_timeout_seconds": EXPECTED_TIMEOUT_SECONDS,
        "wrapper_exports": list(WRAPPER_REQUIRED_EXPORTS),
    }
    return checks, matrix


__all__ = [
    "check_a_nonpositive_timeout_is_still_rejected_at_construction",
    "check_an_empty_model_id_is_still_rejected_at_invoke",
    "check_no_anthropic_payload_helper_was_reintroduced",
    "check_the_bedrock_config_keys_are_unchanged",
    "check_the_constructor_signature_is_unchanged",
    "check_the_default_model_id_is_unchanged",
    "check_the_default_provider_is_bedrock",
    "check_the_default_timeout_is_unchanged",
    "check_the_provider_name_is_unchanged",
    "check_the_wrapper_keeps_its_public_surface",
    "check_the_wrapper_keeps_the_helpers_the_baseline_imports",
    "check_the_wrapper_still_implements_the_legacy_interface",
    "run_baseline_compatibility_checks",
    "wrapper_class",
]
