"""Epic 3 Slice 3.9 — Modernization Assessment Intelligence section tests."""

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
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.anchors import (
    priority_action_anchor,
    roadmap_initiative_anchor,
)
from codestrata.reporting.html_v2.models import FindingView, RecommendationView
from codestrata.reporting.modernization import build_modernization_intelligence
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.roadmap.models import (
    RoadmapReportInitiativeView,
    RoadmapReportPhaseView,
    RoadmapReportSection,
)

_FORBIDDEN_CLAIMS = (
    "modernization ready",
    "transformation ready",
    "transformation-ready",
    "easy to modernize",
    "low modernization risk",
    "strong modernization foundation",
    "clear path to transformation",
    "rapid migration",
    "rapid modernization",
    "high roi",
    "low effort",
    "transformation will succeed",
    "no modernization issues",
    "no modernization need",
    "no modernization needed",
    "guaranteed outcome",
    "easy migration",
)


def _assert_no_forbidden(text: str) -> None:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish absence of modernization need", "")
        .replace("do not establish absence of modernization need", "")
        .replace("absence of priority actions does not establish", "")
        .replace("not a delivery commitment", "")
        .replace("modernization assessment", "")
        .replace("modernization need", "")
        .replace("modernization overview", "")
        .replace("modernization themes", "")
        .replace("key modernization themes", "")
        .replace("phased modernization", "")
        .replace("modernization advisor", "")
    )
    for phrase in _FORBIDDEN_CLAIMS:
        assert phrase not in sanitized, f"forbidden claim present: {phrase}"


def _pa(
    *,
    action_id: str,
    title: str,
    category: str,
    finding_ids: tuple[str, ...] = (),
    priority: str = "high",
    completeness: str = "complete",
) -> RecommendationView:
    return RecommendationView(
        recommendation_id=action_id,
        title=title,
        summary=title,
        rationale="Deterministic priority action",
        priority=priority,
        category=category,
        related_finding_ids=finding_ids,
        supporting_recommendation_ids=(action_id,),
        primary_recommendation_id=action_id,
        action_type="recommendation_backed",
        evidence_completeness=completeness,
        presentation_bucket="near_term",
        effort="medium",
    )


def _finding(
    *,
    finding_id: str,
    rule_id: str,
    category: str,
    title: str,
) -> FindingView:
    return FindingView(
        finding_id=finding_id,
        rule_id=rule_id,
        title=title,
        description=title,
        severity="high",
        category=category,
        evidence_completeness="complete",
    )


def _rec(
    *,
    recommendation_id: str,
    title: str,
    category: str,
    finding_ids: tuple[str, ...] = (),
) -> RecommendationView:
    return RecommendationView(
        recommendation_id=recommendation_id,
        title=title,
        summary=title,
        rationale=title,
        priority="high",
        category=category,
        related_finding_ids=finding_ids,
        primary_finding_id=finding_ids[0] if finding_ids else None,
        evidence_completeness="complete",
    )


def _roadmap_pa_backed(*, action_id: str, title: str) -> RoadmapReportSection:
    initiative = RoadmapReportInitiativeView(
        initiative_id=f"init:{action_id}",
        title=f"Secure — {title}",
        summary=title,
        phase="secure",
        phase_label="Secure",
        priority="high",
        effort="medium",
        risk="medium",
        expected_outcome="Reduce exposure",
        supporting_finding_ids=("f-sec",),
        supporting_recommendation_ids=(action_id,),
        supporting_priority_action_ids=(action_id,),
        primary_priority_action_id=action_id,
        initiative_type="priority_action_backed",
        evidence_completeness="complete",
        confidence="high",
        category="security",
        sequence=1,
    )
    return RoadmapReportSection(
        engine_version="0.2.0",
        status="succeeded",
        status_label="Succeeded",
        summary="Priority Action-backed roadmap",
        phases=(
            RoadmapReportPhaseView(
                phase_id="phase:secure",
                phase="secure",
                title="Secure",
                objective="Reduce exposure",
                sequence=1,
                initiative_ids=(initiative.initiative_id,),
                initiatives=(initiative,),
            ),
        ),
        initiatives=(initiative,),
        initiatives_total=1,
        initiatives_displayed=1,
        confidence="high",
        metadata={"source": "priority_actions"},
    )


def _roadmap_legacy() -> RoadmapReportSection:
    initiative = RoadmapReportInitiativeView(
        initiative_id="init:legacy-1",
        title="Legacy — Address debt",
        summary="Address debt",
        phase="modernize",
        phase_label="Modernize",
        priority="medium",
        effort="unknown",
        risk="medium",
        expected_outcome="Improve structure",
        supporting_recommendation_ids=("r-legacy",),
        initiative_type="legacy",
        evidence_completeness="legacy",
        confidence="limited",
        category="architecture",
        sequence=1,
    )
    return RoadmapReportSection(
        engine_version="0.2.0",
        status="succeeded",
        status_label="Succeeded",
        summary="Legacy recommendation-grouped roadmap",
        phases=(
            RoadmapReportPhaseView(
                phase_id="phase:modernize",
                phase="modernize",
                title="Modernize",
                objective="Address structure",
                sequence=2,
                initiative_ids=(initiative.initiative_id,),
                initiatives=(initiative,),
            ),
        ),
        initiatives=(initiative,),
        initiatives_total=1,
        initiatives_displayed=1,
        confidence="limited",
        metadata={"source": "legacy"},
    )


