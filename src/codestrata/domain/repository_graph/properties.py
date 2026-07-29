"""Typed Repository Graph node property models.

These models validate construction and serialize into ``GraphNode.properties``.
They intentionally do not replace ``GraphNode``; language-specific detail lives
in fields such as ``type_kind`` / ``callable_kind`` rather than node types.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.repository.enums import RepositoryFileKind
from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.repository_graph.enums import (
    DependencyScope,
    RepositoryCallableKind,
    RepositoryTypeKind,
)


class _RepositoryPropertyModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def to_properties(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible mapping for ``GraphNode.properties``."""

        return self.model_dump(mode="json")


class RepositoryProperties(_RepositoryPropertyModel):
    """Properties for a ``repository`` node."""

    name: str
    source_type: str | None = None
    branch: str | None = None
    revision: str | None = None
    source_location: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="name")

    @field_validator("source_type", "branch", "revision", "source_location", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional repository field")


class ModuleProperties(_RepositoryPropertyModel):
    """Properties for a ``module`` node."""

    name: str
    path: str | None = None
    build_system: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="name")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        if value is None:
            return None
        return normalize_repository_relative_path(str(value))

    @field_validator("build_system", mode="before")
    @classmethod
    def normalize_build_system(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="build_system")


class FileProperties(_RepositoryPropertyModel):
    """Properties for a ``file`` node."""

    path: str
    file_kind: RepositoryFileKind
    language: str | None = None
    content_hash: str | None = None
    hash_algorithm: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    generated: bool = False
    executable: bool = False
    media_type: str | None = None

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return normalize_repository_relative_path(str(value))

    @field_validator("language", "content_hash", "hash_algorithm", "media_type", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional file field")


class NamespaceProperties(_RepositoryPropertyModel):
    """Properties for a ``namespace`` node."""

    qualified_name: str
    language: str | None = None

    @field_validator("qualified_name", mode="before")
    @classmethod
    def normalize_qualified_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="qualified_name")

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="language")


class TypeProperties(_RepositoryPropertyModel):
    """Properties for a ``type`` node."""

    name: str
    qualified_name: str
    type_kind: RepositoryTypeKind
    language: str | None = None
    visibility: str | None = None
    abstract: bool = False
    final: bool = False

    @field_validator("name", "qualified_name", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="type field")

    @field_validator("language", "visibility", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional type field")


class CallableProperties(_RepositoryPropertyModel):
    """Properties for a ``callable`` node."""

    name: str
    qualified_signature: str
    callable_kind: RepositoryCallableKind
    language: str | None = None
    visibility: str | None = None
    abstract: bool = False
    static: bool = False

    @field_validator("name", "qualified_signature", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="callable field")

    @field_validator("language", "visibility", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional callable field")


class DependencyProperties(_RepositoryPropertyModel):
    """Properties for a ``dependency`` node.

    ``version`` is recorded as a property only; it is intentionally excluded
    from dependency ``NodeId`` construction so upgrades preserve identity.
    """

    ecosystem: str
    name: str
    namespace: str | None = None
    version: str | None = None
    scope: DependencyScope = DependencyScope.UNKNOWN
    direct: bool = True
    source_file: str | None = None

    @field_validator("ecosystem", "name", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="dependency field")

    @field_validator("namespace", "version", "source_file", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional dependency field")


PropertyModel = (
    RepositoryProperties
    | ModuleProperties
    | FileProperties
    | NamespaceProperties
    | TypeProperties
    | CallableProperties
    | DependencyProperties
)


def properties_mapping(model: PropertyModel) -> Mapping[str, Any]:
    """Convert a typed property model into a GraphNode properties mapping."""

    return model.to_properties()
