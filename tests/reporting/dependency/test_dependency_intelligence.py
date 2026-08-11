"""Epic 3 Slice 3.5 — Dependency Intelligence section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.dependency.assessment.assembler import (
    DependencyAssessmentAssembler,
)
from codestrata.domain.dependency.ids import (
    RULE_DUPLICATE_DECLARATION,
    RULE_UNRESOLVED_VERSION,
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
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.dependency import (
    DependencyReportAdapter,
    build_dependency_intelligence,
)
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.models import FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


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
        is_dependency_management=False,
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
) -> DependencyManifestEvidence:
    return DependencyManifestEvidence(
        evidence_id=f"ev:manifest:{path}",
        path=path,
        ecosystem=ecosystem,
        manifest_type=manifest_type,
        parse_status=status,
        classification=classification,
        unsupported_constructs=(),
        diagnostics=(),
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
        unsupported_construct_count=0,
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
        evidence_fingerprint="fp-dep-intel",
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


def _succeeded_report():
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
    assessment = DependencyAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        include_synthesis=True,
        configuration_payload="dep-intel",
    )
    return DependencyReportAdapter().adapt(assessment)


def test_build_dependency_intelligence_groups_and_excludes_others() -> None:
    report = _succeeded_report()
    dep = FindingView(
        finding_id="f-dep",
        rule_id=RULE_UNRESOLVED_VERSION,
        title="Unresolved version",
        description="missing property",
        severity="high",
        category="dependency",
        affected_nodes=("pom.xml",),
    )
    hygiene = FindingView(
        finding_id="f-dup",
        rule_id=RULE_DUPLICATE_DECLARATION,
        title="Duplicate declaration",
        description="dup",
        severity="medium",
        category="dependency",
        affected_nodes=("pom.xml",),
    )
    cve = FindingView(
        finding_id="f-cve",
        rule_id="dependency.cve-scan",
        title="CVE found",
        description="should exclude",
        severity="high",
        category="dependency",
    )
    outdated = FindingView(
        finding_id="f-old",
        rule_id="dependency.unresolved-version",
        title="Outdated vulnerable package",
        description="should exclude by title",
        severity="medium",
        category="dependency",
    )
    security = FindingView(
        finding_id="f-sec",
        rule_id="security.credential-literal",
        title="Credential",
        description="secret",
        severity="high",
        category="security",
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
        recommendation_id="r-dep",
        title="Pin unresolved versions",
        summary="Define the missing property",
        rationale="Hygiene",
        priority="high",
        category="dependency",
        related_finding_ids=("f-dep",),
    )
    other = RecommendationView(
        recommendation_id="r-sec",
        title="Remove secret",
        summary="Remove",
        rationale="Security",
        priority="high",
        category="security",
        related_finding_ids=("f-sec",),
    )
    intel = build_dependency_intelligence(
        report,
        findings=(dep, hygiene, cve, outdated, security, architecture),
        recommendations=(rec, other),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-dep", "f-dup"}
    assert {item.recommendation_id for item in intel.recommendations} == {"r-dep"}
    assert intel.empty_findings_message is None
    joined = " ".join(intel.limitations).lower()
    assert "declaration hygiene" in joined
    assert "cve analysis" in joined or "registry lookups" in joined
    assert intel.confidence_label in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Confidence unavailable",
    }
    assert intel.ecosystems
    assert intel.manifests
    assert all(not row.path.startswith("/") for row in intel.manifests)
    assert all(not row.path.startswith("file:") for row in intel.manifests)


def test_zero_findings_not_healthy() -> None:
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(_decl(evidence_id="d1", identity="a:a", path="pom.xml"),),
    )
    assessment = DependencyAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        include_synthesis=True,
    )
    report = DependencyReportAdapter().adapt(assessment)
    intel = build_dependency_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.finding_count == 0
    assert intel.findings == ()
    assert intel.empty_findings_message is not None
    lowered = intel.empty_findings_message.lower()
    assert "declaration hygiene" in lowered
    assert "do not mean a healthy" in lowered or "do not mean" in lowered
    assert "secure dependency posture" in lowered
    overview = " ".join(
        f"{fact.label} {fact.value} {fact.note or ''}" for fact in intel.overview_facts
    ).lower()
    assert "zero findings do not mean" in overview or "healthy" in overview


def test_soft_claims_scrubbed_from_status_summary() -> None:
    report = _succeeded_report()
    mutated = report.model_copy(
        update={
            "status_summary": "Dependencies look healthy with a secure supply chain.",
        }
    )
    intel = build_dependency_intelligence(mutated, findings=(), recommendations=())
    assert intel is not None
    lowered = intel.status_summary.lower()
    assert "secure supply" not in lowered
    assert "declaration-hygiene" in lowered or "declaration hygiene" in lowered


def test_absolute_manifest_paths_omitted() -> None:
    report = _succeeded_report()
    hotspots = list(report.manifest_hotspots)
    if not hotspots:
        return
    bad = hotspots[0].model_copy(update={"path": "/Users/secret/pom.xml"})
    mutated = report.model_copy(
        update={"manifest_hotspots": (bad, *hotspots[1:])}
    )
    intel = build_dependency_intelligence(mutated, findings=(), recommendations=())
    assert intel is not None
    assert all(not row.path.startswith("/") for row in intel.manifests)
    assert all(not row.path.startswith("file:") for row in intel.manifests)
    assert "/Users/secret" not in " ".join(row.path for row in intel.manifests)


def test_html_dependency_intelligence_section(tmp_path: Path) -> None:
    report = _succeeded_report()
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["pom.xml"],
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
        dependency_report=report,
    )
    document = build_html_report_view_model(report_input)
    assert document.dependency_intelligence is not None
    html = HtmlReportRenderer().render(document)
    assert 'id="dependency-intelligence"' in html
    assert 'id="dependency-assessment"' in html
    assert 'href="#dependency-intelligence"' in html
    assert "Dependency overview" in html
    assert "Hygiene findings" in html or "declaration hygiene" in html.lower()
    assert "Limitations" in html
    assert "Confidence" in html
    lowered = html.lower()
    assert "secure dependencies" not in lowered
    assert "low risk" not in lowered
    assert "no dependency risk" not in lowered
    assert "registry lookups" in lowered or "declaration hygiene" in lowered
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
    assert build_dependency_intelligence(None) is None


def test_related_recommendation_subset_included() -> None:
    report = _succeeded_report()
    dep = FindingView(
        finding_id="f-dep",
        rule_id=RULE_UNRESOLVED_VERSION,
        title="Unresolved",
        description="x",
        severity="medium",
        category="dependency",
    )
    related = RecommendationView(
        recommendation_id="r-related",
        title="Fix unresolved",
        summary="Pin",
        rationale="Hygiene",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-dep",),
    )
    mixed = RecommendationView(
        recommendation_id="r-mixed",
        title="Mixed",
        summary="Mixed",
        rationale="Mixed",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-dep", "f-other"),
    )
    intel = build_dependency_intelligence(
        report,
        findings=(dep,),
        recommendations=(related, mixed),
    )
    assert intel is not None
    assert {item.recommendation_id for item in intel.recommendations} == {"r-related"}