def test_build_uses_canonical_priority_actions_and_heads() -> None:
    security = _finding(
        finding_id="f-sec",
        rule_id="security.credential-literal",
        category="security",
        title="Literal credential",
    )
    dependency = _finding(
        finding_id="f-dep",
        rule_id="dependency.unresolved-version",
        category="dependency",
        title="Unresolved version",
    )
    rec_sec = _rec(
        recommendation_id="r-sec",
        title="Remediate credentials",
        category="security",
        finding_ids=("f-sec",),
    )
    rec_dep = _rec(
        recommendation_id="r-dep",
        title="Pin dependency versions",
        category="dependency",
        finding_ids=("f-dep",),
    )
    pa_sec = _pa(
        action_id="pa-sec",
        title="Remediate credentials",
        category="security",
        finding_ids=("f-sec",),
    )
    pa_dep = _pa(
        action_id="pa-dep",
        title="Pin dependency versions",
        category="dependency",
        finding_ids=("f-dep",),
    )
    # Synthetic Finding→PA id must never be accepted.
    fake = RecommendationView(
        recommendation_id="presentation:finding:f-sec",
        title="Fake finding action",
        summary="Fake",
        rationale="Fake",
        priority="high",
        category="security",
        related_finding_ids=("f-sec",),
        action_type="recommendation_backed",
    )
    roadmap = _roadmap_pa_backed(action_id="pa-sec", title="Remediate credentials")
    intel = build_modernization_intelligence(
        findings=(security, dependency),
        recommendations=(rec_sec, rec_dep),
        priority_actions=(pa_sec, pa_dep, fake),
        roadmap_report=roadmap,
    )
    assert {item.action_id for item in intel.priority_actions} == {"pa-sec", "pa-dep"}
    assert all(
        not item.action_id.startswith("presentation:finding:")
        for item in intel.priority_actions
    )
    head_ids = {item.head_id for item in intel.contributing_heads}
    assert "security_intelligence" in head_ids
    assert "dependency_intelligence" in head_ids
    # Entities keep original heads — security is not reclassified as modernization.
    sec_head = next(
        item for item in intel.contributing_heads if item.head_id == "security_intelligence"
    )
    assert sec_head.priority_action_count >= 1
    dep_head = next(
        item for item in intel.contributing_heads if item.head_id == "dependency_intelligence"
    )
    assert dep_head.priority_action_count >= 1
    assert intel.uses_canonical_roadmap is True
    assert intel.roadmap_is_legacy is False
    assert intel.roadmap_phases
    assert intel.themes
    theme_ids = {item.head_id for item in intel.themes}
    assert "security_intelligence" in theme_ids
    assert "dependency_intelligence" in theme_ids
    assert "platform transformation" not in " ".join(
        t for theme in intel.themes for t in theme.top_titles
    ).lower()
    joined = " ".join(intel.limitations).lower()
    assert "derived from enabled assessment heads" in joined
    assert "no delivery estimate" in joined
    assert "no cost estimate" in joined
    assert "no staffing estimate" in joined
    assert "no business-case or roi" in joined
    assert "not a delivery commitment" in joined
    assert "does not establish absence of modernization need" in joined
    _assert_no_forbidden(intel.status_summary)
    _assert_no_forbidden(" ".join(intel.limitations))


def test_zero_actions_does_not_claim_no_modernization_need() -> None:
    intel = build_modernization_intelligence(
        findings=(),
        recommendations=(),
        priority_actions=(),
        roadmap_report=None,
    )
    assert intel.priority_action_count == 0
    assert intel.empty_actions_message is not None
    lowered = intel.empty_actions_message.lower()
    assert "no deterministic modernization priority actions" in lowered
    assert "does not establish absence of modernization need" in lowered
    assert "no modernization needed" not in lowered
    assert "no modernization need" not in lowered.replace(
        "absence of modernization need", ""
    )
    overview = " ".join(
        f"{fact.label} {fact.value} {fact.note or ''}" for fact in intel.overview_facts
    ).lower()
    assert "does not establish absence of modernization need" in overview
    _assert_no_forbidden(intel.empty_actions_message)


def test_legacy_roadmap_visibly_marked() -> None:
    intel = build_modernization_intelligence(
        findings=(),
        recommendations=(),
        priority_actions=(),
        roadmap_report=_roadmap_legacy(),
    )
    assert intel.roadmap_is_legacy is True
    assert intel.uses_canonical_roadmap is False
    assert intel.roadmap_phases
    assert all(phase.has_legacy for phase in intel.roadmap_phases)
    for phase in intel.roadmap_phases:
        for initiative in phase.initiatives:
            assert initiative.is_legacy is True
            assert initiative.supporting_priority_action_ids == ()
    assert any("legacy" in note.lower() for note in intel.limitations)


