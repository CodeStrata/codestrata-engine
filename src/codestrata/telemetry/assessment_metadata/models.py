"""Outbound assessment_metadata 1.1 models and projection inputs (Slice 20.8).

Engine-owned DTOs mirroring the public Platform Community API contract.
Never import Platform packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codestrata.telemetry.events import FailureCategory
from codestrata.telemetry.assessment_metadata.policy import (
    ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION,
    ASSESSMENT_REPORT_SCHEMA_VERSION,
)

APPROVED_SEVERITIES: frozenset[str] = frozenset(
    {"informational", "low", "medium", "high", "critical"}
)
APPROVED_CATEGORIES: frozenset[str] = frozenset(
    {
        "architecture",
        "dependency",
        "maintainability",
        "technical_debt",
        "testing",
        "documentation",
        "build",
        "governance",
        "security",
        "cloud",
        "ai_readiness",
        "performance",
        "modernization",
        "unknown",
    }
)
APPROVED_HEADS: frozenset[str] = frozenset(
    {
        "technology_inventory",
        "architecture",
        "technical_debt",
        "dependency",
        "security",
        "testing",
        "cloud_readiness",
        "ai_readiness",
        "performance",
        "modernization",
    }
)
APPROVED_CONFIDENCE_LEVELS: frozenset[str] = frozenset(
    {"high", "moderate", "limited", "unavailable"}
)
APPROVED_COUNT_BUCKETS: frozenset[str] = frozenset(
    {
        "none",
        "1_to_10",
        "11_to_50",
        "51_to_200",
        "201_to_1000",
        "over_1000",
        "unavailable",
    }
)
APPROVED_DURATION_BUCKETS: frozenset[str] = frozenset(
    {
        "under_10s",
        "10s_to_30s",
        "30s_to_2m",
        "2m_to_10m",
        "over_10m",
        "unavailable",
    }
)
APPROVED_LANGUAGES: frozenset[str] = frozenset(
    {
        "python",
        "java",
        "javascript",
        "typescript",
        "go",
        "csharp",
        "rust",
        "unknown",
        "unavailable",
    }
)
APPROVED_ECOSYSTEMS: frozenset[str] = frozenset(
    {
        "maven",
        "gradle",
        "npm",
        "python",
        "nuget",
        "composer",
        "cargo",
        "mixed",
        "unknown",
        "unavailable",
    }
)
APPROVED_SHAPES: frozenset[str] = frozenset(
    {
        "application",
        "library",
        "service",
        "cli",
        "multi_module",
        "infrastructure",
        "mixed",
        "unknown",
    }
)
APPROVED_PLATFORMS: frozenset[str] = frozenset(
    {"darwin", "linux", "windows", "other"}
)


@dataclass(frozen=True, slots=True)
class FindingProjectionRow:
    """One finding's aggregate keys only — never evidence/path/title."""

    rule_id: str
    severity: str
    category: str


@dataclass(frozen=True, slots=True)
class HeadConfidenceProjectionRow:
    head: str
    confidence_level: str


@dataclass(frozen=True, slots=True)
class AssessmentMetadataProjectionSource:
    """Allow-listed inputs for the privacy-boundary projector."""

    assessment_id: str
    event_id: str
    client_version: str
    platform: str
    success: bool
    assessment_mode: str  # deterministic | deterministic_with_ai | unavailable
    executed_heads: tuple[str, ...] = ()
    findings: tuple[FindingProjectionRow, ...] = ()
    head_confidence: tuple[HeadConfidenceProjectionRow, ...] = ()
    failure_category: str | None = None
    duration_ms: float | None = None
    installation_id: str | None = None
    # Optional repository aggregates — omit/unavailable rather than invent.
    primary_language: str = "unavailable"
    package_ecosystem: str | None = None
    repository_shape: str = "unknown"
    language_count: int = 0
    dependency_ecosystem_count: int = 0
    file_count_bucket: str = "unavailable"
    source_file_count_bucket: str = "unavailable"
    test_file_count_bucket: str = "unavailable"
    has_tests: bool = False
    has_build_files: bool = False
    has_dependency_manifests: bool = False
    # Aggregate counts
    finding_count: int = 0
    recommendation_count: int = 0
    priority_action_count: int = 0
    roadmap_initiative_count: int = 0
    evidence_count: int = 0
    limitation_count: int = 0
    offline_mode: bool = True
    ai_used: bool = False
    report_json_generated: bool = False
    findings_json_generated: bool = False
    recommendations_json_generated: bool = False
    html_report_generated: bool = False
    artifact_count: int = 0
    assessment_schema_version: str = ASSESSMENT_REPORT_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class FindingAggregateWireRow:
    rule_id: str
    severity: str
    category: str
    count: int

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "count": self.count,
            "rule_id": self.rule_id,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class HeadConfidenceWireRow:
    head: str
    confidence_level: str

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "confidence_level": self.confidence_level,
            "head": self.head,
        }


