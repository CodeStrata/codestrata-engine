"""P01 reporting repair: urgency follows the calibrated bucket; digest labels differ."""

from __future__ import annotations

import hashlib
from pathlib import Path

from codestrata.domain.contracts.examples import example_complete
from codestrata.domain.recommendations.priority import priority_for_score
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.enums import Effort, Priority, RecommendationCategory, Risk
from codestrata.models.recommendation import Recommendation
from codestrata.models.repository import Repository
from codestrata.reporting.assessment_canonical import _working_digest
from codestrata.reporting.canonical_views import project_canonical_html, project_canonical_json
from codestrata.reporting.customer_universe import (
    CustomerFinding,
    CustomerRecommendation,
    _apply_customer_recommendation_confidence,
    _apply_customer_recommendation_priority,
)
from codestrata.reporting.engineering_health.baseline import (
    CHECKOUT_DIGEST_NOTE,
    COMMITTED_SNAPSHOT_DIGEST_LABEL,
    GIT_WORKING_STATE_DIGEST_LABEL,
    UNSPECIFIED_CHECKOUT_DIGEST_LABEL,
    project_coverage_trust,
)
from codestrata.reporting.html_v2.builder import _customer_recommendation_view
from codestrata.reporting.html_v2.leadership import (
    build_executive_summary_narrative,
    build_leadership_verdict,
)
from codestrata.reporting.html_v2.models import DashboardMetrics, FindingView, RecommendationView
from codestrata.reporting.html_v2.renderer import _priority_basis_meta_rows, _roadmap_bucket
from codestrata.reporting.prioritization import (
    presentation_bucket_for_score,
    prioritize_customer_recommendations,
)
from tests.reporting.test_canonical_views import _report


def _finding_view(*, title: str, severity: str, finding_id: str) -> FindingView:
    return FindingView(
        finding_id=finding_id,
        rule_id="rule-1",
        title=title,
        description="desc",
        severity=severity,
        category="security",
    )


def _action(
    *,
    title: str,
    bucket: str,
    priority: str = "critical",
    related: tuple[str, ...] = (),
) -> RecommendationView:
    return RecommendationView(
        recommendation_id="cred",
        title=title,
        summary="summary",
        rationale="rationale",
        priority=priority,
        category="security",
        related_finding_ids=related,
        presentation_bucket=bucket,
        priority_score=57.0,
    )


def _metrics() -> DashboardMetrics:
    return DashboardMetrics(
        file_count=10,
        technology_count=2,
        findings_count=2,
        recommendations_count=1,
        test_files_label="12",
        cicd_label="Detected",
    )


def test_future_horizon_action_is_not_an_immediate_recommendation() -> None:
    findings = (
        _finding_view(
            title="Authentication disabled",
            severity="high",
            finding_id="auth",
        ),
    )
    actions = (
        _action(
            title="Rotate credentials and remove committed secrets",
            bucket="future",
            priority="critical",
            related=("secret",),
        ),
    )
    verdict = build_leadership_verdict(
        findings=findings,
        priority_actions=actions,
        metrics=_metrics(),
        highest_severity="High",
    )
    narrative = build_executive_summary_narrative(
        findings=findings,
        priority_actions=actions,
        metrics=_metrics(),
        highest_severity="High",
        technologies=("Python",),
    )
    assert "Immediate recommendation" not in verdict
    assert "Immediate recommendation" not in narrative.what_next
    assert (
        "Future-horizon recommendation: Rotate credentials and remove committed secrets." in verdict
    )
    assert (
        "Future-horizon recommendation: Rotate credentials and remove committed secrets."
        in narrative.what_next
    )
    assert verdict.index("Authentication disabled") < verdict.index("Rotate credentials")


def test_immediate_bucket_keeps_immediate_recommendation_wording() -> None:
    findings = (
        _finding_view(
            title="Authentication disabled",
            severity="high",
            finding_id="auth",
        ),
    )
    actions = (
        _action(
            title="Rotate credentials and remove committed secrets",
            bucket="immediate",
            related=("auth",),
        ),
    )
    verdict = build_leadership_verdict(
        findings=findings,
        priority_actions=actions,
        metrics=_metrics(),
        highest_severity="High",
    )
    assert "Immediate recommendation: Rotate credentials and remove committed secrets." in verdict


def test_near_term_bucket_uses_near_term_wording() -> None:
    findings = (_finding_view(title="Missing license", severity="medium", finding_id="lic"),)
    actions = (
        _action(
            title="Add an explicit LICENSE.",
            bucket="near_term",
            priority="high",
            related=("other",),
        ),
    )
    verdict = build_leadership_verdict(
        findings=findings,
        priority_actions=actions,
        metrics=_metrics(),
        highest_severity="Medium",
    )
    assert "Immediate recommendation" not in verdict
    assert "Near-term recommendation: Add an explicit LICENSE." in verdict


