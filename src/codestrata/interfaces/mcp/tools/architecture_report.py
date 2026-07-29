"""MCP tools for architecture report presentation (Phase 4.2.5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.rules.errors import RuleApplicationError
from codestrata.interfaces.mcp.tools._common import run_bounded
from codestrata.reporting.architecture.models import (
    ARCHITECTURE_REPORT_SECTION_ID,
    ARCHITECTURE_REPORT_SECTION_VERSION,
)


def register_architecture_report_tools(server: FastMCP) -> None:
    @server.tool(name="list_report_sections", structured_output=True)
    def list_report_sections(report_path: str | None = None) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            sections: list[dict[str, Any]] = [
                {
                    "section_id": ARCHITECTURE_REPORT_SECTION_ID,
                    "section_version": ARCHITECTURE_REPORT_SECTION_VERSION,
                    "title": "Architecture Assessment",
                    "description": (
                        "Audience-oriented presentation of architecture assessment "
                        "(`[report.sections.architecture] enabled = false` by default)."
                    ),
                    "layer": "report",
                }
            ]
            if report_path:
                section = _load_architecture_section(report_path)
                sections[0]["status"] = section.get("status")
                sections[0]["present"] = True
            else:
                sections[0]["present"] = None
            return {"sections": sections}

        return run_bounded("list_report_sections", _run)

    @server.tool(name="inspect_architecture_report_section", structured_output=True)
    def inspect_architecture_report_section(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {
                "section_id": section.get("section_id"),
                "section_version": section.get("section_version"),
                "status": section.get("status"),
                "status_label": section.get("status_label"),
                "status_summary": section.get("status_summary"),
                "executive_summary": section.get("executive_summary"),
                "architecture_pack_id": section.get("architecture_pack_id"),
                "architecture_pack_version": section.get("architecture_pack_version"),
                "generated_from_assessment_section_version": section.get(
                    "generated_from_assessment_section_version"
                ),
                "key_metrics": section.get("key_metrics", []),
                "finding_count": len(section.get("findings") or []),
                "conclusion_count": len(section.get("conclusions") or []),
                "recommendation_group_count": len(
                    section.get("recommendation_groups") or []
                ),
                "limitation_count": len(section.get("limitations") or []),
                "enterprise_context_used": section.get("enterprise_context_used"),
            }

        return run_bounded("inspect_architecture_report_section", _run)

    @server.tool(name="inspect_architecture_report_executive_summary", structured_output=True)
    def inspect_architecture_report_executive_summary(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {
                "executive_summary": section.get("executive_summary"),
                "status": section.get("status"),
                "status_label": section.get("status_label"),
            }

        return run_bounded("inspect_architecture_report_executive_summary", _run)

    @server.tool(name="inspect_architecture_report_conclusions", structured_output=True)
    def inspect_architecture_report_conclusions(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {
                "conclusions": [
                    {
                        "conclusion_id": item.get("conclusion_id"),
                        "title": item.get("title"),
                        "category": item.get("category"),
                        "summary": item.get("summary"),
                        "materiality": item.get("materiality"),
                        "confidence": item.get("confidence"),
                        "business_impact": item.get("business_impact"),
                        "modernization_relevance": item.get("modernization_relevance"),
                        "primary_finding_id": item.get("primary_finding_id"),
                        "supporting_finding_count": item.get("supporting_finding_count"),
                    }
                    for item in section.get("conclusions") or []
                ]
            }

        return run_bounded("inspect_architecture_report_conclusions", _run)

    @server.tool(
        name="inspect_architecture_report_recommendations",
        structured_output=True,
    )
    def inspect_architecture_report_recommendations(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {
                "recommendation_groups": [
                    {
                        "recommendation_group_id": item.get("recommendation_group_id"),
                        "title": item.get("title"),
                        "objective": item.get("objective"),
                        "rationale": item.get("rationale"),
                        "source_conclusion_ids": item.get("source_conclusion_ids", []),
                        "source_finding_ids": item.get("source_finding_ids", []),
                        "recommended_actions": item.get("recommended_actions", []),
                        "validation_steps": item.get("validation_steps", []),
                        "modernization_wave": item.get("modernization_wave"),
                        "limitations": item.get("limitations", []),
                    }
                    for item in section.get("recommendation_groups") or []
                ]
            }

        return run_bounded("inspect_architecture_report_recommendations", _run)

    @server.tool(name="inspect_architecture_report_findings", structured_output=True)
    def inspect_architecture_report_findings(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {
                "findings": [
                    {
                        "finding_id": item.get("finding_id"),
                        "title": item.get("title"),
                        "rule_id": item.get("rule_id"),
                        "severity": item.get("severity"),
                        "confidence": item.get("confidence"),
                        "affected_scope": item.get("affected_scope", []),
                        "linked_to_conclusion": item.get("linked_to_conclusion"),
                        "conclusion_ids": item.get("conclusion_ids", []),
                        "evidence_count": item.get("evidence_count"),
                    }
                    for item in section.get("findings") or []
                ]
            }

        return run_bounded("inspect_architecture_report_findings", _run)

    @server.tool(name="inspect_architecture_report_coverage", structured_output=True)
    def inspect_architecture_report_coverage(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {"coverage_summary": section.get("coverage_summary", [])}

        return run_bounded("inspect_architecture_report_coverage", _run)

    @server.tool(name="inspect_architecture_report_limitations", structured_output=True)
    def inspect_architecture_report_limitations(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {"limitations": section.get("limitations", [])}

        return run_bounded("inspect_architecture_report_limitations", _run)

    @server.tool(name="inspect_architecture_report_traceability", structured_output=True)
    def inspect_architecture_report_traceability(report_path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            section = _load_architecture_section(report_path)
            return {"traceability_summary": section.get("traceability_summary", {})}

        return run_bounded("inspect_architecture_report_traceability", _run)


def _load_architecture_section(report_path: str) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        raise RuleApplicationError(
            "Report artifact not found",
            reason_code="architecture_report_artifact_missing",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuleApplicationError(
            "Report artifact unreadable",
            reason_code="architecture_report_artifact_invalid",
        ) from error
    if not isinstance(payload, dict):
        raise RuleApplicationError(
            "Report artifact invalid",
            reason_code="architecture_report_artifact_invalid",
        )
    assessment = payload.get("assessment")
    if not isinstance(assessment, dict):
        raise RuleApplicationError(
            "Report artifact missing assessment object",
            reason_code="architecture_report_artifact_invalid",
        )
    architecture = assessment.get("architecture")
    if architecture is None:
        raise RuleApplicationError(
            "Architecture report section absent",
            reason_code="architecture_report_section_absent",
        )
    if not isinstance(architecture, dict):
        raise RuleApplicationError(
            "Architecture report section invalid",
            reason_code="architecture_report_artifact_invalid",
        )
    return architecture
