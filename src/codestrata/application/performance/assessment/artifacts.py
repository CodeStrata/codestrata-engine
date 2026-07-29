"""Persist Performance assessment section artifacts (Phase 4.9.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.performance.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    PERFORMANCE_ASSESSMENT_FILENAME,
)
from codestrata.domain.performance.assessment.models import PerformanceAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json


class PerformanceAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def performance_assessment_payload(
    section: PerformanceAssessmentSection,
) -> dict[str, object]:
    payload = section.model_dump(mode="json")
    payload["artifact_schema_id"] = ARTIFACT_SCHEMA_ID
    return payload


def write_performance_assessment_artifact(
    section: PerformanceAssessmentSection,
    run_directory: Path,
) -> PerformanceAssessmentArtifactWriteResult:
    """Write deterministic performance-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / PERFORMANCE_ASSESSMENT_FILENAME
    text = dumps_stable_json(performance_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return PerformanceAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
