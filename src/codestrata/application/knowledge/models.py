"""Transport-neutral knowledge-store application models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType


class RepositoryAliasType(StrEnum):
    """Supported repository lookup aliases.

    Alias comparison rules:

    * ``github_url`` — credential-free normalized GitHub URL (HTTPS form preferred
      for storage: ``https://github.com/{owner}/{repo}.git`` with lowercase
      owner/repo). Lookup matches any equivalent URL form after normalization.
    * ``local_path`` — absolute, resolved filesystem path string.
    * ``legacy_repository_key`` — Phase 2 inventory name-slug key (not globally
      unique; used only as a soft alias). Conflicting optional legacy aliases are
      skipped during ``register_or_resolve`` and do not merge repositories.
    * ``canonical_key_alias`` — alternate spelling of a canonical key when a
      controlled remapping is required (rarely used).
    """

    GITHUB_URL = "github_url"
    LOCAL_PATH = "local_path"
    LEGACY_REPOSITORY_KEY = "legacy_repository_key"
    CANONICAL_KEY_ALIAS = "canonical_key_alias"


class AssessmentRunStatus(StrEnum):
    """Lifecycle status for a persisted assessment run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class KnowledgeArtifactKind(StrEnum):
    """Kinds of immutable knowledge blobs."""

    REPOSITORY_MANIFEST = "repository_manifest"
    REPOSITORY_GRAPH = "repository_graph"
    ENGINEERING_KNOWLEDGE_GRAPH = "engineering_knowledge_graph"
    KNOWLEDGE_BINDINGS = "knowledge_bindings"
    ASSESSMENT_GRAPH = "assessment_graph"
    FINDINGS = "findings"
    RECOMMENDATIONS = "recommendations"
    AI_EXECUTION = "ai_execution"
    AI_ENRICHMENT = "ai_enrichment"


class RepositoryRecord(BaseModel):
    """Durable repository identity stored by the knowledge registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    canonical_key: str
    source_type: RepositorySourceType
    display_name: str
    created_at: datetime
    updated_at: datetime

    @field_validator("repository_id", "canonical_key", "display_name", mode="before")
    @classmethod
    def require_nonblank(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must be a nonempty string")
        return text

    @field_validator("repository_id")
    @classmethod
    def validate_uuid_string(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as error:
            raise ValueError("repository_id must be a UUID string") from error
        return value

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class RepositoryAliasRecord(BaseModel):
    """Single lookup alias bound to exactly one repository."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    alias_type: RepositoryAliasType
    alias_value: str
    created_at: datetime

    @field_validator("repository_id", "alias_value", mode="before")
    @classmethod
    def require_nonblank(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must be a nonempty string")
        return text

    @field_validator("created_at")
    @classmethod
    def require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class RepositoryIdentityHints(BaseModel):
    """Hints used to register or resolve a repository without content hashing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: RepositorySourceType
    display_name: str
    source_location: str | None = None
    local_path: Path | None = None
    existing_repository_key: str | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("display_name must be nonempty")
        return text

    @field_validator("source_location", "existing_repository_key", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class RepositorySnapshotRecord(BaseModel):
    """Immutable repository content snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str
    repository_id: str
    branch: str | None = None
    revision_type: RepositoryRevisionType
    revision_id: str
    content_fingerprint: str
    manifest_schema_version: str
    manifest_blob_ref: str
    manifest_blob_hash: str
    captured_at: datetime
    created_at: datetime

    @field_validator(
        "snapshot_id",
        "repository_id",
        "revision_id",
        "content_fingerprint",
        "manifest_schema_version",
        "manifest_blob_ref",
        "manifest_blob_hash",
        mode="before",
    )
    @classmethod
    def require_nonblank(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must be a nonempty string")
        return text

    @field_validator("captured_at", "created_at")
    @classmethod
    def require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class AssessmentRunRecord(BaseModel):
    """Persisted assessment execution lifecycle record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    repository_id: str
    snapshot_id: str | None = None
    status: AssessmentRunStatus
    assessment_mode: str
    codestrata_version: str
    ruleset_version: str
    started_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_fingerprint: str | None = None
    invalidation_fingerprint: str | None = None

    @field_validator(
        "run_id",
        "repository_id",
        "assessment_mode",
        "codestrata_version",
        "ruleset_version",
        mode="before",
    )
    @classmethod
    def require_nonblank(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must be a nonempty string")
        return text

    @field_validator("started_at")
    @classmethod
    def require_started_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class KnowledgeArtifactRecord(BaseModel):
    """Index row for an immutable knowledge blob."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str
    run_id: str
    snapshot_id: str | None = None
    artifact_kind: KnowledgeArtifactKind
    schema_version: str
    blob_ref: str
    blob_hash: str
    source_fingerprint: str | None = None
    created_at: datetime

    @field_validator(
        "artifact_id",
        "run_id",
        "schema_version",
        "blob_ref",
        "blob_hash",
        mode="before",
    )
    @classmethod
    def require_nonblank(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must be a nonempty string")
        return text

    @field_validator("created_at")
    @classmethod
    def require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class StagedKnowledgeArtifact(BaseModel):
    """Artifact staged for atomic run completion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_kind: KnowledgeArtifactKind
    schema_version: str
    payload: dict[str, Any] | list[Any]
    source_fingerprint: str | None = None
    snapshot_id: str | None = None
