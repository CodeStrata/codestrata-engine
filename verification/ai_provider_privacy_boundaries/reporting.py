"""Assemble the SV.11.12 report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.ai_provider_privacy_boundaries.contract import (
    ALLOWED_VERDICTS,
    EPIC,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    PROVIDERS,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.ai_provider_privacy_boundaries.models import (
    AIProviderPrivacyBoundaryVerificationReport,
    CheckResult,
    ScenarioResult,
    build_check_counts,
    category_status,
)

NOTES: tuple[str, ...] = (
    "Privacy and failure-isolation verified across bedrock, openai, and openrouter.",
    "Mocked clients only; no live provider calls; no real credentials.",
    "AssessAIProviderRegistry retains Decision B; Bedrock remains default.",
    "Bedrock wrapper may log profile/region; OpenAI wrapper may log model_id — "
    "logs are not reports; diagnostics and verification reports omit values.",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    if any(not check.ok for check in checks) or any(not scenario.ok for scenario in scenarios):
        return "fail"
    return "pass_with_limitations"


def build_status_fields(checks: list[CheckResult]) -> dict[str, str]:
    categories = (
        "credential_privacy",
        "prompt_privacy",
        "response_privacy",
        "model_privacy",
        "error_privacy",
        "logging",
        "diagnostics",
        "configuration_boundary",
        "execution_boundary",
        "retry_safety",
        "failure_isolation",
        "assessment_authority",
        "reporting_boundary",
        "doctor_boundary",
        "cli_boundary",
        "telemetry_boundary",
        "analytics_boundary",
        "platform_boundary",
        "data_lake_boundary",
        "vscode_boundary",
        "cursor_boundary",
        "dependency_boundary",
        "packaging",
        "public_export",
        "registry",
        "determinism",
        "inventory",
        "provider_matrix",
        "safety",
    )
    return {category: category_status(checks, category) for category in categories}


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    provider_matrix: dict[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
) -> AIProviderPrivacyBoundaryVerificationReport:
    return AIProviderPrivacyBoundaryVerificationReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        epic=EPIC,
        slice_id=SLICE_ID,
        verdict=resolve_verdict(checks, scenarios),
        providers=PROVIDERS,
        limitations=EXPECTED_LIMITATIONS,
        checks=tuple(checks),
        negative_scenarios=tuple(scenarios),
        check_counts=build_check_counts(checks),
        status_fields=build_status_fields(checks),
        provider_matrix=provider_matrix or {},
        notes=NOTES,
        warnings=warnings,
        registry_decision=REGISTRY_DECISION,
        registry_decision_label=REGISTRY_DECISION_LABEL,
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
