"""AI Readiness assessment assembler/serialization tests (Phase 4.8.4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.ai_readiness.assessment.artifacts import (
    ai_readiness_assessment_payload as build_ai_readiness_assessment_payload,
)
from codestrata.application.ai_readiness.assessment.artifacts import (
    write_ai_readiness_assessment_artifact,
)
from codestrata.application.ai_readiness.assessment.assembler import AiReadinessAssessmentAssembler
from codestrata.application.ai_readiness.assessment.factory import (
    ai_readiness_analysis_enabled as is_ai_readiness_analysis_enabled,
)
from codestrata.application.ai_readiness.assessment.factory import (
    ai_readiness_report_section_enabled as is_ai_readiness_report_section_enabled,
)
from codestrata.config import load_settings
from codestrata.domain.ai_readiness.assessment.enums import AiReadinessAssessmentStatus
from codestrata.domain.ai_readiness.assessment.identifiers import (
    AI_READINESS_ASSESSMENT_FILENAME,
    ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.ai_readiness.assessment.models import AiReadinessAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.report.sections.ai_readiness.enabled is False
    assert is_ai_readiness_analysis_enabled(settings) is False
    assert is_ai_readiness_report_section_enabled(settings) is False
    assert settings.analysis.cloud.enabled is False
    assert settings.rules.cloud.enabled is False
    assert settings.assessment.sections.testing.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [analysis.ai_readiness]
        enabled = true
        include_findings = false

        [report.sections.ai_readiness]
        enabled = true
        include_coverage = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.analysis.ai_readiness.enabled is True
    assert settings.analysis.ai_readiness.include_findings is False
    assert settings.report.sections.ai_readiness.enabled is True
    assert settings.report.sections.ai_readiness.include_coverage is False
    assert is_ai_readiness_analysis_enabled(settings) is True
    assert is_ai_readiness_report_section_enabled(settings) is True
    assert settings.analysis.cloud.enabled is False
    assert settings.report.sections.cloud.enabled is False


def test_lifecycle_states() -> None:
    assembler = AiReadinessAssessmentAssembler()
    cases = [
        (
            assembler.assemble_disabled(repository_id="repo:demo"),
            AiReadinessAssessmentStatus.DISABLED,
        ),
        (
            assembler.assemble_not_requested(repository_id="repo:demo"),
            AiReadinessAssessmentStatus.NOT_REQUESTED,
        ),
        (
            assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True),
            AiReadinessAssessmentStatus.SUCCEEDED,
        ),
        (
            assembler.assemble_insufficient_evidence(repository_id="repo:demo"),
            AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE,
        ),
        (
            assembler.assemble_partially_succeeded(repository_id="repo:demo"),
            AiReadinessAssessmentStatus.PARTIALLY_SUCCEEDED,
        ),
        (
            assembler.assemble_failed(repository_id="repo:demo"),
            AiReadinessAssessmentStatus.FAILED,
        ),
        (
            assembler.assemble_not_applicable(repository_id="repo:demo"),
            AiReadinessAssessmentStatus.NOT_APPLICABLE,
        ),
    ]
    for section, expected in cases:
        assert section.status is expected
        assert section.finding_ids == ()
        assert section.execution_summary.rules_executed == 0


def test_empty_and_disabled_behavior() -> None:
    empty = AiReadinessAssessmentAssembler().assemble_empty(repository_id="repo:empty")
    assert empty.status is AiReadinessAssessmentStatus.SUCCEEDED
    assert empty.finding_ids == ()
    assert empty.section_version == "1.2.0"
    assert empty.finding_inventory.finding_count == 0
    assert empty.capability_family_inventory.families_total == 7
    assert "no_ai_readiness_findings" in empty.diagnostics
    assert empty.limitations
    joined = " ".join(item.summary for item in empty.limitations).lower()
    assert "inventory" in joined
    assert "no conclusion" in joined

    disabled = AiReadinessAssessmentAssembler().assemble_empty(
        repository_id="repo:empty",
        pack_enabled=False,
    )
    assert disabled.status is AiReadinessAssessmentStatus.DISABLED


def test_artifact_write_deterministic(tmp_path: Path) -> None:
    section = AiReadinessAssessmentAssembler().assemble_empty(repository_id="repo:demo")
    written = write_ai_readiness_assessment_artifact(section, tmp_path)
    assert written.path.name == AI_READINESS_ASSESSMENT_FILENAME
    text = written.path.read_text(encoding="utf-8")
    payload = loads_stable_json(text)
    assert payload["artifact_schema_id"] == ARTIFACT_SCHEMA_ID
    assert payload["section_version"] == "1.2.0"
    assert "finding_inventory" in payload
    assert "capability_family_inventory" in payload
    restored = AiReadinessAssessmentSection.model_validate(
        {key: value for key, value in payload.items() if key != "artifact_schema_id"}
    )
    assert restored == section
    assert dumps_stable_json(build_ai_readiness_assessment_payload(section)) == text
    assert "/Users/" not in text
    assert '"hotspots"' not in text
    assert '"readiness_score"' not in text
    assert '"synthesis"' in text
    assert written.finding_count == 0

    again = write_ai_readiness_assessment_artifact(section, tmp_path / "r2")
    assert written.path.read_text(encoding="utf-8") == again.path.read_text(encoding="utf-8")


def test_orchestration_isolation() -> None:
    with patch(
        "codestrata.application.ai_readiness.assessment.assembler."
        "AiReadinessAssessmentAssembler.assemble_empty",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            AiReadinessAssessmentAssembler().assemble_empty(repository_id="repo:x")
