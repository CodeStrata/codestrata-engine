"""Evaluate architecture launch YAML via the E03.1 compiler and E03.2 operators."""

from __future__ import annotations

from collections.abc import Callable

from codestrata.application.evidence.structure.normalize import (
    STRUCTURE_NORMALIZER_VERSION,
    StructuralGraphEvidence,
)
from codestrata.application.rules.architecture.yaml_catalog import (
    BOUNDARY_RULE_ID,
    CONCENTRATION_RULE_ID,
    DIRECTION_RULE_ID,
    LEAKAGE_RULE_ID,
    SPECIAL_CASE_RULE_IDS,
    architecture_catalog_entries,
    load_architecture_launch_plans,
)
from codestrata.application.rules.execution.process_guard import IsolatedOutcome
from codestrata.application.rules.execution.service import LaunchCatalogService
from codestrata.application.rules.operators import evaluate_condition
from codestrata.domain.contracts.enums import CoverageState, ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.models import BudgetLimits
from codestrata.domain.repository_graph.metrics import BoundaryPattern
from codestrata.domain.rules.assessment import interpret_operator_result
from codestrata.domain.rules.evidence_contract import validate_launch_evidence
from codestrata.domain.rules.execution_models import (
    LaunchEvidence,
    LaunchExecutionBody,
    LaunchRuleRecord,
)
from codestrata.domain.rules.operators.models import OperatorContext, OperatorLimits


def evaluate_architecture_launch(
    evidence: StructuralGraphEvidence,
    *,
    purpose: ExecutionPurpose = ExecutionPurpose.PREVIEW,
    limits: OperatorLimits | None = None,
    budgets: BudgetLimits | None = None,
    isolate: bool = False,
    isolate_fn: Callable[..., IsolatedOutcome] | None = None,
) -> LaunchExecutionBody:
    """Run bundled architecture YAML. Boundary patterns come from the run config."""

    context = evidence.operator_context(limits=limits)
    entries = tuple(
        entry
        for entry in architecture_catalog_entries()
        if entry.rule_id not in SPECIAL_CASE_RULE_IDS
    )
    body = LaunchCatalogService().execute(
        entries,
        context,
        purpose=purpose,
        package_purpose=purpose,
        budgets=budgets,
        isolate=isolate,
        isolate_fn=isolate_fn,
        evidence_paths=evidence.dependency_paths,
    )
    records = [_with_concentration_evidence(item, evidence) for item in body.records]
    records.append(_boundary_record(evidence, limits=limits))
    records.append(_direction_record(evidence, limits=limits))
    records.append(_leakage_record(evidence, limits=limits))
    ordered = tuple(sorted(records, key=lambda item: item.rule_id))
    return body.model_copy(update={"records": ordered})


def architecture_operator_context(
    evidence: StructuralGraphEvidence,
    *,
    limits: OperatorLimits | None = None,
) -> OperatorContext:
    return evidence.operator_context(limits=limits)


