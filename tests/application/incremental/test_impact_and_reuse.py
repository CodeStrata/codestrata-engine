"""Impact analyzer and reuse policy tests."""

from __future__ import annotations

from codestrata.application.incremental.changes import ChangeClassifier
from codestrata.application.incremental.compatibility import CompatibilityEvaluator
from codestrata.application.incremental.fingerprints import current_engine_fingerprint
from codestrata.application.incremental.impact import ImpactAnalyzer
from codestrata.application.incremental.models import ReuseDecision
from codestrata.application.incremental.policies import IncrementalPlanningPolicy
from codestrata.application.incremental.reuse import ReusePolicy
from codestrata.application.knowledge.queries.models import FindingView, RecommendationView
from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
    GraphStatus,
    GraphType,
    NodeId,
    Provenance,
)
from codestrata.domain.graph.enums import ProvenanceSource
from codestrata.domain.repository.enums import RepositoryFileKind
from tests.application.incremental.helpers import entry, manifest


def _graph_with_path(path: str, node_id: str = "component:a") -> GraphSnapshot:
    node = GraphNode(
        id=NodeId(node_id),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": path, "name": "a"},
        provenance=(Provenance(source_type=ProvenanceSource.REPOSITORY_FILE, source_id=path),),
    )
    other = GraphNode(
        id=NodeId("component:b"),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": "src/Other.java", "name": "b"},
        provenance=(),
    )
    rel = GraphRelationship(
        id="rel:1",
        relationship_type="depends_on",
        source_node_id=NodeId(node_id),
        target_node_id=NodeId("component:b"),
        properties={},
        provenance=(),
    )
    metadata = GraphMetadata(
        graph_id=GraphId("g1"),
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="1.0.0",
        source_fingerprint="sha256:" + ("0" * 64),
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )
    return GraphSnapshot(metadata=metadata, nodes=(node, other), relationships=(rel,))


def test_documentation_only_impact_no_full_rebuild() -> None:
    previous = manifest(
        entry("README.md", "a" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None)
    )
    current = manifest(
        entry("README.md", "b" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None)
    )
    changes = ChangeClassifier().classify(previous, current)
    impact = ImpactAnalyzer().analyze(changes, repository_graph=None)
    assert impact.requires_full_rebuild is False


def test_mapped_source_change_impacts_component_and_findings() -> None:
    unchanged = tuple(entry(f"src/Keep{i}.java", (format(i, "x") * 64)[:64]) for i in range(10))
    previous = manifest(entry("src/A.java", "a" * 64), *unchanged)
    current = manifest(entry("src/A.java", "b" * 64), *unchanged)
    changes = ChangeClassifier().classify(previous, current)
    graph = _graph_with_path("src/A.java")
    findings = (
        FindingView(
            finding_id="finding:1",
            rule_id="rule.x",
            severity="medium",
            category="architecture",
            title="t",
            description="d",
            subject_ids=("component:a",),
        ),
    )
    recommendations = (
        RecommendationView(
            recommendation_id="recommendation:1",
            provider_id="provider.demo",
            priority="medium",
            category="modernize",
            title="r",
            summary="s",
            rationale="because",
            related_finding_ids=("finding:1",),
            roadmap_phase="phase-1",
        ),
    )
    impact = ImpactAnalyzer().analyze(
        changes,
        repository_graph=graph,
        findings=findings,
        recommendations=recommendations,
        compatibility=CompatibilityEvaluator().evaluate(
            current_engine_fingerprint(),
            current_engine_fingerprint(),
        ),
        policy=IncrementalPlanningPolicy(max_changed_files=100),
    )
    assert "component:a" in {item.entity_id for item in impact.impacted_components}
    assert "component:b" in {item.entity_id for item in impact.impacted_components}
    assert "finding:1" in {item.entity_id for item in impact.impacted_findings}
    assert "recommendation:1" in {item.entity_id for item in impact.impacted_recommendations}
    assert "phase-1" in {item.entity_id for item in impact.impacted_roadmap_phases}
    assert impact.requires_full_rebuild is False


def test_unmapped_source_forces_full_rebuild() -> None:
    previous = manifest(entry("src/Unknown.java", "a" * 64))
    current = manifest(entry("src/Unknown.java", "b" * 64))
    changes = ChangeClassifier().classify(previous, current)
    impact = ImpactAnalyzer().analyze(changes, repository_graph=_graph_with_path("src/A.java"))
    assert impact.requires_full_rebuild is True
    assert "unmapped_source_file" in impact.full_rebuild_reasons


