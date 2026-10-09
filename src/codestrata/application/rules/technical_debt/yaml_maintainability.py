"""YAML-bound maintainability.hotspot and maintainability.dependency_age (E08.3).

Canonical default severity and messages come from bundled YAML. Native code
reads MaintainabilityEvidence only. Ranking is complexity × churn; age is not
a security proof. There is no opaque score.
"""

from __future__ import annotations

import re

from codestrata.application.evidence.maintainability.capability import HOTSPOT_FORMULA_VERSION
from codestrata.application.evidence.maintainability.models import (
    MaintainabilityEvidence,
    MetricStatusName,
)
from codestrata.application.rules.technical_debt.yaml_catalog import bundled_quality_rule
from codestrata.domain.contracts.enums import ContributorRole
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
_HOTSPOT_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.HIGH,
    basis=(RuleConfidenceBasis.DETERMINISTIC_THRESHOLD,),
    limitations=(
        "Ranking value is complexity times changed lines only. Contextual "
        "centrality, reach, ownership and findings do not change rank. High "
        "rank is not runtime failure probability.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)
_AGE_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.HIGH,
    basis=(RuleConfidenceBasis.EXPLICIT_CONFIGURATION,),
    limitations=(
        "Staleness requires pinned evaluation_time and permitted publication "
        "metadata. Age does not prove a package is insecure or unsupported.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)


def _render(template: str, values: dict[str, str]) -> str:
    return " ".join(_BINDING.sub(lambda node: values.get(node.group(1), ""), template).split())


def maintainability_evidence(context: RuleExecutionContext) -> MaintainabilityEvidence | None:
    for raw in (
        context.assessment_graph,
        context.enterprise_context,
        context.complexity_evidence,
    ):
        if isinstance(raw, MaintainabilityEvidence):
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
        severity_basis=("yaml_catalog_default", "pinned_evidence"),
    )


class _MaintainabilityYamlRule:
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
            tags=(
                "maintainability",
                PACK_ID,
                str(self._catalog.get("measurement") or ""),
                "yaml",
            ),
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
        return _HOTSPOT_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return (
            "Review complexity and the pinned history window together. Do not "
            "treat rank as failure probability, cost-to-fix, or blame."
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        evidence = maintainability_evidence(context)
        if evidence is None:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Maintainability evidence unavailable",
            )
        return RuleApplicability.applicable()


class HotspotRule(_MaintainabilityYamlRule):
    def __init__(self) -> None:
        super().__init__("maintainability.hotspot")

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = maintainability_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Maintainability evidence unavailable",
            )
        threshold = evidence.thresholds.hotspot_min_value
        matches: list[RuleMatch] = []
        for item in evidence.complete_hotspots:
            if item.ranking_value is None:
                continue
            value = int(item.ranking_value)
            if value <= threshold:
                continue
            complexity = next(
                c.value
                for c in item.contributors
                if c.role is ContributorRole.RANKING and c.name == "complexity"
            )
            churn = next(
                c.value
                for c in item.contributors
                if c.role is ContributorRole.RANKING and c.name == "churn"
            )
            values = {
                "subject_id": item.subject_id,
                "ranking_value": item.ranking_value,
                "complexity": complexity or "UNKNOWN",
                "changed_lines": churn or "UNKNOWN",
                "formula_version": HOTSPOT_FORMULA_VERSION,
                "history_window": item.history_window,
                "priority_explanation": item.priority_explanation,
            }
            summary = _render(self._template, values)
            matches.append(
                _match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=MatchEvidenceConfidence.HIGH,
                    rule_confidence=_HOTSPOT_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.MODULE,
                            subject_reference=item.record_id,
                            message=summary,
                            safe_location=item.subject_id,
                            attributes={
                                "record_id": item.record_id,
                                "ranking_value": item.ranking_value,
                                "list_kind": item.list_kind.value,
                                "history_profile_id": item.history_profile_id,
                                "history_window": item.history_window,
                                "priority_explanation": item.priority_explanation,
                                "opaque_score": "false",
                                "runtime_failure_probability": "none",
                            },
                            provenance="maintainability.hotspot",
                        ),
                    ),
                    subject_keys=(self._rule_id, item.subject_id),
                    remediation=self._remediation,
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(sorted(matches, key=lambda item: (item.subject_keys, item.summary)))
        )


class DependencyAgeRule(_MaintainabilityYamlRule):
    def __init__(self) -> None:
        super().__init__("maintainability.dependency_age")

    @property
    def _rule_confidence(self) -> RuleConfidence:
        return _AGE_CONFIDENCE

    @property
    def _remediation(self) -> str:
        return (
            "Review the pinned publication snapshot. Age is advisory and does "
            "not prove the package is insecure or unsupported."
        )

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = maintainability_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Maintainability evidence unavailable",
            )
        threshold = evidence.thresholds.dependency_age_days
        matches: list[RuleMatch] = []
        for item in evidence.staleness:
            if item.status is not MetricStatusName.VALUE or item.days is None:
                continue
            if item.days <= threshold:
                continue
            values = {
                "package_id": item.package_id,
                "installed_version": item.installed_version,
                "days": str(item.days),
                "formula_version": item.formula_version,
                "source_snapshot_id": item.source_snapshot_id,
            }
            summary = _render(self._template, values)
            matches.append(
                _match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=RuleSeverity.LOW,
                    confidence=MatchEvidenceConfidence.HIGH,
                    rule_confidence=_AGE_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.DEPENDENCY,
                            subject_reference=item.package_id,
                            message=summary,
                            safe_location=item.package_id,
                            attributes={
                                "package_id": item.package_id,
                                "installed_version": item.installed_version,
                                "days": str(item.days),
                                "evaluation_time_unix": str(item.evaluation_time_unix or ""),
                                "publication_time_unix": str(item.publication_time_unix or ""),
                                "source_snapshot_id": item.source_snapshot_id,
                                "insecure_claim": "false",
                            },
                            provenance="maintainability.dependency_age",
                        ),
                    ),
                    subject_keys=(self._rule_id, item.package_id, item.installed_version),
                    remediation=self._remediation,
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(
            tuple(sorted(matches, key=lambda item: (item.subject_keys, item.summary)))
        )


__all__ = [
    "DependencyAgeRule",
    "HotspotRule",
    "maintainability_evidence",
]
