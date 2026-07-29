"""MCP tools for language evidence providers."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.rules.errors import RuleApplicationError
from codestrata.interfaces.mcp.tools._common import run_bounded


def register_evidence_tools(
    server: FastMCP,
    *,
    language_evidence_service: object | None = None,
) -> None:
    @server.tool(name="list_evidence_providers", structured_output=True)
    def list_evidence_providers(
        language: str | None = None,
        capability: str | None = None,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            service = _require_service(language_evidence_service)
            providers = service.list_providers(language=language, capability=capability)
            return {"providers": list(providers)}

        return run_bounded("list_evidence_providers", _run)

    @server.tool(name="inspect_evidence_provider", structured_output=True)
    def inspect_evidence_provider(provider_id: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            service = _require_service(language_evidence_service)
            return dict(service.inspect_provider(provider_id))

        return run_bounded("inspect_evidence_provider", _run)

    @server.tool(name="list_evidence_capabilities", structured_output=True)
    def list_evidence_capabilities() -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            from codestrata.domain.evidence.language.capability_catalog import (
                CAP_ARCHITECTURE_LAYERS,
                CAP_ARCHITECTURE_UNITS,
                CAP_DEPENDENCIES_IMPORTS,
                CAP_DEPENDENCIES_TYPE_ONLY,
                CAP_FRAMEWORK_USAGE,
                CAP_SOURCE_FILES,
            )

            return {
                "capabilities": [
                    CAP_SOURCE_FILES,
                    CAP_DEPENDENCIES_IMPORTS,
                    CAP_DEPENDENCIES_TYPE_ONLY,
                    CAP_ARCHITECTURE_UNITS,
                    CAP_ARCHITECTURE_LAYERS,
                    CAP_FRAMEWORK_USAGE,
                ]
            }

        return run_bounded("list_evidence_capabilities", _run)

    @server.tool(name="explain_evidence_provider", structured_output=True)
    def explain_evidence_provider(
        provider_id: str,
        relative_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            service = _require_service(language_evidence_service)
            return dict(
                service.explain_provider(
                    provider_id,
                    relative_paths=relative_paths or [],
                    file_texts={},
                )
            )

        return run_bounded("explain_evidence_provider", _run)


def _require_service(service: object | None) -> Any:
    if service is None:
        from codestrata.application.evidence.language.factory import (
            create_language_evidence_service,
        )

        try:
            return create_language_evidence_service()
        except Exception as error:  # noqa: BLE001
            raise RuleApplicationError(
                "Language evidence service unavailable",
                reason_code="evidence_service_missing",
            ) from error
    return service
