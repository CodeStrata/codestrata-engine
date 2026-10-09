"""YAML-bound license.disallowed rule (E06.3).

Canonical default severity and message come from bundled YAML. Native code
evaluates supported SPDX expressions against an explicit allow/deny policy.
Absent policy emits metadata only. This is not a legal-compliance verdict.
"""

from __future__ import annotations

import re

from codestrata.application.evidence.supply_chain.models import (
    LicenseDecision,
    LicenseRecord,
    SupplyChainEvidence,
)
from codestrata.application.rules.security.helpers import match, recommendation_for
from codestrata.application.rules.security.yaml_catalog import (
    LICENSE_DISALLOWED_RULE_ID,
    load_license_disallowed_rule,
)
from codestrata.application.rules.security.yaml_vulnerability import supply_chain_evidence
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
from codestrata.domain.security.ids import PACK_ID

_BINDING = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_LICENSE_CONFIDENCE = RuleConfidence(
    level=RuleConfidenceLevel.HIGH,
    basis=(RuleConfidenceBasis.MANIFEST_DECLARATION,),
    limitations=(
        "License risk is a configured allow/deny result, not a legal "
        "compliance verdict. Missing or unsupported expressions stay UNKNOWN.",
    ),
    calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
)


def _render(template: str, values: dict[str, str]) -> str:
    return " ".join(_BINDING.sub(lambda node: values.get(node.group(1), ""), template).split())


class LicenseDisallowedRule:
    """SharedRule adapter bound to license.disallowed YAML."""

    def __init__(self) -> None:
        catalog = load_license_disallowed_rule()
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
            "python",
            "javascript",
            "typescript",
            "php",
            "csharp",
        )
        return RuleMetadata(
            rule_id=RuleId(self._rule_id),
            version=RuleVersion.parse(str(self._catalog.get("version") or "1.0.0")),
            title=self._title,
            description=str(self._catalog["description"]),
            category=RuleCategory.SECURITY,
            default_severity=self._severity,
            confidence=_LICENSE_CONFIDENCE,
            supported_languages=tuple(str(item) for item in languages),
            tags=("security", PACK_ID, "supply-chain", "license", "dimension:security"),
            remediation_summary=recommendation_for(self._rule_id),
            documentation_reference=str(self._catalog.get("documentation_url") or ""),
            enabled_by_default=True,
            experimental=False,
            requires_enterprise_context=False,
            incremental_behaviors=(
                RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
                RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        evidence = supply_chain_evidence(context)
        if evidence is None:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Supply-chain evidence unavailable",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = supply_chain_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Supply-chain evidence unavailable",
            )
        if evidence.license_policy is None or not evidence.license_policy.present:
            return SharedRuleEvaluationResult.not_matched()
        findings = tuple(
            item for item in evidence.licenses if item.decision is LicenseDecision.DISALLOWED
        )
        if not findings:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(self._matches(evidence, findings))

    def _matches(
        self, evidence: SupplyChainEvidence, findings: tuple[LicenseRecord, ...]
    ) -> list[RuleMatch]:
        policy_version = evidence.license_policy.version if evidence.license_policy else ""
        matches: list[RuleMatch] = []
        for item in findings:
            values = {
                "package_name": item.package_name,
                "resolved_version": item.resolved_version,
                "expression": item.normalized_expression or item.raw_expression,
                "license_source": item.license_source,
                "policy_version": policy_version,
            }
            summary = _render(self._template, values)
            matches.append(
                match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=summary,
                    severity=self._severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    rule_confidence=_LICENSE_CONFIDENCE,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.DEPENDENCY,
                            subject_reference=item.license_id,
                            message=summary,
                            safe_location=item.lock_path,
                            attributes={
                                "package_name": item.package_name,
                                "resolved_version": item.resolved_version,
                                "expression": item.normalized_expression,
                                "license_source": item.license_source,
                                "configured_decision_rule": item.decision_rule,
                                "expression_status": item.expression_status.value,
                                "policy_version": policy_version,
                                "legal_compliance_verdict": "false",
                            },
                            provenance="resolved_package_license_metadata",
                        ),
                    ),
                    subject_keys=(
                        LICENSE_DISALLOWED_RULE_ID,
                        item.ecosystem,
                        item.package_name,
                        item.resolved_version,
                        item.normalized_expression,
                    ),
                    base_severity=self._severity,
                    calibrated_severity=self._severity,
                    severity_basis=("yaml_catalog_default", "configured_deny"),
                )
            )
        return matches
