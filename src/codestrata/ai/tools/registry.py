"""Registry for provider-neutral CodeStrata tools."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from codestrata.ai.tools.base import (
    CodeStrataTool,
    CodeStrataToolError,
    CodeStrataToolExecutionError,
    CodeStrataToolInputError,
)
from codestrata.ai.tools.models import CodeStrataToolDefinition, CodeStrataToolResult


class CodeStrataToolRegistry:
    """Register, discover, and execute typed CodeStrata tools."""

    def __init__(self) -> None:
        self._tools: dict[str, CodeStrataTool[Any, Any]] = {}

    def register(self, tool: CodeStrataTool[Any, Any]) -> None:
        """Register a tool. Duplicate names are rejected case-insensitively."""

        key = tool.name.strip().lower()
        if not key:
            raise ValueError("Tool name must be a nonempty string")
        if key in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[key] = tool

    def register_many(self, tools: Iterable[CodeStrataTool[Any, Any]]) -> None:
        """Register multiple tools atomically for the provided iterable order."""

        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> CodeStrataTool[Any, Any]:
        """Retrieve a tool by name using case-insensitive lookup."""

        key = name.strip().lower()
        try:
            return self._tools[key]
        except KeyError as error:
            raise KeyError(f"Unknown tool: {name}") from error

    def has(self, name: str) -> bool:
        """Return whether a tool is registered."""

        return name.strip().lower() in self._tools

    def list_definitions(self) -> list[CodeStrataToolDefinition]:
        """Return tool definitions in stable name order."""

        tools = sorted(self._tools.values(), key=lambda tool: tool.name.lower())
        return [tool.definition() for tool in tools]

    def list_names(self) -> list[str]:
        """Return registered tool names in stable order."""

        return [item.name for item in self.list_definitions()]

    def execute(
        self,
        name: str,
        payload: BaseModel | Mapping[str, object] | None = None,
    ) -> CodeStrataToolResult:
        """Execute a tool and always return an CodeStrataToolResult."""

        normalized_name = name.strip() if name else ""
        try:
            tool = self.get(normalized_name)
        except KeyError:
            return CodeStrataToolResult(
                tool_name=normalized_name or name,
                success=False,
                data=None,
                error=f"Unknown tool: {name}",
            )

        try:
            output = tool.execute(dict(payload) if isinstance(payload, Mapping) else payload)
            return CodeStrataToolResult(
                tool_name=tool.name,
                success=True,
                data=output.model_dump(mode="json"),
                error=None,
            )
        except CodeStrataToolInputError as error:
            return CodeStrataToolResult(
                tool_name=tool.name,
                success=False,
                data=None,
                error=str(error),
            )
        except CodeStrataToolExecutionError as error:
            return CodeStrataToolResult(
                tool_name=tool.name,
                success=False,
                data=None,
                error=str(error),
            )
        except CodeStrataToolError as error:
            return CodeStrataToolResult(
                tool_name=tool.name,
                success=False,
                data=None,
                error=str(error),
            )
        except Exception:  # noqa: BLE001 - hard boundary
            return CodeStrataToolResult(
                tool_name=tool.name,
                success=False,
                data=None,
                error=f"Tool '{tool.name}' failed during execution.",
            )
