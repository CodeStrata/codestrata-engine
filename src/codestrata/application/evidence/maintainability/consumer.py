"""Consumer contract for maintainability envelopes and projections.

Consumers validate schema and relationships. They must not recompute hotspot
rank, invent an opaque score, or treat age as a security proof.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from codestrata.application.evidence.maintainability.capability import CAP_M22, CAP_M23
from codestrata.application.evidence.maintainability.envelope import (
    EnvelopeError,
    MaintainabilityEnvelope,
    parse_envelope_payload,
)
from codestrata.application.evidence.maintainability.projections import (
    project_maintainability_html,
    project_maintainability_json,
    project_maintainability_sarif,
)
from codestrata.domain.contracts.enums import ContributorRole, HotspotListKind

FORBIDDEN_SCORE_KEYS = frozenset(
    {
        "health_score",
        "overall_score",
        "quality_score",
        "maintainability_index",
        "maintainability_index_value",
        "cost_to_fix_estimate",
        "costToFix",
        "developer_productivity",
        "failure_probability",
        "hotspot_health",
        "weighted_priority",
        "opaque_priority",
    }
)
REQUIRED_CAPABILITIES = (CAP_M22, CAP_M23)


class ConsumerContractError(ValueError):
    """Projection or envelope failed the consumer contract."""


def _walk_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_SCORE_KEYS:
                raise ConsumerContractError(f"invented score field at {path}.{key_text}")
            _walk_forbidden(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_forbidden(item, path=f"{path}[{index}]")


def consume_envelope(payload: object) -> MaintainabilityEnvelope:
    try:
        envelope = parse_envelope_payload(payload)
    except EnvelopeError as error:
        raise ConsumerContractError(str(error)) from error
    except ValidationError as error:
        raise ConsumerContractError("corrupt maintainability envelope") from error
    dumped = envelope.model_dump(mode="json")
    _walk_forbidden(dumped)
    body = envelope.body
    if body.health_verdict != "none":
        raise ConsumerContractError("maintainability must not supply a health verdict")
    if body.opaque_score is not None:
        raise ConsumerContractError("maintainability must not supply an opaque score")
    if body.runtime_failure_probability is not None:
        raise ConsumerContractError("hotspot rank is not runtime failure probability")
    if body.cost_to_fix is not None:
        raise ConsumerContractError("maintainability must not estimate cost-to-fix")
    if body.developer_blame is not None:
        raise ConsumerContractError("maintainability must not emit developer blame")
    if body.live_lookup:
        raise ConsumerContractError("canonical evaluation used a live lookup")
    present = {item.capability_id for item in body.capabilities}
    missing = [item for item in REQUIRED_CAPABILITIES if item not in present]
    if missing:
        raise ConsumerContractError(f"missing capability manifests: {missing}")
    for item in body.complete_hotspots:
        if item.list_kind is not HotspotListKind.COMPLETE_COMPARABLE:
            raise ConsumerContractError("complete list contains an unranked record")
        ranking = [c.name for c in item.contributors if c.role is ContributorRole.RANKING]
        if ranking != ["complexity", "churn"]:
            raise ConsumerContractError("ranking contributors must be complexity and churn")
        if item.ranking_value is None:
            raise ConsumerContractError("complete hotspot missing ranking_value")
    for item in body.partial_hotspots:
        if item.ranking_value is not None:
            raise ConsumerContractError("partial hotspot entered the comparable ranking")
    _walk_forbidden(project_maintainability_json(envelope))
    _walk_forbidden(project_maintainability_sarif(envelope))
    html = project_maintainability_html(envelope)
    _walk_forbidden({"html": html})
    if "does not compute another priority" not in html:
        raise ConsumerContractError("HTML must not compute another priority")
    return envelope


__all__ = ["FORBIDDEN_SCORE_KEYS", "ConsumerContractError", "consume_envelope"]
