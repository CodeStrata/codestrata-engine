"""Persist complexity evidence artifacts (optional; Phase 4.3.2)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.evidence.language.complexity.identifiers import (
    COMPLEXITY_ARTIFACT_FILENAME,
)
from codestrata.domain.evidence.language.complexity.models import AggregatedComplexityEvidence
from codestrata.services.artifact_serialization import dumps_stable_json


class ComplexityEvidenceArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    file_count: int = Field(ge=0)
    callable_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def complexity_evidence_payload(
    evidence: AggregatedComplexityEvidence,
) -> dict[str, object]:
    return evidence.model_dump(mode="json")


def write_complexity_evidence_artifact(
    evidence: AggregatedComplexityEvidence,
    run_directory: Path,
) -> ComplexityEvidenceArtifactWriteResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / COMPLEXITY_ARTIFACT_FILENAME
    text = dumps_stable_json(complexity_evidence_payload(evidence))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return ComplexityEvidenceArtifactWriteResult(
        path=path,
        file_count=len(evidence.files),
        callable_count=len(evidence.callables),
        byte_size=len(text.encode("utf-8")),
    )
