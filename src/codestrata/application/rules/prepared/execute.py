"""Execute an admitted customer package with the existing operator evaluator."""

from __future__ import annotations

import json
from datetime import datetime

from codestrata.application.rules.compiler.service import compile_rule_mapping
from codestrata.application.rules.effective.admission import admit_effective
from codestrata.application.rules.effective.models import ExecutionContext
from codestrata.application.rules.operators import evaluate_condition
from codestrata.application.rules.prepared.errors import PreparedPackageError
from codestrata.application.rules.prepared.models import (
    PREPARED_CUSTOMER_PACKAGE_API,
    STANDARD_RULES_IDENTITY,
    AdmittedPreparedPackage,
    OperatorFactKind,
    PreparedOperatorFacts,
    PreparedRuleExecution,
)
from codestrata.domain.contracts.enums import ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.rules import (
    EffectiveRuleSet,
    parse_effective_ruleset,
    parse_signed_package,
    unsigned_rule_payload,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.rules.assessment import interpret_operator_result
from codestrata.domain.rules.compiler_models import CompilationPlan, ConditionPlan
from codestrata.domain.rules.operators.models import OperatorContext, OperatorEdge
from codestrata.models.enums import FindingCategory, FindingSource, Severity
from codestrata.models.finding import Finding

_SEVERITY = {
    FindingSeverity.INFORMATIONAL: Severity.INFO,
    FindingSeverity.LOW: Severity.LOW,
    FindingSeverity.MEDIUM: Severity.MEDIUM,
    FindingSeverity.HIGH: Severity.HIGH,
    FindingSeverity.CRITICAL: Severity.CRITICAL,
}


def execute_admitted_customer_rules(
    package: AdmittedPreparedPackage,
    *,
    facts: PreparedOperatorFacts | None,
    observed_at: datetime,
    requested_purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
) -> PreparedRuleExecution:
    """Evaluate the reviewed rule. A missing import view stays UNKNOWN.

    Ordinary assessment requests production. A preview package runs only when
    the caller passes ``ExecutionPurpose.PREVIEW``.
    """

    parsed, plan = _revalidate_at_invocation(package)
    context = ExecutionContext(now=observed_at, requested_purpose=requested_purpose)
    admission = admit_effective(parsed, context)
    if not admission.admitted:
        raise PreparedPackageError(
            admission.reason_code or "not_admitted",
            "admitted package failed invocation checks",
        )
    if plan.condition is None:
        raise PreparedPackageError("corrupted_package", "reviewed rule has no condition")
    supplied = facts or PreparedOperatorFacts(kind=OperatorFactKind.MISSING)
    status, reason, members = _evaluate(plan.condition, supplied)
    if supplied.limitations and status is ResultStatus.PASS:
        status = ResultStatus.UNKNOWN
        reason = "unresolved_relevant_edge"
        members = ()
    provenance = {
        "api": PREPARED_CUSTOMER_PACKAGE_API,
        "rule_id": package.rule.metadata.id,
        "rule_digest": package.rule.digest,
        "plan_digest": package.plan_digest,
        "package_digest": parsed.effective_ruleset_digest,
        "ruleset_id": parsed.ruleset_id,
        "execution_purpose": parsed.execution_purpose.value,
        "status": status.value,
        "reason": reason,
        "fact_kind": supplied.kind.value,
        "example_catalog_substituted": False,
        "standard_rules_identity": STANDARD_RULES_IDENTITY,
        "signed_base_digest": parsed.signed_base_digest,
        "manifest_body_digest": package.manifest.body_digest,
        "repository_applicability": "not_claimed",
    }
    if supplied.coverage_scope:
        from codestrata.application.rules.prepared.import_projection import (
            BOUNDED_STATIC_PASS_STATEMENT,
        )

        provenance["coverage_scope"] = supplied.coverage_scope
        provenance["root_discovery"] = supplied.root_discovery
        provenance["discovery_rule"] = supplied.discovery_rule
        provenance["source_roots"] = json.dumps(list(supplied.source_roots))
        provenance["external_import_names"] = json.dumps(list(supplied.external_import_names))
        provenance["limitations"] = json.dumps(
            [item.model_dump(mode="json") for item in supplied.limitations]
        )
        provenance["import_records"] = json.dumps(
            [item.model_dump(mode="json") for item in supplied.import_records]
        )
        if status is ResultStatus.PASS:
            provenance["pass_statement"] = BOUNDED_STATIC_PASS_STATEMENT
    return PreparedRuleExecution(
        rule_id=package.rule.metadata.id,
        rule_digest=package.rule.digest,
        plan_digest=package.plan_digest,
        package_digest=parsed.effective_ruleset_digest,
        ruleset_id=parsed.ruleset_id,
        status=status,
        reason=reason,
        fact_kind=supplied.kind,
        members=members,
        reviewer=package.review.reviewer,
        provenance=provenance,
    )


def findings_for_execution(
    package: AdmittedPreparedPackage,
    execution: PreparedRuleExecution,
) -> tuple[Finding, ...]:
    """Project a customer result into the ordinary finding list.

    PASS stays in provenance. UNKNOWN and ERROR are findings so they cannot
    disappear. FAIL is a violation finding. None of these replace standard findings.
    """

    if execution.status is ResultStatus.PASS:
        return ()
    severity = _SEVERITY.get(package.rule.finding.default_severity, Severity.HIGH)
    if execution.status is not ResultStatus.FAIL:
        severity = Severity.INFO
    description = package.rule.finding.message_template
    if execution.reason:
        description = f"{description} ({execution.reason})"
    if execution.members:
        description = f"{description}: {', '.join(execution.members)}"
    return (
        Finding(
            rule_id=execution.rule_id,
            title=package.rule.metadata.title,
            description=description,
            category=_category(package.rule.metadata.category),
            severity=severity,
            source=FindingSource.DETERMINISTIC,
            metadata={
                "prepared_customer_package": execution.provenance,
                "result_status": execution.status.value,
            },
        ),
    )


def _revalidate_at_invocation(
    package: AdmittedPreparedPackage,
) -> tuple[EffectiveRuleSet, CompilationPlan]:
    """Recompute the reviewed plan and reject mixed or tampered bindings."""

    parsed = parse_effective_ruleset(package.effective.model_dump(mode="json"))
    manifest = parse_signed_package(package.manifest.model_dump(mode="json"))
    plan = compile_rule_mapping(
        unsigned_rule_payload(package.rule),
        source_digest=package.source_digest,
    )
    if plan.rule is None or plan.condition is None:
        raise PreparedPackageError("corrupted_package", "reviewed rule did not recompile")
    payloads = {item.name: item.digest for item in manifest.body.payload_digests}
    resolved = parsed.rules[0] if len(parsed.rules) == 1 else None
    matches = (
        plan.plan_digest == package.plan_digest == package.review.plan_digest
        and plan.plan_digest == parsed.input_digest
        and plan.document_digest == package.rule.digest == package.review.rule_digest
        and plan.rule.metadata.id == package.rule.metadata.id
        and plan.rule.metadata.version == package.rule.metadata.version
        and resolved is not None
        and resolved.rule_id == package.rule.metadata.id
        and resolved.revision == package.rule.metadata.version
        and resolved.rule_digest == package.rule.digest
        and package.review.package_digest == parsed.effective_ruleset_digest
        and package.review.decision.value == "approved"
        and payloads.get("plan") == plan.plan_digest
        and payloads.get("rule") == package.rule.digest
        and payloads.get("effective") == parsed.effective_ruleset_digest
        and manifest.body.effective_ruleset_digest == parsed.effective_ruleset_digest
        and manifest.body.execution_purpose is parsed.execution_purpose
    )
    if not matches:
        raise PreparedPackageError(
            "package_binding_mismatch",
            "reviewed plan, rule, Effective RuleSet, and manifest do not describe one package",
        )
    return parsed, plan


def _evaluate(
    condition: ConditionPlan,
    facts: PreparedOperatorFacts,
) -> tuple[ResultStatus, str | None, tuple[str, ...]]:
    if facts.kind is OperatorFactKind.MISSING or facts.context is None:
        return ResultStatus.UNKNOWN, "missing_view", ()
    if facts.kind is OperatorFactKind.CONTAINS_ONLY or _contains_only(facts.context):
        return ResultStatus.UNKNOWN, "contains_only_graph", ()
    if facts.context.resolved_graph is None:
        return ResultStatus.UNKNOWN, "missing_view", ()
    result = evaluate_condition(condition, facts.context)
    status = interpret_operator_result(result)
    if status is ResultStatus.PASS and not facts.context.resolved_graph.complete:
        return ResultStatus.UNKNOWN, "unresolved_relevant_edge", ()
    return status, result.reason, result.members


def _contains_only(context: OperatorContext) -> bool:
    graph = context.resolved_graph
    if graph is None:
        return False
    if not graph.edges:
        return False
    return all(_is_contains(edge) for edge in graph.edges)


def _is_contains(edge: OperatorEdge) -> bool:
    return edge.edge_type == "contains"


def _category(name: str) -> FindingCategory:
    try:
        return FindingCategory(name)
    except ValueError:
        return FindingCategory.ARCHITECTURE
