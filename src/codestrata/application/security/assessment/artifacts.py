"""Persist security assessment section artifacts (Phase 4.5.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.security.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    SECURITY_ASSESSMENT_FILENAME,
)
from codestrata.domain.security.assessment.models import SecurityAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json


class SecurityAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def security_assessment_payload(
    section: SecurityAssessmentSection,
) -> dict[str, object]:
    payload = section.model_dump(mode="json")
    payload["artifact_schema_id"] = ARTIFACT_SCHEMA_ID
    return payload


def write_security_assessment_artifact(
    section: SecurityAssessmentSection,
    run_directory: Path,
) -> SecurityAssessmentArtifactWriteResult:
    """Write deterministic security-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / SECURITY_ASSESSMENT_FILENAME
    text = dumps_stable_json(security_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return SecurityAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
