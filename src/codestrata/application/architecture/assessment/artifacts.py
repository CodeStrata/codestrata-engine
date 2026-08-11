"""Persist architecture assessment section artifacts."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.architecture.assessment.identifiers import ARCHITECTURE_ASSESSMENT_FILENAME
from codestrata.domain.architecture.assessment.models import ArchitectureAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json
from codestrata.artifacts.heads import resolve_head_path

ARCHITECTURE_ASSESSMENT_FILENAME_EXPORT = ARCHITECTURE_ASSESSMENT_FILENAME


class ArchitectureAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    conclusion_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def architecture_assessment_payload(
    section: ArchitectureAssessmentSection,
) -> dict[str, object]:
    return section.model_dump(mode="json")


def write_architecture_assessment_artifact(
    section: ArchitectureAssessmentSection,
    run_directory: Path,
) -> ArchitectureAssessmentArtifactWriteResult:
    """Write deterministic architecture-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = resolve_head_path(run_directory, legacy_filename=ARCHITECTURE_ASSESSMENT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps_stable_json(architecture_assessment_payload(section))
    # Atomic replace when possible.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return ArchitectureAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        finding_count=len(section.finding_ids),
        conclusion_count=len(section.conclusion_ids),
        byte_size=len(text.encode("utf-8")),
    )
