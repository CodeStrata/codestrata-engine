"""Assemble, sanitize, and verdict the OpenAI Provider Migration report."""

from __future__ import annotations

import re
from typing import Any

from codestrata.security.redaction import redact_secrets
from verification.openai_provider_migration.contract import (
    ALLOWED_VERDICTS,
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
from verification.openai_provider_migration.models import (
    CheckResult,
    OpenAIMigrationVerificationReport,
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
    re.compile(r"\bsk-[A-Za-z0-9\-]{20,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
)

WARNINGS: tuple[str, ...] = (
    "Only OpenAI is migrated onto the Slice 11.2-11.5 provider contracts; Bedrock "
    "remains on the legacy path, so the engine runs in mixed mode.",
    "No real provider network call, credential, or wall-clock wait occurs anywhere in "
    "this suite: every execution goes through an injected in-memory client.",
    "The pinned retry policy allows exactly one attempt, so the retryable error "
    "categories are classified but never acted on by default.",
    "ai/providers/doctor.py is unchanged and still resolves OpenAI configuration "
    "itself rather than asking the migrated adapter.",
)

NOTES: tuple[str, ...] = (
    "CodeStrata v0.2.0 Epic 11, Slice 11.6 - OpenAI Provider Migration. "
    "OpenAIAIModelProvider remains the public assess-path class and becomes a thin "
    "compatibility wrapper over an AIProvider adapter run by AIProviderExecutor.",
    "Preserved exactly: the bedrock default, provider selection precedence, the "
    "[ai.openai] config keys, the gpt-4o-mini default, the prompt content byte for "
    "byte, assessment report schema 1.2, the Findings/Recommendations surface, and "
    "the CLI exit behavior.",
    "Not done here: Bedrock migration, OpenRouter, operational retry activation, and "
    "any change to telemetry, analytics, the Cloud API, the Data Lake, the VS Code or "
    "Cursor extensions, or infrastructure.",
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
    all_checks: list[CheckResult], scenarios: tuple[ScenarioResult, ...]
) -> str:
    """Return the verdict. ``pass_with_limitations`` is the expected success value.

    The recorded limitations are intentional and permanent for this slice
    (mixed mode, a single attempt, an unmigrated doctor), so a fully clean run
    is still reported as ``pass_with_limitations`` rather than ``pass``.
    """

    if any(not check.ok for check in all_checks) or any(not s.ok for s in scenarios):
        return "fail"
    return "pass_with_limitations"


def assemble_report(
    *,
    all_checks: list[CheckResult],
    matrices: dict[str, Any],
    negative_scenarios: tuple[ScenarioResult, ...],
) -> OpenAIMigrationVerificationReport:
    sanitized_checks = tuple(sanitize_check(check) for check in all_checks)
    sanitized_matrices = sanitize_structure(matrices)
    sanitized_scenarios = tuple(sanitize_scenario(s) for s in negative_scenarios)
    verdict = compute_verdict(list(sanitized_checks), sanitized_scenarios)
    if verdict not in ALLOWED_VERDICTS and verdict != "fail":
        raise RuntimeError(f"computed verdict {verdict!r} is not an allowed verdict")

    return OpenAIMigrationVerificationReport(
        check_counts=build_check_counts(list(sanitized_checks)),
        checks=sanitized_checks,
        compatibility_requirement_ids=REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
        epic=EPIC,
        limitations=EXPECTED_LIMITATIONS,
        matrices=sanitized_matrices,
        negative_scenarios=sanitized_scenarios,
        notes=NOTES,
        package_dotted_name=PACKAGE_DOTTED_NAME,
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        slice_id=SLICE_ID,
        verdict=verdict,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        warnings=WARNINGS,
    )


__all__ = [
    "FORBIDDEN_REPORT_FRAGMENTS",
    "NOTES",
    "WARNINGS",
    "assemble_report",
    "compute_verdict",
    "report_contains_forbidden_leak",
    "sanitize_check",
    "sanitize_scenario",
    "sanitize_structure",
    "sanitize_text",
]
