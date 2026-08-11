"""Assemble and persist the deterministic SV.11.7 report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.bedrock_provider_migration.contract import (
    ALLOWED_VERDICTS,
    EPIC,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    PACKAGE_DOTTED_NAME,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.bedrock_provider_migration.models import (
    BedrockMigrationVerificationReport,
    CheckResult,
    ScenarioResult,
    build_check_counts,
)

NOTES: tuple[str, ...] = (
    "Bedrock now runs as an AIProvider adapter under AIProviderExecutor; "
    "BedrockAIModelProvider is a compatibility wrapper with the same class name, "
    "constructor signature, registry key, and invoke() contract.",
    "Client construction moved from __init__ to the first invoke(). A missing "
    "bedrock extra or an unusable AWS profile now surfaces from invoke() as the "
    "same AIProviderConfigurationError, with the same message, that the "
    "constructor used to raise.",
    "codestrata.ai.aws_config is unchanged and remains the single owner of the "
    "AWS credential/profile/region precedence chain and of the botocore "
    "Config(connect_timeout=..., read_timeout=..., retries={max_attempts: 1}).",
    "Exactly one Converse call is made per assess run: the executor is pinned to "
    "maximum_attempts=1 and botocore stays at max_attempts=1, so CodeStrata "
    "retries are never stacked on SDK retries (CR-1).",
    "Bedrock Converse has no native structured-JSON mode. supports_structured_json "
    "stays False and the JSON instruction is appended to the system block exactly "
    "as before.",
    "The assess path still resolves providers through AssessAIProviderRegistry. "
    "Consolidating onto the contracts' AIProviderRegistry was reviewed in "
    "Slice 11.8 and deferred (Decision B — compatibility registry retained).",
    "codestrata ai doctor is unchanged and still probes AWS through "
    "aws_config.probe_aws_session_for_bedrock rather than the adapter.",
    "No live AWS call, credential read, instance metadata lookup, STS call, or "
    "wall-clock wait occurs anywhere in this suite: every execution uses an "
    "injected in-memory client.",
)


def resolve_verdict(checks: list[CheckResult], scenarios: list[ScenarioResult]) -> str:
    """PASS_WITH_LIMITATIONS when everything holds; a failure means FAIL."""

    if any(not check.ok for check in checks) or any(
        not scenario.ok for scenario in scenarios
    ):
        return "fail"
    return "pass_with_limitations"


def build_report(
    *,
    checks: list[CheckResult],
    scenarios: list[ScenarioResult],
    matrices: dict[str, Any],
    warnings: tuple[str, ...] = (),
) -> BedrockMigrationVerificationReport:
    verdict = resolve_verdict(checks, scenarios)
    return BedrockMigrationVerificationReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        epic=EPIC,
        slice_id=SLICE_ID,
        verdict=verdict,
        package_dotted_name=PACKAGE_DOTTED_NAME,
        compatibility_requirement_ids=REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
        matrices=matrices,
        negative_scenarios=tuple(scenarios),
        checks=tuple(checks),
        limitations=EXPECTED_LIMITATIONS,
        warnings=warnings,
        notes=NOTES,
        check_counts=build_check_counts(checks),
    )


def report_directory(engine_root: Path) -> Path:
    return engine_root / OUTPUT_RELATIVE


def write_report(
    report: BedrockMigrationVerificationReport, engine_root: Path
) -> tuple[Path, Path]:
    directory = report_directory(engine_root)
    json_path = report.write_json(directory / REPORT_FILENAME)
    markdown_path = report.write_markdown(directory / REPORT_MD_FILENAME)
    return json_path, markdown_path


def verdict_is_allowed(verdict: str) -> bool:
    return verdict in ALLOWED_VERDICTS


__all__ = [
    "NOTES",
    "build_report",
    "report_directory",
    "resolve_verdict",
    "verdict_is_allowed",
    "write_report",
]
