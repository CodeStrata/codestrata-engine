"""MCP tools package.

Importing this package does not require the optional ``mcp`` extra.
``register_all_tools`` is resolved lazily so shared helpers such as
``repository_common`` remain usable from the CLI without FastMCP installed.
"""

from __future__ import annotations

from typing import Any

__all__ = ["register_all_tools"]


def __getattr__(name: str) -> Any:
    if name == "register_all_tools":
        from codestrata.interfaces.mcp.tools.register import register_all_tools

        return register_all_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
