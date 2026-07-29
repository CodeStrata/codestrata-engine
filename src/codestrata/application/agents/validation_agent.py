"""Validation agent: verify persisted assessments via query DTOs."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from codestrata.application.agents.errors import AgentDependencyError, AgentValidationError
from codestrata.application.agents.models import (
    AssessmentValidationResult,
    ValidationIssue,
    ValidationSeverity,
)
from codestrata.application.agents.policies import AgentExecutionPolicy
from codestrata.application.knowledge.models import AssessmentRunStatus, KnowledgeArtifactKind
from codestrata.application.knowledge.queries.artifacts import REQUIRED_ARTIFACT_KINDS
from codestrata.application.knowledge.queries.errors import (
    AssessmentRunNotFoundError,
    KnowledgeArtifactCorruptionError,
    KnowledgeQueryError,
    SnapshotNotFoundError,
)
from codestrata.application.knowledge.queries.models import FindingView, RecommendationView
from codestrata.application.knowledge.queries.service import KnowledgeQueryService

logger = logging.getLogger(__name__)

_RECOGNIZED_AI_STATUSES = frozenset(
    {
        "not_requested",
        "succeeded",
        "authentication_failed",
        "provider_failed",
        "parsing_failed",
        "validation_failed",
        "failed",
        "error",
        "unknown",
    }
)


class ValidationAgent:
    """Validate assessment completeness and grounding through query services."""

    def __init__(
        self,
        query_service: KnowledgeQueryService,
        *,
        policy: AgentExecutionPolicy | None = None,
    ) -> None:
        if query_service is None:
            raise AgentDependencyError("KnowledgeQueryService is required")
        self._queries = query_service
        self._policy = policy or AgentExecutionPolicy()

    def validate_assessment(
        self,
        run_id: str,
        *,
        expected_repository_id: str | None = None,
        ai_requested: bool | None = None,
    ) -> AssessmentValidationResult:
        issues: list[ValidationIssue] = []
        checked_artifacts: list[str] = []
        checked_findings = 0
        checked_recommendations = 0
        checked_components = 0
        ai_validation_status = "not_applicable"

        try:
            run = self._queries.get_assessment_run(run_id)
        except AssessmentRunNotFoundError:
            return AssessmentValidationResult(
                valid=False,
                blocking=True,
                issues=(
                    ValidationIssue(
                        code="run_not_found",
                        severity=ValidationSeverity.BLOCKING,
                        message=f"Assessment run not found: {run_id}",
                        entity_type="assessment_run",
                        entity_id=run_id,
                    ),
                ),
                ai_validation_status="not_applicable",
            )
        except KnowledgeQueryError as error:
            raise AgentValidationError(str(error)) from error

        if expected_repository_id is not None and run.repository_id != expected_repository_id:
            issues.append(
                ValidationIssue(
                    code="repository_mismatch",
                    severity=ValidationSeverity.BLOCKING,
                    message="Run repository_id does not match expected repository",
                    entity_type="assessment_run",
                    entity_id=run.run_id,
                    related_ids=(run.repository_id, expected_repository_id),
                )
            )

        if run.status is AssessmentRunStatus.FAILED:
            issues.append(
                ValidationIssue(
                    code="run_failed",
                    severity=ValidationSeverity.BLOCKING,
                    message=f"Assessment run failed: {run.error_code or 'unknown'}",
                    entity_type="assessment_run",
                    entity_id=run.run_id,
                )
            )
        elif run.status is not AssessmentRunStatus.COMPLETED:
            issues.append(
                ValidationIssue(
                    code="run_incomplete",
                    severity=ValidationSeverity.BLOCKING,
                    message=f"Assessment run status is {run.status.value}, expected completed",
                    entity_type="assessment_run",
                    entity_id=run.run_id,
                )
            )

        if run.snapshot_id is None:
            issues.append(
                ValidationIssue(
                    code="snapshot_missing",
                    severity=ValidationSeverity.BLOCKING,
                    message="Completed run has no snapshot_id",
                    entity_type="assessment_run",
                    entity_id=run.run_id,
                )
            )
        else:
            try:
                snapshot = self._queries.get_repository_snapshot(run.snapshot_id)
                if snapshot.repository_id != run.repository_id:
                    issues.append(
                        ValidationIssue(
                            code="snapshot_repository_mismatch",
                            severity=ValidationSeverity.BLOCKING,
                            message="Snapshot does not belong to run repository",
                            entity_type="snapshot",
                            entity_id=snapshot.snapshot_id,
                            related_ids=(run.repository_id, snapshot.repository_id),
                        )
                    )
            except SnapshotNotFoundError:
                issues.append(
                    ValidationIssue(
                        code="snapshot_not_found",
                        severity=ValidationSeverity.BLOCKING,
                        message=f"Snapshot not found: {run.snapshot_id}",
                        entity_type="snapshot",
                        entity_id=run.snapshot_id,
                    )
                )

        present_kinds = {item.value for item in run.artifact_kinds}
        for kind in sorted(REQUIRED_ARTIFACT_KINDS, key=lambda item: item.value):
            checked_artifacts.append(kind.value)
            if kind.value not in present_kinds:
                severity = (
                    ValidationSeverity.BLOCKING
                    if self._policy.fail_on_missing_required_artifact
                    else ValidationSeverity.ERROR
                )
                issues.append(
                    ValidationIssue(
                        code="required_artifact_missing",
                        severity=severity,
                        message=f"Required artifact missing: {kind.value}",
                        entity_type="artifact",
                        entity_id=kind.value,
                        related_ids=(run.run_id,),
                    )
                )

        findings: tuple[FindingView, ...] = ()
        recommendations: tuple[RecommendationView, ...] = ()
        required_present = all(kind.value in present_kinds for kind in REQUIRED_ARTIFACT_KINDS)
        if run.status is AssessmentRunStatus.COMPLETED and required_present:
            try:
                findings = self._queries.get_findings(run.run_id)
                recommendations = self._queries.get_recommendations(run.run_id)
            except KnowledgeArtifactCorruptionError as error:
                issues.append(
                    ValidationIssue(
                        code="artifact_corruption",
                        severity=ValidationSeverity.BLOCKING,
                        message="Required artifact could not be loaded safely",
                        entity_type="artifact",
                        entity_id=run.run_id,
                        related_ids=(type(error).__name__,),
                    )
                )
            except KnowledgeQueryError:
                issues.append(
                    ValidationIssue(
                        code="artifact_load_failed",
                        severity=ValidationSeverity.BLOCKING,
                        message="Unable to load findings/recommendations",
                        entity_type="assessment_run",
                        entity_id=run.run_id,
                    )
                )

        finding_ids = {item.finding_id for item in findings}
        for finding in findings[: self._policy.max_findings]:
            checked_findings += 1
            if _looks_like_uuid(finding.finding_id):
                issues.append(
                    ValidationIssue(
                        code="phase1_uuid_finding",
                        severity=ValidationSeverity.BLOCKING,
                        message="Phase 1 UUID finding must not be treated as authoritative",
                        entity_type="finding",
                        entity_id=finding.finding_id,
                    )
                )
            if not finding.finding_id.startswith("finding:"):
                issues.append(
                    ValidationIssue(
                        code="unstable_finding_id",
                        severity=ValidationSeverity.WARNING,
                        message="Finding ID is not a stable Phase 3 finding:* identity",
                        entity_type="finding",
                        entity_id=finding.finding_id,
                    )
                )
            if not finding.category.strip():
                issues.append(
                    ValidationIssue(
                        code="finding_missing_category",
                        severity=ValidationSeverity.ERROR,
                        message="Finding is missing category",
                        entity_type="finding",
                        entity_id=finding.finding_id,
                    )
                )
            if not finding.severity.strip():
                issues.append(
                    ValidationIssue(
                        code="finding_missing_severity",
                        severity=ValidationSeverity.ERROR,
                        message="Finding is missing severity",
                        entity_type="finding",
                        entity_id=finding.finding_id,
                    )
                )
            if not finding.rule_id.strip():
                issues.append(
                    ValidationIssue(
                        code="finding_missing_provenance",
                        severity=ValidationSeverity.ERROR,
                        message="Finding is missing rule/provenance source",
                        entity_type="finding",
                        entity_id=finding.finding_id,
                    )
                )
            try:
                self._queries.explain_finding(run.run_id, finding.finding_id)
            except KnowledgeQueryError:
                issues.append(
                    ValidationIssue(
                        code="finding_explanation_failed",
                        severity=ValidationSeverity.WARNING,
                        message="Finding explanation could not be constructed",
                        entity_type="finding",
                        entity_id=finding.finding_id,
                    )
                )

        for recommendation in recommendations[: self._policy.max_recommendations]:
            checked_recommendations += 1
            if not recommendation.recommendation_id.strip():
                issues.append(
                    ValidationIssue(
                        code="recommendation_missing_id",
                        severity=ValidationSeverity.BLOCKING,
                        message="Recommendation is missing an ID",
                        entity_type="recommendation",
                    )
                )
                continue
            if not recommendation.priority.strip():
                issues.append(
                    ValidationIssue(
                        code="recommendation_invalid_priority",
                        severity=ValidationSeverity.ERROR,
                        message="Recommendation priority is empty",
                        entity_type="recommendation",
                        entity_id=recommendation.recommendation_id,
                    )
                )
            if not recommendation.category.strip():
                issues.append(
                    ValidationIssue(
                        code="recommendation_invalid_category",
                        severity=ValidationSeverity.ERROR,
                        message="Recommendation category is empty",
                        entity_type="recommendation",
                        entity_id=recommendation.recommendation_id,
                    )
                )
            if not recommendation.related_finding_ids and not recommendation.provider_id:
                issues.append(
                    ValidationIssue(
                        code="recommendation_ungrounded",
                        severity=ValidationSeverity.WARNING,
                        message="Recommendation has no related findings or provider source",
                        entity_type="recommendation",
                        entity_id=recommendation.recommendation_id,
                    )
                )
            missing_findings = [
                finding_id
                for finding_id in recommendation.related_finding_ids
                if finding_id not in finding_ids
            ]
            if missing_findings:
                issues.append(
                    ValidationIssue(
                        code="recommendation_missing_finding_refs",
                        severity=ValidationSeverity.ERROR,
                        message="Recommendation references unknown findings",
                        entity_type="recommendation",
                        entity_id=recommendation.recommendation_id,
                        related_ids=tuple(missing_findings),
                    )
                )
            try:
                self._queries.explain_recommendation(
                    run.run_id,
                    recommendation.recommendation_id,
                )
            except KnowledgeQueryError:
                issues.append(
                    ValidationIssue(
                        code="recommendation_explanation_failed",
                        severity=ValidationSeverity.WARNING,
                        message="Recommendation explanation could not be constructed",
                        entity_type="recommendation",
                        entity_id=recommendation.recommendation_id,
                    )
                )
            for node_id in recommendation.affected_node_ids[:20]:
                try:
                    self._queries.get_component(run.run_id, node_id)
                    checked_components += 1
                except KnowledgeQueryError:
                    issues.append(
                        ValidationIssue(
                            code="missing_component_reference",
                            severity=ValidationSeverity.WARNING,
                            message="Recommendation references unknown component",
                            entity_type="component",
                            entity_id=node_id,
                            related_ids=(recommendation.recommendation_id,),
                        )
                    )

        if ai_requested is False:
            ai_validation_status = "not_requested"
        elif ai_requested is True or KnowledgeArtifactKind.AI_EXECUTION.value in present_kinds:
            ai_validation_status = self._validate_ai(
                run.run_id,
                present_kinds=present_kinds,
                ai_requested=bool(ai_requested),
                issues=issues,
            )

        blocking = any(item.severity is ValidationSeverity.BLOCKING for item in issues)
        valid = not blocking and not any(
            item.severity is ValidationSeverity.ERROR for item in issues
        )

        logger.info(
            "validation.complete",
            extra={
                "run_id": run.run_id,
                "repository_id": run.repository_id,
                "snapshot_id": run.snapshot_id,
                "status": "blocked" if blocking else ("valid" if valid else "invalid"),
                "blocking": blocking,
            },
        )
        return AssessmentValidationResult(
            valid=valid,
            blocking=blocking,
            issues=tuple(issues),
            checked_artifacts=tuple(checked_artifacts),
            checked_findings=checked_findings,
            checked_recommendations=checked_recommendations,
            checked_components=checked_components,
            ai_validation_status=ai_validation_status,
        )

    def _validate_ai(
        self,
        run_id: str,
        *,
        present_kinds: set[str],
        ai_requested: bool,
        issues: list[ValidationIssue],
    ) -> str:
        if KnowledgeArtifactKind.AI_EXECUTION.value not in present_kinds:
            if ai_requested:
                issues.append(
                    ValidationIssue(
                        code="ai_execution_missing",
                        severity=ValidationSeverity.ERROR,
                        message="AI was requested but AI execution artifact is missing",
                        entity_type="artifact",
                        entity_id=KnowledgeArtifactKind.AI_EXECUTION.value,
                        related_ids=(run_id,),
                    )
                )
                return "missing"
            return "not_requested"

        execution = self._queries.get_ai_execution(run_id)
        if execution is None:
            issues.append(
                ValidationIssue(
                    code="ai_execution_unreadable",
                    severity=ValidationSeverity.ERROR,
                    message="AI execution artifact could not be read",
                    entity_type="artifact",
                    entity_id=KnowledgeArtifactKind.AI_EXECUTION.value,
                    related_ids=(run_id,),
                )
            )
            return "unreadable"

        status = str(execution.get("status", "unknown")).strip().lower()
        if status not in _RECOGNIZED_AI_STATUSES:
            issues.append(
                ValidationIssue(
                    code="ai_status_unrecognized",
                    severity=ValidationSeverity.WARNING,
                    message=f"Unrecognized AI execution status: {status}",
                    entity_type="ai_execution",
                    entity_id=run_id,
                )
            )

        if status == "succeeded":
            enrichment = self._queries.get_ai_enrichment(run_id)
            if enrichment is None:
                issues.append(
                    ValidationIssue(
                        code="ai_enrichment_missing",
                        severity=ValidationSeverity.WARNING,
                        message="Successful AI execution lacks enrichment artifact",
                        entity_type="artifact",
                        entity_id=KnowledgeArtifactKind.AI_ENRICHMENT.value,
                        related_ids=(run_id,),
                    )
                )
            else:
                unresolved = _unresolved_ai_references(enrichment)
                if unresolved:
                    issues.append(
                        ValidationIssue(
                            code="ai_unresolved_references",
                            severity=ValidationSeverity.ERROR,
                            message="AI enrichment contains unresolved references",
                            entity_type="ai_enrichment",
                            entity_id=run_id,
                            related_ids=tuple(unresolved[:20]),
                        )
                    )
            return status

        # Failed AI must remain represented as failure, not fabricated success.
        if status != "not_requested":
            issues.append(
                ValidationIssue(
                    code="ai_execution_failed",
                    severity=ValidationSeverity.WARNING,
                    message=f"AI execution status is {status}",
                    entity_type="ai_execution",
                    entity_id=run_id,
                )
            )
        return status


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value.strip())
    except ValueError:
        return False
    return True


def _unresolved_ai_references(enrichment: dict[str, Any]) -> list[str]:
    unresolved: list[str] = []
    raw = enrichment.get("unresolved_references")
    if isinstance(raw, list):
        unresolved.extend(str(item) for item in raw if item)
    refs = enrichment.get("references")
    if isinstance(refs, list):
        for item in refs:
            if isinstance(item, dict) and item.get("resolved") is False:
                unresolved.append(str(item.get("id") or item.get("reference") or "unknown"))
    return unresolved
