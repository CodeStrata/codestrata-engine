"""Assemble the SV.11.13 completion report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.ai_provider_platform_completion.contract import (
    ALLOWED_VERDICTS,
    COMPATIBILITY_REQUIREMENT_IDS,
    COMPLETED_SLICES,
    EPIC,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    PROVIDERS,
    DEFAULT_PROVIDER,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    RELEASE,
    RELEASE_POSTURE,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    START_EPIC_12,
    TOTAL_SLICES,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.ai_provider_platform_completion.models import (
    AIProviderPlatformCompletionVerificationReport,
    CheckResult,
    ScenarioResult,
    build_check_counts,
    category_status,
)

NOTES: tuple[str, ...] = (
    "Epic 11 complete: 13/13 slices verified for v0.2.0 release-readiness.",
    "Canonical providers: bedrock, openai, openrouter. Bedrock remains default.",
    "Registry Decision B: AssessAIProviderRegistry retained; contracts registry unwired.",
    "No live provider calls; no real credentials; Epic 12 not started.",
    "Worktree may contain uncommitted Epic 11 changes; no commit/tag/publish/deploy.",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    if any(not check.ok for check in checks) or any(not scenario.ok for scenario in scenarios):
        return "fail"
    return "pass_with_limitations"


def build_status_fields(checks: list[CheckResult]) -> dict[str, str]:
    categories = (
        "inventory",
        "slice_matrix",
        "provider_registry",
        "registry_decision",
        "policy_registry",
        "schema_registry",
        "configuration",
        "execution",
        "capabilities",
        "usage",
        "migrations",
        "openrouter",
        "doctor",
        "cli",
        "privacy",
        "failure_isolation",
        "reporting_boundary",
        "dependency_boundary",
        "packaging",
        "public_export",
        "documentation",
        "epic12_absence",
        "release_posture",
        "safety",
        "determinism",
    )
    return {category: category_status(checks, category) for category in categories}


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    slice_matrix: list[dict[str, Any]],
    provider_selection: dict[str, Any],
    policy_registry: dict[str, str],
    schema_registry: dict[str, str],
    release_posture: dict[str, bool] | None = None,
    warnings: tuple[str, ...] = (),
) -> AIProviderPlatformCompletionVerificationReport:
    return AIProviderPlatformCompletionVerificationReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        epic=EPIC,
        release=RELEASE,
        slice_id=SLICE_ID,
        verdict=resolve_verdict(checks, scenarios),
        completed_slices=COMPLETED_SLICES,
        total_slices=TOTAL_SLICES,
        start_epic_12=START_EPIC_12,
        providers=PROVIDERS,
        provider_default=DEFAULT_PROVIDER,
        provider_selection=provider_selection,
        registry_decision=REGISTRY_DECISION,
        registry_decision_label=REGISTRY_DECISION_LABEL,
        compatibility_requirements=COMPATIBILITY_REQUIREMENT_IDS,
        policy_registry=policy_registry,
        schema_registry=schema_registry,
        slice_matrix=tuple(slice_matrix),
        limitations=EXPECTED_LIMITATIONS,
        checks=tuple(checks),
        negative_scenarios=tuple(scenarios),
        check_counts=build_check_counts(checks),
        status_fields=build_status_fields(checks),
        release_posture=dict(sorted((release_posture or RELEASE_POSTURE).items())),
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
