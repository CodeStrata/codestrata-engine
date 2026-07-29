"""Orchestrate Phase 2 inventory → graphs → bindings → Assessment Graph.

This application service composes existing builders. It is intentionally free of
Typer, console rendering, AWS/Bedrock, and report formatting concerns.
"""

from __future__ import annotations

from collections.abc import Callable

from codestrata.domain.engineering_knowledge import EngineeringKnowledgeGraph
from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphStatus,
    GraphType,
)
from codestrata.domain.repository import RepositoryFingerprintFactory
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.models import Repository
from codestrata.services.assessment_graph import (
    AssessmentGraphBuilder,
    AssessmentGraphBuildError,
)
from codestrata.services.engineering_knowledge import load_builtin_engineering_knowledge_catalog
from codestrata.services.graph_assessment.adapter import Phase1RepositoryAdapter
from codestrata.services.graph_assessment.exceptions import GraphAssessmentPipelineError
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.inventory import RepositoryInventoryBuilder
from codestrata.services.knowledge_pipeline import (
    AmbiguousKnowledgeConceptError,
    KnowledgePipeline,
)
from codestrata.services.repository_graph import (
    RepositoryDependencyExtractor,
    RepositoryExtractionContext,
    RepositoryExtractionScope,
    RepositoryGraphAssembler,
    RepositoryGraphAssemblyError,
    RepositoryStructureExtractor,
)

KnowledgeGraphLoader = Callable[[], EngineeringKnowledgeGraph]

_PIPELINE_GENERATOR_VERSION = "1.0.0"


class GraphAssessmentPipeline:
    """Deterministic Phase 2 graph pipeline for one assessed repository."""

    def __init__(
        self,
        *,
        adapter: Phase1RepositoryAdapter | None = None,
        knowledge_loader: KnowledgeGraphLoader | None = None,
        knowledge_pipeline: KnowledgePipeline | None = None,
        assessment_builder: AssessmentGraphBuilder | None = None,
        structure_extractor: RepositoryStructureExtractor | None = None,
        dependency_extractor: RepositoryDependencyExtractor | None = None,
        graph_assembler: RepositoryGraphAssembler | None = None,
    ) -> None:
        self._adapter = adapter or Phase1RepositoryAdapter()
        self._knowledge_loader = knowledge_loader or load_builtin_engineering_knowledge_catalog
        self._knowledge_pipeline = knowledge_pipeline or KnowledgePipeline()
        self._assessment_builder = assessment_builder or AssessmentGraphBuilder()
        self._structure_extractor = structure_extractor or RepositoryStructureExtractor()
        self._dependency_extractor = dependency_extractor or RepositoryDependencyExtractor()
        self._graph_assembler = graph_assembler or RepositoryGraphAssembler()

    def run(self, repository: Repository) -> GraphAssessmentPipelineResult:
        """Build inventory, graphs, bindings, and Assessment Graph for ``repository``."""

        try:
            adapted = self._adapter.adapt(repository)
        except Exception as error:
            raise GraphAssessmentPipelineError(
                "inventory",
                f"Phase 1 repository adaptation failed: {error}",
            ) from error

        try:
            manifest = RepositoryInventoryBuilder(adapted.content_reader).build(
                identity=adapted.identity,
                revision=adapted.revision,
                relative_paths=adapted.relative_paths,
            )
        except Exception as error:
            raise GraphAssessmentPipelineError(
                "inventory",
                f"Repository Inventory construction failed: {error}",
            ) from error

        try:
            fingerprint = RepositoryFingerprintFactory.from_manifest(manifest)
            metadata = GraphMetadata(
                graph_id=GraphId(
                    f"graph:repo:{manifest.identity.repository_key}:{fingerprint.digest}"
                ),
                graph_type=GraphType.REPOSITORY,
                schema_version=REPOSITORY_GRAPH_SCHEMA_VERSION,
                generator_version=_PIPELINE_GENERATOR_VERSION,
                source_fingerprint=(f"{fingerprint.algorithm.value}:{fingerprint.digest}"),
                generation_mode=GraphGenerationMode.FULL,
                status=GraphStatus.VALID,
            )
            context = RepositoryExtractionContext(
                manifest=manifest,
                content_reader=adapted.content_reader,
                scope=RepositoryExtractionScope.FULL,
            )
            structure = self._structure_extractor.extract(context)
            dependencies = self._dependency_extractor.extract(context)
            repository_graph = self._graph_assembler.assemble(
                (structure, dependencies),
                metadata=metadata,
            )
        except RepositoryGraphAssemblyError as error:
            raise GraphAssessmentPipelineError(
                "repository_graph",
                f"Repository Graph construction failed: {error}",
            ) from error
        except Exception as error:
            raise GraphAssessmentPipelineError(
                "repository_graph",
                f"Repository Graph construction failed: {error}",
            ) from error

        try:
            knowledge_graph = self._knowledge_loader()
        except Exception as error:
            raise GraphAssessmentPipelineError(
                "engineering_knowledge",
                f"Engineering Knowledge Graph load failed: {error}",
            ) from error

        try:
            binding_result = self._knowledge_pipeline.bind(
                repository_graph,
                knowledge_graph,
            )
        except AmbiguousKnowledgeConceptError as error:
            raise GraphAssessmentPipelineError(
                "knowledge_pipeline",
                f"Ambiguous engineering knowledge catalog alias: {error}",
            ) from error
        except Exception as error:
            raise GraphAssessmentPipelineError(
                "knowledge_pipeline",
                f"Knowledge Pipeline failed: {error}",
            ) from error

        try:
            assessment_graph = self._assessment_builder.build(
                repository_graph=repository_graph,
                knowledge_graph=knowledge_graph,
                binding_result=binding_result,
            )
        except AssessmentGraphBuildError as error:
            raise GraphAssessmentPipelineError(
                "assessment_graph",
                f"Assessment Graph construction failed: {error}",
            ) from error
        except Exception as error:
            raise GraphAssessmentPipelineError(
                "assessment_graph",
                f"Assessment Graph construction failed: {error}",
            ) from error

        return GraphAssessmentPipelineResult(
            manifest=manifest,
            repository_graph=repository_graph,
            knowledge_graph=knowledge_graph,
            binding_result=binding_result,
            assessment_graph=assessment_graph,
        )
