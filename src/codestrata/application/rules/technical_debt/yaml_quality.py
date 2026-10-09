"""YAML-bound quality.complexity / quality.nesting / quality.clone_indicator (E08.1).

Canonical default severity and messages come from bundled YAML. Native code
reads QualityEvidence only. Unknown parse is never a clean zero. There is no
language-independent maintainability index.
"""

from __future__ import annotations

import re

from codestrata.application.evidence.quality.models import (
    FunctionRecord,
    FunctionStatus,
    MetricStatusName,
    QualityEvidence,
)
from codestrata.application.rules.technical_debt.yaml_catalog import bundled_quality_rule
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    MatchEvidenceConfidence,
    RuleCategory,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
    RuleSkipReason,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult
from codestrata.domain.rules.rule_confidence import (
    RuleConfidence,
    RuleConfidenceBasis,
    RuleConfidenceCalibrationStatus,
    RuleConfidenceLevel,
)
from codestrata.domain.technical_debt.ids import PACK_ID

_BINDING = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_STRUCTURAL_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.HIGH,
    basis=(RuleConfidenceBasis.DETERMINISTIC_THRESHOLD,),
    limitations=(
        "Thresholds are configurable heuristics. Unparsed functions stay UNKNOWN "
        "and never become a cross-language maintainability index.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)
_CLONE_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.LIMITED,
    basis=(RuleConfidenceBasis.STATIC_PATTERN,),
    limitations=(
        "Exact normalized token runs are an indicative clone, not proof that "
        "duplication is wrong. Identifier spellings are kept, so a rename is "
        "not a clone under token.normalize.v1.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)


def _render(template: str, values: dict[str, str]) -> str:
    return " ".join(_BINDING.sub(lambda node: values.get(node.group(1), ""), template).split())


def quality_evidence(context: RuleExecutionContext) -> QualityEvidence | None:
    for raw in (
        context.assessment_graph,
        context.enterprise_context,
        context.complexity_evidence,
    ):
        if isinstance(raw, QualityEvidence):
            return raw
    return None


def _match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: MatchEvidenceConfidence,
    rule_confidence: RuleConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    remediation: str,
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse("1.0.0"),
        severity=severity,
        confidence=confidence,
        rule_confidence=rule_confidence,
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=remediation,
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
        base_severity=severity,
        calibrated_severity=severity,
        severity_basis=("yaml_catalog_default", "heuristic_threshold"),
    )


class _QualityYamlRule:
    def __init__(self, rule_id: str) -> None:
        catalog = bundled_quality_rule(rule_id)
        self._catalog = catalog
        self._rule_id = str(catalog["rule_id"])
        severity = catalog["default_severity"]
        if isinstance(severity, RuleSeverity):
            self._severity = severity
        else:
            self._severity = RuleSeverity(str(severity))
        self._title = str(catalog["title"])
        self._template = str(catalog["message_template"])
        self._parameters = catalog.get("parameters") or {}

    @property
    def metadata(self) -> RuleMetadata:
        languages = self._catalog.get("languages") or (
            "java",
            "javascript",
            "typescript",
            "python",
        )
        return RuleMetadata(
            rule_id=RuleId(self._rule_id),
            version=RuleVersion.parse(str(self._catalog.get("version") or "1.0.0")),
            title=self._title,
            description=str(self._catalog["description"]),
            category=RuleCategory.TECHNICAL_DEBT,
            default_severity=self._severity,
            confidence=self._rule_confidence,
            supported_languages=tuple(str(item) for item in languages),
            tags=("quality", PACK_ID, str(self._catalog.get("measurement") or ""), "heuristic"),
            remediation_summary=self._remediation,
            documentation_reference=str(self._catalog.get("documentation_url") or ""),
            enabled_by_default=True,
            experimental=False,
            requires_enterprise_context=False,
            incremental_behaviors=(
                RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
                RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
            ),
        )

    @property
    def _rule_confidence(self) -> RuleConfidence:
        return _STRUCTURAL_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return (
            "Reduce the measured heuristic below the configured threshold. "
            "Do not treat this as a maintainability index."
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        evidence = quality_evidence(context)
        if evidence is None:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Quality evidence unavailable",
            )
        return RuleApplicability.applicable()


class ComplexityRule(_QualityYamlRule):
    def __init__(self) -> None:
        super().__init__("quality.complexity")

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = quality_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Quality evidence unavailable",
            )
        cyclomatic_threshold = int(evidence.thresholds.complexity)
        size_threshold = int(evidence.thresholds.function_lines)
        matches: list[RuleMatch] = []
        for item in evidence.functions:
            if item.status is FunctionStatus.UNKNOWN:
                continue
            if item.cyclomatic is not None and item.cyclomatic > cyclomatic_threshold:
                matches.append(
                    self._function_match(
                        item,
                        metric="cyclomatic",
                        value=item.cyclomatic,
                        threshold=cyclomatic_threshold,
                        formula=item.cyclomatic_version,
                        severity=RuleSeverity.MEDIUM,
                    )
                )
            if item.nloc is not None and item.nloc > size_threshold:
                matches.append(
                    self._function_match(
                        item,
                        metric="nloc",
                        value=item.nloc,
                        threshold=size_threshold,
                        formula=item.size_version,
                        severity=RuleSeverity.LOW,
                    )
                )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(sorted(matches, key=lambda item: (item.subject_keys, item.summary)))
        )

    def _function_match(
        self,
        item: FunctionRecord,
        *,
        metric: str,
        value: int,
        threshold: int,
        formula: str,
        severity: RuleSeverity,
    ) -> RuleMatch:
        values = {
            "qualified_name": item.qualified_name,
            "path": item.path,
            "metric": metric,
            "value": str(value),
            "threshold": str(threshold),
            "formula_version": formula,
        }
        summary = _render(self._template, values)
        return _match(
            rule_id=self._rule_id,
            title=self._title,
            summary=summary,
            severity=severity,
            confidence=MatchEvidenceConfidence.HIGH,
            rule_confidence=_STRUCTURAL_CONFIDENCE,
            evidence=(
                RuleEvidence(
                    kind=RuleEvidenceKind.SYMBOL,
                    subject_reference=item.function_id,
                    message=summary,
                    safe_location=item.path,
                    line_start=item.span.line_start,
                    line_end=item.span.line_end,
                    attributes={
                        "function_id": item.function_id,
                        "qualified_name": item.qualified_name,
                        "metric": metric,
                        "value": str(value),
                        "threshold": str(threshold),
                        "formula_version": formula,
                        "language": item.language,
                        "branch_count": str(item.branch_count or 0),
                        "counted_branch_locations": ",".join(
                            f"{branch.syntax}@{branch.line}" for branch in item.branches
                        ),
                    },
                    provenance="quality.function",
                ),
            ),
            subject_keys=(self._rule_id, item.function_id, metric),
            remediation=self._remediation,
        )


