"""Persist dependency assessment section artifacts (Phase 4.4.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.dependency.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    DEPENDENCY_ASSESSMENT_FILENAME,
)
from codestrata.domain.dependency.assessment.models import DependencyAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json


class DependencyAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def dependency_assessment_payload(
    section: DependencyAssessmentSection,
) -> dict[str, object]:
    payload = section.model_dump(mode="json")
    payload["artifact_schema_id"] = ARTIFACT_SCHEMA_ID
    return payload


def write_dependency_assessment_artifact(
    section: DependencyAssessmentSection,
    run_directory: Path,
) -> DependencyAssessmentArtifactWriteResult:
    """Write deterministic dependency-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / DEPENDENCY_ASSESSMENT_FILENAME
    text = dumps_stable_json(dependency_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return DependencyAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
