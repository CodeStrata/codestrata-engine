"""Technical Debt complexity SharedRules (Phase 4.3.3).

Rules consume AggregatedComplexityEvidence only. They never re-parse source.
Unsupported or unavailable metrics never produce findings.
"""

from __future__ import annotations

from codestrata.application.rules.technical_debt.helpers import (
    complexity_evidence,
    evidence_callable,
    evidence_type,
    exceeds_threshold,
    make_metadata,
    match,
    severity_for_ratio,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleConfidence, RuleSkipReason
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import SharedRuleEvaluationResult
from codestrata.domain.technical_debt.ids import (
    RULE_DEEP_NESTING,
    RULE_EXCESSIVE_BRANCHING,
    RULE_EXCESSIVE_PARAMETERS,
    RULE_LARGE_CALLABLE,
    RULE_OVERSIZED_TYPE,
)


def _complexity_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = complexity_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Complexity evidence unavailable",
        )
    if not evidence.callables and not evidence.types:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Complexity evidence contains no callable or type facts",
        )
    return RuleApplicability.applicable()


class LargeCallableRule:
    """Flags callables whose available physical line count exceeds the threshold."""

    def __init__(self, *, max_physical_lines: int = 50) -> None:
        self._threshold = max_physical_lines

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LARGE_CALLABLE,
            title="Large callable",
            description=(
                "Detects functions/methods/constructors whose measured physical "
                "line count exceeds the configured threshold."
            ),
            remediation=(
                "Split the callable into smaller units so physical line count "
                "falls at or below the configured threshold."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _complexity_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = complexity_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Complexity evidence unavailable",
            )
        matches = []
        for item in evidence.callables:
            if not exceeds_threshold(item.physical_line_count, threshold=self._threshold):
                continue
            value = int(item.physical_line_count.value or 0)
            matches.append(
                match(
                    rule_id=RULE_LARGE_CALLABLE,
                    title="Large callable",
                    summary=(
                        f"Callable '{item.qualified_signature}' has physical_line_count="
                        f"{value}, which exceeds threshold {self._threshold}."
                    ),
                    severity=severity_for_ratio(value=value, threshold=self._threshold),
                    confidence=RuleConfidence.HIGH,
                    evidence=(
                        evidence_callable(
                            item=item,
                            message=(
                                f"physical_line_count {value} > threshold {self._threshold}"
                            ),
                            metric_name="physical_line_count",
                            metric_value=value,
                            threshold=self._threshold,
                        ),
                    ),
                    subject_keys=(item.path, item.qualified_signature),
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(
                sorted(
                    matches,
                    key=lambda item: (
                        item.subject_keys,
                        str(item.rule_id),
                        item.summary,
                    ),
                )
            )
        )


class ExcessiveBranchingRule:
    def __init__(self, *, max_branch_points: int = 10) -> None:
        self._threshold = max_branch_points

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_EXCESSIVE_BRANCHING,
            title="Excessive branching",
            description=(
                "Detects callables whose measured branch-point count exceeds the "
                "configured threshold."
            ),
            remediation=(
                "Reduce branching so branch-point count falls at or below the "
                "configured threshold."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _complexity_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = complexity_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Complexity evidence unavailable",
            )
        matches = []
        for item in evidence.callables:
            if not exceeds_threshold(item.branch_point_count, threshold=self._threshold):
                continue
            value = int(item.branch_point_count.value or 0)
            matches.append(
                match(
                    rule_id=RULE_EXCESSIVE_BRANCHING,
                    title="Excessive branching",
                    summary=(
                        f"Callable '{item.qualified_signature}' has branch_point_count="
                        f"{value}, which exceeds threshold {self._threshold}."
                    ),
                    severity=severity_for_ratio(value=value, threshold=self._threshold),
                    confidence=RuleConfidence.HIGH,
                    evidence=(
                        evidence_callable(
                            item=item,
                            message=(
                                f"branch_point_count {value} > threshold {self._threshold}"
                            ),
                            metric_name="branch_point_count",
                            metric_value=value,
                            threshold=self._threshold,
                        ),
                    ),
                    subject_keys=(item.path, item.qualified_signature),
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(
                sorted(
                    matches,
                    key=lambda item: (
                        item.subject_keys,
                        str(item.rule_id),
                        item.summary,
                    ),
                )
            )
        )


class DeepNestingRule:
    def __init__(self, *, max_nesting_depth: int = 4) -> None:
        self._threshold = max_nesting_depth

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DEEP_NESTING,
            title="Deep nesting",
            description=(
                "Detects callables whose measured maximum nesting depth exceeds the "
                "configured threshold."
            ),
            remediation=(
                "Flatten nesting so maximum nesting depth falls at or below the "
                "configured threshold."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _complexity_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = complexity_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Complexity evidence unavailable",
            )
        matches = []
        for item in evidence.callables:
            if not exceeds_threshold(item.max_nesting_depth, threshold=self._threshold):
                continue
            value = int(item.max_nesting_depth.value or 0)
            matches.append(
                match(
                    rule_id=RULE_DEEP_NESTING,
                    title="Deep nesting",
                    summary=(
                        f"Callable '{item.qualified_signature}' has max_nesting_depth="
                        f"{value}, which exceeds threshold {self._threshold}."
                    ),
                    severity=severity_for_ratio(value=value, threshold=self._threshold),
                    confidence=RuleConfidence.HIGH,
                    evidence=(
                        evidence_callable(
                            item=item,
                            message=(
                                f"max_nesting_depth {value} > threshold {self._threshold}"
                            ),
                            metric_name="max_nesting_depth",
                            metric_value=value,
                            threshold=self._threshold,
                        ),
                    ),
                    subject_keys=(item.path, item.qualified_signature),
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(
                sorted(
                    matches,
                    key=lambda item: (
                        item.subject_keys,
                        str(item.rule_id),
                        item.summary,
                    ),
                )
            )
        )


class ExcessiveParametersRule:
    def __init__(self, *, max_parameters: int = 5) -> None:
        self._threshold = max_parameters

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_EXCESSIVE_PARAMETERS,
            title="Excessive parameters",
            description=(
                "Detects callables whose measured formal parameter count exceeds the "
                "configured threshold."
            ),
            remediation=(
                "Reduce parameters so parameter count falls at or below the configured "
                "threshold."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _complexity_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = complexity_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Complexity evidence unavailable",
            )
        matches = []
        for item in evidence.callables:
            if not exceeds_threshold(item.parameter_count, threshold=self._threshold):
                continue
            value = int(item.parameter_count.value or 0)
            matches.append(
                match(
                    rule_id=RULE_EXCESSIVE_PARAMETERS,
                    title="Excessive parameters",
                    summary=(
                        f"Callable '{item.qualified_signature}' has parameter_count="
                        f"{value}, which exceeds threshold {self._threshold}."
                    ),
                    severity=severity_for_ratio(value=value, threshold=self._threshold),
                    confidence=RuleConfidence.HIGH,
                    evidence=(
                        evidence_callable(
                            item=item,
                            message=(
                                f"parameter_count {value} > threshold {self._threshold}"
                            ),
                            metric_name="parameter_count",
                            metric_value=value,
                            threshold=self._threshold,
                        ),
                    ),
                    subject_keys=(item.path, item.qualified_signature),
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(
                sorted(
                    matches,
                    key=lambda item: (
                        item.subject_keys,
                        str(item.rule_id),
                        item.summary,
                    ),
                )
            )
        )


class OversizedTypeRule:
    def __init__(self, *, max_physical_lines: int = 300) -> None:
        self._threshold = max_physical_lines

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_OVERSIZED_TYPE,
            title="Oversized type",
            description=(
                "Detects classes/modules whose measured physical line count exceeds "
                "the configured threshold."
            ),
            remediation=(
                "Split the type/module so physical size falls at or below the "
                "configured threshold."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _complexity_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = complexity_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Complexity evidence unavailable",
            )
        matches = []
        for item in evidence.types:
            if not exceeds_threshold(item.physical_line_count, threshold=self._threshold):
                continue
            value = int(item.physical_line_count.value or 0)
            matches.append(
                match(
                    rule_id=RULE_OVERSIZED_TYPE,
                    title="Oversized type",
                    summary=(
                        f"Type '{item.qualified_name}' has physical_line_count="
                        f"{value}, which exceeds threshold {self._threshold}."
                    ),
                    severity=severity_for_ratio(value=value, threshold=self._threshold),
                    confidence=RuleConfidence.HIGH,
                    evidence=(
                        evidence_type(
                            item=item,
                            message=(
                                f"physical_line_count {value} > threshold {self._threshold}"
                            ),
                            metric_name="physical_line_count",
                            metric_value=value,
                            threshold=self._threshold,
                        ),
                    ),
                    subject_keys=(item.path, item.qualified_name),
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(
                sorted(
                    matches,
                    key=lambda item: (
                        item.subject_keys,
                        str(item.rule_id),
                        item.summary,
                    ),
                )
            )
        )
