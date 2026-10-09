"""Three-repeat semantic digests. Only declared operational fields are excluded."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from verification.validation.regression.models import RepeatComparison

JSONValue = Mapping[str, Any] | Sequence[Any] | str | int | float | bool | None


def strip_operational(value: Any, fields: frozenset[str]) -> Any:
    """Drop declared operational keys only; undeclared keys stay in the digest."""

    if isinstance(value, Mapping):
        return {
            str(key): strip_operational(item, fields)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in fields
        }
    if isinstance(value, list | tuple):
        return [strip_operational(item, fields) for item in value]
    return value


def canonical_bytes(payload: Mapping[str, Any], fields: frozenset[str]) -> bytes:
    stripped = strip_operational(payload, fields)
    text = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return text.encode("utf-8")


def semantic_digest(payload: Mapping[str, Any], fields: frozenset[str]) -> str:
    return hashlib.sha256(canonical_bytes(payload, fields)).hexdigest()


def compare_repeats(
    *,
    configuration_id: str,
    payloads: Sequence[Mapping[str, Any]],
    fields: frozenset[str],
    required_repeats: int = 3,
) -> RepeatComparison:
    if len(payloads) < required_repeats:
        return RepeatComparison(
            configuration_id=configuration_id,
            digests=tuple(semantic_digest(item, fields) for item in payloads),
            equal=False,
            detail=f"need {required_repeats} repeats, got {len(payloads)}",
        )
    chosen = tuple(payloads[:required_repeats])
    digests = tuple(semantic_digest(item, fields) for item in chosen)
    equal = len(set(digests)) == 1
    detail = "equal" if equal else f"mismatch {digests}"
    return RepeatComparison(
        configuration_id=configuration_id,
        digests=digests,
        equal=equal,
        detail=detail,
    )


def full_incremental_parity(
    full_payload: Mapping[str, Any],
    incremental_payload: Mapping[str, Any],
    fields: frozenset[str],
) -> bool:
    return semantic_digest(full_payload, fields) == semantic_digest(incremental_payload, fields)
