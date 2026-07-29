"""Security assessment assembler/serialization tests (Phase 4.5.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.security.assessment.artifacts import (
    security_assessment_payload,
    write_security_assessment_artifact,
)
from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.application.security.assessment.factory import (
    security_assessment_section_enabled,
    security_pack_enabled,
)
from codestrata.config import load_settings
from codestrata.domain.security.assessment.enums import SecurityAssessmentStatus
from codestrata.domain.security.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    SECURITY_ASSESSMENT_FILENAME,
)
from codestrata.domain.security.assessment.models import SecurityAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert security_pack_enabled(settings) is False
    assert security_assessment_section_enabled(settings) is False
    # Other verticals unchanged.
    assert settings.rules.architecture.enabled is False
    assert settings.rules.technical_debt.enabled is False
    assert settings.rules.dependency.enabled is False
    assert settings.assessment.sections.architecture.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    # Report gate exists and remains independently disabled by default.
    assert settings.report.sections.security.enabled is False
    assert settings.report.sections.dependency.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.security]
        enabled = true

        [assessment.sections.security]
        enabled = true
        include_findings = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.security.enabled is True
    assert settings.assessment.sections.security.enabled is True
    assert settings.assessment.sections.security.include_findings is False
    assert security_pack_enabled(settings) is True
    assert security_assessment_section_enabled(settings) is True
    assert settings.rules.dependency.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.technical_debt.enabled is False
    assert settings.report.sections.dependency.enabled is False


def test_lifecycle_states() -> None:
    assembler = SecurityAssessmentAssembler()
    cases = [
        (assembler.assemble_disabled(repository_id="repo:demo"), SecurityAssessmentStatus.DISABLED),
        (
            assembler.assemble_not_requested(repository_id="repo:demo"),
            SecurityAssessmentStatus.NOT_REQUESTED,
        ),
        (
            assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True),
            SecurityAssessmentStatus.SUCCEEDED,
        ),
        (
            assembler.assemble_insufficient_evidence(repository_id="repo:demo"),
            SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE,
        ),
        (
            assembler.assemble_partially_succeeded(repository_id="repo:demo"),
            SecurityAssessmentStatus.PARTIALLY_SUCCEEDED,
        ),
        (
            assembler.assemble_failed(repository_id="repo:demo"),
            SecurityAssessmentStatus.FAILED,
        ),
        (
            assembler.assemble_not_applicable(repository_id="repo:demo"),
            SecurityAssessmentStatus.NOT_APPLICABLE,
        ),
    ]
    for section, expected in cases:
        assert section.status is expected
        assert section.finding_ids == ()
        assert section.finding_summaries == ()
        assert section.assessment_id.startswith("sec-assessment:")
        assert any(
            "hygiene" in item.summary.lower() or "foundation" in item.summary.lower()
            for item in section.limitations
        )
        assert not any(
            phrase in section.metadata.get("summary", "").lower()
            for phrase in ("secure", "no secrets", "no security issues")
        )


def test_succeeded_empty_states_no_rules_evaluated() -> None:
    section = SecurityAssessmentAssembler().assemble_empty(
        repository_id="repo:demo", pack_enabled=True
    )
    assert section.status is SecurityAssessmentStatus.SUCCEEDED
    assert section.execution_summary.security_rules_planned == 0
    assert section.execution_summary.rules_executed == 0
    assert section.execution_summary.total_finding_count == 0
    assert any(
        "hygiene" in item.lower()
        or "not registered" in item.lower()
        or "typed repository-sensitive" in item.lower()
        or "disabled" in item.lower()
        for item in (lim.summary.lower() for lim in section.limitations)
    )


def test_artifact_write_round_trip(tmp_path: Path) -> None:
    section = SecurityAssessmentAssembler().assemble_empty(repository_id="repo:demo")
    written = write_security_assessment_artifact(section, tmp_path)
    assert written.path.name == SECURITY_ASSESSMENT_FILENAME
    assert written.finding_count == 0
    text = written.path.read_text(encoding="utf-8")
    payload = loads_stable_json(text)
    assert payload["artifact_schema_id"] == ARTIFACT_SCHEMA_ID
    assert payload["schema_name"] == "security-assessment"
    assert payload["section_version"] == "1.3.0"
    restored = SecurityAssessmentSection.model_validate(
        {key: value for key, value in payload.items() if key != "artifact_schema_id"}
    )
    assert restored == section
    assert dumps_stable_json(security_assessment_payload(section)) == text
    assert "/Users/" not in text
    assert '"risk_score"' not in text
    assert '"security_score"' not in text
    assert '"cvss"' not in text


def test_deterministic_disabled_fingerprint() -> None:
    assembler = SecurityAssessmentAssembler()
    left = assembler.assemble_disabled(repository_id="repo:x")
    right = assembler.assemble_disabled(repository_id="repo:x")
    assert left.configuration_fingerprint == right.configuration_fingerprint
    assert left.assessment_id == right.assessment_id
    assert left.model_dump_json() == right.model_dump_json()


def test_orchestration_isolation_pattern() -> None:
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("security boom")

    security_assessment_status = None
    try:
        with patch.object(SecurityAssessmentAssembler, "assemble_empty", _boom):
            SecurityAssessmentAssembler().assemble_empty(repository_id="repo:x")
    except Exception:  # noqa: BLE001 - mirrors assessment service isolation
        security_assessment_status = "failed"
    assert security_assessment_status == "failed"

    with patch.object(SecurityAssessmentAssembler, "assemble_empty", _boom):
        with pytest.raises(RuntimeError, match="security boom"):
            SecurityAssessmentAssembler().assemble_empty(repository_id="repo:x")
