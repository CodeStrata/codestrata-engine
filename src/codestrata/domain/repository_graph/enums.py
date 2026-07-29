"""Language-neutral Repository Graph vocabulary and classifications.

Canonical node types (`RepositoryNodeType`) are storage- and language-neutral.
Language-specific distinctions (for example Java class vs interface) belong in
typed property fields such as ``type_kind``, not in separate node types.

``RepositoryFileKind`` is owned by ``codestrata.domain.repository`` and re-exported
here for Repository Graph compatibility.
"""

from __future__ import annotations

from enum import StrEnum

from codestrata.domain.repository.enums import RepositoryFileKind

__all__ = [
    "DependencyScope",
    "RepositoryCallableKind",
    "RepositoryFileKind",
    "RepositoryNodeType",
    "RepositoryRelationshipType",
    "RepositoryTypeKind",
]


class RepositoryNodeType(StrEnum):
    """Canonical Repository Graph node kinds."""

    REPOSITORY = "repository"
    MODULE = "module"
    FILE = "file"
    NAMESPACE = "namespace"
    TYPE = "type"
    CALLABLE = "callable"
    DEPENDENCY = "dependency"


class RepositoryRelationshipType(StrEnum):
    """Canonical Repository Graph relationship kinds."""

    CONTAINS = "contains"
    DECLARES = "declares"
    DEPENDS_ON = "depends_on"
    CALLS = "calls"


class RepositoryTypeKind(StrEnum):
    """Language-neutral classification for type declarations."""

    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    RECORD = "record"
    ANNOTATION = "annotation"
    TRAIT = "trait"
    STRUCT = "struct"
    OBJECT = "object"
    UNKNOWN = "unknown"


class RepositoryCallableKind(StrEnum):
    """Language-neutral classification for callable declarations."""

    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    INITIALIZER = "initializer"
    LAMBDA = "lambda"
    UNKNOWN = "unknown"


class DependencyScope(StrEnum):
    """How a dependency participates in build or runtime resolution."""

    COMPILE = "compile"
    RUNTIME = "runtime"
    TEST = "test"
    DEVELOPMENT = "development"
    PROVIDED = "provided"
    OPTIONAL = "optional"
    UNKNOWN = "unknown"
