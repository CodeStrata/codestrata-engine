"""CodeStrata FastMCP adapter over application services.

This package is a thin transport layer. Business logic remains in
``AssessmentApplicationService`` and ``KnowledgeQueryService``.

Importing this package does not require the optional ``mcp`` extra until
``create_mcp_server`` / ``build_mcp_server`` are called.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CODESSTRATA_ARTIFACT_MCP_NAME",
    "CODESSTRATA_EXPLANATION_MCP_NAME",
    "CODESSTRATA_MCP_NAME",
    "build_artifact_mcp_server",
    "build_local_explanation_mcp_server",
    "build_mcp_server",
    "create_artifact_mcp_server",
    "create_local_explanation_mcp_server",
    "create_mcp_server",
]


def __getattr__(name: str) -> Any:
    if name == "CODESSTRATA_MCP_NAME":
        from codestrata.interfaces.mcp.server import CODESSTRATA_MCP_NAME

        return CODESSTRATA_MCP_NAME
    if name == "CODESSTRATA_ARTIFACT_MCP_NAME":
        from codestrata.interfaces.mcp.server import CODESSTRATA_ARTIFACT_MCP_NAME

        return CODESSTRATA_ARTIFACT_MCP_NAME
    if name == "CODESSTRATA_EXPLANATION_MCP_NAME":
        from codestrata.interfaces.mcp.server import CODESSTRATA_EXPLANATION_MCP_NAME

        return CODESSTRATA_EXPLANATION_MCP_NAME
    if name == "build_mcp_server":
        from codestrata.interfaces.mcp.server import build_mcp_server

        return build_mcp_server
    if name == "build_artifact_mcp_server":
        from codestrata.interfaces.mcp.server import build_artifact_mcp_server

        return build_artifact_mcp_server
    if name == "build_local_explanation_mcp_server":
        from codestrata.interfaces.mcp.server import build_local_explanation_mcp_server

        return build_local_explanation_mcp_server
    if name == "create_mcp_server":
        from codestrata.interfaces.mcp.factory import create_mcp_server

        return create_mcp_server
    if name == "create_artifact_mcp_server":
        from codestrata.interfaces.mcp.factory import create_artifact_mcp_server

        return create_artifact_mcp_server
    if name == "create_local_explanation_mcp_server":
        from codestrata.interfaces.mcp.factory import create_local_explanation_mcp_server

        return create_local_explanation_mcp_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
