"""Tests for Phase 7.1.3 deterministic recommendation prioritization."""

from __future__ import annotations

from codestrata.reporting.customer_universe import CustomerFinding, CustomerRecommendation
from codestrata.reporting.prioritization import (
    BUCKET_FUTURE,
    BUCKET_IMMEDIATE,
    BUCKET_NEAR_TERM,
    compute_priority_score,
    grounded_recommendations,
    prioritize_customer_recommendations,
)


def _finding(
    *,
    finding_id: str,
    title: str,
    severity: str,
    category: str = "security",
) -> CustomerFinding:
    return CustomerFinding(
        id=finding_id,
        rule_id="rule",
        title=title,
        description="desc",
        severity=severity,
        category=category,
        source="deterministic",
        evidence=(),
        affected_technologies=(),
        metadata={},
    )


def _rec(
    *,
    recommendation_id: str,
    title: str,
    priority: str,
    category: str = "security",
    effort: str = "medium",
    risk: str = "medium",
    related: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
) -> CustomerRecommendation:
    return CustomerRecommendation(
        id=recommendation_id,
        rule_id="prov",
        title=title,
        description="desc",
        rationale="why",
        priority=priority,
        category=category,
        effort=effort,
        risk=risk,
        related_finding_ids=related,
        actions=("Do the thing",),
        dependencies=dependencies,
        evidence=(),
    )


def test_critical_security_outranks_low_effort_future_work() -> None:
    findings = (
        _finding(finding_id="f-crit", title="Secret", severity="critical"),
        _finding(finding_id="f-low", title="Docs", severity="low", category="testing"),
    )
    recommendations = (
        _rec(
            recommendation_id="r-low",
            title="Improve docs",
            priority="low",
            category="testing",
            effort="small",
            risk="low",
            related=("f-low",),
        ),
        _rec(
            recommendation_id="r-crit",
            title="Rotate secrets",
            priority="immediate",
            category="security",
            effort="small",
            risk="high",
            related=("f-crit",),
        ),
    )
    ordered = prioritize_customer_recommendations(recommendations, findings)
    assert ordered[0].id == "r-crit"
    assert ordered[0].presentation_bucket == BUCKET_IMMEDIATE
    assert ordered[0].priority_score > ordered[1].priority_score


def test_score_is_deterministic() -> None:
    findings = (
        _finding(
            finding_id="f1",
            title="Lockfile",
            severity="high",
            category="dependency",
        ),
    )
    recommendations = (
        _rec(
            recommendation_id="r1",
            title="Add lockfile",
            priority="high",
            category="dependency",
            related=("f1",),
        ),
    )
    first = compute_priority_score(
        recommendations[0],
        finding_severity_by_id={"f1": "high"},
    )
    second = compute_priority_score(
        recommendations[0],
        finding_severity_by_id={"f1": "high"},
    )
    assert first == second
    ordered_a = prioritize_customer_recommendations(recommendations, findings)
    ordered_b = prioritize_customer_recommendations(recommendations, findings)
    assert [item.id for item in ordered_a] == [item.id for item in ordered_b]
    assert ordered_a[0].presentation_bucket == ordered_b[0].presentation_bucket


def test_dependencies_reduce_score() -> None:
    base = _rec(
        recommendation_id="r1",
        title="Blocked work",
        priority="high",
        related=("f1",),
        dependencies=(),
    )
    blocked = _rec(
        recommendation_id="r2",
        title="Blocked work",
        priority="high",
        related=("f1",),
        dependencies=("r0", "r00"),
    )
    score_base = compute_priority_score(base, finding_severity_by_id={"f1": "high"})
    score_blocked = compute_priority_score(blocked, finding_severity_by_id={"f1": "high"})
    assert score_blocked < score_base


def test_grounded_filter_requires_findings() -> None:
    recommendations = (
        _rec(recommendation_id="r1", title="With finding", priority="high", related=("f1",)),
        _rec(recommendation_id="r2", title="Orphan", priority="high", related=()),
    )
    grounded = grounded_recommendations(recommendations)
    assert [item.id for item in grounded] == ["r1"]


def test_bucket_thresholds() -> None:
    findings = (
        _finding(finding_id="f-c", title="C", severity="critical"),
        _finding(finding_id="f-m", title="M", severity="medium"),
        _finding(finding_id="f-l", title="L", severity="low"),
    )
    recommendations = (
        _rec(
            recommendation_id="imm",
            title="Immediate",
            priority="immediate",
            risk="high",
            effort="small",
            related=("f-c",),
        ),
        _rec(
            recommendation_id="near",
            title="Near",
            priority="medium",
            risk="medium",
            effort="medium",
            related=("f-m",),
            category="architecture",
        ),
        _rec(
            recommendation_id="fut",
            title="Future",
            priority="low",
            risk="low",
            effort="large",
            related=("f-l",),
            category="performance",
        ),
    )
    ordered = prioritize_customer_recommendations(recommendations, findings)
    by_id = {item.id: item for item in ordered}
    assert by_id["imm"].presentation_bucket == BUCKET_IMMEDIATE
    assert by_id["near"].presentation_bucket in {BUCKET_NEAR_TERM, BUCKET_IMMEDIATE}
    assert by_id["fut"].presentation_bucket == BUCKET_FUTURE
