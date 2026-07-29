"""Repository inventory builder pipeline.

Converts scanner-discovered relative paths into a validated
``RepositoryManifest``. Stages are deterministic and scanner-agnostic: the
builder never depends on how files were discovered (local, GitHub, archive).
"""

from __future__ import annotations

from codestrata.services.inventory.builder import RepositoryInventoryBuilder
from codestrata.services.inventory.classification import RepositoryFileKindClassifier
from codestrata.services.inventory.content_reader import (
    FileContent,
    LocalFilesystemContentReader,
    RepositoryContentReader,
)
from codestrata.services.inventory.hashing import ContentHashingService
from codestrata.services.inventory.language import FilenameLanguageDetector

__all__ = [
    "ContentHashingService",
    "FileContent",
    "FilenameLanguageDetector",
    "LocalFilesystemContentReader",
    "RepositoryContentReader",
    "RepositoryFileKindClassifier",
    "RepositoryInventoryBuilder",
]