def test_dependency_manifest_forces_full_rebuild() -> None:
    previous = manifest(
        entry("pom.xml", "a" * 64, kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None)
    )
    current = manifest(
        entry("pom.xml", "b" * 64, kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None)
    )
    changes = ChangeClassifier().classify(previous, current)
    impact = ImpactAnalyzer().analyze(changes, repository_graph=None)
    assert impact.requires_full_rebuild is True
    assert "dependency_manifest_changed" in impact.full_rebuild_reasons


def test_depth_bound_and_cycle_safe() -> None:
    a = GraphNode(
        id=NodeId("a"),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": "src/A.java"},
        provenance=(),
    )
    b = GraphNode(
        id=NodeId("b"),
        node_type="module",
        schema_version="1.0.0",
        properties={"path": "src/B.java"},
        provenance=(),
    )
    rels = (
        GraphRelationship(
            id="r1",
            relationship_type="depends_on",
            source_node_id=NodeId("a"),
            target_node_id=NodeId("b"),
            properties={},
            provenance=(),
        ),
        GraphRelationship(
            id="r2",
            relationship_type="depends_on",
            source_node_id=NodeId("b"),
            target_node_id=NodeId("a"),
            properties={},
            provenance=(),
        ),
    )
    metadata = GraphMetadata(
        graph_id=GraphId("g2"),
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="1.0.0",
        source_fingerprint="sha256:" + ("1" * 64),
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )
    graph = GraphSnapshot(metadata=metadata, nodes=(a, b), relationships=rels)
    previous = manifest(entry("src/A.java", "a" * 64))
    current = manifest(entry("src/A.java", "b" * 64))
    changes = ChangeClassifier().classify(previous, current)
    impact = ImpactAnalyzer().analyze(
        changes,
        repository_graph=graph,
        policy=IncrementalPlanningPolicy(dependency_depth=1),
    )
    ids = {item.entity_id for item in impact.impacted_components}
    assert "a" in ids
    assert "b" in ids


def test_reuse_policy_no_change_reusable_and_ai_conservative() -> None:
    previous = manifest(entry("src/A.java", "a" * 64))
    current = manifest(entry("src/A.java", "a" * 64))
    changes = ChangeClassifier().classify(previous, current)
    compatibility = CompatibilityEvaluator().evaluate(
        current_engine_fingerprint(),
        current_engine_fingerprint(),
    )
    impact = ImpactAnalyzer().analyze(changes, repository_graph=None, compatibility=compatibility)
    reuse = ReusePolicy().evaluate(
        changes=changes,
        impact=impact,
        compatibility=compatibility,
        ai_inputs_unchanged=True,
        ai_config_unchanged=True,
    )
    by_kind = {item.subject_kind: item.decision for item in reuse}
    assert by_kind["inventory"] is ReuseDecision.REUSABLE
    assert by_kind["findings"] is ReuseDecision.REUSABLE
    assert by_kind["ai_enrichment"] is ReuseDecision.REUSABLE

    reuse_uncertain_ai = ReusePolicy().evaluate(
        changes=changes,
        impact=impact,
        compatibility=compatibility,
        ai_inputs_unchanged=False,
        ai_config_unchanged=False,
    )
    assert (
        next(item for item in reuse_uncertain_ai if item.subject_kind == "ai_enrichment").decision
        is ReuseDecision.RECOMPUTE
    )


def test_reuse_full_rebuild_when_incompatible() -> None:
    previous = manifest(entry("src/A.java", "a" * 64))
    current = manifest(entry("src/A.java", "b" * 64))
    changes = ChangeClassifier().classify(previous, current)
    engine = current_engine_fingerprint()
    compatibility = CompatibilityEvaluator().evaluate(
        engine.model_copy(update={"scanner": "other"}),
        engine,
    )
    impact = ImpactAnalyzer().analyze(changes, repository_graph=None, compatibility=compatibility)
    reuse = ReusePolicy().evaluate(changes=changes, impact=impact, compatibility=compatibility)
    assert all(item.decision is ReuseDecision.FULL_REBUILD for item in reuse)
