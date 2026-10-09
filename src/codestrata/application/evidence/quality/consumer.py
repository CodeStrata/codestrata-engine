"""Consumer contract for quality envelopes and projections.

Consumers validate schema and relationships. They must not recompute
cyclomatic, nesting or clone formulas or invent a maintainability index.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from codestrata.application.evidence.quality.capability import CAP_M16, CAP_M17, CAP_M18
from codestrata.application.evidence.quality.envelope import (
    EnvelopeError,
    QualityEnvelope,
    parse_envelope_payload,
)
from codestrata.application.evidence.quality.projections import (
    project_quality_html,
    project_quality_json,
    project_quality_sarif,
)

FORBIDDEN_HEALTH_KEYS = frozenset(
    {
        "health_score",
        "overall_score",
        "quality_score",
        "healthy",
        "health_badge",
        "mi",
        "maintainability_index_value",
    }
)
REQUIRED_CAPABILITIES = (CAP_M16, CAP_M17, CAP_M18)


class ConsumerContractError(ValueError):
    """Projection or envelope failed the consumer contract."""


def _walk_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_HEALTH_KEYS:
                raise ConsumerContractError(f"invented health field at {path}.{key_text}")
            _walk_forbidden(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_forbidden(item, path=f"{path}[{index}]")


def consume_envelope(payload: object) -> QualityEnvelope:
    try:
        envelope = parse_envelope_payload(payload)
    except EnvelopeError as error:
        raise ConsumerContractError(str(error)) from error
    except ValidationError as error:
        raise ConsumerContractError("corrupt quality envelope") from error
    dumped = envelope.model_dump(mode="json")
    _walk_forbidden(dumped)
    if envelope.body.health_verdict != "none":
        raise ConsumerContractError("quality must not supply a health verdict")
    if envelope.body.maintainability_index is not None:
        raise ConsumerContractError("quality must not supply a maintainability index")
    if envelope.body.live_lookup:
        raise ConsumerContractError("canonical evaluation used a live lookup")
    present = {item.capability_id for item in envelope.body.capabilities}
    missing = [item for item in REQUIRED_CAPABILITIES if item not in present]
    if missing:
        raise ConsumerContractError(f"missing capability manifests: {missing}")
    _walk_forbidden(project_quality_json(envelope))
    _walk_forbidden(project_quality_sarif(envelope))
    _walk_forbidden({"html": project_quality_html(envelope)})
    return envelope


__all__ = ["ConsumerContractError", "consume_envelope"]
