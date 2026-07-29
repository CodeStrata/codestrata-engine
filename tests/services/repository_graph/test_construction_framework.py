"""Tests for extraction context, relationship factories, and graph assembler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphStatus,
    GraphType,
    Provenance,
    ProvenanceSource,
)
from codestrata.domain.repository import (
    FileFingerprint,
    HashAlgorithm,
    RepositoryFileEntry,
    RepositoryFileKind,
    RepositoryFingerprint,
    RepositoryGraphChangeSet,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryPath,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.domain.repository_graph import (
    FileProperties,
    RelationshipIdFactory,
    RepositoryGraphNodeFactory,
    RepositoryProperties,
    RepositoryRelationshipFactory,
    RepositoryRelationshipType,
)
from codestrata.services.repository_graph import (
    ExtractionDiagnostic,
    ExtractionDiagnosticSeverity,
    RepositoryExtractionContext,
    RepositoryExtractionResult,
    RepositoryExtractionScope,
    RepositoryExtractionStatistics,
    RepositoryGraphAssembler,
    RepositoryGraphAssemblyError,
    RepositoryGraphExtractor,
)
from tests.services.inventory.memory_reader import InMemoryContentReader


def _manifest() -> RepositoryManifest:
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key="petclinic",
            source_type=RepositorySourceType.LOCAL,
            display_name="Petclinic",
        ),
        revision=RepositoryRevision(
            revision_id="rev-1",
            revision_type=RepositoryRevisionType.WORKING_TREE,
        ),
        files=(
            RepositoryFileEntry(
                path="src/App.java",
                file_kind=RepositoryFileKind.SOURCE,
                size_bytes=12,
                fingerprint=FileFingerprint(
                    algorithm=HashAlgorithm.SHA256,
                    digest="a" * 64,
                ),
            ),
        ),
    )


def _metadata() -> GraphMetadata:
    return GraphMetadata(
        graph_id=GraphId("graph:petclinic"),
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="0.1.0",
        source_fingerprint="fp:1",
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )


def _provenance(source_id: str = "extractor:test") -> Provenance:
    return Provenance(
        source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
        source_id=source_id,
        extractor_id="test",
        extractor_version="1.0.0",
    )


def test_extraction_context_full_and_incremental() -> None:
    reader = InMemoryContentReader({"src/App.java": b"class App {}"})
    manifest = _manifest()
    full = RepositoryExtractionContext(
        manifest=manifest,
        content_reader=reader,
        scope=RepositoryExtractionScope.FULL,
        metadata={"run": "1"},
    )
    assert full.scope is RepositoryExtractionScope.FULL
    assert full.change_set is None
    assert full.metadata["run"] == "1"

    fingerprint = RepositoryFingerprint(
        algorithm=HashAlgorithm.SHA256,
        digest="b" * 64,
        manifest_version="1.0",
        file_count=1,
    )
    change_set = RepositoryGraphChangeSet(
        added_paths=(RepositoryPath("src/App.java"),),
        repository_fingerprint=fingerprint,
    )
    incremental = RepositoryExtractionContext(
        manifest=manifest,
        content_reader=reader,
        scope=RepositoryExtractionScope.INCREMENTAL,
        change_set=change_set,
    )
    assert incremental.change_set is change_set

    with pytest.raises(ValueError, match="change_set"):
        RepositoryExtractionContext(
            manifest=manifest,
            content_reader=reader,
            scope=RepositoryExtractionScope.INCREMENTAL,
        )


def test_relationship_id_and_relationship_factory_are_deterministic() -> None:
    ids = RelationshipIdFactory()
    first = ids.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id="repo:petclinic",
        target_node_id="repo:petclinic:file:src/App.java",
    )
    second = ids.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id="repo:petclinic",
        target_node_id="repo:petclinic:file:src/App.java",
    )
    assert first == second
    assert first.startswith("rel:contains:")
    assert "=>" in first

    factory = RepositoryRelationshipFactory()
    provenance = (_provenance(),)
    relationship = factory.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id="repo:petclinic",
        target_node_id="repo:petclinic:file:src/App.java",
        provenance=provenance,
    )
    assert relationship.id == first
    assert relationship.provenance == provenance
    assert relationship.properties["schema_version"] == factory.schema_version


class _StaticExtractor:
    def __init__(
        self,
        extractor_id: str,
        *,
        nodes: tuple[Any, ...] = (),
        relationships: tuple[Any, ...] = (),
        diagnostics: tuple[ExtractionDiagnostic, ...] = (),
    ) -> None:
        self._extractor_id = extractor_id
        self._nodes = nodes
        self._relationships = relationships
        self._diagnostics = diagnostics

    @property
    def extractor_id(self) -> str:
        return self._extractor_id

    def extract(self, context: RepositoryExtractionContext) -> RepositoryExtractionResult:
        _ = context
        return RepositoryExtractionResult(
            extractor_id=self._extractor_id,
            nodes=self._nodes,
            relationships=self._relationships,
            diagnostics=self._diagnostics,
            statistics=RepositoryExtractionStatistics(
                extractor_id=self._extractor_id,
                node_count=len(self._nodes),
                relationship_count=len(self._relationships),
                diagnostic_count=len(self._diagnostics),
                duration_ms=None,
            ),
            provenance=(_provenance(self._extractor_id),),
        )


def _repo_and_file_nodes() -> tuple[Any, Any]:
    nodes = RepositoryGraphNodeFactory("petclinic")
    repo = nodes.repository(
        RepositoryProperties(name="Petclinic"),
        provenance=(_provenance("structure"),),
    )
    file_node = nodes.file(
        FileProperties(path="src/App.java", file_kind=RepositoryFileKind.SOURCE),
        provenance=(_provenance("structure"),),
    )
    return repo, file_node


def test_assembler_merges_multiple_extractors_and_validates_schema() -> None:
    repo, file_node = _repo_and_file_nodes()
    relationships = RepositoryRelationshipFactory()
    contains = relationships.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id=repo.id,
        target_node_id=file_node.id,
        provenance=(_provenance("structure"),),
    )

    structure = _StaticExtractor(
        "structure",
        nodes=(repo, file_node),
        relationships=(contains,),
        diagnostics=(
            ExtractionDiagnostic(
                severity=ExtractionDiagnosticSeverity.INFO,
                code="ok",
                message="structure extraction complete",
                extractor_id="structure",
            ),
        ),
    )
    # Second extractor re-emits the same repository node (identical duplicate).
    overlay = _StaticExtractor("overlay", nodes=(repo,))

    reader = InMemoryContentReader({"src/App.java": b"class App {}"})
    context = RepositoryExtractionContext(
        manifest=_manifest(),
        content_reader=reader,
    )
    results = (structure.extract(context), overlay.extract(context))

    # Protocol structural check.
    extractors: list[RepositoryGraphExtractor] = [structure, overlay]
    assert all(hasattr(item, "extract") for item in extractors)

    graph = RepositoryGraphAssembler().assemble(results, metadata=_metadata())
    assert len(graph.nodes) == 2
    assert len(graph.relationships) == 1
    assert [node.id.root for node in graph.nodes] == sorted(node.id.root for node in graph.nodes)
    assert graph.metadata.graph_type is GraphType.REPOSITORY


def test_assembler_rejects_conflicting_duplicates() -> None:
    repo, file_node = _repo_and_file_nodes()
    nodes = RepositoryGraphNodeFactory("petclinic")
    conflicting_repo = nodes.repository(
        RepositoryProperties(name="Other"),
        provenance=(_provenance("conflict"),),
    )
    assert conflicting_repo.id == repo.id
    assert conflicting_repo != repo

    first = _StaticExtractor("a", nodes=(repo, file_node))
    second = _StaticExtractor("b", nodes=(conflicting_repo,))
    context = RepositoryExtractionContext(
        manifest=_manifest(),
        content_reader=InMemoryContentReader({"src/App.java": b"x"}),
    )
    with pytest.raises(RepositoryGraphAssemblyError, match="conflicting duplicate node"):
        RepositoryGraphAssembler().assemble(
            (first.extract(context), second.extract(context)),
            metadata=_metadata(),
        )


def test_assembler_merges_identical_relationships_and_rejects_conflicts() -> None:
    repo, file_node = _repo_and_file_nodes()
    relationships = RepositoryRelationshipFactory()
    contains = relationships.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id=repo.id,
        target_node_id=file_node.id,
        provenance=(_provenance("a"),),
    )
    identical = relationships.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id=repo.id,
        target_node_id=file_node.id,
        provenance=(_provenance("a"),),
    )
    conflicting = relationships.create(
        relationship_type=RepositoryRelationshipType.CONTAINS,
        source_node_id=repo.id,
        target_node_id=file_node.id,
        provenance=(_provenance("b"),),
    )
    assert contains.id == identical.id == conflicting.id
    assert contains == identical
    assert contains != conflicting

    context = RepositoryExtractionContext(
        manifest=_manifest(),
        content_reader=InMemoryContentReader({"src/App.java": b"x"}),
    )
    merged = RepositoryGraphAssembler().assemble(
        (
            _StaticExtractor("a", nodes=(repo, file_node), relationships=(contains,)).extract(
                context
            ),
            _StaticExtractor("b", nodes=(repo, file_node), relationships=(identical,)).extract(
                context
            ),
        ),
        metadata=_metadata(),
    )
    assert len(merged.relationships) == 1

    with pytest.raises(RepositoryGraphAssemblyError, match="conflicting duplicate relationship"):
        RepositoryGraphAssembler().assemble(
            (
                _StaticExtractor("a", nodes=(repo, file_node), relationships=(contains,)).extract(
                    context
                ),
                _StaticExtractor(
                    "b", nodes=(repo, file_node), relationships=(conflicting,)
                ).extract(context),
            ),
            metadata=_metadata(),
        )


def test_schema_validation_rejects_invalid_assembled_endpoints() -> None:
    repo, file_node = _repo_and_file_nodes()
    relationships = RepositoryRelationshipFactory()
    # CALLS requires callable -> callable; this is invalid for repository/file.
    invalid = relationships.create(
        relationship_type=RepositoryRelationshipType.CALLS,
        source_node_id=repo.id,
        target_node_id=file_node.id,
    )
    context = RepositoryExtractionContext(
        manifest=_manifest(),
        content_reader=InMemoryContentReader({"src/App.java": b"x"}),
    )
    result = _StaticExtractor(
        "bad",
        nodes=(repo, file_node),
        relationships=(invalid,),
    ).extract(context)
    with pytest.raises(Exception, match="invalid|CALLS|calls"):
        RepositoryGraphAssembler().assemble((result,), metadata=_metadata())


def test_extraction_result_preserves_diagnostics_and_statistics() -> None:
    diagnostic = ExtractionDiagnostic(
        severity=ExtractionDiagnosticSeverity.WARNING,
        code="empty-file",
        message="file has no content",
        path="src/App.java",
        extractor_id="structure",
    )
    result = RepositoryExtractionResult(
        extractor_id="structure",
        diagnostics=(diagnostic,),
        statistics=RepositoryExtractionStatistics(
            extractor_id="structure",
            node_count=0,
            relationship_count=0,
            diagnostic_count=1,
        ),
    )
    assert result.diagnostics[0].severity is ExtractionDiagnosticSeverity.WARNING
    assert result.statistics.duration_ms is None
    assert isinstance(result.nodes, tuple)


def test_context_metadata_is_immutable_mapping() -> None:
    context = RepositoryExtractionContext(
        manifest=_manifest(),
        content_reader=InMemoryContentReader({}),
        metadata={"a": 1},
    )
    assert isinstance(context.metadata, Mapping)
    with pytest.raises(TypeError):
        context.metadata["a"] = 2  # type: ignore[index]
