"""Previous-run eligibility for incremental planning bases."""

from __future__ import annotations

import logging
from uuid import UUID

from codestrata.application.incremental.models import IncrementalBaseEligibility
from codestrata.application.knowledge.models import AssessmentRunStatus, KnowledgeArtifactKind
from codestrata.application.knowledge.queries.artifacts import REQUIRED_ARTIFACT_KINDS
from codestrata.application.knowledge.queries.errors import (
    AssessmentRunNotFoundError,
    KnowledgeArtifactCorruptionError,
    KnowledgeQueryError,
    SnapshotNotFoundError,
)
from codestrata.application.knowledge.queries.service import KnowledgeQueryService

logger = logging.getLogger(__name__)


class PreviousRunEligibilityChecker:
    """Decide whether a completed run may serve as an incremental base."""

    def __init__(self, query_service: KnowledgeQueryService) -> None:
        self._queries = query_service

    def check(
        self,
        run_id: str,
        *,
        expected_repository_id: str,
        branch: str | None = None,
    ) -> IncrementalBaseEligibility:
        reasons: list[str] = []
        missing: list[str] = []
        incompatible: list[str] = []
        warnings: list[str] = []
        snapshot_id: str | None = None

        try:
            run = self._queries.get_assessment_run(run_id)
        except AssessmentRunNotFoundError:
            return IncrementalBaseEligibility(
                eligible=False,
                repository_id=expected_repository_id,
                run_id=run_id,
                reasons=("run_not_found",),
            )
        except KnowledgeQueryError as error:
            return IncrementalBaseEligibility(
                eligible=False,
                repository_id=expected_repository_id,
                run_id=run_id,
                reasons=("run_query_failed", str(error)),
            )

        if run.repository_id != expected_repository_id:
            reasons.append("repository_mismatch")

        if run.status is AssessmentRunStatus.RUNNING:
            reasons.append("run_running")
        elif run.status is AssessmentRunStatus.FAILED:
            reasons.append("run_failed")
        elif run.status is AssessmentRunStatus.ABORTED:
            reasons.append("run_stale_or_aborted")
        elif run.status is not AssessmentRunStatus.COMPLETED:
            reasons.append("run_incomplete")

        if run.snapshot_id is None:
            reasons.append("snapshot_missing")
        else:
            snapshot_id = run.snapshot_id
            try:
                snapshot = self._queries.get_repository_snapshot(run.snapshot_id)
                if snapshot.repository_id != run.repository_id:
                    reasons.append("snapshot_repository_mismatch")
                if branch is not None and (snapshot.branch or "") != (branch or ""):
                    reasons.append("branch_mismatch")
            except SnapshotNotFoundError:
                reasons.append("snapshot_not_found")
                missing.append("repository_snapshot")

        present = {kind.value for kind in run.artifact_kinds}
        for kind in sorted(REQUIRED_ARTIFACT_KINDS, key=lambda item: item.value):
            if kind.value not in present:
                missing.append(kind.value)
                reasons.append(f"missing_artifact:{kind.value}")

        # Attempt to load required artifacts; corruption blocks eligibility.
        if run.status is AssessmentRunStatus.COMPLETED and not missing:
            try:
                self._queries.get_repository_graph(run_id=run.run_id)
                self._queries.get_engineering_knowledge_graph(run.run_id)
                self._queries.get_assessment_graph(run.run_id)
                findings = self._queries.get_findings(run.run_id)
                self._queries.get_recommendations(run.run_id)
            except KnowledgeArtifactCorruptionError:
                reasons.append("artifact_corruption")
                incompatible.append("corrupted_required_artifact")
                findings = ()
            except KnowledgeQueryError:
                reasons.append("artifact_load_failed")
                incompatible.append("unreadable_required_artifact")
                findings = ()
            else:
                uuid_findings = sum(1 for item in findings if _looks_like_uuid(item.finding_id))
                if findings and uuid_findings == len(findings):
                    reasons.append("phase1_uuid_findings_only")
                    incompatible.append("findings")
                elif uuid_findings:
                    warnings.append("mixed_phase1_uuid_findings_skipped")

        # Optional AI artifacts are not required for eligibility.
        if KnowledgeArtifactKind.AI_ENRICHMENT.value not in present:
            warnings.append("ai_enrichment_absent")

        eligible = not reasons
        result = IncrementalBaseEligibility(
            eligible=eligible,
            repository_id=run.repository_id,
            run_id=run.run_id,
            snapshot_id=snapshot_id,
            reasons=tuple(dict.fromkeys(reasons)),
            missing_artifacts=tuple(dict.fromkeys(missing)),
            incompatible_artifacts=tuple(dict.fromkeys(incompatible)),
            warnings=tuple(dict.fromkeys(warnings)),
        )
        logger.info(
            "incremental.base_eligibility",
            extra={
                "run_id": run.run_id,
                "eligible": eligible,
                "reason_count": len(result.reasons),
            },
        )
        return result


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value.strip())
    except ValueError:
        return False
    return True
