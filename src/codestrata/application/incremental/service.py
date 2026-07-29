"""Transport-neutral incremental planning service (analysis only)."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from codestrata import RULESET_VERSION, __version__
from codestrata.application.incremental.changes import ChangeClassifier
from codestrata.application.incremental.compatibility import CompatibilityEvaluator
from codestrata.application.incremental.eligibility import PreviousRunEligibilityChecker
from codestrata.application.incremental.errors import (
    IncrementalEligibilityError,
    IncrementalManifestError,
    IncrementalPlanningError,
)
from codestrata.application.incremental.fingerprints import (
    EngineCompatibilityFingerprint,
    current_engine_fingerprint,
)
from codestrata.application.incremental.impact import ImpactAnalyzer
from codestrata.application.incremental.models import (
    CandidateRepositoryState,
    CompatibilityResult,
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
    IncrementalPlanningRequest,
    IncrementalPlanStep,
    IncrementalStepType,
    RepositoryChangeSet,
)
from codestrata.application.incremental.planner import IncrementalPlanner
from codestrata.application.incremental.policies import IncrementalPlanningPolicy
from codestrata.application.incremental.ports import CandidateManifestProvider
from codestrata.application.incremental.reuse import ReusePolicy
from codestrata.application.knowledge.queries.errors import (
    KnowledgeQueryError,
    RepositoryQueryNotFoundError,
)
from codestrata.application.knowledge.queries.models import (
    AssessmentRunSummary,
    FindingView,
    RecommendationView,
)
from codestrata.application.knowledge.queries.service import KnowledgeQueryService

logger = logging.getLogger(__name__)


class IncrementalPlanningService:
    """Create incremental assessment plans without executing assessment work."""

    def __init__(
        self,
        *,
        query_service: KnowledgeQueryService | None = None,
        candidate_manifest_provider: CandidateManifestProvider | None = None,
        policy: IncrementalPlanningPolicy | None = None,
        change_classifier: ChangeClassifier | None = None,
        compatibility_evaluator: CompatibilityEvaluator | None = None,
        impact_analyzer: ImpactAnalyzer | None = None,
        reuse_policy: ReusePolicy | None = None,
        planner: IncrementalPlanner | None = None,
    ) -> None:
        self._queries = query_service
        self._candidate_provider = candidate_manifest_provider
        self._policy = policy or IncrementalPlanningPolicy()
        self._changes = change_classifier or ChangeClassifier()
        self._compatibility = compatibility_evaluator or CompatibilityEvaluator()
        self._impact = impact_analyzer or ImpactAnalyzer()
        self._reuse = reuse_policy or ReusePolicy()
        self._planner = planner or IncrementalPlanner()

    def create_plan(self, request: IncrementalPlanningRequest) -> IncrementalAssessmentPlan:
        started = time.perf_counter()
        policy = request.policy or self._policy
        warnings: list[str] = []

        candidate = request.candidate
        if candidate is None:
            if self._candidate_provider is None:
                raise IncrementalManifestError(
                    "candidate manifest is required when no CandidateManifestProvider is configured"
                )
            candidate = self._candidate_provider.create_candidate_manifest(
                request.repository_identifier,
                request.branch,
            )
        warnings.extend(candidate.warnings)

        if self._queries is None:
            plan = self._full_rebuild_without_base(
                candidate=candidate,
                repository_id=None,
                reasons=("no_query_service", "no_previous_run"),
                warnings=tuple(warnings),
                policy=policy,
            )
            self._log_duration(plan, started)
            return plan

        try:
            repository = self._queries.resolve_repository(request.repository_identifier)
        except RepositoryQueryNotFoundError as error:
            raise IncrementalPlanningError(str(error)) from error
        except KnowledgeQueryError as error:
            raise IncrementalPlanningError(str(error)) from error

        if candidate.repository_key and candidate.repository_key not in {
            repository.canonical_key,
            repository.display_name,
            repository.repository_id,
            request.repository_identifier,
        }:
            warnings.append("candidate_repository_key_differs")

        previous_run = self._resolve_previous_run(
            repository_id=repository.repository_id,
            previous_run_id=request.previous_run_id,
            branch=request.branch or candidate.branch,
        )
        if previous_run is None:
            plan = self._full_rebuild_without_base(
                candidate=candidate,
                repository_id=repository.repository_id,
                reasons=("no_previous_run",),
                warnings=tuple(warnings),
                policy=policy,
            )
            self._log_duration(plan, started)
            return plan

        eligibility = PreviousRunEligibilityChecker(self._queries).check(
            previous_run.run_id,
            expected_repository_id=repository.repository_id,
            branch=request.branch or candidate.branch,
        )
        if not eligibility.eligible:
            reasons = eligibility.reasons or ("base_ineligible",)
            compatibility = CompatibilityResult(
                compatible=False,
                blocking_reasons=reasons,
            )
            impact = self._impact.analyze(
                RepositoryChangeSet(),
                repository_graph=None,
                compatibility=compatibility,
                policy=policy,
            )
            plan = self._planner.plan(
                repository_id=repository.repository_id,
                previous_run_id=previous_run.run_id,
                previous_snapshot_id=previous_run.snapshot_id,
                candidate_snapshot_id=None,
                changes=RepositoryChangeSet(),
                compatibility=compatibility,
                impact=impact,
                reuse=(),
                policy=policy,
                warnings=tuple([*warnings, *eligibility.warnings]),
            ).model_copy(
                update={
                    "mode": IncrementalPlanMode.FULL_REBUILD,
                    "full_rebuild_required": True,
                    "full_rebuild_reasons": reasons,
                    "steps": (
                        IncrementalPlanStep(
                            sequence=1,
                            step_type=IncrementalStepType.FULL_REBUILD,
                            reasons=reasons,
                        ),
                    ),
                }
            )
            self._log_duration(plan, started)
            return plan

        assert previous_run.snapshot_id is not None
        try:
            previous_manifest = self._queries.get_repository_manifest(previous_run.snapshot_id)
        except KnowledgeQueryError as error:
            raise IncrementalEligibilityError(
                f"Previous snapshot manifest unavailable: {error}"
            ) from error

        changes = self._changes.classify(
            previous_manifest,
            candidate.manifest,
            previous_snapshot_id=previous_run.snapshot_id,
            candidate_snapshot_id=None,
        )

        previous_engine = _infer_previous_engine(previous_run)
        changed_languages = frozenset(
            lang
            for item in (*changes.added, *changes.modified, *changes.deleted)
            if (
                lang := (
                    item.current_fingerprint.language
                    if item.current_fingerprint is not None
                    else None
                )
                or (
                    item.previous_fingerprint.language
                    if item.previous_fingerprint is not None
                    else None
                )
            )
        )
        compatibility = self._compatibility.evaluate(
            previous_engine,
            candidate.engine,
            policy=policy,
            changed_languages=changed_languages,
        )

        repository_graph = None
        findings: tuple[FindingView, ...] = ()
        recommendations: tuple[RecommendationView, ...] = ()
        try:
            repository_graph = self._queries.get_repository_graph(run_id=previous_run.run_id)
            findings = self._queries.get_findings(previous_run.run_id)
            recommendations = self._queries.get_recommendations(previous_run.run_id)
        except KnowledgeQueryError:
            warnings.append("previous_knowledge_partially_unavailable")

        impact = self._impact.analyze(
            changes,
            repository_graph=repository_graph,
            findings=findings,
            recommendations=recommendations,
            compatibility=compatibility,
            policy=policy,
        )

        if not findings:
            has_stable_findings = True
        else:
            has_stable_findings = not all(_looks_like_uuid(item.finding_id) for item in findings)

        reuse = self._reuse.evaluate(
            changes=changes,
            impact=impact,
            compatibility=compatibility,
            policy=policy,
            previous_artifacts_complete=eligibility.eligible,
            missing_artifacts=eligibility.missing_artifacts,
            has_stable_findings=has_stable_findings,
            ai_inputs_unchanged=(changes.change_count == 0 and compatibility.compatible),
            ai_config_unchanged=compatibility.compatible,
        )

        plan = self._planner.plan(
            repository_id=repository.repository_id,
            previous_run_id=previous_run.run_id,
            previous_snapshot_id=previous_run.snapshot_id,
            candidate_snapshot_id=None,
            changes=changes,
            compatibility=compatibility,
            impact=impact,
            reuse=reuse,
            policy=policy,
            warnings=tuple(dict.fromkeys([*warnings, *eligibility.warnings])),
        )
        self._log_duration(plan, started)
        return plan

    def _resolve_previous_run(
        self,
        *,
        repository_id: str,
        previous_run_id: str | None,
        branch: str | None,
    ) -> AssessmentRunSummary | None:
        assert self._queries is not None
        if previous_run_id is not None:
            return self._queries.get_assessment_run(previous_run_id)
        return self._queries.get_latest_completed_run(repository_id, branch=branch)

    def _full_rebuild_without_base(
        self,
        *,
        candidate: CandidateRepositoryState,
        repository_id: str | None,
        reasons: tuple[str, ...],
        warnings: tuple[str, ...],
        policy: IncrementalPlanningPolicy,
    ) -> IncrementalAssessmentPlan:
        empty = RepositoryChangeSet()
        compatibility = CompatibilityResult(
            compatible=False,
            blocking_reasons=reasons,
        )
        impact = self._impact.analyze(
            empty,
            repository_graph=None,
            compatibility=compatibility,
            policy=policy,
        )
        return self._planner.plan(
            repository_id=repository_id,
            previous_run_id=None,
            previous_snapshot_id=None,
            candidate_snapshot_id=None,
            changes=empty,
            compatibility=compatibility,
            impact=impact,
            reuse=(),
            policy=policy,
            warnings=warnings,
        ).model_copy(
            update={
                "mode": IncrementalPlanMode.FULL_REBUILD,
                "full_rebuild_required": True,
                "full_rebuild_reasons": reasons,
                "steps": (
                    IncrementalPlanStep(
                        sequence=1,
                        step_type=IncrementalStepType.FULL_REBUILD,
                        reasons=reasons,
                    ),
                ),
                "change_summary": {
                    "candidate_manifest_hash": candidate.content_fingerprint.manifest_hash,
                },
            }
        )

    @staticmethod
    def _log_duration(plan: IncrementalAssessmentPlan, started: float) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "incremental.planning_complete",
            extra={
                "plan_id": plan.plan_id,
                "repository_id": plan.repository_id,
                "previous_run_id": plan.previous_run_id,
                "mode": plan.mode.value,
                "duration_ms": duration_ms,
                "full_rebuild_required": plan.full_rebuild_required,
            },
        )


def _infer_previous_engine(run: AssessmentRunSummary) -> EngineCompatibilityFingerprint:
    """Infer previous engine fingerprints from run metadata.

    Phase 2F.1 does not yet persist full engine fingerprints on snapshots.
    Functional fingerprints are assumed equal to the current process when the
    run's ruleset version matches; otherwise rules are marked as the run's
    ruleset. Tool version uses the persisted run.codestrata_version.
    """

    current = current_engine_fingerprint()
    rules = (
        current.rules if run.ruleset_version == RULESET_VERSION else f"rules:{run.ruleset_version}"
    )
    return current.model_copy(
        update={
            "tool_version": run.codestrata_version or __version__,
            "rules": rules,
            "artifact_schemas": dict(current.artifact_schemas),
        }
    )


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value.strip())
    except ValueError:
        return False
    return True
