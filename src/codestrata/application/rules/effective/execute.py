"""Neutral local candidate/preview execution through production compiler and operators."""

from __future__ import annotations

from codestrata.application.rules.compiler import compile_rule_mapping
from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.application.rules.effective.admission import admit_effective
from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.fingerprint import (
    effective_setting_digest_for,
    finding_fingerprint,
)
from codestrata.application.rules.effective.models import (
    CandidateRunRequest,
    CandidateRunResult,
    ExecutionContext,
    FixtureCase,
    FixtureOutcome,
)
from codestrata.application.rules.effective.seal import dsl_digest, engine_digest
from codestrata.application.rules.effective.timestamps import parse_utc
from codestrata.application.rules.operators import evaluate_condition
from codestrata.domain.contracts.enums import ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.invocation import (
    CandidateValidation,
    FixtureExpectation,
    PermittedScope,
)
from codestrata.domain.contracts.rules import EffectiveRuleSet, ResolvedRule, unsigned_rule_payload
from codestrata.domain.rules.compiler_models import ConditionPlan
from codestrata.domain.rules.operators.errors import OperatorBudgetError, OperatorEvaluationError
from codestrata.domain.rules.operators.models import Truth

_SCOPE_ESCAPE = ("..", "~", "://")


def execute_candidate(
    request: CandidateRunRequest,
    catalog: RuleCatalog,
    *,
    context: ExecutionContext,
) -> CandidateRunResult:
    """Run compliant/violating/UNKNOWN fixtures. Results stay preview-only."""

    effective = request.effective
    if request.stale_evidence:
        raise EffectiveSealError("stale_preview_evidence", "stale preview evidence is rejected")
    if any(item.promote_to_production for item in request.fixtures):
        raise EffectiveSealError(
            "preview_cannot_authorize_production",
            "attempted production promotion is rejected",
        )
    if request.requested_purpose is ExecutionPurpose.PRODUCTION:
        raise EffectiveSealError(
            "preview_cannot_authorize_production",
            "candidate entrypoint cannot request production",
        )
    admission = admit_effective(effective, context)
    if not admission.admitted and admission.reason_code == "preview_cannot_authorize_production":
        raise EffectiveSealError(admission.reason_code, "preview cannot authorize production")
    _reject_stale_evidence(request, context)
    resolved = _primary_rule(effective)
    rule = catalog.get_rule(resolved.rule_id, resolved.revision, resolved.rule_digest)
    outcomes: list[FixtureOutcome] = []
    diagnostics: list[str] = []
    for fixture in request.fixtures:
        _assert_scope(fixture, request.permitted_paths, snapshot_only=request.snapshot_only)
        _assert_parameters(fixture, resolved)
        if fixture.selector_override is not None:
            raise EffectiveSealError(
                "selector_rebinding",
                "selector rebinding requires a new Rule revision",
            )
        plan = compile_rule_mapping(unsigned_rule_payload(rule))
        if plan.condition is None:
            raise EffectiveSealError("invalid_candidate", "compiled rule has no condition plan")
        status, coverage, extra = _evaluate_status(plan.condition, fixture)
        fingerprint = finding_fingerprint(
            resolved,
            subject=fixture.subject,
            rendered_message=fixture.rendered_message,
        )
        outcomes.append(
            FixtureOutcome(
                name=fixture.name,
                expected_status=fixture.expected_status,
                actual_status=status,
                coverage=coverage,
                finding_fingerprint=fingerprint,
                diagnostics=extra,
                preview_only=True,
            )
        )
        diagnostics.extend(extra)

    selector_digest = resolved.selector_digest
    setting_digest = effective_setting_digest_for(resolved)
    bound = {
        "candidate_digest": effective.effective_ruleset_digest,
        "selector_digest": selector_digest,
        "effective_setting_digest": setting_digest,
        "input_digest": effective.input_digest,
        "engine_digest": engine_digest(),
        "dsl_digest": dsl_digest(),
    }
    validation = CandidateValidation(
        purpose=ExecutionPurpose.CANDIDATE_VALIDATION,
        permitted_scope=PermittedScope(
            local_paths=request.permitted_paths or ("./fixture",),
            snapshot_only=request.snapshot_only,
        ),
        expiry=request.expiry,
        fixtures=tuple(
            FixtureExpectation(
                name=item.name,
                expected_status=item.expected_status.value,
                actual_status=item.actual_status.value,
                coverage=item.coverage,
            )
            for item in outcomes
        ),
        production_promotion_allowed=False,
        stale_evidence=False,
        **bound,
    )
    return CandidateRunResult(
        purpose=request.requested_purpose,
        production_promotion_allowed=False,
        outcomes=tuple(outcomes),
        validation=validation,
        typed_diagnostics=tuple(diagnostics),
        **bound,
    )


