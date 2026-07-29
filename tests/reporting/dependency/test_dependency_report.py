"""Dependency report adapter and presentation tests (Phase 4.4.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.dependency.assessment.assembler import (
    DependencyAssessmentAssembler,
)
from codestrata.config import load_settings
from codestrata.domain.dependency.assessment.enums import DependencyAssessmentStatus
from codestrata.domain.dependency.ids import (
    RULE_DUPLICATE_DECLARATION,
    RULE_UNRESOLVED_VERSION,
)
from codestrata.domain.dependency.synthesis.enums import (
    DependencyConclusionKind,
    DependencyRecommendationKind,
)
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyDeclarationEvidence,
    DependencyEvidenceCoverage,
    DependencyManifestEvidence,
    DependencySourceLocation,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin, SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.dependency.adapter import DependencyReportAdapter
from codestrata.reporting.dependency.models import (
    DEPENDENCY_REPORT_SECTION_ID,
    DEPENDENCY_REPORT_SECTION_VERSION,
    DIAGNOSTIC_SAMPLE_LIMIT,
    FINDING_DISPLAY_LIMIT,
    TOP_MANIFEST_HOTSPOTS,
    TRACE_SAMPLE_LIMIT,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

_NONE_DETECTED = (
    "No production dependency hygiene findings were detected by the enabled "
    "repository-local rules."
)
_FORBIDDEN_CLAIMS = (
    "healthy",
    "secure",
    "low risk",
    "no dependency risk",
    "upgrades are unnecessary",
    "current",
    "supported forever",
)


def _provenance(path: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="dependency.test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="fixture",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
    )


def _decl(
    *,
    evidence_id: str,
    identity: str,
    path: str,
    kind: DependencyDeclarationKind = DependencyDeclarationKind.RUNTIME,
    classification: SourceClassification = SourceClassification.SOURCE,
    resolution: DependencyVersionResolutionStatus = (
        DependencyVersionResolutionStatus.RESOLVED
    ),
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    manifest_type: DependencyManifestType = DependencyManifestType.POM_XML,
    raw_version: str | None = "1.0.0",
    is_management: bool = False,
) -> DependencyDeclarationEvidence:
    return DependencyDeclarationEvidence(
        evidence_id=evidence_id,
        ecosystem=ecosystem,
        manifest_type=manifest_type,
        declaration_kind=kind,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=(
            raw_version
            if resolution is DependencyVersionResolutionStatus.RESOLVED
            else None
        ),
        version_availability=DependencyEvidenceAvailability.AVAILABLE,
        version_resolution_status=resolution,
        is_dependency_management=is_management,
        source=DependencySourceLocation(path=path, line_start=1, line_end=1),
        classification=classification,
        provenance=_provenance(path),
    )


def _manifest(
    *,
    path: str,
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    manifest_type: DependencyManifestType = DependencyManifestType.POM_XML,
    status: DependencyParseStatus = DependencyParseStatus.SUCCEEDED,
    classification: SourceClassification = SourceClassification.SOURCE,
    unsupported: tuple[str, ...] = (),
    diagnostics: tuple[str, ...] = (),
) -> DependencyManifestEvidence:
    return DependencyManifestEvidence(
        evidence_id=f"ev:manifest:{path}",
        path=path,
        ecosystem=ecosystem,
        manifest_type=manifest_type,
        parse_status=status,
        classification=classification,
        unsupported_constructs=unsupported,
        diagnostics=diagnostics,
        provenance=_provenance(path),
    )


def _evidence(
    *,
    manifests: tuple[DependencyManifestEvidence, ...],
    declarations: tuple[DependencyDeclarationEvidence, ...],
    status: DependencyParseStatus = DependencyParseStatus.SUCCEEDED,
) -> AggregatedDependencyEvidence:
    coverage = DependencyEvidenceCoverage(
        manifests_discovered=len(manifests),
        manifests_supported=len(manifests),
        manifests_parsed=sum(
            1
            for item in manifests
            if item.parse_status is DependencyParseStatus.SUCCEEDED
        ),
        manifests_partially_parsed=sum(
            1
            for item in manifests
            if item.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED
        ),
        manifests_failed=sum(
            1 for item in manifests if item.parse_status is DependencyParseStatus.FAILED
        ),
        declarations_collected=len(declarations),
        unsupported_construct_count=sum(
            len(item.unsupported_constructs) for item in manifests
        ),
        unresolved_expression_count=sum(
            1
            for item in declarations
            if item.version_resolution_status
            in {
                DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
                DependencyVersionResolutionStatus.UNSUPPORTED_RESOLUTION,
            }
        ),
    )
    return AggregatedDependencyEvidence(
        repository_id="repo:test",
        status=status,
        manifests=manifests,
        declarations=declarations,
        coverage=coverage,
        evidence_fingerprint="fp-report-test",
    )


def _finding(
    *,
    rule_id: str,
    path: str,
    identity: str,
    classification: str = "source",
    severity: FindingSeverity = FindingSeverity.MEDIUM,
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{identity} on {path}",
        severity=severity,
        category=FindingCategory.DEPENDENCY,
        subject_keys=(path, identity),
        metadata={
            "classification": classification,
            "path": path,
            "ecosystem": "maven",
            "normalized_identity": identity,
            "confidence": "high",
            "taxonomy_id": "dependency.unknown",
            "evidence_id": f"ev:{identity}",
        },
    )


def _codestrata_style_assessment():
    """Zero production findings; two test/fixture findings."""

    evidence = _evidence(
        manifests=(
            _manifest(path="pom.xml"),
            _manifest(
                path="tests/fixtures/sample/pom.xml",
                classification=SourceClassification.TEST,
            ),
        ),
        declarations=(
            _decl(evidence_id="d1", identity="a:a", path="pom.xml"),
            _decl(
                evidence_id="d2",
                identity="fixture:dup",
                path="tests/fixtures/sample/pom.xml",
                classification=SourceClassification.TEST,
            ),
            _decl(
                evidence_id="d3",
                identity="fixture:dup",
                path="tests/fixtures/sample/pom.xml",
                classification=SourceClassification.TEST,
            ),
            _decl(
                evidence_id="d4",
                identity="fixture:unresolved",
                path="tests/fixtures/sample/pom.xml",
                classification=SourceClassification.TEST,
                raw_version="${missing}",
                resolution=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
            ),
        ),
    )
    findings = (
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="tests/fixtures/sample/pom.xml",
            identity="fixture:dup",
            classification="test",
        ),
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="tests/fixtures/sample/pom.xml",
            identity="fixture:unresolved",
            classification="test",
        ),
    )
    return DependencyAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        include_synthesis=True,
        configuration_payload="report-codestrata",
    )


def _petclinic_style_assessment():
    """Zero findings; active deps + plugins; unsupported Gradle resolution."""

    decls = [
        _decl(
            evidence_id=f"prod-{index}",
            identity=f"org.example:lib-{index}",
            path="build.gradle",
            ecosystem=DependencyEcosystem.GRADLE,
            manifest_type=DependencyManifestType.BUILD_GRADLE,
        )
        for index in range(60)
    ]
    decls.extend(
        [
            _decl(
                evidence_id="plugin-1",
                identity="org.springframework.boot",
                path="build.gradle",
                kind=DependencyDeclarationKind.PLUGIN,
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
            ),
            _decl(
                evidence_id="plugin-2",
                identity="io.spring.dependency-management",
                path="build.gradle",
                kind=DependencyDeclarationKind.PLUGIN,
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
            ),
            _decl(
                evidence_id="mgmt-1",
                identity="org.webjars:jquery",
                path="build.gradle",
                kind=DependencyDeclarationKind.DEPENDENCY_MANAGEMENT,
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
                is_management=True,
            ),
            *[
                _decl(
                    evidence_id=f"interp-{index}",
                    identity=f"org.webjars:asset-{index}",
                    path="build.gradle",
                    ecosystem=DependencyEcosystem.GRADLE,
                    manifest_type=DependencyManifestType.BUILD_GRADLE,
                    raw_version="${webjarsVersion}",
                    resolution=DependencyVersionResolutionStatus.UNSUPPORTED_RESOLUTION,
                )
                for index in range(2)
            ],
        ]
    )
    evidence = _evidence(
        manifests=(
            _manifest(
                path="build.gradle",
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
                diagnostics=(
                    "gradle_interpolation:${webjarsVersion}",
                    "gradle_interpolation:${webjarsBootstrapVersion}",
                ),
            ),
        ),
        declarations=tuple(decls),
    )
    return DependencyAssessmentAssembler().assemble(
        repository_id="repo:petclinic",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        include_synthesis=True,
        configuration_payload="report-petclinic",
        diagnostics=(
            "gradle_interpolation:${webjarsVersion}",
            "gradle_interpolation:${webjarsBootstrapVersion}",
        ),
    )


def test_report_section_contract() -> None:
    report = DependencyReportAdapter().adapt(_codestrata_style_assessment())
    assert report.section_id == DEPENDENCY_REPORT_SECTION_ID
    assert report.section_version == DEPENDENCY_REPORT_SECTION_VERSION
    assert report.status == DependencyAssessmentStatus.SUCCEEDED.value
    assert report.executive_summary
    assert report.landscape
    assert report.production_health is not None
    assert report.test_observations is not None
    assert report.coverage is not None
    assert report.traceability is not None


def test_report_gate_disabled_by_default(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.report.sections.dependency.enabled is False
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.technical_debt.enabled is False


def test_report_gate_independent_of_assessment(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [assessment.sections.dependency]
        enabled = true

        [report.sections.dependency]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.assessment.sections.dependency.enabled is True
    assert settings.report.sections.dependency.enabled is True
    assert settings.report.sections.architecture.enabled is False
    assert settings.report.sections.technical_debt.enabled is False


def test_codestrata_style_production_test_separation() -> None:
    assessment = _codestrata_style_assessment()
    report = DependencyReportAdapter().adapt(assessment)
    assert assessment.execution_summary.production_finding_count == 0
    assert assessment.execution_summary.test_finding_count == 2
    assert report.production_health.finding_count == 0
    assert report.production_health.none_detected_statement == _NONE_DETECTED
    assert report.production_health.findings == ()
    assert report.production_health.recommendations == ()
    assert report.test_observations.present is True
    assert report.test_observations.finding_count == 2
    assert all(item.source_role == "test" for item in report.test_observations.findings)
    assert "do not contribute to the production-primary view" in report.executive_summary
    assert _NONE_DETECTED in report.executive_summary
    assert all(
        claim not in report.executive_summary.lower() for claim in _FORBIDDEN_CLAIMS
    )


def test_petclinic_style_unsupported_gradle_coverage() -> None:
    assessment = _petclinic_style_assessment()
    report = DependencyReportAdapter().adapt(assessment)
    assert assessment.execution_summary.total_finding_count == 0
    assert report.production_health.finding_count == 0
    assert report.test_observations.present is False
    assert report.hygiene_findings == ()
    kinds = {item.kind for item in report.conclusions}
    assert DependencyConclusionKind.UNSUPPORTED_RESOLUTION_COVERAGE.value in kinds
    assert DependencyConclusionKind.DECLARED_DEPENDENCIES_ONLY.value in kinds
    assert DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS.value in kinds
    rec_kinds = {item.kind for item in report.recommendations}
    assert DependencyRecommendationKind.DEFINE_UNRESOLVED_LOCAL_VERSION.value not in rec_kinds
    assert "does not inspect all Gradle resolution mechanisms" in report.executive_summary
    assert "does not represent a resolved or transitive dependency graph" in (
        report.executive_summary
    )
    assert report.coverage.unsupported_resolution_count >= 1
    assert report.diagnostics_total >= 0
    for sample in report.diagnostics:
        assert "finding" not in sample.diagnostic_code.lower()


def test_zero_production_and_declared_only_wording() -> None:
    report = DependencyReportAdapter().adapt(_petclinic_style_assessment())
    assert _NONE_DETECTED in report.executive_summary
    assert "declared-manifest" in report.executive_summary.lower() or (
        "declared-manifest facts only" in report.executive_summary
        or "does not represent a resolved or transitive" in report.executive_summary
    )


def test_landscape_count_reconciliation_and_kind_separation() -> None:
    assessment = _petclinic_style_assessment()
    report = DependencyReportAdapter().adapt(assessment)
    by_key = {item.key: item.count for item in report.landscape}
    decls = assessment.declaration_inventory.production
    assert by_key["production_active"] == decls.active_declaration_count
    assert by_key["production_management"] == decls.dependency_management_count
    assert by_key["production_plugins"] == decls.plugin_count
    assert by_key["production_active"] != by_key["production_plugins"]
    assert by_key["declarations_collected"] == (
        assessment.evidence_summary.declarations_collected
    )
    labels = " ".join(item.label.lower() for item in report.landscape)
    assert "active" in labels
    assert "plugin" in labels
    assert "management" in labels


def test_hotspot_ordering_and_bounds() -> None:
    assessment = _codestrata_style_assessment()
    report = DependencyReportAdapter().adapt(assessment, hotspot_limit=20)
    assert len(report.manifest_hotspots) <= TOP_MANIFEST_HOTSPOTS
    orders = [item.presentation_order for item in report.manifest_hotspots]
    assert orders == list(range(1, len(orders) + 1))
    expected = (
        *assessment.hotspot_inventory.production,
        *assessment.hotspot_inventory.test,
        *assessment.hotspot_inventory.unknown,
    )[:20]
    assert [item.hotspot_id for item in report.manifest_hotspots] == [
        item.hotspot_id for item in expected
    ]
    assert "not a risk or priority" in report.hotspot_presentation_note.lower()


def test_finding_and_diagnostic_bounds() -> None:
    findings = tuple(
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path=f"tests/fixtures/{index}/pom.xml",
            identity=f"pkg:{index}",
            classification="test",
        )
        for index in range(25)
    )
    evidence = _evidence(
        manifests=tuple(
            _manifest(
                path=f"tests/fixtures/{index}/pom.xml",
                classification=SourceClassification.TEST,
            )
            for index in range(25)
        ),
        declarations=tuple(
            _decl(
                evidence_id=f"d{index}",
                identity=f"pkg:{index}",
                path=f"tests/fixtures/{index}/pom.xml",
                classification=SourceClassification.TEST,
            )
            for index in range(25)
        ),
    )
    assessment = DependencyAssessmentAssembler().assemble(
        repository_id="repo:bounds",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        include_synthesis=True,
        diagnostics=tuple(f"diag-{index}" for index in range(30)),
    )
    report = DependencyReportAdapter().adapt(
        assessment,
        finding_limit=FINDING_DISPLAY_LIMIT,
        diagnostic_limit=DIAGNOSTIC_SAMPLE_LIMIT,
    )
    assert report.test_observations.findings_total == 25
    assert report.test_observations.findings_displayed <= FINDING_DISPLAY_LIMIT
    assert len(report.test_observations.findings) <= FINDING_DISPLAY_LIMIT
    assert report.diagnostics_total >= len(report.diagnostics)
    assert len(report.diagnostics) <= DIAGNOSTIC_SAMPLE_LIMIT
    for item in report.test_observations.findings:
        assert item.finding_id
        assert item.rule_id
        assert item.severity
        assert item.confidence
        assert item.source_role == "test"
        assert item.evidence_ids or item.evidence_count >= 0


def test_conclusion_recommendation_grouping_and_traceability() -> None:
    report = DependencyReportAdapter().adapt(_codestrata_style_assessment())
    audiences = {group.audience for group in report.conclusion_groups}
    assert "production_health" in audiences or any(
        item.audience == "production_health" for item in report.conclusions
    )
    assert any(item.audience == "test_observation" for item in report.conclusions)
    assert report.conclusions
    assert all(item.conclusion_id for item in report.conclusions)
    assert all(item.recommendation_id for item in report.recommendations)
    assert report.traceability.edge_count >= len(report.traceability.sample_edges)
    assert len(report.traceability.sample_edges) <= TRACE_SAMPLE_LIMIT
    for edge in report.traceability.sample_edges:
        assert edge.source_id
        assert edge.target_id
        assert edge.relation


def test_empty_subsection_omission_for_disabled_assessment() -> None:
    disabled = DependencyAssessmentAssembler().assemble_disabled(
        repository_id="repo:x"
    )
    report = DependencyReportAdapter().adapt(disabled)
    assert report.status == DependencyAssessmentStatus.DISABLED.value
    assert report.test_observations.present is False
    assert report.hygiene_findings == ()
    assert "disabled" in report.executive_summary.lower()


def test_deterministic_repeated_adapt() -> None:
    assessment = _codestrata_style_assessment()
    left = DependencyReportAdapter().adapt(assessment).model_dump_json()
    right = DependencyReportAdapter().adapt(assessment).model_dump_json()
    assert left == right


def test_report_json_optional_field(tmp_path: Path) -> None:
    analysis = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path / "demo"),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    absent = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
    )
    document = build_assessment_json_document(absent)
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assert "dependency" not in document["assessment"]

    dep_report = DependencyReportAdapter().adapt(_codestrata_style_assessment())
    present = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
        dependency_report=dep_report,
    )
    document = build_assessment_json_document(present)
    assert document["schema_version"] == "1.2"
    section = document["assessment"]["dependency"]
    assert section["section_id"] == DEPENDENCY_REPORT_SECTION_ID
    assert section["section_version"] == DEPENDENCY_REPORT_SECTION_VERSION
    assert section["production_health"]["finding_count"] == 0
    assert section["test_observations"]["present"] is True
    assert "dependency-evidence" not in str(section).lower()


def test_html_placement_anchor_and_identity(tmp_path: Path) -> None:
    dep_report = DependencyReportAdapter().adapt(_codestrata_style_assessment())
    analysis = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path / "demo"),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
        dependency_report=dep_report,
    )
    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert 'id="dependency-assessment"' in html
    assert "Dependency Assessment" in html
    assert "Executive Summary" in html
    assert "Production Dependency Hygiene" in html
    assert "Test and Fixture Observations" in html
    assert _NONE_DETECTED in html
    assert "do not contribute to the production-primary view" in html
    assert "/Users/" not in html
    assert all(claim not in html.lower() for claim in ("secure dependencies", "low risk"))

    html_again = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert html == html_again

    omitted = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
    )
    html_omitted = HtmlReportRenderer().render(build_html_report_view_model(omitted))
    assert 'id="dependency-assessment"' not in html_omitted


def test_adapter_failure_isolation_pattern() -> None:
    assessment = _codestrata_style_assessment()

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("dependency report boom")

    dependency_report_section = None
    dependency_report_status = None
    with patch.object(DependencyReportAdapter, "adapt", _boom):
        try:
            dependency_report_section = DependencyReportAdapter().adapt(assessment)
        except Exception:  # noqa: BLE001 - mirrors assessment service isolation
            dependency_report_section = None
            dependency_report_status = "failed"
    assert dependency_report_section is None
    assert dependency_report_status == "failed"

    with patch.object(DependencyReportAdapter, "adapt", _boom):
        with pytest.raises(RuntimeError, match="dependency report boom"):
            DependencyReportAdapter().adapt(assessment)


def test_unavailable_behavior_wording() -> None:
    insufficient = DependencyAssessmentAssembler().assemble_insufficient_evidence(
        repository_id="repo:x"
    )
    report = DependencyReportAdapter().adapt(insufficient)
    assert report.status == DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE.value
    assert "could not establish safe conclusions" in report.executive_summary.lower()
