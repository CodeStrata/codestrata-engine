"""Stable JSON serialization for LLM analysis contracts."""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.contracts.models import LLMAnalysisContext


def llm_context_to_dict(context: LLMAnalysisContext) -> dict[str, Any]:
    """Return a deterministic JSON-ready dictionary."""

    return context.model_dump(mode="json")


def llm_context_to_json(context: LLMAnalysisContext, *, indent: int | None = 2) -> str:
    """Serialize an LLMAnalysisContext to stable JSON text."""

    payload = llm_context_to_dict(context)
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )


def llm_context_from_json(payload: str | bytes | dict[str, Any]) -> LLMAnalysisContext:
    """Validate JSON (or a dict) against the LLMAnalysisContext contract."""

    if isinstance(payload, dict):
        data = payload
    else:
        data = json.loads(payload)
    return LLMAnalysisContext.model_validate(data)
