"""Persist repository-cloud evidence artifacts (Phase 4.7.2)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.evidence.repository_cloud.identifiers import (
    REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
)
from codestrata.services.artifact_serialization import dumps_stable_json


class RepositoryCloudEvidenceArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    candidate_count: int = Field(ge=0)
    technology_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def repository_cloud_evidence_payload(
    evidence: AggregatedRepositoryCloudEvidence,
) -> dict[str, object]:
    payload = evidence.model_dump(mode="json")
    payload["artifact_schema_id"] = REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_SCHEMA_ID
    return payload


def write_repository_cloud_evidence_artifact(
    evidence: AggregatedRepositoryCloudEvidence,
    run_directory: Path,
) -> RepositoryCloudEvidenceArtifactWriteResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_FILENAME
    text = dumps_stable_json(repository_cloud_evidence_payload(evidence))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    technologies = evidence.coverage.technologies_represented
    return RepositoryCloudEvidenceArtifactWriteResult(
        path=path,
        candidate_count=len(evidence.file_candidates),
        technology_count=len(technologies),
        byte_size=len(text.encode("utf-8")),
    )
