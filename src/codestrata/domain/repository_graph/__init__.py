"""Language-neutral Repository Graph domain schema and identity helpers."""

from codestrata.domain.repository_graph.dependencies import Dependency, DependencyVersion
from codestrata.domain.repository_graph.enums import (
    DependencyScope,
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
)

__all__ = [
    "REPOSITORY_GRAPH_SCHEMA_VERSION",
    "CallableProperties",
    "Dependency",
    "DependencyProperties",
    "DependencyScope",
    "DependencyVersion",
    "FileProperties",
    "ModuleProperties",
    "NamespaceProperties",
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
    "TypeProperties",
    "normalize_repository_key",
    "normalize_repository_relative_path",
]
