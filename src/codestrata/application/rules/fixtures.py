"""Internal fixture SharedRules for proving the platform (not production)."""

from __future__ import annotations

from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleSeverity,
    RuleSkipReason,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult


def _meta(
    rule_id: str,
    *,
    title: str,
    description: str,
    requires_enterprise: bool = False,
    languages: tuple[str, ...] = (),
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion(major=1, minor=0, patch=0),
        title=title,
        description=description,
        category=RuleCategory.PLATFORM,
        default_severity=RuleSeverity.LOW,
        supported_languages=languages,
        tags=("fixture", "internal"),
        remediation_summary="Fixture rule — not a production CodeStrata rule",
        enabled_by_default=True,
        experimental=True,
        requires_enterprise_context=requires_enterprise,
    )


class _AlwaysMatchRule:
    @property
    def metadata(self) -> RuleMetadata:
        return _meta(
            "fixture.always-match",
            title="Always Match Fixture",
            description="Always produces one match for harness tests",
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        _ = context
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        match = RuleMatch(
            rule_id=self.metadata.rule_id,
            rule_version=self.metadata.version,
            severity=self.metadata.default_severity,
            confidence=RuleConfidence.CERTAIN,
            title=self.metadata.title,
            summary="Fixture matched repository",
            evidence=(
                RuleEvidence(
                    kind=RuleEvidenceKind.REPOSITORY_FACT,
                    subject_reference=context.repository.repository_id,
                    message="Repository present in context",
                    safe_location="repository",
                ),
            ),
            subject_keys=(context.repository.repository_id,),
        )
        return SharedRuleEvaluationResult.matched((match,))


class _NeverMatchRule:
    @property
    def metadata(self) -> RuleMetadata:
        return _meta(
            "fixture.never-match",
            title="Never Match Fixture",
            description="Always returns not_matched",
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        _ = context
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        _ = context
        return SharedRuleEvaluationResult.not_matched()


class _NotApplicableRule:
    @property
    def metadata(self) -> RuleMetadata:
        return _meta(
            "fixture.not-applicable",
            title="Not Applicable Fixture",
            description="Always not applicable",
            requires_enterprise=True,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        if not context.has_enterprise_context:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.MISSING_ENTERPRISE_CONTEXT,
                message="Enterprise context required",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        _ = context
        return SharedRuleEvaluationResult.not_matched()


class _MultipleMatchRule:
    @property
    def metadata(self) -> RuleMetadata:
        return _meta(
            "fixture.multiple-match",
            title="Multiple Match Fixture",
            description="Produces two matches",
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        _ = context
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        matches = []
        for index, name in enumerate(("alpha", "beta"), start=1):
            matches.append(
                RuleMatch(
                    rule_id=self.metadata.rule_id,
                    rule_version=self.metadata.version,
                    severity=self.metadata.default_severity,
                    confidence=RuleConfidence.HIGH,
                    title=f"Match {name}",
                    summary=f"Fixture match {name}",
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.SYMBOL,
                            subject_reference=name,
                            message=f"Symbol {name}",
                            attributes={"index": str(index)},
                        ),
                    ),
                    subject_keys=(f"{context.repository.repository_id}:{name}",),
                )
            )
        return SharedRuleEvaluationResult.matched(tuple(matches))


class _FailureRule:
    @property
    def metadata(self) -> RuleMetadata:
        return _meta(
            "fixture.failure",
            title="Failure Fixture",
            description="Raises an unexpected error",
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        _ = context
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        _ = context
        raise RuntimeError("fixture failure")


def fixture_rules() -> tuple[object, ...]:
    """Internal fixture rules — register with production=False only."""

    return (
        _AlwaysMatchRule(),
        _NeverMatchRule(),
        _NotApplicableRule(),
        _MultipleMatchRule(),
        _FailureRule(),
    )
