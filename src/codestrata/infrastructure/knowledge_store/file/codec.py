"""Serialize application records to versioned JSON manifests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.application.knowledge.models import (
    AssessmentRunRecord,
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    KnowledgeArtifactRecord,
    RepositoryAliasRecord,
    RepositoryAliasType,
    RepositoryRecord,
    RepositorySnapshotRecord,
)
from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType
from codestrata.infrastructure.knowledge_store.sqlite.timeutil import (
    format_timestamp,
    parse_timestamp,
)

REPOSITORY_MANIFEST_SCHEMA = "codestrata-repository-identity:1"
SNAPSHOT_MANIFEST_SCHEMA = "codestrata-repository-snapshot:1"
RUN_MANIFEST_SCHEMA = "codestrata-assessment-run:1"
ARTIFACTS_MANIFEST_SCHEMA = "codestrata-run-artifacts:1"
STORE_MANIFEST_SCHEMA = "codestrata-file-knowledge-store:1"


def repository_document(record: RepositoryRecord) -> dict[str, Any]:
    return {
        "schema": REPOSITORY_MANIFEST_SCHEMA,
        "repository_id": record.repository_id,
        "canonical_key": record.canonical_key,
        "source_type": record.source_type.value,
        "display_name": record.display_name,
        "created_at": format_timestamp(record.created_at),
        "updated_at": format_timestamp(record.updated_at),
    }


def repository_from_document(document: Mapping[str, Any]) -> RepositoryRecord:
    return RepositoryRecord(
        repository_id=str(document["repository_id"]),
        canonical_key=str(document["canonical_key"]),
        source_type=RepositorySourceType(str(document["source_type"])),
        display_name=str(document["display_name"]),
        created_at=parse_timestamp(str(document["created_at"])),
        updated_at=parse_timestamp(str(document["updated_at"])),
    )


def aliases_document(records: Sequence[RepositoryAliasRecord]) -> dict[str, Any]:
    return {
        "schema": "codestrata-repository-aliases:1",
        "aliases": [
            {
                "repository_id": item.repository_id,
                "alias_type": item.alias_type.value,
                "alias_value": item.alias_value,
                "created_at": format_timestamp(item.created_at),
            }
            for item in records
        ],
    }


def aliases_from_document(document: Mapping[str, Any]) -> tuple[RepositoryAliasRecord, ...]:
    items = document.get("aliases", ())
    return tuple(
        RepositoryAliasRecord(
            repository_id=str(item["repository_id"]),
            alias_type=RepositoryAliasType(str(item["alias_type"])),
            alias_value=str(item["alias_value"]),
            created_at=parse_timestamp(str(item["created_at"])),
        )
        for item in items
    )


def snapshot_document(record: RepositorySnapshotRecord) -> dict[str, Any]:
    return {
        "schema": SNAPSHOT_MANIFEST_SCHEMA,
        "snapshot_id": record.snapshot_id,
        "repository_id": record.repository_id,
        "branch": record.branch,
        "revision_type": record.revision_type.value,
        "revision_id": record.revision_id,
        "content_fingerprint": record.content_fingerprint,
        "manifest_schema_version": record.manifest_schema_version,
        "manifest_blob_ref": record.manifest_blob_ref,
        "manifest_blob_hash": record.manifest_blob_hash,
        "captured_at": format_timestamp(record.captured_at),
        "created_at": format_timestamp(record.created_at),
    }


def snapshot_from_document(document: Mapping[str, Any]) -> RepositorySnapshotRecord:
    branch = document.get("branch")
    return RepositorySnapshotRecord(
        snapshot_id=str(document["snapshot_id"]),
        repository_id=str(document["repository_id"]),
        branch=None if branch in (None, "") else str(branch),
        revision_type=RepositoryRevisionType(str(document["revision_type"])),
        revision_id=str(document["revision_id"]),
        content_fingerprint=str(document["content_fingerprint"]),
        manifest_schema_version=str(document["manifest_schema_version"]),
        manifest_blob_ref=str(document["manifest_blob_ref"]),
        manifest_blob_hash=str(document["manifest_blob_hash"]),
        captured_at=parse_timestamp(str(document["captured_at"])),
        created_at=parse_timestamp(str(document["created_at"])),
    )


def run_document(record: AssessmentRunRecord) -> dict[str, Any]:
    return {
        "schema": RUN_MANIFEST_SCHEMA,
        "run_id": record.run_id,
        "repository_id": record.repository_id,
        "snapshot_id": record.snapshot_id,
        "status": record.status.value,
        "assessment_mode": record.assessment_mode,
        "codestrata_version": record.codestrata_version,
        "ruleset_version": record.ruleset_version,
        "started_at": format_timestamp(record.started_at),
        "completed_at": None
        if record.completed_at is None
        else format_timestamp(record.completed_at),
        "failed_at": None if record.failed_at is None else format_timestamp(record.failed_at),
        "error_code": record.error_code,
        "error_message": record.error_message,
        "request_fingerprint": record.request_fingerprint,
        "invalidation_fingerprint": record.invalidation_fingerprint,
    }


def run_from_document(document: Mapping[str, Any]) -> AssessmentRunRecord:
    completed = document.get("completed_at")
    failed = document.get("failed_at")
    snapshot_id = document.get("snapshot_id")
    error = document.get("error_code")
    return AssessmentRunRecord(
        run_id=str(document["run_id"]),
        repository_id=str(document["repository_id"]),
        snapshot_id=None if snapshot_id in (None, "") else str(snapshot_id),
        status=AssessmentRunStatus(str(document["status"])),
        assessment_mode=str(document["assessment_mode"]),
        codestrata_version=str(document["codestrata_version"]),
        ruleset_version=str(document["ruleset_version"]),
        started_at=parse_timestamp(str(document["started_at"])),
        completed_at=None if completed in (None, "") else parse_timestamp(str(completed)),
        failed_at=None if failed in (None, "") else parse_timestamp(str(failed)),
        error_code=None if error in (None, "") else str(error),
        error_message=(
            None if document.get("error_message") in (None, "") else str(document["error_message"])
        ),
        request_fingerprint=(
            None
            if document.get("request_fingerprint") in (None, "")
            else str(document["request_fingerprint"])
        ),
        invalidation_fingerprint=(
            None
            if document.get("invalidation_fingerprint") in (None, "")
            else str(document["invalidation_fingerprint"])
        ),
    )


def artifacts_document(records: Sequence[KnowledgeArtifactRecord]) -> dict[str, Any]:
    return {
        "schema": ARTIFACTS_MANIFEST_SCHEMA,
        "artifacts": [
            {
                "artifact_id": item.artifact_id,
                "run_id": item.run_id,
                "snapshot_id": item.snapshot_id,
                "artifact_kind": item.artifact_kind.value,
                "schema_version": item.schema_version,
                "blob_ref": item.blob_ref,
                "blob_hash": item.blob_hash,
                "source_fingerprint": item.source_fingerprint,
                "created_at": format_timestamp(item.created_at),
            }
            for item in records
        ],
    }


def artifacts_from_document(document: Mapping[str, Any]) -> tuple[KnowledgeArtifactRecord, ...]:
    items = document.get("artifacts", ())
    return tuple(
        KnowledgeArtifactRecord(
            artifact_id=str(item["artifact_id"]),
            run_id=str(item["run_id"]),
            snapshot_id=None if item.get("snapshot_id") in (None, "") else str(item["snapshot_id"]),
            artifact_kind=KnowledgeArtifactKind(str(item["artifact_kind"])),
            schema_version=str(item["schema_version"]),
            blob_ref=str(item["blob_ref"]),
            blob_hash=str(item["blob_hash"]),
            source_fingerprint=(
                None
                if item.get("source_fingerprint") in (None, "")
                else str(item["source_fingerprint"])
            ),
            created_at=parse_timestamp(str(item["created_at"])),
        )
        for item in items
    )
