"""Epic 3 Slice 3.6 — Security Intelligence section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.application.security.assessment.inventory import execution_facts_from_status_map
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
    RepositorySensitiveEvidenceCoverage,
    SensitiveArtifactEvidence,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence
from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    RULE_CREDENTIAL_LITERAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)
from codestrata.domain.security.taxonomy import SecurityCategory
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.models import EvidenceRefView, FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.security import (
    SecurityReportAdapter,
    build_security_intelligence,
)


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _facts_all_ok():
    return execution_facts_from_status_map(
        {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    )


def _evidence() -> AggregatedRepositorySensitiveEvidence:
    return AggregatedRepositorySensitiveEvidence(
        repository_id="fixture",
        status=RepositorySensitiveParseStatus.SUCCEEDED,
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
            malformed_files=0,
            configuration_facts_collected=1,
            formats_represented=("properties",),
        ),
        diagnostics=(),
        evidence_fingerprint="deadbeef",
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


def _assemble(*, findings=(), evidence=None, include_synthesis=True):
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
        configuration_payload="sec-intel",
    )


def _succeeded_report():
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_PRIVATE_KEY_MATERIAL,
                path="tls/server.key",
                finding_id="pk",
            ),
            _finding(
                rule_id=RULE_TLS_VERIFICATION_DISABLED,
                path="app/settings.py",
                finding_id="tls",
                category=SecurityCategory.TRANSPORT_SECURITY.value,
            ),
        )
    )
    return SecurityReportAdapter().adapt(assessment)


def test_build_security_intelligence_groups_and_excludes_others() -> None:
    report = _succeeded_report()
    pk = FindingView(
        finding_id="f-pk",
        rule_id=RULE_PRIVATE_KEY_MATERIAL,
        title="Private key material",
        description="key observed",
        severity="high",
        category="security",
        affected_nodes=("tls/server.key",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:tls/server.key",
                kind="other",
                path="tls/server.key",
                snippet_text="[REDACTED]",
            ),
        ),
    )
    tls = FindingView(
        finding_id="f-tls",
        rule_id=RULE_TLS_VERIFICATION_DISABLED,
        title="TLS verification disabled",
        description="tls off",
        severity="high",
        category="security",
        affected_nodes=("app/settings.py",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:app/settings.py",
                kind="other",
                path="app/settings.py",
                snippet_text="[REDACTED]",
            ),
        ),
    )
    cve = FindingView(
        finding_id="f-cve",
        rule_id="security.cve-scan",
        title="CVE found",
        description="should exclude",
        severity="high",
        category="security",
    )
    penetration = FindingView(
        finding_id="f-pen",
        rule_id="security.tls-verification-disabled",
        title="Penetration test failed",
        description="should exclude by title",
        severity="high",
        category="security",
    )
    dependency = FindingView(
        finding_id="f-dep",
        rule_id="dependency.unresolved-version",
        title="Unresolved",
        description="dep",
        severity="medium",
        category="dependency",
    )
    architecture = FindingView(
        finding_id="f-arch",
        rule_id="architecture.dependency-cycle",
        title="Cycle",
        description="cycle",
        severity="medium",
        category="architecture",
    )
    rec = RecommendationView(
        recommendation_id="r-sec",
        title="Remove private key",
        summary="Remove committed key material",
        rationale="Security",
        priority="high",
        category="security",
        related_finding_ids=("f-pk",),
    )
    other = RecommendationView(
        recommendation_id="r-dep",
        title="Pin versions",
        summary="Pin",
        rationale="Dependency",
        priority="high",
        category="dependency",
        related_finding_ids=("f-dep",),
    )
    intel = build_security_intelligence(
        report,
        findings=(pk, tls, cve, penetration, dependency, architecture),
        recommendations=(rec, other),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-pk", "f-tls"}
    assert {item.recommendation_id for item in intel.recommendations} == {"r-sec"}
    assert intel.empty_findings_message is None
    assert intel.artifacts
    assert all(row.path is None or not row.path.startswith("/") for row in intel.artifacts)
    assert any("private key" in row.classification.lower() for row in intel.artifacts)
    assert intel.config_observations
    assert any("tls" in row.label.lower() for row in intel.config_observations)
    joined = " ".join(intel.limitations).lower()
    assert "runtime security" in joined
    assert "cve analysis" in joined
    assert "penetration testing" in joined
    assert "dast" in joined
    assert intel.confidence_label in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Confidence unavailable",
    }


def test_zero_findings_not_secure() -> None:
    assessment = _assemble(findings=())
    report = SecurityReportAdapter().adapt(assessment)
    intel = build_security_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.finding_count == 0
    assert intel.findings == ()
    assert intel.empty_findings_message is not None
    lowered = intel.empty_findings_message.lower()
    assert "absence of findings" in lowered
    assert "secure" not in lowered or "absence of security risk" in lowered
    assert "low risk" not in lowered
    assert "no vulnerabilities" not in lowered
    overview = " ".join(
        f"{fact.label} {fact.value} {fact.note or ''}" for fact in intel.overview_facts
    ).lower()
    assert "zero findings do not mean" in overview or "not mean" in overview
    assert "secure" in overview  # note says not secure


def test_soft_claims_scrubbed_from_status_summary() -> None:
    report = _succeeded_report()
    mutated = report.model_copy(
        update={
            "status_summary": "Secure repository with low risk and no vulnerabilities.",
        }
    )
    intel = build_security_intelligence(mutated, findings=(), recommendations=())
    assert intel is not None
    lowered = intel.status_summary.lower()
    assert "secure repository" not in lowered
    assert "low risk" not in lowered
    assert "no vulnerabilities" not in lowered
    assert "static repository" in lowered or "repository-sensitive" in lowered
    assert "absence of security risk" in lowered


def test_absolute_paths_omitted_and_no_raw_secrets() -> None:
    report = _succeeded_report()
    pk = FindingView(
        finding_id="f-pk",
        rule_id=RULE_PRIVATE_KEY_MATERIAL,
        title="Private key material",
        description="-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC",
        severity="high",
        category="security",
        affected_nodes=("/Users/secret/tls/server.key",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:bad",
                kind="other",
                path="/Users/secret/tls/server.key",
                snippet_text="-----BEGIN PRIVATE KEY-----\nfakekeybody",
            ),
        ),
    )
    cred = FindingView(
        finding_id="f-cred",
        rule_id=RULE_CREDENTIAL_LITERAL,
        title="Credential literal",
        description="password=SuperSecretValue123",
        severity="high",
        category="security",
        affected_nodes=("config/app.properties",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:cred",
                kind="other",
                path="config/app.properties",
                snippet_text="password=SuperSecretValue123",
            ),
        ),
    )
    intel = build_security_intelligence(
        report,
        findings=(pk, cred),
        recommendations=(),
    )
    assert intel is not None
    rendered_paths = " ".join(
        filter(
            None,
            [*(row.path for row in intel.artifacts), *(row.path for row in intel.findings)],
        )
    )
    assert "/Users/secret" not in rendered_paths
    assert all(not (row.path or "").startswith("/") for row in intel.artifacts)
    assert all(not (row.path or "").startswith("file:") for row in intel.findings)
    # Redacted snippet must not carry secret bodies from unsafe EvidenceRef text.
    for obs in intel.config_observations:
        assert obs.redacted_snippet is None or "BEGIN PRIVATE KEY" not in (
            obs.redacted_snippet or ""
        )
        assert "SuperSecretValue123" not in (obs.redacted_snippet or "")
    for finding in intel.findings:
        assert finding.path != "/Users/secret/tls/server.key"


def test_html_security_intelligence_section(tmp_path: Path) -> None:
    report = _succeeded_report()
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["tls/server.key"],
            total_files=1,
        ),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        security_report=report,
    )
    document = build_html_report_view_model(report_input)
    assert document.security_intelligence is not None
    html = HtmlReportRenderer().render(document)
    assert 'id="security-intelligence"' in html
    assert 'id="security-assessment"' in html
    assert 'href="#security-intelligence"' in html
    assert "Security overview" in html
    assert "Limitations" in html
    assert "Confidence" in html
    lowered = html.lower()
    assert "secure repository" not in lowered
    assert "low risk" not in lowered
    assert "no vulnerabilities" not in lowered
    assert "runtime security" in lowered or "penetration testing" in lowered
    assert "cve analysis" in lowered
    assert "BEGIN PRIVATE KEY" not in html
    assert "SuperSecretValue123" not in html
    assert "/Users/" not in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    for anchor in (
        "technology-inventory",
        "architecture-intelligence",
        "technical-debt-intelligence",
        "dependency-intelligence",
        "security-intelligence",
    ):
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html


def test_build_returns_none_when_report_missing() -> None:
    assert build_security_intelligence(None) is None


def test_related_recommendation_subset_included() -> None:
    report = _succeeded_report()
    sec = FindingView(
        finding_id="f-sec",
        rule_id=RULE_PRIVATE_KEY_MATERIAL,
        title="Private key",
        description="x",
        severity="high",
        category="security",
    )
    related = RecommendationView(
        recommendation_id="r-related",
        title="Remove key",
        summary="Remove",
        rationale="Security",
        priority="high",
        category="maintainability",
        related_finding_ids=("f-sec",),
    )
    mixed = RecommendationView(
        recommendation_id="r-mixed",
        title="Mixed",
        summary="Mixed",
        rationale="Mixed",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-sec", "f-other"),
    )
    intel = build_security_intelligence(
        report,
        findings=(sec,),
        recommendations=(related, mixed),
    )
    assert intel is not None
    assert {item.recommendation_id for item in intel.recommendations} == {"r-related"}
