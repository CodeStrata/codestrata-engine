"""Consumer contract for inventory envelopes and projections.

A consumer validates standard schemas and relationships without recomputing
coverage or importing parser internals (npm, surfaces, GitHub Actions YAML).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from codestrata.application.evidence.inventory.envelope import (
    EnvelopeError,
    InventoryEnvelope,
    parse_envelope_payload,
)
from codestrata.application.evidence.inventory.facts import CAP_M01, CAP_M02, CAP_M03, CAP_M04
from codestrata.application.evidence.inventory.projections import (
    JSON_PROJECTION_SCHEMA,
    project_inventory_html,
    project_inventory_json,
    project_inventory_sarif,
)

FORBIDDEN_HEALTH_KEYS = frozenset(
    {
        "health_score",
        "overall_score",
        "inventory_score",
        "healthy",
        "health_badge",
    }
)
REQUIRED_CAPABILITIES = (CAP_M01, CAP_M02, CAP_M03, CAP_M04)


class ConsumerContractError(ValueError):
    """Projection or envelope failed the consumer contract."""


def _walk_forbidden_health(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_HEALTH_KEYS:
                raise ConsumerContractError(f"invented health field at {path}.{key_text}")
            _walk_forbidden_health(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_forbidden_health(item, path=f"{path}[{index}]")


def consume_envelope(payload: object) -> InventoryEnvelope:
    """Validate an envelope as a consumer: schema, digest, no health score."""

    try:
        envelope = parse_envelope_payload(payload)
    except EnvelopeError as error:
        raise ConsumerContractError(str(error)) from error
    except ValidationError as error:
        raise ConsumerContractError("corrupt inventory envelope") from error
    dumped = envelope.model_dump(mode="json")
    _walk_forbidden_health(dumped)
    if envelope.body.health_verdict != "none":
        raise ConsumerContractError("inventory must not supply a health verdict")
    present = {item.capability_id for item in envelope.body.capabilities}
    missing = [item for item in REQUIRED_CAPABILITIES if item not in present]
    if missing:
        raise ConsumerContractError(f"missing capability manifests: {missing}")
    coverage_ids = {item.capability_id for item in envelope.body.coverage}
    if coverage_ids != present:
        raise ConsumerContractError("coverage records must match declared capabilities")
    if envelope.body.executed_repository_code or envelope.body.ci_execution_observed:
        raise ConsumerContractError("inventory consumer forbids execution claims")
    return envelope


def consume_json_projection(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ConsumerContractError("JSON projection must be an object")
    if payload.get("schema_name") != JSON_PROJECTION_SCHEMA:
        raise ConsumerContractError("unsupported JSON projection schema")
    _walk_forbidden_health(payload)
    if payload.get("health_verdict") != "none":
        raise ConsumerContractError("JSON projection must not invent a health verdict")
    if payload.get("descriptive_only") is not True:
        raise ConsumerContractError("JSON projection must remain descriptive")
    coverage = payload.get("coverage")
    if not isinstance(coverage, list) or len(coverage) != 4:
        raise ConsumerContractError("JSON projection must include M01–M04 coverage")
    return dict(payload)


def consume_html_projection(text: str) -> str:
    if "health_verdict: none" not in text:
        raise ConsumerContractError("HTML projection must state health_verdict: none")
    lowered = text.casefold()
    if "health_score:" in lowered or "overall_score:" in lowered or "badge-healthy" in lowered:
        raise ConsumerContractError("HTML projection must not invent health language")
    if re.search(r"\bhealthy\b", lowered):
        raise ConsumerContractError("HTML projection must not invent health language")
    if "coverage_ratio:" not in text:
        raise ConsumerContractError("HTML projection must copy coverage_ratio")
    return text


def consume_sarif_projection(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ConsumerContractError("SARIF projection must be an object")
    if payload.get("version") != "2.1.0":
        raise ConsumerContractError("unsupported SARIF version")
    _walk_forbidden_health(payload)
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ConsumerContractError("SARIF projection missing runs")
    results = runs[0].get("results") if isinstance(runs[0], Mapping) else None
    if not isinstance(results, list) or len(results) != 4:
        raise ConsumerContractError("SARIF projection must include M01–M04 notes")
    for result in results:
        if not isinstance(result, Mapping):
            raise ConsumerContractError("corrupt SARIF result")
        if result.get("level") != "note":
            raise ConsumerContractError("inventory SARIF must stay informational")
        properties = result.get("properties")
        if isinstance(properties, Mapping) and properties.get("health_verdict") != "none":
            raise ConsumerContractError("SARIF must not invent a health verdict")
    return dict(payload)


def consume_envelope_text(text: str) -> InventoryEnvelope:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConsumerContractError("corrupt inventory envelope JSON") from error
    return consume_envelope(payload)


def project_and_consume(envelope: InventoryEnvelope) -> tuple[dict[str, Any], str, dict[str, Any]]:
    json_payload = project_inventory_json(envelope)
    html = project_inventory_html(envelope)
    sarif = project_inventory_sarif(envelope)
    return (
        consume_json_projection(json_payload),
        consume_html_projection(html),
        consume_sarif_projection(sarif),
    )
