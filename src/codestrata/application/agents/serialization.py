"""Transport-neutral JSON serialization for Agent Framework results.

Used by CLI and MCP adapters. Does not depend on Typer or FastMCP.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from codestrata.application.agents.models import (
    AgentStatus,
    AssessmentValidationResult,
    AssessmentValidationWorkflowResult,
    ModernizationReviewResult,
    RepositoryAssessmentResult,
    RepositoryReviewResult,
    SnapshotReviewResult,
    ValidationIssue,
)

DEFAULT_TOP_ITEMS = 10
DEFAULT_ISSUE_LIMIT = 50
DEFAULT_EVIDENCE_SUMMARY_LIMIT = 20


def agent_result_to_dict(
    result: BaseModel,
    *,
    include_full_evidence: bool = False,
) -> dict[str, Any]:
    """Map an agent workflow result to a stable JSON object."""

    if isinstance(result, RepositoryReviewResult):
        return map_repository_review(result, include_full_evidence=include_full_evidence)
    if isinstance(result, RepositoryAssessmentResult):
        return map_repository_assessment(result, include_full_evidence=include_full_evidence)
    if isinstance(result, AssessmentValidationWorkflowResult):
        return map_validation_workflow(result)
    if isinstance(result, SnapshotReviewResult):
        return map_snapshot_review(result, include_full_evidence=include_full_evidence)
    if isinstance(result, ModernizationReviewResult):
        return map_modernization_review(result, include_full_evidence=include_full_evidence)
    converted = _convert(result.model_dump(mode="json"))
    assert isinstance(converted, dict)
    return converted


def map_repository_review(
    result: RepositoryReviewResult,
    *,
    include_full_evidence: bool = False,
) -> dict[str, Any]:
    payload = {
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type.value,
        "status": result.status.value,
        "repository": _convert(result.repository),
        "latest_run": _convert(result.latest_run),
        "latest_snapshot": _convert(result.latest_snapshot),
        "previous_run": _convert(result.previous_run),
        "previous_snapshot": _convert(result.previous_snapshot),
        "snapshot_changes": _map_snapshot_changes(result.snapshot_changes),
        "finding_summary": _convert(result.finding_summary),
        "recommendation_summary": _convert(result.recommendation_summary),
        "top_findings": _convert(result.top_findings[:DEFAULT_TOP_ITEMS]),
        "top_recommendations": _convert(result.top_recommendations[:DEFAULT_TOP_ITEMS]),
        "component_summary": _convert(result.component_summary),
        "dependency_summary": _convert(result.dependency_summary),
        "ai_status": result.ai_status,
        "validation": map_validation(result.validation),
        "steps": _convert(result.steps),
        "warnings": list(result.warnings),
        "evidence_summary": _evidence_summary(result.evidence),
    }
    if include_full_evidence:
        payload["evidence"] = _convert(result.evidence)
    return payload


def map_repository_assessment(
    result: RepositoryAssessmentResult,
    *,
    include_full_evidence: bool = False,
) -> dict[str, Any]:
    payload = {
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type.value,
        "status": result.status.value,
        "repository_id": result.repository_id,
        "snapshot_id": result.snapshot_id,
        "run_id": result.run_id,
        "repository_display_name": result.repository_display_name,
        "branch": result.branch,
        "findings_count": result.findings_count,
        "recommendations_count": result.recommendations_count,
        "phase3_findings_count": result.phase3_findings_count,
        "phase3_recommendations_count": result.phase3_recommendations_count,
        "ai_requested": result.ai_requested,
        "ai_status": result.ai_status,
        "prior_run_id": result.prior_run_id,
        "prior_snapshot_id": result.prior_snapshot_id,
        "assessment": _convert(result.assessment),
        "validation": map_validation(result.validation),
        "steps": _convert(result.steps),
        "warnings": list(result.warnings),
        "evidence_summary": _evidence_summary(result.evidence),
    }
    if include_full_evidence:
        payload["evidence"] = _convert(result.evidence)
    return payload


def map_validation_workflow(
    result: AssessmentValidationWorkflowResult,
    *,
    issue_limit: int = DEFAULT_ISSUE_LIMIT,
) -> dict[str, Any]:
    validation = map_validation(result.validation, issue_limit=issue_limit)
    return {
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type.value,
        "status": result.status.value,
        "run_id": result.run_id,
        "repository_id": result.repository_id,
        "snapshot_id": result.snapshot_id,
        "validation": validation,
        "steps": _convert(result.steps),
        "warnings": list(result.warnings),
    }


def map_snapshot_review(
    result: SnapshotReviewResult,
    *,
    include_full_evidence: bool = False,
) -> dict[str, Any]:
    payload = {
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type.value,
        "status": result.status.value,
        "comparison": _map_snapshot_changes(result.comparison),
        "steps": _convert(result.steps),
        "warnings": list(result.warnings),
        "evidence_summary": _evidence_summary(result.evidence),
    }
    if include_full_evidence:
        payload["evidence"] = _convert(result.evidence)
    return payload


def map_modernization_review(
    result: ModernizationReviewResult,
    *,
    include_full_evidence: bool = False,
) -> dict[str, Any]:
    payload = {
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type.value,
        "status": result.status.value,
        "repository_id": result.repository_id,
        "run_id": result.run_id,
        "snapshot_id": result.snapshot_id,
        "risk_summary": _convert(result.risk_summary),
        "recommendation_groups": _convert(result.recommendation_groups),
        "roadmap_phases": list(result.roadmap_phases),
        "recommendation_summary": _convert(result.recommendation_summary),
        "top_recommendations": _convert(result.top_recommendations[:DEFAULT_TOP_ITEMS]),
        "unresolved_recommendation_ids": list(result.unresolved_recommendation_ids),
        "validation": map_validation(result.validation),
        "steps": _convert(result.steps),
        "warnings": list(result.warnings),
        "evidence_summary": _evidence_summary(result.evidence),
        "source_distinction": {
            "deterministic": True,
            "ai_enriched": False,
        },
    }
    if include_full_evidence:
        payload["evidence"] = _convert(result.evidence)
    return payload


def map_validation(
    validation: AssessmentValidationResult | None,
    *,
    issue_limit: int = DEFAULT_ISSUE_LIMIT,
) -> dict[str, Any] | None:
    if validation is None:
        return None
    issues = validation.issues
    returned = issues[:issue_limit]
    return {
        "valid": validation.valid,
        "blocking": validation.blocking,
        "checked_artifacts": list(validation.checked_artifacts),
        "checked_findings": validation.checked_findings,
        "checked_recommendations": validation.checked_recommendations,
        "checked_components": validation.checked_components,
        "ai_validation_status": validation.ai_validation_status,
        "issues": [_convert(item) for item in returned],
        "issue_total_count": len(issues),
        "issue_returned_count": len(returned),
        "issue_truncated": len(issues) > len(returned),
        "issues_by_severity": _group_issues_by_severity(issues),
    }


def exit_code_for_status(status: AgentStatus, *, validation_blocking: bool = False) -> int:
    """Map workflow status to CLI exit code (0 success, 1 blocked, 2 error)."""

    if status is AgentStatus.COMPLETED:
        return 0
    if status is AgentStatus.BLOCKED or validation_blocking:
        return 1
    return 2


def _evidence_summary(evidence: Sequence[Any]) -> dict[str, Any]:
    items = list(evidence)[:DEFAULT_EVIDENCE_SUMMARY_LIMIT]
    summaries = []
    for item in items:
        summaries.append(
            {
                "evidence_id": getattr(item, "evidence_id", None),
                "source_kind": _enum_value(getattr(item, "source_kind", None)),
                "source_id": getattr(item, "source_id", None),
                "title": getattr(item, "title", None),
                "deterministic": getattr(item, "deterministic", True),
            }
        )
    return {
        "total_count": len(evidence),
        "returned_count": len(summaries),
        "truncated": len(evidence) > len(summaries),
        "items": summaries,
    }


def _map_snapshot_changes(comparison: Any) -> dict[str, Any] | None:
    if comparison is None:
        return None
    counts = getattr(comparison, "counts", None)
    return {
        "previous_snapshot_id": getattr(comparison, "previous_snapshot_id", None),
        "current_snapshot_id": getattr(comparison, "current_snapshot_id", None),
        "previous_content_fingerprint": getattr(
            comparison, "previous_content_fingerprint", None
        ),
        "current_content_fingerprint": getattr(
            comparison, "current_content_fingerprint", None
        ),
        "counts": _convert(counts),
        "added_files": _convert(getattr(comparison, "added_files", ())[:50]),
        "modified_files": _convert(getattr(comparison, "modified_files", ())[:50]),
        "deleted_files": _convert(getattr(comparison, "deleted_files", ())[:50]),
        "metadata_changed_files": _convert(
            getattr(comparison, "metadata_changed_files", ())[:50]
        ),
        "renamed_files": _convert(getattr(comparison, "renamed_files", ())),
        "rename_detection": "not_supported",
    }


def _group_issues_by_severity(issues: Sequence[ValidationIssue]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for issue in issues:
        key = issue.severity.value
        grouped[key] = grouped.get(key, 0) + 1
    return dict(sorted(grouped.items()))


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _convert(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return _convert(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _convert(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_convert(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