class NestingRule(_QualityYamlRule):
    def __init__(self) -> None:
        super().__init__("quality.nesting")

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = quality_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Quality evidence unavailable",
            )
        if not evidence.functions:
            unknown_files = any(item.unknown_reason for item in evidence.files)
            if unknown_files:
                return SharedRuleEvaluationResult.not_applicable(
                    reason=RuleSkipReason.OTHER,
                    message="Unknown parse sections invalidate a negative nesting claim",
                )
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Absent functions",
            )
        threshold = int(evidence.thresholds.nesting)
        matches: list[RuleMatch] = []
        for item in evidence.functions:
            if item.status is FunctionStatus.UNKNOWN or item.max_nesting_depth is None:
                continue
            if item.max_nesting_depth > threshold:
                values = {
                    "qualified_name": item.qualified_name,
                    "path": item.path,
                    "value": str(item.max_nesting_depth),
                    "threshold": str(threshold),
                    "formula_version": item.nesting_version,
                }
                summary = _render(self._template, values)
                matches.append(
                    _match(
                        rule_id=self._rule_id,
                        title=self._title,
                        summary=summary,
                        severity=self._severity,
                        confidence=MatchEvidenceConfidence.HIGH,
                        rule_confidence=_STRUCTURAL_CONFIDENCE,
                        evidence=(
                            RuleEvidence(
                                kind=RuleEvidenceKind.SYMBOL,
                                subject_reference=item.function_id,
                                message=summary,
                                safe_location=item.path,
                                line_start=item.span.line_start,
                                line_end=item.span.line_end,
                                attributes={
                                    "function_id": item.function_id,
                                    "max_nesting_depth": str(item.max_nesting_depth),
                                    "formula_version": item.nesting_version,
                                    "nesting_witness": ",".join(
                                        f"{node.syntax}@{node.line}"
                                        for node in item.nesting_witness
                                    ),
                                },
                                provenance="quality.function",
                            ),
                        ),
                        subject_keys=(self._rule_id, item.function_id),
                        remediation=self._remediation,
                    )
                )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(sorted(matches, key=lambda item: (item.subject_keys, item.summary)))
        )


class CloneIndicatorRule(_QualityYamlRule):
    def __init__(self) -> None:
        super().__init__("quality.clone_indicator")

    @property
    def _rule_confidence(self) -> RuleConfidence:
        return _CLONE_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return (
            "Review matched spans. The indicator is advisory and does not prove "
            "that duplication is wrong."
        )

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = quality_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Quality evidence unavailable",
            )
        clone = evidence.clone
        if clone.status is MetricStatusName.NOT_APPLICABLE:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="No eligible source lines",
            )
        if clone.status is MetricStatusName.UNKNOWN and clone.numerator is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Clone coverage is unknown; a zero ratio is not claimed",
            )
        if clone.serialized is None or clone.numerator is None or clone.denominator is None:
            return SharedRuleEvaluationResult.not_matched()
        threshold = float(evidence.thresholds.clone_ratio)
        if float(clone.serialized) <= threshold:
            return SharedRuleEvaluationResult.not_matched()
        values = {
            "serialized": clone.serialized,
            "numerator": str(clone.numerator),
            "denominator": str(clone.denominator),
            "normalization_version": clone.normalization_version,
            "threshold": evidence.thresholds.clone_ratio,
            "full_scope_status": clone.full_scope_status.value,
        }
        summary = _render(self._template, values)
        first = clone.merged_spans[0] if clone.merged_spans else None
        return SharedRuleEvaluationResult.matched(
            (
                _match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=RuleSeverity.LOW,
                    confidence=MatchEvidenceConfidence.LOW,
                    rule_confidence=_CLONE_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.REPOSITORY_FACT,
                            subject_reference="quality.clone_indicator",
                            message=summary,
                            safe_location=first.path if first is not None else "",
                            line_start=first.line_start if first is not None else None,
                            line_end=first.line_end if first is not None else None,
                            attributes={
                                "numerator": str(clone.numerator),
                                "denominator": str(clone.denominator),
                                "serialized": clone.serialized,
                                "normalization_version": clone.normalization_version,
                                "formula_version": clone.formula_version,
                                "full_scope_status": clone.full_scope_status.value,
                                "cutoff": str(clone.cutoff).lower(),
                            },
                            provenance="quality.clone",
                        ),
                    ),
                    subject_keys=(self._rule_id, clone.serialized),
                    remediation=self._remediation,
                ),
            )
        )


__all__ = [
    "CloneIndicatorRule",
    "ComplexityRule",
    "NestingRule",
    "quality_evidence",
]
