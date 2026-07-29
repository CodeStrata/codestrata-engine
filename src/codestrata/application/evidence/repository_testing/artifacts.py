"""Persist repository-testing evidence artifacts (Phase 4.6.2)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.evidence.repository_testing.identifiers import (
    REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_TESTING_EVIDENCE_ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
)
from codestrata.services.artifact_serialization import dumps_stable_json


class RepositoryTestingEvidenceArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    candidate_count: int = Field(ge=0)
    framework_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def repository_testing_evidence_payload(
    evidence: AggregatedRepositoryTestingEvidence,
) -> dict[str, object]:
    payload = evidence.model_dump(mode="json")
    payload["artifact_schema_id"] = REPOSITORY_TESTING_EVIDENCE_ARTIFACT_SCHEMA_ID
    return payload


def write_repository_testing_evidence_artifact(
    evidence: AggregatedRepositoryTestingEvidence,
    run_directory: Path,
) -> RepositoryTestingEvidenceArtifactWriteResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME
    text = dumps_stable_json(repository_testing_evidence_payload(evidence))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return RepositoryTestingEvidenceArtifactWriteResult(
        path=path,
        candidate_count=len(evidence.file_candidates),
        framework_count=len(evidence.framework_facts),
        byte_size=len(text.encode("utf-8")),
    )
