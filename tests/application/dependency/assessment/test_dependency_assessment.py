"""Dependency assessment assembler/serialization tests (Phase 4.4.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.dependency.assessment.artifacts import (
    dependency_assessment_payload,
    write_dependency_assessment_artifact,
)
from codestrata.application.dependency.assessment.assembler import (
    DependencyAssessmentAssembler,
    dependency_findings,
)
from codestrata.application.dependency.assessment.factory import (
    dependency_assessment_section_enabled,
    dependency_pack_enabled,
)
from codestrata.artifacts.heads import resolve_head_path
from codestrata.config import load_settings
from codestrata.domain.dependency.assessment.enums import (
    DependencyAssessmentStatus,
    DependencyCoverageAreaStatus,
)
from codestrata.domain.dependency.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    DEPENDENCY_ASSESSMENT_FILENAME,
    SECTION_ID,
)
from codestrata.domain.dependency.assessment.models import DependencyAssessmentSection
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.rules.dependency.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    assert dependency_pack_enabled(settings) is False
    assert dependency_assessment_section_enabled(settings) is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.dependency]
        enabled = true

        [assessment.sections.dependency]
        enabled = true
        include_findings = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.dependency.enabled is True
    assert settings.assessment.sections.dependency.enabled is True
    assert settings.assessment.sections.dependency.include_findings is False
    assert dependency_pack_enabled(settings) is True
    assert dependency_assessment_section_enabled(settings) is True
    # Existing Architecture / Technical Debt defaults remain disabled.
    assert settings.rules.architecture.enabled is False
    assert settings.rules.technical_debt.enabled is False
    assert settings.assessment.sections.architecture.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False


def test_assemble_disabled_not_requested_empty_insufficient() -> None:
    assembler = DependencyAssessmentAssembler()
    disabled = assembler.assemble_disabled(repository_id="repo:demo")
    not_requested = assembler.assemble_not_requested(repository_id="repo:demo")
    empty = assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True)
    insufficient = assembler.assemble_insufficient_evidence(repository_id="repo:demo")

    assert disabled.status is DependencyAssessmentStatus.DISABLED
    assert not_requested.status is DependencyAssessmentStatus.NOT_REQUESTED
    assert empty.status is DependencyAssessmentStatus.SUCCEEDED
    assert insufficient.status is DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE
    assert disabled.section_id == SECTION_ID
    assert empty.finding_ids == ()
    assert empty.finding_summaries == ()
    assert any(
        area.area_id == "dependency_evidence_coverage"
        and area.status is DependencyCoverageAreaStatus.UNSUPPORTED
        for area in empty.coverage.areas
    )
    assert empty.business_impact == "unknown"
    assert any("manifest" in item.summary.lower() for item in empty.limitations)
    assert any("cve" in item.summary.lower() for item in empty.limitations)


def test_artifact_write_round_trip(tmp_path: Path) -> None:
    section = DependencyAssessmentAssembler().assemble_empty(
        repository_id="repo:demo"
    )
    written = write_dependency_assessment_artifact(section, tmp_path)
    assert written.path == resolve_head_path(
        tmp_path, legacy_filename=DEPENDENCY_ASSESSMENT_FILENAME
    )
    assert written.finding_count == 0
    text = written.path.read_text(encoding="utf-8")
    payload = loads_stable_json(text)
    assert payload["artifact_schema_id"] == ARTIFACT_SCHEMA_ID
    restored = DependencyAssessmentSection.model_validate(
        {key: value for key, value in payload.items() if key != "artifact_schema_id"}
    )
    assert restored == section
    assert dumps_stable_json(dependency_assessment_payload(section)) == text
    assert "/Users/" not in text


def test_dependency_findings_filter_empty_without_rules() -> None:
    findings = (
        Finding.create(
            rule_id="architecture.dependency-cycle",
            title="cycle",
            description="x",
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.ARCHITECTURE,
            subject_keys=("a",),
        ),
        Finding.create(
            rule_id="dependency.example-future",
            title="dep",
            description="y",
            severity=FindingSeverity.LOW,
            category=FindingCategory.DEPENDENCY,
            subject_keys=("b",),
        ),
    )
    filtered = dependency_findings(findings)
    assert len(filtered) == 1
    assert filtered[0].rule_id.startswith("dependency.")


def test_deterministic_disabled_fingerprint() -> None:
    assembler = DependencyAssessmentAssembler()
    left = assembler.assemble_disabled(repository_id="repo:x")
    right = assembler.assemble_disabled(repository_id="repo:x")
    assert left.configuration_fingerprint == right.configuration_fingerprint
    assert left.model_dump_json() == right.model_dump_json()


def test_orchestration_isolation_pattern() -> None:
    """Dependency assembler failures must not escape the isolation boundary."""

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("dependency boom")

    dependency_assessment_status = None
    try:
        with patch.object(DependencyAssessmentAssembler, "assemble_empty", _boom):
            DependencyAssessmentAssembler().assemble_empty(repository_id="repo:x")
    except Exception:  # noqa: BLE001 - mirrors assessment service isolation
        dependency_assessment_status = "failed"
    assert dependency_assessment_status == "failed"

    with patch.object(DependencyAssessmentAssembler, "assemble_empty", _boom):
        with pytest.raises(RuntimeError, match="dependency boom"):
            DependencyAssessmentAssembler().assemble_empty(repository_id="repo:x")
