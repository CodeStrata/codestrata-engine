"""Language-neutral Repository Graph domain schema and identity helpers."""

from codestrata.domain.repository_graph.dependencies import Dependency, DependencyVersion
from codestrata.domain.repository_graph.enums import (
    OBSERVED_STRUCTURAL_EDGE_TYPES,
    DependencyScope,
    InventoryPrimaryClass,
    RepositoryCallableKind,
    RepositoryFileKind,
    RepositoryNodeType,
    RepositoryRelationshipType,
    RepositoryTypeKind,
)
from codestrata.domain.repository_graph.factories import (
    REPOSITORY_GRAPH_SCHEMA_VERSION,
    RepositoryGraphNodeFactory,
)
from codestrata.domain.repository_graph.ids import (
    RepositoryNodeIdFactory,
    normalize_repository_key,
    normalize_repository_relative_path,
)
from codestrata.domain.repository_graph.mapping import (
    ROOT_COMPONENT_KEY,
    FileComponentMapping,
    map_files_to_components,
)
from codestrata.domain.repository_graph.models import RepositoryGraph
from codestrata.domain.repository_graph.properties import (
    CallableProperties,
    DependencyProperties,
    FileProperties,
    ModuleProperties,
    NamespaceProperties,
    RepositoryProperties,
    TypeProperties,
)
from codestrata.domain.repository_graph.relationship_factory import RepositoryRelationshipFactory
from codestrata.domain.repository_graph.relationship_ids import RelationshipIdFactory
from codestrata.domain.repository_graph.schema import (
    RepositoryGraphSchema,
    RepositoryGraphSchemaError,
    allowed_relationship_endpoints,
)
from codestrata.domain.repository_graph.structural import (
    FAN_OUT_THRESHOLD_DEFAULT,
    AdmittedStructuralEdge,
    StructuralConfidence,
    StructuralDepth,
    StructuralDropReason,
    StructuralEdgeObservation,
    StructuralView,
    admit_structural_edge,
)

__all__ = [
    "FAN_OUT_THRESHOLD_DEFAULT",
    "OBSERVED_STRUCTURAL_EDGE_TYPES",
    "REPOSITORY_GRAPH_SCHEMA_VERSION",
    "AdmittedStructuralEdge",
    "CallableProperties",
    "Dependency",
    "DependencyProperties",
    "DependencyScope",
    "DependencyVersion",
    "FileComponentMapping",
    "FileProperties",
    "InventoryPrimaryClass",
    "ModuleProperties",
    "NamespaceProperties",
    "ROOT_COMPONENT_KEY",
    "RelationshipIdFactory",
    "RepositoryCallableKind",
    "RepositoryFileKind",
    "RepositoryGraph",
    "RepositoryGraphNodeFactory",
    "RepositoryGraphSchema",
    "RepositoryGraphSchemaError",
    "RepositoryNodeIdFactory",
    "RepositoryNodeType",
    "RepositoryProperties",
    "RepositoryRelationshipFactory",
    "RepositoryRelationshipType",
    "RepositoryTypeKind",
    "StructuralConfidence",
    "StructuralDepth",
    "StructuralDropReason",
    "StructuralEdgeObservation",
    "StructuralView",
    "TypeProperties",
    "admit_structural_edge",
    "allowed_relationship_endpoints",
    "map_files_to_components",
    "normalize_repository_key",
    "normalize_repository_relative_path",
]
