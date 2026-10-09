"""YAML-bound quality.test_association / testing.disabled / testing.ci_gap (E08.2).

Canonical default severity and messages come from bundled YAML. Native code
reads TestingEvidence only. Association is never labeled runtime coverage.
"""

from __future__ import annotations

import re

from codestrata.application.evidence.testing.models import (
    CoverageScope,
    GapStatus,
    MetricStatusName,
    SkipKind,
    TestingEvidence,
)
from codestrata.application.rules.technical_debt.yaml_catalog import bundled_quality_rule
from codestrata.application.rules.testing.yaml_catalog import bundled_testing_rule
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
from codestrata.domain.testing.ids import PACK_ID

_BINDING = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_ASSOCIATION_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.LIMITED,
    basis=(RuleConfidenceBasis.STATIC_PATTERN,),
    limitations=(
        "Static association is advisory. Import/reference is stronger than a "
        "naming convention. This is not measured runtime test coverage.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)
_SKIP_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.HIGH,
    basis=(RuleConfidenceBasis.DETERMINISTIC_THRESHOLD,),
    limitations=(
        "Only explicit skip/disable markers count. Conditional skips and "
        "dynamic skip conditions are not unconditional disabled tests.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)
_GAP_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.HIGH,
    basis=(RuleConfidenceBasis.EXPLICIT_CONFIGURATION,),
    limitations=(
        "Medium only when a complete supported CI config proves a declared "
        "tool is absent. Delegated scripts and conditional jobs stay UNKNOWN. "
        "A missing coverage report is not 0% code coverage.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)


def _render(template: str, values: dict[str, str]) -> str:
    return " ".join(_BINDING.sub(lambda node: values.get(node.group(1), ""), template).split())


def testing_evidence(context: RuleExecutionContext) -> TestingEvidence | None:
    for raw in (
        context.assessment_graph,
        context.enterprise_context,
        context.repository_testing_evidence,
    ):
        if isinstance(raw, TestingEvidence):
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
        severity_basis=("yaml_catalog_default", "static_evidence"),
    )


class _TestingYamlRule:
    def __init__(self, rule_id: str, *, quality: bool = False) -> None:
        catalog = bundled_quality_rule(rule_id) if quality else bundled_testing_rule(rule_id)
        self._catalog = catalog
        self._rule_id = str(catalog["rule_id"])
        severity = catalog["default_severity"]
        if isinstance(severity, RuleSeverity):
            self._severity = severity
        else:
            self._severity = RuleSeverity(str(severity))
        self._title = str(catalog["title"])
        self._template = str(catalog["message_template"])
        self._quality = quality

    @property
    def metadata(self) -> RuleMetadata:
        languages = self._catalog.get("languages") or (
            "java",
            "javascript",
            "typescript",
            "python",
        )
        category = RuleCategory.TECHNICAL_DEBT if self._quality else RuleCategory.TESTING
        return RuleMetadata(
            rule_id=RuleId(self._rule_id),
            version=RuleVersion.parse(str(self._catalog.get("version") or "1.0.0")),
            title=self._title,
            description=str(self._catalog["description"]),
            category=category,
            default_severity=self._severity,
            confidence=self._rule_confidence,
            supported_languages=tuple(str(item) for item in languages),
            tags=("testing", PACK_ID, str(self._catalog.get("measurement") or ""), "static"),
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
        return _SKIP_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return "Review the static evidence. Do not treat this as runtime coverage."

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        evidence = testing_evidence(context)
        if evidence is None:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Testing evidence unavailable",
            )
        return RuleApplicability.applicable()


class TestAssociationRule(_TestingYamlRule):
    __test__ = False

    def __init__(self) -> None:
        super().__init__("quality.test_association", quality=True)

    @property
    def _rule_confidence(self) -> RuleConfidence:
        return _ASSOCIATION_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return (
            "Add or clarify static tests for unassociated production units. "
            "This advisory is not measured runtime test coverage."
        )

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = testing_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Testing evidence unavailable",
            )
        metric = evidence.association
        if metric.status is MetricStatusName.NOT_APPLICABLE or not metric.eligible:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="No eligible production units",
            )
        if metric.full_scope_status is not CoverageScope.COMPLETE:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Association scope is UNKNOWN; a missing-test claim is not proven",
            )
        if metric.associated is None or metric.associated >= metric.eligible:
            return SharedRuleEvaluationResult.not_matched()
        values = {
            "serialized": metric.serialized or "",
            "associated": str(metric.associated),
            "eligible": str(metric.eligible),
            "formula_version": metric.formula_version,
            "full_scope_status": metric.full_scope_status.value,
        }
        summary = _render(self._template, values)
        first = metric.unassociated[0] if metric.unassociated else ""
        return SharedRuleEvaluationResult.matched(
            (
                _match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=RuleSeverity.LOW,
                    confidence=MatchEvidenceConfidence.MEDIUM,
                    rule_confidence=_ASSOCIATION_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.REPOSITORY_FACT,
                            subject_reference="quality.test_association",
                            message=summary,
                            safe_location=first,
                            attributes={
                                "associated": str(metric.associated),
                                "eligible": str(metric.eligible),
                                "serialized": metric.serialized or "",
                                "formula_version": metric.formula_version,
                                "runtime_coverage": "false",
                                "unassociated": ",".join(metric.unassociated),
                            },
                            provenance="testing.association",
                        ),
                    ),
                    subject_keys=(self._rule_id, metric.serialized or "none"),
                    remediation=self._remediation,
                ),
            )
        )


