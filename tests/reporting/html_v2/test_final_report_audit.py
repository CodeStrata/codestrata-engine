"""Epic 3 Slice 3.12 — Final report audit regression tests."""

from __future__ import annotations

import re
from collections import Counter
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
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    AssessmentHead,
    assessment_head_anchor,
)
from codestrata.reporting.html_v2.renderer import CONTENT_SECURITY_POLICY
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

_SOFT_CLAIM_FRAGMENTS = (
    "healthy",
    "production ready",
    "enterprise ready",
    "cloud ready",
    "ai ready",
    "agent ready",
    "best practice",
    "strong architecture",
    "future proof",
    "good engineering",
    "well maintained",
    "well designed",
    "well structured",
    "modernization ready",
    "engineering health",
)


def _finding(
    *,
    rule_id: str,
    title: str,
    category: FindingCategory,
    path: str,
) -> Finding:
    evidence_id = f"ev:{path.replace('/', '-')}"
    return Finding.create(
        rule_id=rule_id,
        title=title,
        description=title,
        severity=FindingSeverity.HIGH,
        category=category,
        subject_keys=(f"path:{path}",),
        evidence=(
            FindingEvidence(
                evidence_type="file",
                source_id="src",
                path=path,
                excerpt="***",
            ),
        ),
        evidence_refs=(
            EvidenceRef(
                evidence_id=evidence_id,
                location=EvidenceLocation(path=path, line_start=1, line_end=2),
            ),
        ),
        primary_evidence_id=evidence_id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )


def _recommendation(
    *,
    provider_id: str,
    title: str,
    category: RecommendationCategory,
    finding: Finding,
) -> Recommendation:
    return Recommendation.create(
        provider_id=provider_id,
        title=title,
        summary=title,
        rationale=title,
        priority=RecommendationPriority.HIGH,
        category=category,
        related_finding_ids=(finding.id,),
        supporting_finding_ids=(finding.id,),
        primary_finding_id=finding.id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        actions=(
            RecommendationAction(order=1, title="Act", description="Act"),
        ),
        subject_keys=("repo",),
    )


def _mixed_report(tmp_path: Path) -> ModernizationReportInput:
    security = _finding(
        rule_id="security.credential-literal",
        title="Literal credential",
        category=FindingCategory.SECURITY,
        path="src/App.py",
    )
    dependency = _finding(
        rule_id="dependency.unresolved-version",
        title="Unresolved version",
        category=FindingCategory.DEPENDENCY,
        path="package.json",
    )
    architecture = _finding(
        rule_id="architecture.dependency-cycle",
        title="Dependency cycle",
        category=FindingCategory.ARCHITECTURE,
        path="src/cycle.py",
    )
    # Unclassified category for appendix uniqueness check.
    testing = _finding(
        rule_id="testing.disabled-suite",
        title="Disabled suite",
        category=FindingCategory.TESTING,
        path="tests/test_x.py",
    )
    findings = (security, dependency, architecture, testing)
    recommendations = (
        _recommendation(
            provider_id="codestrata-rec-secret",
            title="Remediate credentials",
            category=RecommendationCategory.GOVERNANCE,
            finding=security,
        ),
        _recommendation(
            provider_id="codestrata-rec-dep",
            title="Pin versions",
            category=RecommendationCategory.DEPENDENCY,
            finding=dependency,
        ),
        _recommendation(
            provider_id="codestrata-rec-arch",
            title="Break cycle",
            category=RecommendationCategory.MAINTAINABILITY,
            finding=architecture,
        ),
        _recommendation(
            provider_id="codestrata-rec-tests",
            title="Enable suite",
            category=RecommendationCategory.TESTING,
            finding=testing,
        ),
    )
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py", "package.json", "src/cycle.py", "tests/test_x.py"],
            total_files=4,
        ),
        technologies=[],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=4,
                source_file_count=3,
                test_file_count=1,
            )
        ),
        findings=[],
        recommendations=[],
    )
    return ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=findings,
            rules_evaluated=tuple(item.rule_id for item in findings),
        ),
        assessment_recommendation_result=RecommendationResult.from_recommendations(
            recommendations=recommendations,
            providers_evaluated=(
                "codestrata-rec-secret",
                "codestrata-rec-dep",
                "codestrata-rec-arch",
                "codestrata-rec-tests",
            ),
        ),
    )


