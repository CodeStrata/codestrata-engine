"""Shared helpers for MCP tool modules."""

from __future__ import annotations

from collections.abc import Callable

from codestrata.application.knowledge.models import AssessmentRunStatus
from codestrata.application.knowledge.queries import (
    DependencyDirection,
    KnowledgeQueryService,
    QueryLimitError,
)
from codestrata.interfaces.mcp.errors import call_tool
from codestrata.interfaces.mcp.security import require_nonblank

__all__ = [
    "COMPONENTS_DEFAULT",
    "COMPONENTS_MAX",
    "DEPENDENCIES_DEFAULT",
    "DEPENDENCIES_MAX",
    "FINDINGS_DEFAULT",
    "FINDINGS_MAX",
    "RECOMMENDATIONS_DEFAULT",
    "RECOMMENDATIONS_MAX",
    "clamp_tool_limit",
    "parse_direction",
    "parse_run_status",
    "require_nonblank",
    "resolve_repository_id",
    "run_bounded",
]

FINDINGS_DEFAULT = 100
FINDINGS_MAX = 500
RECOMMENDATIONS_DEFAULT = 100
RECOMMENDATIONS_MAX = 500
COMPONENTS_DEFAULT = 100
COMPONENTS_MAX = 1000
DEPENDENCIES_DEFAULT = 200
DEPENDENCIES_MAX = 2000


def resolve_repository_id(queries: KnowledgeQueryService, identifier: str) -> str:
    summary = queries.resolve_repository(
        require_nonblank(identifier, label="repository_identifier")
    )
    return summary.repository_id


def parse_run_status(value: str | None) -> AssessmentRunStatus | None:
    if value is None:
        return None
    compact = require_nonblank(value, label="status").lower()
    try:
        return AssessmentRunStatus(compact)
    except ValueError as error:
        raise ValueError(
            "status must be one of: running, completed, failed, aborted"
        ) from error


def parse_direction(value: str) -> DependencyDirection:
    compact = require_nonblank(value, label="direction").lower()
    try:
        return DependencyDirection(compact)
    except ValueError as error:
        raise ValueError("direction must be one of: incoming, outgoing, both") from error


def clamp_tool_limit(
    value: int,
    *,
    default: int,
    maximum: int,
    label: str,
) -> int:
    del default  # callers pass the requested value already
    if value < 1:
        raise QueryLimitError(f"{label} limit must be >= 1")
    if value > maximum:
        raise QueryLimitError(f"{label} limit cannot exceed {maximum}")
    return value


def run_bounded[T](tool_name: str, operation: Callable[[], T]) -> T:
    return call_tool(tool_name, operation)  # type: ignore[return-value]
