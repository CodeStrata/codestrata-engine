"""Deterministic content hashing for repository inventory entries."""

from __future__ import annotations

from codestrata.domain.repository.enums import HashAlgorithm
from codestrata.domain.repository.fingerprints import FileFingerprint, hash_bytes


class ContentHashingService:
    """Hash supplied bytes into ``FileFingerprint`` values (no filesystem I/O)."""

    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> None:
        self._algorithm = algorithm

    @property
    def algorithm(self) -> HashAlgorithm:
        return self._algorithm

    def fingerprint(self, data: bytes) -> FileFingerprint:
        return hash_bytes(data, algorithm=self._algorithm)
