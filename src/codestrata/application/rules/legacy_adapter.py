"""Adapt legacy Assessment Graph rules to the SharedRule contract.

Finding identity and evidence are preserved by evaluating the wrapped
:class:`~codestrata.domain.rules.models.Rule` against a
:class:`~codestrata.domain.rules.models.RuleContext` and passing through
:class:`~codestrata.domain.findings.models.Finding` objects unchanged.
"""

from __future__ import annotations

from codestrata.domain.findings import Finding
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
    RuleSkipReason,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.models import Rule, RuleContext, RuleResult
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult


class LegacyRuleAdapter:
    """Wrap a legacy :class:`Rule` as a :class:`~codestrata.domain.rules.contracts.SharedRule`.

    Does not change rule logic. Prefer :meth:`evaluate_legacy` when Finding
    identity must match the RuleEngine bit-for-bit.
    """

    def __init__(
        self,
        rule: Rule,
        *,
        version: RuleVersion | None = None,
        category: RuleCategory = RuleCategory.PLATFORM,
    ) -> None:
        self._rule = rule
        self._version = version or RuleVersion(major=1, minor=0, patch=0)
        self._category = category
        self._last_findings: tuple[Finding, ...] = ()

    @property
    def legacy_rule(self) -> Rule:
        return self._rule

    @property
    def last_findings(self) -> tuple[Finding, ...]:
        """Findings from the most recent legacy evaluation (passthrough)."""

        return self._last_findings

    @property
    def metadata(self) -> RuleMetadata:
        languages = tuple(sorted(self._rule.supported_languages()))
        return RuleMetadata(
            rule_id=RuleId(self._rule.id()),
            version=self._version,
            title=self._rule.name(),
            description=self._rule.description(),
            category=self._category,
            default_severity=RuleSeverity.MEDIUM,
            supported_languages=languages,
            tags=("legacy", "assessment-graph"),
            remediation_summary=None,
            documentation_reference="docs/rule-engine.md",
            enabled_by_default=True,
            experimental=False,
            requires_enterprise_context=False,
            incremental_behaviors=(
                RuleIncrementalBehavior.ALWAYS_RUN,
                RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
            ),
        )

    def is_applicable_legacy(self, context: RuleContext) -> bool:
        """Mirror :meth:`RuleEngine._is_applicable` language filtering."""

        supported = self._rule.supported_languages()
        if not supported:
            return True
        languages = {key.lower() for key in context.bound_keys()}
        for entry in context.manifest.files:
            if entry.language:
                languages.add(entry.language.strip().lower())
        return bool(languages.intersection({item.lower() for item in supported}))

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        legacy = _legacy_context(context)
        if legacy is None:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Legacy RuleContext required for adapted rules",
            )
        if not self.is_applicable_legacy(legacy):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.UNSUPPORTED_LANGUAGE,
                message="No overlapping language inventory",
            )
        return RuleApplicability.applicable()

    def evaluate_legacy(self, context: RuleContext) -> RuleResult:
        """Passthrough evaluation — preserves Finding IDs and evidence."""

        result = self._rule.evaluate(context)
        self._last_findings = tuple(result.findings)
        return result

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        """SharedRule contract; converts findings to matches for platform use.

        For bit-identical Assessment Graph findings, use :meth:`evaluate_legacy`
        or :class:`RuleExecutionFacade.evaluate_adapted`.
        """

        legacy = _legacy_context(context)
        if legacy is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Legacy RuleContext required for adapted rules",
            )
        result = self.evaluate_legacy(legacy)
        if result.skipped:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message=result.skip_reason or "legacy rule skipped",
            )
        if not result.findings:
            return SharedRuleEvaluationResult.not_matched()
        matches = tuple(
            _finding_to_match(finding, version=self._version)
            for finding in result.findings
        )
        return SharedRuleEvaluationResult.matched(matches)


def adapt_legacy_rules(
    rules: tuple[Rule, ...] | list[Rule],
    *,
    version: RuleVersion | None = None,
) -> tuple[LegacyRuleAdapter, ...]:
    """Wrap legacy rules as adapters in deterministic id order."""

    ordered = tuple(sorted(rules, key=lambda rule: rule.id()))
    return tuple(LegacyRuleAdapter(rule, version=version) for rule in ordered)


def _legacy_context(context: RuleExecutionContext) -> RuleContext | None:
    raw = context.legacy_rule_context
    if isinstance(raw, RuleContext):
        return raw
    return None


def _finding_to_match(finding: Finding, *, version: RuleVersion) -> RuleMatch:
    """Best-effort RuleMatch view of a Finding (not used for ID-preserving assess)."""

    evidence = tuple(
        RuleEvidence(
            kind=_map_evidence_kind(item.evidence_type),
            subject_reference=item.source_id,
            message=finding.description,
            safe_location=item.path,
            excerpt_fingerprint=None,
            attributes={},
            provenance="legacy_rule_adapter",
        )
        for item in finding.evidence
    )
    if not evidence:
        evidence = (
            RuleEvidence(
                kind=RuleEvidenceKind.REPOSITORY_FACT,
                subject_reference=finding.rule_id,
                message=finding.description,
                provenance="legacy_rule_adapter",
            ),
        )
    return RuleMatch(
        rule_id=RuleId(finding.rule_id),
        rule_version=version,
        severity=finding.severity,
        confidence=RuleConfidence.CERTAIN,
        title=finding.title,
        summary=finding.description,
        evidence=evidence,
        remediation=None,
        affected_entities=tuple(node.root for node in finding.affected_assessment_node_ids),
        provenance="legacy_rule_adapter",
        subject_keys=(finding.id,),
    )


def _map_evidence_kind(evidence_type: str) -> RuleEvidenceKind:
    compact = evidence_type.strip().lower()
    mapping = {
        "repository_manifest": RuleEvidenceKind.REPOSITORY_FACT,
        "dependency": RuleEvidenceKind.DEPENDENCY,
        "file": RuleEvidenceKind.FILE_LOCATION,
        "graph_node": RuleEvidenceKind.GRAPH_NODE,
        "configuration": RuleEvidenceKind.CONFIGURATION_KEY,
    }
    return mapping.get(compact, RuleEvidenceKind.REPOSITORY_FACT)
