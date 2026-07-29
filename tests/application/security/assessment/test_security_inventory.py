"""Security assessment inventory tests (Phase 4.5.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.security.assessment.artifacts import (
    security_assessment_payload,
    write_security_assessment_artifact,
)
from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.application.security.assessment.inventory import (
    build_diagnostics_summary,
    build_evidence_summary,
    build_finding_inventory,
    build_finding_references,
    build_hotspot_inventory,
    build_rule_inventory,
    execution_facts_from_status_map,
    map_source_role,
)
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationFormat,
    ConfigurationKeyFamily,
    ContentClassification,
    InspectionStatus,
    PlaceholderStatus,
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
from codestrata.domain.security.assessment.enums import (
    SecurityAssessmentStatus,
    SecuritySourceRole,
)
from codestrata.domain.security.assessment.identifiers import (
    MAX_SECURITY_HOTSPOTS,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_PRIVATE_KEY_MATERIAL,
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
    title: str | None = None,
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=title or f"{rule_id} at {path}",
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
            SensitiveArtifactEvidence(
                evidence_id="art:tls/server.crt",
                path="tls/server.crt",
                kind=SensitiveArtifactKind.PUBLIC_CERTIFICATE,
                inspection_status=InspectionStatus.INSPECTED,
                content_classifications=(
                    ContentClassification.PUBLIC_CERTIFICATE_MATERIAL,
                ),
                classification=SourceClassification.SOURCE,
                provenance=_prov(),
            ),
            SensitiveArtifactEvidence(
                evidence_id="art:store/app.jks",
                path="store/app.jks",
                kind=SensitiveArtifactKind.KEYSTORE,
                inspection_status=InspectionStatus.METADATA_ONLY,
                content_classifications=(ContentClassification.UNKNOWN,),
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
            ConfigurationFactEvidence(
                evidence_id="cfg:app.properties:token",
                path="app.properties",
                classification=SourceClassification.SOURCE,
                format=ConfigurationFormat.PROPERTIES,
                normalized_key="token",
                key_family=ConfigurationKeyFamily.SECRET,
                redacted_preview="${TOKEN}",
                value_kind=ValueKind.ENVIRONMENT_REFERENCE,
                placeholder_status=PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
                provenance=_prov(),
            ),
            ConfigurationFactEvidence(
                evidence_id="cfg:app.properties:api_key",
                path="app.properties",
                classification=SourceClassification.SOURCE,
                format=ConfigurationFormat.PROPERTIES,
                normalized_key="api_key",
                key_family=ConfigurationKeyFamily.CREDENTIAL,
                redacted_preview="CHANGE_ME",
                value_kind=ValueKind.PLACEHOLDER,
                placeholder_status=PlaceholderStatus.PLACEHOLDER_LITERAL,
                provenance=_prov(),
            ),
        ),
        coverage=RepositorySensitiveEvidenceCoverage(
            candidate_files_discovered=5,
            files_inspected=4,
            metadata_only_files=1,
            structured_files_parsed=1,
            malformed_files=1 if diagnostics else 0,
            unsupported_binaries=0,
            skipped_files=0,
            configuration_facts_collected=3,
            placeholder_facts=1,
            formats_represented=("properties",),
        ),
        diagnostics=diagnostics,
        evidence_fingerprint="deadbeef",
    )


def _facts_all_ok() -> tuple:
    return execution_facts_from_status_map(
        {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    )


def test_schema_version_is_1_2_0() -> None:
    assert SECTION_SCHEMA_VERSION == "1.3.0"
    section = SecurityAssessmentAssembler().assemble_empty(repository_id="repo:x")
    assert section.section_version == "1.3.0"
    assert section.metadata.get("assessment_milestone") == "4.5.5"


def test_production_primary_and_all_findings() -> None:
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="tls/server.key",
            finding_id="f-prod",
            classification="source",
        ),
        _finding(
            rule_id=RULE_DEBUG_ENABLED,
            path="src/test/resources/application.properties",
            finding_id="f-test",
            classification="test",
            category=SecurityCategory.CONFIGURATION.value,
        ),
        _finding(
            rule_id=RULE_CREDENTIAL_LITERAL,
            path="vendor/odd/config.properties",
            finding_id="f-unk",
            classification="unknown",
            category=SecurityCategory.CREDENTIAL.value,
        ),
    )
    refs = build_finding_references(findings)
    inventory = build_finding_inventory(refs)
    assert inventory.production.finding_count == 1
    assert inventory.test.finding_count == 1
    assert inventory.unknown.finding_count == 1
    assert map_source_role("unknown") is SecuritySourceRole.UNKNOWN

    section = SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert section.finding_ids == ("f-prod",)
    assert set(section.all_finding_ids) == {"f-prod", "f-test", "f-unk"}
    assert len(section.finding_ids) == 1
    assert len(section.all_finding_ids) == 3
    assert len(set(section.all_finding_ids)) == 3
    assert section.finding_inventory.unknown.finding_ids == ("f-unk",)
    assert section.execution_summary.visible_finding_count == 1
    assert section.execution_summary.total_finding_count == 3


def test_evidence_summary_reconciles_without_secret_claims() -> None:
    evidence = _evidence(
        diagnostics=(
            RepositorySensitiveDiagnostic(
                diagnostic_id="diag:malformed",
                diagnostic_code="malformed_yaml",
                message="Malformed YAML at config/broken.yml",
                path="config/broken.yml",
            ),
        )
    )
    summary = build_evidence_summary(evidence)
    assert summary.candidate_artifacts_discovered == 5
    assert summary.private_key_signatures_observed == 1
    assert summary.public_certificate_signatures_observed == 1
    assert summary.credential_sensitive_facts == 3
    assert summary.environment_reference_facts == 1
    assert summary.placeholder_facts == 1
    assert summary.evidence_diagnostic_count == 1
    assert "do not prove" in summary.note.lower()

    section = SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=evidence,
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert section.status is SecurityAssessmentStatus.SUCCEEDED
    assert section.evidence_summary.private_key_signatures_observed == 1
    assert section.all_finding_ids == ()
    assert len(section.diagnostics_summary.evidence_diagnostics) == 1
    assert section.diagnostics_summary.evidence_diagnostics[0].diagnostic_code == (
        "malformed_yaml"
    )
    # Diagnostics are not Findings.
    assert all(
        item.finding_id != "diag:malformed" for item in section.all_finding_summaries
    )


def test_rule_inventory_includes_zero_finding_rules() -> None:
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="tls/server.key",
            finding_id="f1",
        ),
    )
    facts = execution_facts_from_status_map(
        {
            **{rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS},
            RULE_PRIVATE_KEY_MATERIAL: "matched",
            RULE_DEBUG_ENABLED: "failed",
        },
        diagnostics_by_rule={
            RULE_DEBUG_ENABLED: ("isolated rule exception",),
        },
    )
    section = SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=facts,
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)
    by_id = {item.rule_id: item for item in section.rule_inventory.entries}
    assert by_id[RULE_PRIVATE_KEY_MATERIAL].finding_count == 1
    assert by_id[RULE_PRIVATE_KEY_MATERIAL].production_finding_count == 1
    assert by_id[RULE_CREDENTIAL_LITERAL].finding_count == 0
    assert by_id[RULE_CREDENTIAL_LITERAL].executed is True
    assert by_id[RULE_DEBUG_ENABLED].evaluation_status == "failed"
    assert by_id[RULE_DEBUG_ENABLED].diagnostic_count == 1
    assert section.status is SecurityAssessmentStatus.PARTIALLY_SUCCEEDED
    assert len(section.diagnostics_summary.rule_diagnostics) == 1


def test_category_severity_source_role_inventories() -> None:
    findings = (
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="a.key",
            finding_id="a",
            severity=FindingSeverity.CRITICAL,
        ),
        _finding(
            rule_id=RULE_DEBUG_ENABLED,
            path="tests/app.properties",
            finding_id="b",
            classification="test",
            severity=FindingSeverity.MEDIUM,
            category=SecurityCategory.CONFIGURATION.value,
        ),
    )
    section = SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    severities = {item.key: item.count for item in section.severity_inventory.buckets}
    categories = {item.key: item.count for item in section.category_inventory.buckets}
    assert severities == {"critical": 1, "medium": 1}
    assert categories[SecurityCategory.PRIVATE_KEY.value] == 1
    assert categories[SecurityCategory.CONFIGURATION.value] == 1
    assert section.finding_inventory.production.finding_count == 1
    assert section.finding_inventory.test.finding_count == 1


def test_hotspot_ranking_bounds_and_neutral_wording() -> None:
    findings = [
        _finding(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            path="prod/secrets.pem",
            finding_id=f"p{i}",
            severity=FindingSeverity.HIGH,
        )
        for i in range(3)
    ]
    findings.append(
        _finding(
            rule_id=RULE_CREDENTIAL_LITERAL,
            path="prod/secrets.pem",
            finding_id="cred",
            severity=FindingSeverity.CRITICAL,
            category=SecurityCategory.CREDENTIAL.value,
        )
    )
    findings.append(
        _finding(
            rule_id=RULE_DEBUG_ENABLED,
            path="tests/debug.properties",
            finding_id="t1",
            classification="test",
            severity=FindingSeverity.MEDIUM,
            category=SecurityCategory.CONFIGURATION.value,
        )
    )
    # Extra paths to verify bound.
    for i in range(25):
        findings.append(
            _finding(
                rule_id=RULE_DEBUG_ENABLED,
                path=f"misc/file-{i:02d}.properties",
                finding_id=f"m{i}",
                classification="unknown",
                severity=FindingSeverity.LOW,
                category=SecurityCategory.CONFIGURATION.value,
            )
        )
    refs = build_finding_references(findings)
    hotspots = build_hotspot_inventory(refs)
    assert len(hotspots.hotspots) <= MAX_SECURITY_HOTSPOTS
    assert hotspots.hotspots[0].path == "prod/secrets.pem"
    assert hotspots.hotspots[0].production_finding_count == 4
    assert "high risk" not in hotspots.note.lower()
    assert "vulnerable" not in hotspots.hotspots[0].label.lower()
    assert "critical" not in hotspots.hotspots[0].label.lower()
    assert hotspots.hotspots[0].label == "Security finding hotspot"
    assert set(hotspots.hotspots[0].finding_ids).issubset(
        {item.finding_id for item in refs}
    )


def test_lifecycle_status_precision() -> None:
    assembler = SecurityAssessmentAssembler()
    assert (
        assembler.assemble_disabled(repository_id="r").status
        is SecurityAssessmentStatus.DISABLED
    )
    assert (
        assembler.assemble_not_requested(repository_id="r").status
        is SecurityAssessmentStatus.NOT_REQUESTED
    )
    assert (
        assembler.assemble_insufficient_evidence(repository_id="r").status
        is SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE
    )
    assert (
        assembler.assemble_failed(repository_id="r").status
        is SecurityAssessmentStatus.FAILED
    )
    assert (
        assembler.assemble_not_applicable(repository_id="r").status
        is SecurityAssessmentStatus.NOT_APPLICABLE
    )

    ok = assembler.assemble(
        repository_id="r",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert ok.status is SecurityAssessmentStatus.SUCCEEDED
    assert ok.all_finding_ids == ()

    with_findings = assembler.assemble(
        repository_id="r",
        findings=(
            _finding(
                rule_id=RULE_PRIVATE_KEY_MATERIAL,
                path="a.key",
                finding_id="f1",
            ),
        ),
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert with_findings.status is SecurityAssessmentStatus.SUCCEEDED

    partial_evidence = assembler.assemble(
        repository_id="r",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(
            status=RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED
        ),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert partial_evidence.status is SecurityAssessmentStatus.PARTIALLY_SUCCEEDED

    failed_rule_facts = execution_facts_from_status_map(
        {
            **{rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS},
            RULE_DEBUG_ENABLED: "failed",
        },
        diagnostics_by_rule={RULE_DEBUG_ENABLED: ("boom",)},
    )
    partial_rules = assembler.assemble(
        repository_id="r",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=failed_rule_facts,
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert partial_rules.status is SecurityAssessmentStatus.PARTIALLY_SUCCEEDED

    all_failed = execution_facts_from_status_map(
        {rule_id: "failed" for rule_id in HYGIENE_RULE_IDS},
        diagnostics_by_rule={
            rule_id: ("fail",) for rule_id in HYGIENE_RULE_IDS
        },
    )
    failed = assembler.assemble(
        repository_id="r",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=all_failed,
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert failed.status is SecurityAssessmentStatus.FAILED


def test_privacy_and_determinism(tmp_path: Path) -> None:
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
    shuffled = (findings[1], findings[0])
    left = SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
        configuration_payload="stable-config",
    )
    right = SecurityAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=shuffled,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        repository_sensitive_evidence=_evidence(),
        rule_execution_facts=_facts_all_ok(),
        rules_executed=len(HYGIENE_RULE_IDS),
        configuration_payload="stable-config",
    )
    assert left.assessment_id == right.assessment_id
    assert dumps_stable_json(security_assessment_payload(left)) == dumps_stable_json(
        security_assessment_payload(right)
    )
    written = write_security_assessment_artifact(left, tmp_path)
    text = written.path.read_text(encoding="utf-8")
    assert written.path.read_text(encoding="utf-8") == text
    assert "BEGIN PRIVATE KEY" not in text
    assert "supersecret" not in text
    assert "/Users/" not in text
    assert '"risk_score"' not in text
    assert '"security_score"' not in text
    assert '"cvss"' not in text
    assert left.section_version == "1.3.0"


def test_diagnostics_remain_separate() -> None:
    evidence = _evidence(
        diagnostics=(
            RepositorySensitiveDiagnostic(
                diagnostic_id="d1",
                diagnostic_code="malformed_yaml",
                message="bad yaml",
                path="bad.yml",
            ),
        )
    )
    facts = execution_facts_from_status_map(
        {
            **{rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS},
            RULE_DEBUG_ENABLED: "failed",
        },
        diagnostics_by_rule={RULE_DEBUG_ENABLED: ("rule blew up",)},
    )
    summary = build_diagnostics_summary(
        evidence=evidence,
        execution_facts=facts,
        assessment_diagnostics=("inventory assembly note",),
    )
    assert len(summary.evidence_diagnostics) == 1
    assert len(summary.rule_diagnostics) == 1
    assert len(summary.assessment_diagnostics) == 1
    inventory = build_rule_inventory(
        refs=build_finding_references(()),
        execution_facts=facts,
    )
    assert inventory.entries  # still present