class DisabledTestsRule(_TestingYamlRule):
    def __init__(self) -> None:
        super().__init__("testing.disabled")

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = testing_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Testing evidence unavailable",
            )
        metric = evidence.skipped
        if metric.status is MetricStatusName.NOT_APPLICABLE:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="No tests",
            )
        count = metric.explicit_disabled or 0
        if count <= 0:
            return SharedRuleEvaluationResult.not_matched()
        severity = (
            RuleSeverity.MEDIUM
            if count >= evidence.thresholds.disabled_medium_min
            else RuleSeverity.LOW
        )
        values = {
            "explicit_disabled": str(count),
            "formula_version": metric.formula_version,
            "conditional": str(metric.conditional),
        }
        summary = _render(self._template, values)
        matches: list[RuleMatch] = []
        for item in metric.records:
            if item.kind is not SkipKind.EXPLICIT_DISABLED:
                continue
            matches.append(
                _match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    rule_confidence=_SKIP_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.SYMBOL,
                            subject_reference=item.test_id,
                            message=summary,
                            safe_location=item.path,
                            line_start=item.span.line_start,
                            line_end=item.span.line_end,
                            attributes={
                                "test_id": item.test_id,
                                "annotation": item.annotation,
                                "kind": item.kind.value,
                                "reason": item.reason or "",
                                "static_condition": item.static_condition or "",
                                "conditional_count": str(metric.conditional),
                                "unknown_eligibility": str(metric.unknown_eligibility),
                            },
                            provenance="testing.skip",
                        ),
                    ),
                    subject_keys=(self._rule_id, item.test_id),
                    remediation=self._remediation,
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(sorted(matches, key=lambda item: (item.subject_keys, item.summary)))
        )


class CiGapRule(_TestingYamlRule):
    def __init__(self) -> None:
        super().__init__("testing.ci_gap")

    @property
    def _rule_confidence(self) -> RuleConfidence:
        return _GAP_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return (
            "Add an explicit test or coverage command to inspected CI when the "
            "declared tool is intended to run. Do not treat a missing report as 0%."
        )

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = testing_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Testing evidence unavailable",
            )
        metric = evidence.ci_gap
        if metric.status is MetricStatusName.NOT_APPLICABLE:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message=metric.reason,
            )
        proven = [
            item
            for item in metric.gaps
            if item.status is GapStatus.PROVEN_ABSENT
            and metric.full_scope_status is CoverageScope.COMPLETE
        ]
        if not proven:
            if metric.full_scope_status is CoverageScope.UNKNOWN or metric.unknown:
                return SharedRuleEvaluationResult.not_applicable(
                    reason=RuleSkipReason.OTHER,
                    message="CI invocation evidence is UNKNOWN; a medium gap is not proven",
                )
            return SharedRuleEvaluationResult.not_matched()
        matches: list[RuleMatch] = []
        for item in proven:
            values = {
                "kind": item.kind,
                "tool": item.tool,
                "formula_version": metric.formula_version,
                "checked_scope": item.checked_scope,
            }
            summary = _render(self._template, values)
            first = item.invocations[0] if item.invocations else None
            location = first.path if first is not None and first.path else None
            matches.append(
                _match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=RuleSeverity.MEDIUM,
                    confidence=MatchEvidenceConfidence.HIGH,
                    rule_confidence=_GAP_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.CONFIGURATION_KEY,
                            subject_reference=item.capability_id,
                            message=summary,
                            safe_location=location,
                            line_start=first.line if first is not None else None,
                            attributes={
                                "tool": item.tool,
                                "kind": item.kind,
                                "reason": item.reason,
                                "checked_scope": item.checked_scope,
                                "coverage_percent": "none",
                                "runtime_pass_fail": "false",
                            },
                            provenance="testing.ci_gap",
                        ),
                    ),
                    subject_keys=(self._rule_id, item.capability_id),
                    remediation=self._remediation,
                )
            )
        return SharedRuleEvaluationResult.matched(
            tuple(sorted(matches, key=lambda item: (item.subject_keys, item.summary)))
        )


__all__ = [
    "CiGapRule",
    "DisabledTestsRule",
    "TestAssociationRule",
    "testing_evidence",
]
