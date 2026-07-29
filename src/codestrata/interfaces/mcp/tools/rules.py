"""Additive MCP tools for Shared Rule Platform (Phase 4.1 / 4.2)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.rules.analysis_service import RuleAnalysisService
from codestrata.application.rules.errors import RuleApplicationError
from codestrata.interfaces.mcp.tools._common import require_nonblank, run_bounded


def register_rules_tools(
    server: FastMCP,
    *,
    rule_analysis_service: RuleAnalysisService | None,
) -> None:
    @server.tool(name="list_shared_rules", structured_output=True)
    def list_shared_rules(category: str | None = None) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            # Lazy import avoids codestrata.cli ↔ mcp circular import at module load.
            from codestrata.cli.rules_mapping import map_rule_view
            from codestrata.domain.rules.enums import RuleCategory

            if rule_analysis_service is None:
                raise RuleApplicationError(
                    "Rule analysis service is not configured",
                    reason_code="rules_service_missing",
                )

            resolved_category: RuleCategory | None = None
            if category and category.strip():
                try:
                    resolved_category = RuleCategory(category.strip().lower())
                except ValueError as error:
                    raise RuleApplicationError(
                        f"Unknown category: {category}",
                        reason_code="invalid_category",
                    ) from error
            views = rule_analysis_service.list_rules(
                category=resolved_category,
                include_non_production=False,
            )
            payload: dict[str, Any] = {"rules": [map_rule_view(view) for view in views]}
            if resolved_category is RuleCategory.ARCHITECTURE:
                from codestrata.application.rules.architecture.pack import ArchitectureRulePack

                payload["pack"] = ArchitectureRulePack().to_dict()
            return payload

        return run_bounded("list_shared_rules", _run)

    @server.tool(name="get_shared_rule", structured_output=True)
    def get_shared_rule(rule_id: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            from codestrata.cli.rules_mapping import map_rule_view

            if rule_analysis_service is None:
                raise RuleApplicationError(
                    "Rule analysis service is not configured",
                    reason_code="rules_service_missing",
                )
            view = rule_analysis_service.inspect_rule(
                require_nonblank(rule_id, label="rule_id")
            )
            if not view.production:
                raise RuleApplicationError(
                    "Rule not found",
                    reason_code="rule_not_found",
                    rule_id=rule_id,
                )
            return map_rule_view(view)

        return run_bounded("get_shared_rule", _run)

    @server.tool(name="explain_shared_rule_metadata", structured_output=True)
    def explain_shared_rule_metadata(rule_id: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            from codestrata.cli.rules_mapping import map_explanation

            if rule_analysis_service is None:
                raise RuleApplicationError(
                    "Rule analysis service is not configured",
                    reason_code="rules_service_missing",
                )
            view = rule_analysis_service.inspect_rule(
                require_nonblank(rule_id, label="rule_id")
            )
            if not view.production:
                raise RuleApplicationError(
                    "Rule not found",
                    reason_code="rule_not_found",
                    rule_id=rule_id,
                )
            return map_explanation(rule_analysis_service.explain_rule_metadata(rule_id))

        return run_bounded("explain_shared_rule_metadata", _run)

    @server.tool(name="get_shared_rule_platform_summary", structured_output=True)
    def get_shared_rule_platform_summary() -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            if rule_analysis_service is None:
                raise RuleApplicationError(
                    "Rule analysis service is not configured",
                    reason_code="rules_service_missing",
                )
            views = rule_analysis_service.list_rules(include_non_production=False)
            from codestrata.application.rules.architecture.pack import ArchitectureRulePack
            from codestrata.domain.rules.enums import RuleCategory

            architecture_views = [
                view
                for view in views
                if view.metadata.category is RuleCategory.ARCHITECTURE
            ]
            pack = ArchitectureRulePack()
            return {
                "enabled_by_default": False,
                "production_rule_count": len(views),
                "architecture_rule_count": len(architecture_views),
                "architecture_pack": pack.to_dict(),
                "wired_into_assess": "opt-in via rules.enabled + rules.architecture.enabled",
                "phase": "4.2.1",
                "note": (
                    "Architecture Intelligence initial pack is discoverable; "
                    "assess merge remains disabled by default."
                ),
            }

        return run_bounded("get_shared_rule_platform_summary", _run)
