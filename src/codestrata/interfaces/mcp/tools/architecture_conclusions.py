"""MCP tools for architecture conclusions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.rules.errors import RuleApplicationError
from codestrata.interfaces.mcp.tools._common import run_bounded


def register_architecture_conclusion_tools(
    server: FastMCP,
    *,
    architecture_conclusion_service: object | None = None,
) -> None:
    @server.tool(name="list_architecture_conclusion_policies", structured_output=True)
    def list_architecture_conclusion_policies(
        category: str | None = None,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            service = _require_service(architecture_conclusion_service)
            return {"policies": list(service.list_policies(category=category))}

        return run_bounded("list_architecture_conclusion_policies", _run)

    @server.tool(name="inspect_architecture_conclusion_policy", structured_output=True)
    def inspect_architecture_conclusion_policy(policy_id: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            service = _require_service(architecture_conclusion_service)
            return dict(service.inspect_policy(policy_id))

        return run_bounded("inspect_architecture_conclusion_policy", _run)

    @server.tool(name="list_architecture_conclusions", structured_output=True)
    def list_architecture_conclusions(
        artifact_path: str,
        category: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_artifact(artifact_path)
            conclusions = list(payload.get("conclusions", []))
            if category:
                conclusions = [
                    item for item in conclusions if item.get("category") == category
                ]
            if status:
                conclusions = [
                    item for item in conclusions if item.get("status") == status
                ]
            return {
                "conclusions": [
                    {
                        "conclusion_id": item.get("conclusion_id"),
                        "category": item.get("category"),
                        "title": item.get("title"),
                        "status": item.get("status"),
                        "materiality": item.get("materiality"),
                        "confidence": item.get("confidence"),
                        "business_impact": item.get("business_impact"),
                        "source_finding_ids": item.get("source_finding_ids", []),
                        "affected_scope": item.get("affected_scope", []),
                    }
                    for item in conclusions
                ]
            }

        return run_bounded("list_architecture_conclusions", _run)

    @server.tool(name="inspect_architecture_conclusion", structured_output=True)
    def inspect_architecture_conclusion(
        artifact_path: str,
        conclusion_id: str,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_artifact(artifact_path)
            match = next(
                (
                    item
                    for item in payload.get("conclusions", [])
                    if item.get("conclusion_id") == conclusion_id
                ),
                None,
            )
            if match is None:
                raise RuleApplicationError(
                    "Architecture conclusion not found",
                    reason_code="conclusion_not_found",
                )
            # Omit raw source content; return structured conclusion fields only.
            return {
                "conclusion_id": match.get("conclusion_id"),
                "policy_id": match.get("policy_id"),
                "category": match.get("category"),
                "title": match.get("title"),
                "summary": match.get("summary"),
                "technical_interpretation": match.get("technical_interpretation"),
                "executive_interpretation": match.get("executive_interpretation"),
                "affected_scope": match.get("affected_scope", []),
                "source_finding_ids": match.get("source_finding_ids", []),
                "primary_finding_id": match.get("primary_finding_id"),
                "related_finding_ids": match.get("related_finding_ids", []),
                "severity_summary": match.get("severity_summary"),
                "confidence": match.get("confidence"),
                "coverage": match.get("coverage"),
                "materiality": match.get("materiality"),
                "business_impact": match.get("business_impact"),
                "modernization_relevance": match.get("modernization_relevance"),
                "consolidated_recommendation_ids": match.get(
                    "consolidated_recommendation_ids", []
                ),
                "limitations": match.get("limitations", []),
                "status": match.get("status"),
            }

        return run_bounded("inspect_architecture_conclusion", _run)

    @server.tool(name="explain_architecture_conclusion", structured_output=True)
    def explain_architecture_conclusion(
        artifact_path: str,
        conclusion_id: str,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            payload = _load_artifact(artifact_path)
            match = next(
                (
                    item
                    for item in payload.get("conclusions", [])
                    if item.get("conclusion_id") == conclusion_id
                ),
                None,
            )
            if match is None:
                raise RuleApplicationError(
                    "Architecture conclusion not found",
                    reason_code="conclusion_not_found",
                )
            source_ids = set(match.get("source_finding_ids", []))
            relationships = [
                item
                for item in payload.get("relationships", [])
                if item.get("source_finding_id") in source_ids
                or item.get("target_finding_id") in source_ids
            ]
            groups = [
                item
                for item in payload.get("recommendation_groups", [])
                if item.get("recommendation_group_id")
                in set(match.get("consolidated_recommendation_ids", []))
                or source_ids.intersection(item.get("source_finding_ids", []))
            ]
            return {
                "conclusion_id": conclusion_id,
                "source_finding_ids": match.get("source_finding_ids", []),
                "relationships": relationships,
                "recommendation_groups": [
                    {
                        "recommendation_group_id": item.get("recommendation_group_id"),
                        "title": item.get("title"),
                        "primary_action": item.get("primary_action"),
                        "source_recommendation_ids": item.get(
                            "source_recommendation_ids", []
                        ),
                        "modernization_wave": item.get("modernization_wave"),
                        "limitations": item.get("limitations", []),
                    }
                    for item in groups
                ],
                "coverage": match.get("coverage"),
                "limitations": match.get("limitations", []),
                "technical_interpretation": match.get("technical_interpretation"),
                "executive_interpretation": match.get("executive_interpretation"),
            }

        return run_bounded("explain_architecture_conclusion", _run)


def _load_artifact(artifact_path: str) -> dict[str, Any]:
    path = Path(artifact_path)
    if not path.is_file():
        raise RuleApplicationError(
            "Architecture conclusions artifact not found",
            reason_code="conclusion_artifact_missing",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuleApplicationError(
            "Architecture conclusions artifact unreadable",
            reason_code="conclusion_artifact_invalid",
        ) from error
    if not isinstance(payload, dict):
        raise RuleApplicationError(
            "Architecture conclusions artifact invalid",
            reason_code="conclusion_artifact_invalid",
        )
    return payload


def _require_service(service: object | None) -> Any:
    if service is None:
        from codestrata.application.architecture.conclusions.factory import (
            create_architecture_conclusion_service,
        )

        try:
            return create_architecture_conclusion_service()
        except Exception as error:  # noqa: BLE001
            raise RuleApplicationError(
                "Architecture conclusion service unavailable",
                reason_code="conclusion_service_missing",
            ) from error
    return service
