"""Cloud assessment assembler/serialization tests (Phase 4.7.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.cloud.assessment.artifacts import (
    cloud_assessment_payload as build_cloud_assessment_payload,
)
from codestrata.application.cloud.assessment.artifacts import (
    write_cloud_assessment_artifact,
)
from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.application.cloud.assessment.factory import (
    cloud_analysis_enabled as is_cloud_analysis_enabled,
)
from codestrata.application.cloud.assessment.factory import (
    cloud_report_section_enabled as is_cloud_report_section_enabled,
)
from codestrata.artifacts.heads import resolve_head_path
from codestrata.config import load_settings
from codestrata.domain.cloud.assessment.enums import CloudAssessmentStatus
from codestrata.domain.cloud.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    CLOUD_ASSESSMENT_FILENAME,
)
from codestrata.domain.cloud.assessment.models import CloudAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.analysis.cloud.enabled is False
    assert settings.report.sections.cloud.enabled is False
    assert is_cloud_analysis_enabled(settings) is False
    assert is_cloud_report_section_enabled(settings) is False
    # Other verticals unchanged.
    assert settings.rules.architecture.enabled is False
    assert settings.rules.technical_debt.enabled is False
    assert settings.rules.dependency.enabled is False
    assert settings.rules.security.enabled is False
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.architecture.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert settings.assessment.sections.testing.enabled is False
    assert settings.report.sections.testing.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [analysis.cloud]
        enabled = true
        include_findings = false

        [report.sections.cloud]
        enabled = true
        include_coverage = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.analysis.cloud.enabled is True
    assert settings.analysis.cloud.include_findings is False
    assert settings.report.sections.cloud.enabled is True
    assert settings.report.sections.cloud.include_coverage is False
    assert is_cloud_analysis_enabled(settings) is True
    assert is_cloud_report_section_enabled(settings) is True
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert settings.assessment.sections.testing.enabled is False
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.security.enabled is False
    assert settings.report.sections.testing.enabled is False


def test_lifecycle_states() -> None:
    assembler = CloudAssessmentAssembler()
    cases = [
        (assembler.assemble_disabled(repository_id="repo:demo"), CloudAssessmentStatus.DISABLED),
        (
            assembler.assemble_not_requested(repository_id="repo:demo"),
            CloudAssessmentStatus.NOT_REQUESTED,
        ),
        (
            assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True),
            CloudAssessmentStatus.SUCCEEDED,
        ),
        (
            assembler.assemble_insufficient_evidence(repository_id="repo:demo"),
            CloudAssessmentStatus.INSUFFICIENT_EVIDENCE,
        ),
        (
            assembler.assemble_partially_succeeded(repository_id="repo:demo"),
            CloudAssessmentStatus.PARTIALLY_SUCCEEDED,
        ),
        (
            assembler.assemble_failed(repository_id="repo:demo"),
            CloudAssessmentStatus.FAILED,
        ),
        (
            assembler.assemble_not_applicable(repository_id="repo:demo"),
            CloudAssessmentStatus.NOT_APPLICABLE,
        ),
    ]
    for section, expected in cases:
        assert section.status is expected
        assert section.finding_ids == ()
        assert section.findings == ()
        assert section.assessment_id.startswith("cloud-assessment:")
        assert any(
            "not implemented" in item.summary.lower()
            or "foundation" in item.summary.lower()
            or "not evaluated" in item.summary.lower()
            for item in section.limitations
        )
        summary = section.metadata.get("summary", "").lower()
        assert "cloud ready" not in summary or "does not establish" in summary
        assert "portable" not in summary or "does not establish" in summary


def test_succeeded_empty_states_no_rules_evaluated() -> None:
    section = CloudAssessmentAssembler().assemble_empty(
        repository_id="repo:demo",
        pack_enabled=True,
    )
    assert section.status is CloudAssessmentStatus.SUCCEEDED
    assert section.execution_summary.cloud_rules_planned == 11
    assert section.execution_summary.rules_executed == 0
    assert section.execution_summary.total_finding_count == 0
    assert section.finding_inventory.finding_count == 0
    assert "no_cloud_findings" in section.diagnostics


def test_artifact_write_round_trip(tmp_path: Path) -> None:
    section = CloudAssessmentAssembler().assemble_empty(repository_id="repo:demo")
    written = write_cloud_assessment_artifact(section, tmp_path)
    assert written.path == resolve_head_path(
        tmp_path, legacy_filename=CLOUD_ASSESSMENT_FILENAME
    )
    assert written.finding_count == 0
    text = written.path.read_text(encoding="utf-8")
    payload = loads_stable_json(text)
    assert payload["artifact_schema_id"] == ARTIFACT_SCHEMA_ID
    assert payload["schema_name"] == "cloud-assessment"
    assert payload["section_version"] == "1.2.0"
    restored = CloudAssessmentSection.model_validate(
        {key: value for key, value in payload.items() if key != "artifact_schema_id"}
    )
    assert restored == section
    assert dumps_stable_json(build_cloud_assessment_payload(section)) == text
    assert "/Users/" not in text
    assert '"hotspots"' not in text
    assert '"readiness_score"' not in text
    assert '"finding_inventory"' in text
    assert '"technology_family_inventory"' in text
    assert '"synthesis"' in text


def test_deterministic_disabled_fingerprint() -> None:
    assembler = CloudAssessmentAssembler()
    left = assembler.assemble_disabled(repository_id="repo:x")
    right = assembler.assemble_disabled(repository_id="repo:x")
    assert left.configuration_fingerprint == right.configuration_fingerprint
    assert left.assessment_id == right.assessment_id
    assert left.model_dump_json() == right.model_dump_json()


def test_orchestration_isolation_pattern() -> None:
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("cloud boom")

    cloud_assessment_status = None
    try:
        with patch.object(CloudAssessmentAssembler, "assemble_empty", _boom):
            CloudAssessmentAssembler().assemble_empty(repository_id="repo:x")
    except Exception:  # noqa: BLE001 - mirrors assessment service isolation
        cloud_assessment_status = "failed"
    assert cloud_assessment_status == "failed"

    with patch.object(CloudAssessmentAssembler, "assemble_empty", _boom):
        with pytest.raises(RuntimeError, match="cloud boom"):
            CloudAssessmentAssembler().assemble_empty(repository_id="repo:x")
