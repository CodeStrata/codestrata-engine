"""Persist AI Readiness assessment section artifacts (Phase 4.8.5)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.ai_readiness.assessment.identifiers import (
    AI_READINESS_ASSESSMENT_FILENAME,
    ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.ai_readiness.assessment.models import AiReadinessAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json


class AiReadinessAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def ai_readiness_assessment_payload(
    section: AiReadinessAssessmentSection,
) -> dict[str, object]:
    payload = section.model_dump(mode="json")
    payload["artifact_schema_id"] = ARTIFACT_SCHEMA_ID
    return payload


def write_ai_readiness_assessment_artifact(
    section: AiReadinessAssessmentSection,
    run_directory: Path,
) -> AiReadinessAssessmentArtifactWriteResult:
    """Write deterministic ai-readiness-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / AI_READINESS_ASSESSMENT_FILENAME
    text = dumps_stable_json(ai_readiness_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return AiReadinessAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
