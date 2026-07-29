"""Deterministic persistence of Phase 2 graph assessment artifacts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.services.graph_assessment.exceptions import GraphAssessmentPipelineError
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult

GRAPH_ARTIFACT_DIRECTORY_NAME = "graphs"

REPOSITORY_MANIFEST_FILENAME = "repository-manifest.json"
REPOSITORY_GRAPH_FILENAME = "repository-graph.json"
ENGINEERING_KNOWLEDGE_GRAPH_FILENAME = "engineering-knowledge-graph.json"
KNOWLEDGE_BINDINGS_FILENAME = "knowledge-bindings.json"
ASSESSMENT_GRAPH_FILENAME = "assessment-graph.json"
GRAPH_SUMMARY_FILENAME = "graph-summary.json"


class GraphArtifactSummary(BaseModel):
    """Machine-readable summary of persisted graph artifacts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_graph_id: str
    repository_source_fingerprint: str
    repository_node_count: int = Field(ge=0)
    repository_relationship_count: int = Field(ge=0)
    knowledge_graph_id: str
    knowledge_source_fingerprint: str
    knowledge_node_count: int = Field(ge=0)
    knowledge_relationship_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    unmatched_observation_count: int = Field(ge=0)
    assessment_graph_id: str
    assessment_source_fingerprint: str
    assessment_node_count: int = Field(ge=0)
    assessment_relationship_count: int = Field(ge=0)
    matched_concepts_by_knowledge_type: dict[str, int] = Field(default_factory=dict)
    engineering_knowledge_persisted: bool = True
    engineering_knowledge_persistence_note: str = (
        "Builtin catalog is small; full Engineering Knowledge Graph snapshot is persisted."
    )


class GraphArtifactWriteResult(BaseModel):
    """Paths written for one assessment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    directory: Path
    summary: GraphArtifactSummary
    written_files: tuple[str, ...]


def build_graph_artifact_summary(
    result: GraphAssessmentPipelineResult,
) -> GraphArtifactSummary:
    """Build a concise deterministic summary from pipeline outputs."""

    type_counts: Counter[str] = Counter()
    for binding in result.binding_result.bindings:
        type_counts[binding.knowledge_node_type] += 1
    matched = {key: type_counts[key] for key in sorted(type_counts)}
    return GraphArtifactSummary(
        repository_graph_id=result.repository_graph.metadata.graph_id.root,
        repository_source_fingerprint=result.repository_graph.metadata.source_fingerprint,
        repository_node_count=len(result.repository_graph.nodes),
        repository_relationship_count=len(result.repository_graph.relationships),
        knowledge_graph_id=result.knowledge_graph.metadata.graph_id.root,
        knowledge_source_fingerprint=result.knowledge_graph.metadata.source_fingerprint,
        knowledge_node_count=len(result.knowledge_graph.nodes),
        knowledge_relationship_count=len(result.knowledge_graph.relationships),
        binding_count=len(result.binding_result.bindings),
        unmatched_observation_count=len(result.binding_result.unmatched_observations),
        assessment_graph_id=result.assessment_graph.metadata.graph_id.root,
        assessment_source_fingerprint=result.assessment_graph.metadata.source_fingerprint,
        assessment_node_count=len(result.assessment_graph.nodes),
        assessment_relationship_count=len(result.assessment_graph.relationships),
        matched_concepts_by_knowledge_type=matched,
    )


def write_graph_artifacts(
    result: GraphAssessmentPipelineResult,
    run_directory: Path,
) -> GraphArtifactWriteResult:
    """Persist deterministic graph JSON under ``run_directory/graphs``."""

    # Lazy import avoids a cycle with codestrata.services.artifact_serialization.
    from codestrata.services.artifact_serialization import (
        assessment_graph_payload,
        dumps_stable_json,
        engineering_knowledge_graph_payload,
        graph_summary_payload,
        knowledge_bindings_payload,
        repository_graph_payload,
        repository_manifest_payload,
    )

    try:
        graphs_directory = run_directory / GRAPH_ARTIFACT_DIRECTORY_NAME
        graphs_directory.mkdir(parents=True, exist_ok=True)
        summary = build_graph_artifact_summary(result)

        payloads: dict[str, Any] = {
            REPOSITORY_MANIFEST_FILENAME: repository_manifest_payload(result.manifest),
            REPOSITORY_GRAPH_FILENAME: repository_graph_payload(result),
            ENGINEERING_KNOWLEDGE_GRAPH_FILENAME: engineering_knowledge_graph_payload(result),
            KNOWLEDGE_BINDINGS_FILENAME: knowledge_bindings_payload(result),
            ASSESSMENT_GRAPH_FILENAME: assessment_graph_payload(result),
            GRAPH_SUMMARY_FILENAME: graph_summary_payload(result),
        }

        written: list[str] = []
        for filename, payload in payloads.items():
            path = graphs_directory / filename
            path.write_text(dumps_stable_json(payload), encoding="utf-8")
            written.append(filename)

        return GraphArtifactWriteResult(
            directory=graphs_directory,
            summary=summary,
            written_files=tuple(sorted(written)),
        )
    except GraphAssessmentPipelineError:
        raise
    except Exception as error:
        raise GraphAssessmentPipelineError(
            "artifact_write",
            f"Graph artifact serialization failed: {error}",
        ) from error


def format_graph_console_summary(summary: GraphArtifactSummary) -> tuple[str, ...]:
    """Return concise console lines for a graph summary."""

    return (
        (
            "Repository Graph: "
            f"{summary.repository_node_count} nodes, "
            f"{summary.repository_relationship_count} relationships"
        ),
        f"Knowledge Bindings: {summary.binding_count}",
        (
            "Assessment Graph: "
            f"{summary.assessment_node_count} nodes, "
            f"{summary.assessment_relationship_count} relationships"
        ),
    )
