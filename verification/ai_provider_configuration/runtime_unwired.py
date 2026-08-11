"""Runtime-unwired checks: the configuration package changes nothing about assess today."""

from __future__ import annotations

import importlib
from typing import Any

from codestrata.config.settings import AiSettings, BedrockSettings, OpenAISettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from verification.ai_provider_configuration.contract import SLICE_11_3_NEW_MODULES
from verification.ai_provider_configuration.models import CheckResult

_CONFIGURATION_DOTTED_MODULES: tuple[str, ...] = tuple(
    f"codestrata.ai.provider_contracts.{name[: -len('.py')]}" for name in SLICE_11_3_NEW_MODULES
)


def check_importing_configuration_modules_does_not_change_assess_registry() -> CheckResult:
    reset_assess_ai_provider_registry_for_tests()
    before = get_assess_ai_provider_registry().list_providers()
    for module_name in _CONFIGURATION_DOTTED_MODULES:
        importlib.import_module(module_name)
    reset_assess_ai_provider_registry_for_tests()
    after = get_assess_ai_provider_registry().list_providers()
    ok = before == after == ("bedrock", "openai", "openrouter")
    reset_assess_ai_provider_registry_for_tests()
    return CheckResult(
        name="importing_configuration_modules_does_not_change_assess_registry",
        category="runtime_unwired",
        ok=ok,
        detail=f"before={before} after={after}",
    )


def check_ai_settings_defaults_are_unchanged() -> CheckResult:
    for module_name in _CONFIGURATION_DOTTED_MODULES:
        importlib.import_module(module_name)
    settings = AiSettings()
    ok = settings.provider == "bedrock" and settings.openai.answer_model == "gpt-4o-mini"
    return CheckResult(
        name="ai_settings_defaults_are_unchanged_after_importing_configuration_modules",
        category="runtime_unwired",
        ok=ok,
        detail=f"provider={settings.provider!r} answer_model={settings.openai.answer_model!r}",
    )


def check_bedrock_and_openai_settings_declare_the_same_timeout_retry_fields() -> CheckResult:
    """Slice 11.3 must not add/remove/rename any settings fields."""

    bedrock_fields = set(BedrockSettings.model_fields)
    openai_fields = set(OpenAISettings.model_fields)
    ok = (
        {"timeout_seconds", "max_retries"} <= bedrock_fields
        and {"timeout_seconds", "max_retries"} <= openai_fields
    )
    return CheckResult(
        name="bedrock_and_openai_settings_still_declare_timeout_and_max_retries_fields",
        category="runtime_unwired",
        ok=ok,
        detail=f"bedrock_fields={sorted(bedrock_fields)} openai_fields={sorted(openai_fields)}",
    )


def check_no_configuration_module_defines_a_process_wide_registry() -> CheckResult:
    offenders: list[str] = []
    for module_name in _CONFIGURATION_DOTTED_MODULES:
        module = importlib.import_module(module_name)
        public_names = {name for name in dir(module) if not name.startswith("_")}
        if any("registry" in name.lower() for name in public_names):
            offenders.append(module_name)
    ok = not offenders
    return CheckResult(
        name="no_configuration_module_defines_a_process_wide_registry",
        category="runtime_unwired",
        ok=ok,
        detail=f"offenders={offenders}",
    )


def run_runtime_unwired_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_importing_configuration_modules_does_not_change_assess_registry(),
        check_ai_settings_defaults_are_unchanged(),
        check_bedrock_and_openai_settings_declare_the_same_timeout_retry_fields(),
        check_no_configuration_module_defines_a_process_wide_registry(),
    ]
    matrix = {"configuration_modules_checked": list(_CONFIGURATION_DOTTED_MODULES)}
    return checks, matrix


__all__ = [
    "check_ai_settings_defaults_are_unchanged",
    "check_bedrock_and_openai_settings_declare_the_same_timeout_retry_fields",
    "check_importing_configuration_modules_does_not_change_assess_registry",
    "check_no_configuration_module_defines_a_process_wide_registry",
    "run_runtime_unwired_checks",
]
