"""Persist technical debt assessment section artifacts (Phase 4.3.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.technical_debt.assessment.identifiers import (
    TECHNICAL_DEBT_ASSESSMENT_FILENAME,
)
from codestrata.domain.technical_debt.assessment.models import TechnicalDebtAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json
from codestrata.artifacts.heads import resolve_head_path


class TechnicalDebtAssessmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    section_status: str
    finding_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


def technical_debt_assessment_payload(
    section: TechnicalDebtAssessmentSection,
) -> dict[str, object]:
    return section.model_dump(mode="json")


def write_technical_debt_assessment_artifact(
    section: TechnicalDebtAssessmentSection,
    run_directory: Path,
) -> TechnicalDebtAssessmentArtifactWriteResult:
    """Write deterministic technical-debt-assessment.json under the run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = resolve_head_path(run_directory, legacy_filename=TECHNICAL_DEBT_ASSESSMENT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps_stable_json(technical_debt_assessment_payload(section))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return TechnicalDebtAssessmentArtifactWriteResult(
        path=path,
        section_status=section.status.value,
        # Primary inventory count (production by default).
        finding_count=len(section.finding_ids),
        byte_size=len(text.encode("utf-8")),
    )
