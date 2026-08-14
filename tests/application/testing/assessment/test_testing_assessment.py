"""Test assessment assembler/serialization tests (Phase 4.6.1 / 4.6.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.testing.assessment.artifacts import (
    testing_assessment_payload as build_testing_assessment_payload,
)
from codestrata.application.testing.assessment.artifacts import (
    write_testing_assessment_artifact,
)
from codestrata.application.testing.assessment.assembler import TestAssessmentAssembler
from codestrata.application.testing.assessment.factory import (
    testing_assessment_section_enabled as is_testing_assessment_section_enabled,
)
from codestrata.application.testing.assessment.factory import (
    testing_pack_enabled as is_testing_pack_enabled,
)
from codestrata.artifacts.heads import resolve_head_path
from codestrata.config import load_settings
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    RepositoryTestingParseStatus,
    TestFileRole,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
    MarkerFactEvidence,
    RepositoryTestingEvidenceCoverage,
    TestFileCandidateEvidence,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.testing.assessment.enums import TestAssessmentStatus
from codestrata.domain.testing.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    TESTING_ASSESSMENT_FILENAME,
)
from codestrata.domain.testing.assessment.models import TestAssessmentSection
from codestrata.domain.testing.ids import RULE_DISABLED_OR_SKIPPED
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False
    assert is_testing_pack_enabled(settings) is False
    assert is_testing_assessment_section_enabled(settings) is False
    # Other verticals unchanged.
    assert settings.rules.architecture.enabled is False
    assert settings.rules.technical_debt.enabled is False
    assert settings.rules.dependency.enabled is False
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.architecture.enabled is False
    assert settings.assessment.sections.technical_debt.enabled is False
    assert settings.assessment.sections.dependency.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert settings.report.sections.testing.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.testing]
        enabled = true

        [assessment.sections.testing]
        enabled = true
        include_findings = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.testing.enabled is True
    assert settings.assessment.sections.testing.enabled is True
    assert settings.assessment.sections.testing.include_findings is False
    assert is_testing_pack_enabled(settings) is True
    assert is_testing_assessment_section_enabled(settings) is True
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.security.enabled is False


def test_lifecycle_states() -> None:
    assembler = TestAssessmentAssembler()
    cases = [
        (assembler.assemble_disabled(repository_id="repo:demo"), TestAssessmentStatus.DISABLED),
        (
            assembler.assemble_not_requested(repository_id="repo:demo"),
            TestAssessmentStatus.NOT_REQUESTED,
        ),
        (
            assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True),
            TestAssessmentStatus.SUCCEEDED,
        ),
        (
            assembler.assemble_insufficient_evidence(repository_id="repo:demo"),
            TestAssessmentStatus.INSUFFICIENT_EVIDENCE,
        ),
        (
            assembler.assemble_partially_succeeded(repository_id="repo:demo"),
            TestAssessmentStatus.PARTIALLY_SUCCEEDED,
        ),
        (
            assembler.assemble_failed(repository_id="repo:demo"),
            TestAssessmentStatus.FAILED,
        ),
        (
            assembler.assemble_not_applicable(repository_id="repo:demo"),
            TestAssessmentStatus.NOT_APPLICABLE,
        ),
    ]
    for section, expected in cases:
        assert section.status is expected
        assert section.finding_ids == ()
        assert section.findings == ()
        assert section.assessment_id.startswith("test-assessment:")
        assert any(
            "not implemented" in item.summary.lower() or "foundation" in item.summary.lower()
            for item in section.limitations
        )
        summary = section.metadata.get("summary", "").lower()
        assert "well tested" not in summary or "does not establish" in summary
        assert "release ready" not in summary or "does not establish" in summary
        assert "testing passed" not in summary


def test_succeeded_empty_states_no_rules_evaluated() -> None:
    section = TestAssessmentAssembler().assemble_empty(repository_id="repo:demo", pack_enabled=True)
    assert section.status is TestAssessmentStatus.SUCCEEDED
    assert section.execution_summary.testing_rules_planned == 0
    assert section.execution_summary.rules_executed == 0
    assert section.execution_summary.total_finding_count == 0
    assert "no_testing_rules_registered" in section.diagnostics


def test_artifact_write_round_trip(tmp_path: Path) -> None:
    section = TestAssessmentAssembler().assemble_empty(repository_id="repo:demo")
    written = write_testing_assessment_artifact(section, tmp_path)
    assert written.path == resolve_head_path(
        tmp_path, legacy_filename=TESTING_ASSESSMENT_FILENAME
    )
    assert written.finding_count == 0
    text = written.path.read_text(encoding="utf-8")
    payload = loads_stable_json(text)
    assert payload["artifact_schema_id"] == ARTIFACT_SCHEMA_ID
    assert payload["schema_name"] == "testing-assessment"
    assert payload["section_version"] == "1.2.0"
    restored = TestAssessmentSection.model_validate(
        {key: value for key, value in payload.items() if key != "artifact_schema_id"}
    )
    assert restored == section
    assert dumps_stable_json(build_testing_assessment_payload(section)) == text
    assert "/Users/" not in text
    assert '"hotspots"' not in text
    assert '"coverage_score"' not in text
    assert '"release_readiness"' not in text
    # Synthesis fields exist on schema 1.2.0 but remain empty on foundation paths.
    assert section.themes == ()
    assert section.conclusions == ()
    assert section.recommendations == ()


def test_deterministic_disabled_fingerprint() -> None:
    assembler = TestAssessmentAssembler()
    left = assembler.assemble_disabled(repository_id="repo:x")
    right = assembler.assemble_disabled(repository_id="repo:x")
    assert left.configuration_fingerprint == right.configuration_fingerprint
    assert left.assessment_id == right.assessment_id
    assert left.model_dump_json() == right.model_dump_json()


def test_orchestration_isolation_pattern() -> None:
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("testing boom")

    testing_assessment_status = None
    try:
        with patch.object(TestAssessmentAssembler, "assemble_empty", _boom):
            TestAssessmentAssembler().assemble_empty(repository_id="repo:x")
    except Exception:  # noqa: BLE001 - mirrors assessment service isolation
        testing_assessment_status = "failed"
    assert testing_assessment_status == "failed"

    with patch.object(TestAssessmentAssembler, "assemble_empty", _boom):
        with pytest.raises(RuntimeError, match="testing boom"):
            TestAssessmentAssembler().assemble_empty(repository_id="repo:x")


def test_assemble_with_hygiene_findings(tmp_path: Path) -> None:
    prov = EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )
    evidence = AggregatedRepositoryTestingEvidence(
        repository_id="repo:demo",
        status=RepositoryTestingParseStatus.SUCCEEDED,
        file_candidates=(
            TestFileCandidateEvidence(
                evidence_id="cand:tests/a.py",
                path="tests/a.py",
                role=TestFileRole.UNIT_TEST,
                provenance=prov,
            ),
        ),
        marker_facts=(
            MarkerFactEvidence(
                evidence_id="marker:tests/a.py:disabled",
                path="tests/a.py",
                marker_type=TestMarkerType.DISABLED,
                marker_text="@Disabled",
                provenance=prov,
            ),
        ),
        coverage=RepositoryTestingEvidenceCoverage(
            candidate_files_inspected=1,
            marker_facts=1,
            languages_represented=("python",),
        ),
        evidence_fingerprint="abc123",
    )
    finding = Finding.create(
        rule_id=RULE_DISABLED_OR_SKIPPED,
        title="Disabled or skipped tests detected",
        description="Observed 1 disabled or skipped test marker.",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.TESTING,
        subject_keys=(RULE_DISABLED_OR_SKIPPED, "markers", "1"),
    )
    section = TestAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(finding,),
        evidence=evidence,
        pack_enabled=True,
        rules_executed=4,
        rules_matched=1,
        evidence_pipeline="repository_testing",
        evidence_fingerprint="abc123",
    )
    assert section.status is TestAssessmentStatus.SUCCEEDED
    assert section.finding_ids == (finding.id,)
    assert finding.id in section.all_finding_ids
    assert section.execution_summary.total_finding_count == 1
    assert section.execution_summary.rules_executed == 4
    assert section.metadata.get("assessment_milestone") == "4.6.5"
    assert section.finding_inventory.finding_count == 1
    assert finding.id in section.finding_inventory.finding_ids
    assert section.severity_inventory.buckets
    assert section.rule_inventory.rules_planned == 4
    assert section.synthesis.themes
    assert section.themes
    assert section.conclusions
    assert section.recommendations
    assert section.metadata.get("overall_posture_summary")
    assert "well tested" not in section.metadata.get("summary", "").lower() or (
        "does not" in " ".join(item.summary.lower() for item in section.limitations)
    )
    written = write_testing_assessment_artifact(section, tmp_path)
    body = written.path.read_text(encoding="utf-8")
    assert "/Users/" not in body
    assert finding.id in body