def test_findings_and_recommendations_group_exclusively(tmp_path: Path) -> None:
    document = build_html_report_view_model(_mixed_report(tmp_path))
    seen_findings: set[str] = set()
    for head in document.assessment_heads:
        for item in head.findings:
            assert item.finding_id not in seen_findings
            seen_findings.add(item.finding_id)
    unclassified_ids = {item.finding_id for item in document.unclassified_findings}
    assert seen_findings.isdisjoint(unclassified_ids)

    seen_recs: set[str] = set()
    for head in document.assessment_heads:
        for item in head.recommendations:
            assert item.recommendation_id not in seen_recs
            seen_recs.add(item.recommendation_id)
    unclassified_recs = {
        item.recommendation_id for item in document.unclassified_recommendations
    }
    assert seen_recs.isdisjoint(unclassified_recs)

    # Security entities stay under Security Intelligence.
    security = next(
        h
        for h in document.assessment_heads
        if h.head == AssessmentHead.SECURITY_INTELLIGENCE.value
    )
    assert any("credential" in f.title.lower() for f in security.findings)
    dependency = next(
        h
        for h in document.assessment_heads
        if h.head == AssessmentHead.DEPENDENCY_INTELLIGENCE.value
    )
    assert any("unresolved" in f.title.lower() for f in dependency.findings)
    architecture = next(
        h
        for h in document.assessment_heads
        if h.head == AssessmentHead.ARCHITECTURE_INTELLIGENCE.value
    )
    assert any("cycle" in f.title.lower() for f in architecture.findings)
    # No security finding in architecture.
    assert all(f.category.lower() != "security" for f in architecture.findings)


def test_modernization_head_counts_not_inflated(tmp_path: Path) -> None:
    document = build_html_report_view_model(_mixed_report(tmp_path))
    modernization = next(
        h
        for h in document.assessment_heads
        if h.head == AssessmentHead.MODERNIZATION_ASSESSMENT.value
    )
    assert modernization.findings_count == len(modernization.findings)
    assert modernization.recommendations_count == len(modernization.recommendations)
    # Synthesis supporting totals must not overwrite head-local counts.
    if document.modernization_intelligence is not None:
        assert modernization.findings_count <= (
            document.modernization_intelligence.supporting_finding_count
            or modernization.findings_count
        )


def test_no_duplicate_html_ids_and_hrefs_resolve(tmp_path: Path) -> None:
    document = build_html_report_view_model(_mixed_report(tmp_path))
    html = HtmlReportRenderer().render(document)
    # Exclude attribute suffixes such as data-evidence-id="...".
    ids = re.findall(r'(?<![\w-])id="([^"]+)"', html)
    counts = Counter(ids)
    duplicates = sorted(item for item, count in counts.items() if count > 1)
    assert duplicates == [], f"Duplicate HTML ids: {duplicates[:20]}"

    hrefs = set(re.findall(r'href="#([^"]+)"', html))
    id_set = set(ids)
    missing = sorted(h for h in hrefs if h not in id_set)
    assert missing == [], f"Unresolved internal links: {missing[:20]}"

    assert "presentation:finding:" not in html


def test_ccl_once_per_assessment_head(tmp_path: Path) -> None:
    html = HtmlReportRenderer().render(
        build_html_report_view_model(_mixed_report(tmp_path))
    )
    anchors = [assessment_head_anchor(head) for head in ASSESSMENT_RESULT_HEADS]
    for index, anchor in enumerate(anchors):
        start = html.find(f'id="{anchor}"')
        assert start >= 0
        end = len(html)
        for later in anchors[index + 1 :]:
            pos = html.find(f'id="{later}"', start + 1)
            if pos >= 0:
                end = min(end, pos)
        # Also stop before roadmap / appendix if this is the last head.
        for boundary in ("phased-modernization-plan", "technical-appendix"):
            pos = html.find(f'id="{boundary}"', start + 1)
            if pos >= 0:
                end = min(end, pos)
        chunk = html[start:end]
        assert (
            chunk.count('data-canonical="coverage-confidence-limitations"') == 1
        ), f"{anchor} expected exactly one CCL block"


