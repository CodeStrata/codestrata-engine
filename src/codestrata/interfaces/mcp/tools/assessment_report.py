"""MCP tools for canonical assessment report document traceability (Epic 2 Slice 2.8).

The Engine assessment JSON report remains the authoritative interchange artifact.
These tools read the document as-is — they do not regenerate relationships or invent IDs.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.interfaces.mcp.tools._common import run_bounded
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.traceability.preservation import (
    CanonicalReportLoadError,
    classify_traceability_state,
    counts_from_assessment,
    extract_assessment,
    load_report_document,
    lookup_entity,
    preserve_assessment_collections,
    schema_version_of,
    validate_canonical_assessment,
)


def register_assessment_report_tools(server: FastMCP) -> None:
    @server.tool(name="inspect_assessment_report", structured_output=True)
    def inspect_assessment_report(report_path: str) -> dict[str, Any]:
        """Return canonical assessment collections from an assessment report path without field loss."""

        def _run() -> dict[str, Any]:
            document = load_report_document(report_path)
            assessment = extract_assessment(document)
            state = validate_canonical_assessment(assessment)
            preserved = preserve_assessment_collections(assessment)
            counts = counts_from_assessment(preserved)
            return {
                "schema_version": schema_version_of(document),
                "expected_schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
                "traceability_status": state,
                "counts": counts,
                "assessment": {
                    "evidence": preserved.get("evidence", []),
                    "findings": preserved.get("findings", []),
                    "deterministic_recommendations": preserved.get(
                        "deterministic_recommendations", []
                    ),
                    "priority_actions": preserved.get("priority_actions", []),
                    "roadmap": preserved.get("roadmap"),
                    "summary": preserved.get("summary"),
                },
                "canonical_interchange": "assessment_report_json",
                "notes": (
                    "Collections are projections of the canonical report document. "
                    "Relationships are not regenerated."
                    if state == "complete"
                    else (
                        "Report is legacy or incomplete for Epic 2 traceability; "
                        "missing fields are not fabricated."
                    )
                ),
            }

        try:
            return run_bounded("inspect_assessment_report", _run)
        except CanonicalReportLoadError as error:
            return {
                "error": "report_load_failed",
                "message": str(error),
                "traceability_status": "invalid",
            }

    @server.tool(name="get_assessment_report_entity", structured_output=True)
    def get_assessment_report_entity(
        report_path: str,
        entity_kind: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """Exact-ID lookup into the canonical report assessment collections."""

        def _run() -> dict[str, Any]:
            document = load_report_document(report_path)
            assessment = extract_assessment(document)
            validate_canonical_assessment(assessment)
            entity = lookup_entity(assessment, kind=entity_kind, entity_id=entity_id)
            if entity is None:
                return {
                    "found": False,
                    "entity_kind": entity_kind,
                    "entity_id": entity_id,
                    "error": "not_found",
                    "message": (
                        f"No {entity_kind} with id={entity_id!r} in canonical report"
                    ),
                }
            return {
                "found": True,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
                "entity": entity,
                "traceability_status": classify_traceability_state(assessment),
                "schema_version": schema_version_of(document),
            }

        try:
            return run_bounded("get_assessment_report_entity", _run)
        except CanonicalReportLoadError as error:
            return {
                "found": False,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
                "error": "report_load_failed",
                "message": str(error),
            }

    @server.tool(name="inspect_assessment_report_traceability", structured_output=True)
    def inspect_assessment_report_traceability(report_path: str) -> dict[str, Any]:
        """Summarize Epic 2 chain presence and validation status for an assessment report path."""

        def _run() -> dict[str, Any]:
            document = load_report_document(report_path)
            assessment = extract_assessment(document)
            state = validate_canonical_assessment(assessment)
            counts = counts_from_assessment(assessment)
            return {
                "schema_version": schema_version_of(document),
                "traceability_status": state,
                "counts": counts,
                "has_evidence": isinstance(assessment.get("evidence"), list),
                "has_priority_actions": isinstance(assessment.get("priority_actions"), list),
                "has_roadmap": isinstance(assessment.get("roadmap"), dict),
                "chain": [
                    "evidence",
                    "findings",
                    "deterministic_recommendations",
                    "priority_actions",
                    "roadmap.initiatives",
                ],
                "assessment_roadmap_note": (
                    "assessment.roadmap is repository-scoped and Priority Action backed. "
                    "It is not the Platform Strategic Roadmap."
                ),
            }

        try:
            return run_bounded("inspect_assessment_report_traceability", _run)
        except CanonicalReportLoadError as error:
            return {
                "error": "report_load_failed",
                "message": str(error),
                "traceability_status": "invalid",
            }
