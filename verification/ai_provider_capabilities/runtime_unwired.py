"""Runtime-unwired checks: capability discovery/usage metadata change nothing about assess today."""

from __future__ import annotations

import importlib
from typing import Any

from codestrata.config.settings import AiSettings, BedrockSettings, OpenAISettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from verification.ai_provider_capabilities.contract import SLICE_11_5_NEW_MODULES
from verification.ai_provider_capabilities.models import CheckResult

_CAPABILITY_DOTTED_MODULES: tuple[str, ...] = tuple(
    f"codestrata.ai.provider_contracts.{name[: -len('.py')]}" for name in SLICE_11_5_NEW_MODULES
) + ("codestrata.ai.provider_contracts.usage",)


def check_importing_capability_modules_does_not_change_assess_registry() -> CheckResult:
    reset_assess_ai_provider_registry_for_tests()
    before = get_assess_ai_provider_registry().list_providers()
    for module_name in _CAPABILITY_DOTTED_MODULES:
        importlib.import_module(module_name)
    reset_assess_ai_provider_registry_for_tests()
    after = get_assess_ai_provider_registry().list_providers()
    ok = before == after == ("bedrock", "openai", "openrouter")
    reset_assess_ai_provider_registry_for_tests()
    return CheckResult(
        name="importing_capability_modules_does_not_change_assess_registry",
        category="runtime_unwired",
        ok=ok,
        detail=f"before={before} after={after}",
    )


def check_ai_settings_defaults_are_unchanged() -> CheckResult:
    for module_name in _CAPABILITY_DOTTED_MODULES:
        importlib.import_module(module_name)
    settings = AiSettings()
    ok = settings.provider == "bedrock" and settings.openai.answer_model == "gpt-4o-mini"
    return CheckResult(
        name="ai_settings_defaults_are_unchanged_after_importing_capability_modules",
        category="runtime_unwired",
        ok=ok,
        detail=f"provider={settings.provider!r} answer_model={settings.openai.answer_model!r}",
    )


def check_bedrock_and_openai_settings_declare_the_same_fields() -> CheckResult:
    """Slice 11.5 must not add/remove/rename any settings fields."""

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


def check_no_capability_module_defines_a_process_wide_registry() -> CheckResult:
    offenders: list[str] = []
    for module_name in _CAPABILITY_DOTTED_MODULES:
        module = importlib.import_module(module_name)
        public_names = {name for name in dir(module) if not name.startswith("_")}
        if any("registry" in name.lower() for name in public_names):
            offenders.append(module_name)
    ok = not offenders
    return CheckResult(
        name="no_capability_module_defines_a_process_wide_registry",
        category="runtime_unwired",
        ok=ok,
        detail=f"offenders={offenders}",
    )


def check_no_capability_module_mutates_the_shared_catalog_constants() -> CheckResult:
    """Re-importing the catalogs module must always yield the same, unmutated profiles."""

    from codestrata.ai.provider_contracts.capability_catalogs import (
        BEDROCK_CAPABILITY_PROFILE,
        OPENAI_CAPABILITY_PROFILE,
    )

    module = importlib.import_module("codestrata.ai.provider_contracts.capability_catalogs")
    ok = (
        module.BEDROCK_CAPABILITY_PROFILE is BEDROCK_CAPABILITY_PROFILE
        and module.OPENAI_CAPABILITY_PROFILE is OPENAI_CAPABILITY_PROFILE
    )
    return CheckResult(
        name="capability_catalog_constants_are_stable_singletons_across_imports",
        category="runtime_unwired",
        ok=ok,
        detail="re-importing capability_catalogs.py yields identical objects" if ok else "mismatch",
    )


def run_runtime_unwired_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_importing_capability_modules_does_not_change_assess_registry(),
        check_ai_settings_defaults_are_unchanged(),
        check_bedrock_and_openai_settings_declare_the_same_fields(),
        check_no_capability_module_defines_a_process_wide_registry(),
        check_no_capability_module_mutates_the_shared_catalog_constants(),
    ]
    matrix = {"capability_modules_checked": list(_CAPABILITY_DOTTED_MODULES)}
    return checks, matrix


__all__ = [
    "check_ai_settings_defaults_are_unchanged",
    "check_bedrock_and_openai_settings_declare_the_same_fields",
    "check_importing_capability_modules_does_not_change_assess_registry",
    "check_no_capability_module_defines_a_process_wide_registry",
    "check_no_capability_module_mutates_the_shared_catalog_constants",
    "run_runtime_unwired_checks",
]