def _boundary_record(
    evidence: StructuralGraphEvidence,
    *,
    limits: OperatorLimits | None,
) -> LaunchRuleRecord:
    plan = load_architecture_launch_plans()[BOUNDARY_RULE_ID]
    pattern = evidence.boundary_pattern
    if pattern is None:
        return LaunchRuleRecord(
            rule_id=BOUNDARY_RULE_ID,
            rule_revision="1.0.0",
            plan_digest=plan.plan_digest,
            status=ResultStatus.NOT_APPLICABLE,
            coverage_state=CoverageState.NOT_APPLICABLE,
            enabled=True,
            suppressed=False,
            reason="no_declared_pattern",
        )
    if pattern.selector_digest and pattern.selector_digest != plan.selector_digest:
        return LaunchRuleRecord(
            rule_id=BOUNDARY_RULE_ID,
            rule_revision="1.0.0",
            plan_digest=plan.plan_digest,
            status=ResultStatus.ERROR,
            coverage_state=CoverageState.ERROR,
            enabled=True,
            suppressed=False,
            reason="selector_rebinding",
        )
    condition = plan.condition
    if condition is None:
        return LaunchRuleRecord(
            rule_id=BOUNDARY_RULE_ID,
            rule_revision="1.0.0",
            plan_digest=plan.plan_digest,
            status=ResultStatus.ERROR,
            coverage_state=CoverageState.ERROR,
            enabled=True,
            suppressed=False,
            reason="missing_condition",
        )
    effective = condition.model_copy(
        update={"fact": pattern.source_pattern, "value": pattern.target_pattern}
    )
    result = evaluate_condition(effective, evidence.operator_context(limits=limits))
    status = interpret_operator_result(result)
    items: tuple[LaunchEvidence, ...] = ()
    if result.members:
        items = _boundary_evidence(evidence, pattern, result.members)
    elif status is ResultStatus.FAIL:
        items = _boundary_evidence(evidence, pattern, (pattern.constraint_id,))
    coverage = CoverageState.COMPLETE
    if status is ResultStatus.ERROR:
        coverage = CoverageState.ERROR
    elif status is ResultStatus.UNKNOWN:
        coverage = CoverageState.UNKNOWN
    elif status is ResultStatus.NOT_APPLICABLE:
        coverage = CoverageState.NOT_APPLICABLE
    return LaunchRuleRecord(
        rule_id=BOUNDARY_RULE_ID,
        rule_revision="1.0.0",
        plan_digest=plan.plan_digest,
        status=status,
        coverage_state=coverage,
        enabled=True,
        suppressed=False,
        reason=result.reason,
        evidence=items,
        operator_reason=result.reason,
    )


def _boundary_evidence(
    evidence: StructuralGraphEvidence,
    pattern: BoundaryPattern,
    members: tuple[str, ...],
) -> tuple[LaunchEvidence, ...]:
    return validate_launch_evidence(
        tuple(
            LaunchEvidence(
                subject_id=member,
                source_kind="direct_dependency",
                relative_path=evidence.dependency_paths.get(member),
                extractor_version=STRUCTURE_NORMALIZER_VERSION,
                attributes={
                    "constraint_id": pattern.constraint_id,
                    "dependency_path": member,
                    "source_pattern": pattern.source_pattern,
                    "target_pattern": pattern.target_pattern,
                },
            )
            for member in members
        )
    )


def _direction_record(
    evidence: StructuralGraphEvidence,
    *,
    limits: OperatorLimits | None,
) -> LaunchRuleRecord:
    plan = load_architecture_launch_plans()[DIRECTION_RULE_ID]
    constraint = evidence.direction_constraint
    if constraint is not None and constraint.selector_digest:
        if constraint.selector_digest != plan.selector_digest:
            return LaunchRuleRecord(
                rule_id=DIRECTION_RULE_ID,
                rule_revision="1.0.0",
                plan_digest=plan.plan_digest,
                status=ResultStatus.ERROR,
                coverage_state=CoverageState.ERROR,
                enabled=True,
                suppressed=False,
                reason="selector_rebinding",
            )
    condition = plan.condition
    if condition is None:
        return _error_record(DIRECTION_RULE_ID, plan.plan_digest, "missing_condition")
    result = evaluate_condition(condition, evidence.operator_context(limits=limits))
    status = interpret_operator_result(result)
    items: tuple[LaunchEvidence, ...] = ()
    if status is ResultStatus.FAIL:
        items = validate_launch_evidence(
            tuple(
                LaunchEvidence(
                    subject_id=item.identity,
                    source_kind="direction_violation",
                    relative_path=item.evidence_path,
                    extractor_version=STRUCTURE_NORMALIZER_VERSION,
                    attributes={
                        "constraint_id": evidence.direction.constraint_id,
                        "dependency_path": item.identity,
                        "source_layer": item.source_layer,
                        "target_layer": item.target_layer,
                        "allowed_directions": ",".join(evidence.direction.allowed_directions),
                    },
                )
                for item in evidence.direction.violations
            )
        )
    return _status_record(
        DIRECTION_RULE_ID,
        plan.plan_digest,
        status,
        result.reason,
        items,
    )


