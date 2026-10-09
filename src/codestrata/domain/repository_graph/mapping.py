"""Stable file-to-component mapping for inventory and later change facts.

E09.3 consumes these identities; this module only derives comparison-ready
repository-local IDs. It does not walk a filesystem or execute source.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.repository_graph.ids import RepositoryNodeIdFactory

ROOT_COMPONENT_KEY = "_repository"

_JAVA_SOURCE_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("src", "main", "java"),
    ("src", "test", "java"),
    ("src", "main", "kotlin"),
)


class FileComponentMapping(BaseModel):
    """One file subject joined to its containing component/module subject."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str
    component_key: str
    file_id: str
    component_id: str

    @field_validator("relative_path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return normalize_repository_relative_path(str(value))

    @field_validator("component_key", mode="before")
    @classmethod
    def normalize_component_key(cls, value: object) -> str:
        text = str(value).replace("\\", "/").strip()
        if text in {"", ".", ROOT_COMPONENT_KEY}:
            return ROOT_COMPONENT_KEY
        return normalize_repository_relative_path(text)


def parent_directory_key(relative_path: str) -> str:
    """Return the component key for the parent of a repository-relative file."""

    path = normalize_repository_relative_path(relative_path)
    parent = str(PurePosixPath(path).parent)
    if parent in {"", "."}:
        return ROOT_COMPONENT_KEY
    return parent


def component_key_for_file(
    relative_path: str,
    *,
    manifest_directories: Sequence[str] = (),
) -> str:
    """Derive a stable component key for a file.

    Preference order: Java/Kotlin source package directory, longest containing
    manifest directory, then the file's parent directory.
    """

    path = normalize_repository_relative_path(relative_path)
    parts = PurePosixPath(path).parts
    for prefix in _JAVA_SOURCE_PREFIXES:
        if len(parts) > len(prefix) and parts[: len(prefix)] == prefix:
            return parent_directory_key(path)

    best: str | None = None
    for raw in manifest_directories:
        directory = raw.replace("\\", "/").strip().strip("/")
        if not directory or directory == ".":
            directory = ROOT_COMPONENT_KEY
        if directory == ROOT_COMPONENT_KEY:
            candidate_ok = True
        else:
            candidate_ok = path == directory or path.startswith(f"{directory}/")
        if not candidate_ok:
            continue
        if best is None:
            best = directory
            continue
        best_len = 0 if best == ROOT_COMPONENT_KEY else len(best)
        new_len = 0 if directory == ROOT_COMPONENT_KEY else len(directory)
        if new_len > best_len:
            best = directory
    if best is not None:
        return best
    return parent_directory_key(path)


def map_files_to_components(
    relative_paths: Sequence[str],
    *,
    repository_key: str,
    manifest_directories: Sequence[str] = (),
) -> tuple[FileComponentMapping, ...]:
    """Emit deterministic file/component mappings for inventory facts."""

    ids = RepositoryNodeIdFactory(repository_key)
    mappings: list[FileComponentMapping] = []
    for raw in relative_paths:
        text = raw.replace("\\", "/").strip()
        if not text or text.endswith("/"):
            continue
        try:
            path = normalize_repository_relative_path(text)
        except ValueError:
            continue
        component_key = component_key_for_file(path, manifest_directories=manifest_directories)
        module_key = component_key if component_key != ROOT_COMPONENT_KEY else ROOT_COMPONENT_KEY
        mappings.append(
            FileComponentMapping(
                relative_path=path,
                component_key=component_key,
                file_id=str(ids.file(path)),
                component_id=str(ids.module(module_key)),
            )
        )
    return tuple(sorted(mappings, key=lambda item: item.relative_path))
