"""Session helper for assessment knowledge persistence."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from types import TracebackType
from typing import Any

from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.application.knowledge.persistence import (
    build_staged_assessment_artifacts,
    content_fingerprint_for_manifest,
    default_tooling_versions,
    identity_hints_for_repository,
)
from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.models import Repository
from codestrata.reporting import AssessmentMode
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult


class AssessmentKnowledgeSession:
    """Owns optional knowledge-store lifecycle for one assessment."""

    def __init__(
        self,
        *,
        store: KnowledgeStore,
        repository: Repository,
        mode: AssessmentMode,
        owns_store: bool = False,
        lock_timeout_seconds: float = 3600.0,
        revision_observer: Any | None = None,
    ) -> None:
        self._store = store
        self._repository = repository
        self._mode = mode
        self._owns_store = owns_store
        self._lock: AbstractContextManager[None] = nullcontext()
        self._lock_entered = False
        self._lock_timeout_seconds = lock_timeout_seconds
        self._revision_observer = revision_observer
        self.repository_id: str | None = None
        self.run_id: str | None = None

    def __enter__(self) -> AssessmentKnowledgeSession:
        try:
            _ = self._store.registry
        except KnowledgeStoreError:
            self._store.open()

        hints = identity_hints_for_repository(self._repository)
        record = self._store.registry.register_or_resolve(hints)
        self.repository_id = record.repository_id
        self._lock = self._store.repository_lock(
            record.repository_id,
            timeout_seconds=self._lock_timeout_seconds,
        )
        self._lock.__enter__()
        self._lock_entered = True

        codestrata_version, ruleset_version = default_tooling_versions()
        run = self._store.runs.create_run(
            repository_id=record.repository_id,
            assessment_mode=self._mode.value,
            codestrata_version=codestrata_version,
            ruleset_version=ruleset_version,
        )
        self.run_id = run.run_id
        return self

    def complete(
        self,
        *,
        graph_pipeline_result: GraphAssessmentPipelineResult,
        rule_evaluation: RuleEvaluationResult,
        recommendation_result: RecommendationResult,
        ai_execution_document: dict[str, Any] | None,
        enrichment_result: Any | None,
        configured_branch: str | None,
    ) -> str:
        if self.run_id is None or self.repository_id is None:
            raise KnowledgeStoreError("Knowledge session is not active")

        if self._revision_observer is not None:
            observed = self._revision_observer(
                self._repository.path,
                configured_branch=configured_branch or self._repository.default_branch,
            )
            revision_type = observed.revision_type
            revision_id = observed.revision_id
            branch = observed.branch
        else:
            revision_type = RepositoryRevisionType.WORKING_TREE
            revision_id = "working-tree"
            branch = configured_branch or self._repository.default_branch

        fingerprint = content_fingerprint_for_manifest(graph_pipeline_result.manifest)
        snapshot = self._store.snapshots.create_or_get_snapshot(
            repository_id=self.repository_id,
            branch=branch,
            revision_type=revision_type,
            revision_id=revision_id,
            manifest=graph_pipeline_result.manifest,
            content_fingerprint=fingerprint,
        )
        enrichment_payload = None
        if enrichment_result is not None:
            enrichment_payload = enrichment_result.model_dump(mode="json")
        artifacts = build_staged_assessment_artifacts(
            graph_pipeline_result=graph_pipeline_result,
            rule_evaluation=rule_evaluation,
            recommendation_result=recommendation_result,
            ai_execution_document=ai_execution_document,
            ai_enrichment_payload=enrichment_payload,
            snapshot_id=snapshot.snapshot_id,
        )
        self._store.runs.complete_run(
            self.run_id,
            snapshot_id=snapshot.snapshot_id,
            artifacts=artifacts,
        )
        return snapshot.snapshot_id

    def fail(self, *, error_code: str, error_message: str) -> None:
        if self.run_id is None:
            return
        try:
            self._store.runs.fail_run(
                self.run_id,
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:  # noqa: BLE001 - best effort on failure path
            return

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._lock_entered:
            self._lock.__exit__(exc_type, exc, traceback)
            self._lock_entered = False
        if self._owns_store:
            self._store.close()
