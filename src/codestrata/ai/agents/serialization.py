"""Stable JSON serialization for agent results and traces."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from codestrata.ai.agents.models import AgentExecutionTrace, ModernizationAssessmentResult


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        # Stable ISO-8601 UTC with explicit offset.
        if value.tzinfo is None:
            raise TypeError("Naive datetime is not supported in agent serialization")
        return value.isoformat().replace("+00:00", "Z")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def agent_execution_trace_to_dict(trace: AgentExecutionTrace) -> dict[str, Any]:
    """Return a deterministic JSON-ready dictionary for a trace."""

    return trace.model_dump(mode="json")


def agent_execution_trace_to_json(
    trace: AgentExecutionTrace,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize an AgentExecutionTrace to stable JSON text."""

    payload = agent_execution_trace_to_dict(trace)
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        default=_json_default,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )


def agent_execution_trace_from_json(
    payload: str | bytes | dict[str, Any],
) -> AgentExecutionTrace:
    """Validate JSON (or a dict) against the AgentExecutionTrace contract."""

    if isinstance(payload, dict):
        data = payload
    else:
        data = json.loads(payload)
    return AgentExecutionTrace.model_validate(data)


def modernization_assessment_result_to_dict(
    result: ModernizationAssessmentResult,
) -> dict[str, Any]:
    """Return a deterministic JSON-ready dictionary for an assessment result."""

    return result.model_dump(mode="json")


def modernization_assessment_result_to_json(
    result: ModernizationAssessmentResult,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ModernizationAssessmentResult to stable JSON text."""

    payload = modernization_assessment_result_to_dict(result)
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        default=_json_default,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )


def modernization_assessment_result_from_json(
    payload: str | bytes | dict[str, Any],
) -> ModernizationAssessmentResult:
    """Validate JSON (or a dict) against ModernizationAssessmentResult."""

    if isinstance(payload, dict):
        data = payload
    else:
        data = json.loads(payload)
    return ModernizationAssessmentResult.model_validate(data)
