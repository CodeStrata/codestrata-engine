"""Tests for Phase 7.1.2 / 7.3 leadership presentation helpers."""

from __future__ import annotations

from codestrata.reporting.html_v2.leadership import (
    build_assessment_scope,
    build_engineering_risks,
    build_executive_summary_narrative,
    build_leadership_key_takeaways,
    build_leadership_roadmap,
    build_leadership_verdict,
    build_modernization_opportunities,
    build_priority_actions_for_leadership,
    is_leadership_signal_finding,
)
from codestrata.reporting.html_v2.models import (
    DashboardMetrics,
    FindingView,
    RecommendationView,
    ReportSummary,
)


def _finding(
    *,
    title: str,
    severity: str,
    category: str,
    finding_id: str = "f1",
    description: str = "desc",
) -> FindingView:
    return FindingView(
        finding_id=finding_id,
        rule_id="rule-1",
        title=title,
        description=description,
        severity=severity,
        category=category,
    )


def _rec(
    *,
    title: str,
    priority: str = "high",
    recommendation_id: str = "r1",
    related_finding_ids: tuple[str, ...] = (),
    presentation_bucket: str = "near_term",
    category: str = "security",
) -> RecommendationView:
    return RecommendationView(
        recommendation_id=recommendation_id,
        title=title,
        summary="summary",
        rationale="rationale",
        priority=priority,
        category=category,
        related_finding_ids=related_finding_ids,
        presentation_bucket=presentation_bucket,
        priority_score=90.0,
    )


def test_filters_informational_language_detection() -> None:
    finding = _finding(
        title="Java language detected",
        severity="informational",
        category="technology",
    )
    assert is_leadership_signal_finding(finding) is False


def test_filters_non_actionable_security_context_markers() -> None:
    finding = _finding(
        title="Credential literal in configuration",
        severity="low",
        category="security",
        description=(
            "Configuration key holds a literal. "
            "Context: CI secret reference (ci-secret-expression)."
        ),
    )
    assert is_leadership_signal_finding(finding) is False


def test_keeps_actionable_production_security_finding() -> None:
    finding = _finding(
        title="Credential literal in configuration",
        severity="high",
        category="security",
        description=(
            "Configuration key holds a literal. "
            "Context: Production source (path-production)."
        ),
    )
    assert is_leadership_signal_finding(finding) is True


def test_key_takeaways_prefer_engineering_risk_and_priority_action() -> None:
    findings = (
        _finding(
            title="Java language detected",
            severity="informational",
            category="technology",
            finding_id="noise",
        ),
        _finding(
            title="Hardcoded secret candidate",
            severity="high",
            category="security",
            finding_id="risk",
        ),
    )
    recommendations = (
        _rec(
            title="Rotate secrets",
            priority="immediate",
            related_finding_ids=("risk",),
            presentation_bucket="immediate",
        ),
    )
    metrics = DashboardMetrics(
        file_count=10,
        technology_count=2,
        findings_count=2,
        recommendations_count=1,
        has_tests=True,
        test_files_label="Present",
        cicd_label="GitHub Actions",
        cloud_signals_primary="Docker",
    )
    summary = ReportSummary(
        repository_name="demo",
        assessment_mode="deterministic",
        assessment_mode_label="Deterministic",
        total_findings=2,
        total_recommendations=1,
        ai_enrichment_status="not_requested",
        highest_finding_severity="High",
        metrics=metrics,
    )
    takeaways = build_leadership_key_takeaways(
        findings=findings,
        recommendations=recommendations,
        metrics=metrics,
        summary=summary,
        cloud_present=True,
    )
    assert 3 <= len(takeaways) <= 5
    assert "Hardcoded secret candidate" in takeaways[0]
    assert "Rotate secrets" in takeaways[1]
    assert any("CI/CD" in item or "tests" in item for item in takeaways)


def test_engineering_risks_group_by_theme() -> None:
    findings = (
        _finding(title="Secret", severity="high", category="security", finding_id="a"),
        _finding(title="Stale dep", severity="medium", category="dependency", finding_id="b"),
        _finding(title="Noise", severity="informational", category="technology", finding_id="c"),
    )
    risks = build_engineering_risks(findings)
    themes = {theme for theme, _items in risks}
    assert "Security" in themes
    assert "Dependencies" in themes
    assert "Technology" not in themes


def test_opportunities_do_not_relist_priority_actions_or_risks() -> None:
    findings = (
        _finding(
            title="Improve module boundaries",
            severity="low",
            category="architecture",
            finding_id="a",
        ),
        _finding(
            title="Secret",
            severity="medium",
            category="security",
            finding_id="b",
        ),
    )
    recommendations = (
        _rec(title="Rotate secrets", priority="immediate", recommendation_id="r1"),
        _rec(title="Add CI", priority="high", recommendation_id="r2"),
    )
    opportunities = build_modernization_opportunities(
        findings=findings,
        recommendations=recommendations,
        risk_titles=frozenset({"Secret"}),
    )
    assert any("Improve module boundaries" in item for item in opportunities)
    assert all("Secret" not in item for item in opportunities)
    assert all("Rotate secrets" not in item for item in opportunities)


