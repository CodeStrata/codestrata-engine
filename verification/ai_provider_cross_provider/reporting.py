"""Assemble and persist the deterministic SV.11.8 report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.ai_provider_cross_provider.contract import (
    ALLOWED_VERDICTS,
    CANONICAL_PROVIDER_IDS,
    EPIC,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    REGISTRY_DECISION_RATIONALE,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.ai_provider_cross_provider.matrix import (
    intentional_differences,
    shared_guarantees,
)
from verification.ai_provider_cross_provider.models import (
    CheckResult,
    CrossProviderVerificationReport,
    ScenarioResult,
    build_check_counts,
    category_status,
)

NOTES: tuple[str, ...] = (
    "Both OpenAI and Bedrock are migrated onto Slice 11.2–11.5 contracts.",
    f"Registry decision {REGISTRY_DECISION} ({REGISTRY_DECISION_LABEL}): "
    f"{REGISTRY_DECISION_RATIONALE}",
    "AssessAIProviderRegistry remains authoritative for codestrata assess; "
    "compatibility wrappers remain; contracts AIProviderRegistry stays unwired.",
    "Intentional differences (JSON mode vs prompt instruction; API key vs AWS "
    "chain; Chat Completions vs Converse) are preserved, not normalized away.",
    "No live provider calls, credentials, or wall-clock waits occur in this suite.",
    "OpenRouter completed in Slices 11.9–11.11; see ai_provider_platform_completion.",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    if any(not check.ok for check in checks) or any(not scenario.ok for scenario in scenarios):
        return "fail"
    return "pass_with_limitations"


def build_status_fields(checks: list[CheckResult]) -> dict[str, str]:
    categories = (
        "provider_registry",
        "provider_selection",
        "configuration",
        "model_resolution",
        "authentication",
        "capabilities",
        "requests",
        "responses",
        "usage",
        "errors",
        "execution",
        "fail_soft",
        "doctor",
        "cli",
        "reporting_boundary",
        "privacy",
        "dependency_boundary",
        "openrouter_absent",
        "baseline_compatibility",
        "inventory",
    )
    return {category: category_status(checks, category) for category in categories}


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    matrices: dict[str, Any],
    warnings: tuple[str, ...] = (),
) -> CrossProviderVerificationReport:
    verdict = resolve_verdict(checks, scenarios)
    return CrossProviderVerificationReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        epic=EPIC,
        slice_id=SLICE_ID,
        verdict=verdict,
        providers=CANONICAL_PROVIDER_IDS,
        registry_decision=REGISTRY_DECISION,
        registry_decision_label=REGISTRY_DECISION_LABEL,
        compatibility_requirement_ids=REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
        matrices=matrices,
        negative_scenarios=tuple(scenarios),
        checks=tuple(checks),
        limitations=EXPECTED_LIMITATIONS,
        warnings=warnings,
        notes=NOTES,
        check_counts=build_check_counts(checks),
        shared_guarantees=shared_guarantees(),
        intentional_differences=intentional_differences(),
        status_fields=build_status_fields(checks),
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
