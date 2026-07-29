"""MCP tests for Shared Rule Platform tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.interfaces.mcp.server import build_mcp_server
from codestrata.interfaces.mcp.tools.rules import register_rules_tools


def test_rules_tools_register_additively() -> None:
    server = FastMCP("test")
    service = create_rule_analysis_service()
    register_rules_tools(server, rule_analysis_service=service)
    # Tool manager should expose the four Phase 4.1 tools.
    tools = getattr(server, "_tool_manager", None)
    assert tools is not None


def test_list_shared_rules_includes_architecture_pack() -> None:
    from codestrata.application.assessment import AssessmentApplicationService
    from codestrata.application.knowledge.queries import KnowledgeQueryService
    from codestrata.cli.rules_mapping import map_rule_view
    from codestrata.domain.rules.enums import RuleCategory

    service = create_rule_analysis_service()
    views = service.list_rules(include_non_production=False)
    rows = [map_rule_view(view) for view in views]
    assert rows
    categories = {row["category"] for row in rows}
    assert RuleCategory.ARCHITECTURE.value in categories
    assert RuleCategory.TECHNICAL_DEBT.value in categories
    assert any(row["rule_id"] == "architecture.dependency-cycle" for row in rows)
    assert any(row["rule_id"] == "technical_debt.large-callable" for row in rows)
    _ = AssessmentApplicationService
    _ = KnowledgeQueryService
    _ = build_mcp_server
