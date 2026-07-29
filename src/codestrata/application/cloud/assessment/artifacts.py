"""Persist cloud assessment section artifacts (Phase 4.7.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.cloud.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    CLOUD_ASSESSMENT_FILENAME,
)
from codestrata.domain.cloud.assessment.models import CloudAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json


class CloudAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def cloud_assessment_payload(
    section: CloudAssessmentSection,
) -> dict[str, object]:
    payload = section.model_dump(mode="json")
    payload["artifact_schema_id"] = ARTIFACT_SCHEMA_ID
    return payload


def write_cloud_assessment_artifact(
    section: CloudAssessmentSection,
    run_directory: Path,
) -> CloudAssessmentArtifactWriteResult:
    """Write deterministic cloud-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / CLOUD_ASSESSMENT_FILENAME
    text = dumps_stable_json(cloud_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return CloudAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
