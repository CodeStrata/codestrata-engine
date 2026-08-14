"""Allow-list projector: Engine assessment state → assessment_metadata 1.1.

PRIVACY BOUNDARY INVARIANT
==========================
This module is a hard privacy boundary between rich Engine assessment state and
the public Community Cloud assessment_metadata wire contract.

MUST:
- construct every outbound field explicitly from allow-listed inputs
- filter rule IDs before aggregation
- emit only approved enum vocabularies

MUST NOT:
- model_dump / dict() / __dict__ entire assessment results
- serialize report.json, Finding objects, evidence, paths, or titles wholesale
- serialize-then-redact
- invent repository identity, package names, or failure prose
"""

from __future__ import annotations

from collections import Counter

from codestrata.telemetry.assessment_metadata.models import (
    APPROVED_CATEGORIES,
    APPROVED_CONFIDENCE_LEVELS,
    APPROVED_COUNT_BUCKETS,
    APPROVED_DURATION_BUCKETS,
    APPROVED_ECOSYSTEMS,
    APPROVED_HEADS,
    APPROVED_LANGUAGES,
    APPROVED_PLATFORMS,
    APPROVED_SEVERITIES,
    APPROVED_SHAPES,
    ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION,
    ASSESSMENT_REPORT_SCHEMA_VERSION,
    AssessmentMetadataProjectionSource,
    AssessmentMetadataWireRequest,
    FindingAggregateWireRow,
    HeadConfidenceWireRow,
    classify_duration_bucket_ms,
    map_assessment_mode,
    map_failure_category,
)
from codestrata.telemetry.assessment_metadata.policy import (
    CommunityAssessmentMetadataEmissionPolicy,
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.rule_filter import normalize_safe_rule_id

_CLIENT_NAME = "codestrata_cli"

_SEVERITY_ALIASES: dict[str, str] = {
    "info": "informational",
    "informational": "informational",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}

_ENGINE_HEAD_TO_CLOUD: dict[str, str] = {
    "technology_inventory": "technology_inventory",
    "architecture": "architecture",
    "architecture_intelligence": "architecture",
    "technical_debt": "technical_debt",
    "technical_debt_intelligence": "technical_debt",
    "dependency": "dependency",
    "dependency_intelligence": "dependency",
    "security": "security",
    "security_intelligence": "security",
    "testing": "testing",
    "cloud_readiness": "cloud_readiness",
    "cloud": "cloud_readiness",
    "ai_readiness": "ai_readiness",
    "performance": "performance",
    "modernization": "modernization",
    "modernization_assessment": "modernization",
}


def project_assessment_metadata(
    source: AssessmentMetadataProjectionSource,
    *,
    policy: CommunityAssessmentMetadataEmissionPolicy | None = None,
) -> AssessmentMetadataWireRequest:
    """Project allow-listed source facts into an amd 1.1 wire request."""

    active = policy or default_assessment_metadata_emission_policy()
    executed = _project_executed_heads(source.executed_heads)
    aggregates = _project_finding_aggregates(
        source.findings,
        maximum=active.maximum_finding_aggregates,
    )
    heads = _project_head_confidence(
        source.head_confidence,
        maximum=active.maximum_head_confidence_rows,
    )
    duration = classify_duration_bucket_ms(source.duration_ms)
    if duration not in APPROVED_DURATION_BUCKETS:
        duration = "unavailable"
    platform = _normalize_platform(source.platform)
    mode = map_assessment_mode(
        ai_used=source.ai_used,
        mode_value=source.assessment_mode,
    )
    status = "completed" if source.success else "failed"
    result = "succeeded" if source.success else "failed"
    failure = None
    if not source.success:
        failure = map_failure_category(source.failure_category)

    return AssessmentMetadataWireRequest(
        schema_version=ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION,
        event_id=source.event_id,
        assessment_id=source.assessment_id,
        client_name=_CLIENT_NAME,
        client_version=source.client_version,
        client_platform=platform,
        assessment_schema_version=(
            source.assessment_schema_version
            if source.assessment_schema_version
            else ASSESSMENT_REPORT_SCHEMA_VERSION
        ),
        assessment_status=status,
        assessment_mode=mode,
        executed_heads=executed,
        finding_count=max(0, int(source.finding_count)),
        recommendation_count=max(0, int(source.recommendation_count)),
        priority_action_count=max(0, int(source.priority_action_count)),
        roadmap_initiative_count=max(0, int(source.roadmap_initiative_count)),
        evidence_count=max(0, int(source.evidence_count)),
        limitation_count=max(0, int(source.limitation_count)),
        primary_language=_enum_or(
            source.primary_language, APPROVED_LANGUAGES, "unavailable"
        ),
        language_count=max(0, int(source.language_count)),
        dependency_ecosystem_count=max(0, int(source.dependency_ecosystem_count)),
        file_count_bucket=_enum_or(
            source.file_count_bucket, APPROVED_COUNT_BUCKETS, "unavailable"
        ),
        source_file_count_bucket=_enum_or(
            source.source_file_count_bucket, APPROVED_COUNT_BUCKETS, "unavailable"
        ),
        test_file_count_bucket=_enum_or(
            source.test_file_count_bucket, APPROVED_COUNT_BUCKETS, "unavailable"
        ),
        repository_shape=_enum_or(
            source.repository_shape, APPROVED_SHAPES, "unknown"
        ),
        has_tests=bool(source.has_tests),
        has_build_files=bool(source.has_build_files),
        has_dependency_manifests=bool(source.has_dependency_manifests),
        duration_bucket=duration,
        execution_result=result,
        ai_used=bool(source.ai_used),
        offline_mode=bool(source.offline_mode),
        execution_client_version=source.client_version,
        execution_platform=platform,
        report_json_generated=bool(source.report_json_generated),
        findings_json_generated=bool(source.findings_json_generated),
        recommendations_json_generated=bool(source.recommendations_json_generated),
        html_report_generated=bool(source.html_report_generated),
        artifact_count=max(0, min(100, int(source.artifact_count))),
        finding_aggregates=aggregates,
        head_confidence=heads,
        installation_id=source.installation_id,
        package_ecosystem=_optional_ecosystem(source.package_ecosystem),
        failure_category=failure,
    )


def canonicalize_cloud_head(head: str) -> str | None:
    text = str(head).strip().lower()
    mapped = _ENGINE_HEAD_TO_CLOUD.get(text, text)
    if mapped in APPROVED_HEADS:
        return mapped
    return None


def _project_executed_heads(heads: tuple[str, ...]) -> tuple[str, ...]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in heads:
        mapped = canonicalize_cloud_head(raw)
        if mapped is None or mapped in seen:
            continue
        seen.add(mapped)
        cleaned.append(mapped)
    return tuple(sorted(cleaned))


def _project_finding_aggregates(
    findings: tuple[object, ...],
    *,
    maximum: int,
) -> tuple[FindingAggregateWireRow, ...]:
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in findings:
        rule_id = normalize_safe_rule_id(str(getattr(row, "rule_id", "") or ""))
        if rule_id is None:
            continue
        severity = _normalize_severity(getattr(row, "severity", ""))
        category = _normalize_category(getattr(row, "category", ""))
        if severity is None or category is None:
            continue
        counts[(rule_id, severity, category)] += 1
    rows = [
        FindingAggregateWireRow(
            rule_id=key[0],
            severity=key[1],
            category=key[2],
            count=count,
        )
        for key, count in counts.items()
        if count >= 1
    ]
    rows.sort(key=lambda item: (item.rule_id, item.severity, item.category, item.count))
    if len(rows) > maximum:
        rows = rows[:maximum]
    return tuple(rows)


def _project_head_confidence(
    rows: tuple[object, ...],
    *,
    maximum: int,
) -> tuple[HeadConfidenceWireRow, ...]:
    cleaned: list[HeadConfidenceWireRow] = []
    seen: set[str] = set()
    for row in rows:
        head = canonicalize_cloud_head(str(getattr(row, "head", "") or ""))
        level = str(getattr(row, "confidence_level", "") or "").strip().lower()
        if head is None or level not in APPROVED_CONFIDENCE_LEVELS:
            continue
        if head in seen:
            continue
        seen.add(head)
        cleaned.append(HeadConfidenceWireRow(head=head, confidence_level=level))
    cleaned.sort(key=lambda item: item.head)
    if len(cleaned) > maximum:
        cleaned = cleaned[:maximum]
    return tuple(cleaned)


def _normalize_severity(value: object) -> str | None:
    text = str(value or "").strip().lower()
    mapped = _SEVERITY_ALIASES.get(text)
    if mapped in APPROVED_SEVERITIES:
        return mapped
    return None


def _normalize_category(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if text in APPROVED_CATEGORIES:
        return text
    return None


def _normalize_platform(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"darwin", "macos", "mac os", "mac os x"}:
        return "darwin"
    if text in APPROVED_PLATFORMS:
        return text
    return "other"


def _enum_or(value: str, allowed: frozenset[str], default: str) -> str:
    text = str(value or "").strip().lower()
    if text in allowed:
        return text
    return default


def _optional_ecosystem(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in APPROVED_ECOSYSTEMS:
        return text
    return None


__all__ = [
    "canonicalize_cloud_head",
    "project_assessment_metadata",
]
