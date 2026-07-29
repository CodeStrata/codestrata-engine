"""Language-neutral Repository Graph structure extractor.

This extractor turns inventory facts into repository, module, and file nodes
plus CONTAINS relationships. It does not parse source code: nested build
manifests define modules, directories are not nodes, and deepest-module
ownership avoids duplicate file containment.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.graph.enums import ProvenanceSource
from codestrata.domain.graph.models import (
    EvidenceReference,
    GraphNode,
    GraphRelationship,
    Provenance,
)
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.paths import RepositoryPath
from codestrata.domain.repository_graph.enums import RepositoryRelationshipType
from codestrata.domain.repository_graph.factories import RepositoryGraphNodeFactory
from codestrata.domain.repository_graph.properties import (
    FileProperties,
    ModuleProperties,
    RepositoryProperties,
)
from codestrata.domain.repository_graph.relationship_factory import RepositoryRelationshipFactory
from codestrata.services.repository_graph.context import RepositoryExtractionContext
from codestrata.services.repository_graph.enums import RepositoryExtractionScope
from codestrata.services.repository_graph.extractors.modules import (
    EXTRACTOR_ID,
    ModuleResolution,
    PathBasedModuleResolver,
    RepositoryModuleResolver,
    ResolvedModule,
    direct_child_modules,
    top_level_modules,
)
from codestrata.services.repository_graph.results import (
    RepositoryExtractionResult,
    RepositoryExtractionStatistics,
)

_EXTRACTOR_VERSION = "1.0.0"


class RepositoryStructureExtractor:
    """Extract repository / module / file structure from a ``RepositoryManifest``.

    Structural extraction is language-neutral: it consumes inventory entries and
    path-based module markers only. It never constructs ``RepositoryGraph``.
    """

    def __init__(
        self,
        *,
        module_resolver: RepositoryModuleResolver | None = None,
        extractor_version: str = _EXTRACTOR_VERSION,
    ) -> None:
        self._module_resolver = module_resolver or PathBasedModuleResolver()
        self._extractor_version = extractor_version

    @property
    def extractor_id(self) -> str:
        return EXTRACTOR_ID

    def extract(self, context: RepositoryExtractionContext) -> RepositoryExtractionResult:
        manifest = context.manifest
        identity = manifest.identity
        resolution = self._module_resolver.resolve(manifest)

        node_factory = RepositoryGraphNodeFactory(identity.repository_key)
        relationship_factory = RepositoryRelationshipFactory()
        provenance = self._provenance()

        files_by_path = {entry.path.root: entry for entry in manifest.files}
        emit_file_paths = self._select_file_paths(context, files_by_path)
        deleted_paths = self._deleted_paths(context)

        modules_to_emit = self._modules_to_emit(
            context=context,
            resolution=resolution,
            emit_file_paths=emit_file_paths,
        )
        modules_by_path = {module.path.root: module for module in modules_to_emit}

        repository_node = node_factory.repository(
            RepositoryProperties(
                name=identity.display_name,
                source_type=identity.source_type.value,
                branch=manifest.revision.branch,
                revision=manifest.revision.revision_id,
                source_location=identity.source_location,
            ),
            provenance=(provenance,),
        )

        module_nodes = [
            self._module_node(node_factory, module, provenance)
            for module in sorted(modules_to_emit, key=lambda item: item.path.root)
        ]
        file_nodes = [
            self._file_node(node_factory, files_by_path[path], provenance)
            for path in sorted(emit_file_paths)
        ]

        relationships = self._build_relationships(
            relationship_factory=relationship_factory,
            provenance=provenance,
            repository_node=repository_node,
            module_nodes_by_path={
                module.path.root: node
                for module, node in zip(
                    sorted(modules_to_emit, key=lambda item: item.path.root),
                    module_nodes,
                    strict=True,
                )
            },
            file_nodes_by_path={
                path: node for path, node in zip(sorted(emit_file_paths), file_nodes, strict=True)
            },
            resolution=resolution,
            modules_by_path=modules_by_path,
            emit_file_paths=emit_file_paths,
        )

        nodes = (repository_node, *module_nodes, *file_nodes)
        diagnostics = tuple(
            sorted(
                resolution.diagnostics,
                key=lambda item: (item.code, item.path or "", item.message),
            )
        )
        return RepositoryExtractionResult(
            extractor_id=self.extractor_id,
            nodes=nodes,
            relationships=relationships,
            diagnostics=diagnostics,
            statistics=RepositoryExtractionStatistics(
                extractor_id=self.extractor_id,
                node_count=len(nodes),
                relationship_count=len(relationships),
                diagnostic_count=len(diagnostics),
                duration_ms=None,
            ),
            provenance=(provenance,),
            deleted_repository_paths=deleted_paths,
        )

    def _select_file_paths(
        self,
        context: RepositoryExtractionContext,
        files_by_path: dict[str, RepositoryFileEntry],
    ) -> set[str]:
        if context.scope is RepositoryExtractionScope.FULL:
            return set(files_by_path)

        assert context.change_set is not None
        selected: set[str] = set()
        for path in (
            *context.change_set.added_paths,
            *context.change_set.modified_paths,
            *context.change_set.metadata_changed_paths,
        ):
            if path.root in files_by_path:
                selected.add(path.root)
        return selected

    def _deleted_paths(
        self,
        context: RepositoryExtractionContext,
    ) -> tuple[RepositoryPath, ...]:
        if context.scope is RepositoryExtractionScope.FULL or context.change_set is None:
            return ()
        return tuple(sorted(context.change_set.deleted_paths, key=lambda path: path.root))

    def _modules_to_emit(
        self,
        *,
        context: RepositoryExtractionContext,
        resolution: ModuleResolution,
        emit_file_paths: set[str],
    ) -> tuple[ResolvedModule, ...]:
        if context.scope is RepositoryExtractionScope.FULL:
            return resolution.modules

        needed: set[str] = set()
        for path in emit_file_paths:
            owner = resolution.file_module_paths.get(path)
            if owner is not None:
                needed.add(owner)
                needed.update(_ancestor_module_paths(owner, resolution.modules))
        return tuple(module for module in resolution.modules if module.path.root in needed)

    def _module_node(
        self,
        node_factory: RepositoryGraphNodeFactory,
        module: ResolvedModule,
        provenance: Provenance,
    ) -> GraphNode:
        return node_factory.module(
            module_key=module.path.root,
            properties=ModuleProperties(
                name=module.name,
                path=module.path.root,
                build_system=module.build_system,
            ),
            provenance=(provenance,),
            evidence=(
                EvidenceReference(
                    evidence_type="module_marker",
                    source_id=f"file:{module.marker_path.root}",
                    path=module.marker_path.root,
                ),
            ),
        )

    def _file_node(
        self,
        node_factory: RepositoryGraphNodeFactory,
        entry: RepositoryFileEntry,
        provenance: Provenance,
    ) -> GraphNode:
        return node_factory.file(
            FileProperties(
                path=entry.path.root,
                file_kind=entry.file_kind,
                language=entry.language,
                content_hash=entry.fingerprint.digest,
                hash_algorithm=entry.fingerprint.algorithm.value,
                size_bytes=entry.size_bytes,
                generated=entry.generated,
                executable=entry.executable,
                media_type=entry.media_type,
            ),
            provenance=(provenance,),
            evidence=(
                EvidenceReference(
                    evidence_type="repository_file",
                    source_id=f"file:{entry.path.root}",
                    path=entry.path.root,
                ),
            ),
        )

    def _build_relationships(
        self,
        *,
        relationship_factory: RepositoryRelationshipFactory,
        provenance: Provenance,
        repository_node: GraphNode,
        module_nodes_by_path: dict[str, GraphNode],
        file_nodes_by_path: dict[str, GraphNode],
        resolution: ModuleResolution,
        modules_by_path: dict[str, ResolvedModule],
        emit_file_paths: set[str],
    ) -> tuple[GraphRelationship, ...]:
        relationships: list[GraphRelationship] = []
        emitted_modules = tuple(modules_by_path[path] for path in sorted(modules_by_path))
        children = direct_child_modules(emitted_modules)

        for module in top_level_modules(emitted_modules):
            relationships.append(
                relationship_factory.create(
                    relationship_type=RepositoryRelationshipType.CONTAINS,
                    source_node_id=repository_node.id,
                    target_node_id=module_nodes_by_path[module.path.root].id,
                    provenance=(provenance,),
                    evidence=(
                        EvidenceReference(
                            evidence_type="module_marker",
                            source_id=f"file:{module.marker_path.root}",
                            path=module.marker_path.root,
                        ),
                    ),
                )
            )

        for parent_path, child_paths in children.items():
            if parent_path not in module_nodes_by_path:
                continue
            parent_node = module_nodes_by_path[parent_path]
            parent_module = modules_by_path[parent_path]
            for child_path in child_paths:
                if child_path not in module_nodes_by_path:
                    continue
                relationships.append(
                    relationship_factory.create(
                        relationship_type=RepositoryRelationshipType.CONTAINS,
                        source_node_id=parent_node.id,
                        target_node_id=module_nodes_by_path[child_path].id,
                        provenance=(provenance,),
                        evidence=(
                            EvidenceReference(
                                evidence_type="module_marker",
                                source_id=f"file:{parent_module.marker_path.root}",
                                path=parent_module.marker_path.root,
                            ),
                        ),
                    )
                )

        for path in sorted(emit_file_paths):
            file_node = file_nodes_by_path[path]
            owner = resolution.file_module_paths.get(path)
            evidence = (
                EvidenceReference(
                    evidence_type="repository_file",
                    source_id=f"file:{path}",
                    path=path,
                ),
            )
            if owner is None:
                relationships.append(
                    relationship_factory.create(
                        relationship_type=RepositoryRelationshipType.CONTAINS,
                        source_node_id=repository_node.id,
                        target_node_id=file_node.id,
                        provenance=(provenance,),
                        evidence=evidence,
                    )
                )
            elif owner in module_nodes_by_path:
                relationships.append(
                    relationship_factory.create(
                        relationship_type=RepositoryRelationshipType.CONTAINS,
                        source_node_id=module_nodes_by_path[owner].id,
                        target_node_id=file_node.id,
                        provenance=(provenance,),
                        evidence=evidence,
                    )
                )

        # Deterministic unique relationships by ID.
        unique = {item.id: item for item in relationships}
        return tuple(unique[key] for key in sorted(unique))

    def _provenance(self) -> Provenance:
        return Provenance(
            source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
            source_id="inventory:repository-structure",
            extractor_id=self.extractor_id,
            extractor_version=self._extractor_version,
        )


def _ancestor_module_paths(
    module_path: str,
    modules: Sequence[ResolvedModule],
) -> set[str]:
    roots = [module.path.root for module in modules]
    return {root for root in roots if module_path != root and module_path.startswith(f"{root}/")}
