"""Transport-neutral knowledge query service."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from codestrata.application.knowledge.errors import (
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    RepositoryIdentityError,
)
from codestrata.application.knowledge.identity import normalize_github_url_alias
from codestrata.application.knowledge.models import (
    AssessmentRunRecord,
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    RepositoryAliasType,
    RepositoryRecord,
    RepositorySnapshotRecord,
)
from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.application.knowledge.queries.artifacts import (
    ArtifactResolver,
    finding_map,
    recommendation_map,
)
from codestrata.application.knowledge.queries.errors import (
    AssessmentRunNotFoundError,
    ComponentNotFoundError,
    FindingNotFoundError,
    KnowledgeArtifactCorruptionError,
    KnowledgeQueryError,
    QueryLimitError,
    RecommendationNotFoundError,
    RepositoryQueryNotFoundError,
    SnapshotComparisonError,
    SnapshotNotFoundError,
)
from codestrata.application.knowledge.queries.models import (
    ArtifactSummary,
    AssessmentRunSummary,
    ComponentView,
    DependencyDirection,
    DependencyQueryResult,
    DependencyView,
    EvidenceView,
    FindingExplanation,
    FindingView,
    GraphNodeView,
    RecommendationActionView,
    RecommendationExplanation,
    RecommendationView,
    RepositorySummary,
    SnapshotComparison,
    SnapshotComparisonCounts,
    SnapshotFileChangeView,
    SnapshotSummary,
)
from codestrata.domain.findings import Finding
from codestrata.domain.graph.models import GraphNode, GraphRelationship, GraphSnapshot
from codestrata.domain.knowledge_binding.models import KnowledgeBindingResult
from codestrata.domain.recommendations import Recommendation
from codestrata.domain.repository import RepositoryManifest
from codestrata.domain.repository.changes import (
    RepositoryManifestDiffer,
    RepositoryManifestDiffError,
)
from codestrata.domain.repository.enums import RepositoryChangeType
from codestrata.domain.repository_graph.enums import RepositoryRelationshipType
from codestrata.repository_auth.exceptions import UnsupportedRepositoryUrlError
from codestrata.repository_auth.github_urls import parse_github_repository_url

DEFAULT_REPOSITORY_LIMIT = 50
MAX_REPOSITORY_LIMIT = 500
DEFAULT_RUN_LIMIT = 20
MAX_RUN_LIMIT = 200
DEFAULT_SNAPSHOT_LIMIT = 20
MAX_SNAPSHOT_LIMIT = 200
DEFAULT_COMPONENT_LIMIT = 100
MAX_COMPONENT_LIMIT = 1000
DEFAULT_DEPENDENCY_LIMIT = 500
MAX_DEPENDENCY_LIMIT = 2000
MAX_DEPENDENCY_DEPTH = 3

_DEPENDENCY_REL_TYPES = frozenset(
    {
        RepositoryRelationshipType.DEPENDS_ON.value,
    }
)


class KnowledgeQueryService:
    """Application query API over durable knowledge-store ports.

    Adapters (CLI, FastMCP, REST, agents) must call this service rather than
    opening SQLite, blob files, or report artifacts directly.

    Authoritative findings and recommendations are Phase 3 stable IDs. Phase 1
    UUID report findings are intentionally not exposed.
    """

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def _ensure_open(self) -> None:
        try:
            _ = self._store.registry
        except KnowledgeStoreError:
            self._store.open()

    def _resolver(self) -> ArtifactResolver:
        self._ensure_open()
        return ArtifactResolver(self._store)

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def list_repositories(self, *, limit: int | None = None) -> tuple[RepositorySummary, ...]:
        self._ensure_open()
        capped = _bounded_limit(
            limit,
            default=DEFAULT_REPOSITORY_LIMIT,
            maximum=MAX_REPOSITORY_LIMIT,
            label="repositories",
        )
        records = list(self._store.registry.list_repositories())
        records.sort(
            key=lambda item: (
                item.display_name.lower(),
                item.canonical_key,
                item.repository_id,
            )
        )
        return tuple(self._to_repository_summary(item) for item in records[:capped])

    def get_repository(self, repository_id: str) -> RepositorySummary:
        self._ensure_open()
        record = self._store.registry.get_by_id(repository_id.strip())
        if record is None:
            raise RepositoryQueryNotFoundError(f"Repository not found: {repository_id}")
        return self._to_repository_summary(record)

    def resolve_repository(self, identifier: str) -> RepositorySummary:
        """Resolve by repository ID, canonical key, or non-local alias."""

        self._ensure_open()
        compact = identifier.strip()
        if not compact:
            raise RepositoryQueryNotFoundError("Repository identifier must be nonempty")

        record = self._store.registry.get_by_id(compact)
        if record is None:
            try:
                UUID(compact)
            except ValueError:
                pass
            else:
                raise RepositoryQueryNotFoundError(f"Repository not found: {compact}")

        if record is None:
            record = self._store.registry.get_by_canonical_key(compact.lower())
        if record is None:
            record = self._store.registry.get_by_canonical_key(compact)

        if record is None:
            try:
                parsed = parse_github_repository_url(compact)
                alias = normalize_github_url_alias(parsed)
                record = self._store.registry.resolve_alias(
                    RepositoryAliasType.GITHUB_URL,
                    alias,
                )
            except (UnsupportedRepositoryUrlError, RepositoryIdentityError, ValueError):
                record = None

        if record is None:
            record = self._store.registry.resolve_alias(
                RepositoryAliasType.LEGACY_REPOSITORY_KEY,
                compact.lower(),
            )
        if record is None:
            record = self._store.registry.resolve_alias(
                RepositoryAliasType.CANONICAL_KEY_ALIAS,
                compact.lower(),
            )

        if record is None:
            raise RepositoryQueryNotFoundError(f"Repository not found: {compact}")
        return self._to_repository_summary(record)

    def _to_repository_summary(self, record: RepositoryRecord) -> RepositorySummary:
        latest_run = self._store.runs.get_latest_completed_run(record.repository_id)
        latest_snapshot = self._store.snapshots.get_latest_snapshot(record.repository_id)
        return RepositorySummary(
            repository_id=record.repository_id,
            canonical_key=record.canonical_key,
            display_name=record.display_name,
            source_type=record.source_type,
            latest_completed_run_id=None if latest_run is None else latest_run.run_id,
            latest_snapshot_id=None if latest_snapshot is None else latest_snapshot.snapshot_id,
            latest_assessed_at=None if latest_run is None else latest_run.completed_at,
        )

    # ------------------------------------------------------------------
    # Assessment runs
    # ------------------------------------------------------------------

    def list_assessment_runs(
        self,
        repository_id: str,
        *,
        limit: int | None = None,
        status: AssessmentRunStatus | None = None,
    ) -> tuple[AssessmentRunSummary, ...]:
        self._ensure_open()
        self._require_repository(repository_id)
        capped = _bounded_limit(
            limit,
            default=DEFAULT_RUN_LIMIT,
            maximum=MAX_RUN_LIMIT,
            label="assessment runs",
        )
        runs = list(
            self._store.runs.list_runs(
                repository_id,
                limit=capped,
                status=status,
            )
        )
        return tuple(self._to_run_summary(run) for run in runs)

    def get_assessment_run(self, run_id: str) -> AssessmentRunSummary:
        self._ensure_open()
        run = self._store.runs.get_run(run_id.strip())
        if run is None:
            raise AssessmentRunNotFoundError(f"Assessment run not found: {run_id}")
        return self._to_run_summary(run)

    def get_latest_completed_run(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> AssessmentRunSummary | None:
        self._ensure_open()
        self._require_repository(repository_id)
        run = self._store.runs.get_latest_completed_run(repository_id, branch=branch)
        if run is None:
            return None
        return self._to_run_summary(run)

    def _to_run_summary(self, run: AssessmentRunRecord) -> AssessmentRunSummary:
        branch: str | None = None
        revision_type = None
        revision_id: str | None = None
        if run.snapshot_id is not None:
            snapshot = self._store.snapshots.get_snapshot(run.snapshot_id)
            if snapshot is not None:
                branch = snapshot.branch
                revision_type = snapshot.revision_type
                revision_id = snapshot.revision_id
        kinds: tuple[KnowledgeArtifactKind, ...] = ()
        if run.status is AssessmentRunStatus.COMPLETED:
            kinds = tuple(
                item.artifact_kind for item in self._store.runs.list_artifacts(run.run_id)
            )
        return AssessmentRunSummary(
            run_id=run.run_id,
            repository_id=run.repository_id,
            snapshot_id=run.snapshot_id,
            status=run.status,
            mode=run.assessment_mode,
            branch=branch,
            revision_type=revision_type,
            revision_id=revision_id,
            started_at=run.started_at,
            completed_at=run.completed_at,
            failed_at=run.failed_at,
            error_code=run.error_code,
            artifact_kinds=kinds,
            codestrata_version=run.codestrata_version,
            ruleset_version=run.ruleset_version,
        )

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def list_repository_snapshots(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
        limit: int | None = None,
    ) -> tuple[SnapshotSummary, ...]:
        self._ensure_open()
        self._require_repository(repository_id)
        capped = _bounded_limit(
            limit,
            default=DEFAULT_SNAPSHOT_LIMIT,
            maximum=MAX_SNAPSHOT_LIMIT,
            label="snapshots",
        )
        snapshots = self._store.snapshots.list_snapshots(
            repository_id,
            branch=branch,
            limit=capped,
        )
        return tuple(_to_snapshot_summary(item) for item in snapshots)

    def get_repository_snapshot(self, snapshot_id: str) -> SnapshotSummary:
        self._ensure_open()
        snapshot = self._store.snapshots.get_snapshot(snapshot_id.strip())
        if snapshot is None:
            raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
        return _to_snapshot_summary(snapshot)

    def get_latest_repository_snapshot(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> SnapshotSummary | None:
        self._ensure_open()
        self._require_repository(repository_id)
        snapshot = self._store.snapshots.get_latest_snapshot(repository_id, branch=branch)
        if snapshot is None:
            return None
        return _to_snapshot_summary(snapshot)

    def get_repository_manifest(self, snapshot_id: str) -> RepositoryManifest:
        self._ensure_open()
        snapshot = self._store.snapshots.get_snapshot(snapshot_id.strip())
        if snapshot is None:
            raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
        try:
            return self._store.snapshots.get_manifest(snapshot.snapshot_id)
        except KnowledgeStoreCorruptionError as error:
            raise KnowledgeArtifactCorruptionError(
                f"Manifest for snapshot {snapshot_id} failed integrity checks"
            ) from error
        except KnowledgeStoreError as error:
            raise KnowledgeQueryError(
                f"Failed to read manifest for snapshot {snapshot_id}"
            ) from error

    def compare_repository_snapshots(
        self,
        previous_snapshot_id: str,
        current_snapshot_id: str,
    ) -> SnapshotComparison:
        self._ensure_open()
        previous = self._store.snapshots.get_snapshot(previous_snapshot_id.strip())
        current = self._store.snapshots.get_snapshot(current_snapshot_id.strip())
        if previous is None:
            raise SnapshotNotFoundError(f"Snapshot not found: {previous_snapshot_id}")
        if current is None:
            raise SnapshotNotFoundError(f"Snapshot not found: {current_snapshot_id}")
        if previous.repository_id != current.repository_id:
            raise SnapshotComparisonError(
                "Snapshots belong to different repositories and cannot be compared"
            )
        try:
            previous_manifest = self._store.snapshots.get_manifest(previous.snapshot_id)
            current_manifest = self._store.snapshots.get_manifest(current.snapshot_id)
        except KnowledgeStoreCorruptionError as error:
            raise KnowledgeArtifactCorruptionError(
                "One or both snapshot manifests failed integrity checks"
            ) from error
        except KnowledgeStoreError as error:
            raise SnapshotComparisonError("Failed to load manifests for comparison") from error

        try:
            diff = RepositoryManifestDiffer.diff(previous_manifest, current_manifest)
        except RepositoryManifestDiffError as error:
            raise SnapshotComparisonError(str(error)) from error
        except Exception as error:
            raise SnapshotComparisonError("Manifest comparison failed") from error

        added = tuple(_file_change_view(change) for change in diff.added)
        modified = tuple(_file_change_view(change) for change in diff.modified)
        deleted = tuple(_file_change_view(change) for change in diff.deleted)
        metadata = tuple(_file_change_view(change) for change in diff.metadata_changed)
        return SnapshotComparison(
            previous_snapshot_id=previous.snapshot_id,
            current_snapshot_id=current.snapshot_id,
            previous_content_fingerprint=previous.content_fingerprint,
            current_content_fingerprint=current.content_fingerprint,
            added_files=added,
            modified_files=modified,
            deleted_files=deleted,
            metadata_changed_files=metadata,
            renamed_files=(),
            counts=SnapshotComparisonCounts(
                added=len(added),
                modified=len(modified),
                deleted=len(deleted),
                metadata_changed=len(metadata),
                renamed=0,
            ),
        )

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def list_run_artifacts(self, run_id: str) -> tuple[ArtifactSummary, ...]:
        resolver = self._resolver()
        resolver.require_run(run_id)
        records = list(self._store.runs.list_artifacts(run_id))
        records.sort(key=lambda item: (item.artifact_kind.value, item.artifact_id))
        return tuple(
            ArtifactSummary(
                artifact_id=item.artifact_id,
                artifact_kind=item.artifact_kind,
                schema_version=item.schema_version,
                source_fingerprint=item.source_fingerprint,
                created_at=item.created_at,
            )
            for item in records
        )

    def get_repository_graph(
        self,
        *,
        run_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> GraphSnapshot:
        resolved_run = self._resolve_run_for_artifact(run_id=run_id, snapshot_id=snapshot_id)
        return self._resolver().get_repository_graph(resolved_run).snapshot

    def get_engineering_knowledge_graph(self, run_id: str) -> GraphSnapshot:
        return self._resolver().get_engineering_knowledge_graph(run_id)

    def get_knowledge_bindings(self, run_id: str) -> KnowledgeBindingResult:
        return self._resolver().get_knowledge_bindings(run_id)

    def get_assessment_graph(self, run_id: str) -> GraphSnapshot:
        return self._resolver().get_assessment_graph(run_id).snapshot

    def get_findings(self, run_id: str) -> tuple[FindingView, ...]:
        resolver = self._resolver()
        evaluation = resolver.get_findings(run_id)
        recommendations = resolver.get_recommendations(run_id)
        by_finding = _recommendation_ids_by_finding(recommendations.recommendations)
        return tuple(
            _to_finding_view(item, recommendation_ids=by_finding.get(item.id, ()))
            for item in evaluation.findings
        )

    def get_recommendations(self, run_id: str) -> tuple[RecommendationView, ...]:
        result = self._resolver().get_recommendations(run_id)
        return tuple(_to_recommendation_view(item) for item in result.recommendations)

    def get_ai_execution(self, run_id: str) -> dict[str, Any] | None:
        return self._resolver().get_optional_json_object(
            run_id,
            KnowledgeArtifactKind.AI_EXECUTION,
        )

    def get_ai_enrichment(self, run_id: str) -> dict[str, Any] | None:
        return self._resolver().get_optional_json_object(
            run_id,
            KnowledgeArtifactKind.AI_ENRICHMENT,
        )

    # ------------------------------------------------------------------
    # Explanations
    # ------------------------------------------------------------------

    def explain_finding(self, run_id: str, finding_id: str) -> FindingExplanation:
        resolver = self._resolver()
        run = self._store.runs.get_run(run_id.strip())
        if run is None:
            raise AssessmentRunNotFoundError(f"Assessment run not found: {run_id}")
        evaluation = resolver.get_findings(run_id)
        recommendations = resolver.get_recommendations(run_id)
        findings = finding_map(evaluation)
        finding = findings.get(finding_id.strip())
        if finding is None:
            raise FindingNotFoundError(f"Finding not found: {finding_id}")

        related = tuple(
            item
            for item in recommendations.recommendations
            if finding.id in item.related_finding_ids
        )
        by_finding = _recommendation_ids_by_finding(recommendations.recommendations)
        finding_view = _to_finding_view(
            finding,
            recommendation_ids=by_finding.get(finding.id, ()),
        )
        subjects = self._resolve_subject_nodes(resolver, run_id, finding)
        graph_refs = tuple(
            sorted({str(node_id) for node_id in finding.affected_assessment_node_ids})
        )
        return FindingExplanation(
            finding=finding_view,
            rule_id=finding.rule_id,
            ruleset_version=run.ruleset_version,
            subjects=subjects,
            related_recommendations=tuple(_to_recommendation_view(item) for item in related),
            evidence=finding_view.evidence,
            graph_references=graph_refs,
        )

    def explain_recommendation(
        self,
        run_id: str,
        recommendation_id: str,
    ) -> RecommendationExplanation:
        resolver = self._resolver()
        evaluation = resolver.get_findings(run_id)
        recommendations = resolver.get_recommendations(run_id)
        rec_map = recommendation_map(recommendations)
        recommendation = rec_map.get(recommendation_id.strip())
        if recommendation is None:
            raise RecommendationNotFoundError(
                f"Recommendation not found: {recommendation_id}"
            )

        findings = finding_map(evaluation)
        related_findings = tuple(
            findings[finding_id]
            for finding_id in recommendation.related_finding_ids
            if finding_id in findings
        )
        by_finding = _recommendation_ids_by_finding(recommendations.recommendations)
        components = self._resolve_recommendation_components(resolver, run_id, recommendation)
        view = _to_recommendation_view(recommendation)
        return RecommendationExplanation(
            recommendation=view,
            related_findings=tuple(
                _to_finding_view(item, recommendation_ids=by_finding.get(item.id, ()))
                for item in related_findings
            ),
            affected_components=components,
            evidence=view.evidence,
            roadmap_phase=view.roadmap_phase,
            provider_id=recommendation.provider_id,
        )

    # ------------------------------------------------------------------
    # Components / dependencies
    # ------------------------------------------------------------------

    def get_component(self, run_id: str, component_id: str) -> ComponentView:
        graph = self._resolver().get_repository_graph(run_id)
        index = _GraphIndex(graph.nodes, graph.relationships)
        node = index.nodes.get(component_id.strip())
        if node is None:
            raise ComponentNotFoundError(f"Component not found: {component_id}")
        return index.to_component(node)

    def list_components(
        self,
        run_id: str,
        *,
        node_types: Sequence[str] | None = None,
        name_contains: str | None = None,
        path_prefix: str | None = None,
        limit: int | None = None,
    ) -> tuple[ComponentView, ...]:
        capped = _bounded_limit(
            limit,
            default=DEFAULT_COMPONENT_LIMIT,
            maximum=MAX_COMPONENT_LIMIT,
            label="components",
        )
        graph = self._resolver().get_repository_graph(run_id)
        index = _GraphIndex(graph.nodes, graph.relationships)
        type_filter = (
            None
            if node_types is None
            else {item.strip().lower() for item in node_types if item.strip()}
        )
        name_needle = None if name_contains is None else name_contains.strip().lower()
        path_needle = None if path_prefix is None else path_prefix.strip()

        matched: list[ComponentView] = []
        for node in sorted(graph.nodes, key=lambda item: (item.node_type, str(item.id))):
            if type_filter is not None and node.node_type.lower() not in type_filter:
                continue
            view = index.to_component(node)
            if name_needle is not None:
                haystack = " ".join(
                    part for part in (view.name, view.path, view.component_id) if part
                ).lower()
                if name_needle not in haystack:
                    continue
            if path_needle is not None:
                if view.path is None or not view.path.startswith(path_needle):
                    continue
            matched.append(view)
            if len(matched) >= capped:
                break
        return tuple(matched)

    def get_component_dependencies(
        self,
        run_id: str,
        component_id: str,
        *,
        direction: DependencyDirection | str = DependencyDirection.BOTH,
        depth: int = 1,
        limit: int | None = None,
    ) -> DependencyQueryResult:
        if depth < 1 or depth > MAX_DEPENDENCY_DEPTH:
            raise QueryLimitError(
                f"Dependency depth must be between 1 and {MAX_DEPENDENCY_DEPTH}"
            )
        capped = _bounded_limit(
            limit,
            default=DEFAULT_DEPENDENCY_LIMIT,
            maximum=MAX_DEPENDENCY_LIMIT,
            label="dependencies",
        )
        direction_value = DependencyDirection(str(direction).strip().lower())
        graph = self._resolver().get_repository_graph(run_id)
        index = _GraphIndex(graph.nodes, graph.relationships)
        root_id = component_id.strip()
        if root_id not in index.nodes:
            raise ComponentNotFoundError(f"Component not found: {component_id}")

        results: list[DependencyView] = []
        seen_edges: set[tuple[str, str, str, str]] = set()
        truncated = False

        frontier: deque[tuple[str, int]] = deque([(root_id, 0)])
        visited_nodes = {root_id}

        while frontier:
            node_id, current_depth = frontier.popleft()
            if current_depth >= depth:
                continue
            next_depth = current_depth + 1
            neighbors = index.dependency_neighbors(node_id, direction_value)
            for edge, edge_direction in neighbors:
                key = (
                    str(edge.source_node_id),
                    str(edge.target_node_id),
                    edge.relationship_type,
                    edge_direction.value,
                )
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                if len(results) >= capped:
                    truncated = True
                    break
                results.append(
                    DependencyView(
                        source_component_id=str(edge.source_node_id),
                        target_component_id=str(edge.target_node_id),
                        relationship_type=edge.relationship_type,
                        direction=edge_direction.value,
                        depth=next_depth,
                        provenance_source_ids=tuple(
                            sorted({item.source_id for item in edge.provenance})
                        ),
                    )
                )
                nxt = (
                    str(edge.target_node_id)
                    if edge_direction is DependencyDirection.OUTGOING
                    else str(edge.source_node_id)
                )
                if nxt not in visited_nodes:
                    visited_nodes.add(nxt)
                    frontier.append((nxt, next_depth))
            if truncated:
                break

        results.sort(
            key=lambda item: (
                item.depth,
                item.direction,
                item.source_component_id,
                item.target_component_id,
                item.relationship_type,
            )
        )
        return DependencyQueryResult(
            component_id=root_id,
            direction=direction_value.value,
            depth=depth,
            dependencies=tuple(results),
            truncated=truncated,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_repository(self, repository_id: str) -> RepositoryRecord:
        record = self._store.registry.get_by_id(repository_id.strip())
        if record is None:
            raise RepositoryQueryNotFoundError(f"Repository not found: {repository_id}")
        return record

    def _resolve_run_for_artifact(
        self,
        *,
        run_id: str | None,
        snapshot_id: str | None,
    ) -> str:
        if run_id is not None and snapshot_id is not None:
            raise KnowledgeQueryError("Provide run_id or snapshot_id, not both")
        if run_id is not None:
            compact = run_id.strip()
            if self._store.runs.get_run(compact) is None:
                raise AssessmentRunNotFoundError(f"Assessment run not found: {run_id}")
            return compact
        if snapshot_id is None:
            raise KnowledgeQueryError("run_id or snapshot_id is required")
        snapshot = self._store.snapshots.get_snapshot(snapshot_id.strip())
        if snapshot is None:
            raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
        for run in self._store.runs.list_runs(
            snapshot.repository_id,
            limit=MAX_RUN_LIMIT,
            status=AssessmentRunStatus.COMPLETED,
        ):
            if run.snapshot_id == snapshot.snapshot_id:
                return run.run_id
        raise AssessmentRunNotFoundError(
            f"No completed assessment run found for snapshot {snapshot_id}"
        )

    def _resolve_subject_nodes(
        self,
        resolver: ArtifactResolver,
        run_id: str,
        finding: Finding,
    ) -> tuple[GraphNodeView, ...]:
        assessment = resolver.get_assessment_graph(run_id)
        assessment_index = {str(node.id): node for node in assessment.nodes}
        repo_graph = resolver.get_repository_graph(run_id)
        repo_index = {str(node.id): node for node in repo_graph.nodes}

        views: list[GraphNodeView] = []
        seen: set[str] = set()
        for node_id in finding.affected_assessment_node_ids:
            key = str(node_id)
            if key in seen:
                continue
            seen.add(key)
            assessment_node = assessment_index.get(key)
            if assessment_node is not None:
                views.append(_to_graph_node_view(assessment_node))
                source_repo_id = assessment_node.properties.get("source_repository_node_id")
                if isinstance(source_repo_id, str) and source_repo_id in repo_index:
                    if source_repo_id not in seen:
                        seen.add(source_repo_id)
                        views.append(_to_graph_node_view(repo_index[source_repo_id]))
                continue
            repo_node = repo_index.get(key)
            if repo_node is not None:
                views.append(_to_graph_node_view(repo_node))
        views.sort(key=lambda item: (item.node_type, item.node_id))
        return tuple(views)

    def _resolve_recommendation_components(
        self,
        resolver: ArtifactResolver,
        run_id: str,
        recommendation: Recommendation,
    ) -> tuple[GraphNodeView, ...]:
        repo_graph = resolver.get_repository_graph(run_id)
        assessment = resolver.get_assessment_graph(run_id)
        repo_index = {str(node.id): node for node in repo_graph.nodes}
        assessment_index = {str(node.id): node for node in assessment.nodes}
        views: list[GraphNodeView] = []
        seen: set[str] = set()
        for node_id in recommendation.affected_node_ids:
            key = str(node_id)
            if key in seen:
                continue
            seen.add(key)
            if key in repo_index:
                views.append(_to_graph_node_view(repo_index[key]))
                continue
            assessment_node = assessment_index.get(key)
            if assessment_node is not None:
                views.append(_to_graph_node_view(assessment_node))
                source_repo_id = assessment_node.properties.get("source_repository_node_id")
                if isinstance(source_repo_id, str) and source_repo_id in repo_index:
                    if source_repo_id not in seen:
                        seen.add(source_repo_id)
                        views.append(_to_graph_node_view(repo_index[source_repo_id]))
        views.sort(key=lambda item: (item.node_type, item.node_id))
        return tuple(views)


class _GraphIndex:
    def __init__(
        self,
        nodes: Sequence[GraphNode],
        relationships: Sequence[GraphRelationship],
    ) -> None:
        self.nodes = {str(node.id): node for node in nodes}
        self.outgoing: dict[str, list[GraphRelationship]] = {}
        self.incoming: dict[str, list[GraphRelationship]] = {}
        for rel in relationships:
            if rel.relationship_type not in _DEPENDENCY_REL_TYPES:
                continue
            source = str(rel.source_node_id)
            target = str(rel.target_node_id)
            self.outgoing.setdefault(source, []).append(rel)
            self.incoming.setdefault(target, []).append(rel)

    def to_component(self, node: GraphNode) -> ComponentView:
        node_id = str(node.id)
        props = dict(node.properties)
        name = _optional_str(props.get("name")) or _optional_str(props.get("qualified_name"))
        path = _optional_str(props.get("path"))
        technologies = _technology_tags(props)
        return ComponentView(
            component_id=node_id,
            component_type=node.node_type,
            name=name,
            path=path,
            technologies=technologies,
            incoming_dependency_count=len(self.incoming.get(node_id, ())),
            outgoing_dependency_count=len(self.outgoing.get(node_id, ())),
            provenance_source_ids=tuple(sorted({item.source_id for item in node.provenance})),
            properties=_public_properties(props),
        )

    def dependency_neighbors(
        self,
        node_id: str,
        direction: DependencyDirection,
    ) -> list[tuple[GraphRelationship, DependencyDirection]]:
        items: list[tuple[GraphRelationship, DependencyDirection]] = []
        if direction in (DependencyDirection.OUTGOING, DependencyDirection.BOTH):
            for rel in self.outgoing.get(node_id, ()):
                items.append((rel, DependencyDirection.OUTGOING))
        if direction in (DependencyDirection.INCOMING, DependencyDirection.BOTH):
            for rel in self.incoming.get(node_id, ()):
                items.append((rel, DependencyDirection.INCOMING))
        return items


def _bounded_limit(
    value: int | None,
    *,
    default: int,
    maximum: int,
    label: str,
) -> int:
    if value is None:
        return default
    if value < 1:
        raise QueryLimitError(f"{label} limit must be >= 1")
    if value > maximum:
        raise QueryLimitError(f"{label} limit cannot exceed {maximum}")
    return value


def _to_snapshot_summary(snapshot: RepositorySnapshotRecord) -> SnapshotSummary:
    return SnapshotSummary(
        snapshot_id=snapshot.snapshot_id,
        repository_id=snapshot.repository_id,
        branch=snapshot.branch,
        revision_type=snapshot.revision_type,
        revision_id=snapshot.revision_id,
        content_fingerprint=snapshot.content_fingerprint,
        captured_at=snapshot.captured_at,
    )


def _file_change_view(change: Any) -> SnapshotFileChangeView:
    previous = change.previous
    current = change.current
    return SnapshotFileChangeView(
        path=str(change.path),
        change_type=change.change_type.value
        if isinstance(change.change_type, RepositoryChangeType)
        else str(change.change_type),
        previous_size_bytes=None if previous is None else previous.size_bytes,
        current_size_bytes=None if current is None else current.size_bytes,
        previous_content_digest=None if previous is None else previous.fingerprint.digest,
        current_content_digest=None if current is None else current.fingerprint.digest,
    )


def _to_evidence_view(item: Any) -> EvidenceView:
    node_id = None if item.node_id is None else str(item.node_id)
    return EvidenceView(
        evidence_type=item.evidence_type,
        source_id=item.source_id,
        path=item.path,
        excerpt=item.excerpt,
        node_id=node_id,
    )


def _to_finding_view(
    finding: Finding,
    *,
    recommendation_ids: Sequence[str] = (),
) -> FindingView:
    return FindingView(
        finding_id=finding.id,
        rule_id=finding.rule_id,
        severity=finding.severity.value,
        category=finding.category.value,
        title=finding.title,
        description=finding.description,
        subject_ids=tuple(str(node_id) for node_id in finding.affected_assessment_node_ids),
        evidence=tuple(_to_evidence_view(item) for item in finding.evidence),
        recommendation_ids=tuple(sorted(recommendation_ids)),
        metadata=dict(finding.metadata),
    )


def _roadmap_phase(metadata: Mapping[str, Any]) -> str | None:
    for key in ("roadmap_phase", "phase", "roadmapPhase"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _to_recommendation_view(recommendation: Recommendation) -> RecommendationView:
    return RecommendationView(
        recommendation_id=recommendation.id,
        provider_id=recommendation.provider_id,
        priority=recommendation.priority.value,
        category=recommendation.category.value,
        title=recommendation.title,
        summary=recommendation.summary,
        rationale=recommendation.rationale,
        related_finding_ids=tuple(recommendation.related_finding_ids),
        affected_node_ids=tuple(str(node_id) for node_id in recommendation.affected_node_ids),
        evidence=tuple(_to_evidence_view(item) for item in recommendation.evidence),
        actions=tuple(
            RecommendationActionView(
                order=action.order,
                title=action.title,
                description=action.description,
                command=action.command,
                documentation_ref=action.documentation_ref,
            )
            for action in recommendation.actions
        ),
        roadmap_phase=_roadmap_phase(recommendation.metadata),
        metadata=dict(recommendation.metadata),
    )


def _recommendation_ids_by_finding(
    recommendations: Sequence[Recommendation],
) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    for item in recommendations:
        for finding_id in item.related_finding_ids:
            mapping.setdefault(finding_id, []).append(item.id)
    return {key: tuple(sorted(set(values))) for key, values in mapping.items()}


def _to_graph_node_view(node: GraphNode) -> GraphNodeView:
    props = dict(node.properties)
    return GraphNodeView(
        node_id=str(node.id),
        node_type=node.node_type,
        name=_optional_str(props.get("name")) or _optional_str(props.get("qualified_name")),
        path=_optional_str(props.get("path")),
        properties=_public_properties(props),
        provenance_source_ids=tuple(sorted({item.source_id for item in node.provenance})),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        compact = value.strip()
        return compact or None
    return None


def _technology_tags(properties: Mapping[str, Any]) -> tuple[str, ...]:
    tags: list[str] = []
    for key in ("language", "ecosystem", "build_system", "technology"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            tags.append(value.strip())
    technologies = properties.get("technologies")
    if isinstance(technologies, (list, tuple)):
        for item in technologies:
            if isinstance(item, str) and item.strip():
                tags.append(item.strip())
    return tuple(sorted(set(tags)))


def _public_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    """Copy properties while dropping keys that look like absolute local paths."""

    blocked = {"absolute_path", "local_path", "filesystem_path", "cwd"}
    result: dict[str, Any] = {}
    for key, value in properties.items():
        if key in blocked:
            continue
        if isinstance(value, str) and _looks_like_absolute_path(value):
            continue
        result[key] = value
    return result


def _looks_like_absolute_path(value: str) -> bool:
    if value.startswith("/") and not value.startswith("//"):
        return True
    if len(value) > 2 and value[1] == ":" and value[0].isalpha():
        return True
    return False
