"""CodeStrata FastMCP adapter over application services.

This package is a thin transport layer. Business logic remains in
``AssessmentApplicationService`` and ``KnowledgeQueryService``.

Importing this package does not require the optional ``mcp`` extra until
``create_mcp_server`` / ``build_mcp_server`` are called.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CODESSTRATA_MCP_NAME",
    "build_mcp_server",
    "create_mcp_server",
]


def __getattr__(name: str) -> Any:
    if name == "CODESSTRATA_MCP_NAME":
        from codestrata.interfaces.mcp.server import CODESSTRATA_MCP_NAME

        return CODESSTRATA_MCP_NAME
    if name == "build_mcp_server":
        from codestrata.interfaces.mcp.server import build_mcp_server

        return build_mcp_server
    if name == "create_mcp_server":
        from codestrata.interfaces.mcp.factory import create_mcp_server

        return create_mcp_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
