"""Test Intelligence SharedRule package (Phase 4.6.3)."""

from codestrata.application.rules.testing.assessment import (
    TestingPackExecutionResult,
    TestingRuleExecutionFact,
    evaluate_testing_pack_detailed,
    evaluate_testing_pack_for_context_detailed,
    testing_rules_planned_count,
)
from codestrata.application.rules.testing.pack import TestingRulePack, testing_rules
from codestrata.application.rules.testing.registration import register_testing_pack
from codestrata.application.rules.testing.yaml_catalog import testing_catalog_digests
from codestrata.application.rules.testing.yaml_retained import (
    YamlCoverageWithoutCiRule,
    YamlDeclaredWithoutObservationRule,
    YamlDisabledOrSkippedRule,
    YamlUnconfirmedCandidatesRule,
)
from codestrata.application.rules.testing.yaml_testing import (
    CiGapRule,
    DisabledTestsRule,
    TestAssociationRule,
)

__all__ = [
    "CiGapRule",
    "DisabledTestsRule",
    "TestAssociationRule",
    "YamlCoverageWithoutCiRule",
    "YamlDeclaredWithoutObservationRule",
    "YamlDisabledOrSkippedRule",
    "YamlUnconfirmedCandidatesRule",
    "TestingPackExecutionResult",
    "TestingRuleExecutionFact",
    "TestingRulePack",
    "evaluate_testing_pack_detailed",
    "evaluate_testing_pack_for_context_detailed",
    "register_testing_pack",
    "testing_catalog_digests",
    "testing_rules",
    "testing_rules_planned_count",
]
