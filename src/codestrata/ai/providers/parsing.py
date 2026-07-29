"""Strict JSON parsing for AI recommendation model responses."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from codestrata.ai.contracts.models import LLMAnalysisContext
from codestrata.ai.providers.exceptions import (
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.recommendations.models import AIRecommendationResult
from codestrata.ai.recommendations.validation import (
    AIRecommendationValidationError,
    DeterministicRecommendationNormalizationRemoval,
    validate_recommendation_result_outcome,
)
from codestrata.security.redaction import redact_secrets

logger = logging.getLogger(__name__)

_FENCED_JSON_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*\r?\n(?P<body>.*?)\r?\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)
_MAX_ERROR_EXCERPT = 240
_AWS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
_AWS_SECRET_PATTERN = re.compile(
    r"(?i)(aws_secret_access_key\s*[=:]\s*)(\S+)",
)


@dataclass(frozen=True)
class RecommendationParseOutcome:
    """Accepted recommendation plus pre-acceptance parsed JSON and normalization."""

    result: AIRecommendationResult
    parsed_model_response: dict[str, Any]
    normalization_removals: tuple[DeterministicRecommendationNormalizationRemoval, ...] = ()


def sanitize_provider_text(text: str | None, *, max_length: int = _MAX_ERROR_EXCERPT) -> str:
    """Redact secrets and truncate text for safe error messages."""

    sanitized = redact_secrets(text)
    sanitized = _AWS_KEY_PATTERN.sub("[REDACTED]", sanitized)
    sanitized = _AWS_SECRET_PATTERN.sub(r"\1[REDACTED]", sanitized)
    compact = " ".join(sanitized.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3] + "..."


def parse_recommendation_response(
    raw_text: str,
    analysis_context: LLMAnalysisContext,
) -> RecommendationParseOutcome:
    """Parse and validate a model response into an accepted recommendation result.

    Accepts a single JSON object, optionally wrapped as one fenced code block.
    Rejects surrounding prose, multiple JSON values, and repairs nothing.

    Model-supplied ``evidence_coverage`` numbers are treated as untrusted and are
    replaced by CodeStrata after structural and referential validation. The original
    parsed JSON object is retained separately for evaluation artifacts.
    """

    try:
        payload = _extract_json_object_text(raw_text)
    except AIResponseParsingError as error:
        raise AIResponseParsingError(
            str(error),
            raw_response_text=raw_text,
            validation_details=error.validation_details,
        ) from error

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise AIResponseParsingError(
            "Model response is not valid JSON: " + sanitize_provider_text(str(error)),
            raw_response_text=raw_text,
            validation_details=str(error),
        ) from error

    if not isinstance(data, dict):
        raise AIResponseParsingError(
            f"Model response must be a single JSON object, got {type(data).__name__}",
            raw_response_text=raw_text,
        )

    model_reported_coverage = data.get("evidence_coverage")
    if isinstance(model_reported_coverage, dict):
        logger.debug("model_reported_coverage=%s", model_reported_coverage)

    try:
        result = AIRecommendationResult.model_validate(data)
    except ValidationError as error:
        raise AIResponseValidationError(
            "Model response failed AIRecommendationResult validation: "
            + sanitize_provider_text(str(error)),
            raw_response_text=raw_text,
            parsed_payload=data,
            validation_details=str(error),
        ) from error

    try:
        outcome = validate_recommendation_result_outcome(result, analysis_context)
    except AIRecommendationValidationError as error:
        raise AIResponseValidationError(
            "Model response failed context-aware recommendation validation: "
            + sanitize_provider_text(str(error)),
            raw_response_text=raw_text,
            parsed_payload=data,
            validation_details=str(error),
        ) from error

    return RecommendationParseOutcome(
        result=outcome.result,
        parsed_model_response=data,
        normalization_removals=outcome.normalization_removals,
    )


def _extract_json_object_text(raw_text: str) -> str:
    if raw_text is None:
        raise AIResponseParsingError("Model response is empty")

    text = raw_text.strip()
    if not text:
        raise AIResponseParsingError("Model response is empty")

    fenced = _FENCED_JSON_PATTERN.fullmatch(text)
    if fenced is not None:
        text = fenced.group("body").strip()
        if not text:
            raise AIResponseParsingError("Fenced model response is empty")
    elif "```" in text:
        raise AIResponseParsingError(
            "Model response contains a code fence but is not exactly one fenced JSON block"
        )

    return _require_single_json_object(text)


def _require_single_json_object(text: str) -> str:
    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(text)
    except json.JSONDecodeError as error:
        raise AIResponseParsingError(
            "Model response must be a single JSON object with no surrounding "
            "prose: " + sanitize_provider_text(str(error))
        ) from error

    remainder = text[end:].strip()
    if remainder:
        raise AIResponseParsingError(
            "Model response must contain exactly one JSON object with no trailing content"
        )

    if not isinstance(value, dict):
        raise AIResponseParsingError(
            f"Model response must be a single JSON object, got {type(value).__name__}"
        )

    # Re-serialize for a stable loads path while preserving original parse.
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def ensure_mapping(value: Any, *, label: str) -> dict[str, Any]:
    """Return value if it is a dict, otherwise raise a parsing error."""

    if not isinstance(value, dict):
        raise AIResponseParsingError(f"Expected mapping for {label}")
    return value
