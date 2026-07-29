"""Assessment knowledge persistence helpers (application layer)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestrata import RULESET_VERSION, __version__
from codestrata.application.knowledge.models import (
    KnowledgeArtifactKind,
    RepositoryIdentityHints,
    StagedKnowledgeArtifact,
)
from codestrata.domain.assessment_graph.factories import ASSESSMENT_GRAPH_SCHEMA_VERSION
from codestrata.domain.engineering_knowledge.factories import (
    ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
)
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.knowledge_binding.models import KNOWLEDGE_BINDING_RESULT_VERSION
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository import RepositoryManifest
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.models import Repository
from codestrata.reporting.ai_execution import AI_EXECUTION_SCHEMA_VERSION
from codestrata.services.artifact_serialization import (
    assessment_graph_payload,
    engineering_knowledge_graph_payload,
    findings_payload,
    knowledge_bindings_payload,
    recommendations_payload,
    repository_graph_payload,
    repository_manifest_payload,
)
from codestrata.services.graph_assessment.adapter import Phase1RepositoryAdapter
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult


def identity_hints_for_repository(repository: Repository) -> RepositoryIdentityHints:
    """Build registry hints from a scanned Phase 1 repository."""

    adapter = Phase1RepositoryAdapter()
    return RepositoryIdentityHints(
        source_type=adapter._source_type(repository),
        display_name=repository.name.strip() or "repository",
        source_location=adapter._source_location(repository),
        local_path=Path(repository.path).expanduser().resolve(),
        existing_repository_key=Phase1RepositoryAdapter.repository_key_for(repository),
    )


def build_staged_assessment_artifacts(
    *,
    graph_pipeline_result: GraphAssessmentPipelineResult,
    rule_evaluation: RuleEvaluationResult,
    recommendation_result: RecommendationResult,
    ai_execution_document: dict[str, Any] | None = None,
    ai_enrichment_payload: dict[str, Any] | None = None,
    snapshot_id: str | None = None,
) -> list[StagedKnowledgeArtifact]:
    """Build immutable artifact payloads for a completed assessment run."""

    result = graph_pipeline_result
    staged: list[StagedKnowledgeArtifact] = [
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.REPOSITORY_MANIFEST,
            schema_version=result.manifest.manifest_version,
            payload=repository_manifest_payload(result.manifest),
            source_fingerprint=(
                f"{_fingerprint_algorithm(result)}:{_fingerprint_digest(result)}"
            ),
            snapshot_id=snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.REPOSITORY_GRAPH,
            schema_version=result.repository_graph.metadata.schema_version
            or REPOSITORY_GRAPH_SCHEMA_VERSION,
            payload=repository_graph_payload(result),
            source_fingerprint=result.repository_graph.metadata.source_fingerprint,
            snapshot_id=snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.ENGINEERING_KNOWLEDGE_GRAPH,
            schema_version=result.knowledge_graph.metadata.schema_version
            or ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
            payload=engineering_knowledge_graph_payload(result),
            source_fingerprint=result.knowledge_graph.metadata.source_fingerprint,
            snapshot_id=snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.KNOWLEDGE_BINDINGS,
            schema_version=result.binding_result.result_version
            or KNOWLEDGE_BINDING_RESULT_VERSION,
            payload=knowledge_bindings_payload(result),
            source_fingerprint=result.binding_result.repository_source_fingerprint,
            snapshot_id=snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.ASSESSMENT_GRAPH,
            schema_version=result.assessment_graph.metadata.schema_version
            or ASSESSMENT_GRAPH_SCHEMA_VERSION,
            payload=assessment_graph_payload(result),
            source_fingerprint=result.assessment_graph.metadata.source_fingerprint,
            snapshot_id=snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.FINDINGS,
            schema_version="1.0.0",
            payload=findings_payload(rule_evaluation),
            source_fingerprint=result.assessment_graph.metadata.source_fingerprint,
            snapshot_id=snapshot_id,
        ),
        StagedKnowledgeArtifact(
            artifact_kind=KnowledgeArtifactKind.RECOMMENDATIONS,
            schema_version=recommendation_result.version,
            payload=recommendations_payload(recommendation_result),
            source_fingerprint=result.assessment_graph.metadata.source_fingerprint,
            snapshot_id=snapshot_id,
        ),
    ]
    if ai_execution_document is not None:
        staged.append(
            StagedKnowledgeArtifact(
                artifact_kind=KnowledgeArtifactKind.AI_EXECUTION,
                schema_version=str(
                    ai_execution_document.get("schema_version", AI_EXECUTION_SCHEMA_VERSION)
                ),
                payload=ai_execution_document,
                snapshot_id=snapshot_id,
            )
        )
    if ai_enrichment_payload is not None:
        staged.append(
            StagedKnowledgeArtifact(
                artifact_kind=KnowledgeArtifactKind.AI_ENRICHMENT,
                schema_version=str(ai_enrichment_payload.get("version", "1.0.0")),
                payload=ai_enrichment_payload,
                snapshot_id=snapshot_id,
            )
        )
    return staged


def default_tooling_versions() -> tuple[str, str]:
    """Return ``(codestrata_version, ruleset_version)`` for run records."""

    return __version__, RULESET_VERSION


def _fingerprint_digest(result: GraphAssessmentPipelineResult) -> str:
    from codestrata.domain.repository.fingerprints import RepositoryFingerprintFactory

    return RepositoryFingerprintFactory.from_manifest(result.manifest).digest


def _fingerprint_algorithm(result: GraphAssessmentPipelineResult) -> str:
    from codestrata.domain.repository.fingerprints import RepositoryFingerprintFactory

    return RepositoryFingerprintFactory.from_manifest(result.manifest).algorithm.value


def content_fingerprint_for_manifest(manifest: RepositoryManifest) -> str:
    from codestrata.domain.repository.fingerprints import RepositoryFingerprintFactory

    fingerprint = RepositoryFingerprintFactory.from_manifest(manifest)
    return f"{fingerprint.algorithm.value}:{fingerprint.digest}"
