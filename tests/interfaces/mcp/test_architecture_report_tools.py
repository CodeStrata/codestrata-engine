"""MCP tests for architecture report tools (Phase 4.2.5)."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from codestrata.interfaces.mcp.tools.architecture_report import (
    register_architecture_report_tools,
)


def test_architecture_report_tools_inspect(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "assessment": {
                    "architecture": {
                        "section_id": "report.architecture",
                        "section_version": "1.0.0",
                        "status": "succeeded",
                        "status_label": "Succeeded",
                        "status_summary": "ok",
                        "executive_summary": "Exec.",
                        "architecture_pack_id": "architecture.core",
                        "architecture_pack_version": "1.0.0",
                        "findings": [{"finding_id": "f1", "title": "Cycle"}],
                        "conclusions": [{"conclusion_id": "c1", "title": "Boundary"}],
                        "recommendation_groups": [
                            {"recommendation_group_id": "r1", "title": "Fix"}
                        ],
                        "coverage_summary": [],
                        "limitations": [],
                        "traceability_summary": {"edge_count": 0},
                        "key_metrics": [],
                        "enterprise_context_used": False,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    server = FastMCP("test")
    register_architecture_report_tools(server)
    tools = getattr(server, "_tool_manager", None)
    assert tools is not None
    tool = tools.get_tool("inspect_architecture_report_section")
    assert tool is not None
    payload = tool.fn(report_path=str(report))
    assert payload["section_id"] == "report.architecture"
    assert payload["finding_count"] == 1
    assert payload["conclusion_count"] == 1
    assert "/Users/" not in json.dumps(payload)