def test_critical_seed_with_low_findings_stays_future_and_projects_calibrated_priority() -> None:
    finding = CustomerFinding(
        id="secret-1",
        rule_id="SEC004",
        title="Possible hardcoded credential",
        description="desc",
        severity="low",
        category="security",
        source="deterministic",
        evidence=(),
        affected_technologies=(),
        metadata={},
    )
    phase1 = Recommendation(
        rule_id="REC.SECURITY.001",
        title="Rotate credentials and remove committed secrets",
        description="Remove committed secrets.",
        rationale="Exposed credentials.",
        priority=Priority.CRITICAL,
        category=RecommendationCategory.SECURITY,
        effort=Effort.SMALL,
        risk=Risk.HIGH,
        related_finding_ids=["secret-1"],
    )
    customer = CustomerRecommendation(
        id="rec-1",
        rule_id="REC.SECURITY.001",
        title=phase1.title,
        description=phase1.description,
        rationale=phase1.rationale,
        priority="critical",
        category="security",
        effort="small",
        risk="high",
        related_finding_ids=("secret-1",),
        supporting_finding_ids=("secret-1",),
        primary_finding_id="secret-1",
        recommendation_type="finding_backed",
        evidence_completeness="complete",
        actions=("Rotate credentials",),
        dependencies=(),
        evidence=(),
        phase1=phase1,
    )
    confident = _apply_customer_recommendation_confidence(
        customer,
        findings_by_id={finding.id: finding},
    )
    calibrated = _apply_customer_recommendation_priority(
        confident,
        findings_by_id={finding.id: finding},
    )
    ordered = prioritize_customer_recommendations((calibrated,), (finding,))
    projected = ordered[0]
    assert projected.priority_assessment is not None
    score = int(projected.priority_score)
    assert presentation_bucket_for_score(float(score)) == "future"
    assert projected.presentation_bucket == "future"
    assert priority_for_score(score).value == "medium"
    assert projected.priority == "medium"
    view = _customer_recommendation_view(projected)
    assert view.priority == projected.priority
    assert view.priority != "critical"
    assert view.presentation_bucket == "future"
    assert _roadmap_bucket(view) == "Future"
    meta = _priority_basis_meta_rows(view)
    assert "Critical" not in meta
    assert projected.priority.replace("_", " ").title() in meta


def test_file_inventory_digest_hashes_sorted_paths_and_keeps_schema_key() -> None:
    result = AnalysisResult(
        repository=Repository(
            name="platform",
            path=Path("platform"),
            files=["src/b.py", "src/a.py"],
        )
    )
    digest = _working_digest(result)
    assert digest == hashlib.sha256(b"src/a.py\nsrc/b.py").hexdigest()
    envelope = example_complete()
    payload = project_canonical_json(_report(envelope))
    assert set(payload["snapshot"]) == {"source_revision", "working_state_digest"}
    html = project_canonical_html(_report(envelope))
    assert f"file-inventory digest: {envelope.body.working_state_digest}" in html
    assert "does not prove file-content equality" in html
    assert "Git working-state digest" in html
    assert "snapshot: " not in html


def test_checkout_digest_labels_follow_kind_without_renaming_the_value() -> None:
    git_view = project_coverage_trust(
        {
            "working_state_digest": "abc123",
            "working_state_digest_kind": "git_working_state",
            "dirty": False,
        }
    )
    pinned = project_coverage_trust(
        {
            "working_state_digest": "def456",
            "working_state_digest_kind": "committed_snapshot",
            "dirty": False,
        }
    )
    unspecified = project_coverage_trust({"working_state_digest": "fff000", "dirty": False})
    git_labels = {row.label: row.value for row in git_view.rows}
    pinned_labels = {row.label: row.value for row in pinned.rows}
    unspecified_labels = {row.label: row.value for row in unspecified.rows}
    assert git_labels[GIT_WORKING_STATE_DIGEST_LABEL] == "abc123"
    assert pinned_labels[COMMITTED_SNAPSHOT_DIGEST_LABEL] == "def456"
    assert unspecified_labels[UNSPECIFIED_CHECKOUT_DIGEST_LABEL] == "fff000"
    assert GIT_WORKING_STATE_DIGEST_LABEL not in unspecified_labels
    assert "file-inventory digest" in CHECKOUT_DIGEST_NOTE
    assert "does not prove file-content equality" in git_view.identity_note
