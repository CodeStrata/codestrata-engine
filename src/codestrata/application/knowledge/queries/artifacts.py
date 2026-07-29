"""Internal artifact resolution for knowledge queries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from codestrata.application.knowledge.errors import (
    KnowledgeArtifactNotFoundError,
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
)
from codestrata.application.knowledge.models import KnowledgeArtifactKind
from codestrata.application.knowledge.ports import AssessmentRunStore, KnowledgeStore
from codestrata.application.knowledge.queries.errors import (
    ArtifactNotFoundError,
    AssessmentRunNotFoundError,
    DuplicateArtifactError,
    IncompatibleArtifactVersionError,
    KnowledgeArtifactCorruptionError,
    KnowledgeQueryError,
)
from codestrata.domain.assessment_graph.models import AssessmentGraph
from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.graph.models import GraphSnapshot
from codestrata.domain.knowledge_binding.models import KnowledgeBindingResult
from codestrata.domain.recommendations import Recommendation, RecommendationResult
from codestrata.domain.repository_graph.models import RepositoryGraph

REQUIRED_ARTIFACT_KINDS = frozenset(
    {
        KnowledgeArtifactKind.REPOSITORY_GRAPH,
        KnowledgeArtifactKind.ENGINEERING_KNOWLEDGE_GRAPH,
        KnowledgeArtifactKind.KNOWLEDGE_BINDINGS,
        KnowledgeArtifactKind.ASSESSMENT_GRAPH,
        KnowledgeArtifactKind.FINDINGS,
        KnowledgeArtifactKind.RECOMMENDATIONS,
    }
)

OPTIONAL_ARTIFACT_KINDS = frozenset(
    {
        KnowledgeArtifactKind.AI_EXECUTION,
        KnowledgeArtifactKind.AI_ENRICHMENT,
        KnowledgeArtifactKind.REPOSITORY_MANIFEST,
    }
)

ArtifactPayload = Mapping[str, Any] | list[Any]


class ArtifactResolver:
    """Resolve and validate run-linked knowledge artifacts via store ports."""

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store
        self._cache: dict[tuple[str, KnowledgeArtifactKind], ArtifactPayload | None] = {}

    @property
    def runs(self) -> AssessmentRunStore:
        return self._store.runs

    def require_run(self, run_id: str) -> None:
        if self._store.runs.get_run(run_id) is None:
            raise AssessmentRunNotFoundError(f"Assessment run not found: {run_id}")

    def list_kinds(self, run_id: str) -> tuple[KnowledgeArtifactKind, ...]:
        self.require_run(run_id)
        records = list(self._store.runs.list_artifacts(run_id))
        _assert_no_duplicate_kinds(records)
        return tuple(record.artifact_kind for record in records)

    def read_payload(
        self,
        run_id: str,
        kind: KnowledgeArtifactKind,
        *,
        required: bool,
    ) -> ArtifactPayload | None:
        cache_key = (run_id, kind)
        if cache_key in self._cache:
            return self._cache[cache_key]

        self.require_run(run_id)
        records = [
            item
            for item in self._store.runs.list_artifacts(run_id)
            if item.artifact_kind is kind
        ]
        if len(records) > 1:
            raise DuplicateArtifactError(
                f"Run {run_id} has duplicate artifacts of kind {kind.value}"
            )
        if not records:
            if required:
                raise ArtifactNotFoundError(
                    f"Required artifact {kind.value} is missing for run {run_id}"
                )
            self._cache[cache_key] = None
            return None

        try:
            payload = self._store.runs.read_artifact_payload(run_id, kind)
        except KnowledgeArtifactNotFoundError as error:
            if required:
                raise ArtifactNotFoundError(str(error)) from error
            self._cache[cache_key] = None
            return None
        except KnowledgeStoreCorruptionError as error:
            raise KnowledgeArtifactCorruptionError(
                f"Artifact {kind.value} failed integrity checks for run {run_id}"
            ) from error
        except KnowledgeStoreError as error:
            raise KnowledgeQueryError(
                f"Failed to read artifact {kind.value} for run {run_id}"
            ) from error
        except KnowledgeQueryError:
            raise
        except Exception as error:  # pragma: no cover - defensive boundary
            raise KnowledgeArtifactCorruptionError(
                f"Artifact {kind.value} could not be read for run {run_id}"
            ) from error

        self._cache[cache_key] = payload
        return payload

    def get_findings(self, run_id: str) -> RuleEvaluationResult:
        payload = self.read_payload(run_id, KnowledgeArtifactKind.FINDINGS, required=True)
        assert payload is not None
        try:
            if isinstance(payload, Mapping):
                return RuleEvaluationResult.model_validate(payload)
            raise IncompatibleArtifactVersionError(
                f"Findings artifact for run {run_id} must be a JSON object"
            )
        except ValidationError as error:
            raise IncompatibleArtifactVersionError(
                f"Findings artifact for run {run_id} is incompatible"
            ) from error

    def get_recommendations(self, run_id: str) -> RecommendationResult:
        payload = self.read_payload(run_id, KnowledgeArtifactKind.RECOMMENDATIONS, required=True)
        assert payload is not None
        try:
            if isinstance(payload, Mapping):
                return RecommendationResult.model_validate(payload)
            raise IncompatibleArtifactVersionError(
                f"Recommendations artifact for run {run_id} must be a JSON object"
            )
        except ValidationError as error:
            raise IncompatibleArtifactVersionError(
                f"Recommendations artifact for run {run_id} is incompatible"
            ) from error

    def get_repository_graph(self, run_id: str) -> RepositoryGraph:
        payload = self.read_payload(run_id, KnowledgeArtifactKind.REPOSITORY_GRAPH, required=True)
        assert payload is not None
        try:
            snapshot = GraphSnapshot.model_validate(payload)
            return RepositoryGraph(snapshot)
        except (ValidationError, ValueError) as error:
            raise IncompatibleArtifactVersionError(
                f"Repository graph for run {run_id} is incompatible"
            ) from error

    def get_assessment_graph(self, run_id: str) -> AssessmentGraph:
        payload = self.read_payload(run_id, KnowledgeArtifactKind.ASSESSMENT_GRAPH, required=True)
        assert payload is not None
        try:
            snapshot = GraphSnapshot.model_validate(payload)
            return AssessmentGraph(snapshot)
        except (ValidationError, ValueError) as error:
            raise IncompatibleArtifactVersionError(
                f"Assessment graph for run {run_id} is incompatible"
            ) from error

    def get_engineering_knowledge_graph(self, run_id: str) -> GraphSnapshot:
        payload = self.read_payload(
            run_id,
            KnowledgeArtifactKind.ENGINEERING_KNOWLEDGE_GRAPH,
            required=True,
        )
        assert payload is not None
        try:
            return GraphSnapshot.model_validate(payload)
        except ValidationError as error:
            raise IncompatibleArtifactVersionError(
                f"Engineering knowledge graph for run {run_id} is incompatible"
            ) from error

    def get_knowledge_bindings(self, run_id: str) -> KnowledgeBindingResult:
        payload = self.read_payload(
            run_id,
            KnowledgeArtifactKind.KNOWLEDGE_BINDINGS,
            required=True,
        )
        assert payload is not None
        try:
            if isinstance(payload, Mapping):
                return KnowledgeBindingResult.model_validate(payload)
            raise IncompatibleArtifactVersionError(
                f"Knowledge bindings for run {run_id} must be a JSON object"
            )
        except ValidationError as error:
            raise IncompatibleArtifactVersionError(
                f"Knowledge bindings for run {run_id} are incompatible"
            ) from error

    def get_optional_json_object(
        self,
        run_id: str,
        kind: KnowledgeArtifactKind,
    ) -> dict[str, Any] | None:
        payload = self.read_payload(run_id, kind, required=False)
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise IncompatibleArtifactVersionError(
                f"Artifact {kind.value} for run {run_id} must be a JSON object"
            )
        return dict(payload)


def _assert_no_duplicate_kinds(records: list[Any]) -> None:
    seen: set[KnowledgeArtifactKind] = set()
    for record in records:
        kind = record.artifact_kind
        if kind in seen:
            raise DuplicateArtifactError(
                f"Run {record.run_id} has duplicate artifacts of kind {kind.value}"
            )
        seen.add(kind)


def finding_map(result: RuleEvaluationResult) -> dict[str, Finding]:
    return {item.id: item for item in result.findings}


def recommendation_map(result: RecommendationResult) -> dict[str, Recommendation]:
    return {item.id: item for item in result.recommendations}
