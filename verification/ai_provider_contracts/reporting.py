"""Assemble, sanitize, and verdict the Common AI Provider Contracts verification report."""

from __future__ import annotations

import re
from typing import Any

from codestrata.security.redaction import redact_secrets
from verification.ai_provider_contracts.contract import (
    EPIC,
    EXPECTED_LIMITATIONS,
    PACKAGE_DOTTED_NAME,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.ai_provider_contracts.models import (
    CheckResult,
    ContractVerificationReport,
    ScenarioResult,
    build_check_counts,
)

_PATH_PATTERNS = (
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
)

FORBIDDEN_REPORT_FRAGMENTS: tuple[str, ...] = (
    "/Users/",
    "/home/",
    "Authorization: Bearer",
    "-----BEGIN",
    "sk-proj-",
)

_CREDENTIAL_SHAPE_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
)


def sanitize_text(value: str) -> str:
    sanitized = redact_secrets(value)
    for pattern in _PATH_PATTERNS:
        sanitized = pattern.sub("[PATH_REDACTED]", sanitized)
    for pattern in _CREDENTIAL_SHAPE_PATTERNS:
        sanitized = pattern.sub("[CREDENTIAL_REDACTED]", sanitized)
    return sanitized


def report_contains_forbidden_leak(blob: str) -> list[str]:
    hits = [token for token in FORBIDDEN_REPORT_FRAGMENTS if token in blob]
    for pattern in _CREDENTIAL_SHAPE_PATTERNS:
        if pattern.search(blob):
            hits.append(pattern.pattern)
    return hits


def sanitize_structure(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {key: sanitize_structure(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_structure(item) for item in value]
    return value


def sanitize_check(check: CheckResult) -> CheckResult:
    return CheckResult(
        name=check.name,
        category=check.category,
        ok=check.ok,
        detail=sanitize_text(check.detail),
        evidence=sanitize_structure(check.evidence),
    )


def sanitize_scenario(scenario: ScenarioResult) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        title=sanitize_text(scenario.title),
        forbidden_condition=sanitize_text(scenario.forbidden_condition),
        ok=scenario.ok,
        detail=sanitize_text(scenario.detail),
    )


def compute_verdict(
    all_checks: list[CheckResult],
    scenarios: tuple[ScenarioResult, ...],
) -> str:
    failed_checks = [c for c in all_checks if not c.ok]
    failed_scenarios = [s for s in scenarios if not s.ok]
    if failed_checks or failed_scenarios:
        return "fail"
    # PASS_WITH_LIMITATIONS is expected/acceptable: the contracts are an
    # intentionally unwired foundation (see EXPECTED_LIMITATIONS).
    return "pass_with_limitations"


def assemble_report(
    *,
    all_checks: list[CheckResult],
    matrices: dict[str, Any],
    negative_scenarios: tuple[ScenarioResult, ...],
) -> ContractVerificationReport:
    sanitized_checks = tuple(sanitize_check(c) for c in all_checks)
    sanitized_matrices = sanitize_structure(matrices)
    sanitized_scenarios = tuple(sanitize_scenario(s) for s in negative_scenarios)
    verdict = compute_verdict(list(sanitized_checks), sanitized_scenarios)

    warnings: list[str] = [
        "codestrata.ai.provider_contracts is not called by any product path; this "
        "verification exercises the package directly, not through codestrata assess.",
        "No real provider network calls or credentials are used anywhere in this suite.",
    ]
    notes: list[str] = [
        "CodeStrata v0.2.0 Epic 11, Slice 11.2 — Common AI Provider Contracts. Defines "
        "unwired, SDK-free domain contracts for a possible future common provider platform.",
        "Does not migrate OpenAI or Bedrock, does not add OpenRouter, and does not wire "
        "these contracts into the assessment product path.",
        "Slice 11.3 (Standardized Provider and Model Configuration) later extended the "
        "same sibling package with configuration_* modules, verified separately by "
        "verification.ai_provider_configuration; this package's own checks are unchanged "
        "and still verify only the original Slice 11.2 module behavior.",
    ]

    return ContractVerificationReport(
        check_counts=build_check_counts(list(sanitized_checks)),
        checks=sanitized_checks,
        compatibility_requirement_ids=REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
        epic=EPIC,
        limitations=EXPECTED_LIMITATIONS,
        matrices=sanitized_matrices,
        negative_scenarios=sanitized_scenarios,
        notes=tuple(notes),
        package_dotted_name=PACKAGE_DOTTED_NAME,
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        slice_id=SLICE_ID,
        verdict=verdict,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        warnings=tuple(warnings),
    )


__all__ = [
    "FORBIDDEN_REPORT_FRAGMENTS",
    "assemble_report",
    "compute_verdict",
    "report_contains_forbidden_leak",
    "sanitize_check",
    "sanitize_scenario",
    "sanitize_structure",
    "sanitize_text",
]
