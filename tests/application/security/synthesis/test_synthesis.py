"""Security synthesis tests (Phase 4.5.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.application.security.assessment.artifacts import (
    security_assessment_payload,
    write_security_assessment_artifact,
)
from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.application.security.assessment.inventory import execution_facts_from_status_map
from codestrata.application.security.synthesis import synthesize_security
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
from codestrata.domain.security.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.security.assessment.models import (
    SecurityDiagnosticsSummary,
    SecurityEvidenceSummary,
    SecurityFindingInventory,
    SecurityHotspotInventory,
    SecurityRuleInventory,
)
from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    RULE_AUTHENTICATION_DISABLED,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)
from codestrata.domain.security.synthesis.enums import (
    SecurityConclusionKind,
    SecurityRecommendationKind,
    SecuritySynthesisStatus,
    SecurityThemeKind,
)
from codestrata.domain.security.taxonomy import SecurityCategory
from codestrata.services.artifact_serialization import dumps_stable_json


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


def _facts_all_ok():
    return execution_facts_from_status_map(
        {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
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


def test_schema_and_synthesis_gate(tmp_path: Path) -> None:
    assert SECTION_SCHEMA_VERSION == "1.3.0"
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [assessment.sections.security]
        enabled = true
        include_synthesis = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.assessment.sections.security.include_synthesis is False

    off = _assemble(include_synthesis=False)
    assert off.section_version == "1.3.0"
    assert off.synthesis.status is SecuritySynthesisStatus.NOT_REQUESTED
    assert off.themes == ()
    assert off.conclusions == ()
    assert off.recommendations == ()
    assert off.rule_inventory.entries  # inventory retained
    assert off.finding_inventory.total_finding_count == 0

    on = _assemble()
    assert on.synthesis.status in {
        SecuritySynthesisStatus.SUCCEEDED,
        SecuritySynthesisStatus.EMPTY,
    }
    assert on.metadata.get("assessment_milestone") == "4.5.5"
    assert on.metadata.get("synthesis_version") == "1.0.0"


def test_zero_findings_landscape_and_no_production_wording() -> None:
    section = _assemble()
    kinds = {item.kind for item in section.themes}
    assert SecurityThemeKind.SECURITY_HYGIENE_LANDSCAPE in kinds
    assert SecurityThemeKind.NO_PRODUCTION_FINDINGS in kinds
    conclusion_kinds = {item.kind for item in section.conclusions}
    assert (
        SecurityConclusionKind.NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE
        in conclusion_kinds
    )
    text = dumps_stable_json(security_assessment_payload(section)).lower()
    assert "no production-role findings" in text
    assert "security passed" not in text
    assert "no vulnerabilities" not in text
    assert "secure repository" not in text
    assert any(
        item.kind
        is SecurityRecommendationKind.ACKNOWLEDGE_NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE
        for item in section.recommendations
    )


def test_rule_themes_and_recommendations() -> None:
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="tls/server.key",
            finding_id="pk",
        ),
        _finding(
            rule_id=RULE_CREDENTIAL_LITERAL,
            path="app.properties",
            finding_id="cred",
            category=SecurityCategory.CREDENTIAL.value,
        ),
        _finding(
            rule_id=RULE_PLACEHOLDER_CREDENTIAL,
            path="app.properties",
            finding_id="ph",
            category=SecurityCategory.CREDENTIAL.value,
        ),
        _finding(
            rule_id=RULE_TLS_VERIFICATION_DISABLED,
            path="tls.properties",
            finding_id="tls",
            category=SecurityCategory.TRANSPORT_SECURITY.value,
        ),
        _finding(
            rule_id=RULE_HOSTNAME_VERIFICATION_DISABLED,
            path="tls.properties",
            finding_id="host",
            category=SecurityCategory.TRANSPORT_SECURITY.value,
        ),
        _finding(
            rule_id=RULE_AUTHENTICATION_DISABLED,
            path="auth.properties",
            finding_id="auth",
            category=SecurityCategory.AUTHENTICATION.value,
        ),
        _finding(
            rule_id=RULE_PERMISSIVE_CORS_ORIGIN,
            path="cors.properties",
            finding_id="cors",
            category=SecurityCategory.CONFIGURATION.value,
        ),
        _finding(
            rule_id=RULE_DEBUG_ENABLED,
            path="debug.properties",
            finding_id="dbg",
            category=SecurityCategory.CONFIGURATION.value,
        ),
    )
    section = _assemble(findings=findings)
    theme_kinds = {item.kind for item in section.themes}
    assert SecurityThemeKind.PRIVATE_KEY_EXPOSURE in theme_kinds
    assert SecurityThemeKind.CREDENTIAL_AND_SECRET_HYGIENE in theme_kinds
    assert SecurityThemeKind.PLACEHOLDER_CREDENTIALS in theme_kinds
    assert SecurityThemeKind.TRANSPORT_SECURITY_CONFIGURATION in theme_kinds
    assert SecurityThemeKind.AUTHENTICATION_CONFIGURATION in theme_kinds
    assert SecurityThemeKind.PERMISSIVE_CORS_CONFIGURATION in theme_kinds
    assert SecurityThemeKind.DEBUG_CONFIGURATION in theme_kinds
    rec_kinds = {item.kind for item in section.recommendations}
    assert SecurityRecommendationKind.REMOVE_COMMITTED_PRIVATE_KEY_MATERIAL in rec_kinds
    assert SecurityRecommendationKind.ROTATE_AND_REPLACE_LITERAL_CREDENTIALS in rec_kinds
    assert SecurityRecommendationKind.REPLACE_PLACEHOLDER_CREDENTIALS in rec_kinds
    assert SecurityRecommendationKind.ENABLE_TLS_VERIFICATION in rec_kinds
    assert SecurityRecommendationKind.ENABLE_HOSTNAME_VERIFICATION in rec_kinds
    assert SecurityRecommendationKind.ENABLE_AUTHENTICATION in rec_kinds
    assert SecurityRecommendationKind.RESTRICT_CORS_ORIGINS in rec_kinds
    assert SecurityRecommendationKind.DISABLE_DEBUG_CONFIGURATION in rec_kinds
    # Dedup: one private-key recommendation even if more findings appear later.
    assert (
        sum(
            1
            for item in section.recommendations
            if item.kind
            is SecurityRecommendationKind.REMOVE_COMMITTED_PRIVATE_KEY_MATERIAL
        )
        == 1
    )


def test_source_role_separation() -> None:
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="prod.key",
            finding_id="prod",
        ),
        _finding(
            rule_id=RULE_PLACEHOLDER_CREDENTIAL,
            path="src/test/resources/app.properties",
            finding_id="test",
            classification="test",
            category=SecurityCategory.CREDENTIAL.value,
        ),
        _finding(
            rule_id=RULE_DEBUG_ENABLED,
            path="vendor/odd.properties",
            finding_id="unk",
            classification="unknown",
            category=SecurityCategory.CONFIGURATION.value,
        ),
    )
    section = _assemble(findings=findings)
    assert "prod" in section.finding_ids
    assert "test" not in section.finding_ids
    assert "unk" not in section.finding_ids
    assert set(section.all_finding_ids) == {"prod", "test", "unk"}
    theme_kinds = {item.kind for item in section.themes}
    assert SecurityThemeKind.TEST_FIXTURE_OBSERVATIONS in theme_kinds
    assert SecurityThemeKind.UNKNOWN_ROLE_OBSERVATIONS in theme_kinds
    conclusion_kinds = {item.kind for item in section.conclusions}
    assert SecurityConclusionKind.UNKNOWN_ROLE_FINDINGS_PRESENT in conclusion_kinds
    rec_kinds = {item.kind for item in section.recommendations}
    assert SecurityRecommendationKind.CLASSIFY_UNKNOWN_ROLE_FILES in rec_kinds
    assert (
        SecurityRecommendationKind.REVIEW_TEST_FIXTURE_SECURITY_OBSERVATIONS
        in rec_kinds
    )


def test_partial_evidence_and_hotspots() -> None:
    evidence = _evidence(
        status=RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED,
        diagnostics=(
            RepositorySensitiveDiagnostic(
                diagnostic_id="d1",
                diagnostic_code="malformed_yaml",
                message="Malformed YAML at bad.yml",
                path="bad.yml",
            ),
        ),
    )
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="shared/secrets.pem",
            finding_id="a",
        ),
        _finding(
            rule_id=RULE_CREDENTIAL_LITERAL,
            path="shared/secrets.pem",
            finding_id="b",
            category=SecurityCategory.CREDENTIAL.value,
        ),
    )
    section = _assemble(findings=findings, evidence=evidence)
    assert section.status is SecurityAssessmentStatus.PARTIALLY_SUCCEEDED
    theme_kinds = {item.kind for item in section.themes}
    assert SecurityThemeKind.PARTIAL_EVIDENCE_COVERAGE in theme_kinds
    assert SecurityThemeKind.FINDING_CONCENTRATION in theme_kinds
    rec_kinds = {item.kind for item in section.recommendations}
    assert SecurityRecommendationKind.CORRECT_MALFORMED_CONFIGURATION in rec_kinds
    assert section.diagnostics_summary.evidence_diagnostics
    assert all(
        item.finding_id != "d1" for item in section.all_finding_summaries
    )


def test_insufficient_and_disabled_synthesis() -> None:
    result = synthesize_security(
        repository_id="repo:x",
        pack_enabled=True,
        section_status=SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE,
        finding_summaries=(),
        finding_inventory=SecurityFindingInventory(),
        hotspot_inventory=SecurityHotspotInventory(),
        evidence_summary=SecurityEvidenceSummary(),
        diagnostics_summary=SecurityDiagnosticsSummary(),
        rule_inventory=SecurityRuleInventory(),
    )
    assert result.status is SecuritySynthesisStatus.INSUFFICIENT_EVIDENCE

    disabled = synthesize_security(
        repository_id="repo:x",
        pack_enabled=False,
        section_status=SecurityAssessmentStatus.DISABLED,
        finding_summaries=(),
        finding_inventory=SecurityFindingInventory(),
        hotspot_inventory=SecurityHotspotInventory(),
        evidence_summary=SecurityEvidenceSummary(),
        diagnostics_summary=SecurityDiagnosticsSummary(),
        rule_inventory=SecurityRuleInventory(),
    )
    assert disabled.status is SecuritySynthesisStatus.DISABLED


def test_determinism_privacy_and_failure_isolation(tmp_path: Path) -> None:
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="tls/server.key",
            finding_id="f1",
        ),
        _finding(
            rule_id=RULE_CREDENTIAL_LITERAL,
            path="app.properties",
            finding_id="f2",
            category=SecurityCategory.CREDENTIAL.value,
        ),
    )
    left = _assemble(findings=findings)
    right = _assemble(findings=(findings[1], findings[0]))
    assert dumps_stable_json(security_assessment_payload(left)) == dumps_stable_json(
        security_assessment_payload(right)
    )
    text = write_security_assessment_artifact(left, tmp_path).path.read_text(
        encoding="utf-8"
    )
    assert "BEGIN PRIVATE" not in text
    assert "/Users/" not in text
    assert "fingerprint" not in text.lower() or "evidence_fingerprint" in text
    # Customer-facing narrative fields should not dump value fingerprints.
    for conclusion in left.conclusions:
        assert "fp1" not in conclusion.summary
        assert "fp1" not in conclusion.technical_interpretation
    assert '"score"' not in text or "recommendation_count" in text

    with patch(
        "codestrata.application.security.assessment.assembler.synthesize_security",
        side_effect=RuntimeError("boom"),
    ):
        failed = _assemble(findings=findings)
    assert failed.synthesis.status is SecuritySynthesisStatus.FAILED
    assert set(failed.all_finding_ids) == {"f1", "f2"}
    assert failed.rule_inventory.entries
    assert any("synthesis_failed" in item for item in failed.diagnostics)
