"""Composition helpers for Shared Rule Platform."""

from __future__ import annotations

from codestrata.application.rules.analysis_service import RuleAnalysisService
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.context import RuleExecutionPolicy


def policy_from_settings(settings: CodestrataSettings | None) -> RuleExecutionPolicy:
    if settings is None or getattr(settings, "rules", None) is None:
        return RuleExecutionPolicy()
    section = settings.rules
    return RuleExecutionPolicy(
        fail_on_rule_error=bool(section.fail_on_rule_error),
        max_matches_per_rule=int(section.max_matches_per_rule),
        max_total_matches=int(section.max_total_matches),
        max_evidence_per_match=int(section.max_evidence_per_match),
        max_rules_per_run=int(section.max_rules_per_run),
        claim_reuse=False,
    )


def create_empty_rule_registry() -> RuleRegistry:
    return RuleRegistry()


def create_rule_analysis_service(
    *,
    settings: CodestrataSettings | None = None,
    registry: RuleRegistry | None = None,
    suppressions: tuple[RuleSuppression, ...] = (),
    include_fixture_rules: bool = False,
    include_architecture_pack: bool = True,
    include_technical_debt_pack: bool = True,
    include_dependency_pack: bool = True,
    include_security_pack: bool = True,
    include_cloud_pack: bool = True,
    include_ai_readiness_pack: bool = True,
    include_performance_pack: bool = True,
) -> RuleAnalysisService:
    """Create a service with optional Architecture/TD/Dependency/Security/Cloud/AI/Perf packs.

    Packs are registered for CLI/MCP discovery even when disabled for assess.
    Execution remains gated by ``rules.enabled`` and per-pack ``enabled`` flags.
    """

    resolved = registry or RuleRegistry()
    if resolved.size == 0:
        rules_settings = settings.rules if settings is not None else None
        if include_architecture_pack:
            from codestrata.application.rules.architecture.registration import (
                register_architecture_pack,
            )

            register_architecture_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
        if include_technical_debt_pack:
            from codestrata.application.rules.technical_debt.registration import (
                register_technical_debt_pack,
            )

            register_technical_debt_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
        if include_dependency_pack:
            from codestrata.application.rules.dependency.registration import (
                register_dependency_pack,
            )

            register_dependency_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
        if include_security_pack:
            from codestrata.application.rules.security.registration import (
                register_security_pack,
            )

            register_security_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
        if include_cloud_pack:
            from codestrata.application.rules.cloud.registration import register_cloud_pack

            register_cloud_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
        if include_ai_readiness_pack:
            from codestrata.application.rules.ai_readiness.registration import (
                register_ai_readiness_pack,
            )

            register_ai_readiness_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
        if include_performance_pack:
            from codestrata.application.rules.performance.registration import (
                register_performance_pack,
            )

            register_performance_pack(
                resolved,
                settings=rules_settings,
                production=True,
            )
    if include_fixture_rules:
        from codestrata.application.rules.fixtures import fixture_rules

        resolved.register_collection(fixture_rules(), production=False)  # type: ignore[arg-type]
    return RuleAnalysisService(registry=resolved, suppressions=suppressions)
