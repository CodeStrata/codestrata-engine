"""Persist testing assessment section artifacts (Phase 4.6.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.testing.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    TESTING_ASSESSMENT_FILENAME,
)
from codestrata.domain.testing.assessment.models import TestAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json
from codestrata.artifacts.heads import resolve_head_path


class TestingAssessmentArtifactWriteResult(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def testing_assessment_payload(
    section: TestAssessmentSection,
) -> dict[str, object]:
    payload = section.model_dump(mode="json")
    payload["artifact_schema_id"] = ARTIFACT_SCHEMA_ID
    return payload


def write_testing_assessment_artifact(
    section: TestAssessmentSection,
    run_directory: Path,
) -> TestingAssessmentArtifactWriteResult:
    """Write deterministic testing-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = resolve_head_path(run_directory, legacy_filename=TESTING_ASSESSMENT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps_stable_json(testing_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return TestingAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
