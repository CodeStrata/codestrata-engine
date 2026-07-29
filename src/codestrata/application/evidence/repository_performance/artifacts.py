"""Persist repository performance evidence artifacts (Phase 4.9.2)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.evidence.repository_performance.identifiers import (
    REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.evidence.repository_performance.models import (
    AggregatedRepositoryPerformanceEvidence,
)
from codestrata.services.artifact_serialization import dumps_stable_json


class RepositoryPerformanceEvidenceArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    candidate_count: int = Field(ge=0)
    technology_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def repository_performance_evidence_payload(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> dict[str, object]:
    payload = evidence.model_dump(mode="json")
    payload["artifact_schema_id"] = REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_SCHEMA_ID
    return payload


def write_repository_performance_evidence_artifact(
    evidence: AggregatedRepositoryPerformanceEvidence,
    run_directory: Path,
) -> RepositoryPerformanceEvidenceArtifactWriteResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_FILENAME
    text = dumps_stable_json(repository_performance_evidence_payload(evidence))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    technologies = evidence.coverage.technologies_represented
    return RepositoryPerformanceEvidenceArtifactWriteResult(
        path=path,
        candidate_count=len(evidence.file_candidates),
        technology_count=len(technologies),
        byte_size=len(text.encode("utf-8")),
    )
