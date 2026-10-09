"""Tests for E10.2 / M30 thresholded outcome movement and driver classification."""

from __future__ import annotations

from codestrata.application.incremental.outcome_movement import (
    evaluate_outcome_movement,
)
from codestrata.domain.contracts.driver_manifest import build_outcome_driver_manifest
from codestrata.domain.contracts.enums import DriverKind, OutcomeFamily, OutcomeMovement
from codestrata.domain.contracts.models import OutcomeDriver
from codestrata.models.scan_comparison import (
    ComparedFinding,
    MetricDelta,
)


def _compared_finding(
    *,
    rule_id: str,
    identity_key: str,
    lifecycle: str,
    title: str = "Test Finding",
    category: str = "security",
    severity: str = "high",
) -> ComparedFinding:
    return ComparedFinding(
        rule_id=rule_id,
        identity_key=identity_key,
        lifecycle=lifecycle,
        title=title,
        category=category,
        severity=severity,
    )


def test_outcome_manifest_loading() -> None:
    manifest = build_outcome_driver_manifest()
    assert manifest is not None
    assert manifest.manifest_version == "1.0.0"
    assert len(manifest.drivers) > 0
    # Families covered
    families = {d.family.value.lower() for d in manifest.drivers}
    assert "architecture" in families
    assert "security" in families
    assert "quality" in families


def test_outcome_movement_all_unchanged_is_stable() -> None:
    # No finding deltas, no metric changes beyond epsilon
    metric_deltas = [
        MetricDelta(
            metric_name="m01_coverage",
            unit="ratio",
            base_value=0.85,
            candidate_value=0.85,
            delta=0.0,
        ),
    ]

    verdicts, overall = evaluate_outcome_movement(
        compared_findings=[],
        metric_deltas=metric_deltas,
        baseline_available=True,
    )

    for family in ["architecture", "security", "quality"]:
        assert verdicts[family].verdict == OutcomeMovement.STABLE.value
        assert verdicts[family].favorable_count == 0
        assert verdicts[family].unfavorable_count == 0
    assert overall == OutcomeMovement.STABLE


def test_outcome_movement_only_improvement() -> None:
    manifest = build_outcome_driver_manifest()
    # Find a rule driver for security
    sec_rule = next(
        d for d in manifest.drivers
        if d.family.value.lower() == "security"
        and d.kind == "rule"
        and d.outcome_or_context_role == "outcome_driver"
    )

    findings = [
        _compared_finding(
            rule_id=sec_rule.id,
            identity_key="sqli_1",
            lifecycle="resolved",
        )
    ]

    verdicts, overall = evaluate_outcome_movement(
        compared_findings=findings,
        metric_deltas=[],
        baseline_available=True,
    )

    sec_verdict = verdicts["security"]
    assert sec_verdict.verdict == OutcomeMovement.IMPROVED.value
    assert sec_verdict.favorable_count >= 1
    assert sec_verdict.unfavorable_count == 0


def test_outcome_movement_only_deterioration() -> None:
    manifest = build_outcome_driver_manifest()
    sec_rule = next(
        d for d in manifest.drivers
        if d.family.value.lower() == "security"
        and d.kind == "rule"
        and d.outcome_or_context_role == "outcome_driver"
    )

    findings = [
        _compared_finding(
            rule_id=sec_rule.id,
            identity_key="sqli_2",
            lifecycle="new",
        )
    ]

    verdicts, overall = evaluate_outcome_movement(
        compared_findings=findings,
        metric_deltas=[],
        baseline_available=True,
    )

    sec_verdict = verdicts["security"]
    assert sec_verdict.verdict == OutcomeMovement.DETERIORATED.value
    assert sec_verdict.unfavorable_count >= 1
    assert sec_verdict.favorable_count == 0
    assert overall == OutcomeMovement.DETERIORATED