def execute_preview(
    request: CandidateRunRequest,
    catalog: RuleCatalog,
    *,
    context: ExecutionContext,
) -> CandidateRunResult:
    """Permitted snapshot preview uses the same compiler and operators."""

    if not request.snapshot_only:
        raise EffectiveSealError(
            "scope_violation",
            "preview execution is snapshot-only",
        )
    preview = request.model_copy(update={"requested_purpose": ExecutionPurpose.PREVIEW})
    result = execute_candidate(preview, catalog, context=context)
    return result.model_copy(update={"purpose": ExecutionPurpose.PREVIEW})


def _primary_rule(effective: EffectiveRuleSet) -> ResolvedRule:
    return effective.rules[0]


def _assert_parameters(fixture: FixtureCase, resolved: ResolvedRule) -> None:
    if fixture.parameters_override is None:
        return
    if dict(fixture.parameters_override) != dict(resolved.parameters):
        raise EffectiveSealError(
            "parameter_change",
            "candidate parameters do not match sealed effective settings",
        )


def _assert_scope(
    fixture: FixtureCase,
    permitted_paths: tuple[str, ...],
    *,
    snapshot_only: bool,
) -> None:
    if not snapshot_only:
        raise EffectiveSealError("scope_violation", "candidate execution requires snapshot_only")
    path = fixture.path
    if path is None:
        return
    normalized = path.replace("\\", "/")
    if any(token in normalized for token in _SCOPE_ESCAPE) or normalized.startswith("/"):
        raise EffectiveSealError(
            "scope_violation",
            f"fixture path {path} is outside permitted local snapshot scope",
        )
    if permitted_paths:
        allowed = False
        for root in permitted_paths:
            prefix = root.replace("\\", "/").rstrip("/")
            compact = prefix[2:] if prefix.startswith("./") else prefix
            under_compact = normalized == compact or normalized.startswith(f"{compact}/")
            under_prefix = normalized == prefix or normalized.startswith(f"{prefix}/")
            if under_compact or under_prefix:
                allowed = True
                break
        if not allowed:
            raise EffectiveSealError(
                "scope_violation",
                f"fixture path {path} is outside permitted local snapshot scope",
            )


def _reject_stale_evidence(request: CandidateRunRequest, context: ExecutionContext) -> None:
    if (
        request.evidence_candidate_digest is not None
        and request.evidence_candidate_digest != request.effective.effective_ruleset_digest
    ):
        raise EffectiveSealError(
            "stale_preview_evidence",
            "preview evidence is bound to a different candidate digest",
        )
    expiry = parse_utc(request.expiry, label="candidate expiry")
    if context.now > expiry:
        raise EffectiveSealError("stale_preview_evidence", "candidate evidence is past expiry")
    for fixture in request.fixtures:
        if fixture.captured_at is None:
            continue
        captured = parse_utc(fixture.captured_at, label="evidence captured_at")
        if captured > expiry:
            raise EffectiveSealError(
                "stale_preview_evidence",
                f"fixture {fixture.name} evidence is past expiry",
            )


def _evaluate_status(
    condition: ConditionPlan, fixture: FixtureCase
) -> tuple[ResultStatus, str, tuple[str, ...]]:
    try:
        result = evaluate_condition(condition, fixture.operator_context)
    except OperatorBudgetError as error:
        return ResultStatus.ERROR, "budget", (error.reason_code,)
    except OperatorEvaluationError as error:
        return ResultStatus.ERROR, "error", (error.reason_code,)
    coverage = "complete" if result.complete and not result.cutoff else "partial"
    if result.error:
        return ResultStatus.ERROR, coverage, ((result.reason or "operator_error"),)
    if result.truth is Truth.TRUE:
        return ResultStatus.FAIL, coverage, ()
    if result.truth is Truth.FALSE:
        return ResultStatus.PASS, coverage, ()
    return ResultStatus.UNKNOWN, coverage, ((result.reason,) if result.reason else ())
