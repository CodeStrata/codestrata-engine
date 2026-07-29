"""Stable JSON serialization for AI recommendation contracts."""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.recommendations.models import AIRecommendationResult


def ai_recommendation_result_to_dict(
    result: AIRecommendationResult,
) -> dict[str, Any]:
    """Return a deterministic JSON-ready dictionary."""

    return result.model_dump(mode="json")


def ai_recommendation_result_to_json(
    result: AIRecommendationResult,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize an AIRecommendationResult to stable JSON text."""

    payload = ai_recommendation_result_to_dict(result)
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )


def ai_recommendation_result_from_json(
    payload: str | bytes | dict[str, Any],
) -> AIRecommendationResult:
    """Validate JSON (or a dict) against the AIRecommendationResult contract."""

    if isinstance(payload, dict):
        data = payload
    else:
        data = json.loads(payload)
    return AIRecommendationResult.model_validate(data)