def test_outcome_movement_mixed() -> None:
    manifest = build_outcome_driver_manifest()
    sec_rules = [
        d for d in manifest.drivers
        if d.family.value.lower() == "security"
        and d.kind == "rule"
        and d.outcome_or_context_role == "outcome_driver"
    ]
    r1 = sec_rules[0]
    r2 = sec_rules[1] if len(sec_rules) > 1 else sec_rules[0]

    findings = [
        _compared_finding(
            rule_id=r1.id,
            identity_key="k1",
            lifecycle="new",
        ),
        _compared_finding(
            rule_id=r2.id,
            identity_key="k2",
            lifecycle="resolved",
        ),
    ]

    verdicts, overall = evaluate_outcome_movement(
        compared_findings=findings,
        metric_deltas=[],
        baseline_available=True,
    )

    sec_verdict = verdicts["security"]
    assert sec_verdict.verdict == OutcomeMovement.MIXED.value
    assert sec_verdict.favorable_count >= 1
    assert sec_verdict.unfavorable_count >= 1
    assert overall == OutcomeMovement.MIXED


def test_outcome_movement_coverage_drop_insufficient() -> None:
    verdicts, overall = evaluate_outcome_movement(
        compared_findings=[],
        metric_deltas=[],
        baseline_available=True,
        overall_coverage_pass=False,
    )

    for family in ["architecture", "security", "quality"]:
        assert verdicts[family].verdict == OutcomeMovement.INSUFFICIENT.value
    assert overall == OutcomeMovement.INSUFFICIENT


def test_outcome_movement_exact_epsilon_boundary() -> None:
    # 1. Count metric driver with epsilon 0: delta 0 is stable, delta 1 is deteriorated
    count_driver = OutcomeDriver(
        id="test.count_metric",
        kind=DriverKind.METRIC,
        family=OutcomeFamily.QUALITY,
        outcome_or_context_role="outcome_driver",
        applicability="applicable",
        direction="lower_count_favorable",
        comparison_unit="count",
        epsilon="0",
        coverage_requirement="full",
        empty_scope="not_applicable",
    )
    md_count_zero = MetricDelta(
        metric_name=count_driver.id,
        unit="count",
        base_value=2,
        candidate_value=2,
        delta=0,
        compatible=True,
        coverage_status="pass",
    )
    verdicts_count_zero, _ = evaluate_outcome_movement(
        manifest_drivers=[count_driver],
        compared_findings=[],
        metric_deltas=[md_count_zero],
        baseline_available=True,
    )
    assert verdicts_count_zero["quality"].verdict == OutcomeMovement.STABLE.value

    # 2. Ratio metric driver with epsilon 0.01:
    ratio_driver = OutcomeDriver(
        id="test.ratio_metric",
        kind=DriverKind.METRIC,
        family=OutcomeFamily.QUALITY,
        outcome_or_context_role="outcome_driver",
        applicability="applicable",
        direction="lower_ratio_favorable",
        comparison_unit="ratio",
        epsilon="0.01",
        coverage_requirement="full",
        empty_scope="not_applicable",
    )
    # Delta below epsilon (0.005 <= 0.01) -> stable
    md_sub = MetricDelta(
        metric_name=ratio_driver.id,
        unit="ratio",
        base_value=1.0,
        candidate_value=1.005,
        delta=0.005,
        compatible=True,
        coverage_status="pass",
    )
    verdicts_sub, _ = evaluate_outcome_movement(
        manifest_drivers=[ratio_driver],
        compared_findings=[],
        metric_deltas=[md_sub],
        baseline_available=True,
    )
    assert verdicts_sub["quality"].verdict == OutcomeMovement.STABLE.value

    # Delta above epsilon (0.05 > 0.01) -> deteriorated
    md_above = MetricDelta(
        metric_name=ratio_driver.id,
        unit="ratio",
        base_value=1.0,
        candidate_value=1.05,
        delta=0.05,
        compatible=True,
        coverage_status="pass",
    )
    verdicts_above, _ = evaluate_outcome_movement(
        manifest_drivers=[ratio_driver],
        compared_findings=[],
        metric_deltas=[md_above],
        baseline_available=True,
    )
    assert verdicts_above["quality"].verdict == OutcomeMovement.DETERIORATED.value


