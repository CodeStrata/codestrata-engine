"""Repository inventory enumerations.

This package describes the source repository itself (identity, files, fingerprints,
and change detection). It is distinct from Repository Graph semantics, which
model extracted structural knowledge about that repository.
"""

from __future__ import annotations

from enum import StrEnum


class RepositorySourceType(StrEnum):
    """How a repository was obtained for assessment."""

    LOCAL = "local"
    GIT = "git"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


class RepositoryRevisionType(StrEnum):
    """What a revision identifier represents."""

    COMMIT = "commit"
    WORKING_TREE = "working_tree"
    ARCHIVE = "archive"
    SNAPSHOT = "snapshot"
    UNKNOWN = "unknown"


class HashAlgorithm(StrEnum):
    """Supported content-hash algorithms for repository inventory."""

    SHA256 = "sha256"
    SHA512 = "sha512"


class RepositoryChangeType(StrEnum):
    """Classification of a per-file difference between two manifests."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    METADATA_CHANGED = "metadata_changed"
    UNCHANGED = "unchanged"


class RepositoryFileKind(StrEnum):
    """Coarse classification for inventoried repository files.

    Owned by the repository inventory domain. Repository Graph re-exports this
    enum for compatibility; language-specific type/callable kinds remain in
    ``codestrata.domain.repository_graph``.
    """

    SOURCE = "source"
    TEST = "test"
    CONFIGURATION = "configuration"
    BUILD = "build"
    DEPENDENCY_MANIFEST = "dependency_manifest"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"
    GENERATED = "generated"
    UNKNOWN = "unknown"
