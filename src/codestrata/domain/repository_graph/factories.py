"""Factories for deterministic Repository Graph ``GraphNode`` construction."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.models import EvidenceReference, GraphNode, Provenance
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.ids import RepositoryNodeIdFactory
from codestrata.domain.repository_graph.properties import (
    CallableProperties,
    DependencyProperties,
    FileProperties,
    ModuleProperties,
    NamespaceProperties,
    PropertyModel,
    RepositoryProperties,
    TypeProperties,
    properties_mapping,
)

REPOSITORY_GRAPH_SCHEMA_VERSION = "1.0.0"


class RepositoryGraphNodeFactory:
    """Create validated ``GraphNode`` instances for Repository Graph node types.

    Callers supply typed property models; this factory assigns canonical
    ``node_type`` values and deterministic IDs. It does not read files, scan
    repositories, create relationships, or persist anything.
    """

    def __init__(
        self,
        repository_key: str,
        *,
        schema_version: str = REPOSITORY_GRAPH_SCHEMA_VERSION,
    ) -> None:
        self._ids = RepositoryNodeIdFactory(repository_key)
        self._schema_version = schema_version

    @property
    def repository_key(self) -> str:
        return self._ids.repository_key

    @property
    def schema_version(self) -> str:
        return self._schema_version

    @property
    def ids(self) -> RepositoryNodeIdFactory:
        return self._ids

    def repository(
        self,
        properties: RepositoryProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.repository(),
            node_type=RepositoryNodeType.REPOSITORY,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def module(
        self,
        *,
        module_key: str,
        properties: ModuleProperties,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.module(module_key),
            node_type=RepositoryNodeType.MODULE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def file(
        self,
        properties: FileProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.file(properties.path),
            node_type=RepositoryNodeType.FILE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def namespace(
        self,
        properties: NamespaceProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.namespace(properties.qualified_name),
            node_type=RepositoryNodeType.NAMESPACE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def type(
        self,
        properties: TypeProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.type(properties.qualified_name),
            node_type=RepositoryNodeType.TYPE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def callable(
        self,
        *,
        qualified_owner: str,
        signature: str,
        properties: CallableProperties,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.callable(
                qualified_owner=qualified_owner,
                signature=signature,
            ),
            node_type=RepositoryNodeType.CALLABLE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def dependency(
        self,
        properties: DependencyProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self._build(
            node_id=self._ids.dependency(
                ecosystem=properties.ecosystem,
                name=properties.name,
                namespace=properties.namespace,
            ),
            node_type=RepositoryNodeType.DEPENDENCY,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def _build(
        self,
        *,
        node_id: NodeId,
        node_type: RepositoryNodeType,
        properties: PropertyModel,
        provenance: Sequence[Provenance],
        evidence: Sequence[EvidenceReference],
    ) -> GraphNode:
        return GraphNode(
            id=node_id,
            node_type=node_type.value,
            schema_version=self._schema_version,
            properties=properties_mapping(properties),
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )
