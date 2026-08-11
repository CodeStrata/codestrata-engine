"""Epic 3 Slice 3.4 — Technical Debt Intelligence section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.technical_debt.ids import (
    RULE_EXCESSIVE_BRANCHING,
    RULE_LARGE_CALLABLE,
)
from codestrata.domain.traceability.enums import (
    EvidenceKind,
    MeasurementScope,
    ThresholdOperator,
)
from codestrata.domain.traceability.evidence_ref import EvidenceRef
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.measurement import EvidenceMeasurement
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.evidence_presentation import evidence_ref_view_from_domain
from codestrata.reporting.html_v2.models import EvidenceRefView, FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.technical_debt import (
    TechnicalDebtReportAdapter,
    build_technical_debt_intelligence,
)


def _td_finding(
    *,
    rule_id: str,
    path: str,
    symbol: str,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{rule_id} observation",
        severity=severity,
        category=FindingCategory.TECHNICAL_DEBT,
        subject_keys=(path, symbol),
        metadata={
            "classification": "source",
            "language": "python",
            "confidence": "high",
            "path": path,
            "subject_keys": f"{path},{symbol}",
        },
    )


def _succeeded_report():
    findings = (
        _td_finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/app.py",
            symbol="run#0@1",
            severity=FindingSeverity.HIGH,
        ),
        _td_finding(
            rule_id=RULE_EXCESSIVE_BRANCHING,
            path="src/app.py",
            symbol="run#0@1",
        ),
        _td_finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/other.py",
            symbol="other#0@1",
        ),
    )
    assessment = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=2,
        files_analyzed=2,
        configuration_payload="td-intel",
    )
    return TechnicalDebtReportAdapter().adapt(assessment)


def test_build_technical_debt_intelligence_groups_and_excludes_others() -> None:
    report = _succeeded_report()
    td = FindingView(
        finding_id="f-td",
        rule_id=RULE_LARGE_CALLABLE,
        title="Large callable",
        description="too long",
        severity="high",
        category="technical_debt",
        affected_nodes=("src/app.py",),
    )
    maintainability = FindingView(
        finding_id="f-maint",
        rule_id="technical_debt.excessive-branching",
        title="Branching",
        description="branches",
        severity="medium",
        category="maintainability",
        affected_nodes=("src/app.py",),
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
        recommendation_id="r-td",
        title="Reduce complexity",
        summary="Split the callable",
        rationale="Maintainability",
        priority="high",
        category="technical_debt",
        related_finding_ids=("f-td",),
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
    intel = build_technical_debt_intelligence(
        report,
        findings=(td, maintainability, security, architecture),
        recommendations=(rec, other),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-td", "f-maint"}
    assert {item.recommendation_id for item in intel.recommendations} == {"r-td"}
    assert intel.empty_findings_message is None
    joined = " ".join(intel.limitations).lower()
    assert "broader technical debt" in joined
    assert "static complexity" in joined
    assert intel.confidence_label in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Confidence unavailable",
    }


def test_zero_findings_not_low_debt() -> None:
    assessment = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=1,
        files_analyzed=1,
    )
    report = TechnicalDebtReportAdapter().adapt(assessment)
    intel = build_technical_debt_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.finding_count == 0
    assert intel.hotspots == ()
    assert intel.empty_findings_message is not None
    lowered = intel.empty_findings_message.lower()
    assert "low technical debt" not in lowered or "do not mean low" in lowered
    assert "broader technical debt" in lowered
    assert "no complexity-related" in lowered


def test_measurements_zero_distinct_from_unavailable() -> None:
    available = EvidenceMeasurement.available(
        metric_id="physical_line_count",
        metric_name="Physical line count",
        measured_value=0,
        threshold=50,
        threshold_operator=ThresholdOperator.GT,
        scope=MeasurementScope.CALLABLE,
        limitations=("static complexity only",),
    )
    unavailable = EvidenceMeasurement.unavailable(
        metric_id="branch_point_count",
        metric_name="Branch point count",
        limitations=("metric not computed",),
    )
    ref_available = EvidenceRef(
        evidence_id="ev-zero",
        kind=EvidenceKind.MEASUREMENT,
        location=EvidenceLocation(path="src/app.py", symbolic_reference="run"),
        measurement=available,
    )
    ref_unavailable = EvidenceRef(
        evidence_id="ev-missing",
        kind=EvidenceKind.MEASUREMENT,
        location=EvidenceLocation(path="src/other.py", symbolic_reference="other"),
        measurement=unavailable,
    )
    view_available = evidence_ref_view_from_domain(ref_available)
    view_unavailable = evidence_ref_view_from_domain(ref_unavailable)
    assert isinstance(view_available, EvidenceRefView)
    assert view_available.measurement_value == 0
    assert view_unavailable.measurement_value is None

    finding = FindingView(
        finding_id="f-meas",
        rule_id=RULE_LARGE_CALLABLE,
        title="Callable size",
        description="lines",
        severity="medium",
        category="technical_debt",
        evidence_refs=(view_available, view_unavailable),
        affected_nodes=("src/app.py",),
        evidence_completeness="complete",
    )
    report = _succeeded_report()
    intel = build_technical_debt_intelligence(report, findings=(finding,), recommendations=())
    assert intel is not None
    by_name = {row.metric_name: row for row in intel.measurements}
    assert by_name["Physical line count"].observed_value == "0"
    assert by_name["Physical line count"].availability == "available"
    assert by_name["Physical line count"].threshold == "50"
    assert by_name["Physical line count"].operator == "gt"
    assert by_name["Branch point count"].observed_value == "unavailable"
    assert by_name["Branch point count"].availability == "unavailable"
    assert by_name["Branch point count"].observed_value != "0"


def test_hotspots_sorted_and_require_finding() -> None:
    def _hotspot_finding(
        finding_id: str,
        *,
        severity: str,
        path: str,
        value: float,
        threshold: float,
        metric: str,
    ) -> FindingView:
        measurement = EvidenceMeasurement.available(
            metric_id=metric,
            metric_name=metric,
            measured_value=value,
            threshold=threshold,
            threshold_operator=ThresholdOperator.GT,
            scope=MeasurementScope.CALLABLE,
        )
        ref = EvidenceRef(
            evidence_id=f"ev-{finding_id}",
            kind=EvidenceKind.MEASUREMENT,
            location=EvidenceLocation(path=path, symbolic_reference="fn"),
            measurement=measurement,
        )
        return FindingView(
            finding_id=finding_id,
            rule_id=RULE_LARGE_CALLABLE,
            title=finding_id,
            description="hotspot",
            severity=severity,
            category="technical_debt",
            evidence_refs=(evidence_ref_view_from_domain(ref),),
            affected_nodes=(path,),
            evidence_completeness="complete",
        )

    findings = (
        _hotspot_finding(
            "f-med",
            severity="medium",
            path="b.py",
            value=80,
            threshold=50,
            metric="lines",
        ),
        _hotspot_finding(
            "f-high-a",
            severity="high",
            path="a.py",
            value=100,
            threshold=50,
            metric="lines",
        ),
        _hotspot_finding(
            "f-high-b",
            severity="high",
            path="c.py",
            value=120,
            threshold=50,
            metric="lines",
        ),
        FindingView(
            finding_id="f-abs",
            rule_id=RULE_LARGE_CALLABLE,
            title="Absolute path only",
            description="should omit absolute path",
            severity="low",
            category="technical_debt",
            evidence_refs=(
                EvidenceRefView(
                    evidence_id="ev-abs",
                    kind="measurement",
                    path="/Users/secret/abs.py",
                    measurement_name="lines",
                    measurement_value=99,
                    threshold_operator="gt",
                    threshold_value=10,
                ),
            ),
            affected_nodes=("/Users/secret/abs.py",),
        ),
    )
    report = _succeeded_report()
    intel = build_technical_debt_intelligence(report, findings=findings, recommendations=())
    assert intel is not None
    assert all(row.finding_id for row in intel.hotspots)
    ids = [row.finding_id for row in intel.hotspots]
    # high severity first, then larger exceedance within high
    assert ids.index("f-high-b") < ids.index("f-high-a") < ids.index("f-med")
    assert "f-abs" in ids
    abs_row = next(row for row in intel.hotspots if row.finding_id == "f-abs")
    assert abs_row.path == "—"
    assert not any((row.path or "").startswith("/") for row in intel.hotspots)
    assert not any((row.path or "").startswith("file:") for row in intel.hotspots)


def test_report_hotspots_alone_do_not_invent_hotspots() -> None:
    report = _succeeded_report()
    assert report.top_production_hotspots
    intel = build_technical_debt_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.hotspots == ()
    assert intel.finding_count == 0
    assert intel.empty_findings_message is not None


def test_html_technical_debt_intelligence_section(tmp_path: Path) -> None:
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
        technical_debt_report=report,
    )
    document = build_html_report_view_model(report_input)
    assert document.technical_debt_intelligence is not None
    html = HtmlReportRenderer().render(document)
    assert 'id="technical-debt-intelligence"' in html
    assert 'id="technical-debt-assessment"' in html
    assert 'href="#technical-debt-intelligence"' in html
    assert "Technical debt overview" in html
    assert "Limitations" in html
    assert "Confidence" in html
    lowered = html.lower()
    assert "low technical debt" not in lowered or "do not mean low" in lowered
    assert "no significant" not in lowered
    assert "rewrite required" not in lowered
    assert "productivity is reduced" not in lowered
    assert "broader technical debt" in lowered or "static complexity" in lowered
    assert "/Users/" not in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    for anchor in (
        "technology-inventory",
        "architecture-intelligence",
        "dependency-intelligence",
        "security-intelligence",
    ):
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html


def test_build_returns_none_when_report_missing() -> None:
    assert build_technical_debt_intelligence(None) is None
