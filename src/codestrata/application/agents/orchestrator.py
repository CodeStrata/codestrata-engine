"""Deterministic AgentOrchestrator over application services."""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from codestrata.application.agents.assessment_agent import AssessmentAgent
from codestrata.application.agents.context import WorkflowContext
from codestrata.application.agents.errors import (
    AgentEvidenceError,
    AgentExecutionError,
    AgentStepError,
    AgentWorkflowBlockedError,
)
from codestrata.application.agents.evidence import dedupe_evidence
from codestrata.application.agents.knowledge_agent import KnowledgeAgent
from codestrata.application.agents.models import (
    AgentDecision,
    AgentName,
    AgentStatus,
    AgentStep,
    AssessmentValidationRequest,
    AssessmentValidationWorkflowResult,
    ComponentSummary,
    FindingSummary,
    ModernizationReviewRequest,
    ModernizationReviewResult,
    RecommendationGroup,
    RecommendationSummary,
    RepositoryAssessmentRequest,
    RepositoryAssessmentResult,
    RepositoryReviewRequest,
    RepositoryReviewResult,
    SnapshotReviewRequest,
    SnapshotReviewResult,
    WorkflowType,
)
from codestrata.application.agents.planner import AgentPlanner, DeterministicAgentPlanner
from codestrata.application.agents.policies import AgentExecutionPolicy
from codestrata.application.agents.validation_agent import ValidationAgent
from codestrata.application.knowledge.queries.errors import (
    KnowledgeQueryError,
    RepositoryQueryNotFoundError,
)
from codestrata.application.knowledge.queries.models import (
    ComponentView,
    FindingView,
    RecommendationView,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AgentOrchestrator:
    """Coordinate Knowledge, Assessment, and Validation agents.

    Workflows are explicit and bounded. Agents call application services
    directly — never MCP, CLI, SQLite, or report files.
    """

    def __init__(
        self,
        *,
        knowledge_agent: KnowledgeAgent,
        assessment_agent: AssessmentAgent | None = None,
        validation_agent: ValidationAgent,
        policy: AgentExecutionPolicy | None = None,
        planner: AgentPlanner | None = None,
    ) -> None:
        self._knowledge = knowledge_agent
        self._assessment = assessment_agent
        self._validation = validation_agent
        self._policy = policy or AgentExecutionPolicy()
        self._planner = planner or DeterministicAgentPlanner()

    def review_repository(
        self,
        request: RepositoryReviewRequest,
    ) -> RepositoryReviewResult:
        context = WorkflowContext(
            workflow_type=WorkflowType.REPOSITORY_REVIEW,
            repository_identifier=request.repository_identifier,
            branch=request.branch,
        )
        plan = self._planner.plan(WorkflowType.REPOSITORY_REVIEW)
        self._enforce_plan_bounds(plan.steps)

        try:
            package = self._run_step(
                context,
                name="resolve_repository_context",
                agent=AgentName.KNOWLEDGE,
                action=lambda: self._knowledge.build_repository_review_context(
                    request.repository_identifier,
                    branch=request.branch,
                    include_snapshot_comparison=request.include_snapshot_comparison,
                ),
            )
        except (
            KnowledgeQueryError,
            AgentExecutionError,
            AgentStepError,
            AgentEvidenceError,
        ) as error:
            context.complete(AgentStatus.FAILED)
            return RepositoryReviewResult(
                workflow_id=context.workflow_id,
                status=AgentStatus.FAILED,
                steps=tuple(context.steps),
                warnings=tuple(context.warnings) + (str(error),),
            )

        context.repository_id = package.repository.repository_id
        context.run_id = package.run.run_id
        context.snapshot_id = None if package.snapshot is None else package.snapshot.snapshot_id
        context.add_evidence(*package.evidence)
        for warning in package.warnings:
            context.add_warning(warning)

        self._record_completed_step(
            context,
            name="retrieve_review_artifacts",
            agent=AgentName.KNOWLEDGE,
            message="Loaded findings, recommendations, and components",
        )

        validation = self._run_step(
            context,
            name="validate_assessment",
            agent=AgentName.VALIDATION,
            action=lambda: self._validation.validate_assessment(
                package.run.run_id,
                expected_repository_id=package.repository.repository_id,
            ),
        )

        if validation.blocking and self._policy.stop_on_blocking_validation:
            context.complete(AgentStatus.BLOCKED)
            context.add_decision(
                AgentDecision(
                    decision_type="validation",
                    outcome="blocked",
                    reason="Blocking validation issues present",
                )
            )
            return self._build_review_result(
                context,
                package=package,
                validation=validation,
                status=AgentStatus.BLOCKED,
            )

        self._record_completed_step(
            context,
            name="assemble_review",
            agent=AgentName.ORCHESTRATOR,
            message="Assembled grounded repository review",
        )
        context.complete(AgentStatus.COMPLETED)
        context.add_decision(
            AgentDecision(
                decision_type="review",
                outcome="completed",
                reason="Repository review assembled from persisted knowledge",
                evidence_ids=tuple(item.evidence_id for item in package.evidence[:20]),
            )
        )
        return self._build_review_result(
            context,
            package=package,
            validation=validation,
            status=AgentStatus.COMPLETED,
        )

    def assess_repository(
        self,
        request: RepositoryAssessmentRequest,
        *,
        provider: object | None = None,
        scanner: object | None = None,
        knowledge_store: object | None = None,
        output_directory: Path | None = None,
    ) -> RepositoryAssessmentResult:
        if self._assessment is None:
            raise AgentExecutionError("AssessmentAgent is not configured")

        context = WorkflowContext(
            workflow_type=WorkflowType.REPOSITORY_ASSESSMENT,
            repository_identifier=request.repository,
            branch=request.branch,
        )
        plan = self._planner.plan(WorkflowType.REPOSITORY_ASSESSMENT)
        self._enforce_plan_bounds(plan.steps)

        prior_run_id: str | None = None
        prior_snapshot_id: str | None = None
        try:
            prior = self._run_step(
                context,
                name="resolve_repository_context",
                agent=AgentName.KNOWLEDGE,
                action=lambda: self._knowledge.get_latest_repository_context(
                    request.repository,
                    branch=request.branch,
                ),
                allow_not_found=True,
            )
            if prior is not None:
                context.repository_id = prior.repository.repository_id
                prior_run_id = None if prior.latest_run is None else prior.latest_run.run_id
                prior_snapshot_id = (
                    None if prior.latest_snapshot is None else prior.latest_snapshot.snapshot_id
                )
                context.prior_run_id = prior_run_id
                context.prior_snapshot_id = prior_snapshot_id
        except AgentStepError as error:
            context.add_warning(str(error))

        self._record_completed_step(
            context,
            name="retrieve_previous_assessment",
            agent=AgentName.KNOWLEDGE,
            message=(
                "No previous assessment" if prior_run_id is None else f"Previous run {prior_run_id}"
            ),
        )

        assessment_request = request
        if output_directory is not None:
            assessment_request = request.model_copy(
                update={"output_directory": str(output_directory)}
            )

        try:
            assessment_agent = self._assessment
            assessment = self._run_step(
                context,
                name="run_assessment",
                agent=AgentName.ASSESSMENT,
                action=lambda: assessment_agent.run_assessment(
                    assessment_request,
                    provider=provider,
                    scanner=scanner,
                    knowledge_store=knowledge_store,
                ),
            )
        except (AgentExecutionError, AgentStepError) as error:
            context.complete(AgentStatus.FAILED)
            return RepositoryAssessmentResult(
                workflow_id=context.workflow_id,
                status=AgentStatus.FAILED,
                ai_requested=request.with_ai,
                prior_run_id=prior_run_id,
                prior_snapshot_id=prior_snapshot_id,
                steps=tuple(context.steps),
                warnings=tuple(context.warnings) + (str(error),),
            )

        for warning in assessment.warnings:
            context.add_warning(warning)
        context.repository_id = assessment.repository_id
        context.snapshot_id = assessment.snapshot_id
        context.run_id = assessment.run_id

        run_summary = None
        if assessment.run_id is not None:
            try:
                run_summary = self._run_step(
                    context,
                    name="retrieve_new_assessment",
                    agent=AgentName.KNOWLEDGE,
                    action=lambda: self._knowledge.get_assessment_context(
                        assessment.run_id  # type: ignore[arg-type]
                    ),
                )
            except AgentStepError as error:
                context.add_warning(str(error))
        else:
            self._record_completed_step(
                context,
                name="retrieve_new_assessment",
                agent=AgentName.KNOWLEDGE,
                status=AgentStatus.SKIPPED,
                message="No run_id returned from assessment",
            )

        validation = None
        status = AgentStatus.COMPLETED
        if assessment.run_id is not None:
            validation = self._run_step(
                context,
                name="validate_assessment",
                agent=AgentName.VALIDATION,
                action=lambda: self._validation.validate_assessment(
                    assessment.run_id,  # type: ignore[arg-type]
                    expected_repository_id=assessment.repository_id,
                    ai_requested=request.with_ai,
                ),
            )
            if validation.blocking and self._policy.stop_on_blocking_validation:
                status = AgentStatus.BLOCKED
                context.add_decision(
                    AgentDecision(
                        decision_type="validation",
                        outcome="blocked",
                        reason="Blocking validation issues after assessment",
                    )
                )
        else:
            status = AgentStatus.FAILED
            context.add_warning("Assessment did not return knowledge run_id")

        self._record_completed_step(
            context,
            name="assemble_result",
            agent=AgentName.ORCHESTRATOR,
            message="Assembled assessment workflow result",
        )
        context.complete(status)
        command = assessment.command
        return RepositoryAssessmentResult(
            workflow_id=context.workflow_id,
            status=status,
            repository_id=assessment.repository_id,
            snapshot_id=assessment.snapshot_id,
            run_id=assessment.run_id,
            repository_display_name=command.repository_name,
            branch=request.branch,
            findings_count=command.findings_count,
            recommendations_count=command.recommendations_count,
            phase3_findings_count=command.rule_finding_count,
            phase3_recommendations_count=command.phase3_recommendation_count,
            ai_requested=request.with_ai,
            ai_status=("requested" if request.with_ai else "not_requested"),
            prior_run_id=prior_run_id,
            prior_snapshot_id=prior_snapshot_id,
            assessment=run_summary,
            validation=validation,
            evidence=dedupe_evidence(context.evidence),
            decisions=tuple(context.decisions),
            steps=tuple(context.steps),
            warnings=tuple(context.warnings),
        )

    def validate_assessment(
        self,
        request: AssessmentValidationRequest,
    ) -> AssessmentValidationWorkflowResult:
        context = WorkflowContext(
            workflow_type=WorkflowType.ASSESSMENT_VALIDATION,
            run_id=request.run_id,
            repository_id=request.repository_id,
        )
        plan = self._planner.plan(WorkflowType.ASSESSMENT_VALIDATION)
        self._enforce_plan_bounds(plan.steps)

        validation = self._run_step(
            context,
            name="validate_assessment",
            agent=AgentName.VALIDATION,
            action=lambda: self._validation.validate_assessment(
                request.run_id,
                expected_repository_id=request.repository_id,
            ),
        )
        snapshot_id: str | None = None
        repository_id = request.repository_id
        try:
            run = self._knowledge.get_assessment_context(request.run_id)
            snapshot_id = run.snapshot_id
            repository_id = run.repository_id
            context.repository_id = repository_id
            context.snapshot_id = snapshot_id
        except KnowledgeQueryError:
            pass

        status = (
            AgentStatus.BLOCKED
            if validation.blocking and self._policy.stop_on_blocking_validation
            else AgentStatus.COMPLETED
        )
        self._record_completed_step(
            context,
            name="assemble_result",
            agent=AgentName.ORCHESTRATOR,
            message="Assembled validation result",
        )
        context.complete(status)
        return AssessmentValidationWorkflowResult(
            workflow_id=context.workflow_id,
            status=status,
            run_id=request.run_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            validation=validation,
            evidence=dedupe_evidence(context.evidence),
            decisions=tuple(context.decisions),
            steps=tuple(context.steps),
            warnings=tuple(context.warnings),
        )

    def compare_repository_snapshots(
        self,
        request: SnapshotReviewRequest,
    ) -> SnapshotReviewResult:
        context = WorkflowContext(workflow_type=WorkflowType.SNAPSHOT_REVIEW)
        plan = self._planner.plan(WorkflowType.SNAPSHOT_REVIEW)
        self._enforce_plan_bounds(plan.steps)

        try:
            comparison = self._run_step(
                context,
                name="compare_snapshots",
                agent=AgentName.KNOWLEDGE,
                action=lambda: self._knowledge.get_snapshot_change_context(
                    request.previous_snapshot_id,
                    request.current_snapshot_id,
                ),
            )
        except (KnowledgeQueryError, AgentStepError) as error:
            context.complete(AgentStatus.FAILED)
            return SnapshotReviewResult(
                workflow_id=context.workflow_id,
                status=AgentStatus.FAILED,
                steps=tuple(context.steps),
                warnings=(str(error),),
            )

        self._record_completed_step(
            context,
            name="assemble_result",
            agent=AgentName.ORCHESTRATOR,
            message="Assembled snapshot comparison",
        )
        context.complete(AgentStatus.COMPLETED)
        return SnapshotReviewResult(
            workflow_id=context.workflow_id,
            status=AgentStatus.COMPLETED,
            comparison=comparison,
            evidence=dedupe_evidence(context.evidence),
            decisions=tuple(context.decisions),
            steps=tuple(context.steps),
            warnings=tuple(context.warnings),
        )

    def modernization_review(
        self,
        request: ModernizationReviewRequest,
    ) -> ModernizationReviewResult:
        context = WorkflowContext(
            workflow_type=WorkflowType.MODERNIZATION_REVIEW,
            repository_identifier=request.repository_identifier,
        )
        plan = self._planner.plan(WorkflowType.MODERNIZATION_REVIEW)
        self._enforce_plan_bounds(plan.steps)

        try:
            package = self._run_step(
                context,
                name="resolve_repository_context",
                agent=AgentName.KNOWLEDGE,
                action=lambda: self._knowledge.build_repository_review_context(
                    request.repository_identifier,
                    run_id=request.run_id,
                    include_snapshot_comparison=False,
                ),
            )
        except (
            KnowledgeQueryError,
            AgentStepError,
            AgentExecutionError,
            AgentEvidenceError,
        ) as error:
            context.complete(AgentStatus.FAILED)
            return ModernizationReviewResult(
                workflow_id=context.workflow_id,
                status=AgentStatus.FAILED,
                steps=tuple(context.steps),
                warnings=(str(error),),
            )

        context.repository_id = package.repository.repository_id
        context.run_id = package.run.run_id
        context.snapshot_id = None if package.snapshot is None else package.snapshot.snapshot_id
        context.add_evidence(*package.evidence)

        self._record_completed_step(
            context,
            name="retrieve_recommendations",
            agent=AgentName.KNOWLEDGE,
            message=f"Loaded {len(package.recommendations)} recommendations",
        )

        validation = self._run_step(
            context,
            name="validate_assessment",
            agent=AgentName.VALIDATION,
            action=lambda: self._validation.validate_assessment(
                package.run.run_id,
                expected_repository_id=package.repository.repository_id,
            ),
        )

        status = AgentStatus.COMPLETED
        if validation.blocking and self._policy.stop_on_blocking_validation:
            status = AgentStatus.BLOCKED

        finding_ids = {item.finding_id for item in package.findings}
        unresolved = tuple(
            item.recommendation_id
            for item in package.recommendations
            if any(fid not in finding_ids for fid in item.related_finding_ids)
        )
        groups = _group_recommendations(package.recommendations)
        phases = tuple(
            sorted({item.roadmap_phase for item in package.recommendations if item.roadmap_phase})
        )

        self._record_completed_step(
            context,
            name="assemble_modernization_review",
            agent=AgentName.ORCHESTRATOR,
            message="Assembled modernization review from persisted recommendations",
        )
        context.complete(status)
        return ModernizationReviewResult(
            workflow_id=context.workflow_id,
            status=status,
            repository_id=package.repository.repository_id,
            run_id=package.run.run_id,
            snapshot_id=None if package.snapshot is None else package.snapshot.snapshot_id,
            risk_summary=_finding_summary(package.findings),
            recommendation_groups=groups,
            roadmap_phases=phases,
            recommendation_summary=_recommendation_summary(package.recommendations),
            top_recommendations=tuple(
                package.recommendations[: min(10, self._policy.max_recommendations)]
            ),
            unresolved_recommendation_ids=unresolved,
            validation=validation,
            evidence=dedupe_evidence(context.evidence),
            decisions=tuple(context.decisions),
            steps=tuple(context.steps),
            warnings=tuple(context.warnings) + tuple(package.warnings),
        )

    def _enforce_plan_bounds(self, steps: tuple[object, ...]) -> None:
        if len(steps) > self._policy.max_steps:
            raise AgentWorkflowBlockedError(
                f"Workflow plan has {len(steps)} steps; policy max_steps={self._policy.max_steps}"
            )

    def _run_step(
        self,
        context: WorkflowContext,
        *,
        name: str,
        agent: AgentName,
        action: Callable[[], T],
        allow_not_found: bool = False,
    ) -> T:
        if len(context.steps) >= self._policy.max_steps:
            raise AgentWorkflowBlockedError(
                f"Exceeded max workflow steps ({self._policy.max_steps})"
            )
        started = datetime.now(UTC)
        started_perf = time.perf_counter()
        context.current_step = name
        try:
            result = action()
        except RepositoryQueryNotFoundError:
            if allow_not_found:
                duration_ms = (time.perf_counter() - started_perf) * 1000.0
                context.add_step(
                    AgentStep(
                        name=name,
                        agent=agent,
                        status=AgentStatus.SKIPPED,
                        started_at=started,
                        completed_at=datetime.now(UTC),
                        duration_ms=duration_ms,
                        message="Repository not yet registered",
                    )
                )
                return None  # type: ignore[return-value]
            duration_ms = (time.perf_counter() - started_perf) * 1000.0
            context.add_step(
                AgentStep(
                    name=name,
                    agent=agent,
                    status=AgentStatus.FAILED,
                    started_at=started,
                    completed_at=datetime.now(UTC),
                    duration_ms=duration_ms,
                    message="Repository not found",
                )
            )
            raise AgentStepError(f"Step {name} failed: repository not found") from None
        except Exception as error:
            duration_ms = (time.perf_counter() - started_perf) * 1000.0
            context.add_step(
                AgentStep(
                    name=name,
                    agent=agent,
                    status=AgentStatus.FAILED,
                    started_at=started,
                    completed_at=datetime.now(UTC),
                    duration_ms=duration_ms,
                    message=f"{type(error).__name__}",
                )
            )
            logger.info(
                "agent.step_failed",
                extra={
                    "workflow_id": context.workflow_id,
                    "workflow_type": context.workflow_type.value,
                    "agent_name": agent.value,
                    "step_name": name,
                    "run_id": context.run_id,
                    "repository_id": context.repository_id,
                    "snapshot_id": context.snapshot_id,
                    "status": "failed",
                    "duration_ms": duration_ms,
                },
            )
            if isinstance(error, (AgentExecutionError, AgentStepError, KnowledgeQueryError)):
                raise AgentStepError(f"Step {name} failed: {error}") from error
            raise AgentStepError(f"Step {name} failed: {type(error).__name__}") from error

        duration_ms = (time.perf_counter() - started_perf) * 1000.0
        context.add_step(
            AgentStep(
                name=name,
                agent=agent,
                status=AgentStatus.COMPLETED,
                started_at=started,
                completed_at=datetime.now(UTC),
                duration_ms=duration_ms,
            )
        )
        logger.info(
            "agent.step_complete",
            extra={
                "workflow_id": context.workflow_id,
                "workflow_type": context.workflow_type.value,
                "agent_name": agent.value,
                "step_name": name,
                "run_id": context.run_id,
                "repository_id": context.repository_id,
                "snapshot_id": context.snapshot_id,
                "status": "completed",
                "duration_ms": duration_ms,
            },
        )
        return result

    def _record_completed_step(
        self,
        context: WorkflowContext,
        *,
        name: str,
        agent: AgentName,
        message: str | None = None,
        status: AgentStatus = AgentStatus.COMPLETED,
    ) -> None:
        if len(context.steps) >= self._policy.max_steps:
            raise AgentWorkflowBlockedError(
                f"Exceeded max workflow steps ({self._policy.max_steps})"
            )
        now = datetime.now(UTC)
        context.add_step(
            AgentStep(
                name=name,
                agent=agent,
                status=status,
                started_at=now,
                completed_at=now,
                duration_ms=0.0,
                message=message,
            )
        )

    def _build_review_result(
        self,
        context: WorkflowContext,
        *,
        package: object,
        validation: object,
        status: AgentStatus,
    ) -> RepositoryReviewResult:
        from codestrata.application.agents.knowledge_agent import AssessmentKnowledgePackage

        assert isinstance(package, AssessmentKnowledgePackage)
        dependency_summary = {
            "sampled_components": len(package.dependency_samples),
            "dependency_edges": sum(len(item.dependencies) for item in package.dependency_samples),
            "truncated": any(item.truncated for item in package.dependency_samples),
        }
        ai_status = "not_present"
        if package.ai_execution is not None:
            ai_status = str(package.ai_execution.get("status", "unknown"))
        elif package.ai_enrichment is not None:
            ai_status = "enrichment_present"

        return RepositoryReviewResult(
            workflow_id=context.workflow_id,
            status=status,
            repository=package.repository,
            latest_run=package.run,
            latest_snapshot=package.snapshot,
            previous_run=package.previous_run,
            previous_snapshot=package.previous_snapshot,
            snapshot_changes=package.snapshot_comparison,
            finding_summary=_finding_summary(package.findings),
            recommendation_summary=_recommendation_summary(package.recommendations),
            top_findings=tuple(package.findings[:10]),
            top_recommendations=tuple(package.recommendations[:10]),
            component_summary=_component_summary(package.components),
            dependency_summary=dependency_summary,
            ai_status=ai_status,
            validation=validation,  # type: ignore[arg-type]
            evidence=dedupe_evidence(list(context.evidence) + list(package.evidence)),
            decisions=tuple(context.decisions),
            steps=tuple(context.steps),
            warnings=tuple(context.warnings),
        )


def _finding_summary(findings: tuple[FindingView, ...]) -> FindingSummary:
    by_severity: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    for item in findings:
        by_severity[item.severity] += 1
        by_category[item.category] += 1
    return FindingSummary(
        total=len(findings),
        by_severity=dict(sorted(by_severity.items())),
        by_category=dict(sorted(by_category.items())),
    )


def _recommendation_summary(
    recommendations: tuple[RecommendationView, ...],
) -> RecommendationSummary:
    by_priority: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    for item in recommendations:
        by_priority[item.priority] += 1
        by_category[item.category] += 1
    return RecommendationSummary(
        total=len(recommendations),
        by_priority=dict(sorted(by_priority.items())),
        by_category=dict(sorted(by_category.items())),
    )


def _component_summary(components: tuple[ComponentView, ...]) -> ComponentSummary:
    by_type: Counter[str] = Counter()
    for item in components:
        by_type[item.component_type] += 1
    return ComponentSummary(total=len(components), by_type=dict(sorted(by_type.items())))


def _group_recommendations(
    recommendations: tuple[RecommendationView, ...],
) -> tuple[RecommendationGroup, ...]:
    buckets: dict[tuple[str | None, str | None, str | None], list[str]] = {}
    for item in recommendations:
        key = (item.roadmap_phase, item.priority, item.category)
        buckets.setdefault(key, []).append(item.recommendation_id)
    groups: list[RecommendationGroup] = []
    for (phase, priority, category), ids in sorted(
        buckets.items(),
        key=lambda pair: (
            pair[0][0] or "",
            pair[0][1] or "",
            pair[0][2] or "",
        ),
    ):
        groups.append(
            RecommendationGroup(
                key="|".join(part or "-" for part in (phase, priority, category)),
                priority=priority,
                category=category,
                roadmap_phase=phase,
                recommendation_ids=tuple(ids),
            )
        )
    return tuple(groups)
