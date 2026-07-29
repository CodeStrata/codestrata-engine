"""Knowledge agent: assemble persisted knowledge via KnowledgeQueryService."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from codestrata.application.agents.errors import AgentDependencyError, AgentEvidenceError
from codestrata.application.agents.evidence import (
    AgentEvidence,
    EvidenceSourceKind,
    evidence_id_for,
)
from codestrata.application.agents.policies import AgentExecutionPolicy
from codestrata.application.knowledge.queries.errors import (
    KnowledgeQueryError,
    RepositoryQueryNotFoundError,
)
from codestrata.application.knowledge.queries.models import (
    AssessmentRunSummary,
    ComponentView,
    DependencyQueryResult,
    FindingExplanation,
    FindingView,
    RecommendationExplanation,
    RecommendationView,
    RepositorySummary,
    SnapshotComparison,
    SnapshotSummary,
)
from codestrata.application.knowledge.queries.service import KnowledgeQueryService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepositoryKnowledgeContext:
    """Bounded repository + latest assessment context."""

    repository: RepositorySummary
    latest_run: AssessmentRunSummary | None = None
    latest_snapshot: SnapshotSummary | None = None
    previous_run: AssessmentRunSummary | None = None
    previous_snapshot: SnapshotSummary | None = None


@dataclass
class AssessmentKnowledgePackage:
    """Bounded assessment package for review/validation workflows."""

    repository: RepositorySummary
    run: AssessmentRunSummary
    snapshot: SnapshotSummary | None
    previous_run: AssessmentRunSummary | None = None
    previous_snapshot: SnapshotSummary | None = None
    findings: tuple[FindingView, ...] = ()
    recommendations: tuple[RecommendationView, ...] = ()
    components: tuple[ComponentView, ...] = ()
    dependency_samples: tuple[DependencyQueryResult, ...] = ()
    finding_explanations: tuple[FindingExplanation, ...] = ()
    recommendation_explanations: tuple[RecommendationExplanation, ...] = ()
    ai_execution: dict[str, Any] | None = None
    ai_enrichment: dict[str, Any] | None = None
    snapshot_comparison: SnapshotComparison | None = None
    evidence: list[AgentEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class KnowledgeAgent:
    """Retrieve and assemble persisted engineering knowledge.

    Uses only :class:`KnowledgeQueryService`. Does not scan repositories,
    run assessments, or touch persistence infrastructure.
    """

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

    def resolve_repository(self, identifier: str) -> RepositorySummary:
        try:
            return self._queries.resolve_repository(identifier)
        except RepositoryQueryNotFoundError:
            raise
        except KnowledgeQueryError as error:
            raise AgentEvidenceError(str(error)) from error

    def get_latest_repository_context(
        self,
        identifier: str,
        *,
        branch: str | None = None,
    ) -> RepositoryKnowledgeContext:
        repository = self.resolve_repository(identifier)
        latest_run = self._queries.get_latest_completed_run(
            repository.repository_id,
            branch=branch,
        )
        latest_snapshot: SnapshotSummary | None = None
        if latest_run is not None and latest_run.snapshot_id is not None:
            latest_snapshot = self._queries.get_repository_snapshot(latest_run.snapshot_id)
        elif repository.latest_snapshot_id is not None:
            latest_snapshot = self._queries.get_repository_snapshot(repository.latest_snapshot_id)

        previous_run: AssessmentRunSummary | None = None
        previous_snapshot: SnapshotSummary | None = None
        runs = self._queries.list_assessment_runs(
            repository.repository_id,
            limit=5,
        )
        completed = [item for item in runs if item.status.value == "completed"]
        if latest_run is not None:
            for candidate in completed:
                if candidate.run_id != latest_run.run_id:
                    previous_run = candidate
                    if candidate.snapshot_id is not None:
                        previous_snapshot = self._queries.get_repository_snapshot(
                            candidate.snapshot_id
                        )
                    break

        logger.info(
            "knowledge.resolve_repository",
            extra={
                "repository_id": repository.repository_id,
                "run_id": None if latest_run is None else latest_run.run_id,
                "snapshot_id": None if latest_snapshot is None else latest_snapshot.snapshot_id,
            },
        )
        return RepositoryKnowledgeContext(
            repository=repository,
            latest_run=latest_run,
            latest_snapshot=latest_snapshot,
            previous_run=previous_run,
            previous_snapshot=previous_snapshot,
        )

    def get_assessment_context(self, run_id: str) -> AssessmentRunSummary:
        return self._queries.get_assessment_run(run_id)

    def get_snapshot_change_context(
        self,
        previous_snapshot_id: str,
        current_snapshot_id: str,
    ) -> SnapshotComparison:
        return self._queries.compare_repository_snapshots(
            previous_snapshot_id,
            current_snapshot_id,
        )

    def get_finding_evidence(
        self,
        run_id: str,
        finding_id: str,
    ) -> tuple[FindingExplanation, AgentEvidence]:
        explanation = self._queries.explain_finding(run_id, finding_id)
        evidence = AgentEvidence(
            evidence_id=evidence_id_for(EvidenceSourceKind.FINDING_EXPLANATION, finding_id),
            evidence_type="finding_explanation",
            source_id=finding_id,
            source_kind=EvidenceSourceKind.FINDING_EXPLANATION,
            title=explanation.finding.title,
            summary=explanation.finding.description[:240],
            related_ids=(run_id, *explanation.finding.subject_ids),
            deterministic=True,
        )
        return explanation, evidence

    def get_recommendation_evidence(
        self,
        run_id: str,
        recommendation_id: str,
    ) -> tuple[RecommendationExplanation, AgentEvidence]:
        explanation = self._queries.explain_recommendation(run_id, recommendation_id)
        evidence = AgentEvidence(
            evidence_id=evidence_id_for(
                EvidenceSourceKind.RECOMMENDATION_EXPLANATION,
                recommendation_id,
            ),
            evidence_type="recommendation_explanation",
            source_id=recommendation_id,
            source_kind=EvidenceSourceKind.RECOMMENDATION_EXPLANATION,
            title=explanation.recommendation.title,
            summary=explanation.recommendation.summary[:240],
            related_ids=(run_id, *explanation.recommendation.related_finding_ids),
            deterministic=True,
        )
        return explanation, evidence

    def build_repository_review_context(
        self,
        identifier: str,
        *,
        branch: str | None = None,
        include_snapshot_comparison: bool = True,
        run_id: str | None = None,
    ) -> AssessmentKnowledgePackage:
        context = self.get_latest_repository_context(identifier, branch=branch)
        repository = context.repository
        run = context.latest_run
        if run_id is not None:
            run = self._queries.get_assessment_run(run_id)
            if run.repository_id != repository.repository_id:
                raise AgentEvidenceError("Requested run does not belong to the resolved repository")
        if run is None:
            raise AgentEvidenceError(f"No completed assessment found for repository {identifier!r}")

        snapshot: SnapshotSummary | None = None
        if run.snapshot_id is not None:
            snapshot = self._queries.get_repository_snapshot(run.snapshot_id)

        findings = self._queries.get_findings(run.run_id)[: self._policy.max_findings]
        recommendations = self._queries.get_recommendations(run.run_id)[
            : self._policy.max_recommendations
        ]
        components = self._queries.list_components(
            run.run_id,
            limit=self._policy.max_components,
        )

        dependency_samples: list[DependencyQueryResult] = []
        for component in components[: min(5, len(components))]:
            try:
                dependency_samples.append(
                    self._queries.get_component_dependencies(
                        run.run_id,
                        component.component_id,
                        depth=self._policy.dependency_depth,
                        limit=50,
                    )
                )
            except KnowledgeQueryError as error:
                logger.info(
                    "knowledge.dependency_skip",
                    extra={
                        "run_id": run.run_id,
                        "component_id": component.component_id,
                        "error_code": type(error).__name__,
                    },
                )

        finding_explanations: list[FindingExplanation] = []
        recommendation_explanations: list[RecommendationExplanation] = []
        evidence: list[AgentEvidence] = []
        warnings: list[str] = []

        evidence.append(
            AgentEvidence(
                evidence_id=evidence_id_for(
                    EvidenceSourceKind.REPOSITORY,
                    repository.repository_id,
                ),
                evidence_type="repository_summary",
                source_id=repository.repository_id,
                source_kind=EvidenceSourceKind.REPOSITORY,
                title=repository.display_name,
                summary=f"canonical_key={repository.canonical_key}",
                related_ids=(repository.repository_id,),
                deterministic=True,
            )
        )
        evidence.append(
            AgentEvidence(
                evidence_id=evidence_id_for(EvidenceSourceKind.ASSESSMENT_RUN, run.run_id),
                evidence_type="assessment_run",
                source_id=run.run_id,
                source_kind=EvidenceSourceKind.ASSESSMENT_RUN,
                title=f"Assessment {run.status.value}",
                summary=f"mode={run.mode} branch={run.branch or '-'}",
                related_ids=(
                    run.repository_id,
                    *([] if run.snapshot_id is None else [run.snapshot_id]),
                ),
                deterministic=True,
            )
        )
        if snapshot is not None:
            evidence.append(
                AgentEvidence(
                    evidence_id=evidence_id_for(
                        EvidenceSourceKind.SNAPSHOT,
                        snapshot.snapshot_id,
                    ),
                    evidence_type="snapshot",
                    source_id=snapshot.snapshot_id,
                    source_kind=EvidenceSourceKind.SNAPSHOT,
                    title="Repository snapshot",
                    summary=f"revision={snapshot.revision_id}",
                    related_ids=(snapshot.repository_id,),
                    deterministic=True,
                )
            )

        for finding in findings[:10]:
            if _looks_like_uuid(finding.finding_id):
                warnings.append(
                    f"Phase 1 UUID finding id is not authoritative: {finding.finding_id}"
                )
                continue
            evidence.append(
                AgentEvidence(
                    evidence_id=evidence_id_for(
                        EvidenceSourceKind.FINDING,
                        finding.finding_id,
                    ),
                    evidence_type="finding",
                    source_id=finding.finding_id,
                    source_kind=EvidenceSourceKind.FINDING,
                    title=finding.title,
                    summary=f"{finding.severity}/{finding.category}",
                    related_ids=(run.run_id, *finding.subject_ids[:5]),
                    deterministic=True,
                )
            )
            try:
                explanation, _ = self.get_finding_evidence(run.run_id, finding.finding_id)
                finding_explanations.append(explanation)
            except KnowledgeQueryError:
                warnings.append(f"Unable to explain finding {finding.finding_id}")

        for recommendation in recommendations[:10]:
            evidence.append(
                AgentEvidence(
                    evidence_id=evidence_id_for(
                        EvidenceSourceKind.RECOMMENDATION,
                        recommendation.recommendation_id,
                    ),
                    evidence_type="recommendation",
                    source_id=recommendation.recommendation_id,
                    source_kind=EvidenceSourceKind.RECOMMENDATION,
                    title=recommendation.title,
                    summary=f"{recommendation.priority}/{recommendation.category}",
                    related_ids=(run.run_id, *recommendation.related_finding_ids[:5]),
                    deterministic=True,
                )
            )
            try:
                rec_explanation, _ = self.get_recommendation_evidence(
                    run.run_id,
                    recommendation.recommendation_id,
                )
                recommendation_explanations.append(rec_explanation)
            except KnowledgeQueryError:
                warnings.append(
                    f"Unable to explain recommendation {recommendation.recommendation_id}"
                )

        ai_execution = None
        ai_enrichment = None
        if self._policy.include_ai_context:
            ai_execution = self._queries.get_ai_execution(run.run_id)
            ai_enrichment = self._queries.get_ai_enrichment(run.run_id)
            if ai_execution is not None:
                evidence.append(
                    AgentEvidence(
                        evidence_id=evidence_id_for(
                            EvidenceSourceKind.AI_EXECUTION,
                            run.run_id,
                        ),
                        evidence_type="ai_execution",
                        source_id=run.run_id,
                        source_kind=EvidenceSourceKind.AI_EXECUTION,
                        title="AI execution artifact",
                        summary=str(ai_execution.get("status", "unknown")),
                        related_ids=(run.run_id,),
                        deterministic=False,
                    )
                )
            if ai_enrichment is not None:
                evidence.append(
                    AgentEvidence(
                        evidence_id=evidence_id_for(
                            EvidenceSourceKind.AI_ENRICHMENT,
                            run.run_id,
                        ),
                        evidence_type="ai_enrichment",
                        source_id=run.run_id,
                        source_kind=EvidenceSourceKind.AI_ENRICHMENT,
                        title="AI enrichment artifact",
                        summary="AI enrichment present",
                        related_ids=(run.run_id,),
                        deterministic=False,
                    )
                )

        comparison: SnapshotComparison | None = None
        if (
            include_snapshot_comparison
            and context.previous_snapshot is not None
            and snapshot is not None
            and context.previous_snapshot.snapshot_id != snapshot.snapshot_id
        ):
            comparison = self.get_snapshot_change_context(
                context.previous_snapshot.snapshot_id,
                snapshot.snapshot_id,
            )
            evidence.append(
                AgentEvidence(
                    evidence_id=evidence_id_for(
                        EvidenceSourceKind.SNAPSHOT_COMPARISON,
                        f"{comparison.previous_snapshot_id}:{comparison.current_snapshot_id}",
                    ),
                    evidence_type="snapshot_comparison",
                    source_id=f"{comparison.previous_snapshot_id}:{comparison.current_snapshot_id}",
                    source_kind=EvidenceSourceKind.SNAPSHOT_COMPARISON,
                    title="Snapshot comparison",
                    summary=(
                        f"added={comparison.counts.added} "
                        f"modified={comparison.counts.modified} "
                        f"deleted={comparison.counts.deleted}"
                    ),
                    related_ids=(
                        comparison.previous_snapshot_id,
                        comparison.current_snapshot_id,
                    ),
                    deterministic=True,
                )
            )

        return AssessmentKnowledgePackage(
            repository=repository,
            run=run,
            snapshot=snapshot,
            previous_run=context.previous_run,
            previous_snapshot=context.previous_snapshot,
            findings=findings,
            recommendations=recommendations,
            components=components,
            dependency_samples=tuple(dependency_samples),
            finding_explanations=tuple(finding_explanations),
            recommendation_explanations=tuple(recommendation_explanations),
            ai_execution=ai_execution,
            ai_enrichment=ai_enrichment,
            snapshot_comparison=comparison,
            evidence=evidence,
            warnings=warnings,
        )


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value.strip())
    except ValueError:
        return False
    return True
