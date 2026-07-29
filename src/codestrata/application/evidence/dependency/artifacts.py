"""Persist Dependency Evidence artifacts (Phase 4.4.2)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.evidence.dependency.identifiers import (
    DEPENDENCY_EVIDENCE_ARTIFACT_FILENAME,
    DEPENDENCY_EVIDENCE_ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.evidence.dependency.models import AggregatedDependencyEvidence
from codestrata.services.artifact_serialization import dumps_stable_json


class DependencyEvidenceArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    manifest_count: int = Field(ge=0)
    declaration_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def dependency_evidence_payload(
    evidence: AggregatedDependencyEvidence,
) -> dict[str, object]:
    payload = evidence.model_dump(mode="json")
    payload["artifact_schema_id"] = DEPENDENCY_EVIDENCE_ARTIFACT_SCHEMA_ID
    return payload


def write_dependency_evidence_artifact(
    evidence: AggregatedDependencyEvidence,
    run_directory: Path,
) -> DependencyEvidenceArtifactWriteResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / DEPENDENCY_EVIDENCE_ARTIFACT_FILENAME
    text = dumps_stable_json(dependency_evidence_payload(evidence))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return DependencyEvidenceArtifactWriteResult(
        path=path,
        manifest_count=len(evidence.manifests),
        declaration_count=len(evidence.declarations),
        byte_size=len(text.encode("utf-8")),
    )
