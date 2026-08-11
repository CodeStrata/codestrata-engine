"""Map security evidence context to severity/confidence without dropping matches."""

from __future__ import annotations

from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleSeverity
from codestrata.domain.security.context import (
    CONTEXT_LABELS,
    NON_ACTIONABLE_CONTEXTS,
    SecurityContextDecision,
    SecurityEvidenceContext,
)
from codestrata.models.enums import Severity

_CONTEXT_RULE_SEVERITY: dict[SecurityEvidenceContext, RuleSeverity] = {
    SecurityEvidenceContext.PRODUCTION: RuleSeverity.HIGH,
    SecurityEvidenceContext.UNKNOWN: RuleSeverity.MEDIUM,
    SecurityEvidenceContext.TEST: RuleSeverity.LOW,
    SecurityEvidenceContext.TEST_FIXTURE: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.DOCUMENTATION: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.SAMPLE: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.GENERATED: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.DEPENDENCY_METADATA: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.BUILD_ARTIFACT: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.CONFIGURATION_SCHEMA: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.CI_EXPRESSION: RuleSeverity.INFORMATIONAL,
    SecurityEvidenceContext.MOCK_CREDENTIAL: RuleSeverity.INFORMATIONAL,
}

_CONTEXT_RULE_CONFIDENCE: dict[SecurityEvidenceContext, MatchEvidenceConfidence] = {
    SecurityEvidenceContext.PRODUCTION: MatchEvidenceConfidence.HIGH,
    SecurityEvidenceContext.UNKNOWN: MatchEvidenceConfidence.MEDIUM,
    SecurityEvidenceContext.TEST: MatchEvidenceConfidence.MEDIUM,
    SecurityEvidenceContext.TEST_FIXTURE: MatchEvidenceConfidence.MEDIUM,
    SecurityEvidenceContext.DOCUMENTATION: MatchEvidenceConfidence.LOW,
    SecurityEvidenceContext.SAMPLE: MatchEvidenceConfidence.LOW,
    SecurityEvidenceContext.GENERATED: MatchEvidenceConfidence.LOW,
    SecurityEvidenceContext.DEPENDENCY_METADATA: MatchEvidenceConfidence.LOW,
    SecurityEvidenceContext.BUILD_ARTIFACT: MatchEvidenceConfidence.LOW,
    SecurityEvidenceContext.CONFIGURATION_SCHEMA: MatchEvidenceConfidence.LOW,
    SecurityEvidenceContext.CI_EXPRESSION: MatchEvidenceConfidence.MEDIUM,
    SecurityEvidenceContext.MOCK_CREDENTIAL: MatchEvidenceConfidence.HIGH,
}

_CONTEXT_PHASE1_SEVERITY: dict[SecurityEvidenceContext, Severity] = {
    SecurityEvidenceContext.PRODUCTION: Severity.HIGH,
    SecurityEvidenceContext.UNKNOWN: Severity.MEDIUM,
    SecurityEvidenceContext.TEST: Severity.LOW,
    SecurityEvidenceContext.TEST_FIXTURE: Severity.INFO,
    SecurityEvidenceContext.DOCUMENTATION: Severity.INFO,
    SecurityEvidenceContext.SAMPLE: Severity.INFO,
    SecurityEvidenceContext.GENERATED: Severity.INFO,
    SecurityEvidenceContext.DEPENDENCY_METADATA: Severity.INFO,
    SecurityEvidenceContext.BUILD_ARTIFACT: Severity.INFO,
    SecurityEvidenceContext.CONFIGURATION_SCHEMA: Severity.INFO,
    SecurityEvidenceContext.CI_EXPRESSION: Severity.INFO,
    SecurityEvidenceContext.MOCK_CREDENTIAL: Severity.INFO,
}


def adjust_rule_severity(
    base: RuleSeverity,
    decision: SecurityContextDecision,
) -> RuleSeverity:
    """Lower severity for non-production contexts; never raise above base."""

    if decision.context is SecurityEvidenceContext.PRODUCTION:
        return base
    mapped = _CONTEXT_RULE_SEVERITY.get(decision.context, RuleSeverity.MEDIUM)
    return _min_rule_severity(base, mapped)


def adjust_rule_confidence(
    base: MatchEvidenceConfidence,
    decision: SecurityContextDecision,
) -> MatchEvidenceConfidence:
    if decision.context is SecurityEvidenceContext.PRODUCTION:
        return base
    mapped = _CONTEXT_RULE_CONFIDENCE.get(decision.context, MatchEvidenceConfidence.MEDIUM)
    return _min_rule_confidence(base, mapped)


def adjust_phase1_severity(
    base: Severity,
    decision: SecurityContextDecision,
) -> Severity:
    if decision.context is SecurityEvidenceContext.PRODUCTION:
        return base
    mapped = _CONTEXT_PHASE1_SEVERITY.get(decision.context, Severity.MEDIUM)
    return _min_phase1_severity(base, mapped)


def contextual_summary_suffix(decision: SecurityContextDecision) -> str:
    label = CONTEXT_LABELS.get(decision.context, decision.context.value)
    reason = ", ".join(decision.reasons) if decision.reasons else "context-heuristic"
    return f" Context: {label} ({reason})."


def is_non_actionable(decision: SecurityContextDecision) -> bool:
    return decision.context in NON_ACTIONABLE_CONTEXTS


_RULE_SEV_RANK = {
    RuleSeverity.INFORMATIONAL: 0,
    RuleSeverity.LOW: 1,
    RuleSeverity.MEDIUM: 2,
    RuleSeverity.HIGH: 3,
    RuleSeverity.CRITICAL: 4,
}
_RULE_CONF_RANK = {
    MatchEvidenceConfidence.LOW: 0,
    MatchEvidenceConfidence.MEDIUM: 1,
    MatchEvidenceConfidence.HIGH: 2,
    MatchEvidenceConfidence.CERTAIN: 3,
}
_PHASE1_SEV_RANK = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def _min_rule_severity(left: RuleSeverity, right: RuleSeverity) -> RuleSeverity:
    return left if _RULE_SEV_RANK[left] <= _RULE_SEV_RANK[right] else right


def _min_rule_confidence(left: MatchEvidenceConfidence, right: MatchEvidenceConfidence) -> MatchEvidenceConfidence:
    return left if _RULE_CONF_RANK[left] <= _RULE_CONF_RANK[right] else right


def _min_phase1_severity(left: Severity, right: Severity) -> Severity:
    return left if _PHASE1_SEV_RANK[left] <= _PHASE1_SEV_RANK[right] else right


__all__ = [
    "adjust_phase1_severity",
    "adjust_rule_confidence",
    "adjust_rule_severity",
    "contextual_summary_suffix",
    "is_non_actionable",
]
