"""Repository file inventory entries.

``RepositoryFileEntry`` captures deterministic per-file inventory facts used for
fingerprinting and change detection. Absolute filesystem paths and raw file
bytes are intentionally excluded.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import optional_nonblank
from codestrata.domain.repository.enums import RepositoryFileKind
from codestrata.domain.repository.fingerprints import FileFingerprint
from codestrata.domain.repository.paths import RepositoryPath


class RepositoryFileEntry(BaseModel):
    """One inventoried file with its content fingerprint and extraction metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: RepositoryPath
    file_kind: RepositoryFileKind
    size_bytes: int = Field(ge=0)
    fingerprint: FileFingerprint
    executable: bool = False
    generated: bool = False
    language: str | None = None
    media_type: str | None = None

    @field_validator("language", "media_type", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional file field")

    def content_equals(self, other: RepositoryFileEntry) -> bool:
        """Return True when content fingerprints match."""

        return self.fingerprint == other.fingerprint

    def metadata_equals(self, other: RepositoryFileEntry) -> bool:
        """Return True when extraction-relevant metadata matches."""

        return (
            self.file_kind == other.file_kind
            and self.size_bytes == other.size_bytes
            and self.executable == other.executable
            and self.generated == other.generated
            and self.language == other.language
            and self.media_type == other.media_type
        )

    def semantically_equals(self, other: RepositoryFileEntry) -> bool:
        """Return True when path, content, and metadata are equivalent."""

        return (
            self.path == other.path and self.content_equals(other) and self.metadata_equals(other)
        )
