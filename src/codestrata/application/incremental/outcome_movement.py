"""M30 Thresholded Outcome Movement.

Evaluates deterministic change movement across four public outcome families:
Architecture, Security, Quality, and Testing.

Standing rules:
- Precedence: INSUFFICIENT > MIXED > DETERIORATED > IMPROVED > STABLE.
- Improved requires real favorable movement (>=1 favorable and 0 unfavorable).
- Stable has neither (0 favorable and 0 unfavorable).
- No composite average hides deterioration.
- Empty outcome or entirely disabled/exempt driver sets yield NOT_APPLICABLE, never healthy/Stable.
- Qualifying change: strict delta beyond versioned epsilon (counts default 0, ratios default 0.01).
- Context-only and advisory metrics are excluded from driving verdicts.
- A known violation survives unrelated incomplete evidence.
- Baseline missing => INSUFFICIENT / no comparison.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.contracts.driver_manifest import build_outcome_driver_manifest
from codestrata.domain.contracts.enums import OutcomeMovement
from codestrata.domain.contracts.formulas import m30_classify
from codestrata.domain.contracts.models import OutcomeDriver
from codestrata.models.scan_comparison import (
    CauseAttribution,
    ComparedFinding,
    MetricDelta,
    OutcomeDriverMovement,
    OutcomeMovementVerdict,
)


def evaluate_outcome_movement(
    *,
    compared_findings: Sequence[ComparedFinding] = (),
    metric_deltas: Sequence[MetricDelta] = (),
    manifest_drivers: Sequence[OutcomeDriver] | None = None,
    baseline_available: bool = True,
    is_empty_outcome: bool = False,
    disabled_all_scope: bool = False,
    overall_coverage_pass: bool = True,
    cause_attribution: CauseAttribution | None = None,
) -> tuple[dict[str, OutcomeMovementVerdict], OutcomeMovement]:
    """Calculate M30 outcome movement per family and overall."""
    if manifest_drivers is None:
        manifest = build_outcome_driver_manifest()
        all_drivers = manifest.drivers
    else:
        all_drivers = tuple(manifest_drivers)

    # Group drivers by outcome family
    by_family: dict[str, list[OutcomeDriver]] = {
        "architecture": [],
        "security": [],
        "quality": [],
        "maintainability": [],
        "testing": [],
    }
    for d in all_drivers:
        fam = d.family.value.lower() if hasattr(d.family, "value") else str(d.family).lower()
        if fam in by_family:
            by_family[fam].append(d)
        else:
            by_family.setdefault(fam, []).append(d)

    verdicts: dict[str, OutcomeMovementVerdict] = {}
    family_verdict_values: list[OutcomeMovement] = []

    # Map findings by rule_id
    findings_by_rule: dict[str, list[ComparedFinding]] = {}
    for f in compared_findings:
        if f.rule_id:
            findings_by_rule.setdefault(f.rule_id, []).append(f)

    # Map metric deltas by metric_name / id
    metric_delta_map: dict[str, MetricDelta] = {}
    for md in metric_deltas:
        metric_delta_map[md.metric_name] = md

    for family, drivers in by_family.items():
        if not baseline_available:
            verdicts[family] = OutcomeMovementVerdict(
                family=family,
                verdict=OutcomeMovement.INSUFFICIENT.value,
                reason="no_baseline",
                coverage_status="unknown",
            )
            family_verdict_values.append(OutcomeMovement.INSUFFICIENT)
            continue

        if is_empty_outcome or disabled_all_scope:
            verdicts[family] = OutcomeMovementVerdict(
                family=family,
                verdict=OutcomeMovement.NOT_APPLICABLE.value,
                reason="empty_or_disabled_scope",
                coverage_status="not_applicable",
            )
            family_verdict_values.append(OutcomeMovement.NOT_APPLICABLE)
            continue

        # Separate outcome drivers vs context-only / advisory
        eligible_drivers: list[OutcomeDriver] = []
        excluded_contextual: list[str] = []

        for d in drivers:
            if d.outcome_or_context_role == "outcome_driver":
                eligible_drivers.append(d)
            else:
                excluded_contextual.append(d.id)

        if not eligible_drivers:
            verdicts[family] = OutcomeMovementVerdict(
                family=family,
                verdict=OutcomeMovement.NOT_APPLICABLE.value,
                excluded_contextual=excluded_contextual,
                reason="no_eligible_outcome_drivers",
            )
            family_verdict_values.append(OutcomeMovement.NOT_APPLICABLE)
            continue

        qualifying_driver_records: list[OutcomeDriverMovement] = []
        favorable_count = 0
        unfavorable_count = 0
        stable_count = 0
        required_unknown = not overall_coverage_pass

        for d in eligible_drivers:
            mov_record = _evaluate_single_driver(
                driver=d,
                findings=findings_by_rule.get(d.id, []),
                metric_delta=metric_delta_map.get(d.id),
            )
            qualifying_driver_records.append(mov_record)

            if mov_record.movement == "favorable":
                favorable_count += 1
            elif mov_record.movement == "unfavorable":
                unfavorable_count += 1
            elif mov_record.movement == "stable":
                stable_count += 1
            elif mov_record.movement == "insufficient":
                required_unknown = True

        family_movement = m30_classify(
            driver_set_empty=False,
            comparable=True,
            required_unknown=required_unknown,
            favorable=favorable_count,
            unfavorable=unfavorable_count,
        )

        family_verdict_values.append(family_movement)
        reason_val = None
        if family == "security" and cause_attribution and cause_attribution.is_feed_driven:
            excluded_contextual.append("feed_driven_cve_changes_not_customer_code_deterioration")
            reason_val = "feed_driven_cve_changes_not_customer_code_deterioration"

        verdicts[family] = OutcomeMovementVerdict(
            family=family,
            verdict=family_movement.value,
            favorable_count=favorable_count,
            unfavorable_count=unfavorable_count,
            stable_count=stable_count,
            qualifying_drivers=qualifying_driver_records,
            excluded_contextual=excluded_contextual,
            threshold_profile={"epsilons": {d.id: d.epsilon for d in eligible_drivers}},
            coverage_status="unknown" if required_unknown else "pass",
            reason=reason_val,
        )


    # Classify overall outcome movement using the same strict precedence
    overall_movement = _classify_overall(family_verdict_values)
    return verdicts, overall_movement


def _evaluate_single_driver(
    *,
    driver: OutcomeDriver,
    findings: Sequence[ComparedFinding],
    metric_delta: MetricDelta | None,
) -> OutcomeDriverMovement:
    """Evaluate qualifying movement for a single outcome driver."""
    raw_epsilon = driver.epsilon
    epsilon_val = _parse_epsilon(raw_epsilon, driver.comparison_unit)

    is_rule = driver.kind == "rule" or (
        getattr(driver.kind, "value", None) == "rule"
    )
    if is_rule:
        # Rule driver: based on finding lifecycle
        new_cnt = sum(1 for f in findings if f.lifecycle == "new")
        resolved_cnt = sum(1 for f in findings if f.lifecycle == "resolved")
        worsened_cnt = sum(1 for f in findings if f.lifecycle == "worsened")
        improved_cnt = sum(1 for f in findings if f.lifecycle == "improved")
        unknown_cnt = sum(1 for f in findings if f.lifecycle == "unknown")

        net_unfavorable = new_cnt + worsened_cnt
        net_favorable = resolved_cnt + improved_cnt
        delta = net_unfavorable - net_favorable

        has_unknown_coverage = unknown_cnt > 0 or any(
            f.compatibility_status == "unknown" for f in findings
        )

        # Lower count is favorable by default for rules
        # Strict delta beyond epsilon
        if net_unfavorable > 0 and net_favorable > 0:
            mov = "mixed"
            qualifying = True
        elif net_unfavorable > epsilon_val:
            mov = "unfavorable"
            qualifying = True
        elif net_favorable > epsilon_val:
            mov = "favorable"
            qualifying = True
        elif has_unknown_coverage and net_unfavorable == 0:
            mov = "insufficient"
            qualifying = False
        else:
            mov = "stable"
            qualifying = False

        notes_str = (
            f"new={new_cnt}; resolved={resolved_cnt}; "
            f"worsened={worsened_cnt}; improved={improved_cnt}"
        )
        return OutcomeDriverMovement(
            driver_id=driver.id,
            family=driver.family.value if hasattr(driver.family, "value") else str(driver.family),
            kind="rule",
            direction=driver.direction,
            unit=driver.comparison_unit,
            epsilon=epsilon_val,
            base_value=None,
            candidate_value=None,
            delta=delta,
            movement=mov,
            qualifying=qualifying,
            coverage_status="unknown" if has_unknown_coverage else "pass",
            notes=notes_str,
        )

    # Metric driver
    if metric_delta is None:
        return OutcomeDriverMovement(
            driver_id=driver.id,
            family=driver.family.value if hasattr(driver.family, "value") else str(driver.family),
            kind="metric",
            direction=driver.direction,
            unit=driver.comparison_unit,
            epsilon=epsilon_val,
            movement="stable",
            qualifying=False,
            coverage_status="pass",
            notes="no_metric_delta_observed",
        )

    if not metric_delta.compatible or metric_delta.coverage_status != "pass":
        return OutcomeDriverMovement(
            driver_id=driver.id,
            family=driver.family.value if hasattr(driver.family, "value") else str(driver.family),
            kind="metric",
            direction=driver.direction,
            unit=driver.comparison_unit,
            epsilon=epsilon_val,
            base_value=metric_delta.base_value,
            candidate_value=metric_delta.candidate_value,
            delta=metric_delta.delta,
            movement="insufficient",
            qualifying=False,
            coverage_status=metric_delta.coverage_status,
            notes=metric_delta.compatibility_reason,
        )

    # Numeric delta comparison. An unparseable delta is insufficient, never a zero.
    raw_delta = metric_delta.delta
    if raw_delta is None:
        numeric_delta: float | None = 0.0
    else:
        try:
            numeric_delta = float(raw_delta)
        except (ValueError, TypeError):
            numeric_delta = None
        else:
            if numeric_delta != numeric_delta:
                numeric_delta = None
    if numeric_delta is None:
        return OutcomeDriverMovement(
            driver_id=driver.id,
            family=driver.family.value if hasattr(driver.family, "value") else str(driver.family),
            kind="metric",
            direction=driver.direction,
            unit=driver.comparison_unit,
            epsilon=epsilon_val,
            base_value=metric_delta.base_value,
            candidate_value=metric_delta.candidate_value,
            delta=raw_delta,
            movement="insufficient",
            qualifying=False,
            coverage_status="unknown",
            notes="unparseable_delta",
        )

    lower_favorable = "lower" in driver.direction.lower()
    higher_favorable = "higher" in driver.direction.lower()

    if abs(numeric_delta) > epsilon_val:
        if lower_favorable:
            movement = "favorable" if numeric_delta < -epsilon_val else "unfavorable"
        elif higher_favorable:
            movement = "favorable" if numeric_delta > epsilon_val else "unfavorable"
        else:
            movement = "stable"
        qualifying = movement in {"favorable", "unfavorable"}
    else:
        movement = "stable"
        qualifying = False

    return OutcomeDriverMovement(
        driver_id=driver.id,
        family=driver.family.value if hasattr(driver.family, "value") else str(driver.family),
        kind="metric",
        direction=driver.direction,
        unit=driver.comparison_unit,
        epsilon=epsilon_val,
        base_value=metric_delta.base_value,
        candidate_value=metric_delta.candidate_value,
        delta=metric_delta.delta,
        movement=movement,
        qualifying=qualifying,
        coverage_status=metric_delta.coverage_status,
        notes=f"delta={numeric_delta} vs epsilon={epsilon_val}",
    )


def _parse_epsilon(raw_epsilon: str, unit: str) -> float:
    try:
        return float(raw_epsilon)
    except (ValueError, TypeError):
        return 0.01 if unit == "ratio" else 0.0


def _classify_overall(verdicts: Sequence[OutcomeMovement]) -> OutcomeMovement:
    """Precedence: INSUFFICIENT > MIXED > DETERIORATED > IMPROVED > STABLE."""
    clean = [v for v in verdicts if v != OutcomeMovement.NOT_APPLICABLE]
    if not clean:
        return OutcomeMovement.NOT_APPLICABLE
    if any(v == OutcomeMovement.INSUFFICIENT for v in clean):
        return OutcomeMovement.INSUFFICIENT
    if any(v == OutcomeMovement.MIXED for v in clean):
        return OutcomeMovement.MIXED
    has_deteriorated = any(v == OutcomeMovement.DETERIORATED for v in clean)
    has_improved = any(v == OutcomeMovement.IMPROVED for v in clean)
    if has_deteriorated and has_improved:
        return OutcomeMovement.MIXED
    if has_deteriorated:
        return OutcomeMovement.DETERIORATED
    if has_improved:
        return OutcomeMovement.IMPROVED
    return OutcomeMovement.STABLE