def test_assessment_scope_sanitizes_config_paths() -> None:
    activation = {
        "mode": "default",
        "packs": [
            {
                "pack_id": "security",
                "enabled": False,
                "decision": "forced_off",
                "reason": "Explicit configuration override (rules.security.enabled)",
                "evidence": [],
            },
            {
                "pack_id": "dependency",
                "enabled": True,
                "decision": "enabled",
                "reason": "Dependency manifests detected",
                "evidence": ["manifest:npm:package.json"],
            },
            {
                "pack_id": "performance",
                "enabled": False,
                "decision": "skipped",
                "reason": "Performance remains opt-in under default activation",
                "evidence": [],
            },
        ],
    }
    assessed, skipped = build_assessment_scope(activation)
    assert assessed == ("Dependencies",)
    reasons = {label: reason for label, reason in skipped}
    assert "Security" in reasons
    assert "rules.security.enabled" not in reasons["Security"]
    assert "Performance" in reasons


def test_priority_actions_are_recommendation_backed_not_finding_synthesized() -> None:
    findings = (
        _finding(
            title="Framework symbol in domain boundary",
            severity="medium",
            category="architecture",
            finding_id="arch-1",
        ),
        _finding(
            title="Excessive branching",
            severity="medium",
            category="technical_debt",
            finding_id="td-1",
        ),
    )
    ungrounded = _rec(
        title="Evaluate reusable Kubernetes deployment packaging",
        priority="low",
        recommendation_id="cloud-1",
        related_finding_ids=(),
        presentation_bucket="future",
        category="cloud",
    )
    grounded = _rec(
        title="Establish a test baseline",
        priority="medium",
        recommendation_id="test-1",
        related_finding_ids=("missing-tests",),
        presentation_bucket="near_term",
        category="testing",
    )
    grounded = grounded.model_copy(
        update={"related_finding_titles": ("Missing tests",)}
    )
    actions = build_priority_actions_for_leadership(
        findings=findings,
        recommendations=(ungrounded, grounded),
    )
    assert all(item.related_finding_ids for item in actions)
    assert all("Kubernetes" not in item.title for item in actions)
    assert any(item.presentation_bucket == "near_term" for item in actions)
    # Uncovered findings must not become Priority Actions (Engineering Risks only).
    assert all(not item.recommendation_id.startswith("presentation:finding:") for item in actions)
    assert [item.recommendation_id for item in actions] == ["test-1"]
    titles = [item.title for item in actions]
    assert not any("framework" in title.lower() or "Contain framework" in title for title in titles)


def test_uncovered_findings_remain_engineering_risks_not_priority_actions() -> None:
    findings = (
        _finding(
            title="Framework symbol in domain boundary",
            severity="medium",
            category="architecture",
            finding_id="arch-1",
        ),
    )
    actions = build_priority_actions_for_leadership(
        findings=findings,
        recommendations=(),
    )
    assert actions == ()
    risks = build_engineering_risks(findings)
    assert risks
    flat = " ".join(item for _theme, items in risks for item in items).lower()
    assert "framework" in flat


def test_roadmap_order_matches_priority_actions() -> None:
    actions = (
        _rec(
            title="Establish a test baseline",
            related_finding_ids=("f1",),
            presentation_bucket="near_term",
            category="testing",
            recommendation_id="a1",
        ),
        _rec(
            title="Commit an npm lockfile",
            related_finding_ids=("f2",),
            presentation_bucket="near_term",
            category="dependency",
            recommendation_id="a2",
        ),
        _rec(
            title="Add a CI workflow",
            related_finding_ids=("f3",),
            presentation_bucket="future",
            category="ci_cd",
            recommendation_id="a3",
            priority="low",
        ),
    )
    roadmap = build_leadership_roadmap(actions)
    assert roadmap is not None
    flat_titles = [item.title for item in roadmap.initiatives]
    assert flat_titles == [item.title for item in actions]
    # Near-term actions land in Stabilize; future CI is not Stabilize-first.
    phases = {phase.phase: [i.title for i in phase.initiatives] for phase in roadmap.phases}
    assert "Establish a test baseline" in phases.get("stabilize", [])
    assert "Add a CI workflow" not in phases.get("stabilize", [])


def test_leadership_verdict_and_executive_summary_avoid_methodology() -> None:
    findings = (
        _finding(
            title="Missing tests",
            severity="medium",
            category="testing",
            finding_id="t1",
        ),
    )
    actions = build_priority_actions_for_leadership(
        findings=findings,
        recommendations=(),
    )
    metrics = DashboardMetrics(
        file_count=3,
        technology_count=2,
        findings_count=1,
        recommendations_count=1,
        test_files_label="0",
        cicd_label="Not detected",
    )
    verdict = build_leadership_verdict(
        findings=findings,
        priority_actions=actions,
        metrics=metrics,
        highest_severity="Medium",
    )
    narrative = build_executive_summary_narrative(
        findings=findings,
        priority_actions=actions,
        metrics=metrics,
        highest_severity="Medium",
        technologies=("JavaScript", "npm"),
    )
    blob = f"{verdict}\n{narrative.should_i_care}\n{narrative.why_now}\n{narrative.what_next}"
    for banned in ("deterministic", "scoring logic", "methodology", "wave_"):
        assert banned.lower() not in blob.lower()
    assert "Should I care" not in narrative.should_i_care  # value itself, not heading
    assert narrative.what_next