@dataclass(frozen=True, slots=True)
class AssessmentMetadataWireRequest:
    """Explicit allow-listed POST body for schema 1.1."""

    schema_version: str
    event_id: str
    assessment_id: str
    client_name: str
    client_version: str
    client_platform: str
    assessment_schema_version: str
    assessment_status: str
    assessment_mode: str
    executed_heads: tuple[str, ...]
    finding_count: int
    recommendation_count: int
    priority_action_count: int
    roadmap_initiative_count: int
    evidence_count: int
    limitation_count: int
    primary_language: str
    language_count: int
    dependency_ecosystem_count: int
    file_count_bucket: str
    source_file_count_bucket: str
    test_file_count_bucket: str
    repository_shape: str
    has_tests: bool
    has_build_files: bool
    has_dependency_manifests: bool
    duration_bucket: str
    execution_result: str
    ai_used: bool
    offline_mode: bool
    execution_client_version: str
    execution_platform: str
    report_json_generated: bool
    findings_json_generated: bool
    recommendations_json_generated: bool
    html_report_generated: bool
    artifact_count: int
    finding_aggregates: tuple[FindingAggregateWireRow, ...] = ()
    head_confidence: tuple[HeadConfidenceWireRow, ...] = ()
    installation_id: str | None = None
    package_ecosystem: str | None = None
    failure_category: str | None = None

    def to_stable_dict(self) -> dict[str, Any]:
        """Construct the outbound JSON object field-by-field (privacy boundary)."""

        assessment = {
            "assessment_mode": self.assessment_mode,
            "assessment_schema_version": self.assessment_schema_version,
            "assessment_status": self.assessment_status,
            "evidence_count": self.evidence_count,
            "executed_heads": list(self.executed_heads),
            "finding_count": self.finding_count,
            "limitation_count": self.limitation_count,
            "priority_action_count": self.priority_action_count,
            "recommendation_count": self.recommendation_count,
            "roadmap_initiative_count": self.roadmap_initiative_count,
        }
        repository: dict[str, Any] = {
            "dependency_ecosystem_count": self.dependency_ecosystem_count,
            "file_count_bucket": self.file_count_bucket,
            "has_build_files": self.has_build_files,
            "has_dependency_manifests": self.has_dependency_manifests,
            "has_tests": self.has_tests,
            "language_count": self.language_count,
            "primary_language": self.primary_language,
            "repository_shape": self.repository_shape,
            "source_file_count_bucket": self.source_file_count_bucket,
            "test_file_count_bucket": self.test_file_count_bucket,
        }
        if self.package_ecosystem is not None:
            repository["package_ecosystem"] = self.package_ecosystem
        execution: dict[str, Any] = {
            "ai_used": self.ai_used,
            "client_version": self.execution_client_version,
            "duration_bucket": self.duration_bucket,
            "offline_mode": self.offline_mode,
            "platform": self.execution_platform,
            "result": self.execution_result,
        }
        if self.failure_category is not None:
            execution["failure_category"] = self.failure_category
        artifacts = {
            "artifact_count": self.artifact_count,
            "findings_json_generated": self.findings_json_generated,
            "html_report_generated": self.html_report_generated,
            "recommendations_json_generated": self.recommendations_json_generated,
            "report_json_generated": self.report_json_generated,
        }
        payload: dict[str, Any] = {
            "assessment": assessment,
            "assessment_id": self.assessment_id,
            "artifacts": artifacts,
            "client": {
                "name": self.client_name,
                "platform": self.client_platform,
                "version": self.client_version,
            },
            "event_id": self.event_id,
            "execution": execution,
            "finding_aggregates": [
                row.to_stable_dict() for row in self.finding_aggregates
            ],
            "head_confidence": [row.to_stable_dict() for row in self.head_confidence],
            "repository": repository,
            "schema_version": self.schema_version,
        }
        if self.installation_id is not None:
            payload["installation_id"] = self.installation_id
        return payload


def classify_duration_bucket_ms(duration_ms: float | int | None) -> str:
    if duration_ms is None:
        return "unavailable"
    try:
        value = float(duration_ms)
    except (TypeError, ValueError):
        return "unavailable"
    if value < 0 or value != value:
        return "unavailable"
    if value < 10_000:
        return "under_10s"
    if value < 30_000:
        return "10s_to_30s"
    if value < 120_000:
        return "30s_to_2m"
    if value < 600_000:
        return "2m_to_10m"
    return "over_10m"


def map_assessment_mode(*, ai_used: bool, mode_value: str | None = None) -> str:
    if mode_value == "ai_enhanced" or ai_used:
        return "deterministic_with_ai"
    if mode_value in {"deterministic", "deterministic_with_ai", "unavailable"}:
        return mode_value
    return "deterministic"


def map_failure_category(value: object) -> str:
    if isinstance(value, FailureCategory):
        return value.value
    if isinstance(value, str) and value in {item.value for item in FailureCategory}:
        return value
    return FailureCategory.UNKNOWN.value


__all__ = [
    "APPROVED_CATEGORIES",
    "APPROVED_CONFIDENCE_LEVELS",
    "APPROVED_COUNT_BUCKETS",
    "APPROVED_DURATION_BUCKETS",
    "APPROVED_ECOSYSTEMS",
    "APPROVED_HEADS",
    "APPROVED_LANGUAGES",
    "APPROVED_PLATFORMS",
    "APPROVED_SEVERITIES",
    "APPROVED_SHAPES",
    "ASSESSMENT_METADATA_WIRE_SCHEMA_VERSION",
    "ASSESSMENT_REPORT_SCHEMA_VERSION",
    "AssessmentMetadataProjectionSource",
    "AssessmentMetadataWireRequest",
    "FindingAggregateWireRow",
    "FindingProjectionRow",
    "HeadConfidenceProjectionRow",
    "HeadConfidenceWireRow",
    "classify_duration_bucket_ms",
    "map_assessment_mode",
    "map_failure_category",
]
