"""Compatibility with the Slice 11.1 baseline (CR-1..CR-6) after the migration."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.compatibility import (
    build_contract_compatibility_statements,
)
from verification.openai_provider_migration.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    DEFAULT_PROVIDER,
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_REGISTERED_PROVIDERS,
    INVOKE_CALLS_PER_ASSESS_RUN,
    OPENAI_DEFAULT_ANSWER_MODEL,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from verification.openai_provider_migration.models import CheckResult


def check_baseline_defines_cr1_through_cr6() -> CheckResult:
    statements = build_contract_compatibility_statements()
    actual = tuple(sorted(item.requirement_id for item in statements))
    expected = tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))
    all_hold = all(item.holds for item in statements)
    return CheckResult(
        name="slice_11_1_baseline_still_defines_cr1_through_cr6",
        category="baseline_compatibility",
        ok=actual == expected and all_hold,
        detail=f"requirement_ids={list(actual)} all_hold={all_hold}",
    )


def check_default_provider_is_unchanged() -> CheckResult:
    from codestrata.config import CodestrataSettings

    settings = CodestrataSettings.model_validate({"repository": {"path": "."}})
    actual = settings.ai.provider
    return CheckResult(
        name="default_assess_provider_is_still_bedrock",
        category="baseline_compatibility",
        ok=actual == DEFAULT_PROVIDER,
        detail=f"default_provider={actual}",
    )


def check_openai_default_answer_model_is_unchanged() -> CheckResult:
    from codestrata.config.settings import OpenAISettings

    actual = OpenAISettings().answer_model
    return CheckResult(
        name="openai_default_answer_model_is_still_gpt_4o_mini",
        category="baseline_compatibility",
        ok=actual == OPENAI_DEFAULT_ANSWER_MODEL,
        detail=f"answer_model={actual}",
    )


def check_registered_providers_are_unchanged() -> CheckResult:
    from codestrata.extensions.assess_ai import (
        get_assess_ai_provider_registry,
        reset_assess_ai_provider_registry_for_tests,
    )

    reset_assess_ai_provider_registry_for_tests()
    try:
        actual = get_assess_ai_provider_registry().list_providers()
    finally:
        reset_assess_ai_provider_registry_for_tests()
    return CheckResult(
        name="assess_registry_lists_bedrock_openai_and_openrouter",
        category="baseline_compatibility",
        ok=tuple(actual) == EXPECTED_REGISTERED_PROVIDERS,
        detail=f"providers={list(actual)}",
    )


def check_openai_selection_returns_the_wrapper_class() -> CheckResult:
    from codestrata.ai.providers.factory import create_assess_ai_provider
    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
    from codestrata.config import CodestrataSettings

    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "openai", "openai": {}}}
    )
    provider = create_assess_ai_provider(settings)
    return CheckResult(
        name="selecting_openai_still_returns_the_public_wrapper_class",
        category="baseline_compatibility",
        ok=isinstance(provider, OpenAIAIModelProvider),
        detail=f"provider_class={type(provider).__name__}",
    )


def check_wrapper_constructor_signature_is_unchanged() -> CheckResult:
    import inspect

    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider

    expected = ["self", "settings", "openai_settings", "timeout_seconds", "client"]
    actual = list(inspect.signature(OpenAIAIModelProvider.__init__).parameters)
    return CheckResult(
        name="openai_wrapper_constructor_signature_is_unchanged",
        category="baseline_compatibility",
        ok=actual == expected,
        detail=f"parameters={actual}",
    )


def check_wrapper_still_implements_the_legacy_interface() -> CheckResult:
    from codestrata.ai.providers.base import AIModelProvider
    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider

    return CheckResult(
        name="openai_wrapper_still_implements_the_legacy_ai_model_provider_interface",
        category="baseline_compatibility",
        ok=issubclass(OpenAIAIModelProvider, AIModelProvider),
        detail="OpenAIAIModelProvider subclasses AIModelProvider",
    )


def check_assessment_schema_version_is_unchanged() -> CheckResult:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    return CheckResult(
        name="assessment_report_schema_version_is_still_1_2",
        category="baseline_compatibility",
        ok=ASSESSMENT_JSON_SCHEMA_VERSION == ASSESSMENT_SCHEMA_VERSION,
        detail=f"schema_version={ASSESSMENT_JSON_SCHEMA_VERSION}",
    )


def check_single_invoke_per_assess_run_is_preserved() -> CheckResult:
    """CR-1: one provider call per assess run, enforced by maximum_attempts=1."""

    from codestrata.ai.provider_adapters.openai.factory import OPENAI_RETRY_POLICY

    attempts = OPENAI_RETRY_POLICY.maximum_attempts
    ok = attempts == EXPECTED_MAXIMUM_ATTEMPTS == INVOKE_CALLS_PER_ASSESS_RUN
    return CheckResult(
        name="openai_executor_still_makes_exactly_one_attempt_per_invocation",
        category="baseline_compatibility",
        ok=ok,
        detail=f"maximum_attempts={attempts}",
    )


def check_declared_max_retries_is_still_not_wired() -> CheckResult:
    """``[ai.openai].max_retries`` stays diagnostic-only (CR-1 is unchanged)."""

    from codestrata.ai.provider_adapters.openai.configuration import build_runtime_configuration
    from codestrata.ai.provider_adapters.openai.factory import OPENAI_RETRY_POLICY
    from codestrata.config.settings import OpenAISettings

    settings = OpenAISettings(max_retries=3)
    runtime = build_runtime_configuration(openai_settings=settings)
    declared = runtime.adapter_configuration.max_retries
    ok = declared == 3 and OPENAI_RETRY_POLICY.maximum_attempts == 1
    return CheckResult(
        name="declared_openai_max_retries_is_still_not_wired_into_the_retry_policy",
        category="baseline_compatibility",
        ok=ok,
        detail=f"declared_max_retries={declared} maximum_attempts="
        f"{OPENAI_RETRY_POLICY.maximum_attempts}",
    )


def check_retained_module_helpers_still_exist() -> CheckResult:
    """SV.11.1 characterizes these module-level helpers by name."""

    from codestrata.ai.providers import openai_provider

    missing = [
        name
        for name in ("_chat_messages", "_extract_chat_response", "_map_openai_exception")
        if not hasattr(openai_provider, name)
    ]
    return CheckResult(
        name="openai_provider_module_retains_its_characterized_helper_functions",
        category="baseline_compatibility",
        ok=not missing,
        detail=f"missing={missing}",
    )


def check_wrapper_does_not_reference_retry_call() -> CheckResult:
    import inspect

    from codestrata.ai.providers import openai_provider

    source = inspect.getsource(openai_provider)
    return CheckResult(
        name="openai_provider_still_does_not_reference_the_unused_retry_call_helper",
        category="baseline_compatibility",
        ok="retry_call" not in source,
        detail="'retry_call' token absent from ai/providers/openai_provider.py",
    )


def run_baseline_compatibility_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_baseline_defines_cr1_through_cr6(),
        check_default_provider_is_unchanged(),
        check_openai_default_answer_model_is_unchanged(),
        check_registered_providers_are_unchanged(),
        check_openai_selection_returns_the_wrapper_class(),
        check_wrapper_constructor_signature_is_unchanged(),
        check_wrapper_still_implements_the_legacy_interface(),
        check_assessment_schema_version_is_unchanged(),
        check_single_invoke_per_assess_run_is_preserved(),
        check_declared_max_retries_is_still_not_wired(),
        check_retained_module_helpers_still_exist(),
        check_wrapper_does_not_reference_retry_call(),
    ]
    matrix: dict[str, Any] = {
        "assessment_schema_version": ASSESSMENT_SCHEMA_VERSION,
        "default_provider": DEFAULT_PROVIDER,
        "expected_maximum_attempts": EXPECTED_MAXIMUM_ATTEMPTS,
        "invoke_calls_per_assess_run": INVOKE_CALLS_PER_ASSESS_RUN,
        "openai_default_answer_model": OPENAI_DEFAULT_ANSWER_MODEL,
        "registered_providers": list(EXPECTED_REGISTERED_PROVIDERS),
    }
    return checks, matrix


__all__ = [
    "check_assessment_schema_version_is_unchanged",
    "check_baseline_defines_cr1_through_cr6",
    "check_declared_max_retries_is_still_not_wired",
    "check_default_provider_is_unchanged",
    "check_openai_default_answer_model_is_unchanged",
    "check_openai_selection_returns_the_wrapper_class",
    "check_registered_providers_are_unchanged",
    "check_retained_module_helpers_still_exist",
    "check_single_invoke_per_assess_run_is_preserved",
    "check_wrapper_constructor_signature_is_unchanged",
    "check_wrapper_does_not_reference_retry_call",
    "check_wrapper_still_implements_the_legacy_interface",
    "run_baseline_compatibility_checks",
]
