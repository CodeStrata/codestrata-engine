"""Tests for Phase 1→Phase 2 adapter and graph assessment orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.models import Repository
from codestrata.services.graph_assessment import (
    GraphAssessmentPipeline,
    GraphAssessmentPipelineError,
    Phase1RepositoryAdapter,
    build_graph_artifact_summary,
    write_graph_artifacts,
)


def _js_repository(root: Path) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture-js",
                "version": "1.0.0",
                "dependencies": {"express": "^4.0.0"},
            }
        ),
        encoding="utf-8",
    )
    src = root / "src"
    src.mkdir(exist_ok=True)
    (src / "index.js").write_text("console.log('ok');\n", encoding="utf-8")
    return Repository(
        name="fixture-js",
        path=root.resolve(),
        files=["package.json", "src/index.js"],
        total_files=2,
    )


def test_phase1_adapter_uses_relative_paths_and_omits_absolute_source_location(
    tmp_path: Path,
) -> None:
    repository = _js_repository(tmp_path / "app")
    adapted = Phase1RepositoryAdapter().adapt(repository)
    assert adapted.relative_paths == ("package.json", "src/index.js")
    assert adapted.identity.source_location is None
    assert adapted.identity.repository_key == "fixture-js"
    assert str(tmp_path) not in adapted.identity.repository_key
    content = adapted.content_reader.read("src/index.js")
    assert b"console.log" in content.data


def test_graph_assessment_pipeline_builds_javascript_bindings(tmp_path: Path) -> None:
    repository = _js_repository(tmp_path / "app")
    result = GraphAssessmentPipeline().run(repository)
    assert result.manifest.files
    assert result.repository_graph.nodes
    assert result.knowledge_graph.nodes
    assert result.binding_result.bindings
    keys = {binding.matched_key for binding in result.binding_result.bindings}
    assert "javascript" in keys
    dep_names = {
        node.properties.get("name")
        for node in result.repository_graph.nodes
        if node.node_type == "dependency"
    }
    assert "express" in dep_names
    assert result.assessment_graph.relationships
    assert result.binding_result.unmatched_observations is not None


def test_pipeline_does_not_mutate_source_graphs(tmp_path: Path) -> None:
    repository = _js_repository(tmp_path / "app")
    result = GraphAssessmentPipeline().run(repository)
    before_rg = result.repository_graph.snapshot.model_dump(mode="json")
    before_ekg = result.knowledge_graph.snapshot.model_dump(mode="json")
    before_bindings = result.binding_result.model_dump(mode="json")
    write_graph_artifacts(result, tmp_path / "run")
    assert result.repository_graph.snapshot.model_dump(mode="json") == before_rg
    assert result.knowledge_graph.snapshot.model_dump(mode="json") == before_ekg
    assert result.binding_result.model_dump(mode="json") == before_bindings


def test_artifact_writer_creates_stable_json(tmp_path: Path) -> None:
    repository = _js_repository(tmp_path / "app")
    result = GraphAssessmentPipeline().run(repository)
    written = write_graph_artifacts(result, tmp_path / "run-a")
    expected = {
        "repository-manifest.json",
        "repository-graph.json",
        "engineering-knowledge-graph.json",
        "knowledge-bindings.json",
        "assessment-graph.json",
        "graph-summary.json",
    }
    assert set(written.written_files) == expected
    for name in expected:
        path = written.directory / name
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        payload = json.loads(text)
        assert json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n" == text
        serialized = text.lower()
        assert str(tmp_path).lower() not in serialized
        assert "akia" not in serialized
        assert "aws_secret" not in serialized


def test_repeat_execution_produces_identical_graph_artifacts(tmp_path: Path) -> None:
    repository = _js_repository(tmp_path / "app")
    pipeline = GraphAssessmentPipeline()
    first = write_graph_artifacts(pipeline.run(repository), tmp_path / "run-1")
    second = write_graph_artifacts(pipeline.run(repository), tmp_path / "run-2")
    for name in first.written_files:
        assert (first.directory / name).read_bytes() == (second.directory / name).read_bytes()


def test_different_temp_roots_produce_identical_graph_artifacts(tmp_path: Path) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_repo = _js_repository(left_root / "app")
    right_repo = _js_repository(right_root / "app")
    pipeline = GraphAssessmentPipeline()
    left = write_graph_artifacts(pipeline.run(left_repo), left_root / "out")
    right = write_graph_artifacts(pipeline.run(right_repo), right_root / "out")
    for name in left.written_files:
        assert (left.directory / name).read_bytes() == (right.directory / name).read_bytes()


def test_empty_bindings_still_write_assessment_graph(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    (root / "README.md").write_text("# plain\n", encoding="utf-8")
    repository = Repository(name="plain", path=root, files=["README.md"], total_files=1)
    result = GraphAssessmentPipeline().run(repository)
    assert result.binding_result.bindings == ()
    assert result.assessment_graph.nodes == ()
    summary = build_graph_artifact_summary(result)
    assert summary.binding_count == 0
    assert summary.unmatched_observation_count >= 0


def test_alias_ambiguity_is_staged(tmp_path: Path) -> None:
    from codestrata.domain.engineering_knowledge import (
        EngineeringKnowledgeCatalogMetadata,
        EngineeringKnowledgeGraph,
        EngineeringKnowledgeNodeFactory,
        EngineeringKnowledgeNodeType,
        FrameworkProperties,
        build_engineering_knowledge_metadata,
    )
    from codestrata.domain.graph import GraphSnapshot, Provenance, ProvenanceSource

    repository = _js_repository(tmp_path / "app")
    factory = EngineeringKnowledgeNodeFactory()
    provenance = Provenance(
        source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
        source_id="test",
        extractor_id="test",
        extractor_version="1.0.0",
    )
    nodes = [
        factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(
                canonical_key="alpha",
                name="Alpha",
                aliases=("shared",),
            ),
            provenance=(provenance,),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(
                canonical_key="beta",
                name="Beta",
                aliases=("shared",),
            ),
            provenance=(provenance,),
        ),
    ]
    knowledge = EngineeringKnowledgeGraph(
        GraphSnapshot(
            metadata=build_engineering_knowledge_metadata(
                EngineeringKnowledgeCatalogMetadata(
                    catalog_id="ambiguous",
                    catalog_version="1.0.0",
                    name="Ambiguous",
                )
            ),
            nodes=tuple(sorted(nodes, key=lambda node: node.id.root)),
            relationships=(),
        )
    )
    pipeline = GraphAssessmentPipeline(knowledge_loader=lambda: knowledge)
    with pytest.raises(GraphAssessmentPipelineError, match=r"\[knowledge_pipeline\]"):
        pipeline.run(repository)


def test_knowledge_loader_failure_is_staged(tmp_path: Path) -> None:
    repository = _js_repository(tmp_path / "app")

    def _boom() -> None:
        raise ValueError("catalog corrupt")

    pipeline = GraphAssessmentPipeline(knowledge_loader=_boom)  # type: ignore[arg-type]
    with pytest.raises(GraphAssessmentPipelineError, match=r"\[engineering_knowledge\]"):
        pipeline.run(repository)
