"""Manifest change detection and incremental graph planning projection.

Rename detection is intentionally deferred: a rename appears as one deletion and
one addition. ``RepositoryGraphChangeSet`` is the boundary for future incremental
Repository Graph extraction; it carries only paths and the current content
fingerprint, never graph nodes or relationships.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, model_validator

from codestrata.domain.repository.enums import RepositoryChangeType
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.fingerprints import (
    RepositoryFingerprint,
    RepositoryFingerprintFactory,
)
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.domain.repository.paths import RepositoryPath


class RepositoryManifestDiffError(ValueError):
    """Raised when two manifests cannot be compared."""


class RepositoryFileChange(BaseModel):
    """Per-path difference between two repository manifests."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: RepositoryPath
    change_type: RepositoryChangeType
    previous: RepositoryFileEntry | None = None
    current: RepositoryFileEntry | None = None

    @model_validator(mode="after")
    def validate_change_shape(self) -> RepositoryFileChange:
        change = self.change_type
        previous = self.previous
        current = self.current

        if change is RepositoryChangeType.ADDED:
            if previous is not None or current is None:
                raise ValueError("ADDED requires previous=None and current present")
            if current.path != self.path:
                raise ValueError("ADDED current path must match change path")
            return self

        if change is RepositoryChangeType.DELETED:
            if previous is None or current is not None:
                raise ValueError("DELETED requires previous present and current=None")
            if previous.path != self.path:
                raise ValueError("DELETED previous path must match change path")
            return self

        if previous is None or current is None:
            raise ValueError(f"{change} requires both previous and current entries")
        if previous.path != self.path or current.path != self.path:
            raise ValueError("change path must match both previous and current paths")

        if change is RepositoryChangeType.MODIFIED:
            if previous.content_equals(current):
                raise ValueError("MODIFIED requires a content fingerprint change")
            return self

        if change is RepositoryChangeType.METADATA_CHANGED:
            if not previous.content_equals(current):
                raise ValueError("METADATA_CHANGED requires unchanged content fingerprint")
            if previous.metadata_equals(current):
                raise ValueError("METADATA_CHANGED requires at least one metadata difference")
            return self

        if change is RepositoryChangeType.UNCHANGED:
            if not previous.semantically_equals(current):
                raise ValueError("UNCHANGED requires semantically equal entries")
            return self

        raise ValueError(f"unsupported change type: {change}")


class RepositoryManifestDiff(BaseModel):
    """Ordered set of file changes between two manifests of the same repository."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    previous_fingerprint: RepositoryFingerprint
    current_fingerprint: RepositoryFingerprint
    changes: tuple[RepositoryFileChange, ...] = ()

    @property
    def added(self) -> tuple[RepositoryFileChange, ...]:
        return tuple(c for c in self.changes if c.change_type is RepositoryChangeType.ADDED)

    @property
    def modified(self) -> tuple[RepositoryFileChange, ...]:
        return tuple(c for c in self.changes if c.change_type is RepositoryChangeType.MODIFIED)

    @property
    def deleted(self) -> tuple[RepositoryFileChange, ...]:
        return tuple(c for c in self.changes if c.change_type is RepositoryChangeType.DELETED)

    @property
    def metadata_changed(self) -> tuple[RepositoryFileChange, ...]:
        return tuple(
            c for c in self.changes if c.change_type is RepositoryChangeType.METADATA_CHANGED
        )

    @property
    def unchanged(self) -> tuple[RepositoryFileChange, ...]:
        return tuple(c for c in self.changes if c.change_type is RepositoryChangeType.UNCHANGED)

    @property
    def has_changes(self) -> bool:
        return any(c.change_type is not RepositoryChangeType.UNCHANGED for c in self.changes)


class RepositoryManifestDiffer:
    """Pure-domain comparison of two repository manifests."""

    @classmethod
    def diff(
        cls,
        previous: RepositoryManifest,
        current: RepositoryManifest,
        *,
        include_unchanged: bool = False,
    ) -> RepositoryManifestDiff:
        if previous.identity.repository_key != current.identity.repository_key:
            raise RepositoryManifestDiffError(
                "cannot diff manifests with different repository_key values"
            )
        if previous.manifest_version != current.manifest_version:
            raise RepositoryManifestDiffError(
                "cannot diff manifests with different manifest_version values"
            )

        previous_by_path = {entry.path.root: entry for entry in previous.files}
        current_by_path = {entry.path.root: entry for entry in current.files}
        all_paths = sorted(set(previous_by_path) | set(current_by_path))

        changes: list[RepositoryFileChange] = []
        for path in all_paths:
            before = previous_by_path.get(path)
            after = current_by_path.get(path)
            classified = cls._classify(
                path=RepositoryPath(path),
                previous=before,
                current=after,
            )
            if classified.change_type is RepositoryChangeType.UNCHANGED and not include_unchanged:
                continue
            changes.append(classified)

        return RepositoryManifestDiff(
            previous_fingerprint=RepositoryFingerprintFactory.from_manifest(previous),
            current_fingerprint=RepositoryFingerprintFactory.from_manifest(current),
            changes=tuple(changes),
        )

    @classmethod
    def _classify(
        cls,
        *,
        path: RepositoryPath,
        previous: RepositoryFileEntry | None,
        current: RepositoryFileEntry | None,
    ) -> RepositoryFileChange:
        if previous is None and current is not None:
            return RepositoryFileChange(
                path=path,
                change_type=RepositoryChangeType.ADDED,
                previous=None,
                current=current,
            )
        if previous is not None and current is None:
            return RepositoryFileChange(
                path=path,
                change_type=RepositoryChangeType.DELETED,
                previous=previous,
                current=None,
            )
        assert previous is not None and current is not None
        if previous.semantically_equals(current):
            return RepositoryFileChange(
                path=path,
                change_type=RepositoryChangeType.UNCHANGED,
                previous=previous,
                current=current,
            )
        if not previous.content_equals(current):
            return RepositoryFileChange(
                path=path,
                change_type=RepositoryChangeType.MODIFIED,
                previous=previous,
                current=current,
            )
        return RepositoryFileChange(
            path=path,
            change_type=RepositoryChangeType.METADATA_CHANGED,
            previous=previous,
            current=current,
        )


class RepositoryGraphChangeSet(BaseModel):
    """Path-oriented projection for future incremental Repository Graph extraction.

    Unchanged files are omitted. This model does not contain graph nodes or
    relationships; extractors will use these path sets to decide what to rebuild.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    added_paths: tuple[RepositoryPath, ...] = ()
    modified_paths: tuple[RepositoryPath, ...] = ()
    deleted_paths: tuple[RepositoryPath, ...] = ()
    metadata_changed_paths: tuple[RepositoryPath, ...] = ()
    repository_fingerprint: RepositoryFingerprint

    @classmethod
    def from_diff(cls, diff: RepositoryManifestDiff) -> RepositoryGraphChangeSet:
        return cls(
            added_paths=_unique_sorted_paths(change.path for change in diff.added),
            modified_paths=_unique_sorted_paths(change.path for change in diff.modified),
            deleted_paths=_unique_sorted_paths(change.path for change in diff.deleted),
            metadata_changed_paths=_unique_sorted_paths(
                change.path for change in diff.metadata_changed
            ),
            repository_fingerprint=diff.current_fingerprint,
        )


def _unique_sorted_paths(paths: Iterable[RepositoryPath]) -> tuple[RepositoryPath, ...]:
    unique = {path.root: path for path in paths}
    return tuple(unique[key] for key in sorted(unique))
