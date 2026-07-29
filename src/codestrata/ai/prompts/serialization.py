"""Stable JSON serialization for prompt packages."""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.prompts.models import PromptRequest


def prompt_request_to_dict(request: PromptRequest) -> dict[str, Any]:
    """Return a deterministic JSON-ready dictionary."""

    return request.model_dump(mode="json")


def prompt_request_to_json(request: PromptRequest, *, indent: int | None = 2) -> str:
    """Serialize a PromptRequest to stable JSON text."""

    payload = prompt_request_to_dict(request)
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )


def prompt_request_from_json(payload: str | bytes | dict[str, Any]) -> PromptRequest:
    """Validate JSON (or a dict) against the PromptRequest contract."""

    if isinstance(payload, dict):
        data = payload
    else:
        data = json.loads(payload)
    return PromptRequest.model_validate(data)
