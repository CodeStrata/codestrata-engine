"""Slice 20.11 — shared privacy canary constants and scan helpers.

Deterministic sensitive values used to stress every known amd leakage route.
Product code must never serialize these into Community outbound payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from codestrata.telemetry.assessment_metadata.models import (
    AssessmentMetadataProjectionSource,
    FindingProjectionRow,
    HeadConfidenceProjectionRow,
)

# Mandatory canaries (Slice 20.11 §3).
REPO_NAME = "VERY_PRIVATE_REPO_123"
PATH = "/Users/private/AcmeSecretProject/payments/"
SYMBOL = "AcmeInternalSettlementEngine"
SECRET = "TEST_SECRET_DO_NOT_TRANSMIT"
REMOTE = "git@github.com:private/acme-secret.git"
PACKAGE = "acme-internal-payments-sdk"
URL = "https://internal.acme.example/private"

MANDATORY_CANARIES: tuple[str, ...] = (
    REPO_NAME,
    PATH,
    SYMBOL,
    SECRET,
    REMOTE,
    PACKAGE,
    URL,
)

# Representative sensitive prose / identity that must also stay local.
EXTRA_CANARIES: tuple[str, ...] = (
    "Finding: AcmeInternalSettlementEngine leaks settlement keys",
    "Evidence excerpt from /Users/private/AcmeSecretProject/payments/ledger.py",
    "Recommendation: rotate TEST_SECRET_DO_NOT_TRANSMIT immediately",
    "graph-node:AcmeInternalSettlementEngine",
    "edge→https://internal.acme.example/private",
    "Traceback: File \"/Users/private/AcmeSecretProject/payments/run.py\"",
    "cscc_v1_SYNTHETIC_CREDENTIAL_CANARY_DO_NOT_TRANSMIT",
    "AWS_SECRET_ACCESS_KEY=AKIA_CANARY_DO_NOT_TRANSMIT",
)

ALL_CANARIES: tuple[str, ...] = MANDATORY_CANARIES + EXTRA_CANARIES

# Forbidden field names that must never appear in amd request / lake payload.
FORBIDDEN_AMD_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "repository_name",
        "repository_url",
        "git_remote",
        "path",
        "file_path",
        "source",
        "source_code",
        "snippet",
        "evidence",
        "finding_id",
        "title",
        "description",
        "recommendation_text",
        "report_id",
        "report_url",
        "graph",
        "nodes",
        "edges",
        "dependencies",
        "packages",
        "stack_trace",
        "exception_message",
        "prompt",
        "response",
        "occurred_at",
        "client_timestamp",
        "executed_at",
    }
)

# Authoritative allow-listed top-level keys for schema 1.1 wire body.
APPROVED_AMD_1_1_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "event_id",
        "assessment_id",
        "installation_id",
        "client",
        "assessment",
        "repository",
        "execution",
        "artifacts",
        "finding_aggregates",
        "head_confidence",
    }
)

APPROVED_CLIENT_KEYS: frozenset[str] = frozenset({"name", "version", "platform"})
APPROVED_ASSESSMENT_KEYS: frozenset[str] = frozenset(
    {
        "assessment_schema_version",
        "assessment_status",
        "assessment_mode",
        "executed_heads",
        "finding_count",
        "recommendation_count",
        "priority_action_count",
        "roadmap_initiative_count",
        "evidence_count",
        "limitation_count",
    }
)
APPROVED_REPOSITORY_KEYS: frozenset[str] = frozenset(
    {
        "primary_language",
        "language_count",
        "dependency_ecosystem_count",
        "file_count_bucket",
        "source_file_count_bucket",
        "test_file_count_bucket",
        "repository_shape",
        "has_tests",
        "has_build_files",
        "has_dependency_manifests",
        "package_ecosystem",
    }
)
APPROVED_EXECUTION_KEYS: frozenset[str] = frozenset(
    {
        "duration_bucket",
        "result",
        "ai_used",
        "offline_mode",
        "client_version",
        "platform",
        "failure_category",
    }
)
APPROVED_ARTIFACTS_KEYS: frozenset[str] = frozenset(
    {
        "report_json_generated",
        "findings_json_generated",
        "recommendations_json_generated",
        "html_report_generated",
        "artifact_count",
    }
)
APPROVED_FINDING_AGGREGATE_KEYS: frozenset[str] = frozenset(
    {"rule_id", "severity", "category", "count"}
)
APPROVED_HEAD_CONFIDENCE_KEYS: frozenset[str] = frozenset({"head", "confidence_level"})

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "privacy_canary_repo"


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def iter_all_keys(obj: object, *, prefix: str = "") -> Iterable[str]:
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield str(key)
            yield from iter_all_keys(value, prefix=path)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from iter_all_keys(item, prefix=f"{prefix}[{index}]")


def assert_no_canaries(obj: object, *, canaries: Iterable[str] = ALL_CANARIES) -> None:
    blob = canonical_json(obj)
    for canary in canaries:
        assert canary not in blob, f"canary leaked into payload: {canary!r}"
    for key in iter_all_keys(obj):
        for canary in canaries:
            assert canary not in key, f"canary leaked into key name: {key!r}"


def assert_no_forbidden_fields(obj: object) -> None:
    for key in iter_all_keys(obj):
        assert key not in FORBIDDEN_AMD_FIELD_NAMES, f"forbidden field present: {key!r}"


def assert_amd_1_1_allowlist(payload: Mapping[str, Any]) -> None:
    assert set(payload.keys()) <= APPROVED_AMD_1_1_TOP_LEVEL_KEYS
    assert set(payload["client"].keys()) <= APPROVED_CLIENT_KEYS
    assert set(payload["assessment"].keys()) <= APPROVED_ASSESSMENT_KEYS
    assert set(payload["repository"].keys()) <= APPROVED_REPOSITORY_KEYS
    assert set(payload["execution"].keys()) <= APPROVED_EXECUTION_KEYS
    assert set(payload["artifacts"].keys()) <= APPROVED_ARTIFACTS_KEYS
    for row in payload.get("finding_aggregates") or []:
        assert set(row.keys()) <= APPROVED_FINDING_AGGREGATE_KEYS
    for row in payload.get("head_confidence") or []:
        assert set(row.keys()) <= APPROVED_HEAD_CONFIDENCE_KEYS


def canary_findings_artifact() -> Path:
    return FIXTURE_ROOT / "findings_with_canaries.json"


def canary_rich_projection_source(
    *,
    assessment_id: str,
    installation_id: str,
    event_id: str = "amd-e2e-20-11-0001",
    success: bool = True,
) -> AssessmentMetadataProjectionSource:
    """Projection source intentionally stuffed with canary-bearing finding rows."""

    findings = (
        FindingProjectionRow(
            rule_id="architecture.layer-dependency",
            severity="high",
            category="architecture",
        ),
        FindingProjectionRow(
            rule_id="architecture.layer-dependency",
            severity="high",
            category="architecture",
        ),
        FindingProjectionRow(
            rule_id="security.debug-enabled",
            severity="medium",
            category="security",
        ),
        FindingProjectionRow(
            rule_id="security.debug-enabled",
            severity="high",
            category="security",
        ),
        FindingProjectionRow(
            rule_id="PMD.JAVA.VeryPrivate",
            severity="critical",
            category="security",
        ),
        FindingProjectionRow(
            rule_id="provider:openai",
            severity="low",
            category="unknown",
        ),
        FindingProjectionRow(
            rule_id=f"dynamic/{REPO_NAME}",
            severity="high",
            category="security",
        ),
        FindingProjectionRow(
            rule_id=URL,
            severity="high",
            category="security",
        ),
        FindingProjectionRow(
            rule_id=PATH + "ledger.py",
            severity="high",
            category="security",
        ),
        FindingProjectionRow(
            rule_id="not a valid rule",
            severity="high",
            category="security",
        ),
    )
    heads = (
        HeadConfidenceProjectionRow(head="security", confidence_level="high"),
        HeadConfidenceProjectionRow(head="architecture", confidence_level="moderate"),
        HeadConfidenceProjectionRow(head="dependency", confidence_level="limited"),
        HeadConfidenceProjectionRow(head="testing", confidence_level="unavailable"),
    )
    return AssessmentMetadataProjectionSource(
        assessment_id=assessment_id,
        event_id=event_id,
        client_version="0.2.1",
        platform="darwin",
        success=success,
        assessment_mode="deterministic",
        executed_heads=("technology_inventory", "security", "architecture", "dependency"),
        findings=findings,
        head_confidence=heads,
        duration_ms=15_000.0,
        installation_id=installation_id,
        finding_count=len(findings),
        recommendation_count=2,
        offline_mode=True,
        ai_used=False,
        report_json_generated=True,
        findings_json_generated=True,
        recommendations_json_generated=True,
        html_report_generated=True,
        artifact_count=4,
        primary_language="python",
        language_count=1,
        dependency_ecosystem_count=1,
        file_count_bucket="11_to_50",
        source_file_count_bucket="1_to_10",
        test_file_count_bucket="none",
        repository_shape="application",
        has_tests=True,
        has_build_files=True,
        has_dependency_manifests=True,
        package_ecosystem="python",
    )


__all__ = [
    "ALL_CANARIES",
    "APPROVED_AMD_1_1_TOP_LEVEL_KEYS",
    "EXTRA_CANARIES",
    "FIXTURE_ROOT",
    "FORBIDDEN_AMD_FIELD_NAMES",
    "MANDATORY_CANARIES",
    "PACKAGE",
    "PATH",
    "REMOTE",
    "REPO_NAME",
    "SECRET",
    "SYMBOL",
    "URL",
    "assert_amd_1_1_allowlist",
    "assert_no_canaries",
    "assert_no_forbidden_fields",
    "canary_findings_artifact",
    "canary_rich_projection_source",
    "canonical_json",
]