def _leakage_record(
    evidence: StructuralGraphEvidence,
    *,
    limits: OperatorLimits | None,
) -> LaunchRuleRecord:
    plan = load_architecture_launch_plans()[LEAKAGE_RULE_ID]
    condition = plan.condition
    if condition is None:
        return _error_record(LEAKAGE_RULE_ID, plan.plan_digest, "missing_condition")
    result = evaluate_condition(condition, evidence.operator_context(limits=limits))
    status = interpret_operator_result(result)
    items: tuple[LaunchEvidence, ...] = ()
    if status is ResultStatus.FAIL:
        items = validate_launch_evidence(
            tuple(
                LaunchEvidence(
                    subject_id=f"{item.unit_id}:{item.framework}:{item.symbol}",
                    source_kind="framework_symbol",
                    relative_path=item.path or None,
                    extractor_version=STRUCTURE_NORMALIZER_VERSION,
                    attributes={
                        "framework": item.framework,
                        "symbol": item.symbol,
                        "unit": item.unit_id,
                        "language": item.language,
                    },
                )
                for item in evidence.leakage.hits
            )
        )
    return _status_record(LEAKAGE_RULE_ID, plan.plan_digest, status, result.reason, items)


def _error_record(rule_id: str, plan_digest: str, reason: str) -> LaunchRuleRecord:
    return LaunchRuleRecord(
        rule_id=rule_id,
        rule_revision="1.0.0",
        plan_digest=plan_digest,
        status=ResultStatus.ERROR,
        coverage_state=CoverageState.ERROR,
        enabled=True,
        suppressed=False,
        reason=reason,
    )


def _status_record(
    rule_id: str,
    plan_digest: str,
    status: ResultStatus,
    reason: str | None,
    items: tuple[LaunchEvidence, ...],
) -> LaunchRuleRecord:
    return LaunchRuleRecord(
        rule_id=rule_id,
        rule_revision="1.0.0",
        plan_digest=plan_digest,
        status=status,
        coverage_state=_coverage(status),
        enabled=True,
        suppressed=False,
        reason=reason,
        evidence=items,
        operator_reason=reason,
    )


def _coverage(status: ResultStatus) -> CoverageState:
    if status is ResultStatus.ERROR:
        return CoverageState.ERROR
    if status is ResultStatus.UNKNOWN:
        return CoverageState.UNKNOWN
    if status is ResultStatus.NOT_APPLICABLE:
        return CoverageState.NOT_APPLICABLE
    return CoverageState.COMPLETE


def _with_concentration_evidence(
    record: LaunchRuleRecord,
    evidence: StructuralGraphEvidence,
) -> LaunchRuleRecord:
    if record.rule_id != CONCENTRATION_RULE_ID or record.status is not ResultStatus.FAIL:
        return record
    metric = evidence.concentration.max_share
    component = str(metric.extra.get("max_component_id") or record.rule_id)
    witness = metric.extra.get("witness_path")
    path = witness if isinstance(witness, str) and witness else None
    membership = metric.extra.get("membership")
    items = validate_launch_evidence(
        (
            LaunchEvidence(
                subject_id=component,
                source_kind="component_line_share",
                relative_path=path,
                extractor_version=STRUCTURE_NORMALIZER_VERSION,
                attributes={
                    "numerator": str(metric.numerator),
                    "denominator": str(metric.denominator),
                    "derivation": evidence.concentration.derivation,
                    "full_repo_valid": (
                        "true" if evidence.concentration.full_repo_valid else "false"
                    ),
                    "threshold": evidence.concentration.threshold,
                    "membership": _membership_text(membership),
                },
            ),
        )
    )
    return record.model_copy(update={"evidence": items})


def _membership_text(membership: object) -> str:
    if not isinstance(membership, list):
        return ""
    parts: list[str] = []
    for item in membership:
        if not isinstance(item, dict):
            continue
        component = item.get("component_id")
        lines = item.get("lines")
        if isinstance(component, str):
            parts.append(f"{component}:{lines}")
    return ",".join(parts)


def bundled_boundary_pattern(*, selector_digest: str | None = None) -> BoundaryPattern:
    """Explicit copy of the bundled API/internal example. Callers must opt in."""

    return BoundaryPattern(
        constraint_id="forbid:api->internal",
        source_pattern="api",
        target_pattern="internal",
        allowed_directions=("api>api", "api>public"),
        selector_digest=selector_digest,
    )
