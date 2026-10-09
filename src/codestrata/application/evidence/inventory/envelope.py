"""Canonical inventory envelope: deterministic body vs operational metadata.

Engine-local until E01.2/E03.3 publish shared envelope adapters. Unknown fields
and unsupported major versions reject. No tenant, workspace, portfolio or job
identity belongs in the analysis body. Inventory never invents a health score.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.inventory.capability import (
    CAPABILITY_MANIFEST_VERSION,
    CapabilityManifest,
    capability_manifests,
)
from codestrata.application.evidence.inventory.facts import (
    CapabilityCoverageRecord,
    InventoryFactBundle,
)
from codestrata.application.evidence.inventory.registry import (
    InventoryFactIndex,
    register_inventory_facts,
)

INVENTORY_ENVELOPE_SCHEMA = "codestrata.inventory.envelope.v1"
INVENTORY_ENVELOPE_VERSION = "1"
INVENTORY_ENVELOPE_MAJOR = 1
SUPPORTED_ENVELOPE_MAJORS = frozenset({1})


class EnvelopeError(ValueError):
    """Unsupported or corrupt inventory envelope."""


class CapabilityFreshnessRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    status: str
    reason: str
    evaluation_time: str | None = None
    source_digest: str


class InventoryEnvelopeBody(BaseModel):
    """Deterministic comparison body. Operational timestamps stay out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = INVENTORY_ENVELOPE_SCHEMA
    schema_version: str = INVENTORY_ENVELOPE_VERSION
    projection_version: str = CAPABILITY_MANIFEST_VERSION
    repository_id: str
    repository_key: str
    source_revision: str
    working_state_digest: str
    fact_schema_version: str
    facts: dict[str, object]
    coverage: tuple[CapabilityCoverageRecord, ...]
    freshness: tuple[CapabilityFreshnessRecord, ...]
    capabilities: tuple[CapabilityManifest, ...]
    registered_facts: InventoryFactIndex
    executed_repository_code: bool = False
    ci_execution_observed: bool = False
    descriptive_only: bool = True
    health_verdict: str = "none"
    limitations: tuple[str, ...] = ()

    @field_validator("facts", mode="before")
    @classmethod
    def require_mapping(cls, value: object) -> dict[str, object]:
        if not isinstance(value, Mapping):
            raise EnvelopeError("facts must be an object")
        return dict(value)


class InventoryOperationalMetadata(BaseModel):
    """Run metadata excluded from semantic comparison and body digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    generated_at: str | None = None
    duration_ms: float | None = Field(default=None, ge=0.0)
    signature: str | None = None


class InventoryEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = INVENTORY_ENVELOPE_SCHEMA
    schema_version: str = INVENTORY_ENVELOPE_VERSION
    body: InventoryEnvelopeBody
    body_digest: str
    operational: InventoryOperationalMetadata = Field(default_factory=InventoryOperationalMetadata)

    def canonical_body(self) -> dict[str, object]:
        return self.body.model_dump(mode="json")


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_body(body: InventoryEnvelopeBody) -> str:
    payload = body.model_dump(mode="json")
    return hashlib.sha256(_stable_dumps(payload).encode("utf-8")).hexdigest()


def _freshness(bundle: InventoryFactBundle) -> tuple[CapabilityFreshnessRecord, ...]:
    records = []
    for coverage in bundle.coverage:
        records.append(
            CapabilityFreshnessRecord(
                capability_id=coverage.capability_id,
                status="not_applicable",
                reason="inventory_is_not_time_sensitive",
                source_digest=bundle.working_state_digest,
            )
        )
    return tuple(records)


def seal_inventory_envelope(
    bundle: InventoryFactBundle,
    *,
    operational: InventoryOperationalMetadata | None = None,
    capabilities: Sequence[CapabilityManifest] | None = None,
) -> InventoryEnvelope:
    index = register_inventory_facts(bundle)
    limitations = list(bundle.limitations)
    if "no_invented_health_score" not in limitations:
        limitations.append("no_invented_health_score")
    if "inventory_envelope_is_engine_local" not in limitations:
        limitations.append("inventory_envelope_is_engine_local")
    body = InventoryEnvelopeBody(
        repository_id=bundle.repository_id,
        repository_key=bundle.repository_key,
        source_revision=bundle.source_revision,
        working_state_digest=bundle.working_state_digest,
        fact_schema_version=bundle.schema_version,
        facts=bundle.to_canonical_dict(),
        coverage=bundle.coverage,
        freshness=_freshness(bundle),
        capabilities=tuple(capabilities or capability_manifests()),
        registered_facts=index,
        executed_repository_code=bundle.executed_repository_code,
        ci_execution_observed=bundle.ci_execution_observed,
        limitations=tuple(sorted(set(limitations))),
    )
    return InventoryEnvelope(
        body=body,
        body_digest=digest_body(body),
        operational=operational or InventoryOperationalMetadata(),
    )


def parse_envelope_payload(payload: object) -> InventoryEnvelope:
    """Reject unknown fields and unsupported major versions."""

    if not isinstance(payload, Mapping):
        raise EnvelopeError("envelope must be an object")
    schema = str(payload.get("schema_name") or "")
    version = str(payload.get("schema_version") or "")
    if schema != INVENTORY_ENVELOPE_SCHEMA:
        raise EnvelopeError(f"unsupported envelope schema: {schema}")
    major_text = version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as error:
        raise EnvelopeError(f"unsupported envelope version: {version}") from error
    if major not in SUPPORTED_ENVELOPE_MAJORS:
        raise EnvelopeError(f"unsupported envelope major version: {version}")
    try:
        envelope = InventoryEnvelope.model_validate(payload)
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError("corrupt inventory envelope") from error
    expected = digest_body(envelope.body)
    if envelope.body_digest != expected:
        raise EnvelopeError("envelope body_digest does not match canonical body")
    if envelope.body.health_verdict != "none":
        raise EnvelopeError("inventory envelope must not carry a health verdict")
    return envelope