def test_soft_claims_scrubbed() -> None:
    from codestrata.reporting.modernization import scrub_soft_modernization_claims

    scrubbed = scrub_soft_modernization_claims(
        "Modernization ready with high ROI and rapid migration possible.",
        fallback="safe fallback",
    )
    assert scrubbed == "safe fallback"
    ok = scrub_soft_modernization_claims(
        "The modernization assessment synthesizes deterministic findings.",
        fallback="safe fallback",
    )
    assert "synthesizes deterministic findings" in ok.lower()


def test_html_modernization_assessment_section(tmp_path: Path) -> None:
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
    report_input = ModernizationReportInput(
        analysis_result=analysis,
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
    document = build_html_report_view_model(report_input)
    assert document.modernization_intelligence is not None
    assert document.priority_actions
    assert document.roadmap_report is not None
    html = HtmlReportRenderer().render(document)

    assert 'id="modernization-assessment"' in html
    assert 'href="#modernization-assessment"' in html
    assert "Modernization overview" in html
    assert "Contributing assessment heads" in html
    assert "Priority Actions" in html
    assert "Roadmap phases" in html
    assert "Key modernization themes" in html
    assert "Coverage" in html
    assert "Confidence" in html
    assert "Limitations" in html
    assert "Security Intelligence" in html
    assert "planning guidance, not a delivery commitment" in html.lower()
    assert "does not establish absence of modernization need" in html.lower()
    assert "presentation:finding:" not in html
    assert "modernization ready" not in html.lower()
    assert "high roi" not in html.lower()
    assert "no modernization needed" not in html.lower()
    # AI Advisor is separate when present; deterministic section must not include advisor narrative.
    assert "Optional AI Enhancements" not in html or 'id="modernization-advisor"' in html
    assert document.ai_enrichment is None or "Modernization Advisor" in html

    # Canonical PA / roadmap anchors remain; no duplicate detail anchors from synthesis.
    ids = re.findall(r'(?<![\w-])id="([^"]+)"', html)
    pa_ids = [i for i in ids if i.startswith("priority-action-")]
    init_ids = [i for i in ids if i.startswith("roadmap-initiative-")]
    assert len(pa_ids) == len(set(pa_ids))
    assert len(init_ids) == len(set(init_ids))

    initiative = document.roadmap_report.initiatives[0]
    pa_id = initiative.supporting_priority_action_ids[0]
    assert f'href="#{priority_action_anchor(pa_id)}"' in html
    assert f'href="#{roadmap_initiative_anchor(initiative.initiative_id)}"' in html
    assert 'href="#priority-actions"' in html
    assert 'href="#phased-modernization-plan"' in html

    # Other assessment-head anchors unchanged.
    for anchor in (
        "technology-inventory",
        "architecture-intelligence",
        "technical-debt-intelligence",
        "dependency-intelligence",
        "security-intelligence",
        "cloud-readiness",
        "ai-readiness",
        "modernization-assessment",
    ):
        assert f'id="{anchor}"' in html

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    _assert_no_forbidden(html)


def test_no_cost_roi_timeline_staffing_claims() -> None:
    intel = build_modernization_intelligence(
        findings=(),
        recommendations=(),
        priority_actions=(),
        roadmap_report=None,
    )
    blob = " ".join(
        [
            intel.status_summary,
            *intel.limitations,
            *(f"{f.label} {f.value} {f.note or ''}" for f in intel.overview_facts),
        ]
    ).lower()
    assert "no delivery estimate was produced" in blob
    assert "no cost estimate was produced" in blob
    assert "no staffing estimate was produced" in blob
    assert "no business-case or roi analysis was performed" in blob
    assert "delivery commitment" in blob
    assert "3 months" not in blob
    assert "staff of" not in blob
    assert "$" not in blob


def test_security_and_dependency_not_reclassified() -> None:
    security = _finding(
        finding_id="f-sec",
        rule_id="security.private-key",
        category="security",
        title="Private key",
    )
    dependency = _finding(
        finding_id="f-dep",
        rule_id="dependency.unresolved-version",
        category="dependency",
        title="Unresolved",
    )
    pa_sec = _pa(
        action_id="pa-sec",
        title="Remediate key material",
        category="security",
        finding_ids=("f-sec",),
    )
    pa_dep = _pa(
        action_id="pa-dep",
        title="Pin versions",
        category="dependency",
        finding_ids=("f-dep",),
    )
    intel = build_modernization_intelligence(
        findings=(security, dependency),
        recommendations=(),
        priority_actions=(pa_sec, pa_dep),
        roadmap_report=None,
    )
    by_action = {item.action_id: item for item in intel.priority_actions}
    assert by_action["pa-sec"].head_id == "security_intelligence"
    assert by_action["pa-sec"].head_title == "Security Intelligence"
    assert by_action["pa-dep"].head_id == "dependency_intelligence"
    assert by_action["pa-dep"].head_title == "Dependency Intelligence"
    assert all(item.head_id != "modernization_assessment" for item in intel.priority_actions)
