"""Helpers for knowledge query service tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestrata.application.knowledge.models import (
    KnowledgeArtifactKind,
    RepositoryIdentityHints,
    StagedKnowledgeArtifact,
)
from codestrata.domain.assessment_graph import (
    AssessmentNodeFactory,
    RepositoryEntityReferenceProperties,
    build_assessment_graph_metadata,
)
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    RuleEvaluationResult,
)
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
)
from codestrata.domain.knowledge_binding import (
    KnowledgeBindingResult,
    KnowledgeMatchingStrategy,
)
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
)
from codestrata.domain.repository import (
    FileFingerprint,
    RepositoryFileEntry,
    RepositoryFingerprintFactory,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryPath,
    RepositoryRevision,
)
from codestrata.domain.repository.enums import (
    HashAlgorithm,
    RepositoryFileKind,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.domain.repository_graph import (
    DependencyProperties,
    ModuleProperties,
    RepositoryGraphNodeFactory,
    RepositoryNodeType,
    RepositoryProperties,
    RepositoryRelationshipType,
)
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.services.artifact_serialization import (
    findings_payload,
    recommendations_payload,
)


def make_manifest(
    *,
    key: str = "demo",
    files: tuple[tuple[str, str, int], ...] = (("README.md", "a" * 64, 12),),
) -> RepositoryManifest:
    entries = tuple(
        RepositoryFileEntry(
            path=RepositoryPath(path),
            file_kind=RepositoryFileKind.DOCUMENTATION,
            size_bytes=size,
            fingerprint=FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest),
        )
        for path, digest, size in files
    )
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key=key,
            source_type=RepositorySourceType.LOCAL,
            display_name=key,
        ),
        revision=RepositoryRevision(
            revision_id="working-tree",
            revision_type=RepositoryRevisionType.WORKING_TREE,
        ),
        files=entries,
    )


def fingerprint_for(manifest: RepositoryManifest) -> str:
    fp = RepositoryFingerprintFactory.from_manifest(manifest)
    return f"{fp.algorithm.value}:{fp.digest}"


def build_repository_graph_payload(
    *,
    with_cycle: bool = False,
) -> dict[str, Any]:
    factory = RepositoryGraphNodeFactory("demo")
    repo = factory.repository(RepositoryProperties(name="demo"))
    module_a = factory.module(
        module_key="a",
        properties=ModuleProperties(name="module-a", path="a"),
    )
    module_b = factory.module(
        module_key="b",
        properties=ModuleProperties(name="module-b", path="b"),
    )
    dep_b = factory.dependency(
        DependencyProperties(ecosystem="npm", name="lib-b", version="1.0.0")
    )
    dep_c = factory.dependency(
        DependencyProperties(ecosystem="npm", name="lib-c", version="2.0.0")
    )
    nodes = (repo, module_a, module_b, dep_b, dep_c)
    relationships = (
        GraphRelationship(
            id="rel:repo-a",
            relationship_type=RepositoryRelationshipType.CONTAINS.value,
            source_node_id=repo.id,
            target_node_id=module_a.id,
        ),
        GraphRelationship(
            id="rel:repo-b",
            relationship_type=RepositoryRelationshipType.CONTAINS.value,
            source_node_id=repo.id,
            target_node_id=module_b.id,
        ),
        GraphRelationship(
            id="rel:a-dep-b",
            relationship_type=RepositoryRelationshipType.DEPENDS_ON.value,
            source_node_id=module_a.id,
            target_node_id=dep_b.id,
        ),
        GraphRelationship(
            id="rel:b-dep-c",
            relationship_type=RepositoryRelationshipType.DEPENDS_ON.value,
            source_node_id=module_b.id,
            target_node_id=dep_c.id,
        ),
        GraphRelationship(
            id="rel:dep-b-dep-c",
            relationship_type=RepositoryRelationshipType.DEPENDS_ON.value,
            source_node_id=dep_b.id,
            target_node_id=dep_c.id,
        ),
    )
    if with_cycle:
        relationships = relationships + (
            GraphRelationship(
                id="rel:dep-c-dep-b",
                relationship_type=RepositoryRelationshipType.DEPENDS_ON.value,
                source_node_id=dep_c.id,
                target_node_id=dep_b.id,
            ),
        )
    snapshot = GraphSnapshot(
        metadata=GraphMetadata(
            graph_id=GraphId("graph:repo:demo"),
            graph_type=GraphType.REPOSITORY,
            schema_version="1.0.0",
            generator_version="0.1.0",
            source_fingerprint="fp:repo",
            generation_mode=GraphGenerationMode.FULL,
            status=GraphStatus.VALID,
        ),
        nodes=nodes,
        relationships=relationships,
    )
    return snapshot.model_dump(mode="json")


def build_assessment_graph_payload(subject_node: GraphNode) -> dict[str, Any]:
    nodes = AssessmentNodeFactory()
    ref = nodes.repository_entity_reference(
        RepositoryEntityReferenceProperties(
            source_repository_graph_id="graph:repo:demo",
            source_repository_node_id=str(subject_node.id),
            repository_node_type=subject_node.node_type,
        )
    )
    metadata = build_assessment_graph_metadata(
        repository_graph_id="graph:repo:demo",
        repository_source_fingerprint="fp:repo",
        knowledge_graph_id="graph:ekg:demo",
        knowledge_source_fingerprint="fp:ekg",
        binding_ids=(),
        generator_version="0.1.0",
    )
    snapshot = GraphSnapshot(metadata=metadata, nodes=(ref,), relationships=())
    return snapshot.model_dump(mode="json")


def build_ekg_payload() -> dict[str, Any]:
    return GraphSnapshot(
        metadata=GraphMetadata(
            graph_id=GraphId("graph:ekg:demo"),
            graph_type=GraphType.ENGINEERING_KNOWLEDGE,
            schema_version="1.0.0",
            generator_version="0.1.0",
            source_fingerprint="fp:ekg",
            generation_mode=GraphGenerationMode.FULL,
            status=GraphStatus.VALID,
        ),
        nodes=(),
        relationships=(),
    ).model_dump(mode="json")


def build_bindings_payload() -> dict[str, Any]:
    return KnowledgeBindingResult(
        repository_graph_id=GraphId("graph:repo:demo"),
        repository_source_fingerprint="fp:repo",
        knowledge_graph_id=GraphId("graph:ekg:demo"),
        knowledge_source_fingerprint="fp:ekg",
        matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
    ).model_dump(mode="json")


def build_findings_and_recommendations(
    *,
    subject_id: str,
) -> tuple[dict[str, Any], Finding]:
    finding = Finding.create(
        rule_id="rule.demo",
        title="Demo finding",
        description="A deterministic finding",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.ARCHITECTURE,
        evidence=(
            FindingEvidence(
                evidence_type="graph_node",
                source_id="rule.demo",
                path="a",
                excerpt="module-a",
                node_id=NodeId(subject_id),
            ),
        ),
        affected_assessment_node_ids=(NodeId(subject_id),),
        subject_keys=(subject_id,),
    )
    evaluation = RuleEvaluationResult.from_findings(
        findings=(finding,),
        rules_evaluated=("rule.demo",),
    )
    return findings_payload(evaluation), finding


def seed_completed_assessment(
    store: SqliteKnowledgeStore,
    *,
    display_name: str = "demo",
    github_url: str | None = None,
    branch: str = "main",
    manifest: RepositoryManifest | None = None,
    with_cycle: bool = False,
    include_ai: bool = False,
) -> tuple[str, str, str, Finding, Recommendation]:
    """Register repo, snapshot, and completed run with required artifacts."""

    if github_url is None:
        hints = RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name=display_name,
            local_path=Path(f"/tmp/codestrata-query-{display_name}"),
            existing_repository_key=display_name,
        )
    else:
        hints = RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name=display_name,
            source_location=github_url,
            existing_repository_key=display_name,
        )
    repo = store.registry.register_or_resolve(hints)
    used_manifest = manifest or make_manifest(key=display_name)
    fingerprint = fingerprint_for(used_manifest)
    snapshot = store.snapshots.create_or_get_snapshot(
        repository_id=repo.repository_id,
        branch=branch,
        revision_type=RepositoryRevisionType.COMMIT,
        revision_id="abc123",
        manifest=used_manifest,
        content_fingerprint=fingerprint,
    )
    run = store.runs.create_run(
        repository_id=repo.repository_id,
        assessment_mode="deterministic",
        codestrata_version="0.1.0",
        ruleset_version="1.2.0",
    )
    repo_graph = build_repository_graph_payload(with_cycle=with_cycle)
    module_a_id = next(
        str(node["id"])
        for node in repo_graph["nodes"]
        if node["node_type"] == RepositoryNodeType.MODULE.value
        and node["properties"]["name"] == "module-a"
    )
    module_node = GraphNode.model_validate(
        next(node for node in repo_graph["nodes"] if str(node["id"]) == module_a_id)
    )
    assessment_payload = build_assessment_graph_payload(module_node)
    assessment_subject_id = str(assessment_payload["nodes"][0]["id"])
    findings_doc, finding = build_findings_and_recommendations(subject_id=assessment_subject_id)
    recommendation = Recommendation.create(
        provider_id="provider.demo",
        title="Demo recommendation",
        summary="Fix the finding",
        rationale="Because the finding exists",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.MODERNIZATION,
        related_finding_ids=(finding.id,),
        actions=(
            RecommendationAction(
                order=1,
                title="Inspect module",
                description="Review module-a dependencies",
            ),
        ),
        affected_node_ids=(NodeId(module_a_id),),
        metadata={"roadmap_phase": "phase-1"},
        subject_keys=(module_a_id,),
    )
    recommendations_doc = recommendations_payload(
        RecommendationResult.from_recommendations(
            recommendations=(recommendation,),
            providers_evaluated=("provider.demo",),
        )
    )

    artifacts = [
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.REPOSITORY_GRAPH,
            schema_version="1.0.0",
            payload=repo_graph,
            source_fingerprint="fp:repo",
            snapshot_id=snapshot.snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.ENGINEERING_KNOWLEDGE_GRAPH,
            schema_version="1.0.0",
            payload=build_ekg_payload(),
            source_fingerprint="fp:ekg",
            snapshot_id=snapshot.snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.KNOWLEDGE_BINDINGS,
            schema_version="1.0.0",
            payload=build_bindings_payload(),
            source_fingerprint="fp:bindings",
            snapshot_id=snapshot.snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.ASSESSMENT_GRAPH,
            schema_version="1.0.0",
            payload=assessment_payload,
            source_fingerprint="fp:assessment",
            snapshot_id=snapshot.snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.FINDINGS,
            schema_version="1.0.0",
            payload=findings_doc,
            source_fingerprint="fp:findings",
            snapshot_id=snapshot.snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.RECOMMENDATIONS,
            schema_version="1.0.0",
            payload=recommendations_doc,
            source_fingerprint="fp:recommendations",
            snapshot_id=snapshot.snapshot_id,
        ),
    ]
    if include_ai:
        artifacts.extend(
            [
                StagedKnowledgeArtifact(
                    artifact_kind=KnowledgeArtifactKind.AI_EXECUTION,
                    schema_version="1.0.0",
                    payload={"status": "succeeded", "schema_version": "1.0.0"},
                    snapshot_id=snapshot.snapshot_id,
                ),
                StagedKnowledgeArtifact(
                    artifact_kind=KnowledgeArtifactKind.AI_ENRICHMENT,
                    schema_version="1.0.0",
                    payload={"narrative": "ok", "schema_version": "1.0.0"},
                    snapshot_id=snapshot.snapshot_id,
                ),
            ]
        )
    store.runs.complete_run(
        run.run_id,
        snapshot_id=snapshot.snapshot_id,
        artifacts=artifacts,
    )
    return repo.repository_id, run.run_id, snapshot.snapshot_id, finding, recommendation
