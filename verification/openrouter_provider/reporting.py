"""Assemble the SV.11.9 report."""

from __future__ import annotations

from pathlib import Path

from verification.openrouter_provider.contract import (
    ALLOWED_VERDICTS,
    COMMON_CONTRACT_COMPATIBILITY_DECISION,
    EPIC,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.openrouter_provider.models import (
    CheckResult,
    OpenRouterProviderVerificationReport,
    ScenarioResult,
    build_check_counts,
    category_status,
)

NOTES: tuple[str, ...] = (
    "OpenRouter adapter implements provider-platform contracts with an injected mocked client.",
    "AssessAIProviderRegistry registers bedrock, openai, and openrouter (Decision B; explicit-only).",
    "Configuration and authentication live in Slice 11.10; doctor local readiness in Slice 11.11.",
    f"Common-contract decision: {COMMON_CONTRACT_COMPATIBILITY_DECISION}",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    if any(not check.ok for check in checks) or any(not scenario.ok for scenario in scenarios):
        return "fail"
    return "pass_with_limitations"


def build_status_fields(checks: list[CheckResult]) -> dict[str, str]:
    categories = (
        "provider_identity",
        "configuration",
        "capabilities",
        "client_boundary",
        "requests",
        "responses",
        "usage",
        "errors",
        "execution",
        "registration",
        "doctor",
        "openai_regression",
        "bedrock_regression",
        "privacy",
        "dependency_boundary",
        "inventory",
    )
    return {category: category_status(checks, category) for category in categories}


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    warnings: tuple[str, ...] = (),
) -> OpenRouterProviderVerificationReport:
    return OpenRouterProviderVerificationReport(
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
        common_contract_compatibility_decision=COMMON_CONTRACT_COMPATIBILITY_DECISION,
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
