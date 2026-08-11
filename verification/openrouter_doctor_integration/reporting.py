"""Assemble the SV.11.11 report."""

from __future__ import annotations

from pathlib import Path

from verification.openrouter_doctor_integration.contract import (
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
from verification.openrouter_doctor_integration.models import (
    CheckResult,
    OpenRouterDoctorIntegrationVerificationReport,
    ScenarioResult,
    build_check_counts,
    category_status,
)

NOTES: tuple[str, ...] = (
    "OpenRouter doctor readiness is local-only; no live OpenRouter calls.",
    "Mocked end-to-end integration uses injected clients only.",
    "AssessAIProviderRegistry retains bedrock/openai/openrouter (Decision B).",
    "Bedrock remains the default provider; credentials and models are not remotely validated.",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    if any(not check.ok for check in checks) or any(not scenario.ok for scenario in scenarios):
        return "fail"
    return "pass_with_limitations"


def build_status_fields(checks: list[CheckResult]) -> dict[str, str]:
    categories = (
        "doctor_policy",
        "readiness",
        "dependency",
        "credentials",
        "model",
        "base_url",
        "optional_header",
        "doctor_output",
        "doctor_exit",
        "integration_success",
        "integration_failure",
        "provider_selection",
        "fail_soft",
        "openai_regression",
        "bedrock_regression",
        "reporting_boundary",
        "privacy",
        "dependency_boundary",
        "determinism",
        "inventory",
    )
    return {category: category_status(checks, category) for category in categories}


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    warnings: tuple[str, ...] = (),
) -> OpenRouterDoctorIntegrationVerificationReport:
    return OpenRouterDoctorIntegrationVerificationReport(
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
