"""Content-reading abstractions for inventory fingerprinting.

The inventory builder depends on ``RepositoryContentReader`` rather than the
filesystem directly so local, GitHub-checkout, and archive workflows share one
pipeline.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from codestrata.domain.repository.paths import RepositoryPath, normalize_repository_relative_path


@dataclass(frozen=True, slots=True)
class FileContent:
    """Bytes and lightweight filesystem metadata for one repository file."""

    data: bytes
    executable: bool = False

    @property
    def size_bytes(self) -> int:
        return len(self.data)


class RepositoryContentReader(Protocol):
    """Read discovered repository files by repository-relative path."""

    def read(self, relative_path: str) -> FileContent:
        """Return file bytes for a normalized repository-relative path."""


class LocalFilesystemContentReader:
    """Read file bytes from a local repository root directory."""

    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root.expanduser().resolve()
        if not self._root.is_dir():
            raise NotADirectoryError(f"repository root is not a directory: {self._root}")

    @property
    def repository_root(self) -> Path:
        return self._root

    def read(self, relative_path: str) -> FileContent:
        normalized = normalize_repository_relative_path(relative_path)
        joined = self._root / normalized
        if joined.is_symlink():
            raise ValueError(f"refusing to read symlink path: {normalized}")
        candidate = joined.resolve(strict=False)
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"path escapes repository root: {RepositoryPath(normalized)}") from exc
        if not candidate.is_file() or candidate.is_symlink():
            raise FileNotFoundError(f"repository file not found: {normalized}")

        data = candidate.read_bytes()
        mode = candidate.stat().st_mode
        executable = bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        return FileContent(data=data, executable=executable)
