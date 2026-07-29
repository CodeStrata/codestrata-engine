"""Repository manifest contracts.

A manifest is a scanner-independent inventory snapshot: identity, revision, and
a deterministically ordered set of file entries. Discovery order must not affect
equality or content fingerprints.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from codestrata.domain.graph.validation import normalize_properties, require_nonblank
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.identities import RepositoryIdentity, RepositoryRevision

REPOSITORY_MANIFEST_VERSION = "1.0"


def _empty_metadata() -> Mapping[str, Any]:
    return MappingProxyType({})


class RepositoryManifest(BaseModel):
    """Immutable, ordered repository inventory suitable for incremental extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: RepositoryIdentity
    revision: RepositoryRevision
    files: tuple[RepositoryFileEntry, ...] = ()
    manifest_version: str = REPOSITORY_MANIFEST_VERSION
    metadata: Mapping[str, Any] = Field(default_factory=_empty_metadata)

    @field_validator("manifest_version", mode="before")
    @classmethod
    def normalize_manifest_version(cls, value: object) -> str:
        return require_nonblank(str(value), label="manifest_version")

    @field_validator("files", mode="before")
    @classmethod
    def coerce_files(cls, value: object) -> tuple[Any, ...]:
        if value is None:
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise ValueError("files must be a list or tuple")

    @field_validator("files", mode="after")
    @classmethod
    def sort_unique_files(
        cls, value: tuple[RepositoryFileEntry, ...]
    ) -> tuple[RepositoryFileEntry, ...]:
        paths = [entry.path.root for entry in value]
        if len(paths) != len(set(paths)):
            raise ValueError("manifest file paths must be unique")
        return tuple(sorted(value, key=lambda entry: entry.path.root))

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> Mapping[str, Any]:
        if value is None:
            return _empty_metadata()
        return normalize_properties(value, label="metadata")

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(value, MappingProxyType):
            return value
        return MappingProxyType(dict(value))

    @field_serializer("metadata")
    def serialize_metadata(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)
