"""Assemble the SV.11.10 report."""

from __future__ import annotations

from pathlib import Path

from verification.openrouter_configuration.contract import (
    ALLOWED_VERDICTS,
    EPIC,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.openrouter_configuration.models import (
    CheckResult,
    OpenRouterConfigurationVerificationReport,
    ScenarioResult,
    build_check_counts,
    category_status,
)

NOTES: tuple[str, ...] = (
    "OpenRouter configuration and authentication are verified with injected mocked clients only.",
    "AssessAIProviderRegistry registers bedrock, openai, and openrouter (Decision B; explicit-only).",
    "Optional identification headers via site_url/app_name are implemented; doctor local readiness in 11.11.",
    "Bedrock remains the default provider; OpenRouter has no product model default.",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    if any(not check.ok for check in checks) or any(not scenario.ok for scenario in scenarios):
        return "fail"
    return "pass_with_limitations"


def build_status_fields(checks: list[CheckResult]) -> dict[str, str]:
    categories = (
        "provider_selection",
        "configuration",
        "model_resolution",
        "credentials",
        "base_url",
        "headers",
        "client_construction",
        "runtime_wiring",
        "fail_soft",
        "cli",
        "doctor",
        "openai_regression",
        "bedrock_regression",
        "privacy",
        "dependency_boundary",
        "inventory",
        "determinism",
    )
    return {category: category_status(checks, category) for category in categories}


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    warnings: tuple[str, ...] = (),
) -> OpenRouterConfigurationVerificationReport:
    return OpenRouterConfigurationVerificationReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        epic=EPIC,
        slice_id=SLICE_ID,
        verdict=resolve_verdict(checks, scenarios),
        limitations=EXPECTED_LIMITATIONS,
        checks=tuple(checks),
        negative_scenarios=tuple(scenarios),
        check_counts=build_check_counts(checks),
        status_fields=build_status_fields(checks),
        notes=NOTES,
        warnings=warnings,
    )


def report_directory(engine_root: Path) -> Path:
    return engine_root / OUTPUT_RELATIVE


def verdict_is_allowed(verdict: str) -> bool:
    return verdict in ALLOWED_VERDICTS


__all__ = [
    "NOTES",
    "build_report",
    "build_status_fields",
    "report_directory",
    "resolve_verdict",
    "verdict_is_allowed",
]
