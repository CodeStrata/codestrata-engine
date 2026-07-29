"""MCP tools for architecture assessment section inspection (Phase 4.2.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.rules.errors import RuleApplicationError
from codestrata.domain.architecture.assessment.identifiers import SECTION_ID
from codestrata.interfaces.mcp.tools._common import run_bounded


def register_architecture_assessment_tools(server: FastMCP) -> None:
    @server.tool(name="list_assessment_sections", structured_output=True)
    def list_assessment_sections(artifact_path: str | None = None) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            sections: list[dict[str, Any]] = [
                {
                    "section_id": SECTION_ID,
                    "title": "Architecture",
                    "description": (
                        "Optional architecture assessment section "
                        "(`[assessment.sections.architecture] enabled = false` by default)."
                    ),
                }
            ]
            if artifact_path:
                payload = _load_section(artifact_path)
                sections[0]["status"] = payload.get("status")
                sections[0]["section_version"] = payload.get("section_version")
            return {"sections": sections}

        return run_bounded("list_assessment_sections", _run)

    @server.tool(name="inspect_architecture_assessment_section", structured_output=True)
    def inspect_architecture_assessment_section(artifact_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            return {
                "section_id": payload.get("section_id"),
                "section_version": payload.get("section_version"),
                "status": payload.get("status"),
                "architecture_pack_id": payload.get("architecture_pack_id"),
                "architecture_pack_version": payload.get("architecture_pack_version"),
                "graph_fingerprint": payload.get("graph_fingerprint"),
                "evidence_pipeline": payload.get("evidence_pipeline"),
                "execution_summary": payload.get("execution_summary"),
                "finding_ids": payload.get("finding_ids", []),
                "conclusion_ids": payload.get("conclusion_ids", []),
                "recommendation_group_ids": payload.get("recommendation_group_ids", []),
                "strength_count": len(payload.get("strengths", [])),
                "limitation_count": len(payload.get("limitations", [])),
                "business_impact": payload.get("business_impact"),
                "enterprise_context_used": payload.get("enterprise_context_used"),
            }

        return run_bounded("inspect_architecture_assessment_section", _run)

    @server.tool(name="inspect_architecture_assessment_findings", structured_output=True)
    def inspect_architecture_assessment_findings(artifact_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            return {"findings": payload.get("finding_summaries", [])}

        return run_bounded("inspect_architecture_assessment_findings", _run)

    @server.tool(name="inspect_architecture_assessment_conclusions", structured_output=True)
    def inspect_architecture_assessment_conclusions(artifact_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            return {
                "conclusion_ids": payload.get("conclusion_ids", []),
                "conclusions": [
                    {
                        "conclusion_id": item.get("conclusion_id"),
                        "category": item.get("category"),
                        "title": item.get("title"),
                        "status": item.get("status"),
                        "source_finding_ids": item.get("source_finding_ids", []),
                        "materiality": item.get("materiality"),
                        "business_impact": item.get("business_impact"),
                        "modernization_relevance": item.get("modernization_relevance"),
                    }
                    for item in payload.get("conclusions", [])
                ],
            }

        return run_bounded("inspect_architecture_assessment_conclusions", _run)

    @server.tool(
        name="inspect_architecture_assessment_recommendations",
        structured_output=True,
    )
    def inspect_architecture_assessment_recommendations(
        artifact_path: str,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            return {
                "recommendation_groups": [
                    {
                        "recommendation_group_id": item.get("recommendation_group_id"),
                        "title": item.get("title"),
                        "primary_action": item.get("primary_action"),
                        "source_finding_ids": item.get("source_finding_ids", []),
                        "source_recommendation_ids": item.get(
                            "source_recommendation_ids", []
                        ),
                        "modernization_wave": item.get("modernization_wave"),
                        "limitations": item.get("limitations", []),
                    }
                    for item in payload.get("recommendation_groups", [])
                ]
            }

        return run_bounded("inspect_architecture_assessment_recommendations", _run)

    @server.tool(name="inspect_architecture_assessment_coverage", structured_output=True)
    def inspect_architecture_assessment_coverage(artifact_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            return {"coverage": payload.get("coverage")}

        return run_bounded("inspect_architecture_assessment_coverage", _run)

    @server.tool(name="inspect_architecture_assessment_limitations", structured_output=True)
    def inspect_architecture_assessment_limitations(artifact_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            return {"limitations": payload.get("limitations", [])}

        return run_bounded("inspect_architecture_assessment_limitations", _run)

    @server.tool(name="inspect_architecture_assessment_traceability", structured_output=True)
    def inspect_architecture_assessment_traceability(artifact_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_section(artifact_path)
            trace = payload.get("traceability") or {}
            edges = trace.get("edges", [])
            return {
                "edge_count": len(edges),
                "edges": edges[:200],
                "truncated": len(edges) > 200,
            }

        return run_bounded("inspect_architecture_assessment_traceability", _run)


def _load_section(artifact_path: str) -> dict[str, Any]:
    path = Path(artifact_path)
    if not path.is_file():
        raise RuleApplicationError(
            "Architecture assessment artifact not found",
            reason_code="architecture_assessment_artifact_missing",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuleApplicationError(
            "Architecture assessment artifact unreadable",
            reason_code="architecture_assessment_artifact_invalid",
        ) from error
    if not isinstance(payload, dict):
        raise RuleApplicationError(
            "Architecture assessment artifact invalid",
            reason_code="architecture_assessment_artifact_invalid",
        )
    return payload
