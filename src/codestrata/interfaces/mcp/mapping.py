"""Central DTO → MCP-safe JSON mapping."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from codestrata.interfaces.mcp.models import BoundedListResponse
from codestrata.interfaces.mcp.security import redact_mapping


def to_mcp_payload(value: Any) -> Any:
    """Convert application DTOs into JSON-compatible MCP payloads."""

    return redact_mapping(_convert(value))


def to_mcp_dict(value: Any) -> dict[str, Any]:
    """Convert a value to an MCP JSON object payload."""

    payload = to_mcp_payload(value)
    if not isinstance(payload, dict):
        raise TypeError("Expected a JSON object payload")
    return payload


def bounded_list(
    items: Sequence[Any],
    *,
    limit: int,
    truncated: bool | None = None,
) -> dict[str, Any]:
    """Wrap a sequence with truncation metadata."""

    materialised = list(items)
    is_truncated = truncated if truncated is not None else False
    payload = BoundedListResponse(
        items=[to_mcp_payload(item) for item in materialised],
        returned_count=len(materialised),
        truncated=is_truncated,
        limit=limit,
    )
    return to_mcp_dict(payload)


def _convert(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return _convert(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _convert(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_convert(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
