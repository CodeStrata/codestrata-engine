"""Build allow-listed projection inputs from Engine assessment state (Slice 20.8).

Never copies repository names, paths, titles, evidence, or exception messages.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from codestrata.package_metadata import get_package_version
from codestrata.telemetry.assessment_metadata.models import (
    AssessmentMetadataProjectionSource,
    FindingProjectionRow,
    HeadConfidenceProjectionRow,
    map_assessment_mode,
    map_failure_category,
)
from codestrata.telemetry.assessment_metadata.projector import canonicalize_cloud_head
from codestrata.telemetry.event_identity import generate_transport_event_id
from codestrata.telemetry.events import FailureCategory


def new_assessment_id() -> str:
    """Opaque random UUID for one assessment invocation (success or failure)."""

    return str(uuid4())


def resolve_client_platform() -> str:
    system = platform.system().strip().lower()
    if system in {"darwin", "macos", "mac os", "mac os x"}:
        return "darwin"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return "other"


def classify_assessment_failure(exc: BaseException | None) -> str:
    """Map failure type → bounded category without reading exception messages."""

    if exc is None:
        return FailureCategory.UNKNOWN.value
    if isinstance(exc, TimeoutError):
        return FailureCategory.TIMEOUT.value
    name = type(exc).__name__
    if name in {"ValidationError", "AssessmentCommandError"}:
        # AssessmentCommandError covers validation and many internal failures;
        # without a safe typed category attribute, prefer unknown over inventing.
        if name == "ValidationError":
            return FailureCategory.VALIDATION.value
        return FailureCategory.UNKNOWN.value
    if name in {"ConnectionError", "OSError", "URLError"}:
        return FailureCategory.UNAVAILABLE.value
    return FailureCategory.INTERNAL.value


def finding_rows_from_mappings(
    findings: Sequence[Mapping[str, Any]] | None,
) -> tuple[FindingProjectionRow, ...]:
    """Extract only (rule_id, severity, category) from finding-like mappings."""

    rows: list[FindingProjectionRow] = []
    if not findings:
        return ()
    for item in findings:
        if not isinstance(item, Mapping):
            continue
        rule_id = str(item.get("rule_id") or "").strip()
        severity = str(item.get("severity") or "").strip()
        category = str(item.get("category") or "").strip()
        if not rule_id:
            continue
        rows.append(
            FindingProjectionRow(
                rule_id=rule_id,
                severity=severity,
                category=category,
            )
        )
    return tuple(rows)


def finding_rows_from_artifact(path: Path | None) -> tuple[FindingProjectionRow, ...]:
    """Read findings.json and keep only aggregate keys (never evidence/paths)."""

    if path is None or not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — fail soft; amd is best-effort
        return ()
    if not isinstance(payload, Mapping):
        return ()
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return ()
    return finding_rows_from_mappings(findings)


def head_confidence_rows_from_map(
    mapping: Mapping[str, Any] | None,
) -> tuple[HeadConfidenceProjectionRow, ...]:
    rows: list[HeadConfidenceProjectionRow] = []
    if not mapping:
        return ()
    for head, block in mapping.items():
        level: str | None = None
        if isinstance(block, Mapping):
            level = str(block.get("level") or block.get("confidence_level") or "").strip()
        elif isinstance(block, str):
            level = block.strip()
        cloud_head = canonicalize_cloud_head(str(head))
        if cloud_head is None or not level:
            continue
        rows.append(
            HeadConfidenceProjectionRow(head=cloud_head, confidence_level=level.lower())
        )
    rows.sort(key=lambda item: item.head)
    return tuple(rows)


def head_confidence_from_assessment_json(
    path: Path | None,
) -> tuple[HeadConfidenceProjectionRow, ...]:
    if path is None or not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ()
    if not isinstance(payload, Mapping):
        return ()
    assessment = payload.get("assessment")
    if not isinstance(assessment, Mapping):
        assessment = payload
    block = assessment.get("assessment_head_confidence")
    if not isinstance(block, Mapping):
        return ()
    return head_confidence_rows_from_map(block)


def executed_heads_from_assessment_result(result: object) -> tuple[str, ...]:
    """Derive executed heads from status fields only — never paths/names."""

    heads: list[str] = []
    status_map = (
        ("architecture_assessment_status", "architecture"),
        ("technical_debt_assessment_status", "technical_debt"),
        ("dependency_assessment_status", "dependency"),
        ("security_assessment_status", "security"),
        ("testing_assessment_status", "testing"),
        ("cloud_assessment_status", "cloud_readiness"),
        ("ai_readiness_assessment_status", "ai_readiness"),
        ("performance_assessment_status", "performance"),
    )
    for attr, head in status_map:
        status = str(getattr(result, attr, "") or "").strip().lower()
        if status in {
            "succeeded",
            "partially_succeeded",
            "assessed",
            "partially_assessed",
            "completed",
            "inventory_generated",
            "partial_inventory",
        }:
            heads.append(head)
    technologies = getattr(result, "technologies_count", None)
    if isinstance(technologies, int) and technologies > 0:
        heads.append("technology_inventory")
    phases = getattr(result, "phases_count", None)
    if isinstance(phases, int) and phases > 0:
        heads.append("modernization")
    # Dedup + sort via projector canonicalize later.
    return tuple(dict.fromkeys(heads))


def build_success_projection_source(
    result: object,
    *,
    assessment_id: str,
    installation_id: str | None,
    offline_mode: bool = True,
    event_id: str | None = None,
    client_version: str | None = None,
    platform_name: str | None = None,
) -> AssessmentMetadataProjectionSource:
    """Build projection input from a successful AssessmentCommandResult-like object."""

    findings_path = getattr(result, "findings_artifact_path", None)
    json_path = getattr(result, "json_report_path", None)
    findings = finding_rows_from_artifact(
        findings_path if isinstance(findings_path, Path) else None
    )
    head_confidence = head_confidence_from_assessment_json(
        json_path if isinstance(json_path, Path) else None
    )
    mode_raw = getattr(result, "mode", None)
    mode_value = getattr(mode_raw, "value", mode_raw)
    ai_used = bool(getattr(result, "ai_executed", False))
    if str(mode_value) in {"ai-enhanced", "ai_enhanced", "deterministic_with_ai"}:
        ai_used = True
    finding_count = int(getattr(result, "findings_count", 0) or 0)
    recommendation_count = int(getattr(result, "recommendations_count", 0) or 0)
    html = getattr(result, "html_report_path", None)
    report_json = getattr(result, "json_report_path", None)
    recommendations = getattr(result, "recommendations_artifact_path", None)
    artifact_flags = [
        report_json is not None,
        findings_path is not None,
        recommendations is not None,
        html is not None,
    ]
    return AssessmentMetadataProjectionSource(
        assessment_id=assessment_id,
        event_id=event_id or generate_transport_event_id(),
        client_version=client_version or get_package_version(),
        platform=platform_name or resolve_client_platform(),
        success=True,
        assessment_mode=map_assessment_mode(
            ai_used=ai_used,
            mode_value=(
                "deterministic_with_ai"
                if ai_used
                else "deterministic"
            ),
        ),
        executed_heads=executed_heads_from_assessment_result(result),
        findings=findings,
        head_confidence=head_confidence,
        failure_category=None,
        duration_ms=_optional_float(getattr(result, "duration_ms", None)),
        installation_id=installation_id,
        finding_count=finding_count,
        recommendation_count=recommendation_count,
        priority_action_count=0,
        roadmap_initiative_count=max(0, int(getattr(result, "phases_count", 0) or 0)),
        evidence_count=0,
        limitation_count=0,
        offline_mode=offline_mode,
        ai_used=ai_used,
        report_json_generated=report_json is not None,
        findings_json_generated=findings_path is not None,
        recommendations_json_generated=recommendations is not None,
        html_report_generated=html is not None,
        artifact_count=sum(1 for flag in artifact_flags if flag),
        # Repository aggregates unavailable from AssessmentCommandResult alone —
        # leave optional/unavailable rather than inventing from repo name/path.
        primary_language="unavailable",
        package_ecosystem=None,
        repository_shape="unknown",
        language_count=0,
        dependency_ecosystem_count=0,
        file_count_bucket="unavailable",
        source_file_count_bucket="unavailable",
        test_file_count_bucket="unavailable",
        has_tests=False,
        has_build_files=False,
        has_dependency_manifests=False,
    )


def build_failure_projection_source(
    *,
    assessment_id: str,
    installation_id: str | None,
    failure: BaseException | None = None,
    failure_category: str | None = None,
    offline_mode: bool = True,
    ai_used: bool = False,
    duration_ms: float | None = None,
    event_id: str | None = None,
    client_version: str | None = None,
    platform_name: str | None = None,
) -> AssessmentMetadataProjectionSource:
    """Bounded failed amd source — no partial rich result serialization."""

    category = failure_category or classify_assessment_failure(failure)
    return AssessmentMetadataProjectionSource(
        assessment_id=assessment_id,
        event_id=event_id or generate_transport_event_id(),
        client_version=client_version or get_package_version(),
        platform=platform_name or resolve_client_platform(),
        success=False,
        assessment_mode="unavailable",
        executed_heads=(),
        findings=(),
        head_confidence=(),
        failure_category=map_failure_category(category),
        duration_ms=duration_ms,
        installation_id=installation_id,
        offline_mode=offline_mode,
        ai_used=ai_used,
        report_json_generated=False,
        findings_json_generated=False,
        recommendations_json_generated=False,
        html_report_generated=False,
        artifact_count=0,
        primary_language="unavailable",
        repository_shape="unknown",
        file_count_bucket="unavailable",
        source_file_count_bucket="unavailable",
        test_file_count_bucket="unavailable",
    )


def _optional_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and value == value:
        return float(value)
    return None


__all__ = [
    "build_failure_projection_source",
    "build_success_projection_source",
    "classify_assessment_failure",
    "executed_heads_from_assessment_result",
    "finding_rows_from_artifact",
    "finding_rows_from_mappings",
    "head_confidence_from_assessment_json",
    "head_confidence_rows_from_map",
    "new_assessment_id",
    "resolve_client_platform",
]
