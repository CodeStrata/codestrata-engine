"""Shared Rule Platform application package (Phase 4.1)."""

from __future__ import annotations

__all__ = [
    "LegacyRuleAdapter",
    "RuleAnalysisService",
    "RuleExecutionFacade",
    "RuleRegistry",
    "RuleTestHarness",
    "create_rule_analysis_service",
    "policy_from_settings",
]


def __getattr__(name: str) -> object:
    if name == "RuleAnalysisService":
        from codestrata.application.rules.analysis_service import RuleAnalysisService

        return RuleAnalysisService
    if name == "RuleRegistry":
        from codestrata.application.rules.registry import RuleRegistry

        return RuleRegistry
    if name == "RuleTestHarness":
        from codestrata.application.rules.harness import RuleTestHarness

        return RuleTestHarness
    if name == "RuleExecutionFacade":
        from codestrata.application.rules.facade import RuleExecutionFacade

        return RuleExecutionFacade
    if name == "LegacyRuleAdapter":
        from codestrata.application.rules.legacy_adapter import LegacyRuleAdapter

        return LegacyRuleAdapter
    if name in {"create_rule_analysis_service", "policy_from_settings"}:
        from codestrata.application.rules import factory as _factory

        return getattr(_factory, name)
    raise AttributeError(name)
