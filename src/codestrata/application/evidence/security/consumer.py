"""Consumer contract for security envelopes and projections."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from codestrata.application.evidence.security.capability import CAP_M10, CAP_M11
from codestrata.application.evidence.security.envelope import (
    EnvelopeError,
    SecurityEnvelope,
    parse_envelope_payload,
)
from codestrata.application.evidence.security.projections import (
    project_security_html,
    project_security_json,
    project_security_sarif,
)

FORBIDDEN_HEALTH_KEYS = frozenset(
    {"health_score", "overall_score", "security_score", "healthy", "health_badge"}
)
FORBIDDEN_EXPLOIT_TERMS = ("is exploitable", "remote code execution")
REQUIRED_CAPABILITIES = (CAP_M10, CAP_M11)


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
    if isinstance(value, str):
        lower = value.lower()
        for term in FORBIDDEN_EXPLOIT_TERMS:
            if term in lower:
                raise ConsumerContractError(f"exploitability claim at {path}")


def consume_envelope(payload: object) -> SecurityEnvelope:
    try:
        envelope = parse_envelope_payload(payload)
    except EnvelopeError as error:
        raise ConsumerContractError(str(error)) from error
    except ValidationError as error:
        raise ConsumerContractError("corrupt security envelope") from error
    dumped = envelope.model_dump(mode="json")
    _walk_forbidden(dumped)
    if envelope.body.health_verdict != "none":
        raise ConsumerContractError("security must not supply a health verdict")
    if envelope.body.git_history_scanned:
        raise ConsumerContractError("Git history must not be scanned by default")
    present = {item.capability_id for item in envelope.body.capabilities}
    missing = [item for item in REQUIRED_CAPABILITIES if item not in present]
    if missing:
        raise ConsumerContractError(f"missing capability manifests: {missing}")
    for finding in envelope.body.findings:
        if finding.default_severity != finding.effective_severity:
            raise ConsumerContractError("effective severity silently diverged from YAML default")
        if finding.severity_basis != "yaml_catalog_default":
            raise ConsumerContractError("severity basis is not the YAML catalog")
    _walk_forbidden(project_security_json(envelope))
    _walk_forbidden(project_security_sarif(envelope))
    _walk_forbidden(project_security_html(envelope))
    return envelope


def consume_json_projection(payload: object) -> None:
    if not isinstance(payload, Mapping):
        raise ConsumerContractError("JSON projection must be an object")
    _walk_forbidden(payload)
    if payload.get("health_verdict") != "none":
        raise ConsumerContractError("JSON projection invented a health verdict")
    if payload.get("git_history_scanned") is True:
        raise ConsumerContractError("JSON projection claimed a Git history scan")
