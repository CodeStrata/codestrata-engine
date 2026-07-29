"""Phase 1 Repository → Phase 2 inventory adaptation.

Phase 1 ``Repository`` remains the scanner/analysis DTO (absolute path, relative
file list, display metadata). Phase 2 ``RepositoryManifest`` is the inventory
contract (repository-relative paths, fingerprints, no absolute machine paths).

This adapter converts one into the other without re-discovering files and without
embedding absolute paths into deterministic inventory identity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from codestrata.domain.repository import (
    RepositoryIdentity,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
    normalize_repository_key,
)
from codestrata.models import Repository
from codestrata.services.inventory import LocalFilesystemContentReader, RepositoryContentReader

_UNSAFE_KEY_CHARS = re.compile(r"[^a-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class Phase1InventoryAdaptation:
    """Inputs required to build a Phase 2 ``RepositoryManifest`` from Phase 1."""

    identity: RepositoryIdentity
    revision: RepositoryRevision
    relative_paths: tuple[str, ...]
    content_reader: RepositoryContentReader
    repository_root: Path


class Phase1RepositoryAdapter:
    """Narrow bridge from Phase 1 ``Repository`` to inventory builder inputs."""

    def adapt(self, repository: Repository) -> Phase1InventoryAdaptation:
        """Adapt a scanned Phase 1 repository into Phase 2 inventory inputs.

        Reuses ``repository.files`` (already repository-relative) and opens a
        content reader on ``repository.path`` so file bytes are not re-listed.
        Absolute paths are used only for reading; they are not placed into
        ``RepositoryIdentity.source_location``.
        """

        root = Path(repository.path).expanduser()
        if not root.is_dir():
            raise ValueError(f"repository path is not a directory: {root}")

        relative_paths = tuple(
            sorted({path.strip().replace("\\", "/") for path in repository.files if path.strip()})
        )
        identity = RepositoryIdentity(
            repository_key=self.repository_key_for(repository),
            source_type=self._source_type(repository),
            display_name=repository.name.strip() or "repository",
            source_location=self._source_location(repository),
        )
        revision = RepositoryRevision(
            revision_id="working-tree",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            branch=repository.default_branch,
        )
        return Phase1InventoryAdaptation(
            identity=identity,
            revision=revision,
            relative_paths=relative_paths,
            content_reader=LocalFilesystemContentReader(root),
            repository_root=root.resolve(),
        )

    @staticmethod
    def repository_key_for(repository: Repository) -> str:
        """Derive a deterministic repository_key from Phase 1 display name."""

        compact = repository.name.strip().lower()
        slug = _UNSAFE_KEY_CHARS.sub("-", compact).strip(".-") or "repository"
        return normalize_repository_key(slug)

    @staticmethod
    def _source_type(repository: Repository) -> RepositorySourceType:
        url = (repository.source_url or "").strip().lower()
        if "github.com" in url:
            return RepositorySourceType.GITHUB
        if url.startswith("git@") or url.endswith(".git") or "://" in url:
            return RepositorySourceType.GIT
        return RepositorySourceType.LOCAL

    @staticmethod
    def _source_location(repository: Repository) -> str | None:
        """Prefer remote URL; never emit absolute local filesystem paths."""

        url = (repository.source_url or "").strip()
        return url or None
