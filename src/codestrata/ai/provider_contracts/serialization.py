"""Deterministic JSON serialization of diagnostic views (tests/reports only).

Sorted keys, no timestamps, no wall-clock data, no credentials, no prompts —
these functions serialize only the safe diagnostic views from
``diagnostics.py``, never a request's/result's raw prompt or response text.
"""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.provider_contracts.diagnostics import (
    diagnostic_view_of_request,
    diagnostic_view_of_result,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def serialize_request_for_diagnostics(request: AIProviderRequest) -> str:
    return canonical_json(diagnostic_view_of_request(request))


def serialize_result_for_diagnostics(result: AIProviderResult) -> str:
    return canonical_json(diagnostic_view_of_result(result))


__all__ = [
    "canonical_json",
    "serialize_request_for_diagnostics",
    "serialize_result_for_diagnostics",
]
