"""Stable serialization helpers for Evidence and Traceability contracts.

Produces JSON-compatible dicts with deterministic key ordering, sanitized
repository-relative paths, and empty optional values omitted. No timestamps or
runtime object representations.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel

from codestrata.domain.traceability.evidence_confidence import EvidenceConfidence
from codestrata.domain.traceability.evidence_ref import EvidenceRef
from codestrata.domain.traceability.graph_reference import GraphReference
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.measurement import EvidenceMeasurement
from codestrata.domain.traceability.snippet import RedactedSnippet
from codestrata.domain.traceability.validators import TraceabilityValidationError

_SUPPORTED_MODELS: tuple[type[BaseModel], ...] = (
    EvidenceLocation,
    RedactedSnippet,
    EvidenceMeasurement,
    GraphReference,
    EvidenceConfidence,
    EvidenceRef,
)


def _is_empty_optional(value: object) -> bool:
    if value is None:
        return True
    if value == () or value == [] or value == {}:
        return True
    return False


def _normalize_json_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return to_stable_dict(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (
            value != value or value in (float("inf"), float("-inf"))
        ):
            raise TraceabilityValidationError("non-finite floats are not JSON-safe")
        return value
    raise TraceabilityValidationError(
        f"unsupported serialization type: {type(value).__name__}"
    )


def to_stable_dict(model: BaseModel, *, omit_empty: bool = True) -> dict[str, Any]:
    """Serialize a traceability model to a deterministic JSON-compatible dict."""

    if not isinstance(model, _SUPPORTED_MODELS):
        raise TraceabilityValidationError(
            f"unsupported model type for stable serialization: {type(model).__name__}"
        )
    raw = model.model_dump(mode="python")
    result: dict[str, Any] = {}
    for key in sorted(raw):
        value = raw[key]
        if omit_empty and _is_empty_optional(value):
            continue
        result[key] = _normalize_json_value(value)
    return result


def from_stable_dict(model_type: type[BaseModel], data: Mapping[str, Any]) -> BaseModel:
    """Parse a stable dict back into a traceability model."""

    if model_type not in _SUPPORTED_MODELS:
        raise TraceabilityValidationError(
            f"unsupported model type for stable parsing: {model_type.__name__}"
        )
    if not isinstance(data, Mapping):
        raise TraceabilityValidationError("stable payload must be a mapping")
    return model_type.model_validate(dict(data))


def evidence_ref_to_stable_dict(ref: EvidenceRef, *, omit_empty: bool = True) -> dict[str, Any]:
    return to_stable_dict(ref, omit_empty=omit_empty)


def evidence_ref_from_stable_dict(data: Mapping[str, Any]) -> EvidenceRef:
    parsed = from_stable_dict(EvidenceRef, data)
    assert isinstance(parsed, EvidenceRef)
    return parsed
