"""Consumer contract for testing envelopes and projections.

Consumers validate schema and relationships. They must not treat association
as runtime coverage or a missing report as 0% code coverage.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from codestrata.application.evidence.testing.capability import CAP_M19, CAP_M20, CAP_M21
from codestrata.application.evidence.testing.envelope import (
    EnvelopeError,
    TestingEnvelope,
    parse_envelope_payload,
)
from codestrata.application.evidence.testing.projections import (
    project_testing_html,
    project_testing_json,
    project_testing_sarif,
)

FORBIDDEN_RUNTIME_KEYS = frozenset(
    {
        "runtime_coverage_percent",
        "measured_coverage",
        "code_coverage_percent",
        "tests_passed",
        "tests_failed",
        "health_score",
        "overall_score",
        "quality_score",
        "healthy",
        "health_badge",
    }
)
REQUIRED_CAPABILITIES = (CAP_M19, CAP_M20, CAP_M21)


class ConsumerContractError(ValueError):
    """Projection or envelope failed the consumer contract."""


def _walk_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_RUNTIME_KEYS:
                raise ConsumerContractError(f"invented runtime field at {path}.{key_text}")
            _walk_forbidden(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_forbidden(item, path=f"{path}[{index}]")


def consume_envelope(payload: object) -> TestingEnvelope:
    try:
        envelope = parse_envelope_payload(payload)
    except EnvelopeError as error:
        raise ConsumerContractError(str(error)) from error
    except ValidationError as error:
        raise ConsumerContractError("corrupt testing envelope") from error
    dumped = envelope.model_dump(mode="json")
    _walk_forbidden(dumped)
    if envelope.body.health_verdict != "none":
        raise ConsumerContractError("testing must not supply a health verdict")
    if envelope.body.runtime_coverage is not None:
        raise ConsumerContractError("testing must not claim runtime coverage")
    if envelope.body.coverage_percent is not None:
        raise ConsumerContractError("missing coverage report is not 0% code coverage")
    if envelope.body.live_lookup:
        raise ConsumerContractError("canonical evaluation used a live lookup")
    present = {item.capability_id for item in envelope.body.capabilities}
    missing = [item for item in REQUIRED_CAPABILITIES if item not in present]
    if missing:
        raise ConsumerContractError(f"missing capability manifests: {missing}")
    json_proj = project_testing_json(envelope)
    _walk_forbidden(json_proj)
    html = project_testing_html(envelope)
    if "measured runtime coverage" in html.lower() and "not measured" not in html.lower():
        raise ConsumerContractError("HTML must not label association as runtime coverage")
    if "0% code coverage" in html.lower() and "not 0%" not in html.lower():
        raise ConsumerContractError("HTML must not treat a missing report as 0% coverage")
    _walk_forbidden(project_testing_sarif(envelope))
    return envelope


__all__ = ["ConsumerContractError", "consume_envelope"]
