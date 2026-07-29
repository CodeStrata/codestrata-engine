"""Security report adapter and presentation tests (Phase 4.5.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.application.security.assessment.inventory import execution_facts_from_status_map
from codestrata.config import load_settings
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationFormat,
    ConfigurationKeyFamily,
    ContentClassification,
    InspectionStatus,
    RepositorySensitiveParseStatus,
    SensitiveArtifactKind,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
    ConfigurationFactEvidence,
    RepositorySensitiveDiagnostic,
    RepositorySensitiveEvidenceCoverage,
    SensitiveArtifactEvidence,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence
from codestrata.domain.security.assessment.enums import SecurityAssessmentStatus
from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    RULE_CREDENTIAL_LITERAL,
    RULE_PRIVATE_KEY_MATERIAL,
)
from codestrata.domain.security.synthesis.enums import (
    SecurityConclusionKind,
    SecurityRecommendationKind,
    SecuritySynthesisStatus,
    SecurityThemeKind,
)
from codestrata.domain.security.taxonomy import SecurityCategory
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.security.adapter import SecurityReportAdapter
from codestrata.reporting.security.models import (
    CONCLUSION_DISPLAY_LIMIT,
    DIAGNOSTIC_DISPLAY_LIMIT,
    FINDING_DISPLAY_LIMIT,
    HOTSPOT_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    RECOMMENDATION_DISPLAY_LIMIT,
    SECURITY_REPORT_SECTION_ID,
    SECURITY_REPORT_SECTION_VERSION,
    THEME_DISPLAY_LIMIT,
    TRACE_SAMPLE_LIMIT,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_FORBIDDEN_CLAIMS = (
    "no security issues",
    "no vulnerabilities",
    "security passed",
    "safe to deploy",
    "low risk",
    "compliant",
    "secure repository",
    "vulnerability-free",
)


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _finding(
    *,
    rule_id: str,
    path: str,
    finding_id: str,
    classification: str = "source",
    severity: FindingSeverity = FindingSeverity.HIGH,
    category: str = SecurityCategory.PRIVATE_KEY.value,
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} at {path}",
        description=f"Bounded explanation for {path}",
        severity=severity,
        category=FindingCategory.SECURITY,
        evidence=(
            FindingEvidence(
                evidence_type="repository_sensitive",
                source_id=f"ev:{path}",
                path=path,
                excerpt="[REDACTED]",
            ),
        ),
        metadata={
            "classification": classification,
            "security_category": category,
            "confidence": "high",
            "remediation": "Remediate the observed hygiene condition.",
            "evidence_id": f"ev:{path}",
            "path": path,
        },
    )


def _facts_all_ok():
    return execution_facts_from_status_map(
        {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    )


def _evidence(
    *,
    status: RepositorySensitiveParseStatus = RepositorySensitiveParseStatus.SUCCEEDED,
    diagnostics: tuple[RepositorySensitiveDiagnostic, ...] = (),
) -> AggregatedRepositorySensitiveEvidence:
    return AggregatedRepositorySensitiveEvidence(
        repository_id="fixture",
        status=status,
        artifacts=(
            SensitiveArtifactEvidence(
                evidence_id="art:tls/server.key",
                path="tls/server.key",
                kind=SensitiveArtifactKind.PRIVATE_KEY,
                inspection_status=InspectionStatus.INSPECTED,
                content_classifications=(
                    ContentClassification.PRIVATE_KEY_MATERIAL,
                ),
                classification=SourceClassification.SOURCE,
                provenance=_prov(),
            ),
        ),
        configuration_facts=(
            ConfigurationFactEvidence(
                evidence_id="cfg:app.properties:password",
                path="app.properties",
                classification=SourceClassification.SOURCE,
                format=ConfigurationFormat.PROPERTIES,
                normalized_key="password",
                key_family=ConfigurationKeyFamily.CREDENTIAL,
                redacted_preview="[REDACTED]",
                value_fingerprint="fp1",
                value_kind=ValueKind.LITERAL,
                provenance=_prov(),
            ),
        ),
        coverage=RepositorySensitiveEvidenceCoverage(
            candidate_files_discovered=2,
            files_inspected=2,
            structured_files_parsed=1,
            malformed_files=1 if diagnostics else 0,
            configuration_facts_collected=1,
            formats_represented=("properties",),
        ),
        diagnostics=diagnostics,
        evidence_fingerprint="deadbeef",
    )


def _assemble(*, findings=(), evidence=None, include_synthesis=True, **kwargs):
    return SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=evidence or _evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
        include_synthesis=include_synthesis,
        configuration_payload="stable-config",
        **kwargs,
    )


def _report_input(
    security_report=None, *, tmp_path: Path | None = None
) -> ModernizationReportInput:
    repo_path = tmp_path / "demo" if tmp_path is not None else Path("demo")
    return ModernizationReportInput(
        analysis_result=AnalysisResult(
            repository=Repository(name="demo", path=repo_path),
            technologies=[],
            findings=[],
            recommendations=[],
        ),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        security_report=security_report,
    )


def test_report_section_contract() -> None:
    report = SecurityReportAdapter().adapt(_assemble())
    assert report.section_id == SECURITY_REPORT_SECTION_ID
    assert report.section_version == SECURITY_REPORT_SECTION_VERSION
    assert report.schema_name == "report.security"
    assert report.status == SecurityAssessmentStatus.SUCCEEDED.value
    assert report.executive_summary
    assert report.coverage_summary.rules_executed == len(HYGIENE_RULE_IDS)
    assert report.traceability is not None


def test_report_gate_disabled_by_default(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.report.sections.security.enabled is False
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.technical_debt.enabled is False
    assert settings.report.sections.dependency.enabled is False


def test_report_gate_independent_of_upstream(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [evidence.repository_sensitive]
        enabled = true

        [rules.security]
        enabled = true

        [assessment.sections.security]
        enabled = true

        [report.sections.security]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_sensitive.enabled is True
    assert settings.rules.security.enabled is True
    assert settings.assessment.sections.security.enabled is True
    assert settings.report.sections.security.enabled is True
    assert settings.report.sections.dependency.enabled is False


def test_adapter_purity_no_reanalysis() -> None:
    assessment = _assemble()
    before = dumps_stable_json(assessment.model_dump(mode="json"))
    with (
        patch(
            "codestrata.application.security.synthesis.synthesize_security",
            side_effect=AssertionError("synthesis must not run"),
        ),
        patch(
            "codestrata.application.security.assessment.assembler.SecurityAssessmentAssembler.assemble",
            side_effect=AssertionError("assembler must not run"),
        ),
    ):
        report = SecurityReportAdapter().adapt(assessment)
    after = dumps_stable_json(assessment.model_dump(mode="json"))
    assert before == after
    assert (
        report.finding_summary.all_finding_count
        == assessment.finding_inventory.total_finding_count
    )


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        (
            lambda: SecurityAssessmentAssembler().assemble_disabled(
                repository_id="repo:x"
            ),
            "disabled",
        ),
        (
            lambda: SecurityAssessmentAssembler().assemble_not_requested(
                repository_id="repo:x"
            ),
            "not_requested",
        ),
        (
            lambda: SecurityAssessmentAssembler().assemble_insufficient_evidence(
                repository_id="repo:x"
            ),
            "insufficient_evidence",
        ),
        (
            lambda: SecurityAssessmentAssembler().assemble_failed(
                repository_id="repo:x"
            ),
            "failed",
        ),
        (
            lambda: SecurityAssessmentAssembler().assemble_partially_succeeded(
                repository_id="repo:x"
            ),
            "partially_succeeded",
        ),
        (lambda: _assemble(), "succeeded"),
    ],
)
def test_status_mapping(factory, expected: str) -> None:
    report = SecurityReportAdapter().adapt(factory())
    assert report.status == expected
    assert report.assessment_status == expected


def test_synthesis_disabled_inventory_only() -> None:
    assessment = _assemble(include_synthesis=False)
    report = SecurityReportAdapter().adapt(assessment)
    assert assessment.synthesis.status is SecuritySynthesisStatus.NOT_REQUESTED
    assert report.synthesis_status == "not_requested"
    assert report.themes == ()
    assert report.conclusions == ()
    assert report.recommendations == ()
    assert report.coverage_summary.rules_executed == len(HYGIENE_RULE_IDS)
    assert "inventory and coverage" in report.executive_summary.lower()


def test_synthesis_failed_preserves_inventory() -> None:
    with patch(
        "codestrata.application.security.assessment.assembler.synthesize_security",
        side_effect=RuntimeError("boom"),
    ):
        assessment = _assemble(
            findings=(
                _finding(
                    rule_id=RULE_PRIVATE_KEY_MATERIAL,
                    path="tls/server.key",
                    finding_id="f1",
                ),
            )
        )
    report = SecurityReportAdapter().adapt(assessment)
    assert report.synthesis_status == "failed"
    assert report.finding_summary.production_finding_count == 1
    assert report.themes == ()
    assert "synthesis is unavailable" in report.executive_summary.lower()


def test_zero_findings_executive_summary() -> None:
    report = SecurityReportAdapter().adapt(_assemble())
    text = report.executive_summary.lower()
    assert "no production-role findings" in text
    assert "does not establish" in text
    assert "is secure" in text  # disclaimer only
    for claim in _FORBIDDEN_CLAIMS:
        assert claim not in text


def test_production_findings_executive_summary() -> None:
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_PRIVATE_KEY_MATERIAL,
                path="tls/server.key",
                finding_id="pk",
            ),
            _finding(
                rule_id=RULE_CREDENTIAL_LITERAL,
                path="test/fixtures.properties",
                finding_id="test-cred",
                classification="test",
                category=SecurityCategory.CREDENTIAL.value,
            ),
        )
    )
    report = SecurityReportAdapter().adapt(assessment)
    assert "production-role finding" in report.executive_summary
    assert "test, fixture, or unknown-role" in report.executive_summary
    assert report.finding_summary.production_finding_count == 1
    assert report.finding_summary.test_finding_count == 1
    assert report.finding_summary.all_finding_count == 2


def test_test_only_executive_summary() -> None:
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_CREDENTIAL_LITERAL,
                path="test/fixtures.properties",
                finding_id="test-cred",
                classification="test",
                category=SecurityCategory.CREDENTIAL.value,
            ),
        )
    )
    report = SecurityReportAdapter().adapt(assessment)
    assert "No production-role findings" in report.executive_summary
    assert "test or fixture" in report.executive_summary
    assert report.finding_summary.production_finding_count == 0


def test_unknown_only_executive_summary() -> None:
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_CREDENTIAL_LITERAL,
                path="misc/config.properties",
                finding_id="unk",
                classification="unknown",
                category=SecurityCategory.CREDENTIAL.value,
            ),
        )
    )
    report = SecurityReportAdapter().adapt(assessment)
    assert "could not be classified" in report.executive_summary
    assert report.finding_summary.unknown_finding_count == 1


def test_partial_evidence_executive_summary() -> None:
    evidence = _evidence(
        status=RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED,
        diagnostics=(
            RepositorySensitiveDiagnostic(
                diagnostic_id="d1",
                diagnostic_code="malformed_yaml",
                message="Malformed YAML at application.yml",
                path="application.yml",
            ),
        ),
    )
    report = SecurityReportAdapter().adapt(_assemble(evidence=evidence))
    assert "Evidence collection was partial" in report.executive_summary
    assert any(item.diagnostic_code == "malformed_yaml" for item in report.diagnostics)
    assert all(
        item.finding_id != "d1" for item in report.finding_summary.production_findings
    )


def test_insufficient_and_failed_summaries() -> None:
    insufficient = SecurityReportAdapter().adapt(
        SecurityAssessmentAssembler().assemble_insufficient_evidence(
            repository_id="repo:x"
        )
    )
    assert "unavailable or insufficient" in insufficient.executive_summary
    failed = SecurityReportAdapter().adapt(
        SecurityAssessmentAssembler().assemble_failed(repository_id="repo:x")
    )
    assert "did not complete successfully" in failed.executive_summary


def test_projection_without_regeneration() -> None:
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_PRIVATE_KEY_MATERIAL,
                path="tls/server.key",
                finding_id="pk",
            ),
        )
    )
    report = SecurityReportAdapter().adapt(assessment)
    assert {item.theme_id for item in report.themes} <= {
        item.theme_id for item in assessment.themes
    }
    assert {item.conclusion_id for item in report.conclusions} <= {
        item.conclusion_id for item in assessment.conclusions
    }
    assert {item.recommendation_id for item in report.recommendations} <= {
        item.recommendation_id for item in assessment.recommendations
    }
    assert SecurityThemeKind.PRIVATE_KEY_EXPOSURE.value in {
        item.kind for item in report.themes
    }
    assert SecurityConclusionKind.PRIVATE_KEY_MATERIAL_DETECTED.value in {
        item.kind for item in report.conclusions
    }
    assert SecurityRecommendationKind.REMOVE_COMMITTED_PRIVATE_KEY_MATERIAL.value in {
        item.kind for item in report.recommendations
    }
    assert report.recommendation_groups
    assert report.hotspots_total == len(assessment.hotspot_inventory.hotspots)


def test_bounds_and_truncation() -> None:
    report = SecurityReportAdapter().adapt(
        _assemble(
            findings=(
                _finding(
                    rule_id=RULE_PRIVATE_KEY_MATERIAL,
                    path="tls/server.key",
                    finding_id="pk",
                ),
            )
        ),
        theme_limit=THEME_DISPLAY_LIMIT,
        conclusion_limit=CONCLUSION_DISPLAY_LIMIT,
        recommendation_limit=RECOMMENDATION_DISPLAY_LIMIT,
        hotspot_limit=HOTSPOT_DISPLAY_LIMIT,
        finding_limit=FINDING_DISPLAY_LIMIT,
        diagnostic_limit=DIAGNOSTIC_DISPLAY_LIMIT,
        limitation_limit=LIMITATION_DISPLAY_LIMIT,
    )
    assert len(report.themes) <= THEME_DISPLAY_LIMIT
    assert len(report.conclusions) <= CONCLUSION_DISPLAY_LIMIT
    assert len(report.recommendations) <= RECOMMENDATION_DISPLAY_LIMIT
    assert len(report.hotspots) <= HOTSPOT_DISPLAY_LIMIT
    assert len(report.diagnostics) <= DIAGNOSTIC_DISPLAY_LIMIT
    assert len(report.limitations) <= LIMITATION_DISPLAY_LIMIT
    assert len(report.traceability.sample_edges) <= TRACE_SAMPLE_LIMIT


def test_privacy_no_sensitive_leakage() -> None:
    report = SecurityReportAdapter().adapt(
        _assemble(
            findings=(
                _finding(
                    rule_id=RULE_PRIVATE_KEY_MATERIAL,
                    path="tls/server.key",
                    finding_id="pk",
                ),
            )
        )
    )
    blob = dumps_stable_json(report.model_dump(mode="json")).lower()
    assert "begin private" not in blob
    assert "fp1" not in blob
    assert "/users/" not in blob
    assert "password=secret" not in blob
    for claim in _FORBIDDEN_CLAIMS:
        assert claim not in blob


def test_json_optional_and_deterministic() -> None:
    report = SecurityReportAdapter().adapt(_assemble())
    with_sec = build_assessment_json_document(_report_input(security_report=report))
    without = build_assessment_json_document(_report_input(security_report=None))
    assert ASSESSMENT_JSON_SCHEMA_VERSION == with_sec["schema_version"]
    assert "security" in with_sec["assessment"]
    assert "security" not in without["assessment"]
    left = dumps_stable_json(with_sec)
    right = dumps_stable_json(
        build_assessment_json_document(_report_input(security_report=report))
    )
    assert left == right
    assert "all_finding_summaries" not in left


def test_html_section_placement_and_zero_state() -> None:
    report = SecurityReportAdapter().adapt(_assemble())
    view = build_html_report_view_model(_report_input(security_report=report))
    html = HtmlReportRenderer().render(view)
    assert 'id="security-assessment"' in html
    assert "Security Assessment" in html
    assert "no production-role findings" in html.lower()
    assert "security passed" not in html.lower()
    assert "vulnerability-free" not in html.lower()
    assert "<table></table>" not in html
    assert html == HtmlReportRenderer().render(view)


def test_html_partial_evidence_and_separation() -> None:
    evidence = _evidence(
        status=RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED,
        diagnostics=(
            RepositorySensitiveDiagnostic(
                diagnostic_id="d1",
                diagnostic_code="malformed_yaml",
                message="Malformed YAML at application.yml",
                path="application.yml",
            ),
        ),
    )
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_PRIVATE_KEY_MATERIAL,
                path="tls/server.key",
                finding_id="pk",
            ),
            _finding(
                rule_id=RULE_CREDENTIAL_LITERAL,
                path="test/fixtures.properties",
                finding_id="t1",
                classification="test",
                category=SecurityCategory.CREDENTIAL.value,
            ),
        ),
        evidence=evidence,
    )
    report = SecurityReportAdapter().adapt(assessment)
    html = HtmlReportRenderer().render(
        build_html_report_view_model(_report_input(security_report=report))
    )
    assert "Production-Primary Findings" in html
    assert "Additional Test/Fixture/Unknown Observations" in html
    assert "partially_succeeded" in html
    # Diagnostic codes remain in report artifacts / coverage counts, not leadership HTML.


def test_html_hidden_when_disabled() -> None:
    html = HtmlReportRenderer().render(
        build_html_report_view_model(_report_input(security_report=None))
    )
    assert 'id="security-assessment"' not in html
    assert "Security Assessment" not in html


def test_assessment_unchanged_after_adapt() -> None:
    assessment = _assemble()
    assert assessment.status is SecurityAssessmentStatus.SUCCEEDED
    assert assessment.section_version == "1.3.0"
    SecurityReportAdapter().adapt(assessment)
    assert assessment.status is SecurityAssessmentStatus.SUCCEEDED
    assert assessment.section_version == "1.3.0"
