"""Epic 3 Slice 3.3 — Architecture Intelligence section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.architecture.assessment.assembler import (
    ArchitectureAssessmentAssembler,
)
from codestrata.application.architecture.conclusions.factory import (
    create_architecture_conclusion_service,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.architecture.ids import (
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_INVALID_DEPENDENCY_DIRECTION,
)
from codestrata.domain.traceability.enums import (
    EvidenceKind,
    GraphKind,
    GraphReferenceKind,
    MeasurementScope,
    ThresholdOperator,
)
from codestrata.domain.traceability.evidence_ref import EvidenceRef
from codestrata.domain.traceability.graph_reference import GraphReference
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.measurement import EvidenceMeasurement
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.architecture import (
    ArchitectureReportAdapter,
    build_architecture_intelligence,
)
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.evidence_presentation import evidence_ref_view_from_domain
from codestrata.reporting.html_v2.models import EvidenceRefView, FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def _arch_finding(rule_id: str, *subjects: str, evidence_refs=()) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{rule_id} observation",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.ARCHITECTURE,
        subject_keys=subjects,
        evidence_refs=evidence_refs,
        metadata={
            "confidence": "high",
            "subject_keys": ",".join(subjects),
            "remediation": f"Fix {rule_id}",
            "business_impact": "unknown",
        },
    )


def _succeeded_report():
    findings = (
        _arch_finding(
            RULE_DEPENDENCY_CYCLE,
            "codestrata.application",
            "codestrata.infrastructure",
            "cycle",
        ),
        _arch_finding(
            RULE_INVALID_DEPENDENCY_DIRECTION,
            "codestrata.application",
            "codestrata.infrastructure",
            "application",
            "infrastructure",
        ),
        _arch_finding(
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            "codestrata.application",
            "out:10",
        ),
    )
    conclusions = create_architecture_conclusion_service().build(
        repository_id="repo:codestrata",
        findings=findings,
        extraction_coverage=1.0,
        classification_coverage=0.3125,
        graph_fingerprint="fp",
    )
    assessment = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=findings,
        conclusion_result=conclusions,
        pack_enabled=True,
        conclusions_enabled=True,
        extraction_coverage=1.0,
        classification_coverage=0.3125,
        graph_fingerprint="fp",
    )
    return ArchitectureReportAdapter().adapt(assessment)


def test_build_architecture_intelligence_groups_and_excludes_non_arch() -> None:
    report = _succeeded_report()
    arch = FindingView(
        finding_id="f-arch",
        rule_id=RULE_DEPENDENCY_CYCLE,
        title="Dependency cycle",
        description="cycle",
        severity="medium",
        category="architecture",
        affected_nodes=("codestrata.application",),
    )
    security = FindingView(
        finding_id="f-sec",
        rule_id="security.credential-literal",
        title="Credential",
        description="secret",
        severity="high",
        category="security",
    )
    rec = RecommendationView(
        recommendation_id="r-arch",
        title="Break cycle",
        summary="Break the cycle",
        rationale="Coupling",
        priority="high",
        category="architecture",
        related_finding_ids=("f-arch",),
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
    intel = build_architecture_intelligence(
        report,
        findings=(arch, security),
        recommendations=(rec, other),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-arch"}
    assert {item.recommendation_id for item in intel.recommendations} == {"r-arch"}
    assert intel.empty_findings_message is None
    assert any("static repository structure only" in note.lower() for note in intel.limitations)
    assert "runtime" in " ".join(intel.limitations).lower()
    assert intel.confidence_label in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Confidence unavailable",
    }


def test_zero_findings_not_healthy() -> None:
    assessment = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        conclusion_result=None,
        pack_enabled=True,
        conclusions_enabled=False,
        extraction_coverage=1.0,
        classification_coverage=1.0,
    )
    report = ArchitectureReportAdapter().adapt(assessment)
    intel = build_architecture_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.finding_count == 0
    assert intel.empty_findings_message is not None
    assert "healthy" not in intel.empty_findings_message.lower()
    assert "no architecture findings" in intel.empty_findings_message.lower()


def test_html_architecture_intelligence_section(tmp_path: Path) -> None:
    report = _succeeded_report()
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py"],
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
        architecture_report=report,
    )
    document = build_html_report_view_model(report_input)
    assert document.architecture_intelligence is not None
    html = HtmlReportRenderer().render(document)
    assert 'id="architecture-intelligence"' in html
    assert 'id="architecture-assessment"' in html
    assert 'href="#architecture-intelligence"' in html
    assert "Architecture overview" in html
    assert "Key architecture findings" in html or "Architecture conclusions" in html
    assert "Limitations" in html
    assert "Confidence" in html
    assert "no significant architecture risks" not in html.lower()
    assert "architecture is healthy" not in html.lower()
    assert "well-architected" not in html.lower()
    assert "microservices architecture" not in html.lower()
    assert "runtime architecture was not assessed" in html.lower() or "static" in html.lower()
    assert "/Users/" not in html
    assert '"node_ids"' not in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    for anchor in (
        "technology-inventory",
        "technical-debt-intelligence",
        "dependency-intelligence",
        "security-intelligence",
    ):
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html


def test_graph_and_measurement_rows_from_evidence_refs() -> None:
    measurement = EvidenceMeasurement.available(
        metric_id="fan_out",
        metric_name="Fan-out",
        measured_value=10,
        threshold=5,
        threshold_operator=ThresholdOperator.GT,
        scope=MeasurementScope.MODULE,
        limitations=("static structure only",),
    )
    graph = GraphReference(
        graph_id="architecture-view",
        graph_kind=GraphKind.ARCHITECTURE_VIEW,
        reference_kind=GraphReferenceKind.RELATIONSHIP,
        relationship_type="depends_on",
        node_ids=("mod.a", "mod.b"),
        source_locations=(EvidenceLocation(path="pkg/a.py"),),
    )
    ref = EvidenceRef(
        evidence_id="ev-1",
        kind=EvidenceKind.GRAPH,
        location=EvidenceLocation(path="pkg/a.py"),
        measurement=measurement,
        graph_ref=graph,
    )
    view_ref = evidence_ref_view_from_domain(ref)
    assert isinstance(view_ref, EvidenceRefView)
    assert view_ref.graph_relationship_type == "depends_on"
    assert "mod.a" in view_ref.graph_node_ids
    assert view_ref.measurement_value == 10
    assert view_ref.threshold_value == 5

    finding = FindingView(
        finding_id="f1",
        rule_id=RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
        title="Coupling",
        description="fan-out",
        severity="medium",
        category="architecture",
        evidence_refs=(view_ref,),
        affected_nodes=("mod.a",),
    )
    report = _succeeded_report()
    intel = build_architecture_intelligence(report, findings=(finding,), recommendations=())
    assert intel is not None
    assert intel.measurements
    assert intel.measurements[0].observed_value == "10"
    assert intel.measurements[0].threshold == "5"
    assert intel.graph_evidence
    assert not any((row.location or "").startswith("/") for row in intel.graph_evidence)
    assert not any((row.location or "").startswith("file:") for row in intel.graph_evidence)
