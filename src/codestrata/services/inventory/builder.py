"""Build validated ``RepositoryManifest`` values from discovered file paths.

Pipeline:

1. normalize identity (caller-supplied ``RepositoryIdentity``)
2. normalize repository-relative paths
3. classify file kind
4. detect language
5. fingerprint file bytes
6. build ``RepositoryFileEntry``
7. canonical ordering via ``RepositoryManifest`` construction
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.domain.repository.enums import HashAlgorithm, RepositoryFileKind
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.identities import RepositoryIdentity, RepositoryRevision
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.domain.repository.paths import RepositoryPath
from codestrata.services.inventory.classification import RepositoryFileKindClassifier
from codestrata.services.inventory.content_reader import RepositoryContentReader
from codestrata.services.inventory.hashing import ContentHashingService
from codestrata.services.inventory.language import FilenameLanguageDetector


class RepositoryInventoryBuilder:
    """Deterministic scanner-agnostic repository inventory builder."""

    def __init__(
        self,
        content_reader: RepositoryContentReader,
        *,
        classifier: RepositoryFileKindClassifier | None = None,
        language_detector: FilenameLanguageDetector | None = None,
        hasher: ContentHashingService | None = None,
    ) -> None:
        self._reader = content_reader
        self._classifier = classifier or RepositoryFileKindClassifier()
        self._languages = language_detector or FilenameLanguageDetector()
        self._hasher = hasher or ContentHashingService(HashAlgorithm.SHA256)

    def build(
        self,
        *,
        identity: RepositoryIdentity,
        revision: RepositoryRevision,
        relative_paths: Sequence[str],
        metadata: Mapping[str, Any] | None = None,
    ) -> RepositoryManifest:
        """Build a canonical ``RepositoryManifest`` for discovered paths."""

        entries = [self._build_entry(path) for path in relative_paths]
        return RepositoryManifest(
            identity=identity,
            revision=revision,
            files=tuple(entries),
            metadata=dict(metadata or {}),
        )

    def _build_entry(self, relative_path: str) -> RepositoryFileEntry:
        path = RepositoryPath(relative_path)
        content = self._reader.read(path.root)
        kind = self._classifier.classify(path.root)
        return RepositoryFileEntry(
            path=path,
            file_kind=kind,
            size_bytes=content.size_bytes,
            fingerprint=self._hasher.fingerprint(content.data),
            executable=content.executable,
            generated=kind is RepositoryFileKind.GENERATED,
            language=self._languages.detect(path.root),
            media_type=self._classifier.media_type(path.root),
        )