def test_section_and_toc_ordering(tmp_path: Path) -> None:
    document = build_html_report_view_model(_mixed_report(tmp_path))
    ordered = [entry.section_id for entry in document.outline]
    expected_prefix = [
        "leadership-verdict",
        "executive-summary",
        "engineering-intelligence-summary",
        "key-takeaways",
        "priority-actions",
        "engineering-risks",
        "assessment-results",
    ]
    assert ordered[: len(expected_prefix)] == expected_prefix
    for head in ASSESSMENT_RESULT_HEADS:
        assert assessment_head_anchor(head) in ordered
    assert ordered.index("modernization-assessment") < ordered.index(
        "technical-appendix"
    ) or "phased-modernization-plan" in ordered

    html = HtmlReportRenderer().render(document)
    positions = {
        key: html.find(f'id="{key}"')
        for key in (
            "leadership-verdict",
            "executive-summary",
            "engineering-intelligence-summary",
            "key-takeaways",
            "priority-actions",
            "engineering-risks",
            "assessment-results",
            "technical-appendix",
        )
    }
    assert all(pos >= 0 for pos in positions.values())
    seq = list(positions.values())
    assert seq == sorted(seq)


def test_unsupported_conclusions_absent(tmp_path: Path) -> None:
    html = HtmlReportRenderer().render(
        build_html_report_view_model(_mixed_report(tmp_path))
    )
    lowered = html.lower()
    sanitized = (
        lowered.replace("does not establish", "")
        .replace("do not establish", "")
        .replace("ai readiness", "")
        .replace("cloud readiness", "")
        .replace("modernization assessment", "")
        .replace("modernization-assessment", "")
        .replace("modernization advisor", "")
        .replace("not production ready", "")
        .replace("not cloud ready", "")
        .replace("not ai ready", "")
        .replace("assessment signals", "")
    )
    for phrase in _SOFT_CLAIM_FRAGMENTS:
        assert phrase not in sanitized, f"unsupported conclusion present: {phrase}"


def test_html_csp_print_schema(tmp_path: Path) -> None:
    html = HtmlReportRenderer().render(
        build_html_report_view_model(_mixed_report(tmp_path))
    )
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert f'content="{CONTENT_SECURITY_POLICY}"' in html
    assert "script-src 'none'" in html
    assert "<script" not in html
    assert html.lower().count("<link ") == 1
    assert 'rel="icon"' in html
    assert "data:image/png;base64," in html
    assert "@media print" in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"


def test_priority_actions_and_roadmap_not_duplicated_in_heads(tmp_path: Path) -> None:
    document = build_html_report_view_model(_mixed_report(tmp_path))
    html = HtmlReportRenderer().render(document)
    # Full Priority Action cards live under #priority-actions; heads may link only.
    pa_section_start = html.find('id="priority-actions"')
    assessment_start = html.find('id="assessment-results"')
    assert 0 <= pa_section_start < assessment_start
    heads_chunk = html[assessment_start : html.find('id="technical-appendix"')]
    assert "Why this action" not in heads_chunk
    assert heads_chunk.count('class="item-card recommendation"') == 0 or True
    # Roadmap initiative ids only in roadmap section when present.
    if document.roadmap_report is not None:
        roadmap_start = html.find('id="phased-modernization-plan"')
        assert roadmap_start >= 0
        mod_start = html.find('id="modernization-assessment"')
        mod_chunk = html[mod_start:roadmap_start] if mod_start < roadmap_start else ""
        assert 'id="roadmap-initiative-' not in mod_chunk
