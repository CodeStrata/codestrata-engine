"""Incremental assessment executor (Phase 2F.2).

Selective path validates inventory merge then persists through the existing
full assessment boundary using a pre-scanned repository (stage-level
incremental). Unsupported or unsafe plans fall back to a normal full rebuild.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from codestrata.application.incremental.changes import ChangeClassifier
from codestrata.application.incremental.errors import (
    IncrementalArtifactMergeError,
    IncrementalExecutionError,
    IncrementalMergeValidationError,
    IncrementalPlanRejectedError,
    SelectiveScanError,
)
from codestrata.application.incremental.execution_gating import evaluate_selective_eligibility
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionRequest,
    IncrementalExecutionResult,
    IncrementalExecutionStatus,
    IncrementalExecutionStepResult,
    IncrementalExecutionStepStatus,
    IncrementalRecomputeCounts,
    IncrementalReuseCounts,
)
from codestrata.application.incremental.execution_policies import (
    IncrementalExecutionPolicy,
    execution_policy_from_settings,
)
from codestrata.application.incremental.inventory_merge import merge_inventory
from codestrata.application.incremental.models import (
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
    IncrementalPlanningRequest,
)
from codestrata.application.incremental.selective_scan import (
    CandidateManifestSelectiveScanService,
    SelectiveScanRequest,
    SelectiveScanService,
    UnsupportedSelectiveScanService,
)
from codestrata.application.incremental.service import IncrementalPlanningService
from codestrata.application.knowledge.queries.service import KnowledgeQueryService
from codestrata.config.settings import CodestrataSettings
from codestrata.models import Repository

logger = logging.getLogger(__name__)


class FullAssessmentRunner(Protocol):
    """Narrow port to the existing full assessment workflow."""

    def run_full(
        self,
        *,
        repository: str,
        output_directory: Path,
        branch: str | None,
        with_ai: bool,
        settings: CodestrataSettings | None,
        scanned_repository: Repository | None = None,
    ) -> Any: ...


class IncrementalAssessmentExecutor:
    """Execute a plan selectively or fall back to full assessment."""

    def __init__(
        self,
        *,
        assessment_runner: FullAssessmentRunner,
        planning_service: IncrementalPlanningService | None = None,
        query_service: KnowledgeQueryService | None = None,
        selective_scan: SelectiveScanService | None = None,
        settings: CodestrataSettings | None = None,
        policy: IncrementalExecutionPolicy | None = None,
    ) -> None:
        self._runner = assessment_runner
        self._planning = planning_service
        self._queries = query_service
        self._selective_scan = selective_scan or UnsupportedSelectiveScanService()
        self._settings = settings
        self._policy = policy or execution_policy_from_settings(settings)

    def execute(self, request: IncrementalExecutionRequest) -> IncrementalExecutionResult:
        started = datetime.now(UTC)
        started_perf = time.perf_counter()
        execution_id = str(uuid4())
        policy = request.policy or self._policy
        warnings: list[str] = []

        plan = request.plan
        if plan is None:
            plan = self._create_plan(request)
        eligible, gate_reasons = evaluate_selective_eligibility(plan, policy)

        if not eligible:
            result = self._fallback(
                request=request,
                execution_id=execution_id,
                plan=plan,
                reasons=gate_reasons or ("selective_ineligible",),
                started=started,
                warnings=tuple(warnings),
            )
            self._log(result, started_perf)
            return result

        try:
            result = self._execute_selective(
                request=request,
                plan=plan,
                execution_id=execution_id,
                started=started,
                warnings=warnings,
            )
        except (
            IncrementalExecutionError,
            IncrementalArtifactMergeError,
            IncrementalMergeValidationError,
            SelectiveScanError,
            IncrementalPlanRejectedError,
        ) as error:
            if not policy.fallback_on_step_failure:
                raise
            reason = getattr(error, "reason_code", type(error).__name__)
            result = self._fallback(
                request=request,
                execution_id=execution_id,
                plan=plan,
                reasons=(reason,),
                started=started,
                warnings=tuple([*warnings, "selective_failed_fallback"]),
            )
        self._log(result, started_perf)
        return result

    def _create_plan(self, request: IncrementalExecutionRequest) -> IncrementalAssessmentPlan:
        if self._planning is None:
            raise IncrementalPlanRejectedError(
                "Planning service is required when plan is omitted",
                reason_code="planning_service_missing",
            )
        return self._planning.create_plan(
            IncrementalPlanningRequest(
                repository_identifier=request.repository,
                previous_run_id=request.previous_run_id,
                branch=request.branch,
                candidate=request.candidate,
            )
        )

    def _execute_selective(
        self,
        *,
        request: IncrementalExecutionRequest,
        plan: IncrementalAssessmentPlan,
        execution_id: str,
        started: datetime,
        warnings: list[str],
    ) -> IncrementalExecutionResult:
        if self._queries is None or plan.previous_snapshot_id is None:
            raise IncrementalPlanRejectedError(
                "Previous snapshot required for selective execution",
                reason_code="previous_snapshot_missing",
                execution_id=execution_id,
                plan_id=plan.plan_id,
            )

        previous_manifest = self._queries.get_repository_manifest(plan.previous_snapshot_id)
        candidate = request.candidate
        if candidate is None:
            raise IncrementalPlanRejectedError(
                "Candidate repository state required for selective execution",
                reason_code="candidate_missing",
                execution_id=execution_id,
                plan_id=plan.plan_id,
            )

        changes = ChangeClassifier().classify(
            previous_manifest,
            candidate.manifest,
            previous_snapshot_id=plan.previous_snapshot_id,
        )

        scan_request = SelectiveScanRequest(
            repository=request.repository,
            branch=request.branch,
            changes=changes,
            previous_manifest=previous_manifest,
            candidate=candidate,
        )
        scan = self._selective_scan.scan(scan_request)
        if not scan.supports_subset or not scan.complete:
            if isinstance(self._selective_scan, UnsupportedSelectiveScanService):
                scan = CandidateManifestSelectiveScanService().scan(scan_request)
            if not scan.complete:
                raise SelectiveScanError(
                    "Selective scan incomplete",
                    reason_code="selective_scan_incomplete",
                    execution_id=execution_id,
                    plan_id=plan.plan_id,
                    failed_step="selective_scan",
                )

        merged_manifest = merge_inventory(
            previous_manifest,
            changes=changes,
            updated_entries=scan.updated_inventory_entries,
            candidate_identity_manifest=candidate.manifest,
        )
        if plan.mode in {
            IncrementalPlanMode.NO_CHANGES,
            IncrementalPlanMode.METADATA_ONLY,
            IncrementalPlanMode.INCREMENTAL_CANDIDATE,
        }:
            candidate_paths = {entry.path.root for entry in candidate.manifest.files}
            merged_paths = {entry.path.root for entry in merged_manifest.files}
            if candidate_paths != merged_paths:
                raise IncrementalArtifactMergeError(
                    "Merged inventory does not match candidate manifest",
                    reason_code="inventory_candidate_mismatch",
                    execution_id=execution_id,
                    plan_id=plan.plan_id,
                    failed_step="inventory_merge",
                )
            merged_manifest = candidate.manifest

        repository = scan.repository
        if repository is None:
            raise SelectiveScanError(
                "Selective scan did not produce a repository handle",
                reason_code="repository_missing",
                execution_id=execution_id,
                plan_id=plan.plan_id,
                failed_step="selective_scan",
            )
        repo_path = Path(request.repository).expanduser()
        if not repo_path.is_dir():
            raise SelectiveScanError(
                "Repository path is not a local directory for selective execution",
                reason_code="repository_not_local",
                execution_id=execution_id,
                plan_id=plan.plan_id,
                failed_step="selective_scan",
            )
        repository = repository.model_copy(
            update={
                "files": [entry.path.root for entry in merged_manifest.files],
                "total_files": len(merged_manifest.files),
                "path": repo_path,
            }
        )

        # Single persistence path: existing assessment pipeline with pre-scanned repo.
        assessment = self._runner.run_full(
            repository=request.repository,
            output_directory=Path(request.output_directory),
            branch=request.branch,
            with_ai=request.with_ai,
            settings=self._settings,
            scanned_repository=repository,
        )

        reuse = IncrementalReuseCounts(files=max(0, changes.unchanged_count))
        recompute = IncrementalRecomputeCounts(
            files=changes.change_count,
            findings=getattr(assessment, "findings_count", 0) or 0,
            recommendations=getattr(assessment, "recommendations_count", 0) or 0,
            ai_artifacts=0,
        )
        warnings.extend(scan.warnings)
        return IncrementalExecutionResult(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            mode=IncrementalExecutionMode.INCREMENTAL,
            status=IncrementalExecutionStatus.COMPLETED,
            repository_id=plan.repository_id,
            previous_run_id=plan.previous_run_id,
            previous_snapshot_id=plan.previous_snapshot_id,
            run_id=getattr(assessment, "knowledge_run_id", None),
            snapshot_id=getattr(assessment, "knowledge_snapshot_id", None),
            reused_counts=reuse,
            recomputed_counts=recompute,
            fallback_used=False,
            fallback_reasons=(),
            steps=(
                IncrementalExecutionStepResult(
                    sequence=1,
                    step_type="selective_scan",
                    status=IncrementalExecutionStepStatus.COMPLETED,
                    subject_ids=scan.scanned_files,
                ),
                IncrementalExecutionStepResult(
                    sequence=2,
                    step_type="inventory_merge",
                    status=IncrementalExecutionStepStatus.MERGED,
                ),
                IncrementalExecutionStepResult(
                    sequence=3,
                    step_type="stage_rebuild_and_persist",
                    status=IncrementalExecutionStepStatus.RECOMPUTED,
                    reasons=("complete_graphs_rules_recommendations_via_existing_pipeline",),
                ),
            ),
            warnings=tuple(dict.fromkeys(warnings)),
            started_at=started,
            completed_at=datetime.now(UTC),
            assessment_result=assessment,
        )

    def _fallback(
        self,
        *,
        request: IncrementalExecutionRequest,
        execution_id: str,
        plan: IncrementalAssessmentPlan | None,
        reasons: tuple[str, ...],
        started: datetime,
        warnings: tuple[str, ...],
    ) -> IncrementalExecutionResult:
        assessment = self._runner.run_full(
            repository=request.repository,
            output_directory=Path(request.output_directory),
            branch=request.branch,
            with_ai=request.with_ai,
            settings=self._settings,
            scanned_repository=None,
        )
        return IncrementalExecutionResult(
            execution_id=execution_id,
            plan_id=None if plan is None else plan.plan_id,
            mode=IncrementalExecutionMode.FULL_REBUILD_FALLBACK,
            status=IncrementalExecutionStatus.FALLBACK_COMPLETED,
            repository_id=None if plan is None else plan.repository_id,
            previous_run_id=None if plan is None else plan.previous_run_id,
            previous_snapshot_id=None if plan is None else plan.previous_snapshot_id,
            run_id=getattr(assessment, "knowledge_run_id", None),
            snapshot_id=getattr(assessment, "knowledge_snapshot_id", None),
            reused_counts=IncrementalReuseCounts(),
            recomputed_counts=IncrementalRecomputeCounts(),
            fallback_used=True,
            fallback_reasons=reasons,
            steps=(
                IncrementalExecutionStepResult(
                    sequence=1,
                    step_type="full_rebuild",
                    status=IncrementalExecutionStepStatus.COMPLETED,
                    reasons=reasons,
                ),
            ),
            warnings=warnings,
            started_at=started,
            completed_at=datetime.now(UTC),
            assessment_result=assessment,
        )

    @staticmethod
    def _log(result: IncrementalExecutionResult, started_perf: float) -> None:
        logger.info(
            "incremental.execution_complete",
            extra={
                "execution_id": result.execution_id,
                "plan_id": result.plan_id,
                "repository_id": result.repository_id,
                "previous_run_id": result.previous_run_id,
                "mode": result.mode.value,
                "status": result.status.value,
                "fallback_used": result.fallback_used,
                "fallback_reasons": list(result.fallback_reasons),
                "run_id": result.run_id,
                "duration_ms": int((time.perf_counter() - started_perf) * 1000),
            },
        )
