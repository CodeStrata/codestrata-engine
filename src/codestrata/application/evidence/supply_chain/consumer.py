"""Consumer contract for supply-chain envelopes and projections."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from codestrata.application.evidence.supply_chain.capability import CAP_M12, CAP_M13, CAP_M14
from codestrata.application.evidence.supply_chain.envelope import (
    EnvelopeError,
    SupplyChainEnvelope,
    parse_envelope_payload,
)
from codestrata.application.evidence.supply_chain.projections import (
    project_supply_chain_html,
    project_supply_chain_json,
    project_supply_chain_sarif,
)

FORBIDDEN_HEALTH_KEYS = frozenset(
    {"health_score", "overall_score", "security_score", "healthy", "health_badge"}
)
REQUIRED_CAPABILITIES = (CAP_M12, CAP_M13, CAP_M14)


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
        return


def consume_envelope(payload: object) -> SupplyChainEnvelope:
    try:
        envelope = parse_envelope_payload(payload)
    except EnvelopeError as error:
        raise ConsumerContractError(str(error)) from error
    except ValidationError as error:
        raise ConsumerContractError("corrupt supply-chain envelope") from error
    dumped = envelope.model_dump(mode="json")
    _walk_forbidden(dumped)
    if envelope.body.health_verdict != "none":
        raise ConsumerContractError("supply-chain must not supply a health verdict")
    if envelope.body.live_lookup:
        raise ConsumerContractError("canonical evaluation used a live lookup")
    present = {item.capability_id for item in envelope.body.capabilities}
    missing = [item for item in REQUIRED_CAPABILITIES if item not in present]
    if missing:
        raise ConsumerContractError(f"missing capability manifests: {missing}")
    if (
        envelope.body.matching.status.value != "complete"
        and envelope.body.matching.match_count == 0
    ):
        raise ConsumerContractError("unknown matching scope reported zero CVEs")
    _walk_forbidden(project_supply_chain_json(envelope))
    _walk_forbidden(project_supply_chain_sarif(envelope))
    _walk_forbidden({"html": project_supply_chain_html(envelope)})
    return envelope
