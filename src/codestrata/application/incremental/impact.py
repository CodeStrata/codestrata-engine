"""Bounded impact analysis over persisted graphs and findings."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Sequence
from uuid import UUID

from codestrata.application.incremental.models import (
    CompatibilityResult,
    FileChangeKind,
    ImpactAnalysis,
    ImpactEntity,
    ImpactEntityKind,
    ImpactReason,
    ImpactRelationship,
    RepositoryChangeSet,
)
from codestrata.application.incremental.policies import IncrementalPlanningPolicy
from codestrata.application.knowledge.queries.models import FindingView, RecommendationView
from codestrata.domain.graph.models import GraphSnapshot
from codestrata.domain.repository.enums import RepositoryFileKind

logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    """Map file changes to potentially invalidated knowledge entities."""

    def analyze(
        self,
        changes: RepositoryChangeSet,
        *,
        repository_graph: GraphSnapshot | None,
        findings: Sequence[FindingView] = (),
        recommendations: Sequence[RecommendationView] = (),
        compatibility: CompatibilityResult | None = None,
        policy: IncrementalPlanningPolicy | None = None,
    ) -> ImpactAnalysis:
        policy = policy or IncrementalPlanningPolicy()
        rebuild_reasons: list[str] = []
        unknown: list[str] = []
        truncated = False

        if compatibility is not None and not compatibility.compatible:
            rebuild_reasons.extend(compatibility.blocking_reasons)

        changed_files = sorted(
            {
                *(item.path for item in changes.added),
                *(item.path for item in changes.modified),
                *(item.path for item in changes.deleted),
                *(item.path for item in changes.metadata_changed),
                *(item.path for item in changes.unknown),
            }
        )

        # Documentation-only with no other signals can avoid rebuild.
        if changes.has_documentation_only_changes and not (
            changes.has_source_changes
            or changes.has_build_changes
            or changes.has_configuration_changes
            or changes.has_dependency_manifest_changes
        ):
            return ImpactAnalysis(
                directly_changed_files=tuple(changed_files),
                requires_full_rebuild=False,
                full_rebuild_reasons=(),
            )

        if changes.change_count > policy.max_changed_files:
            rebuild_reasons.append("too_many_changed_files")

        total_files = changes.change_count + changes.unchanged_count
        if total_files > 0:
            ratio = changes.change_count / total_files
            if ratio > policy.max_change_ratio:
                rebuild_reasons.append("change_ratio_exceeded")

        # Unmapped / unclassified source impact cannot be bounded safely.
        unclassified_source = any(
            item.role is RepositoryFileKind.UNKNOWN or item.kind is FileChangeKind.UNKNOWN
            for item in (*changes.added, *changes.modified, *changes.deleted, *changes.unknown)
            if item.role
            in {
                RepositoryFileKind.SOURCE,
                RepositoryFileKind.TEST,
                RepositoryFileKind.UNKNOWN,
            }
        )
        if unclassified_source and policy.fallback_on_unknown_impact:
            rebuild_reasons.append("unknown_source_impact")
            unknown.append("unclassified_source_change")

        if changes.has_dependency_manifest_changes:
            rebuild_reasons.append("dependency_manifest_changed")
        if changes.has_build_changes:
            rebuild_reasons.append("build_files_changed")

        path_to_nodes = _index_nodes_by_path(repository_graph)
        seed_node_ids: list[str] = []
        for path in changed_files:
            matched = path_to_nodes.get(path, ())
            is_source_like = any(
                item.role in {RepositoryFileKind.SOURCE, RepositoryFileKind.TEST}
                for item in (*changes.added, *changes.modified, *changes.deleted, *changes.unknown)
                if item.path == path
            )
            if not matched and is_source_like:
                unknown.append(f"unmapped_source_file:{path}")
                if policy.fallback_on_unknown_impact:
                    rebuild_reasons.append("unmapped_source_file")
            seed_node_ids.extend(matched)

        # Missing structural hashes reduce reuse confidence but do not alone force rebuild
        # when files map to known graph entities.
        if any(
            item.dimensions.unknown
            and item.role in {RepositoryFileKind.SOURCE, RepositoryFileKind.TEST}
            for item in (*changes.added, *changes.modified)
        ):
            unknown.append("structural_hash_unavailable")

        impacted_node_ids, relationships, traversal_truncated = _bounded_traverse(
            repository_graph,
            seed_ids=seed_node_ids,
            depth=policy.dependency_depth,
            max_nodes=policy.max_impacted_components,
        )
        if traversal_truncated:
            truncated = True
            rebuild_reasons.append("impact_traversal_truncated")

        components = tuple(
            ImpactEntity(
                kind=ImpactEntityKind.COMPONENT,
                entity_id=node_id,
                display_name=node_id,
                source_ids=tuple(changed_files[:5]),
                reasons=(ImpactReason.COMPONENT_DEPENDENCY,),
                directly_impacted=node_id in set(seed_node_ids),
            )
            for node_id in sorted(impacted_node_ids)
        )
        if len(components) > policy.max_impacted_components:
            truncated = True
            rebuild_reasons.append("too_many_impacted_components")
            components = components[: policy.max_impacted_components]

        impacted_findings = _impacted_findings(findings, impacted_node_ids, policy)
        if len(impacted_findings) > policy.max_impacted_findings:
            truncated = True
            rebuild_reasons.append("too_many_impacted_findings")
            impacted_findings = impacted_findings[: policy.max_impacted_findings]

        finding_ids = {item.entity_id for item in impacted_findings}
        impacted_recs, phases = _impacted_recommendations(
            recommendations,
            finding_ids,
            policy,
        )
        if len(impacted_recs) > policy.max_impacted_recommendations:
            truncated = True
            rebuild_reasons.append("too_many_impacted_recommendations")
            impacted_recs = impacted_recs[: policy.max_impacted_recommendations]

        requires_full = bool(rebuild_reasons)
        # Deduplicate reasons while preserving order.
        unique_reasons = tuple(dict.fromkeys(rebuild_reasons))
        analysis = ImpactAnalysis(
            directly_changed_files=tuple(changed_files),
            impacted_components=components,
            impacted_graph_nodes=components,
            impacted_findings=tuple(impacted_findings),
            impacted_recommendations=tuple(impacted_recs),
            impacted_roadmap_phases=tuple(phases),
            relationships=tuple(relationships),
            unknown_impacts=tuple(sorted(set(unknown))),
            truncated=truncated,
            requires_full_rebuild=requires_full,
            full_rebuild_reasons=unique_reasons,
        )
        logger.info(
            "incremental.impact_analyzed",
            extra={
                "changed_files": len(changed_files),
                "impacted_components": len(components),
                "requires_full_rebuild": requires_full,
            },
        )
        return analysis


def _index_nodes_by_path(graph: GraphSnapshot | None) -> dict[str, tuple[str, ...]]:
    if graph is None:
        return {}
    index: dict[str, list[str]] = {}
    for node in graph.nodes:
        props = dict(node.properties)
        path = props.get("path") or props.get("file_path") or props.get("source_path")
        if isinstance(path, str) and path.strip():
            index.setdefault(path.strip(), []).append(str(node.id))
        # Also match provenance source ids that look like paths.
        for prov in node.provenance:
            if "/" in prov.source_id or prov.source_id.endswith(
                (".java", ".py", ".js", ".ts", ".go", ".cs")
            ):
                index.setdefault(prov.source_id, []).append(str(node.id))
    return {key: tuple(sorted(set(values))) for key, values in index.items()}


def _bounded_traverse(
    graph: GraphSnapshot | None,
    *,
    seed_ids: Sequence[str],
    depth: int,
    max_nodes: int,
) -> tuple[set[str], list[ImpactRelationship], bool]:
    if graph is None or not seed_ids:
        return set(seed_ids), [], False
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for rel in graph.relationships:
        adjacency.setdefault(str(rel.source_node_id), []).append(
            (str(rel.target_node_id), rel.relationship_type)
        )
        adjacency.setdefault(str(rel.target_node_id), []).append(
            (str(rel.source_node_id), rel.relationship_type)
        )

    visited: set[str] = set()
    relationships: list[ImpactRelationship] = []
    truncated = False
    queue: deque[tuple[str, int]] = deque((node_id, 0) for node_id in seed_ids)
    while queue:
        node_id, current_depth = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        if len(visited) > max_nodes:
            truncated = True
            break
        if current_depth >= depth:
            continue
        for neighbor, rel_type in sorted(adjacency.get(node_id, ()), key=lambda item: item[0]):
            relationships.append(
                ImpactRelationship(
                    source_id=node_id,
                    target_id=neighbor,
                    relationship_type=rel_type,
                    reason=ImpactReason.COMPONENT_DEPENDENCY,
                )
            )
            if neighbor not in visited:
                queue.append((neighbor, current_depth + 1))
    return visited, relationships, truncated


def _impacted_findings(
    findings: Sequence[FindingView],
    impacted_nodes: set[str],
    policy: IncrementalPlanningPolicy,
) -> list[ImpactEntity]:
    del policy
    results: list[ImpactEntity] = []
    for finding in findings:
        if _looks_like_uuid(finding.finding_id):
            continue
        subjects = set(finding.subject_ids)
        if subjects & impacted_nodes or not impacted_nodes and finding.subject_ids:
            # Only mark when there is overlap with impacted nodes.
            if subjects & impacted_nodes:
                results.append(
                    ImpactEntity(
                        kind=ImpactEntityKind.FINDING,
                        entity_id=finding.finding_id,
                        display_name=finding.title,
                        source_ids=tuple(sorted(subjects & impacted_nodes)),
                        reasons=(ImpactReason.FINDING_SOURCE,),
                        directly_impacted=True,
                    )
                )
    return sorted(results, key=lambda item: item.entity_id)


def _impacted_recommendations(
    recommendations: Sequence[RecommendationView],
    finding_ids: set[str],
    policy: IncrementalPlanningPolicy,
) -> tuple[list[ImpactEntity], list[ImpactEntity]]:
    del policy
    recs: list[ImpactEntity] = []
    phases: dict[str, list[str]] = {}
    for recommendation in recommendations:
        related = set(recommendation.related_finding_ids)
        if related & finding_ids:
            recs.append(
                ImpactEntity(
                    kind=ImpactEntityKind.RECOMMENDATION,
                    entity_id=recommendation.recommendation_id,
                    display_name=recommendation.title,
                    source_ids=tuple(sorted(related & finding_ids)),
                    reasons=(ImpactReason.RECOMMENDATION_REFERENCE,),
                    directly_impacted=True,
                )
            )
            if recommendation.roadmap_phase:
                phases.setdefault(recommendation.roadmap_phase, []).append(
                    recommendation.recommendation_id
                )
    phase_entities = [
        ImpactEntity(
            kind=ImpactEntityKind.ROADMAP_PHASE,
            entity_id=phase,
            display_name=phase,
            source_ids=tuple(sorted(ids)),
            reasons=(ImpactReason.RECOMMENDATION_REFERENCE,),
            directly_impacted=True,
        )
        for phase, ids in sorted(phases.items())
    ]
    return sorted(recs, key=lambda item: item.entity_id), phase_entities


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value.strip())
    except ValueError:
        return False
    return True
