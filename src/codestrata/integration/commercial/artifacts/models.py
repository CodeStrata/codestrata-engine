"""Immutable Engine-side artifact publishing contracts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    artifact_type: str
    format: str
    schema_version: str
    checksum: str
    size_bytes: int
    metadata: dict[str, str] = field(default_factory=dict)
    local_path: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class PublishArtifactRequest:
    engine_assessment_id: str
    platform_assessment_id: str
    artifact_type: str
    format: str
    schema_version: str
    checksum: str
    size_bytes: int
    metadata: dict[str, str] = field(default_factory=dict)
    content: bytes = b""


@dataclass(frozen=True, slots=True)
class PublishArtifactResult:
    artifact_id: str
    assessment_id: str
    artifact_type: str
    checksum: str
    status: str
    version: int
    created: bool


@dataclass(frozen=True, slots=True)
class ArtifactFailure:
    artifact_type: str
    reason: str
    reason_code: str = "artifact_publish_failed"
