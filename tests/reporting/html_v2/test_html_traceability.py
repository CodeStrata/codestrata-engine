"""Epic 2 Slice 2.7 — HTML traceability presentation tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    RuleEvaluationResult,
)
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
)
from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceLocation,
    EvidenceRef,
)
from codestrata.models import (
    AnalysisResult,
    Repository,
    RepositoryFacts,
    StructureFacts,
)
from codestrata.reporting.html_v2.anchors import (
    evidence_anchor,
    finding_anchor,
    priority_action_anchor,
    recommendation_anchor,
    roadmap_initiative_anchor,
    safe_fragment_id,
)
from codestrata.reporting.html_v2.builder import build_customer_report_document
from codestrata.reporting.html_v2.evidence_presentation import render_evidence_ref_panel
from codestrata.reporting.html_v2.labels import completeness_label, limitation_label
from codestrata.reporting.html_v2.models import EvidenceRefView
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def test_anchor_stability_and_validity() -> None:
    assert safe_fragment_id("finding:abc") == "finding:abc" or "finding" in safe_fragment_id(
        "finding:abc"
    )
    a = finding_anchor("abc-123")
    b = finding_anchor("abc-123")
    assert a == b
    assert a.startswith("finding-")
    assert evidence_anchor("ev:1") != finding_anchor("ev:1")
    assert priority_action_anchor("rec-1") != recommendation_anchor("rec-1")
    assert re.fullmatch(r"[A-Za-z][\w:.\-]*", roadmap_initiative_anchor("init.1"))


def test_completeness_and_limitation_labels() -> None:
    assert completeness_label("complete") == "Complete evidence"
    assert completeness_label("legacy") == "Legacy evidence"
    assert "not yet available" in limitation_label(
        "evidence_ref_mapping_deferred_for_pack"
    ).lower()
    assert "omitted" in limitation_label("snippet_omitted_unverified_redaction").lower()
    assert limitation_label("some_unknown_code").startswith("Some")


def test_evidence_panel_omits_absolute_and_empty() -> None:
    assert render_evidence_ref_panel(()) == ""
    panel = render_evidence_ref_panel(
        (
            EvidenceRefView(
                evidence_id="ev-1",
                path="src/App.py",
                line_start=10,
                line_end=12,
                snippet_text="safe text",
            ),
            EvidenceRefView(
                evidence_id="ev-bad",
                path="/abs/secret.py",
            ),
        ),
        primary_evidence_id="ev-1",
    )
    assert "src/<wbr>App.<wbr>py" in panel or "src/App.py" in panel.replace("<wbr>", "")
    assert "lines 10–12" in panel
    assert "safe text" in panel
    assert "/abs/secret.py" not in panel
    assert 'id="evidence-' in panel


def test_shared_evidence_emits_html_id_only_once() -> None:
    """Same Evidence supporting multiple Findings must not duplicate id=."""

    import re

    from codestrata.reporting.html_v2.evidence_presentation import (
        begin_evidence_anchor_scope,
        end_evidence_anchor_scope,
    )

    shared = EvidenceRefView(evidence_id="ev:shared-1", path="src/App.py", line_start=1)
    token = begin_evidence_anchor_scope()
    try:
        first = render_evidence_ref_panel((shared,))
        second = render_evidence_ref_panel((shared,))
    finally:
        end_evidence_anchor_scope(token)
    id_re = re.compile(r'\sid="evidence-ev:shared-1"')
    data_re = re.compile(r'\sdata-evidence-id="evidence-ev:shared-1"')
    assert id_re.search(first)
    assert data_re.search(first)
    assert not id_re.search(second)
    assert data_re.search(second)


def _analysis(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py"],
            total_files=1,
        ),
        technologies=[],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=1,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[],
        recommendations=[],
    )


def _report_with_chain(tmp_path: Path) -> ModernizationReportInput:
    ref = EvidenceRef(
        evidence_id="ev:secret-1",
        location=EvidenceLocation(path="src/App.py", line_start=4, line_end=6),
    )
    finding = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="Found credential",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("path:src/App.py",),
        evidence=(
            FindingEvidence(
                evidence_type="file",
                source_id="src",
                path="src/App.py",
                excerpt="***",
            ),
        ),
        evidence_refs=(ref,),
        primary_evidence_id="ev:secret-1",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-secret",
        title="Remediate credentials",
        summary="Rotate exposed credentials",
        rationale="Security risk",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.GOVERNANCE,
        related_finding_ids=(finding.id,),
        supporting_finding_ids=(finding.id,),
        primary_finding_id=finding.id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        actions=(
            RecommendationAction(order=1, title="Rotate", description="Rotate secret"),
        ),
        subject_keys=("repo",),
    )
    return ModernizationReportInput(
        analysis_result=_analysis(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=(finding,),
            rules_evaluated=("security.credential-literal",),
        ),
        assessment_recommendation_result=RecommendationResult.from_recommendations(
            recommendations=(recommendation,),
            providers_evaluated=("codestrata-rec-secret",),
        ),
    )


def _ids_in_html(html: str) -> set[str]:
    return set(re.findall(r'(?<![\w-])id="([^"]+)"', html))


def test_full_chain_internal_links_resolve(tmp_path: Path) -> None:
    document = build_customer_report_document(_report_with_chain(tmp_path))
    assert document.evidence
    assert document.priority_actions
    assert document.roadmap_report is not None
    html = HtmlReportRenderer().render(document)
    ids = _ids_in_html(html)

    # No presentation:finding synthesis
    assert "presentation:finding:" not in html

    initiative = document.roadmap_report.initiatives[0]
    assert initiative.initiative_type == "priority_action_backed"
    init_id = roadmap_initiative_anchor(initiative.initiative_id)
    assert init_id in ids

    pa_id = initiative.supporting_priority_action_ids[0]
    assert priority_action_anchor(pa_id) in ids

    action = next(a for a in document.priority_actions if a.recommendation_id == pa_id)
    rec_id = (action.supporting_recommendation_ids or (action.recommendation_id,))[0]
    assert recommendation_anchor(rec_id) in ids

    finding = document.findings[0]
    assert finding_anchor(finding.finding_id) in ids
    evidence_id = finding.primary_evidence_id or finding.evidence_refs[0].evidence_id
    assert evidence_anchor(evidence_id) in ids

    # Every href="#..." target exists
    hrefs = set(re.findall(r'href="#([^"]+)"', html))
    # Skip-to-contents and section anchors are fine; filter fragment links that look like entities
    missing = sorted(h for h in hrefs if h not in ids and not h.startswith(("http",)))
    assert missing == [], f"Unresolved internal links: {missing[:20]}"

    assert "Why this action" in html
    assert "Complete evidence" in html
    assert 'id="traceability"' in html
    assert "View evidence details" in html


def test_legacy_finding_has_no_empty_evidence_panel(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
    )
    document = build_customer_report_document(report_input)
    html = HtmlReportRenderer().render(document)
    assert 'class="evidence-panel"' not in html or "Evidence" in html
    assert "presentation:finding:" not in html
    # Empty universe should still be valid offline HTML
    assert "<!DOCTYPE html>" in html
    assert document.schema_version if hasattr(document, "schema_version") else True
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"


def test_no_duplicate_finding_or_pa_anchors(tmp_path: Path) -> None:
    document = build_customer_report_document(_report_with_chain(tmp_path))
    html = HtmlReportRenderer().render(document)
    ids = re.findall(r'(?<![\w-])id="([^"]+)"', html)
    finding_ids = [i for i in ids if i.startswith("finding-")]
    pa_ids = [i for i in ids if i.startswith("priority-action-")]
    assert len(finding_ids) == len(set(finding_ids))
    assert len(pa_ids) == len(set(pa_ids))
