"""Content fingerprint value objects and repository fingerprint construction.

Repository content fingerprints hash only inventory semantics that affect future
extraction (paths, kinds, sizes, file digests, flags, language, media type).
Source location, branch, capture time, display name, and arbitrary manifest
metadata are excluded so content identity stays stable across clone URL or
branch renames.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.repository.enums import HashAlgorithm

if TYPE_CHECKING:
    from codestrata.domain.repository.manifests import RepositoryManifest

_HEX = re.compile(r"^[0-9a-f]+$")

_DIGEST_LENGTHS: dict[HashAlgorithm, int] = {
    HashAlgorithm.SHA256: 64,
    HashAlgorithm.SHA512: 128,
}


def normalize_digest(value: str, *, algorithm: HashAlgorithm) -> str:
    """Normalize and validate a hexadecimal digest for ``algorithm``."""

    if not isinstance(value, str):
        raise ValueError("digest must be a string")
    if not value or any(ch.isspace() for ch in value):
        raise ValueError("digest must not be blank or contain whitespace")
    if ":" in value:
        raise ValueError("digest must not include an algorithm prefix")
    compact = value.lower()
    expected = _DIGEST_LENGTHS[algorithm]
    if len(compact) != expected:
        raise ValueError(f"{algorithm} digest must be exactly {expected} hexadecimal characters")
    if _HEX.fullmatch(compact) is None:
        raise ValueError("digest must be hexadecimal")
    return compact


def hash_bytes(
    data: bytes,
    *,
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
) -> FileFingerprint:
    """Hash supplied bytes into a ``FileFingerprint`` (no filesystem access)."""

    if algorithm is HashAlgorithm.SHA256:
        digest = hashlib.sha256(data).hexdigest()
    elif algorithm is HashAlgorithm.SHA512:
        digest = hashlib.sha512(data).hexdigest()
    else:  # pragma: no cover - enum exhaustiveness guard
        raise ValueError(f"unsupported hash algorithm: {algorithm}")
    return FileFingerprint(algorithm=algorithm, digest=digest)


class FileFingerprint(BaseModel):
    """Algorithm plus digest for a single file's content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm: HashAlgorithm
    digest: str

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: object, info: ValidationInfo) -> str:
        algorithm = info.data.get("algorithm")
        if algorithm is None:
            raise ValueError("algorithm is required before digest validation")
        return normalize_digest(str(value), algorithm=HashAlgorithm(algorithm))


class RepositoryFingerprint(BaseModel):
    """Canonical content fingerprint for an entire repository manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm: HashAlgorithm
    digest: str
    manifest_version: str
    file_count: int = Field(ge=0)

    @field_validator("manifest_version", mode="before")
    @classmethod
    def normalize_manifest_version(cls, value: object) -> str:
        return require_nonblank(str(value), label="manifest_version")

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: object, info: ValidationInfo) -> str:
        algorithm = info.data.get("algorithm")
        if algorithm is None:
            raise ValueError("algorithm is required before digest validation")
        return normalize_digest(str(value), algorithm=HashAlgorithm(algorithm))


class RepositoryFingerprintFactory:
    """Build deterministic repository content fingerprints from manifests."""

    @classmethod
    def from_manifest(
        cls,
        manifest: RepositoryManifest,
        *,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> RepositoryFingerprint:
        payload = cls.canonical_payload(manifest)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        fingerprint = hash_bytes(encoded, algorithm=algorithm)
        return RepositoryFingerprint(
            algorithm=fingerprint.algorithm,
            digest=fingerprint.digest,
            manifest_version=manifest.manifest_version,
            file_count=len(manifest.files),
        )

    @classmethod
    def canonical_payload(cls, manifest: RepositoryManifest) -> dict[str, object]:
        """Return the explicit canonical structure hashed for content identity."""

        files: list[dict[str, object]] = []
        for entry in manifest.files:
            files.append(
                {
                    "executable": entry.executable,
                    "file_kind": entry.file_kind.value,
                    "fingerprint": {
                        "algorithm": entry.fingerprint.algorithm.value,
                        "digest": entry.fingerprint.digest,
                    },
                    "generated": entry.generated,
                    "language": entry.language,
                    "media_type": entry.media_type,
                    "path": entry.path.root,
                    "size_bytes": entry.size_bytes,
                }
            )
        return {
            "files": files,
            "manifest_version": manifest.manifest_version,
        }
