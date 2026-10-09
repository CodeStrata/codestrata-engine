"""R2-G1 repair: honest headlines, subordinate packs, subdirectory Git identity."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.engineering_health.projection import (
    DISPLAY_INSUFFICIENT_EVIDENCE,
    DISPLAY_NEEDS_ATTENTION,
    DISPLAY_NO_MATERIAL_ISSUES,
    apply_engineering_health_projection,
    architecture_evidence_is_sufficient,
    overlay_headline_evidence_coverage,
    security_evidence_is_sufficient,
)
from codestrata.reporting.html_v2.assessment_heads import AssessmentHead
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.models import AssessmentHeadSectionView
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def _section(
    head: AssessmentHead,
    *,
    status: str = "assessed",
    status_label: str = "Succeeded",
    findings_count: int = 0,
    coverage_status: str = "complete",
) -> AssessmentHeadSectionView:
    return AssessmentHeadSectionView(
        head=head.value,
        title=head.value,
        anchor=head.value.replace("_", "-"),
        status=status,
        status_label=status_label,
        findings_count=findings_count,
        recommendations_count=0,
        assessment_coverage={"status": coverage_status},
        pack_content_available=True,
    )


def _project(
    section: AssessmentHeadSectionView,
    *,
    metadata: dict[str, object] | None = None,
    architecture_report: object | None = None,
) -> AssessmentHeadSectionView:
    overlaid = overlay_headline_evidence_coverage(
        (section,),
        metadata=metadata,
        architecture_report=architecture_report,
    )
    return apply_engineering_health_projection(overlaid)[0]


def test_security_complete_zero_findings_is_clean() -> None:
    metadata = {
        "canonical_coverage": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "execution_state": "complete",
                "coverage_reason": "exact_versions_matched",
                "limitations": [],
            }
        ],
        "canonical_freshness": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "state": "fresh",
                "reason_code": "feed_fresh",
            }
        ],
        "canonical_limitations": [],
    }
    projected = _project(
        _section(AssessmentHead.SECURITY_INTELLIGENCE, findings_count=0),
        metadata=metadata,
    )
    assert projected.display_label == DISPLAY_NO_MATERIAL_ISSUES
    assert projected.status_label != "Succeeded"


def test_security_unknown_vulnerability_evidence_is_insufficient() -> None:
    metadata = {
        "canonical_coverage": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "execution_state": "unknown",
                "coverage_reason": "no_exact_version",
                "limitations": ["cannot_prove_clean"],
            }
        ],
        "canonical_freshness": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "state": "fresh",
                "reason_code": "feed_fresh",
            }
        ],
        "canonical_limitations": ["cannot_prove_clean"],
    }
    projected = _project(
        _section(AssessmentHead.SECURITY_INTELLIGENCE, findings_count=0),
        metadata=metadata,
    )
    assert projected.display_label == DISPLAY_INSUFFICIENT_EVIDENCE
    assert projected.status_label.lower() not in {"succeeded", "complete", "success"}


def test_security_missing_feed_is_insufficient() -> None:
    metadata = {
        "canonical_coverage": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "execution_state": "unknown",
                "coverage_reason": "feed_missing",
                "limitations": ["feed_missing"],
            }
        ],
        "canonical_freshness": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "state": "unknown",
                "reason_code": "feed_missing",
            }
        ],
        "canonical_limitations": ["feed_missing", "cannot_prove_clean"],
    }
    assert security_evidence_is_sufficient(
        coverage_rows=metadata["canonical_coverage"],
        freshness_rows=metadata["canonical_freshness"],
        limitations=metadata["canonical_limitations"],
    ) is False
    projected = _project(
        _section(AssessmentHead.SECURITY_INTELLIGENCE),
        metadata=metadata,
    )
    assert projected.display_label == DISPLAY_INSUFFICIENT_EVIDENCE


def test_security_stale_feed_is_insufficient() -> None:
    metadata = {
        "canonical_coverage": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "execution_state": "unknown",
                "coverage_reason": "feed_stale",
                "limitations": ["feed_stale"],
            }
        ],
        "canonical_freshness": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "state": "stale",
                "reason_code": "feed_stale",
            }
        ],
        "canonical_limitations": ["feed_stale", "cannot_prove_clean"],
    }
    projected = _project(
        _section(AssessmentHead.SECURITY_INTELLIGENCE),
        metadata=metadata,
    )
    assert projected.display_label == DISPLAY_INSUFFICIENT_EVIDENCE


def test_security_cannot_prove_clean_is_insufficient() -> None:
    metadata = {
        "canonical_coverage": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "execution_state": "complete",
                "coverage_reason": "hotspot_records_attached",
                "limitations": [],
            }
        ],
        "canonical_freshness": [
            {
                "capability_id": "security.m13.vulnerabilities",
                "state": "fresh",
                "reason_code": "feed_fresh",
            }
        ],
        "canonical_limitations": ["cannot_prove_clean"],
    }
    projected = _project(
        _section(AssessmentHead.SECURITY_INTELLIGENCE),
        metadata=metadata,
    )
    assert projected.display_label == DISPLAY_INSUFFICIENT_EVIDENCE


def test_architecture_sufficient_with_findings_needs_attention() -> None:
    report = SimpleNamespace(status="succeeded", conclusions=())
    projected = _project(
        _section(AssessmentHead.ARCHITECTURE_INTELLIGENCE, findings_count=2),
        architecture_report=report,
    )
    assert architecture_evidence_is_sufficient(report) is True
    assert projected.display_label == DISPLAY_NEEDS_ATTENTION


def test_architecture_sufficient_without_findings_is_clean() -> None:
    report = SimpleNamespace(status="succeeded", conclusions=())
    projected = _project(
        _section(AssessmentHead.ARCHITECTURE_INTELLIGENCE, findings_count=0),
        architecture_report=report,
    )
    assert projected.display_label == DISPLAY_NO_MATERIAL_ISSUES


def test_architecture_insufficient_evidence_is_not_succeeded() -> None:
    report = SimpleNamespace(
        status="succeeded",
        conclusions=(
            SimpleNamespace(
                category="architecture.insufficient-evidence",
                policy_id="architecture.conclusion.insufficient-evidence",
                conclusion_id="conclusion:architecture.conclusion.insufficient-evidence:1",
                coverage={"classification_coverage": "0.0000"},
            ),
        ),
    )
    projected = _project(
        _section(AssessmentHead.ARCHITECTURE_INTELLIGENCE, findings_count=1),
        architecture_report=report,
    )
    assert architecture_evidence_is_sufficient(report) is False
    assert projected.display_label == DISPLAY_INSUFFICIENT_EVIDENCE
    assert projected.status_label != "Succeeded"


def test_architecture_execution_failed_is_insufficient() -> None:
    report = SimpleNamespace(status="failed", conclusions=())
    projected = _project(
        _section(
            AssessmentHead.ARCHITECTURE_INTELLIGENCE,
            status="failed",
            status_label="Failed",
            coverage_status="complete",
        ),
        architecture_report=report,
    )
    assert projected.display_label == DISPLAY_INSUFFICIENT_EVIDENCE


def test_legacy_intelligence_packs_are_subordinate_evidence() -> None:
    document = build_html_report_view_model(
        ModernizationReportInput(
            analysis_result=AnalysisResult(
                repository=Repository(name="demo", path=".", files=["src/app.js"])
            ),
            assessment_mode=AssessmentMode.DETERMINISTIC,
            generated_at_utc=datetime(2026, 9, 27, tzinfo=UTC),
        )
    )
    html = HtmlReportRenderer().render(document)
    assert "Current-code baseline" in html
    assert html.find('id="assessment-results"') < html.find("Outcome evidence")
    assert "not additional headline outcomes" in html
    assert "Architecture Intelligence pack" in html or "Architecture Intelligence" in html
    results = html[html.find('id="assessment-results"') : html.find('id="architecture-map"')]
    assert results.count('class="card health-card') == 4
    assert "<h2>Architecture Intelligence</h2>" not in results
    assert "<h2>Security Intelligence</h2>" not in results