def test_outcome_movement_empty_outcome_not_applicable() -> None:
    verdicts, overall = evaluate_outcome_movement(
        manifest_drivers=[],
        is_empty_outcome=True,
    )

    for _family, verdict in verdicts.items():
        assert verdict.verdict == OutcomeMovement.NOT_APPLICABLE.value
    assert overall == OutcomeMovement.NOT_APPLICABLE


def test_outcome_movement_surviving_known_violation_with_partial_coverage() -> None:
    manifest = build_outcome_driver_manifest()
    sec_rule = next(
        d for d in manifest.drivers
        if d.family.value.lower() == "security"
        and d.kind == "rule"
        and d.outcome_or_context_role == "outcome_driver"
    )

    findings = [
        _compared_finding(
            rule_id=sec_rule.id,
            identity_key="sqli_crit",
            lifecycle="new",
        )
    ]

    verdicts, overall = evaluate_outcome_movement(
        compared_findings=findings,
        metric_deltas=[],
        baseline_available=True,
        overall_coverage_pass=False,  # Incomplete coverage
    )

    sec_verdict = verdicts["security"]
    # Due to precedence: INSUFFICIENT > MIXED > DETERIORATED, overall family verdict is INSUFFICIENT
    assert sec_verdict.verdict == OutcomeMovement.INSUFFICIENT.value
    # But the known violation survives in unfavorable_count and drivers!
    assert sec_verdict.unfavorable_count >= 1
    assert any(d.movement == "unfavorable" for d in sec_verdict.qualifying_drivers)


def test_unparseable_delta_is_insufficient_not_stable() -> None:
    driver = OutcomeDriver(
        id="M13.known_vulnerability",
        kind=DriverKind.METRIC,
        family=OutcomeFamily.SECURITY,
        outcome_or_context_role="outcome_driver",
        applicability="applicable",
        direction="lower_count_favorable",
        comparison_unit="count",
        epsilon="0",
        coverage_requirement="required",
        empty_scope="not_applicable",
    )
    verdicts, overall = evaluate_outcome_movement(
        metric_deltas=[
            MetricDelta(
                metric_name="M13.known_vulnerability",
                unit="count",
                base_value=1,
                candidate_value=1,
                delta="not-a-number",
            )
        ],
        manifest_drivers=(driver,),
        baseline_available=True,
    )
    security = verdicts["security"]
    assert security.verdict == OutcomeMovement.INSUFFICIENT.value
    assert overall == OutcomeMovement.INSUFFICIENT
    assert security.qualifying_drivers[0].movement == "insufficient"
    assert security.qualifying_drivers[0].notes == "unparseable_delta"
    assert overall != OutcomeMovement.STABLE


def test_series_pair_public_projection_maps_testing_under_quality() -> None:
    from codestrata.application.incremental.trend_comparisons import (
        PUBLIC_OUTCOME_FAMILIES,
        TESTING_MAPS_UNDER,
        public_outcome_verdicts,
    )

    verdicts, _overall = evaluate_outcome_movement(
        compared_findings=[],
        metric_deltas=[],
        baseline_available=True,
    )
    public = public_outcome_verdicts(
        {
            family: {
                "family": family,
                "verdict": verdicts[family].verdict,
            }
            for family in verdicts
        }
    )
    assert set(PUBLIC_OUTCOME_FAMILIES) <= set(verdicts)
    assert "testing" in verdicts
    assert set(public) == set(PUBLIC_OUTCOME_FAMILIES)
    assert "testing" not in public
    assert TESTING_MAPS_UNDER == "quality"
    assert "testing_mapped_under_quality" in public["quality"]
    from codestrata.reporting.engineering_health.trend_report import OUTCOME_TITLES

    assert [family for family, _title in OUTCOME_TITLES] == list(PUBLIC_OUTCOME_FAMILIES)
