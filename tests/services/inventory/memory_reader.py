"""Shared in-memory content reader for inventory tests."""

from __future__ import annotations

from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.services.inventory.content_reader import FileContent


class InMemoryContentReader:
    """Map repository-relative paths to in-memory file bytes."""

    def __init__(self, files: dict[str, bytes | FileContent]) -> None:
        self._files: dict[str, FileContent] = {}
        for path, payload in files.items():
            key = normalize_repository_relative_path(path)
            if isinstance(payload, FileContent):
                self._files[key] = payload
            else:
                self._files[key] = FileContent(data=payload)

    def read(self, relative_path: str) -> FileContent:
        key = normalize_repository_relative_path(relative_path)
        try:
            return self._files[key]
        except KeyError as exc:
            raise FileNotFoundError(f"repository file not found: {key}") from exc
