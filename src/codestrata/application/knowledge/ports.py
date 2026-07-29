"""Application ports for the engineering knowledge store."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Any, Protocol

from codestrata.application.knowledge.models import (
    AssessmentRunRecord,
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    KnowledgeArtifactRecord,
    RepositoryAliasRecord,
    RepositoryAliasType,
    RepositoryIdentityHints,
    RepositoryRecord,
    RepositorySnapshotRecord,
    StagedKnowledgeArtifact,
)
from codestrata.domain.repository import RepositoryManifest
from codestrata.domain.repository.enums import RepositoryRevisionType


class RepositoryRegistry(Protocol):
    """Register and resolve durable repository identities."""

    def register_or_resolve(self, identity_hints: RepositoryIdentityHints) -> RepositoryRecord:
        """Create or resolve a repository from identity hints."""

    def get_by_id(self, repository_id: str) -> RepositoryRecord | None:
        """Return a repository by durable ID."""

    def get_by_canonical_key(self, canonical_key: str) -> RepositoryRecord | None:
        """Return a repository by canonical key."""

    def resolve_alias(
        self,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> RepositoryRecord | None:
        """Return the repository bound to an alias, if any."""

    def add_alias(
        self,
        repository_id: str,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> None:
        """Attach an alias to a repository; conflicts raise application errors."""

    def list_aliases(self, repository_id: str) -> Sequence[RepositoryAliasRecord]:
        """List aliases for a repository."""

    def list_repositories(self) -> Sequence[RepositoryRecord]:
        """List all registered repositories ordered by display name."""


class SnapshotStore(Protocol):
    """Persist and read immutable repository content snapshots."""

    def create_or_get_snapshot(
        self,
        *,
        repository_id: str,
        branch: str | None,
        revision_type: RepositoryRevisionType,
        revision_id: str,
        manifest: RepositoryManifest,
        content_fingerprint: str,
        captured_at: object | None = None,
    ) -> RepositorySnapshotRecord:
        """Create a snapshot or reuse one with the same content fingerprint."""

    def get_snapshot(self, snapshot_id: str) -> RepositorySnapshotRecord | None:
        """Return a snapshot by ID."""

    def get_latest_snapshot(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> RepositorySnapshotRecord | None:
        """Return the latest snapshot for a repository (optionally branch-scoped)."""

    def get_manifest(self, snapshot_id: str) -> RepositoryManifest:
        """Load and validate the repository manifest for a snapshot."""

    def list_snapshots(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
        limit: int = 50,
    ) -> Sequence[RepositorySnapshotRecord]:
        """List snapshots newest-first."""


class AssessmentRunStore(Protocol):
    """Persist assessment run lifecycle and linked artifacts."""

    def create_run(
        self,
        *,
        repository_id: str,
        assessment_mode: str,
        codestrata_version: str,
        ruleset_version: str,
        request_fingerprint: str | None = None,
        invalidation_fingerprint: str | None = None,
    ) -> AssessmentRunRecord:
        """Create a run in ``running`` status."""

    def attach_snapshot(self, run_id: str, snapshot_id: str) -> AssessmentRunRecord:
        """Associate a snapshot with a running assessment."""

    def complete_run(
        self,
        run_id: str,
        *,
        snapshot_id: str,
        artifacts: Sequence[StagedKnowledgeArtifact],
    ) -> AssessmentRunRecord:
        """Atomically persist artifacts and mark the run completed."""

    def fail_run(
        self,
        run_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> AssessmentRunRecord:
        """Mark a run failed."""

    def abort_stale_runs(
        self,
        *,
        older_than_seconds: float,
    ) -> Sequence[AssessmentRunRecord]:
        """Abort runs stuck in ``running`` longer than the threshold."""

    def get_run(self, run_id: str) -> AssessmentRunRecord | None:
        """Return a run by ID."""

    def get_latest_completed_run(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> AssessmentRunRecord | None:
        """Return the latest completed run (optionally for a branch tip snapshot)."""

    def list_runs(
        self,
        repository_id: str,
        *,
        limit: int = 50,
        status: AssessmentRunStatus | None = None,
    ) -> Sequence[AssessmentRunRecord]:
        """List runs newest-first."""

    def list_artifacts(self, run_id: str) -> Sequence[KnowledgeArtifactRecord]:
        """List artifacts for a run."""

    def get_artifact(
        self,
        run_id: str,
        artifact_kind: KnowledgeArtifactKind,
    ) -> KnowledgeArtifactRecord | None:
        """Return a single artifact index row."""

    def read_artifact_payload(
        self,
        run_id: str,
        artifact_kind: KnowledgeArtifactKind,
    ) -> Mapping[str, Any] | list[Any]:
        """Read and hash-verify an artifact JSON payload."""


class KnowledgeStore(Protocol):
    """Lifecycle and transaction boundary for the knowledge persistence backend."""

    @property
    def directory(self) -> object:
        """Root knowledge directory (implementation-specific path type)."""

    @property
    def registry(self) -> RepositoryRegistry:
        """Repository registry bound to this store."""

    @property
    def snapshots(self) -> SnapshotStore:
        """Snapshot store bound to this store."""

    @property
    def runs(self) -> AssessmentRunStore:
        """Assessment run store bound to this store."""

    def open(self) -> None:
        """Initialize or open the store and apply migrations."""

    def close(self) -> None:
        """Release database resources."""

    def __enter__(self) -> KnowledgeStore:
        """Open the store as a context manager."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        """Close the store."""

    def repository_lock(
        self,
        repository_id: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> AbstractContextManager[None]:
        """Exclusive mutation lock for a repository (local machine only)."""
