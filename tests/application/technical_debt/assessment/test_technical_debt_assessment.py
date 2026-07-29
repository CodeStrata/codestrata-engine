"""Technical debt assessment assembler/serialization tests (Phase 4.3.1)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.technical_debt.assessment.artifacts import (
    technical_debt_assessment_payload,
    write_technical_debt_assessment_artifact,
)
from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
    technical_debt_findings,
)
from codestrata.application.technical_debt.assessment.factory import (
    technical_debt_assessment_section_enabled,
    technical_debt_pack_enabled,
)
from codestrata.config import load_settings
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtCoverageAreaStatus,
)
from codestrata.domain.technical_debt.assessment.identifiers import (
    SECTION_ID,
    TECHNICAL_DEBT_ASSESSMENT_FILENAME,
)
from codestrata.domain.technical_debt.assessment.models import TechnicalDebtAssessmentSection
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.rules.technical_debt.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False
    assert technical_debt_pack_enabled(settings) is False
    assert technical_debt_assessment_section_enabled(settings) is False


def test_assemble_disabled_and_empty_are_valid() -> None:
    assembler = TechnicalDebtAssessmentAssembler()
    disabled = assembler.assemble_disabled(repository_id="repo:demo")
    empty = assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True)
    assert disabled.status is TechnicalDebtAssessmentStatus.DISABLED
    assert empty.status is TechnicalDebtAssessmentStatus.SUCCEEDED
    assert disabled.section_id == SECTION_ID
    assert empty.finding_ids == ()
    assert empty.finding_summaries == ()
    assert any(
        area.area_id == "debt_rule_coverage"
        and area.status is TechnicalDebtCoverageAreaStatus.MEASURED
        for area in empty.coverage.areas
    )
    assert any(
        area.area_id == "complexity_coverage"
        and area.status is TechnicalDebtCoverageAreaStatus.PARTIAL
        for area in empty.coverage.areas
    )
    assert any(
        area.area_id == "duplication_coverage"
        and area.status is TechnicalDebtCoverageAreaStatus.UNSUPPORTED
        for area in empty.coverage.areas
    )
    assert empty.business_impact == "unknown"
    assert any("javascript" in item.summary.lower() for item in empty.limitations)
    assert any("financial cost" in item.summary.lower() for item in empty.limitations)


def test_artifact_write_round_trip(tmp_path: Path) -> None:
    section = TechnicalDebtAssessmentAssembler().assemble_empty(
        repository_id="repo:demo"
    )
    written = write_technical_debt_assessment_artifact(section, tmp_path)
    assert written.path.name == TECHNICAL_DEBT_ASSESSMENT_FILENAME
    assert written.finding_count == 0
    text = written.path.read_text(encoding="utf-8")
    restored = TechnicalDebtAssessmentSection.model_validate(loads_stable_json(text))
    assert restored == section
    assert dumps_stable_json(technical_debt_assessment_payload(section)) == text


def test_technical_debt_findings_filter() -> None:
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
            rule_id="technical_debt.example-future",
            title="debt",
            description="y",
            severity=FindingSeverity.LOW,
            category=FindingCategory.TECHNICAL_DEBT,
            subject_keys=("b",),
        ),
    )
    filtered = technical_debt_findings(findings)
    assert len(filtered) == 1
    assert filtered[0].rule_id.startswith("technical_debt.")


def test_deterministic_disabled_fingerprint() -> None:
    assembler = TechnicalDebtAssessmentAssembler()
    left = assembler.assemble_disabled(repository_id="repo:x")
    right = assembler.assemble_disabled(repository_id="repo:x")
    assert left.configuration_fingerprint == right.configuration_fingerprint
    assert left.model_dump_json() == right.model_dump_json()
