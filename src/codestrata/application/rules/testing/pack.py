"""Test Intelligence pack metadata and rule construction (Phase 4.6.3)."""

from __future__ import annotations

from codestrata.application.rules.testing.rules import (
    CoverageWithoutCiInvocationRule,
    DeclaredWithoutObservationRule,
    DisabledOrSkippedMarkersRule,
    UnconfirmedCandidatesRule,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.testing.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)


class TestingRulePack:
    """First-class Test Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.TESTING
    supported_languages: tuple[str, ...] = (
        "java",
        "python",
        "javascript",
        "typescript",
        "kotlin",
        "groovy",
        "csharp",
        "php",
    )
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = (
        "docs/analysis-intelligence/shared-rule-platform.md"
    )
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.testing.enabled=true",
        "evidence.repository_testing.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = ()
    included_rule_ids: tuple[str, ...] = HYGIENE_RULE_IDS
    deferred_rule_ids: tuple[str, ...] = DEFERRED_RULE_IDS

    def to_dict(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "included_rule_ids": list(self.included_rule_ids),
            "deferred_rule_ids": list(self.deferred_rule_ids),
            "supported_languages": list(self.supported_languages),
            "default_enabled": self.default_enabled,
            "requires_enterprise_context": self.requires_enterprise_context,
            "configuration_requirements": list(self.configuration_requirements),
            "enterprise_context_requirements": list(
                self.enterprise_context_requirements
            ),
            "documentation_reference": self.documentation_reference,
        }


def testing_rules(
    *,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    candidates: list[tuple[str, SharedRule]] = [
        (RULE_DISABLED_OR_SKIPPED, DisabledOrSkippedMarkersRule()),
        (RULE_UNCONFIRMED_CANDIDATES, UnconfirmedCandidatesRule()),
        (RULE_DECLARED_WITHOUT_OBSERVATION, DeclaredWithoutObservationRule()),
        (RULE_COVERAGE_WITHOUT_CI_INVOCATION, CoverageWithoutCiInvocationRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
